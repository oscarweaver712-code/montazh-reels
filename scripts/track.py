#!/usr/bin/env python3
"""Слежение за лицом и виртуальная камера.

Главное правило: кадр никогда не «вылезает». Окно камеры всегда целиком внутри
исходника, поэтому пустых полос по краям не бывает в принципе — ни на резком
движении, ни на зуме, ни когда лицо потерялось. Чтобы было куда ехать за лицом,
камера всегда чуть приближена (base_zoom): при 1.12 запас по бокам ~58 px исходника.
Если человек уходит к краю дальше запаса, приближение плавно подрастает (до
max_zoom), а не окно уезжает за границу. Это проверяется на каждом кадре, и если
вдруг нарушено — сборка падает с ошибкой, а не отдаёт ролик с дырой.

Камера ведёт себя как оператор, а не как прицел: мелкие покачивания головы она
пропускает (мёртвая зона), за заметным сдвигом едет плавно.

  .venv/bin/python scripts/track.py work/IMG_3279/aroll.mp4

Лица ищет Apple Vision (встроен в macOS, считает на нейроядре): процессор почти
не нагружается, модели качать не нужно.
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d, maximum_filter1d, median_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ffmpeg_bin, probe

DEFAULTS = {
    "base_zoom": 1.12,     # постоянный запас на слежение; 1.0 = ехать некуда
    "max_zoom": 1.32,      # потолок: исходник 1080p, дальше картинка заметно мылится
    "target_x": 0.5,       # где держать центр лица по горизонтали (доля ширины кадра)
    "target_y": None,      # по вертикали; None — там, где лицо было при съёмке
    "dead_zone_x": 0.035,  # покачивания меньше этого (доля ширины) камера пропускает
    "dead_zone_y": 0.025,
    "follow_sec": 0.45,    # плавность доезда камеры
    "smooth_sec": 0.12,    # сглаживание дрожи самого детектора
}


# ---------------------------------------------------------------- поиск лиц

def detect_faces(video: Path, analysis_width: int = 540) -> dict:
    """Лицо на каждом кадре: центр и размер в пикселях исходника, или None.

    Кадры идут из ffmpeg по одному через канал: память не растёт с длиной ролика.
    Для поиска хватает уменьшенного кадра — лицо крупное, а считается вчетверо быстрее.
    """
    import objc
    import Quartz
    import Vision

    info = probe(video)
    width, height, fps = info["width"], info["height"], info["fps"]
    w = analysis_width
    h = int(round(height * w / width / 2) * 2)
    frame_bytes = w * h * 4

    proc = subprocess.Popen(
        [ffmpeg_bin(), "-v", "error", "-i", str(video), "-an",
         "-vf", f"scale={w}:{h}", "-pix_fmt", "rgba", "-f", "rawvideo", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    colorspace = Quartz.CGColorSpaceCreateDeviceRGB()
    handler = Vision.VNSequenceRequestHandler.alloc().init()
    frames = []
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            with objc.autorelease_pool():
                # Только через CFData. CGDataProviderCreateWithData без функции освобождения
                # навсегда держит каждый кадр: +2 МБ на кадр, 2,4 ГБ на минутном ролике.
                provider = Quartz.CGDataProviderCreateWithCFData(
                    Quartz.CFDataCreate(None, buf, frame_bytes))
                image = Quartz.CGImageCreate(
                    w, h, 8, 32, w * 4, colorspace, Quartz.kCGImageAlphaNoneSkipLast,
                    provider, None, False, Quartz.kCGRenderingIntentDefault)
                request = Vision.VNDetectFaceRectanglesRequest.alloc().init()
                ok, error = handler.performRequests_onCGImage_error_([request], image, None)
                if not ok:
                    raise RuntimeError(f"Apple Vision не смог разобрать кадр {len(frames)}: {error}")
                best = None
                for face in request.results() or []:
                    (x, y), (fw, fh) = face.boundingBox()
                    if best is None or fw * fh > best[2] * best[3]:
                        best = (x, y, fw, fh, float(face.confidence()))
                if best is None:
                    frames.append(None)
                else:
                    x, y, fw, fh, conf = best
                    # у Vision начало координат внизу слева, у видео — вверху слева
                    frames.append([round((x + fw / 2) * width, 1),
                                   round((1 - (y + fh / 2)) * height, 1),
                                   round(fw * width, 1), round(fh * height, 1),
                                   round(conf, 3)])
            if len(frames) % 300 == 0:
                print(f"     {len(frames)} кадров", flush=True)
    finally:
        proc.stdout.close()
        stderr = proc.stderr.read().decode(errors="replace")
        proc.wait()
    if proc.returncode not in (0, None) and not frames:
        raise RuntimeError(f"ffmpeg не отдал кадры для поиска лица:\n{stderr[-600:]}")
    if not frames:
        raise RuntimeError("В видео нет ни одного кадра — искать лицо не в чем")

    found = sum(1 for f in frames if f)
    return {"fps": fps, "width": width, "height": height,
            "found": found, "frames": frames}


# ---------------------------------------------------------------- камера

def _fill_gaps(values: np.ndarray) -> np.ndarray:
    """Пропуски детектора (рука перед лицом, отвернулся) — линейно между соседями."""
    good = ~np.isnan(values)
    if not good.any():
        return values
    idx = np.arange(len(values))
    return np.interp(idx, idx[good], values[good])


def _lazy_follow(series: np.ndarray, dead: float) -> np.ndarray:
    """Камера-оператор: стоит, пока цель внутри мёртвой зоны, и едет, когда вышла."""
    out = np.empty_like(series)
    anchor = series[0]
    for i, value in enumerate(series):
        if value > anchor + dead:
            anchor = value - dead
        elif value < anchor - dead:
            anchor = value + dead
        out[i] = anchor
    return out


def clamp_centers(zoom: np.ndarray, cx: np.ndarray, cy: np.ndarray,
                  width: int, height: int, window: tuple | None = None) -> tuple:
    """Окно камеры обязано целиком лежать внутри исходника — отсюда и полный кадр.

    window — размер окна при зуме 1.0 (formats.window). По умолчанию равен исходнику:
    пропорции ролика и съёмки совпадают. Горизонтальный исходник под вертикаль даёт
    узкое окно во всю высоту — и ему есть куда ехать вбок за лицом.
    """
    win_w, win_h = window or (width, height)
    half_w, half_h = win_w / (2 * zoom), win_h / (2 * zoom)
    return (np.clip(cx, half_w, width - half_w), np.clip(cy, half_h, height - half_h))


def coverage_violations(camera: list, width: int, height: int, eps: float = 1e-6,
                        window: tuple | None = None) -> list:
    """Номера кадров, где окно камеры выходит за исходник (там была бы пустота)."""
    win_w, win_h = window or (width, height)
    bad = []
    for i, (z, cx, cy) in enumerate(camera):
        half_w, half_h = win_w / (2 * z), win_h / (2 * z)
        if (z < 1 - eps or cx - half_w < -eps or cx + half_w > width + eps
                or cy - half_h < -eps or cy + half_h > height + eps):
            bad.append(i)
    return bad


def zoom_plan(n: int, fps: float, base: float, punches: list, offset: float = 0.0) -> np.ndarray:
    """Базовое приближение плюс акценты режиссёра: [начало, конец, зум, въезд, выезд].

    Въезд 0 — мгновенный скачок крупности (так прячут склейку), выезд по умолчанию равен
    въезду. offset — с какой секунды ролика начинается этот кусок (для резки по склейкам).
    """
    zoom = np.full(n, float(base))
    for punch in punches or []:
        start, end, level = float(punch[0]) - offset, float(punch[1]) - offset, float(punch[2])
        ease_in = float(punch[3]) if len(punch) > 3 else 0.35
        ease_out = float(punch[4]) if len(punch) > 4 else ease_in
        for i in range(max(0, int(round(start * fps))), min(n, int(np.ceil(end * fps)))):
            t = i / fps
            rise = min(1.0, (t - start) / ease_in) if ease_in > 0 else 1.0
            fall = min(1.0, (end - t) / ease_out) if ease_out > 0 else 1.0
            k = max(0.0, min(rise, fall))
            k = k * k * (3 - 2 * k)                       # плавный вход и выход
            zoom[i] = max(zoom[i], base + (level - base) * k)
    return zoom


def solve_camera(faces: dict, cfg: dict | None = None, punches: list | None = None,
                 cuts: list | None = None) -> list:
    """Путь камеры по кадрам: [(зум, центр_x, центр_y)] в пикселях исходника.

    cuts — номера кадров, где в дубле склейка. Камера не имеет права «переезжать» через
    рез: по разные стороны склейки человек стоит по-разному, и плавный проезд между ними
    выглядит как съехавший кадр. Поэтому каждый кусок решается отдельно, а на самой
    склейке кадр меняется мгновенно — так монтажёр прячет рез.
    """
    cfg = dict(DEFAULTS, **(cfg or {}))
    frames = faces["frames"]
    bounds = [0] + sorted(c for c in (cuts or []) if 0 < c < len(frames)) + [len(frames)]
    camera = []
    for a, b in zip(bounds, bounds[1:]):
        piece = dict(faces, frames=frames[a:b])
        camera += _solve_piece(piece, cfg, punches, offset=a / faces["fps"])
    bad = coverage_violations(camera, faces["width"], faces["height"], window=cfg.get("window"))
    if bad:
        raise RuntimeError(
            f"Камера вылезла за край исходника на {len(bad)} кадрах (первый — {bad[0]}). "
            "В ролике была бы пустота по краю — сборка остановлена.")
    return camera


def _solve_piece(faces: dict, cfg: dict, punches: list | None, offset: float) -> list:
    """Камера на одном куске без склеек."""
    width, height, fps = faces["width"], faces["height"], faces["fps"]
    win_w, win_h = cfg.get("window") or (width, height)
    frames = faces["frames"]
    n = len(frames)
    if n == 0:
        return []

    px = np.array([f[0] if f else np.nan for f in frames], dtype=float)
    py = np.array([f[1] if f else np.nan for f in frames], dtype=float)
    if np.isnan(px).all():
        # лица нет совсем — камера стоит по центру с базовым запасом, кадр всё равно полный
        px[:] = width / 2
        py[:] = height / 2
    px, py = _fill_gaps(px), _fill_gaps(py)

    # дрожь детектора: медиана выбивает одиночные промахи, гаусс сглаживает остальное
    window = max(3, int(round(fps * 0.3)) | 1)
    sigma = max(0.5, cfg["smooth_sec"] * fps)
    px = gaussian_filter1d(median_filter(px, window, mode="nearest"), sigma, mode="nearest")
    py = gaussian_filter1d(median_filter(py, window, mode="nearest"), sigma, mode="nearest")

    # оператор: пропускает покачивания, едет за заметным сдвигом — и доезжает плавно
    follow = max(0.5, cfg["follow_sec"] * fps)
    # мёртвая зона — доля ОКНА: в узком окне вертикали из горизонтали шаг заметнее
    tx = gaussian_filter1d(_lazy_follow(px, cfg["dead_zone_x"] * win_w), follow, mode="nearest")
    ty = gaussian_filter1d(_lazy_follow(py, cfg["dead_zone_y"] * win_h), follow, mode="nearest")

    # Где держать лицо — доля окна. По вертикали по умолчанию там, где оно было при
    # съёмке; если окно ниже исходника (горизонталь из вертикали) — на верхней трети.
    fx = cfg["target_x"]
    if cfg["target_y"] is not None:
        fy = cfg["target_y"]
    elif abs(win_h - height) < 1:
        fy = float(np.median(py)) / height
    else:
        fy = 0.38

    zoom = zoom_plan(n, fps, cfg["base_zoom"], punches, offset)

    # Сколько надо приблизить, чтобы лицо встало в цель и окно не вылезло. Лицо стоит
    # на доле f окна шириной S/z: левый край окна = лицо − f·S/z ≥ 0, правый ≤ размер.
    need = np.ones(n)
    for coord, frac, win, size in ((tx, fx, win_w, width), (ty, fy, win_h, height)):
        with np.errstate(divide="ignore", invalid="ignore"):
            low = np.where(coord > 0, frac * win / coord, np.inf)
            high = np.where(size - coord > 0, (1 - frac) * win / (size - coord), np.inf)
        need = np.maximum(need, np.maximum(low, high))
    need = np.minimum(need, cfg["max_zoom"])
    # Приближение начинается заранее и отпускает медленно: смотрим на 1.2 с вперёд и назад.
    # Сглаживание широкое (0.5 с): автоматический наезд должен быть спокойным, меньше
    # 1% зума за кадр. Быстрые наезды — это акценты режиссёра, они идут через punches.
    ahead = max(1, int(round(fps * 1.2)))
    need = gaussian_filter1d(maximum_filter1d(need, ahead * 2 + 1, mode="nearest"),
                             fps * 0.5, mode="nearest")
    zoom = np.clip(np.maximum(zoom, need), 1.0, max(cfg["max_zoom"], zoom.max()))

    cx = tx - (fx - 0.5) * win_w / zoom
    cy = ty - (fy - 0.5) * win_h / zoom
    cx, cy = clamp_centers(zoom, cx, cy, width, height, (win_w, win_h))
    # упор в край даёт излом траектории — сглаживаем и прижимаем ещё раз
    cx = gaussian_filter1d(cx, fps * 0.12, mode="nearest")
    cy = gaussian_filter1d(cy, fps * 0.12, mode="nearest")
    cx, cy = clamp_centers(zoom, cx, cy, width, height, (win_w, win_h))

    return _finish(zoom, cx, cy, width, height, (win_w, win_h))


def _finish(zoom, cx, cy, width: int, height: int, window: tuple | None = None) -> list:
    """Путь камеры на выход: [(зум, центр_x, центр_y)], округлённый для camera.js.

    Округление не имеет права вытолкнуть окно за край. Окно, прижатое к краю, после
    round(z, 5) вниз вырастало и вылезало на тысячные пикселя (IMG_3303, кадр 1679).
    Поэтому зум округляется вверх — окно от этого только меньше, — а центр прижимается
    к краю уже с этим зумом и округляется внутрь.
    """
    win_w, win_h = window or (width, height)
    out = []
    for z, x, y in zip(zoom, cx, cy):
        z = math.ceil(round(float(z) * 1e5, 6)) / 1e5
        hw, hh = win_w / (2 * z), win_h / (2 * z)
        x = min(max(round(float(x), 3), math.ceil(hw * 1000) / 1000), math.floor((width - hw) * 1000) / 1000)
        y = min(max(round(float(y), 3), math.ceil(hh * 1000) / 1000), math.floor((height - hh) * 1000) / 1000)
        out.append((z, x, y))
    return out


def css_transform(z: float, cx: float, cy: float, width: int, height: int) -> tuple:
    """(tx, ty, scale) для transform: translate(tx, ty) scale(z) при transform-origin 0 0."""
    return (width / 2 - cx * z, height / 2 - cy * z, z)


# ---------------------------------------------------------------- превью

def preview_sheet(video: Path, camera: list, fps: float, out: Path, samples: int = 6) -> Path:
    """Сверху — исходник и рамка камеры, снизу — что видит зритель. Кадры по очереди."""
    info = probe(video)
    width, height = info["width"], info["height"]
    tw, th = 270, 480
    tmp_dir = out.parent / f".{out.stem}_tiles"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tiles = []
    try:
        picks = np.linspace(0, len(camera) - 1, samples + 2)[1:-1].astype(int)
        for k, idx in enumerate(picks):
            z, cx, cy = camera[idx]
            cw, ch = width / z, height / z
            x0, y0 = int(round(cx - cw / 2)), int(round(cy - ch / 2))
            cw, ch = int(round(cw)) // 2 * 2, int(round(ch)) // 2 * 2
            x0 = max(0, min(width - cw, x0))
            y0 = max(0, min(height - ch, y0))
            t = idx / fps
            full = tmp_dir / f"full_{k}.png"
            framed = tmp_dir / f"framed_{k}.png"
            for target, chain in (
                (full, f"drawbox=x={x0}:y={y0}:w={cw}:h={ch}:color=0x3BE8B0@0.95:t=10,"
                       f"scale={tw}:{th}"),
                (framed, f"crop={cw}:{ch}:{x0}:{y0},scale={tw}:{th}"),
            ):
                subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-ss", f"{t:.3f}",
                                "-i", str(video), "-frames:v", "1", "-vf", chain, str(target)],
                               check=True, capture_output=True)
            tiles.append((full, framed))

        inputs = []
        for full, framed in tiles:
            inputs += ["-i", str(full)]
        for full, framed in tiles:
            inputs += ["-i", str(framed)]
        m = len(tiles)
        graph = (f"{''.join(f'[{i}]' for i in range(m))}hstack={m}[top];"
                 f"{''.join(f'[{m + i}]' for i in range(m))}hstack={m}[bot];"
                 "[top][bot]vstack[out]")
        subprocess.run([ffmpeg_bin(), "-v", "error", "-y", *inputs,
                        "-filter_complex", graph, "-map", "[out]", str(out)],
                       check=True, capture_output=True)
    finally:
        for p in tmp_dir.glob("*"):
            p.unlink()
        tmp_dir.rmdir()
    return out


def main():
    ap = argparse.ArgumentParser(description="Слежение за лицом и путь камеры")
    ap.add_argument("video")
    ap.add_argument("--punches", help="JSON: [[начало, конец, зум, въезд], ...]")
    args = ap.parse_args()

    video = Path(args.video).resolve()
    if not video.exists():
        sys.exit(f"Нет файла: {video}")
    base = video.with_suffix("")

    print("  → ищу лицо на каждом кадре (Apple Vision)", flush=True)
    faces = detect_faces(video)
    share = faces["found"] / max(1, len(faces["frames"]))
    print(f"  → лицо найдено на {faces['found']} из {len(faces['frames'])} кадров ({share:.0%})")
    Path(f"{base}.faces.json").write_text(json.dumps(faces), encoding="utf-8")

    punches = json.loads(args.punches) if args.punches else []
    camera = solve_camera(faces, punches=punches)
    zooms = [z for z, _, _ in camera]
    Path(f"{base}.camera.json").write_text(json.dumps({
        "fps": faces["fps"], "width": faces["width"], "height": faces["height"],
        "frames": camera}), encoding="utf-8")
    print(f"  → камера: зум {min(zooms):.2f}–{max(zooms):.2f}, кадр полный на всех "
          f"{len(camera)} кадрах")

    sheet = preview_sheet(video, camera, faces["fps"], Path(f"{base}.camera.jpg"))
    print(f"  → превью: {sheet}")


if __name__ == "__main__":
    main()
