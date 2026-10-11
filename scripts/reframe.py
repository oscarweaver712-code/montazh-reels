#!/usr/bin/env python3
"""Перекадрирование по лицу: исходник одних пропорций → ролик других, без обрезки по центру.

Горизонтальный урок под Reels раньше резался по центру: стоило спикеру отойти к доске —
он уезжал из кадра. Здесь окно нужных пропорций ведёт камера-оператор (track.py): за лицом,
с мёртвой зоной, плавно, и никогда не выходит за исходник — кадр всегда полный.

Окно постоянного размера (зум 1.0): двигаются только x и y. Поэтому один вызов ffmpeg с
sendcmd — память постоянная, длина ролика на неё не влияет (CLAUDE.md, инвариант 1).
Приближения и акценты — дальше, на этапе камеры в compose.py.

  .venv/bin/python scripts/reframe.py input/urok.mov --format 9:16
  → work/urok/urok.9x16.mov (звук скопирован без пережатия, тайминги те же)
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import formats
import host
from common import WORK_DIR, ffmpeg_bin, probe
from track import coverage_violations, detect_faces, solve_camera

COLOR_TAGS = ["-color_range", "tv", "-colorspace", "bt709",
              "-color_primaries", "bt709", "-color_trc", "bt709"]


def reframe_path(faces: dict, fmt: str) -> tuple:
    """Окно (ширина, высота) и путь камеры [(1.0, cx, cy)] по кадрам исходника."""
    window = formats.window(faces["width"], faces["height"], formats.aspect(fmt))
    cfg = {"base_zoom": 1.0, "max_zoom": 1.0, "window": window, "target_y": None,
           # в узком окне шаг заметнее: камера едет раньше и доезжает мягче
           "dead_zone_x": 0.08, "follow_sec": 0.6}
    camera = solve_camera(faces, cfg)
    bad = coverage_violations(camera, faces["width"], faces["height"], window=window)
    if bad:
        raise RuntimeError(f"Окно перекадрирования вышло за исходник на {len(bad)} кадрах — "
                           "так быть не должно, сборка остановлена")
    return window, camera


def crop_origin(camera_frame: tuple, window: tuple, width: int, height: int) -> tuple:
    """Левый верхний угол окна в целых пикселях, чётный (4:2:0) и внутри кадра."""
    _, cx, cy = camera_frame
    w, h = window
    x = int(round(cx - w / 2)) // 2 * 2
    y = int(round(cy - h / 2)) // 2 * 2
    return (max(0, min(int(width - w) // 2 * 2, x)), max(0, min(int(height - h) // 2 * 2, y)))


def write_commands(camera: list, window: tuple, fps: float, width: int, height: int,
                   path: Path) -> tuple:
    """Файл sendcmd: команда только там, где окно сдвинулось. Возвращает начальный угол."""
    lines, last = [], None
    for i, frame in enumerate(camera):
        origin = crop_origin(frame, window, width, height)
        if origin != last:
            if last is not None:
                lines.append(f"{i / fps:.4f} crop@cam x {origin[0]}, crop@cam y {origin[1]};")
            last = origin
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return crop_origin(camera[0], window, width, height)


def apply(video: Path, out: Path, camera: list, window: tuple, fps: float, fmt: str,
          width: int, height: int, bitrate: str = "30M") -> Path:
    """Один проход ffmpeg: окно едет по sendcmd, кадр масштабируется под формат."""
    out_w, out_h = formats.size(fmt)
    w, h = (int(window[0]) // 2 * 2, int(window[1]) // 2 * 2)
    cmds = out.with_suffix(".cmds.txt")
    tmp = out.with_name(f".{out.name}")
    try:
        x0, y0 = write_commands(camera, (w, h), fps, width, height, cmds)
        chain = (f"sendcmd=f='{cmds.name}',crop@cam=w={w}:h={h}:x={x0}:y={y0}:exact=1,"
                 f"scale={out_w}:{out_h}:flags=lanczos:out_range=tv,format=yuv420p,setsar=1")
        encoder = host.video_encoder("auto", ffmpeg_bin())
        # промежуточный файл: качество почти без потерь, его ещё раз пережмёт сборка
        quality = (["-c:v", encoder, "-b:v", bitrate, "-profile:v", "high"] if encoder != "libx264"
                   else ["-c:v", "libx264", "-crf", "14", "-preset", "veryfast",
                         "-threads", str(host.encoder_threads())])
        cmd = [ffmpeg_bin(), "-v", "error", "-y", "-i", str(video.resolve()), "-vf", chain,
               "-map", "0:v:0", "-map", "0:a?", *quality,
               "-fps_mode", "passthrough", "-pix_fmt", "yuv420p", *COLOR_TAGS,
               "-c:a", "copy", str(tmp.name)]
        result = subprocess.run(cmd, cwd=out.parent, capture_output=True, encoding="utf-8", errors="replace")
        if result.returncode != 0 or not tmp.exists():
            raise RuntimeError("ffmpeg не собрал перекадрированный исходник:\n"
                               + "\n".join(result.stderr.strip().splitlines()[-12:]))
        tmp.replace(out)
    finally:
        tmp.unlink(missing_ok=True)
        cmds.unlink(missing_ok=True)
    return out


def target_path(video: Path, fmt: str) -> Path:
    # имя уникально для ролика: render.py называет свои временные куски по имени исходника
    return WORK_DIR / video.stem / f"{video.stem}.{fmt.replace(':', 'x')}.mov"


def reframe(video: Path, fmt: str, force: bool = False) -> Path:
    """Перекадрированный исходник (кэш по времени изменения); при совпадении пропорций — сам исходник."""
    info = probe(video)
    if formats.same_aspect(info["width"], info["height"], fmt):
        return video
    out = target_path(video, fmt)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not force and out.stat().st_mtime > video.stat().st_mtime:
        print(f"  → перекадрирование под {fmt} уже есть: {out.name}")
        return out

    started = time.time()
    print(f"  → перекадрирую {info['width']}×{info['height']} под {fmt}: ищу лицо (YuNet)", flush=True)
    faces = detect_faces(video)
    share = faces["found"] / max(1, len(faces["frames"]))
    if share < 0.3:
        print(f"  ⚠ лицо нашлось только на {share:.0%} кадров — окно будет стоять по центру там, где его нет")
    window, camera = reframe_path(faces, fmt)
    (out.with_suffix(".path.json")).write_text(json.dumps({
        "format": fmt, "window": window, "fps": faces["fps"], "found": share,
        "x": [round(c[1], 1) for c in camera]}), encoding="utf-8")
    apply(video, out, camera, window, faces["fps"], fmt, faces["width"], faces["height"])
    print(f"  ✓ перекадрировано за {time.time() - started:.0f} с → {out.relative_to(WORK_DIR.parent)}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Перекадрирование исходника по лицу под другой формат")
    ap.add_argument("video")
    ap.add_argument("--format", default=formats.DEFAULT, help=", ".join(formats.FORMATS))
    ap.add_argument("--force", action="store_true", help="пересчитать, даже если уже есть")
    args = ap.parse_args()
    video = Path(args.video).resolve()
    if not video.exists():
        sys.exit(f"Нет файла: {video}")
    try:
        formats.get(args.format)
        out = reframe(video, args.format, args.force)
    except (ValueError, RuntimeError) as e:
        sys.exit(f"✗ {e}")
    if out == video:
        print(f"  · пропорции исходника уже {args.format} — перекадрировать нечего")


if __name__ == "__main__":
    main()
