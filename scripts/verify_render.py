#!/usr/bin/env python3
"""Проверка готового ролика перед тем, как отдать его человеку.

Ловит то, что глазом на телефоне замечают уже после публикации:
  • длина разошлась с дублем — субтитры и графика уехали от речи;
  • нет звука или он не той громкости;
  • по краю кадра пустая полоса — камера вылезла за исходник;
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
from common import WORK_DIR, ffmpeg_bin, ffprobe_bin

# Пустота у края — это ровный чёрный фон страницы (Y≈16) без единой фактуры. Тёмный стол или
# штора тоже бывают около 16–20, но в них есть шум и перепады: поэтому смотрим и на разброс.
EMPTY_EDGE_Y = 18.0
EMPTY_EDGE_SPREAD = 6.0


def probe(path: Path) -> dict:
    out = subprocess.run([ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_format",
                          "-show_streams", str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def loudness(path: Path) -> float | None:
    err = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-vn",
                          "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
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
            "-f", "null", "-"], capture_output=True, text=True).stdout
        avg = [float(v) for v in re.findall(r"YAVG=([\d.]+)", out)]
        low = [float(v) for v in re.findall(r"YMIN=([\d.]+)", out)]
        high = [float(v) for v in re.findall(r"YMAX=([\d.]+)", out)]
        result.append((name, list(zip(avg, low, high))))
    return result


def contact_sheet(path: Path, out: Path, step: float = 2.5, width: int = 1080, height: int = 1920) -> Path:
    # плитка в пропорциях ролика: вертикаль 216×384 в 8 колонок, горизонталь 384×216 в 5
    tile_w, tile_h = (216, int(216 * height / width) // 2 * 2) if height >= width else (384, int(384 * height / width) // 2 * 2)
    cols = 8 if height >= width else 5
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(path), "-vf",
                    f"fps=1/{step},scale={tile_w}:{tile_h},tile={cols}x{24 // cols}:padding=4:color=white",
                    "-frames:v", "1", str(out)], check=True, capture_output=True)
    return out


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

    worst = []
    for name, values in edge_lumas(video, width, height, step=1.0):
        holes = [i for i, (y, lo, hi) in enumerate(values)
                 if y < EMPTY_EDGE_Y and hi - lo < EMPTY_EDGE_SPREAD]
        worst.append(f"{name} мин {min(y for y, _, _ in values):.0f}" if values else f"{name} —")
        if holes:
            worst.append(f"пусто: {name} на {holes[:5]} с")
    check(not any(w.startswith("пусто") for w in worst), "по краям нет пустых полос", ", ".join(worst))

    decode = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(video), "-f", "null", "-"],
                            capture_output=True, text=True)
    check(not decode.stderr.strip(), "файл декодируется без ошибок", decode.stderr.strip()[:80] or "чисто")

    sheet = contact_sheet(video, video.with_suffix(".sheet.jpg"), width=width, height=height)
    print(f"  · сетка кадров: {sheet}")
    if failed:
        print(f"\n✗ провалено: {len(failed)} — ролик не отдавать, пока не разберёмся")
        sys.exit(1)
    print("\n✓ ролик можно отдавать")


if __name__ == "__main__":
    main()
