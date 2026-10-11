#!/usr/bin/env python3
"""Вырезка человека из дубля: маска по кадрам и прозрачное видео поверх фона.

Маска нужна для двух вещей: крупное слово ЗА спиной (текст между фоном и человеком)
и замена фона. Движки — открытые и одинаково работают на Mac и Windows:

  mediapipe — MediaPipe Selfie Multiclass (Apache-2.0), по умолчанию. Классы «волосы, кожа,
              одежда» дают человека вместе с тем, что у него в руках: банку из IMG_3317 он
              держит даже в смазанном кадре, где прежний Apple Vision её терял. Края доводятся
              по самому кадру (guided filter), полупрозрачная дымка по контуру сжимается.
  rvm       — Robust Video Matting (GPL-3.0), запасной: помнит прошлые кадры, но выкидывает
              предметы из рук. Нужен torch.

Замер 11.10.2026 на IMG_3279/3305/3317 против масок Apple Vision (до этого дня был он):
MediaPipe совпал на 94–96% (RVM — на 88–92%), а на спорных кадрах выглядит не хуже.

Кадры идут по одному через канал ffmpeg → модель → ffmpeg: память не зависит от
длины ролика. Потоки ограничены, чтобы ноутбук оставался живым.

  .venv/bin/python scripts/matte.py work/IMG_3279/aroll.mp4 --cutout
"""
import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import host
import models
from common import ffmpeg_bin, probe


class MediaPipeMatte:
    """MediaPipe Selfie Multiclass: человек = всё, кроме класса «фон», с доводкой краёв по кадру."""

    def __init__(self, width: int, height: int):
        import cv2
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        cv2.setNumThreads(host.encoder_threads())
        self.cv2, self.mp = cv2, mp
        self.width, self.height = width, height
        options = vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=str(models.ensure("selfie_multiclass", download=False))),
            running_mode=vision.RunningMode.VIDEO, output_confidence_masks=True, output_category_mask=False)
        self.segmenter = vision.ImageSegmenter.create_from_options(options)
        self.ms = 0
        # доводка краёв считается на половинном кадре: на глаз то же, а вчетверо быстрее
        self.half = (max(2, width // 2), max(2, height // 2))

    def __call__(self, rgba: bytes) -> np.ndarray:
        cv2 = self.cv2
        frame = np.frombuffer(rgba, np.uint8).reshape(self.height, self.width, 4)[:, :, :3]
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(frame))
        result = self.segmenter.segment_for_video(image, self.ms)
        self.ms += 33                                   # метки времени обязаны расти
        person = 1.0 - np.asarray(result.confidence_masks[0].numpy_view(), np.float32)   # класс 0 — фон
        alpha = cv2.resize(person, self.half, interpolation=cv2.INTER_LINEAR)
        # уверенность 0.35–0.65 — та самая дымка вокруг контура: сжимаем её в плавную ступень
        alpha = np.clip((alpha - 0.35) / 0.30, 0.0, 1.0)
        alpha = alpha * alpha * (3.0 - 2.0 * alpha)
        guide = cv2.cvtColor(cv2.resize(frame, self.half, interpolation=cv2.INTER_AREA),
                             cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
        alpha = guided_filter(guide, alpha, 4, 1e-3, cv2)           # край маски — по краю в кадре
        alpha = drop_islands(np.clip(alpha, 0.0, 1.0), cv2)
        alpha = cv2.resize(alpha, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
        return np.clip(alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)


def guided_filter(guide: np.ndarray, src: np.ndarray, radius: int, eps: float, cv2) -> np.ndarray:
    """Управляемый фильтр (He, Sun, Tang 2010): сглаживает маску, а край ведёт по краю в кадре.

    Свой, на box-фильтрах ядра OpenCV, а не cv2.ximgproc: тот есть только в contrib-сборке,
    а какая сборка OpenCV окажется в окружении, решают зависимости (MediaPipe тянет contrib,
    распознавание текста — обычную) — маска не должна зависеть от этой лотереи.
    """
    # край кадра отражается так же, как в справочном cv2.ximgproc.guidedFilter: результат совпадает
    box = lambda x: cv2.boxFilter(x, -1, (2 * radius + 1, 2 * radius + 1), borderType=cv2.BORDER_REFLECT)
    mean_i, mean_p = box(guide), box(src)
    var_i = box(guide * guide) - mean_i * mean_i
    cov_ip = box(guide * src) - mean_i * mean_p
    a = cov_ip / (var_i + eps)
    b = mean_p - a * mean_i
    return box(a) * guide + box(b)


def drop_islands(alpha: np.ndarray, cv2, share: float = 0.003) -> np.ndarray:
    """Убирает мелкие оторванные пятна (кусок шторы, лист растения): человек — одно целое."""
    solid = (alpha >= 0.5).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(solid, connectivity=8)
    if count <= 2:
        return alpha
    limit = share * alpha.size
    small = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] < limit]
    if small:
        alpha = alpha.copy()
        alpha[np.isin(labels, small)] = 0.0
    return alpha


class RvmMatte:
    """Robust Video Matting: рекуррентная сеть, память о прошлых кадрах держит края."""

    def __init__(self, width: int, height: int, downsample: float = 0.25):
        import torch
        model = models.ensure("rvm", download=False)
        torch.set_num_threads(host.encoder_threads())            # пара ядер машине
        self.torch = torch
        self.device = torch.device("mps" if torch.backends.mps.is_available() else
                                   "cuda" if torch.cuda.is_available() else "cpu")
        self.model = torch.jit.load(str(model), map_location=self.device).eval()
        self.state = [None] * 4
        self.downsample = downsample
        self.width, self.height = width, height

    def __call__(self, rgba: bytes) -> np.ndarray:
        torch = self.torch
        frame = np.frombuffer(rgba, dtype=np.uint8).reshape(self.height, self.width, 4)[:, :, :3]
        with torch.no_grad():
            src = torch.from_numpy(frame.copy()).to(self.device)
            src = src.permute(2, 0, 1).unsqueeze(0).float().div_(255)
            _, alpha, *self.state = self.model(src, *self.state, self.downsample)
            out = alpha[0, 0].mul(255).round().clamp(0, 255).to(torch.uint8).cpu().numpy()
        return out


BACKENDS = {"mediapipe": MediaPipeMatte, "rvm": RvmMatte}


def run_matte(video: Path, backend: str, out: Path) -> dict:
    """Маска по кадрам в серое видео без потерь (FFV1): основа для вырезки и текста.

    Маска пишется во временный файл и встаёт на место только целой. Раньше упавший или
    прерванный прогон оставлял короткую маску под настоящим именем, следующий запуск с
    --cutout брал её как готовую («маска уже есть»), вырезка выходила короче дубля — и в
    поздних окнах «текст за спиной» поверх живого человека стоял застывший.
    """
    info = probe(video)
    width, height = info["width"], info["height"]
    model = BACKENDS[backend](width, height)
    frame_bytes = width * height * 4
    expected = round(info["duration"] * info["fps"])
    part = out.with_name(f".{out.stem}.part{out.suffix}")
    # stderr ffmpeg — в файлы, а не в канал, который никто не читает: на битом исходнике
    # ffmpeg упирался бы в полный канал и вставал, а с ним и вся очередь
    reader_err, writer_err = tempfile.TemporaryFile(), tempfile.TemporaryFile()

    reader = subprocess.Popen(
        [ffmpeg_bin(), "-v", "error", "-i", str(video), "-an",
         "-pix_fmt", "rgba", "-f", "rawvideo", "-"],
        stdout=subprocess.PIPE, stderr=reader_err)
    writer = subprocess.Popen(
        [ffmpeg_bin(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray",
         "-s", f"{width}x{height}", "-r", f"{info['fps']:g}", "-i", "-",
         "-c:v", "ffv1", "-pix_fmt", "gray", str(part)],
        stdin=subprocess.PIPE, stderr=writer_err)

    def tail(err) -> str:
        err.seek(0)
        return err.read().decode(errors="replace")[-500:]

    started, count = time.time(), 0
    try:
        try:
            while True:
                rgba = reader.stdout.read(frame_bytes)
                if len(rgba) < frame_bytes:
                    break
                writer.stdin.write(model(rgba).tobytes())
                count += 1
                if count % 300 == 0:
                    print(f"     {count} кадров, {count / (time.time() - started):.1f} к/с", flush=True)
        finally:
            reader.stdout.close()
            reader.wait()
            writer.stdin.close()
            writer.wait()
        if writer.returncode != 0:
            raise RuntimeError(f"ffmpeg не записал маску:\n{tail(writer_err)}")
        if count == 0:
            raise RuntimeError(f"Из {video.name} не прочитано ни одного кадра")
        if count < expected * 0.98 - 2:
            raise RuntimeError(f"Маска короче дубля: {count} кадров из {expected} — чтение "
                               f"{video.name} оборвалось:\n{tail(reader_err)}")
        part.replace(out)
    finally:
        part.unlink(missing_ok=True)
        reader_err.close()
        writer_err.close()
    spent = time.time() - started
    return {"frames": count, "seconds": spent, "fps": count / spent}


def make_cutout(video: Path, matte: Path, out: Path) -> Path:
    """Человек без фона: видео + маска → VP9 с прозрачностью, его понимает браузер.

    Это слой поверх текста «за спиной» и поверх подменённого фона. Потоки кодека
    ограничены: кодирование долгое, и ноутбук в это время должен оставаться рабочим.
    """
    threads = max(1, (os.cpu_count() or 4) - 4)
    part = out.with_name(f".{out.stem}.part{out.suffix}")     # на место — только целое
    try:
        result = subprocess.run([
            ffmpeg_bin(), "-v", "error", "-y", "-i", str(video), "-i", str(matte),
            "-filter_complex", "[1:v]format=gray[a];[0:v][a]alphamerge,format=yuva420p[v]",
            "-map", "[v]", "-an",
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24",
            "-deadline", "good", "-cpu-used", "5", "-row-mt", "1", "-threads", str(threads),
            "-auto-alt-ref", "0", str(part),
        ], capture_output=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"Не собралось прозрачное видео:\n{result.stderr[-600:]}")
        part.replace(out)
    finally:
        part.unlink(missing_ok=True)
    return out


def main():
    ap = argparse.ArgumentParser(description="Маска человека по кадрам")
    ap.add_argument("video")
    ap.add_argument("--backend", choices=sorted(BACKENDS), default="mediapipe")
    ap.add_argument("--out", help="куда положить маску (по умолчанию рядом с видео)")
    ap.add_argument("--cutout", action="store_true",
                    help="ещё и собрать человека без фона (.cutout.webm) из готовой маски")
    args = ap.parse_args()

    video = Path(args.video).resolve()
    if not video.exists():
        sys.exit(f"Нет файла: {video}")
    out = Path(args.out).resolve() if args.out else video.with_name(
        f"{video.stem}.matte_{args.backend}.mkv")
    if out.exists() and args.cutout:
        print(f"  → маска уже есть: {out.name}")
    else:
        print(f"  → маска: {args.backend}", flush=True)
        stats = run_matte(video, args.backend, out)
        print(f"  → {stats['frames']} кадров за {stats['seconds']:.0f} с "
              f"({stats['fps']:.1f} к/с) → {out.name}")
    if args.cutout:
        started = time.time()
        cutout = make_cutout(video, out, video.with_name(f"{video.stem}.cutout.webm"))
        print(f"  → без фона за {time.time() - started:.0f} с → {cutout.name} "
              f"({cutout.stat().st_size / 1048576:.0f} МБ)")


if __name__ == "__main__":
    main()
