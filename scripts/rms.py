#!/usr/bin/env python3
"""Огибающая громкости по 20 мс: где на самом деле начинается и кончается звук.

Точки реза и «пипа» ставятся по звуку, а не по таймингам whisper (инвариант 3):

  .venv/bin/python scripts/rms.py input/IMG_3320.MOV 81.9 83.2
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ffmpeg_bin  # noqa: E402

if len(sys.argv) != 4:
    sys.exit("Нужно: rms.py <видео> <от, с> <до, с>")
src, a, b = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
result = subprocess.run([ffmpeg_bin(), "-v", "error", "-ss", f"{a}", "-to", f"{b}", "-i", src,
                         "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True)
if result.returncode != 0:
    sys.exit(f"Не получилось достать звук: {result.stderr.decode(errors='replace')[-300:]}")
x = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768
hop = 320
print(" ".join(f"{a + k / 16000:.2f}:{20 * np.log10(np.sqrt(np.mean(x[k:k + hop] ** 2)) + 1e-9):.0f}"
               for k in range(0, len(x) - hop, hop)))
