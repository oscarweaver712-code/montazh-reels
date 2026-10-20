#!/usr/bin/env python3
"""Чистовой дубль для монтажа: подрезка начала и конца, цвет, голос. Без графики.

Первый этап нового конвейера. Поверх этого файла дальше работают камера (track.py),
вырезка фона и графика. Решения «режиссёра» лежат в work/<имя>/edit.json:

  {
    "trim": [6.2, 63.6],     # откуда и докуда дубль; границы сами уезжают в тишину
    "cut_pauses": true,       # резать длинные паузы внутри (по умолчанию — как в project.json проекта)
    "format": "16:9",         # формат ролика (formats.py); по умолчанию — из брифа или 9:16
    "language": "en",         # язык речи для распознавания; по умолчанию — из project.json проекта
    "air_end": 0.6            # тишины после последнего слова, с (не дальше конца паузы); по умолчанию 0.12
  }

Сборка (несколько видео → один ролик, scripts/pack.py): prep идёт по собранному input/<имя>.mov, края кусков
уже в тишине, а стыки сборки (work/<имя>/pack.built.json) становятся границами кусков дубля и ложатся в
aroll.json → scenes: на них меняется сцена — камера решается заново, субтитр через стык не висит, вспышка
склейки не нужна. Паузы через стык и в кусках без речи не режутся.

Если пропорции исходника и формата расходятся (горизонтальный урок под Reels), кадр
перекадрируется по лицу (reframe.py), а не режется по центру. Если у ролика есть бриф
(work/<имя>/brief.json, его пишет студия), цвет берётся из стиля брифа.

  .venv/bin/python scripts/prep.py projects/antishkola/input/IMG_3279.MOV

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
from common import require_queue
from common import (WORK_DIR, detect_silence, detect_voice, ffmpeg_bin, load_preset, measure_noise_floor, probe,
                    snap_segments)
from cut import remap_words
from reframe import reframe
from render import render
from transcribe import run_transcribe

AIR = 0.12          # сколько тишины оставить до первого слова и после последнего
VOICE_PRE = 0.08    # с: начало дубля — за столько до голоса (согласная в начале тише гласной)
BREATH_MAX = 0.6    # с: вдох или шорох между двумя тишинами — пауза не рвётся, если в нём нет голоса


def project_config(stem: str) -> dict:
    """project.json проекта ролика (рез пауз и его пороги); ролик вне проектов — умолчания."""
    import projects
    try:
        return projects.of_or_default(stem).config
    except projects.ProjectError:
        return dict(projects.CONFIG)


def speech_language(stem: str, edit: dict) -> str:
    """Язык речи: edit.json "language", иначе язык проекта ролика (project.json), иначе русский."""
    if edit.get("language"):
        return edit["language"]
    import projects
    try:
        return projects.of_or_default(stem).config["language"]
    except projects.ProjectError:
        return "ru"


def find_edges(words: list, silences: list, start_hint: float, end_hint: float,
               air_end: float = AIR, voice: list | None = None) -> tuple:
    """Границы дубля в настоящей тишине, а не по таймингам распознавания.

    Whisper ставит конец слова на 0.3–0.4 с раньше, чем человек договорил: если резать
    по нему, последнее слово ролика оборвётся. Поэтому конец — это начало тишины после
    последнего слова, а начало — конец тишины перед первым.

    air_end — сколько тишины оставить после последнего слова (не дальше конца паузы). По
    умолчанию AIR; для финала, после которого графике нужно доиграть, — больше (edit.json
    "air_end": 0.6; IMG_6668, 13.10: с 0.12 с ролик обрывался на последнем слове).
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
    # Вдох перед первым словом паузу по −35 дБ рвёт, и ролик открывался им (IMG_3645, 20.10.2026: «на старте точно есть
    # пауза»). Голос (common.detect_voice) громче вдоха — начало за VOICE_PRE до него, если он позже найденного начала.
    onset = next((a for a, b in voice or [] if b > start and a <= first["end"] + 0.4), None)
    if onset is not None and onset - VOICE_PRE > start:
        start = onset - VOICE_PRE

    after = next((s for s in silences if s[0] >= last["start"] + 0.1), None)
    end = min(after[0] + air_end, after[1]) if after else last["end"] + 0.3
    # Лишнее слово за краем отрезается по распознаванию, только если оно звучит раньше
    # тишины. Если whisper просто приклеил его начало к концу последнего — верим тишине.
    if following and (after is None or following["end"] <= after[0]):
        end = min(end, following["start"] - 0.05)
    # Тихая запись (IMG_1816, 16.10): порог принял тихое последнее слово за паузу, она началась раньше
    # него и выше пропущена — конец уехал в тишину за лишним словом, и в дубль попадало «это,». Если
    # лишнее слово начинается ровно там, где кончилась тишина, его начало настоящее: режем до него.
    if following and end > following["start"] and any(
            s[1] - s[0] >= 0.1 and abs(s[1] - following["start"]) <= 0.08 for s in silences):
        end = following["start"] - 0.05
    return max(0.0, start), end


def split_by_drops(start: float, end: float, drops: list) -> list:
    """Дубль без неудачных кусков: [(начало, конец), …] в секундах исходника.

    Неудачные дубли и оговорки с матом вырезаются по точкам, которые режиссёр нашёл по
    громкости (в тишине между словами). Длинные паузы (find_pauses) приходят сюда же — вырезами.
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


def find_pauses(words: list, silences: list, voice: list, start: float, end: float,
                longer: float, keep: float) -> list:
    """Длинные паузы внутри дубля → вырезы [(от, до)] в секундах исходника.

    Валера 20.10.2026: «в моменте я могу затупить… хочется не терять динамику; вырезать паузу и склеить переходом, чтобы
    не заметно было». Пауза — настоящая тишина (detect_silence), а не промежуток между словами whisper (инвариант 3);
    вдох или шорох без голоса (detect_voice) посреди паузы её не рвёт. Пауза длиннее longer режется так, что от неё
    остаётся keep — пополам у каждого края, рез обоими концами в тишине. Если whisper слышит внутри слово — не режем.
    """
    inside = sorted((max(a, start), min(b, end)) for a, b in silences if b > start and a < end)
    merged = []
    for a, b in inside:
        if merged:
            p0, p1 = merged[-1]
            quiet = not any(va < a and vb > p1 for va, vb in voice)
            if a - p1 <= 0.05 or (a - p1 <= BREATH_MAX and quiet):
                merged[-1] = (p0, max(p1, b))
                continue
        merged.append((a, b))
    cuts = []
    for p0, p1 in merged:
        if p0 <= start + 0.01 or p1 >= end - 0.01 or p1 - p0 <= longer:
            continue                                  # края дубля решает find_edges
        a, b = round(p0 + keep / 2, 3), round(p1 - keep / 2, 3)
        if any(a < (w["start"] + w["end"]) / 2 < b for w in words):
            continue
        cuts.append((a, b))
    return cuts


def pause_jumps(segments: list, cuts: list) -> list:
    """Склейки по вырезанным паузам на шкале дубля — там смена плана, а не вспышка (kit.Take.jumps)."""
    acc, out = 0.0, []
    for (s0, s1), (n0, _) in zip(segments, segments[1:]):
        acc += s1 - s0
        if any(abs(a - s1) <= 0.05 and abs(b - n0) <= 0.05 for a, b in cuts):
            out.append(round(acc, 3))
    return out


def keep_bloopers(drops: list, bloopers: list) -> list:
    """Вырезы с оставленными внутри угарами: [(от, до)] без кусков bloopers.

    Угар (19.10.2026, Валера: «где запороли дубль — серый фильтр, запикать маты, 3 секунды того, как мы угарали, и
    продолжить дубль») — кусок сорванной попытки, который остаётся в ролике вставкой. Он лежит внутри выреза: вырез
    делится на два, угар между ними становится своим куском дубля, графика красит его серым (kit.blooper).
    """
    out = [(float(a), float(b)) for a, b in drops]
    for a, b in sorted((float(a), float(b)) for a, b in bloopers):
        if not 0.6 <= b - a <= 4.0:
            raise ValueError(f"Угар {a}–{b} с: {b - a:.1f} с — бывает от 0,6 до 4 с (Валера: «3 секунды»)")
        host = [d for d in out if d[0] - 0.05 <= a and b <= d[1] + 0.05]
        if not host:
            raise ValueError(f"Угар {a}–{b} с не лежит внутри выреза (drop): угар — кусок сорванной попытки, которую "
                             "вырезаешь; часть чистого дубля серым не красят")
        d0, d1 = host[0]
        out.remove(host[0])
        out += [(d0, a)] if a - d0 > 0.05 else []
        out += [(b, d1)] if d1 - b > 0.05 else []
    return sorted(out)


def mark_dropped(words: list, drops: list) -> None:
    """Помечает слова, попавшие в вырезанные куски (drop из edit.json).

    Судим по середине слова: начало whisper ставит раньше звука, и слово сразу за
    вырезом («И» на 13.36 при вырезе до 13.37) по началу считалось вырезанным.
    """
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        w["drop"] = any(a <= mid < b for a, b in drops)


def blooper_spans(segments: list, bloopers: list) -> list:
    """Угары на шкале дубля: кусок дубля, который больше всех перекрывает угар из edit.json."""
    out = []
    for a, b in bloopers:
        acc, best = 0.0, None
        for s, e in segments:
            overlap = min(e, float(b)) - max(s, float(a))
            if overlap > 0 and (best is None or overlap > best[0]):
                best = (overlap, round(acc, 3), round(acc + e - s, 3))
            acc += e - s
        if best:
            out.append([best[1], best[2]])
    return out


def load_pack(stem: str, video: Path) -> dict | None:
    """Как собран исходник-сборка (scripts/pack.py → work/<имя>/pack.built.json); не сборка — None.

    Отметка сверяется с файлом: пересобранная сборка без новой отметки — громкая ошибка, а не стыки чужой сборки.
    """
    path = WORK_DIR / stem / "pack.built.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if Path(data.get("file", "")).resolve() != video.resolve():
        return None
    if data.get("size") != video.stat().st_size:
        sys.exit(f"✗ {video.name} — не тот файл, что собрал pack.py (размер {video.stat().st_size}, а собран "
                 f"{data.get('size')}): пересобери сборку — .venv/bin/python scripts/pack.py {stem} --build")
    return data


def split_at(pieces: list, joins: list) -> list:
    """Куски дубля, разрезанные по стыкам сборки: через стык не идёт ни один кусок — там меняется сцена."""
    out = []
    for a, b in pieces:
        cuts = sorted(j for j in joins if a + 1e-6 < j < b - 1e-6)
        for x, y in zip([a] + cuts, cuts + [b]):
            out.append((x, y))
    return out


def scene_marks(segments: list, joins: list) -> list:
    """Стыки сборки на шкале дубля (aroll.json → scenes): граница куска дубля, совпавшая со стыком."""
    acc, out = 0.0, []
    for (s0, s1), _ in zip(segments, segments[1:]):
        acc += s1 - s0
        if any(abs(s1 - j) <= 0.02 for j in joins):
            out.append(round(acc, 3))
    return out


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
                                 "-movflags", "+faststart", str(tmp)], capture_output=True, encoding="utf-8", errors="replace")
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


def pick_look(stem: str) -> dict:
    """Цвет дубля — из стиля брифа ролика, а без своего брифа — из умолчаний его проекта (project.json → brief).

    До 20.10.2026 стиль брался только у ролика со своим brief.json, иначе — общий пресет (яркость −8 Антишколы): у
    заказа «Вкудесника» с тёплым грейдом проекта субтитры шли по стилю проекта, а цвет — по чужому. Для Антишколы и
    Фирузы это одно и то же (viral-behind: natural, −8), поэтому старые ролики не меняются.
    """
    brief = styles.load_brief(stem)
    return styles.look(styles.effective(styles.load_style(brief["style"]), brief.get("overrides")))


def refresh_words(video: Path, out_dir: Path, edit: dict) -> None:
    """Слова на шкале уже собранного дубля — по его сегментам, без пересборки видео."""
    meta_path = out_dir / "aroll.json"
    if not meta_path.exists():
        sys.exit(f"Нет {meta_path.relative_to(WORK_DIR.parent)} — сначала полный prep.py")
    segments = json.loads(meta_path.read_text(encoding="utf-8"))["segments"]
    words = run_transcribe(video, language=speech_language(video.stem, edit))["words"]
    mark_dropped(words, keep_bloopers(edit.get("drop") or [], edit.get("blooper") or []))
    aroll_words = remap_words(words, segments)
    (out_dir / "aroll.words.json").write_text(
        json.dumps({"words": aroll_words}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ✓ слов на шкале дубля: {len(aroll_words)}")


def make_hq(video: Path, out_dir: Path, preset: dict, edit: dict, fmt: str) -> Path:
    """Дубль для страницы с запасом под зум камеры (15.10.2026, IMG_1799: «не херишь ли качество»).

    Обычный дубль — 1080×1920, а камера страницы приближает до 1.36: лицо растягивалось из ~800 px,
    резкость выходила вдвое ниже, чем у того же кадра из 4K-исходника. Здесь тот же рез (сегменты
    берутся из aroll.json, а не считаются заново), тот же цвет, звук — байт в байт из aroll.mp4
    (с «пипами» и громкостью). Включается только у ролика с "hq" в edit.json; compose берёт его вместо
    aroll.mp4. Слежение, маска и тайминги остаются на обычном дубле — геометрия страницы та же.
    """
    scale = float(edit.get("hq") or 0)
    if not 1.0 < scale <= 2.0:
        sys.exit(f"✗ edit.json → \"hq\": {edit.get('hq')!r} — нужен множитель от 1.1 до 2 (обычно 1.5)")
    meta_path, base = out_dir / "aroll.json", out_dir / "aroll.mp4"
    if not meta_path.exists() or not base.exists():
        sys.exit("✗ сначала обычный дубль: prep.py без --hq")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    width, height = preset["video"]["width"], preset["video"]["height"]
    preset["video"]["width"], preset["video"]["height"] = (round(width * scale / 2) * 2, round(height * scale / 2) * 2)
    bitrate = float(str(preset["video"].get("bitrate", "12M")).rstrip("Mm"))
    preset["video"]["bitrate"] = f"{bitrate * scale * scale:.0f}M"
    preset["look"] = meta.get("look") or preset.get("look")
    for key in ("cut", "subs"):
        preset[key]["enabled"] = False
    preset["motion"]["punch_in"] = False
    preset["audio"]["enabled"] = False             # звук всё равно берётся из aroll.mp4
    print(f"\n▶ {video.name} → дубль для страницы {preset['video']['width']}×{preset['video']['height']} "
          f"({preset['video']['bitrate']}), рез из aroll.json")
    started = time.time()
    try:
        picture = reframe(video, fmt)
    except RuntimeError as error:
        sys.exit(f"✗ {error}")
    out = out_dir / "aroll.hq.mp4"
    raw = out_dir / ".aroll.hq.video.mp4"
    part = out_dir / ".aroll.hq.part.mp4"
    try:
        render(picture, raw, meta["segments"], preset, ass_path=None, noise_floor=None)
        subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(raw), "-i", str(base),
                        "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-movflags", "+faststart", str(part)],
                       check=True)
        a, b = probe(part), probe(base)
        if abs(a["duration"] - b["duration"]) > 1.5 / meta["fps"]:
            sys.exit(f"✗ дубль для страницы {a['duration']:.3f} с, а обычный {b['duration']:.3f} с — "
                     f"кадры разъехались бы с камерой и субтитрами, не отдаю")
        part.replace(out)
    finally:
        raw.unlink(missing_ok=True)
        part.unlink(missing_ok=True)
    print(f"  ✓ готово за {time.time() - started:.0f} с → {out.relative_to(WORK_DIR.parent)}")
    return out


def main():
    require_queue("подготовка дубля")
    ap = argparse.ArgumentParser(description="Чистовой дубль: подрезка, цвет, голос")
    ap.add_argument("video")
    ap.add_argument("--preset", default="viral")
    ap.add_argument("--hq", action="store_true",
                    help="второй дубль для страницы в разрешении edit.json → hq (×1.5): тот же рез, цвет и звук")
    ap.add_argument("--words-only", action="store_true",
                    help="только пересчитать слова на шкале готового дубля, видео не трогать")
    args = ap.parse_args()

    video = Path(args.video).resolve()
    if not video.exists():
        sys.exit(f"Нет файла: {video}")
    if video.is_dir():
        sys.exit(f"✗ {video.name}/ — сборка из нескольких видео: сначала разбор и сборка — scripts/pack.py "
                 f"{video.name} (меню кусков), work/{video.name}/pack.json, scripts/pack.py {video.name} --build; "
                 f"prep — по собранному input/{video.name}.mov")
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
        preset["look"] = pick_look(stem)
    except (ValueError, styles.StyleError) as error:
        sys.exit(f"✗ {error}")
    preset["video"]["width"], preset["video"]["height"] = formats.size(fmt)
    if args.hq:
        make_hq(video, out_dir, preset, edit, fmt)
        return
    print(f"\n▶ {video.name}: {info['width']}×{info['height']}, {info['duration']:.1f} с → формат {fmt}")

    # У ролика один дубль. Пересборка в другом формате молча заменила бы дубль готового
    # ролика другой формы — и его страница, камера и маска поехали бы. Второй формат того
    # же видео — отдельный ролик (жёсткая ссылка на исходник места не занимает).
    meta_path = out_dir / "aroll.json"
    if meta_path.exists():
        was = json.loads(meta_path.read_text(encoding="utf-8")).get("format") or formats.DEFAULT
        if was != fmt:
            sys.exit(f"✗ Дубль {stem} уже собран в {was}, а сейчас просят {fmt}. Чтобы не сломать готовый "
                     f"ролик, второй формат делай отдельным: ln \"{video}\" \"{video.with_name(stem + '_' + fmt.replace(':', 'x') + video.suffix)}\" "
                     f"и prep по новому имени (в его edit.json — \"format\": \"{fmt}\"). "
                     f"Или удали work/{stem}/aroll.* , если старый формат больше не нужен.")

    data = run_transcribe(video, language=speech_language(video.stem, edit))
    words = data["words"]
    silences = detect_silence(video, preset["cut"].get("silence_db", -35),
                              preset["cut"].get("silence_min", 0.10))

    voice = detect_voice(video)
    pack = load_pack(stem, video)
    joins = [float(j) for j in (pack or {}).get("joins") or []]
    inner = [float(j) for j in (pack or {}).get("cuts") or []]      # склейки сборки внутри одного плана
    trim = edit.get("trim") or [0.0, info["duration"]]
    if pack and not edit.get("trim"):
        # края кусков сборки уже в тишине (pack.py), а первый кусок бывает без слов — find_edges он не по зубам
        start, end = 0.0, float(pack["duration"])
    else:
        start, end = find_edges(words, silences, float(trim[0]), float(trim[1]),
                                float(edit.get("air_end", AIR)), voice=voice)

    try:
        drops = keep_bloopers(edit.get("drop") or [], edit.get("blooper") or [])
        cuts = []
        project = project_config(stem)
        if edit.get("cut_pauses", project["cut_pauses"]):
            busy = [(float(a), float(b)) for a, b in drops + list(edit.get("bleep") or [])]
            # в сборке пауза не режется через стык и в кусках без речи (там картинка и звук места, а не заминка)
            busy += [(j, j) for j in joins + inner] + [(p["t0"], p["t1"]) for p in (pack or {}).get("pieces", [])
                                                       if not p.get("speech")]
            cuts = [c for c in find_pauses(words, silences, voice, start, end, float(project["pause_max"]),
                                           float(project["pause_keep"]))
                    if not any(c[0] < b + 0.05 and c[1] > a - 0.05 for a, b in busy)]
        pieces = split_at(split_by_drops(start, end, drops + cuts), joins + inner)
    except ValueError as error:
        sys.exit(str(error))
    segments = snap_segments(pieces, fps)
    # куски дубля — строго по порядку и без нахлёста: иначе дубль длиннее исходника, и всё после нахлёста (субтитры,
    # графика) уезжает (20.10.2026: несортированные стыки сборки дали 93,5 с дубля из 75,2 с — поймано глазами)
    bad = [(a, b) for (a, b), (c, d) in zip(segments, segments[1:]) if c < b - 1e-6] + [x for x in segments if x[1] <= x[0]]
    if bad or segments[-1][1] > info["duration"] + 0.05:
        sys.exit(f"✗ куски дубля идут не по порядку или нахлёстом ({bad[:3] or segments[-1]}) — дубль вышел бы длиннее "
                 f"исходника; это ошибка сборки кусков, не отдаю")
    # склейки внутри плана — и вырезанные паузы, и стыки сборки одного клипа: их прячет смена плана (kit.Take.framing)
    jumps = sorted(pause_jumps(segments, cuts) + scene_marks(segments, inner))
    scenes = scene_marks(segments, joins)
    if scenes:
        print(f"  → сборка: {len(scenes) + 1} сцен — на стыках камера и субтитры не переезжают")
    if cuts:
        print(f"  → пауз вырезано: {len(cuts)} ({sum(b - a for a, b in cuts):.1f} с) — на склейках смена плана")
    bloopers = blooper_spans(segments, edit.get("blooper") or [])

    mark_dropped(words, drops)
    aroll_words = remap_words(words, segments)
    kept = sum(e - s for s, e in segments)
    dropped = len(segments) - 1 - len(bloopers) - len(jumps) - len(scenes)
    done = f", вырезано дублей: {dropped}" if dropped > 0 else ""
    done += f", угаров: {len(bloopers)}" if bloopers else ""
    print(f"  → дубль {segments[0][0]:.2f}–{segments[-1][1]:.2f} с исходника "
          f"({kept:.1f} с{done}), слов {len(aroll_words)}")

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
        "look": preset.get("look"), "format": fmt, "bloopers": bloopers, "jumps": jumps, "scenes": scenes,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ✓ готово за {time.time() - started:.0f} с → {out.relative_to(WORK_DIR.parent)}")


if __name__ == "__main__":
    main()
