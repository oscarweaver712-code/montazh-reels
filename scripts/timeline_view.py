#!/usr/bin/env python3
"""Кусок ролика одной картинкой: кадры, волна звука, слова и тишина — чтобы «увидеть» рез.

Идея из video-use (browser-use): агент не смотрит видео кадр за кадром — он читает
текст, а на спорных местах смотрит такую картинку. Сверху плёнка кадров, под ней волна
звука с настоящей тишиной (красным — там можно резать), снизу слова по их таймингам.
Видно сразу: обрывается ли слово на резе, не прыгает ли кадр, не висит ли графика.

Только ffmpeg (кадры, волна, слова через libass) — новых зависимостей нет. Один процесс
за раз, память не растёт: кадры берутся по одному seek'у.

  .venv/bin/python scripts/timeline_view.py work/IMG_3279/aroll.mp4 10 16
  .venv/bin/python scripts/timeline_view.py output/IMG_3279_v1.mp4 41.5 44.5 --frames 10
  → work/_views/IMG_3279_aroll_10.00-16.00.png (путь печатается последней строкой)
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import FONT_DIR, WORK_DIR, detect_silence, ffmpeg_bin, probe, ts

VIEWS = WORK_DIR / "_views"
STRIP_H = 240          # высота кадра на плёнке
WAVE_H = 150
WORDS_H = 126


def guess_words(video: Path) -> Path | None:
    """Слова к файлу: aroll.words.json рядом с дублем или work/<имя>.words.json исходника."""
    near = video.with_name(video.stem + ".words.json")
    if near.exists():
        return near
    by_stem = WORK_DIR / f"{video.stem}.words.json"
    if by_stem.exists():
        return by_stem
    # готовый ролик output/IMG_3279_v2.mp4 (или вариант IMG_3279--hormozi_v1) идёт по шкале дубля
    match = re.fullmatch(r"(.+?)(?:--[\w-]+)?_v\d+", video.stem)
    if match:
        aroll = WORK_DIR / match.group(1) / "aroll.words.json"
        if aroll.exists():
            return aroll
    return None


def words_ass(words: list, start: float, end: float, width: int, out: Path) -> Path:
    """Слова на полосе: каждое у своего начала по времени, в три ряда — соседние не слипаются."""
    span = end - start
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {WORDS_H}", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
             "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
             "Alignment, MarginL, MarginR, MarginV, Encoding",
             "Style: W,Manrope ExtraBold,22,&H00F0F0F0,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
             "Style: T,Manrope ExtraBold,13,&H00909090,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
             "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    shown = [w for w in words if w["end"] > start and w["start"] < end]
    for i, w in enumerate(shown):
        x = int((max(w["start"], start) - start) / span * width)
        y = 4 + (i % 3) * 40
        text = w["word"].strip().replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{ts(0)},{ts(1)},W,,0,0,0,,{{\\pos({x + 3},{y})}}{text}")
        lines.append(f"Dialogue: 0,{ts(0)},{ts(1)},T,,0,0,0,,{{\\pos({x + 3},{y + 23})}}{w['start']:.2f}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def run(cmd: list, what: str, cwd: Path | None = None):
    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg не собрал {what}:\n" + "\n".join(result.stderr.strip().splitlines()[-8:]))


def timeline_view(video: Path, start: float, end: float, frames: int = 8,
                  words_path: Path | None = None, out: Path | None = None) -> Path:
    info = probe(video)
    end = min(end, info["duration"])
    if end - start < 0.2:
        raise ValueError(f"Слишком короткий кусок: {start:.2f}–{end:.2f} с")
    frame_w = int(round(STRIP_H * info["width"] / info["height"] / 2)) * 2
    width = frame_w * frames
    span = end - start
    VIEWS.mkdir(parents=True, exist_ok=True)
    out = out or VIEWS / f"{video.parent.name}_{video.stem}_{start:.2f}-{end:.2f}.png"
    words = []
    words_path = words_path or guess_words(video)
    if words_path and words_path.exists():
        words = json.loads(words_path.read_text(encoding="utf-8")).get("words", [])

    tmp = Path(tempfile.mkdtemp(prefix="reels_view_"))
    try:
        # 1. плёнка: кадр из середины каждого отрезка, по одному seek'у
        tiles = []
        # шрифт — рядом и по относительному пути: «C:\\…» на Windows ломает синтаксис фильтра
        shutil.copy2(FONT_DIR / "JetBrainsMono.ttf", tmp / "mono.ttf")
        for i in range(frames):
            at = start + span * (i + 0.5) / frames
            tile = tmp / f"f{i:02d}.png"
            run([ffmpeg_bin(), "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1",
                 "-vf", f"scale={frame_w}:{STRIP_H},drawtext=fontfile=mono.ttf:"
                        f"text='{at:.2f}':x=6:y=6:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6",
                 tile.name], f"кадр {at:.2f} с", cwd=tmp)
            tiles.append(tile)
        strip = tmp / "strip.png"
        inputs = sum((["-i", str(t)] for t in tiles), [])
        run([ffmpeg_bin(), "-v", "error", "-y", *inputs, "-filter_complex",
             "".join(f"[{i}]" for i in range(frames)) + f"hstack={frames}", str(strip)], "плёнку")

        # 2. волна звука и настоящая тишина красным — туда рез не отрежет слово
        wave = tmp / "wave.png"
        silence = [(max(a, start), min(b, end)) for a, b in detect_silence(video)
                   if b > start and a < end]
        boxes = "".join(f",drawbox=x={int((a - start) / span * width)}:y=0:"
                        f"w={max(1, int((b - a) / span * width))}:h={WAVE_H}:color=red@0.22:t=fill"
                        for a, b in silence)
        run([ffmpeg_bin(), "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{span:.3f}", "-i", str(video),
             "-filter_complex", f"[0:a]aformat=channel_layouts=mono,showwavespic=s={width}x{WAVE_H}:"
                                f"colors=0x3BE8B0,format=rgba[w];color=c=0x101317:s={width}x{WAVE_H}[bg];"
                                f"[bg][w]overlay=format=auto,format=rgb24{boxes}",
             "-frames:v", "1", str(wave)], "волну звука")

        # 3. слова по их таймингам (libass — кириллица и позиции без сюрпризов)
        band = tmp / "words.png"
        chain = f"color=c=0x0B0D10:s={width}x{WORDS_H}:d=1"
        if words:
            ass = words_ass(words, start, end, width, tmp / "words.ass")
            shutil.copy2(FONT_DIR / "Manrope-ExtraBold.ttf", tmp / "Manrope-ExtraBold.ttf")
            chain += f",ass=f={ass.name}:fontsdir=."
        run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", chain, "-frames:v", "1", band.name],
            "полосу слов", cwd=tmp)

        run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(strip), "-i", str(wave), "-i", str(band),
             "-filter_complex", "[0][1][2]vstack=3", str(out)], "сводную картинку")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser(description="Кадры + волна звука + слова куска ролика одной картинкой")
    ap.add_argument("video")
    ap.add_argument("start", type=float)
    ap.add_argument("end", type=float)
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--words", help="words.json (по умолчанию ищется рядом с видео или в work/)")
    ap.add_argument("--out", help="куда положить png")
    args = ap.parse_args()
    video = Path(args.video).resolve()
    if not video.exists():
        sys.exit(f"Нет файла: {video}")
    try:
        out = timeline_view(video, args.start, args.end, max(2, min(16, args.frames)),
                            Path(args.words) if args.words else None,
                            Path(args.out) if args.out else None)
    except (ValueError, RuntimeError) as e:
        sys.exit(f"✗ {e}")
    print(out)


if __name__ == "__main__":
    main()
