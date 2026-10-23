"""Общие утилиты пайплайна: пути, конфиг, вызовы ffmpeg."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import host  # noqa: E402

host.utf8_console()          # на Windows вывод в лог очереди иначе падал бы на «✓»

ROOT = Path(__file__).resolve().parent.parent
# Исходники и готовые ролики — у каждого проекта свои: projects/<имя>/input и output (projects.py).
# Общих input/ и output/ больше нет (14.10.2026).
WORK_DIR = ROOT / "work"
PRESET_DIR = ROOT / "presets"
FONT_DIR = PRESET_DIR / "fonts"
MODEL_DIR = PRESET_DIR / "models"
VENV_PY = host.venv_python(ROOT)
# Агенты студии (мозг) идут с REELS_STUDIO_CHILD=1, шаги очереди — с REELS_QUEUE_STEP=1 (jobqueue.run_step)
STUDIO_CHILD, QUEUE_STEP = "REELS_STUDIO_CHILD", "REELS_QUEUE_STEP"


def sheet_path(video: Path, work_dir: Path | None = None) -> Path:
    """Сетка кадров готового ролика — рядом с решениями ролика, а не в output/ (Валера 16.10.2026: «в Output я хочу
    видеть только видео», раскадровки мешали пересылать ролики). work/<имя>/sheets/<файл>.sheet.jpg: имя — без версии
    (_v4) и варианта (--sfx); ролик без папки в work/ — work/_sheets/."""
    work_dir = work_dir or WORK_DIR
    stem = re.sub(r"_v\d+$", "", Path(video).stem).split("--")[0]
    folder = work_dir / stem / "sheets" if (work_dir / stem).is_dir() else work_dir / "_sheets"
    return folder / f"{Path(video).stem}.sheet.jpg"


def require_queue(what: str) -> None:
    """Тяжёлый шаг агент студии запускает только через очередь — громкий отказ, а не второй тяжёлый процесс.

    Пока мозг в студии был один, правило «тяжёлое — в очередь» держалось словами в подсказке. С 16.10.2026
    пачка монтирует несколько роликов разом, каждый в своей сессии: два агента, запустивших рендер сами,
    сложили бы память двух рендеров (инвариант 2). Человек в терминале и сама очередь не ограничены.
    """
    import os
    if os.environ.get(STUDIO_CHILD) == "1" and os.environ.get(QUEUE_STEP) != "1":
        sys.exit(f"✗ {what} — тяжёлый шаг, агент студии запускает его только через очередь: "
                 f"{'.venv/Scripts/python.exe' if host.IS_WINDOWS else '.venv/bin/python'} scripts/jobqueue.py add "
                 f"<NN>-<шаг>-<имя ролика> \"python scripts/…\". Рядом могут монтироваться другие ролики, "
                 f"а тяжёлый процесс на машине — один (AGENTS.md, инвариант 2)")


def _find(name: str) -> str | None:
    # Homebrew-ffmpeg-full на Mac стоит рядом с обычным ffmpeg без libass — он первым
    for candidate in ("/opt/homebrew/bin/" + name, name):
        path = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if path:
            return path
    return None


def ffmpeg_bin() -> str:
    """ffmpeg с поддержкой libass (нужен для субтитров)."""
    return _find("ffmpeg") or sys.exit(f"ffmpeg не найден. Установи: {host.install_hint('ffmpeg')}")


def ffprobe_bin() -> str:
    return _find("ffprobe") or sys.exit(f"ffprobe не найден. Установи: {host.install_hint('ffmpeg')}")


def has_libass() -> bool:
    out = subprocess.run([ffmpeg_bin(), "-hide_banner", "-filters"],
                         capture_output=True, encoding="utf-8", errors="replace").stdout
    return any(line.split()[1:2] == ["ass"] for line in out.splitlines() if line.strip())


def load_preset(name: str = "viral") -> dict:
    """Пресет по имени (presets/<имя>.json) или путь к .json — так задача очереди несёт
    свои настройки, а не общий файл, который перепишет следующий запуск."""
    if name.endswith(".json"):
        path = Path(name) if Path(name).is_absolute() else ROOT / name
    else:
        path = PRESET_DIR / f"{name}.json"
    if not path.exists():
        sys.exit(f"Пресет не найден: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def probe(video: Path) -> dict:
    """Разрешение, длительность, fps, поворот исходника."""
    out = subprocess.run([
        ffprobe_bin(), "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(video)
    ], capture_output=True, encoding="utf-8", errors="replace", check=True).stdout
    data = json.loads(out)

    vstream = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if vstream is None:
        sys.exit(f"В файле нет видеодорожки: {video}")

    width, height = int(vstream["width"]), int(vstream["height"])

    # Поворот из метаданных: телефон часто пишет ландшафтный кадр + rotate=90
    rotation = 0
    for entry in vstream.get("side_data_list", []) or []:
        if "rotation" in entry:
            rotation = int(entry["rotation"])
    if rotation in (90, -90, 270, -270):
        width, height = height, width

    num, den = (vstream.get("avg_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0

    return {
        "width": width,
        "height": height,
        "duration": float(data["format"]["duration"]),
        "fps": fps,
        "vertical": height >= width,
        "has_audio": any(s["codec_type"] == "audio" for s in data["streams"]),
        # цвет: HDR с айфона (HLG, BT.2020) надо переводить в обычный — look.hdr_to_sdr
        "transfer": vstream.get("color_transfer") or "",
        "primaries": vstream.get("color_primaries") or "",
        "matrix": vstream.get("color_space") or "",
        "range": vstream.get("color_range") or "",
    }


def decode_threads(info: dict) -> list:
    """Потоки декодера для исходников больше 1080p (4K HEVC с айфона) — опции перед -i.

    Декодер держит в работе по кадру на поток, а кадр 4K в 10 битах весит 25 МБ: на 10 ядрах
    кусок занимал 822 МБ. Четыре потока — 476 МБ при +19% времени (IMG_1803, 12.10.2026).
    Обычным 1080p-дублям это не нужно, их команды не меняются.
    """
    return ["-threads", "4"] if max(info["width"], info["height"]) > 1920 else []


def detect_silence(video: Path, threshold_db: float = -35.0,
                   min_len: float = 0.10) -> list:
    """Промежутки настоящей тишины в звуке: [(начало, конец), …].

    Тайминги распознавания на границах слов врут. Произнесённое «ноль целых восемь
    десятых» whisper пишет как «0 ,8» и ставит конец там, где кончился текст, — на
    0.3–0.4 с раньше, чем человек договорил. Рез по такому концу отрезает хвост слова.
    Поэтому границы кусков ставятся по этой карте, а не по концу распознанного слова.
    """
    out = subprocess.run([
        ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(video), "-vn",
        "-af", f"silencedetect=n={threshold_db}dB:d={min_len}", "-f", "null", "-",
    ], capture_output=True, encoding="utf-8", errors="replace").stderr

    silences, opened = [], None
    for match in re.finditer(r"silence_(start|end):\s*(-?[\d.]+)", out):
        kind, value = match.group(1), float(match.group(2))
        if kind == "start":
            opened = value
        elif opened is not None:
            silences.append((max(0.0, opened), value))
            opened = None
    if opened is not None:                  # тишина тянется до конца файла
        silences.append((max(0.0, opened), float("inf")))
    return silences


VOICE_WINDOW = 0.02     # с: окно громкости для detect_voice


def detect_voice(video: Path, below_speech: float = 15.0, min_len: float = 0.06) -> list:
    """Промежутки голоса: [(начало, конец), …] — громкость не ниже речи минус below_speech дБ дольше min_len.

    Тишина по порогу −35 дБ (detect_silence) не отличает вдох от слова: вдох перед первой фразой (−24…−37 дБ) рвал
    паузу, и ролик открывался полусекундой вдоха (IMG_3645, 20.10.2026: голос с 0,62 с, whisper — с 0,12). Голос
    громче вдоха на 10–20 дБ, поэтому порог считается от уровня самой речи — медианы громких окон, а одиночный
    щелчок короче min_len голосом не считается. Звук читается потоком по секунде: память не зависит от длины записи.
    """
    import numpy as np
    rate = 16000
    step = int(rate * VOICE_WINDOW)
    proc = subprocess.Popen([ffmpeg_bin(), "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(rate),
                             "-f", "s16le", "-"], stdout=subprocess.PIPE)
    levels, rest = [], b""
    try:
        while True:
            chunk = proc.stdout.read(rate * 2)
            if not chunk:
                break
            data = rest + chunk
            usable = len(data) // (step * 2) * step * 2
            rest = data[usable:]
            if usable:
                frames = np.frombuffer(data[:usable], np.int16).astype(np.float32).reshape(-1, step) / 32768
                levels.extend((20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)).tolist())
    finally:
        proc.stdout.close()
        proc.wait()
    if not levels:
        return []
    db = np.array(levels)
    speech = float(np.median(db[db > np.percentile(db, 40)]))
    loud = db >= speech - below_speech
    spans, k, need = [], 0, max(1, round(min_len / VOICE_WINDOW))
    while k < len(loud):
        if not loud[k]:
            k += 1
            continue
        j = k
        while j < len(loud) and loud[j]:
            j += 1
        if j - k >= need:
            spans.append((round(k * VOICE_WINDOW, 3), round(j * VOICE_WINDOW, 3)))
        k = j
    return spans


def measure_noise_floor(video: Path, silences: list, default: float = -45.0) -> float:
    """Настоящий уровень шума — по средней громкости пауз этой же записи.

    Порог шумодава раньше стоял константой −24 дБ. Это уровень самого голоса: шумодаву
    было сказано считать шумом почти всё, он выедал согласные и делал речь «подводной».

    Считается именно среднее (RMS), а не пик. В паузе всегда есть вдохи, щелчки и
    шорохи: на живой записи пик в паузе стоял на −34 дБ, а настоящий шум — на −55.
    Порог по пику снова заводит шумодав на голос. Медиана по нескольким самым длинным
    паузам — чтобы одна неудачная не решала за всю запись.
    """
    usable = sorted((pair for pair in silences
                     if pair[1] != float("inf") and pair[1] - pair[0] >= 0.25),
                    key=lambda pair: pair[1] - pair[0], reverse=True)[:5]
    if not usable:
        return default

    levels = []
    for start, end in usable:
        out = subprocess.run([
            ffmpeg_bin(), "-hide_banner", "-nostats",
            "-ss", f"{start:.3f}", "-t", f"{min(end - start, 2.0):.3f}",
            "-i", str(video), "-vn", "-af", "volumedetect", "-f", "null", "-",
        ], capture_output=True, encoding="utf-8", errors="replace").stderr
        # на цифровой тишине ffmpeg пишет «-inf dB» — такую паузу просто пропускаем
        match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", out)
        if match:
            levels.append(float(match.group(1)))

    if not levels:
        return default

    levels.sort()
    middle = len(levels) // 2
    median = levels[middle] if len(levels) % 2 else (levels[middle - 1] + levels[middle]) / 2
    # небольшой запас вверх: RMS чуть занижает то, что ухо слышит как шум
    return max(-80.0, min(-20.0, median + 3.0))


def run(cmd: list, desc: str = "", quiet: bool = True):
    """Запуск с человеческой ошибкой вместо простыни ffmpeg."""
    if desc:
        print(f"  → {desc}", flush=True)
    result = subprocess.run(cmd, capture_output=quiet, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        if quiet and result.stderr:
            tail = "\n".join(result.stderr.strip().splitlines()[-15:])
            print(f"\nОшибка на шаге «{desc}»:\n{tail}", file=sys.stderr)
        sys.exit(result.returncode)
    return result


def snap_segments(segments: list, fps: float) -> list:
    """Кладёт границы сегментов на сетку кадров.

    Длительность куска, не кратная кадру, округляется кодеком вверх. Субтитры при этом
    считаются по точным числам плана — и к концу ролика расходятся с речью на секунды.
    Операция идемпотентная: применить дважды безопасно.
    """
    snapped = []
    for start, end in segments:
        first, last = round(start * fps), round(end * fps)
        if last <= first:
            last = first + 1               # кусок короче кадра показать нельзя
        snapped.append((first / fps, last / fps))
    return snapped


def plural(n: int, one: str, few: str, many: str) -> str:
    """1 сегмент, 2 сегмента, 5 сегментов."""
    d10, d100 = n % 10, n % 100
    if d10 == 1 and d100 != 11:
        word = one
    elif 2 <= d10 <= 4 and not 12 <= d100 <= 14:
        word = few
    else:
        word = many
    return f"{n} {word}"


def ts(seconds: float) -> str:
    """Секунды → 0:00:00.00 для формата ASS."""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def ass_color(hex_rgb: str, alpha: int = 0) -> str:
    """#RRGGBB → &HAABBGGRR& (в ASS порядок байтов обратный, alpha 0 — непрозрачно)."""
    hex_rgb = hex_rgb.lstrip("#")
    r, g, b = hex_rgb[0:2], hex_rgb[2:4], hex_rgb[4:6]
    return f"&H{alpha:02X}{b}{g}{r}&"


# Чёткость вставок (Валера 23.10.2026: «всё что ниже 720p идёт лесом автоматом железно, а лучше не ниже 1080p»).
# Мерится не по ярлыку файла, а по месту в кадре: горизонтальный 1080p во весь вертикальный кадр — это 608 px ширины,
# растянутые до 1080, то есть «608p». Один счёт для стоков, клипов, фото, мемов и материалов человека.
QUALITY_FLOOR = 720     # ниже — вставка не идёт никуда
QUALITY_GOOD = 1080     # во весь кадр — так; между полом и этим — можно, но сказать


def sharpness(src_w: float, src_h: float, shown_w: float, shown_h: float, fit: str = "cover") -> int:
    """«p» вставки: кусок исходника src_w×src_h показан местом shown_w×shown_h кадра 1080 px шириной. Пиксель в пиксель
    и крупнее — 1080, растянутый в k раз — 1080/k. fit — object-fit: contain вписывает (растяжение по меньшему)."""
    if src_w <= 0 or src_h <= 0:
        return 0
    kx, ky = shown_w / src_w, shown_h / src_h
    k = min(kx, ky) if fit == "contain" else max(kx, ky)
    return int(round(QUALITY_GOOD / max(k, 1.0)))


def vertical_crop(width: int, height: int, aspect: float = 9 / 16) -> tuple:
    """Сколько пикселей исходника войдёт в вертикальный кадр при обрезке по высоте (stock.fit): (ширина, высота)."""
    return min(width, int(round(height * aspect / 2)) * 2), height
