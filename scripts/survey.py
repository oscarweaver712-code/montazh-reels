#!/usr/bin/env python3
"""Отсмотр большой съёмки: каталог живых моментов вместо часов сырья (24.10.2026, заказ «Вкудесника» на ~90 рилсов).

Съёмка без сценария — десятки гигабайт с айфона, DJI Nano и 360-камеры. Сценарий пишет ИИ по тексту, а не по видео,
поэтому каталог — текст: каждый живой кусок с таймкодами, что происходит, кто в кадре, что говорят, к каким опорам
заказчика подходит и насколько силён. Брак тоже записан, с причиной — чтобы человек мог проверить отбор.

Деньги — главное ограничение (Валера: «максимально дёшево»). Всё, что считается локально, — локально и бесплатно:
опись, речь (Whisper), лица (YuNet), брак (яркость, резкость, тряска), границы кусков. Gemini видит только живые
куски — один лист из нескольких маленьких кадров и готовый текст речи; видеофайлы никуда не уходят.

Этапы (каждый пишет свой файл, обрыв не заставляет платить или считать дважды):
  inventory   опись: ffprobe всех файлов — длительность, кадр с учётом поворота, к/с, кодек; фото отдельно
              → projects/<проект>/catalog/inventory.json
  local       тяжёлый локальный проход по каждому видео (через очередь): кадры потоком 4 к/с — яркость, резкость,
              тряска, смены плана, лица; звук — громкость и речь Whisper → work/_survey/<проект>/files/<id>.json
  pieces      разбиение на куски (план + речь + тишина) и брак с причиной → catalog/pieces.json, листы кадров
  gemini      описание живых кусков группами по 4 (кэш ответа по куску, расход — catalog/gemini_ledger.jsonl)
  photos      фото листами по 12 миниатюр
  build       catalog.json и catalog.md

  .venv/bin/python scripts/survey.py inventory vkudesnik
  .venv/bin/python scripts/jobqueue.py add 30-survey-vkudesnik "python scripts/survey.py local vkudesnik"

360-камера (DJI Osmo 360): .OSV — две несшитые линзы фишай, декодировать их целиком дорого и бесполезно.
Отсмотр идёт по .LRF — лёгкому превью того же клипа; в каталоге у куска стоит, в какой линзе герой.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (ROOT, WORK_DIR, ffmpeg_bin, ffprobe_bin, require_queue, sharpness,  # noqa: E402
                    vertical_crop)

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".osv"}
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic"}
PREVIEW_EXT = ".lrf"          # 360: лёгкое превью клипа, сам по себе не материал


class SurveyError(Exception):
    """Отсмотр не может идти дальше — человеку нужен понятный русский ответ, а не трейсбек."""


def project_dir(project: str) -> Path:
    path = ROOT / "projects" / project
    if not path.is_dir():
        raise SurveyError(f"нет проекта projects/{project}")
    return path


def raw_dir(project: str) -> Path:
    return project_dir(project) / "input" / "_raw"


def catalog_dir(project: str) -> Path:
    return project_dir(project) / "catalog"


def survey_dir(project: str) -> Path:
    """Кэш разбора и листы кадров — в work/_survey/ (мимо обоих git: пересобираются из исходников)."""
    return WORK_DIR / "_survey" / project


def write_json(path: Path, data) -> None:
    """Атомарно: оборванная запись не оставляет полкаталога под настоящим именем."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------- опись

def ffprobe(path: Path) -> dict:
    import subprocess
    out = subprocess.run([ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                          str(path)], capture_output=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise SurveyError(f"ffprobe не открыл {path.name}: {out.stderr.strip()[-300:]}")
    return json.loads(out.stdout)


def rotation_of(stream: dict) -> int:
    for entry in stream.get("side_data_list", []) or []:
        if "rotation" in entry:
            return int(entry["rotation"])
    return 0


def fps_of(stream: dict) -> float:
    num, den = (stream.get("avg_frame_rate") or "0/1").split("/")
    return round(float(num) / float(den), 3) if float(den) else 0.0


def video_streams(data: dict) -> list:
    """Видеодорожки без обложек: у DJI в файле лежит ещё mjpeg-миниатюра (attached_pic или 0 к/с)."""
    return [s for s in data["streams"] if s["codec_type"] == "video" and s.get("codec_name") != "mjpeg"
            and not (s.get("disposition") or {}).get("attached_pic")]


def file_id(rel: Path) -> str:
    """Стабильный короткий id файла: папка + имя без расширения (phone/IMG_7001, DJI_360/CAM_…_0080_D)."""
    return f"{rel.parent.name}/{rel.stem}"


def describe_video(path: Path, rel: Path) -> dict:
    data = ffprobe(path)
    streams = video_streams(data)
    if not streams:
        raise SurveyError(f"в {rel} нет видеодорожки")
    v = streams[0]
    w, h, rot = int(v["width"]), int(v["height"]), rotation_of(v)
    if rot in (90, -90, 270, -270):
        w, h = h, w
    item = {"id": file_id(rel), "path": str(rel), "kind": "video", "duration": round(float(data["format"]["duration"]), 3),
            "width": w, "height": h, "rotation": rot, "fps": fps_of(v), "codec": v.get("codec_name"),
            "size_mb": round(int(data["format"]["size"]) / 1e6, 1),
            "audio": any(s["codec_type"] == "audio" for s in data["streams"]), "analyze": str(rel),
            # время съёмки: одни и те же минуты сняты айфоном, Nano и 360 — сценарию нужен «тот же момент другой камерой»
            "shot_at": (data["format"].get("tags") or {}).get("creation_time", "")}
    if path.suffix.lower() == ".osv":
        # две линзы фишай отдельными дорожками; сшить можно только в DJI Studio
        item.update(kind="360", lenses=len(streams))
    if path.parent.name.upper().startswith("DJI_360") or path.suffix.lower() == ".osv":
        lrf = path.with_suffix(".LRF") if path.with_suffix(".LRF").exists() else path.with_suffix(".lrf")
        if lrf.exists():
            pv = video_streams(ffprobe(lrf))[0]
            pw, ph = int(pv["width"]), int(pv["height"])
            if rotation_of(pv) in (90, -90, 270, -270):
                pw, ph = ph, pw
            item["analyze"] = str(rel.with_name(lrf.name))
            item["preview"] = {"width": pw, "height": ph, "fps": fps_of(pv)}
        elif item["kind"] == "360":
            raise SurveyError(f"{rel}: нет .LRF рядом — сырой 360 целиком не декодируем (две линзы 1920² по 100 к/с)")
        if item["kind"] != "360":
            item["kind"] = "360flat"      # снято одной линзой «как обычная камера»: кадр уже прямой
    return item


def describe_photo(path: Path, rel: Path) -> dict:
    item = {"id": file_id(rel), "path": str(rel), "kind": "photo", "size_mb": round(path.stat().st_size / 1e6, 2)}
    try:
        streams = [s for s in ffprobe(path)["streams"] if s["codec_type"] == "video"]
        # HEIC ffprobe показывает плитками: берём самую большую дорожку
        best = max(streams, key=lambda s: int(s.get("width", 0)) * int(s.get("height", 0)))
        w, h = int(best["width"]), int(best["height"])
        if rotation_of(best) in (90, -90, 270, -270):
            w, h = h, w
        item.update(width=w, height=h)
    except (SurveyError, ValueError, KeyError):
        item["note"] = "размер не прочитан"
    return item


def inventory(project: str) -> dict:
    src = raw_dir(project)
    if not src.is_dir():
        raise SurveyError(f"нет папки съёмки {src.relative_to(ROOT)}")
    videos, photos, skipped = [], [], []
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = path.relative_to(src)
        ext = path.suffix.lower()
        if path.name.startswith("."):
            continue
        if ext in VIDEO_EXT:
            videos.append(describe_video(path, rel))
        elif ext in PHOTO_EXT:
            photos.append(describe_photo(path, rel))
        elif ext != PREVIEW_EXT:
            skipped.append(str(rel))
    ids = [v["id"] for v in videos]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise SurveyError(f"одинаковые id файлов (одно имя в одной папке с разными расширениями?): {', '.join(dup)}")
    folders = {}
    for v in videos:
        f = folders.setdefault(str(Path(v["path"]).parent), {"videos": 0, "hours": 0.0, "photos": 0})
        f["videos"] += 1
        f["hours"] = round(f["hours"] + v["duration"] / 3600, 3)
    for p in photos:
        folders.setdefault(str(Path(p["path"]).parent), {"videos": 0, "hours": 0.0, "photos": 0})["photos"] += 1
    data = {"project": project, "source": str(src.relative_to(ROOT)), "folders": folders, "videos": videos,
            "photos": photos, "skipped": skipped,
            "hours": round(sum(v["duration"] for v in videos) / 3600, 3)}
    write_json(catalog_dir(project) / "inventory.json", data)
    return data


def load_inventory(project: str) -> dict:
    path = catalog_dir(project) / "inventory.json"
    if not path.exists():
        raise SurveyError(f"сначала опись: .venv/bin/python scripts/survey.py inventory {project}")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- чёткость по месту в кадре

LENS_PX, LENS_FOV, FLAT_FOV = 1920, 200.0, 70.0   # Osmo 360 в режиме 100 к/с: линза 1920², ~200°; выпрямленный кадр ~70°


def sharp_p(item: dict) -> int:
    """«p» исходника во весь вертикальный кадр (правило 23.10.2026: ниже 720p — никуда).

    360 — оценка: выпрямленный вертикальный кадр с горизонтальным углом ~70° берёт из линзы 1920 px на ~200° около
    670 px ширины — то есть ~670p, и экспорт DJI Studio этого не поднимет (пикселей в линзе больше нет)."""
    if item["kind"] == "360":
        w = LENS_PX * FLAT_FOV / LENS_FOV
        return sharpness(w, w * 16 / 9, 1080, 1920)
    return sharpness(*vertical_crop(item["width"], item["height"]), 1080, 1920)


# ---------------------------------------------------------------- локальный проход

LOCAL_VERSION = 1           # меняется, когда меняется смысл чисел разбора — старый кэш пересчитывается
SAMPLE_FPS = 4              # кадров в секунду на яркость, резкость, тряску и лица
THUMB_EVERY = 2             # каждый второй — миниатюра (2 к/с) для листов и Gemini
THUMB_H = 320
RMS_HZ = 10
ANALYSIS_W = 540            # YuNet обучен на лицах до ~300 px (track.detect_faces)
# Whisper в тишине и на ветре выдумывает титры («Продолжение следует», «Субтитры сделал…») — их не берём
HALLUCINATIONS = ("продолжение следует", "субтитр", "редактор", "спасибо за просмотр", "подпишись", "dimatorzok",
                  "корректор", "amara", "до новых встреч")


def analysis_path(project: str, fid: str) -> Path:
    return survey_dir(project) / "files" / f"{fid.replace('/', '__')}.json"


def frames_dir(project: str, fid: str) -> Path:
    return survey_dir(project) / "frames" / fid.replace("/", "__")


def lens_regions(w: int, h: int, dual: bool) -> list:
    """Где в кадре анализа смотреть: обычный кадр — целиком; два фишая 360 — вписанный квадрат каждой линзы
    (чёрные углы вокруг круга врали бы в яркости и резкости)."""
    if not dual:
        return [(0, 0, w, h)]
    side = h
    inner = int(side / 1.4142)
    off = (side - inner) // 2
    return [(off, off, inner, inner), (side + off, off, inner, inner)]


def frame_stats(bgr, regions: list, prev_small):
    import cv2
    import numpy as np
    gray_full = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = np.hstack([gray_full[y:y + rh, x:x + rw] for x, y, rw, rh in regions])
    small = cv2.resize(gray, (96, max(8, int(96 * gray.shape[0] / gray.shape[1]))),
                       interpolation=cv2.INTER_AREA).astype(np.float32)
    diff = shift = 0.0
    if prev_small is not None and prev_small.shape == small.shape:
        diff = float(np.abs(small - prev_small).mean())
        (dx, dy), _ = cv2.phaseCorrelate(prev_small, small)
        shift = float(np.hypot(dx, dy) / small.shape[1])
    return small, {
        "luma": round(float(gray.mean()), 1), "std": round(float(gray.std()), 1),
        "bright": round(float((gray > 245).mean()), 3),
        "sharp": round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1),
        "diff": round(diff, 2), "shift": round(shift, 4)}


def faces_in(detector, bgr, regions: list, dual: bool) -> list:
    """Лица: [линза, центр x, центр y (доли своей области), высота (доля высоты), уверенность] — три крупнейших."""
    found = []
    h, w = bgr.shape[:2]
    areas = [(0, 0, w // 2, h), (w // 2, 0, w // 2, h)] if dual else [(0, 0, w, h)]
    for lens, (x, y, aw, ah) in enumerate(areas):
        detector.setInputSize((aw, ah))
        _, rows = detector.detect(bgr[y:y + ah, x:x + aw].copy())
        for row in rows if rows is not None else []:
            fx, fy, fw, fh = (float(v) for v in row[:4])
            found.append([lens if dual else None, round((fx + fw / 2) / aw, 3), round((fy + fh / 2) / ah, 3),
                          round(fh / ah, 3), round(float(row[-1]), 2)])
    return sorted(found, key=lambda f: -f[3])[:3]


def audio_rms(wav: Path) -> list:
    """Громкость окнами 0,1 с, дБ — читается кусками, память не растёт с длиной файла."""
    import wave
    import numpy as np
    out = []
    with wave.open(str(wav), "rb") as w:
        step = w.getframerate() // RMS_HZ
        while True:
            buf = w.readframes(step * 600)
            if not buf:
                break
            a = np.frombuffer(buf, np.int16).astype(np.float32) / 32768.0
            n = len(a) // step
            if n:
                rms = np.sqrt((a[:n * step].reshape(n, step) ** 2).mean(axis=1) + 1e-10)
                out += [round(float(v), 1) for v in 20 * np.log10(rms)]
    return out


def mark_words(words: list, rms: list) -> list:
    """Слово годно, если в его промежутке звук громче шума и это не выдуманный Whisper титр."""
    if not rms:
        return words
    import numpy as np
    # На улице шум всего на 3–5 дБ тише речи (IMG_7541: шум −29, речь −25 дБ): порог «громче шума» здесь — +3 дБ,
    # а неуверенное слово в настоящей тишине — выдумка. Строгий порог +8 выкинул 158 настоящих слов из 184.
    floor = float(np.percentile(rms, 10))
    for wd in words:
        a, b = int(wd["start"] * RMS_HZ), max(int(wd["start"] * RMS_HZ) + 1, int(np.ceil(wd["end"] * RMS_HZ)))
        loud = max(rms[a:b] or [-99.0])
        text = wd["word"].lower()
        heard = loud > floor + 3 or (wd.get("prob", 1) > 0.6 and loud > -50)
        wd["ok"] = heard and not any(h in text for h in HALLUCINATIONS)
    return words


def analyze_file(project: str, item: dict, force: bool = False) -> dict:
    import subprocess
    import tempfile
    import time
    import cv2
    import numpy as np
    import host
    from track import YUNET
    import transcribe

    out = analysis_path(project, item["id"])
    src = raw_dir(project) / item["analyze"]
    size = src.stat().st_size
    if out.exists() and not force:
        done = json.loads(out.read_text(encoding="utf-8"))
        if done.get("version") == LOCAL_VERSION and done.get("source_size") == size:
            return done
    dual = item["kind"] == "360"
    pv = item.get("preview") or item
    sw, shh = pv["width"], pv["height"]
    w = ANALYSIS_W * 2 if dual else ANALYSIS_W
    h = int(round(shh * w / sw / 2) * 2)
    regions = lens_regions(w, h, dual)
    cv2.setNumThreads(host.encoder_threads())            # пара ядер — человеку за ноутом
    if not YUNET.exists():
        raise SurveyError(f"нет модели лиц {YUNET.relative_to(ROOT)}")
    # модель — байтами: OpenCV на Windows не открывает путь с кириллицей
    detector = cv2.FaceDetectorYN.create("onnx", np.frombuffer(YUNET.read_bytes(), np.uint8),
                                         np.empty(0, np.uint8), (w, h), 0.6, 0.3, 50)
    thumbs = frames_dir(project, item["id"])
    thumbs.mkdir(parents=True, exist_ok=True)
    tw = int(round(THUMB_H * w / h / 2) * 2)
    started = time.time()
    frames, prev = [], None
    err = tempfile.TemporaryFile()
    proc = subprocess.Popen([ffmpeg_bin(), "-v", "error", "-threads", "4", "-i", str(src), "-map", "0:v:0", "-an",
                             "-vf", f"fps={SAMPLE_FPS},scale={w}:{h}", "-pix_fmt", "bgr24", "-f", "rawvideo", "-"],
                            stdout=subprocess.PIPE, stderr=err)
    try:
        while True:
            buf = proc.stdout.read(w * h * 3)
            if len(buf) < w * h * 3:
                break
            bgr = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            prev, st = frame_stats(bgr, regions, prev)
            st["faces"] = faces_in(detector, bgr, regions, dual)
            i = len(frames)
            if i % THUMB_EVERY == 0:
                cv2.imwrite(str(thumbs / f"{i // THUMB_EVERY:05d}.jpg"), cv2.resize(bgr, (tw, THUMB_H),
                            interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 72])
            frames.append(st)
            if i and i % (SAMPLE_FPS * 60) == 0:
                print(f"     {item['id']}: {i // SAMPLE_FPS // 60} мин кадров", flush=True)
    finally:
        proc.stdout.close()
        proc.wait()
        err.seek(0)
        stderr = err.read().decode(errors="replace")
        err.close()
    if not frames:
        raise SurveyError(f"ffmpeg не отдал кадров из {item['analyze']}:\n{stderr[-500:]}")
    t_frames = time.time() - started

    words, rms = [], []
    if item.get("audio"):
        tmp = survey_dir(project) / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        wav = tmp / f"{item['id'].replace('/', '__')}.16k.wav"
        try:
            transcribe.extract_audio(src, wav)
            rms = audio_rms(wav)
            if rms and max(rms) > -50:                   # совсем немой файл Whisper не гоняем: выдумает титры
                words = mark_words(transcribe.transcribe(wav, "ru")["words"], rms)
        finally:
            wav.unlink(missing_ok=True)                  # дорожка — временная, даже при сбое (инвариант 5)
    data = {"version": LOCAL_VERSION, "id": item["id"], "analyze": item["analyze"], "source_size": size,
            "duration": item["duration"], "dual": dual, "sample_fps": SAMPLE_FPS, "thumb_fps": SAMPLE_FPS / THUMB_EVERY,
            "frames": frames, "rms_hz": RMS_HZ, "rms": rms, "words": words,
            "seconds": {"frames": round(t_frames, 1), "total": round(time.time() - started, 1)}}
    write_json(out, data)
    return data


def run_local(project: str, only: list | None = None, force: bool = False) -> None:
    require_queue("отсмотр съёмки (кадры, лица, речь)")
    inv = load_inventory(project)
    items = [v for v in inv["videos"] if not only or v["id"] in only]
    missing = set(only or []) - {v["id"] for v in items}
    if missing:
        raise SurveyError(f"нет в описи: {', '.join(sorted(missing))}")
    total = sum(v["duration"] for v in items)
    done_sec = 0.0
    for n, item in enumerate(items, 1):
        print(f"  [{n}/{len(items)}] {item['id']} — {item['duration'] / 60:.1f} мин", flush=True)
        data = analyze_file(project, item, force)
        done_sec += item["duration"]
        print(f"     ✓ слов {len(data['words'])}, кадров {len(data['frames'])}, {data['seconds']['total']:.0f} с "
              f"· готово {done_sec / total:.0%}", flush=True)


# ---------------------------------------------------------------- куски и брак

MIN_PIECE = 1.5             # с: короче — не законченное действие
UTTER_GAP = 0.8             # с: пауза, которая делит речь на фразы
BLOCK_GAP = 1.5             # с: фразы ближе этого — один разговор, один кусок
ABSORB = 2.0                # с: немой обрывок короче этого прирастает к соседней речи
QUIET_MAX = 15.0            # с: длинный немой план режется на куски не длиннее этого
SPEECH_MAX = 30.0           # с: длинный разговор режется в самой длинной паузе
# брак — по медиане кадров куска (калибровка — лист кадров пробы, 24.10.2026)
DARK_LUMA = 38
BRIGHT_FRAC = 0.35
FLAT_STD = 13               # однотонный кадр: асфальт в упор, карман, ладонь на объективе
BLUR_SHARP = 40
SHAKE_SHIFT = 0.2           # доля ширины за 1/4 с: камеру мотает, а не ведут. 0,09 браковал проходки и пан
                            # (лист брака 24.10.2026: Дед в шлеме на набережной); ниже порога судит Gemini
MOVING_SHIFT = 0.08         # выше — Gemini узнаёт, что камера сильно движется


def short_id(fid: str) -> str:
    """Короткая метка файла в id куска: IMG_7009, N0038 (DJI Nano), X0080 (360)."""
    folder, stem = fid.split("/", 1)
    tail = stem.split("_")
    if folder.upper().startswith("DJI_NANO"):
        return "N" + tail[2]
    if folder.upper().startswith("DJI_360"):
        return "X" + tail[2]
    return stem


def utterances(words: list) -> list:
    """Годные слова → фразы [(начало, конец, текст)]."""
    out = []
    for wd in (w for w in words if w.get("ok", True)):
        if out and wd["start"] - out[-1][1] <= UTTER_GAP:
            out[-1] = (out[-1][0], wd["end"], out[-1][2] + " " + wd["word"])
        else:
            out.append((wd["start"], wd["end"], wd["word"]))
    return out


def quiet_edge(rms: list, t: float, direction: int, limit: float, floor: float) -> float:
    """Сдвиг края речи наружу до тишины (не дальше limit): Whisper ставит конец слова раньше, чем договорили.
    Точный рез в тишину делает монтаж (pack.py, инвариант 3) — здесь только чтобы кусок не начинался с полслова."""
    if not rms:
        return t
    i = int(t * RMS_HZ)
    for step in range(int(limit * RMS_HZ) + 1):
        j = i + direction * step
        if j < 0 or j >= len(rms):
            break
        if rms[j] < floor + 2:            # на улице речь всего на 3–5 дБ громче шума
            return round(j / RMS_HZ, 2)
    return round(t + direction * limit, 2)


def split_quiet(a: float, b: float, frames: list, fps: float) -> list:
    """Немой промежуток → куски не длиннее QUIET_MAX, рез — на самом заметном изменении кадра."""
    out = []
    while b - a > QUIET_MAX:
        lo, hi = int((a + 5) * fps), int(min(b - MIN_PIECE, a + QUIET_MAX) * fps)
        best = max(range(lo, hi + 1), key=lambda i: frames[i]["diff"] if i < len(frames) else -1, default=hi)
        out.append((a, best / fps))
        a = best / fps
    out.append((a, b))
    return out


def split_speech(block: tuple, utts: list) -> list:
    """Разговор длиннее SPEECH_MAX — пополам в самой длинной паузе между фразами (фраза не рвётся)."""
    a, b = block
    inner = [u for u in utts if u[0] >= a - 0.01 and u[1] <= b + 0.01]
    if b - a <= SPEECH_MAX or len(inner) < 2:
        return [block]
    gaps = [(inner[i + 1][0] - inner[i][1], (inner[i][1] + inner[i + 1][0]) / 2) for i in range(len(inner) - 1)]
    # самая длинная пауза, но не у самого края — иначе отрежется обрывок
    _, at = max(gaps, key=lambda g: g[0] - abs(g[1] - (a + b) / 2) / (b - a))
    return split_speech((a, at), utts) + split_speech((at, b), utts)


def segment(data: dict) -> list:
    """Файл → куски [(начало, конец)]: границы планов, разговоры целиком, немое — по смене кадра."""
    import numpy as np
    fps, dur, rms = data["sample_fps"], data["duration"], data["rms"]
    floor = float(np.percentile(rms, 10)) if rms else -60.0
    utts = utterances(mark_words(data["words"], rms))
    # В сырых дублях склеек нет: «смена плана» по разнице кадров — это рывок камеры, и разговор через него не рвётся.
    # Рывки остаются точками реза для немых планов (split_quiet).
    bounds = [0.0, dur]
    pieces = []
    for s0, s1 in zip(bounds, bounds[1:]):
        blocks = []
        for u0, u1, _ in (u for u in utts if s0 <= (u[0] + u[1]) / 2 < s1):
            if blocks and u0 - blocks[-1][1] <= BLOCK_GAP:
                blocks[-1][1] = u1
            else:
                blocks.append([u0, u1])
        intervals, cur = [], s0
        for a, b in blocks:
            a = max(cur, s0, quiet_edge(rms, a, -1, 0.5, floor))
            b = max(a, min(s1, quiet_edge(rms, b, 1, 0.6, floor)))
            if a > cur:
                intervals.append((cur, a, "quiet"))
            intervals.append((a, b, "speech"))
            cur = b
        if s1 > cur:
            intervals.append((cur, s1, "quiet"))
        # немые обрывки короче ABSORB прирастают к соседней речи; речь через такой обрывок — один разговор
        out = []
        for a, b, kind in intervals:
            short_quiet = kind == "quiet" and b - a < ABSORB
            if out and short_quiet and out[-1][2] == "speech":
                out[-1] = (out[-1][0], b, "speech")
            elif out and kind == "speech" and (out[-1][2] == "speech" or out[-1][1] - out[-1][0] < ABSORB):
                out[-1] = (out[-1][0], b, "speech")
            else:
                out.append((a, b, kind))
        for a, b, kind in out:
            pieces += split_speech((a, b), utts) if kind == "speech" else split_quiet(a, b, data["frames"], fps)
    return [(round(a, 2), round(b, 2)) for a, b in pieces if b - a > 0.05]


def piece_stats(data: dict, a: float, b: float) -> dict:
    import numpy as np
    fps = data["sample_fps"]
    fr = data["frames"][int(a * fps):max(int(a * fps) + 1, int(b * fps))]
    med = {k: float(np.median([f[k] for f in fr])) for k in ("luma", "std", "bright", "sharp", "shift")}
    faces = [f["faces"] for f in fr]
    with_face = [fc for fc in faces if fc]
    lens = [fc[0][0] for fc in with_face if fc[0][0] is not None]
    rms = data["rms"][int(a * RMS_HZ):int(b * RMS_HZ) + 1]
    speech_rms = [v for v in data["rms"] if v > -45] or [-45.0]
    words = [w for w in data["words"] if w.get("ok", True) and a - 0.05 <= (w["start"] + w["end"]) / 2 < b + 0.05]
    return {
        **{k: round(v, 3) for k, v in med.items()},
        "faces_max": max((len(fc) for fc in faces), default=0),
        "face_share": round(len(with_face) / max(1, len(faces)), 2),
        "face_big": round(max((fc[0][3] for fc in with_face), default=0.0), 3),
        "lens": (max(set(lens), key=lens.count) if lens else None),
        "loud_peak": round(max(rms) - float(np.median(speech_rms)), 1) if rms else None,
        "text": " ".join(w["word"] for w in words).strip(),
        "words": len(words),
    }


def reject_reason(st: dict, dur: float) -> str | None:
    if dur < MIN_PIECE:
        return f"короче {MIN_PIECE:g} с"
    if st["luma"] < DARK_LUMA:
        return "тёмное"
    if st["bright"] > BRIGHT_FRAC:
        return "засветка"
    if st["std"] < FLAT_STD and not st["words"]:
        return "камера в землю / в карман (однотонный кадр)"
    if st["sharp"] < BLUR_SHARP and not st["words"]:
        return "мыло (нет резкости)"
    if st["shift"] > SHAKE_SHIFT and not st["words"]:
        return "сильная тряска"
    return None


def build_pieces(project: str) -> dict:
    inv = load_inventory(project)
    pieces, files = [], []
    for item in inv["videos"]:
        path = analysis_path(project, item["id"])
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        sp = sharp_p(item)
        files.append(item["id"])
        for a, b in segment(data):
            st = piece_stats(data, a, b)
            reason = reject_reason(st, b - a)
            pieces.append({"id": f"{short_id(item['id'])}-{int(round(a * 10)):05d}", "file": item["id"],
                           "path": item["path"], "kind": item["kind"], "start": a, "end": b,
                           "duration": round(b - a, 2), "sharp_p": sp, **st, "reject": reason})
    ids = [p["id"] for p in pieces]
    if len(ids) != len(set(ids)):
        raise SurveyError("два куска с одним id — разбиение дало пересекающиеся куски")
    out = {"project": project, "files": files, "pieces": pieces}
    write_json(catalog_dir(project) / "pieces.json", out)
    return out


def piece_frames(project: str, piece: dict, n: int) -> list:
    """n миниатюр куска, равномерно (из сохранённых локальным проходом — видео заново не читаем)."""
    folder = frames_dir(project, piece["file"])
    data_fps = SAMPLE_FPS / THUMB_EVERY
    first, last = int(piece["start"] * data_fps + 0.5), max(int(piece["start"] * data_fps + 0.5), int(piece["end"] * data_fps) - 1)
    idx = sorted({round(first + (last - first) * (k + 0.5) / n) for k in range(n)})
    paths = [folder / f"{i:05d}.jpg" for i in idx]
    return [p for p in paths if p.exists()]


def font(size: int):
    from PIL import ImageFont
    from common import FONT_DIR
    return ImageFont.truetype(str(FONT_DIR / "Onest-SemiBold.ttf"), size)


def file_sheet(project: str, fid: str, pieces: list) -> Path:
    """Лист кадров файла: по миниатюре на кусок, с id, таймкодом и причиной брака — глазами проверить отбор."""
    from PIL import Image, ImageDraw
    cell_w, cell_h, cols = 240, 300, 6
    rows = (len(pieces) + cols - 1) // cols
    sheet = Image.new("RGB", (cell_w * cols, max(1, rows) * cell_h), "white")
    draw, f_id, f_note = ImageDraw.Draw(sheet), font(12), font(11)
    for k, p in enumerate(pieces):
        x, y = (k % cols) * cell_w, (k // cols) * cell_h
        frames = piece_frames(project, p, 1)
        if frames:
            im = Image.open(frames[0])
            im.thumbnail((cell_w - 8, cell_h - 58))
            sheet.paste(im, (x + (cell_w - im.width) // 2, y + 4))
        draw.text((x + 6, y + cell_h - 52), f"{p['id']}  {clock(p['start'])}–{clock(p['end'])}", fill="black", font=f_id)
        note = ("✗ " + p["reject"]) if p.get("reject") else (p.get("text") or "")[:34]
        draw.text((x + 6, y + cell_h - 30), note, fill="#c00" if p.get("reject") else "#333", font=f_note)
    out = survey_dir(project) / "sheets" / f"{fid.replace('/', '__')}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=80)
    return out


def clock(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


# ---------------------------------------------------------------- Gemini: описание живых кусков

API = "https://generativelanguage.googleapis.com/v1beta"
MODEL_CHEAP = "gemini-3.1-flash-lite"       # 24.10.2026 самая дешёвая живая flash-lite
MODEL_SMART = ("gemini-3.8-flash", "gemini-3.6-flash")   # непонятое — сюда; 3.8 бывает перегружен (503)
# $ за 1 млн токенов, официальная страница ai.google.dev/gemini-api/docs/pricing, 24.10.2026 (платный уровень).
# Модели без цены здесь не вызываются: трата без счёта — не трата, а сюрприз.
PRICES = {
    "gemini-3.1-flash-lite": {"in": 0.25, "cached": 0.025, "out": 1.50},
    "gemini-3.5-flash-lite": {"in": 0.30, "cached": 0.03, "out": 2.50},
    "gemini-3.6-flash": {"in": 0.75, "cached": 0.075, "out": 3.75},    # до 31.12.2026, потом вдвое
    "gemini-3.8-flash": {"in": 0.75, "cached": 0.075, "out": 3.75},
}
BUDGET = 8.0                # $ на весь отсмотр (Валера, 24.10.2026)

TAGS = ["речь в камеру", "диалог с людьми", "стишок", "реакция на подарок", "вручение подарка", "подарки крупно",
        "мешок", "мороженое", "самокат", "мотоцикл", "турники", "зарядка", "пробки и машины", "полицейский",
        "объятия", "дети", "смех", "танец или игра", "дорога или проходка", "общий план места"]
SPEECH = ["нет", "в камеру", "диалог с людьми", "стишок", "за кадром", "фон или шум"]
LENSES = ["не 360", "герой в линзе 1 (левая половина)", "герой в линзе 2 (правая половина)", "герой в обеих",
          "героя нет"]

SCHEMA = {
    "type": "object",
    "properties": {
        "what": {"type": "string", "description": "что происходит, 1–2 конкретных предложения"},
        "who": {"type": "string", "description": "кто в кадре: Дед Вкудесник, прохожие (пол, возраст примерно), дети…"},
        "said": {"type": "string", "description": "о чём говорят — смысл по-русски; пусто, если речи нет"},
        "speech": {"type": "string", "enum": SPEECH},
        "emotion": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string", "enum": TAGS}},
        "pillars": {"type": "array", "items": {"type": "integer"}, "description": "номера подходящих опор 1–18"},
        "strength": {"type": "integer", "description": "1–5: насколько момент держит внимание в рилсе"},
        "hook": {"type": "boolean", "description": "первые 1–2 с куска сами цепляют как начало рилса"},
        "hook_note": {"type": "string"},
        "people": {"type": "integer", "description": "сколько людей видно"},
        "hero_lens": {"type": "string", "enum": LENSES},
        "usable": {"type": "boolean", "description": "годится ли кусок в рилс вообще"},
        "reject_why": {"type": "string"},
        "unsure": {"type": "boolean", "description": "не понял, что происходит"},
    },
    "required": ["id", "what", "who", "said", "speech", "emotion", "tags", "pillars", "strength", "hook", "people",
                 "hero_lens", "usable", "unsure"],
}
SCHEMA["properties"] = {"id": {"type": "string", "description": "id куска из запроса"}, **SCHEMA["properties"]}
GROUP_SCHEMA = {"type": "object", "properties": {"pieces": {"type": "array", "items": SCHEMA}}, "required": ["pieces"]}
GROUP = 4                   # кусков одного файла в запросе: у бесплатного ключа квота — запросы в сутки, а не токены


def system_prompt(project: str) -> str:
    """Общая часть запроса — одинаковая у всех кусков и первой в запросе: Google кэширует её сам (10× дешевле)."""
    pillars = (catalog_dir(project) / "pillars.md")
    if not pillars.exists():
        raise SurveyError(f"нет {pillars.relative_to(ROOT)}: опоры заказчика — по строке «N. текст»")
    return ("Ты отсматриваешь сырую съёмку для вертикальных рилсов бренда подарков «Вкудесник» (@vkudesnik_). "
            "Деда Мороза — «Деда Вкудесника» — играет сама основательница бренда (женщина в костюме, борода, красный "
            "кафтан). Съёмка в Москве (Лужники, набережная, улицы), сентябрь. Цель рилсов — узнаваемость бренда, "
            "покупатели и подписчики. Ролики держит живая речь человека в кадре и реакции людей; подарки (мешок, "
            "коробки) — это продукт, их крупные планы ценны.\n\n"
            "Тебе дают один или несколько кусков видео подряд из одного файла. У каждого — подпись с id, текст речи "
            "из Whisper (может быть с ошибками и выдумками в тишине — сверяй с кадрами), замеры и лист из нескольких "
            "кадров по порядку (слева направо; у 360-камеры кадры сверху вниз, в каждом две линзы фишай рядом: левая "
            "половина — линза 1, правая — линза 2). Опиши каждый кусок отдельно, с его id, для каталога: "
            "его прочтёт сценарист, который видео не видит. Пиши конкретно и коротко, по-русски, без воды и оценочных "
            "штампов. Не выдумывай того, чего нет в кадрах и речи; не уверен — unsure=true.\n\n"
            "strength: 5 — сильная живая эмоция или речь, готовый момент рилса; 4 — хороший живой момент; 3 — годный "
            "план-связка; 2 — проходной; 1 — почти ничего. hook — только если первые секунды сами по себе цепляют. "
            "pillars — только те опоры, для которых кусок реально пригоден.\n\nОпоры заказчицы:\n"
            + pillars.read_text(encoding="utf-8").strip())


def piece_prompt(piece: dict, inv_item: dict) -> str:
    cam = {"video": "айфон" if piece["path"].startswith("phone") else "DJI Osmo Nano (вертикально)",
           "360": "360-камера, две линзы фишай (сырые, не сшиты)", "360flat": "360-камера в режиме одной линзы"}
    lines = [f"Кусок {piece['id']}: камера — {cam.get(piece['kind'], piece['kind'])}, {piece['duration']:.1f} с, "
             f"снято {inv_item.get('shot_at', '')[:16].replace('T', ' ')} UTC.",
             f"Лиц найдено детектором: до {piece['faces_max']} (в {piece['face_share']:.0%} кадров; детектор "
             f"часто не видит лицо в бороде).",
             f"Пик громкости над речью: {piece['loud_peak']} дБ." if piece.get("loud_peak") is not None else "",
             "Камера сильно движется (возможна тряска и смаз) — годность реши по кадрам."
             if piece.get("shift", 0) > MOVING_SHIFT else "",
             f"Речь (Whisper): «{piece['text']}»" if piece["text"] else "Речи Whisper не нашёл."]
    return "\n".join(x for x in lines if x)


def frames_image(project: str, piece: dict) -> bytes:
    """Один лист из 2–4 маленьких кадров куска (JPEG): одна картинка дешевле нескольких."""
    import io
    from PIL import Image
    n = 2 if piece["duration"] <= 4 else 3 if piece["duration"] <= 12 else 4
    ims = [Image.open(p) for p in piece_frames(project, piece, n)]
    if not ims:
        raise SurveyError(f"нет миниатюр куска {piece['id']} — локальный проход не досчитан")
    if piece["kind"] == "360":                 # 640×320 — столбиком
        sheet = Image.new("RGB", (ims[0].width, sum(i.height for i in ims) + 4 * (len(ims) - 1)), "white")
        y = 0
        for im in ims:
            sheet.paste(im, (0, y))
            y += im.height + 4
    else:
        sheet = Image.new("RGB", (sum(i.width for i in ims) + 4 * (len(ims) - 1), max(i.height for i in ims)), "white")
        x = 0
        for im in ims:
            sheet.paste(im, (x, 0))
            x += im.width + 4
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=78)
    return buf.getvalue()


def request_body(project: str, group: list, inv: dict, model: str) -> dict:
    """Запрос на группу кусков: подпись куска, за ней его лист кадров — и так по очереди."""
    import base64
    parts = []
    for piece in group:
        parts += [{"text": piece_prompt(piece, inv[piece["file"]])},
                  {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(frames_image(project, piece)).decode()}}]
    return {
        "systemInstruction": {"parts": [{"text": system_prompt(project)}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json",
                             "responseJsonSchema": GROUP_SCHEMA, "mediaResolution": "MEDIA_RESOLUTION_MEDIUM",
                             # flash-lite думает «минимально» (дешевле всего), flash так не умеет — 400 «not supported»
                             "thinkingConfig": {"thinkingLevel": "minimal" if "lite" in model else "low"}},
    }


def groups_of(pieces: list) -> list:
    """Подряд идущие куски одного файла — по GROUP: соседние куски ещё и дают Gemini контекст сцены."""
    out = []
    for piece in pieces:
        if out and out[-1][0]["file"] == piece["file"] and len(out[-1]) < GROUP:
            out[-1].append(piece)
        else:
            out.append([piece])
    return out


def cache_key(body: dict, model: str) -> str:
    import hashlib
    return hashlib.sha1((model + json.dumps(body, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()[:16]


def cost_of(usage: dict, model: str) -> float:
    price = PRICES[model]
    prompt = usage.get("promptTokenCount", 0)
    cached = usage.get("cachedContentTokenCount", 0)
    out = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
    usd = ((prompt - cached) * price["in"] + cached * price["cached"] + out * price["out"]) / 1e6
    return usd


def ledger_path(project: str) -> Path:
    return catalog_dir(project) / "gemini_ledger.jsonl"


def spent(project: str) -> dict:
    total = {"usd": 0.0, "in": 0, "cached": 0, "out": 0, "calls": 0}
    path = ledger_path(project)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                total["usd"] += r["usd"]
                total["in"] += r["in"]
                total["cached"] += r.get("cached", 0)
                total["out"] += r["out"]
                total["calls"] += 1
    total["usd"] = round(total["usd"], 4)
    return total


def log_spend(project: str, piece_id: str, model: str, usage: dict) -> float:
    usd = cost_of(usage, model)
    rec = {"at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"), "piece": piece_id, "model": model,
           "in": usage.get("promptTokenCount", 0),
           "cached": usage.get("cachedContentTokenCount", 0),
           "out": usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0), "usd": round(usd, 6)}
    ledger_path(project).parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path(project), "a", encoding="utf-8") as f:     # строка на вызов: обрыв не теряет учёт
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return usd


def answer_path(project: str, piece_id: str) -> Path:
    return catalog_dir(project) / "gemini" / f"{piece_id}.json"


def cached_answer(project: str, piece_id: str, key: str | None = None) -> dict | None:
    path = answer_path(project, piece_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if key is None or data.get("key") == key else None


class GeminiRefused(SurveyError):
    """Отказ Gemini с кодом. 429 — квота: минутная проходит паузой, суточная — до завтра (24.10.2026 ключ оказался
    бесплатного уровня: gemini-3.6-flash — 20 запросов в сутки, пакетного режима нет — 400 FAILED_PRECONDITION)."""

    def __init__(self, code: int, text: str):
        import re
        self.code, self.text = code, text
        try:
            err = json.loads(text)["error"]
            message = err.get("message", "")
            details = err.get("details", [])
        except (ValueError, KeyError, TypeError):
            message, details = text, []
        delay = next((d.get("retryDelay") for d in details if "retryDelay" in d), "") or ""
        self.retry = float(re.sub(r"[^\d.]", "", delay) or 0)
        self.daily = "PerDay" in text
        super().__init__(f"Gemini ответил {code}: {message[:500]}")


def post(url: str, body: dict, key: str, timeout: float = 120) -> dict:
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        raise GeminiRefused(e.code, text) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise SurveyError(f"нет связи с Gemini (нужен VPN?): {e}") from e


def parse_answer(resp: dict) -> dict:
    try:
        text = "".join(p.get("text", "") for p in resp["candidates"][0]["content"]["parts"])
        return json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        reason = (resp.get("candidates") or [{}])[0].get("finishReason") or resp.get("promptFeedback")
        raise SurveyError(f"Gemini вернул не JSON ({reason}): {str(resp)[:300]}") from e


def store_answer(project: str, piece: dict, key: str, model: str, answer: dict, usage: dict) -> None:
    write_json(answer_path(project, piece["id"]), {"piece": piece["id"], "key": key, "model": model,
                                                   "answer": answer, "usage": usage})


def generate(model: str, body: dict, api_key: str, can_skip: bool = False) -> dict | None:
    """Один запрос с паузами на минутную квоту и перегрузку; None — модель перегружена и есть куда уйти (can_skip)."""
    import time
    for attempt in range(6):
        try:
            return post(f"{API}/models/{model}:generateContent", body, api_key)
        except GeminiRefused as e:
            if e.code == 429 and e.daily:
                raise SurveyError(f"суточная квота {model} кончилась (ключ бесплатного уровня) — готовые ответы в "
                                  f"кэше, тот же запуск продолжит через {e.retry / 3600:.0f} ч") from e
            if e.code == 503 and can_skip:
                return None
            if e.code not in (429, 500, 503) or attempt == 5:
                raise
            time.sleep(min(90.0, max(e.retry, 10.0 * (attempt + 1))))
    return None


def describe_sync(project: str, pieces: list, budget: float, model: str = MODEL_CHEAP) -> None:
    """Описание кусков группами по GROUP. Пакетного режима (вдвое дешевле) у ключа бесплатного уровня нет —
    400 FAILED_PRECONDITION (24.10.2026); появится платный ключ — пакетный режим добавлять тогда, с живой проверкой."""
    import keys
    if model not in PRICES:
        raise SurveyError(f"у модели {model} нет цены в PRICES — без счёта не вызываем")
    api_key = keys.require("gemini")
    inv = {v["id"]: v for v in load_inventory(project)["videos"]}
    models = [model] + [m for m in MODEL_SMART if model in MODEL_SMART and m != model]   # 503 у flash — соседняя
    groups = groups_of(pieces)
    for n, group in enumerate(groups, 1):
        ids = [p["id"] for p in group]
        for m in models:
            body = request_body(project, group, inv, m)
            key = cache_key(body, m)
            if all(cached_answer(project, pid, key) for pid in ids):
                break                              # уже спрошено ровно это — второй раз не платим
            if spent(project)["usd"] >= budget:
                raise SurveyError(f"потрачено ${spent(project)['usd']:.2f} — потолок ${budget:.2f}; дальше — с разрешения")
            resp = generate(m, body, api_key, can_skip=m != models[-1])
            if resp is None:
                continue                           # перегружена — следующая из списка
            usage = resp.get("usageMetadata", {})
            usd = log_spend(project, "+".join(ids), m, usage)
            answers = {a.get("id"): a for a in parse_answer(resp).get("pieces", [])}
            lost = [pid for pid in ids if pid not in answers]
            for piece in group:
                if piece["id"] in answers:
                    store_answer(project, piece, key, m, answers[piece["id"]], usage)
            print(f"  [{n}/{len(groups)}] {', '.join(ids)} {m}: вход {usage.get('promptTokenCount')}, "
                  f"выход {usage.get('candidatesTokenCount', 0) + usage.get('thoughtsTokenCount', 0)}, ${usd:.5f}"
                  + (f" · БЕЗ ОТВЕТА: {', '.join(lost)}" if lost else ""), flush=True)
            break


def live_pieces(project: str) -> list:
    path = catalog_dir(project) / "pieces.json"
    if not path.exists():
        raise SurveyError(f"сначала куски: .venv/bin/python scripts/survey.py pieces {project}")
    return [p for p in json.loads(path.read_text(encoding="utf-8"))["pieces"] if not p["reject"]]


# ---------------------------------------------------------------- фото: листы миниатюр по 12

PHOTO_CELL, PHOTO_COLS, PHOTO_ROWS = 256, 4, 3
PHOTO_USE = ["портрет героя", "подарки крупно", "люди и эмоции", "место или фон", "команда или съёмка", "брак"]
PHOTO_SCHEMA = {"type": "object", "properties": {"photos": {"type": "array", "items": {"type": "object", "properties": {
    "n": {"type": "integer"}, "what": {"type": "string"}, "use": {"type": "string", "enum": PHOTO_USE},
    "strength": {"type": "integer"}, "pillars": {"type": "array", "items": {"type": "integer"}}},
    "required": ["n", "what", "use", "strength", "pillars"]}}}, "required": ["photos"]}


def photo_thumb(project: str, item: dict) -> Path | None:
    """Миниатюра фото 256 px (кэш в work/_survey): JPEG — черновым декодом PIL, HEIC — через ffmpeg."""
    import subprocess
    from PIL import Image
    out = survey_dir(project) / "photos" / f"{item['id'].replace('/', '__')}.jpg"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    src = raw_dir(project) / item["path"]
    tmp = None
    try:
        if src.suffix.lower() == ".heic":
            tmp = survey_dir(project) / "tmp" / (out.stem + ".png")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            r = subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(src), "-frames:v", "1", str(tmp)],
                               capture_output=True, encoding="utf-8", errors="replace")
            if r.returncode != 0:
                return None
            src = tmp
        im = Image.open(src)
        im.draft("RGB", (PHOTO_CELL * 2, PHOTO_CELL * 2))
        from PIL import ImageOps
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((PHOTO_CELL, PHOTO_CELL))
        im.save(out, quality=80)
        return out
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def describe_photos(project: str, budget: float, model: str) -> None:
    """Фото — пачкой: лист из 12 пронумерованных миниатюр на запрос (~$0,002 на лист у flash)."""
    import base64
    import io
    import keys
    from PIL import Image, ImageDraw
    api_key = keys.require("gemini")
    photos = load_inventory(project)["photos"]
    per = PHOTO_COLS * PHOTO_ROWS
    for g in range(0, len(photos), per):
        group = photos[g:g + per]
        sheet = Image.new("RGB", (PHOTO_COLS * PHOTO_CELL, PHOTO_ROWS * PHOTO_CELL), "white")
        draw, f = ImageDraw.Draw(sheet), font(28)
        for k, item in enumerate(group):
            x, y = (k % PHOTO_COLS) * PHOTO_CELL, (k // PHOTO_COLS) * PHOTO_CELL
            thumb = photo_thumb(project, item)
            if thumb:
                im = Image.open(thumb)
                sheet.paste(im, (x + (PHOTO_CELL - im.width) // 2, y + (PHOTO_CELL - im.height) // 2))
            draw.rectangle((x, y, x + 40, y + 36), fill="black")
            draw.text((x + 6, y + 2), str(k + 1), fill="yellow", font=f)
        buf = io.BytesIO()
        sheet.save(buf, "JPEG", quality=80)
        body = {"systemInstruction": {"parts": [{"text": system_prompt(project)}]},
                "contents": [{"role": "user", "parts": [
                    {"text": f"Это лист из {len(group)} фото со съёмки, номера — в чёрных квадратах. Для каждого: что на "
                             "фото (одна фраза), для чего годится во вставке, сила 1–5, подходящие опоры."},
                    {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}}]}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json",
                                     "responseJsonSchema": PHOTO_SCHEMA, "mediaResolution": "MEDIA_RESOLUTION_HIGH",
                                     "thinkingConfig": {"thinkingLevel": "minimal" if "lite" in model else "low"}}}
        key = cache_key(body, model)
        gid = f"photos-{g // per + 1:03d}"
        if cached_answer(project, gid, key):
            continue
        if spent(project)["usd"] >= budget:
            raise SurveyError(f"потрачено ${spent(project)['usd']:.2f} — потолок ${budget:.2f}; дальше — с разрешения")
        resp = generate(model, body, api_key)
        usage = resp.get("usageMetadata", {})
        usd = log_spend(project, gid, model, usage)
        answer = parse_answer(resp)
        answer["files"] = [p["id"] for p in group]
        write_json(answer_path(project, gid), {"piece": gid, "key": key, "model": model,
                                               "answer": answer, "usage": usage})
        print(f"  {gid}: {len(group)} фото, ${usd:.4f}", flush=True)


def photo_answers(project: str) -> dict:
    out = {}
    for path in sorted((catalog_dir(project) / "gemini").glob("photos-*.json")):
        ans = json.loads(path.read_text(encoding="utf-8"))["answer"]
        for row in ans.get("photos", []):
            if 1 <= row["n"] <= len(ans["files"]):
                out[ans["files"][row["n"] - 1]] = row
    return out


# ---------------------------------------------------------------- каталог

CAMERA = {"phone": "айфон", "DJI_NANO": "DJI Nano", "DJI_360": "360"}
STRONG = 4                  # «сильный момент» в отчёте — сила от 4
SCENE_GAP = 90              # с: перерыв в съёмке дольше этого — новая сцена


def camera_of(piece: dict) -> str:
    if piece["kind"] == "360":
        return "360, две линзы (не сшито)"
    if piece["kind"] == "360flat":
        return "360 одной линзой"
    return CAMERA.get(Path(piece["path"]).parent.name, Path(piece["path"]).parent.name)


def msk(shot_at: str, offset: float):
    """Время съёмки по Москве: все три камеры пишут честное UTC (DJI — сверено с часами в имени файла)."""
    from datetime import datetime, timedelta
    if not shot_at:
        return None
    return datetime.fromisoformat(shot_at.replace("Z", "+00:00")) + timedelta(hours=3, seconds=offset)


def final_status(piece: dict, ans: dict | None) -> tuple:
    """(статус, причина): live — живой, reject — брак (с причиной), undescribed — живой, но Gemini не ответил."""
    if piece["reject"]:
        return "reject", piece["reject"]
    if ans is None:
        return "undescribed", "нет описания Gemini"
    a = ans["answer"]
    if not a.get("usable", True):
        return "reject", "по смыслу: " + (a.get("reject_why") or "не годится")
    product = {"подарки крупно", "мешок", "вручение подарка", "мороженое"} & set(a.get("tags", []))
    if a.get("people", 1) == 0 and a.get("speech") in ("нет", "фон или шум") and not product:
        return "reject", "нет ни людей, ни речи"
    return "live", ""


def build_catalog(project: str) -> dict:
    inv = load_inventory(project)
    items = {v["id"]: v for v in inv["videos"]}
    raw = json.loads((catalog_dir(project) / "pieces.json").read_text(encoding="utf-8"))["pieces"]
    pieces = []
    for p in raw:
        ans = cached_answer(project, p["id"])
        status, why = final_status(p, ans)
        t0 = msk(items[p["file"]].get("shot_at", ""), p["start"])
        t1 = msk(items[p["file"]].get("shot_at", ""), p["end"])
        entry = {"id": p["id"], "file": p["file"], "path": p["path"], "camera": camera_of(p), "start": p["start"],
                 "end": p["end"], "duration": p["duration"], "time": f"{clock(p['start'])}–{clock(p['end'])}",
                 "msk": t0.strftime("%d.%m %H:%M:%S") if t0 else "", "_t": (t0, t1),
                 "sharp_p": p["sharp_p"], "faces_max": p["faces_max"], "loud_peak": p["loud_peak"],
                 "whisper": p["text"], "status": status, "reject": why}
        if ans:
            a = ans["answer"]
            entry.update({k: a.get(k) for k in ("what", "who", "said", "speech", "emotion", "tags", "pillars",
                                                 "strength", "hook", "hook_note", "people", "unsure")})
            entry["pillars"] = sorted({n for n in entry["pillars"] or [] if 1 <= n <= 18})
            if p["kind"] == "360":
                entry["hero_lens"] = a.get("hero_lens")
            entry["model"] = ans["model"]
        pieces.append(entry)
    # тот же момент другой камерой — пересечение по московскому времени
    live = [e for e in pieces if e["status"] != "reject" and e["_t"][0]]
    for e in live:
        e["same_moment"] = [o["id"] for o in live if o["file"] != e["file"]
                            and o["_t"][0] < e["_t"][1] and e["_t"][0] < o["_t"][1]]
    # сцена — встреча или эпизод: куски всех камер, снятые без перерыва дольше SCENE_GAP. Один ролик — обычно одна
    # сцена; «сколько разных роликов» по опоре честнее считать сценами, а не файлами (их снимали тремя камерами разом)
    scenes, end = [], None
    for e in sorted(live, key=lambda r: r["_t"][0]):
        if end is None or (e["_t"][0] - end).total_seconds() > SCENE_GAP:
            scenes.append([])
        scenes[-1].append(e)
        end = max(end, e["_t"][1]) if end and scenes[-1][:-1] else e["_t"][1]
    scene_list = []
    for k, rows in enumerate(scenes, 1):
        sid = f"S{k:02d}"
        for e in rows:
            e["scene"] = sid
        best = sorted(rows, key=rank)[0]
        scene_list.append({"id": sid, "from": rows[0]["_t"][0].strftime("%d.%m %H:%M"),
                           "to": max(r["_t"][1] for r in rows).strftime("%H:%M"),
                           "cameras": sorted({r["camera"] for r in rows}), "pieces": [r["id"] for r in rows],
                           "best": best["id"], "strength": best.get("strength"), "what": best.get("what")})
    for e in pieces:
        e.pop("_t")
    photos = []
    pa = photo_answers(project)
    for ph in inv["photos"]:
        row = pa.get(ph["id"], {})
        photos.append({"id": ph["id"], "path": ph["path"], "width": ph.get("width"), "height": ph.get("height"),
                       **{k: row.get(k) for k in ("what", "use", "strength", "pillars")}})
    folders = {}
    for e in pieces:
        f = folders.setdefault(str(Path(e["path"]).parent), {"hours": 0.0, "live_hours": 0.0, "pieces": 0, "live": 0})
        f["hours"] += e["duration"] / 3600
        f["pieces"] += 1
        if e["status"] != "reject":
            f["live_hours"] += e["duration"] / 3600
            f["live"] += 1
    for f in folders.values():
        f["hours"], f["live_hours"] = round(f["hours"], 3), round(f["live_hours"], 3)
    data = {"project": project, "built": __import__("time").strftime("%Y-%m-%d %H:%M"), "folders": folders,
            "gemini": spent(project), "pillars": pillar_texts(project), "scenes": scene_list, "pieces": pieces,
            "photos": photos}
    write_json(catalog_dir(project) / "catalog.json", data)
    cat = catalog_dir(project)
    (cat / "catalog.md").write_text(catalog_md(data), encoding="utf-8")
    (cat / "photos.md").write_text(photos_md(data), encoding="utf-8")
    scenes_dir = cat / "scenes"
    scenes_dir.mkdir(exist_ok=True)
    for old in scenes_dir.glob("S*.md"):          # сцены пересчитываются — старые номера не должны висеть
        old.unlink()
    for sc in scene_list:
        (scenes_dir / f"{sc['id']}.md").write_text(scene_md(data, sc), encoding="utf-8")
    return data


def pillar_texts(project: str) -> dict:
    out = {}
    for line in (catalog_dir(project) / "pillars.md").read_text(encoding="utf-8").splitlines():
        num, _, text = line.partition(".")
        if num.strip().isdigit():
            out[int(num)] = text.strip()
    return out


def rank(e: dict) -> tuple:
    return (-(e.get("strength") or 0), not e.get("hook"), -e["duration"])


def line(e: dict, said_len: int = 160) -> str:
    """Строка куска для списков: сила, id, камера, сцена, таймкод, что происходит и (коротко) что говорят."""
    said = (e.get("said") or "").strip() if said_len else ""
    said = said if len(said) <= said_len else said[:said_len - 1] + "…"
    lens = f", {e['hero_lens']}" if e.get("hero_lens") else ""
    return (f"- ★{e.get('strength') or '?'} **{e['id']}** · {e.get('scene', '')} · {e['camera']}{lens} · {e['time']} "
            f"({e['duration']:.0f} с){' · хук' if e.get('hook') else ''} — {e.get('what') or ''}"
            + (f" Говорят: {said}" if said else ""))


def card(e: dict) -> list:
    """Полная карточка куска — в файле сцены."""
    lens = f" · {e['hero_lens']}" if e.get("hero_lens") else ""
    out = [f"- **{e['id']}** · {e['camera']} · `{e['path']}` {e['time']} ({e['duration']:.1f} с) · {e['msk']} МСК · "
           f"★{e.get('strength') or '?'}{' · хук: ' + (e.get('hook_note') or '') if e.get('hook') else ''}{lens}"]
    if e["status"] == "undescribed":
        out.append("  - НЕТ ОПИСАНИЯ (Gemini не ответил)")
    else:
        out.append(f"  - Что: {e.get('what')} Кто: {e.get('who')} Эмоция: {e.get('emotion')}.")
        out.append(f"  - Речь: {e.get('speech')}. {e.get('said') or ''}".rstrip())
        out.append(f"  - Метки: {', '.join(e.get('tags') or []) or '—'}; опоры: "
                   f"{', '.join(map(str, e.get('pillars') or [])) or '—'}; людей: {e.get('people')}"
                   + (" · Gemini не уверен" if e.get("unsure") else ""))
    if e["whisper"]:
        out.append(f"  - Whisper: «{e['whisper']}»")
    if e.get("same_moment"):
        out.append(f"  - Тот же момент: {', '.join(e['same_moment'][:6])}")
    return out


HOW_TO_READ = (
    "**Как читать.** `id` куска — метка файла + начало в десятых секунды (`IMG_7009-00262` — IMG_7009 с 26,2 с; "
    "`N0038-…` — DJI Nano, файл `…_0038_D`; `X0084-…` — 360-камера, файл `CAM_…_0084_D`). `S04` — сцена. Таймкоды — "
    "секунды файла, границы речи примерные: точный рез в тишину делает сборка (`pack.py`). ★ — сила момента 1–5 "
    "(5 — готовый момент рилса). «Говорят» — смысл речи от Gemini; дословно — строка Whisper в карточке сцены. "
    "«Тот же момент» — куски других камер, снятые в те же секунды.\n\n"
    "**360 (.OSV)** — две несшитые линзы фишай; «линза 1» — левая половина превью .LRF, «линза 2» — правая. "
    "Выпрямленный кадр из одной линзы — около 670p (ниже пола 720p во весь кадр): только карточкой, полосой или в сплите.")


def catalog_md(data: dict) -> str:
    """Оглавление: сводка, сцены, хуки, речь, подарки, опоры — сильное; карточки — в scenes/, фото — в photos.md.
    Целиком (1,25 МБ, ~400 тыс. токенов) каталог сессии сценариев не прочесть — так он и не пишется."""
    live = [e for e in data["pieces"] if e["status"] == "live"]
    rejects = [e for e in data["pieces"] if e["status"] == "reject"]
    undescribed = [e for e in data["pieces"] if e["status"] == "undescribed"]
    g = data["gemini"]
    out = [f"# Каталог отсмотра — {data['project']}", "",
           f"Собран {data['built']} скриптом `scripts/survey.py` (движок). Это текст для сценариев: видео смотреть не "
           "нужно. Здесь — оглавление и сильное; все куски сцены с речью дословно — `scenes/<сцена>.md`, фото — "
           "`photos.md`, всё машиночитаемо — `catalog.json`. Листы кадров для проверки глазами — "
           "`work/_survey/<проект>/sheets/<файл>.jpg`.", "", HOW_TO_READ, "",
           "## Сводка", "", "| папка | часов всего | живого | кусков | живых |", "|---|---|---|---|---|"]
    for folder, f in data["folders"].items():
        out.append(f"| {folder} | {f['hours']:.2f} | {f['live_hours']:.2f} | {f['pieces']} | {f['live']} |")
    out += ["", f"Gemini: ${g['usd']:.2f} по ценам платного уровня, вызовов {g['calls']}, токенов — вход {g['in']}, "
            f"выход {g['out']}.", f"Живых кусков {len(live)}, брак {len(rejects)}"
            + (f", без описания {len(undescribed)}" if undescribed else "") + f". Фото — {len(data['photos'])}.", "",
            "## Сцены", "", f"Сцена — эпизод съёмки без перерыва дольше {SCENE_GAP} с, всеми камерами вместе. Длинная "
            "сцена (прогулка, поездка) — это много встреч подряд: «разных роликов» в ней столько, сколько разных "
            "встреч и идей, а не одна.", "",
            "| сцена | время (МСК) | камеры | кусков | ★4+ | лучший | что |", "|---|---|---|---|---|---|---|"]
    for sc in data.get("scenes", []):
        strong = sum(1 for e in live if e.get("scene") == sc["id"] and (e.get("strength") or 0) >= STRONG)
        out.append(f"| [{sc['id']}](scenes/{sc['id']}.md) | {sc['from']}–{sc['to']} | {', '.join(sc['cameras'])} | "
                   f"{len(sc['pieces'])} | {strong} | ★{sc['strength'] or '?'} {sc['best']} | "
                   f"{(sc['what'] or '').replace('|', '/')} |")
    out.append("")

    def section(title: str, rows: list, note: str = "", floor: int = 3, said_len: int = 120):
        shown = sorted((e for e in rows if (e.get("strength") or 0) >= floor), key=rank)
        out.extend([f"## {title} ({len(rows)}, здесь от ★{floor} — {len(shown)})", ""] + ([note, ""] if note else []))
        out.extend(line(e, said_len) for e in shown)
        out.append("")

    section("Лучшие хуки (первые 1–2 с)", [e for e in live if e.get("hook")],
            "Куски, первые секунды которых сами цепляют как начало рилса.")
    section("Речь в камеру", [e for e in live if e.get("speech") == "в камеру"],
            "Главный ресурс по референсу заказчицы (GoHoney): человек сам говорит в кадр.")
    section("Диалоги с людьми", [e for e in live if e.get("speech") == "диалог с людьми"], floor=4)
    section("Стишки", [e for e in live if e.get("speech") == "стишок" or "стишок" in (e.get("tags") or [])], floor=1)
    section("Реакции на подарок и вручение", [e for e in live if {"реакция на подарок", "вручение подарка", "объятия"}
                                              & set(e.get("tags") or [])])
    section("Подарки крупно (продукт)", [e for e in live if {"подарки крупно", "мешок", "мороженое"}
                                         & set(e.get("tags") or [])],
            "Продукт — как бутылка у GoHoney: мешок, коробки, вручение крупно.")
    out += ["## По опорам заказчицы", "",
            f"Здесь — куски от ★{STRONG} без пересказа речи (он — в разделах выше и в карточках сцен); ★3 и слабее — "
            "в catalog.json. «Разных сцен» — сколько эпизодов съёмки дают сильные куски.", ""]
    for num, text in data["pillars"].items():
        rows = [e for e in live if num in (e.get("pillars") or [])]
        strong = sorted((e for e in rows if (e.get("strength") or 0) >= STRONG), key=rank)
        out += [f"### {num}. {text}", "",
                f"Кусков {len(rows)}, ★3 — {sum(1 for e in rows if e.get('strength') == 3)}, сильных (★{STRONG}+) "
                f"{len(strong)} из {len({e.get('scene') for e in strong})} сцен ({len({e['file'] for e in strong})} "
                "файлов).", ""]
        out.extend(line(e, 0) for e in strong)
        out.append("")
    out += [f"## Брак ({len(rejects)})", "", "Отброшено с причиной — для проверки глазами по листам кадров.", "",
            "| id | файл | время | причина |", "|---|---|---|---|"]
    for e in sorted(rejects, key=lambda r: (r["file"], r["start"])):
        out.append(f"| {e['id']} | {e['path']} | {e['time']} | {e['reject']} |")
    out += ["", f"## Фото ({len(data['photos'])}) — все в photos.md", ""]
    for use in PHOTO_USE + [None]:
        rows = [p for p in data["photos"] if p.get("use") == use]
        if rows:
            out.append(f"- {use or 'без описания'}: {len(rows)}, из них ★4+ — "
                       f"{sum(1 for p in rows if (p.get('strength') or 0) >= STRONG)}")
    return "\n".join(out) + "\n"


def scene_md(data: dict, scene: dict) -> str:
    rows = [e for e in data["pieces"] if e.get("scene") == scene["id"]]
    out = [f"# Сцена {scene['id']} — {scene['from']}–{scene['to']} МСК", "",
           f"Камеры: {', '.join(scene['cameras'])}. Кусков {len(rows)}, лучший — ★{scene['strength'] or '?'} "
           f"{scene['best']}: {scene['what']}", "", "Куски всех камер по времени съёмки. Как читать — catalog.md.", ""]
    for e in sorted(rows, key=lambda r: (r["msk"], r["file"])):
        out.extend(card(e))
    return "\n".join(out) + "\n"


def photos_md(data: dict) -> str:
    out = [f"# Фото ({len(data['photos'])})", "",
           "Вставки и стоп-кадры. Sony 6000×4000 — во весь кадр с запасом на кадрирование.", ""]
    for use in PHOTO_USE + [None]:
        rows = [p for p in data["photos"] if p.get("use") == use]
        if not rows:
            continue
        out += [f"## {use or 'без описания'} ({len(rows)})", ""]
        for ph in sorted(rows, key=lambda r: -(r.get("strength") or 0)):
            pill = f" (опоры {', '.join(map(str, ph['pillars']))})" if ph.get("pillars") else ""
            out.append(f"- ★{ph.get('strength') or '?'} `{ph['path']}` {ph.get('width')}×{ph.get('height')} — "
                       f"{ph.get('what') or ''}{pill}")
        out.append("")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- командная строка

def main():
    ap = argparse.ArgumentParser(description="Отсмотр большой съёмки: каталог живых моментов")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inventory", help="опись файлов (ffprobe)").add_argument("project")
    loc = sub.add_parser("local", help="кадры, лица, громкость и речь каждого видео (тяжёлое — через очередь)")
    loc.add_argument("project")
    loc.add_argument("--only", nargs="*", help="id файлов из описи (phone/IMG_7001 …)")
    loc.add_argument("--force", action="store_true")
    pcs = sub.add_parser("pieces", help="разбиение на куски, брак с причиной, листы кадров")
    pcs.add_argument("project")
    pcs.add_argument("--sheets", action="store_true", help="нарисовать листы кадров по файлам")
    gem = sub.add_parser("gemini", help="описание живых кусков (кадры + текст речи, не видео)")
    gem.add_argument("project")
    gem.add_argument("--files", nargs="*", help="только куски этих файлов (проба)")
    gem.add_argument("--retry-unsure", action="store_true", help="непонятое flash-lite — переспросить на flash")
    gem.add_argument("--model", default=MODEL_CHEAP, choices=sorted(PRICES))
    gem.add_argument("--budget", type=float, default=BUDGET)
    gph = sub.add_parser("photos", help="фото листами по 12 миниатюр → Gemini")
    gph.add_argument("project")
    gph.add_argument("--model", default=MODEL_CHEAP, choices=sorted(PRICES))
    gph.add_argument("--budget", type=float, default=BUDGET)
    sub.add_parser("build", help="catalog.json и catalog.md").add_argument("project")
    args = ap.parse_args()
    try:
        if args.cmd == "photos":
            describe_photos(args.project, args.budget, args.model)
            print(f"✓ фото описаны; расход Gemini всего ${spent(args.project)['usd']:.4f}")
        if args.cmd == "build":
            data = build_catalog(args.project)
            n = {s: sum(1 for e in data["pieces"] if e["status"] == s) for s in ("live", "reject", "undescribed")}
            print(f"✓ каталог: живых {n['live']}, брак {n['reject']}"
                  + (f", БЕЗ ОПИСАНИЯ {n['undescribed']} — сначала gemini" if n["undescribed"] else ""))
            print(f"  {(catalog_dir(args.project) / 'catalog.md').relative_to(ROOT)}")
        if args.cmd == "gemini":
            todo = [p for p in live_pieces(args.project) if not args.files or p["file"] in args.files]
            model = args.model
            if args.retry_unsure:
                todo = [p for p in todo if (a := cached_answer(args.project, p["id"]))
                        and a["model"] not in MODEL_SMART and a["answer"].get("unsure")]
                model = MODEL_SMART[0]
            describe_sync(args.project, todo, args.budget, model)
            s = spent(args.project)
            print(f"  расход Gemini: ${s['usd']:.4f}, вызовов {s['calls']}, токенов: вход {s['in']} (из кэша {s['cached']}), "
                  f"выход {s['out']}")
        if args.cmd == "pieces":
            data = build_pieces(args.project)
            live = [p for p in data["pieces"] if not p["reject"]]
            print(f"✓ кусков {len(data['pieces'])}, живых {len(live)}, "
                  f"{sum(p['duration'] for p in live) / 60:.1f} мин из {sum(p['duration'] for p in data['pieces']) / 60:.1f}")
            if args.sheets:
                for fid in data["files"]:
                    print("  ", file_sheet(args.project, fid, [p for p in data["pieces"] if p["file"] == fid])
                          .relative_to(ROOT))
        if args.cmd == "local":
            run_local(args.project, args.only, args.force)
        if args.cmd == "inventory":
            data = inventory(args.project)
            for folder, f in data["folders"].items():
                print(f"  {folder}: видео {f['videos']}, {f['hours']:.2f} ч; фото {f['photos']}")
            print(f"✓ опись: {len(data['videos'])} видео, {data['hours']:.2f} ч, фото {len(data['photos'])}"
                  + (f"; пропущено {len(data['skipped'])}" if data["skipped"] else ""))
    except SurveyError as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
