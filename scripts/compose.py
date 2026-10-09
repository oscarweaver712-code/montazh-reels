#!/usr/bin/env python3
"""Собирает проект HyperFrames для ролика: дубль, камера, субтитры, ассеты.

Всё, что нужно рендеру, кладётся внутрь studio/<имя>/: видео, GSAP, шрифты, звуки,
картинки, данные камеры и субтитров. Во время рендера ничего не качается из сети —
ролик соберётся и без интернета, и через полгода точно таким же.

Решения режиссёра лежат в work/<имя>/director.json: акцентные наезды камеры,
исправления текста, где прятать субтитры. Сама графика ролика — в studio/<имя>/index.html:
его пишет режиссёр (Claude) под конкретный ролик, и этот скрипт его не перетирает.

  .venv/bin/python scripts/compose.py IMG_3279
  .venv/bin/python scripts/compose.py IMG_3279 --seconds 10   # кусок для замеров
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import FONT_DIR, ROOT, WORK_DIR
from track import coverage_violations, css_transform, solve_camera

STUDIO = ROOT / "studio"
VENDOR = STUDIO / "_vendor"
SFX_DIR = ROOT / "presets" / "sfx"
HYPERFRAMES = "hyperframes@0.8.141"     # версия прибита: ролик пересоберётся так же

# Шрифты, которые графика ролика подключает через @font-face (все OFL, с кириллицей)
FONTS = ["Oswald-Bold.ttf", "Manrope-ExtraBold.ttf", "Montserrat-ExtraBold.ttf",
         "AlumniSans-Black.ttf", "CormorantGaramond.ttf", "CormorantGaramond-Italic.ttf",
         "JetBrainsMono.ttf"]

# Слова, которые в субтитрах не стоят отдельно: цепляются к следующему
CLINGY = {"в", "во", "на", "по", "до", "из", "из-за", "и", "а", "не", "ни", "у", "с", "со",
          "к", "о", "об", "за", "от", "что", "ну", "это", "он", "ты", "при"}
MAX_CHUNK = 15                          # символов в одной вспышке субтитра
MIN_FLASH = 0.15                        # короче не прочесть, а короче входа (0.09) — залипает

PAGE = """<!doctype html>
<html lang="ru" data-resolution="portrait">
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


def caption_chunks(words: list, director: dict, duration: float) -> list:
    """Бегущие субтитры как в референсах: по слову-два, без знаков, предлоги не висят.

    Возвращает [{t0, t1, text, accent}] на шкале дубля. Где смысл несёт крупная
    типографика (hide_captions), вспышки убираются — текст на экране не двоится.
    """
    fixes = {int(k): v for k, v in (director.get("text_fixes") or {}).items()}
    keep_case = set(director.get("keep_case") or [])
    accents = {w.lower() for w in director.get("accent_words") or []}

    tokens = []
    for i, w in enumerate(words):
        text = fixes.get(i, w["word"]).strip()
        if not text:
            continue
        bare = re.sub(r"^[«\"]+|[.,!?;:«»\"]+$", "", text)
        if re.fullmatch(r"[-–—]*", bare):
            continue                        # отдельное тире — не слово, вспышкой не показывается
        bare = bare if bare in keep_case else bare.lower()
        # whisper рвёт «по-индийски» на «по» + «-индийски», а «80+» на «80» + «+»:
        # хвост приклеивается к своему слову
        if tokens and (bare.startswith("-") or bare in ("+", "%")):
            tokens[-1]["text"] += bare
            tokens[-1]["end"] = w["end"]
            continue
        tokens.append({"text": bare, "start": w["start"], "end": w["end"]})

    chunks, i = [], 0
    while i < len(tokens):
        group = [tokens[i]]
        while (i + len(group) < len(tokens) and group[-1]["text"].lower() in CLINGY
               and len(" ".join(t["text"] for t in group)) + 1
               + len(tokens[i + len(group)]["text"]) <= MAX_CHUNK + 4):
            group.append(tokens[i + len(group)])
        i += len(group)
        chunks.append({"t0": round(group[0]["start"], 3), "end": group[-1]["end"],
                       "text": " ".join(t["text"] for t in group),
                       "accent": any(t["text"].lower() in accents for t in group)})

    for k, chunk in enumerate(chunks):
        nxt = chunks[k + 1]["t0"] if k + 1 < len(chunks) else duration
        # держим до следующей вспышки, но не дольше секунды тишины после слова
        chunk["t1"] = round(min(nxt, chunk.pop("end") + 1.0, duration), 3)

    # Whisper ставит соседние слова вплотную («кто» и «не» через 20 мс). Такая вспышка
    # короче своего входа: уход срабатывал посреди появления, и при покадровом рендере
    # слово висело до конца ролика, а следующие бежали поверх (IMG_3317, 3320 и ещё три).
    # Короткая сливается со следующей — текст остаётся на своём месте по времени.
    merged = []
    for chunk in chunks:
        if merged and merged[-1]["t1"] - merged[-1]["t0"] < MIN_FLASH:
            merged[-1].update(text=merged[-1]["text"] + " " + chunk["text"], t1=chunk["t1"],
                              accent=merged[-1]["accent"] or chunk["accent"])
        else:
            merged.append(chunk)
    if len(merged) > 1 and merged[-1]["t1"] - merged[-1]["t0"] < MIN_FLASH:
        last = merged.pop()                 # короткая последняя — к предыдущей
        merged[-1].update(text=merged[-1]["text"] + " " + last["text"], t1=last["t1"],
                          accent=merged[-1]["accent"] or last["accent"])
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
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def compose(stem: str, seconds: float | None = None, fresh: bool = False) -> Path:
    work = WORK_DIR / stem
    aroll = work / "aroll.mp4"
    faces_path = work / "aroll.faces.json"
    for need, hint in ((aroll, "scripts/prep.py"), (faces_path, "scripts/track.py")):
        if not need.exists():
            sys.exit(f"Нет {need.relative_to(ROOT)} — сначала {hint}")

    meta = load_json(work / "aroll.json")
    faces = load_json(faces_path)
    director = load_json(work / "director.json", {})
    words = (load_json(work / "aroll.words.json", {}) or {}).get("words", [])
    width, height, fps = faces["width"], faces["height"], faces["fps"]
    duration = meta["duration"] if seconds is None else min(seconds, meta["duration"])

    # камера пересчитывается с акцентами режиссёра; полный кадр проверяется ещё раз
    # склейки дубля: камера решается по кускам и не «переезжает» через рез
    cuts, acc = [], 0.0
    for s0, s1 in meta.get("segments", [])[:-1]:
        acc += s1 - s0
        cuts.append(int(round(acc * fps)))
    camera = solve_camera(faces, punches=director.get("punches"), cuts=cuts)
    if coverage_violations(camera, width, height):
        sys.exit("Камера вылезла за край кадра — сборка остановлена (так быть не должно)")
    frames = camera[:int(round(duration * fps)) + 1]

    project = STUDIO / stem
    assets = project / "assets"
    for sub in ("img", "fonts", "sfx"):
        (assets / sub).mkdir(parents=True, exist_ok=True)
    copy_if_newer(aroll, assets / "aroll.mp4")
    if (work / "aroll.cutout.webm").exists():
        copy_if_newer(work / "aroll.cutout.webm", assets / "cutout.webm")
    copy_if_newer(VENDOR / "gsap.min.js", assets / "gsap.min.js")
    for name in FONTS:
        src = FONT_DIR / name
        if src.exists():
            copy_if_newer(src, assets / "fonts" / name)
    for src in (work / "downloads").glob("*"):
        if src.suffix.lower() in (".jpg", ".jpeg", ".png", ".svg", ".webp"):
            copy_if_newer(src, assets / "img" / src.name)
    for src in SFX_DIR.glob("*.mp3"):
        copy_if_newer(src, assets / "sfx" / src.name)

    transforms = [[round(v, 3) for v in css_transform(z, cx, cy, width, height)]
                  for z, cx, cy in frames]
    (project / "camera.js").write_text(
        f"window.CAMERA_FPS = {fps:g};\nwindow.CAMERA = {json.dumps(transforms)};\n",
        encoding="utf-8")
    chunks = caption_chunks(words, director, duration)
    (project / "captions.js").write_text(
        "window.CAPTIONS = " + json.dumps(chunks, ensure_ascii=False) + ";\n", encoding="utf-8")

    page = project / "index.html"
    if fresh or not page.exists():
        page.write_text(PAGE.format(width=width, height=height, duration=f"{duration:.3f}"),
                        encoding="utf-8")
    (project / "hyperframes.json").write_text(json.dumps({
        "paths": {"assets": "assets"}, "media": {"autoProxy": True}}, indent=2), encoding="utf-8")
    (project / "package.json").write_text(json.dumps({
        "name": f"reels-{stem.lower()}", "private": True, "type": "module",
        "scripts": {"dev": f"npx --yes {HYPERFRAMES} preview",
                    "check": f"npx --yes {HYPERFRAMES} check",
                    "render": f"npx --yes {HYPERFRAMES} render"}}, indent=2), encoding="utf-8")
    zooms = [z for z, _, _ in frames]
    print(f"  → камера: зум {min(zooms):.2f}–{max(zooms):.2f}, кадр полный на всех {len(frames)}")
    print(f"  → субтитров: {len(chunks)} вспышек")
    return project


def main():
    ap = argparse.ArgumentParser(description="Проект HyperFrames из подготовленного дубля")
    ap.add_argument("stem", help="имя исходника без расширения, например IMG_3279")
    ap.add_argument("--seconds", type=float, help="собрать только начало (для замеров)")
    ap.add_argument("--fresh", action="store_true",
                    help="перезаписать index.html заготовкой (графика режиссёра пропадёт)")
    args = ap.parse_args()
    project = compose(args.stem, args.seconds, args.fresh)
    print(f"  → проект: {project.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
