#!/usr/bin/env python3
"""Финальная сборка: рез сегментов, смена крупности, субтитры, обработка голоса.

Собираем в два прохода, и это принципиально.

Раньше здесь был один filter_complex, в котором каждый сегмент читал один и тот же
вход [0:v]. ffmpeg на такое сам вставляет split на N выходов, trim при этом ничего
не перематывает — он пропускает через себя весь файл и выбрасывает лишнее, — а concat
забирает ветки строго по очереди. Пока идёт первая ветка, остальные N-1 продолжают
получать кадры и копят их в памяти. Кадр 1080×1920 это ~3 МБ, тридцать штук в секунду,
и на сотне сегментов машина уходит в своп и виснет намертво.

Поэтому: сегменты режутся по одному отдельными вызовами ffmpeg (память постоянная и
не зависит от их числа), потом склеиваются concat-демуксером, и только на втором
проходе накладываются субтитры и обработка голоса. Не возвращать один большой граф.
"""
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from common import FONT_DIR, WORK_DIR, ffmpeg_bin, plural, snap_segments
from look import look_filter

FADE = 0.012

# Выход всегда в стандартном диапазоне BT.709 и с честной пометкой об этом в файле:
# айфон пишет полный диапазон, и без пометки плееры читают одно и то же по-разному.
COLOR_TAGS = ["-color_range", "tv", "-colorspace", "bt709",
              "-color_primaries", "bt709", "-color_trc", "bt709"]


def even(value: float) -> int:
    """Размеры кадра должны быть чётными — иначе h264 ругается."""
    return int(round(value / 2) * 2)


def safe_name(stem: str) -> str:
    """Убирает из имени то, что ломает синтаксис фильтра ffmpeg (пробелы, двоеточия, кавычки).

    Буквы не трогаем — кириллица внутри filter_complex работает, а читать work/ проще.
    """
    return re.sub(r"[^\w.-]", "_", stem, flags=re.UNICODE) or "render"


def assign_zoom(segments: list, motion: dict) -> list:
    """Раздаёт сегментам крупность: картинка меняется на склейках, но не дёргается каждые полсекунды."""
    if not motion.get("punch_in", True):
        return [1.0] * len(segments)

    cycle = motion.get("zoom_cycle", [1.0, 1.07, 1.03, 1.11])
    min_hold = float(motion.get("min_hold_sec", 2.5))

    zooms, idx, held = [], 0, 0.0
    for start, end in segments:
        if held >= min_hold:
            idx = (idx + 1) % len(cycle)
            held = 0.0
        zooms.append(cycle[idx])
        held += end - start
    return zooms


def voice_chain(audio_cfg: dict, noise_floor: float | None = None) -> list:
    """Чистка голоса без нормализации: срез низов, шумодав, лёгкая компрессия.

    Порог шумодава (nf) — это уровень, ниже которого сигнал считается шумом. Раньше он
    стоял константой −24 дБ, то есть на уровне самого голоса: шумодав выедал согласные и
    делал речь «подводной». Теперь он замеряется по паузам этой же записи, а константа
    из пресета осталась только запасным вариантом.
    """
    chain = [f"highpass=f={audio_cfg.get('highpass', 80)}"]

    if audio_cfg.get("denoise", True):
        floor = noise_floor if noise_floor is not None else audio_cfg.get("noise_floor", -45)
        floor = max(-80.0, min(-20.0, float(floor)))          # рамки, которые понимает afftdn
        strength = max(0.01, min(97.0, float(audio_cfg.get("denoise_strength", 10))))
        chain.append(f"afftdn=nr={strength:g}:nf={floor:g}")

    if audio_cfg.get("compress", True):
        # мягче, чем было: жёсткая компрессия перед loudnorm заставляла звук «дышать»
        chain.append("acompressor=threshold=-20dB:ratio=2.5:attack=8:release=250:makeup=1")

    return chain


def loudnorm_filter(audio_cfg: dict, measured: dict | None = None) -> str:
    """Нормализация громкости. С замерами — один ровный проход, без них — динамический.

    Однопроходный loudnorm подстраивает усиление по ходу ролика: в паузах он поднимает
    шум комнаты, и звук начинает «дышать». Замеры снимаются отдельным проходом заранее.
    """
    target = audio_cfg.get("loudness_target", -14)
    peak = audio_cfg.get("true_peak", -1.5)
    base = f"loudnorm=I={target}:TP={peak}:LRA=11"
    if not measured:
        return base
    return (f"{base}:measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
            f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
            f"offset={measured['target_offset']}:linear=true")


def audio_chain(audio_cfg: dict, noise_floor: float | None = None,
                measured: dict | None = None) -> list:
    """Обработка голоса вешается один раз на уже склеенную дорожку, а не на каждый кусок."""
    if not audio_cfg.get("enabled", True):
        return ["anull"]                        # звук уходит как записан

    chain = voice_chain(audio_cfg, noise_floor)
    if audio_cfg.get("normalize", True):
        chain.append(loudnorm_filter(audio_cfg, measured))
    return chain


def measure_loudness(list_name: str, audio_cfg: dict, noise_floor: float | None,
                     cwd: Path) -> dict | None:
    """Первый проход нормализации: замеряет громкость уже обработанной дорожки.

    Идёт только по звуку (-vn), видео не декодируется — на двухминутном ролике это пара
    секунд. Не вышло замерить — возвращаем None, и loudnorm отработает однопроходно.
    """
    probe_chain = voice_chain(audio_cfg, noise_floor) + [
        f"loudnorm=I={audio_cfg.get('loudness_target', -14)}:"
        f"TP={audio_cfg.get('true_peak', -1.5)}:LRA=11:print_format=json"
    ]
    result = subprocess.run([
        ffmpeg_bin(), "-hide_banner", "-nostats",
        "-f", "concat", "-safe", "0", "-i", list_name,
        "-vn", "-af", ",".join(probe_chain), "-f", "null", "-",
    ], cwd=cwd, capture_output=True, text=True)

    match = re.search(r"\{[^{}]*\"input_i\"[\s\S]*?\}", result.stderr)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        values = {k: data[k] for k in
                  ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    except (json.JSONDecodeError, KeyError):
        return None

    # на тишине loudnorm отдаёт -inf: подставлять такое в фильтр нельзя
    if any(not math.isfinite(float(v)) for v in values.values()):
        return None
    return values


def bump(bitrate: str) -> str:
    """Промежуточные куски кодируем с запасом — их пережмут ещё раз на втором проходе."""
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KkMm]?)\s*", bitrate or "")
    if not match:
        return bitrate
    return f"{float(match.group(1)) * 2:g}{match.group(2)}"


def vcodec(video_cfg: dict, stage: str) -> list:
    encoder = video_cfg.get("encoder", "h264_videotoolbox")
    bitrate = video_cfg.get("bitrate", "12M")
    if encoder == "libx264":
        # на промежутке жмём мягче и быстрее: качество тут важнее размера, файл временный
        crf, preset = ("16", "veryfast") if stage == "segment" else ("19", "medium")
        return ["-c:v", "libx264", "-crf", crf, "-preset", preset]
    return ["-c:v", encoder,
            "-b:v", bump(bitrate) if stage == "segment" else bitrate,
            "-profile:v", "high"]


def concat_line(rel_path: str) -> str:
    """Строка для concat-демуксера: одинарные кавычки внутри имени надо экранировать."""
    return "file '" + rel_path.replace("'", "'\\''") + "'\n"


def ffmpeg_run(cmd: list, cwd: Path, what: str):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-20:])
        raise RuntimeError(f"ffmpeg упал на {what}:\n{tail}")
    return result


def prepare_assets(ass_path: Path | None, stem: str) -> str | None:
    """Шрифты и субтитры кладём рядом в work/ — libass ищет их относительно рабочей папки."""
    work_fonts = WORK_DIR / "fonts"
    work_fonts.mkdir(exist_ok=True)
    for font in FONT_DIR.iterdir():
        if font.suffix.lower() not in (".ttf", ".otf"):
            continue
        target = work_fonts / font.name
        if not target.exists() or target.stat().st_mtime < font.stat().st_mtime:
            shutil.copy2(font, target)

    if not (ass_path and ass_path.exists()):
        return None

    ass_name = f"{stem}.ass"
    target = WORK_DIR / ass_name
    if ass_path.resolve() != target.resolve():
        shutil.copy2(ass_path, target)
    return ass_name


def cut_segments(video: Path, segments: list, zooms: list, video_cfg: dict,
                 seg_dir: Path, look: dict | None = None) -> list:
    """Первый проход: каждый сегмент — отдельный вызов ffmpeg со своим seek по входу.

    -ss стоит до -i, поэтому ffmpeg перематывает вход, а не гонит через себя весь файл.
    Один декодер за раз — потребление памяти не зависит от количества сегментов.

    Длину куска задаёт trim/atrim, а не -t: -t, кратный кадру, отдаёт лишний кадр видео
    и при этом режет звук по-своему. trim даёт ровно N кадров и ровно столько же звука,
    иначе к концу ролика набегает сдвиг и субтитры уезжают от речи.
    """
    width, height = video_cfg["width"], video_cfg["height"]
    fps = video_cfg.get("fps", 30)
    src = str(video.resolve())
    total = len(segments)
    # цвет крутится уже после приведения к 16–235: кривая яркости рассчитана на этот диапазон
    grade = look_filter(look)
    grade = f",{grade}" if grade else ""

    seg_files = []
    for i, ((start, end), zoom) in enumerate(zip(segments, zooms)):
        frames = max(1, round((end - start) * fps))
        duration = frames / fps
        zw, zh = even(width * zoom), even(height * zoom)
        # микрофейды на стыках убирают щелчки от реза посреди волны
        out_at = max(0.0, duration - FADE)
        seg_file = seg_dir / f"seg_{i:04d}.mov"

        cmd = [
            ffmpeg_bin(), "-y", "-loglevel", "error",
            # запас на входе, чтобы trim точно нашёл нужные кадры; читается всё равно только он
            "-ss", f"{start:.6f}", "-t", f"{duration + 1.0:.6f}", "-i", src,
            "-filter_complex",
            (f"[0:v]trim=0:{duration:.6f},setpts=PTS-STARTPTS,"
             f"scale={zw}:{zh}:force_original_aspect_ratio=increase:out_range=tv,"
             f"format=yuv420p,crop={width}:{height},setsar=1{grade}[v];"
             f"[0:a]atrim=0:{duration:.6f},asetpts=PTS-STARTPTS,"
             f"afade=t=in:st=0:d={FADE},afade=t=out:st={out_at:.3f}:d={FADE}[a]"),
            "-map", "[v]", "-map", "[a]",
            *vcodec(video_cfg, "segment"),
            "-r", str(fps), "-fps_mode", "cfr", "-pix_fmt", "yuv420p", *COLOR_TAGS,
            # промежуточный звук держим несжатым: его ещё раз обрабатывать на втором проходе
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
            str(seg_file),
        ]
        ffmpeg_run(cmd, WORK_DIR, f"сегменте {i + 1}/{total}")
        seg_files.append(seg_file)

        if (i + 1) % 20 == 0 or i + 1 == total:
            print(f"     {i + 1}/{total}", flush=True)

    return seg_files


def render(video: Path, out_path: Path, segments: list, preset: dict,
           ass_path: Path | None = None, noise_floor: float | None = None) -> Path:
    video_cfg = preset["video"]
    fps = video_cfg.get("fps", 30)

    WORK_DIR.mkdir(exist_ok=True)
    # план уже приходит по сетке кадров, но операция идемпотентная — страхуемся от других вызовов
    segments = snap_segments(segments, fps)
    stem = safe_name(video.stem)
    ass_name = prepare_assets(ass_path, stem)
    zooms = assign_zoom(segments, preset.get("motion", {}))

    seg_dir = WORK_DIR / f"{stem}_segments"
    if seg_dir.exists():
        shutil.rmtree(seg_dir)
    seg_dir.mkdir(parents=True)

    list_file = WORK_DIR / f"{stem}.concat.txt"
    filter_file = WORK_DIR / f"{stem}.filter"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Итог пишется рядом под временным именем и встаёт на место только целым. Раньше ffmpeg
    # писал прямо в output/ (или в aroll.mp4): упавшая сборка оставляла битый файл под
    # настоящим именем — студия показывала его готовым — и стирала прошлый удачный.
    part = out_path.with_name(f".{out_path.stem}.part{out_path.suffix}")

    try:
        print(f"  → режу {plural(len(segments), 'сегмент', 'сегмента', 'сегментов')}", flush=True)
        seg_files = cut_segments(video, segments, zooms, video_cfg, seg_dir,
                                 look=preset.get("look"))

        list_file.write_text(
            "".join(concat_line(f"{seg_dir.name}/{f.name}") for f in seg_files),
            encoding="utf-8",
        )

        vfilter = (f"[0:v]ass=f={ass_name}:fontsdir=fonts[vout];" if ass_name
                   else "[0:v]null[vout];")

        audio_cfg = preset.get("audio", {})
        measured = None
        if audio_cfg.get("enabled", True) and audio_cfg.get("normalize", True):
            print("  → замеряю громкость", flush=True)
            measured = measure_loudness(list_file.name, audio_cfg, noise_floor, WORK_DIR)
            if measured is None:
                print("  ⚠ громкость замерить не вышло — нормализую на ходу", flush=True)

        chain = audio_chain(audio_cfg, noise_floor, measured)
        filter_file.write_text(f"{vfilter}\n[0:a]{','.join(chain)}[aout]", encoding="utf-8")

        cmd = [
            ffmpeg_bin(), "-y", "-loglevel", "error", "-stats",
            "-f", "concat", "-safe", "0", "-i", list_file.name,
            "-filter_complex_script", filter_file.name,
            "-map", "[vout]", "-map", "[aout]",
            *vcodec(video_cfg, "final"),
            "-r", str(fps), "-fps_mode", "cfr", "-pix_fmt", "yuv420p", *COLOR_TAGS,
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart",
            str(part.resolve()),
        ]
        print("  → склеиваю, накладываю субтитры и чищу голос", flush=True)
        ffmpeg_run(cmd, WORK_DIR, "финальной сборке")
        part.replace(out_path)
    finally:
        # временные куски весят прилично — убираем даже если упали посередине
        shutil.rmtree(seg_dir, ignore_errors=True)
        list_file.unlink(missing_ok=True)
        part.unlink(missing_ok=True)

    return out_path
