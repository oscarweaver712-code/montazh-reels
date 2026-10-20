#!/usr/bin/env python3
"""Сборка: один ролик из нескольких видео (20.10.2026).

Просьба: «монтировать одно видео из нескольких сразу». До этого ролик был ровно одним исходником,
а заказ пришёл пачкой клипов с одного события (новоселье «Вкудесника»: 9 клипов, 3,5 мин, ролик — до
1,5 мин). Сборка отбирает куски из всех клипов в нужном порядке и склеивает их в один дубль — дальше
работает обычный конвейер (prep, track, compose, страница, рендер), ничего в нём не зная о клипах,
кроме стыков: там меняется сцена, и камера с субтитрами через стык не переезжают.

  projects/<проект>/input/<имя>/        папка с клипами — сырьё ОДНОГО ролика <имя>
  work/<имя>/pack/                       речь, тишина и листы кадров каждого клипа (кэш разбора)
  work/<имя>/pack.md                     меню режиссёра: клипы, фразы с таймкодами, где листы кадров
  work/<имя>/pack.json                   решение режиссёра: какие куски и в каком порядке
  projects/<проект>/input/<имя>.mov      собранный дубль — исходник ролика для всего конвейера
  work/<имя>/pack.built.json             как собрано: куски на шкале сборки и стыки (prep → aroll.json → scenes)

pack.json:
  {"pieces": [
     {"clip": "IMG_6703.MOV", "from": 0.0, "to": 4.4, "why": "хук: устроила новоселье"},
     {"clip": "IMG_6709.MOV", "from": 3.0, "to": 13.0, "speed": 2.0, "why": "идёт встречать — ускорено"},
     {"clip": "IMG_6711.MOV", "from": 0.0, "to": 2.8, "gain": 3, "why": "тост"}
  ]}
  from, to — секунды клипа. Кусок с речью сам уезжает краями в тишину (инвариант 3: whisper ставит конец
             слова раньше, чем человек договорил); кусок без слов режется как написано (по сетке кадров).
  exact    — true: резать ровно по from/to, даже если там речь (оборванная фраза на хуке — осознанно).
  speed    — ускорение 0.5–4. Кусок со словами — не быстрее 1.25: голос иначе мультяшный (громкий отказ).
  gain     — дБ поверх выравнивания громкости; mute — без звука (там будет музыка).
  fit      — "cover" (по умолчанию: кадр заполнен, лишнее по краям) или "blur" (клип целиком поверх своей
             размытой копии) — для клипа других пропорций; без fit такой клип — отказ, а не лицо за краем.
  cut      — каким будет стык перед куском: "scene" (смена сцены: камера заново, субтитр не переходит) или "jump"
             (склейка внутри одного плана — вырезанная пауза или оговорка: её прячет смена плана со смазом). По
             умолчанию — jump, если кусок того же клипа идёт дальше по времени с той же скоростью, иначе scene.

Громкость: куски с речью приводятся к общей громкости речи (ebur128 по каждому куску): клипы
сняты разными телефонами и на разном расстоянии, и без этого голос прыгал бы на каждом стыке.

  .venv/bin/python scripts/pack.py <имя>            # разбор клипов → work/<имя>/pack.md (очередь: 10-pack-<имя>)
  .venv/bin/python scripts/pack.py <имя> --check    # pack.json годен: клипы есть, куски внутри, хронометраж
  .venv/bin/python scripts/pack.py <имя> --build    # сборка по pack.json → input/<имя>.mov (очередь: 20-prep-<имя>,
                                                    #   следом — prep.py, track.py: стыки prep возьмёт сам)
"""
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import formats
import projects
import numpy as np

from common import WORK_DIR, decode_threads, detect_voice, ffmpeg_bin, probe, require_queue
from cut import MIN_WORD_LAP
from look import hdr_to_sdr
from prep import AIR, find_edges, load_edit, pick_format, speech_language
from render import COLOR_TAGS, concat_line, even, vcodec
from transcribe import run_transcribe

FPS = 30
SHEET_COLS, SHEET_TILES = 6, 24
SPEECH_SPEED_MAX = 1.25          # речь быстрее — мультяшный голос
FIT = ("cover", "blur")
ASPECT_SLACK = 0.12              # пропорции клипа и ролика расходятся больше — нужен явный fit
GAIN_MAX = 12.0                  # дБ: выравнивание громкости не тянет кусок сильнее
EDGE_KEYS = ("trim", "drop", "bleep", "blooper")   # решения edit.json по шкале сборки — устаревают с пересборкой
CUTS = ("scene", "jump")         # стык: смена сцены — или склейка внутри одного плана (вырезана пауза, оговорка)


def cut_kind(prev: dict, piece: dict) -> str:
    """Стык перед куском: тот же клип дальше по времени — склейка внутри плана (прячется как склейка дубля: смена
    плана, смаз), иначе — смена сцены. "cut" в pack.json решает явно (тот же клип после резкого разворота — сцена)."""
    if piece.get("cut"):
        return piece["cut"]
    same = piece["clip"] == prev["clip"] and piece["start"] >= prev["end"] - 0.01 and piece["speed"] == prev["speed"]
    return "jump" if same else "scene"


class PackError(Exception):
    """Понятная ошибка сборки — для человека."""


# ---------------------------------------------------------------- где что лежит

def folder(stem: str) -> Path:
    try:
        found = projects.pack_of(stem)
    except projects.ProjectError as e:
        raise PackError(str(e))
    if not found:
        raise PackError(f"Сборки {stem} нет: нужна папка projects/<проект>/input/{stem}/ с видео — "
                        "все клипы, из которых собирается один ролик")
    return found


def clips(stem: str) -> list:
    return projects.pack_clips(folder(stem))


def cache_dir(stem: str) -> Path:
    return WORK_DIR / stem / "pack"


def built_path(stem: str) -> Path:
    return folder(stem).parent / f"{stem}.mov"


def load_built(stem: str) -> dict | None:
    """pack.built.json, если сборка есть и собранный файл — тот же (размер сходится); иначе None."""
    path = WORK_DIR / stem / "pack.built.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    out = Path(data.get("file", ""))
    if not out.exists() or out.stat().st_size != data.get("size"):
        return None
    return data


# ---------------------------------------------------------------- разбор клипов

QUIET_ABOVE_FLOOR = 7.0         # дБ: пауза — громкость у пола шума клипа, не выше него на столько
WINDOW = 0.02                   # с: окно огибающей


def quiet_spans(clip: Path, min_len: float = 0.10) -> list:
    """Паузы клипа по его собственному полу шума: [(начало, конец)].

    Порог −35 дБ (detect_silence) рассчитан на дубли Валеры у микрофона. Клипы сборки сняты телефоном на расстоянии:
    в интервью новоселья речь шла на −27…−30 дБ при фоне офиса −42…−44, и порог −35 не нашёл ни одной паузы — края
    кусков встали бы по таймингам whisper, которые врут на 0,3–0,4 с (инвариант 3). Пол шума — 10-й перцентиль
    огибающей; пауза — дольше min_len не громче пола + QUIET_ABOVE_FLOOR (но не громче −35, как раньше). Звук читается
    потоком — память не зависит от длины клипа.
    """
    proc = subprocess.Popen([ffmpeg_bin(), "-v", "error", "-i", str(clip), "-vn", "-ac", "1", "-ar", "16000",
                             "-f", "s16le", "-"], stdout=subprocess.PIPE)
    hop, levels = int(16000 * WINDOW), []
    try:
        while chunk := proc.stdout.read(hop * 2 * 50):
            x = np.frombuffer(chunk[:len(chunk) // (hop * 2) * hop * 2], np.int16).astype(np.float32) / 32768
            if len(x):
                levels += list(20 * np.log10(np.sqrt((x.reshape(-1, hop) ** 2).mean(1)) + 1e-9))
    finally:
        proc.stdout.close()
        proc.wait()
    if not levels:
        return []
    env = np.array(levels)
    limit = min(-35.0, float(np.percentile(env, 10)) + QUIET_ABOVE_FLOOR)
    out, start = [], None
    for k, quiet in enumerate(list(env <= limit) + [False]):
        if quiet and start is None:
            start = k
        elif not quiet and start is not None:
            if (k - start) * WINDOW >= min_len:
                out.append([round(start * WINDOW, 3), round(k * WINDOW, 3)])
            start = None
    return out


def clip_info(stem: str, clip: Path, language: str) -> dict:
    """Речь (кэш work/<имя>/pack/<клип>.words.json), тишина и голос клипа — всё, что нужно для краёв кусков."""
    cache = cache_dir(stem)
    words = run_transcribe(clip, language=language, cache_dir=cache)["words"]
    marks = cache / f"{clip.stem}.audio.json"
    size = clip.stat().st_size
    data = json.loads(marks.read_text(encoding="utf-8")) if marks.exists() else {}
    if data.get("size") != size or data.get("v") != 2:
        info = probe(clip)
        data = {"size": size, "v": 2, "info": info, "silences": [], "voice": []}
        if info["has_audio"]:
            data["silences"] = quiet_spans(clip)
            data["voice"] = detect_voice(clip)
        marks.write_text(json.dumps(data), encoding="utf-8")
    return {"words": words, **data}


def clip_sheet(stem: str, clip: Path, duration: float) -> tuple:
    """Лист кадров клипа: плитки слева направо, сверху вниз, каждая step с; первая — 0 с."""
    step = max(1.0, round(duration / SHEET_TILES + 0.05, 1))
    out = cache_dir(stem) / f"{clip.stem}.jpg"
    if out.exists() and out.stat().st_mtime >= clip.stat().st_mtime:
        return out, step
    rows = math.ceil(math.ceil(duration / step) / SHEET_COLS)
    info = probe(clip)
    hdr = hdr_to_sdr(info)
    result = subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-threads", "2", *decode_threads(info), "-i", str(clip),
                             "-vf", f"fps=1/{step:g}:round=down,scale=216:-2,{hdr + ',' if hdr else ''}"
                                    f"tile={SHEET_COLS}x{rows}:padding=4:color=white",
                             "-frames:v", "1", str(out)], capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise PackError(f"Лист кадров {clip.name} не собрался:\n{result.stderr[-400:]}")
    return out, step


def phrases(words: list, gap: float = 0.6) -> list:
    """Слова → фразы [(начало, конец, текст)]: по точке или паузе длиннее gap."""
    out, cur = [], []
    for w in words:
        if cur and (w["start"] - cur[-1]["end"] >= gap or cur[-1]["word"].rstrip()[-1:] in ".?!…"):
            out.append((cur[0]["start"], cur[-1]["end"], " ".join(x["word"] for x in cur)))
            cur = []
        cur.append(w)
    if cur:
        out.append((cur[0]["start"], cur[-1]["end"], " ".join(x["word"] for x in cur)))
    return out


def scan(stem: str) -> Path:
    """Разбор сборки: речь и листы кадров каждого клипа → work/<имя>/pack.md — по нему режиссёр пишет pack.json."""
    require_queue("разбор сборки")
    files = clips(stem)
    project = projects.of(stem)
    language = speech_language(stem, load_edit(stem))
    cache_dir(stem).mkdir(parents=True, exist_ok=True)
    lines = [f"# Сборка {stem}: {len(files)} клипов", "",
             f"Папка: {projects.rel(folder(stem))}. Проект: {project.name} — «{project.title}».",
             "Решение — work/{0}/pack.json (формат — docstring scripts/pack.py); проверка — "
             "`pack.py {0} --check`. Листы кадров: плитки слева направо, сверху вниз, первая — 0 с.".format(stem), ""]
    total = 0.0
    for clip in files:
        print(f"▶ {clip.name}", flush=True)
        data = clip_info(stem, clip, language)
        info = data["info"]
        total += info["duration"]
        sheet, step = clip_sheet(stem, clip, info["duration"])
        shape = "вертикаль" if info["height"] > info["width"] else ("квадрат" if info["height"] == info["width"]
                                                                       else "горизонталь")
        lines += [f"## {clip.name} — {info['duration']:.1f} с, {info['width']}×{info['height']} ({shape}), "
                  f"{info['fps']:.0f} к/с{'' if info['has_audio'] else ', без звука'}",
                  f"Лист кадров: {projects.rel(sheet)} (плитка — {step:g} с)", ""]
        said = phrases(data["words"])
        lines += [f"- [{a:5.1f}–{b:5.1f}] {text}" for a, b, text in said] or ["- (слов нет — только картинка и звук)"]
        voiced = sum(b - a for a, b in data["voice"])
        lines += ["", f"Голос звучит {voiced:.1f} с из {info['duration']:.1f}.", ""]
    lines.insert(3, f"Всего: {total:.1f} с ({total / 60:.1f} мин).")
    out = WORK_DIR / stem / "pack.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✓ меню сборки: {projects.rel(out)} — прочитай, посмотри листы кадров и напиши work/{stem}/pack.json")
    return out


# ---------------------------------------------------------------- решение режиссёра

def load_plan(stem: str) -> list:
    path = WORK_DIR / stem / "pack.json"
    if not path.exists():
        raise PackError(f"Нет work/{stem}/pack.json — сначала разбор (pack.py {stem}), потом решение: какие куски "
                        "каких клипов и в каком порядке (формат — docstring scripts/pack.py)")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise PackError(f"work/{stem}/pack.json: битый JSON ({e})")
    pieces = data.get("pieces") if isinstance(data, dict) else None
    if not isinstance(pieces, list) or not pieces:
        raise PackError(f"work/{stem}/pack.json: нужен список pieces хотя бы с одним куском")
    return pieces


def check_plan(stem: str, pieces: list, durations: dict) -> list:
    """Куски решения → нормальный вид. Всё, что не так, — одной ошибкой со всеми причинами."""
    problems, out = [], []
    known = {"clip", "from", "to", "speed", "gain", "mute", "fit", "exact", "cut", "why"}
    for n, p in enumerate(pieces, 1):
        where = f"кусок {n}"
        if not isinstance(p, dict):
            problems.append(f"{where}: должен быть объектом {{clip, from, to}}")
            continue
        extra = set(p) - known
        if extra:
            problems.append(f"{where}: не знаю полей {', '.join(sorted(extra))} (есть: {', '.join(sorted(known))})")
        name = str(p.get("clip", ""))
        if name not in durations:
            problems.append(f"{where}: клипа «{name}» нет в сборке (есть: {', '.join(durations)})")
            continue
        try:
            a, b = float(p["from"]), float(p["to"])
        except (KeyError, TypeError, ValueError):
            problems.append(f"{where} ({name}): from и to — числа секунд клипа")
            continue
        dur = durations[name]
        if not 0 <= a < b <= dur + 0.05:
            problems.append(f"{where} ({name}): {a:g}–{b:g} с вне клипа 0–{dur:.2f} с")
            continue
        speed = float(p.get("speed", 1.0))
        if not 0.5 <= speed <= 4.0:
            problems.append(f"{where} ({name}): speed {speed:g} — бывает от 0.5 до 4")
        fit = p.get("fit", "cover")
        if fit not in FIT:
            problems.append(f"{where} ({name}): fit «{fit}» — бывает {' или '.join(FIT)}")
        if p.get("cut") not in (None, *CUTS):
            problems.append(f"{where} ({name}): cut «{p['cut']}» — бывает {' или '.join(CUTS)}")
        out.append({"clip": name, "from": a, "to": min(b, dur), "speed": speed, "gain": float(p.get("gain", 0.0)),
                    "mute": bool(p.get("mute")), "fit": fit, "exact": bool(p.get("exact")), "cut": p.get("cut"),
                    "why": p.get("why", "")})
    if problems:
        raise PackError(f"work/{stem}/pack.json:\n  " + "\n  ".join(problems))
    return out


# ---------------------------------------------------------------- края и громкость

def edges(piece: dict, data: dict) -> tuple:
    """Края куска в секундах клипа: со словами — в тишине (find_edges, как начало и конец дубля), без слов —
    как написано. Возвращает (начало, конец, есть ли речь)."""
    a, b = piece["from"], piece["to"]
    inside = [w for w in data["words"] if a - 0.05 <= w["start"] < b]
    if not inside or piece["exact"] or piece["mute"]:
        return a, b, bool(inside) and not piece["mute"]
    start, end = find_edges(data["words"], [tuple(s) for s in data["silences"]], a, b, AIR, voice=data["voice"])
    return max(0.0, start), min(end, data["info"]["duration"]), True


def loudness(clip: Path, a: float, b: float) -> float | None:
    """Интегральная громкость куска (LUFS, ebur128: паузы отсекает сам). Тишина или сбой — None."""
    result = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}",
                             "-i", str(clip), "-vn", "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
                            capture_output=True, encoding="utf-8", errors="replace")
    found = re.findall(r"I:\s*(-?[\d.]+|-inf)\s*LUFS", result.stderr)
    if not found or found[-1] == "-inf":
        return None
    value = float(found[-1])
    return value if value > -70 else None


def atempo(speed: float) -> str:
    """atempo по ступеням: одна ступень надёжна в 0.5–2, дальше — цепочкой."""
    steps, left = [], speed
    while left > 2.0:
        steps.append(2.0)
        left /= 2.0
    while left < 0.5:
        steps.append(0.5)
        left /= 0.5
    steps.append(left)
    return ",".join(f"atempo={s:.6f}" for s in steps if abs(s - 1.0) > 1e-6) or "anull"


# ---------------------------------------------------------------- сборка

def canvas(stem: str, infos: list) -> tuple:
    """Кадр сборки: формат ролика, с запасом до ×1.5, если клипы это позволяют (дубль для страницы, prep --hq)."""
    fmt = pick_format(stem, load_edit(stem))
    w, h = formats.size(fmt)
    shortest = sorted(min(i["width"], i["height"]) for i in infos)[len(infos) // 2]
    k = max(1.0, min(1.5, shortest / min(w, h)))
    return fmt, even(w * k), even(h * k)


def cut_piece(clip: Path, info: dict, piece: dict, size: tuple, gain: float, out: Path, bitrate: str) -> int:
    """Один кусок — один вызов ffmpeg (память постоянная, инвариант 1). Возвращает число кадров.

    Длина — trim/atrim по числу кадров, а не -t (инвариант 4): N кадров видео и ровно N/30 с звука,
    иначе к концу ролика набегает сдвиг и субтитры уезжают от речи.
    """
    w, h = size
    a, b, speed = piece["start"], piece["end"], piece["speed"]
    frames = max(1, round((b - a) / speed * FPS))
    samples = round(frames / FPS * 48000)
    hdr = hdr_to_sdr(info)
    hdr = f"{hdr}," if hdr else ""
    base = f"[0:v]trim=0:{b - a:.6f},setpts=(PTS-STARTPTS)/{speed:.6f},fps={FPS}"
    if piece["fit"] == "blur":
        video = (f"{base},split[s0][s1];"
                 f"[s0]scale={w}:{h}:force_original_aspect_ratio=increase:out_range=tv,{hdr}format=yuv420p,"
                 f"crop={w}:{h},boxblur=36:2,eq=brightness=-0.06[bg];"
                 f"[s1]scale={w}:{h}:force_original_aspect_ratio=decrease:out_range=tv,{hdr}format=yuv420p[fg];"
                 f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,trim=end_frame={frames}[v]")
    else:
        video = (f"{base},scale={w}:{h}:force_original_aspect_ratio=increase:out_range=tv,{hdr}format=yuv420p,"
                 f"crop={w}:{h},setsar=1,trim=end_frame={frames}[v]")
    if info["has_audio"] and not piece["mute"]:
        audio = (f"[0:a]atrim=0:{b - a:.6f},asetpts=PTS-STARTPTS,{atempo(speed)},aresample=48000,"
                 f"aformat=channel_layouts=stereo,volume={gain:.2f}dB,apad=whole_len={samples},"
                 f"atrim=end_sample={samples},afade=t=in:d=0.012,"
                 f"afade=t=out:st={max(0.0, frames / FPS - 0.012):.4f}:d=0.012[a]")
        extra = []
    else:
        audio = f"[1:a]atrim=end_sample={samples}[a]"
        extra = ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    cmd = [ffmpeg_bin(), "-y", "-loglevel", "error", *decode_threads(info),
           "-ss", f"{a:.6f}", "-t", f"{b - a + 1.0:.6f}", "-i", str(clip), *extra,
           "-filter_complex", f"{video};{audio}", "-map", "[v]", "-map", "[a]",
           *vcodec({"bitrate": bitrate}, "segment"), "-r", str(FPS), "-fps_mode", "cfr", "-pix_fmt", "yuv420p",
           *COLOR_TAGS, "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(out)]
    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-12:])
        raise PackError(f"ffmpeg упал на куске {clip.name} {a:.2f}–{b:.2f} с:\n{tail}")
    return frames


def remap_clip_words(pieces: list, datas: dict) -> list:
    """Слова клипов → на шкалу сборки: слово принадлежит куску, где лежит его середина; время делится на speed.

    Две ловушки whisper (новоселье, 20.10.2026): «Ну» из «Ну что, иду встречать» он растянул на 0,00–1,76 при голосе с
    1,68 — середина вне куска, и первое слово пропадало (как в cut.remap_words); «ну» из «Ой, ну я в восторге» пришло
    нулевой длины и выкидывалось как пустое. Слово, которое начинается до куска, но заходит в него хотя бы слогом
    (MIN_WORD_LAP), — в куске; нулевое слово получает кадр длины.
    """
    out = []
    for p in pieces:
        if p["mute"]:
            continue
        for w in datas[p["clip"]]["words"]:
            mid = (w["start"] + w["end"]) / 2
            leading = w["start"] < p["start"] < w["end"] and w["end"] - p["start"] >= MIN_WORD_LAP
            if not (p["start"] <= mid < p["end"] or leading):
                continue
            s = p["t0"] + (max(w["start"], p["start"]) - p["start"]) / p["speed"]
            e = p["t0"] + (min(w["end"], p["end"]) - p["start"]) / p["speed"]
            e = max(e, s + 1 / FPS) if mid < p["end"] else e
            if e > s:
                out.append({"word": w["word"], "start": round(s, 3), "end": round(e, 3), "prob": w.get("prob", 1.0)})
    return out


def stale_edit(stem: str, raw: list) -> list:
    """Решения edit.json по шкале сборки (trim, drop, bleep, blooper), если сборка меняется, — они от старой."""
    edit = load_edit(stem)
    old = WORK_DIR / stem / "pack.built.json"
    if not old.exists() or not any(edit.get(k) for k in EDGE_KEYS):
        return []
    was = json.loads(old.read_text(encoding="utf-8")).get("plan")
    return [k for k in EDGE_KEYS if edit.get(k)] if was != raw else []


def build(stem: str) -> Path:
    require_queue("сборка из нескольких видео")
    started = time.time()
    files = {c.name: c for c in clips(stem)}
    language = speech_language(stem, load_edit(stem))
    datas = {name: clip_info(stem, path, language) for name, path in files.items()}
    raw = load_plan(stem)
    plan = check_plan(stem, raw, {n: d["info"]["duration"] for n, d in datas.items()})
    stale = stale_edit(stem, raw)
    if stale:
        raise PackError(f"Сборка меняется, а в work/{stem}/edit.json есть {', '.join(stale)} — они по шкале старой "
                        f"сборки и легли бы не туда. Режь кусками pack.json; если они всё же нужны — убери их из "
                        f"edit.json, собери и поставь заново по новой шкале")
    fmt, w, h = canvas(stem, [datas[p["clip"]]["info"] for p in plan])
    problems = []
    for n, p in enumerate(plan, 1):
        info = datas[p["clip"]]["info"]
        mismatch = (info["width"] / info["height"]) / (w / h)
        lost = 1 - min(mismatch, 1 / mismatch)
        if p["fit"] == "cover" and lost > ASPECT_SLACK and "fit" not in raw[n - 1]:
            problems.append(f"кусок {n} ({p['clip']}): клип {info['width']}×{info['height']}, ролик {fmt} — по краям "
                            f"ушло бы {lost:.0%} кадра. Поставь \"fit\": \"blur\" (клип целиком поверх размытой "
                            f"копии) или \"cover\" осознанно")
        p["start"], p["end"], p["speech"] = edges(p, datas[p["clip"]])
        if p["speech"] and p["speed"] > SPEECH_SPEED_MAX:
            problems.append(f"кусок {n} ({p['clip']}): в нём речь, а speed {p['speed']:g} — голос станет мультяшным "
                            f"(не быстрее {SPEECH_SPEED_MAX:g}); ускоряй куски без слов или поставь mute")
    if problems:
        raise PackError(f"work/{stem}/pack.json:\n  " + "\n  ".join(problems))

    # громкость речи — к общей: медиана кусков с речью; куски без речи — как записаны (+ gain)
    levels = {n: loudness(files[p["clip"]], p["start"], p["end"]) for n, p in enumerate(plan) if p["speech"]}
    known = sorted(v for v in levels.values() if v is not None)
    target = known[len(known) // 2] if known else None
    for n, p in enumerate(plan):
        auto = 0.0
        if target is not None and levels.get(n) is not None:
            auto = max(-GAIN_MAX, min(GAIN_MAX, target - levels[n]))
        p["auto_gain"] = round(auto, 2)

    out = built_path(stem)
    tmp = WORK_DIR / stem / ".pack_pieces"
    part = out.with_name(f".{out.stem}.part{out.suffix}")
    bitrate = f"{max(12, round(24 * (w * h) / (1080 * 1920)))}M"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    print(f"▶ сборка {stem}: {len(plan)} кусков из {len(set(p['clip'] for p in plan))} клипов → {w}×{h}, {fmt}",
          flush=True)
    try:
        acc, files_out = 0, []
        for n, p in enumerate(plan):
            piece_file = tmp / f"piece_{n:03d}.mov"
            frames = cut_piece(files[p["clip"]], datas[p["clip"]]["info"], p, (w, h), p["auto_gain"] + p["gain"],
                               piece_file, bitrate)
            p["t0"], p["t1"], p["frames"] = round(acc / FPS, 6), round((acc + frames) / FPS, 6), frames
            acc += frames
            files_out.append(piece_file)
            speed = f" ×{p['speed']:g}" if p["speed"] != 1 else ""
            level = f"  {p['auto_gain']:+.1f} дБ" if p["auto_gain"] else ""
            print(f"  {n + 1:>2}. {p['clip']} {p['start']:6.2f}–{p['end']:6.2f}{speed} → {p['t0']:6.2f}–{p['t1']:6.2f}"
                  f"{'  речь' if p['speech'] else ''}{level}", flush=True)
        listing = tmp / "list.txt"
        listing.write_text("".join(concat_line(f.name) for f in files_out), encoding="utf-8")
        result = subprocess.run([ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                                 "-i", listing.name, "-c", "copy", "-movflags", "+faststart", str(part.resolve())],
                                cwd=tmp, capture_output=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise PackError(f"ffmpeg не склеил куски:\n{result.stderr[-600:]}")
        got = probe(part)["duration"]
        if abs(got - acc / FPS) > 1.5 / FPS:
            raise PackError(f"Сборка вышла {got:.3f} с, а кусков на {acc / FPS:.3f} с — кадры разъехались бы с "
                            "субтитрами, не отдаю")
        part.replace(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        part.unlink(missing_ok=True)

    # слова клипов — на шкалу сборки: транскрипт ролика из них же, без второго прохода whisper (кэш run_transcribe)
    words = remap_clip_words(plan, datas)
    text = " ".join(w["word"] for w in words)
    (WORK_DIR / f"{stem}.words.json").write_text(json.dumps({"words": words, "text": text, "language": language},
                                                            ensure_ascii=False, indent=1), encoding="utf-8")
    (WORK_DIR / f"{stem}.txt").write_text(text, encoding="utf-8")
    (WORK_DIR / f"{stem}.source.json").write_text(json.dumps({"name": out.name, "size": out.stat().st_size}),
                                                  encoding="utf-8")
    joins = [p["t0"] for prev, p in zip(plan, plan[1:]) if cut_kind(prev, p) == "scene"]
    cuts = [p["t0"] for prev, p in zip(plan, plan[1:]) if cut_kind(prev, p) == "jump"]
    (WORK_DIR / stem / "pack.built.json").write_text(json.dumps({
        "file": str(out), "size": out.stat().st_size, "fps": FPS, "format": fmt, "width": w, "height": h,
        "duration": acc / FPS, "joins": joins, "cuts": cuts, "plan": raw,
        "pieces": [{k: p[k] for k in ("clip", "start", "end", "speed", "t0", "t1", "frames", "speech", "auto_gain",
                                      "gain", "mute", "fit", "why")} for p in plan],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    # дубль, камера и маска от прошлой сборки — уже не про этот файл: без aroll.json дальше всё скажет «сначала prep»
    for name in ("aroll.json",):
        (WORK_DIR / stem / name).unlink(missing_ok=True)
    later = [n for n in ("director.json", "score.json", "page.py") if (WORK_DIR / stem / n).exists()]
    print(f"✓ собрано за {time.time() - started:.0f} с: {acc / FPS:.1f} с, {len(plan)} кусков, смен сцены {len(joins)}"
          f"{f', склеек внутри плана {len(cuts)}' if cuts else ''} → {projects.rel(out)}")
    if later:
        print(f"  ⚠ у ролика уже есть {', '.join(later)} — они по шкале прошлой сборки: номера слов и тайминги "
              f"сверь заново после prep")
    return out


def summary(stem: str) -> None:
    """--check: решение читается, клипы есть; сколько выйдет (до краёв в тишине — грубо)."""
    files = {c.name: c for c in clips(stem)}
    durations = {}
    for name, path in files.items():
        marks = cache_dir(stem) / f"{path.stem}.audio.json"
        durations[name] = (json.loads(marks.read_text(encoding="utf-8"))["info"]["duration"] if marks.exists()
                           else probe(path)["duration"])
    plan = check_plan(stem, load_plan(stem), durations)
    total = sum((p["to"] - p["from"]) / p["speed"] for p in plan)
    for n, p in enumerate(plan, 1):
        speed = f" ×{p['speed']:g}" if p["speed"] != 1 else ""
        print(f"  {n:>2}. {p['clip']} {p['from']:6.2f}–{p['to']:6.2f}{speed}  {p['why']}")
    print(f"✓ pack.json годен: {len(plan)} кусков, ≈{total:.1f} с (края речи уедут в тишину при сборке)")


def main():
    ap = argparse.ArgumentParser(description="Сборка: один ролик из нескольких видео")
    ap.add_argument("stem", help="имя ролика = имя папки в input/ проекта")
    ap.add_argument("--build", action="store_true", help="собрать по pack.json → input/<имя>.mov")
    ap.add_argument("--check", action="store_true", help="проверить pack.json")
    args = ap.parse_args()
    try:
        if args.build:
            build(args.stem)
        elif args.check:
            summary(args.stem)
        else:
            scan(args.stem)
    except (PackError, ValueError) as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
