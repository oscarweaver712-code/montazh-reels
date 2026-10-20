#!/usr/bin/env python3
"""Финальный мастеринг звука: громкость к −14 LUFS, пики не выше −1.5 dBTP.

HyperFrames сводит голос со звуковыми эффектами и, если удар ложится на пик голоса,
опускает ВЕСЬ микс, чтобы не перегрузить пики: голос получается тише нормы соцсетей
(было −15.7 LUFS вместо −14). Здесь громкость возвращается на место, а редкие пики,
где эффект наложился на голос, мягко срезает лимитер. Видео копируется без пережатия.

  .venv/bin/python scripts/master.py studio/IMG_3279/renders/IMG_3279_v1.mp4 projects/antishkola/output/IMG_3279_v1.mp4
"""
import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ffmpeg_bin

TARGET_LUFS = -14.0
# Потолок лимитера в разах. alimiter режет пики по отсчётам, а проверка меряет истинные (между
# отсчётами), и AAC добавляет к ним ещё: с потолком −1.5 IMG_1810 (14.10.2026) вышел на −0.8 dBTP —
# голос с ударами до 0.7 дБ выше потолка. −2.0 оставляет этот запас; цель −1.5 dBTP не меняется.
CEILING = 10 ** (-2.0 / 20)
TOLERANCE = 0.6                      # насколько итог может отойти от цели
TP_TARGET = -1.5                     # dBTP: норма истинного пика


def measure(path: Path) -> dict:
    err = subprocess.run([
        ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-vn",
        "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-",
    ], capture_output=True, encoding="utf-8", errors="replace").stderr
    found = re.search(r"\{[^{}]*\"input_i\"[\s\S]*?\}", err)
    if not found:
        raise RuntimeError(f"Не удалось замерить громкость {path.name}")
    data = json.loads(found.group(0))
    return {"i": float(data["input_i"]), "tp": float(data["input_tp"])}


def master(src: Path, dst: Path) -> dict:
    """Громкость к цели и лимитер. Истинный пик выше нормы — ещё проходы с потолком ниже; отдаётся лучший проход.

    Лимитер режет отсчёты, а норма — истинный пик между ними: на плотном басе музыки, поднятой в тишине (новоселье
    «Вкудесника», 20.10.2026), после AAC вышло +0.6 dBTP. Лимитер на 4× частоте держал пик, но ронял громкость на 1.5 LU,
    а снижение потолка с AAC немонотонно (−3 дБ дало пик хуже, чем −2 дБ) — поэтому несколько потолков и лучший из них.
    Ролики, проходившие с первого раза, звучат как раньше: первый проход — прежний.
    """
    before = measure(src)
    gain = TARGET_LUFS - before["i"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    tries, best = [], None
    ceiling_db = 20 * math.log10(CEILING)
    try:
        for attempt in range(4):
            tmp = dst.with_name(f".{dst.stem}.mastering{attempt}{dst.suffix}")
            tries.append(tmp)
            result = subprocess.run([
                ffmpeg_bin(), "-v", "error", "-y", "-i", str(src),
                "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
                "-af", f"volume={gain:.2f}dB,alimiter=limit={10 ** (ceiling_db / 20):.4f}:attack=3:release=60:level=false",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(tmp),
            ], capture_output=True, encoding="utf-8", errors="replace")
            if result.returncode != 0:
                raise RuntimeError(f"Мастеринг упал:\n{result.stderr[-500:]}")
            after = measure(tmp)
            fits = abs(after["i"] - TARGET_LUFS) <= TOLERANCE
            if fits and (best is None or after["tp"] < best[1]["tp"]):
                best = (tmp, after, round(ceiling_db, 2))
            if fits and after["tp"] <= TP_TARGET:
                break
            ceiling_db -= max(0.5, after["tp"] - TP_TARGET + 0.3)   # на столько пик вышел за норму — плюс запас
        if best is None or best[1]["tp"] > -0.9:
            got = best[1] if best else after
            raise RuntimeError(
                f"После мастеринга громкость {got['i']:.1f} LUFS, пики {got['tp']:.1f} dBTP — "
                f"не попали в {TARGET_LUFS:g} LUFS / −1.5 dBTP. Файл не отдан.")
        best[0].replace(dst)
    finally:
        for tmp in tries:
            tmp.unlink(missing_ok=True)
    return {"before": before, "after": best[1], "gain": gain, "ceiling": best[2]}


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
