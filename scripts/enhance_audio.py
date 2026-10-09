#!/usr/bin/env python3
"""Улучшение речи через Resemble Enhance — аналог Adobe Enhance Speech.

Запускается ОТДЕЛЬНЫМ интерпретатором `.venv-audio/bin/python`: resemble-enhance прибит
к torch 2.1.1, под который нет колёс для Python 3.12 основного окружения.

  .venv-audio/bin/python scripts/enhance_audio.py вход.wav выход.wav [--denoise-only]
"""
import argparse
import os
import sys
import time
from pathlib import Path

# На cpu модель идёт примерно вчетверо дольше самой записи (диффузия, nfe шагов на окно).
# Грубая оценка нужна, чтобы не запустить втихую многочасовой прогон на всё ядро.
CPU_SLOWDOWN = 4.0
CPU_LIMIT_SEC = 300.0


def pick_device(requested: str) -> str:
    import torch
    if requested != "auto":
        return requested
    # MPS у torch 2.1 покрывает не все операции модели; cpu медленнее, но не падает
    return "cuda" if torch.cuda.is_available() else "cpu"


def limit_threads():
    """Оставляем машине пару ядер: иначе на время прогона ноутбуком нельзя пользоваться."""
    import torch
    spare = max(1, (os.cpu_count() or 4) - 2)
    torch.set_num_threads(spare)
    return spare


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--denoise-only", action="store_true",
                    help="только убрать шум, без достройки частот (быстрее)")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--nfe", type=int, default=64, help="шагов решателя: больше — чище, но дольше")
    ap.add_argument("--yes", action="store_true",
                    help="согласиться на долгий прогон на cpu без вопросов")
    args = ap.parse_args()

    import torch
    import torchaudio
    from resemble_enhance.enhancer.inference import denoise, enhance

    device = pick_device(args.device)
    src = Path(args.src)
    if not src.exists():
        sys.exit(f"нет файла: {src}")

    wav, sr = torchaudio.load(str(src))
    wav = wav.mean(dim=0)          # модель ждёт моно
    seconds = wav.shape[-1] / sr

    threads = limit_threads() if device == "cpu" else None
    if device == "cpu" and not args.denoise_only and seconds > CPU_LIMIT_SEC and not args.yes:
        eta = seconds * CPU_SLOWDOWN / 60
        sys.exit(
            f"Дорожка {seconds / 60:.0f} мин, на cpu это примерно {eta:.0f} мин "
            f"под полной нагрузкой.\n"
            f"Так и хотел — добавь --yes. Быстрее: --denoise-only или --nfe 16."
        )

    started = time.time()
    if threads:
        print(f"  → обрабатываю голос на cpu в {threads} потоках", flush=True)
    if args.denoise_only:
        out, out_sr = denoise(wav, sr, device)
    else:
        out, out_sr = enhance(wav, sr, device, nfe=args.nfe,
                              solver="midpoint", lambd=0.9, tau=0.5)

    torchaudio.save(args.dst, out.unsqueeze(0).cpu(), out_sr)
    spent = time.time() - started
    print(f"  → голос обработан за {spent:.0f} с "
          f"({spent / max(seconds, 0.1):.1f}× длительности, {device}, {out_sr} Гц)")


if __name__ == "__main__":
    main()
