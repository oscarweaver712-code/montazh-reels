#!/usr/bin/env python3
"""Вырезка человека из дубля: маска по кадрам и прозрачное видео поверх фона.

Маска нужна для двух вещей: крупное слово ЗА спиной (текст между фоном и человеком)
и замена фона. Способов несколько, и какой лучше на нашей съёмке — решает глаз:

  vision — Apple Vision, встроен в macOS, считает на нейроядре, держит маску
           стабильной между кадрами. Ничего качать не нужно.
  rvm    — Robust Video Matting (GPL-3.0, для внутренней работы годится): сеть для
           людей на видео, помнит прошлые кадры, поэтому края не мерцают.

Кадры идут по одному через канал ffmpeg → модель → ffmpeg: память не зависит от
длины ролика. Потоки торча ограничены, чтобы ноутбук оставался живым.

  .venv/bin/python scripts/matte.py work/IMG_3279/aroll.mp4 --backend rvm
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

from common import ROOT, ffmpeg_bin, probe

RVM_MODEL = ROOT / "models" / "rvm_mobilenetv3_fp32.torchscript"


class VisionMatte:
    """Apple Vision: сегментация человека с временным сглаживанием между кадрами."""

    def __init__(self, width: int, height: int):
        import Quartz
        import Vision
        self.Quartz, self.Vision = Quartz, Vision
        self.width, self.height = width, height
        self.colorspace = Quartz.CGColorSpaceCreateDeviceRGB()
        self.handler = Vision.VNSequenceRequestHandler.alloc().init()
        # запрос «с состоянием»: голый init у него запрещён, только с обработчиком
        self.request = Vision.VNGeneratePersonSegmentationRequest.alloc().initWithCompletionHandler_(None)
        self.request.setQualityLevel_(Vision.VNGeneratePersonSegmentationRequestQualityLevelAccurate)
        self.request.setOutputPixelFormat_(0x4C303038)            # 'L008': 8 бит, один канал

    def __call__(self, rgba: bytes) -> np.ndarray:
        import objc
        Q = self.Quartz
        with objc.autorelease_pool():
            # только через CFData: иначе каждый кадр остаётся в памяти навсегда
            provider = Q.CGDataProviderCreateWithCFData(Q.CFDataCreate(None, rgba, len(rgba)))
            image = Q.CGImageCreate(self.width, self.height, 8, 32, self.width * 4,
                                    self.colorspace, Q.kCGImageAlphaNoneSkipLast, provider,
                                    None, False, Q.kCGRenderingIntentDefault)
            ok, error = self.handler.performRequests_onCGImage_error_([self.request], image, None)
            if not ok or not self.request.results():
                raise RuntimeError(f"Apple Vision не отдал маску: {error}")
            buffer = self.request.results()[0].pixelBuffer()
            Q.CVPixelBufferLockBaseAddress(buffer, 1)
            try:
                w, h = Q.CVPixelBufferGetWidth(buffer), Q.CVPixelBufferGetHeight(buffer)
                stride = Q.CVPixelBufferGetBytesPerRow(buffer)
                raw = Q.CVPixelBufferGetBaseAddress(buffer).as_buffer(stride * h)
                mask = np.frombuffer(raw, dtype=np.uint8).reshape(h, stride)[:, :w].copy()
            finally:
                Q.CVPixelBufferUnlockBaseAddress(buffer, 1)
        return resize(mask, self.width, self.height)


class RvmMatte:
    """Robust Video Matting: рекуррентная сеть, память о прошлых кадрах держит края."""

    def __init__(self, width: int, height: int, downsample: float = 0.25):
        import torch
        if not RVM_MODEL.exists():
            raise RuntimeError(f"Нет модели {RVM_MODEL.relative_to(ROOT)} — скачай её "
                               "с github.com/PeterL1n/RobustVideoMatting/releases")
        torch.set_num_threads(max(1, (os.cpu_count() or 4) - 2))   # пара ядер машине
        self.torch = torch
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.model = torch.jit.load(str(RVM_MODEL), map_location=self.device).eval()
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


def resize(mask: np.ndarray, width: int, height: int) -> np.ndarray:
    """Маска Vision меньше кадра — растягиваем билинейно до размера видео."""
    if mask.shape == (height, width):
        return mask
    import torch
    import torch.nn.functional as F
    t = torch.from_numpy(mask).float()[None, None]
    t = F.interpolate(t, size=(height, width), mode="bilinear", align_corners=False)
    return t[0, 0].round().clamp(0, 255).to(torch.uint8).numpy()


BACKENDS = {"vision": VisionMatte, "rvm": RvmMatte}


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
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Не собралось прозрачное видео:\n{result.stderr[-600:]}")
        part.replace(out)
    finally:
        part.unlink(missing_ok=True)
    return out


def main():
    ap = argparse.ArgumentParser(description="Маска человека по кадрам")
    ap.add_argument("video")
    ap.add_argument("--backend", choices=sorted(BACKENDS), default="vision")
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
