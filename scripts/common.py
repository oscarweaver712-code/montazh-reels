"""Общие утилиты пайплайна: пути, конфиг, вызовы ffmpeg."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
WORK_DIR = ROOT / "work"
PRESET_DIR = ROOT / "presets"
FONT_DIR = PRESET_DIR / "fonts"
VENV_PY = ROOT / ".venv" / "bin" / "python"


def ffmpeg_bin() -> str:
    """ffmpeg с поддержкой libass (нужен для субтитров)."""
    for candidate in ("/opt/homebrew/bin/ffmpeg", "ffmpeg"):
        path = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if path:
            return path
    sys.exit("ffmpeg не найден. Установи: brew install ffmpeg-full")


def ffprobe_bin() -> str:
    for candidate in ("/opt/homebrew/bin/ffprobe", "ffprobe"):
        path = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if path:
            return path
    sys.exit("ffprobe не найден. Установи: brew install ffmpeg-full")


def has_libass() -> bool:
    out = subprocess.run([ffmpeg_bin(), "-hide_banner", "-filters"],
                         capture_output=True, text=True).stdout
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
    ], capture_output=True, text=True, check=True).stdout
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
    }


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
    ], capture_output=True, text=True).stderr

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
        ], capture_output=True, text=True).stderr
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
    result = subprocess.run(cmd, capture_output=quiet, text=True)
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
