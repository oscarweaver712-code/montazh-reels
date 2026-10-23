#!/usr/bin/env python3
"""ИИ-футажи: кадр (GPT или Nano Banana) → оживление в Google Flow (Omni) → клип под кадр ролика.

Схема коллеги (архив montazh-reels, 12–14.10.2026), внедрена по просьбе Валеры 16.10.2026: «через гпт фото 1,
потом анимируем через гугл омни». Генерация идёт в облаке Google — в браузере, руками агента через Claude
in Chrome (скилл flow). Здесь — всё, что не требует браузера и должно быть одинаковым каждый раз:

  work/<имя>/footage.json        бриф: какие клипы, под какую фразу, промпты кадра и движения, бюджет бонусов
  work/<имя>/footage/prompts.md  два готовых сообщения агенту Flow: «сделай картинки» и «оживи каждую»
  work/<имя>/footage/orig/       скачанные из Flow оригиналы — не трогаются
  work/<имя>/footage/<клип>.mp4  клип под кадр: 1080×1920, 30 к/с, без звука, начало подрезано, ускорен
  work/<имя>/footage/<клип>.md   откуда клип: сгенерировано, когда, каким промптом, сколько бонусов
  work/<имя>/footage/takes.json  что принято и сколько потрачено

  .venv/bin/python scripts/footage.py IMG_1830                          # состояние: что есть, чего нет, бонусы
  .venv/bin/python scripts/footage.py IMG_1830 --prompts                # сообщения для Flow (и prompts.md)
  .venv/bin/python scripts/footage.py IMG_1830 --frame a_shelf          # первый кадр через Codex (GPT), не Flow
  .venv/bin/python scripts/footage.py IMG_1830 --take a_shelf --from 2.0 --speed 1.5 --credits 15
  .venv/bin/python scripts/footage.py IMG_1830 --check                  # все клипы на месте и не короче плана

--take без --file берёт самое свежее видео из «Загрузок» (Flow кладёт туда; бывает двойное .mp4.mp4),
ещё не принятое в этот ролик. В странице клип ставит kit.footage(…) — время по шкале дубля, как всё.

Почему подрезка и ускорение: клип Flow всегда начинается с покоя, а действие случается на 5–7-й секунде
из 10 (ЖУРНАЛ коллеги, IMG_7308_e2) — под короткий план без этого главное остаётся за кадром. Omni держит
дизайн упаковок первые ~5 с, дальше предметы «перетекают» — в план идёт кусок до искажения.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import host  # noqa: E402
from common import QUALITY_FLOOR, ROOT, WORK_DIR, ffmpeg_bin, probe, require_queue, sharpness  # noqa: E402

FRAME = (1080, 1920)
FPS = 30
VIDEO = {".mp4", ".mov", ".m4v", ".webm"}
FRESH = 3 * 3600          # «свежее» в Загрузках: скачано за последние три часа
# Хвост стиля к каждому кадру — то, без чего клип не встанет в ролик: вертикаль, спокойный верх (там текст
# ролика и серая зона площадки), главное в центре (плеер Instagram режет бока ~на 5%), без титров. Только формат и
# композиция: как кадр выглядит, решает стиль проекта (project_look). Здесь же стояло «photorealistic… shot on a phone
# camera», и любой стиль проекта тянуло в фото с телефона (20.10.2026, «Макет на чёрном столе» Антишколы)
STYLE_TAIL = ("Vertical 9:16. Keep the top 20% of the frame calm and uncluttered. Main subject in the central "
              "80% of the width. No captions, no subtitles, no watermarks.")
DEFAULT_LOOK = ("Photorealistic, looks like a real everyday moment shot on a phone camera, natural light, "
                "true-to-life colours.")
MOTION_TAIL = "One continuous shot, no cuts. The main action happens within the first 4 seconds."


class FootageError(Exception):
    """Понятная ошибка о футаже — для человека."""


def folder(stem: str) -> Path:
    return WORK_DIR / stem / "footage"


def load_brief(stem: str) -> dict:
    path = WORK_DIR / stem / "footage.json"
    if not path.exists():
        raise FootageError(f"нет брифа work/{stem}/footage.json — сначала реши, какие клипы нужны (скилл flow)")
    try:
        brief = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise FootageError(f"work/{stem}/footage.json не читается: {e}") from e
    import projects
    project = projects.of_or_default(stem)
    style, motion = project_look(project)
    if not str(brief.get("style") or "").strip():          # стиль проекта (rules.md п.15), если у ролика нет своего
        brief["style"] = style
    brief.setdefault("motion_style", motion)
    # бюджет без отдельного «да»: умолчание проекта (Валера 20.10.2026: «на ролик 2 клипа по умолчанию» — 2 × 15 бонусов)
    if brief.get("budget") is None and int(project.config.get("footage_budget") or 0) > 0:
        brief["budget"] = int(project.config["footage_budget"])
    return validate(brief, stem)


def project_look(project) -> tuple:
    """(стиль кадра, стиль движения) ИИ-клипов проекта: DESIGN.md → footage (один замок на все генерации), иначе
    footage_style из project.json, иначе фото с телефона, как было до дизайн-систем."""
    import design
    system = design.of(project)
    if system and system.footage:
        return system.footage["style"], system.footage["motion"]
    return (str(project.config.get("footage_style") or "").strip() or DEFAULT_LOOK), ""


def validate(brief: dict, stem: str = "?") -> dict:
    """Бриф без дыр: имя клипа годится в имя файла, у каждого — окно в ролике, кадр и движение."""
    clips = brief.get("clips")
    if not isinstance(clips, list) or not clips:
        raise FootageError(f"в брифе {stem} нет клипов (clips: [...])")
    seen = set()
    for i, clip in enumerate(clips, 1):
        name = clip.get("name", "")
        if not re.fullmatch(r"[a-z0-9_]+", name or ""):
            raise FootageError(f"клип №{i}: имя «{name}» — только латиница, цифры и «_» (это имя файла)")
        if name in seen:
            raise FootageError(f"клип «{name}» в брифе дважды")
        seen.add(name)
        at = clip.get("at")
        if not (isinstance(at, list) and len(at) == 2 and all(isinstance(x, (int, float)) for x in at) and at[1] > at[0]):
            raise FootageError(f"клип «{name}»: at — окно в ролике [начало, конец] в секундах дубля, а не {at!r}")
        for key in ("image", "motion"):
            if not str(clip.get(key, "")).strip():
                raise FootageError(f"клип «{name}»: нет промпта «{key}»")
    budget = brief.get("budget")
    if budget is not None and (not isinstance(budget, (int, float)) or budget < 0):
        raise FootageError(f"budget — сколько бонусов Flow одобрено на ролик, число, а не {budget!r}")
    return brief


def take_sharpness(work: Path, took: dict) -> tuple:
    """(«p» во весь кадр 1080×1920, исходник словами) принятого клипа: файл в footage/ уже растянут до кадра, поэтому
    чёткость — по исходнику (common.sharpness). Записи до 23.10.2026 без "sharp" — досчитываются по исходнику."""
    from common import vertical_crop
    if "sharp" in took:
        return took["sharp"], took.get("source_size") or took.get("source_name", "")
    if took.get("source") == "stock":
        info = probe(work / took["source_name"])
        w, h = vertical_crop(info["width"], info["height"])
        return sharpness(w, h, *FRAME), f"{w}×{h} из {took['source_name']}"
    w, h = (int(x) for x in str(took.get("source_size") or "0×0").split("×"))
    return sharpness(w, h, *FRAME), took.get("source_size")


def takes(stem: str) -> dict:
    path = folder(stem) / "takes.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except json.JSONDecodeError as e:
        raise FootageError(f"{path.relative_to(ROOT)} не читается: {e}") from e


def _save_takes(stem: str, data: dict) -> None:
    path = folder(stem) / "takes.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def spent(stem: str) -> int:
    return sum(int(t.get("credits") or 0) for t in takes(stem).values())


# ---------------------------------------------------------------- сообщения для Flow

def messages(brief: dict) -> tuple:
    """Два сообщения агенту Flow: сперва все кадры, потом «оживи каждый». Одним сообщением на пачку —
    так агент Flow понимает задачу целиком (ЖУРНАЛ коллеги: «exactly one image per prompt»)."""
    style = (brief.get("style") or "").strip()
    clips = brief["clips"]
    imgs = [f"{i}. [{c['name']}] {c['image'].strip().rstrip('.')}. {style} {STYLE_TAIL}".replace("  ", " ")
            for i, c in enumerate(clips, 1)]
    refs = sorted({r for c in clips for r in c.get("refs", [])})
    head = (f"Create {len(clips)} images, exactly one image per prompt, aspect ratio 9:16, one variant each."
            + (" Use the uploaded reference images as exact references for the products/objects they show:"
               " keep their real packaging, colours and logos unchanged." if refs else ""))
    first = head + "\n\n" + "\n\n".join(imgs)
    look = (brief.get("motion_style") or "").strip()
    moves = [f"{i}. [{c['name']}] {c['motion'].strip().rstrip('.')}. {look} {MOTION_TAIL}".replace("  ", " ")
             for i, c in enumerate(clips, 1)]
    second = ("Animate each of these images into a video, using the image as the first frame, 9:16, no sound needed. "
              "One video per image, in the same order:\n\n" + "\n\n".join(moves))
    return first, second, refs


def write_prompts(stem: str, brief: dict) -> Path:
    first, second, refs = messages(brief)
    out = folder(stem) / "prompts.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    budget = brief.get("budget")
    lines = [f"# Футажи {stem} — сообщения для Google Flow", "",
             f"Клипов: {len(brief['clips'])}. Бонусы: одобрено {budget if budget is not None else 'не задано'}, "
             f"потрачено {spent(stem)}. Цена видео — Flow называет сам перед генерацией (16.10: 8 с Omni 1.1 Flash — 12); "
             "больше одобренного — спросить Валеру. План AI Plus — 50 бонусов в день.", ""]
    if refs:
        lines += ["Загрузить в проект Flow перед первым сообщением (референсы):", ""] + [f"- `{r}`" for r in refs] + [""]
    frames = [f"- `{c['name']}` — `work/{stem}/footage/frames/{c['name']}.png`" for c in brief["clips"]]
    lines += ["## Кадры — через GPT (правило Валеры, 16.10.2026)", "",
              f"`footage.py {stem} --frame <клип>` на каждый клип, потом загрузить в проект Flow по порядку:", "",
              *frames, "", "## Сообщение — оживить загруженные кадры", "", "```", second, "```", "",
              "## Запасное — кадры в самом Flow (Nano Banana), только если Валера попросил", "", "```", first, "```", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------- приём клипа

def downloads_dir() -> Path:
    return Path.home() / "Downloads"


def newest_download(stem: str, where: Path | None = None, now: float | None = None) -> Path:
    """Самое свежее видео в «Загрузках», скачанное за три часа и ещё не принятое в этот ролик."""
    where = where or downloads_dir()
    now = now or time.time()
    used = {t.get("source_name") for t in takes(stem).values()}
    found = [p for p in where.iterdir() if p.is_file() and not p.name.startswith(".")
             and Path(p.name.removesuffix(".mp4") if p.name.endswith(".mp4.mp4") else p.name).suffix.lower() in VIDEO
             and now - p.stat().st_mtime <= FRESH and p.name not in used] if where.exists() else []
    if not found:
        raise FootageError(f"в {where} нет свежего видео (за 3 часа, ещё не принятого) — скачай клип из Flow "
                           "или укажи файл: --file путь")
    return max(found, key=lambda p: p.stat().st_mtime)


def plan_cut(duration: float, start: float = 0.0, speed: float = 1.0, end: float | None = None) -> tuple:
    """Окно исходника [a, b] так, чтобы готовый клип лёг ровно на сетку кадров (инвариант 4)."""
    if not 0.25 <= speed <= 4:
        raise FootageError(f"ускорение {speed} — допустимо от 0.25 до 4")
    end = duration if end is None else min(end, duration)
    if start < 0 or end - start < 0.5:
        raise FootageError(f"от клипа длиной {duration:.2f} с остаётся меньше полсекунды ({start:.2f}–{end:.2f})")
    frames = int((end - start) / speed * FPS + 1e-6)
    return round(start, 4), round(start + frames * speed / FPS, 4), frames


def normalize(src: Path, out: Path, start: float = 0.0, speed: float = 1.0, end: float | None = None) -> dict:
    """Клип → 1080×1920, 30 к/с, без звука. Длина — через trim, а не -t (инвариант 4)."""
    info = probe(src)
    a, b, frames = plan_cut(float(info["duration"]), start, speed, end)
    w, h = FRAME
    sharp = sharpness(info["width"], info["height"], w, h)
    if sharp < QUALITY_FLOOR:                   # Валера 23.10.2026: ниже 720p — лесом, автоматом
        raise FootageError(f"клип {src.name}: {info['width']}×{info['height']} во весь кадр — {sharp}p, ниже "
                           f"{QUALITY_FLOOR}p — не берём")
    vf = (f"trim=start={a}:end={b},setpts=(PTS-STARTPTS)/{speed},fps={FPS},"
          f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},setsar=1,format=yuv420p")
    encoder = host.video_encoder("auto", ffmpeg_bin())
    codec = (["-c:v", encoder, "-b:v", "10M"] if encoder != "libx264"
             else ["-c:v", "libx264", "-crf", "17", "-preset", "veryfast", "-threads", str(host.encoder_threads())])
    tmp = out.with_suffix(".part.mp4")
    try:
        done = subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(src), "-vf", vf, "-an",
                               *codec, "-movflags", "+faststart", str(tmp)], capture_output=True,
                              encoding="utf-8", errors="replace")
        if done.returncode != 0:
            raise FootageError(f"ffmpeg не привёл клип {src.name}: {done.stderr.strip()[-400:]}")
        tmp.replace(out)
    finally:
        tmp.unlink(missing_ok=True)                    # инвариант 5: кусок не остаётся даже при падении
    return {"from": a, "to": b, "speed": speed, "frames": frames, "duration": round(frames / FPS, 3),
            "source_duration": round(float(info["duration"]), 3), "source_size": f"{info.get('width')}×{info.get('height')}", "sharp": sharp}


def take(stem: str, name: str, file: Path | None = None, start: float = 0.0, speed: float = 1.0,
         end: float | None = None, credits: int = 0, where: Path | None = None) -> dict:
    brief = load_brief(stem)
    clip = next((c for c in brief["clips"] if c["name"] == name), None)
    if clip is None:
        raise FootageError(f"клипа «{name}» нет в брифе {stem}: {', '.join(c['name'] for c in brief['clips'])}")
    src = Path(file) if file else newest_download(stem, where)
    if not src.exists():
        raise FootageError(f"нет файла {src}")
    base = folder(stem)
    (base / "orig").mkdir(parents=True, exist_ok=True)
    orig = base / "orig" / f"{name}{src.suffix.lower() if src.suffix.lower() in VIDEO else '.mp4'}"
    if src.resolve() != orig.resolve():
        shutil.copy2(src, orig)
    meta = normalize(orig, base / f"{name}.mp4", start, speed, end)
    need = round(clip["at"][1] - clip["at"][0], 3)
    data = takes(stem)
    prev = data.get(name, {})
    data[name] = {**meta, "source_name": src.name, "credits": int(credits) + int(prev.get("credits") or 0),
                  "taken": time.strftime("%Y-%m-%d %H:%M"), "need": need}
    _save_takes(stem, data)
    (base / f"{name}.md").write_text(
        f"# {name}.mp4\n\nСгенерировано в Google Flow (Omni), принято {data[name]['taken']}. Это не съёмка: "
        f"в ролике — ИИ-футаж.\nФраза: {clip.get('say', '—')}\nКадр: {clip['image']}\nДвижение: {clip['motion']}\n"
        f"Оригинал — orig/{orig.name} ({meta['source_size']}, {meta['source_duration']} с); взято "
        f"{meta['from']}–{meta['to']} с ×{speed} → {meta['duration']} с.\nБонусы Flow: {data[name]['credits']}.\n",
        encoding="utf-8")
    return data[name]


def status(stem: str) -> tuple:
    """(строки отчёта, всё ли готово): каждый клип брифа есть и не короче своего окна в ролике."""
    brief = load_brief(stem)
    data, rows, ok = takes(stem), [], True
    for clip in brief["clips"]:
        name, need = clip["name"], clip["at"][1] - clip["at"][0]
        path = folder(stem) / f"{name}.mp4"
        got = data.get(name)
        if not path.exists() or not got:
            rows.append(f"  ✗ {name:<14} нет — нужно {need:.1f} с под «{clip.get('say', '')[:50]}»")
            ok = False
        elif got["duration"] + 1e-3 < need:
            rows.append(f"  ✗ {name:<14} {got['duration']:.2f} с — короче плана ({need:.2f} с): меньше ускорение "
                        f"или раньше начало")
            ok = False
        else:
            rows.append(f"  ✓ {name:<14} {got['duration']:.2f} с (нужно {need:.2f}), ×{got['speed']}, "
                        f"бонусов {got.get('credits', 0)}")
    budget, used = brief.get("budget"), spent(stem)
    if budget is not None and used > budget:
        rows.append(f"  ✗ потрачено {used} бонусов при одобренных {budget} — согласовать с Валерой")
        ok = False
    else:
        rows.append(f"  · бонусы Flow: потрачено {used}" + (f" из {budget} одобренных" if budget is not None else ""))
    return rows, ok


def frame(stem: str, name: str) -> Path:
    """Первый кадр клипа через Codex (GPT imagegen) — когда кадр лучше у GPT, а Flow только оживляет."""
    import gen_image
    brief = load_brief(stem)
    clip = next((c for c in brief["clips"] if c["name"] == name), None)
    if clip is None:
        raise FootageError(f"клипа «{name}» нет в брифе {stem}")
    out = folder(stem) / "frames" / f"{name}.png"
    rules = ("вертикальный кадр 9:16, строго в стиле из описания; верхние 20% кадра спокойные; главное — "
             "в центральных 80% ширины; без титров, надписей и водяных знаков; без узнаваемых реальных людей")
    gen_image.generate(out, f"{clip['image'].strip().rstrip('.')}. {brief.get('style', '')}".strip(), rules)
    return out


def main():
    ap = argparse.ArgumentParser(description="ИИ-футажи из Google Flow: бриф, промпты, приём клипов")
    ap.add_argument("stem", help="ролик: IMG_1830")
    ap.add_argument("--prompts", action="store_true", help="сообщения для Flow → footage/prompts.md")
    ap.add_argument("--frame", metavar="КЛИП", help="первый кадр клипа через Codex (GPT)")
    ap.add_argument("--take", metavar="КЛИП", help="принять скачанный клип")
    ap.add_argument("--file", type=Path, help="файл клипа (без него — свежий из «Загрузок»)")
    ap.add_argument("--from", dest="start", type=float, default=0.0, help="с какой секунды клипа брать")
    ap.add_argument("--to", dest="end", type=float, help="до какой секунды клипа (дальше — искажения)")
    ap.add_argument("--speed", type=float, default=1.0, help="ускорение, 1.5 — действие с 6-й с успеет в план")
    ap.add_argument("--credits", type=int, default=0, help="сколько бонусов Flow ушло на этот клип")
    ap.add_argument("--check", action="store_true", help="код ошибки, если чего-то не хватает")
    args = ap.parse_args()
    try:
        if args.prompts:
            out = write_prompts(args.stem, load_brief(args.stem))
            print(out.read_text(encoding="utf-8"))
            print(f"  ✓ {out.relative_to(ROOT)}")
            return
        if args.frame:
            out = frame(args.stem, args.frame)
            print(f"  ✓ первый кадр {out.relative_to(ROOT)} — загрузи его во Flow и оживи")
            return
        if args.take:
            require_queue("приём ИИ-футажа")
            got = take(args.stem, args.take, args.file, args.start, args.speed, args.end, args.credits)
            print(f"  ✓ work/{args.stem}/footage/{args.take}.mp4: {got['duration']} с "
                  f"(из {got['source_name']}, {got['from']}–{got['to']} с ×{got['speed']})")
            if got["duration"] + 1e-3 < got["need"]:
                print(f"  ! короче окна в ролике ({got['need']} с) — меньше --speed или раньше --from")
            return
        rows, ok = status(args.stem)
        print(f"Футажи {args.stem}:\n" + "\n".join(rows))
        if args.check and not ok:
            sys.exit(1)
    except FootageError as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
