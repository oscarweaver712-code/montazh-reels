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
import contextlib
import io
import json
import math
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

from common import (FONT_DIR, ROOT, WORK_DIR, detect_silence, ffmpeg_bin, ffprobe_bin,
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


def stage_page_assets(project: Path) -> None:
    """Тестовый проект страницы: правки монтажной (layers.js, edits.js) — как кладёт compose.py."""
    import timeline
    shutil.copy2(timeline.LAYERS_JS, project / "layers.js")
    (project / "edits.js").write_text(timeline.edits_js({}), encoding="utf-8")


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


def check_fps_source(report: Report, preset: dict, tmp: Path):
    """Исходник 60 к/с (айфон по умолчанию) и 29,97 к/с режется в ролик 30 к/с кадр в кадр с планом и звуком.

    23.10.2026 у IMG_0930 (iPhone, 60 к/с) каждый кусок дубля выходил на два кадра длиннее звука:
    «-r 30» на выходе добивал кусок до длины последнего кадра 60 к/с. Склейка оставила в звуке дыры
    на стыках, рендер страницы их схлопнул — пропало последнее слово ролика, губы к концу отстали от
    голоса на 0,3 с. Синтетика основной проверки — 30 к/с, на ней этого не видно.

    В тот же день починка (fps после trim) на исходнике 29,97 к/с (IMG_3656, IMG_3662) отдавала кусок на кадр
    длиннее плана: у айфона частота переменная, перед концом куска пропали кадры, и fps дотягивал последний,
    «длинный» кадр за конец куска. Поэтому второй исходник — 29,97 с пропуском кадров у конца куска.

    Вторая дыра — от loudnorm: в динамическом режиме на дорожке не кратной 0,1 с он сбивает метки
    за 3 с до конца (у каждого дубля 1–2 кадра). Поэтому звук здесь пиковый (тихий тон и щелчки —
    линейный режим невозможен, как у живой речи), а длина плана не кратна 0,1 с.
    """
    from render import render

    fps = preset["video"]["fps"]
    # айфон 29,97 к/с с переменной частотой: перед концом куска пропало несколько кадров (метки на сетке 1/600),
    # последний оставшийся кадр «длинный» — fps дотягивал его за конец куска лишним кадром
    vfr = ["-vf", "select='not(between(t\\,4.30\\,4.45))'", "-fps_mode", "vfr", "-video_track_timescale", "600"]
    cases = (("60", "60 к/с", 8, [(0.4, 2.3), (3.1, 4.9), (5.5, 7.567)], []),
             ("30000/1001", "29,97 к/с, пропуски кадров", 8, [(0.567, 4.433), (4.733, 7.2)], vfr))
    for rate, name, seconds, cuts, extra in cases:
        print(f"\nИсходник {name}")
        tag = rate.replace("/", "_")
        src, out = tmp / f"fps{tag}_src.mov", tmp / f"fps{tag}_out.mp4"
        subprocess.run([
            ffmpeg_bin(), "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"testsrc2=size=1080x1920:rate={rate}:duration={seconds}",
            "-f", "lavfi", "-i", f"aevalsrc=0.03*sin(2*PI*300*t)+0.9*between(mod(t\\,2)\\,1\\,1.002):d={seconds}:s=48000",
            *extra, *source_codec(), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest",
            str(src),
        ], check=True, capture_output=True)
        segments = snap_segments(cuts, fps)
        want = sum(round((e - s) * fps) for s, e in segments)
        try:
            render(src, out, segments, {**preset, "look": {"enabled": False}})
            error = ""
        except RuntimeError as e:
            error = str(e).splitlines()[0]
        frames = int(probe_value(out, "stream=nb_frames", "v:0") or 0) if not error else 0
        plan = want / fps
        # звук берём, как рендер страницы: «-t длина» по меткам, дыры при декодировании схлопываются —
        # каждая дыра в метках съедает столько же хвоста
        raw = subprocess.run([ffmpeg_bin(), "-v", "error", "-t", f"{plan:.6f}", "-i", str(out), "-vn", "-ac", "1",
                              "-ar", "48000", "-f", "s16le", "-"], capture_output=True).stdout if not error else b""
        heard = len(raw) / 2 / 48000
        report.check(not error and frames == want and abs(heard - plan) < 0.005,
                     f"исходник {name}: кадров и звука ровно по плану, хвост звука цел",
                     error or f"кадров {frames} из {want}, звука до конца плана {heard:.3f} с из {plan:.3f}")


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

    # 15.10.2026: база проекта 1.2, наезд 1.2 — камера молча стояла на 1.2 весь ролик в семи роликах
    from track import zoom_plan
    try:
        zoom_plan(300, fps, 1.2, [[5.0, 7.0, 1.2, 0.0, 0.6]])
        report.check(False, "наезд не выше базы камеры — громкая ошибка, а не тихо пропавший акцент")
    except ValueError:
        report.check(True, "наезд не выше базы камеры — громкая ошибка, а не тихо пропавший акцент")
    pushed = zoom_plan(600, fps, 1.2, [[12.0, 13.0, 1.36, 0.1]], push=0.006)
    steps = float(np.abs(np.diff(pushed[:int(11.9 * fps)])).max())
    after = pushed[int(13.2 * fps)]          # акцент кончился в 13.0 — база снова почти у 1.2
    report.check(pushed[0] == 1.2 and 1.25 < pushed[int(11.9 * fps)] <= 1.2601 and after < 1.215 and steps < 0.001,
                 "медленный наезд через мысль идёт и сбрасывается на пике акцента",
                 f"{pushed[0]:.3f} → {pushed[int(11.9 * fps)]:.3f}, после акцента {after:.3f}, шаг {steps:.4f}")
    # 23.10.2026, IMG_3661: склейка по паузе — мгновенный крупный «база + 0.12», а медленный наезд к ней набрал +0.03,
    # и крупность на резе сменилась на 0.09 — verify_page не пустил страницу, аналитик крутил ходы впустую
    # Камера решается по кускам между склейками — скачок стоит в первом кадре нового куска, наезд набран в прошлом
    k = int(round(9.0 * fps))
    cut = solve_camera(synthetic_faces([540.0] * 600, [480.0] * 600, fps=fps), cfg={"base_zoom": 1.2, "push": 0.006},
                       cuts=[k], punches=[[9.0, 10.0, 1.32, 0.0, 0.0]])
    report.check(cut[k][0] - cut[k - 1][0] >= 0.12 - 1e-6,
                 "мгновенный скачок на склейке — от докуда доехал наезд, а не от базы",
                 f"{cut[k - 1][0]:.3f} → {cut[k][0]:.3f}")

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

    # воздух после последнего слова (edit.json air_end) — внутри паузы и не дальше её конца
    _, wide = find_edges(words, [(68.10, 68.34), (68.81, 69.65), (69.93, 70.64)], 60.0, 68.80, air_end=0.6)
    _, wider = find_edges(words, [(68.10, 68.34), (68.81, 69.65), (69.93, 70.64)], 60.0, 68.80, air_end=5.0)
    report.check(abs(wide - 69.41) < 0.01 and wider <= 69.65, "воздух после последнего слова — в пределах паузы",
                 f"0.6 с → {wide:.2f}, 5 с → {wider:.2f} (пауза до 69.65)")

    # слова идут вплотную, тишина только после лишнего: резать до него, по распознаванию
    words = [{"word": "мне", "start": 67.12, "end": 67.24}, {"word": "в", "start": 67.24, "end": 67.34}]
    _, end = find_edges(words, [(67.40, 67.60)], 60.0, 67.20)
    report.check(end <= 67.24, "лишнее слово без паузы перед ним не попадает в дубль",
                 f"конец {end:.2f} с")

    # IMG_1816: тихое «профиле» порог −35 дБ счёл паузой (66.62–67.36), она началась раньше слова —
    # конец уезжал в тишину после лишнего «это,» (67.68), и ролик кончался обрывком слова
    words = [{"word": "профиле,", "start": 66.70, "end": 67.02}, {"word": "это,", "start": 67.36, "end": 67.56}]
    _, end = find_edges(words, [(66.62, 67.36), (67.55, 67.80)], 60.0, 67.20)
    report.check(67.02 <= end < 67.36, "тихое последнее слово: лишнее после паузы не попадает в дубль",
                 f"конец {end:.2f} с, «это» с 67.36")

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

    # IMG_3647 (20.10.2026): первое слово файла whisper начал с 0.00 — «Открываешь» 0.00–1.12, а голос с 0.68 и дубль
    # с 0.60. Середина слова (0.56) легла до дубля, и оно выпало из субтитров хука целиком, хотя звучит внутри.
    # Мусор до дубля, задетый его краем на 0.05 с, в субтитры по-прежнему не попадает
    words = [{"word": "Открываешь", "start": 0.0, "end": 1.12}, {"word": "карты", "start": 1.12, "end": 1.46}]
    junk = [{"word": "так", "start": 0.0, "end": 0.65}, {"word": "Открываешь", "start": 0.70, "end": 1.12}]
    mark_dropped(words, [])
    mark_dropped(junk, [])
    kept = [(w["word"], round(w["start"], 2)) for w in remap_words(words, [(0.6, 20.0)])]
    clean = [w["word"] for w in remap_words(junk, [(0.6, 20.0)])]
    report.check([k for k, _ in kept] == ["Открываешь", "карты"] and kept[0][1] == 0.0 and clean == ["Открываешь"],
                 "первое слово, которое whisper начал раньше дубля, остаётся в субтитрах; мусор, задетый краем, — нет",
                 " · ".join(f"{k} {s:.2f}" for k, s in kept) + f"; с мусором: {' · '.join(clean)}")


def check_black_frames(report: Report):
    """Пустой край готового ролика — провал, кроме явного окна director.json → black_frames (21.10.2026, IMG_5688:
    кадр в кадре на чёрном по замыслу). Окно не прощает пустоту за своими границами и без причины не принимается."""
    import verify_render

    print("\nЗадуманный чёрный фон")
    flat, live = (16.0, 16.0, 17.0), (60.0, 20.0, 140.0)
    values = [live] * 20 + [flat, flat] + [live] * 5 + [flat]        # пусто на 20–21 с (замысел) и на 27 с (камера)
    holes, meant = verify_render.empty_edges(values, 1.0, [(20.5, 22.0)])
    bare, _ = verify_render.empty_edges(values, 1.0, [])
    work = Path(tempfile.mkdtemp(prefix="reels_black_"))
    saved = verify_render.WORK_DIR
    verify_render.WORK_DIR = work
    try:
        (work / "X").mkdir()
        (work / "X" / "director.json").write_text(json.dumps({"black_frames": [[20.5, 22.0]]}), encoding="utf-8")
        try:
            verify_render.black_frames("X")
            silent = "окно без причины принято"
        except ValueError:
            silent = ""
    finally:
        verify_render.WORK_DIR = saved
        shutil.rmtree(work, ignore_errors=True)
    report.check(holes == [27] and meant == [20, 21] and bare == [20, 21, 27] and not silent,
                 "пустой край прощается только в окне black_frames с причиной, за окном — провал",
                 f"вне окна {holes}, в окне {meant}, без окна {bare}" + (f"; {silent}" if silent else ""))


def check_pauses(report: Report):
    """Начало по голосу и рез длинных пауз (20.10.2026, Валера: «на старте точно есть пауза», «могу затупить — хочется не
    терять динамику, склеить переходом, чтобы не заметно было»).

    IMG_3645: вдох перед «Почему» (−24…−37 дБ) порвал тишину по −35 дБ, и ролик открывался 0,6 с вдоха. Пауза длиннее
    pause_max сжимается до pause_keep, вдох посреди паузы её не рвёт, слово whisper внутри — не режем. На склейке по
    паузе — смена плана (Take.framing): граница крупного ровно на ней и смаз whip, а не вспышка.
    """
    import kit
    from prep import find_edges, find_pauses, pause_jumps

    print("\nПаузы")
    words = [{"word": "Почему", "start": 0.12, "end": 0.72}, {"word": "в", "start": 0.72, "end": 0.96}]
    silences = [(0.0, 0.14), (0.44, 0.62)]                     # вдох 0.14–0.44 разорвал тишину
    bare, _ = find_edges(words, silences, 0.0, 2.0)
    start, _ = find_edges(words, silences, 0.0, 2.0, voice=[(0.62, 1.40)])
    report.check(0.5 <= start <= 0.62, "ролик начинается с голоса, а не со вдоха",
                 f"начало {start:.2f} с (без карты голоса было бы {bare:.2f}), голос с 0.62")

    words = [{"word": w, "start": a, "end": b} for w, a, b in (
        ("раз", 0.3, 0.9), ("два", 1.3, 1.9), ("три", 3.3, 3.9), ("тут", 4.0, 4.4), ("четыре", 5.6, 6.2), ("пять", 6.3, 6.9))]
    voice = [(0.3, 0.9), (1.3, 1.9), (3.3, 4.4), (5.6, 6.9)]
    silences = [(0.9, 1.3),                                    # обычная пауза 0,4 с — остаётся
                (1.9, 2.5), (2.8, 3.3),                        # затуп 1,4 с, посреди вдох 2.5–2.8 без голоса
                (4.4, 5.6)]                                    # тишина 1,2 с, но whisper слышит в ней «э» — не режем
    words.append({"word": "э", "start": 4.8, "end": 5.2})
    cuts = find_pauses(words, silences, voice, 0.2, 7.0, 0.5, 0.2)
    report.check(cuts == [(2.0, 3.2)], "затуп режется до 0,2 с, вдох его не рвёт, обычная пауза и слово в тишине целы",
                 f"вырезы {cuts}")
    segments = [(0.2, 2.0), (3.2, 7.0)]
    report.check(pause_jumps(segments, cuts) == [1.8], "склейка по паузе помечена на шкале дубля",
                 f"{pause_jumps(segments, cuts)}")

    tk = kit.Take.__new__(kit.Take)
    tk.base_zoom, tk.duration, tk.splices, tk.jumps = 1.2, 20.0, [], [7.0, 13.0]
    tk.words = [{"word": f"слово{i}.", "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(40)]
    punches, whips = tk.framing()
    bounds = [x for p in punches for x in p[:2]]
    hidden = [j for j in tk.jumps if any(abs(x - j) < 0.02 for x in bounds) and f"whip({j:.2f})" in whips]
    report.check(hidden == tk.jumps, "склейка по паузе спрятана сменой плана со смазом",
                 f"спрятано {hidden} из {tk.jumps}; крупные {[(p[0], p[1]) for p in punches]}")
    # склейка не на ровной сотой (22.10.2026, IMG_9665: кадр 764 = 25,4667 с, в aroll.json — 25.467): whip(25.47) смазывал
    # кадр через 3 мс после реза, а крупный кончался на 25.467 — план менялся кадром позже реза, двойной рывок
    tk.duration, tk.jumps = 40.0, [round(764 / 30, 3)]
    punches, whips = tk.framing()
    cut = 764 / 30
    near = min((float(x) for x in re.findall(r"whip\(([\d.]+)\)", whips)), key=lambda x: abs(x - cut))
    edge = min((x for p in punches for x in p[:2]), key=lambda x: abs(x - cut))
    # «Живой отзыв» (testimonial.fit_word, IMG_9665 v1: «висело слово, которое не произносилось»): whisper тянул «я»
    # на 2 с через «э-э» — слово кончается с первым куском голоса; короткая щель внутри слова его не рвёт
    from testimonial import fit_word
    hum = fit_word({"word": "я", "start": 2.2, "end": 4.16}, [[2.2, 2.9], [4.0, 4.16]])
    whole = fit_word({"word": "изменить", "start": 1.0, "end": 2.0}, [[1.1, 1.5], [1.6, 1.95]])
    report.check(hum["end"] == 2.94 and whole["end"] == 1.99 and whole["start"] == 1.08,
                 "слово отзыва — по голосу: «я… э-э…» кончается с голосом, щель внутри слова его не рвёт",
                 f"«я» {hum['start']}–{hum['end']} (ждали до 2.94), «изменить» {whole['start']}–{whole['end']} (1.08–1.99)")
    report.check(near <= cut + 1e-6 and math.ceil(edge * 30 - 1e-6) == 764,
                 "склейка между сотыми: смаз и смена крупности — на её кадре, а не кадром позже",
                 f"рез {cut:.4f} с (кадр 764), смаз whip({near}), граница крупного {edge} → кадр {math.ceil(edge * 30 - 1e-6)}")

    # трек автора (keep_audio, «Настюха» 21.10.2026: «Настя уже подложила музыку, нам надо визуал подбить только»):
    # края — ровно trim (хвост трека после последнего слова цел), паузы не режутся, звук без чистки голоса
    from prep import cuts_pauses, take_audio, take_edges
    from render import audio_chain
    words = [{"word": "летай", "start": 0.0, "end": 1.4}, {"word": "темноте", "start": 27.5, "end": 28.4}]
    silences = [(28.5, 29.07)]
    song = take_edges(words, silences, [(0.0, 28.4)], {}, 29.07, None, keep_audio=True)
    talk = take_edges(words, silences, [(0.0, 28.4)], {}, 29.07, None, keep_audio=False)
    chain = audio_chain(take_audio({"enabled": True, "denoise": True}, True))
    report.check(song == (0.0, 29.07) and talk[1] < 29.0 and chain == ["anull"]
                 and not cuts_pauses({"cut_pauses": True}, {"cut_pauses": True}, True)
                 and cuts_pauses({}, {"cut_pauses": True}, False),
                 "трек автора (keep_audio): дубль целиком до хвоста, паузы не режутся, звук как записан",
                 f"края {song} (без keep_audio — {talk[0]:.2f}–{talk[1]:.2f}), звук {chain}")


def check_captions(report: Report):
    """Субтитры уступают место крупной типографике, но слова перед ударом не теряют.

    Однажды вспышка, лишь хвостом заходившая в зону огромного «=», выкидывалась целиком —
    и перед хуком пропадало слово «равенства». Тихая поломка: ролик собирается, а смысл
    первой секунды уже не тот.
    """
    from compose import caption_chunks, fit_words

    print("\nСубтитры")
    # 23.10.2026, IMG_3663/IMG_3666: «дифференцированный» шире строки — переносом не делится и уезжал под кнопки
    # площадок; аналитик автопилота этого не видел и вставал. Длинному слову — свой кегль, короткому — нет
    import kit
    caps = {"mode": "words", "position": "chest", "size": 1.0, "case": "lower"}
    long_, short = {"text": "дифференцированный", "accent": True}, {"text": "банк", "accent": True}
    fit_words([long_, short], FONT_DIR / "InterDisplay-ExtraBold.ttf", 1.15, caps, "9:16")
    from fontTools.ttLib import TTFont
    font = TTFont(FONT_DIR / "InterDisplay-ExtraBold.ttf", lazy=True)
    cmap, hmtx, upm = font.getBestCmap(), font["hmtx"], font["head"].unitsPerEm
    width = sum(hmtx[cmap[ord(ch)]][0] for ch in long_["text"]) / upm * long_.get("fs", 999)
    report.check("fs" not in short and long_.get("fs", 0) > 30 and width <= kit.CAPTION_BOX["9:16"]["chest"][1],
                 "слово шире строки субтитров — свой кегль, в строку влезает",
                 f"кегль {long_.get('fs')}, ширина {width:.0f} px из {kit.CAPTION_BOX['9:16']['chest'][1]}")
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

    # слова режиссёра со знаками (19.10.2026, IMG_3292: «Индии.» в accent_words, «I.» в keep_case) — как без них:
    # подсвечивалось одно ключевое слово из восьми, «Пётр I» шёл как «Пётр i»
    marked = caption_chunks([{"word": "в", "start": 0.1, "end": 0.2}, {"word": "Индии.", "start": 0.25, "end": 0.7},
                             {"word": "Пётр", "start": 0.9, "end": 1.2}, {"word": "I.", "start": 1.25, "end": 1.5}],
                            {"accent_words": ["Индии."], "keep_case": ["Пётр", "I."]}, duration=2.0)
    plain = caption_chunks([{"word": "Петр", "start": 0.1, "end": 0.4}, {"word": "I.", "start": 0.45, "end": 0.7}], {},
                           duration=1.0)          # имя не в keep_case (партитура аналитика) — номер всё равно с ним
    report.check([(c["text"], c["accent"]) for c in marked] == [("в индии", True), ("Пётр I", False)]
                 and [c["text"] for c in plain] == ["петр I"],
                 "ключевые слова и регистр режиссёра — и со знаками препинания; «Пётр I» одной вспышкой",
                 " · ".join(f'{c["text"]}{"*" if c["accent"] else ""}' for c in marked))

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
    m_names = [n for n in manifest if not n.startswith("_")] + [p.stem for p in folder.glob("*.mp3")]
    leftovers = [n for n in removed if (folder / f"{n}.mp3").exists()]
    try:
        kit.audio("x", "glitch-1", 1.0)
        refused = False
    except ValueError as e:
        refused = "больше нет" in str(e)
    report.check(not [n for n in m_names if n.startswith("glitch")], "шумов-помех (glitch) в библиотеке нет — Валера 15.10: «никогда не подойдут в рилы»",
                 ", ".join(n for n in m_names if n.startswith("glitch")) or "ни одного")
    report.check("glitch-1" in removed and refused and not leftovers,
                 "убранный звук (glitch-1 с «бардака») не вернётся: файла нет, kit отказывает с причиной",
                 ", ".join(leftovers) or "чисто")
    try:
        kit.audio("x", "air-1", 1.0)
        air_back = True
    except ValueError as e:
        air_back = "по ушам" not in str(e)
    hiss = [n for n, (names, *_) in kit.SOFT_KINDS.items() if any(x.startswith("air") for x in names)]
    report.check(not air_back and not hiss and not list(folder.glob("air-*.mp3")),
                 "свист air на вспышках не вернётся (Валера 16.10: «по ушам ездят») — на склейках накат swell",
                 ", ".join(hiss) or "чисто")

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

    # тихие звуки монтажа (16.10, тест удержания на IMG_3303): свой класс — часто, но тихо, вразнобой и не у ударов
    soft_ok = [kit.audio("s0", "swell-1", 1.0), kit.audio("s1", "tap-1", 1.5), kit.audio("s2", "tap-2", 2.0),
               kit.audio("s3", "swell-3", 2.6), kit.audio("i", "impact-bass-1", 4.0)]
    soft_level = effective(kit.audio("x", "tap-1", 1.0))
    report.check(not refused_by_rules(soft_ok)
                 and refused_by_rules([kit.audio("a", "tap-1", 1.0), kit.audio("b", "tap-1", 1.6)])          # тот же подряд
                 and refused_by_rules([kit.audio("a", "tap-1", 1.0), kit.audio("b", "tap-2", 1.2)])          # слиплись
                 and refused_by_rules([kit.audio("a", "impact-bass-1", 1.0), kit.audio("b", "swell-1", 1.3)])  # у удара
                 and refused_by_rules([kit.audio(f"t{i}", f"tap-{i % 3 + 1}", 1.0 + 0.5 * i) for i in range(8)])  # густо
                 and abs(soft_level - (kit.SFX_TARGET + kit.SOFT_DB)) <= 0.5,
                 "тихие звуки монтажа: часто можно, но на 9 дБ тише, вразнобой, не вплотную, не у удара и не гуще 6 за 10 с",
                 f"тап {soft_level:.1f} LUFS при тихой норме {kit.SFX_TARGET + kit.SOFT_DB:g}")
    placed = kit.soft_track([(1.0, "cut"), (1.05, "line"), (2.0, "text"), (2.5, "text"), (4.2, "text")],
                            [kit.audio("i", "impact-bass-1", 4.0)])
    names = re.findall(r"sfx/([\w-]+)\.mp3", "".join(placed))
    report.check(names == ["swell-1", "tap-1", "tap-2"] and not refused_by_rules(placed)
                 and 'data-start="0.74"' in placed[0],
                 "раскладка тихих звуков: склейка важнее линии, накат — с упреждением, у удара — тишина, тапы чередуются", ", ".join(names))
    # фоновая музыка (17.10: «менять постоянно, но по громкости негромко, вот как сейчас хорошо»)
    import tempfile
    import materials
    import verify_page
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        (tmp / "w" / "X" / "materials").mkdir(parents=True)
        shutil.copy2(folder / "swell-1.mp3", tmp / "w" / "X" / "materials" / "yt-test.mp3")
        saved = (materials.WORK_DIR, verify_page.STUDIO)
        materials.WORK_DIR, verify_page.STUDIO = tmp / "w", tmp / "studio"
        try:
            bgm = kit.background_music("X", "yt-test.mp3", 30.0)
            quiet = sound_problems(bgm, "X")
            vol = float(re.search(r'data-volume="([\d.]+)"', bgm).group(1))
            loud_bgm = sound_problems(bgm.replace(f'data-volume="{vol:.3f}"', f'data-volume="{min(1.0, vol * 2):.3f}"'), "X")
            (tmp / "studio" / "Y").mkdir(parents=True)
            (tmp / "studio" / "Y" / "index.html").write_text(bgm, encoding="utf-8")
            again = sound_problems(bgm, "X")
            try:
                kit.background_music("X", "song.mp3", 30.0)
                any_file = True
            except ValueError:
                any_file = False
        finally:
            materials.WORK_DIR, verify_page.STUDIO = saved
    report.check(not quiet and any("громче" in p for p in loud_bgm) and any("уже стоит" in p for p in again) and not any_file,
                 "фоновая музыка: трек фонотеки, не громче «как сейчас», в двух роликах один трек — красное",
                 f"тихо: {quiet or 'чисто'}; громче: {len(loud_bgm)}; повтор: {len(again)}")
    # Mixkit — второй источник фона (20.10.2026, Валера: «найди другой ресурс для музыки»): mx-*.mp3 ставится и меряется, как
    # фонотека YouTube, страница с ним — с музыкой; в запас без указания источника (--yt-library | --mixkit) не кладётся
    import music
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        (tmp / "w" / "X" / "materials").mkdir(parents=True)
        shutil.copy2(folder / "swell-1.mp3", tmp / "w" / "X" / "materials" / "mx-test.mp3")
        saved = (materials.WORK_DIR, verify_page.STUDIO)
        materials.WORK_DIR, verify_page.STUDIO = tmp / "w", tmp / "studio"
        try:
            mx = kit.background_music("X", "mx-test.mp3", 30.0)
            vol = float(re.search(r'data-volume="([\d.]+)"', mx).group(1))
            mx_loud = sound_problems(mx.replace(f'data-volume="{vol:.3f}"', f'data-volume="{min(1.0, vol * 2):.3f}"'), "X")
        finally:
            materials.WORK_DIR, verify_page.STUDIO = saved
    try:
        music.pool_add("_нет_такого_", [], None)
        refused = False
    except SystemExit:
        refused = True
    named = music.slug(Path("mixkit-sleepy-cat-135.mp3"), music.SOURCES["mixkit"][0])
    # проект — временный: на чистой машине (CI) видео роликов нет, и настоящий IMG_3647 проекта не находит
    with tempfile.TemporaryDirectory() as t, temp_projects(Path(t) / "mx_projects", "main") as made:
        made["main"].root.joinpath("project.json").write_text(json.dumps({"music": True}), encoding="utf-8")
        (made["main"].input / "IMG_0900.MOV").write_bytes(b"a")
        heard = verify_page.music_missing(mx, "IMG_0900") is None and verify_page.music_missing("", "IMG_0900") is not None
    report.check(any("громче" in p for p in mx_loud) and refused and named == "mx-sleepy-cat.mp3" and heard,
                 "фон с Mixkit: mx-*.mp3 ставится, меряется и считается музыкой, как фонотека YouTube; запас без источника — отказ",
                 f"громче: {len(mx_loud)}, без источника {'отказ' if refused else 'принят'}, имя {named}, "
                 f"страница {'с музыкой' if heard else 'без музыки'}")


def check_footage(report: Report, tmp: Path):
    """ИИ-футажи из Google Flow (footage.py, 16.10.2026): бриф, сообщения для Flow, приём клипа под кадр.

    Flow и браузер не зовутся — самопроверка не тратит бонусы и не зависит от сети. Проверяется то, что
    сломалось бы тихо: клип Flow (720×1280, 24 к/с, со звуком) должен лечь в кадр 1080×1920, 30 к/с, без
    звука, на сетку кадров; из «Загрузок» берётся свежий и ещё не принятый файл, а не старый; короткий клип
    и перерасход бонусов — красные, а не чёрный хвост в ролике.
    """
    import common
    import footage
    import kit

    print("\nИИ-футажи (Google Flow)")
    work = tmp / "footage_work"
    brief = {"budget": 20, "style": "warm kitchen light",
             "clips": [{"name": "a_shelf", "at": [1.0, 3.0], "say": "полка", "image": "a supermarket shelf",
                        "motion": "walk forward", "refs": ["materials/pack.png"]},
                       {"name": "b_tea", "at": [4.0, 9.0], "say": "чай", "image": "tea on a table",
                        "motion": "steam rises"}]}
    bad = []
    for broken in ({**brief, "clips": [{**brief["clips"][0], "name": "Полка"}]},
                   {**brief, "clips": [{**brief["clips"][0], "motion": ""}]},
                   {**brief, "clips": [{**brief["clips"][0], "at": [3, 1]}]}):
        try:
            footage.validate(broken)
            bad.append(broken["clips"][0])
        except footage.FootageError:
            pass
    first, second, refs = footage.messages(footage.validate(brief))
    msg_ok = ("exactly one image per prompt" in first and "9:16" in first and "[b_tea]" in first
              and "first frame" in second and "[a_shelf]" in second and refs == ["materials/pack.png"]
              and "reference" in first and "top 20%" in first)
    report.check(not bad and msg_ok, "бриф без дыр; сообщения для Flow — все клипы, вертикаль, референсы, спокойный верх",
                 f"пропущено битых {len(bad)}, сообщения {'полные' if msg_ok else 'неполные'}")

    # один стиль на все генерации (20.10.2026, «Макет на чёрном столе» в DESIGN.md Антишколы): замок кадра и движения
    # уходит в каждый промпт, а вшитый хвост «фото с телефона» его не перебивает; у проекта без системы — как было
    import projects
    from types import SimpleNamespace
    # система Антишколы — копией из шаблона expert-viral: проекты — данные клиентов, на чистой машине их нет (23.10.2026)
    with temp_projects(tmp / "ft_look", "ds") as made:
        shutil.copy2(ROOT / "presets" / "templates" / "expert-viral" / "DESIGN.md", made["ds"].root / "DESIGN.md")
        look, move = footage.project_look(projects.get("ds"))
    plain, _ = footage.project_look(SimpleNamespace(name="_нет_такого_", config={}))
    lock = {k: v for k, v in brief.items() if k != "style"}
    first, second, _ = footage.messages(footage.validate({**lock, "style": look, "motion_style": move}))
    styled = ("black desk" in first and "red lacquer" in first and "phone camera" not in first and "photorealistic"
              not in first.lower() and "kinetic paper model" in second and second.count("kinetic paper model") == 2)
    # бюджет без отдельного «да» — умолчание проекта (20.10.2026, Валера: «на ролик 2 клипа по умолчанию»); свой budget
    # брифа главнее
    with temp_projects(tmp / "ft_projects", "main") as made:
        made["main"].root.joinpath("project.json").write_text(json.dumps({"footage_clips": 2, "footage_budget": 30}),
                                                              encoding="utf-8")
        saved_dir = footage.WORK_DIR
        footage.WORK_DIR = tmp / "ft_work"
        try:
            for stem, b in (("IMG_0800", {k: v for k, v in brief.items() if k != "budget"}), ("IMG_0801", brief)):
                (made["main"].input / f"{stem}.MOV").write_bytes(b"a")
                (footage.WORK_DIR / stem).mkdir(parents=True)
                (footage.WORK_DIR / stem / "footage.json").write_text(json.dumps(b), encoding="utf-8")
            by_project, own = footage.load_brief("IMG_0800").get("budget"), footage.load_brief("IMG_0801").get("budget")
        finally:
            footage.WORK_DIR = saved_dir
    report.check(by_project == 30 and own == 20,
                 "бонусы Flow: без budget в брифе — умолчание проекта (footage_budget), свой budget брифа главнее",
                 f"по проекту {by_project}, свой {own}")
    report.check(styled and "phone camera" in plain,
                 "ИИ-клипы в стиле проекта: замок «Макета» из DESIGN.md в каждом кадре и движении, без «фото с телефона»; "
                 "без дизайн-системы — фото, как было",
                 f"кадр {'«Макет»' if 'black desk' in first else 'без замка'}, телефон {'есть' if 'phone camera' in first else 'нет'}, "
                 f"движение {second.count('kinetic paper model')} из 2, без системы — {plain[:40]}")

    saved = footage.WORK_DIR, common.WORK_DIR
    footage.WORK_DIR = common.WORK_DIR = work
    try:
        (work / "X").mkdir(parents=True)
        (work / "X" / "footage.json").write_text(json.dumps(brief), encoding="utf-8")
        dl = tmp / "Downloads"
        dl.mkdir()
        # как отдаёт Flow: 720×1280, 24 к/с, 4 с, со звуком; плюс старый файл и двойное расширение
        for name, age in (("old.mp4", 5 * 3600), ("flow_clip.mp4.mp4", 0)):
            subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=24:duration=4",
                            "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-shortest", *source_codec(), "-c:a", "aac",
                            "-f", "mp4", str(dl / name)], check=True, capture_output=True)
            os.utime(dl / name, (time.time() - age, time.time() - age))
        picked = footage.newest_download("X", dl).name
        got = footage.take("X", "a_shelf", None, start=0.5, speed=1.5, credits=15, where=dl)
        out = work / "X" / "footage" / "a_shelf.mp4"
        size = probe_value(out, "stream=width,height", "v:0")
        rate = probe_value(out, "stream=r_frame_rate", "v:0")
        frames = int(probe_value(out, "stream=nb_frames", "v:0") or 0)
        audio = probe_value(out, "stream=codec_type", "a")
        expect = int((4 - 0.5) / 1.5 * 30)
        report.check(picked == "flow_clip.mp4.mp4" and size == "1080,1920" and rate == "30/1" and not audio
                     and abs(frames - expect) <= 1 and abs(got["duration"] - expect / 30) < 1e-3
                     and (work / "X" / "footage" / "orig" / "a_shelf.mp4").exists()
                     and (work / "X" / "footage" / "a_shelf.md").exists(),
                     "клип Flow ложится в кадр: 1080×1920, 30 к/с, без звука, подрезка и ускорение на сетке кадров",
                     f"взят {picked}, {size} {rate} кадров {frames} (ждали {expect}), звук {'есть' if audio else 'нет'}")
        try:
            footage.newest_download("X", dl)
            again = "взят повторно"
        except footage.FootageError:
            again = ""
        report.check(not again, "принятый клип и старый (5 ч) из «Загрузок» второй раз не берутся", again or "не берутся")

        rows, ok_missing = footage.status("X")                 # b_tea нет — красное
        footage.take("X", "b_tea", dl / "flow_clip.mp4.mp4", speed=1.0, credits=10)   # 4 с при окне 5 с
        rows2, ok_short = footage.status("X")                  # короткий и 25 бонусов при 20 — красное
        try:
            kit.footage("ft", "X", "b_tea", 4.0, 5.0)
            kit_short = "kit поставил короткий клип"
        except ValueError:
            kit_short = ""
        html, js = kit.footage("ft", "X", "a_shelf", 1.0, 2.0)
        kit_ok = ('src="assets/footage/a_shelf.mp4"' in html and 'data-start="1.00"' in html
                  and "splice(3.000)" in js and 'tl.to("#flash"' in js)          # вход вспышкой, выход — склейкой проекта
        report.check(not ok_missing and not ok_short and any("короче плана" in r for r in rows2)
                     and any("25 бонусов при одобренных 20" in r for r in rows2) and not kit_short and kit_ok,
                     "нет клипа, клип короче окна, перерасход бонусов — красные; kit не ставит короткий клип",
                     kit_short or ("всё ловится" if kit_ok else "kit.footage собрал не то"))
    finally:
        footage.WORK_DIR, common.WORK_DIR = saved


def check_fx(report: Report, tmp: Path):
    """Приёмы из рилса @tenfoldmarc (fx.py, 16.10.2026): складываются в страницу kit и не залипают.

    Ловится то, на что наступили при сборке галереи (work/_fx/gallery.py): ключи орбиты кончались ровно на
    скрытии — на сдвиге в кадр карточка висела до конца ролика; CSS-transform на элементе, которому GSAP
    двигает y, затирался; координаты рамки брались мимо камеры. Плюс громкие отказы на кривой вызов.
    """
    import re as _re

    import fx
    import kit

    print("\nПриёмы fx (17 эффектов)")
    parts = fx.merge(fx.checklist("ck", "Шаги", ["а", "б"], [1.0, 2.0], 3.0), fx.orbit("orb", ["a.jpg", "b.jpg"], 1.0, 3.0),
                     fx.zoom_through(4.0), fx.wall("w", ["x"], [5.0], 6.0), fx.frame_break("fb", 7.0, 9.0),
                     fx.vertigo(10.0, 11.0), fx.glass_word("gl", 12.0, 13.0, "СЛОВО"), fx.toc("toc", ["а", "б"], [1.0, 2.0], 9.0))
    page = kit.build_page("fx", 14.0, parts.behind, parts.front, parts.js, [], parts.windows, cta_at=13.0,
                          extra_css=parts.css, cta=False)
    done = parts.finalize(page)
    stage_ok = done.count('<div id="stage">') == 1 and parts.css.count("#stage {") == 1 and parts.css.count(".fx {") == 1
    try:
        fx.FX(stage=True).finalize("<html></html>")
        stage_ok = False
    except ValueError:
        pass
    ends = []
    for m in _re.finditer(r'tl\.to\("#(orb-[bf]\d)", \{ keyframes: \[(.*?)\] \}, ([\d.]+)\);', parts.js):
        total = sum(float(x) for x in _re.findall(r"duration: ([\d.]+)", m.group(2)))
        hide = float(_re.search(rf'tl\.set\("#{m.group(1)}", \{{ opacity: 0 \}}, ([\d.]+)\)', parts.js).group(1))
        ends.append(hide - (float(m.group(3)) + total))
    css_conflict = [k for k, v in fx.CSS.items() if _re.search(r"transform:\s*(translate|scale|rotate)", v)]
    camera = "cam[Math.min" in parts.js and parts.js.count("window.CAMERA_FPS") >= 2
    report.check(stage_ok and ends and min(ends) >= 0.066 and not css_conflict and camera
                 and sum(w[0] <= 5.0 <= w[1] for w in parts.windows) >= 1,
                 "приёмы складываются в страницу: #stage один раз, орбита гаснет после своих ключей, без CSS-transform, "
                 "рамка и вертиго — по камере",
                 f"stage {'да' if stage_ok else 'нет'}, запас орбиты {min(ends) if ends else '—'} с, "
                 f"CSS-transform {css_conflict or 'нет'}, камера {'да' if camera else 'нет'}")
    loud = 0
    for bad in (lambda: fx.checklist("x", "t", ["a", "b"], [1.0], 2.0), lambda: fx.wall("x", ["a"] * 9, [1.0] * 9, 2.0),
                lambda: fx.vertigo(1, 2, amount=0.5), lambda: fx.doodle("x", 1, 2, [("dragon", 0, 0, "#fff")]),
                lambda: fx.toc("x", ["a", "b"], [2.0, 1.0], 3.0), lambda: fx.orbit("x", [], 1, 2)):
        try:
            bad()
        except ValueError:
            loud += 1
    report.check(loud == 6, "кривой вызов приёма — громкая ошибка, а не молча кривая графика", f"{loud} из 6")

    # блоки приёмов — .g прямо в #behind/#front: иначе их не видят ни проверки страницы (серые зоны, динамика,
    # лицо), ни монтажная студии (на галерее 16.10 проверки молчали, пока класс был только .fx)
    import timeline
    items = timeline.parse_page(done)["items"]
    names = {x["id"]: timeline._kind_label(x) for x in items}
    unnamed = [k for k, v in names.items() if v.startswith("рисунок")]
    report.check({"ck", "toc", "w-0", "gl", "orb-b0", "orb-f0"} <= set(names) and not unnamed,
                 "монтажная видит слои приёмов и подписывает их по-человечески (чек-лист, орбита, стекло)",
                 f"слоёв {len(names)}, без подписи {unnamed or 'нет'}")


def check_cutaway_rules(report: Report, tmp: Path):
    """Правила после IMG_3303 v2 (Валера 16.10.2026): субтитры не на лице и не вплотную к подбородку; текст за спиной
    не прячется за головой; на перебивке (футаж, серия картинок) нет человека поверх; линия субтитров — одна на ролик."""
    import compose
    import kit
    from verify_page import run_timeline

    print("\nСубтитры, текст за головой, перебивки")
    project = tmp / "cutaway"
    (project / "assets" / "img").mkdir(parents=True)
    shutil.copy2(ROOT / "studio" / "_vendor" / "gsap.min.js", project / "assets" / "gsap.min.js")
    (project / "camera.js").write_text("window.CAMERA_FPS = 30;\nwindow.CAMERA = [[0, 0, 1], [0, 0, 1]];\n")
    stage_page_assets(project)
    caps = [{"t0": 0.2, "t1": 1.0, "text": "на лице", "accent": False, "y": 1000},
            {"t0": 1.0, "t1": 1.9, "text": "под подбородком", "accent": False, "y": 1180}]
    (project / "captions.js").write_text("window.CAPTIONS = " + json.dumps(caps, ensure_ascii=False) + ";\n", encoding="utf-8")
    face = [(round(0.25 * k, 2), 360.0, 600.0, 740.0, 1100.0) for k in range(8)]     # макушка ~520, подбородок 1100
    behind = ('        <div id="o-head" class="g big" style="top: 560px; font-size: 140px;">за головой</div>\n'
              '        <div id="o-top" class="g big" style="top: 300px; font-size: 140px;">над головой</div>')
    beats = ('      tl.set("#o-head", { opacity: 1 }, 0.2); tl.set("#o-top", { opacity: 1 }, 0.2);\n')
    (project / "index.html").write_text(build_page_safe(kit, behind, "", beats, [(0.1, 1.9)]), encoding="utf-8")
    res = run_timeline(project / "index.html", faces=face)
    capf = {h["el"] for h in res.get("faceHits", [])}
    hidden = {o["el"] for o in res.get("occluded", [])}
    report.check(capf == {"субтитр «на лице»"}, "субтитр на лице ловится, под подбородком с отступом — нет",
                 ", ".join(sorted(capf)) or "ничего не поймано")
    report.check(hidden == {"#o-head"}, "текст за спиной, закрытый головой, ловится; над головой — нет",
                 ", ".join(sorted(hidden)) or "ничего не поймано")

    (project / "captions.js").write_text("window.CAPTIONS = [];\n", encoding="utf-8")
    shutil.copy2(ROOT / "studio" / "_vendor" / "gsap.min.js", project / "assets" / "img" / "a.jpg")
    html, js = kit.slides("sl", ["a.jpg", "a.jpg"], 0.4, [0.7, 0.7])
    bad = build_page_safe(kit, html, "", js, [(0.2, 1.0)])          # окно вырезки заходит на перебивку
    good = build_page_safe(kit, html, "", js, [(0.05, 0.3)])
    (project / "index.html").write_text(bad, encoding="utf-8")
    over_bad = run_timeline(project / "index.html").get("fgOverCut", [])
    (project / "index.html").write_text(good, encoding="utf-8")
    over_good = run_timeline(project / "index.html").get("fgOverCut", [])
    report.check(over_bad and not over_good, "человек поверх перебивки ловится; окно вырезки до неё — нет",
                 f"поверх: {len(over_bad)} замеров, без него: {len(over_good)}")

    # линия субтитров одна на ролик: подбородок низко → над головой, обычно → под подбородком
    sc = {"fmt": "9:16", "caps": {"mode": "words", "position": "chest"}, "director": {},
          "chunks": [{"t0": 0.2, "t1": 1.0}, {"t0": 1.0, "t1": 1.8}]}
    import verify_page
    saved = verify_page.face_track
    try:
        verify_page.face_track = lambda p: [(0.25 * k, 360, 600, 740, 1100) for k in range(8)]
        low = compose.caption_lane(project, sc) and {c["y"] for c in sc["chunks"]}
        verify_page.face_track = lambda p: [(0.25 * k, 300, 700, 780, 1330) for k in range(8)]
        high = compose.caption_lane(project, sc) and {c["y"] for c in sc["chunks"]}
    finally:
        verify_page.face_track = saved
    report.check(low == {1150} and len(high) == 1 and next(iter(high)) < 700,
                 "линия субтитров одна на ролик: под подбородком с отступом, а если низ занят — над головой",
                 f"обычно {low}, лицо низко {high}")

    # субтитры не двоятся с текстом и не пропадают надолго (Валера 16.10, IMG_3303 v3: «дублировались… надолго пропали»)
    caps = [{"t0": 0.2, "t1": 1.0, "text": "что соты", "accent": False, "y": 1150},
            {"t0": 1.0, "t1": 1.9, "text": "у пчел x", "accent": False, "y": 1150}]
    (project / "captions.js").write_text("window.CAPTIONS = " + json.dumps(caps, ensure_ascii=False) + ";\n", encoding="utf-8")
    behind = ('        <div id="d-lead" class="g big" style="top: 300px; font-size: 60px;">соты у пчёл</div>\n'
              '        <div id="d-other" class="g big" style="top: 420px; font-size: 60px;">шестиугольные</div>\n'
              '        <div id="d-spell" class="g big" style="top: 540px; font-size: 60px;">XVIII</div>\n'
              '        <div id="d-latin" class="g big" style="top: 660px; font-size: 60px;">ABC</div>')
    beats = ('      tl.set("#d-lead", { opacity: 1 }, 0.2); tl.set("#d-other", { opacity: 1 }, 0.2);\n'
             '      tl.set("#d-spell", { opacity: 1 }, 0.2); tl.set("#d-latin", { opacity: 1 }, 0.2);\n')
    (project / "index.html").write_text(build_page_safe(kit, behind, "", beats, [(0.1, 1.9)]), encoding="utf-8")
    dupes = {d["el"] for d in run_timeline(project / "index.html").get("dupes", [])}
    report.check(dupes == {"#d-lead", "#d-spell"},
                 "субтитр и текст на экране с одними словами ловятся, буквы по одной («x» под XVIII) — тоже; другие — нет",
                 ", ".join(sorted(dupes)) or "ничего не поймано")

    # пустые места (19.10.2026, Валера на демо IMG_3292 v2: «в какой-то момент нет никаких вставок… динамика очень
    # теряется» — 15 с без вставок): участок без единой графики меряется, сплошной показ — нет
    (project / "captions.js").write_text("window.CAPTIONS = [];\n", encoding="utf-8")
    bare_html = ('        <div id="e-a" class="g big" style="top: 300px; font-size: 60px;">раз</div>\n'
                 '        <div id="e-b" class="g big" style="top: 420px; font-size: 60px;">два</div>')
    holes = {}
    for name, beats in (("дыра", '      tl.set("#e-a", { opacity: 1 }, 0.1); tl.set("#e-a", { opacity: 0 }, 0.3);\n'
                                 '      tl.set("#e-b", { opacity: 1 }, 1.7);\n'),
                        ("сплошь", '      tl.set("#e-a", { opacity: 1 }, 0.1); tl.set("#e-b", { opacity: 1 }, 0.9);\n')):
        (project / "index.html").write_text(build_page_safe(kit, bare_html, "", beats, []), encoding="utf-8")
        holes[name] = run_timeline(project / "index.html").get("bare", [])
    report.check(len(holes["дыра"]) == 1 and holes["дыра"][0][1] - holes["дыра"][0][0] > 1 and not holes["сплошь"],
                 "пустое место без вставок ловится, сплошной показ — нет",
                 f"с дырой: {holes['дыра']}, сплошь: {holes['сплошь']}")
    (project / "captions.js").write_text("window.CAPTIONS = " + json.dumps(caps, ensure_ascii=False) + ";\n", encoding="utf-8")
    words = [{"word": w, "start": 0.5 * k, "end": 0.5 * k + 0.45} for k, w in enumerate(
        ["ячейки", "должны", "стоять", "вплотную", "без", "щелей", "круглые", "так", "не", "встанут", "а", "потерянное"])]
    (project / "aroll.words.json").write_text(json.dumps({"words": words}, ensure_ascii=False), encoding="utf-8")
    saved = verify_page.take_dir
    try:
        verify_page.take_dir = lambda p: project
        long_gap = verify_page.caption_gaps(project)            # субтитры есть только на 0.2–1.9 — дальше 4 с речи без них
        caps.append({"t0": 3.4, "t1": 6.0, "text": "встанут", "accent": False, "y": 1150})
        (project / "captions.js").write_text("window.CAPTIONS = " + json.dumps(caps, ensure_ascii=False) + ";\n", encoding="utf-8")
        short_gap = verify_page.caption_gaps(project)           # провал 2.0–3.4 — короче 3 с
    finally:
        verify_page.take_dir = saved
    report.check(len(long_gap) == 1 and not short_gap, "речь без субтитров дольше 3 с ловится, короткий провал — нет",
                 f"долгий: {long_gap}, короткий: {short_gap}")


def build_page_safe(kit, behind: str, front: str, beats: str, windows: list) -> str:
    return kit.build_page("проверка", 2.0, behind, front, beats, [], windows, cta_at=5.0, cta=False)


def check_gen_image(report: Report, tmp: Path):
    """Фон через Codex (gen_image.py, 12.10.2026): правила в запросе, отбор картинки, подхват результата.

    Сам Codex не зовётся — самопроверка не тратит лимит ChatGPT и не зависит от сети. Проверяется
    то, что ломалось бы тихо: Codex то копирует картинку по просьбе, то только называет свой путь
    (второй же пробный запуск) — скрипт берёт свежую из generated_images, но не старую чужую.
    """
    import gen_image

    print("\nФон через Codex")
    prompt = gen_image.build_prompt("ворота Иштар", ROOT / "work" / "X" / "downloads" / "bg.png")
    rules_in = all(w in prompt for w in ("без людей", "без случайных надписей", "9:16", "work/X/downloads/bg.png"))
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
    # copyfile, а не copy2: copy2 переносит время исходника, а его сделали раньше запуска — на медленной
    # машине (Windows CI 12.10) больше чем за секунду, и «свежая» картинка выходила старой
    shutil.copyfile(pics["vertical"], fresh)
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


def check_board(report: Report, tmp: Path):
    """«Доска» (13.10.2026, арсенал Валеры): ManimGX рендерит сцену в клип, а viz.board ставит его на
    страницу. Проверяется по-настоящему: своё окружение .venv-manim (Python 3.13) на месте, кадр не
    пустой, длина и размер — как заказаны, плашка видна ровно столько, сколько идёт клип.
    """
    import common
    import viz
    from manim_clip import render

    print("\nДоска: математика движением (ManimGX)")
    scene = tmp / "board_check.py"
    scene.write_text('import manimgx as m\n\n\nclass Check(m.Scene):\n    def construct(self):\n'
                     '        self.camera.background_color = "#141210"\n'
                     '        self.play(m.Write(m.MathTex(r"x^2 = 4", color="#F2EBDD").scale(2)), run_time=0.8)\n'
                     '        self.wait(0.2)\n', encoding="utf-8")
    clip_dir = tmp / "work" / "X" / "manim"
    out = clip_dir / "Check.mp4"
    try:
        stats = render(scene, out, size="360x360")
    except Exception as e:                       # не установлен, упал, не отдал файл — громко
        report.check(False, "ManimGX рендерит сцену в клип нужной длины и размера, кадр не пустой", str(e)[:300])
        return
    frame = subprocess.run([ffmpeg_bin(), "-v", "error", "-ss", "0.9", "-i", str(out), "-frames:v", "1",
                            "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    contrast = (max(frame) - min(frame)) if frame else 0
    frames = int(probe_value(out, "stream=nb_frames", "v:0") or 0)
    steady = abs(frames - round(stats["duration"] * 30)) <= 1          # постоянные 30 к/с, пауза — кадрами
    report.check(0.8 <= stats["duration"] <= 1.5 and (stats["width"], stats["height"]) == (360, 360) and contrast > 100
                 and steady,
                 "ManimGX рендерит сцену в клип нужной длины и размера, кадры ровно 30 в секунду, кадр не пустой",
                 f"{stats['duration']:.2f} с, {frames} кадров, {stats['width']}×{stats['height']}, контраст {contrast}")
    saved = common.WORK_DIR
    common.WORK_DIR = tmp / "work"
    try:
        html, js = viz.board("bd", "X", "Check.mp4", at=2.0)
    finally:
        common.WORK_DIR = saved
    dur = re.search(r'data-duration="([\d.]+)"', html)
    report.check('class="clip"' in html and 'src="assets/manim/Check.mp4"' in html and dur is not None
                 and abs(float(dur.group(1)) - stats["duration"]) < 0.05 and 'leave("#bd"' in js,
                 "доска на странице: клип-слой с длиной из файла, плашка входит и уходит движением",
                 f"длина на странице {dur.group(1) if dur else '?'} с при клипе {stats['duration']:.2f} с")


def check_plan(report: Report, tmp: Path):
    """План до сборки (правило Валеры, 13.10.2026: «понимать, что и как будешь делать, и какими
    инструментами где» — до редактуры). Годный план проходит; пустой раздел, инструмент не из
    арсенала, плашка, стоящая 7 с, и 10 с без смены на экране — нет. Рендер без годного плана не идёт.
    """
    import plan

    print("\nПлан монтажа")
    saved = plan.WORK_DIR
    plan.WORK_DIR = tmp / "plans"
    try:
        (plan.WORK_DIR / "X").mkdir(parents=True)
        (plan.WORK_DIR / "X" / "aroll.json").write_text(json.dumps({"duration": 20.0}), encoding="utf-8")

        def problems(rows: list, filled: bool = True, seen: int = 5) -> list:
            board = "\n".join(f"| {t} | реплика | что на экране | {tool} | почему | {hold} |" for t, tool, hold in rows)
            thought = "зритель унесёт одно" if filled else f"{plan.TODO} одной фразой"
            eyes = "\n".join(f"- {i * 3.5:.1f} с — банка в правой руке, жест ладонью" for i in range(seen))
            (plan.WORK_DIR / "X" / "plan.md").write_text(
                f"# План\n\n## Исходник\n- длина 20 с\n\n## Дубль глазами\n{eyes}\n\n"
                f"## Мысль ролика\n{thought}\n\n## Хук\nвопрос в лоб\n\n"
                f"## Раскадровка\n| время, с | реплика | что на экране | инструмент | почему он | держится, с |\n"
                f"|---|---|---|---|---|---|\n{board}\n\n## Звук\nудар на главном\n\n## Риски\nлицо низко\n",
                encoding="utf-8")
            return plan.check("X")

        good = problems([("0.5", "слово за спиной + звук", "2"), ("4.0", "панель", "3.5"), ("8.0", "наезд", ""),
                         ("12.5", "счётчик", "3"), ("16.0", "CTA", "4")])
        bad = " | ".join(problems([("0.5", "голограмма", "2"), ("4.0", "панель", "7"), ("14.0", "наезд", ""),
                                   ("17.0", "CTA", "3")], filled=False))
        rows = [("0.5", "слово за спиной", "2"), ("4.0", "панель", "3"), ("8.0", "наезд", ""), ("12.5", "счётчик", "3"),
                ("16.0", "CTA", "4")]
        blind = " | ".join(problems(rows, seen=2))
        # 17.10.2026, IMG_3292 v2: «как будто анализ видео вообще не проводился» — дубль никто не смотрел
        (plan.WORK_DIR / "X" / "aroll.mp4").write_bytes(b"")
        no_sheet = " | ".join(problems(rows))
        (plan.WORK_DIR / "X" / "aroll.mp4").unlink()
        caught = {"пустой раздел": "«Мысль ролика» не заполнен" in bad, "чужой инструмент": "голограмма" in bad,
                  "плашка висит": "держится 7" in bad, "дыра без смены": "4.0–14.0" in bad,
                  "дубль не смотрели": "2 наблюдений" in blind, "нет сетки дубля": "сетки кадров" in no_sheet}
    finally:
        plan.WORK_DIR = saved
    report.check(not good and all(caught.values()),
                 "план: годный проходит; пустой раздел, чужой инструмент, висящая плашка, дыра без смены "
                 "и дубль, который не смотрели глазами, — нет",
                 "; ".join(good) if good else ", ".join(k for k, v in caught.items() if not v) or "все шесть пойманы")


def check_events(report: Report, tmp: Path):
    """События дубля и обязательное сборки (19.10.2026, Валера: «где-то вспышку после хука, где-то вырезать неудачную часть
    дубля, где запороли — серый фильтр, запикать маты, 3 секунды угара», «то звуки потеряются, то музыка»).

    Сбивка с матом и с повтором режется от первой попытки до последней; цитата и объяснение с повтором — нет; мат
    ловится по началу слова, «требует» и «хуже» — не мат; угар вне выреза — громкий отказ; движения страницы дают тихие
    звуки; без подтверждения источника запас музыки файл не берёт; готовый ролик без музыки краснеет по звуку."""
    import events
    import montage
    import music
    import prep
    import verify_page
    import verify_render

    print("\nСобытия дубля и обязательное сборки")

    def said(text: str, t0: float = 0.0, step: float = 0.3, gaps: dict | None = None) -> list:
        out, t = [], t0
        for k, w in enumerate(text.split()):
            t += (gaps or {}).get(k, 0.0)
            out.append({"word": w, "start": round(t, 2), "end": round(t + step - 0.04, 2), "n": events.norm(w)})
            t += step
        return out

    take = said("А в Америке пишут крестик. Блять. Не, не, ничего. А в Америке школьники пишут крестик. Дальше идём.")
    cuts = events.retakes(take)
    retake_ok = len(cuts) == 1 and take[cuts[0][0]]["word"] == "А" and " ".join(
        w["word"] for w in take[cuts[0][1]:cuts[0][1] + 3]) == "А в Америке"
    quote = said("Главный маячок слова хотя бы один. Видишь хотя бы один, считай наоборот.")
    explain = said("Это 25 тридцать шестых. Значит одна шестерка это 1 минус 25 тридцать шестых.")
    rhetoric = said("С первого класса и с первого класса ненавидят Запад.")
    # возврат к хуку через 18 с без маркеров — развязка, а не сбивка (IMG_3292: «цифры… узбекские» в начале и в конце)
    callback = said("Цифры на самом деле узбекские. " + "раз " * 58 + "Итак, цифры на самом деле узбекские.")
    calm = not any(events.retakes(x) for x in (quote, explain, rhetoric, callback))
    mats = [w for w in ("Блять,", "нихуя", "Пиздец", "хер", "заебал", "сука") if events.is_mat(w)]
    clean = [w for w in ("требует", "хуже", "колебания", "употреблять", "херувим", "сукно") if events.is_mat(w)]
    try:
        prep.keep_bloopers([[10.0, 20.0]], [[30.0, 32.5]])
        outside = False
    except ValueError:
        outside = True
    kept = prep.keep_bloopers([[10.0, 20.0]], [[14.0, 16.5]]) == [(10.0, 14.0), (16.5, 20.0)]
    report.check(retake_ok and calm and len(mats) == 6 and not clean and outside and kept,
                 "события: сбивка с матом режется до последней попытки; цитата, объяснение и риторика — нет; мат по "
                 "началу слова; угар — только внутри выреза",
                 f"сбивка {'да' if retake_ok else 'НЕТ'}, ложных {'нет' if calm else 'ЕСТЬ'}, мат {len(mats)}/6, "
                 f"не мат {clean or 'чисто'}, угар вне выреза {'отказ' if outside else 'ПРОШЁЛ'}, деление {'да' if kept else 'НЕТ'}")

    js = ('      splice(12.500);\n      whip(4.20);\n      slam("#a", 2.00, { rot: -6 });\n      enter(["#b", "#c"], 3.10);\n'
          '      draw("#line", 5.5, 0.3);\n      enter("#d", T + 1);\n'
          '      tl.fromTo("#flash", { opacity: 0 }, { opacity: 0.5, duration: 0.033, ease: "none", immediateRender: false }, 8.967);\n')
    found = montage.page_events(js)
    want = [(2.0, "stamp"), (3.1, "text"), (4.2, "frame"), (5.5, "line"), (9.0, "cut"), (12.5, "cut")]
    report.check(found == want, "тихие звуки монтажа — по движениям страницы (склейка, смена плана, штамп, влёт, линия, "
                 "вход перебивки)", f"{found}")

    with temp_projects(tmp / "ev_projects", "main") as made:
        made["main"].root.joinpath("project.json").write_text(json.dumps(
            {"music": True, "soft_sounds": True, "hook_flash": True}), encoding="utf-8")
        (made["main"].input / "IMG_0700.MOV").write_bytes(b"a")
        bare = '<div id="root" data-duration="60.000">' + verify_page.MONTAGE_MARK
        soft = "".join(f'<audio id="sfx-soft{i}" src="assets/sfx/tap-1.mp3">' for i in range(11))
        missing = verify_page.required_missing(bare, "IMG_0700")
        full = verify_page.required_missing(bare + soft + '<div id="hook-flash">', "IMG_0700")
        excused = verify_page.required_missing(bare + soft + '<meta name="reels-hook" content="без вспышки: x" />', "IMG_0700")
        try:
            music.pool_add("main", [__file__], None)
            refused = False
        except SystemExit:
            refused = True
        refused = refused and not (music.pool_dir("main") / "pool.json").exists()
    report.check(len(missing) == 2 and not full and not excused and refused,
                 "обязательное проекта: без тихих звуков и вспышки хука страница красная; запас музыки без "
                 "указания источника (фонотека YouTube без автора или Mixkit) файл не берёт",
                 f"пустая: {len(missing)} провала, полная: {len(full)}, без вспышки с причиной: {len(excused)}, "
                 f"запас {'отказал' if refused else 'ВЗЯЛ'}")

    # готовый ролик без музыки краснеет по звуку, с подложкой — нет (IMG_3292 v2: музыки нет, заметил только Валера)
    voice = "0.3*sin(2*PI*300*t)*lt(mod(t,2),1)"
    stem = "IMG_0701"
    (tmp / "ev_work" / stem).mkdir(parents=True)
    def tone(path: Path, expr: str):
        subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=8000:d=12",
                        "-c:a", "aac", "-b:a", "96k", str(path)], check=True)
    tone(tmp / "ev_work" / stem / "aroll.mp4", voice)
    tone(tmp / "ev_work" / "with.m4a", voice + "+0.02*sin(2*PI*110*t)")
    tone(tmp / "ev_work" / "without.m4a", voice)
    tone(tmp / "ev_work" / "loud.m4a", voice + "+0.25*sin(2*PI*110*t)")       # музыка вровень с голосом (новоселье v2)
    saved = verify_render.WORK_DIR
    verify_render.WORK_DIR = tmp / "ev_work"
    try:
        with_bed = verify_render.music_bed(tmp / "ev_work" / "with.m4a", stem)
        dry = verify_render.music_bed(tmp / "ev_work" / "without.m4a", stem)
        loud = verify_render.music_bed(tmp / "ev_work" / "loud.m4a", stem)
    finally:
        verify_render.WORK_DIR = saved
    heard = lambda b: (b is not None and b[0] >= verify_render.MUSIC_BED_DB                       # noqa: E731
                       and verify_render.MUSIC_QUIETEST <= b[1] <= verify_render.MUSIC_LOUDEST)
    report.check(heard(with_bed) and not heard(dry) and not heard(loud),
                 "готовый ролик: музыка в паузах речи слышна — без неё красный, вровень с голосом — тоже",
                 f"с подложкой {with_bed and round(with_bed[1], 1)} дБ от речи, без — {dry and round(dry[0], 1)}, "
                 f"громкая — {loud and round(loud[1], 1)} дБ от речи")


def check_sharpness(report: Report, tmp: Path):
    """Чёткость вставок (Валера 23.10.2026: «ниже 720p — лесом автоматом железно, лучше не ниже 1080p»): «p» — по месту
    в кадре, а не по ярлыку файла. Горизонтальный 1080p во весь вертикальный кадр — 608p; 4K — 1080; вертикальный
    720×1280 — 720; мелкая карточка из крупной картинки — 1080. Сток 720p не берётся ни при скачивании, ни при нарезке."""
    from common import QUALITY_FLOOR, sharpness, vertical_crop, ffmpeg_bin
    import stock
    print("\nЧёткость вставок")
    got = {"1080p во весь кадр": sharpness(*vertical_crop(1920, 1080), 1080, 1920),
           "4K во весь кадр": sharpness(*vertical_crop(3840, 2160), 1080, 1920),
           "вертикаль 720×1280": sharpness(720, 1280, 1080, 1920),
           "карточка 300 px из 400": sharpness(400, 400, 300, 300)}
    want = {"1080p во весь кадр": 608, "4K во весь кадр": 1080, "вертикаль 720×1280": 720, "карточка 300 px из 400": 1080}
    report.check(got == want, "«p» вставки — по месту в кадре: горизонталь 1080p в вертикали — 608p, 4K — 1080p",
                 ", ".join(f"{k}: {v}p" for k, v in got.items()))
    stem = "_selfcheck_sharp"
    work = WORK_DIR / stem
    try:
        (work / "broll").mkdir(parents=True, exist_ok=True)
        subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:duration=1",
                        "-pix_fmt", "yuv420p", str(work / "broll" / "low.mp4")], check=True)
        try:
            stock.fit(stem, "low", 0.0, 0.5, 0.5)
            refused = ""
        except stock.StockError as e:
            refused = str(e)
        report.check(f"ниже {QUALITY_FLOOR}p" in refused and not (work / "materials" / "broll-low.mp4").exists(),
                     "сток 720p во весь вертикальный кадр — громкий отказ, а не растянутое мыло", refused[:120] or "взят")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def check_order(report: Report, tmp: Path):
    """Заказ автора — во вход аналитика (23.10.2026, Валера: «результат — тем, чем задумывал его автор»): просьба из
    брифа, фото из материалов с оценкой чёткости (мутное — «не ставь»), референс — только то, что велено из него брать,
    с цифрами замера; цвет и шрифты референса аналитику не идут (это сборка). Фото во весь кадр мутнее 720p — отказ."""
    import json as _json
    import types
    from PIL import Image
    import analyst
    import score as sc
    print("\nЗаказ автора")
    stem, ref = "_selfcheck_order", "_selfcheck_ref"
    work, measured = WORK_DIR / stem, WORK_DIR / "_refs" / f"{ref}.json"
    try:
        (work / "materials").mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1200, 2000), "#777").save(work / "materials" / "good.jpg")
        Image.new("RGB", (400, 300), "#777").save(work / "materials" / "small.jpg")
        (work / "brief.json").write_text(_json.dumps({"notes": "покажи фото с выпускного", "refs": [
            {"ref": ref, "take": ["темп", "шрифты"]}]}, ensure_ascii=False), encoding="utf-8")
        measured.parent.mkdir(exist_ok=True)
        measured.write_text(_json.dumps({"cuts_per_min": 42, "avg_shot": 1.4, "wpm": 170}), encoding="utf-8")
        text = "\n".join(analyst.order(stem, types.SimpleNamespace(references=None)))
        want = {"просьба": "покажи фото с выпускного" in text, "фото годное": "good.jpg: 1200×2000, во весь кадр 1080p" in text,
                "мутное — не ставь": "small.jpg" in text and "не ставь" in text,
                "темп с цифрами": "склеек 42/мин" in text, "шрифты не аналитику": "- шрифты" not in text}
        bad = sc.photo_problems(work / "materials", ["good.jpg", "small.jpg", "нет.jpg"])
        report.check(all(want.values()) and len(bad) == 2 and "ниже 720p" in bad[0],
                     "заказ автора у аналитика: просьба, фото с чёткостью, из референса — только велено; мутное фото — отказ",
                     ", ".join(k for k, v in want.items() if not v) or f"отказы: {bad}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
        measured.unlink(missing_ok=True)


def check_keys(report: Report, tmp: Path):
    """Ключ Pexels — обязательный шаг установки (Валера, 23.10.2026: «ключ как обязалово при настройке репо другим
    человеком»): обе установки его спрашивают, ключ лежит мимо git, без ключа сток — громкий отказ с тем, где взять; в CI
    не спрашивается. Из файлов Pexels берётся самый лёгкий, что даёт 1080p во весь кадр, а мутнее 720p — никакой."""
    import keys
    import stock
    print("\nКлючи сервисов")
    mac = (ROOT / "1 Установка — Mac.command").read_text(encoding="utf-8")
    win = (ROOT / "scripts" / "install_windows.ps1").read_text(encoding="utf-8-sig")
    ignored = "/.keys/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
    report.check("keys.py setup" in mac and "keys.py setup" in win and ignored,
                 "ключ Pexels спрашивают обе установки, а .keys/ не попадает в git",
                 f"Mac: {'да' if 'keys.py setup' in mac else 'нет'}, Windows: {'да' if 'keys.py setup' in win else 'нет'}, "
                 f".gitignore: {'да' if ignored else 'нет'}")
    old_keys, old_env, old_ci = keys.KEYS, os.environ.pop("PEXELS_API_KEY", None), os.environ.get("CI")
    try:
        keys.KEYS = tmp / "keys"
        try:
            keys.require("pexels")
            loud = False
        except keys.KeyMissing as e:
            loud = "pexels.com/api" in str(e)
        keys.save("pexels", "abc123")
        from_file = keys.get("pexels") == "abc123"
        os.environ["CI"] = "true"
        ci_ok = keys.setup() == 0
    finally:
        keys.KEYS = old_keys
        if old_env is not None:
            os.environ["PEXELS_API_KEY"] = old_env
        if old_ci is None:
            os.environ.pop("CI", None)
        else:
            os.environ["CI"] = old_ci
    files = [{"width": 720, "height": 1280, "link": "hd"}, {"width": 1080, "height": 1920, "link": "fhd"},
             {"width": 2160, "height": 3840, "link": "4k"}, {"width": 1920, "height": 1080, "link": "wide"}]
    pick = stock.pexels_pick(files)
    none = stock.pexels_pick([{"width": 1280, "height": 720, "link": "x"}, {"width": 540, "height": 960, "link": "y"}])
    report.check(loud and from_file and ci_ok and pick and pick["link"] == "fhd" and none is None,
                 "без ключа — отказ с тем, где взять; ключ из .keys/; в CI не спрашивается; из Pexels — лёгкий 1080p, мыло — нет",
                 f"отказ: {loud}, из файла: {from_file}, CI: {ci_ok}, выбран: {pick and pick['link']}, мыло: {none}")


def check_score(report: Report):
    """Партитура (scripts/score.py, этап 3, 19.10.2026): годная проходит, а типовые ошибки аналитика ловятся до сборки,
    каждая своим сообщением — его аналитик получает обратно: чужой приём, слово за краем, призыв, после которого
    дольше 3 с без субтитров, вставка поверх призыва, три подряд в одной раскладке, предложение в подписи."""
    import score as sc

    print("\nПартитура")
    words = [{"word": f"слово{i}", "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(40)]      # 20 с речи
    good = {"hook": "auto", "cta": {"w": 36}, "accent": ["слово3"],
            "items": [{"kind": "word", "w": [1, 3], "text": "хук"},
                      {"kind": "write", "w": [8, 12], "layout": "chest", "text": "1 2 3", "sub": "факт"},
                      {"kind": "route", "layout": "behind", "until": 20, "stops": [{"label": "А", "x": 0.1, "y": 0.2, "w": 16},
                                                                                     {"label": "Б", "x": 0.9, "y": 0.2, "w": 18}]},
                      {"kind": "write", "w": [24, 28], "layout": "split", "text": "XVIII", "over": 26, "titlo": True}]}
    bad = {"cta": {"w": 20}, "items": [
        {"kind": "flash", "w": [1, 2]},
        {"kind": "write", "w": [5, 99], "text": "x"},
        {"kind": "write", "w": [10, 11], "layout": "chest", "text": "a"},
        {"kind": "stamp", "w": [13, 13], "text": "b"},
        {"kind": "write", "w": [15, 16], "layout": "chest", "text": "c", "sub": "это целое предложение, а не подпись к числу"},
        {"kind": "write", "w": [30, 32], "layout": "split", "text": "d"}]}
    errs_good, errs_bad = sc.check(good, words), sc.check(bad, words)
    want = {"приёма «flash» нет": "чужой приём", "номер слова 99": "слово за краем", "cta на слове 20": "призыв рано",
            "идёт после призыва": "вставка после призыва", "3 подряд «chest»": "однообразие", "знаков, а в строку": "длинная подпись"}
    missed = [what for key, what in want.items() if not any(key in e for e in errs_bad)]
    report.check(not errs_good and not missed, "партитура: годная проходит, ошибки аналитика ловятся до сборки",
                 f"годная: {'; '.join(errs_good) or 'чисто'}; не поймано: {', '.join(missed) or 'ничего'}")

    # провалы проверки — аналитику словами партитуры, механику правит машина, сборку — не ИИ (23.10.2026: 0 чистых
    # ходов из 15 — аналитик получал одно название проверки и правил вслепую, а баг вёрстки переписывал 6 раз)
    import analyst
    grey = "текст не заезжает в серые зоны площадок (шапка, ник и подпись, кнопки справа)"
    gaps, cut = "субтитры не пропадают дольше 3 с, пока идёт речь", "склейки спрятаны: переход, смена крупности, ничего не висит через рез"
    info = {"details": {grey: ["#s9-timeline «долг = 0» — справа: Instagram обрезает бок, 41.00–44.25 с, глубина 92 px"],
                        gaps: ["23.32–26.84 с: 3.5 с речи без субтитров"],
                        cut: ["склейка 53.47 с: крупность меняется на 0.02 (нужно ≥ 0.1)"]}}
    told = analyst.triage([grey, gaps], info)
    addressed = len(told) == 2 and "items[9] (timeline) «долг = 0»" in told[0] and "3.5 с речи" in told[1]
    try:
        analyst.triage([grey, cut], info)
        stopped = False
    except analyst.BuildBroken as e:
        stopped = "крупность меняется" in str(e)
    score = {"hide": [[2, 3]]}
    dupes = {"res": {"dupes": [{"el": "#s4-write", "text": "331", "cap": "331", "from": 4.0, "last": 4.5}]}}
    fixed = analyst.autofix(words[:5] + [{"word": "331,", "start": 4.2, "end": 4.6}] + words[6:], score, dupes)
    report.check(addressed and stopped and fixed and [5, 5] in score["hide"] and [2, 3] in score["hide"],
                 "провалы проверки: аналитику — номер приёма и подробность; двойной текст прячет машина; "
                 "поломка сборки — стоп без хода ИИ",
                 f"адресно: {'да' if addressed else told}; сборка — стоп: {'да' if stopped else 'нет'}; "
                 f"машина спрятала: {score.get('hide')}")


def check_blueprint(report: Report, tmp: Path):
    """«Чертёж» (scripts/blueprint.py, 19.10.2026): все приёмы складываются в страницу без ошибок и залипаний; в сплите
    проверка лица видит человека в окне листа (движение #stage не выкидывается из прогона); лист во весь кадр — это
    перебивка в доле лица; подпись за головой ловится по одной, а не в общей площади приёма; кривой вызов — отказ."""
    import blueprint as bp
    import fx
    from kit import build_page
    from verify_page import run_timeline

    print("\n«Чертёж»")
    project = tmp / "bp"
    (project / "assets").mkdir(parents=True)
    shutil.copy2(ROOT / "studio" / "_vendor" / "gsap.min.js", project / "assets" / "gsap.min.js")
    (project / "camera.js").write_text("window.CAMERA_FPS = 30;\nwindow.CAMERA = [[0, 0, 1], [0, 0, 1]];\n")
    (project / "captions.js").write_text("window.CAPTIONS = [];\n", encoding="utf-8")
    stage_page_assets(project)
    face = (330.0, 440.0, 750.0, 1060.0)
    geo = bp.split_geometry(face)
    pieces = [bp.route("r", [("а", 0.1, 0.9), ("б", 0.14, 0.3), ("в", 0.86, 0.5)], [0.5, 0.9, 1.3], 2.5, layout="behind"),
              # последняя метка у правого края — выравнивается внутрь (ar); общий .big из kit (left: 0, width: 1080px)
              # растягивал её на кадр, и подпись уезжала за край (IMG_3683, IMG_3684: 6 ходов аналитика впустую)
              bp.timeline("tm", [("IX", "x"), ("XII", "y"), ("133,1−133,1", "третий год")], [3.5, 4.2, 4.8], 5.5,
                          layout="split"),
              bp.write("w", "XVIII", 7.0, 8.5, layout="full", sub="= 18"),
              bp.hexes("hx", 10.0, 11.5, cols=4, rows=2, red=3, label="соты", layout="chest"),
              bp.cuboid("cb", 12.5, 14.0, layout="split"), bp.plot("pl", [0.1, 0.3, 0.8], 15.5, 17.0, mark=1, layout="full"),
              bp.compass("cp", 18.0, 19.5, label="r", center=(0.85, 0.4)), bp.measure("ms", (300, 1250), (300, 1500), "12 см", 20.5, 21.8),
              # подпись прямо за головой — проверка обязана её поймать
              bp.route("hid", [("за головой", 0.5, 0.75), ("сбоку", 0.08, 0.2)], [23.0, 23.5], 25.0, layout="behind"),
              # засечка (IMG_3647): точка обегает окружность, лишнее пересечение гаснет, окружности становятся сферами
              bp.trilat("tri", 26.0, 29.4, [26.0, 26.6, 27.2], 28.2, label="ты", roam=26.4, sphere=28.6)]
    behind, front, sheets, js, windows = [], [], [], [], []
    for p in pieces:
        if p.layout == "behind":
            behind.append(p.html); js.append(p.js); windows.append((p.t0 - 0.05, p.t1 + 0.4))
        elif p.layout == "chest":
            front.append(p.html); js.append(p.js)
        elif p.layout == "full":
            html, j = bp.full_sheet(p, p.t0 - 0.25, p.t1 + 0.35); behind.append(html); js.append(j)
        else:
            html, j = bp.split_parts(p, geo); sheets.append(html); front.append(p.html); js.append(j)
    # картинка 400×225 во весь кадр по ширине (≈400p) — проверка чёткости обязана её поймать по месту в кадре
    from PIL import Image
    Image.new("RGB", (400, 225), "#808080").save(project / "assets" / "low.png")
    behind.append('<img id="sharp-low" class="g" src="assets/low.png" style="left: 0; top: 700px; width: 1080px; height: 608px;">')
    js.append('      tl.set("#sharp-low", { opacity: 1 }, 5.7); tl.set("#sharp-low", { opacity: 0 }, 6.6);')
    page = build_page("чертёж", 30.0, "\n".join(behind), "\n".join(sheets + front), "\n".join(js), [], windows, cta_at=29.9,
                      extra_css=bp.CSS + bp.SPLIT_CSS, cta=False)
    page = fx.FX(stage=True).finalize(page)
    (project / "index.html").write_text(page, encoding="utf-8")
    faces = [[round(k * 0.25, 2), *face] for k in range(int(30 / 0.25))]
    import formats
    res = run_timeline(project / "index.html", faces=faces, zones=formats.grey_zones("9:16"))
    errors = res.get("pageErrors", []) + [w for w in res.get("warnings", []) if "not found" in w or "Invalid" in w]
    stuck = [i["el"] for i in res.get("stuck", []) + res.get("risky", [])]
    edge = [f"{g['el']} «{g['text']}» {g.get('zone') or g.get('where')}" for g in res.get("grey", []) + res.get("spills", [])
            if g["el"].startswith("#tm")]
    report.check(not edge, "«Чертёж»: подпись оси у правого края стоит внутри кадра, а не за обрезкой Instagram",
                 "; ".join(edge) or "")
    import verify_page
    shown = [m for m in res.get("media", []) if m["id"] == "sharp-low"]
    sharp = verify_page.media_sharpness(project, page, shown)
    report.check(bool(shown) and shown[0]["w"] >= 1070 and sharp and sharp[0][2] < 720,
                 "чёткость вставки — по самому крупному показу в кадре: 400×225 во всю ширину ловится как ≈400p",
                 f"показ {shown[0]['w']}×{shown[0]['h'] if shown else '—'}, «p» {sharp[0][2] if sharp else '—'}"
                 if shown else "картинку разбор страницы не увидел")
    split_hits = [h["el"] for h in res.get("faceHits", []) if h["el"].startswith(("#tm", "#cb", "#tri"))]
    hidden = [o["el"] for o in res.get("occluded", [])]
    share = res.get("cutawayShare", 0)
    report.check(res.get("ok") and not errors and not stuck and not split_hits and "#hid-l0" in hidden
                 and not any(h.startswith("#r-") for h in hidden) and 0.05 < share < 0.25,
                 "«Чертёж»: девять приёмов в четырёх раскладках без ошибок и залипаний; в сплите лицо — в окне листа; "
                 "лист во весь кадр — перебивка; подпись за головой ловится по одной",
                 f"ошибок {len(errors)}, залипает {stuck or 'ничего'}, сплит «на лице» {split_hits or 'нет'}, "
                 f"за головой {hidden or 'никто'}, перебивок {share * 100:.0f}%")
    loud = 0
    for bad in (lambda: bp.route("x", [("а", 0, 0)], [1.0, 2.0], 3.0), lambda: bp.write("x", "1", 1.0, 1.3),
                lambda: bp.hexes("x", 1.0, 3.0, layout="сбоку"), lambda: bp.timeline("x", [("a", ""), ("b", "")], [2.0, 1.0], 3.0)):
        try:
            bad()
        except ValueError:
            loud += 1
    report.check(loud == 4, "кривой вызов «Чертежа» — громкая ошибка: времена, длина на экране, раскладка", f"{loud} из 4")


def check_trim(report: Report, tmp: Path):
    """Обрезка готового ролика (scripts/trim.py, 20.10.2026: IMG_3645 v1 открывался полусекундой вдоха): срез в тишине
    даёт ровно столько кадров, сколько осталось, и первый кадр — тот самый кадр исходника; срез по голосу — громкий
    отказ с ближайшими тихими кадрами, а не оборванное слово."""
    import trim as tr
    from common import probe

    print("\nОбрезка готового ролика")
    src, out = tmp / "trim_src.mp4", tmp / "trim_out.mp4"
    subprocess.run([ffmpeg_bin(), "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30:duration=3",
                    "-f", "lavfi", "-i", "aevalsrc=if(gte(t\\,1)\\,0.5*sin(2*PI*440*t)\\,0):s=48000:d=3",
                    *source_codec(), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", str(src)],
                   check=True, capture_output=True)
    done = tr.trim(src, out, 15)
    frames = round(probe(out)["duration"] * 30)

    def frame(path: Path, n: int) -> bytes:
        return subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(path), "-vf", f"select=eq(n\\,{n}),scale=90:160",
                               "-vframes", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    first = frame(out, 0)
    diff = lambda n: sum(abs(p - q) for p, q in zip(frame(src, n), first)) / max(1, len(first))   # noqa: E731
    near = {n: diff(n) for n in (14, 15, 16)}
    report.check(done["frames"] == 75 and frames == 75 and near[15] < min(near[14], near[16]),
                 "срез 15 кадров в тишине: осталось ровно 75 кадров, первый кадр — кадр 15 исходника, не сосед",
                 f"кадров {frames}, отличие от кадров 14/15/16 — " + " / ".join(f"{v:.2f}" for v in near.values()))
    try:
        tr.trim(src, tmp / "trim_bad.mp4", 33)
        refused = ""
    except tr.TrimError as e:
        refused = str(e)
    report.check("режет голос" in refused and not (tmp / "trim_bad.mp4").exists(),
                 "срез по голосу — громкий отказ с ближайшими тихими кадрами, файла нет", refused[:90] or "срезал слово")


class _DesignTake:
    """Сборка для приёмов дизайн-системы без дубля: то же, что Montage даёт приёмам score.py, — слои, js, окна."""

    def __init__(self, system):
        self.design, self.notes = system, []
        self.behind_html, self.front_html, self.beats, self.hidden, self.fgs = [], [], [], [], []

    def behind(self, h): self.behind_html.append(h)        # noqa: E704
    def front(self, h): self.front_html.append(h)          # noqa: E704
    def js(self, j): self.beats.append(j.rstrip("\n") + "\n")   # noqa: E704
    def fg(self, a, b): self.fgs.append((a, b))            # noqa: E704
    def hide(self, a, b): self.hidden.append((a, b))       # noqa: E704
    def punch(self, *a, **k): pass                          # noqa: E704
    def sound(self, *a, **k): pass                          # noqa: E704
    def _face(self, a, b): return (330.0, 440.0, 750.0, 1060.0)   # noqa: E704
    def matte_need(self): return True, "место над головой есть"   # noqa: E704


def check_design(report: Report, tmp: Path):
    """Дизайн-система проекта (projects/<проект>/DESIGN.md, scripts/design.py, 20.10.2026): DESIGN.md Антишколы
    читается, а битый — громко и с местом; приёмы системы (буквы дымом, рукой, число акцентом, список-обещание, ручка,
    маркер субтитров) складываются в страницу без ошибок и залипаний; verify_page ловит цвет и шрифт мимо системы
    (чужой цвет текста, чужой шрифт, чужая линия SVG), а цвета и шрифты системы — нет."""
    import design
    import score as sc
    from kit import build_page
    from verify_page import run_timeline

    print("\nДизайн-система")
    try:
        system = design.Design(ROOT / "presets" / "templates" / "expert-viral" / "DESIGN.md", "antishkola")   # копия системы
        ok = system is not None and len(system.fonts) == len(design.ROLES) and len(system.stops) >= 2
        report.check(ok, "DESIGN.md Антишколы читается: цвета, градиент, шесть ролей шрифтов с кириллицей",
                     ", ".join(f"{r} {f['family']}" for r, f in (system.fonts if system else {}).items()))
    except design.DesignError as e:
        report.check(False, "DESIGN.md Антишколы читается", str(e))
        return
    src = system.path.read_text(encoding="utf-8")
    broken = {"цвет словом": (src.replace('text: "#F2EBDD"', 'text: "кремовый"'), "colors.text"),
              "нет роли": (src.replace("  hand:\n    fontFamily: Caveat", "  scrawl:\n    fontFamily: Caveat", 1), "typography.hand"),
              "нет файла": (src.replace("src: Caveat-Bold.ttf", "src: Nope-Bold.ttf"), "Nope-Bold.ttf"),
              "отскок": (src.replace("enter: expo.out", "enter: back.out(1.7)"), "отскоки"),
              "без шапки": (src.split("---", 2)[2], "нет шапки"),
              "рукопись словом": (src.replace('  text: "#F2EBDD"', '  hand: "жёлтый"\n  text: "#F2EBDD"', 1), "colors.hand")}
    caught = []
    for what, (text, want) in broken.items():
        path = tmp / "ds-broken" / what / "DESIGN.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        try:
            design.Design(path, "broken")
        except design.DesignError as e:
            if want in str(e):
                caught.append(what)
    report.check(len(caught) == len(broken), "битый DESIGN.md — громкая ошибка с местом: цвет словом, нет роли, нет файла "
                 "шрифта, отскок, нет шапки, цвет рукописи словом", f"поймано {len(caught)} из {len(broken)}: {', '.join(caught)}")
    # свой цвет рукописи (colors.hand, «СлаваМонтаж» 22.10.2026): пометка рукой — им, и verify_page его пропускает;
    # без него рукопись — цветом текста, как у Антишколы
    path = tmp / "ds-hand" / "DESIGN.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(src.replace('  text: "#F2EBDD"', '  hand: "#F6EAB0"\n  text: "#F2EBDD"', 1), encoding="utf-8")
    own = design.Design(path, "hand")
    report.check("--ds-hand: #F6EAB0" in own.css() and [246, 234, 176] in own.allowed()["colors"]
                 and f"--ds-hand: {system.colors['text']}" in system.css() and "color: var(--ds-hand)" in system.css(),
                 "свой цвет рукописи из DESIGN.md: пометка рукой им, verify_page его пропускает; нет его — цвет текста")

    # партитура: приёмы системы — с проверкой формы до сборки
    words = [{"word": f"слово{i}", "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(40)]
    good = {"items": [{"kind": "hand", "w": [0, 2], "text": "почему соседняя", "line": True},
                      {"kind": "number", "w": [6, 8], "at": 7, "text": "2/3", "sub": "шанс, что другая быстрее"},
                      {"kind": "promise", "w": [10, 20], "title": "3 причины",
                       "rows": [{"text": "вероятность", "w": 12}, {"text": "память", "w": 15}, {"text": "теория очередей", "w": 18}]},
                      {"kind": "strike", "w": [24, 25], "at": 25, "text": "проклят"}]}
    bad = {"items": [{"kind": "promise", "w": [10, 20], "title": "три причины, почему так бывает всегда",
                      "rows": [{"text": "память", "w": 15}, {"text": "вероятность", "w": 12}, {"text": "лишнее", "w": 30}]},
                     {"kind": "number", "w": [26, 27], "text": "1234567890"}]}
    errs_good, errs_bad = sc.check(good, words), sc.check(bad, words)
    want = {"не позже": "пункты не по порядку", "вне окна списка": "пункт вне окна", "title": "длинный заголовок",
            "items[1] (number).text": "длинное число"}
    missed = [what for key, what in want.items() if not any(key in e for e in errs_bad)]
    report.check(not errs_good and not missed, "партитура системы: hand, number, promise, strike проходят, ошибки ловятся",
                 f"годная: {'; '.join(errs_good) or 'чисто'}; не поймано: {', '.join(missed) or 'ничего'}")

    # страница: все приёмы системы + маркер субтитров + три нарушения, которые проверка обязана поймать
    project = tmp / "ds"
    (project / "assets" / "fonts").mkdir(parents=True)
    shutil.copy2(ROOT / "studio" / "_vendor" / "gsap.min.js", project / "assets" / "gsap.min.js")
    for spec in system.fonts.values():
        shutil.copy2(design.FONT_DIR / spec["src"], project / "assets" / "fonts" / spec["src"])
    (project / "camera.js").write_text("window.CAMERA_FPS = 30;\nwindow.CAMERA = [[0, 0, 1], [0, 0, 1]];\n")
    caps = [{"t0": 0.2, "t1": 1.2, "text": "соседняя", "accent": False}, {"t0": 1.2, "t1": 2.0, "text": "всегда", "accent": True}]
    (project / "captions.js").write_text(f"window.CAPTIONS = {json.dumps(caps, ensure_ascii=False)};\n", encoding="utf-8")
    stage_page_assets(project)
    times = [{"start": t} for t in (5.6, 6.4, 7.2, 8.0)]
    start = lambda i: times[i]["start"]                    # noqa: E731
    end = lambda i: times[i]["start"] + 0.3                # noqa: E731
    m = _DesignTake(system)
    sc._word(m, "w", {"w": [0, 0], "text": "быстрее"}, 2.2, 3.4, 2.2)
    sc._hand(m, "h", {"text": "почему соседняя", "line": True}, 0.2, 1.8)
    sc._number(m, "n", {"text": "2/3", "sub": "шанс, что другая быстрее"}, 3.8, 5.0, 4.0)
    sc._promise(m, "p", {"title": "3 причины", "rows": [{"text": "вероятность", "w": 1}, {"text": "память", "w": 2},
                                                         {"text": "теория очередей", "w": 3}]}, 5.4, 8.6, start, end)
    sc._strike(m, "s", {"text": "проклят"}, 9.0, 10.2, 9.6)
    bad_html = ('        <div id="d-green" class="g" style="left: 245px; top: 1300px; font-family: \'Inter Display\'; '
                'font-size: 60px; color: #00C853;">зелёный</div>\n'
                '        <div id="d-font" class="g" style="left: 245px; top: 1400px; font-family: Montserrat; font-size: 60px; '
                'color: #F2EBDD;">чужой шрифт</div>\n'
                '        <svg id="d-blue" class="g" viewBox="0 0 400 40" style="left: 245px; top: 1500px; width: 400px; height: 40px;">'
                '<path d="M 0 20 H 400" stroke="#3F5FFF" stroke-width="8" fill="none" /></svg>')
    bad_js = "".join(f'      tl.set("#{i}", {{ opacity: 1 }}, 11.0);\n      tl.set("#{i}", {{ opacity: 0 }}, 11.8);\n'
                     for i in ("d-green", "d-font", "d-blue"))
    cap_style = system.captions({"mode": "words", "position": "chest", "color": "#F2EBDD", "highlight": "#FF4A3D",
                                 "animation": "blur", "case": "lower"})
    page = build_page("система", 12.5, "\n".join(m.behind_html), "\n".join([system.defs()] + m.front_html + [bad_html]),
                      system.js() + "".join(m.beats) + bad_js, [], m.fgs, cta_at=12.0, extra_css=system.css(),
                      captions=cap_style, cta=False)
    (project / "index.html").write_text(page, encoding="utf-8")
    res = run_timeline(project / "index.html", design=system.allowed(),
                       faces=[[round(k * 0.25, 2), 330.0, 440.0, 750.0, 1060.0] for k in range(50)])
    errors = res.get("pageErrors", []) + [w for w in res.get("warnings", []) if "not found" in w or "Invalid" in w]
    stuck = [i["el"] for i in res.get("stuck", []) + res.get("risky", [])]
    flagged = sorted({d["el"].split(" ")[0] for d in res.get("design", [])})
    report.check(res.get("ok") and not errors and not stuck, "приёмы системы на странице: буквы дымом и рукой, число "
                 "акцентом, список с квадратами, ручка, маркер субтитров — без ошибок JS и залипаний",
                 f"ошибок {len(errors)}{': ' + errors[0] if errors else ''}, залипает {stuck or 'ничего'}")
    report.check(flagged == ["#d-blue", "#d-font", "#d-green"],
                 "verify_page ловит цвет и шрифт мимо DESIGN.md (чужой цвет текста, шрифт, линия SVG), а систему — нет",
                 "; ".join(f"{d['el']} {d['what']} {d['value']}" for d in res.get("design", [])[:6]) or "ничего не поймано")
    # маркер субтитров открывается на ключевом слове: копия слова на плашке, шторка раскрыта
    probe = probe_page(project, """() => {
      const tl = window.__timelines.main; tl.totalTime(1.7, false);
      const fills = [...document.querySelectorAll("#caps .ds-mk-fill")];
      const ch = getComputedStyle(document.querySelector("#h .ds-ch"));
      return { n: fills.length, text: fills[0] && fills[0].textContent, clip: fills[0] && getComputedStyle(fills[0]).clipPath,
               pad: parseFloat(ch.paddingLeft) / parseFloat(ch.fontSize), shift: parseFloat(ch.marginLeft) + parseFloat(ch.paddingLeft) };
    }""")
    # буква рукописи движется своим слоем: без запаса по бокам Chrome срезает штрих Caveat по ячейке (Валера 20.10.2026,
    # доска: «буквы откусаны слева справа»); поля компенсированы минус-полями — строка не сдвигается
    report.check(probe.get("pad", 0) >= 0.1 and abs(probe.get("shift", 1)) < 0.5,
                 "буквы, которые движутся по одной, — с запасом по бокам (штрих рукописи не срезается), строка на месте",
                 f"запас {probe.get('pad', 0):.2f} em, сдвиг {probe.get('shift', 0):.1f} px")
    report.check(probe.get("n") == 1 and probe.get("text") == "всегда" and "-6%" in str(probe.get("clip", "")).replace(" ", "")
                 and not probe.get("errors"),
                 "маркер субтитров: плашка акцента только у ключевого слова и раскрыта к его середине",
                 f"плашек {probe.get('n')}, текст {probe.get('text')!r}, шторка {probe.get('clip')}, ошибки {probe.get('errors')}")


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
    stage_page_assets(project)
    caps = [{"t0": 0.2, "t1": 1.8, "text": "по центру", "accent": False}]
    (project / "captions.js").write_text("window.CAPTIONS = " + json.dumps(caps, ensure_ascii=False) + ";\n",
                                         encoding="utf-8")
    behind = '        <div id="z-top" class="g big" style="top: 40px; font-size: 200px;">шапка</div>'
    front = ('        <div id="z-right" class="g lead" style="top: 1000px; left: 600px; width: 460px;'
             ' text-align: right; font-size: 60px;">кнопки</div>\n'
             # рамка .lead — во всю ширину и на высоте кнопок, а само слово — по центру: не заезд
             '        <div id="z-ok" class="g lead" style="top: 1000px;">центр</div>\n'
             '        <div id="z-safe" class="g lead" data-safe="стрелка на ник — намеренно"'
             ' style="top: 1700px;">ник</div>\n'
             # data-safe-zones="низ": внизу — осознанно, а за правой обрезкой — заезд (19.10.2026, «Чертёж» на груди)
             '        <div id="z-chest" class="g lead" data-safe="на груди" data-safe-zones="низ"'
             ' style="top: 1700px; left: 700px; width: 600px; text-align: left; white-space: nowrap;">вбок за обрезку справа</div>\n'
             # лента в окне с overflow: hidden: её хвост за окном (и под кнопками справа) не виден — не заезд
             '        <div id="z-tape" class="g" style="left: 300px; top: 800px; width: 400px; height: 90px; overflow: hidden;">'
             '<div class="lead" style="left: 0; width: auto; white-space: nowrap; font-size: 70px;">лента бежит далеко вправо за окно</div></div>')
    beats = "".join(f'      tl.set("#{i}", {{ opacity: 1 }}, 0.2);\n' for i in ("z-top", "z-right", "z-ok", "z-safe", "z-tape", "z-chest"))
    (project / "index.html").write_text(build_page("зоны", 2.0, behind, front, beats, [], [], cta_at=5.0),
                                        encoding="utf-8")
    res = run_timeline(project / "index.html", zones=formats.grey_zones("9:16"))
    grey = {(g["el"], g["zone"].split(":")[0]) for g in res.get("grey", [])}
    allowed = {g["el"] for g in res.get("greyAllowed", [])}
    flagged = {el for el, _ in grey}
    report.check(("#z-top", "верх") in grey and ("#z-right", "справа") in grey
                 and not flagged & {"#z-ok", "#z-safe", "#z-tape"} and not any(el.startswith("субтитр") for el in flagged),
                 "текст в шапке и под кнопками ловится, текст по центру и хвост ленты за краем окна — нет",
                 ", ".join(sorted(f"{el} ({z})" for el, z in grey)) or "ничего не поймано")
    report.check("#z-safe" in allowed, "осознанный заезд (data-safe) идёт отдельным списком, а не ошибкой",
                 ", ".join(sorted(allowed)) or "не найден")
    chest = {g["zone"].split(":")[0] for g in res.get("grey", []) if g["el"] == "#z-chest"}
    chest_ok = {g["zone"].split(":")[0] for g in res.get("greyAllowed", []) if g["el"] == "#z-chest"}
    report.check("справа" in chest and chest_ok == {"низ"},
                 "data-safe-zones: прощён только названный низ, заезд за боковую обрезку — ошибка",
                 f"ошибкой: {sorted(chest) or 'ничего'}, прощено: {sorted(chest_ok) or 'ничего'}")

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
    # ИИ-футаж во весь кадр (kit.footage, 16.10.2026): пока он виден, лица на экране нет — надпись поверх
    # футажа не «на лице». Но футаж не прячет карточку, которая висит на лице и после него
    front4 = ('        <div id="f-cut" class="g footage" style="left: 0; top: 0; width: 1080px; height: 1920px; background: #333;"></div>\n'
              '        <div id="f-on" class="g doc" style="left: 245px; top: 950px; width: 590px; height: 200px;">поверх футажа</div>\n'
              '        <div id="f-after" class="g doc" style="left: 245px; top: 950px; width: 590px; height: 200px;">после футажа</div>')
    beats4 = ('      tl.set("#f-cut", { opacity: 1 }, 0.2); tl.set("#f-cut", { opacity: 0 }, 1.1);\n'
              '      tl.set("#f-on", { opacity: 1 }, 0.2); tl.set("#f-on", { opacity: 0 }, 1.0);\n'
              '      tl.set("#f-after", { opacity: 1 }, 0.2);\n')
    (project / "index.html").write_text(build_page("футаж", 2.0, "", front4, beats4, [], [], cta_at=5.0), encoding="utf-8")
    hit4 = {h["el"] for h in run_timeline(project / "index.html", faces=face).get("faceHits", [])}
    report.check(hit4 == {"#f-after"}, "футаж во весь кадр сменяет план: надпись поверх него не на лице, карточка после — на лице",
                 ", ".join(sorted(hit4)) or "ничего не поймано")
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

    # динамика (Валера 13.10.2026: «плашка про миллион очень долго висела, теряли в динамике»): плашка,
    # простоявшая 7 с без изменений, ловится; та же, в которой каждые 2 с появляется строка, — нет;
    # помеченная data-hold — отдельным списком
    rows = "".join(f'<div id="h-row{i}" style="opacity: 0;">строка {i}</div>' for i in range(4))
    front4 = (f'        <div id="h-static" class="g doc" style="left: 245px; top: 1250px; width: 590px;">висит</div>\n'
              f'        <div id="h-live" class="g doc" style="left: 245px; top: 1450px; width: 590px;">{rows}</div>\n'
              f'        <div id="h-meant" class="g doc" data-hold="формулу надо дочитать" '
              f'style="left: 245px; top: 1050px; width: 590px;">формула</div>\n'
              f'        <div id="h-clip" class="g viz" style="left: 245px; top: 150px; width: 590px; height: 300px;">'
              f'<video class="clip" src="assets/manim/x.mp4" muted data-start="0.2" data-duration="7.2" data-track-index="2"></video></div>')
    beats4 = ("".join(f'      tl.set("#{i}", {{ opacity: 1 }}, 0.2);\n' for i in ("h-static", "h-live", "h-meant", "h-clip"))
              + "".join(f'      tl.set("#h-row{i}", {{ opacity: 1 }}, {0.2 + 2 * i});\n' for i in range(4))
              + "".join(f'      tl.set("#{i}", {{ opacity: 0 }}, 7.4);\n' for i in ("h-static", "h-live", "h-meant", "h-clip")))
    (project / "index.html").write_text(build_page("динамика", 8.0, "", front4, beats4, [], [], cta_at=20.0),
                                        encoding="utf-8")
    res = run_timeline(project / "index.html")
    stale = {h["el"] for h in res.get("holds", [])}
    meant = {h["el"] for h in res.get("holdsAllowed", [])}
    report.check(stale == {"#h-static"} and meant == {"#h-meant"},
                 "плашка, висящая без изменений, ловится; живущая (новая строка раз в 2 с) и доска с идущим клипом — нет; "
                 "data-hold — отдельно",
                 f"висит: {', '.join(sorted(stale)) or 'ничего'}; осознанно: {', '.join(sorted(meant)) or 'ничего'}")

    # текст вылез (Валера 15.10.2026: «"Больше математики" — текст за рамки вылетал»): слово шире своей
    # плашки и надпись за краем кадра ловятся; лента в окне с overflow: hidden, вписанное слово и
    # data-spill — нет. Плашка CTA из kit — та самая, что вылезала на 24 px во всех роликах 14–15.10.
    front5 = ('        <div id="s-wide" class="g pill" style="left: 400px; top: 1300px; width: 200px; white-space: nowrap;">'
              'очень длинное слово</div>\n'
              '        <div id="s-ok" class="g pill" style="left: 245px; top: 1450px; width: 590px;">влезает</div>\n'
              '        <div id="s-edge" class="g lead" style="top: 1600px; left: 700px; width: 600px; text-align: left;">за краем кадра</div>\n'
              '        <div id="s-tape" class="g" style="left: 245px; top: 1100px; width: 300px; height: 80px; overflow: hidden;">'
              '<div style="white-space: nowrap; font-size: 60px; color: #fff;">лента бежит далеко за окно</div></div>\n'
              '        <div id="s-run" class="g lead" data-spill="бегущая строка" style="top: 1000px; left: 600px; width: 900px;'
              ' text-align: left;">3,14159265358979</div>')
    beats5 = "".join(f'      tl.set("#{i}", {{ opacity: 1 }}, 0.2);\n' for i in ("s-wide", "s-ok", "s-edge", "s-tape", "s-run"))
    # ширина букв — настоящими шрифтами: запасной шире Oswald, и CTA вылезала бы только здесь
    (project / "assets" / "fonts").mkdir(exist_ok=True)
    for font in ("Oswald-Bold.ttf", "Manrope-ExtraBold.ttf"):
        shutil.copy2(ROOT / "presets" / "fonts" / font, project / "assets" / "fonts" / font)
    (project / "index.html").write_text(build_page("вылет", 2.0, "", front5, beats5, [], [], cta_at=0.5), encoding="utf-8")
    res = run_timeline(project / "index.html")
    spilled = {s["el"] for s in res.get("spills", [])}
    report.check(spilled == {"#s-wide", "#s-edge"},
                 "текст шире своей плашки и за краем кадра ловится; лента в окне, вписанный текст, data-spill "
                 "и плашка CTA из kit — нет",
                 ", ".join(sorted(spilled)) or "ничего не поймано")


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
    stage_page_assets(project)
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
    # склейки (15.10.2026, «склейки не спрятаны»): надпись через рез и рез без вспышки/смаза ловятся,
    # splice() на странице проходит
    try:
        cross_beats = '      enter("#t-word", 1.0);\n      leave("#t-word", 3.0);\n'
        (project / "index.html").write_text(build_page("проверка", 4.0, behind, "", cross_beats, [], [], cta_at=3.6),
                                            encoding="utf-8")
        bare = run_timeline(project / "index.html", splices=[2.0])["splices"][0]
        (project / "index.html").write_text(build_page("проверка", 4.0, behind, "", 'enter("#t-word", 2.02);\n      splice(2.0);\n',
                                                       [], [], cta_at=3.6), encoding="utf-8")
        hidden = run_timeline(project / "index.html", splices=[2.0])["splices"][0]
    except (RuntimeError, ValueError, KeyError, IndexError) as e:
        report.check(False, "склейки разбираются на странице", str(e)[:200])
    else:
        report.check("#t-word" in bare["across"] and bare["flash"] < 0.3 and bare["blur"] < 4,
                     "надпись через склейку и склейка без перехода ловятся", json.dumps(bare, ensure_ascii=False))
        report.check(not hidden["across"] and hidden["flash"] >= 0.3 and hidden["blur"] >= 4,
                     "splice(): вспышка и смаз на склейке, новое влетает на ней", json.dumps(hidden, ensure_ascii=False))

    old_stuck = {i["el"] for i in old.get("stuck", [])}
    old_risky = {i["el"] for i in old.get("risky", [])}
    report.check(old_entry != page and "субтитр «мы»" in old_stuck and "субтитр «кто»" in old_risky,
                 "старый вход субтитров ловится: «мы» залипает, «кто» — без запаса по кадрам",
                 f"залипает: {', '.join(sorted(old_stuck)) or '—'}; без запаса: {', '.join(sorted(old_risky)) or '—'}")


def probe_page(project: Path, js: str) -> dict:
    """Страница в том же Chrome, что и рендер: свой скрипт после страницы пишет ответ JSON в DOM."""
    from verify_page import find_chrome
    page = (project / "index.html").read_text(encoding="utf-8")
    page = re.sub(r'(<(?:video|audio)\b[^>]*?)\s+src="[^"]*"', r"\1", page)
    page = page.replace("<head>", f'<head>\n<base href="{project.as_uri()}/">\n<script>window.__timelines = {{}}; '
                        'window.__errs = []; window.addEventListener("error", (e) => window.__errs.push(String(e.message)));'
                        '</script>', 1)
    cut = page.rfind("</body>")
    page = page[:cut] + ("<script>(function(){let out;try{out=(" + js + ")();}catch(e){out={crash:String(e)}}"
                         "out.errors=window.__errs;const p=document.createElement('pre');p.id='probe';"
                         "p.textContent=JSON.stringify(out);document.body.appendChild(p);})();</script>\n") + page[cut:]
    wrapper = project / "_probe.html"
    wrapper.write_text(page, encoding="utf-8")
    try:
        res = subprocess.run([find_chrome(), "--headless", "--disable-gpu", "--no-first-run", "--mute-audio",
                              f"--user-data-dir={project / '_profile'}", "--virtual-time-budget=2000", "--dump-dom",
                              wrapper.as_uri()], capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    finally:
        wrapper.unlink(missing_ok=True)
        shutil.rmtree(project / "_profile", ignore_errors=True)
    m = re.search(r'<pre id="probe">(.*?)</pre>', res.stdout, re.S)
    if not m:
        raise RuntimeError(f"Chrome не отдал разбор страницы: {res.stderr.strip()[-200:]}")
    import html as _html
    return json.loads(_html.unescape(m.group(1)))


def check_timeline(report: Report, tmp: Path):
    """Ручные правки монтажной (timeline.py, presets/studio/layers.js).

    Правки человека живут в work/<имя>/timeline.json и ложатся поверх решений агента последними:
    page.py агента director.json перезаписывает. Проверка: наезд и зона без субтитров правятся и
    возвращаются, разметка правится без накопления (дважды = один раз, сняли правку — как было),
    звук сдвигается в атрибутах (HyperFrames читает время звука оттуда, а не из таймлайна —
    замер 16.10.2026), слой сдвигается в таймлайне страницы, двигается и меняет шрифт, цвет и
    текст на кадре; правка, которая разошлась со страницей, — громкая ошибка с текстом.
    """
    import timeline
    from kit import audio, build_page

    print("\nДорожки студии и ручные правки")
    director = {"punches": [[1.0, 2.0, 1.36, 0.1], [3.0, 4.0, 1.36, 0.1]], "hide_captions": [[5.0, 6.0]],
                "text_fixes": {"1": "раз"}}
    edits = timeline.normalize({"camera": {"remove": [[3.0, 4.0]], "add": [[3.5, 4.5, 1.4, 0.1, 0.25]]},
                                "captions": {"hide_add": [[7.0, 8.0]], "hide_remove": [[5.0, 6.0]],
                                             "fixes": {"2": "два"}}})
    d = timeline.apply_director(director, edits)
    report.check(d["punches"] == [[1.0, 2.0, 1.36, 0.1], [3.5, 4.5, 1.4, 0.1, 0.25]]
                 and d["hide_captions"] == [[7.0, 8.0]] and d["text_fixes"] == {"1": "раз", "2": "два"}
                 and director["punches"][1] == [3.0, 4.0, 1.36, 0.1],
                 "правки камеры и субтитров ложатся поверх решений агента, director.json не трогается",
                 json.dumps(d, ensure_ascii=False)[:160])

    project = tmp / "tl-page"
    (project / "assets" / "fonts").mkdir(parents=True)
    shutil.copy2(ROOT / "studio" / "_vendor" / "gsap.min.js", project / "assets" / "gsap.min.js")
    shutil.copy2(timeline.FONT_DIR / "Unbounded-ExtraBold.ttf", project / "assets" / "fonts" / "Unbounded-ExtraBold.ttf")
    (project / "camera.js").write_text("window.CAMERA_FPS = 30;\nwindow.CAMERA = [[0, 0, 1], [0, 0, 1]];\n")
    (project / "captions.js").write_text("window.CAPTIONS = [];\n", encoding="utf-8")
    shutil.copy2(timeline.LAYERS_JS, project / "layers.js")
    behind = '        <div id="t-word" class="g big" style="top: 200px; font-size: 200px;">тест <b>два</b></div>'
    beats = '      enter("#t-word", 1.0);\n      leave("#t-word", 2.0);\n'
    page = build_page("правки", 4.0, behind, "", beats, [audio("boom", "impact-bass-1", 1.2)], [], cta_at=3.5)

    shifted = timeline.normalize({"items": {"t-word": {"shift": 0.5}, "sfx-boom": {"shift": 0.3}}})
    muted = timeline.normalize({"items": {"sfx-boom": {"mute": True}}})
    once = timeline.patch_page(page, shifted)
    twice = timeline.patch_page(once, shifted)
    back = timeline.patch_page(once, {})
    boom = re.search(r'<audio[^>]*id="sfx-boom"[^>]*>', once)
    report.check(once == twice and back == timeline.patch_page(page, {}) and boom
                 and 'data-start="1.500"' in boom.group(0) and 'data-orig-start="1.20"' in boom.group(0),
                 "звук сдвигается в разметке; повторная правка не копится, снятая — возвращает как было",
                 boom.group(0)[:150] if boom else "звука нет на странице")
    hush = re.search(r'<audio[^>]*id="sfx-boom"[^>]*>', timeline.patch_page(page, muted))
    loud = re.search(r'<audio[^>]*id="sfx-boom"[^>]*>', timeline.patch_page(timeline.patch_page(page, muted), {}))
    report.check(hush and 'data-volume="0"' in hush.group(0) and loud and 'data-volume="0"' not in loud.group(0)
                 and "data-orig-volume" not in loud.group(0),
                 "выключенный звук молчит, включённый — с прежней громкостью", (hush.group(0) if hush else "")[:150])
    try:
        timeline.patch_page(page, {"items": {"nope": {"dx": 10}}})
        report.check(False, "правка на слой, которого нет на странице, — громкий отказ", "прошла молча")
    except timeline.EditError as e:
        report.check(True, "правка на слой, которого нет на странице, — громкий отказ", str(e)[:90])

    styled = timeline.normalize({"items": {"t-word": {"shift": 0.5, "dx": 40, "dy": -20, "scale": 1.5,
                                                      "font": "Unbounded-ExtraBold", "color": "#F0352C",
                                                      "texts": ["проба ", "три"]}},
                                 "captions": {"style": {"font": "Unbounded-ExtraBold", "color": "#FFFFFF"}}})
    js = """() => {
      const tl = window.__timelines.main, el = document.getElementById("t-word"), cs = getComputedStyle(el);
      const starts = tl.getChildren(true, true, false).filter((tw) => tw.targets && tw.targets().includes(el)).map((tw) => tw.startTime());
      return { first: Math.min(...starts), translate: el.style.translate, scale: el.style.scale, color: cs.color,
               font: cs.fontFamily, text: el.textContent, capsFont: !!document.getElementById("studio-captions"),
               face: [...document.styleSheets].some((s) => [...s.cssRules].some((r) => r.cssText.includes("Unbounded-ExtraBold.ttf"))) };
    }"""
    try:
        (project / "edits.js").write_text(timeline.edits_js(styled), encoding="utf-8")
        (project / "index.html").write_text(timeline.patch_page(page, styled), encoding="utf-8")
        got = probe_page(project, js)
        stale = timeline.normalize({"items": {"t-word": {"texts": ["один кусок"]}}})
        (project / "edits.js").write_text(timeline.edits_js(stale), encoding="utf-8")
        (project / "index.html").write_text(timeline.patch_page(page, stale), encoding="utf-8")
        bad = probe_page(project, "() => ({})")
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        report.check(False, "страница с правками разбирается в Chrome", str(e)[:200])
        return
    report.check(abs(got.get("first", 0) - 1.5) < 0.01 and not got.get("errors"),
                 "слой сдвигается целиком в таймлайне страницы (+0.5 с)", json.dumps(got, ensure_ascii=False)[:160])
    report.check(got.get("translate") == "40px -20px" and got.get("scale") == "1.5" and got.get("color") == "rgb(240, 53, 44)"
                 and "Студия Unbounded-ExtraBold" in got.get("font", "") and got.get("face")
                 and got.get("text") == "проба три" and got.get("capsFont"),
                 "слой двигается, масштабируется, меняет шрифт, цвет и текст; субтитры — свой шрифт",
                 json.dumps(got, ensure_ascii=False)[:220])
    report.check(any("правки студии" in e and "t-word" in e for e in bad.get("errors", [])),
                 "правка текста, разошедшаяся со страницей, — громкая ошибка с текстом, а не тихий пропуск",
                 "; ".join(bad.get("errors", []))[:140] or "ошибки нет")
    # свой текст на кадре: рисуется на странице, входит и уходит движением; кривой — не проходит
    ut = timeline.merge_text({**timeline.TEXT_DEFAULT, "id": "t1", "t0": 0.5, "t1": 1.8, "x": 540, "y": 330, "text": "x"},
                             {"text": "мой текст", "font": "Unbounded-ExtraBold"}, 4.0, 1080, 1920)
    try:
        withtext = timeline.normalize({"texts": [ut]})
        (project / "edits.js").write_text(timeline.edits_js(withtext), encoding="utf-8")
        (project / "index.html").write_text(timeline.patch_page(page, withtext), encoding="utf-8")
        ut_got = probe_page(project, """() => { const tl = window.__timelines.main, el = document.getElementById("ut-t1");
          if (!el) return { missing: true };
          tl.seek(1.0); const mid = getComputedStyle(el).opacity; tl.seek(1.9); const after = getComputedStyle(el).opacity;
          return { text: el.textContent, mid, after, font: getComputedStyle(el).fontFamily, front: el.parentElement.id }; }""")
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        ut_got = {"crash": str(e)[:150]}
    report.check(ut_got.get("text") == "мой текст" and ut_got.get("mid") == "1" and ut_got.get("after") == "0"
                 and "Unbounded" in ut_got.get("font", "") and ut_got.get("front") == "front" and not ut_got.get("errors"),
                 "свой текст встаёт на кадр, виден в своё время и уходит", json.dumps(ut_got, ensure_ascii=False)[:180])
    for change, why in (({"text": "  "}, "пустой текст"), ({"text": "я" * 161}, "текст длиннее 160 знаков"),
                        ({"t1": 0.7}, "текст короче полсекунды"), ({"anim": "glitch"}, "неизвестная анимация")):
        try:
            timeline.merge_text(ut, change, 4.0, 1080, 1920)
            report.check(False, f"кривой текст на кадре не проходит: {why}", "прошёл")
        except timeline.EditError as e:
            report.check(True, f"кривой текст на кадре не проходит: {why}", str(e)[:60])
    # айфон: несколько записей метаданных, поворот — во второй; пустая третья его не затирает
    import studio_api
    dims = studio_api.stream_dims({"width": 3840, "height": 2160, "side_data_list": [{}, {"rotation": -90}, {}]})
    report.check(dims == (2160, 3840), "студия видит вертикальное видео айфона вертикальным (поворот из метаданных)",
                 f"{dims[0]}×{dims[1]}")
    # индикатор «ИИ монтирует»: сервер говорит, какой ролик и что агент делает сейчас; закончившийся ход не виден
    saved_runs = dict(studio_api.runs)
    studio_api.runs.clear()
    studio_api.runs.update({
        "a": {"events": [{"type": "tool", "name": "Read", "summary": "x"}, {"type": "tool", "name": "Bash", "summary": "render_reel"}],
              "done": False, "started": time.time() - 65, "stem": "IMG_0001"},
        "b": {"events": [], "done": True, "started": time.time(), "stem": "IMG_0002"}})
    try:
        view = studio_api.brain_view()
    finally:
        studio_api.runs.clear(); studio_api.runs.update(saved_runs)
    report.check(len(view) == 1 and view[0]["stem"] == "IMG_0001" and view[0]["doing"]["summary"] == "render_reel"
                 and view[0]["actions"] == 2 and 64 <= view[0]["elapsed"] <= 70,
                 "студия видит идущий ИИ-монтаж: ролик, время, текущее действие", str(view))
    good = timeline.merge_caption_style({}, {"font": "Unbounded-ExtraBold", "color": "#ffffff", "scale": 1.2})
    layer = timeline.merge_item_style({"dx": 10}, {"dx": None, "scale": 1, "color": "#f0352c"})
    report.check(good == {"font": "Unbounded-ExtraBold", "color": "#FFFFFF", "scale": 1.2} and layer == {"color": "#F0352C"},
                 "правка вида принимается; пустое значение и масштаб 1 снимают свойство",
                 json.dumps([good, layer], ensure_ascii=False))
    for merge, change, why in ((timeline.merge_caption_style, {"color": "red"}, "цвет субтитров не #RRGGBB"),
                               (timeline.merge_caption_style, {"font": "Comic-Sans"}, "шрифта субтитров нет"),
                               (timeline.merge_item_style, {"scale": 9}, "масштаб слоя 9"),
                               (timeline.merge_item_style, {"blur": 3}, "неизвестное свойство слоя")):
        try:
            merge({}, change)
            report.check(False, f"кривая правка вида не проходит: {why}", "прошла")
        except timeline.EditError as e:
            report.check(True, f"кривая правка вида не проходит: {why}", str(e)[:60])


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

    # вещь в руке не «паркуется» в пустую комнату (IMG_1803, 12–13.10: микрофон на банке модель порой
    # уверенно звала фоном, банка стояла на привычном месте — и микрофон попадал в комнату: на месте
    # вырезался как фон, уходил — оставлял дыру; Валера: «то вырезан, то не вырезан»). Тёмный микрофон
    # стоит у кисти в 60% кадров выборки, модель уверена, что он фон; в остальных рука с ним в другом месте
    spot = (xx >= 60) & (xx < 110) & (yy >= 300) & (yy < 360)
    frames, sure = [], []
    for i in range(20):
        parked = i % 5 < 3
        hand_at = hand if parked else (xx >= 400) & (xx < 455) & (yy >= 600) & (yy < 660)
        mic_at = spot if parked else (xx >= 420) & (xx < 470) & (yy >= 500) & (yy < 560)
        shot = folds.copy()
        shot[body <= 1] = (0.10, 0.10, 0.12)
        shot[hand_at] = (0.80, 0.60, 0.50)
        shot[mic_at] = (0.05, 0.05, 0.05)
        background = np.full((h, w), 0.97, np.float32)
        background[(body <= 1) | hand_at] = 0.05                       # микрофон модель считает фоном
        frames.append((shot * 255).astype(np.uint8))
        sure.append(matte.room_mask(background, hand_at))
    parked_plate, _ = matte.build_plate(np.stack(frames), np.stack(sure))
    ghost = parked_plate is not None and bool(
        ((parked_plate.weight[spot] > 0.5) & (np.abs(parked_plate.image[spot] - folds[spot]).max(axis=1) > 0.1)).any())
    report.check(parked_plate is not None and not ghost,
                 "вещь в руке не паркуется в пустую комнату: за кистью комната — из кадров, где руки в другом месте",
                 "призрак микрофона в комнате" if ghost else "на месте микрофона — занавес или «неизвестно»")

    # кисти — кожа без шеи и мелких пятен; второй взгляд — квадрат у кисти, у края кадра без среза
    skin, face = np.zeros((h, w), np.float32), np.zeros((h, w), np.float32)
    face[150:335, 240:360] = 0.9
    skin[330:400, 270:330] = 0.9                                        # шея касается лица
    skin[600:680, 0:60] = 0.9                                           # кисть у левого края кадра
    skin[620:700, 430:490] = 0.9
    skin[800:803, 300:303] = 0.9                                        # пятнышко — не кисть
    hands = matte.hands_mask(skin, face)
    boxes = matte.hand_boxes(hands)
    left = next((b for b in boxes if b[0] == 0), None)
    edge_full = left is not None and float(matte.zoom_feather(*left, w, h)[left[2] // 2, 0]) == 1.0
    inner_fades = left is not None and float(matte.zoom_feather(*left, w, h)[left[2] // 2, -1]) < 0.05
    covers = left is not None and left[1] < 600 - left[2] * 0.3 and left[1] + left[2] >= 680
    report.check(bool(hands[640, 30]) and bool(hands[660, 460]) and not hands[360, 300] and not hands[801, 301]
                 and len(boxes) == 2 and edge_full and inner_fades and covers,
                 "кисти без шеи; крупный второй взгляд у кисти, у края кадра без прямоугольного среза",
                 f"квадратов {len(boxes)}, у края кадра вес {'полный' if edge_full else 'гаснет'}")


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

    # вырезка в цветах дубля (19.10.2026, Валера: «то я одного цвета, то другого»): метка bt709 на выходе при сырых
    # кадрах без меток — и ffmpeg 8 пересчитывал их как bt601, кожа в вырезке темнела на 2–3 уровня. На сером
    # источнике пересчёт не виден — поэтому цветной, тон кожи
    skin = tmp / "cutout_skin.mp4"
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0xD29882:s=1080x1920:r=30:d=1",
                    "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
                    "-color_trc", "bt709", "-color_range", "tv", str(skin)], check=True, capture_output=True)
    cut = matte.make_cutout(skin, mask, tmp / "cutout_skin.webm")

    def planes(args: list, alpha: bool) -> np.ndarray:
        n = 1080 * 1920
        raw = subprocess.run([ffmpeg_bin(), "-v", "error", *args, "-frames:v", "1", "-pix_fmt",
                              "yuva420p" if alpha else "yuv420p", "-f", "rawvideo", "-"], capture_output=True).stdout
        return np.frombuffer(raw, np.uint8)[:n * 3 // 2].astype(float)

    a, b = planes(["-c:v", "libvpx-vp9", "-i", str(cut)], True), planes(["-i", str(skin)], False)
    n = 1080 * 1920
    inside = (slice(900 * 1080 + 440, 900 * 1080 + 640), slice(n + 450 * 540 + 220, n + 450 * 540 + 320),
              slice(n * 5 // 4 + 450 * 540 + 220, n * 5 // 4 + 450 * 540 + 320))      # Y, U, V в середине круга маски
    shift = [round(float((a[s] - b[s]).mean()), 2) for s in inside]
    report.check(all(abs(d) < 1 for d in shift), "вырезка в цветах дубля: на коже Y, U, V совпадают (без пересчёта матрицы)",
                 f"сдвиг Y {shift[0]}, U {shift[1]}, V {shift[2]}")


def check_matte_windows(report: Report, tmp: Path):
    """Маска — только там, где её видно (22.10.2026, Валера: «вырезка самое долгое из всего процесса, мб ИИ будет
    определять кусочки, где надо вырезать, и там вырезать?»; про IMG_0930: «за головой у человека нет места»).

    Модель здесь — подделка: она читает номер кадра, нарисованный в самом кадре, и отдаёт его альфой. Так видно сразу
    три вещи: какие кадры модель вообще смотрела (только окна и разогрев), что альфа кадра j стоит в кадре j вырезки
    (22.10.2026 кусок IMG_3647 съехал на кадр: после -ss ffmpeg дублировал первый кадр — так делает файл со звуком,
    поэтому здесь звук есть и ключевой кадр, как у дубля, раз в 12) и что вне окон вырезка прозрачная.
    """
    import kit
    import matte
    import verify_page

    print("\nМаска только по окнам")
    W, H, N = 320, 576, 120

    def frame(k: int) -> bytes:                       # номер кадра — семь полос-битов
        img = np.full((H, W), 40, np.uint8)
        for b in range(7):
            if k >> b & 1:
                img[:, b * 40:(b + 1) * 40] = 215
        return img.tobytes()

    def number(f: np.ndarray) -> int:
        return sum(1 << b for b in range(7) if f[H // 2, b * 40 + 20] > 128)

    def level(k: int) -> int:                         # альфа кадра k: шаг 6 на кадр — сдвиг на кадр не спрячется в допуск
        return 30 + 6 * (k % 35)

    take = tmp / "mw" / "work" / "_sc_matte" / "aroll.mp4"
    take.parent.mkdir(parents=True)
    enc = subprocess.Popen([ffmpeg_bin(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
                            "-r", "30", "-i", "-", "-f", "lavfi", "-i", "sine=d=4", *source_codec(), "-g", "12", "-bf", "0",
                            "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-shortest", str(take)], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for k in range(N):
        enc.stdin.write(frame(k))
    enc.stdin.close()
    enc.wait()

    class Numbered:
        seen = []

        def __init__(self, width: int, height: int):
            self.width, self.height = width, height

        def __call__(self, rgba: bytes) -> np.ndarray:
            k = number(np.frombuffer(rgba, np.uint8).reshape(self.height, self.width, 4)[..., 0])
            Numbered.seen.append(k)
            return np.full((self.height, self.width), level(k), np.uint8)

    def alphas(path: Path) -> list:
        raw = subprocess.run([ffmpeg_bin(), "-v", "error", "-c:v", "libvpx-vp9", "-i", str(path), "-pix_fmt", "yuva420p",
                              "-f", "rawvideo", "-"], capture_output=True).stdout
        size = W * H * 5 // 2
        return [int(raw[i * size + W * H * 3 // 2 + (H // 2) * W + W // 2]) for i in range(len(raw) // size)]

    matte.BACKENDS["numbered"] = Numbered
    try:
        ranges = matte.frame_ranges([(1.0, 1.3), (2.6, 2.8)], 30, N)
        cut = matte.cut_windows(take, [(1.0, 1.3), (2.6, 2.8)], "numbered")
        seen, Numbered.seen = Numbered.seen, []
        allowed = {k for f0, f1 in ranges for k in range(max(0, f0 - matte.WARM), f1)}
        want = sum(f1 - f0 + min(matte.WARM, f0) for f0, f1 in ranges)
        got = alphas(take.with_name("aroll.cutout.webm"))
        inside = {k for f0, f1 in ranges for k in range(f0, f1)}
        off = [k for k, a in enumerate(got) if (abs(a - level(k)) > 2 if k in inside else a > 2)]
        report.check(set(seen) <= allowed and len(seen) == want and cut["ranges"] == ranges,
                     "модель смотрит только окна вырезки (с запасом 0,5 с и разогревом), не весь дубль",
                     f"окна {ranges}: модель видела {len(seen)} кадров из {N} (ждали {want}), "
                     f"лишние: {sorted(set(seen) - allowed)[:6] or 'нет'}")
        report.check(len(got) == N and not off,
                     "вырезка во всю длину дубля: в окне альфа кадра j — в кадре j, вне окон прозрачно",
                     f"кадров {len(got)} из {N}; не на месте: "
                     + (", ".join(f"{k}: {got[k]}" for k in off[:6]) or "нет"))

        matte.cut_windows(take, [(1.0, 1.3), (2.6, 3.2)], "numbered")      # окно сдвинули — досчитать новое
        grown, Numbered.seen = Numbered.seen, []
        again = alphas(take.with_name("aroll.cutout.webm"))
        new = matte.frame_ranges([(1.0, 1.3), (2.6, 3.2)], 30, N)
        inside = {k for f0, f1 in new for k in range(f0, f1)}
        off = [k for k, a in enumerate(again) if (abs(a - level(k)) > 2 if k in inside else a > 2)]
        added = new[-1][1] - ranges[-1][1]
        pieces = sorted(p.name for p in take.with_name("aroll.pieces").iterdir())
        report.check(len(grown) == added + matte.WARM and not off and len(pieces) == 2 * len(new),
                     "окно сдвинули — досчитывается только новый край, куски сливаются",
                     f"досчитано {len(grown)} кадров (ждали {added + matte.WARM}), не на месте: {off[:4] or 'нет'}, "
                     f"куски: {', '.join(pieces)}")
    finally:
        matte.BACKENDS.pop("numbered", None)

    # окон нет — маска не считается вовсе: ни модели, ни вырезки, решение записано
    bare = tmp / "mw" / "work" / "_sc_matte_nowin" / "aroll.mp4"
    bare.parent.mkdir(parents=True)
    shutil.copy2(take, bare)
    run = subprocess.run([sys.executable, str(ROOT / "scripts" / "matte.py"), str(bare), "--windows", "page",
                          "--backend", "mediapipe"], capture_output=True, encoding="utf-8", errors="replace", cwd=ROOT)
    record = json.loads(bare.with_name("aroll.cutout.json").read_text(encoding="utf-8")) \
        if bare.with_name("aroll.cutout.json").exists() else {}
    made = sorted(p.name for p in bare.parent.iterdir() if p.name != "aroll.mp4" and p.name != "aroll.cutout.json")
    report.check(run.returncode == 0 and not made and record.get("ranges") == [] and record.get("skipped"),
                 "окон «человек поверх» на странице нет — маска не считается, решение записано",
                 f"код {run.returncode}, лишние файлы: {', '.join(made) or 'нет'}, запись: {record.get('skipped')!r}"
                 + (f"\n      {run.stderr.strip()[-300:]}" if run.returncode else ""))

    # нужна ли маска вообще — по месту над головой (IMG_0930: волосы у верхнего края) до счёта и до страницы
    full = [(0.25 * k, 230.0, 277.0, 930.0, 1208.0) for k in range(40)]    # как IMG_0930
    usual = [(0.25 * k, 315.0, 510.0, 765.0, 1099.0) for k in range(40)]   # как IMG_3647 — текст за спиной встаёт
    low, high = matte.head_room(full), matte.head_room(usual)
    report.check(low is not None and high is not None and low < matte.HEAD_ROOM_MIN <= high,
                 "голова во весь кадр — маска не нужна; голова пониже — нужна (по месту над головой)",
                 f"во весь кадр — {low:.0f} px свободных строк, обычно — {high:.0f} px (порог {matte.HEAD_ROOM_MIN})")

    # страница без окон — без слоя вырезки (маску не просит); с окнами — слой есть
    no_layer = 'id="cutout"' not in build_page_safe(kit, "", "", "", [])
    layer = 'id="cutout"' in build_page_safe(kit, "", "", "", [(0.2, 1.0)])
    report.check(no_layer and layer, "страница без окон вырезки — без слоя человека; с окнами — со слоем",
                 f"без окон слоя {'нет' if no_layer else 'есть'}, с окнами {'есть' if layer else 'нет'}")

    # человек поверх, а маски под ним нет — громкий отказ verify_page (черновик до маски — только пометка)
    project = tmp / "mw" / "fgpage"
    (project / "assets").mkdir(parents=True)
    shutil.copy2(ROOT / "studio" / "_vendor" / "gsap.min.js", project / "assets" / "gsap.min.js")
    (project / "camera.js").write_text("window.CAMERA_FPS = 30;\nwindow.CAMERA = [[0, 0, 1], [0, 0, 1]];\n")
    (project / "captions.js").write_text("window.CAPTIONS = [];\n", encoding="utf-8")
    stage_page_assets(project)
    (project / "index.html").write_text(build_page_safe(kit, "", "", "", [(0.2, 1.0)]), encoding="utf-8")
    title = "под каждым окном «человек поверх» посчитана маска"
    states = {}
    for name, record in (("нет вырезки", None), ("маска на окне", {"fps": 30, "ranges": [[0, 45]]}),
                         ("маска мимо окна", {"fps": 30, "ranges": [[15, 45]]}), ("вся длина", "full")):
        (project / "assets" / "cutout.webm").unlink(missing_ok=True)
        (project / "assets" / "cutout.json").unlink(missing_ok=True)
        if record is not None:
            shutil.copy2(take.with_name("aroll.cutout.webm"), project / "assets" / "cutout.webm")
            if record != "full":
                (project / "assets" / "cutout.json").write_text(json.dumps(record), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            states[name] = title in verify_page.verify(str(project), strict=False)
    with contextlib.redirect_stdout(io.StringIO()):
        (project / "assets" / "cutout.webm").unlink()
        pending = title in verify_page.verify(str(project), strict=False, matte_pending=True)
    want = {"нет вырезки": True, "маска на окне": False, "маска мимо окна": True, "вся длина": False}
    report.check(states == want and not pending,
                 "окно «человек поверх» без маски под ним — провал verify_page; черновик до маски — пометка",
                 ", ".join(f"{k}: {'провал' if v else 'чисто'}" for k, v in states.items())
                 + f"; черновик: {'провал' if pending else 'пометка'}")

    # порядок автопилота: маска — после страницы (аналитика), не в подготовке
    import autopilot
    import inspect
    flow, prep = inspect.getsource(autopilot.run), inspect.getsource(autopilot.prepare)
    after = "analyst.run(" in flow and "cut_on_windows(" in flow and flow.index("analyst.run(") < flow.index("cut_on_windows(")
    report.check(after and "matte" not in prep, "автопилот считает маску после страницы и по её окнам, не до аналитика",
                 f"после аналитика: {'да' if after else 'нет'}, маска в подготовке: {'да' if 'matte' in prep else 'нет'}")


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
    С 16.10.2026 ролики идут разом (parallel=2): ходы обоих идут одновременно, а задачи очереди
    каждый получает свои — по имени ролика. Ролик проекта без анкеты не монтируется — «нужен человек».
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
        return [sys.executable, "-c", f"import time; print({event!r}, flush=True); time.sleep(0.6)"]

    def fake_runner():                    # «обработчик»: всё, что ждёт, сразу выполнено
        (queue / "done").mkdir(parents=True, exist_ok=True)
        for job in jobqueue.job_files(queue):
            job.replace(queue / "done" / job.name)
        return True

    saved = (brain.THREADS, brain.command, studio_api.QUEUE, studio_api.ensure_runner)
    brain.THREADS, brain.command = tmp / "batch_threads", fake_agent
    studio_api.QUEUE, studio_api.ensure_runner = queue, fake_runner
    studio_api.batch.update(running=False, items=[])
    items, threads, together = [], [], 0
    try:
        with temp_projects(tmp / "batch_projects", "main", "fresh") as made, \
                TestClient(app, base_url="http://127.0.0.1:8765") as live:
            projects_mod = sys.modules["projects"]
            projects_mod.save_setup(made["main"], READY_ANSWERS)    # «fresh» — без анкеты
            for stem in ("РОЛИК_А", "РОЛИК_Б"):        # ролик вне проектов пачка не берёт — громко
                (made["main"].input / f"{stem}.MOV").write_bytes(b"v")
            (made["fresh"].input / "РОЛИК_В.MOV").write_bytes(b"v")
            live.post("/api/brain/batch", json={"stems": ["РОЛИК_А", "РОЛИК_Б", "РОЛИК_В"], "engine": "claude",
                                                "parallel": 2, "how": "brain"},
                      headers={"X-Studio-Token": TOKEN})
            for _ in range(200):
                time.sleep(0.05)
                together = max(together, len(studio_api.running_threads()))
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
    own = all(f"20-prep-{t['stem']}" in t["messages"][2]["text"] and
              not any(f"20-prep-{o['stem']}" in t["messages"][2]["text"] for o in threads if o is not t)
              for t in threads if len(t["messages"]) > 2)
    report.check([i["status"] for i in items[:2]] == ["done", "done"] and len(ids) == 2 and resumed
                 and all(t["stem"] == i["stem"] for t, i in zip(threads, items)),
                 "пачка: у каждого ролика своя сессия, после очереди разговор продолжается сам",
                 "; ".join(f"{i['stem']}: {i['status']}" for i in items) or "пачка не прошла")
    report.check(together == 2 and own, "пачка разом: два ролика монтируются одновременно, задачи очереди — каждому свои",
                 f"одновременно {together}, свои задачи: {'да' if own else 'НЕТ — перепутались'}")
    report.check(len(items) == 3 and items[2]["status"] == "needs_human" and "не настроен" in items[2]["note"]
                 and not items[2].get("thread"),
                 "ролик проекта без анкеты пачка не монтирует — «нужен человек», сессия не тратится",
                 f"{items[2]['status']}: {items[2]['note'][:60]}" if len(items) > 2 else "нет третьего ролика")

    # автопилотом (по умолчанию с 19.10.2026): итог ролика — по коду выхода autopilot.py (0 готово, 3 нужен человек,
    # иначе не вышло), ход — строками его вывода; ИИ и очередь не трогаются: команда подставная
    fake = tmp / "fake_autopilot.py"
    fake.write_text("import sys\nstem = sys.argv[1]\nprint('▶ автопилот', stem)\nprint('  → очередь: 20-prep-' + stem)\n"
                    "code = {'РОЛИК_А': 0, 'РОЛИК_Б': 3}.get(stem, 1)\n"
                    "print(('✓ ' if code == 0 else '✗ ') + stem + (': готов' if code == 0 else ': нужен человек — брак' if code == 3 "
                    "else ': упал'))\nsys.exit(code)\n", encoding="utf-8")
    saved_ap = (studio_api.AUTOPILOT_CMD, studio_api.AUTOPILOT_LOGS)
    studio_api.AUTOPILOT_CMD = lambda stem: [sys.executable, str(fake), stem]
    studio_api.AUTOPILOT_LOGS = tmp / "autopilot_logs"
    studio_api.batch.update(running=False, items=[])
    auto = []
    try:
        with temp_projects(tmp / "auto_projects", "main") as made, TestClient(app, base_url="http://127.0.0.1:8765") as live:
            sys.modules["projects"].save_setup(made["main"], READY_ANSWERS)
            for stem in ("РОЛИК_А", "РОЛИК_Б", "РОЛИК_Г"):
                (made["main"].input / f"{stem}.MOV").write_bytes(b"v")
            live.post("/api/brain/batch", json={"stems": ["РОЛИК_А", "РОЛИК_Б", "РОЛИК_Г"], "engine": "claude", "parallel": 2},
                      headers={"X-Studio-Token": TOKEN})
            for _ in range(200):
                time.sleep(0.05)
                if not studio_api.batch["running"]:
                    break
            auto = [dict(i) for i in studio_api.batch["items"]]
    finally:
        studio_api.AUTOPILOT_CMD, studio_api.AUTOPILOT_LOGS = saved_ap
        studio_api.batch.update(running=False, items=[])
        (studio_api.WORK_DIR / "_studio" / "batch.json").unlink(missing_ok=True)
    logged = (tmp / "autopilot_logs" / "РОЛИК_А" / "autopilot.log").exists()
    report.check([i["status"] for i in auto] == ["done", "needs_human", "failed"] and logged
                 and "брак" in auto[1]["note"] and not any(i.get("thread") for i in auto),
                 "пачка автопилотом: готово, нужен человек и «не вышло» — по коду выхода, ход — в логе, сессий мозга нет",
                 "; ".join(f"{i['stem']}: {i['status']} ({i['note'][:40]})" for i in auto) or "пачка не прошла")

    # догрузка (21.10.2026): видео закидывали по одному «сразу в монтаж», и все, кроме первого, отбивались «пачка уже
    # идёт». Догруженный ролик начинается сразу — в своём процессе, мимо parallel пачки; пятый — громкий отказ
    slow = tmp / "slow_autopilot.py"
    slow.write_text("import sys, time\nprint('▶ автопилот', sys.argv[1], flush=True)\ntime.sleep(1.5)\n"
                    "print('✓ ' + sys.argv[1] + ': готов')\n", encoding="utf-8")
    studio_api.AUTOPILOT_CMD = lambda stem: [sys.executable, str(slow), stem]
    studio_api.AUTOPILOT_LOGS = tmp / "autopilot_logs"
    studio_api.batch.update(running=False, items=[])
    names = ("РОЛИК_А", "РОЛИК_Б", "РОЛИК_В", "РОЛИК_Г", "РОЛИК_Д")
    codes, extra, peak, late = {}, [], 0, []
    try:
        with temp_projects(tmp / "more_projects", "main") as made, TestClient(app, base_url="http://127.0.0.1:8765") as live:
            sys.modules["projects"].save_setup(made["main"], READY_ANSWERS)
            for stem in names:
                (made["main"].input / f"{stem}.MOV").write_bytes(b"v")

            def start(stem):
                r = live.post("/api/brain/batch", json={"stems": [stem], "engine": "claude", "parallel": 1},
                              headers={"X-Studio-Token": TOKEN})
                return r.status_code, r.json()

            for stem in names:
                codes[stem] = start(stem)
            codes["повтор"] = start("РОЛИК_Б")
            for _ in range(200):
                time.sleep(0.05)
                peak = max(peak, len(studio_api.batch["procs"]))
                if not studio_api.batch["running"]:
                    break
            extra = [dict(i) for i in studio_api.batch["items"]]
            late = start("РОЛИК_Д")          # места освободились — пятый идёт
            for _ in range(200):
                time.sleep(0.05)
                if not studio_api.batch["running"]:
                    break
            late = (late[0], [dict(i) for i in studio_api.batch["items"]])
    finally:
        studio_api.AUTOPILOT_CMD, studio_api.AUTOPILOT_LOGS = saved_ap
        studio_api.batch.update(running=False, items=[])
        (studio_api.WORK_DIR / "_studio" / "batch.json").unlink(missing_ok=True)
    took = [s for s in names[:4] if codes.get(s, (0,))[0] == 200]
    full = codes.get("РОЛИК_Д", (0, {}))
    again = codes.get("повтор", (0, {}))
    report.check(len(took) == 4 and peak == 4 and [i["status"] for i in extra] == ["done"] * 4
                 and full[0] == 409 and "уже 4 ролика" in str(full[1]) and again[0] == 409
                 and late and late[0] == 200 and [i["status"] for i in late[1]] == ["done"],
                 "догрузка: ролик, закинутый во время пачки, монтируется сразу рядом; пятый разом — отказ, не ожидание",
                 f"пошли сразу {len(took)} из 4, разом {peak}, пятый: {full[0]}, повтор: {again[0]}, "
                 f"после освобождения: {late[0] if late else '—'}")
    # ролик пачки, ждущий своей очереди (queued без now), — не в счёт и не ошибка: 22.10.2026 повторный
    # batch.py во время пачки из двух роликов получал 500 (сумма bool и None), а не отказ
    saved_batch = dict(studio_api.batch)
    try:
        studio_api.batch.update(running=True, items=[{"stem": "А", "status": "working"}, {"stem": "Б", "status": "queued"}])
        busy = studio_api.montage_busy() - len(studio_api.running_threads())
    except TypeError as e:
        busy = f"падает: {e}"
    finally:
        studio_api.batch.clear()
        studio_api.batch.update(saved_batch)
    report.check(busy == 1, "ждущий очереди ролик пачки не считается монтирующимся и не роняет подсчёт", f"занято {busy}")


def check_ai_workflow(report: Report, tmp: Path):
    """ИИ-монтаж, 16.10.2026: тяжёлое агентом — только через очередь; дописанное по ходу доходит до агента;
    разросшийся разговор ролика продолжается свежей сессией; проект без анкеты не монтируется; материалы
    ролика видны с происхождением; оценки времени шагов берутся из замеров очереди."""
    from fastapi.testclient import TestClient
    import brain
    import jobqueue
    import kit
    import materials
    import projects
    import studio_api
    from server import TOKEN, app

    print("\nИИ-монтаж: очередь, дописанное, свежая сессия, анкета, материалы")

    # 1. тяжёлый шаг агентом студии мимо очереди — громкий отказ; из очереди — можно
    env = {k: v for k, v in os.environ.items() if k != "REELS_QUEUE_STEP"}
    env["REELS_STUDIO_CHILD"] = "1"
    probe_code = ("import sys; sys.path.insert(0, 'scripts'); from common import require_queue; "
                  "require_queue('проверка'); print('прошло')")
    blocked = subprocess.run([sys.executable, "-c", probe_code], cwd=ROOT, env=env, capture_output=True,
                             encoding="utf-8", errors="replace")
    allowed = subprocess.run([sys.executable, "-c", probe_code], cwd=ROOT, env=dict(env, REELS_QUEUE_STEP="1"),
                             capture_output=True, encoding="utf-8", errors="replace")
    unguarded = [f for f in ("transcribe", "prep", "track", "matte", "reframe", "render_reel", "reels")
                 if "require_queue(" not in (ROOT / "scripts" / f"{f}.py").read_text(encoding="utf-8")]
    queue_marks = 'env["REELS_QUEUE_STEP"] = "1"' in (ROOT / "scripts" / "jobqueue.py").read_text(encoding="utf-8")
    report.check(blocked.returncode != 0 and "через очередь" in blocked.stderr and "прошло" in allowed.stdout
                 and not unguarded and queue_marks,
                 "тяжёлый шаг агент студии запускает только через очередь (роликов разом много, тяжёлый процесс один)",
                 f"без очереди: {'отказ' if blocked.returncode else 'ПРОШЛО'}; без защиты: {', '.join(unguarded) or 'нет'}")

    # 2. дописанное по ходу: хук отдаёт агенту и помечает доставленным; без разговора студии — молчит
    tid = f"selfcheck-{os.getpid()}"
    node = shutil.which("node")
    try:
        brain.inbox_add(tid, "кодовое слово ГРУША")
        before = brain.inbox_state(tid)
        hook = [node, str(ROOT / "scripts" / "inbox_hook.mjs")] if node else None
        out = subprocess.run(hook, env=dict(os.environ, REELS_THREAD=tid), input="{}", capture_output=True,
                             encoding="utf-8", errors="replace", timeout=30) if hook else None
        ctx = json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"] if out and out.stdout.strip() else ""
        after = brain.inbox_state(tid)
        quiet = subprocess.run(hook, env={k: v for k, v in os.environ.items() if k != "REELS_THREAD"}, input="{}",
                               capture_output=True, encoding="utf-8", errors="replace", timeout=30) if hook else None
        brain.inbox_add(tid, "второе")
        taken, again = brain.inbox_take(tid), brain.inbox_take(tid)
    finally:
        shutil.rmtree(brain.INBOX / tid, ignore_errors=True)
    saved_find = brain.find_binary
    brain.find_binary = lambda name: name
    try:
        cmd = brain.command("claude", "x", thread_id=tid)
        plain = brain.command("claude", "x")
    finally:
        brain.find_binary = saved_find
    settings = cmd[cmd.index("--settings") + 1] if "--settings" in cmd else ""
    report.check("ГРУША" in ctx and list(before.values()) == [False] and list(after.values()) == [True]
                 and quiet is not None and not quiet.stdout.strip() and taken == ["второе"] and not again
                 and "inbox_hook.mjs" in settings and "--settings" not in plain,
                 "дописанное посреди монтажа: хук отдаёт его агенту и помечает, недоставленное уходит следующим ходом",
                 f"хук: {'отдал' if 'ГРУША' in ctx else 'НЕ отдал'}{'' if node else ' (нет node)'}; дальше: {taken}")

    # 3. свежая сессия ролика: разросшийся разговор продолжается новым, с передачей дел
    thread = {"id": "x", "stem": "S", "session": "abc", "messages": [
        {"role": "user", "text": "сделай динамичнее"},
        {"role": "assistant", "events": [{"type": "text", "text": "сделал быстрее"}, {"type": "result", "context": 50_000}]}]}
    small = brain.needs_fresh(thread)
    thread["messages"][1]["events"][1]["context"] = brain.FRESH_CONTEXT + 1
    big = brain.needs_fresh(thread)
    many = {"session": "a", "messages": [{"role": "user", "text": str(i)} for i in range(brain.FRESH_REQUESTS)]}
    autos = {"session": "a", "messages": [{"role": "user", "text": "x", "auto": True}] * 20}
    handed = brain.handoff(thread)
    report.check(small is None and big and brain.needs_fresh(many) and brain.needs_fresh(autos) is None
                 and "сделай динамичнее" in handed and "сделал быстрее" in handed and "work/S/" in handed,
                 "разговор ролика разросся (контекст или число просьб) — свежая сессия с передачей дел",
                 f"мал: {small}; велик: {big}")

    # то же через студию: отправка в разросшийся разговор открывает новый; проект без анкеты — отказ
    prompts = []

    def fake_agent(engine, prompt, *args, **kwargs):
        prompts.append(prompt)
        return [sys.executable, "-c", "print('{}')"]

    saved = (brain.THREADS, brain.command)
    brain.THREADS, brain.command = tmp / "fresh_threads", fake_agent
    sent, gate, inbox_late, fresh_thread = {}, None, None, {}
    try:
        with temp_projects(tmp / "fresh_projects", "main", "neo") as made, \
                TestClient(app, base_url="http://127.0.0.1:8765") as live:
            projects.save_setup(made["main"], READY_ANSWERS)
            (made["main"].input / "РОЛИК_С.MOV").write_bytes(b"v")
            (made["neo"].input / "РОЛИК_Н.MOV").write_bytes(b"v")
            old = brain.new_thread("claude", "старый", "РОЛИК_С")
            old.update(session="s1", messages=thread["messages"])
            brain.save_thread(old)
            key = {"X-Studio-Token": TOKEN}
            sent = live.post("/api/brain/send", json={"thread": old["id"], "text": "ещё правка", "stem": "РОЛИК_С"},
                             headers=key).json()
            for _ in range(100):
                if not studio_api.running_threads():
                    break
                time.sleep(0.05)
            if sent.get("thread") and sent["thread"] != old["id"]:
                fresh_thread = brain.load_thread(sent["thread"])
            neo = brain.new_thread("claude", "", "РОЛИК_Н")
            gate = live.post("/api/brain/send", json={"thread": neo["id"], "text": "смонтируй", "stem": "РОЛИК_Н"},
                             headers=key)
            inbox_late = live.post(f"/api/brain/inbox/{old['id']}", json={"text": "поздно"}, headers=key)
    finally:
        brain.THREADS, brain.command = saved
        for t in list(studio_api.runs):
            if not studio_api.runs[t]["done"]:
                continue
            studio_api.runs.pop(t, None)
    report.check(sent.get("fresh") and fresh_thread.get("fresh_of") == old["id"] and prompts
                 and prompts[0].startswith("Это продолжение работы") and "ещё правка" in prompts[0]
                 and fresh_thread.get("messages", [{}])[0].get("text") == "ещё правка",
                 "студия сама продолжает разросшийся разговор ролика свежей сессией и передаёт ей дела",
                 f"{sent.get('fresh') or 'не начала свежую'}")
    report.check(gate is not None and gate.status_code == 409 and "не настроен" in gate.text
                 and inbox_late is not None and inbox_late.status_code == 409,
                 "ролик проекта без анкеты ИИ не монтирует — отказ с тем, что ответить; дописать в законченный ход нельзя",
                 f"{gate.status_code if gate is not None else '—'}: {gate.json().get('detail', '')[:60] if gate is not None else ''}")

    # 4. анкета: обязательное без ответа видно; блок в rules.md один, ручные правила не теряются; умолчания проекта
    with temp_projects(tmp / "setup_projects", "neo", "old") as made:
        neo = made["neo"]
        required = [q["id"] for q in projects.SETUP_QUESTIONS if q.get("required")]
        fresh_missing = [q["id"] for q in projects.missing_setup(neo)]
        left = projects.save_setup(neo, {"about": "x", "language": "en", "platforms": ["YouTube 16:9", "TikTok"],
                                         "cta": "без призыва"})
        cfg = json.loads((neo.root / "project.json").read_text(encoding="utf-8"))
        neo.rules.write_text(neo.rules_text() + "\n## Своё\n- правило руками\n", encoding="utf-8")
        left2 = projects.save_setup(projects.get("neo"), dict(READY_ANSWERS, about="новое"))
        rules2 = projects.get("neo").rules_text()
        try:
            projects.save_setup(neo, {"zzz": 1})
            unknown = False
        except projects.ProjectError:
            unknown = True
        made["old"].rules.write_text("# Правила\n1. Написаны руками до анкеты.\n", encoding="utf-8")
        legacy = projects.missing_setup(projects.get("old"))
    report.check(fresh_missing == required and "audience" in [q["id"] for q in left] and not left2
                 and rules2.count(projects.SETUP_BEGIN) == 1 and "правило руками" in rules2 and "новое" in rules2
                 and unknown and legacy == [],
                 "анкета проекта: без ответов — видно чего нет, блок в правилах один и ручные правила целы",
                 f"не хватало: {len(fresh_missing)}, после ответов: {len(left2)}")
    report.check(cfg.get("language") == "en" and cfg.get("brief", {}).get("formats") == ["9:16", "16:9"]
                 and cfg.get("cta") is False,
                 "ответы анкеты становятся умолчаниями проекта: язык, форматы площадок, призыв",
                 f"{cfg.get('language')}, {cfg.get('brief', {}).get('formats')}, cta={cfg.get('cta')}")

    # 4б. шаблоны дизайн-систем (22.10.2026, Валера: «чтобы система сразу понимала, на какой шаблон ориентироваться… с
    # первого раза годноту»): все годны; анкета узнаёт жанр; применение пишет бриф, уроки и эталон, повтор не дублирует.
    # 23.10.2026 (аудит docs/АУДИТ-23-10.md): шрифт шаблона не из presets/fonts — красный (на Mac проверка была зелёной,
    # пока шрифты заказчицы лежали рядом, на чистой Windows — красной); ловушки подбора; смена шаблона честная
    import fonts as font_files
    import templates
    bad = [b for t in templates.all_templates() for b in templates.validate(t)]
    report.check(not bad and len(templates.ids()) >= 10, "шаблоны дизайн-систем годны: стиль, эталон внутри шаблона, шрифты движка",
                 "; ".join(bad[:3]) or f"{len(templates.ids())} шт.")
    probe_font = font_files.LOCAL / "_selfcheck_probe.ttf"
    fake = tmp / "tpl_fake" / "expert-premium"
    try:
        shutil.copytree(templates.TEMPLATE_DIR / "expert-premium", fake)
        font_files.LOCAL.mkdir(parents=True, exist_ok=True)
        shutil.copy2(font_files.ENGINE / "Caveat-Bold.ttf", probe_font)
        fake_t = templates.load("expert-premium") | {"dir": fake}
        md = (fake / "DESIGN.md").read_text(encoding="utf-8")
        (fake / "DESIGN.md").write_text(md.replace("src: Caveat-Bold.ttf", "src: _selfcheck_probe.ttf"), encoding="utf-8")
        foreign = templates.validate(fake_t)
        (fake / "DESIGN.md").write_text(md.replace("src: Caveat-Bold.ttf", "src: NoSuchFont-Bold.ttf"), encoding="utf-8")
        missing = templates.validate(fake_t)
    finally:
        probe_font.unlink(missing_ok=True)
    report.check(any("не из presets/fonts" in b for b in foreign) and any("NoSuchFont" in b for b in missing),
                 "шаблон на шрифте не из движка или без файла шрифта — красный (на любой машине одинаково)",
                 f"чужой: {len(foreign)} провал(а), нет файла: {len(missing)}")
    # ловушки подбора: каждая — настоящая ошибка мешка слов (аудит 23.10.2026)
    cases = [({"about": "Виктория — таргетолог и маркетолог для бьюти-салонов, кейсы клиентов",
               "tone": ["спокойный, экспертный", "премиальный, минимализм"]}, "talking", False, "expert-premium"),
             ({"about": "Бренд подарков, новоселье команды в новом офисе", "tone": ["динамичный, вирусный"]}, "pack", False,
              "brand-lifestyle"),
             ({"about": "Настя поёт под свой трек"}, "talking", True, "lyric"),
             ({"about": "Отзывы клиенток психолога, благодарность", "tone": ["тёплый"]}, "talking", False, "testimonial"),
             ({"about": "Репетитор ЕГЭ по математике объясняет задачи", "tone": ["динамичный, вирусный"]}, "talking", False,
              "expert-viral"),
             ({"about": "Психолог: про тревогу и выгорание, советы", "tone": ["спокойный, экспертный"]}, "talking", False,
              "expert-premium"),
             ({"about": "Влог про путешествия, говорю в камеру", "tone": ["тёплый"]}, "talking", False, "storytime"),
             ({"about": "Учу английскому, разбираю частые ошибки", "tone": ["дерзкий, с юмором"]}, "talking", False,
              "expert-viral"),
             ({"about": "Стоматолог про импланты", "sound": "без музыки, только голос"}, "talking", False, "expert-premium"),
             ({"about": "Фитнес-тренер: упражнения дома и питание", "tone": ["динамичный, вирусный"]}, "talking", False,
              "bold-captions"),
             ({"about": "котики и закаты", "tone": ["дерзкий, с юмором"]}, "talking", False, "expert-viral"),
             ({"about": "котики и закаты"}, "talking", False, None)]
    got = []
    for answers, kind, keep, want in cases:
        top = templates.choose(answers, kind, keep)[0]
        got.append((want, top["id"] if top else None))
    lyric_off = templates.score(templates.load("lyric"), {"about": "стоматолог", "sound": "без музыки"}, "talking", False)[0]
    pack_off = templates.score(templates.load("brand-lifestyle"), {"about": "влог про офис"}, "talking", False)[0]
    ref = {"file": "ref.mp4", "matches": [{"style": "hormozi"}], "cuts_per_min": 30}
    by_ref = templates.choose({"about": "говорю в камеру", "tone": ["динамичный, вирусный"]}, "talking", False,
                              refs=[ref])[0]
    report.check(all(w == g for w, g in got) and lyric_off is None and pack_off is None and by_ref["id"] == "bold-captions",
                 "подбор шаблона: жанр по анкете, речи и референсам; чужой тип и «без музыки» не голосуют; без жанра — по тону",
                 ", ".join(f"{w or 'своё'}→{g or 'своё'}" for w, g in got if w != g) or f"{len(got)} ловушек, референс → {by_ref['id']}")
    # тип проекта по входу: папка с одним видео — «лучшее из дубля кусками» (живой отзыв IMG_9665), не сборка; с двумя — сборка
    with temp_projects(tmp / "kind_projects", "one", "two") as made:
        for name, n in (("one", 1), ("two", 2)):
            folder = made[name].input / "RIL"
            folder.mkdir()
            for k in range(n):
                (folder / f"IMG_{k}.MOV").write_bytes(b"v")
            (made[name].input / "RIL.mov").write_bytes(b"v")
        kinds = (templates.project_facts(projects.get("one"))["kind"], templates.project_facts(projects.get("two"))["kind"])
    report.check(kinds == ("talking", "pack"), "тип проекта по входу: одно видео в папке — говорящая голова, два и больше — сборка",
                 f"одно: {kinds[0]}, два: {kinds[1]}")
    with temp_projects(tmp / "tpl_projects", "tpl") as made:
        p = made["tpl"]
        projects.save_setup(p, dict(READY_ANSWERS, about="Отзывы клиенток психолога, благодарность", tone=["тёплый"]))
        first = templates.apply(projects.get("tpl"))
        cfg_t = json.loads((p.root / "project.json").read_text(encoding="utf-8"))
        templates.apply(projects.get("tpl"), "testimonial")
        rules_t = projects.get("tpl").rules_text()
        # смена: стиль и умолчания — нового шаблона, DESIGN.md — его; поставленное руками остаётся
        templates.apply(projects.get("tpl"), "expert-premium")
        cfg_a = json.loads((p.root / "project.json").read_text(encoding="utf-8"))
        has_ds = (p.root / "DESIGN.md").is_file()
        cfg_a["music_level"] = 0.33                                  # человек поставил сам
        (p.root / "project.json").write_text(json.dumps(cfg_a, ensure_ascii=False), encoding="utf-8")
        templates.apply(projects.get("tpl"), "testimonial")
        cfg_b = json.loads((p.root / "project.json").read_text(encoding="utf-8"))
        ds_gone = not (p.root / "DESIGN.md").exists()
        templates.apply(projects.get("tpl"), "expert-premium")
        (p.root / "DESIGN.md").write_text((p.root / "DESIGN.md").read_text(encoding="utf-8") + "\n<!-- правил человек -->\n",
                                          encoding="utf-8")
        kept = templates.apply(projects.get("tpl"), "testimonial")["design"]
        templates.clear(projects.get("tpl"))
        cleared = projects.get("tpl").rules_text()
    report.check(first["template"] == "testimonial" and cfg_t.get("template") == "testimonial"
                 and cfg_t.get("brief", {}).get("style") == "testimonial" and cfg_t.get("music") is True
                 and rules_t.count(templates.BEGIN) == 1 and "exemplar.jpg" in rules_t
                 and rules_t.count(projects.SETUP_BEGIN) == 1 and templates.BEGIN not in cleared,
                 "шаблон ставится в проект: бриф, умолчания, блок с эталоном в правилах — один; «своё» его убирает",
                 f"{first['template']}, стиль {cfg_t.get('brief', {}).get('style')}, блоков {rules_t.count(templates.BEGIN)}")
    report.check(cfg_a.get("brief", {}).get("style") == "viral-behind" and cfg_a.get("music") is False and has_ds
                 and cfg_b.get("brief", {}).get("style") == "testimonial" and cfg_b.get("music") is True
                 and cfg_b.get("music_level") == 0.33 and ds_gone and "своя" in kept,
                 "смена шаблона меняет стиль, умолчания и DESIGN.md; поставленное руками и правленый DESIGN.md — не трогает",
                 f"стиль {cfg_a.get('brief', {}).get('style')}→{cfg_b.get('brief', {}).get('style')}, музыка "
                 f"{cfg_a.get('music')}→{cfg_b.get('music')}, уровень руками {cfg_b.get('music_level')}, DESIGN.md: "
                 f"{has_ds}/{'снят' if ds_gone else 'остался'}/{kept}")

    # 5. материалы: свой файл с замером, отказ не-медиа, происхождение того, что в странице, звук по норме
    saved_m = (materials.WORK_DIR, materials.ROOT)
    materials.WORK_DIR, materials.ROOT = tmp / "m_work", tmp / "m_root"
    try:
        beep, photo, junk = tmp / "beep.mp3", tmp / "photo.png", tmp / "junk.png"
        subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1.5", str(beep)], check=True)
        subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=orange:s=200x300", "-frames:v", "1", str(photo)], check=True)
        junk.write_text("не картинка", encoding="utf-8")
        a = materials.add("M", "мой звук.mp3", beep)
        i1, i2 = materials.add("M", "photo.png", photo), materials.add("M", "photo.png", photo)
        refused = []
        for name, src in (("doc.pdf", photo), ("x.png", junk)):
            try:
                materials.add("M", name, src)
            except materials.MaterialError as e:
                refused.append(str(e)[:40])
        tag = kit.material_audio("m1", "M", a["name"], 1.0)
        gain = float(re.search(r'data-volume="([\d.]+)"', tag).group(1))
        level = a["loudness_m"] + 20 * math.log10(gain)
        page = materials.ROOT / "studio" / "M" / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text('<div id="bg-a" class="g bg"><img src="assets/img/photo.png" alt=""></div>\n' + tag
                        + '\n<audio id="sfx-x" src="assets/sfx/pop.mp3" data-start="1"></audio>', encoding="utf-8")
        lst = materials.listing("M")
        used = {x["name"]: (x["code"], x["blocks"]) for x in lst["used"]}
        unused = [x["name"] for x in lst["unused"]]
        line = materials.context_line("M")
    finally:
        materials.WORK_DIR, materials.ROOT = saved_m
    report.check(a["name"] == "мой_звук.mp3" and i1["width"] == 200 and i2["name"] == "photo_2.png" and len(refused) == 2
                 and used.get("photo.png") == ("mine", ["bg-a"]) and used.get("мой_звук.mp3") == ("mine", ["sfx-m1"])
                 and used.get("pop.mp3", ("",))[0] == "library" and unused == ["photo_2.png"] and "photo_2.png" in line,
                 "материалы ролика: свой файл с замером, не-медиа — отказ, в ролике видно что и откуда",
                 f"в ролике: {', '.join(f'{k} ({v[0]})' for k, v in used.items())}; отказов {len(refused)}")
    report.check(level <= kit.SFX_TARGET + 0.5 and 'src="assets/materials/мой_звук.mp3"' in tag,
                 "звук из материалов ставится по замеру громкости, как библиотечный — не громче нормы",
                 f"{level:.1f} LUFS при норме {kit.SFX_TARGET:g}")

    # 6. оценки времени: замеры очереди этой машины важнее умолчаний
    saved_t = (jobqueue.TIMINGS, studio_api.quick_probe)
    jobqueue.TIMINGS = tmp / "timings.jsonl"
    studio_api.quick_probe = lambda path: {"duration": 60}
    try:
        jobqueue.note_timing(["python", "scripts/prep.py", "projects/x/input/IMG_1.MOV"], 200)
        jobqueue.note_timing(["python", "scripts/prep.py", "projects/x/input/IMG_1.MOV", "--hq"], 240)
        est = studio_api.step_estimates([(None, Path("IMG_1.MOV"))])
        rec = json.loads(jobqueue.TIMINGS.read_text(encoding="utf-8").splitlines()[-1])
    finally:
        jobqueue.TIMINGS, studio_api.quick_probe = saved_t
    report.check(est["prepped"] == {"per_min": 240, "measured": 2} and est["tracked"]["measured"] == 0
                 and rec["stem"] == "IMG_1" and rec["hq"] is True,
                 "время шагов: по замерам очереди на этой машине, пока их нет — по прошлым прогонам",
                 f"подготовка ≈ {est['prepped']['per_min']} с на минуту по {est['prepped']['measured']} замерам")


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
    stage_page_assets(project)
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


# ответы на все обязательные вопросы анкеты — проект «настроен» (projects.missing_setup пуст)
READY_ANSWERS = {"about": "проверка", "audience": "проверка", "platforms": ["Instagram Reels"], "language": "ru",
                 "tone": ["динамичный, вирусный"], "never": "нет табу"}


@contextlib.contextmanager
def temp_projects(root: Path, *names: str):
    """Проекты проверки во временной папке: настоящие projects/ тест не трогает.

    Все модули берут папку через projects.PROJECTS_DIR, поэтому подмены одной её достаточно.
    Первый из names — проект по умолчанию.
    """
    import projects
    saved = (projects.PROJECTS_DIR, projects.DEFAULT)
    projects.PROJECTS_DIR, projects.DEFAULT = root, names[0]
    try:
        made = {name: projects.create(name) for name in names}
        yield made
    finally:
        projects.PROJECTS_DIR, projects.DEFAULT = saved


def check_approve(report: Report, tmp: Path):
    """Апрув убирает копии ролика (черновые версии, сырые рендеры), но не принятый и не решения."""
    import approve

    print("\nАпрув и уборка копий")
    work, studio = tmp / "a_work", tmp / "a_studio"
    for folder in (work / "X", studio / "X" / "renders"):
        folder.mkdir(parents=True)
    (studio / "X" / "renders" / "X_v1.mp4").write_bytes(b"raw")
    (work / "X" / "aroll.matte_mediapipe.mkv").write_bytes(b"mask")
    (work / "X" / "edit.json").write_text("{}", encoding="utf-8")
    (work / "X" / "sheets").mkdir()
    (work / "X" / "sheets" / "X_v1.sheet.jpg").write_bytes(b"sheet")    # сетки кадров — не в output/ (16.10)
    saved = (approve.WORK_DIR, approve.ROOT, approve.studio_dir)
    approve.WORK_DIR, approve.ROOT = work, tmp
    approve.studio_dir = lambda: studio
    with temp_projects(tmp / "a_projects", "main") as made:
        out = made["main"].output
        (made["main"].input / "X.MOV").write_bytes(b"src")
        for name in ("X_v1.mp4", "X_v1.sheet.jpg", "X_v2.mp4", "X_v2.sheet.jpg", "XY_v1.mp4"):
            (out / name).write_bytes(b"v")
        try:
            approve.plan("X", "X_v2.mp4")
            done = approve.apply("X", "X_v2.mp4", ["drafts"])
        except Exception as e:
            done = {"error": f"{type(e).__name__}: {e}"}
        finally:
            approve.WORK_DIR, approve.ROOT, approve.studio_dir = saved
    left = sorted(p.name for p in out.iterdir() if p.name != ".gitkeep")
    kept_rest = (work / "X" / "aroll.matte_mediapipe.mkv").exists() and (work / "X" / "edit.json").exists()
    import common
    sheet = common.sheet_path(out / "X_v2.mp4", work)
    report.check(sheet.parent == work / "X" / "sheets" and "output" not in sheet.parts,
                 "сетка кадров ролика пишется в work/<имя>/sheets/, в output/ — только видео", str(sheet))
    report.check(left == ["XY_v1.mp4", "X_v2.mp4", "X_v2.sheet.jpg"] and not any((studio / "X" / "renders").iterdir())
                 and not (work / "X" / "sheets" / "X_v1.sheet.jpg").exists()
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

    # Язык: английский ролик (тестовое для заказчика, 13.10) по русскому кэшу дал бы мусор в субтитрах
    other = tmp / "IMG_0002.MOV"
    other.write_bytes(b"z" * 500)
    (cache / "IMG_0002.words.json").write_text('{"words": [], "text": ""}', encoding="utf-8")
    try:
        transcribe.run_transcribe(other, language="ru", cache_dir=cache)   # старый кэш без языка — русский
        transcribe.run_transcribe(other, language="en", cache_dir=cache)
        caught, why = False, "русский транскрипт отдан как английский молча"
    except SystemExit as e:
        caught, why = "распознана как" in str(e), str(e)[:70]
    except Exception as e:
        caught, why = False, f"{type(e).__name__}: {e}"[:70]
    report.check(caught, "транскрипт другого языка — громкий отказ, а не чужие слова", why)


def check_long_runs(report: Report):
    """Долгий ML-прогон спрашивает согласие по оценке счёта, а не по длине записи (инвариант 6)."""
    import enhance_audio

    print("\nДолгие прогоны")
    ask = getattr(enhance_audio, "needs_consent", None)
    ok = ask is not None and ask(240, "cpu", False) and not ask(60, "cpu", False) and not ask(600, "cpu", True)
    report.check(bool(ok), "улучшение голоса спрашивает согласие, если счёт дольше пяти минут",
                 "4-минутная запись (≈16 мин счёта) — спросит" if ok else "четыре минуты записи ушли бы без вопроса")

    import matte
    ask = getattr(matte, "needs_consent", None)
    minute, short = 60 * 30, 10 * 30
    ok = ask is not None and ask("birefnet", minute) and not ask("birefnet", short) and not ask("mediapipe", minute)
    report.check(bool(ok), "маска BiRefNet спрашивает согласие, если счёт дольше пяти минут",
                 f"минута дубля — ~{minute / matte.BIREFNET_FPS / 60:.0f} мин счёта, спросит" if ok
                 else "минута дубля ушла бы в маску на четверть часа без вопроса")


def check_sections(report: Report, tmp: Path):
    """Разделы проекта (21.10.2026): «Антишкола → Рилс», «Заказчик → Склейки». Свои видео, выпуски и правила; конфиг —
    проекта и поверх свой; дизайн-система, музыка и анкета — проекта. Имя «проект/раздел» проходит адреса студии
    (правила раздела не путаются с «открыть»), загрузка в раздел знает раздел, перенос везёт исходник и выпуски."""
    from fastapi.testclient import TestClient
    import design
    import projects
    import studio_api
    from server import TOKEN, app

    print("\nПроекты: разделы")
    res = {}
    with temp_projects(tmp / "sec_projects", "main", "other") as made, \
            TestClient(app, base_url="http://127.0.0.1:8765") as live:
        main = made["main"]
        projects.save_setup(main, READY_ANSWERS)
        cfg = json.loads((main.root / "project.json").read_text(encoding="utf-8"))
        cfg["brief"] = {"style": "viral-behind", "formats": ["9:16"], "notes": "серия"}
        cfg["music"] = True
        (main.root / "project.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        shutil.copy(ROOT / "presets" / "templates" / "expert-viral" / "DESIGN.md", main.root / "DESIGN.md")    # система Антишколы
        key = {"X-Studio-Token": TOKEN}
        made_sec = live.post("/api/studio/sections", json={"project": "main", "title": "Ютуб", "kind": "pack",
                                                          "formats": ["16:9"]}, headers=key)
        res["made"] = made_sec.status_code, made_sec.json()
        sec = projects.get("main/yutub")
        res["cfg"] = (sec.config["brief"].get("style"), sec.config["brief"].get("formats"), sec.config["brief"].get("notes"),
                      sec.config["music"], sec.config["kind"], main.config["kind"])
        res["home"] = (sec.home == main, design.of(sec) is not None,
                       projects.missing_setup(sec) == [], sec.references == main.references)
        sec.rules.write_text("# Раздел\n- только горизонталь\n", encoding="utf-8")
        both = sec.all_rules_text()
        res["rules"] = (both.find("Анкета проекта") < both.find("только горизонталь") and both.find("Анкета проекта") >= 0)
        got = live.get("/api/studio/rules/" + "main%2Fyutub").json()
        res["rules_api"] = (got.get("section"), "только горизонталь" in got.get("text", ""), "Анкета" in got.get("text", ""))
        opened = []
        saved_open = studio_api.host.open_file
        studio_api.host.open_file = opened.append
        try:
            live.post("/api/studio/rules/main%2Fyutub/open", headers=key)
        finally:
            studio_api.host.open_file = saved_open
        res["open"] = opened == [sec.rules]
        up = live.post("/api/upload", data={"project": "main/yutub"}, files={"file": ("РАЗДЕЛ_1.MOV", b"v")}, headers=key).json()
        res["upload"] = (up.get("project"), (sec.input / "РАЗДЕЛ_1.MOV").exists(), projects.of("РАЗДЕЛ_1") == sec)
        sec.output.mkdir(parents=True, exist_ok=True)
        (sec.output / "РАЗДЕЛ_1_v1.mp4").write_bytes(b"done")
        mv = live.post("/api/studio/video/РАЗДЕЛ_1/move", json={"target": "other"}, headers=key)
        other = made["other"]
        res["move"] = (mv.status_code, (other.input / "РАЗДЕЛ_1.MOV").exists(), (other.output / "РАЗДЕЛ_1_v1.mp4").exists(),
                       not (sec.input / "РАЗДЕЛ_1.MOV").exists())
        tree = live.get("/api/studio/state").json().get("projects", [])
        node = next((p for p in tree if p["name"] == "main"), {})
        res["tree"] = [(x["name"], x["kind"], x["own_title"]) for x in node.get("sections", [])]
        bad = live.post("/api/studio/sections", json={"project": "main/yutub", "title": "Вложенный"}, headers=key)
        res["nested"] = bad.status_code
        res["check"] = projects.check()
    made_ok = res["made"][0] == 200 and res["made"][1].get("name") == "main/yutub"
    report.check(made_ok and res["cfg"] == ("viral-behind", ["16:9"], "серия", True, "pack", "talking")
                 and all(res["home"]) and res["rules"] and res["tree"] == [("main/yutub", "pack", "Ютуб")],
                 "раздел: свой тип и формат поверх проекта; стиль, музыка, дизайн, анкета и референсы — проекта; "
                 "правила — оба файла, сначала проекта",
                 f"конфиг {res['cfg']}, от проекта {res['home']}, правила по порядку: {res['rules']}, дерево {res['tree']}")
    report.check(res["rules_api"] == (True, True, False) and res["open"] and res["upload"] == ("main/yutub", True, True)
                 and res["move"] == (200, True, True, True) and res["nested"] == 409,
                 "студия: правила раздела по адресу с косой (и «открыть» не путается), загрузка и перенос знают раздел",
                 f"правила {res['rules_api']}, открыть {res['open']}, загрузка {res['upload']}, перенос {res['move']}, "
                 f"раздел в разделе: {res['nested']}")
    report.check(not res["check"], "projects.py --check видит разделы и не находит ошибок", "; ".join(res["check"])[:200] or "чисто")


def check_projects(report: Report, tmp: Path):
    """Проект — граница: язык, бриф, CTA, порог лица и выпуски одного не протекают в другой (14.10.2026)."""
    import prep
    import projects
    import styles
    import verify_page
    import verify_render

    print("\nПроекты")
    projects.ensure_default()                    # на чистой машине проектов нет: умолчание создаёт установка — и здесь
    problems = projects.check()
    # данные клиентов — не в git движка (23.10.2026): проекты и решения роликов хранит .clients/ (scripts/clients.py).
    # Файл клиента, попавший в индекс движка, уехал бы ко всем, кому раздают движок
    if (ROOT / ".git").exists():
        leaked = [f for f in subprocess.run(["git", "ls-files", "--", "projects", "work", "studio"], cwd=ROOT,
                                            capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
                  if f != "projects/README.md" and not f.startswith("studio/_vendor/")]
        report.check(not leaked, "данные клиентов не в git движка: projects/, work/ и страницы роликов — в .clients/",
                     f"в индексе движка: {', '.join(leaked[:3])}" + (f" и ещё {len(leaked) - 3}" if len(leaked) > 3 else "")
                     if leaked else "чисто")
    # до 14.10 видео лежали в общих input/ и output/: файл, брошенный туда по привычке, никто не увидит
    stray = [f"{d}/{f.name}" for d in ("input", "output") if (ROOT / d).is_dir()
             for f in (ROOT / d).iterdir() if f.suffix.lower() in projects.VIDEO_EXT]
    report.check(not problems and not stray, "проекты в projects/ читаются, имена роликов не повторяются, "
                 "в старых input/ и output/ видео нет", "; ".join(problems + stray)[:160] or ", ".join(projects.names()))
    # репозиторий клиентов хранит решения и правила, но не видео и не промежуточное (scripts/clients.gitignore)
    import clients
    saved_c = (clients.ROOT, clients.GIT_DIR)
    croot = tmp / "c_root"
    clients.ROOT, clients.GIT_DIR = croot, croot / ".clients"
    try:
        keep = ["projects/x/rules.md", "projects/x/fonts/Brand.otf", "work/IMG_1.txt", "work/IMG_1/page.py",
                "work/IMG_1/edit.json", "work/IMG_1/materials/photo.jpg"]
        drop = ["projects/x/input/IMG_1.MOV", "projects/x/output/IMG_1_v1.mp4", "work/IMG_1/aroll.mp4",
                "work/IMG_1/materials/clip.mp4", "work/_queue/a.json", "projects/x/music/mx-a.mp3"]
        for f in keep + drop:
            (croot / f).parent.mkdir(parents=True, exist_ok=True)
            (croot / f).write_bytes(b"x")
        clients.init()
        stored = set(clients.git("ls-files").splitlines())
    except Exception as e:                                   # noqa: BLE001 — красный с причиной, а не падение проверки
        stored = {f"ошибка: {e}"}
    finally:
        clients.ROOT, clients.GIT_DIR = saved_c
    report.check(stored == set(keep), "данные клиентов: решения, правила и шрифты бренда — в .clients/, видео и промежуточное — нет",
                 ", ".join(sorted(stored ^ set(keep))[:4]) or f"{len(stored)} файлов, лишних нет")
    with temp_projects(tmp / "p_projects", "main", "client") as made:
        main, client = made["main"], made["client"]
        (main.root / "project.json").write_text(json.dumps(
            {"language": "ru", "cta": True, "face_max": 165, "brief": {"style": "viral-behind"}}), encoding="utf-8")
        (client.root / "project.json").write_text(json.dumps(
            {"language": "en", "cta": False, "face_max": None,
             "brief": {"style": "hormozi", "overrides": {"captions.font": "cormorant"}}}), encoding="utf-8")
        (main.input / "IMG_0001.MOV").write_bytes(b"a")
        (client.input / "IMG_0002.MOV").write_bytes(b"b")
        saved = styles.WORK_DIR
        styles.WORK_DIR = tmp / "p_work"
        try:
            mine, theirs = styles.load_brief("IMG_0001"), styles.load_brief("IMG_0002")
        finally:
            styles.WORK_DIR = saved
        report.check(theirs["style"] == "hormozi" and theirs["overrides"].get("captions.font") == "cormorant"
                     and mine["style"] == "viral-behind" and not mine["overrides"],
                     "ролик без своего брифа берёт умолчания своего проекта, а не соседнего",
                     f"заказчик: {theirs['style']}, свой: {mine['style']}")
        langs = (prep.speech_language("IMG_0002", {}), prep.speech_language("IMG_0001", {}),
                 prep.speech_language("IMG_0001", {"language": "en"}))
        report.check(langs == ("en", "ru", "en"), "язык речи — из проекта, edit.json может переопределить",
                     " / ".join(langs))
        saved = styles.WORK_DIR
        styles.WORK_DIR = tmp / "p_work"
        try:
            looks = (prep.pick_look("IMG_0002"), prep.pick_look("IMG_0001"))
        finally:
            styles.WORK_DIR = saved
        import compose
        saved = styles.WORK_DIR
        styles.WORK_DIR = tmp / "p_work"
        try:
            ruled = (compose.ruling_style("IMG_0002"), compose.ruling_style("IMG_0001"))
        finally:
            styles.WORK_DIR = saved
        report.check(ruled[0] is not None and ruled[0]["id"] == "hormozi"
                     and ruled[0]["params"]["captions"]["font"] == "cormorant" and ruled[1] is None,
                     "сборка ролика заказчика без своего брифа — по стилю его проекта; ролики проекта по умолчанию — "
                     "как были", f"заказчик: {ruled[0] and ruled[0]['id']}, свой: {ruled[1]}")
        report.check(looks[0].get("grade") == "punchy" and looks[1] == {"enabled": True, "brightness": -8.0,
                                                                         "grade": "natural"},
                     "цвет дубля без своего брифа — из стиля проекта, а не общий пресет (у заказчика — свой грейд)",
                     f"заказчик: {looks[0].get('grade')} {looks[0].get('brightness')}, свой: {looks[1].get('grade')} "
                     f"{looks[1].get('brightness')}")
        cta = 'id="cta"'
        leaks = (verify_page.cta_leak("IMG_0002", cta), verify_page.cta_leak("IMG_0002--hormozi", cta),
                 verify_page.cta_leak("IMG_0002", ""), verify_page.cta_leak("IMG_0001", cta))
        report.check(bool(leaks[0]) and bool(leaks[1]) and leaks[2] == "" and leaks[3] is None,
                     "плашка «смотри у меня в профиле» в проекте без CTA не пройдёт до рендера",
                     "поймана и в варианте A/B" if leaks[1] else f"{leaks}")
        faces = (verify_render.face_limit("IMG_0001")[0], verify_render.face_limit("IMG_0002")[0])
        report.check(faces == (165, None), "порог засвета лица — свой у проекта (у заказчика не наша серия)",
                     f"{faces}")
        outs = (projects.output_dir("IMG_0002"), projects.output_dir("IMG_0001"))
        report.check(outs == (client.output, main.output), "выпуск ложится в output/ проекта ролика",
                     " / ".join(f"{o.parent.name}/output" for o in outs))
        try:
            projects.of("IMG_9999")
            lost = "ролик без проекта получил проект молча"
        except projects.ProjectError as e:
            lost = "" if "ни в одном проекте" in str(e) else str(e)[:70]
        (client.input / "IMG_0001.mp4").write_bytes(b"c")
        try:
            projects.index()
            clash = "одно имя в двух проектах прошло молча"
        except projects.ProjectError as e:
            clash = "" if "двух проектах" in str(e) else str(e)[:70]
        (client.input / "IMG_0001.mp4").unlink()
        report.check(not lost and not clash, "ролик вне проектов и одно имя в двух проектах — громкий отказ",
                     lost or clash or "оба пойманы")
        import matte
        (main.root / "project.json").write_text(json.dumps({"long_matte": True}), encoding="utf-8")
        agreed = (matte.project_consent(ROOT / "work" / "IMG_0001" / "aroll.mp4"),
                  matte.project_consent(ROOT / "work" / "IMG_0002" / "aroll.mp4"),
                  matte.project_consent(ROOT / "work" / "IMG_9999" / "aroll.mp4"))
        report.check(agreed == ("main", None, None), "согласие на долгую маску — только у роликов своего проекта",
                     "чужой ролик и ролик вне проектов спросят" if agreed == ("main", None, None) else f"{agreed}")


def make_pack_clip(path: Path, size: str, seconds: float, bursts: list, level: float):
    """Клип сборки: тон «речи» во вспышках bursts [(от, до)] громкостью level, между ними — тишина."""
    gate = "+".join(f"between(t\\,{a}\\,{b})" for a, b in bursts)
    subprocess.run([ffmpeg_bin(), "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration={seconds}",
                    "-f", "lavfi", "-i", f"aevalsrc={level}*sin(2*PI*330*t)*({gate}):s=48000:d={seconds}",
                    *source_codec(), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", str(path)],
                   check=True, capture_output=True)


def check_packs(report: Report, tmp: Path):
    """Сборка: один ролик из нескольких видео (20.10.2026, заказ «Вкудесника» — 9 клипов, ролик до 1,5 мин).

    Куски с речью встают краями в тишину (инвариант 3), громкость речи разных клипов выравнивается, клип других
    пропорций без явного fit и ускоренная речь — громкий отказ; длина сборки — ровно сумма кадров кусков (инвариант 4),
    слова клипов переезжают на шкалу сборки; стыки — смена сцены: субтитр через стык не висит, склейкой дубля стык
    не считается.
    """
    import compose
    import pack
    import prep
    import projects
    import verify_page

    print("\nСборка из нескольких видео")
    work = tmp / "k_work"
    work.mkdir()
    with temp_projects(tmp / "k_projects", "main") as made:
        box = made["main"].input / "party"
        box.mkdir()
        made["main"].input.joinpath("IMG_0001.MOV").write_bytes(b"x")
        clips = {"a.mov": ("720x1280", 3.0, [(0.5, 1.0), (1.4, 1.9)], 0.03),        # тихая речь
                 "b.mov": ("1280x720", 2.0, [(0.2, 1.8)], 0.12),                   # горизонталь
                 "c.mov": ("720x1280", 2.0, [(0.4, 1.2)], 0.12)}                   # громкая речь
        for name, (size, sec, bursts, level) in clips.items():
            make_pack_clip(box / name, size, sec, bursts, level)
        words = {"a.mov": [("раз", 0.5, 1.0), ("два", 1.4, 1.85)], "b.mov": [("три", 0.3, 0.9), ("четыре", 1.0, 1.7)],
                 "c.mov": [("пять", 0.4, 1.15)]}
        found = projects.index().get("party")
        report.check(bool(found) and found[1] == box and projects.pack_of("party") == box
                     and projects.pack_of("IMG_0001") is None,
                     "папка видео в input/ — один ролик (сборка), обычный файл сборкой не считается",
                     f"{found[1].name if found else 'не найдена'}")
        saved = (pack.WORK_DIR, prep.WORK_DIR, verify_page.WORK_DIR)
        pack.WORK_DIR = prep.WORK_DIR = verify_page.WORK_DIR = work
        try:
            cache = work / "party" / "pack"
            cache.mkdir(parents=True)
            for name, ws in words.items():                   # речь «распознана» заранее — whisper тесту не нужен
                stem = Path(name).stem
                (cache / f"{stem}.words.json").write_text(json.dumps({"language": "ru", "text": "", "words": [
                    {"word": w, "start": a, "end": b, "prob": 1.0} for w, a, b in ws]}), encoding="utf-8")
                (cache / f"{stem}.source.json").write_text(json.dumps({"name": name, "size": (box / name).stat().st_size}),
                                                           encoding="utf-8")
            plan_path = work / "party" / "pack.json"

            def refused(pieces: list, needle: str) -> str:
                plan_path.write_text(json.dumps({"pieces": pieces}), encoding="utf-8")
                try:
                    pack.build("party")
                    return "собралось молча"
                except pack.PackError as e:
                    return "" if needle in str(e) else str(e)[:90]

            bad = (refused([{"clip": "b.mov", "from": 0, "to": 2, "mute": True}], "fit"),
                   refused([{"clip": "c.mov", "from": 0, "to": 2, "speed": 2}], "мультяшн"),
                   refused([{"clip": "z.mov", "from": 0, "to": 1}], "нет в сборке"))
            report.check(not any(bad), "горизонталь без fit, ускоренная речь и чужой клип — громкий отказ",
                         "; ".join(b for b in bad if b) or "все три пойманы")

            plan_path.write_text(json.dumps({"pieces": [
                {"clip": "a.mov", "from": 1.3, "to": 1.7},
                {"clip": "b.mov", "from": 0, "to": 2, "speed": 2, "mute": True, "fit": "blur"},
                {"clip": "c.mov", "from": 0, "to": 1.6}]}), encoding="utf-8")
            out = pack.build("party")
            built = json.loads((work / "party" / "pack.built.json").read_text(encoding="utf-8"))
            a, b, c = built["pieces"]
            report.check(a["start"] <= 1.4 and a["end"] >= 1.85 and a["speech"] and not b["speech"],
                         "кусок с речью уехал краями в тишину: слово не обрезано ни с какой стороны",
                         f"просили 1.30–1.70, вышло {a['start']:.2f}–{a['end']:.2f} (слово 1.40–1.85)")
            frames = sum(p["frames"] for p in built["pieces"])
            got = float(probe_value(out, "format=duration"))
            report.check(abs(got - frames / 30) <= 1.5 / 30 and b["frames"] == 30
                         and built["joins"] == [a["t1"], b["t1"]],
                         "длина сборки — ровно сумма кадров кусков, ускорение ×2 — вдвое короче, стыки на месте",
                         f"{got:.3f} с при {frames} кадрах, стыки {built['joins']}")

            def lufs(t0: float, t1: float) -> float:
                # замер свой, не pack.loudness: сломанный замер сборки не должен сам себя проверять
                err = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}",
                                      "-i", str(out), "-vn", "-af", "ebur128", "-f", "null", "-"],
                                     capture_output=True, encoding="utf-8", errors="replace").stderr
                found = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", err)
                return float(found[-1]) if found else -99.0
            gap = abs(lufs(a["t0"], a["t1"]) - lufs(c["t0"], c["t1"]))
            report.check(gap <= 2.0, "громкость речи разных клипов выровнена",
                         f"разница {gap:.1f} LU (в клипах — ~12 дБ); тихому {a['auto_gain']:+.1f} дБ")
            moved = json.loads((work / "party.words.json").read_text(encoding="utf-8"))["words"]
            said = [w["word"] for w in moved]
            two = next((w for w in moved if w["word"] == "два"), None)
            report.check(said == ["два", "пять"] and two and abs(two["start"] - (1.4 - a["start"])) < 0.02,
                         "слова клипов — на шкале сборки, у куска без звука слов нет",
                         f"{said}, «два» с {two['start'] if two else '?'}")

            # вырезанная пауза внутри одного плана — склейка (её прячут), а не смена сцены
            plan_path.write_text(json.dumps({"pieces": [
                {"clip": "a.mov", "from": 0.4, "to": 1.1}, {"clip": "a.mov", "from": 1.3, "to": 2.0},
                {"clip": "c.mov", "from": 0, "to": 1.6}]}), encoding="utf-8")
            pack.build("party")
            built = json.loads((work / "party" / "pack.built.json").read_text(encoding="utf-8"))
            first, second, third = built["pieces"]
            report.check(built["cuts"] == [second["t0"]] and built["joins"] == [third["t0"]],
                         "кусок того же клипа дальше по времени — склейка внутри плана, другой клип — смена сцены",
                         f"склейки {built['cuts']}, сцены {built['joins']}")
        finally:
            pack.WORK_DIR, prep.WORK_DIR, verify_page.WORK_DIR = saved

    # whisper растягивает первое слово на паузу перед ним («Ну» 0,00–1,76 при голосе с 1,68) и даёт слова нулевой длины
    words = pack.remap_clip_words(
        [{"clip": "x", "start": 1.55, "end": 3.0, "speed": 1.0, "t0": 0.0, "mute": False}],
        {"x": {"words": [{"word": "Ну", "start": 0.0, "end": 1.76}, {"word": "что", "start": 1.76, "end": 1.92},
                         {"word": "ну", "start": 2.2, "end": 2.2}, {"word": "хвост", "start": 0.2, "end": 1.6}]}})
    report.check([w["word"] for w in words] == ["Ну", "что", "ну"],
                 "первое слово, растянутое whisper до куска, и слово нулевой длины не теряются; чужой хвост — не в куске",
                 f"{[w['word'] for w in words]}")

    # стыки: камера и субтитры не переезжают, склейкой дубля стык не считается
    segments = prep.snap_segments(prep.split_at([(0.0, 3.0), (3.5, 6.0)], [2.0, 1.0, 5.0]), 30)
    scenes = prep.scene_marks(segments, [1.0, 5.0])
    report.check(segments == [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.5, 5.0), (5.0, 6.0)] and scenes == [1.0, 4.5],
                 "стыки сборки (в любом порядке) делят дубль на куски по порядку и ложатся в aroll.json → scenes",
                 f"{segments}, {scenes}")
    words = [{"word": w, "start": s, "end": e} for w, s, e in
             (("мы", 0.2, 0.4), ("рады", 0.45, 0.9), ("очень", 1.1, 1.4), ("рады", 1.45, 1.8))]
    chunks = compose.caption_chunks(words, {}, 3.0, "phrase", "lower", scenes=[1.0])
    across = [c["text"] for c in chunks if c["t0"] < 1.0 < c["t1"]]
    report.check(not across and len(chunks) == 2, "субтитр не собирает слова с двух сторон стыка и не висит через него",
                 f"{[(c['text'], c['t0'], c['t1']) for c in chunks]}")
    project = tmp / "k_studio" / "party"
    (work / "party").mkdir(parents=True, exist_ok=True)
    (work / "party" / "aroll.json").write_text(json.dumps(
        {"segments": [[0, 1], [1, 3], [3.5, 6]], "scenes": [1.0], "jumps": []}), encoding="utf-8")
    saved = verify_page.WORK_DIR
    verify_page.WORK_DIR = work
    try:
        cuts = verify_page.take_splices(project)
    finally:
        verify_page.WORK_DIR = saved
    report.check(cuts == [3.0], "стык сборки — не склейка дубля: вспышку и наезд там не требуют",
                 f"склейки {cuts}")


def check_life_edit(report: Report, tmp: Path):
    """Лайф-монтаж (20.10.2026, «Вкудесник» v2): музыка уходит под живой звук и поднимается в тишине, доли трека,
    ускорение рывком, стоп-кадр и конец куска в долю, активное слово субтитров на плашке, склейка внутри плана смазом."""
    import kit
    import montage
    import music
    import pack
    import prep
    import styles

    print("\nЛайф-монтаж: музыка, доли, рывок, стоп-кадр, плашка")
    # приглушение: тон 1–3 с и 5–6 с, между ними тишина 2 с — там музыка выше; в конце уход
    dry = tmp / "l_dry.wav"
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i",
                    "aevalsrc=0.2*sin(2*PI*300*t)*(between(t\\,1\\,3)+between(t\\,5\\,6)):s=22050:d=7", str(dry)],
                   check=True, capture_output=True)
    lane = music.duck_lane(dry, 7.0)
    up = [t for (t, v), (_, w) in zip(lane, lane[1:]) if v == 1.0 and w > 1.0]
    low = [v for t, v in lane if 1.2 <= t <= 2.9 or 5.1 <= t <= 5.9]
    report.check(lane and lane[0][1] > 1.0 and len(up) == 2 and all(v == 1.0 for v in low),
                 "музыка под живым звуком — уровень проекта, в тишине дубля поднимается",
                 f"лента {lane}")
    auto = '{"version":1'
    saved = (kit.material_audio, kit.material_gain)   # громкость по замеру файла не нужна — проверяется разметка тега
    kit.material_gain = lambda stem, name, level: 0.3      # лента — абсолютная громкость: уровень × множитель
    kit.material_audio = lambda sid, stem, name, start, level, duration=None, fade_out=None: (
        f'      <audio id="sfx-{sid}" src="assets/materials/{name}" data-start="{start:.2f}"'
        + (f' data-duration="{duration}"' if duration else "") + (f' data-fade-out="{fade_out}"' if fade_out else "")
        + ' data-volume="0.300"></audio>')
    try:
        tag = kit.background_music("X", "mx-x.mp3", 7.0, lane=lane, media_start=0.5, fade_out=0.5)
        plain = kit.background_music("X", "mx-x.mp3", 7.0)
    finally:
        kit.material_audio, kit.material_gain = saved
    report.check(auto in tag and "data-fade-out" not in tag and '"t":7.0,"v":0.0' in tag and '"v":0.3}' in tag
                 and f'"v":{round(0.3 * lane[0][1], 4)}' in tag
                 and 'data-media-start="0.500"' in tag and "data-automation" not in plain and "data-fade-out" in plain,
                 "лента громкости (абсолютная: уровень проекта × подъём) и сильная доля — в теге музыки; уход — точками ленты",
                 tag[-120:])

    # доли: щелчки 120 BPM со сдвигом 0.25 с
    clicks = tmp / "l_clicks.wav"
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i",
                    "aevalsrc=0.8*sin(2*PI*1000*t)*lt(mod(t-0.25\\,0.5)\\,0.03)*gte(t\\,0.25):s=22050:d=20", str(clicks)],
                   check=True, capture_output=True)
    bpm, offset = music.beat_grid(clicks)
    report.check(abs(bpm - 120) < 2 and abs(offset - 0.25) < 0.04, "темп и сильная доля трека находятся",
                 f"{bpm} BPM, доля с {offset} с (ждали 120 и 0.25)")

    # рывок: разгон и торможение по кривой, середина быстрее краёв
    speeds = pack.ramp_speeds([1, 4, 1])
    report.check(len(speeds) == pack.RAMP_STEPS and speeds[0] < 1.5 and max(speeds) > 3.5 and speeds[-1] < 1.5
                 and speeds == speeds[::-1], "ускорение рывком: плавно разгоняется и тормозит",
                 " ".join(f"{v:.2f}" for v in speeds))

    # сборка: рывок без звука, стоп-кадр, конец в долю
    work = tmp / "l_work"
    with temp_projects(tmp / "l_projects", "main") as made:
        box = made["main"].input / "life"
        box.mkdir()
        make_pack_clip(box / "a.mov", "720x1280", 4.0, [(0.5, 1.5)], 0.1)
        make_pack_clip(box / "b.mov", "720x1280", 4.0, [(0.2, 3.8)], 0.1)
        saved = (pack.WORK_DIR, prep.WORK_DIR)
        pack.WORK_DIR = prep.WORK_DIR = work
        try:
            cache = work / "life" / "pack"
            cache.mkdir(parents=True)
            for name, ws in {"a.mov": [("раз", 0.5, 1.5)], "b.mov": []}.items():
                stem = Path(name).stem
                (cache / f"{stem}.words.json").write_text(json.dumps({"language": "ru", "text": "", "words": [
                    {"word": w, "start": a, "end": b, "prob": 1.0} for w, a, b in ws]}), encoding="utf-8")
                (cache / f"{stem}.source.json").write_text(json.dumps({"name": name, "size": (box / name).stat().st_size}),
                                                           encoding="utf-8")
            plan_path = work / "life" / "pack.json"

            def refused(data: dict, needle: str) -> str:
                plan_path.write_text(json.dumps(data), encoding="utf-8")
                try:
                    pack.build("life")
                    return "собралось молча"
                except pack.PackError as e:
                    return "" if needle in str(e) else str(e)[:90]

            bad = (refused({"pieces": [{"clip": "b.mov", "from": 0, "to": 3, "ramp": [1, 4, 1]}]}, "mute"),
                   refused({"beat": {"bpm": 120}, "pieces": [{"clip": "a.mov", "from": 0.3, "to": 1.8, "snap": True}]},
                           "без речи"),
                   refused({"pieces": [{"clip": "b.mov", "from": 0, "to": 1, "mute": True, "snap": True}]}, "beat"))
            report.check(not any(bad), "рывок со звуком, «в долю» на речи и без долей — громкий отказ",
                         "; ".join(b for b in bad if b) or "все три пойманы")
            plan_path.write_text(json.dumps({"beat": {"bpm": 120, "offset": 0.0}, "pieces": [
                {"clip": "a.mov", "from": 0.4, "to": 1.7, "hold": 0.6, "exact": True},
                {"clip": "b.mov", "from": 0.0, "to": 3.6, "ramp": [1, 4, 1], "mute": True, "snap": True},
                {"clip": "b.mov", "from": 3.6, "to": 3.9, "mute": True, "hold": 0.5, "snap": True, "cut": "scene"}]}),
                encoding="utf-8")
            out = pack.build("life")
            built = json.loads((work / "life" / "pack.built.json").read_text(encoding="utf-8"))
            a, b, c = built["pieces"]
            got = float(probe_value(out, "format=duration"))
            on_beat = all(abs(p["t1"] / 0.5 - round(p["t1"] / 0.5)) < 1 / 30 / 0.5 for p in (b, c))
            report.check(a["frames"] == 39 + 18 and on_beat and b["frames"] < 3.6 * 30 * 0.6
                         and abs(got - sum(p["frames"] for p in built["pieces"]) / 30) <= 1.5 / 30,
                         "стоп-кадр добавляет кадры, рывок короче ×1, концы кусков «в долю» — на долях",
                         f"стоп: {a['frames']} кадров (39 + 18), рывок: {b['frames']} кадров, доли: {b['t1']:.3f} и "
                         f"{c['t1']:.3f} с, файл {got:.3f} с")
        finally:
            pack.WORK_DIR, prep.WORK_DIR = saved

    kinds = (pack.cut_kind({"clip": "x", "end": 3.0, "speed": 1.0}, {"clip": "x", "start": 6.0, "speed": 1.0, "ramp": [1, 4]}),
             pack.cut_kind({"clip": "x", "end": 3.0, "speed": 1.0, "hold": 1.0}, {"clip": "x", "start": 6.0, "speed": 1.0}),
             pack.cut_kind({"clip": "x", "end": 3.0, "speed": 1.0}, {"clip": "x", "start": 6.0, "speed": 1.0}))
    report.check(kinds == ("scene", "scene", "jump"), "стык с рывком или после стоп-кадра — смена сцены; пауза в плане — склейка",
                 f"{kinds}")

    # мастеринг: истинный пик между отсчётами — редкие короткие всплески на четверти частоты дискретизации со сдвигом
    # 45° (отсчёты на 3 дБ ниже волны) поверх ровной подложки: лимитер по отсчётам их пропускал (новоселье v2: +0.6 dBTP
    # после мастеринга); мастеринг повторяет проход с потолком ниже на превышение, а громкость остаётся
    import master
    src, dst = tmp / "l_tp.mov", tmp / "l_tp_master.mp4"
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x568:r=30:d=6",
                    "-f", "lavfi", "-i", "aevalsrc=0.35*sin(2*PI*12000*t+PI/4)*lt(mod(t\\,1)\\,0.005)"
                                         "+0.1*sin(2*PI*1000*t):s=48000:d=6",
                    *source_codec(), "-c:a", "pcm_s16le", "-shortest", str(src)], check=True, capture_output=True)
    try:
        stats = master.master(src, dst)
        report.check(stats["after"]["tp"] <= -1.4, "мастеринг держит истинный пик (между отсчётами), громкость — в норме",
                     f"{stats['after']['tp']:.1f} dBTP, {stats['after']['i']:.1f} LUFS, потолок {stats['ceiling']} дБ")
    except RuntimeError as e:
        report.check(False, "мастеринг держит истинный пик (между отсчётами), громкость — в норме", str(e)[:120])

    # активное слово на плашке; склейка внутри плана — смаз, а не вспышка
    st = styles.effective(styles.load_style("hormozi"), {"captions.active_box": "#FFD60A", "captions.active_text": "#111111"})
    js = kit.caption_js(styles.kit_captions(st))
    plain = kit.caption_js(styles.kit_captions(styles.load_style("hormozi")))
    css = kit.caption_css(styles.kit_captions(st))
    report.check('CAP_BOX = "#FFD60A"' in js and 'class: "w on"' in js and 'CAP_BOX = ""' in plain
                 and re.search(r"\.cap \.w\.on \{[^}]*background-color: #FFD60A[^}]*text-shadow: none", css) is not None,
                 "караоке с плашкой: активное слово на цветной плашке без тёмного ореола, без опции — как было", "")
    # обводка «пару пикселей» (21.10.2026): 2 px снаружи — штрих 4 px; 5 px снаружи — громкий отказ, а не жирный текст
    thin = kit.caption_css(styles.kit_captions(styles.effective(styles.load_style("hormozi"), {"captions.stroke": 2})))
    try:
        styles.effective(styles.load_style("hormozi"), {"captions.stroke": 5})
        fat = "принята"
    except styles.StyleError:
        fat = "отказ"
    report.check("-webkit-text-stroke: 4px #000" in thin and fat == "отказ",
                 "обводка субтитров тонкая: 2 px снаружи, 5 px — отказ («просил буквально пару пикселей»)",
                 f"обводка 5 px {fat}")
    splices, whips = montage.cover_cuts([4.0], [7.5, 9.2], "      whip(9.20);\n", framing=False, jump_whip=True)
    flash, _ = montage.cover_cuts([4.0], [7.5], "", framing=False, jump_whip=False)
    report.check(splices == [4.0] and whips == [7.5] and flash == [4.0, 7.5],
                 "склейка внутри плана — смазом (jump_whip), вырез дубля — вспышкой; смаз страницы не дублируется",
                 f"вспышки {splices}, смазы {whips}; без опции вспышки {flash}")


def check_web_import(report: Report, tmp: Path):
    """Перетаскивание из Telegram даёт странице путь к файлу, а не сам файл.

    Путь принимает сервер. Проверяется главное: чужой файл либо доходит до input/,
    либо получает внятный отказ. Тихое «ничего не произошло» здесь хуже всего — человек
    ждёт ролик от видео, которого в работе нет.
    """
    print("\nПриём перетащенного файла")
    with temp_projects(tmp / "w_projects", "main", "client") as projs:
        _check_web_import(report, tmp, projs)


def _check_web_import(report: Report, tmp: Path, projs: dict):
    from server import import_local_file
    inbox = projs["main"].input

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
            landed.append(inbox / first["name"])
        arrived = "name" in first and (inbox / first["name"]).exists()
        report.check(arrived, "файл по file://-ссылке лёг в input/",
                     first.get("name") or first.get("error", ""))
        report.check(arrived and Path(first["name"]).suffix == ".mp4",
                     "файлу без расширения дано .mp4")

        second = import_local_file(str(cached))
        if "name" in second:
            landed.append(inbox / second["name"])
        report.check(arrived and second.get("name") not in (None, first.get("name")),
                     "повторный приём не затирает уже лежащий файл", second.get("name", ""))
        # в другой проект с тем же именем — тоже рядом: у роликов общий work/<имя>/ на все проекты
        third = import_local_file(str(cached), "client")
        landed.append(projs["client"].input / third.get("name", "-"))
        report.check(third.get("project") == "client" and third.get("name") not in
                     (None, first.get("name"), second.get("name")),
                     "файл ложится в input/ выбранного проекта, и имя не повторяет ролик другого проекта",
                     f"{third.get('project')}: {third.get('name') or third.get('error', '')}")
    finally:
        for path in landed:
            path.unlink(missing_ok=True)

    import server
    import studio_api
    from fastapi.testclient import TestClient

    queue = tmp / "queue"
    saved = (server.PRESET_DIR, studio_api.QUEUE, studio_api.ensure_runner)
    server.PRESET_DIR = tmp
    studio_api.QUEUE, studio_api.ensure_runner = queue, (lambda: False)
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
        server.PRESET_DIR, studio_api.QUEUE, studio_api.ensure_runner = saved


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
    # регистр «как сказано» (natural) держит и точку: «равенства,» не совпадало с ключевым «равенства», и подсветка молча
    # пропадала (IMG_9665, 22.10.2026: из шестнадцати ключевых слов горели три)
    lit = [c["text"] for c in caption_chunks(words, {"accent_words": ["равенства", "Нет"]}, 5.0, "words", "natural")
           if c["accent"]]
    report.check(len(lit) == 2, "ключевое слово подсвечивается и в регистре «как сказано», со знаком на конце",
                 f"подсвечено {lit} из «равенства,» и «Нет.»")

    project = tmp / "style-page"
    (project / "assets").mkdir(parents=True)
    shutil.copy2(ROOT / "studio" / "_vendor" / "gsap.min.js", project / "assets" / "gsap.min.js")
    (project / "camera.js").write_text("window.CAMERA_FPS = 30;\nwindow.CAMERA = [[0, 0, 1], [0, 0, 1]];\n")
    stage_page_assets(project)
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


def check_studio_page(report: Report, tmp: Path):
    """Страница студии поднимается без ошибок JS — в том же Chrome, что и рендер.

    Вся монтажная — один скрипт: обращение к убранной кнопке или опечатка на старте роняет его целиком, и человек
    видит пустую студию без единого сообщения. Сервер здесь не нужен: запросы к API с file:// падают и ловятся кодом
    студии, а синхронная ошибка скрипта — нет. Заодно — что 21.10.2026 убрано («Свойства», кнопка «Зоны») и что
    пришло на замену (свойства над чатом, ручки ширины и высоты, корзина у видео).
    """
    from verify_page import find_chrome
    print("\nСтудия: страница")
    page = (ROOT / "web" / "studio.html").read_text(encoding="utf-8")
    page = page.replace("<head>", '<head>\n<script>window.__errs = []; window.addEventListener("error", '
                        '(e) => window.__errs.push(String(e.message)));</script>', 1)
    probe = """<script>setTimeout(() => { let menu = {};
      try {   // меню проектов деревом, окна нового раздела и переноса — на подставных данных (API с file:// нет)
        S.projects = [{ name: "p", title: "Проект — тест", kind: "talking", setup_missing: 1, sections: [
          { name: "p/s", title: "Проект — тест · Склейки", own_title: "Склейки", parent: "p", kind: "pack", setup_missing: 1 }] }];
        S.videos = []; S.project = "p/s"; renderProjects(); openSection("p"); $("section-dialog").close();
        askMove("X"); $("move-dialog").close();
        menu = { rows: document.querySelectorAll("#pmenu-pop .pitem[data-project]").length,
                 cur: (document.querySelector('#pmenu-pop .pitem[aria-current="true"]') || {}).dataset?.project,
                 kind: (document.querySelector('#pmenu-pop .pkind [aria-pressed="true"]') || {}).dataset?.kind,
                 rules: [...document.querySelectorAll("#pmenu-pop [data-rules]")].map((b) => b.dataset.rules),
                 icons: document.querySelectorAll("#pmenu-pop svg.ico").length, moves: document.querySelectorAll("#move-list [data-to]").length,
                 packZones: placeKind() };
      } catch (e) { window.__errs.push("меню проектов: " + e); }
      let heads = {};
      try {   // заголовок ИИ-панели: ручной экспорт в очереди — это не «ИИ монтирует» (22.10.2026)
        const head = () => ($("ai-start").querySelector("h3") || {}).textContent;
        S.videos = [{ stem: "IMG_0001", project: "p", steps: { page: true }, outputs: [], brief: {} }];
        S.stem = "IMG_0001"; S.brief = {}; S.brainRuns = []; S.brainBusy = false; S.starting = null;
        S.queue = { current: { job: "IMG_0001-render-v2", elapsed: 5, log: [] }, pending: [] };
        renderAiStart(); heads.exp = head();
        S.brainRuns = [{ thread: "t", stem: "IMG_0001", elapsed: 3, at: Date.now(), actions: 0 }];
        renderAiStart(); heads.ai = head();
        S.brainRuns = []; S.queue = { current: null, pending: [] }; S.videos = []; S.stem = null;
      } catch (e) { window.__errs.push("ИИ-панель: " + e); }
      const out = { errors: window.__errs, menu, heads,
      gone: ["tab-props", "zones-btn", "ask-ai"].filter((id) => document.getElementById(id)),
      missing: ["insp-card", "rsplit", "csplit", "del-dialog"].filter((id) => !document.getElementById(id)),
      tabs: [...document.querySelectorAll("#rtabs [data-tab]")].map((b) => b.dataset.tab),
      trash: typeof icon === "function" && icon("trash").includes("<path") };
      const p = document.createElement("pre"); p.id = "probe"; p.textContent = JSON.stringify(out); document.body.appendChild(p); }, 800);</script>"""
    cut = page.rfind("</body>")
    wrapper = tmp / "studio_probe.html"
    wrapper.write_text(page[:cut] + probe + page[cut:], encoding="utf-8")
    res = subprocess.run([find_chrome(), "--headless", "--disable-gpu", "--no-first-run", "--mute-audio",
                          f"--user-data-dir={tmp / 'studio_profile'}", "--virtual-time-budget=3000", "--dump-dom",
                          wrapper.as_uri()], capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    shutil.rmtree(tmp / "studio_profile", ignore_errors=True)
    m = re.search(r'<pre id="probe">(.*?)</pre>', res.stdout, re.S)
    import html as _html
    out = json.loads(_html.unescape(m.group(1))) if m else {"errors": ["Chrome не отдал страницу: " + res.stderr[-200:]]}
    report.check(not out.get("errors"), "страница студии поднимается без ошибок скрипта",
                 "; ".join(out.get("errors") or [])[:300] or "чисто")
    menu = out.get("menu") or {}
    report.check(menu.get("rows") == 2 and menu.get("cur") == "p/s" and menu.get("kind") == "pack"
                 and menu.get("rules") == ["p/s", "p"] and menu.get("icons", 0) >= 8 and menu.get("moves") == 2
                 and menu.get("packZones") == "pack",
                 "меню проектов: дерево с разделом, тип раздела, правила раздела и проекта, свои иконки, перенос",
                 json.dumps(menu, ensure_ascii=False)[:200])
    heads = out.get("heads") or {}
    report.check("ИИ" not in (heads.get("exp") or "ИИ") and "Сборка" in heads.get("exp", "")
                 and heads.get("ai") == "ИИ монтирует…",
                 "ручной экспорт в очереди подписан сборкой, «ИИ монтирует» — только когда идёт ход ИИ",
                 json.dumps(heads, ensure_ascii=False))
    report.check(not out.get("gone") and not out.get("missing") and out.get("tabs") == ["ai"] and out.get("trash"),
                 "справа один ИИ-монтаж: свойства — над чатом у выделенного, панель и поле ввода тянутся, у видео — корзина",
                 f"лишнее: {out.get('gone')}, нет: {out.get('missing')}, вкладки: {out.get('tabs')}")


def check_delete_video(report: Report, tmp: Path):
    """Удаление видео из студии (21.10.2026): исходник, work/<имя>/, work/<имя>.* и studio/<имя>/ — в Корзину,
    готовые ролики остаются в output/, чужое с похожим именем (IMG_3662_2 рядом с IMG_3662) не трогается, а видео
    в работе не удаляется — громкий отказ. Корзина здесь — своя папка (TRASH_DIR), настоящую тест не трогает."""
    from fastapi.testclient import TestClient
    import studio_api
    from server import TOKEN, app

    print("\nСтудия: удаление видео")
    work, pages, trash = tmp / "del_work", tmp / "del_studio", tmp / "del_trash"
    saved = (studio_api.WORK_DIR, studio_api.STUDIO_PAGES, studio_api.TRASH_DIR)
    studio_api.WORK_DIR, studio_api.STUDIO_PAGES, studio_api.TRASH_DIR = work, pages, trash
    studio_api.batch.update(running=False, items=[])
    res = {}
    try:
        with temp_projects(tmp / "del_projects", "main") as made, TestClient(app, base_url="http://127.0.0.1:8765") as live:
            main = made["main"]
            for stem in ("РОЛИК_У", "РОЛИК_У_2", "РОЛИК_Ф"):
                (main.input / f"{stem}.MOV").write_bytes(b"v")
            main.output.mkdir(parents=True, exist_ok=True)
            (main.output / "РОЛИК_У_v1.mp4").write_bytes(b"done")
            (work / "РОЛИК_У").mkdir(parents=True)
            (work / "РОЛИК_У" / "edit.json").write_text("{}", encoding="utf-8")
            (work / "РОЛИК_У.words.json").write_text("[]", encoding="utf-8")
            (work / "РОЛИК_У_2.words.json").write_text("[]", encoding="utf-8")
            (pages / "РОЛИК_У").mkdir(parents=True)
            key = {"X-Studio-Token": TOKEN}
            res["preview"] = live.get("/api/studio/video/РОЛИК_У/delete").json()
            res["del"] = live.post("/api/studio/video/РОЛИК_У/delete", headers=key)
            studio_api.batch.update(running=True, items=[{"stem": "РОЛИК_Ф", "status": "working"}])
            res["busy"] = live.post("/api/studio/video/РОЛИК_Ф/delete", headers=key)
            studio_api.batch.update(running=False, items=[])
            res["left"] = sorted(p.name for p in main.input.iterdir() if not p.name.startswith("."))
            res["out"] = (main.output / "РОЛИК_У_v1.mp4").exists()
            res["work"] = sorted(p.name for p in work.iterdir())
            res["trash"] = sorted(p.name for p in trash.iterdir()) if trash.exists() else []
    finally:
        studio_api.WORK_DIR, studio_api.STUDIO_PAGES, studio_api.TRASH_DIR = saved
        studio_api.batch.update(running=False, items=[])
    # work/РОЛИК_У/ и studio/РОЛИК_У/ — одноимённые папки: вторая ложится в Корзину с временем в имени
    got = res.get("trash", [])
    gone = len(got) == 4 and {"РОЛИК_У.MOV", "РОЛИК_У.words.json", "РОЛИК_У"} <= set(got) \
        and any(n.startswith("РОЛИК_У ") for n in got)
    report.check(res.get("del") is not None and res["del"].status_code == 200 and gone
                 and res.get("left") == ["РОЛИК_У_2.MOV", "РОЛИК_Ф.MOV"] and res.get("out")
                 and res.get("work") == ["РОЛИК_У_2.words.json"] and res["preview"].get("outputs") == 1,
                 "удалённое видео — в Корзине со своими файлами; готовый ролик и соседнее видео на месте",
                 f"в Корзине: {res.get('trash')}, в input: {res.get('left')}, в work: {res.get('work')}, "
                 f"выпуск: {'на месте' if res.get('out') else 'ПРОПАЛ'}")
    busy = res.get("busy")
    report.check(busy is not None and busy.status_code == 409 and "пачка" in busy.text and "РОЛИК_Ф.MOV" in res.get("left", []),
                 "видео, которое монтируется, не удаляется — громкий отказ",
                 f"код {busy.status_code if busy is not None else '—'}")


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
    # 17.10.2026: мозг студии был без браузера — v2 IMG_3292 вышла без видео Flow и без музыки, а в терминале
    # то же самое делалось. Студия должна монтировать так же, как терминал
    report.check(("--chrome" in cmd_safe or not brain.find_binary("claude")) and "mcp__claude-in-chrome" in brain.SAFE_TOOLS
                 and "браузера нет" not in brain.STUDIO_PROMPT and "jobqueue.py wait" in brain.STUDIO_PROMPT,
                 "мозг студии с браузером, как агент в терминале, и ждёт очередь через wait")
    report.check(brain.child_env().get(brain.CHILD_ENV) == "1", "агент студии помечен для хука старта")
    # 19.10.2026: модель и усилие мозга брались из личных настроек запустившего — закреплены в проекте
    saved_find = brain.find_binary
    brain.find_binary = lambda name: name
    try:
        pinned = brain.command("claude", "x")
    finally:
        brain.find_binary = saved_find
    flag = lambda name: pinned[pinned.index(name) + 1] if name in pinned else None  # noqa: E731
    report.check(flag("--model") == brain.CLAUDE_MODEL and flag("--effort") == brain.CLAUDE_EFFORT,
                 "мозг студии идёт на модели и усилии проекта, а не на личных настройках",
                 f"модель {flag('--model')}, усилие {flag('--effort')}")

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
    work, queue = tmp / "studio_work", tmp / "studio_queue"
    for folder in (work / "X", queue):
        folder.mkdir(parents=True)
    stack = contextlib.ExitStack()          # временные проекты снимаются в finally ниже
    inbox = stack.enter_context(temp_projects(tmp / "studio_projects", "main"))["main"].input
    subprocess.run([ffmpeg_bin(), "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=64x64:r=30:d=1",
                    "-c:v", "libx264", str(inbox / "X.mp4")], check=True)
    (work / "X" / "brief.json").write_text("{ сломано", encoding="utf-8")
    import jobqueue
    jobqueue.write_job("20-prep-X", [["python", "-c", "pass"]], queue=queue)   # как кладёт мозг
    woke = []
    saved = (studio_api.WORK_DIR, styles.WORK_DIR, studio_api.QUEUE,
             studio_api.ensure_runner, studio_api.runner_alive)
    studio_api.WORK_DIR, styles.WORK_DIR, studio_api.QUEUE = work, work, queue
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
        (studio_api.WORK_DIR, styles.WORK_DIR, studio_api.QUEUE,
         studio_api.ensure_runner, studio_api.runner_alive) = saved
        stack.close()
    report.check(marked and rejected, "битый бриф помечает свой ролик, а не роняет студию; кривой не сохраняется",
                 why if not marked else ("кривой бриф отвергнут" if rejected else "кривой бриф сохранился"))
    report.check(bool(woke), "задачу, которую мозг положил в очередь, студия запускает сама, без кнопки")

    # 17.10.2026: новое поле в project.json, старый сервер — 500 на всё состояние, в монтажной пропали
    # все проекты, а страница писала «сервер не отвечает». Битый проект помечается сам, причина видна
    with temp_projects(tmp / "studio_projects2", "main", "broken") as made:
        (made["broken"].root / "project.json").write_text('{"nonsense_field": 1}', encoding="utf-8")
        live = TestClient(app, base_url="http://127.0.0.1:8765", raise_server_exceptions=False)
        got = live.get("/api/studio/state")
        listed = {p["name"]: p for p in got.json().get("projects", [])} if got.status_code == 200 else {}
    report.check(got.status_code == 200 and "error" not in listed.get("main", {"error": 1})
                 and "nonsense_field" in listed.get("broken", {}).get("error", "")
                 and "nonsense_field" in (got.json().get("problem") or ""),
                 "битый project.json помечает свой проект и называет поле, остальные проекты на месте",
                 f"{got.status_code}: {sorted(listed)}")
    saved_view = studio_api.projects_view
    studio_api.projects_view = lambda: 1 / 0
    try:
        got = TestClient(app, base_url="http://127.0.0.1:8765", raise_server_exceptions=False).get("/api/studio/state")
    finally:
        studio_api.projects_view = saved_view
    try:
        said = got.json().get("error", "")
    except ValueError:
        said = got.text
    report.check(got.status_code == 500 and "division by zero" in said,
                 "упавший запрос студии отдаёт странице причину, а не голое «Internal Server Error»", said[:70])

    # 17.10.2026: ИИ ждал рендер своим циклом по логу («until grep ^exit») — строки нет, ход висел
    q = tmp / "wait_queue"
    for sub_dir in ("done", "failed", "logs"):
        (q / sub_dir).mkdir(parents=True)
    (q / "done" / "05-render-A.json").write_text("[]", encoding="utf-8")
    (q / "logs" / "05-render-A.log").write_text("✓ A_v1.mp4 готов\n", encoding="utf-8")
    (q / "failed" / "05-render-B.json").write_text("[]", encoding="utf-8")
    (q / "20-prep-C.json").write_text("[]", encoding="utf-8")
    # тот же рендер поставлен снова, а прошлый с этим именем лежит в done/ — ждать надо новый
    (q / "done" / "05-render-D.json").write_text("[]", encoding="utf-8")
    (q / "05-render-D.json").write_text("[]", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        codes = [jobqueue.wait(n, 0.3, queue=q, poll=0.1) for n in ("05-render-A", "05-render-B", "20-prep-C", "99-нет", "05-render-D")]
    report.check(codes == [0, 1, 2, 2, 2], "ожидание задачи очереди: готово — 0, упала — 1, идёт дольше срока или нет — 2, "
                 "повтор с тем же именем ждёт новую, а не прошлую из done/", str(codes))

    # 17.10.2026, IMG_3292 v2: трека не нашлось — ролик ушёл в рендер без музыки, сказано только в отчёте
    import verify_page
    with temp_projects(tmp / "music_projects", "loud", "quiet") as made:
        (made["loud"].root / "project.json").write_text('{"music": true}', encoding="utf-8")
        for name, folder in (("M1", "loud"), ("M2", "quiet")):
            (made[folder].input / f"{name}.mp4").write_bytes(b"")
        bare = '<audio id="sfx-hit" src="assets/sfx/pop.mp3" data-start="1.00" data-volume="0.5"></audio>'
        with_bgm = bare + '<audio id="sfx-bgm" src="assets/materials/yt-calm.mp3" data-start="0.00" data-volume="0.1"></audio>'
        verdicts = [verify_page.music_missing(bare, "M1"), verify_page.music_missing(with_bgm, "M1"),
                    verify_page.music_missing(bare, "M2")]
    report.check(bool(verdicts[0]) and verdicts[1] is None and verdicts[2] is None,
                 "проект просит музыку — ролик без трека не идёт в рендер; с треком и в проекте без музыки — идёт",
                 (verdicts[0] or "пропустил без музыки")[:70])

    # хук старта перезапускает сервер на старом коде — но не посреди хода ИИ или пачки
    import studio_up
    calls = []
    saved_up = (studio_up.ping, studio_up.stop_server, studio_up.start_server, studio_up.host.link_skills)
    def hook(ping_state):
        calls.clear()
        studio_up.ping = lambda timeout=0.6: dict(ping_state, tab_open=True) if "start" not in calls else {"app": "x", "tab_open": True}
        studio_up.stop_server = lambda: calls.append("stop")
        studio_up.start_server = lambda: calls.append("start") or True
        studio_up.host.link_skills = lambda: []
        saved_argv, saved_env = sys.argv, {k: os.environ.pop(k, None) for k in ("REELS_STUDIO_CHILD", "REELS_NO_STUDIO")}
        sys.argv = ["studio_up.py", "--no-open"]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                studio_up.main()
        finally:
            sys.argv = saved_argv
            os.environ.update({k: v for k, v in saved_env.items() if v is not None})
        return list(calls)
    try:
        now = studio_up.code_stamp()
        fresh = hook({"app": "montazh-reels", "code": now, "busy": None})
        stale = hook({"app": "montazh-reels", "code": now - 1, "busy": None})
        working = hook({"app": "montazh-reels", "code": now - 1, "busy": "ИИ монтирует"})
    finally:
        studio_up.ping, studio_up.stop_server, studio_up.start_server, studio_up.host.link_skills = saved_up
    report.check(fresh == [] and stale == ["stop", "start"] and working == [],
                 "хук старта перезапускает студию на старом коде, но не посреди работы ИИ",
                 f"свежий {fresh}, старый {stale}, занятый {working}")

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
    said = brain.explain_error("You've hit your session limit · resets 6:20am (Europe/Moscow)")
    report.check(said.startswith("Лимит"), "лимит сессии Claude — «Лимит», пачка останавливается, а не бежит по роликам",
                 said[:50])

    # 14.10.2026: результат с is_error пачка читала как обычный ответ и крутила ходы впустую
    failed = brain.parse_line("claude", json.dumps({"type": "result", "is_error": True,
                                                     "result": "Failed to authenticate. API Error: 403 Request not allowed"}))
    errors = [e["text"] for e in failed if e["type"] == "error"]
    report.check(bool(errors) and "не авторизован" in errors[0],
                 "ошибка входа мозга (403) — громкая ошибка, пачка останавливается", (errors or ["молча"])[0][:60])


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
    section(report, check_black_frames)
    section(report, check_pauses)
    section(report, check_captions)
    section(report, check_score)
    section(report, check_cleanup_on_failure, preset)
    section(report, check_long_runs)
    with tempfile.TemporaryDirectory(prefix="reels_selfcheck_") as tmpdir:
        tmp = Path(tmpdir)
        section(report, check_skill_links, tmp)
        section(report, check_gen_image, tmp)
        section(report, check_footage, tmp)
        section(report, check_sharpness, tmp)
        section(report, check_order, tmp)
        section(report, check_keys, tmp)
        section(report, check_fx, tmp)
        section(report, check_cutaway_rules, tmp)
        section(report, check_atomic_outputs, preset, tmp)
        section(report, check_transcript_source, tmp)
        section(report, check_page_timeline, tmp)
        section(report, check_timeline, tmp)
        section(report, check_grey_zones, tmp)
        section(report, check_plan, tmp)
        section(report, check_events, tmp)
        section(report, check_blueprint, tmp)
        section(report, check_design, tmp)
        section(report, check_trim, tmp)
        section(report, check_board, tmp)
        section(report, check_style_captions, tmp)
        section(report, check_formats, tmp)
        section(report, check_grades, tmp)
        section(report, check_studio_page, tmp)
        section(report, check_delete_video, tmp)
        section(report, check_studio, tmp)
        section(report, check_queue_control, tmp)
        section(report, check_web_import, tmp)
        section(report, check_cut_keeps_speech, preset, tmp)
        section(report, check_voice, preset, tmp)
        section(report, check_hdr, preset, tmp)
        section(report, check_fps_source, preset, tmp)
        section(report, check_face_exposure, tmp)
        section(report, check_look, preset, tmp)
        section(report, check_face_memory, tmp)
        section(report, check_matte_memory, tmp)
        section(report, check_cutout, tmp)
        section(report, check_cutout_video, tmp)
        section(report, check_matte_windows, tmp)
        section(report, check_portable, tmp)
        section(report, check_approve, tmp)
        section(report, check_projects, tmp)
        section(report, check_sections, tmp)
        section(report, check_packs, tmp)
        section(report, check_life_edit, tmp)
        section(report, check_batch, tmp)
        section(report, check_ai_workflow, tmp)
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
