#!/usr/bin/env python3
"""Финальный мастеринг звука: громкость к −14 LUFS, пики не выше −1.5 dBTP.

HyperFrames сводит голос со звуковыми эффектами и, если удар ложится на пик голоса,
опускает ВЕСЬ микс, чтобы не перегрузить пики: голос получается тише нормы соцсетей
(было −15.7 LUFS вместо −14). Здесь громкость возвращается на место, а редкие пики,
где эффект наложился на голос, мягко срезает лимитер. Видео копируется без пережатия.

  .venv/bin/python scripts/master.py studio/IMG_3279/renders/IMG_3279_v1.mp4 output/IMG_3279_v1.mp4
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ffmpeg_bin

TARGET_LUFS = -14.0
CEILING = 10 ** (-1.5 / 20)          # −1.5 dBFS в разах: потолок лимитера
TOLERANCE = 0.6                      # насколько итог может отойти от цели


def measure(path: Path) -> dict:
    err = subprocess.run([
        ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-vn",
        "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-",
    ], capture_output=True, text=True).stderr
    found = re.search(r"\{[^{}]*\"input_i\"[\s\S]*?\}", err)
    if not found:
        raise RuntimeError(f"Не удалось замерить громкость {path.name}")
    data = json.loads(found.group(0))
    return {"i": float(data["input_i"]), "tp": float(data["input_tp"])}


def master(src: Path, dst: Path) -> dict:
    before = measure(src)
    gain = TARGET_LUFS - before["i"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f".{dst.stem}.mastering{dst.suffix}")
    try:
        result = subprocess.run([
            ffmpeg_bin(), "-v", "error", "-y", "-i", str(src),
            "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
            "-af", f"volume={gain:.2f}dB,alimiter=limit={CEILING:.4f}:attack=3:release=60:level=false",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(tmp),
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Мастеринг упал:\n{result.stderr[-500:]}")
        after = measure(tmp)
        if abs(after["i"] - TARGET_LUFS) > TOLERANCE or after["tp"] > -0.9:
            raise RuntimeError(
                f"После мастеринга громкость {after['i']:.1f} LUFS, пики {after['tp']:.1f} dBTP — "
                f"не попали в {TARGET_LUFS:g} LUFS / −1.5 dBTP. Файл не отдан.")
        tmp.replace(dst)
    finally:
        tmp.unlink(missing_ok=True)
    return {"before": before, "after": after, "gain": gain}


def main():
    ap = argparse.ArgumentParser(description="Громкость готового ролика к норме соцсетей")
    ap.add_argument("src")
    ap.add_argument("dst")
    args = ap.parse_args()
    src, dst = Path(args.src).resolve(), Path(args.dst).resolve()
    if not src.exists():
        sys.exit(f"Нет файла: {src}")
    stats = master(src, dst)
    b, a = stats["before"], stats["after"]
    print(f"  → громкость {b['i']:.1f} → {a['i']:.1f} LUFS, пики {b['tp']:.1f} → {a['tp']:.1f} dBTP "
          f"(+{stats['gain']:.1f} дБ)")
    print(f"  ✓ {dst}")


if __name__ == "__main__":
    main()
