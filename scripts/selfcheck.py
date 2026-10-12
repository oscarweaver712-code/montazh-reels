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
    покадровом рендере HyperFrames проигрывал (пять роликов из пятнадцати, на снимках чисто);
  • упавшая сборка и маска не оставляют битый файл под настоящим именем и не стирают прошлый;
  • другое видео под старым именем не получает чужой транскрипт;
  • студия переживает сбой в одном месте (битый бриф, файл без видео, странное событие
    агента), а тяжёлое из неё — и из быстрой панели — идёт только через очередь.

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
import traceback
from pathlib import Path

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

    def _rows(self) -> list:
        """(pid, ppid, rss в КБ, имя) всех процессов: psutil на любой системе, ps — запасной."""
        try:
            import psutil
            rows = []
            for proc in psutil.process_iter(["pid", "ppid", "memory_info", "name"]):
                info = proc.info
                if info.get("memory_info") is not None:
                    rows.append((info["pid"], info["ppid"] or 0, info["memory_info"].rss // 1024, info["name"] or ""))
            return rows
        except ImportError:
            out = subprocess.run(["ps", "-axo", "pid=,ppid=,rss=,comm="],
                                 capture_output=True, encoding="utf-8", errors="replace").stdout
            rows = []
            for line in out.splitlines():
                parts = line.split(None, 3)
                if len(parts) == 4 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
                    rows.append((int(parts[0]), int(parts[1]), int(parts[2]), parts[3]))
            return rows

    def _sample(self) -> tuple:
        rows, kids, parent = [], {}, {}
        for pid, ppid, rss, comm in self._rows():
            kids.setdefault(ppid, []).append(pid)
            parent[pid] = ppid
            rows.append((pid, rss, comm))

        mine, stack = set(), [self.root]
        while stack:
            for kid in kids.get(stack.pop(), []):
                if kid not in mine:
                    mine.add(kid)
                    stack.append(kid)

        # ffmpeg, запущенный другим ffmpeg, — та же работа: обёртки choco и scoop (shim) на
        # Windows запускают настоящий ffmpeg своим ребёнком. Два ffmpeg рядом — это два.
        ffmpeg = {pid for pid, _rss, comm in rows if pid in mine and "ffmpeg" in comm}
        total = procs = 0
        for pid, rss, _comm in rows:
            if pid in ffmpeg:
                total += rss
                procs += parent.get(pid) not in ffmpeg
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
    return subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace").stdout.strip()


def source_codec() -> list:
    """Кодек синтетических исходников: тот же, что у сборки на этой машине."""
    import host
    encoder = host.video_encoder("auto", ffmpeg_bin())
    return (["-c:v", encoder, "-b:v", "8M"] if encoder != "libx264"
            else ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-threads", str(host.encoder_threads())])


def make_source(path: Path, seconds: float, fps: int):
    """Синтетический вертикальный клип со звуком — свои видео для теста не нужны."""
    subprocess.run([
        ffmpeg_bin(), "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc2=size=1080x1920:rate={fps}:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        *source_codec(), "-pix_fmt", "yuv420p",
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
        *source_codec(), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest",
        str(path),
    ], check=True, capture_output=True)


def loudness_of(path: Path) -> float | None:
    """Интегральная громкость готового файла в LUFS."""
    out = subprocess.run([
        ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path),
        "-af", "ebur128", "-f", "null", "-",
    ], capture_output=True, encoding="utf-8", errors="replace").stderr
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
    ], capture_output=True, encoding="utf-8", errors="replace")
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
    ], capture_output=True, encoding="utf-8", errors="replace").stdout
    values = [float(v) for v in re.findall(r"YAVG=([\d.]+)", out)]
    return sum(values) / len(values) if values else float("nan")


def check_hdr(report: Report, preset: dict, tmp: Path):
    """HDR с айфона (HLG, BT.2020) выходит в обычном цвете, а не бледной пастелью.

    12.10.2026 пришёл первый HDR-дубль (IMG_1803, 4K HLG). Перевода в конвейере не было:
    ffmpeg принимал HLG за обычный BT.709 — лицо бледно-серое, цвета выцветшие, и заметили бы
    это уже после публикации. Проверка: цветные полосы размечаются в HLG так, как пишет айфон
    (обычный белый — 203 нита), и проходят настоящую нарезку. Цвета должны вернуться. Замер
    12.10 при npl=180 (уровень лица как в серии): с переводом насыщенность 62% от исходной и
    отклонение 49, без перевода 43% и 72 — пороги посередине, с запасом в обе стороны.
    """
    from render import render

    print("\nHDR-исходник")
    sdr, hlg, out = tmp / "hdr_sdr.mp4", tmp / "hdr_hlg.mov", tmp / "hdr_out.mp4"
    make_source(sdr, 1.0, 30)
    subprocess.run([ffmpeg_bin(), "-y", "-loglevel", "error", "-i", str(sdr), "-vf",
                    "zscale=tin=bt709:min=bt709:pin=bt709:rin=tv:t=arib-std-b67:m=bt2020nc:p=bt2020:r=tv:npl=203,"
                    "format=yuv422p10le", "-c:v", "prores_ks", "-profile:v", "3",
                    "-color_trc", "arib-std-b67", "-color_primaries", "bt2020", "-colorspace", "bt2020nc",
                    "-color_range", "tv", "-c:a", "copy", str(hlg)], check=True, capture_output=True)
    # грейд стиля выключен: сравнивается только перевод цвета
    render(hlg, out, snap_segments([(0.0, 0.9)], 30), {**preset, "look": {"enabled": False}})

    def rgb(path: Path) -> np.ndarray:
        raw = subprocess.run([ffmpeg_bin(), "-v", "error", "-ss", "0.5", "-i", str(path), "-frames:v", "1",
                              "-vf", "scale=270:480", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.uint8).reshape(480, 270, 3).astype(float)

    original, result = rgb(sdr), rgb(out)
    saturation = (result.max(axis=2) - result.min(axis=2)).mean() / (original.max(axis=2) - original.min(axis=2)).mean()
    deviation = np.abs(original - result).mean()
    tags = probe_value(out, "stream=color_transfer,color_primaries", "v:0")
    report.check(saturation >= 0.52 and deviation < 61 and tags == "bt709,bt709",
                 "HDR с айфона (HLG) выходит в обычном цвете, а не бледной пастелью",
                 f"насыщенность {saturation:.0%} от исходной, отклонение {deviation:.0f}, цвет на выходе {tags}")


def check_face_exposure(report: Report, tmp: Path):
    """Засвет лица ловится в готовом ролике (verify_render).

    IMG_1803 v2: лицо на 171 при норме серии 150–152 — Валера: «засвечено лицо» (12.10.2026).
    Настоящее лицо (снимок NASA, общественное достояние — presets/test) в двух экспозициях:
    как в серии — проходит, засвеченное — нет.
    """
    import verify_render

    print("\nЗасвет лица")
    face = ROOT / "presets" / "test" / "face_pd.jpg"
    results = {}
    for label, gain in (("как в серии", 0.9), ("засвечено", 1.15)):
        clip = tmp / f"face_{gain}.mp4"
        subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-loop", "1", "-i", str(face), "-t", "2", "-r", "30", "-vf",
                        f"scale=1080:-2,pad=1080:1920:0:(oh-ih)/2:black,format=yuv420p,"
                        f"lutyuv=y=clip(16+(val-16)*{gain}\\,16\\,235)", *source_codec(), str(clip)],
                       check=True, capture_output=True)
        results[label] = verify_render.face_brightness(clip, 2.0, frames=3)
    normal, bright = results["как в серии"], results["засвечено"]
    passes = lambda r: r[2] > 0 and r[0] <= verify_render.FACE_MAX_Y and r[1] <= verify_render.FACE_MAX_HOT
    report.check(passes(normal) and not passes(bright),
                 "лицо как в серии проходит, засвеченное — нет",
                 f"как в серии {normal[0]}, засвечено {bright[0]} при пороге {verify_render.FACE_MAX_Y:g}")


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


def section(report: Report, check, *args):
    """Раздел, упавший исключением, — это ✗ с причиной, а остальные разделы всё равно идут.

    Первый прогон на Windows (11.10.2026) оборвался на «Обработке голоса», и треть проверок
    так и не запустилась: что с ними, стало бы видно только на следующем круге.
    """
    try:
        check(report, *args)
    except (Exception, SystemExit) as e:
        traceback.print_exc()
        report.check(False, f"раздел {check.__name__} оборвался исключением", f"{type(e).__name__}: {e}"[:200])


def check_ffmpeg_options(report: Report):
    """Опций, которые сам ffmpeg называет устаревшими, в конвейере нет.

    Устаревшее сегодня убирают в следующей версии. -filter_complex_script в ffmpeg 8 работал,
    а предупреждение глушил -loglevel error; в 9.0, который на Windows ставят winget и choco,
    опции уже нет — первый прогон на Windows (11.10.2026) упал на финальной сборке.
    """
    print("\nОпции ffmpeg")
    help_text = subprocess.run([ffmpeg_bin(), "-hide_banner", "-h", "full"], capture_output=True,
                               encoding="utf-8", errors="replace").stdout
    deprecated = {m.group(1) for m in re.finditer(r"^(-\w+)\S*\s.*\bdeprecated\b", help_text, re.M)}
    used = sorted({f"{opt} в {path.name}" for path in Path(__file__).resolve().parent.glob("*.py")
                   if path.name != "selfcheck.py"
                   for opt in deprecated
                   if re.search(rf"[\"']{re.escape(opt)}[\"']", path.read_text(encoding="utf-8"))})
    report.check(not used, "конвейер не пользуется опциями, которые ffmpeg называет устаревшими",
                 "; ".join(used) or f"чисто; устаревших в этом ffmpeg: {len(deprecated)}")


def check_skill_links(report: Report, tmp: Path):
    """Заглушка git на месте ссылки на скилл превращается в ссылку.

    Git на Windows ставится без права на symlink и кладёт вместо .claude/skills/<имя> текстовый
    файл с путём — Claude такого скилла не видит. host.link_skills (установщик и старт студии)
    делает настоящую ссылку; порванную — тоже; папку-копию не трогает.
    """
    import host

    print("\nСкиллы на Windows")
    root = tmp / "skills_root"
    for name in ("a", "b", "c"):
        (root / ".agents/skills" / name).mkdir(parents=True)
        (root / ".agents/skills" / name / "SKILL.md").write_text(f"---\nname: {name}\n", encoding="utf-8")
    links = root / ".claude/skills"
    links.mkdir(parents=True)
    (links / "a").write_text("../../.agents/skills/a", encoding="utf-8")    # так git кладёт ссылку на Windows
    if not host.IS_WINDOWS:                    # symlink на Windows без прав не создать
        (links / "b").symlink_to(root / "нет-такой")                     # порванная ссылка
    (links / "c").mkdir()
    (links / "c" / "SKILL.md").write_text("копия", encoding="utf-8")
    try:
        fixed = host.link_skills(root)
        again = host.link_skills(root)
    except OSError as e:
        fixed, again = [f"ошибка: {e}"], []
    linked = all((links / n).exists() and (links / n).resolve() == (root / ".agents/skills" / n).resolve()
                 for n in (["a"] if host.IS_WINDOWS else ["a", "b"]))
    report.check(linked and not again, "заглушка git на месте ссылки на скилл становится ссылкой, повтор ничего не меняет",
                 ", ".join(fixed) or "ничего не починено")
    report.check((links / "c" / "SKILL.md").read_text(encoding="utf-8") == "копия",
                 "папку-копию скилла починка не удаляет (её ловит проверка «скиллы общие»)")


def check_sfx(report: Report):
    """Звуки — по правилам Валеры (12.10.2026): тише голоса, без убранных, без копий, без повторов подряд.

    В IMG_1803 басовый удар звучал громче голоса (общая громкость 0.36 на файл, записанный на −2 LUFS),
    а «чередование» whoosh и whoosh-short давало один и тот же свист шесть раз: файлы были копиями.
    """
    import hashlib
    import kit
    from verify_page import sound_problems

    print("\nЗвуки")
    folder = kit.SFX_DIR
    files = sorted(folder.glob("*.mp3"))
    digests = {}
    for f in files:
        digests.setdefault(hashlib.md5(f.read_bytes()).hexdigest(), []).append(f.stem)
    twins = [" = ".join(names) for names in digests.values() if len(names) > 1]
    report.check(not twins, "в presets/sfx нет одинаковых файлов под разными именами", "; ".join(twins) or "чисто")

    manifest = kit.sfx_manifest()
    off = []
    for f in files:
        info = manifest.get(f.stem)
        err = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(f), "-af", "apad=pad_dur=1,ebur128",
                              "-f", "null", "-"], capture_output=True, encoding="utf-8", errors="replace").stderr
        measured = max(float(x) for x in re.findall(r"M:\s*(-?[\d.]+)", err))
        if not info or "loudness_m" not in info or abs(info["loudness_m"] - measured) > 1.5:
            off.append(f"{f.stem}: в манифесте {info.get('loudness_m') if info else '—'}, замер {measured:.1f}")
    report.check(not off, "у каждого звука в манифесте честный замер громкости", "; ".join(off) or f"{len(files)} файлов")

    removed = manifest.get("_removed", {})
    leftovers = [n for n in removed if (folder / f"{n}.mp3").exists()]
    try:
        kit.audio("x", "glitch-1", 1.0)
        refused = False
    except ValueError as e:
        refused = "больше нет" in str(e)
    report.check("glitch-1" in removed and refused and not leftovers,
                 "убранный звук (glitch-1 с «бардака») не вернётся: файла нет, kit отказывает с причиной",
                 ", ".join(leftovers) or "чисто")

    def effective(tag: str) -> float:
        name, vol = re.search(r'sfx/([\w.\-]+)\.mp3".*data-volume="([\d.]+)"', tag).groups()
        return manifest[name]["loudness_m"] + 20 * np.log10(float(vol))

    levels = {n: effective(kit.audio("x", n, 1.0)) for n in ("impact-bass-2", "whoosh", "pop")}
    try:
        kit.audio("x", "pop", 1.0, level=1.5)
        louder = True
    except ValueError:
        louder = False
    report.check(all(abs(v - kit.SFX_TARGET) <= 0.5 for v in levels.values()) and not louder,
                 "громкость звука — от замера файла: удар и щелчок на одной норме, громче нормы нельзя",
                 ", ".join(f"{n} {v:.1f}" for n, v in levels.items()) + f" LUFS при норме {kit.SFX_TARGET:g}")

    def refused_by_rules(sounds: list) -> bool:
        try:
            kit.check_sounds(sounds)
            return False
        except ValueError:
            return True

    ok_seq = [kit.audio("a", "impact-bass-1", 1.0), kit.audio("b", "whoosh", 3.0), kit.audio("c", "impact-bass-2", 5.0)]
    report.check(not refused_by_rules(ok_seq)
                 and refused_by_rules([kit.audio("a", "whoosh", 1.0), kit.audio("b", "whoosh-cinematic", 3.0)])
                 and refused_by_rules([kit.audio(f"p{i}", n, 1.0 + 2 * i) for i, n in enumerate(["pop", "ping", "pop", "click", "pop"])])
                 and refused_by_rules([kit.audio("a", "pop", 1.0), kit.audio("b", "ping", 1.4)]),
                 "одинаковое семейство подряд, файл трижды и звуки вплотную — ошибка сборки")
    loud = '<audio id="sfx-x" src="assets/sfx/impact-bass-1.mp3" data-start="1.00" data-volume="0.36"></audio>'
    report.check(bool(sound_problems(loud)) and not sound_problems("".join(ok_seq)),
                 "проверка страницы ловит звук громче нормы (удар 0.36 из старых роликов)")


def check_gen_image(report: Report, tmp: Path):
    """Фон через Codex (gen_image.py, 12.10.2026): правила в запросе, отбор картинки, подхват результата.

    Сам Codex не зовётся — самопроверка не тратит лимит ChatGPT и не зависит от сети. Проверяется
    то, что ломалось бы тихо: Codex то копирует картинку по просьбе, то только называет свой путь
    (второй же пробный запуск) — скрипт берёт свежую из generated_images, но не старую чужую.
    """
    import gen_image

    print("\nФон через Codex")
    prompt = gen_image.build_prompt("ворота Иштар", ROOT / "work" / "X" / "downloads" / "bg.png")
    rules_in = all(w in prompt for w in ("без людей", "без надписей", "9:16", "work/X/downloads/bg.png"))
    pics = {}
    for name, size in (("vertical", "941x1672"), ("landscape", "1672x941"), ("tiny", "300x533")):
        pics[name] = tmp / f"gen_{name}.png"
        subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=navy:s={size}",
                        "-frames:v", "1", str(pics[name])], check=True, capture_output=True)
    picked = [gen_image.check_image(pics[n])[0] for n in ("vertical", "landscape", "tiny")]
    report.check(rules_in and picked == [True, False, False],
                 "запрос несёт правила (без людей, без надписей, вертикаль), годится только вертикаль от 720 px",
                 f"правила {'на месте' if rules_in else 'потеряны'}, отбор {picked}")

    folder = tmp / "generated_images" / "thread"
    folder.mkdir(parents=True)
    old, fresh = folder / "old.png", folder / "fresh.png"
    shutil.copy2(pics["landscape"], old)
    os.utime(old, (time.time() - 3600, time.time() - 3600))       # чужая картинка часовой давности
    started = time.time()
    shutil.copy2(pics["vertical"], fresh)
    out = tmp / "bg.png"
    got = gen_image.collect(out, started, folder)
    stale_out = tmp / "bg_stale.png"
    stale = gen_image.collect(stale_out, time.time() + 60, folder)   # за этот запуск ничего нового
    report.check(got and gen_image.check_image(out)[0] and not stale,
                 "если Codex только назвал свой путь — берётся его свежая картинка, старая чужая — нет",
                 "свежая взята" if got else "свежая не найдена")

    # под кадр: imagegen отдаёт 941×1672, кадр 1080×1920 и наезд — без запаса браузер тянул её в мыло
    size = gen_image.refit(out)
    original = out.with_suffix(".codex.png")
    fitted = subprocess.run([ffprobe_bin(), "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                             str(out)], capture_output=True, encoding="utf-8").stdout.strip()
    width, height = (int(x) for x in fitted.split(",")[:2])
    report.check(width >= 1080 * 1.08 and height >= 1920 * 1.08 and original.exists()
                 and gen_image.check_image(original)[1].startswith("941×1672"),
                 "фон готовится под кадр с запасом под наезд, оригинал Codex остаётся рядом",
                 f"под кадр {size}, оригинал {'на месте' if original.exists() else 'потерян'}")

    # повторная генерация (--force): рядом лежат прежние bg.png и bg.codex.png (синие, час назад), Codex
    # отдал новую (бордовую) только к себе в generated_images. Новой и быть под кадр — прежняя по пути
    # засчитывалась как свежая, а под кадр шёл прежний оригинал: «перегенерировал», а фон тот же
    again = tmp / "again"
    (again / "generated_images").mkdir(parents=True)
    redo = again / "bg.png"
    shutil.copy2(pics["vertical"], redo)
    gen_image.refit(redo)
    for path in (redo, redo.with_suffix(".codex.png")):
        os.utime(path, (time.time() - 3600, time.time() - 3600))
    started = time.time()
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=maroon:s=941x1672",
                    "-frames:v", "1", str(again / "generated_images" / "new.png")], check=True, capture_output=True)
    took = gen_image.collect(redo, started, again / "generated_images")
    gen_image.refit(redo, fresh=True)
    pixel = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(redo), "-vf", "scale=1:1",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    report.check(took and len(pixel) == 3 and pixel[0] > pixel[2],
                 "повторная генерация (--force) ставит под кадр новую картинку, а не прежнюю",
                 "новая" if len(pixel) == 3 and pixel[0] > pixel[2] else "осталась прежняя")


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


def check_grey_zones(report: Report, tmp: Path):
    """Текст не заезжает в серые зоны площадок: шапку, ник и подпись, кнопки справа (12.10.2026).

    Валера: «текстом туда как можно меньше, центрирование — по всему экрану, как было; иногда можно
    заехать, если надо». Проверка меряет сами строки текста в том же Chrome, что и рендер: слово по
    центру — не заезд, крупное слово в шапке и надпись под кнопками — заезд, помеченное data-safe —
    осознанный заезд, отдельным списком.
    """
    import formats
    from kit import build_page
    from verify_page import run_timeline

    print("\nСерые зоны площадок")
    project = tmp / "zones"
    (project / "assets").mkdir(parents=True)
    shutil.copy2(ROOT / "studio" / "_vendor" / "gsap.min.js", project / "assets" / "gsap.min.js")
    (project / "camera.js").write_text("window.CAMERA_FPS = 30;\nwindow.CAMERA = [[0, 0, 1], [0, 0, 1]];\n")
    caps = [{"t0": 0.2, "t1": 1.8, "text": "по центру", "accent": False}]
    (project / "captions.js").write_text("window.CAPTIONS = " + json.dumps(caps, ensure_ascii=False) + ";\n",
                                         encoding="utf-8")
    behind = '        <div id="z-top" class="g big" style="top: 40px; font-size: 200px;">шапка</div>'
    front = ('        <div id="z-right" class="g lead" style="top: 1000px; left: 600px; width: 460px;'
             ' text-align: right; font-size: 60px;">кнопки</div>\n'
             # рамка .lead — во всю ширину и на высоте кнопок, а само слово — по центру: не заезд
             '        <div id="z-ok" class="g lead" style="top: 1000px;">центр</div>\n'
             '        <div id="z-safe" class="g lead" data-safe="стрелка на ник — намеренно"'
             ' style="top: 1700px;">ник</div>')
    beats = "".join(f'      tl.set("#{i}", {{ opacity: 1 }}, 0.2);\n' for i in ("z-top", "z-right", "z-ok", "z-safe"))
    (project / "index.html").write_text(build_page("зоны", 2.0, behind, front, beats, [], [], cta_at=5.0),
                                        encoding="utf-8")
    res = run_timeline(project / "index.html", zones=formats.grey_zones("9:16"))
    grey = {(g["el"], g["zone"].split(":")[0]) for g in res.get("grey", [])}
    allowed = {g["el"] for g in res.get("greyAllowed", [])}
    flagged = {el for el, _ in grey}
    report.check(("#z-top", "верх") in grey and ("#z-right", "справа") in grey
                 and not flagged & {"#z-ok", "#z-safe"} and not any(el.startswith("субтитр") for el in flagged),
                 "текст в шапке и под кнопками ловится, текст по центру — нет",
                 ", ".join(sorted(f"{el} ({z})" for el, z in grey)) or "ничего не поймано")
    report.check("#z-safe" in allowed, "осознанный заезд (data-safe) идёт отдельным списком, а не ошибкой",
                 ", ".join(sorted(allowed)) or "не найден")

    # лицо: карточка поверх лица — ошибка (Валера, 12.10.2026: «карточки никогда не должны перекрывать
    # лицо»); та же карточка ниже подбородка и субтитр — нет. Лицо — как его даёт слежение с камерой.
    front2 = ('        <div id="f-over" class="g doc" style="left: 245px; top: 950px; width: 590px; height: 200px;">на лице</div>\n'
              '        <div id="f-below" class="g doc" style="left: 245px; top: 1250px; width: 590px; height: 200px;">ниже</div>')
    beats2 = "".join(f'      tl.set("#{i}", {{ opacity: 1 }}, 0.2);\n' for i in ("f-over", "f-below"))
    (project / "index.html").write_text(build_page("лицо", 2.0, "", front2, beats2, [], [], cta_at=5.0), encoding="utf-8")
    face = [(round(0.25 * k, 2), 360.0, 600.0, 740.0, 1100.0) for k in range(8)]   # подбородок на 1100
    res = run_timeline(project / "index.html", faces=face)
    hit = {h["el"] for h in res.get("faceHits", [])}
    report.check(hit == {"#f-over"}, "карточка поверх лица ловится, ниже подбородка — нет (лицо по кадрам)",
                 ", ".join(sorted(hit)) or "ничего не поймано")
    # вариант для A/B (studio/<имя>--<стиль>/) собран из того же дубля: лицо — из его work/<имя>/. Искалось
    # в work/<имя>--<стиль>/, не находилось — и проверка лица у вариантов молча не делалась
    from verify_page import take_dir
    variant = take_dir(Path("studio") / "IMG_3305--lofi-ugc")
    report.check(variant.name == "IMG_3305", "у варианта для A/B лицо берётся из его дубля, проверка не пропускается",
                 f"studio/IMG_3305--lofi-ugc → work/{variant.name}")

    # фон за спиной: наплыв из размытия — можно, а остаться мыльным на весь показ — нет (IMG_1803 v4
    # держал blur(2px), Валера: «фоны низкокачественные какие-то»)
    (project / "assets" / "img").mkdir(exist_ok=True)
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1188x2112", "-frames:v", "1",
                    str(project / "assets" / "img" / "room.png")], check=True, capture_output=True)
    css = ".bgt { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; opacity: 0; }\n" \
          ".bgt img { width: 1080px; height: 1920px; object-fit: cover; }\n"
    behind3 = "\n".join(f'        <div id="{i}" class="bgt"{extra}><img src="assets/img/room.png" alt="" /></div>'
                        for i, extra in (("bg-soft", ""), ("bg-sharp", ""), ("bg-meant", ' data-safe="туман — замысел"')))
    beats3 = "".join(f'      tl.fromTo("#{i}", {{ opacity: 0, filter: "blur(14px)" }}, {{ opacity: 1, filter: "blur({end}px)", '
                     f'duration: 0.5 }}, 0.2);\n' for i, end in (("bg-soft", 2), ("bg-sharp", 0), ("bg-meant", 3)))
    (project / "index.html").write_text(build_page("фон", 2.5, behind3, "", beats3, [], [], cta_at=5.0, extra_css=css),
                                        encoding="utf-8")
    res = run_timeline(project / "index.html")
    soft = {b["el"]: b.get("allowed") for b in res.get("softBg", [])}
    report.check(set(soft) == {"#bg-soft", "#bg-meant"} and soft["#bg-meant"] and not soft["#bg-soft"],
                 "фон, оставшийся размытым на показе, ловится; наплыв из размытия — нет; data-safe — отдельно",
                 ", ".join(f"{k}{' (осознанно)' if v else ''}" for k, v in sorted(soft.items())) or "ничего не поймано")


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
        # пик памяти процесса: psutil на любой системе (на Mac ещё и resource — для сверки)
        probe_code = (
            "import sys; sys.path.insert(0, 'scripts');"
            "from track import detect_faces;"
            f"faces = detect_faces(__import__('pathlib').Path(r'{clip}'));"
            "import psutil; m = psutil.Process().memory_info();"
            "peak = getattr(m, 'peak_wset', 0) or __import__('resource').getrusage(0).ru_maxrss;"
            "print(len(faces['frames']), peak)")
        result = subprocess.run([sys.executable, "-c", probe_code], capture_output=True,
                                encoding="utf-8", errors="replace", cwd=Path(__file__).resolve().parent.parent)
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


def check_matte_memory(report: Report, tmp: Path):
    """Маска человека держит память постоянной, сколько бы ни было кадров (MediaPipe)."""
    print("\nПамять при вырезке человека")
    peaks = {}
    for seconds in (2, 12):
        clip = tmp / f"matte_{seconds}s.mp4"
        make_source(clip, seconds, 30)
        probe_code = (
            "import sys; sys.path.insert(0, 'scripts');"
            "from matte import run_matte;"
            f"stats = run_matte(__import__('pathlib').Path(r'{clip}'), 'mediapipe', __import__('pathlib').Path(r'{clip}.mkv'));"
            "import psutil; m = psutil.Process().memory_info();"
            "peak = getattr(m, 'peak_wset', 0) or __import__('resource').getrusage(0).ru_maxrss;"
            "print(stats['frames'], peak)")
        result = subprocess.run([sys.executable, "-c", probe_code], capture_output=True, encoding="utf-8",
                                errors="replace", cwd=ROOT)
        try:
            frames, rss = result.stdout.split()[-2:]
            peaks[seconds] = (int(frames), int(rss) / 1048576)
        except ValueError:
            peaks[seconds] = (0, float("nan"))
            print(f"    {result.stderr.strip()[-300:]}")
    (n_short, short), (n_long, long_) = peaks[2], peaks[12]
    report.check(n_long > n_short > 0 and long_ - short < 150, "маска не копит кадры в памяти",
                 f"{n_short} кадров — {short:.0f} МБ, {n_long} кадров — {long_:.0f} МБ")


def check_cutout(report: Report, tmp: Path):
    """Вырезка держит вещь в руке целиком, режет край по пустой комнате и не несёт старый фон в край.

    IMG_1803 (12.10.2026): модель считала банку в руке скорее фоном (0,59 против 0,30 у «прочего») —
    верх банки таял, сквозь него светила свеча с нового фона; в человека попадали полосы старой
    комнаты, а край нёс её серую дымку. Валера: «вырезка фона хуево работает», «рука и банка — не
    лишние». Здесь всё на рисованном кадре половинного размера, как его видит matte.py, без модели:
    проверяется логика, которая это чинит. Потом — настоящее прозрачное видео из короткого клипа.
    """
    import cv2
    import matte

    print("\nВырезка человека")
    h, w = 960, 540
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    body = ((xx - 300) / 150) ** 2 + ((yy - 640) / 330) ** 2
    hand = (xx >= 120) & (xx < 175) & (yy >= 420) & (yy < 480)
    can = (xx >= 40) & (xx < 125) & (yy >= 330) & (yy < 520)            # банка у руки, модель в ней не уверена
    person = np.full((h, w), 0.03, np.float32)
    person[body <= 1] = 0.95
    person[(body > 1) & (body <= 1.05)] = 0.42                          # дымка по контуру — тонкая полоса
    person[hand] = 0.95
    person[can] = 0.41
    far = (xx >= 420) & (yy < 120)                                      # неуверенное пятно вдали — не вещь в руке
    person[far] = 0.41

    can_in_mask = cv2.erode(can.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0   # край банки ведёт кадр
    alpha = matte.model_alpha(person)
    can_in, ring = float(alpha[can_in_mask].min()), float(alpha[(body > 1.01) & (body <= 1.04) & ~can & ~hand].max())
    report.check(can_in >= 0.9 and ring <= 0.5 and float(alpha[far].max()) <= 0.2,
                 "вещь в руке остаётся целиком, дымка по контуру и пятно вдали — нет",
                 f"банка ≥ {can_in:.2f}, дымка ≤ {ring:.2f}, пятно вдали ≤ {float(alpha[far].max()):.2f}")

    # пустая комната: складки занавеса; в кадре — пиджак, рука, красная банка; слева от человека модель
    # ошибочно взяла полосу комнаты (как красные полосы IMG_1803), справа вверху — блик вдали от человека
    room = np.dstack([0.32 + 0.08 * np.sin(xx / 9.0)] * 3).astype(np.float32)
    frame = room.copy()
    frame[body <= 1] = (0.10, 0.10, 0.12)
    frame[hand] = (0.80, 0.60, 0.50)
    frame[can] = (0.80, 0.12, 0.12)
    flicker = (xx >= 380) & (yy >= 150) & (yy < 230)
    frame[flicker] = (0.9, 0.9, 0.9)
    strip = (body > 1.0) & (xx < 300) & (yy > 700) & (np.sqrt(body) <= 1.0 + 12 / 330)
    person_fp = person.copy()
    person_fp[strip] = 0.8
    person_fp[far] = 0.03
    known = (body > 1.0).astype(np.float32)                             # за спиной комнату не видно
    plate = matte.Plate(room, np.full_like(room, 2 / 255), cv2.GaussianBlur(known, (0, 0), 3))
    alpha = matte.hybrid_alpha(person_fp, frame, plate)
    got = {"банка": float(alpha[can_in_mask].min()),
           "полоса комнаты": float(alpha[strip & (plate.weight >= 0.95)].max()),
           "блик вдали": float(alpha[flicker].max()), "середина": float(alpha[body <= 0.8].min())}
    report.check(got["банка"] >= 0.9 and got["полоса комнаты"] <= 0.1 and got["блик вдали"] <= 0.05
                 and got["середина"] >= 0.95,
                 "край режется по пустой комнате: банка — человек, полоса комнаты и блик вдали — нет",
                 ", ".join(f"{k} {v:.2f}" for k, v in got.items()))

    # толчок штатива: половина выборки сдвинута на 6 точек — по такой «комнате» край резать нельзя
    rng = np.random.default_rng(7)
    # занавес со складками слева и ровная стена справа — как в настоящей комнате, где есть и узор, и гладь
    folds = np.dstack([0.32 + np.where(xx < 330, 0.15 * np.sin(xx / 9.0), 0.0)] * 3).astype(np.float32)
    frames, sure = [], []
    for i in range(12):
        shot = folds + rng.normal(0, 1.5 / 255, room.shape).astype(np.float32)
        shot[:, 100 + 20 * i:240 + 20 * i] = 0.1                       # человек ходит по кадру
        frames.append((np.clip(shot, 0, 1) * 255).astype(np.uint8))
        mask = np.ones((h, w), bool)
        mask[:, 90 + 20 * i:250 + 20 * i] = False
        sure.append(mask)
    still, still_note = matte.build_plate(np.stack(frames), np.stack(sure))
    moved_frames = [np.roll(f, 6, axis=1) if i % 2 else f for i, f in enumerate(frames)]
    moved, moved_note = matte.build_plate(np.stack(moved_frames), np.stack(sure))
    error = np.abs(still.image - folds)[still.weight > 0.9] if still is not None else np.ones(1)
    exact = float(np.percentile(error, 99)) <= 3 / 255 and float(error.max()) <= 8 / 255   # медиана 4–12 шумных кадров
    report.check(exact and moved is None and "камера" in moved_note,
                 "пустая комната собирается со стоящей камеры и не собирается с двигавшейся",
                 f"стоит: {still_note}; двигалась: {moved_note}")

    # край на месте не «кипит», а за движущейся рукой не тянется шлейф
    still_img = np.dstack([0.3 + 0.1 * np.sin(xx / 7.0)] * 3).astype(np.float32)
    moved_img = still_img.copy()
    moved_img[:, :270] += 0.2                                           # левая половина сменилась: рука прошла
    last = (still_img, np.full((h, w), 0.4, np.float32))
    calmed = matte.calm(np.full((h, w), 0.6, np.float32), moved_img, last)
    report.check(abs(float(calmed[:, 300:].mean()) - 0.5) < 0.01 and abs(float(calmed[:, :250].mean()) - 0.6) < 0.01,
                 "край на неподвижном не дрожит, за движением не тянется шлейф",
                 f"на месте {float(calmed[:, 300:].mean()):.2f} (кадр 0.6, прошлый 0.4), "
                 f"где картинка сменилась {float(calmed[:, :250].mean()):.2f}")

    # цвет края: старый фон светлый (200), человек тёмный (40), новый фон тёмный (16)
    ramp = np.clip((np.arange(w, dtype=np.float32) - 200) / 40, 0, 1)
    edge_alpha = np.tile(1.0 - ramp, (64, 1))
    plane = np.round(edge_alpha * 40 + (1 - edge_alpha) * 200).astype(np.uint8)
    clean = matte.foreground_plane(plane, edge_alpha, 41).astype(np.float32)
    ideal = edge_alpha * 40 + (1 - edge_alpha) * 16
    halo = float((edge_alpha * clean + (1 - edge_alpha) * 16 - ideal).max())
    raw = float((edge_alpha * plane + (1 - edge_alpha) * 16 - ideal).max())
    solid_same = bool(np.array_equal(clean[edge_alpha >= 0.999], plane[edge_alpha >= 0.999]))
    report.check(halo <= 6 and solid_same,
                 "край без ореола старого фона, сплошной человек — байт в байт",
                 f"лишняя яркость края на тёмном фоне {halo:.1f} (без чистки было бы {raw:.0f})")


def check_cutout_video(report: Report, tmp: Path):
    """Прозрачное видео человека целое: альфа, длина и цвет как у дубля; чужая маска — громкий отказ.

    Вырезку теперь собирает питон (чистит цвет края) и отдаёт кодеку сырые плоскости — значит, длину,
    метки цвета и прозрачность больше не гарантирует один вызов ffmpeg, их надо стеречь.
    """
    import matte

    print("\nПрозрачное видео человека")
    src, mask = tmp / "cutout_src.mp4", tmp / "cutout_mask.mkv"
    make_source(src, 1.0, 30)
    for path, seconds in ((mask, 1.0), (tmp / "cutout_short.mkv", 0.5)):
        subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"color=black:s=1080x1920:r=30:d={seconds},format=gray,"
                        "geq=lum='if(lt(hypot(X-540\\,Y-900)\\,380)\\,255\\,0)'",
                        "-c:v", "ffv1", "-pix_fmt", "gray", str(path)], check=True, capture_output=True)
    out = matte.make_cutout(src, mask, tmp / "cutout.webm")
    meta = subprocess.run([ffprobe_bin(), "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                           "stream=codec_name,nb_read_frames,color_space:stream_tags=alpha_mode", "-of", "json", str(out)],
                          capture_output=True, encoding="utf-8").stdout
    stream = json.loads(meta)["streams"][0]
    try:
        matte.make_cutout(src, tmp / "cutout_short.mkv", tmp / "cutout_bad.webm")
        refused = False
    except RuntimeError:
        refused = True
    leftovers = sorted(p.name for p in tmp.glob(".cutout*"))
    report.check(stream.get("codec_name") == "vp9" and stream.get("tags", {}).get("alpha_mode") == "1"
                 and stream.get("nb_read_frames") == "30" and stream.get("color_space") == "bt709"
                 and refused and not (tmp / "cutout_bad.webm").exists() and not leftovers,
                 "прозрачное видео целое: альфа, 30 кадров из 30, цвет bt709; чужая маска — отказ",
                 f"{stream.get('codec_name')}, альфа {stream.get('tags', {}).get('alpha_mode')}, "
                 f"кадров {stream.get('nb_read_frames')}, {stream.get('color_space')}; короткая маска — "
                 f"{'отказ' if refused else 'приняли'}, хвосты: {', '.join(leftovers) or 'нет'}")


def check_portable(report: Report, tmp: Path):
    """Проект один на Mac и Windows: ни одного закрытого маковского модуля, очередь без bash.

    До 11.10.2026 лица, маска и текст в кадре шли через Apple Vision (только Mac, закрытый),
    а задача очереди была скриптом bash — на Windows не работало ничего из этого.
    """
    import jobqueue

    print("\nMac и Windows")
    mac_only = re.compile(r"^\s*(import|from)\s+(Vision|Quartz|objc|AppKit|Foundation)\b|h264_videotoolbox\"|\"open\", \"-R\"",
                          re.MULTILINE)
    offenders = sorted(p.name for p in (ROOT / "scripts").glob("*.py")
                       if p.name not in ("host.py", "selfcheck.py") and mac_only.search(p.read_text(encoding="utf-8")))
    report.check(not offenders, "в конвейере нет закрытых маковских модулей и жёсткого маковского кодека",
                 ", ".join(offenders) or "чисто")

    queue = tmp / "portable_queue"
    marker, leftover = tmp / "step2.txt", ROOT / "work" / f".selfcheck_cleanup_{os.getpid()}.json"
    leftover.write_text("{}", encoding="utf-8")
    ok_job = jobqueue.write_job("10-selfcheck-ok", [
        ["python", "-c", "print('шаг 1 ✓')"],
        ["python", "-c", f"open(r'{marker}', 'w').write('ok')"],
    ], cleanup=[leftover.relative_to(ROOT).as_posix()], queue=queue)
    bad_job = jobqueue.write_job("10-selfcheck-bad", [
        ["python", "-c", "raise SystemExit(3)"],
        ["python", "-c", f"open(r'{tmp / 'never.txt'}', 'w').write('x')"],
    ], queue=queue)
    with open(tmp / "portable.log", "w", encoding="utf-8") as log:
        code_ok = jobqueue.run_job(ok_job, log)
        code_bad = jobqueue.run_job(bad_job, log)
    log_text = (tmp / "portable.log").read_text(encoding="utf-8")
    report.check(code_ok == 0 and marker.exists() and "шаг 1 ✓" in log_text and not leftover.exists(),
                 "задача очереди — JSON: шаги идут питоном проекта без bash, временное убирается",
                 f"код {code_ok}, временный файл {'убран' if not leftover.exists() else 'остался'}")
    report.check(code_bad == 3 and not (tmp / "never.txt").exists(),
                 "упавший шаг останавливает задачу — следующие не идут", f"код {code_bad}")
    leftover.unlink(missing_ok=True)


def check_batch(report: Report, tmp: Path):
    """Пачка: каждый ролик — в своей новой сессии мозга, а после очереди студия продолжает сама.

    Правило Валеры (11.10.2026): если монтировать всю пачку в одном разговоре, контекст
    кончается и каждый следующий ролик выходит хуже. Здесь вместо агента — подставной скрипт:
    на первый ход он ставит задачу в очередь («ЖДУ ОЧЕРЕДЬ»), на второй — «ГОТОВО».
    """
    from fastapi.testclient import TestClient
    import brain
    import jobqueue
    import studio_api
    from server import TOKEN, app

    print("\nПачка: ролик — своя сессия")
    queue = tmp / "batch_queue"

    def fake_agent(engine, prompt, *args, **kwargs):
        stem = re.search(r"(?:Смонтируй|монтаж) (\S+?)[ .]", prompt).group(1)
        if "Очередь отработала" in prompt:
            text = f"{stem} собран. СТАТУС: ГОТОВО — output/{stem}_v1.mp4"
        else:
            jobqueue.write_job(f"20-prep-{stem}", [["python", "-c", "pass"]], queue=queue)
            text = "Поставил подготовку в очередь. СТАТУС: ЖДУ ОЧЕРЕДЬ"
        event = json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}},
                           ensure_ascii=False)
        return [sys.executable, "-c", f"print({event!r})"]

    def fake_runner():                    # «обработчик»: всё, что ждёт, сразу выполнено
        (queue / "done").mkdir(parents=True, exist_ok=True)
        for job in jobqueue.job_files(queue):
            job.replace(queue / "done" / job.name)
        return True

    saved = (brain.THREADS, brain.command, studio_api.QUEUE, studio_api.ensure_runner)
    brain.THREADS, brain.command = tmp / "batch_threads", fake_agent
    studio_api.QUEUE, studio_api.ensure_runner = queue, fake_runner
    studio_api.batch.update(running=False, items=[])
    items, threads = [], []
    try:
        with TestClient(app, base_url="http://127.0.0.1:8765") as live:
            live.post("/api/brain/batch", json={"stems": ["РОЛИК_А", "РОЛИК_Б"], "engine": "claude"},
                      headers={"X-Studio-Token": TOKEN})
            for _ in range(150):
                time.sleep(0.1)
                if not studio_api.batch["running"]:
                    break
            items = [dict(i) for i in studio_api.batch["items"]]
            threads = [brain.load_thread(i["thread"]) for i in items if i.get("thread")]
    finally:
        brain.THREADS, brain.command, studio_api.QUEUE, studio_api.ensure_runner = saved
        for item in items:
            studio_api.runs.pop(item.get("thread"), None)
        studio_api.batch.update(running=False, items=[])
        (studio_api.WORK_DIR / "_studio" / "batch.json").unlink(missing_ok=True)
    ids = {t["id"] for t in threads}
    resumed = all(sum(m["role"] == "user" for m in t["messages"]) == 2
                  and "Очередь отработала" in t["messages"][2]["text"] for t in threads)
    report.check([i["status"] for i in items] == ["done", "done"] and len(ids) == 2 and resumed
                 and all(t["stem"] == i["stem"] for t, i in zip(threads, items)),
                 "пачка: у каждого ролика своя сессия, после очереди разговор продолжается сам",
                 "; ".join(f"{i['stem']}: {i['status']}" for i in items) or "пачка не прошла")


def check_viz(report: Report, tmp: Path):
    """Визуализации данных: офлайн, по-русски, с входом и выходом, ошибка — до рендера.

    Каталог HyperFrames как есть тянул при рендере GSAP, D3, карту и шрифты из интернета и
    писал «182,000». Формула с опечаткой в LaTeX должна валить проверку страницы, а не
    уезжать в ролик пустым местом.
    """
    import viz
    from kit import build_page
    from verify_page import missing_assets, run_timeline

    print("\nВизуализации данных")
    leaks = []
    for path in (ROOT / "presets" / "viz").rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        leaks += [f"{path.name}: {u}" for u in re.findall(r"https?://[^\"' )>]+", text) if "www.w3.org" not in u]
        if 'toLocaleString("en-US"' in text:
            leaks.append(f"{path.name}: числа по-английски")
    report.check(not leaks, "каталог визуализаций офлайн и по-русски: ни одной ссылки в интернет",
                 "; ".join(leaks[:3]) or f"{len(viz.catalog())} элементов")

    try:
        viz.mount("count-up", "x", at=1, dur=3, values={"конец": 5})
        typo = False
    except ValueError:
        typo = True
    report.check(typo, "опечатка в переменной визуализации — громкая ошибка, а не значение по умолчанию")

    project = tmp / "viz-page"
    (project / "assets").mkdir(parents=True)
    shutil.copy2(ROOT / "studio" / "_vendor" / "gsap.min.js", project / "assets" / "gsap.min.js")
    (project / "camera.js").write_text("window.CAMERA_FPS = 30;\nwindow.CAMERA = [[0, 0, 1], [0, 0, 1]];\n",
                                       encoding="utf-8")
    (project / "captions.js").write_text("window.CAPTIONS = [];\n", encoding="utf-8")
    parts = [viz.mount("count-up", "stat", at=0.3, dur=2.0, values={"end": 182000, "suffix": " ₽"}),
             viz.formula("disc", r"D = b^2 - 4ac", at=1.0, dur=1.6),
             viz.plot("parab", lambda x: x * x - 4, x=(-3, 3), y=(-5, 6), at=1.4, dur=1.8, points=[(-2, 0), (2, 0)])]

    def page(front_parts):
        return build_page("т", 4.0, "", "\n".join(h for h, _ in front_parts), "\n".join(j for _, j in front_parts),
                          [], [], cta_at=9.0, cutout=False)

    good = page(parts)
    gone_before = missing_assets(project, good)
    # как compose: шрифты и звуки страницы, плюс то, что нужно визуализациям
    need = dict(viz.assets_for(good))
    need.update({f"assets/fonts/{f.name}": f for f in (ROOT / "presets" / "fonts").glob("*.ttf")})
    need.update({f"assets/sfx/{f.name}": f for f in (ROOT / "presets" / "sfx").glob("*.mp3")})
    for rel, src in need.items():
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    (project / "assets" / "aroll.mp4").write_bytes(b"")          # дубль compose берёт из work/
    (project / "index.html").write_text(good, encoding="utf-8")
    res = run_timeline(project / "index.html")
    stuck = [i["el"] for i in res.get("stuck", []) + res.get("risky", [])]
    report.check(bool(gone_before) and not missing_assets(project, good),
                 "ассеты визуализаций находятся и подкладываются в проект (compose)",
                 f"не хватало {len(gone_before)}, после — {len(missing_assets(project, good))}")
    report.check(res.get("ok") and not res.get("pageErrors") and not stuck,
                 "страница с числом, формулой и графиком без ошибок и без залипаний",
                 "; ".join(res.get("pageErrors", []) + stuck)[:120] or "чисто")

    broken = page([viz.formula("bad", r"D = b^{2 - 4ac", at=0.5, dur=1.5)])
    (project / "index.html").write_text(broken, encoding="utf-8")
    bad = run_timeline(project / "index.html")
    report.check(bool(bad.get("pageErrors")) or not bad.get("ok"),
                 "опечатка в формуле ловится проверкой страницы, до рендера",
                 (bad.get("pageErrors") or [bad.get("crash", "ничего не поймано")])[0][:80])


def check_approve(report: Report, tmp: Path):
    """Апрув убирает копии ролика (черновые версии, сырые рендеры), но не принятый и не решения."""
    import approve

    print("\nАпрув и уборка копий")
    out, work, studio = tmp / "a_output", tmp / "a_work", tmp / "a_studio"
    for folder in (out, work / "X", studio / "X" / "renders"):
        folder.mkdir(parents=True)
    for name in ("X_v1.mp4", "X_v1.sheet.jpg", "X_v2.mp4", "X_v2.sheet.jpg", "XY_v1.mp4"):
        (out / name).write_bytes(b"v")
    (studio / "X" / "renders" / "X_v1.mp4").write_bytes(b"raw")
    (work / "X" / "aroll.matte_mediapipe.mkv").write_bytes(b"mask")
    (work / "X" / "edit.json").write_text("{}", encoding="utf-8")
    saved = (approve.OUTPUT_DIR, approve.WORK_DIR, approve.ROOT, approve.studio_dir)
    approve.OUTPUT_DIR, approve.WORK_DIR, approve.ROOT = out, work, tmp
    approve.studio_dir = lambda: studio
    try:
        plan = approve.plan("X", "X_v2.mp4")
        done = approve.apply("X", "X_v2.mp4", ["drafts"])
    except Exception as e:
        plan, done = {}, {"error": f"{type(e).__name__}: {e}"}
    finally:
        approve.OUTPUT_DIR, approve.WORK_DIR, approve.ROOT, approve.studio_dir = saved
    left = sorted(p.name for p in out.iterdir())
    kept_rest = (work / "X" / "aroll.matte_mediapipe.mkv").exists() and (work / "X" / "edit.json").exists()
    report.check(left == ["XY_v1.mp4", "X_v2.mp4", "X_v2.sheet.jpg"] and not any((studio / "X" / "renders").iterdir())
                 and kept_rest and (work / "X" / "approved.json").exists(),
                 "апрув: черновые версии и сырые рендеры убраны, принятый, чужой ролик и решения — на месте",
                 f"в output/: {', '.join(left)}" + (f"; {done.get('error')}" if done.get("error") else ""))


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


def check_atomic_outputs(report: Report, preset: dict, tmp: Path):
    """Упавшая сборка не оставляет битый файл под настоящим именем и не стирает прошлый.

    ffmpeg писал итог прямо в output/ (и в aroll.mp4): упал на финале — в студии «готовый»
    ролик, который не открывается, а прошлый удачный стёрт. Маска так же оставалась короткой
    и потом бралась как готовая («маска уже есть»). Теперь итог встаёт на место только целым.
    """
    import matte
    import render as render_mod

    print("\nЦелые файлы при падении")
    src = tmp / "atomic_src.mov"
    make_source(src, 1.0, 30)
    out = tmp / "atomic_out.mp4"
    out.write_bytes(b"old")
    real = render_mod.ffmpeg_run

    def broken_final(cmd, cwd, what):
        if what == "финальной сборке":
            Path(cmd[-1]).write_bytes(b"half")          # ffmpeg успел начать файл — и упал
            raise RuntimeError("ffmpeg упал на финальной сборке (проверка)")
        return real(cmd, cwd, what)

    render_mod.ffmpeg_run = broken_final
    before = {p.name for p in WORK_DIR.glob("*")}
    try:
        render_mod.render(src, out, [(0.0, 1.0)], preset)
        failed = False
    except RuntimeError:
        failed = True
    finally:
        render_mod.ffmpeg_run = real
        # граф фильтра рендер оставляет в work/ намеренно, проверка за собой — нет
        for p in WORK_DIR.glob("*"):
            if p.name not in before and p.is_file():
                p.unlink()
    tails = sorted(p.name for p in tmp.glob(".atomic_out*"))
    report.check(failed and out.read_bytes() == b"old" and not tails,
                 "упавшая сборка не трогает прошлый ролик и не оставляет недописанный",
                 f"на месте {out.read_bytes()[:4]!r}, хвосты: {', '.join(tails) or 'нет'}")

    class Breaks:
        """Модель маски, которая падает на десятом кадре — как Vision на битом кадре."""
        def __init__(self, width: int, height: int):
            self.shape, self.n = (height, width), 0

        def __call__(self, rgba: bytes) -> np.ndarray:
            self.n += 1
            if self.n > 10:
                raise RuntimeError("модель маски упала (проверка)")
            return np.zeros(self.shape, dtype=np.uint8)

    mask = tmp / "atomic.matte.mkv"
    matte.BACKENDS["broken"] = Breaks
    try:
        matte.run_matte(src, "broken", mask)
        crashed = False
    except RuntimeError:
        crashed = True
    finally:
        matte.BACKENDS.pop("broken", None)
    tails = sorted(p.name for p in tmp.glob(".atomic.matte*"))
    report.check(crashed and not mask.exists() and not tails,
                 "упавшая маска не остаётся короткой под настоящим именем",
                 f"маска {'осталась' if mask.exists() else 'нет'}, хвосты: {', '.join(tails) or 'нет'}")


def check_transcript_source(report: Report, tmp: Path):
    """Другое видео под старым именем не получает чужой транскрипт.

    Кэш распознавания живёт по имени, а у айфонов команды имена одинаковые (IMG_XXXX).
    Новый файл под старым именем молча брал чужие слова — субтитры, рез и text_fixes
    режиссёра от другого видео.
    """
    import transcribe

    print("\nТранскрипт и его исходник")
    cache = tmp / "transcripts"
    cache.mkdir()
    video = tmp / "IMG_0001.MOV"
    video.write_bytes(b"x" * 1000)
    (cache / "IMG_0001.words.json").write_text('{"words": [], "text": ""}', encoding="utf-8")
    try:
        transcribe.run_transcribe(video, cache_dir=cache)       # первая встреча: отметка по файлу
        transcribe.run_transcribe(video, cache_dir=cache)       # тот же файл — без вопросов
        same = True
    except (Exception, SystemExit) as e:
        same, why = False, str(e)
    video.write_bytes(b"y" * 2000)                              # другое видео, имя то же
    try:
        transcribe.run_transcribe(video, cache_dir=cache)
        caught, why = False, "чужой транскрипт взят молча"
    except SystemExit as e:
        caught, why = "не тот файл" in str(e), str(e)[:70]
    except Exception as e:
        caught, why = False, f"{type(e).__name__}: {e}"[:70]
    report.check(same and caught, "другое видео под старым именем — громкий отказ, а не чужие субтитры", why)


def check_long_runs(report: Report):
    """Долгий ML-прогон спрашивает согласие по оценке счёта, а не по длине записи (инвариант 6)."""
    import enhance_audio

    print("\nДолгие прогоны")
    ask = getattr(enhance_audio, "needs_consent", None)
    ok = ask is not None and ask(240, "cpu", False) and not ask(60, "cpu", False) and not ask(600, "cpu", True)
    report.check(bool(ok), "улучшение голоса спрашивает согласие, если счёт дольше пяти минут",
                 "4-минутная запись (≈16 мин счёта) — спросит" if ok else "четыре минуты записи ушли бы без вопроса")


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
        first = import_local_file(cached.as_uri())      # file:///C:/… на Windows, file:///… на Mac
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

    import server
    import studio_api
    from fastapi.testclient import TestClient

    inbox, queue = tmp / "inbox", tmp / "queue"
    inbox.mkdir()
    saved = (server.INPUT_DIR, server.OUTPUT_DIR, server.PRESET_DIR, studio_api.QUEUE, studio_api.ensure_runner)
    server.INPUT_DIR, server.OUTPUT_DIR, server.PRESET_DIR = inbox, tmp / "outbox", tmp
    studio_api.QUEUE, studio_api.ensure_runner = queue, (lambda: False)
    (tmp / "outbox").mkdir()
    try:
        web = TestClient(server.app, base_url="http://127.0.0.1:8765")
        key = {"X-Studio-Token": server.TOKEN}
        first = web.post("/api/upload", files={"file": ("IMG_0001.MOV", b"first", "video/quicktime")}, headers=key).json()
        second = web.post("/api/upload", files={"file": ("IMG_0001.MOV", b"second", "video/quicktime")}, headers=key).json()
        kept = (inbox / "IMG_0001.MOV").read_bytes() if (inbox / "IMG_0001.MOV").exists() else b""
        report.check(first.get("name") == "IMG_0001.MOV" and second.get("name") not in (None, "IMG_0001.MOV")
                     and kept == b"first",
                     "загрузка с занятым именем ложится рядом, а не поверх (у айфонов имена одинаковые)",
                     f"{first.get('name')} → {second.get('name')}")

        voice = inbox / "голос.mp4"
        subprocess.run([ffmpeg_bin(), "-v", "error", "-f", "lavfi", "-i", "sine=d=1", "-c:a", "aac",
                        str(voice)], check=True)
        try:
            listed = server.state()["inputs"]
            survived = any(i["name"] == voice.name and i["duration"] is None for i in listed)
            why = "сервер жив, файл в списке без длительности"
        except BaseException as e:                    # SystemExit из probe() гасил весь сервер
            survived, why = False, f"{type(e).__name__}: {e}"[:80]
        report.check(survived, "файл без видеодорожки в input/ не гасит сервер студии", why)

        r = web.post("/api/render", data={"video": "IMG_0001.MOV", "hook": "Так делают 90%"}, headers=key).json()
        job = r.get("job_id", "")
        import jobqueue
        script = jobqueue.find_job(queue, job) if job else None
        text = script.read_text(encoding="utf-8") if script else ""
        report.check("scripts/reels.py" in text and "--preset" in text,
                     "быстрая панель ставит монтаж в общую очередь, а не запускает рядом с ней",
                     job or str(r)[:80])
        if text:                                       # очередь отработала: поток только читает лог
            for sub in ("logs", "done"):
                (queue / sub).mkdir(exist_ok=True)
            (queue / "logs" / f"{job}.log").write_text("  ✓ готово за 3 с\n", encoding="utf-8")
            script.replace(queue / "done" / script.name)
            body = web.get(f"/api/stream/{job}").text
        else:
            body = ""
        report.check("готово за 3 с" in body and '"code": 0' in body,
                     "поток панели читает лог задачи очереди и сообщает итог", body.replace("\n", " ")[:80] or "—")
    finally:
        server.INPUT_DIR, server.OUTPUT_DIR, server.PRESET_DIR, studio_api.QUEUE, studio_api.ensure_runner = saved


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
                            capture_output=True, encoding="utf-8", errors="replace")
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
    # каждый скилл проекта (reels, viz…) у Claude — ссылка на общий, а не своя копия
    skills = sorted(p.name for p in (ROOT / ".agents/skills").iterdir() if (p / "SKILL.md").exists())
    unlinked = [n for n in skills if not ((ROOT / ".claude/skills" / n).exists()
                                          and (ROOT / ".claude/skills" / n).resolve() == (ROOT / ".agents/skills" / n).resolve())]
    report.check(same and not unlinked, "скиллы общие на оба агента (у Claude — ссылки, не копии)",
                 f"{', '.join(skills)}" + (f"; без ссылки: {', '.join(unlinked)}" if unlinked else ""))
    heads = {n: (ROOT / ".agents/skills" / n / "SKILL.md").read_text(encoding="utf-8").split("\n", 3)[:3] for n in skills}
    bad_heads = [n for n, h in heads.items() if not (len(h) == 3 and h[0] == "---" and h[1] == f"name: {n}"
                                                       and h[2].startswith("description: "))]
    report.check(bool(heads) and not bad_heads, "у каждого скилла есть заголовок name/description",
                 ", ".join(bad_heads) or "чисто")

    hooks = []
    for path, key in ((ROOT / ".claude/settings.json", "hooks"), (ROOT / ".codex/hooks.json", "hooks")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            hooks += [h["command"] for g in data[key]["SessionStart"] for h in g["hooks"]]
        except (OSError, KeyError, json.JSONDecodeError) as e:
            hooks.append(f"ошибка {path.name}: {e}")
    # хук — одна команда node: её одинаково понимают bash (Mac, Git Bash у Claude на Windows),
    # PowerShell и cmd (Codex на Windows); синтаксис «[ -x … ] || true» понимал только bash
    launcher = (ROOT / "scripts/studio_hook.mjs").read_text(encoding="utf-8") \
        if (ROOT / "scripts/studio_hook.mjs").exists() else ""
    report.check(len(hooks) == 2 and all(h.startswith("node ") and "studio_hook.mjs" in h for h in hooks)
                 and "studio_up.py" in launcher and "process.exit(0)" in launcher,
                 "хуки старта Claude и Codex поднимают студию одной командой node на любой системе",
                 "; ".join(h[:50] for h in hooks))

    env = dict(os.environ, REELS_STUDIO_CHILD="1")
    node = shutil.which("node")
    cmd = [node, str(ROOT / "scripts/studio_hook.mjs")] if node else [sys.executable, str(ROOT / "scripts/studio_up.py")]
    child = subprocess.run(cmd, input="{}", capture_output=True, encoding="utf-8", errors="replace",
                           env=env, timeout=30)
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

    # «#FFF» ломал цвет и в ASS, и в CSS молча; «../» в имени стиля читал JSON из чужой папки
    bad_color = bad_id = False
    try:
        styles.effective(broken, {"captions.color": "#FFF"})
    except styles.StyleError:
        bad_color = True
    try:
        styles.load_style("../styles/hormozi")
    except styles.StyleError:
        bad_id = True
    report.check(bad_color and bad_id, "цвет не вида #RRGGBB и имя стиля с путём — громкий отказ",
                 f"цвет {'пойман' if bad_color else 'прошёл'}, путь {'пойман' if bad_id else 'прошёл'}")
    # плашка под тёмным текстом — светлая для любого тёмного, а не только из списка трёх цветов
    lofi = styles.effective(styles.load_style("lofi-ugc"), {"captions.color": "#222222"})
    box = styles.to_fast_preset(lofi, "9:16")["subs"]["box_color"]
    report.check(box == "FFFFFF", "тёмный текст получает светлую плашку при любом тёмном оттенке",
                 f"#222222 → плашка #{box}")

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
                              "-frames:v", "1", "-f", "null", "-"], capture_output=True, encoding="utf-8", errors="replace").stdout
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
                                    "-of", "csv=p=0", str(out)], capture_output=True, encoding="utf-8", errors="replace").stdout.split()
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


def check_studio(report: Report, tmp: Path):
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

    # цена хода (13.10.2026): total_cost_usd у Claude — нарастающий итог сессии, а студия показывала его
    # под каждым ходом как цену хода — у IMG_1803 сумма по ходам выходила $13,41 при настоящих $3,90
    talk = [{"role": "user", "text": "x"}]
    for session, total in (("s1", 0.36), ("s1", 0.71), ("s1", 2.49), ("s2", 0.5)):
        talk += [{"role": "assistant", "events": [{"type": "result", "session": session, "cost": total}]},
                 {"role": "user", "text": "x"}]
    brain.fill_turn_costs(talk)
    turns = [e["turn"] for m in talk for e in m.get("events", []) if e.get("type") == "result"]
    report.check([round(t, 2) for t in turns] == [0.36, 0.35, 1.78, 0.5],
                 "цена хода — разница нарастающих итогов, новая сессия — с нуля (сумма ходов = цена разговора)",
                 ", ".join(f"{t:.2f}" for t in turns))

    # «что идёт сейчас» (current.json) лежит рядом с задачами, но задачей не считается
    queue_dir = tmp / "queue_files"
    queue_dir.mkdir()
    for name in ("current.json", "05-render-X.json"):
        (queue_dir / name).write_text("{}", encoding="utf-8")
    listed = [p.name for p in jobqueue.job_files(queue_dir)]
    report.check(listed == ["05-render-X.json"], "в очереди — только задачи, «что идёт сейчас» не задача",
                 ", ".join(listed) or "пусто")

    first = jobqueue.take_lock()
    if first is None:
        # рядом работает настоящий обработчик — его замок и есть проверка
        report.check(jobqueue.runner_alive(), "обработчик очереди один: второй видит замок",
                     "проверено на работающей очереди")
    else:
        second = jobqueue.take_lock()
        alive = jobqueue.runner_alive()
        first.close()
        report.check(second is None and alive and not jobqueue.runner_alive(),
                     "обработчик очереди один: второй видит замок")

    real_lock = jobqueue.LOCK
    jobqueue.LOCK = tmp / "runner.lock"
    try:
        jobqueue.LOCK.write_text("4242", encoding="utf-8")
        jobqueue.runner_alive()
        kept_pid = jobqueue.LOCK.read_text(encoding="utf-8")
    finally:
        jobqueue.LOCK = real_lock
    report.check(kept_pid == "4242", "вопрос «жив ли обработчик» не переписывает номер его процесса",
                 f"в замке {kept_pid or 'пусто'}")

    check_studio_failures(report, tmp)


def check_queue_control(report: Report, tmp: Path):
    """Идущую задачу можно остановить, а зависшая не держит очередь вечно.

    Аудит 11.10.2026: у очереди не было ни кнопки «Остановить», ни тайм-аута — зависший шаг
    держал очередь, пока его не убьют руками. Теперь кнопка гасит шаг со всеми потомками, а шаг
    без процессора и вывода гасится как зависший. Шаг, который молча считает (маска, речь на
    процессоре), зависшим не считается — иначе очередь убивала бы честную работу.
    """
    import jobqueue
    import psutil

    print("\nОчередь: остановка и зависания")
    marker = f"selfcheck-queue-{os.getpid()}"
    saved = (jobqueue.STOP, jobqueue.HANG_SECONDS)
    jobqueue.STOP = tmp / "stop"

    def leftovers() -> list:
        found = []
        for proc in psutil.process_iter(["cmdline"]):
            try:
                if marker in " ".join(proc.info["cmdline"] or []):
                    found.append(proc)
            except psutil.Error:
                pass
        return found

    def run(name: str, code: str, hang: float, stop_after: float | None = None) -> tuple:
        job = tmp / f"{name}.json"
        job.write_text(json.dumps({"steps": [["python", "-c", code, marker]]}), encoding="utf-8")
        jobqueue.HANG_SECONDS = hang
        log_path, result = tmp / f"{name}.log", {}

        def go():
            with open(log_path, "w", encoding="utf-8") as log:
                result["code"] = jobqueue.run_job(job, log)

        worker = threading.Thread(target=go, daemon=True)
        started = time.time()
        worker.start()
        if stop_after is not None:
            time.sleep(stop_after)
            jobqueue.request_stop(job.stem, queue=tmp)
        worker.join(timeout=45)
        left = leftovers()
        for proc in left:                     # чтобы проверка не оставила после себя процессов
            try:
                proc.kill()
            except psutil.Error:
                pass
        return result.get("code"), time.time() - started, log_path.read_text(encoding="utf-8"), len(left)

    sleeper = "import time; time.sleep(60)"
    nested = ("import subprocess, sys; "
              "subprocess.run([sys.executable, '-c', 'import time; time.sleep(60)', sys.argv[1]])")
    busy = "import time\nt = time.time()\nwhile time.time() - t < 6:\n    pass"
    try:
        code, spent, log, left = run("10-stop", nested, hang=600, stop_after=2)
        report.check(code == 130 and "остановлено вручную" in log and left == 0,
                     "«Остановить» гасит задачу со всеми её процессами, задача падает с причиной",
                     f"код {code}, {spent:.0f} с, процессов осталось {left}")
        code, spent, log, left = run("10-hang", sleeper, hang=3)
        report.check(code == 124 and "завис" in log and left == 0,
                     "шаг без процессора и вывода гасится как зависший, очередь идёт дальше",
                     f"код {code}, {spent:.0f} с")
        code, spent, log, left = run("10-busy", busy, hang=3)
        report.check(code == 0, "шаг, который молча считает, зависшим не считается",
                     f"код {code}, {spent:.0f} с молча при пороге 3 с")
    finally:
        jobqueue.STOP, jobqueue.HANG_SECONDS = saved


def check_studio_failures(report: Report, tmp: Path):
    """Сбой в одном месте студии не кладёт её целиком и не прячет причину.

    Всё это находил аудит 11.10.2026, и всё воспроизводилось: битый brief.json одного ролика
    давал 500 на весь список («сервер не отвечает»); исключение посреди хода мозга оставляло
    его «работающим» навсегда; задачи, которые мозг кладёт в очередь, ждали кнопки; сервер,
    поднятый из сессии агента, раздавал мозгу её номер, сокет и ключ.
    """
    from fastapi.testclient import TestClient
    import brain
    import styles
    import studio_api
    from server import TOKEN, app

    key = {"X-Studio-Token": TOKEN}
    inbox, work, queue = tmp / "studio_in", tmp / "studio_work", tmp / "studio_queue"
    for folder in (inbox, work / "X", queue):
        folder.mkdir(parents=True)
    subprocess.run([ffmpeg_bin(), "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=64x64:r=30:d=1",
                    "-c:v", "libx264", str(inbox / "X.mp4")], check=True)
    (work / "X" / "brief.json").write_text("{ сломано", encoding="utf-8")
    import jobqueue
    jobqueue.write_job("20-prep-X", [["python", "-c", "pass"]], queue=queue)   # как кладёт мозг
    woke = []
    saved = (studio_api.INPUT_DIR, studio_api.WORK_DIR, styles.WORK_DIR, studio_api.QUEUE,
             studio_api.ensure_runner, studio_api.runner_alive)
    studio_api.INPUT_DIR, studio_api.WORK_DIR, styles.WORK_DIR, studio_api.QUEUE = inbox, work, work, queue
    studio_api.ensure_runner, studio_api.runner_alive = (lambda: woke.append(1) or True), (lambda: False)
    try:
        try:
            videos = studio_api.studio_state()["videos"]
            marked, why = bool(videos and videos[0]["brief"].get("error")), "чисто"
        except Exception as e:
            marked, why = False, f"{type(e).__name__}: {e}"[:70]
        try:
            styles.save_brief("X", {"style": "hormozi", "goals": [5, 4]})
            rejected = False
        except styles.StyleError:
            rejected = True
    finally:
        (studio_api.INPUT_DIR, studio_api.WORK_DIR, styles.WORK_DIR, studio_api.QUEUE,
         studio_api.ensure_runner, studio_api.runner_alive) = saved
    report.check(marked and rejected, "битый бриф помечает свой ролик, а не роняет студию; кривой не сохраняется",
                 why if not marked else ("кривой бриф отвергнут" if rejected else "кривой бриф сохранился"))
    report.check(bool(woke), "задачу, которую мозг положил в очередь, студия запускает сама, без кнопки")

    # одно непонятное событие агента не вешает мозг навсегда
    bad = json.dumps({"type": "assistant", "message": {"content": ["строка вместо блока"]}})
    saved_brain = (brain.THREADS, brain.command)
    echo = [sys.executable, "-c", f"print({bad!r})"]          # /bin/echo есть не везде (Windows)
    brain.THREADS, brain.command = tmp / "threads", (lambda *a, **k: echo)
    states = []
    try:
        with TestClient(app, base_url="http://127.0.0.1:8765") as live:
            thread = live.post("/api/brain/threads", json={"engine": "claude"}, headers=key).json()["id"]
            for text in ("привет", "ещё раз"):
                sent = live.post("/api/brain/send", json={"thread": thread, "text": text}, headers=key)
                for _ in range(50):
                    time.sleep(0.1)
                    if not live.get(f"/api/brain/threads/{thread}").json()["running"]:
                        break
                states.append(sent.status_code)
            studio_api.runs.pop(thread, None)
    finally:
        brain.THREADS, brain.command = saved_brain
    report.check(states == [200, 200], "непонятное событие агента не вешает мозг: следующая реплика проходит",
                 " → ".join(map(str, states)))

    # переподключение потока чата продолжает с места, а не повторяет весь ход
    studio_api.runs["selfcheck-resume"] = {"done": True, "events": [
        {"type": "text", "text": "раз"}, {"type": "text", "text": "два"}, {"type": "text", "text": "три"}]}
    try:
        body = TestClient(app, base_url="http://127.0.0.1:8765").get(
            "/api/brain/stream/selfcheck-resume", headers={"Last-Event-ID": "1"}).text
    finally:
        studio_api.runs.pop("selfcheck-resume", None)
    report.check("три" in body and "раз" not in body and "два" not in body,
                 "поток чата после обрыва продолжает с места — без задвоенных ответов",
                 "с места" if "раз" not in body else "повторил ход с начала")

    planted = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "чужая", "CLAUDE_CODE_MESSAGING_TOKEN": "ключ",
               "CLAUDE_CODE_USE_BEDROCK": "1"}
    before = {k: os.environ.get(k) for k in planted}
    os.environ.update(planted)
    try:
        env = brain.child_env()
    finally:
        for k, v in before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    leaked = [k for k in ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_MESSAGING_TOKEN") if k in env]
    report.check(not leaked and env.get("CLAUDE_CODE_USE_BEDROCK") == "1",
                 "мозг не получает номер, сокет и ключ чужой сессии агента, а настройки пользователя — да",
                 ", ".join(leaked) or "чисто")

    said = brain.explain_error("Claude usage limit reached · /upgrade to increase your usage limit")
    report.check(said.startswith("Лимит"), "лимит подписки Claude не выдаётся за «Codex устарел»", said[:50])


def main():
    ap = argparse.ArgumentParser(description="Самопроверка пайплайна монтажа")
    ap.add_argument("--long", action="store_true", help="200 сегментов вместо 60")
    ap.add_argument("--preset", default="viral")
    args = ap.parse_args()

    WORK_DIR.mkdir(exist_ok=True)
    preset = load_preset(args.preset)
    report = Report()

    section(report, check_module_names)
    section(report, check_ffmpeg_options)
    section(report, check_sfx)
    section(report, check_agents)
    section(report, check_styles)
    section(report, check_snapping)
    section(report, check_plan_alignment, preset)
    section(report, check_camera)
    section(report, check_cuts)
    section(report, check_edges)
    section(report, check_captions)
    section(report, check_cleanup_on_failure, preset)
    section(report, check_long_runs)
    with tempfile.TemporaryDirectory(prefix="reels_selfcheck_") as tmpdir:
        tmp = Path(tmpdir)
        section(report, check_skill_links, tmp)
        section(report, check_gen_image, tmp)
        section(report, check_atomic_outputs, preset, tmp)
        section(report, check_transcript_source, tmp)
        section(report, check_page_timeline, tmp)
        section(report, check_grey_zones, tmp)
        section(report, check_style_captions, tmp)
        section(report, check_formats, tmp)
        section(report, check_grades, tmp)
        section(report, check_studio, tmp)
        section(report, check_queue_control, tmp)
        section(report, check_web_import, tmp)
        section(report, check_cut_keeps_speech, preset, tmp)
        section(report, check_voice, preset, tmp)
        section(report, check_hdr, preset, tmp)
        section(report, check_face_exposure, tmp)
        section(report, check_look, preset, tmp)
        section(report, check_face_memory, tmp)
        section(report, check_matte_memory, tmp)
        section(report, check_cutout, tmp)
        section(report, check_cutout_video, tmp)
        section(report, check_portable, tmp)
        section(report, check_approve, tmp)
        section(report, check_batch, tmp)
        section(report, check_viz, tmp)
        section(report, check_render, preset, 200 if args.long else 60, tmp)

    print()
    if report.failed:
        print(f"✗ провалено проверок: {len(report.failed)}")
        for title in report.failed:
            print(f"    — {title}")
        sys.exit(1)
    print("✓ всё чисто, пайплайн можно отдавать в работу")


if __name__ == "__main__":
    main()
