#!/usr/bin/env python3
"""Чистовой дубль для монтажа: подрезка начала и конца, цвет, голос. Без графики.

Первый этап нового конвейера. Поверх этого файла дальше работают камера (track.py),
вырезка фона и графика. Решения «режиссёра» лежат в work/<имя>/edit.json:

  {
    "trim": [6.2, 63.6],     # откуда и докуда дубль; границы сами уезжают в тишину
    "cut_pauses": false,      # паузы внутри пока не режем — дубль идёт сплошняком
    "format": "16:9"          # формат ролика (formats.py); по умолчанию — из брифа или 9:16
  }

Если пропорции исходника и формата расходятся (горизонтальный урок под Reels), кадр
перекадрируется по лицу (reframe.py), а не режется по центру. Если у ролика есть бриф
(work/<имя>/brief.json, его пишет студия), цвет берётся из стиля брифа.

  .venv/bin/python scripts/prep.py input/IMG_3279.MOV

На выходе work/<имя>/aroll.mp4 и aroll.words.json — слова уже на шкале дубля.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import formats
import styles
from common import (WORK_DIR, detect_silence, ffmpeg_bin, load_preset, measure_noise_floor, probe,
                    snap_segments)
from cut import remap_words
from reframe import reframe
from render import render
from transcribe import run_transcribe

AIR = 0.12          # сколько тишины оставить до первого слова и после последнего


def find_edges(words: list, silences: list, start_hint: float, end_hint: float) -> tuple:
    """Границы дубля в настоящей тишине, а не по таймингам распознавания.

    Whisper ставит конец слова на 0.3–0.4 с раньше, чем человек договорил: если резать
    по нему, последнее слово ролика оборвётся. Поэтому конец — это начало тишины после
    последнего слова, а начало — конец тишины перед первым.
    """
    inside = [w for w in words if start_hint - 0.05 <= w["start"] < end_hint]
    if not inside:
        raise ValueError(f"Между {start_hint:.1f} и {end_hint:.1f} с нет ни одного слова — "
                         "проверь trim в edit.json")
    first, last = inside[0], inside[-1]
    following = next((w for w in words if w["start"] >= end_hint), None)

    # Начало whisper тоже ставит раньше звука, бывает на полсекунды — прямо в тишину.
    # Слово начинается там, где тишина кончилась, иначе ролик открывается пустотой.
    before = [s for s in silences if s[0] <= first["start"] <= s[1] + 0.35]
    if before:
        s0, s1 = before[-1]
        for a, b in silences:                   # пауза, разорванная щелчком, — всё ещё пауза
            if s1 <= a <= s1 + 0.05:
                s1 = max(s1, b)
        start = max(s0, s1 - AIR)
    else:
        start = max(0.0, first["start"] - 0.2)

    after = next((s for s in silences if s[0] >= last["start"] + 0.1), None)
    end = min(after[0] + AIR, after[1]) if after else last["end"] + 0.3
    # Лишнее слово за краем отрезается по распознаванию, только если оно звучит раньше
    # тишины. Если whisper просто приклеил его начало к концу последнего — верим тишине.
    if following and (after is None or following["end"] <= after[0]):
        end = min(end, following["start"] - 0.05)
    return max(0.0, start), end


def split_by_drops(start: float, end: float, drops: list) -> list:
    """Дубль без неудачных кусков: [(начало, конец), …] в секундах исходника.

    Неудачные дубли и оговорки с матом вырезаются по точкам, которые режиссёр нашёл по
    громкости (в тишине между словами), — это не рез пауз, паузы остаются как были.
    """
    pieces, cursor = [], start
    for a, b in sorted((float(a), float(b)) for a, b in drops):
        if not (cursor < a < b < end):
            raise ValueError(f"Вырез {a}–{b} с лежит вне дубля {start:.2f}–{end:.2f} или "
                             "наезжает на соседний — проверь drop в edit.json")
        pieces.append((cursor, a))
        cursor = b
    pieces.append((cursor, end))
    return pieces


def mark_dropped(words: list, drops: list) -> None:
    """Помечает слова, попавшие в вырезанные куски (drop из edit.json).

    Судим по середине слова: начало whisper ставит раньше звука, и слово сразу за
    вырезом («И» на 13.36 при вырезе до 13.37) по началу считалось вырезанным.
    """
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        w["drop"] = any(a <= mid < b for a, b in drops)


def to_aroll(t: float, segments: list) -> float | None:
    """Секунда исходника → секунда дубля (None, если этот момент вырезан)."""
    acc = 0.0
    for s, e in segments:
        if s <= t <= e:
            return acc + (t - s)
        acc += e - s
    return None


def apply_bleeps(aroll: Path, spans: list) -> None:
    """«Пи-и-ип» поверх мата: голос в этих местах глушится, звучит тон 1 кГц.

    Классический приём: шутка остаётся, слова нет. Видео копируется без пережатия.
    """
    expr = "+".join(f"between(t\\,{a:.3f}\\,{b:.3f})" for a, b in spans)
    tmp = aroll.with_name(f".bleep.{aroll.name}")
    graph = (f"[0:a]volume=volume=0:enable='{expr}'[voice];"
             f"sine=frequency=1000:sample_rate=48000,aformat=channel_layouts=stereo,"
             f"volume=volume='0.20*({expr})':eval=frame[tone];"
             f"[voice][tone]amix=inputs=2:duration=first:normalize=0[a]")
    try:
        result = subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(aroll),
                                 "-filter_complex", graph, "-map", "0:v", "-map", "[a]",
                                 "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                                 "-movflags", "+faststart", str(tmp)], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Не получилось наложить «пип»:\n{result.stderr[-400:]}")
        tmp.replace(aroll)
    finally:
        tmp.unlink(missing_ok=True)


def load_edit(stem: str) -> dict:
    path = WORK_DIR / stem / "edit.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def pick_format(stem: str, edit: dict) -> str:
    """Формат дубля: явный в edit.json → первый из брифа → 9:16."""
    if edit.get("format"):
        return formats.get(edit["format"])["id"]
    brief = styles.load_brief(stem)
    if brief.get("exists"):
        return formats.get(brief["formats"][0])["id"]
    return formats.DEFAULT


def refresh_words(video: Path, out_dir: Path, edit: dict) -> None:
    """Слова на шкале уже собранного дубля — по его сегментам, без пересборки видео."""
    meta_path = out_dir / "aroll.json"
    if not meta_path.exists():
        sys.exit(f"Нет {meta_path.relative_to(WORK_DIR.parent)} — сначала полный prep.py")
    segments = json.loads(meta_path.read_text(encoding="utf-8"))["segments"]
    words = run_transcribe(video)["words"]
    mark_dropped(words, edit.get("drop") or [])
    aroll_words = remap_words(words, segments)
    (out_dir / "aroll.words.json").write_text(
        json.dumps({"words": aroll_words}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ✓ слов на шкале дубля: {len(aroll_words)}")


def main():
    ap = argparse.ArgumentParser(description="Чистовой дубль: подрезка, цвет, голос")
    ap.add_argument("video")
    ap.add_argument("--preset", default="viral")
    ap.add_argument("--words-only", action="store_true",
                    help="только пересчитать слова на шкале готового дубля, видео не трогать")
    args = ap.parse_args()

    video = Path(args.video).resolve()
    if not video.exists():
        sys.exit(f"Нет файла: {video}")
    started = time.time()
    stem = video.stem
    out_dir = WORK_DIR / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.words_only:
        refresh_words(video, out_dir, load_edit(stem))
        return

    preset = load_preset(args.preset)
    edit = load_edit(stem)
    info = probe(video)
    fps = preset["video"].get("fps", 30)
    try:
        fmt = pick_format(stem, edit)
        brief = styles.load_brief(stem)
        if brief.get("exists"):
            style = styles.effective(styles.load_style(brief["style"]), brief.get("overrides"))
            preset["look"] = styles.look(style)
    except (ValueError, styles.StyleError) as error:
        sys.exit(f"✗ {error}")
    preset["video"]["width"], preset["video"]["height"] = formats.size(fmt)
    print(f"\n▶ {video.name}: {info['width']}×{info['height']}, {info['duration']:.1f} с → формат {fmt}")

    data = run_transcribe(video)
    words = data["words"]
    silences = detect_silence(video, preset["cut"].get("silence_db", -35),
                              preset["cut"].get("silence_min", 0.10))

    trim = edit.get("trim") or [0.0, info["duration"]]
    start, end = find_edges(words, silences, float(trim[0]), float(trim[1]))
    if edit.get("cut_pauses", False):
        sys.exit("Рез пауз внутри дубля в prep.py пока не включён — договорились не резать")

    try:
        pieces = split_by_drops(start, end, edit.get("drop") or [])
    except ValueError as error:
        sys.exit(str(error))
    segments = snap_segments(pieces, fps)

    mark_dropped(words, edit.get("drop") or [])
    aroll_words = remap_words(words, segments)
    kept = sum(e - s for s, e in segments)
    cuts = f", вырезано дублей: {len(segments) - 1}" if len(segments) > 1 else ""
    print(f"  → дубль {segments[0][0]:.2f}–{segments[-1][1]:.2f} с исходника "
          f"({kept:.1f} с{cuts}), слов {len(aroll_words)}")

    preset["cut"]["enabled"] = False
    preset["subs"]["enabled"] = False
    preset["motion"]["punch_in"] = False
    noise = None
    if preset["audio"].get("enabled", True) and preset["audio"].get("denoise", True):
        noise = measure_noise_floor(video, silences)
        print(f"  → уровень шума в паузах: {noise:.0f} дБ")

    out = out_dir / "aroll.mp4"
    try:
        # исходник других пропорций — кадр по лицу; звук и тайминги у него те же
        picture = reframe(video, fmt)
    except RuntimeError as error:
        sys.exit(f"✗ {error}")
    render(picture, out, segments, preset, ass_path=None, noise_floor=noise)

    bleeps = []
    for a, b in edit.get("bleep") or []:
        ta, tb = to_aroll(float(a), segments), to_aroll(float(b), segments)
        if ta is None or tb is None:
            sys.exit(f"«Пип» {a}–{b} с попадает в вырезанный кусок — проверь bleep в edit.json")
        bleeps.append((ta, tb))
    if bleeps:
        apply_bleeps(out, bleeps)
        print(f"  → «пип» поверх: {', '.join(f'{a:.2f}–{b:.2f}' for a, b in bleeps)} с дубля")

    (out_dir / "aroll.words.json").write_text(
        json.dumps({"words": aroll_words}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "aroll.json").write_text(json.dumps({
        "source": str(video), "segments": segments, "fps": fps,
        "duration": sum(e - s for s, e in segments),
        "look": preset.get("look"), "format": fmt,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ✓ готово за {time.time() - started:.0f} с → {out.relative_to(WORK_DIR.parent)}")


if __name__ == "__main__":
    main()
