#!/usr/bin/env python3
"""Проверка готового ролика перед тем, как отдать его человеку.

Ловит то, что глазом на телефоне замечают уже после публикации:
  • длина разошлась с дублем — субтитры и графика уехали от речи;
  • нет звука или он не той громкости;
  • по краю кадра пустая полоса — камера вылезла за исходник;
  • лицо засвечено — светлее, чем в принятых роликах серии;
  • музыки не слышно — в паузах речи готовый ролик звучит, как голый дубль (проект просит музыку);
  • файл битый.

  .venv/bin/python scripts/verify_render.py studio/IMG_3279/renders/IMG_3279_v1.mp4 --stem IMG_3279
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import formats
from common import WORK_DIR, ffmpeg_bin, ffprobe_bin, sheet_path

# Пустота у края — это ровный чёрный фон страницы (Y≈16) без единой фактуры. Тёмный стол или
# штора тоже бывают около 16–20, но в них есть шум и перепады: поэтому смотрим и на разброс.
EMPTY_EDGE_Y = 18.0
EMPTY_EDGE_SPREAD = 6.0

# Лицо: медиана яркости (Y) середины лица по 12 кадрам. В принятых роликах серии (яркость −8,
# студия со шторой) — 150–152; IMG_1803 v2 с засвеченным лицом (HDR без калибровки) — 171,
# Валера его забраковал (12.10.2026). Выше FACE_MAX_Y — засвет: ролик не отдавать.
FACE_MAX_Y = 165.0
FACE_MAX_HOT = 2.0          # % почти белых (Y ≥ 230) пикселей лица — выбитые света


def probe(path: Path) -> dict:
    out = subprocess.run([ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_format",
                          "-show_streams", str(path)], capture_output=True, encoding="utf-8", errors="replace", check=True).stdout
    return json.loads(out)


def loudness(path: Path) -> float | None:
    err = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-vn",
                          "-af", "ebur128", "-f", "null", "-"], capture_output=True, encoding="utf-8", errors="replace").stderr
    found = re.findall(r"I:\s*(-?[\d.]+) LUFS", err)
    return float(found[-1]) if found else None


def edge_lumas(path: Path, width: int, height: int, step: float) -> list:
    """Средняя яркость четырёх полос по 6 px у краёв, на кадре раз в step секунд."""
    strips = {"лево": f"6:{height}:0:0", "право": f"6:{height}:{width - 6}:0",
              "верх": f"{width}:6:0:0", "низ": f"{width}:6:0:{height - 6}"}
    result = []
    for name, crop in strips.items():
        out = subprocess.run([
            ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-an",
            "-vf", f"fps=1/{step},crop={crop},signalstats,metadata=print:file=-",
            "-f", "null", "-"], capture_output=True, encoding="utf-8", errors="replace").stdout
        avg = [float(v) for v in re.findall(r"YAVG=([\d.]+)", out)]
        low = [float(v) for v in re.findall(r"YMIN=([\d.]+)", out)]
        high = [float(v) for v in re.findall(r"YMAX=([\d.]+)", out)]
        result.append((name, list(zip(avg, low, high))))
    return result


def contact_sheet(path: Path, out: Path, step: float = 2.5, width: int = 1080, height: int = 1920,
                  duration: float = 0.0) -> Path:
    # плитка в пропорциях ролика: вертикаль 216×384 в 8 колонок, горизонталь 384×216 в 5
    tile_w, tile_h = (216, int(216 * height / width) // 2 * 2) if height >= width else (384, int(384 * height / width) // 2 * 2)
    cols = 8 if height >= width else 5
    tiles = cols * (24 // cols)
    # шаг растёт с длиной ролика: сетка собирается из первых tiles кадров, и при шаге 2.5 с
    # ролик длиннее минуты попадал на неё без конца — финал и плашку глазами не проверить
    step = max(step, duration / tiles)
    # серые зоны площадок (formats.GREY_ZONES) — полупрозрачным красным на каждой плитке: что
    # заехало под шапку, ник и подпись или кнопки справа, видно на той же сетке, что и всё остальное
    k = tile_w / width
    zones = "".join(f"drawbox=x={x0 * k:.0f}:y={y0 * k:.0f}:w={(x1 - x0) * k:.0f}:h={(y1 - y0) * k:.0f}"
                    f":color=red@0.22:t=fill,"
                    for _, (x0, y0, x1, y1) in formats.grey_zones(formats.of_size(width, height)))
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(path), "-vf",
                    f"fps=1/{step:.3f},scale={tile_w}:{tile_h},{zones}tile={cols}x{24 // cols}:padding=4:color=white",
                    "-frames:v", "1", str(out)], check=True, capture_output=True)
    return out


def face_brightness(path: Path, duration: float, frames: int = 12) -> tuple:
    """(медиана Y середины лица, % почти белых, сколько кадров с лицом) — YuNet по 12 кадрам."""
    import cv2
    import numpy as np
    from track import YUNET

    w, h = 540, 960
    # модель — байтами: OpenCV на Windows не открывает путь с кириллицей
    det = cv2.FaceDetectorYN.create("onnx", np.frombuffer(YUNET.read_bytes(), np.uint8),
                                    np.empty(0, np.uint8), (w, h), 0.6, 0.3, 50)
    medians, hot = [], []
    for i in range(frames):
        at = duration * (i + 0.5) / frames
        raw = subprocess.run([ffmpeg_bin(), "-v", "error", "-ss", f"{at:.2f}", "-i", str(path), "-frames:v", "1",
                              "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
                              "format=bgr24", "-f", "rawvideo", "-"], capture_output=True).stdout
        if len(raw) != w * h * 3:
            continue
        img = np.frombuffer(raw, np.uint8).reshape(h, w, 3)
        _, found = det.detect(img)
        if found is None:
            continue
        x, y, fw, fh = found[0][:4].astype(int)
        cx, cy = x + fw // 2, y + fh // 2
        box = img[max(0, cy - fh // 3): cy + fh // 3, max(0, cx - fw // 3): cx + fw // 3]
        luma = cv2.cvtColor(box, cv2.COLOR_BGR2YUV)[:, :, 0].astype(float)
        medians.append(float(np.median(luma)))
        hot.append(float((luma >= 230).mean() * 100))
    if not medians:
        return None, None, 0
    return float(np.median(medians)), float(np.mean(hot)), len(medians)


# Музыка в паузах речи (19.10.2026, замер на выпусках): медиана тихих окон ролика выше, чем у голого дубля, на 0,8–3,5 дБ
# без музыки (IMG_3292 v2, IMG_3303 v4, IMG_1816 v1) и на 14–21 дБ с ней. Подложка относительно речи: v5 −26,9 дБ —
# «музыка совсем не слышна», v6 −22 дБ — «вот как сейчас хорошо» (Валера 17.10); IMG_3645 −23,1 дБ — «чуть громче, чем
# должен быть» (20.10): уровень проекта снижен на 2 дБ (project.json → music_level), нижняя граница — выше v5.
MUSIC_BED_DB = 8.0
MUSIC_QUIETEST = -26.5
MUSIC_LOUDEST = -12.0     # дБ от речи: громче — музыка спорит с голосом (новоселье v2, 20.10.2026: +1.3, вровень с речью)


def _pcm(path: Path):
    import numpy as np
    raw = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def music_bed(video: Path, stem: str) -> tuple | None:
    """(насколько паузы ролика громче пауз голого дубля, подложка относительно речи), дБ — слышна ли музыка.

    17.10.2026 IMG_3292 v2 ушла без музыки, и заметил это только Валера. Меряем готовый файл, а не страницу: тихий трек
    или сбой микса страница не покажет. Тишина и речь — по голому дублю (тайминги whisper тянут слова через паузы,
    инвариант 3); медиана, а не среднее: хвосты ударов и тихих звуков в паузах редки, музыка — всё время.
    """
    import numpy as np
    aroll = WORK_DIR / stem / "aroll.mp4"
    if not aroll.exists():
        return None
    final, dry = _pcm(video), _pcm(aroll)
    n = min(len(final), len(dry)) // 400 * 400                    # окна по 50 мс
    if not n:
        return None
    db = lambda x: 20 * np.log10(np.sqrt((x[:n].reshape(-1, 400) ** 2).mean(axis=1)) + 1e-9)    # noqa: E731
    f_db, d_db = db(final), db(dry)
    speech = d_db > np.percentile(d_db, 60)
    quiet = d_db < np.percentile(d_db[speech], 50) - 30
    if quiet.sum() < 40:                                          # меньше 2 с тишины — не по чему судить
        return None
    offset = np.median(f_db[speech]) - np.median(d_db[speech])    # мастеринг сдвинул громкость целиком
    rise = float(np.median(f_db[quiet]) - np.median(d_db[quiet]) - offset)
    return rise, float(np.median(f_db[quiet]) - np.median(f_db[speech]))


def face_limit(stem: str | None) -> tuple:
    """(порог яркости лица или None, чей он) — из project.json проекта ролика.

    Порог 165 снят с серии антишколы (лицо 150–152); у чужого проекта свой свет и своя кожа,
    и мерить его по нашей серии — значит браковать или пропускать наугад (14.10.2026).
    """
    import projects
    try:
        project = projects.of_or_default(stem) if stem else None
    except projects.ProjectError:
        project = None
    if project is None:
        return FACE_MAX_Y, "по серии антишколы"
    return project.config["face_max"], f"проект {project.name}"


def main():
    ap = argparse.ArgumentParser(description="Проверка готового ролика")
    ap.add_argument("video")
    ap.add_argument("--stem", help="имя исходника: длина сверяется с work/<имя>/aroll.json")
    ap.add_argument("--format", help="ожидаемый формат (9:16, 16:9, 1:1, 4:5); по умолчанию из дубля")
    args = ap.parse_args()

    video = Path(args.video).resolve()
    if not video.exists():
        sys.exit(f"Нет файла: {video}")
    failed = []

    def check(ok: bool, title: str, detail: str = ""):
        print(f"  {'✓' if ok else '✗'} {title}" + (f"  ({detail})" if detail else ""))
        if not ok:
            failed.append(title)

    info = probe(video)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    width, height = int(v["width"]), int(v["height"])
    duration = float(info["format"]["duration"])

    meta = None
    if args.stem:
        meta = json.loads((WORK_DIR / args.stem / "aroll.json").read_text(encoding="utf-8"))
    # формат — из дубля (aroll.json пишет prep.py); у старых роликов его нет — это 9:16
    fmt = args.format or (meta or {}).get("format") or formats.DEFAULT
    want_w, want_h = formats.size(fmt)
    check((width, height) == (want_w, want_h), f"кадр {want_w}×{want_h} ({fmt})", f"{width}×{height}")
    check(v.get("r_frame_rate") in ("30/1", "30000/1000"), "30 кадров в секунду", v.get("r_frame_rate", "?"))
    if meta:
        drift = abs(duration - meta["duration"])
        check(drift <= 2 / 30, "длина совпадает с дублем", f"{duration:.3f} с против {meta['duration']:.3f} с")
    check(has_audio, "звуковая дорожка на месте")
    level = loudness(video) if has_audio else None
    check(level is not None and -15.5 <= level <= -12.5, "громкость около −14 LUFS",
          f"{level:.1f} LUFS" if level is not None else "не замерить")

    if args.stem and has_audio:
        import projects
        try:
            wants = projects.of(args.stem).config.get("music")
        except projects.ProjectError:
            wants = False
        bed = music_bed(video, args.stem) if wants else None
        if bed is not None:
            rise, under = bed
            check(rise >= MUSIC_BED_DB and MUSIC_QUIETEST <= under <= MUSIC_LOUDEST,
                  "фоновая музыка слышна в паузах речи и не спорит с голосом",
                  f"паузы громче голого дубля на {rise:.1f} дБ (нужно ≥ {MUSIC_BED_DB:g}), подложка {under:.1f} дБ "
                  f"от речи (от {MUSIC_QUIETEST:g} до {MUSIC_LOUDEST:g})")

    worst = []
    for name, values in edge_lumas(video, width, height, step=1.0):
        holes = [i for i, (y, lo, hi) in enumerate(values)
                 if y < EMPTY_EDGE_Y and hi - lo < EMPTY_EDGE_SPREAD]
        worst.append(f"{name} мин {min(y for y, _, _ in values):.0f}" if values else f"{name} —")
        if holes:
            worst.append(f"пусто: {name} на {holes[:5]} с")
    check(not any(w.startswith("пусто") for w in worst), "по краям нет пустых полос", ", ".join(worst))

    face_max, whose = face_limit(args.stem)
    face, hot, seen = face_brightness(video, duration) if face_max is not None else (0, 0, 0)
    if face_max is None:
        print(f"  · засвет лица не проверялся: у проекта {whose} нет порога (project.json face_max)")
    elif seen:
        check(face <= face_max and hot <= FACE_MAX_HOT, f"лицо не засвечено (яркость лица до {face_max:g}, {whose})",
              f"медиана {face:.0f}, почти белых {hot:.1f}%, кадров с лицом {seen}")
    else:
        print("  · лица в кадре нет — засвет лица не проверялся")

    decode = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(video), "-f", "null", "-"],
                            capture_output=True, encoding="utf-8", errors="replace")
    check(not decode.stderr.strip(), "файл декодируется без ошибок", decode.stderr.strip()[:80] or "чисто")

    out = sheet_path(video)                    # не в output/: там только видео (Валера 16.10)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet = contact_sheet(video, out, width=width, height=height,
                          duration=duration)
    print(f"  · сетка кадров: {sheet}")
    if failed:
        print(f"\n✗ провалено: {len(failed)} — ролик не отдавать, пока не разберёмся")
        sys.exit(1)
    print("\n✓ ролик можно отдавать")


if __name__ == "__main__":
    main()
