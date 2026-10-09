#!/usr/bin/env python3
"""Монтаж Reels одной командой: рез пауз → субтитры по словам → динамика → звук.

  .venv/bin/python scripts/reels.py input/urok.mp4
  .venv/bin/python scripts/reels.py input/urok.mp4 --hook "Так делают 90% учеников"
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (INPUT_DIR, OUTPUT_DIR, WORK_DIR, detect_silence, has_libass,
                    load_preset, measure_noise_floor, probe)
from cut import plan_cut
from render import render
from subs import write_ass
from transcribe import run_transcribe


def mmss(seconds: float) -> str:
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


def process(video: Path, args) -> Path:
    preset = load_preset(args.preset)

    if args.no_cut:
        preset["cut"]["enabled"] = False
    if args.no_subs:
        preset["subs"]["enabled"] = False
    if args.no_motion:
        preset["motion"]["punch_in"] = False
    if args.no_audio:
        preset["audio"]["enabled"] = False
    if args.encoder:
        preset["video"]["encoder"] = args.encoder

    print(f"\n▶ {video.name}")
    info = probe(video)
    print(f"  → исходник: {info['width']}×{info['height']}, {mmss(info['duration'])}, {info['fps']:.0f} fps")

    if not info["has_audio"]:
        sys.exit("  ✗ в файле нет звуковой дорожки — монтировать нечего")

    if not info["vertical"]:
        print("  ⚠ исходник горизонтальный: кадр обрежется по центру в 9:16")

    started = time.time()

    # распознавание нужно только для реза и субтитров — иначе это минута впустую
    needs_speech = preset["cut"].get("enabled", True) or preset["subs"].get("enabled", True)
    if needs_speech:
        data = run_transcribe(video, language=args.language, force=args.force)
        if not data["words"]:
            sys.exit("  ✗ речь не распознана — проверь звук в исходнике")
    else:
        print("  → рез и субтитры выключены, распознавание пропускаю")
        data = {"words": []}

    # Карта настоящей тишины. Нужна дважды: по ней ставятся границы реза (тайминги
    # распознавания на концах слов врут и режут речь) и по ней же замеряется уровень
    # шума для шумодава. Проход только по звуку — секунды даже на длинной записи.
    cut_on = preset["cut"].get("enabled", True)
    denoise_on = preset["audio"].get("enabled", True) and preset["audio"].get("denoise", True)

    silences, noise_floor = [], None
    if cut_on or denoise_on:
        silences = detect_silence(video,
                                  preset["cut"].get("silence_db", -35),
                                  preset["cut"].get("silence_min", 0.10))
        print(f"  → пауз в звуке: {len(silences)}")
        if denoise_on:
            noise_floor = measure_noise_floor(video, silences)
            print(f"  → уровень шума в паузах: {noise_floor:.0f} дБ")

    # сетка кадров берётся от выходного fps: по этим же числам считаются тайминги субтитров
    plan = plan_cut(data["words"], preset["cut"], info["duration"],
                    fps=preset["video"].get("fps", 30), silences=silences)
    segments = plan["segments"]
    kept = plan["kept_duration"]
    saved = info["duration"] - kept

    # карта реза — её рисует веб-интерфейс, чтобы было видно, что именно вырезано
    import json as _json
    (WORK_DIR / f"{video.stem}.plan.json").write_text(_json.dumps({
        "duration": info["duration"], "kept": kept, "segments": segments,
        "dropped_words": plan["dropped_words"],
    }), encoding="utf-8")

    print(f"  → сегментов: {len(segments)}, вырезано слов-паразитов: {plan['dropped_words']}")
    print(f"  → хронометраж: {mmss(info['duration'])} → {mmss(kept)}  (минус {saved:.1f} с, {saved / info['duration'] * 100:.0f}%)")

    ass_path = None
    if preset["subs"].get("enabled", True):
        if not has_libass():
            print("  ⚠ ffmpeg собран без libass — субтитры пропускаю")
        else:
            hook = dict(preset.get("hook", {}))
            if args.hook:
                hook.update({"enabled": True, "text": args.hook})
            ass_path = write_ass(
                WORK_DIR / f"{video.stem}.ass",
                plan["words"], preset["subs"], preset["video"], hook,
            )
            print(f"  → субтитры: {len(plan['words'])} слов")

    out_name = args.out or f"{video.stem}_reels.mp4"
    out_path = OUTPUT_DIR / out_name
    render(video, out_path, segments, preset, ass_path, noise_floor=noise_floor)

    size_mb = out_path.stat().st_size / 1_048_576
    print(f"  ✓ готово за {time.time() - started:.0f} с → output/{out_path.name}  ({size_mb:.1f} МБ, {mmss(kept)})")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Автомонтаж вертикальных Reels")
    parser.add_argument("video", nargs="*", help="файлы; без аргументов — всё из input/")
    parser.add_argument("--preset", default="viral")
    parser.add_argument("--language", default="ru")
    parser.add_argument("--hook", help="текст-хук поверх первых секунд")
    parser.add_argument("--out", help="имя выходного файла (только для одного входного)")
    parser.add_argument("--force", action="store_true", help="пересчитать транскрипт заново")
    parser.add_argument("--no-cut", action="store_true", help="не резать паузы")
    parser.add_argument("--no-subs", action="store_true", help="без субтитров")
    parser.add_argument("--no-motion", action="store_true", help="без смены крупности")
    parser.add_argument("--no-audio", action="store_true", help="не трогать звук")
    parser.add_argument("--encoder", help="h264_videotoolbox (быстро) или libx264 (качественнее)")
    args = parser.parse_args()

    if args.video:
        videos = [Path(v).resolve() for v in args.video]
    else:
        exts = {".mp4", ".mov", ".m4v", ".mkv"}
        videos = sorted(p for p in INPUT_DIR.glob("*") if p.suffix.lower() in exts)

    if not videos:
        sys.exit(f"Нет входных файлов. Положи видео в {INPUT_DIR}/")

    if args.out and len(videos) > 1:
        sys.exit("--out работает только с одним входным файлом")

    OUTPUT_DIR.mkdir(exist_ok=True)
    WORK_DIR.mkdir(exist_ok=True)

    for video in videos:
        if not video.exists():
            print(f"  ✗ не найден: {video}", file=sys.stderr)
            continue
        process(video, args)


if __name__ == "__main__":
    main()
