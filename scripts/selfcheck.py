#!/usr/bin/env python3
"""Самопроверка пайплайна: гоняет сборку на синтетическом видео и проверяет инварианты.

Запускать после любой правки render.py, cut.py или common.py:

  .venv/bin/python scripts/selfcheck.py          # ~1 минута, 60 сегментов
  .venv/bin/python scripts/selfcheck.py --long   # ~4 минуты, 200 сегментов

Проверяется то, что уже ломалось на живой машине:
  • память не растёт от числа сегментов (граф на сотню веток однажды увёл ноут в своп);
  • сборка идёт по одному процессу за раз, а не веером;
  • длина ролика совпадает с планом — иначе субтитры уезжают от речи;
  • временные файлы убираются даже когда сборка падает посередине;
  • файл, перетащенный из мессенджера, либо доходит до input/, либо получает отказ;
  • рез встаёт в паузу, а не внутрь слова, даже когда распознавание врёт с таймингами;
  • шумодав не выедает голос, а громкость на выходе попадает в цель;
  • айфоновский полный диапазон приводится к стандартному, а яркость двигает средние
    тона, не поднимая чёрное в серое и не срезая белое;
  • камера следит за лицом, но её окно никогда не выходит за исходник: кадр всегда
    полный, без пустых полос, а лицо не теряется даже у самого края;
  • поиск лиц не копит кадры в памяти (однажды держал по 2 МБ на кадр — 2,4 ГБ на минуту);
  • субтитр или надпись не залипает на экране до конца ролика: уход посреди входа в
    покадровом рендере HyperFrames проигрывал (пять роликов из пятнадцати, на снимках чисто).

Тест намеренно не «быстрый»: он честно кодирует видео. Минута здесь дешевле, чем
зависший ноутбук и переснятый урок.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import quote

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (INPUT_DIR, ROOT, WORK_DIR, detect_silence, ffmpeg_bin, ffprobe_bin,
                    load_preset, measure_noise_floor, snap_segments)
from cut import plan_cut
from look import expected_luma, look_filter
from render import render, voice_chain

# Потолок памяти. Правильная сборка держится в районе 300 МБ; берём запас, но такой,
# чтобы возврат к «одному большому графу» гарантированно упёрся в него.
RAM_CEILING_MB = 1500
# Допуск на рассинхрон. Кадр при 30 fps это 33 мс; полкадра на сотню склеек — норма.
DRIFT_TOLERANCE_SEC = 0.20


class Watcher:
    """Следит за ffmpeg этого прогона: сколько их разом и сколько памяти держат.

    Считаются только процессы-потомки самого теста. Раньше считались все ffmpeg в
    системе — и открытая рядом веб-панель, дёрнувшая кадр для превью, красила проверку
    в красный на ровном месте. Инвариант «один тяжёлый процесс за раз» — про то, что
    запускает пайплайн, а не про всё, что человек делает на машине параллельно.
    """

    def __init__(self):
        self.root = os.getpid()
        self.peak_mb = 0.0
        self.peak_procs = 0
        self.samples = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _sample(self) -> tuple:
        out = subprocess.run(["ps", "-axo", "pid=,ppid=,rss=,comm="],
                             capture_output=True, text=True).stdout

        rows, kids = [], {}
        for line in out.splitlines():
            parts = line.split(None, 3)
            if len(parts) != 4:
                continue
            try:
                pid, ppid, rss = int(parts[0]), int(parts[1]), int(parts[2])
            except ValueError:
                continue
            kids.setdefault(ppid, []).append(pid)
            rows.append((pid, rss, parts[3]))

        mine, stack = set(), [self.root]
        while stack:
            for kid in kids.get(stack.pop(), []):
                if kid not in mine:
                    mine.add(kid)
                    stack.append(kid)

        total = procs = 0
        for pid, rss, comm in rows:
            if pid in mine and "ffmpeg" in comm:
                total += rss
                procs += 1
        return total / 1024, procs

    def _loop(self):
        while not self._stop.is_set():
            megabytes, procs = self._sample()
            self.peak_mb = max(self.peak_mb, megabytes)
            self.peak_procs = max(self.peak_procs, procs)
            self.samples += 1
            time.sleep(0.3)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=2)


class Report:
    def __init__(self):
        self.failed = []

    def check(self, ok: bool, title: str, detail: str = ""):
        print(f"  {'✓' if ok else '✗'} {title}" + (f"  ({detail})" if detail else ""))
        if not ok:
            self.failed.append(title)
        return ok


def probe_value(path: Path, entries: str, stream: str | None = None) -> str:
    cmd = [ffprobe_bin(), "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "csv=p=0", str(path)]
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def make_source(path: Path, seconds: float, fps: int):
    """Синтетический вертикальный клип со звуком — свои видео для теста не нужны."""
    subprocess.run([
        ffmpeg_bin(), "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc2=size=1080x1920:rate={fps}:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:v", "h264_videotoolbox", "-b:v", "8M", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest",
        str(path),
    ], check=True, capture_output=True)


def make_burst_source(path: Path, seconds: float, fps: int,
                      period: float = 3.0, on: float = 1.5):
    """Клип с «речью»: тон включается и выключается, между вспышками — настоящая тишина.

    Ровный синус для проверки реза не годится: в нём нет пауз, а вся суть в том, куда
    встанут границы относительно смолкшей речи.
    """
    # Тон в «речи», тихий шум всю дорогу и вдох внутри каждой паузы. Вдох намеренно
    # тише порога тишины (−38 дБ против −35): тишиной пауза быть не перестаёт, но пик
    # в ней задирается на 15 дБ выше настоящего шума — ровно как на живой записи.
    expr = (f"0.3*sin(2*PI*300*t)*between(mod(t\\,{period})\\,0\\,{on})"
            f"+0.006*(random(0)-0.5)"
            f"+0.012*sin(2*PI*900*t)*between(mod(t\\,{period})\\,{on + 0.4}\\,{on + 0.43})")
    subprocess.run([
        ffmpeg_bin(), "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc2=size=1080x1920:rate={fps}:duration={seconds}",
        "-f", "lavfi", "-i", f"aevalsrc={expr}:d={seconds}:s=48000",
        "-c:v", "h264_videotoolbox", "-b:v", "8M", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest",
        str(path),
    ], check=True, capture_output=True)


def loudness_of(path: Path) -> float | None:
    """Интегральная громкость готового файла в LUFS."""
    out = subprocess.run([
        ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path),
        "-af", "ebur128", "-f", "null", "-",
    ], capture_output=True, text=True).stderr
    found = re.findall(r"I:\s*(-?[\d.]+) LUFS", out)
    return float(found[-1]) if found else None


def check_cut_keeps_speech(report: Report, preset: dict, tmp: Path):
    """Рез не имеет права попасть внутрь слова.

    Тайминги распознавания на концах слов врут: произнесённое «ноль целых восемь десятых»
    whisper пишет как «0 ,8» и обрывает слово на 0.3–0.4 с раньше, чем человек договорил.
    Здесь это воспроизведено честно — концы слов сдвинуты назад, — и проверка требует,
    чтобы границы всё равно встали в настоящую тишину. Поломка тихая: файл соберётся,
    ничего не упадёт, а в ролике останется «де» и обрыв.
    """
    print("\nРез по настоящей тишине")
    fps = preset["video"]["fps"]
    period, on, seconds = 3.0, 1.5, 12.0

    src = tmp / "burst.mp4"
    make_burst_source(src, seconds, fps, period, on)

    silences = detect_silence(src, preset["cut"].get("silence_db", -35),
                              preset["cut"].get("silence_min", 0.10))
    report.check(len(silences) >= 3, "паузы между вспышками найдены", f"{len(silences)} шт.")

    bursts = [(k * period, k * period + on) for k in range(int(seconds // period))]
    words = [{"word": f"слово{k}", "start": s + 0.05, "end": e - 0.4}   # так врёт whisper
             for k, (s, e) in enumerate(bursts)]

    cfg = dict(preset["cut"], remove_fillers=False, remove_stutters=False)
    plan = plan_cut([dict(w) for w in words], cfg, seconds, fps=fps, silences=silences)

    lost = [f"{s:.1f}–{e:.1f}" for s, e in bursts
            if not any(a <= s + 0.1 and b >= e - 0.06 for a, b in plan["segments"])]
    report.check(not lost, "ни одно слово не обрезано на конце",
                 ", ".join(lost) or f"{len(bursts)} вспышек целы")

    inside = []
    for a, b in plan["segments"]:
        for bs, be in bursts:
            inside += [f"{edge:.2f}" for edge in (a, b) if bs + 0.06 < edge < be - 0.06]
    report.check(not inside, "границы кусков стоят в паузе, а не в речи",
                 ", ".join(sorted(set(inside))) or "все в паузах")


def check_voice(report: Report, preset: dict, tmp: Path):
    """Обработка голоса не должна выедать сам голос.

    Порог шумодава раньше стоял константой −24 дБ — это уровень речи, а не шума: голос
    звучал «подводным». Проверяется, что порог берётся из замера и не заходит на голос,
    что цепочку принимает сам ffmpeg и что громкость на выходе попадает в цель.
    """
    print("\nОбработка голоса")
    fps = preset["video"]["fps"]
    audio = dict(preset["audio"])

    # порог обязан лечь на настоящий шум (тут он около −55 дБ), а не на пик тишины:
    # щелчки и вдохи в паузе стоят на −26 дБ, и порог по пику снова заедет на голос
    noisy = tmp / "floor_src.mp4"
    make_burst_source(noisy, 9.0, fps)
    floor = measure_noise_floor(noisy, detect_silence(noisy))
    report.check(-75.0 <= floor <= -40.0,
                 "порог шума замерен по настоящему шуму, а не по щелчкам в паузе",
                 f"{floor:.1f} дБ")

    chain = ",".join(voice_chain(audio, noise_floor=-52.0))
    report.check("nf=-52" in chain, "порог шумодава взят из замера, а не из пресета", chain)

    loud = [nf for nf in re.findall(r"nf=(-?[\d.]+)", chain) if float(nf) > -30]
    report.check(not loud, "шумодав не заходит на уровень голоса (nf выше −30 дБ)",
                 ", ".join(loud) or "чисто")

    # старое значение из пресета не должно доехать до ffmpeg как есть
    legacy = ",".join(voice_chain(dict(audio, denoise_strength=-24), noise_floor=-52.0))
    out_of_range = [nr for nr in re.findall(r"nr=(-?[\d.]+)", legacy)
                    if not 0.01 <= float(nr) <= 97]
    report.check(not out_of_range, "сила шумодава удержана в рамках ffmpeg",
                 ", ".join(out_of_range) or "в рамках")

    accepted = subprocess.run([
        ffmpeg_bin(), "-v", "error", "-f", "lavfi",
        "-i", "sine=frequency=300:duration=1", "-af", chain, "-f", "null", "-",
    ], capture_output=True, text=True)
    report.check(accepted.returncode == 0, "ffmpeg принимает цепочку обработки",
                 accepted.stderr.strip()[:80] or "принята")

    src = tmp / "voice_src.mp4"
    make_burst_source(src, 9.0, fps)
    out = tmp / "voice_out.mp4"
    before = {p.name for p in WORK_DIR.glob("*")}
    try:
        render(src, out, snap_segments([(0.0, 4.2), (4.6, 8.4)], fps), preset,
               ass_path=None, noise_floor=measure_noise_floor(src, detect_silence(src)))
    finally:
        for p in WORK_DIR.glob("*"):
            if p.name not in before and p.is_file():
                p.unlink()

    target = float(audio.get("loudness_target", -14))
    got = loudness_of(out)
    report.check(got is not None and abs(got - target) <= 2.0,
                 f"громкость на выходе рядом с целью {target:g} LUFS",
                 f"{got:.1f} LUFS" if got is not None else "замерить не вышло")


# Полосы тестового кадра в полном диапазоне: чёрная, почти чёрная, серая, почти белая, белая.
# Почти чёрная и почти белая нужны обязательно: кривая яркости сама зажимает края, и на
# чистых 0 и 255 пропущенное приведение диапазона не видно. Видно на тенях и светах рядом.
RANGE_BANDS = (0, 10, 128, 245, 255)
BAND_HEIGHT = 1920 // len(RANGE_BANDS)


def make_range_source(path: Path, seconds: float, fps: int):
    """Клип как с айфона: полный диапазон 0–255, горизонтальные полосы RANGE_BANDS."""
    lum = str(RANGE_BANDS[-1])
    for k in range(len(RANGE_BANDS) - 2, -1, -1):
        lum = f"if(lt(Y\\,{(k + 1) * BAND_HEIGHT})\\,{RANGE_BANDS[k]}\\,{lum})"
    subprocess.run([
        ffmpeg_bin(), "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"nullsrc=size=1080x1920:rate={fps}:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-vf", f"format=yuvj420p,geq=lum='{lum}':cb=128:cr=128",
        "-c:v", "libx264", "-qp", "0", "-color_range", "pc",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest",
        str(path),
    ], check=True, capture_output=True)


def band_luma(path: Path, top: int, height: int) -> float:
    """Средняя яркость (Y) горизонтальной полосы кадра."""
    out = subprocess.run([
        ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-frames:v", "5",
        "-vf", f"crop=1080:{height}:0:{top},signalstats,metadata=print:file=-",
        "-f", "null", "-",
    ], capture_output=True, text=True).stdout
    values = [float(v) for v in re.findall(r"YAVG=([\d.]+)", out)]
    return sum(values) / len(values) if values else float("nan")


def check_look(report: Report, preset: dict, tmp: Path):
    """Цвет: диапазон приводится к стандартному, яркость не ломает чёрное и белое.

    Айфон пишет полный диапазон 0–255. Без приведения одни плееры показывают чёрное
    серым, другие проваливают тени, — и это видно уже после публикации. А яркость,
    сделанная прибавлением константы, поднимает чёрное в серое: картинка застиранная.
    Полосы берутся из середины, подальше от стыков: на границе цвет размывает сжатие.
    """
    print("\nЦвет и яркость")
    fps = preset["video"]["fps"]
    src = tmp / "range_src.mov"
    make_range_source(src, 1.0, fps)

    base = dict(preset, motion=dict(preset.get("motion", {}), punch_in=False),
                audio=dict(preset.get("audio", {}), enabled=False))
    outputs = {}
    before = {p.name for p in WORK_DIR.glob("*")}
    try:
        for value in (0, -8):
            out = tmp / f"range_out_{abs(value)}.mp4"
            render(src, out, snap_segments([(0.0, 0.8)], fps),
                   dict(base, look={"enabled": True, "brightness": value}), ass_path=None)
            outputs[value] = out
    finally:
        for p in WORK_DIR.glob("*"):
            if p.name not in before and p.is_file():
                p.unlink()

    def bands(path: Path) -> list:
        # середина каждой полосы: на стыках цвет размывает сжатие
        return [band_luma(path, k * BAND_HEIGHT + BAND_HEIGHT // 4, BAND_HEIGHT // 2)
                for k in range(len(RANGE_BANDS))]

    def tv(y_full: float) -> float:
        return 16 + y_full * 219 / 255

    graded, plain = bands(outputs[-8]), bands(outputs[0])
    black, shadow, mid, light, white = graded
    want = [expected_luma(tv(y), -8) for y in RANGE_BANDS]

    report.check(abs(black - 16) <= 3, "чёрное осталось чёрным, а не серым и не провалилось",
                 f"Y={black:.1f}, ждали 16")
    report.check(abs(white - 235) <= 3, "белое не срезано и не посерело",
                 f"Y={white:.1f}, ждали 235")
    report.check(abs(shadow - want[1]) <= 3 and abs(light - want[3]) <= 3,
                 "тени и света у краёв не срезаны: диапазон приведён до кривой",
                 f"тень {shadow:.1f} (ждали {want[1]:.1f}), свет {light:.1f} (ждали {want[3]:.1f})")
    report.check(all(abs(got - tv(y)) <= 3 for got, y in zip(plain, RANGE_BANDS))
                 and look_filter({"brightness": 0}) == "",
                 "яркость 0 ничего не меняет, только приводит диапазон",
                 " ".join(f"{got:.0f}/{tv(y):.0f}" for got, y in zip(plain, RANGE_BANDS)))
    report.check(abs(mid - want[2]) <= 3 and plain[2] - mid >= 5,
                 "яркость −8 затемняет средние тона ровно настолько, насколько задумано",
                 f"Y={mid:.1f}, ждали {want[2]:.1f}, без коррекции {plain[2]:.1f}")
    tag = probe_value(outputs[-8], "stream=color_range", "v")
    report.check(tag == "tv", "файл помечен как стандартный диапазон", tag or "без пометки")


def synthetic_faces(xs: list, ys: list, fps: int = 30, width: int = 1080,
                    height: int = 1920, size: float = 260.0) -> dict:
    """Дорожка лица как из детектора: центр и размер по кадрам, None — лицо не найдено."""
    frames = [None if x is None else [x, y, size, size * 1.25, 0.99] for x, y in zip(xs, ys)]
    return {"fps": fps, "width": width, "height": height,
            "found": sum(1 for f in frames if f), "frames": frames}


def check_camera(report: Report):
    """Камера следит за лицом, но кадр всегда полный.

    Пустая полоса по краю — самый заметный брак слежения: окно камеры уехало за край
    исходника. Здесь лицо специально загоняется к самому краю, пропадает из детектора,
    дрожит и попадает под резкий зум режиссёра — окно обязано остаться внутри кадра.
    """
    import random
    from track import coverage_violations, solve_camera

    print("\nКамера и слежение за лицом")
    fps, width, height = 30, 1080, 1920
    rng = random.Random(7)

    def path(points: list, seconds: float) -> list:
        n = int(seconds * fps)
        return [float(np.interp(i / (n - 1), [p[0] for p in points], [p[1] for p in points]))
                for i in range(n)]

    # к левому краю и обратно, с дрожью детектора и дырами в распознавании
    xs = path([(0, 540), (0.35, 540), (0.5, 70), (0.7, 70), (1.0, 900)], 8.0)
    xs = [None if 90 <= i < 120 else x + rng.uniform(-12, 12) for i, x in enumerate(xs)]
    ys = [480.0 + rng.uniform(-8, 8) for _ in xs]
    cases = {
        "лицо у самого края": (synthetic_faces(xs, ys), []),
        "резкий зум режиссёра у края": (
            synthetic_faces([1010.0] * 120, [300.0] * 120), [[1.0, 2.5, 1.3, 0.1]]),
        "лица нет вовсе": (synthetic_faces([None] * 90, [None] * 90), []),
    }

    holes, crashed = [], []
    lost = 0.0
    for name, (faces, punches) in cases.items():
        try:
            camera = solve_camera(faces, punches=punches)
        except RuntimeError as error:
            crashed.append(f"{name}: {error}")
            continue
        holes += [f"{name}: кадр {i}" for i in coverage_violations(camera, width, height)]
        for (z, cx, cy), face in zip(camera, faces["frames"]):
            if face:
                sx = (face[0] - cx) * z + width / 2
                lost = max(lost, max(0.0, 0.03 * width - sx, sx - 0.97 * width))
    report.check(not crashed and not holes, "кадр полный на каждом кадре: окно не вылезает за исходник",
                 "; ".join((crashed + holes)[:3]) or "ни одной дыры")
    report.check(lost == 0.0, "лицо не теряется даже у самого края", f"вылет {lost:.0f} px")

    # Покачивания головы оператор пропускает целиком: камера стоит намертво. Камера-прицел
    # без мёртвой зоны даёт тут 2–3 px дрожи на каждом кадре — на экране это видно.
    calm = synthetic_faces([540 + rng.uniform(-15, 15) for _ in range(240)],
                           [480 + rng.uniform(-10, 10) for _ in range(240)])
    try:
        still = solve_camera(calm)
        wobble = float(np.std([cx for _, cx, _ in still]) + np.std([cy for _, _, cy in still]))
    except RuntimeError as error:
        wobble, still = float("inf"), str(error)
    report.check(wobble < 1.0, "мелкие покачивания камера пропускает",
                 f"разброс центра {wobble:.1f} px")

    try:
        moving = solve_camera(cases["лицо у самого края"][0])
        jump = max(abs(b[1] - a[1]) + abs(b[2] - a[2]) for a, b in zip(moving, moving[1:]))
        zoom_jump = max(abs(b[0] - a[0]) for a, b in zip(moving, moving[1:]))
    except RuntimeError:
        jump = zoom_jump = float("inf")
    report.check(jump < 20 and zoom_jump < 0.01, "камера едет плавно, без рывков",
                 f"до {jump:.1f} px и {zoom_jump:.4f} зума за кадр")

    # IMG_3303, кадр 1679: окно прижато к правому краю, зум 1.319994 округлялся вниз до
    # 1.31999 — окно росло и вылезало на 0.000008 px, сборка честно вставала.
    from track import _finish
    edge = []
    for z in (1.319994, 1.123456789, 1.2000049, 1.0):
        hw, hh = width / (2 * z), height / (2 * z)
        edge += [(z, width - hw, height - hh), (z, hw, hh)]
    rounded = _finish([e[0] for e in edge], [e[1] for e in edge], [e[2] for e in edge], width, height)
    report.check(not coverage_violations(rounded, width, height), "округление не выталкивает окно за край",
                 f"вылет на кадрах {coverage_violations(rounded, width, height)}" if coverage_violations(rounded, width, height)
                 else "ни одного")


def check_cuts(report: Report):
    """Склейка дубля: камера не «переезжает» через рез, а вырезанный кусок не возвращается.

    На склейке человек стоит по-разному. Если решать камеру одним куском, она полсекунды
    плавно едет от старого кадра к новому — выглядит как съехавший оператор. Правильно —
    сменить кадр мгновенно ровно на склейке и дальше стоять.
    """
    from prep import split_by_drops
    from track import coverage_violations, solve_camera

    print("\nСклейки")
    fps = 30
    # на склейке человек сместился вправо — но в пределах запаса камеры, без автозума к краю
    xs = [470.0] * 150 + [610.0] * 150
    faces = synthetic_faces(xs, [480.0] * 300, fps=fps)
    camera = solve_camera(faces, cuts=[150], punches=[[5.0, 7.0, 1.2, 0.0, 0.6]])
    jump = abs(camera[150][1] - camera[149][1])
    drift_after = abs(camera[165][1] - camera[150][1])
    report.check(jump > 100 and drift_after < 20, "на склейке кадр меняется сразу, а не едет следом",
                 f"скачок {jump:.0f} px на склейке, потом ещё {drift_after:.0f} px")
    report.check(not coverage_violations(camera, 1080, 1920), "кадр полный и со склейкой")
    report.check(abs(camera[150][0] - 1.2) < 1e-3, "наезд прячет склейку с первого же кадра",
                 f"зум на склейке {camera[150][0]:.3f}")

    pieces = split_by_drops(0.0, 60.0, [[41.86, 48.98]])
    report.check(pieces == [(0.0, 41.86), (48.98, 60.0)], "вырезанный дубль не попадает в ролик",
                 str(pieces))
    try:
        split_by_drops(0.0, 60.0, [[10.0, 20.0], [15.0, 25.0]])
        report.check(False, "наезжающие вырезы — громкая ошибка, а не тихая каша")
    except ValueError:
        report.check(True, "наезжающие вырезы — громкая ошибка, а не тихая каша")


def check_edges(report: Report):
    """Края дубля стоят по звуку, даже когда whisper ошибается на полсекунды.

    Два настоящих случая. IMG_3317: whisper начал «Тим» на 0.64, а звук пошёл с 1.07 —
    ролик открывался полсекундой пустоты. IMG_3311: «Супер» после паузы whisper приклеил
    вплотную к «объясню» — рез по его началу откусывал хвост последнего слова.
    """
    from prep import AIR, find_edges

    print("\nКрая дубля")
    words = [{"word": "Тим", "start": 0.64, "end": 1.28}, {"word": "Кук", "start": 1.28, "end": 1.50}]
    start, _ = find_edges(words, [(0.02, 0.41), (0.62, 1.07), (1.55, 1.70)], 0.3, 2.0)
    report.check(1.07 - AIR - 0.01 <= start <= 1.07, "дубль начинается со звука, а не с пустоты",
                 f"начало {start:.2f} с, звук с 1.07")
    # IMG_3320: тишину перед «Это» разорвал щелчок на 2.03 — это всё ещё одна пауза
    words = [{"word": "Это", "start": 1.70, "end": 2.28}, {"word": "Тимофей", "start": 2.28, "end": 2.78}]
    start, _ = find_edges(words, [(0.78, 1.59), (1.65, 2.03), (2.03, 2.15), (2.60, 2.70)], 1.5, 3.0)
    report.check(2.15 - AIR - 0.01 <= start <= 2.15, "щелчок в паузе не сдвигает начало в пустоту",
                 f"начало {start:.2f} с, звук с 2.15")

    words = [{"word": "объясню", "start": 68.44, "end": 68.82}, {"word": "Супер", "start": 68.82, "end": 69.84}]
    _, end = find_edges(words, [(68.10, 68.34), (68.81, 69.65), (69.93, 70.64)], 60.0, 68.80)
    report.check(68.81 <= end <= 69.65, "последнее слово не обрезано, следующее не попало",
                 f"конец {end:.2f} с, тишина 68.81–69.65")

    # слова идут вплотную, тишина только после лишнего: резать до него, по распознаванию
    words = [{"word": "мне", "start": 67.12, "end": 67.24}, {"word": "в", "start": 67.24, "end": 67.34}]
    _, end = find_edges(words, [(67.40, 67.60)], 60.0, 67.20)
    report.check(end <= 67.24, "лишнее слово без паузы перед ним не попадает в дубль",
                 f"конец {end:.2f} с")

    # Дубль начинается со звука (0.93), а whisper начал «Это» на 0.76: по началу слова оно
    # выпадало из субтитров, и все правки текста по номерам съезжали на слово.
    from cut import remap_words
    from prep import mark_dropped
    words = [{"word": "Это", "start": 0.76, "end": 1.24}, {"word": "Тимофей", "start": 1.24, "end": 1.80},
             {"word": "день", "start": 9.40, "end": 9.62}, {"word": "лишнее", "start": 10.5, "end": 11.0},
             {"word": "И", "start": 13.36, "end": 13.52}, {"word": "всё", "start": 13.52, "end": 13.80}]
    mark_dropped(words, [[9.78, 13.37]])
    kept = [w["word"] for w in remap_words(words, [(0.93, 9.78), (13.37, 20.0)])]
    report.check(kept == ["Это", "Тимофей", "день", "И", "всё"],
                 "слова на краях дубля и выреза не пропадают из субтитров", " · ".join(kept))


def check_captions(report: Report):
    """Субтитры уступают место крупной типографике, но слова перед ударом не теряют.

    Однажды вспышка, лишь хвостом заходившая в зону огромного «=», выкидывалась целиком —
    и перед хуком пропадало слово «равенства». Тихая поломка: ролик собирается, а смысл
    первой секунды уже не тот.
    """
    from compose import caption_chunks

    print("\nСубтитры")
    words = [{"word": w, "start": s, "end": e} for w, s, e in (
        ("Почему", 0.10, 0.50), ("знак", 0.59, 0.95), ("равенства", 1.07, 1.45),
        ("две", 1.57, 1.80), ("полоски?", 1.93, 2.50), ("это", 2.63, 2.90),
        ("в", 3.00, 3.05), ("Уэльсе", 3.10, 3.60))]
    director = {"hide_captions": [[1.50, 2.60]], "keep_case": ["Уэльсе"], "accent_words": ["равенства"]}
    chunks = caption_chunks(words, director, duration=4.0)
    texts = [c["text"] for c in chunks]

    report.check("равенства" in texts, "слово перед зоной типографики не потеряно",
                 " · ".join(texts))
    report.check(not any(c["t0"] < 2.60 and c["t1"] > 1.50 for c in chunks),
                 "субтитры не лезут в зону крупной типографики")
    report.check("две" not in texts and "полоски" not in texts,
                 "слова внутри зоны не дублируются субтитрами")
    from compose import CLINGY
    hanging = [t for t in texts if t.split()[-1].lower() in CLINGY]
    report.check(not hanging and any(t.endswith("Уэльсе") for t in texts),
                 "предлог не висит в конце вспышки, имя с большой буквы",
                 ", ".join(hanging) or " · ".join(texts))
    ordered = all(a["t1"] <= b["t0"] + 1e-6 for a, b in zip(chunks, chunks[1:]))
    report.check(ordered and all(c["t1"] > c["t0"] for c in chunks),
                 "вспышки идут по очереди и не накладываются")

    # Знаки снимались только с конца слова: из «цифра». выходило «цифра — открытая
    # кавычка без пары висела на экране.
    quoted = caption_chunks([{"word": "«цифра».", "start": 0.1, "end": 0.6},
                             {"word": "\"сифр\"", "start": 0.7, "end": 1.1}], {}, duration=2.0)
    texts = [c["text"] for c in quoted]
    report.check(texts == ["цифра", "сифр"], "кавычки не висят без пары", " · ".join(texts))

    # Whisper рвёт «по-индийски» на «по» + «-индийски», а «80+» на «80» + «+,»: на экране
    # выходило «по -индийски», отдельная вспышка «-чуть» и одинокое «—».
    torn = [("по", 0.1, 0.2), ("-индийски", 0.2, 0.7), ("—", 0.8, 0.9), ("чуть", 1.0, 1.2),
            ("-чуть", 1.2, 1.4), ("на", 1.5, 1.6), ("80", 1.6, 1.9), ("+,", 1.9, 2.1)]
    glued = caption_chunks([{"word": w, "start": s, "end": e} for w, s, e in torn], {}, duration=3.0)
    texts = [c["text"] for c in glued]
    report.check(not any(t.startswith("-") or " -" in t or t in ("—", "+") for t in texts)
                 and any("по-индийски" in t for t in texts) and any("чуть-чуть" in t for t in texts)
                 and any("80+" in t for t in texts),
                 "слова через дефис и «80+» не рвутся, тире не мигает", " · ".join(texts))

    # Whisper ставит соседние слова вплотную: «кто» и «не» через 20 мс. Вспышка короче
    # своего входа залипала в рендере до конца ролика (пять роликов из пятнадцати).
    from compose import MIN_FLASH
    tight = caption_chunks([{"word": w, "start": s, "end": e} for w, s, e in (
        ("Кто", 0.50, 0.52), ("не", 0.52, 0.60), ("знал", 0.62, 0.90), ("привет", 1.50, 1.80),
        ("всем", 2.96, 3.00))], {}, duration=3.0)
    texts = [c["text"] for c in tight]
    report.check(texts == ["кто не знал", "привет всем"] and all(c["t1"] - c["t0"] >= 0.12 for c in tight),
                 f"вспышка короче {MIN_FLASH:g} с сливается со следующей, слова не теряются",
                 " · ".join(f"{c['text']} {c['t1'] - c['t0']:.2f}" for c in tight))


def check_module_names(report: Report, folder: Path = Path(__file__).resolve().parent):
    """Скрипт не называется как модуль стандартной библиотеки.

    scripts/ стоит первым в sys.path, и однажды очередь лежала в scripts/queue.py: она
    подменила стандартный queue, huggingface_hub упал на импорте, и восемь распознаваний
    подряд провалились за секунду каждое.
    """
    print("\nИмена скриптов")
    clash = sorted(p.stem for p in folder.glob("*.py") if p.stem in sys.stdlib_module_names)
    report.check(not clash, "ни один скрипт не подменяет модуль стандартной библиотеки",
                 ", ".join(f"{name}.py" for name in clash) or "чисто")


def check_page_timeline(report: Report, tmp: Path):
    """Ничего не залипает на экране в покадровом рендере HyperFrames.

    Уход субтитра (set) срабатывал посреди его входа, и на следующем кадре недоигравший
    fromTo дописывал opacity 1: слово висело до конца ролика, следующие бежали поверх.
    На снимках чисто — снимок прыгает сразу во время. Проверка гоняет страницу в том же
    Chrome, что и рендер; здесь она обязана поймать и старый код субтитров, и такое же
    перекрытие у обычной надписи.
    """
    from kit import build_page
    from verify_page import run_timeline

    print("\nСтраница графики")
    project = tmp / "page"
    (project / "assets").mkdir(parents=True)
    shutil.copy2(ROOT / "studio" / "_vendor" / "gsap.min.js", project / "assets" / "gsap.min.js")
    (project / "camera.js").write_text("window.CAMERA_FPS = 30;\nwindow.CAMERA = [[0, 0, 1], [0, 0, 1]];\n")
    caps = [{"t0": 0.50, "t1": 1.20, "text": "обычная", "accent": False},
            {"t0": 1.807, "t1": 1.847, "text": "мы", "accent": False},    # кадр 1.867 — между уходом и концом входа
            {"t0": 2.927, "t1": 3.007, "text": "кто", "accent": False}]   # щель 3.007–3.017 пока мимо кадров
    (project / "captions.js").write_text(
        "window.CAPTIONS = " + json.dumps(caps, ensure_ascii=False) + ";\n", encoding="utf-8")
    behind = '        <div id="t-word" class="g big" style="top: 200px; font-size: 200px;">тест</div>'
    beats = ('      enter("#t-word", 0.20);\n'
             '      leave("#t-word", 0.30, { dur: 0.05 });   // уход раньше конца влёта (0.52)\n'
             '      enter("#nope", 1.00);                     // опечатка в селекторе\n')
    page = build_page("проверка", 4.0, behind, "", beats, [], [], cta_at=3.3)
    old_entry = page.replace("Math.min(0.09, c.t1 - c.t0)", "0.09")
    try:
        (project / "index.html").write_text(page, encoding="utf-8")
        res = run_timeline(project / "index.html")
        (project / "index.html").write_text(old_entry, encoding="utf-8")
        old = run_timeline(project / "index.html")
    except (RuntimeError, ValueError) as e:
        report.check(False, "страница разбирается в Chrome HyperFrames", str(e)[:200])
        return

    stuck = {i["el"] for i in res.get("stuck", [])}
    risky = {i["el"] for i in res.get("risky", [])}
    report.check(res.get("ok") and "#t-word" in stuck, "уход посреди влёта у надписи ловится",
                 ", ".join(stuck) or res.get("crash", "ничего не нашла"))
    caps_bad = sorted(e for e in stuck | risky if e.startswith("субтитр"))
    report.check(res.get("ok") and not caps_bad, "субтитр короче своего входа не залипает",
                 ", ".join(caps_bad) or "чисто")
    report.check(any("#nope" in w for w in res.get("warnings", [])), "селектор, который ничего не нашёл, виден",
                 "; ".join(res.get("warnings", []))[:120] or "предупреждений нет")
    old_stuck = {i["el"] for i in old.get("stuck", [])}
    old_risky = {i["el"] for i in old.get("risky", [])}
    report.check(old_entry != page and "субтитр «мы»" in old_stuck and "субтитр «кто»" in old_risky,
                 "старый вход субтитров ловится: «мы» залипает, «кто» — без запаса по кадрам",
                 f"залипает: {', '.join(sorted(old_stuck)) or '—'}; без запаса: {', '.join(sorted(old_risky)) or '—'}")


def check_face_memory(report: Report, tmp: Path):
    """Поиск лиц держит память постоянной, сколько бы ни было кадров.

    Привязка к Apple Vision однажды держала каждый кадр навсегда: +2 МБ на кадр,
    2,4 ГБ на минутном ролике — и это до сборки, на 16 ГБ машине с открытым браузером.
    """
    print("\nПамять при поиске лиц")
    peaks = {}
    for seconds in (2, 12):
        clip = tmp / f"faces_{seconds}s.mp4"
        make_source(clip, seconds, 30)
        probe_code = (
            "import resource, sys; sys.path.insert(0, 'scripts');"
            "from track import detect_faces;"
            f"faces = detect_faces(__import__('pathlib').Path(r'{clip}'));"
            "print(len(faces['frames']), resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)")
        result = subprocess.run([sys.executable, "-c", probe_code], capture_output=True,
                                text=True, cwd=Path(__file__).resolve().parent.parent)
        try:
            frames, rss = result.stdout.split()[-2:]
            peaks[seconds] = (int(frames), int(rss) / 1048576)
        except ValueError:
            peaks[seconds] = (0, float("nan"))
            print(f"    {result.stderr.strip()[-300:]}")
    (n_short, short), (n_long, long_) = peaks[2], peaks[12]
    growth = long_ - short
    report.check(n_long > n_short > 0 and growth < 150,
                 "память не растёт с числом кадров",
                 f"{n_short} кадров — {short:.0f} МБ, {n_long} кадров — {long_:.0f} МБ")


def stray_files() -> list:
    """Промежуточные куски и списки склейки, которые обязаны убираться за собой."""
    return sorted(p.name for p in WORK_DIR.glob("*")
                  if p.name.endswith(".concat.txt") or p.name.endswith("_segments"))


def check_snapping(report: Report):
    print("\nСетка кадров")
    raw = [(0.017, 1.681), (2.34, 3.4207), (4.02, 6.4799)]
    once = snap_segments(raw, 30)
    twice = snap_segments(once, 30)

    report.check(once == twice, "повторное применение ничего не меняет")
    report.check(
        all(abs((e - s) * 30 - round((e - s) * 30)) < 1e-6 for s, e in once),
        "длительности кратны кадру",
        ", ".join(f"{(e - s) * 30:.0f} кадр." for s, e in once),
    )
    degenerate = snap_segments([(1.0, 1.0), (2.0, 2.001)], 30)
    report.check(all(e > s for s, e in degenerate),
                 "нулевой сегмент не схлопывается в пустоту")


def check_plan_alignment(report: Report, preset: dict):
    """План обязан отдавать сегменты уже по сетке кадров.

    Проверка идёт именно через plan_cut, а не через готовые сегменты: субтитры считаются
    от его чисел, и если выравнивание отсюда пропадёт, сборка останется корректной,
    а текст поедет. Такую поломку легко не заметить — она копится к концу ролика.
    """
    print("\nПлан реза")
    fps = preset["video"]["fps"]

    # синтетическая речь: границы слов заведомо не попадают на кадры
    words, t = [], 0.137
    for i in range(40):
        words.append({"word": f"слово{i}", "start": round(t, 3), "end": round(t + 0.313, 3)})
        t += 0.313 + (0.9 if i % 5 == 4 else 0.07)   # каждое пятое слово — длинная пауза

    plan = plan_cut(words, preset["cut"], duration=t + 1.0, fps=fps)
    segments = plan["segments"]

    report.check(len(segments) > 1, "паузы разбили речь на сегменты", f"{len(segments)} шт.")
    report.check(
        all(abs((e - s) * fps - round((e - s) * fps)) < 1e-6 for s, e in segments),
        "сегменты плана кратны кадру",
    )

    kept = sum(e - s for s, e in segments)
    last_word = max((w["end"] for w in plan["words"]), default=0.0)
    report.check(last_word <= kept + 1e-6,
                 "субтитры укладываются в хронометраж",
                 f"последнее слово на {last_word:.2f} с, ролик {kept:.2f} с")


def check_cleanup_on_failure(report: Report, preset: dict):
    print("\nУборка при падении")
    before = stray_files()
    try:
        render(Path("/nonexistent/нет-такого-файла.mov"), WORK_DIR / "_never.mp4",
               [(0.0, 1.0)], preset)
        report.check(False, "сборка несуществующего файла обязана падать")
    except RuntimeError:
        report.check(True, "падение отдаёт понятную ошибку, а не тишину")
    report.check(stray_files() == before, "временные файлы убраны после падения",
                 f"было {len(before)}, стало {len(stray_files())}")


def check_web_import(report: Report, tmp: Path):
    """Перетаскивание из Telegram даёт странице путь к файлу, а не сам файл.

    Путь принимает сервер. Проверяется главное: чужой файл либо доходит до input/,
    либо получает внятный отказ. Тихое «ничего не произошло» здесь хуже всего — человек
    ждёт ролик от видео, которого в работе нет.
    """
    print("\nПриём перетащенного файла")
    from server import import_local_file

    report.check("error" in import_local_file(""), "пустой путь отвергнут")
    report.check("error" in import_local_file(str(tmp / "нет-такого.mp4")),
                 "несуществующий путь отвергнут")

    note = tmp / "заметка.txt"
    note.write_text("это не видео", encoding="utf-8")
    report.check("error" in import_local_file(str(note)), "не-видео отвергнуто")

    # ровно то, что отдаёт мессенджер: file://-ссылка на файл кэша, часто без расширения
    cached = tmp / "кусок кэша"
    made = tmp / "кусок кэша.mp4"      # ffmpeg выбирает контейнер по расширению
    make_source(made, 1.0, 30)
    made.replace(cached)
    landed = []
    try:
        first = import_local_file("file://" + quote(str(cached)))
        if "name" in first:
            landed.append(INPUT_DIR / first["name"])
        arrived = "name" in first and (INPUT_DIR / first["name"]).exists()
        report.check(arrived, "файл по file://-ссылке лёг в input/",
                     first.get("name") or first.get("error", ""))
        report.check(arrived and Path(first["name"]).suffix == ".mp4",
                     "файлу без расширения дано .mp4")

        second = import_local_file(str(cached))
        if "name" in second:
            landed.append(INPUT_DIR / second["name"])
        report.check(arrived and second.get("name") not in (None, first.get("name")),
                     "повторный приём не затирает уже лежащий файл", second.get("name", ""))
    finally:
        for path in landed:
            path.unlink(missing_ok=True)


def check_render(report: Report, preset: dict, n_segments: int, tmp: Path):
    fps = preset["video"]["fps"]
    seconds = max(20.0, n_segments * 0.55)
    print(f"\nСборка: {n_segments} сегментов из {seconds:.0f} с исходника")

    src = tmp / "selfcheck_src.mov"
    print("  … готовлю синтетический исходник", flush=True)
    make_source(src, seconds, fps)

    step = seconds / n_segments
    segments = snap_segments(
        [(i * step, i * step + step * 0.6) for i in range(n_segments)], fps)
    expected = sum(e - s for s, e in segments)

    out = tmp / "selfcheck_out.mp4"
    before = {p.name for p in WORK_DIR.glob("*")}
    started = time.time()
    try:
        with Watcher() as watcher:
            render(src, out, segments, preset, ass_path=None)
    finally:
        # граф фильтра рендер оставляет намеренно — он полезен при разборе падений,
        # но синтетический прогон не должен мусорить в рабочей папке
        for p in WORK_DIR.glob("*"):
            if p.name not in before and p.is_file():
                p.unlink()
    spent = time.time() - started

    report.check(watcher.peak_mb < RAM_CEILING_MB,
                 f"память под потолком {RAM_CEILING_MB} МБ",
                 f"пик {watcher.peak_mb:.0f} МБ")
    report.check(watcher.peak_procs <= 1,
                 "не больше одного ffmpeg разом",
                 f"максимум {watcher.peak_procs}, замеров {watcher.samples}")

    actual = float(probe_value(out, "format=duration"))
    drift = abs(actual - expected)
    report.check(drift < DRIFT_TOLERANCE_SEC,
                 "длина ролика совпадает с планом",
                 f"расхождение {drift * 1000:.0f} мс на {n_segments} склейках")

    width = probe_value(out, "stream=width", "v")
    height = probe_value(out, "stream=height", "v")
    report.check((width, height) == (str(preset["video"]["width"]),
                                     str(preset["video"]["height"])),
                 "кадр 9:16", f"{width}×{height}")
    report.check(probe_value(out, "stream=codec_type", "a") == "audio",
                 "звуковая дорожка на месте")

    decode = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(out), "-f", "null", "-"],
                            capture_output=True, text=True)
    report.check(not decode.stderr.strip(), "файл декодируется без ошибок",
                 decode.stderr.strip()[:80] or "чисто")
    report.check(not stray_files(), "временные файлы убраны")

    print(f"  · заняло {spent:.0f} с, ролик {out.stat().st_size / 1048576:.0f} МБ")


def check_agents(report: Report):
    """Claude и Codex читают одни и те же правила и один скилл.

    Раньше правила и скилл жили двумя копиями: поправил одну — Claude и Codex начинали
    монтировать по-разному, молча. Теперь CLAUDE.md подключает AGENTS.md, а скилл Claude —
    ссылка на скилл Codex. Хуки старта обоих агентов поднимают студию, но не внутри агентов,
    которых запускает сама студия (иначе каждый ответ мозга открывал бы вкладку).
    """
    print("\nClaude и Codex: одни правила")
    claude_md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8").strip()
    report.check(claude_md == "@AGENTS.md", "CLAUDE.md подключает AGENTS.md, а не хранит копию",
                 claude_md[:40])
    agents_md = ROOT / "AGENTS.md"
    report.check(agents_md.exists() and "Инварианты" in agents_md.read_text(encoding="utf-8"),
                 "правила проекта лежат в AGENTS.md")
    claude_skill, codex_skill = ROOT / ".claude/skills/reels", ROOT / ".agents/skills/reels"
    same = claude_skill.resolve() == codex_skill.resolve() and (codex_skill / "SKILL.md").exists()
    report.check(same, "скилл reels один на оба агента (ссылка, не копия)",
                 str(claude_skill.resolve().relative_to(ROOT)) if claude_skill.exists() else "нет скилла")
    head = (codex_skill / "SKILL.md").read_text(encoding="utf-8").split("\n", 3)[:3] if same else []
    report.check(len(head) == 3 and head[0] == "---" and head[1].startswith("name: reels"),
                 "у скилла есть заголовок name/description", " | ".join(head)[:60])

    hooks = []
    for path, key in ((ROOT / ".claude/settings.json", "hooks"), (ROOT / ".codex/hooks.json", "hooks")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            hooks += [h["command"] for g in data[key]["SessionStart"] for h in g["hooks"]]
        except (OSError, KeyError, json.JSONDecodeError) as e:
            hooks.append(f"ошибка {path.name}: {e}")
    report.check(len(hooks) == 2 and all("studio_up.py" in h and "|| true" in h for h in hooks),
                 "хуки старта Claude и Codex поднимают студию и не роняют сессию", "; ".join(h[:50] for h in hooks))

    env = dict(os.environ, REELS_STUDIO_CHILD="1")
    child = subprocess.run([sys.executable, str(ROOT / "scripts/studio_up.py")], input="{}",
                           capture_output=True, text=True, env=env, timeout=20)
    report.check(child.returncode == 0 and not child.stdout.strip(),
                 "агент, запущенный студией, студию не открывает", child.stdout.strip()[:80] or "тихо")


def check_styles(report: Report):
    """Каталог стилей валиден, а сломанный стиль — громкая ошибка, а не 9:16 молча."""
    import copy as _copy
    import styles

    print("\nСтили монтажа")
    try:
        catalog = styles.all_styles()
        presets = [styles.to_fast_preset(st, fmt) for st in catalog for fmt in st["formats"]]
        problem = ""
    except styles.StyleError as e:
        catalog, presets, problem = [], [], str(e)
    tiers = {st["tier"] for st in catalog}
    report.check(len(catalog) >= 10 and tiers == set(styles.TIERS),
                 "каталог: стили всех тиров — от мейнстрима до антитренда",
                 problem or f"{len(catalog)} стилей, тиры: {', '.join(sorted(tiers))}")
    sizes_ok = all((p["video"]["width"], p["video"]["height"]) in
                   [(f["width"], f["height"]) for f in styles.formats.FORMATS.values()] for p in presets)
    report.check(bool(presets) and sizes_ok, "каждый стиль собирается в пресет под каждый свой формат",
                 f"{len(presets)} пресетов")

    broken = _copy.deepcopy(catalog[0]) if catalog else {}
    caught = 0
    for field, value in (("captions.mode", "бегущая строка"), ("color.grade", "кислотный"),
                         ("camera.base_zoom", 1.8)):
        try:
            styles.effective(broken, {field: value})
        except styles.StyleError:
            caught += 1
    report.check(caught == 3, "ошибка в стиле — громкий отказ (режим субтитров, грейд, зум)",
                 f"поймано {caught} из 3")

    best = styles.recommend({"reach": 5, "retention": 5, "trust": 0, "saves": 0, "sales": 0}, 0.0)[0][1]
    calm = styles.recommend({"reach": 0, "retention": 0, "trust": 5, "saves": 2, "sales": 5}, 1.0)[0][1]
    report.check(best["tier"] == "mainstream" and calm["tier"] in ("niche", "contrarian"),
                 "подбор слушает цели и смелость: охват — мейнстрим, доверие со смелостью — ниша",
                 f"{best['id']} / {calm['id']}")


def check_grades(report: Report, tmp: Path):
    """Грейд стиля не выталкивает чёрное ниже 16 и белое выше 235.

    eq=contrast крутит яркость вокруг 128 полного диапазона: чёрное уходило в 6, белое в
    242 — на телефоне это срезанные тени и пересвет. Контраст считается кривой внутри 16–235.
    """
    import re as _re
    from look import GRADES, look_filter

    print("\nЦвет стилей")
    def level(color: str, chain: str) -> float:
        out = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-f", "lavfi", "-i",
                              f"color=c={color}:s=320x320:d=0.1", "-vf",
                              f"scale=out_range=tv,format=yuv420p{',' + chain if chain else ''},"
                              "crop=120:120:100:100,signalstats,metadata=print:file=-",
                              "-frames:v", "1", "-f", "null", "-"], capture_output=True, text=True).stdout
        found = _re.search(r"YAVG=([\d.]+)", out)
        return float(found.group(1)) if found else -1.0
    bad = []
    for name in GRADES:
        chain = look_filter({"brightness": -8, "grade": name})
        black, white = level("black", chain), level("white", chain)
        # выше 235 и ниже 16 — брак; виньетка «редакционного» белое честно приглушает (до ~220)
        if not (15 <= black <= 17.5 and 200 <= white <= 235.5):
            bad.append(f"{name}: {black:.0f}/{white:.0f}")
    report.check(not bad, "грейды держат стандартный диапазон 16–235", "; ".join(bad) or f"{len(GRADES)} грейдов")
    naive = level("black", "eq=contrast=1.12")
    report.check(naive < 15, "проверка ловит наивный контраст (eq=contrast роняет чёрное)", f"чёрное {naive:.0f}")


def check_formats(report: Report, tmp: Path):
    """Горизонталь и перекадрирование: окно любой формы внутри исходника, кадр едет за лицом."""
    import formats
    from kit import STYLE, build_page
    from reframe import apply, reframe_path
    from track import coverage_violations

    print("\nФорматы и перекадрирование")
    # горизонтальный исходник, лицо гуляет от края до края — вертикальное окно не вылезает
    xs = [80 + 1760 * (0.5 - 0.5 * np.cos(i / 239 * np.pi)) for i in range(240)]
    faces = synthetic_faces(xs, [420.0] * 240, width=1920, height=1080, size=200)
    try:
        window, camera = reframe_path(faces, "9:16")
        holes = coverage_violations(camera, 1920, 1080, window=window)
        wrong = coverage_violations(camera, 1920, 1080)       # без окна — будто окно во весь кадр
    except RuntimeError as e:
        window, camera, holes, wrong = None, [], [str(e)], []
    report.check(window is not None and abs(window[0] / window[1] - 9 / 16) < 1e-6 and not holes,
                 "вертикальное окно из горизонтали всегда внутри исходника", f"окно {window}, дыр {len(holes)}")
    report.check(bool(wrong) or not camera, "проверка окна различает формы (иначе она не про то)",
                 f"с неверным окном: {len(wrong)} кадров «вне»")

    # настоящий ffmpeg: полоса едет по горизонтальному кадру, а в вертикальном стоит у центра
    src = tmp / "bar.mov"
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x202020:s=1280x720:r=30:d=4",
                    "-f", "lavfi", "-i", "color=c=white:s=60x720:r=30:d=4", "-f", "lavfi", "-i", "sine=f=440:d=4",
                    "-filter_complex", "[0][1]overlay=x='100+t*250':y=0[v]", "-map", "[v]", "-map", "2:a",
                    "-c:v", "libx264", "-crf", "16", "-c:a", "pcm_s16le", str(src)], check=True)
    bar = synthetic_faces([130 + i / 30 * 250 for i in range(120)], [360.0] * 120, width=1280, height=720, size=80)
    out = tmp / "bar.9x16.mov"

    def centers(path: Path, w: int, h: int) -> list:
        found = []
        for at in (1.0, 2.0, 3.0):
            raw = subprocess.run([ffmpeg_bin(), "-v", "error", "-ss", str(at), "-i", str(path), "-frames:v", "1",
                                  "-vf", "format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
            img = np.frombuffer(raw, np.uint8).reshape(h, w)
            cols = np.where(img[h // 2 - 40:h // 2 + 40].mean(axis=0) > 128)[0]
            found.append(float(cols.mean()) if len(cols) else -1.0)
        return found
    try:
        window, camera = reframe_path(bar, "9:16")
        apply(src, out, camera, window, 30, "9:16", 1280, 720)
        got = centers(out, 1080, 1920)
        probe_out = subprocess.run([ffprobe_bin(), "-v", "error", "-show_entries", "stream=width,height",
                                    "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.split()
    except (RuntimeError, subprocess.CalledProcessError, ValueError) as e:
        got, probe_out = [], [str(e)[:80]]
    src_moves = centers(src, 1280, 720)
    report.check(probe_out[:1] == ["1080,1920"] and bool(got) and all(abs(c - 540) < 240 for c in got),
                 "перекадрирование ведёт кадр за объектом (полоса у центра вертикали)",
                 f"исходник: {', '.join(f'{c:.0f}' for c in src_moves)} → вертикаль: {', '.join(f'{c:.0f}' for c in got)}")

    # страница: вертикаль байт в байт прежняя, горизонталь — своя сцена
    portrait = build_page("т", 2.0, "", "", "", [], [], cta_at=1.0)
    landscape = build_page("т", 2.0, "", "", "", [], [], cta_at=1.0, fmt="16:9")
    report.check(STYLE in portrait and 'data-width="1080" data-height="1920"' in portrait,
                 "вертикальная страница собирается как раньше")
    report.check('data-width="1920" data-height="1080"' in landscape and "width: 1080px; height: 1920px" not in landscape
                 and formats.get("16:9")["resolution"] in landscape,
                 "горизонтальная страница — сцена 1920×1080 без вертикальных остатков")


def check_style_captions(report: Report, tmp: Path):
    """Субтитры стилей (караоке, фразы, плашки) тоже не залипают в покадровом рендере."""
    import styles
    from compose import MIN_FLASH, caption_chunks
    from kit import build_page
    from verify_page import run_timeline

    print("\nСубтитры стилей")
    words = [{"word": w, "start": a, "end": b} for w, a, b in (
        ("Почему", 0.10, 0.40), ("знак", 0.42, 0.60), ("равенства,", 0.61, 1.00), ("это", 1.80, 1.95),
        ("тест?", 1.96, 2.40), ("Нет.", 3.50, 3.80), ("Всё", 3.81, 3.83), ("дело", 3.84, 4.10))]
    ok_modes = []
    for mode in ("karaoke", "phrase", "sentence"):
        chunks = caption_chunks(words, {}, 5.0, mode, "natural")
        short = [c for c in chunks if c["t1"] - c["t0"] < MIN_FLASH]
        karaoke_ok = mode != "karaoke" or all(c["t0"] <= w["t0"] < c["t1"] for c in chunks for w in c["words"])
        ok_modes.append(not short and karaoke_ok and chunks)
    report.check(all(ok_modes), "режимы субтитров: без вспышек короче 0.15 с, караоке внутри своих фраз",
                 ", ".join(m for m, ok in zip(("караоке", "фразы", "предложения"), ok_modes) if not ok) or "чисто")

    project = tmp / "style-page"
    (project / "assets").mkdir(parents=True)
    shutil.copy2(ROOT / "studio" / "_vendor" / "gsap.min.js", project / "assets" / "gsap.min.js")
    (project / "camera.js").write_text("window.CAMERA_FPS = 30;\nwindow.CAMERA = [[0, 0, 1], [0, 0, 1]];\n")
    caps = [{"t0": 0.50, "t1": 1.20, "text": "обычная", "accent": False,
             "words": [{"text": "обычная", "t0": 0.5}]},
            {"t0": 1.807, "t1": 1.847, "text": "мы", "accent": False, "words": [{"text": "мы", "t0": 1.807}]}]
    (project / "captions.js").write_text("window.CAPTIONS = " + json.dumps(caps, ensure_ascii=False) + ";\n",
                                         encoding="utf-8")
    bad, caught = [], False
    for style_id in ("hormozi", "lofi-ugc", "video-essay"):
        kc = styles.kit_captions(styles.load_style(style_id))
        page = build_page("т", 3.0, "", "", "", [], [], cta_at=2.5, fmt="16:9", captions=kc)
        (project / "index.html").write_text(page, encoding="utf-8")
        try:
            res = run_timeline(project / "index.html")
        except (RuntimeError, ValueError) as e:
            bad.append(f"{style_id}: {e}")
            continue
        stuck = [i["el"] for i in res.get("stuck", []) + res.get("risky", []) if i["el"].startswith("субтитр")]
        if not res.get("ok") or stuck or res.get("pageErrors"):
            bad.append(f"{style_id}: {', '.join(stuck) or res.get('pageErrors') or res.get('crash')}")
        if style_id == "video-essay":           # вход 0.14 с без ограничения — «мы» обязан залипнуть
            broken = page.replace("const d = Math.min(0.14, c.t1 - c.t0);", "const d = 0.14;")
            (project / "index.html").write_text(broken, encoding="utf-8")
            res = run_timeline(project / "index.html")
            caught = broken != page and any(i["el"] == "субтитр «мы»" for i in res.get("stuck", []))
    report.check(not bad, "субтитры стилей не залипают (Хормози, лоуфай, видео-эссе)", "; ".join(bad) or "чисто")
    report.check(caught, "проверка ловит вход стиля длиннее вспышки")


def check_studio(report: Report):
    """Студия отвечает только этой машине и только своей странице.

    Сервер умеет запускать агента с правом править файлы. Чужой сайт в соседней вкладке
    не должен суметь ни запустить его, ни поменять бриф: нужен ключ, который знает лишь
    наша страница, а Host — только 127.0.0.1/localhost (защита от DNS rebinding).
    """
    from fastapi.testclient import TestClient
    import brain
    import jobqueue
    from server import TOKEN, app

    print("\nСтудия: доступ и мозг")
    web = TestClient(app, base_url="http://127.0.0.1:8765")
    page = web.get("/")
    report.check(page.status_code == 200 and TOKEN in page.text, "страница студии отдаётся с ключом")
    no_key = web.post("/api/brain/threads", json={"engine": "claude"})
    foreign = web.post("/api/brain/threads", json={"engine": "claude"},
                       headers={"X-Studio-Token": TOKEN, "Origin": "https://evil.example"})
    rebound = TestClient(app, base_url="http://evil.example").get("/api/studio/state")
    allowed = web.post("/api/studio/brief/НЕТ_ТАКОГО_РОЛИКА", json={}, headers={"X-Studio-Token": TOKEN})
    report.check(no_key.status_code == 403 and foreign.status_code == 403 and rebound.status_code == 403,
                 "без ключа, с чужой страницы и с чужого адреса — отказ",
                 f"{no_key.status_code}/{foreign.status_code}/{rebound.status_code}")
    report.check(allowed.status_code == 404, "с ключом запрос проходит до дела", f"код {allowed.status_code}")

    claude = brain.parse_line("claude", json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "Готово"}, {"type": "tool_use", "id": "t1", "name": "Bash",
                                              "input": {"command": "ls work"}}]}}))
    codex = brain.parse_line("codex", json.dumps({"type": "item.started", "item": {
        "id": "i1", "type": "mcp_tool_call", "server": "node_repl", "tool": "js", "arguments": {}}}))
    report.check([e["type"] for e in claude] == ["text", "tool"] and codex and codex[0]["type"] == "tool",
                 "события Claude и Codex доходят до чата (и действия через MCP тоже)")
    cmd_safe = brain.command("claude", "x", mode="safe") if brain.find_binary("claude") else ["--permission-mode"]
    report.check("--dangerously-skip-permissions" not in cmd_safe and "--permission-mode" in cmd_safe,
                 "безопасный режим мозга не снимает ограничения")
    report.check(brain.child_env().get(brain.CHILD_ENV) == "1", "агент студии помечен для хука старта")

    first = jobqueue.take_lock()
    if first is None:
        # рядом работает настоящий обработчик — его замок и есть проверка
        report.check(jobqueue.runner_alive(), "обработчик очереди один: второй видит замок",
                     "проверено на работающей очереди")
        return
    second = jobqueue.take_lock()
    alive = jobqueue.runner_alive()
    first.close()
    report.check(second is None and alive and not jobqueue.runner_alive(),
                 "обработчик очереди один: второй видит замок")


def main():
    ap = argparse.ArgumentParser(description="Самопроверка пайплайна монтажа")
    ap.add_argument("--long", action="store_true", help="200 сегментов вместо 60")
    ap.add_argument("--preset", default="viral")
    args = ap.parse_args()

    WORK_DIR.mkdir(exist_ok=True)
    preset = load_preset(args.preset)
    report = Report()

    check_module_names(report)
    check_agents(report)
    check_styles(report)
    check_snapping(report)
    check_plan_alignment(report, preset)
    check_camera(report)
    check_cuts(report)
    check_edges(report)
    check_captions(report)
    check_cleanup_on_failure(report, preset)
    with tempfile.TemporaryDirectory(prefix="reels_selfcheck_") as tmpdir:
        check_page_timeline(report, Path(tmpdir))
        check_style_captions(report, Path(tmpdir))
        check_formats(report, Path(tmpdir))
        check_grades(report, Path(tmpdir))
        check_studio(report)
        check_web_import(report, Path(tmpdir))
        check_cut_keeps_speech(report, preset, Path(tmpdir))
        check_voice(report, preset, Path(tmpdir))
        check_look(report, preset, Path(tmpdir))
        check_face_memory(report, Path(tmpdir))
        check_render(report, preset, 200 if args.long else 60, Path(tmpdir))

    print()
    if report.failed:
        print(f"✗ провалено проверок: {len(report.failed)}")
        for title in report.failed:
            print(f"    — {title}")
        sys.exit(1)
    print("✓ всё чисто, пайплайн можно отдавать в работу")


if __name__ == "__main__":
    main()
