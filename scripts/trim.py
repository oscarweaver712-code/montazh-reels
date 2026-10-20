#!/usr/bin/env python3
"""Обрезка начала и конца готового ролика — без пересборки страницы и пересчёта слоёв (20.10.2026).

Валера про IMG_3645 v1: «правок хуй да нихуя — почему всё заново?» — ролик открывался полусекундой вдоха, и ради
неё план был: дубль заново, маска заново (BiRefNet ≈ 12 мин), автопилот. А готовый ролик уже несёт все слои —
камеру, вырезку, графику, субтитры, звук, — и срез по кадру сдвигает их вместе. Здесь одно перекодирование:

  • граница — на сетке кадров (инвариант 4): видео режется trim по номеру кадра, звук — atrim ровно по той же
    секунде, длина — целое число кадров;
  • граница — в тишине (инвариант 3): голос ближе GUARD к срезу (common.detect_voice) — отказ с ближайшим тихим
    кадром, слово не обрывается;
  • вход читается один раз (инвариант 1), временный файл — рядом с выходом и убирается в finally (инвариант 5);
  • кодек — host (аппаратный на Mac, libx264 с потоками на Windows), звук — как у мастеринга (AAC 192k, 48 кГц).

  .venv/bin/python scripts/trim.py projects/antishkola/output/IMG_3645_v2.mp4 --head 16      # первые 16 кадров, на месте
  .venv/bin/python scripts/trim.py <ролик> --head 16 --tail 30 --out <куда>                  # и 30 кадров с конца
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import detect_voice, ffmpeg_bin, probe, require_queue  # noqa: E402

GUARD = 0.04            # с: голос ближе к срезу — режется слово


class TrimError(ValueError):
    """Срез нельзя сделать так, как просили, — по-русски, что выбрать вместо."""


def plan(video: Path, head: int, tail: int) -> dict:
    """Кадры и секунды среза, проверенные по звуку: {'fps', 'frames', 'start', 'end'}."""
    info = probe(video)
    fps = info["fps"]
    total = int(round(info["duration"] * fps))
    if head < 0 or tail < 0 or head + tail >= total:
        raise TrimError(f"{video.name}: {total} кадров — срезать {head} с начала и {tail} с конца нельзя")
    start, end = head / fps, (total - tail) / fps
    if info["has_audio"]:
        voice = detect_voice(video)
        for cut, side in [(start, "начала")] * bool(head) + [(end, "конца")] * bool(tail):
            hit = [(a, b) for a, b in voice if a - GUARD < cut < b + GUARD]
            if hit:
                a, b = hit[0]
                before, after = int((a - GUARD) * fps), int((b + GUARD) * fps) + 1
                raise TrimError(f"срез {side} на {cut:.3f} с режет голос ({a:.2f}–{b:.2f} с): ближайшие тихие кадры — "
                                f"{before} ({before / fps:.3f} с) или {after} ({after / fps:.3f} с)")
    return {"fps": fps, "frames": total - head - tail, "start": start, "end": end, "head": head}


def trim(src: Path, dst: Path, head: int, tail: int = 0) -> dict:
    """Срез по кадрам; dst может совпадать с src — тогда файл заменяется целиком, только когда новый готов."""
    from render import vcodec
    cut = plan(src, head, tail)
    fps, n = cut["fps"], cut["frames"]
    graph = (f"[0:v]trim=start_frame={head}:end_frame={head + n},setpts=PTS-STARTPTS[v];"
             f"[0:a]atrim=start={cut['start']:.6f}:end={cut['end']:.6f},asetpts=PTS-STARTPTS[a]")
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f".{dst.stem}.trim{dst.suffix}")
    try:
        result = subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(src), "-filter_complex", graph,
                                 "-map", "[v]", "-map", "[a]", *vcodec({"encoder": "auto", "bitrate": "12M"}, "final"),
                                 "-pix_fmt", "yuv420p", "-r", f"{fps:g}", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                                 "-movflags", "+faststart", str(tmp)],
                                capture_output=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"Обрезка {src.name} упала:\n{result.stderr[-500:]}")
        got = probe(tmp)
        if abs(got["duration"] * fps - n) > 1.0:
            raise RuntimeError(f"после обрезки {got['duration'] * fps:.1f} кадров вместо {n} — файл не отдан")
        tmp.replace(dst)
    finally:
        tmp.unlink(missing_ok=True)
    return {**cut, "duration": round(n / fps, 3)}


def main():
    ap = argparse.ArgumentParser(description="Обрезать начало и конец готового ролика по кадрам, срез — в тишине")
    ap.add_argument("video")
    ap.add_argument("--head", type=int, default=0, help="кадров срезать с начала")
    ap.add_argument("--tail", type=int, default=0, help="кадров срезать с конца")
    ap.add_argument("--out", help="куда (по умолчанию — заменить исходный файл, когда новый готов)")
    args = ap.parse_args()
    require_queue("обрезка ролика")
    src = Path(args.video)
    if not src.is_file():
        sys.exit(f"✗ нет файла {src}")
    try:
        done = trim(src, Path(args.out) if args.out else src, args.head, args.tail)
    except TrimError as e:
        sys.exit(f"✗ {e}")
    print(f"✓ {Path(args.out or src).name}: срезано {args.head} кадров с начала и {args.tail} с конца, "
          f"{done['frames']} кадров ({done['duration']:.3f} с)")


if __name__ == "__main__":
    main()
