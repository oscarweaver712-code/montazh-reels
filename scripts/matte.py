#!/usr/bin/env python3
"""Вырезка человека из дубля: маска по кадрам и прозрачное видео поверх фона.

Маска нужна для двух вещей: крупное слово ЗА спиной (текст между фоном и человеком)
и замена фона. Движки — открытые и одинаково работают на Mac и Windows:

  birefnet  — BiRefNet lite (MIT), по умолчанию на видеочипе (MPS на Mac, CUDA): человек вместе
              с банкой и микрофоном в руке одной моделью. Замер 14.10 — в BiRefNetMatte.
  mediapipe — MediaPipe Selfie Multiclass (Apache-2.0) вместе с пустой комнатой из самого
              дубля (ниже) — по умолчанию там, где видеочипа нет: BiRefNet на процессоре — 13 с на кадр.
  rvm       — Robust Video Matting (GPL-3.0), запасной: помнит прошлые кадры, но выкидывает
              предметы из рук. Нужен torch.

Замер 11.10.2026 на IMG_3279/3305/3317 против масок Apple Vision (до этого дня был он):
MediaPipe совпал на 94–96% (RVM — на 88–92%), а на спорных кадрах выглядит не хуже.

Пустая комната (12.10.2026, жалоба Валеры на IMG_1803: «вырезка фона хуево работает»; «рука и
банка — не лишние, они тоже должны быть»). Модель смотрит на кадр в 256×256: край у неё мягкий,
с серой дымкой старого фона, а банку в руке она считает скорее фоном (0,59 против 0,30 у класса
«прочее») — верх банки таял, сквозь него светила свеча с нового фона, внизу в человека попадали
красные полосы старой комнаты. Камера в дублях стоит, поэтому пустая комната собирается из самого
дубля: медиана каждой точки по 24 кадрам, где модель уверена, что там фон. Там, где комнату видно,
край режется по отличию кадра от неё — рука, банка, микрофон, пряди: всё, чего в пустой комнате
нет и что одним куском с человеком; модель только говорит, где человек. Где комнату не видно
никогда (за спиной, под руками), решает модель, а предмет, который держится за человека, она отдаёт
целиком: широкое пятно неуверенности, касающееся человека, — это вещь в руке, а не дымка по контуру.
Края на полном кадре ведёт цветной управляемый фильтр: красная банка на сером занавесе одной с ним
яркости, по одной яркости край расплывался. Камера двигалась — комнаты нет, маска по одной модели,
и это пишется в вывод.

Вещь в руке (12–13.10.2026, Валера: «микрофон туда-сюда, то вырезан, то не вырезан» — он прикреплён
к банке). Модель смотрит на кадр в 256×256: банка у края и микрофон на ней для неё — пятно в пару
десятков точек, и она порой уверенно считает их фоном. Отсюда две беды: в кадрах, где банка стояла
на привычном месте, она «парковалась» в пустую комнату (на месте вырезалась как фон, уходила —
оставляла дыру), а в остальных пропадала по самой модели. Поэтому комната за кистью собирается
только из кадров, где руки в другом месте (кисти — класс «кожа тела» без шеи), а вокруг каждой
кисти модель смотрит второй раз, крупно.

Кадры идут по одному через канал ffmpeg → модель → ffmpeg: память не зависит от
длины ролика (выборка для комнаты — всегда PLATE_SAMPLES кадров). Потоки ограничены, чтобы
ноутбук оставался живым.

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
from common import require_queue


PLATE_SAMPLES = 48      # кадров на пустую комнату — сколько бы ни шёл дубль: память постоянная
SURE_BG = 0.85          # «точно фон» по модели; её потолок для класса «фон» — 0.92
PLATE_MIN_SEEN = 4      # точка комнаты известна, если чистой её видно хотя бы в 4 кадрах выборки
PLATE_MIN_AREA = 0.10   # комнаты видно меньше 10% кадра — собирать нечего
PLATE_MAX_MOVED = 0.08  # столько «фона» не сходится с собранной комнатой — камера двигалась
NOISE_FLOOR = 4 / 255   # отличие от комнаты меряется в шумах точки, но не мельче этого
HAND_REACH = 0.25       # доля ширины кадра: кисть с банкой и микрофоном — ближе комнату не собираем
HAND_MIN_AREA = 0.0015  # пятно кожи меньше этой доли кадра — шум, а не кисть
ZOOM_SIDE = 0.55        # квадрат второго взгляда вокруг кисти — доля ширины кадра


class Plate:
    """Пустая комната из самого дубля (половинный кадр): цвет, шум точки и где она известна."""

    def __init__(self, image: np.ndarray, sigma: np.ndarray, weight: np.ndarray):
        self.image, self.sigma, self.weight = image, sigma, weight
        self.scale = (1.0 / np.maximum(sigma, NOISE_FLOOR)).astype(np.float32)   # отличие → шумы точки


def smoothstep(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    x = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def disk(size: int) -> np.ndarray:
    import cv2
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def square(size: int) -> np.ndarray:
    """Квадратное ядро: OpenCV считает его по строкам и столбцам — большие ядра впятеро быстрее круга."""
    return np.ones((size, size), np.uint8)


def touching(mask: np.ndarray, seed: np.ndarray) -> np.ndarray:
    """Куски mask, которые касаются seed (связность по восьми соседям)."""
    import cv2
    mask = mask.astype(np.uint8)
    count, labels = cv2.connectedComponents(mask, connectivity=8)
    if count <= 1:
        return np.zeros(mask.shape, bool)
    hit = np.unique(labels[(seed > 0) & (mask > 0)])
    hit = hit[hit > 0]
    return np.isin(labels, hit) if hit.size else np.zeros(mask.shape, bool)


def hands_mask(body: np.ndarray, face: np.ndarray) -> np.ndarray:
    """Кисти: класс «кожа тела» без шеи (кусок кожи, касающийся лица) и без мелких пятен."""
    import cv2
    skin = (body >= 0.5).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(skin, connectivity=8)
    if count <= 1:
        return np.zeros(body.shape, bool)
    by_face = cv2.dilate((face >= 0.5).astype(np.uint8), square(15)) > 0
    neck = np.unique(labels[by_face & (skin > 0)])
    small = np.flatnonzero(stats[:, cv2.CC_STAT_AREA] < HAND_MIN_AREA * body.size)
    drop = np.union1d(np.union1d(neck, small), [0])
    return ~np.isin(labels, drop)


def room_mask(background: np.ndarray, hands: np.ndarray) -> np.ndarray:
    """Где в этом кадре выборки точно комната: модель уверена в фоне, и кисть далеко.

    Вещь в руке модель порой уверенно считает фоном; стоит она на привычном месте — и
    «паркуется» в пустую комнату. Вещь не дальше HAND_REACH от кисти, так что за ней комната
    собирается из кадров, где руки в другом месте. Подальше и от края человека (сужение на 9 точек).
    """
    import cv2
    sure = background >= SURE_BG
    if hands.any():
        reach = HAND_REACH * background.shape[1]
        sure &= cv2.distanceTransform((~hands).astype(np.uint8), cv2.DIST_L2, 5) > reach
    return cv2.erode(sure.astype(np.uint8), disk(9)).astype(bool)


def hand_boxes(hands: np.ndarray) -> list:
    """Квадраты второго взгляда [(x0, y0, сторона)]: вокруг каждой кисти, с запасом вверх (банка)."""
    import cv2
    h, w = hands.shape
    side = min(int(ZOOM_SIDE * w), h, w)
    count, _, stats, _ = cv2.connectedComponentsWithStats(hands.astype(np.uint8), connectivity=8)
    boxes = []
    for x, y, bw, bh, area in stats[1:]:
        if area >= HAND_MIN_AREA * h * w:
            boxes.append((int(np.clip(x + bw / 2 - side / 2, 0, w - side)),
                          int(np.clip(y + bh / 2 - side * 0.6, 0, h - side)), side))
    return boxes


def zoom_feather(x0: int, y0: int, side: int, width: int, height: int) -> np.ndarray:
    """Вес второго взгляда в квадрате: к обрезу сходит на нет — у обреза модель видит полкартинки.

    У края кадра обреза нет (его же видит и модель на весь кадр): там вес полный, иначе банка
    у края получала прямоугольный срез.
    """
    ramp = np.minimum(np.arange(side, dtype=np.float32) / (0.12 * side), 1.0)
    ramp = ramp * ramp * (3.0 - 2.0 * ramp)
    one = np.ones(side, np.float32)
    rows = np.minimum(one if y0 == 0 else ramp, one if y0 + side >= height else ramp[::-1])
    cols = np.minimum(one if x0 == 0 else ramp, one if x0 + side >= width else ramp[::-1])
    return np.minimum(rows[:, None], cols[None, :])


def _median_of_seen(values: np.ndarray, seen: np.ndarray) -> np.ndarray:
    """Медиана по оси 0 среди известных значений (неизвестные — NaN, сортировка уводит их в конец)."""
    ordered = np.sort(values, axis=0)
    shape = (1,) + values.shape[1:]
    lo = np.broadcast_to(np.maximum((seen - 1) // 2, 0)[None, ..., None], shape)
    hi = np.broadcast_to(np.maximum(seen // 2, 0)[None, ..., None], shape)
    return 0.5 * (np.take_along_axis(ordered, lo, 0) + np.take_along_axis(ordered, hi, 0))[0]


def build_plate(frames: np.ndarray, sure: np.ndarray) -> tuple:
    """Пустая комната: медиана каждой точки по кадрам, где модель уверена, что там фон.

    frames — K×h×w×3 (uint8, RGB), sure — K×h×w (bool). Возвращает (Plate или None, пояснение):
    None, если комнаты почти не видно или камера двигалась — тогда фон в выборке не сходится
    сам с собой, и резать по нему край нельзя.
    """
    import cv2
    count, height, width = sure.shape
    seen = sure.sum(0)
    known = seen >= PLATE_MIN_SEEN
    if known.mean() < PLATE_MIN_AREA:
        return None, f"пустой комнаты почти не видно ({known.mean() * 100:.0f}% кадра)"
    image = np.zeros((height, width, 3), np.float32)
    sigma = np.ones((height, width, 3), np.float32)
    for y in range(0, height, 64):                   # полосами: память не растёт с размером кадра
        part = frames[:, y:y + 64].astype(np.float32) / 255.0
        part[~sure[:, y:y + 64]] = np.nan
        rows = seen[y:y + 64]
        med = _median_of_seen(part, rows)
        image[y:y + 64] = np.nan_to_num(med)
        sigma[y:y + 64] = np.nan_to_num(_median_of_seen(np.abs(part - med[None]), rows) * 1.4826, nan=1.0)
    # камера стояла? каждый кадр выборки — с собранной комнатой там, где он сам «точно фон». Порог — от шума
    # ролика на ровных местах комнаты, а не от шума каждой точки: у сдвинутой камеры он раздувается на узоре
    # и спрятал бы сам сдвиг. Замер 12.10 на пяти дублях: камера стоит — расходится не больше 1,5% точек;
    # толчок штатива на 6 точек — 11–54%. Ровная стена сдвига не покажет, но по ровной стене и резать не страшно
    gray = image.mean(axis=2)
    slope = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)) + np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))
    flat = known & (slope <= np.percentile(slope[known], 30))
    noise = float(np.median(sigma.max(axis=2)[flat]))
    limit = max(6 / 255, 4.0 * noise)
    moved = []
    for i in range(count):
        mask = sure[i] & known
        if mask.sum() >= 500:
            shot = frames[i].astype(np.float32) / 255.0
            gain = np.median(shot[mask], axis=0) / np.maximum(np.median(image[mask], axis=0), 1e-3)
            off = (np.abs(shot - image * gain) > limit).any(axis=2)
            moved.append(float(off[mask].mean()))
    worst = float(np.percentile(moved, 80)) if moved else 1.0
    if worst > PLATE_MAX_MOVED:
        return None, f"камера двигалась: {worst * 100:.0f}% фона не сходится с собранной комнатой"
    weight = cv2.GaussianBlur(cv2.erode(known.astype(np.float32), disk(5)), (0, 0), 3)
    return Plate(image, sigma, weight), f"пустая комната собрана, её видно в {known.mean() * 100:.0f}% кадра"


def model_alpha(person: np.ndarray) -> np.ndarray:
    """Альфа по одной модели: дымка по контуру сжимается, вещь в руке остаётся целиком."""
    import cv2
    alpha = smoothstep(person, 0.35, 0.65)           # уверенность 0.35–0.65 — дымка вокруг контура
    sure = (person >= 0.6).astype(np.uint8)
    unsure = ((person >= 0.25) & (person < 0.6)).astype(np.uint8)
    # дымка по контуру — тонкая полоса, вещь в руке (банка: 0.41) — широкое пятно, касающееся человека
    wide = cv2.morphologyEx(unsure, cv2.MORPH_OPEN, square(11))
    held = touching(wide, cv2.dilate(sure, square(15)))
    if held.any():
        alpha = np.maximum(alpha, cv2.GaussianBlur(held.astype(np.float32), (0, 0), 1.5))
    return alpha


def plate_trust(person: np.ndarray, img: np.ndarray, plate: Plate) -> tuple:
    """(насколько кадр сходится с пустой комнатой 0..1, множитель экспозиции по каналам)."""
    sure = (person[::6, ::6] < 0.1) & (plate.weight[::6, ::6] > 0.5)
    if sure.sum() < 300:
        return 1.0, np.ones(3, np.float32)
    seen, room = img[::6, ::6][sure], plate.image[::6, ::6][sure]
    gain = (np.median(seen, axis=0) / np.maximum(np.median(room, axis=0), 1e-3)).astype(np.float32)
    if np.any(gain < 0.6) or np.any(gain > 1.6):     # свет в комнате сменился целиком — не она
        return 0.0, np.ones(3, np.float32)
    floor = np.maximum(4.0 * plate.sigma[::6, ::6][sure], 10 / 255)
    off = float((np.abs(seen - room * gain) > floor).any(axis=1).mean())
    return float(np.clip((0.30 - off) / 0.15, 0.0, 1.0)), gain


def hybrid_alpha(person: np.ndarray, img: np.ndarray, plate: Plate = None, trust: float = 1.0,
                 gain=1.0) -> np.ndarray:
    """Альфа половинного кадра: где пустая комната известна — по отличию от неё, где нет — по модели.

    person — уверенность модели «это человек», img — кадр (RGB 0..1) того же размера.
    """
    import cv2
    alpha_model = model_alpha(person)
    if plate is None or trust <= 0.01:
        return alpha_model
    core = (person >= 0.6).astype(np.uint8)
    differs = (np.abs(img - plate.image * gain) * plate.scale).max(axis=2)
    alpha_diff = smoothstep(differs, 3.0, 7.0)
    # отличие от комнаты засчитывается только у человека и одним куском с ним: тень и блик вдали — не он.
    # «У человека» — от всего, что модель хоть сколько-то считает им: банку (0.41) она видит, но не уверена
    near = cv2.dilate(((person >= 0.25) | (core > 0)).astype(np.uint8), square(31))
    piece = touching((alpha_diff > 0.5) & (near > 0), core)
    piece = cv2.dilate(piece.astype(np.uint8), disk(3)).astype(np.float32)
    # глубокая середина — от модели: тёмный пиджак на тёмной стене отличием не возьмёшь. Глубокая — дальше
    # 12 точек от края: полосу старой комнаты у края, которую модель взяла в человека, срезает комната
    deep = cv2.GaussianBlur(cv2.erode(core, square(25)).astype(np.float32), (0, 0), 1.5)
    alpha_plate = np.maximum(alpha_diff * piece, deep)
    weight = plate.weight * trust
    return weight * alpha_plate + (1.0 - weight) * alpha_model


def calm(alpha: np.ndarray, img: np.ndarray, last) -> np.ndarray:
    """Край не «кипит»: где картинка с прошлого кадра не изменилась, альфа усредняется с прошлой.

    Модель на каждом кадре решает заново, и край на неподвижных волосах дрожал. Где картинка
    изменилась (рука движется), берётся новая альфа как есть — шлейфа за движением нет.
    Замер 12.10 на IMG_1803: дрожание края там, где картинка стоит, −20…27%, мигания −30…42%.
    """
    if last is None:
        return alpha
    still = np.abs(img - last[0]).max(axis=2) < 3 / 255
    return np.where(still, 0.5 * (alpha + last[1]), alpha)


def upscale_alpha(alpha: np.ndarray, small: np.ndarray, frame: np.ndarray, radius: int = 2,
                  eps: float = 1e-4) -> np.ndarray:
    """Альфа с половинного кадра на полный: края — по цветному кадру.

    Быстрый управляемый фильтр (He, Sun 2015): коэффициенты считаются на половинном кадре,
    край берётся из полного. Цветной, а не по яркости: красная банка на сером занавесе той же
    яркости, по одной яркости её край расплывался.
    """
    import cv2
    box = lambda x: cv2.boxFilter(x, -1, (2 * radius + 1, 2 * radius + 1), borderType=cv2.BORDER_REFLECT)
    r, g, b = small[..., 0], small[..., 1], small[..., 2]
    mr, mg, mb, mp_ = box(r), box(g), box(b), box(alpha)
    cr, cg, cb = box(r * alpha) - mr * mp_, box(g * alpha) - mg * mp_, box(b * alpha) - mb * mp_
    rr = box(r * r) - mr * mr + eps
    rg = box(r * g) - mr * mg
    rb = box(r * b) - mr * mb
    gg = box(g * g) - mg * mg + eps
    gb = box(g * b) - mg * mb
    bb = box(b * b) - mb * mb + eps
    # обратная к ковариации цвета 3×3 в каждой точке — через алгебраические дополнения
    i_rr, i_rg, i_rb = gg * bb - gb * gb, gb * rb - rg * bb, rg * gb - gg * rb
    i_gg, i_gb, i_bb = rr * bb - rb * rb, rb * rg - rr * gb, rr * gg - rg * rg
    det = rr * i_rr + rg * i_rg + rb * i_rb
    ar = (i_rr * cr + i_rg * cg + i_rb * cb) / det
    ag = (i_rg * cr + i_gg * cg + i_gb * cb) / det
    ab = (i_rb * cr + i_gb * cg + i_bb * cb) / det
    bias = mp_ - ar * mr - ag * mg - ab * mb
    height, width = frame.shape[:2]
    grow = lambda c: cv2.resize(c, (width, height), interpolation=cv2.INTER_LINEAR)
    out = grow(box(bias))
    for coef, channel in zip((ar, ag, ab), cv2.split(frame)[:3]):       # кадр RGB или RGBA
        out = cv2.add(out, cv2.multiply(grow(box(coef) * (1.0 / 255.0)), channel, dtype=cv2.CV_32F))
    return np.clip(out, 0.0, 1.0, out=out)


class MediaPipeMatte:
    """MediaPipe Selfie Multiclass + пустая комната из дубля; края — по полному кадру."""

    def __init__(self, width: int, height: int):
        import cv2
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        cv2.setNumThreads(host.encoder_threads())
        self.cv2, self.mp = cv2, mp
        self.width, self.height = width, height
        # модель — байтами, а не путём: MediaPipe на Windows не открывает путь с кириллицей
        model = models.ensure("selfie_multiclass", download=False).read_bytes()

        def segmenter(mode):
            return vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
                base_options=BaseOptions(model_asset_buffer=model), running_mode=mode,
                output_confidence_masks=True, output_category_mask=False))

        self.segmenter = segmenter(vision.RunningMode.VIDEO)
        self.zoom = segmenter(vision.RunningMode.IMAGE)         # второй взгляд у кистей, кадр за кадром
        self.ms = 0
        # модель видит 256×256, так что ей и всей логике маски хватает половинного кадра;
        # полный нужен только краю (upscale_alpha)
        self.half = (max(2, width // 2), max(2, height // 2))
        self.plate, self.trust, self.gain = None, 1.0, np.ones(3, np.float32)
        self.last = None                                # прошлый кадр и его альфа — для покоя края

    def shrink(self, frame: np.ndarray) -> np.ndarray:
        """Половинный кадр (RGB): при чётном размере — пирамидой, втрое быстрее INTER_AREA."""
        if not (self.width % 2 or self.height % 2):
            return self.cv2.pyrDown(frame)[:, :, :3]
        return self.cv2.resize(frame, self.half, interpolation=self.cv2.INTER_AREA)[:, :, :3]

    def classes(self, small: np.ndarray) -> list:
        """Уверенность каждого класса: фон, волосы, кожа тела, кожа лица, одежда, прочее."""
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(small))
        result = self.segmenter.segment_for_video(image, self.ms)
        self.ms += 33                                   # метки времени обязаны расти
        return [np.squeeze(np.asarray(m.numpy_view(), np.float32)) for m in result.confidence_masks]

    def person(self, small: np.ndarray) -> np.ndarray:
        """Уверенность «это человек» (всё, кроме класса «фон») в точках половинного кадра.

        Вокруг каждой кисти модель смотрит второй раз, крупно (квадрат с запасом на вещь в руке),
        и берётся бо́льшая уверенность. Замер 12.10 на IMG_1803: верх банки и микрофон на месте
        в кадрах, где одна модель на весь кадр их теряла; +65 мс на кадр с кистями.
        """
        conf = self.classes(small)
        person = 1.0 - conf[0]
        height, width = person.shape
        for x0, y0, side in hand_boxes(hands_mask(conf[2], conf[3])):
            crop = self.mp.Image(image_format=self.mp.ImageFormat.SRGB,
                                 data=np.ascontiguousarray(small[y0:y0 + side, x0:x0 + side]))
            zoom = 1.0 - np.squeeze(np.asarray(self.zoom.segment(crop).confidence_masks[0].numpy_view(), np.float32))
            zoom = self.cv2.resize(zoom, (side, side), interpolation=self.cv2.INTER_LINEAR)
            region = person[y0:y0 + side, x0:x0 + side]
            region += zoom_feather(x0, y0, side, width, height) * np.maximum(zoom - region, 0.0)
        return person

    def room(self, small: np.ndarray, conf: list) -> np.ndarray:
        """Точки кадра выборки, где модель уверена, что это фон, — из них собирается пустая комната."""
        return room_mask(conf[0], hands_mask(conf[2], conf[3]))

    def prepare(self, video: Path, info: dict) -> str:
        """Пустая комната по выборке из PLATE_SAMPLES кадров дубля; вернёт, что вышло, — для вывода."""
        width, height = self.half
        rate = PLATE_SAMPLES / max(info["duration"], 0.1)
        size = width * height * 3
        frames, sure = [], []
        with tempfile.TemporaryFile() as err:
            reader = subprocess.Popen(
                [ffmpeg_bin(), "-v", "error", "-i", str(video), "-an",
                 "-vf", f"fps={rate:.6f},scale={width}:{height}:flags=area",
                 "-frames:v", str(PLATE_SAMPLES), "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                stdout=subprocess.PIPE, stderr=err)
            try:
                while len(frames) < PLATE_SAMPLES:
                    raw = reader.stdout.read(size)
                    if len(raw) < size:
                        break
                    small = np.frombuffer(raw, np.uint8).reshape(height, width, 3)
                    frames.append(small)
                    sure.append(self.room(small, self.classes(small)))
            finally:
                reader.stdout.close()
                reader.wait()
        if len(frames) < 8:
            return "пустая комната не собралась: из дубля прочитано мало кадров — маска по модели"
        self.plate, note = build_plate(np.stack(frames), np.stack(sure))
        return note if self.plate is not None else f"{note} — маска по одной модели"

    def __call__(self, rgba: bytes) -> np.ndarray:
        cv2 = self.cv2
        frame = np.frombuffer(rgba, np.uint8).reshape(self.height, self.width, 4)
        small = self.shrink(frame)
        person = self.person(small)
        img = small.astype(np.float32) / 255.0
        if self.plate is not None:
            # кадр, который с комнатой не сходится (свет, толчок камеры), режется по модели — плавно
            trust, gain = plate_trust(person, img, self.plate)
            self.trust = 0.8 * self.trust + 0.2 * trust
            if trust > 0:
                self.gain = gain
        alpha = hybrid_alpha(person, img, self.plate, self.trust, self.gain)
        alpha = drop_islands(np.clip(alpha, 0.0, 1.0), cv2)
        alpha = calm(alpha, img, self.last)
        self.last = (img, alpha)
        alpha = upscale_alpha(alpha, img, frame)
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
        with open(model, "rb") as f:                   # открывает питон: путь с кириллицей на Windows
            self.model = torch.jit.load(f, map_location=self.device).eval()
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


def accelerator():
    """Видеочип для torch: MPS на Mac с Apple Silicon, CUDA на Windows с NVIDIA; нет — None."""
    import torch
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return None


class BiRefNet:
    """BiRefNet lite (MIT) на видеочипе: уверенность «человек и его вещи» для кадра RGB."""

    SIDE = 512                  # вход модели: квадрат, как при обучении; замер — в BiRefNetMatte

    def __init__(self):
        import torch
        from birefnet import BiRefNet as Net

        self.device = accelerator()
        if self.device is None:
            raise RuntimeError("BiRefNet без видеочипа считает ~13 с на кадр (минута ролика — 6 часов). "
                               "Здесь нет ни MPS, ни CUDA: возьми --backend mediapipe")
        torch.set_num_threads(host.encoder_threads())            # пара ядер машине
        self.torch = torch
        net = Net(bb_pretrained=False)
        with open(models.ensure("birefnet_lite", download=False), "rb") as f:   # путь с кириллицей — питону
            state = torch.load(f, map_location="cpu", weights_only=True)
        net.load_state_dict(state, strict=True)                  # не те веса — громкая ошибка torch
        self.net = net.to(self.device).eval().half()
        self.mean = torch.tensor([0.485, 0.456, 0.406], device=self.device).view(1, 3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225], device=self.device).view(1, 3, 1, 1)

    def __call__(self, small: np.ndarray, cv2) -> np.ndarray:
        torch = self.torch
        height, width = small.shape[:2]
        square = cv2.resize(small, (self.SIDE, self.SIDE), interpolation=cv2.INTER_AREA)
        x = torch.from_numpy(np.ascontiguousarray(square)).to(self.device)
        x = ((x.permute(2, 0, 1)[None].float() / 255.0 - self.mean) / self.std).half()
        with torch.no_grad():
            out = self.net(x)[-1].sigmoid()[0, 0].float().cpu().numpy()
        return cv2.resize(out, (width, height), interpolation=cv2.INTER_LINEAR)


class BiRefNetMatte(MediaPipeMatte):
    """MediaPipe с пустой комнатой, а «где человек» — вместе с BiRefNet: бо́льшая уверенность из двух.

    Замер 14.10.2026 на IMG_1803 (банка с микрофоном, на которую жаловался Валера), 9 кадров против
    масок MediaPipe (с пустой комнатой и вторым взглядом у кистей) и Apple Vision (accurate):
    MediaPipe на 4-й и 44-й секунде срезал ветрозащиту микрофона, Vision держал микрофон, но тянул
    в человека лист растения и зелёную кайму у плеча, BiRefNet держал банку и микрофон целиком без
    хвостов фона. Вход 1024, 768 и 512 на глаз не отличался (край всё равно ведёт upscale_alpha по
    полному кадру); на M-чипе 1024 — 0,46 с на кадр, 768 — 0,25, 512 — 0,11 (fp16, MPS), на
    процессоре — 13 с: без видеочипа её не берём.

    Одна BiRefNet на видео — мало: она смотрит на каждый кадр с нуля и на 4,8–5,0 и 9,3 с IMG_1803
    теряла банку с кистью у края кадра на 2–3 кадра (полупрозрачный призрак — то самое «то вырезан,
    то не вырезан»), а MediaPipe с пустой комнатой их держал. Поэтому модели складываются: у MediaPipe —
    кисть и устойчивость, у BiRefNet — микрофон и форма вещи; край и дальше режет пустая комната.
    И комната собирается только из точек, которые обе модели считают фоном: иначе микрофон, который
    MediaPipe считает фоном, «парковался» бы в пустую комнату и вырезался вместе с ней.
    """

    def __init__(self, width: int, height: int):
        super().__init__(width, height)
        self.birefnet = BiRefNet()

    def room(self, small: np.ndarray, conf: list) -> np.ndarray:
        return super().room(small, conf) & (self.birefnet(small, self.cv2) < 0.15)

    def person(self, small: np.ndarray) -> np.ndarray:
        return np.maximum(super().person(small), self.birefnet(small, self.cv2))


BACKENDS = {"birefnet": BiRefNetMatte, "mediapipe": MediaPipeMatte, "rvm": RvmMatte}


# Скорость маски, кадров в секунду: замер 14.10.2026 на 15 с IMG_1803 (Mac M, рядом шёл Zoom):
# MediaPipe с комнатой — 4,7, BiRefNet вместе с ним — 2,0. Минута ролика — ~15 мин маски BiRefNet.
BIREFNET_FPS = 2.0
LIMIT_SEC = 300.0          # дольше пяти минут счёта — только с согласия (AGENTS.md, инвариант 6)


def needs_consent(backend: str, frames: int) -> float | None:
    """Оценка счёта в секундах, если она дольше пяти минут и нужно согласие; иначе None.

    Сравнивается ОЦЕНКА СЧЁТА, а не длина записи. MediaPipe минуту ролика считает за 4–6 мин
    и шёл без вопроса всегда (до 14.10 — единственный движок), BiRefNet втрое дольше.
    """
    if backend != "birefnet":
        return None
    seconds = frames / BIREFNET_FPS
    return seconds if seconds > LIMIT_SEC else None


def project_consent(video: Path) -> str | None:
    """Имя проекта, чей владелец заранее согласился на долгую маску (long_matte в project.json), иначе None.

    Валера 14.10.2026: «Я готов на долгую маску» — пачка его роликов не встаёт на этом шаге.
    Ролик ищется строго по исходнику (projects.of), без проекта по умолчанию: согласие одного
    проекта не должно молча доставаться чужому ролику или файлу вне проектов.
    """
    import projects
    stem = video.parent.name if video.parent.parent.name == "work" else video.stem
    try:
        project = projects.of(stem)
    except projects.ProjectError:
        return None
    return project.name if project.config["long_matte"] else None


def pick_backend(wanted: str) -> tuple:
    """(движок, пояснение для вывода). auto — BiRefNet на видеочипе, без него — MediaPipe, и это пишется."""
    if wanted != "auto":
        return wanted, ""
    try:
        if accelerator() is not None:
            return "birefnet", ""
        why = "видеочипа нет (ни MPS, ни CUDA)"
    except ImportError:
        why = "нет torch"
    return "mediapipe", (f"BiRefNet не взят: {why} — маска MediaPipe с пустой комнатой; банку и микрофон "
                         f"в руке она теряет чаще (замер 14.10 в docstring BiRefNetMatte)")


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
    note = model.prepare(video, info) if hasattr(model, "prepare") else ""
    if note:
        print(f"     {note}", flush=True)
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


def foreground_plane(plane: np.ndarray, alpha: np.ndarray, size: int) -> np.ndarray:
    """Одна плоскость кадра (Y, U или V) с цветом человека без примеси старого фона.

    В полупрозрачной точке кадр — смесь: I = αF + (1−α)B. Старый фон B рядом с краем берётся
    по соседним точкам фона (вес — (1−α)², окно size), цвет человека F — из уравнения. Где человек
    сплошной — плоскость как есть, байт в байт; где прозрачно — цвет ближайшего человека: кодек 4:2:0
    смешивает цвет соседних точек, и цвет старой комнаты за краем просочился бы в край.
    """
    import cv2
    x = plane.astype(np.float32)
    rest = 1.0 - alpha
    box = lambda m, k: cv2.boxFilter(m, -1, (k, k), borderType=cv2.BORDER_REFLECT)
    # старый фон — среднее чистых точек фона рядом: смешанные точки края тянули бы его к цвету человека.
    # Нет чистых в окне — в окне втрое шире; нет и там — точка остаётся как есть
    pure = (alpha < 0.02).astype(np.float32)
    near_sum, near_n = box(x * pure, size), box(pure, size)
    wide_sum, wide_n = box(x * pure, size * 3), box(pure, size * 3)
    room = np.where(near_n > 0.02, near_sum / np.maximum(near_n, 1e-6),
                    np.where(wide_n > 1e-3, wide_sum / np.maximum(wide_n, 1e-6), x))
    fg = (x - rest * room) / np.maximum(alpha, 0.08)
    near = size // 3 | 1
    reach = box(alpha, near)
    spread = box(fg * alpha, near) / np.maximum(reach, 1e-4)
    fg = np.where(alpha < 0.02, np.where(reach > 1e-3, spread, x), fg)
    fg = np.where(alpha >= 0.97, x, fg)
    return np.clip(fg + 0.5, 0, 255).astype(np.uint8)


def cutout_frame(yuv: bytes, mask: bytes, width: int, height: int) -> bytes:
    """Кадр yuv420p + маска → кадр yuva420p с чистым краем (в цветах самого видео, без RGB)."""
    import cv2
    luma, cw, ch = width * height, width // 2, height // 2
    buf = np.frombuffer(yuv, np.uint8)
    y = buf[:luma].reshape(height, width)
    u = buf[luma:luma + cw * ch].reshape(ch, cw)
    v = buf[luma + cw * ch:luma + 2 * cw * ch].reshape(ch, cw)
    a = np.frombuffer(mask, np.uint8).reshape(height, width)
    alpha = a.astype(np.float32) / 255.0
    alpha_c = cv2.resize(alpha, (cw, ch), interpolation=cv2.INTER_AREA)
    return b"".join((foreground_plane(y, alpha, 41).tobytes(), foreground_plane(u, alpha_c, 21).tobytes(),
                     foreground_plane(v, alpha_c, 21).tobytes(), a.tobytes()))


def make_cutout(video: Path, matte: Path, out: Path) -> Path:
    """Человек без фона: видео + маска → VP9 с прозрачностью, его понимает браузер.

    Это слой поверх текста «за спиной» и поверх подменённого фона. Цвет края чистится от старого
    фона (foreground_plane): раньше кадр брался как есть, и полупрозрачный край нёс серый занавес
    старой комнаты — на новом фоне он светился ореолом. Считается в YUV самого дубля: где человек
    сплошной, слой совпадает с дублем байт в байт, и текст «за спиной» не даёт шва.
    Кадры идут по одному (память постоянная), потоки кодека ограничены: ноутбук остаётся рабочим.
    """
    import cv2
    cv2.setNumThreads(2)
    info = probe(video)
    width, height = info["width"], info["height"]
    if width % 2 or height % 2:
        raise RuntimeError(f"Размер {width}×{height} нечётный — yuv420p так не умеет")
    frame_bytes = width * height * 3 // 2
    expected = round(info["duration"] * info["fps"])
    threads = max(1, (os.cpu_count() or 4) - 5)
    # цвет — как у дубля: кодеку отдаются сырые плоскости, метки цвета ставятся явно
    tags = []
    for flag, key, default in (("-colorspace", "matrix", "bt709"), ("-color_primaries", "primaries", "bt709"),
                               ("-color_trc", "transfer", "bt709"), ("-color_range", "range", "tv")):
        value = info.get(key) or default
        tags += [flag, default if value in ("unknown", "reserved") else value]
    part = out.with_name(f".{out.stem}.part{out.suffix}")     # на место — только целое
    errs = [tempfile.TemporaryFile() for _ in range(3)]

    def tail(err) -> str:
        err.seek(0)
        return err.read().decode(errors="replace")[-600:]

    reader = subprocess.Popen([ffmpeg_bin(), "-v", "error", "-i", str(video), "-an",
                               "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"],
                              stdout=subprocess.PIPE, stderr=errs[0])
    # маска с обычного дубля под дубль для страницы покрупнее (prep.py --hq): растягивается плавно —
    # от неё зависит только край, детали лица и волос идут из самого видео
    fit = [] if (probe(matte)["width"], probe(matte)["height"]) == (width, height) else \
        ["-vf", f"scale={width}:{height}:flags=bicubic"]
    masks = subprocess.Popen([ffmpeg_bin(), "-v", "error", "-i", str(matte), *fit,
                              "-pix_fmt", "gray", "-f", "rawvideo", "-"],
                             stdout=subprocess.PIPE, stderr=errs[1])
    writer = subprocess.Popen([
        ffmpeg_bin(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "yuva420p",
        "-s", f"{width}x{height}", "-r", f"{info['fps']:g}", "-i", "-",
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24",
        "-deadline", "good", "-cpu-used", "5", "-row-mt", "1", "-threads", str(threads),
        "-auto-alt-ref", "0", *tags, str(part)], stdin=subprocess.PIPE, stderr=errs[2])
    count, left = 0, 0
    try:
        try:
            while True:
                yuv = reader.stdout.read(frame_bytes)
                mask = masks.stdout.read(width * height)
                if len(yuv) < frame_bytes or len(mask) < width * height:
                    left = len(yuv) // frame_bytes + len(mask) // (width * height)
                    break
                writer.stdin.write(cutout_frame(yuv, mask, width, height))
                count += 1
        except BrokenPipeError:
            pass                                      # кодек упал — причина ниже, из его вывода
        finally:
            for proc in (reader, masks):
                proc.stdout.close()
                proc.wait()
            try:
                writer.stdin.close()
            except BrokenPipeError:
                pass
            writer.wait()
        if writer.returncode != 0:
            raise RuntimeError(f"Не собралось прозрачное видео:\n{tail(errs[2])}")
        if count < expected * 0.98 - 2 or left:
            raise RuntimeError(f"Вырезка не совпала с дублем по длине: {count} кадров из {expected} — "
                               f"маска {matte.name} от другого или оборванного дубля, пересчитай её "
                               f"(matte.py без --cutout)\n{tail(errs[0])}{tail(errs[1])}")
        part.replace(out)
    finally:
        part.unlink(missing_ok=True)
        for err in errs:
            err.close()
    return out


def main():
    require_queue("маска человека")
    ap = argparse.ArgumentParser(description="Маска человека по кадрам")
    ap.add_argument("video")
    ap.add_argument("--backend", choices=["auto", *sorted(BACKENDS)], default="auto",
                    help="auto — BiRefNet на видеочипе, без него MediaPipe")
    ap.add_argument("--out", help="куда положить маску (по умолчанию рядом с видео)")
    ap.add_argument("--cutout", action="store_true",
                    help="ещё и собрать человека без фона (.cutout.webm) из готовой маски")
    ap.add_argument("--yes", action="store_true",
                    help="согласие на маску дольше пяти минут (BiRefNet на длинном дубле)")
    args = ap.parse_args()

    video = Path(args.video).resolve()
    if not video.exists():
        sys.exit(f"Нет файла: {video}")
    backend, why = pick_backend(args.backend)
    if why:
        print(f"  ⚠ {why}", flush=True)
    out = Path(args.out).resolve() if args.out else video.with_name(
        f"{video.stem}.matte_{backend}.mkv")
    if out.exists() and args.cutout:
        print(f"  → маска уже есть: {out.name}")
    else:
        info = probe(video)
        eta = needs_consent(backend, round(info["duration"] * info["fps"]))
        agreed = project_consent(video) if eta and not args.yes else None
        if agreed:
            print(f"  → долгая маска: согласие проекта {agreed} (long_matte в project.json)", flush=True)
        elif eta and not args.yes:
            sys.exit(f"  ✗ Маска BiRefNet для {info['duration']:.0f} с видео — примерно {eta / 60:.0f} мин счёта "
                     f"(видеочип и ~1,5 ядра, машина остаётся живой).\n"
                     f"    Так и хотел — добавь --yes. Быстрее (~{eta / 60 * BIREFNET_FPS / 4.7:.0f} мин) — "
                     f"--backend mediapipe: банку и микрофон в руке он теряет чаще.")
        print(f"  → маска: {backend}" + (f", оценка ~{eta / 60:.0f} мин" if eta else ""), flush=True)
        try:
            stats = run_matte(video, backend, out)
        except RuntimeError as e:
            sys.exit(f"  ✗ {e}")
        print(f"  → {stats['frames']} кадров за {stats['seconds']:.0f} с "
              f"({stats['fps']:.1f} к/с) → {out.name}")
    if args.cutout:
        started = time.time()
        cutout = make_cutout(video, out, video.with_name(f"{video.stem}.cutout.webm"))
        print(f"  → без фона за {time.time() - started:.0f} с → {cutout.name} "
              f"({cutout.stat().st_size / 1048576:.0f} МБ)")


if __name__ == "__main__":
    main()
