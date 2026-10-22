#!/usr/bin/env python3
"""Собирает проект HyperFrames для ролика: дубль, камера, субтитры, ассеты.

Всё, что нужно рендеру, кладётся внутрь studio/<имя>/: видео, GSAP, шрифты, звуки,
картинки, данные камеры и субтитров. Во время рендера ничего не качается из сети —
ролик соберётся и без интернета, и через полгода точно таким же.

Решения режиссёра лежат в work/<имя>/director.json: акцентные наезды камеры,
исправления текста, где прятать субтитры. Сама графика ролика — в studio/<имя>/index.html:
его пишет режиссёр (Claude или Codex) под конкретный ролик, и этот скрипт его не перетирает.

Стиль и формат берутся из брифа (work/<имя>/brief.json, его пишет студия): камера-оператор
и группировка субтитров — по стилю, размер сцены — по формату дубля. Без брифа всё как
раньше: камера по умолчанию, субтитры по слову, 1080×1920.

Вариант для A/B — тот же дубль в другом стиле, отдельным проектом studio/<имя>--<стиль>/:
своя страница (work/<имя>/page.<стиль>.py), свои акценты (director.<стиль>.json, если есть).

  .venv/bin/python scripts/compose.py IMG_3279
  .venv/bin/python scripts/compose.py IMG_3279 --variant hormozi
  .venv/bin/python scripts/compose.py IMG_3279 --seconds 10   # кусок для замеров
"""
import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import formats
import materials
import styles
import viz
from common import FONT_DIR, ROOT, WORK_DIR
from track import coverage_violations, css_transform, solve_camera

STUDIO = ROOT / "studio"
VENDOR = STUDIO / "_vendor"
SFX_DIR = ROOT / "presets" / "sfx"
HYPERFRAMES = "hyperframes@0.8.141"     # версия прибита: ролик пересоберётся так же


# Слова, которые в субтитрах не стоят отдельно: цепляются к следующему
CLINGY = {"в", "во", "на", "по", "до", "из", "из-за", "и", "а", "не", "ни", "у", "с", "со",
          "к", "о", "об", "за", "от", "что", "ну", "это", "он", "ты", "при"}
MAX_CHUNK = 15                          # символов в одной вспышке субтитра
MIN_FLASH = 0.15                        # короче не прочесть, а короче входа (0.09) — залипает
# Группировка для режимов субтитров стилей: (слов, символов, пауза-разрыв в секундах)
GROUPING = {"karaoke": (3, 18, 0.35), "phrase": (4, 24, 0.35), "sentence": (8, 42, 0.6)}

PAGE = """<!doctype html>
<html lang="ru" data-resolution="{resolution}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={width}, height={height}" />
    <script src="assets/gsap.min.js"></script>
    <script src="camera.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {width}px; height: {height}px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; }}
      .cam {{ position: absolute; left: 0; top: 0; width: {width}px; height: {height}px; }}
      #aroll {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{duration}"
         data-width="{width}" data-height="{height}">
      <div id="cam-bg" class="cam">
        <video id="aroll" class="clip" src="assets/aroll.mp4" playsinline data-has-audio="true"
               data-start="0" data-duration="{duration}" data-track-index="0"></video>
      </div>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      const cam = window.CAMERA, step = 1 / window.CAMERA_FPS;
      tl.set(".cam", {{ transformOrigin: "0 0", x: cam[0][0], y: cam[0][1], scale: cam[0][2] }}, 0);
      tl.to(".cam", {{
        keyframes: cam.slice(1).map(([x, y, s]) => ({{ x, y, scale: s, duration: step, ease: "none" }})),
      }}, 0);
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


CHIN_GAP = 50           # отступ субтитров от подбородка, px сцены (Валера 16.10: «сабы ниже подбородка, с отступом»)
LANE_LOW = 1370         # ниже — ник и подпись Instagram (formats.GREY_ZONES)
LANE_HIGH = 270         # выше — вкладки TikTok


def caption_lane(project: Path, sc: dict) -> str:
    """Одна высота субтитров на ролик — по тому, где в этом ролике бывает лицо (16.10.2026).

    Валера: «субтитры не должны залезать в лицо… могут быть и надо мной, и подо мной, как в IMG_1799», «не в каждой
    фразе, а выбрал, как удачнее преимущественно располагать, чтобы текст не летал вверх-вниз». Поэтому: подбородок
    по слежению с камерой (90-й процентиль за ролик) + CHIN_GAP; не помещается над ником — линия над головой.
    Редкие окна, где линию нужно сменить, режиссёр задаёт сам: director.json → caption_lanes [[от, до, top], …].
    Где субтитр всё же лёг на лицо — краснеет verify_page. Вернёт строку для вывода или "".
    """
    import numpy as np
    from kit import CAPTION_BOX, CAPTION_SIZE
    if sc["fmt"] != "9:16":
        return ""
    import verify_page
    faces = verify_page.face_track(project)
    left, _, base = CAPTION_BOX["9:16"][sc["caps"].get("position", "chest")]
    size = round(CAPTION_SIZE.get(sc["caps"]["mode"], 52) * float(sc["caps"].get("size", 1.0)))
    cap_h = round(size * 1.15 * (1 if sc["caps"]["mode"] in ("words", "karaoke") else 2)) + 10
    lane, why = base, "по стилю"
    if faces:
        chin = float(np.percentile([f[4] for f in faces], 90))
        crown = float(np.percentile([f[2] for f in faces], 10))
        below = max(base, round(chin + CHIN_GAP))
        above = round(crown - CHIN_GAP - cap_h)
        if below + cap_h <= LANE_LOW:
            lane, why = below, f"под подбородком (он до y {chin:.0f})"
        elif above >= LANE_HIGH:
            lane, why = above, f"над головой: под подбородком (y {chin:.0f}) не помещается до ника"
        else:
            lane, why = LANE_LOW - cap_h, f"⚠ лицо крупное (подбородок y {chin:.0f}, макушка {crown:.0f}) — линия у ника"
    windows = sc["director"].get("caption_lanes") or []
    for c in sc["chunks"]:
        c["y"] = lane
        for a, b, top in windows:
            if a <= c["t0"] < b:
                c["y"] = int(top)
    extra = f", своих окон {len(windows)}" if windows else ""
    return f"субтитры на y {lane} — {why}{extra}"


def caption_chunks(words: list, director: dict, duration: float, mode: str = "words",
                   case: str = "lower", scenes: list | None = None) -> list:
    """Бегущие субтитры как в референсах: по слову-два, без знаков, предлоги не висят.

    Возвращает [{t0, t1, text, accent}] на шкале дубля. Где смысл несёт крупная
    типографика (hide_captions), вспышки убираются — текст на экране не двоится.

    mode — режим стиля: words (по слову-два, как было), karaoke (2–3 слова, у каждого
    своё время подсветки — поле words), phrase (до 4 слов), sentence (предложение до 8
    слов), none. case natural оставляет регистр и знаки препинания как сказано.

    scenes — стыки сборки (aroll.json → scenes, scripts/pack.py): там меняется сцена и человек в кадре, поэтому
    вспышка не собирает слова с двух сторон стыка и не висит через него.
    """
    if mode == "none":
        return []
    if mode not in ("words", *GROUPING):
        raise ValueError(f"Режим субтитров «{mode}» не знаю")
    fixes = {int(k): v for k, v in (director.get("text_fixes") or {}).items()}
    # слова режиссёра — без знаков по краям, как слова субтитров: «Индии.» в accent_words не совпадало с «индии»
    # на экране, и из восьми ключевых слов IMG_3292 подсвечивалось одно; «I.» в keep_case — и «Пётр I» шёл как «i»
    edge = lambda x: re.sub(r"^[«\"]+|[.,!?;:«»\"]+$", "", x.strip())      # noqa: E731
    keep_case = {edge(w) for w in director.get("keep_case") or []}
    # «Пётр I» в списке — оба слова; однобуквенные («I», «в») не подсвечиваются сами по себе
    accents = {part for w in director.get("accent_words") or [] for part in edge(w).lower().split() if len(part) > 1}

    tokens = []
    for i, w in enumerate(words):
        text = fixes.get(i, w["word"]).strip()
        if not text:
            continue
        bare = re.sub(r"^[«\"]+|[.,!?;:«»\"]+$", "", text)
        if re.fullmatch(r"[-–—]*", bare):
            continue                        # отдельное тире — не слово, вспышкой не показывается
        stop = bool(re.search(r"[.!?…]+[»\"]*$", text))
        pause_mark = bool(re.search(r"[,;:—]+[»\"]*$", text))
        raw = bare                              # как сказано: регистр — для склейки «Пётр I»
        if case == "natural":
            bare = re.sub(r"^[«\"]+", "", text)    # регистр и знаки как сказано
        else:
            bare = bare if bare in keep_case else bare.lower()
        # whisper рвёт «по-индийски» на «по» + «-индийски», а «80+» на «80» + «+»:
        # хвост приклеивается к своему слову
        if tokens and (bare.startswith("-") or bare in ("+", "%")):
            tokens[-1]["text"] += bare
            tokens[-1]["end"] = w["end"]
            continue
        # «Пётр I», «Екатерина II» — номер одной вспышкой с именем, а не отдельной «I» (19.10.2026, IMG_3292). Регистр —
        # как сказано (raw): у партитуры аналитика имя не в keep_case, и «петр» в нижнем регистре номер не узнавал
        if (tokens and re.fullmatch(r"[IVX]{1,4}", raw) and re.fullmatch(r"[А-ЯЁA-Z][а-яёa-z]{2,}", tokens[-1]["raw"])
                and not tokens[-1]["stop"]):
            tokens[-1].update(text=f'{tokens[-1]["text"]} {raw}', end=w["end"], stop=stop, mark=pause_mark)
            continue
        tokens.append({"text": bare, "raw": raw, "start": w["start"], "end": w["end"], "stop": stop,
                       "mark": pause_mark})

    scenes = sorted(float(x) for x in scenes or [])
    apart = lambda a, b: any(a["end"] - 0.05 <= x <= b["start"] + 0.05 for x in scenes)   # noqa: E731
    chunks, i = [], 0
    while i < len(tokens):
        group = [tokens[i]]
        if mode == "words":
            while (i + len(group) < len(tokens) and group[-1]["text"].lower() in CLINGY
                   and not apart(group[-1], tokens[i + len(group)])
                   and len(" ".join(t["text"] for t in group)) + 1
                   + len(tokens[i + len(group)]["text"]) <= MAX_CHUNK + 4):
                group.append(tokens[i + len(group)])
        else:
            most, chars, gap = GROUPING[mode]
            while i + len(group) < len(tokens):
                last, nxt = group[-1], tokens[i + len(group)]
                if last["stop"] or nxt["start"] - last["end"] >= gap or apart(last, nxt):
                    break                   # конец фразы: точка, настоящая пауза или стык сцен
                if len(group) >= most or len(" ".join(t["text"] for t in group)) + 1 + len(nxt["text"]) > chars:
                    # предлог в хвосте строки не оставляем — уносим его в следующую
                    if len(group) > 1 and last["text"].lower() in CLINGY:
                        group.pop()
                    break
                if last["mark"] and len(group) >= max(2, most // 2):
                    break                   # запятая — хорошее место для разрыва
                group.append(nxt)
        i += len(group)
        chunk = {"t0": round(group[0]["start"], 3), "end": group[-1]["end"],
                 "text": " ".join(t["text"] for t in group),
                 "accent": any(part in accents for t in group for part in t["text"].lower().split())}
        if mode == "karaoke":
            chunk["words"] = [{"text": t["text"], "t0": round(t["start"], 3)} for t in group]
        chunks.append(chunk)

    for k, chunk in enumerate(chunks):
        nxt = chunks[k + 1]["t0"] if k + 1 < len(chunks) else duration
        cut = next((x for x in scenes if x >= chunk["end"] - 0.05), duration)
        # держим до следующей вспышки, но не дольше секунды тишины после слова и не через стык сцен
        chunk["t1"] = round(min(nxt, chunk.pop("end") + 1.0, duration, max(cut, chunk["t0"] + MIN_FLASH)), 3)

    # Whisper ставит соседние слова вплотную («кто» и «не» через 20 мс). Такая вспышка
    # короче своего входа: уход срабатывал посреди появления, и при покадровом рендере
    # слово висело до конца ролика, а следующие бежали поверх (IMG_3317, 3320 и ещё три).
    # Короткая сливается со следующей — текст остаётся на своём месте по времени.
    def join(into: dict, other: dict):
        into.update(text=into["text"] + " " + other["text"], t1=other["t1"],
                    accent=into["accent"] or other["accent"])
        if "words" in into:
            into["words"] = into["words"] + other["words"]

    merged = []
    for chunk in chunks:
        if (merged and merged[-1]["t1"] - merged[-1]["t0"] < MIN_FLASH
                and not any(merged[-1]["t0"] < x <= chunk["t0"] for x in scenes)):
            join(merged[-1], chunk)
        else:
            merged.append(chunk)
    if len(merged) > 1 and merged[-1]["t1"] - merged[-1]["t0"] < MIN_FLASH:
        last = merged.pop()                 # короткая последняя — к предыдущей
        join(merged[-1], last)
    chunks = merged

    # Вспышка, которая лишь заходит хвостом в зону типографики, укорачивается до её
    # начала; выкидывается только та, что начинается уже внутри зоны. Иначе пропадают
    # слова прямо перед ударом — «равенства» перед огромным «=».
    visible = []
    for chunk in chunks:
        for a, b in director.get("hide_captions") or []:
            if a < chunk["t1"] and chunk["t0"] < b:
                if chunk["t0"] < a - 0.12:
                    chunk["t1"] = round(a, 3)
                else:
                    chunk = None
                    break
        if chunk:
            visible.append(chunk)
    return visible


def copy_if_newer(src: Path, dst: Path):
    """Ассет проекта — жёсткая ссылка на файл из work/ или presets/, а не вторая копия.

    Раньше дубль и вырезка каждого ролика лежали дважды (1,9 ГБ на 15 роликов). Ссылка места
    не занимает, а HyperFrames ассеты только читает. Пересобранный дубль — новый файл, ссылка
    на старый перестаёт совпадать и заменяется. Сослаться нельзя (другой диск) — копия.
    """
    fresh_copy = False
    if dst.exists():
        if dst.samefile(src):
            return
        fresh_copy = (dst.stat().st_mtime >= src.stat().st_mtime
                      and dst.stat().st_size == src.stat().st_size)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f".{dst.name}.link")
    tmp.unlink(missing_ok=True)
    try:
        try:
            os.link(src, tmp)                     # прежняя копия тоже становится ссылкой
        except OSError:
            if fresh_copy:
                return                            # ссылки не бывает, а копия свежая
            shutil.copy2(src, tmp)
        tmp.replace(dst)
    finally:
        tmp.unlink(missing_ok=True)


def project_name(stem: str, variant: str | None = None) -> str:
    """studio/<имя>/ — основной проект, studio/<имя>--<стиль>/ — вариант для A/B."""
    return f"{stem}--{variant}" if variant else stem


# Варианты A/B, которые проверяют приём, а не стиль: тот же стиль, что у основного ролика, своя страница
# work/<имя>/page.<вариант>.py → studio/<имя>--<вариант>/. Список закрытый — опечатка в имени стиля не должна
# молча собрать ролик в стиле по умолчанию.
TEST_VARIANTS = {"sfx": "тихие звуки на переходах и влётах текста — тест удержания (16.10.2026, rules.md п.9)",
                 "music": "еле слышная фоновая музыка (лоу-фай из фонотеки YouTube) — тест удержания (17.10.2026, rules.md п.9)",
                 "montage": "сборка montage.py: обязательное ставится само — вспышка хука, склейки, звуки, музыка (19.10.2026)",
                 "manual": "партитура вручную (score.manual.json → score.py) — эталон для аналитика (19.10.2026, этап 3)",
                 "auto": "партитура аналитика (analyst.py → score.auto.json → score.py): монтаж без page.py (19.10.2026, этап 3)"}


def ruling_style(stem: str, variant: str | None = None) -> dict | None:
    """Стиль, по которому собирается проект: вариант, стиль брифа или None (как раньше)."""
    if variant in TEST_VARIANTS:
        variant = None                    # приём проверяется в стиле основного ролика
    if variant:
        brief = styles.load_brief(stem)
        overrides = brief.get("overrides") if brief.get("style") == variant else None
        return styles.effective(styles.load_style(variant), overrides)
    brief = styles.load_brief(stem)
    if not brief.get("exists") and not own_project_style(stem):
        return None
    return styles.effective(styles.load_style(brief["style"]), brief.get("overrides"))


def own_project_style(stem: str) -> bool:
    """Ролик без своего brief.json собирается по стилю своего проекта, если это не проект по умолчанию.

    Студия пишет brief.json при старте монтажа, а ролик, смонтированный из терминала, его не имел — и заказ «Вкудесника»
    (20.10.2026) молча собрался субтитрами и камерой умолчаний скилла, а не стилем проекта (проект — граница, 14.10).
    У проекта по умолчанию (Антишкола) ролики без брифа остаются как были: среди них эталоны серии (IMG_3292, IMG_3303),
    и их пересборка не должна менять камеру и субтитры без разговора с Валерой.
    """
    import projects
    try:
        project = projects.of(stem)
    except projects.ProjectError:
        return False
    return project.home.name != projects.DEFAULT and bool(project.config["brief"].get("style"))


class SceneError(ValueError):
    """Сцену не собрать: нет подготовки, битый director.json или камера вылезла за кадр."""


def scene(stem: str, variant: str | None = None, seconds: float | None = None) -> dict:
    """Камера и субтитры ролика с решениями режиссёра и ручными правками студии.

    Ручные правки (work/<имя>/timeline.json, timeline.py) ложатся поверх director.json
    последними: page.py агента director.json перезаписывает, а правки человека живут отдельно
    и не теряются. Тем же расчётом пользуется предпросмотр студии — то, что видно на дорожках,
    и то, что уйдёт в рендер, считается одной функцией.
    """
    import timeline
    work = WORK_DIR / stem
    aroll = work / "aroll.mp4"
    faces_path = work / "aroll.faces.json"
    for need, hint in ((aroll, "scripts/prep.py"), (faces_path, "scripts/track.py")):
        if not need.exists():
            raise SceneError(f"Нет {need.relative_to(ROOT)} — сначала {hint}")

    meta = load_json(work / "aroll.json")
    faces = load_json(faces_path)
    director = load_json(work / "director.json", {})
    if variant and (work / f"director.{variant}.json").exists():
        director = load_json(work / f"director.{variant}.json")
    try:
        edits = timeline.load_edits(stem) if not variant else {}
    except timeline.EditError as e:
        raise SceneError(f"✗ {e}")
    director = timeline.apply_director(director, edits)
    words = (load_json(work / "aroll.words.json", {}) or {}).get("words", [])
    width, height, fps = faces["width"], faces["height"], faces["fps"]
    duration = meta["duration"] if seconds is None else min(seconds, meta["duration"])
    fmt = meta.get("format") or formats.of_size(width, height) or formats.DEFAULT
    try:
        style = ruling_style(stem, variant)
    except styles.StyleError as e:
        raise SceneError(f"✗ {e}")
    caps = styles.kit_captions(style) if style else {"mode": "words", "case": "lower"}

    # камера пересчитывается с акцентами режиссёра; полный кадр проверяется ещё раз
    # склейки дубля: камера решается по кускам и не «переезжает» через рез
    cuts, acc = [], 0.0
    for s0, s1 in meta.get("segments", [])[:-1]:
        acc += s1 - s0
        cuts.append(int(round(acc * fps)))
    try:
        camera = solve_camera(faces, cfg=styles.camera_cfg(style) if style else None,
                              punches=director.get("punches"), cuts=cuts)
    except ValueError as e:
        raise SceneError(f"✗ director.json: {e}")
    if coverage_violations(camera, width, height):
        raise SceneError("Камера вылезла за край кадра — сборка остановлена (так быть не должно)")
    frames = camera[:int(round(duration * fps)) + 1]
    transforms = [[round(v, 3) for v in css_transform(z, cx, cy, width, height)]
                  for z, cx, cy in frames]
    chunks = caption_chunks(words, director, duration, caps["mode"], caps["case"], scenes=meta.get("scenes"))
    return {"meta": meta, "director": director, "edits": edits, "words": words, "style": style,
            "caps": caps, "fmt": fmt, "width": width, "height": height, "fps": fps,
            "duration": duration, "frames": frames, "chunks": chunks,
            "camera_js": f"window.CAMERA_FPS = {fps:g};\nwindow.CAMERA = {json.dumps(transforms)};\n",
            "captions_js": "window.CAPTIONS = " + json.dumps(chunks, ensure_ascii=False) + ";\n"}


def compose(stem: str, seconds: float | None = None, fresh: bool = False,
            variant: str | None = None) -> Path:
    import timeline
    try:
        sc = scene(stem, variant, seconds)
    except SceneError as e:
        sys.exit(str(e))
    work = WORK_DIR / stem
    aroll = work / "aroll.mp4"
    meta, style, caps, fmt = sc["meta"], sc["style"], sc["caps"], sc["fmt"]
    width, height, fps, duration, frames, chunks = (sc["width"], sc["height"], sc["fps"],
                                                    sc["duration"], sc["frames"], sc["chunks"])

    project = STUDIO / project_name(stem, variant)
    assets = project / "assets"
    for sub in ("img", "fonts", "sfx"):
        (assets / sub).mkdir(parents=True, exist_ok=True)
    # "hq" в edit.json (15.10, IMG_1799): страница берёт дубль и вырезку с запасом под зум камеры —
    # prep.py --hq и matte.make_cutout по нему. Флаг есть, а файлов нет — громкий отказ, не тихая мыльность
    # Вырезки может не быть вовсе: с 22.10.2026 маска считается после страницы и только по её окнам (matte.py
    # --windows page). Чего не хватает странице, громко скажет verify_page — по окнам «человек поверх»
    picture, cutout = aroll, work / "aroll.cutout.webm"
    if (load_json(work / "edit.json", {}) or {}).get("hq"):
        picture, cutout = work / "aroll.hq.mp4", work / "aroll.hq.cutout.webm"
        if not picture.exists():
            sys.exit(f"✗ в edit.json стоит hq, а {picture.relative_to(ROOT)} нет — prep.py --hq по исходнику {stem}")
    copy_if_newer(picture, assets / "aroll.mp4")
    if cutout.exists():
        copy_if_newer(cutout, assets / "cutout.webm")
        # где вырезка посчитана (matte.cut_windows) — рядом с ней: verify_page сверяет с окнами страницы. Нет записи —
        # вырезка во всю длину (до 22.10.2026)
        covered = work / "aroll.cutout.json"
        if covered.exists():
            shutil.copy2(covered, assets / "cutout.json")
        else:
            (assets / "cutout.json").unlink(missing_ok=True)
    copy_if_newer(VENDOR / "gsap.min.js", assets / "gsap.min.js")
    # все шрифты presets/fonts — жёсткими ссылками, места не занимают: в монтажной шрифт слоя
    # или субтитров меняется на любой из них, и страница должна найти его без пересборки
    # .otf тоже: шрифты заказчика бывают только в нём (SF Pro, «СлаваМонтаж» 22.10.2026), а DESIGN.md их пускает
    for src in sorted([*FONT_DIR.glob("*.ttf"), *FONT_DIR.glob("*.otf")]):
        copy_if_newer(src, assets / "fonts" / src.name)
    for src in (work / "downloads").glob("*"):
        if src.suffix.lower() in (".jpg", ".jpeg", ".png", ".svg", ".webp"):
            copy_if_newer(src, assets / "img" / src.name)
    for src in SFX_DIR.glob("*.mp3"):
        copy_if_newer(src, assets / "sfx" / src.name)
    # материалы человека (work/<имя>/materials/, студия → «Материалы»): всё — в assets/materials/,
    # картинки ещё и в assets/img/, рядом с найденными ИИ: helpers kit берут картинку по имени оттуда
    for src in sorted((work / "materials").glob("*")):
        if src.name.startswith(".") or not materials.kind_of(src.name):
            continue
        (assets / "materials").mkdir(exist_ok=True)
        copy_if_newer(src, assets / "materials" / src.name)
        if materials.kind_of(src.name) == "image":
            copy_if_newer(src, assets / "img" / src.name)
    for src in (work / "footage").glob("*.mp4"):                # ИИ-футажи Flow (footage.py), без оригиналов
        (assets / "footage").mkdir(exist_ok=True)
        copy_if_newer(src, assets / "footage" / src.name)
    for src in (work / "manim").glob("*.mp4"):                  # «доска»: клипы ManimGX (manim_clip.py)
        (assets / "manim").mkdir(exist_ok=True)
        copy_if_newer(src, assets / "manim" / src.name)

    (project / "camera.js").write_text(sc["camera_js"], encoding="utf-8")
    lane = caption_lane(project, sc)
    if lane:
        print(f"  → {lane}")
    (project / "captions.js").write_text("window.CAPTIONS = " + json.dumps(sc["chunks"], ensure_ascii=False) + ";\n",
                                         encoding="utf-8")

    page = project / "index.html"
    if fresh or not page.exists():
        page.write_text(PAGE.format(width=width, height=height, duration=f"{duration:.3f}",
                                    resolution=formats.get(fmt)["resolution"]),
                        encoding="utf-8")
    # ручные правки монтажной (layers.js + edits.js): страница подключает их сама, если её собрал
    # свежий kit, а старую дополняет timeline.patch_page — без перезаписи графики
    copy_if_newer(timeline.LAYERS_JS, project / "layers.js")
    (project / "fx.js").unlink(missing_ok=True)       # эффекты света 16.10.2026 убраны
    (project / "edits.js").write_text(timeline.edits_js(sc["edits"]), encoding="utf-8")
    html = page.read_text(encoding="utf-8")
    try:
        patched = timeline.patch_page(html, sc["edits"], fps)
    except ValueError as e:
        sys.exit(f"✗ ручные правки студии (work/{stem}/timeline.json): {e}")
    if patched != html:
        page.write_text(patched, encoding="utf-8")
    # визуализации страницы (viz.py): элементы каталога, KaTeX, D3 и карта — ссылками, офлайн
    for rel, src in viz.assets_for(page.read_text(encoding="utf-8"), project).items():
        copy_if_newer(src, project / rel)
    (project / "hyperframes.json").write_text(json.dumps({
        "paths": {"assets": "assets"}, "media": {"autoProxy": True}}, indent=2), encoding="utf-8")
    (project / "package.json").write_text(json.dumps({
        "name": f"reels-{project_name(stem, variant).lower()}", "private": True, "type": "module",
        "scripts": {"dev": f"npx --yes {HYPERFRAMES} preview",
                    "check": f"npx --yes {HYPERFRAMES} check",
                    "render": f"npx --yes {HYPERFRAMES} render"}}, indent=2), encoding="utf-8")
    zooms = [z for z, _, _ in frames]
    if style:
        print(f"  → стиль: {style['name']}, формат {fmt}")
    print(f"  → камера: зум {min(zooms):.2f}–{max(zooms):.2f}, кадр полный на всех {len(frames)}")
    print(f"  → субтитров: {len(chunks)} вспышек ({caps['mode']})")
    return project


def main():
    ap = argparse.ArgumentParser(description="Проект HyperFrames из подготовленного дубля")
    ap.add_argument("stem", help="имя исходника без расширения, например IMG_3279")
    ap.add_argument("--seconds", type=float, help="собрать только начало (для замеров)")
    ap.add_argument("--fresh", action="store_true",
                    help="перезаписать index.html заготовкой (графика режиссёра пропадёт)")
    ap.add_argument("--variant", help="стиль варианта для A/B: проект studio/<имя>--<стиль>/")
    args = ap.parse_args()
    project = compose(args.stem, args.seconds, args.fresh, args.variant)
    print(f"  → проект: {project.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
