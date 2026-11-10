#!/usr/bin/env python3
"""Фото → короткий клип с движением (Ken Burns): кадр серии для сборки (25.10.2026).

Валера про «Вкудесник» v01: «вставки фоток долго занимают, супер стрёмно выглядит. Нужен монтаж, который удерживает».
Там стишок, снятый только камерой 360, шёл под двумя неподвижными фото Sony — 7 с почти одного кадра. Фото годятся,
но серией: каждый снимок — секунда, у каждого движение (наезд или сдвиг) и своё кадрирование (общий → лицо → руки).
Клипы этого скрипта ложатся в папку сборки и включаются кусками или камерами (pack.json → cams) поверх звука.

Рамка — (cx, cy, w) в пикселях снимка после поворота по EXIF: центр и ширина окна 9:16. Движение — от рамки from к to
с плавным торможением. Окно уже 720 px снимка — отказ (чёткость вставок, AGENTS.md): вышло бы мутнее 720p.

  .venv/bin/python scripts/photoclip.py фото.JPG out.mp4 --from 1100,3300,2600 --to 1100,3300,2200 --dur 1.2

Один вызов ffmpeg на клип, вход читается один раз (инвариант 1); звук — тишина нужной длины (сборке нужен звук).
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import QUALITY_FLOOR, ffmpeg_bin, probe  # noqa: E402
from render import vcodec  # noqa: E402

FPS = 30
PHOTO_TAG = "photoclip"      # метка в comment клипа: по ней pack.py узнаёт фото (project.json → photos: false — отказ)
OUT_W, OUT_H = 1080, 1920


class PhotoError(Exception):
    """Понятная ошибка для человека."""


def rotated_size(photo: Path) -> tuple:
    """Размер снимка, как его видит ffmpeg после поворота по EXIF (по кадру, а не по тегам)."""
    raw = subprocess.run([ffmpeg_bin(), "-v", "info", "-i", str(photo), "-frames:v", "1", "-vf",
                          "showinfo", "-f", "null", "-"], capture_output=True, encoding="utf-8", errors="replace")
    import re
    found = re.search(r"\bs:(\d+)x(\d+)", raw.stderr)
    if not found:
        info = probe(photo)
        return info["width"], info["height"]
    return int(found.group(1)), int(found.group(2))


def box(spec: str, size: tuple) -> tuple:
    try:
        cx, cy, w = (float(v) for v in spec.split(","))
    except ValueError:
        raise PhotoError(f"рамка «{spec}» — три числа cx,cy,w")
    h = w * OUT_H / OUT_W
    W, H = size
    if w < QUALITY_FLOOR:
        raise PhotoError(f"рамка {spec}: окно {w:.0f} px снимка — мутнее {QUALITY_FLOOR}p, так не берём")
    if cx - w / 2 < 0 or cx + w / 2 > W or cy - h / 2 < 0 or cy + h / 2 > H:
        raise PhotoError(f"рамка {spec} ({w:.0f}×{h:.0f}) вылезает за снимок {W}×{H}")
    return cx, cy, w


def make(photo: Path, out: Path, a: tuple, b: tuple, dur: float) -> None:
    n = max(2, round(dur * FPS))
    size = rotated_size(photo)
    a, b = box(",".join(map(str, a)), size), box(",".join(map(str, b)), size)
    # p — доля пути с торможением (easeOutCubic): 1 − (1 − on/(n−1))³
    p = f"(1-pow(1-on/{n - 1},3))"
    w = f"({a[2]}+({b[2]}-{a[2]})*{p})"
    cx, cy = f"({a[0]}+({b[0]}-{a[0]})*{p})", f"({a[1]}+({b[1]}-{a[1]})*{p})"
    zoom = f"iw/{w}"
    # zoompan берёт окно iw/z × ih/z — пропорции входа: снимок дополняется до 9:16 полями справа и снизу (рамка в них не
    # заходит — проверено выше), иначе картинку сплющило бы
    vf = (f"pad=w='max(iw,ih*{OUT_W}/{OUT_H})':h='max(ih,iw*{OUT_H}/{OUT_W})':x=0:y=0,zoompan=z='{zoom}':x='{cx}-{w}/2':y='{cy}-{w}*{OUT_H / OUT_W:.6f}/2':d={n}:s={OUT_W}x{OUT_H}:fps={FPS},"
          f"setsar=1,format=yuv420p,trim=end_frame={n}")
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_name(f".{out.stem}.part{out.suffix}")
    try:
        result = subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(photo),
                                 "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                                 "-filter_complex", f"[0:v]{vf}[v];[1:a]atrim=end_sample={round(n / FPS * 48000)}[a]",
                                 "-map", "[v]", "-map", "[a]", "-r", str(FPS),
                                 *vcodec({"bitrate": "20M"}, "segment"), "-color_primaries", "bt709", "-color_trc", "bt709",
                                 "-colorspace", "bt709", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                                 "-metadata", f"comment={PHOTO_TAG} {photo.name}",
                                 str(part)], capture_output=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise PhotoError(f"ffmpeg не собрал клип из {photo.name}:\n{result.stderr[-600:]}")
        got = probe(part)["duration"]
        if abs(got - n / FPS) > 1.5 / FPS:
            raise PhotoError(f"{out.name}: вышло {got:.3f} с вместо {n / FPS:.3f} — не отдаю")
        part.replace(out)
    finally:
        part.unlink(missing_ok=True)
    print(f"{out.name}: {photo.name} {n / FPS:.2f} с, окно {a[2]:.0f} → {b[2]:.0f} px")


def main():
    ap = argparse.ArgumentParser(description="Фото → клип с движением (Ken Burns)")
    ap.add_argument("photo", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--from", dest="a", required=True, help="cx,cy,w — рамка в начале")
    ap.add_argument("--to", dest="b", required=True, help="cx,cy,w — рамка в конце")
    ap.add_argument("--dur", type=float, required=True)
    args = ap.parse_args()
    try:
        make(args.photo, args.out, tuple(float(v) for v in args.a.split(",")),
             tuple(float(v) for v in args.b.split(",")), args.dur)
    except PhotoError as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
