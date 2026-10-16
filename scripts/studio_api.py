#!/usr/bin/env python3
"""API студии монтажа: ролики и их состояние, бриф и стили, очередь, мозг (Claude/Codex).

Подключается к серверу панели (server.py) и живёт на той же машине, на 127.0.0.1.
Страница — web/studio.html. Тяжёлое отсюда не запускается напрямую: быстрый монтаж и
задачи мозга идут через очередь (jobqueue.py), а она выполняет их строго по одной.
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import approve
import brain
import formats
import host
import jobqueue
import materials
import projects
import styles
from common import ROOT, WORK_DIR, ffprobe_bin
from jobqueue import CURRENT, QUEUE, runner_alive

router = APIRouter()
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv"}
STEM_RE = re.compile(r"^[\w.\-]+$", re.UNICODE)
_probe_cache: dict = {}
runs: dict = {}            # thread_id → состояние текущего хода мозга
seen = {"at": 0.0}         # когда открытая вкладка студии последний раз спрашивала состояние


def safe_stem(stem: str) -> str:
    if not stem or not STEM_RE.match(stem) or stem.startswith("."):
        raise HTTPException(400, f"Плохое имя ролика: {stem!r}")
    return stem


def stream_dims(stream: dict) -> tuple:
    """Ширина и высота кадра, как его видит человек: с поворотом из метаданных.

    Айфон кладёт несколько записей (Dolby Vision, матрица поворота, …): пустая не должна затирать
    найденный поворот — иначе вертикальное видео считалось горизонтальным (16.10.2026).
    """
    w, h = stream.get("width"), stream.get("height")
    rotation = 0
    for entry in stream.get("side_data_list") or []:
        if "rotation" in entry:
            rotation = int(entry.get("rotation") or 0)
    if rotation in (90, -90, 270, -270):
        w, h = h, w
    return w, h


def quick_probe(path: Path) -> dict:
    """Размер и длительность; кэш по времени изменения — студия опрашивает часто."""
    key = (str(path), path.stat().st_mtime)
    if key in _probe_cache:
        return _probe_cache[key]
    out = subprocess.run([ffprobe_bin(), "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=width,height:stream_side_data=rotation:format=duration",
                          "-of", "json", str(path)], capture_output=True, encoding="utf-8", errors="replace")
    info = {"width": None, "height": None, "duration": None}
    try:
        data = json.loads(out.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
        w, h = stream_dims(stream)
        info = {"width": w, "height": h,
                "duration": round(float((data.get("format") or {}).get("duration", 0)), 1)}
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    _probe_cache[key] = info
    return info


def source_of(stem: str) -> Path | None:
    """Исходник ролика в input/ его проекта; нет — None. Одно имя в двух проектах — 409 с объяснением."""
    try:
        return projects.source(stem)
    except projects.ProjectError as e:
        raise HTTPException(409, str(e))


def outputs_for(stem: str, project: "projects.Project | None" = None) -> list:
    items = []
    final = (approve.approved(stem) or {}).get("file")
    try:
        folder = (project or projects.of(stem)).output
    except projects.ProjectError:
        return []
    for path in folder.glob(f"{stem}*"):
        if path.suffix.lower() not in VIDEO_EXT:
            continue
        rest = path.stem[len(stem):]
        if rest and rest[0] not in "_-":
            continue                      # IMG_32790 не принадлежит IMG_3279
        sheet = path.with_suffix(".sheet.jpg")
        items.append({"name": path.name, "mtime": path.stat().st_mtime,
                      "size_mb": round(path.stat().st_size / 1_048_576, 1),
                      "sheet": sheet.name if sheet.exists() else None,
                      "approved": path.name == final})
    return sorted(items, key=lambda i: -i["mtime"])


def video_state(path: Path, project: "projects.Project") -> dict:
    stem = path.stem
    work = WORK_DIR / stem
    try:
        brief = styles.load_brief(stem)
    except styles.StyleError as e:
        # битый бриф одного ролика не должен ронять весь список: ролик помечается ошибкой
        brief = dict(styles.DEFAULT_BRIEF, exists=True, error=str(e))
    info = quick_probe(path)
    fmt_src = None
    if info["width"] and info["height"]:
        fmt_src = "горизонталь" if info["width"] > info["height"] else (
            "квадрат" if info["width"] == info["height"] else "вертикаль")
    return {
        "stem": stem, "name": path.name, "mtime": path.stat().st_mtime,
        "project": project.name, "project_title": project.title,
        "size_mb": round(path.stat().st_size / 1_048_576, 1), **info, "orientation": fmt_src,
        "steps": {
            "transcribed": (WORK_DIR / f"{stem}.words.json").exists(),
            "prepped": (work / "aroll.mp4").exists(),
            "tracked": (work / "aroll.faces.json").exists(),
            "cutout": (work / "aroll.cutout.webm").exists(),
            "page": (ROOT / "studio" / stem / "index.html").exists(),
        },
        "brief": {"exists": bool(brief.get("exists")), "style": brief["style"],
                  "formats": brief["formats"], "variants": brief["variants"],
                  "error": brief.get("error")},
        "outputs": outputs_for(stem, project),
        "approved": (approve.approved(stem) or {}).get("file"),
    }


@router.get("/api/ping")
def ping():
    # вкладка студии опрашивает состояние раз в 3 с: если она открыта, вторую не открываем
    return {"app": "montazh-reels", "studio": True, "pid": os.getpid(),
            "tab_open": time.time() - seen["at"] < 12}


def project_view(p) -> dict:
    """Проект для студии: название и сколько обязательных вопросов анкеты без ответа (битая анкета — тоже)."""
    try:
        missing = len(projects.missing_setup(p))
    except projects.ProjectError:
        missing = 1
    return {"name": p.name, "title": p.title, "setup_missing": missing}


@router.get("/api/studio/state")
def studio_state():
    seen["at"] = time.time()
    # исходники всех проектов (скрытые — недописанные загрузки и «._имя» macOS — Project.sources
    # не отдаёт). Одно имя в двух проектах — ошибка на весь список: у них общий work/<имя>/
    try:
        inputs, problem = projects.sources(), None
    except projects.ProjectError as e:
        inputs, problem = [], str(e)
    queue = queue_state()
    if queue["pending"] and not queue["alive"]:
        # задачи мозг кладёт в очередь файлами; выполняет их студия — сама, без кнопки
        ensure_runner()
        queue = queue_state()
    return {"videos": [video_state(path, project) for project, path in inputs], "problem": problem,
            "projects": [project_view(p) for p in projects.all_projects()],
            "default_project": projects.DEFAULT, "queue": queue, "batch": batch_view(), "brain": brain_view(),
            "max_brains": MAX_BRAINS, "estimates": step_estimates(inputs),
            "formats": {k: dict(v, id=k) for k, v in formats.FORMATS.items()},
            "goals": styles.GOALS, "tiers": styles.TIERS}


# ---------------------------------------------------------------- сколько идут шаги

# Секунд на минуту исходника — замеры 14–16.10.2026 на эталонном Mac (IMG_1799, IMG_1816); как только
# очередь наберёт свои замеры на этой машине (work/_queue/timings.jsonl), берутся они. «page» — работа
# ИИ над планом и страницей, от длины ролика почти не зависит.
STEP_SCRIPTS = {"transcribed": "transcribe.py", "prepped": "prep.py", "tracked": "track.py",
                "cutout": "matte.py", "out": "render_reel.py"}
STEP_DEFAULTS = {"transcribed": 40, "prepped": 110, "tracked": 60, "cutout": 560, "out": 660}
PAGE_MINUTES = 12


def step_estimates(inputs: list) -> dict:
    """{шаг: секунд на минуту исходника, по скольким замерам}; page — минут целиком."""
    durations = {}
    for _, path in inputs:
        try:
            info = quick_probe(path)                 # из кэша: состояние студии его уже прогрело
        except OSError:
            continue
        if info.get("duration"):
            durations[path.stem] = info["duration"]
    samples = {k: [] for k in STEP_SCRIPTS}
    by_script = {v: k for k, v in STEP_SCRIPTS.items()}
    try:
        lines = jobqueue.TIMINGS.read_text(encoding="utf-8").splitlines()[-500:]
    except OSError:
        lines = []
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        step, dur = by_script.get(rec.get("script")), durations.get(rec.get("stem") or "")
        if step and dur and dur > 5:
            samples[step].append(rec["seconds"] / (dur / 60))
    out = {}
    for step, default in STEP_DEFAULTS.items():
        vals = sorted(samples[step])
        out[step] = {"per_min": round(vals[len(vals) // 2] if len(vals) >= 2 else default), "measured": len(vals)}
    out["page"] = {"minutes": PAGE_MINUTES}
    return out


# ---------------------------------------------------------------- стили и бриф

@router.get("/api/studio/styles")
def style_list(goals: str = "", bold: float = 0.3, format: str = ""):
    weights = dict(styles.DEFAULT_BRIEF["goals"])
    for pair in filter(None, goals.split(",")):
        key, _, value = pair.partition("=")
        if key in styles.GOALS:
            try:
                weights[key] = float(value)
            except ValueError:
                pass
    try:
        ranked = styles.recommend(weights, bold, format or None)
    except styles.StyleError as e:
        raise HTTPException(500, str(e))
    return {"styles": [dict(style, score=score) for score, style in ranked]}


@router.get("/api/studio/brief/{stem}")
def get_brief(stem: str):
    stem = safe_stem(stem)
    try:
        brief = styles.load_brief(stem)
    except styles.StyleError as e:
        # студия показывает ошибку и даёт пересохранить бриф с нуля
        return {"brief": dict(styles.DEFAULT_BRIEF), "text": f"Бриф с ошибкой: {e}", "error": str(e)}
    try:
        text = styles.director_brief(brief=brief)
    except styles.StyleError as e:
        text = f"Бриф с ошибкой: {e}"
    return {"brief": brief, "text": text}


@router.post("/api/studio/brief/{stem}")
def post_brief(stem: str, data: dict = Body(...)):
    stem = safe_stem(stem)
    if source_of(stem) is None and not (WORK_DIR / stem).exists():
        raise HTTPException(404, f"Ролика {stem} нет в input/ ни одного проекта")
    try:
        brief = styles.save_brief(stem, data)
        return {"ok": True, "brief": brief, "text": styles.director_brief(brief=brief)}
    except (styles.StyleError, ValueError) as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------- очередь

def ensure_runner() -> bool:
    """Будит обработчик очереди, если он не живёт. Второго он сам не допустит (замок)."""
    return jobqueue.wake(idle=1800)


def _tail(path: Path, lines: int = 6) -> list:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-lines:]
    except OSError:
        return []


def queue_state() -> dict:
    pending = [p.stem for p in jobqueue.job_files(QUEUE)]
    current = None
    if CURRENT.exists():
        try:
            current = json.loads(CURRENT.read_text(encoding="utf-8"))
            current["elapsed"] = round(time.time() - current["started"])
            current["log"] = _tail(QUEUE / "logs" / f"{current['job']}.log", 4)
        except (json.JSONDecodeError, KeyError, OSError):
            current = None
    def finished(sub: str) -> list:
        folder = QUEUE / sub
        if not folder.exists():
            return []
        items = sorted(jobqueue.job_files(folder), key=lambda p: -p.stat().st_mtime)[:8]
        return [{"job": p.stem, "at": p.stat().st_mtime,
                 "log": _tail(QUEUE / "logs" / f"{p.stem}.log", 3) if sub == "failed" else []}
                for p in items]
    if current:
        # идущая задача ещё лежит файлом в очереди — в «ждут» её не показываем
        pending = [job for job in pending if job != current.get("job")]
    return {"alive": runner_alive(), "pending": pending, "current": current,
            "done": finished("done"), "failed": finished("failed")}


def enqueue(name: str, steps: list, cleanup: list | None = None, title: str = "") -> str:
    """Задача очереди — JSON со списком шагов (jobqueue.write_job). Имя уникально: повтор не затирает живую."""
    try:
        path = jobqueue.write_job(name, steps, cleanup, title, queue=QUEUE)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    ensure_runner()
    return path.stem


@router.get("/api/studio/queue")
def get_queue():
    return queue_state()


@router.post("/api/studio/queue/wake")
def wake_queue():
    return {"started": ensure_runner(), **queue_state()}


@router.post("/api/studio/queue/cancel/{job}")
def cancel_job(job: str):
    if not re.fullmatch(r"[\w.\-]+", job, re.UNICODE):
        raise HTTPException(400, "плохое имя задачи")
    path = jobqueue.find_job(QUEUE, job)
    if path is None:
        raise HTTPException(404, "такой задачи в очереди нет (уже выполнена)")
    try:
        running = json.loads(CURRENT.read_text(encoding="utf-8")).get("job") if CURRENT.exists() else None
    except (json.JSONDecodeError, OSError):
        running = None
    if running == job:
        # файл идущей задачи нужен обработчику: после конца он переносит его в done/failed
        raise HTTPException(409, "эта задача уже выполняется — её не убрать из очереди")
    path.unlink()
    return queue_state()


@router.post("/api/studio/queue/stop")
def stop_job():
    """Остановить идущую задачу: её гасит обработчик со всеми процессами, задача падает, очередь идёт дальше."""
    current = queue_state().get("current")
    if not current:
        raise HTTPException(409, "сейчас ничего не выполняется")
    jobqueue.request_stop(current["job"], queue=QUEUE)
    return queue_state()


@router.get("/api/studio/log/{job}")
def job_log(job: str):
    if not re.fullmatch(r"[\w.\-]+", job, re.UNICODE):
        raise HTTPException(400, "плохое имя задачи")
    return {"job": job, "lines": _tail(QUEUE / "logs" / f"{job}.log", 200)}


@router.post("/api/studio/fast")
def fast_job(data: dict = Body(...)):
    """Быстрый монтаж в стиле: рез, субтитры, цвет — без графики. Через очередь."""
    stem = safe_stem(data.get("stem", ""))
    style_id = data.get("style") or "hormozi"
    fmt = data.get("format") or formats.DEFAULT
    try:
        styles.load_style(style_id)
        formats.get(fmt)
    except (styles.StyleError, ValueError) as e:
        raise HTTPException(400, str(e))
    source = source_of(stem)
    if not source:
        raise HTTPException(404, f"Нет исходника {stem} в input/ проектов")
    tag = fmt.replace(":", "x")
    name = f"30-fast-{stem}-{style_id}-{tag}-{int(time.time()) % 100000}"
    # шаг — список слов, а не строка оболочки: имя файла с пробелами или кавычками его не сломает
    steps = [["python", "scripts/reels.py", projects.rel(source), "--style", style_id, "--format", fmt]]
    return {"job": enqueue(name, steps, title=f"Быстрый монтаж {stem}: {style_id}, {fmt}"), **queue_state()}


# ---------------------------------------------------------------- дорожки и предпросмотр

@router.get("/api/studio/timeline/{stem}")
def timeline_get(stem: str):
    """Дорожки ролика для монтажной: рез, камера, субтитры, графика, звуки, эффекты."""
    import compose
    import timeline
    stem = safe_stem(stem)
    try:
        return timeline.tracks(stem)
    except (compose.SceneError, timeline.EditError) as e:
        raise HTTPException(409, str(e).lstrip("✗ "))


@router.post("/api/studio/timeline/{stem}")
def timeline_edit(stem: str, op: dict = Body(...)):
    """Одна правка руками. Пишется в work/<имя>/timeline.json, решения агента не трогает."""
    import compose
    import timeline
    stem = safe_stem(stem)
    try:
        timeline.apply_op(stem, op)
        return timeline.tracks(stem)
    except (compose.SceneError, timeline.EditError, KeyError, TypeError, ValueError) as e:
        raise HTTPException(400, str(e).lstrip("✗ ") or "правка не принята")


_thumb_lock = threading.Lock()


@router.get("/api/studio/thumb/{stem}")
def video_thumb(stem: str):
    """Кадр-миниатюра видео для списка: людям проще узнать ролик по картинке, чем по IMG_1801.

    Один ffmpeg за раз (замок): список из 30 видео не запускает 30 декодеров 4K разом (инвариант 2).
    Готовая миниатюра лежит в work/_thumbs/ и пересчитывается, только если исходник сменился.
    """
    from common import ffmpeg_bin
    stem = safe_stem(stem)
    src = source_of(stem)
    if not src:
        raise HTTPException(404, "нет исходника")
    folder = WORK_DIR / "_thumbs"
    folder.mkdir(parents=True, exist_ok=True)
    thumb = folder / f"{stem}.jpg"
    with _thumb_lock:
        if not thumb.exists() or thumb.stat().st_mtime < src.stat().st_mtime:
            tmp = folder / f".{stem}.jpg"
            out = subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-ss", "1.0", "-i", str(src), "-frames:v", "1",
                                  "-vf", "scale=-2:240", "-q:v", "5", str(tmp)], capture_output=True, timeout=60)
            if out.returncode != 0 or not tmp.exists():
                tmp.unlink(missing_ok=True)
                raise HTTPException(500, "миниатюру не сделать")
            tmp.replace(thumb)
    return FileResponse(thumb, media_type="image/jpeg", headers={"Cache-Control": "max-age=600"})


@router.get("/api/studio/peaks/{stem}")
def timeline_peaks(stem: str):
    import timeline
    try:
        return timeline.peaks(safe_stem(stem))
    except timeline.EditError as e:
        raise HTTPException(409, str(e))


PREVIEW_STUB = ('<script>window.__timelines = window.__timelines || {};'
                'window.addEventListener("error", (e) => parent.postMessage({ previewError: String(e.message) }, "*"));'
                '</script>')


@router.get("/api/studio/preview/{stem}/{path:path}")
def preview_file(stem: str, path: str):
    """Страница ролика для живого предпросмотра в монтажной — с текущими правками, без рендера.

    camera.js, captions.js и edits.js считаются на лету той же функцией, что и сборка
    (compose.scene): что видно здесь, то и уйдёт в ролик.
    """
    import compose
    import timeline
    from fastapi.responses import HTMLResponse, Response
    stem = safe_stem(stem)
    project = (ROOT / "studio" / stem).resolve()
    no_cache = {"Cache-Control": "no-store"}
    try:
        if path in ("index.html", "camera.js", "captions.js", "edits.js"):
            sc = compose.scene(stem)
            if path == "camera.js":
                return Response(sc["camera_js"], media_type="text/javascript", headers=no_cache)
            if path == "captions.js":
                return Response(sc["captions_js"], media_type="text/javascript", headers=no_cache)
            if path == "edits.js":
                return Response(timeline.edits_js(sc["edits"]), media_type="text/javascript", headers=no_cache)
            page = project / "index.html"
            if not page.exists():
                raise HTTPException(404, f"У {stem} ещё нет страницы графики — ролик не смонтирован")
            html = timeline.patch_page(page.read_text(encoding="utf-8"), sc["edits"], sc["fps"])
            html = html.replace("<head>", "<head>\n    " + PREVIEW_STUB, 1)
            return HTMLResponse(html, headers=no_cache)
    except (compose.SceneError, timeline.EditError) as e:
        raise HTTPException(409, str(e).lstrip("✗ "))
    if path == "layers.js":
        return FileResponse(timeline.LAYERS_JS, media_type="text/javascript", headers=no_cache)
    target = (project / path).resolve()
    if project not in target.parents or not target.is_file():
        raise HTTPException(404, "нет такого файла")
    return FileResponse(target)


@router.post("/api/studio/projects")
def create_project(data: dict = Body(...)):
    """Новый проект из монтажной: название по-русски, имя папки — латиницей (его даёт страница)."""
    title = str(data.get("title") or "").strip()[:60]
    name = str(data.get("name") or "").strip()
    if not title:
        raise HTTPException(400, "Назови проект")
    try:
        p = projects.create(name, title)
    except projects.ProjectError as e:
        raise HTTPException(409, str(e))
    return {"name": p.name, "title": p.title}


def _project(name: str):
    try:
        return projects.get(name)
    except projects.ProjectError as e:
        raise HTTPException(404, str(e))


@router.get("/api/studio/setup/{name}")
def get_setup(name: str):
    """Анкета проекта: вопросы, ответы, чего не хватает, файлы референсов."""
    p = _project(name)
    try:
        answers = projects.load_setup(p) or {}
    except projects.ProjectError as e:
        raise HTTPException(409, str(e))
    refs = sorted(x.name for x in p.references.iterdir() if x.is_file() and not x.name.startswith(".")) \
        if p.references.exists() else []
    return {"project": p.name, "title": p.title, "questions": projects.SETUP_QUESTIONS, "answers": answers,
            "missing": [q["id"] for q in projects.missing_setup(p)], "references": refs}


@router.post("/api/studio/setup/{name}")
def save_setup(name: str, data: dict = Body(...)):
    p = _project(name)
    answers = data.get("answers")
    if not isinstance(answers, dict):
        raise HTTPException(400, "answers — объект {вопрос: ответ}")
    try:
        left = projects.save_setup(p, answers)
    except projects.ProjectError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "missing": [q["id"] for q in left]}


@router.post("/api/studio/references/{name}")
async def add_reference(name: str, file: UploadFile = File(...)):
    """Референс в projects/<имя>/references/ — имя занято, ложится рядом с номером."""
    p = _project(name)
    first = p.references / materials.safe_name(file.filename or "reference")
    p.references.mkdir(parents=True, exist_ok=True)
    target, n = first, 2
    while target.exists():
        target = first.with_name(f"{first.stem}_{n}{first.suffix}")
        n += 1
    part = target.with_name(f".{target.name}.part")
    try:
        with open(part, "wb") as f:
            while chunk := await file.read(1 << 20):
                f.write(chunk)
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)
    return {"ok": True, "name": target.name}


@router.get("/api/studio/materials/{stem}")
def get_materials(stem: str):
    safe_stem(stem)
    return materials.listing(stem)


@router.post("/api/studio/materials/{stem}")
async def add_material(stem: str, file: UploadFile = File(...)):
    """Свой файл в материалы ролика (work/<имя>/materials/): фото, видео, звук."""
    safe_stem(stem)
    box = materials.folder(stem)
    box.mkdir(parents=True, exist_ok=True)
    tmp = box / f".upload-{time.time():.0f}.part"
    try:
        with open(tmp, "wb") as f:
            while chunk := await file.read(1 << 20):
                f.write(chunk)
        info = await asyncio.to_thread(materials.add, stem, file.filename or "material", tmp)
    except materials.MaterialError as e:
        raise HTTPException(400, str(e))
    finally:
        tmp.unlink(missing_ok=True)
    return info


@router.post("/api/studio/materials/{stem}/remove")
def remove_material(stem: str, data: dict = Body(...)):
    safe_stem(stem)
    try:
        materials.remove(stem, str(data.get("name") or ""))
    except materials.MaterialError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


@router.get("/api/studio/material/{stem}/{area}/{name}")
def material_file(stem: str, area: str, name: str):
    safe_stem(stem)
    try:
        return FileResponse(materials.file_path(stem, area, name))
    except materials.MaterialError as e:
        raise HTTPException(404, str(e))


@router.get("/api/studio/rules/{name}")
def get_rules(name: str):
    """Правила проекта (projects/<имя>/rules.md) — их читает агент до монтажа, правит человек или ИИ."""
    p = _project(name)
    mtime = p.rules.stat().st_mtime if p.rules.exists() else 0
    return {"project": p.name, "title": p.title, "path": f"projects/{p.name}/rules.md",
            "text": p.rules_text(), "mtime": mtime}


@router.post("/api/studio/rules/{name}")
def save_rules(name: str, data: dict = Body(...)):
    """Сохранить правила. Файл поменяли с тех пор, как его открыли (руками на компе или ИИ), —
    отказ, а не молчаливое затирание чужой правки."""
    p = _project(name)
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(400, "Правила пустые — не сохраняю. Удалить всё можно в самом файле")
    now = p.rules.stat().st_mtime if p.rules.exists() else 0
    if data.get("mtime") is not None and abs(float(data["mtime"]) - now) > 1e-6:
        raise HTTPException(409, "Правила поменялись, пока окно было открыто (на компе или ИИ). "
                                 "Нажми «Загрузить заново» — твой текст останется в буфере, если скопируешь")
    part = p.rules.with_name(".rules.md.part")
    try:
        part.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        part.replace(p.rules)
    finally:
        part.unlink(missing_ok=True)
    return get_rules(name)


@router.post("/api/studio/rules/{name}/open")
def open_rules(name: str):
    """Открыть rules.md в редакторе по умолчанию на компе."""
    p = _project(name)
    if not p.rules.exists():
        p.rules.write_text(projects.RULES_TEMPLATE.format(title=p.title), encoding="utf-8")
    host.open_file(p.rules)
    return {"ok": True}


def _busy(stem: str) -> bool:
    """Ролик сейчас собирается в очереди: его папку в studio/ трогать нельзя."""
    q = queue_state()
    cur = (q.get("current") or {}).get("job") or ""
    return stem in cur


@router.post("/api/studio/check/{stem}")
def check_before_export(stem: str):
    """Проверка перед экспортом: те же правила, что у рендера (verify_page), — за секунды, а не через
    10 минут упавшей сборки. Ответ — провалы с подробностями человеческим языком."""
    import contextlib
    import io
    import compose
    import verify_page
    stem = safe_stem(stem)
    if not (ROOT / "studio" / stem / "index.html").exists():
        raise HTTPException(409, f"У {stem} нет страницы графики — сначала ИИ-монтаж")
    if _busy(stem):
        raise HTTPException(409, f"{stem} сейчас собирается — дождись конца сборки")
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            compose.compose(stem)
            failed = verify_page.verify(stem)
    except SystemExit as e:
        return {"ok": False, "failed": [str(e.code or "сборка сцены не прошла")], "details": buf.getvalue()[-4000:]}
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        return {"ok": False, "failed": [str(e)], "details": buf.getvalue()[-4000:]}
    lines = buf.getvalue().splitlines()
    problems, cur = [], None
    for line in lines:
        if line.startswith("  ✗ "):
            cur = {"title": line[4:].strip(), "items": []}
            problems.append(cur)
        elif cur is not None and line.startswith("      "):
            cur["items"].append(line.strip())
        elif line.startswith("  ✓ ") or line.startswith("  · "):
            cur = None
    return {"ok": not failed, "failed": failed, "problems": problems}


@router.post("/api/studio/export/{stem}")
def export_job(stem: str):
    """Экспорт: ролик со всеми правками — следующей версией, через очередь."""
    import render_reel
    stem = safe_stem(stem)
    if not (ROOT / "studio" / stem / "index.html").exists():
        raise HTTPException(409, f"У {stem} нет страницы графики — сначала ИИ-монтаж")
    version = render_reel.next_version(stem)
    name = f"25-render-{stem}-{version}"
    steps = [["python", "scripts/render_reel.py", stem, "--version", version]]
    return {"job": enqueue(name, steps, title=f"Экспорт {stem} {version}"), "version": version, **queue_state()}


# ---------------------------------------------------------------- апрув

@router.get("/api/studio/approve/{stem}")
def approve_plan(stem: str, file: str):
    """Что останется и что можно удалить после апрува — ничего не трогает."""
    try:
        return approve.plan(safe_stem(stem), file)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/api/studio/approve/{stem}")
def approve_apply(stem: str, data: dict = Body(...)):
    """Апрув конечного варианта: запись в work/<имя>/approved.json и уборка отмеченных копий."""
    try:
        return approve.apply(safe_stem(stem), data.get("file", ""), list(data.get("remove") or []))
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------- файлы для просмотра

@router.get("/api/studio/file/{folder}/{name}")
def studio_file(folder: str, name: str):
    try:
        path = projects.locate(folder, name)
    except projects.ProjectError as e:
        raise HTTPException(404, str(e))
    media = {".jpg": "image/jpeg", ".png": "image/png"}.get(path.suffix.lower(), "video/mp4")
    return FileResponse(path, media_type=media)


@router.post("/api/studio/reveal")
def reveal(data: dict = Body(...)):
    folder, name = data.get("folder", "output"), data.get("name")
    if folder == "work":
        target = WORK_DIR / Path(name).name if name else WORK_DIR
    elif folder not in ("input", "output"):
        raise HTTPException(400, "нет такой папки")
    elif name:
        try:
            target = projects.locate(folder, name)
        except projects.ProjectError as e:
            raise HTTPException(404, str(e))
    else:
        try:
            target = getattr(projects.get(data.get("project") or projects.DEFAULT), folder)
        except projects.ProjectError as e:
            raise HTTPException(404, str(e))
    if target.exists():
        host.reveal(target)               # Finder на Mac, Проводник на Windows
    return {"ok": True}


# ---------------------------------------------------------------- мозг

_engines_seen: dict = {"at": 0.0, "data": None}


@router.get("/api/brain/engines")
def brain_engines(fresh: int = 0):
    """Какие мозги стоят, вошёл ли человек, на каком тарифе. Проверка стоит секунды — держим минуту."""
    if fresh or not _engines_seen["data"] or time.time() - _engines_seen["at"] > 60:
        data = brain.engines()
        for name, e in data.items():
            e.update(brain.auth_status(name, e["path"]) if e["available"] else {"logged_in": None})
            e["ready"] = bool(e["available"] and e.get("logged_in") is not False)
        _engines_seen.update(at=time.time(), data=data)
    return {"engines": _engines_seen["data"], "busy": [t for t, r in runs.items() if not r["done"]]}


@router.post("/api/brain/connect/{engine}")
def brain_connect(engine: str, data: dict = Body(...)):
    """Поставить или подключить мозг: открывает Терминал (PowerShell на Windows) с нужной командой.

    Вход у Claude и Codex — через браузер, по ссылке из терминала; пароль в студию не попадает.
    """
    if engine not in ("claude", "codex"):
        raise HTTPException(400, "мозг бывает claude или codex")
    action = data.get("action")
    try:
        cmd = brain.connect_command(engine, action)
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        host.open_terminal(cmd)
    except (OSError, subprocess.SubprocessError) as e:
        raise HTTPException(500, f"Не открылся терминал: {e}. Выполни сам: {cmd}")
    _engines_seen["at"] = 0.0
    return {"ok": True, "command": cmd}


def brain_view() -> list:
    """Идущие ходы мозга — для индикатора «ИИ монтирует» в студии: какой ролик, сколько идёт,
    что агент делает прямо сейчас (последнее действие, а если его ещё не было — «думает»)."""
    out = []
    for tid, run in list(runs.items()):
        if run["done"]:
            continue
        tool = next((e for e in reversed(run["events"]) if e.get("type") == "tool"), None)
        out.append({"thread": tid, "stem": run.get("stem"), "project": run.get("project"),
                    "elapsed": round(time.time() - run["started"]),
                    "doing": {"name": tool.get("name") or "", "summary": tool.get("summary") or ""} if tool else None,
                    "actions": sum(1 for e in run["events"] if e.get("type") == "tool"),
                    "inbox": brain.inbox_state(tid)})
    return out


@router.get("/api/brain/threads")
def brain_threads():
    return {"threads": brain.list_threads()}


@router.post("/api/brain/threads")
def brain_new_thread(data: dict = Body(...)):
    engine = data.get("engine", "claude")
    if engine not in ("claude", "codex"):
        raise HTTPException(400, "мозг бывает claude или codex")
    stem, project = data.get("stem"), data.get("project")
    if stem:
        safe_stem(stem)
    if project:
        try:
            projects.get(project)
        except projects.ProjectError as e:
            raise HTTPException(404, str(e))
    return brain.new_thread(engine, data.get("title", ""), stem, project if not stem else None)


@router.get("/api/brain/threads/{thread_id}")
def brain_thread(thread_id: str):
    try:
        thread = brain.load_thread(thread_id)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(404, str(e))
    run = runs.get(thread_id)
    thread["running"] = bool(run and not run["done"])
    brain.fill_turn_costs(thread["messages"])
    return thread


def studio_context(stem: str | None, project_name: str | None = None) -> str:
    """Что мозгу знать о выбранном ролике (или о проекте — разговор о правилах): файлы, этапы и бриф."""
    if not stem and project_name:
        try:
            project = projects.get(project_name)
        except projects.ProjectError as e:
            return f"Проект {project_name}: {e}"
        left = projects.missing_setup(project)
        return (f"Разговор о проекте {project.name} — «{project.title}», не о ролике: ролики не монтируй и не трогай. "
                f"Правила — projects/{project.name}/rules.md, анкета — projects/{project.name}/setup.json (блок «Анкета "
                f"проекта» в rules.md пишет студия по анкете — его не правь, дописывай правила ниже), референсы — "
                f"projects/{project.name}/references/. "
                + (f"Анкета не заполнена: {', '.join(q['q'] for q in left)}." if left else "Анкета заполнена."))
    if not stem:
        return ("Ролик не выбран: работай с тем, о чём просит человек. Проекты: " +
                ", ".join(f"{p.name} ({p.title})" for p in projects.all_projects()) +
                f"; по умолчанию — {projects.DEFAULT}.")
    try:
        path, project = projects.source(stem), projects.of(stem)
    except projects.ProjectError as e:
        path, project = None, None
        lines = [f"Ролик {stem}: {e}"]
    if project:
        lines = [f"Выбран ролик {stem} ({projects.rel(path) if path else 'исходника нет'}), "
                 f"проект {project.name} — «{project.title}». Эта сессия — только про него: другие ролики "
                 f"монтируются в своих сессиях, не трогай их.",
                 f"Правила проекта — projects/{project.name}/rules.md: прочитай до плана, они важнее стиля. "
                 f"Язык речи {project.config['language']}, финальная плашка CTA "
                 f"{'нужна' if project.config['cta'] else 'НЕ нужна (build_page(cta=False))'}; "
                 f"выпуски — projects/{project.name}/output/."]
    mats = materials.context_line(stem)
    if mats:
        lines.append(mats)
    if path:
        state = video_state(path, project)
        done = [k for k, v in state["steps"].items() if v]
        lines.append(f"Готовые этапы: {', '.join(done) or 'ничего'}. Выпуски: "
                     f"{', '.join(o['name'] for o in state['outputs'][:6]) or 'нет'}.")
        if state["approved"]:
            lines.append(f"Апрув: {state['approved']} — это конечный вариант; новые версии — только по просьбе.")
    try:
        lines.append("Бриф:\n" + styles.director_brief(stem))
    except styles.StyleError as e:
        lines.append(f"Бриф с ошибкой: {e}")
    return "\n".join(lines)


async def _run_turn(thread: dict, text: str, mode: str, model: str | None, finish: bool = True):
    """Один ход мозга. Что бы ни случилось внутри, ход заканчивается (done) и с понятной ошибкой.

    Раньше исключение посреди хода (новый формат события у агента, сбой записи диалога)
    оставляло ход «работающим» навсегда: каждая следующая реплика получала «мозг уже
    работает», пока сервер студии не перезапустят, а в чате — ни слова о причине.

    Агент читается в отдельном потоке обычным Popen, а не через asyncio: на Windows
    подпроцессы asyncio работают не в каждом цикле событий, а поток работает везде.
    """
    run = runs[thread["id"]]
    engine = thread["engine"]
    reply = {"role": "assistant", "engine": engine, "at": time.time(), "events": []}
    thread["messages"].append(reply)
    run["reply"] = reply                             # дописанное человеком по ходу ложится в этот ответ
    proc = None

    def add(ev: dict):
        ev["at"] = time.time()
        run["events"].append(ev)
        reply["events"].append(ev)

    def read_agent():
        """В потоке: события агента по строкам, пока он не закончит."""
        for raw in iter(proc.stdout.readline, b""):
            try:
                events = brain.parse_line(engine, raw.decode("utf-8", "replace"))
            except Exception as e:                  # одно странное событие не роняет ход
                events = [{"type": "note", "text": f"Не разобрал событие {engine}: {type(e).__name__}: {e}"}]
            for ev in events:
                if ev["type"] == "session" and ev.get("id"):
                    thread["session"] = ev["id"]
                if ev["type"] == "result" and ev.get("session"):
                    thread["session"] = ev["session"]
                if ev["type"] == "result":
                    ev["turn"] = brain.turn_cost(thread["messages"][:-1], ev)   # без текущего ответа
                add(ev)
                if ev["type"] in ("text", "result", "error"):
                    brain.save_thread(thread)
        return proc.wait()

    try:
        try:
            cmd = brain.command(engine, text, thread.get("session"), mode, model,
                                context=studio_context(thread.get("stem"), thread.get("project")),
                                thread_id=thread["id"])
        except (RuntimeError, ValueError) as e:
            add({"type": "error", "text": str(e)})
            return
        try:
            proc = subprocess.Popen(cmd, cwd=ROOT, env=brain.child_env(thread["id"]), stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, **host.own_group())
        except OSError as e:
            add({"type": "error", "text": f"Не запустился {engine}: {e}"})
            return
        run["proc"] = proc
        stderr = []
        drain = threading.Thread(target=lambda: stderr.append(proc.stderr.read()), daemon=True)
        drain.start()
        code = await asyncio.to_thread(read_agent)
        await asyncio.to_thread(drain.join, 10)
        run["stderr"] = b"".join(stderr).decode("utf-8", "replace")[-4000:]
        if code != 0 and not any(e["type"] in ("result", "error") for e in run["events"]):
            tail = (run.get("stderr") or "").strip().splitlines()[-6:]
            msg = brain.explain_error(" ".join(tail)) if tail else f"код {code}"
            if run.get("stopped"):
                msg = "Остановлено по кнопке."
            add({"type": "error", "text": f"{engine} завершился с ошибкой: {msg}"})
    except Exception as e:
        add({"type": "error", "text": f"Ход мозга прерван ошибкой студии: {type(e).__name__}: {e}"})
        if proc is not None and proc.poll() is None:
            host.kill_tree(proc.pid)                 # агент без читателя повис бы на полном канале
    finally:
        if finish:
            run["done"] = True
        try:
            brain.save_thread(thread)
        except OSError:
            pass


# Сколько ИИ работает разом: каждый агент — свой процесс на сотни мегабайт и свои запросы к лимиту
# подписки. Тяжёлое при этом всё равно идёт через одну очередь (common.require_queue).
MAX_BRAINS = 4


def running_threads() -> list:
    return [t for t, r in runs.items() if not r["done"]]


def batch_active_stems() -> set:
    if not batch["running"]:
        return set()
    return {i["stem"] for i in batch["items"] if i["status"] in ("queued", "working", "waiting_queue")}


def setup_gate(stem: str | None, project_name: str | None = None) -> str | None:
    """Текст отказа, если проект ролика не настроен (анкета без обязательных ответов), иначе None."""
    try:
        project = projects.of(stem) if stem else (projects.get(project_name) if project_name else None)
    except projects.ProjectError:
        return None
    if project is None or not stem:
        return None
    left = projects.missing_setup(project)
    if not left:
        return None
    return (f"Проект «{project.title}» не настроен: ИИ не знает — {', '.join(q['q'].lower() for q in left)}. "
            f"Ответь на анкету (меню «Проект → Настроить проект»), и монтаж пойдёт по твоим правилам")


def take_inbox_prompt(thread: dict) -> str | None:
    """Недоставленное хуком — в следующий ход: «пока ты работал, человек дописал…»."""
    extra = brain.inbox_take(thread["id"])
    if not extra:
        return None
    thread["messages"].append({"role": "user", "text": "\n".join(extra), "at": time.time(), "inbox": True})
    brain.save_thread(thread)
    return ("Пока ты работал, человек дописал:\n" + "\n".join(f"— {t}" for t in extra)
            + "\nУчти это: доделай или переделай нужное и скажи, что поменял.")


async def _chat_turns(thread: dict, text: str, mode: str, model: str | None):
    """Ход из чата и, если человек дописал по ходу, а агент этого не получил, — продолжение с дописанным."""
    run = runs[thread["id"]]
    try:
        for _ in range(5):
            await _run_turn(thread, text, mode, model, finish=False)
            reply = thread["messages"][-1] if thread["messages"] else {}
            if run.get("stopped") or any(e["type"] == "error" for e in reply.get("events", [])):
                break
            text = take_inbox_prompt(thread)
            if not text:
                break
    finally:
        run["done"] = True


@router.post("/api/brain/send")
async def brain_send(data: dict = Body(...)):
    thread_id = data.get("thread", "")
    text = (data.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "пустое сообщение")
    try:
        thread = brain.load_thread(thread_id)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(404, str(e))
    busy = running_threads()
    if thread_id in busy:
        raise HTTPException(409, "ИИ ещё работает в этом разговоре — допиши через «Добавить к монтажу»: "
                                 "он получит это по ходу")
    if len(busy) >= MAX_BRAINS:
        raise HTTPException(409, f"Уже работают {len(busy)} ИИ — больше {MAX_BRAINS} разом не запускаю "
                                 "(память и лимиты подписки). Дождись, пока один закончит")
    stem = data.get("stem") or None
    if stem and stem in batch_active_stems():
        raise HTTPException(409, f"{stem} сейчас монтирует пачка — дождись её или останови пачку")
    if stem:
        safe_stem(stem)
        if thread.get("stem") and thread["stem"] != stem:
            # Один ролик — одна сессия агента. Контекст у сессии конечный: монтаж второго ролика
            # в сессии первого идёт на обрывках чужого контекста и выходит хуже (правило Валеры).
            raise HTTPException(409, f"Этот разговор — про {thread['stem']}. Для {stem} начни новый: "
                                     "у каждого ролика своя сессия мозга")
        if not thread.get("stem") and thread["messages"]:
            raise HTTPException(409, f"Этот разговор начат без ролика. Для {stem} начни новый: "
                                     "у каждого ролика своя сессия мозга")
        thread["stem"] = stem
    gate = setup_gate(stem)
    if gate:
        raise HTTPException(409, gate)
    # Свежая сессия ролика: разговор разросся — продолжаем новым, с передачей дел (Валера, 16.10.2026)
    prompt, fresh = text, None
    if stem and thread.get("stem") == stem:
        fresh = brain.needs_fresh(thread)
        if fresh:
            old = thread
            thread = brain.new_thread(old["engine"], f"{stem}: продолжение", stem)
            thread["fresh_of"] = old["id"]
            prompt = brain.handoff(old) + "\n\nНовая просьба человека:\n" + text
    if thread["title"] == "Новый разговор":
        thread["title"] = text[:60]
    thread["messages"].append({"role": "user", "text": text, "at": time.time()})
    brain.save_thread(thread)
    runs[thread["id"]] = {"events": [], "done": False, "started": time.time(), "stem": thread.get("stem"),
                          "project": thread.get("project")}
    mode = data.get("mode", "safe")
    model = (data.get("model") or "").strip() or None
    asyncio.create_task(_chat_turns(thread, prompt, mode, model))
    return {"ok": True, "thread": thread["id"], "fresh": fresh}


@router.post("/api/brain/inbox/{thread_id}")
def brain_inbox(thread_id: str, data: dict = Body(...)):
    """Дописать к идущему ходу: Claude получит после ближайшего действия (хук), Codex — следующим ходом."""
    text = (data.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "пустое сообщение")
    run = runs.get(thread_id)
    if not run or run["done"]:
        raise HTTPException(409, "ИИ уже закончил — отправь обычным сообщением")
    try:
        thread = brain.load_thread(thread_id)
        msg_id = brain.inbox_add(thread_id, text)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(404, str(e))
    ev = {"type": "inbox", "id": msg_id, "text": text, "at": time.time()}
    run["events"].append(ev)
    if run.get("reply") is not None:
        run["reply"]["events"].append(ev)
    when = ("после ближайшего действия" if thread["engine"] == "claude"
            else "как закончит текущий шаг — Codex не умеет получать сообщения посреди хода")
    return {"ok": True, "id": msg_id, "when": when}


@router.post("/api/brain/stop/{thread_id}")
def brain_stop(thread_id: str):
    run = runs.get(thread_id)
    if not run or run["done"] or not run.get("proc"):
        return {"ok": False, "error": "нечего останавливать"}
    run["stopped"] = True
    host.kill_tree(run["proc"].pid)                  # агент и всё, что он запустил
    return {"ok": True}


@router.get("/api/brain/stream/{thread_id}")
async def brain_stream(thread_id: str, request: Request, since: int = 0):
    """События текущего хода, каждое со своим номером (id:).

    Переподключаясь (сон ноутбука, обрыв), браузер сам присылает Last-Event-ID — поток
    продолжается с места. Раньше он начинался с нуля, и в чате задваивались действия и ответы.
    """
    last = request.headers.get("last-event-id", "")
    if last.isdigit():
        since = int(last) + 1

    async def events():
        sent = max(0, since)
        idle = 0
        while True:
            run = runs.get(thread_id)
            if not run:
                yield f"data: {json.dumps({'type': 'idle'})}\n\n"
                return
            while sent < len(run["events"]):
                ev = dict(run["events"][sent], index=sent)
                yield f"id: {sent}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
                sent += 1
            if run["done"]:
                yield f"data: {json.dumps({'type': 'done', 'index': sent})}\n\n"
                return
            idle += 1
            if idle % 40 == 0:
                yield ": живой\n\n"                     # держим соединение
            await asyncio.sleep(0.25)
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- пачка: каждый ролик — своя сессия

# Ролики пачки монтируются по одному, и у каждого — своя, новая сессия мозга: контекст у
# сессии конечный, и монтаж пятого ролика в разговоре, где уже были четыре, выходит хуже
# (правило Валеры, 11.10.2026). Между ходами студия ждёт очередь и сама продолжает разговор,
# когда тяжёлые задачи отработали. Конец ролика мозг отмечает строкой «СТАТУС: …».
BATCH_TURNS = 12
BATCH_FIRST = """Смонтируй {stem} по брифу (work/{stem}/brief.json; нет брифа — умолчания проекта из project.json).
Ролик из проекта {project}: прочитай projects/{project}/rules.md до плана — правила проекта важнее стиля.
Сначала план: scripts/plan.py {stem} → заполни work/{stem}/plan.md (инструменты — docs/АРСЕНАЛ.md) →
plan.py {stem} --check, и только потом страница; без годного плана рендер не пойдёт.
Это пачка: человек не отвечает по ходу — решай сам, каждое решение с откатом в отчёт.
Тяжёлое — в очередь (scripts/jobqueue.py add …), в имени задачи — имя ролика: 20-prep-{stem}, 05-render-{stem}.
Когда очередь отработает, студия сама напишет тебе сюда. Рядом в своих сессиях монтируются другие ролики:
трогай только work/{stem}/ и studio/{stem}/, общие файлы (scripts/, presets/, правила) не меняй.
В конце КАЖДОГО ответа — одна строка:
  СТАТУС: ГОТОВО — ролик в projects/{project}/output/ и прошёл verify_render;
  СТАТУС: ЖДУ ОЧЕРЕДЬ — поставил задачи, продолжу после них;
  СТАТУС: НУЖЕН ЧЕЛОВЕК — <что решить> — если без человека дальше нельзя (сорванный дубль и т.п.)."""
batch: dict = {"running": False, "items": [], "engine": None, "mode": "safe", "stop": False, "started": None,
               "parallel": 1}


def batch_view() -> dict:
    return {k: batch.get(k) for k in ("running", "items", "engine", "mode", "started", "parallel")}


def batch_save() -> None:
    path = WORK_DIR / "_studio" / "batch.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(batch_view(), ensure_ascii=False, indent=1), encoding="utf-8")


def all_jobs() -> dict:
    """Все задачи очереди по имени: queued / done / failed."""
    found = {p.stem: "queued" for p in jobqueue.job_files(QUEUE)}
    for state in ("done", "failed"):
        found.update({p.stem: state for p in jobqueue.job_files(QUEUE / state)})
    return found


def status_of(reply: dict) -> tuple:
    """(статус, пояснение) из последней строки «СТАТУС: …» в ответе мозга."""
    text = "\n".join(e.get("text", "") for e in reply.get("events", []) if e["type"] == "text")
    found = re.findall(r"СТАТУС:\s*(ГОТОВО|ЖДУ ОЧЕРЕДЬ|НУЖЕН ЧЕЛОВЕК)\s*[—–-]?\s*(.*)", text)
    return found[-1] if found else ("", "")


async def batch_turn(thread: dict, text: str) -> dict:
    """Один ход мозга внутри пачки — тот же, что из чата, только ждём его здесь."""
    thread["messages"].append({"role": "user", "text": text, "at": time.time(), "auto": True})
    brain.save_thread(thread)
    runs[thread["id"]] = {"events": [], "done": False, "started": time.time(), "stem": thread.get("stem")}
    await _run_turn(thread, text, batch["mode"], None)
    return thread["messages"][-1]


async def batch_item(item: dict) -> None:
    """Один ролик пачки: своя сессия, ходы до «СТАТУС», ожидание своих задач очереди."""
    stem = item["stem"]
    try:
        project = projects.of(stem).name
    except projects.ProjectError as e:
        item.update(status="failed", note=str(e)[:300])
        batch_save()
        return
    gate = setup_gate(stem)
    if gate:
        item.update(status="needs_human", note=gate[:300])
        batch_save()
        return
    thread = brain.new_thread(batch["engine"], f"{stem}: пачка", stem)
    item.update(thread=thread["id"], status="working", note="")
    batch_save()
    text = BATCH_FIRST.format(stem=stem, project=project)
    for turn in range(BATCH_TURNS):
        before = all_jobs()
        reply = await batch_turn(thread, text)
        if batch["stop"]:
            item.update(status="skipped", note="пачку остановили посреди ролика")
            return
        errors = [e["text"] for e in reply.get("events", []) if e["type"] == "error"]
        status, why = status_of(reply)
        if errors:
            item.update(status="failed", note=errors[-1][:300])
            if any(w in errors[-1] for w in ("Лимит", "не авторизован", "не найден")):
                batch["stop"] = True           # с этим мозгом дальше не пойдёт ни один ролик
            return
        if status == "ГОТОВО":
            item.update(status="done", note=why[:300])
            return
        if status == "НУЖЕН ЧЕЛОВЕК":
            item.update(status="needs_human", note=why[:300])
            return
        # задачи этого ролика — по имени: рядом идут другие ролики, и «всё новое в очереди» уже не его
        mine = [j for j in all_jobs() if j not in before and stem in j]
        if mine:
            item.update(status="waiting_queue", note=", ".join(mine)[:300])
            batch_save()
            while not batch["stop"] and any(all_jobs().get(j) == "queued" for j in mine):
                ensure_runner()
                await asyncio.sleep(5)
            if batch["stop"]:
                item.update(status="skipped", note="пачку остановили, пока шла очередь")
                return
            result = all_jobs()
            lines = []
            for job in mine:
                state = result.get(job, "?")
                tail = " | ".join(_tail(QUEUE / "logs" / f"{job}.log", 3)) if state == "failed" else ""
                lines.append(f"{job}: {'✓ готово' if state == 'done' else '✗ упала — ' + tail}")
            text = ("Очередь отработала:\n" + "\n".join(lines) +
                    f"\nПродолжай монтаж {stem}. В конце — строка СТАТУС.")
        elif status == "ЖДУ ОЧЕРЕДЬ":
            text = (f"Новых задач с именем {stem} в очереди нет — проверь work/_queue/ (и failed/) и продолжай. "
                    "В имени задачи должно быть имя ролика. В конце — строка СТАТУС.")
        else:
            text = f"Продолжай монтаж {stem}. Если ролик готов и проверен — «СТАТУС: ГОТОВО»."
        extra = take_inbox_prompt(thread)
        if extra:
            text = extra + "\n\n" + text
        fresh = brain.needs_fresh(thread)
        if fresh:
            # ролик пачки тоже может разрастись — продолжаем свежей сессией с передачей дел
            old = thread
            thread = brain.new_thread(batch["engine"], f"{stem}: пачка, продолжение", stem)
            thread["fresh_of"] = old["id"]
            text = brain.handoff(old) + "\n\n" + BATCH_FIRST.format(stem=stem, project=project) + "\n\nСейчас: " + text
            item.update(thread=thread["id"])
        item.update(status="working")
        batch_save()
    item.update(status="failed", note=f"не уложился в {BATCH_TURNS} ходов")


async def run_batch() -> None:
    """Пачка: каждый ролик — своя сессия; batch["parallel"] роликов разом, тяжёлое — одной очередью."""
    slots = asyncio.Semaphore(max(1, batch.get("parallel") or 1))

    async def one(item: dict) -> None:
        async with slots:
            if batch["stop"]:
                item.update(status="skipped", note="пачку остановили")
                return
            await batch_item(item)
            batch_save()

    try:
        await asyncio.gather(*(one(item) for item in batch["items"]))
    except Exception as e:
        for item in batch["items"]:
            if item["status"] in ("queued", "working", "waiting_queue"):
                item.update(status="failed", note=f"пачка прервана ошибкой студии: {type(e).__name__}: {e}"[:300])
    finally:
        batch["running"] = False
        batch_save()


def new_videos() -> list:
    """Ролики без выпусков и без апрува — кандидаты в пачку."""
    found = []
    try:
        index = projects.index()
    except projects.ProjectError:
        return []                       # одно имя в двух проектах: студия уже показывает ошибку
    for stem, (project, _) in sorted(index.items()):
        if not outputs_for(stem, project) and not approve.approved(stem):
            found.append(stem)
    return found


@router.get("/api/brain/batch")
def batch_state():
    return {**batch_view(), "new": new_videos()}


@router.post("/api/brain/batch")
async def batch_start(data: dict = Body(...)):
    """Пачка роликов: по одному, каждый в своей новой сессии мозга."""
    if batch["running"]:
        raise HTTPException(409, "Пачка уже идёт")
    engine = data.get("engine", "claude")
    if engine not in ("claude", "codex"):
        raise HTTPException(400, "мозг бывает claude или codex")
    stems = [safe_stem(s) for s in (data.get("stems") or new_videos())]
    if not stems:
        raise HTTPException(400, "Новых роликов нет: у всех есть выпуски")
    talking = {runs[t].get("stem") for t in running_threads()}
    clash = [s for s in stems if s in talking]
    if clash:
        raise HTTPException(409, f"С {', '.join(clash)} сейчас работает ИИ в чате — дождись или убери из пачки")
    try:
        parallel = max(1, min(MAX_BRAINS, int(data.get("parallel", 1))))
    except (TypeError, ValueError):
        raise HTTPException(400, "parallel — число роликов разом, от 1 до %d" % MAX_BRAINS)
    batch.update(running=True, stop=False, engine=engine, mode=data.get("mode", "safe"), parallel=parallel,
                 started=time.time(), items=[{"stem": s, "status": "queued", "thread": None, "note": ""} for s in stems])
    batch_save()
    asyncio.create_task(run_batch())
    return batch_view()


@router.post("/api/brain/batch/stop")
def batch_stop():
    """Остановить пачку: текущий ход мозга гасится, следующие ролики не начинаются."""
    batch["stop"] = True
    for run in runs.values():
        if not run["done"] and run.get("proc"):
            run["stopped"] = True
            host.kill_tree(run["proc"].pid)
    return batch_view()
