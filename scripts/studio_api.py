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
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import brain
import formats
import styles
from common import INPUT_DIR, OUTPUT_DIR, ROOT, VENV_PY, WORK_DIR, ffprobe_bin
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


def quick_probe(path: Path) -> dict:
    """Размер и длительность; кэш по времени изменения — студия опрашивает часто."""
    key = (str(path), path.stat().st_mtime)
    if key in _probe_cache:
        return _probe_cache[key]
    out = subprocess.run([ffprobe_bin(), "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=width,height:stream_side_data=rotation:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True)
    info = {"width": None, "height": None, "duration": None}
    try:
        data = json.loads(out.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
        w, h = stream.get("width"), stream.get("height")
        rotation = 0
        for entry in stream.get("side_data_list") or []:
            rotation = int(entry.get("rotation", 0) or 0)
        if rotation in (90, -90, 270, -270):
            w, h = h, w
        info = {"width": w, "height": h,
                "duration": round(float((data.get("format") or {}).get("duration", 0)), 1)}
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    _probe_cache[key] = info
    return info


def outputs_for(stem: str) -> list:
    items = []
    for path in OUTPUT_DIR.glob(f"{stem}*"):
        if path.suffix.lower() not in VIDEO_EXT:
            continue
        rest = path.stem[len(stem):]
        if rest and rest[0] not in "_-":
            continue                      # IMG_32790 не принадлежит IMG_3279
        sheet = path.with_suffix(".sheet.jpg")
        items.append({"name": path.name, "mtime": path.stat().st_mtime,
                      "size_mb": round(path.stat().st_size / 1_048_576, 1),
                      "sheet": sheet.name if sheet.exists() else None})
    return sorted(items, key=lambda i: -i["mtime"])


def video_state(path: Path) -> dict:
    stem = path.stem
    work = WORK_DIR / stem
    brief = styles.load_brief(stem)
    info = quick_probe(path)
    fmt_src = None
    if info["width"] and info["height"]:
        fmt_src = "горизонталь" if info["width"] > info["height"] else (
            "квадрат" if info["width"] == info["height"] else "вертикаль")
    return {
        "stem": stem, "name": path.name, "mtime": path.stat().st_mtime,
        "size_mb": round(path.stat().st_size / 1_048_576, 1), **info, "orientation": fmt_src,
        "steps": {
            "transcribed": (WORK_DIR / f"{stem}.words.json").exists(),
            "prepped": (work / "aroll.mp4").exists(),
            "tracked": (work / "aroll.faces.json").exists(),
            "cutout": (work / "aroll.cutout.webm").exists(),
            "page": (ROOT / "studio" / stem / "index.html").exists(),
        },
        "brief": {"exists": bool(brief.get("exists")), "style": brief["style"],
                  "formats": brief["formats"], "variants": brief["variants"]},
        "outputs": outputs_for(stem),
    }


@router.get("/api/ping")
def ping():
    # вкладка студии опрашивает состояние раз в 3 с: если она открыта, вторую не открываем
    return {"app": "montazh-reels", "studio": True, "pid": os.getpid(),
            "tab_open": time.time() - seen["at"] < 12}


@router.get("/api/studio/state")
def studio_state():
    seen["at"] = time.time()
    inputs = sorted((p for p in INPUT_DIR.glob("*") if p.suffix.lower() in VIDEO_EXT),
                    key=lambda p: -p.stat().st_mtime)
    return {"videos": [video_state(p) for p in inputs], "queue": queue_state(),
            "formats": {k: dict(v, id=k) for k, v in formats.FORMATS.items()},
            "goals": styles.GOALS, "tiers": styles.TIERS}


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
    brief = styles.load_brief(stem)
    try:
        text = styles.director_brief(brief=brief)
    except styles.StyleError as e:
        text = f"Бриф с ошибкой: {e}"
    return {"brief": brief, "text": text}


@router.post("/api/studio/brief/{stem}")
def post_brief(stem: str, data: dict = Body(...)):
    stem = safe_stem(stem)
    if not any((INPUT_DIR / f"{stem}{ext}").exists() for ext in (".MOV", ".mov", ".mp4", ".MP4", ".m4v", ".mkv")) \
            and not (WORK_DIR / stem).exists():
        raise HTTPException(404, f"Ролика {stem} нет в input/")
    try:
        brief = styles.save_brief(stem, data)
        return {"ok": True, "brief": brief, "text": styles.director_brief(brief=brief)}
    except (styles.StyleError, ValueError) as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------- очередь

def ensure_runner() -> bool:
    """Будит обработчик очереди, если он не живёт. Второго он сам не допустит (замок)."""
    if runner_alive():
        return False
    QUEUE.mkdir(parents=True, exist_ok=True)
    log = open(QUEUE / "runner.out", "a", encoding="utf-8")
    subprocess.Popen([str(VENV_PY), "-u", "scripts/jobqueue.py", "--idle", "1800"], cwd=ROOT,
                     stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     start_new_session=True)
    return True


def _tail(path: Path, lines: int = 6) -> list:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-lines:]
    except OSError:
        return []


def queue_state() -> dict:
    pending = sorted(p.stem for p in QUEUE.glob("*.sh")) if QUEUE.exists() else []
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
        items = sorted(folder.glob("*.sh"), key=lambda p: -p.stat().st_mtime)[:8]
        return [{"job": p.stem, "at": p.stat().st_mtime,
                 "log": _tail(QUEUE / "logs" / f"{p.stem}.log", 3) if sub == "failed" else []}
                for p in items]
    if current:
        # идущая задача ещё лежит файлом в очереди — в «ждут» её не показываем
        pending = [job for job in pending if job != current.get("job")]
    return {"alive": runner_alive(), "pending": pending, "current": current,
            "done": finished("done"), "failed": finished("failed")}


def enqueue(name: str, command: str) -> str:
    """Задача очереди — файл с одной командой. Имя уникально: повтор не затирает живую."""
    if not re.fullmatch(r"\d\d-[\w.\-]+", name, re.UNICODE):
        raise HTTPException(400, f"Плохое имя задачи: {name}")
    QUEUE.mkdir(parents=True, exist_ok=True)
    path = QUEUE / f"{name}.sh"
    if path.exists():
        raise HTTPException(409, f"Задача {name} уже в очереди")
    path.write_text(f"set -e\n{command}\n", encoding="utf-8")
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
    path = QUEUE / f"{job}.sh"
    if not path.exists():
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
    source = next((p for p in INPUT_DIR.glob(f"{stem}.*") if p.suffix.lower() in VIDEO_EXT), None)
    if not source:
        raise HTTPException(404, f"Нет исходника {stem} в input/")
    tag = fmt.replace(":", "x")
    name = f"30-fast-{stem}-{style_id}-{tag}-{int(time.time()) % 100000}"
    # имя файла — в кавычки оболочки как есть: задача очереди — это скрипт bash
    cmd = (f".venv/bin/python scripts/reels.py {shlex.quote('input/' + source.name)} "
           f"--style {shlex.quote(style_id)} --format {shlex.quote(fmt)}")
    return {"job": enqueue(name, cmd), **queue_state()}


# ---------------------------------------------------------------- файлы для просмотра

@router.get("/api/studio/file/{folder}/{name}")
def studio_file(folder: str, name: str):
    base = {"output": OUTPUT_DIR, "input": INPUT_DIR}.get(folder)
    if base is None:
        raise HTTPException(404, "нет такой папки")
    path = base / Path(name).name
    if not path.exists():
        raise HTTPException(404, "нет файла")
    media = {".jpg": "image/jpeg", ".png": "image/png"}.get(path.suffix.lower(), "video/mp4")
    return FileResponse(path, media_type=media)


@router.post("/api/studio/reveal")
def reveal(data: dict = Body(...)):
    folder = {"output": OUTPUT_DIR, "input": INPUT_DIR, "work": WORK_DIR}.get(data.get("folder", "output"))
    if folder is None:
        raise HTTPException(400, "нет такой папки")
    target = folder / Path(data.get("name", "")).name if data.get("name") else folder
    if target.is_file():
        subprocess.run(["open", "-R", str(target)])       # показать файл в Finder
    elif target.exists():
        subprocess.run(["open", str(target)])
    return {"ok": True}


# ---------------------------------------------------------------- мозг

@router.get("/api/brain/engines")
def brain_engines():
    return {"engines": brain.engines(), "busy": [t for t, r in runs.items() if not r["done"]]}


@router.get("/api/brain/threads")
def brain_threads():
    return {"threads": brain.list_threads()}


@router.post("/api/brain/threads")
def brain_new_thread(data: dict = Body(...)):
    engine = data.get("engine", "claude")
    if engine not in ("claude", "codex"):
        raise HTTPException(400, "мозг бывает claude или codex")
    stem = data.get("stem")
    if stem:
        safe_stem(stem)
    return brain.new_thread(engine, data.get("title", ""), stem)


@router.get("/api/brain/threads/{thread_id}")
def brain_thread(thread_id: str):
    try:
        thread = brain.load_thread(thread_id)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(404, str(e))
    run = runs.get(thread_id)
    thread["running"] = bool(run and not run["done"])
    return thread


def studio_context(stem: str | None) -> str:
    """Что мозгу знать о выбранном ролике: файлы, этапы и бриф."""
    if not stem:
        return "Ролик не выбран: работай с тем, о чём просит человек (по умолчанию — новые из input/)."
    path = next((p for p in INPUT_DIR.glob(f"{stem}.*") if p.suffix.lower() in VIDEO_EXT), None)
    lines = [f"Выбран ролик {stem} ({path.name if path else 'исходника в input/ нет'})."]
    if path:
        state = video_state(path)
        done = [k for k, v in state["steps"].items() if v]
        lines.append(f"Готовые этапы: {', '.join(done) or 'ничего'}. Выпуски: "
                     f"{', '.join(o['name'] for o in state['outputs'][:6]) or 'нет'}.")
    try:
        lines.append("Бриф:\n" + styles.director_brief(stem))
    except styles.StyleError as e:
        lines.append(f"Бриф с ошибкой: {e}")
    return "\n".join(lines)


async def _run_turn(thread: dict, text: str, mode: str, model: str | None):
    run = runs[thread["id"]]
    engine = thread["engine"]
    try:
        cmd = brain.command(engine, text, thread.get("session"), mode, model,
                            context=studio_context(thread.get("stem")))
    except (RuntimeError, ValueError) as e:
        run["events"].append({"type": "error", "text": str(e)})
        run["done"] = True
        return
    reply = {"role": "assistant", "engine": engine, "at": time.time(), "events": []}
    thread["messages"].append(reply)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=ROOT, env=brain.child_env(), stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            limit=16 * 1024 * 1024, start_new_session=True)
    except OSError as e:
        run["events"].append({"type": "error", "text": f"Не запустился {engine}: {e}"})
        run["done"] = True
        return
    run["proc"] = proc

    async def drain_stderr():
        data = await proc.stderr.read()
        run["stderr"] = data.decode("utf-8", "replace")[-4000:]
    err_task = asyncio.create_task(drain_stderr())

    while True:
        raw = await proc.stdout.readline()
        if not raw:
            break
        for ev in brain.parse_line(engine, raw.decode("utf-8", "replace")):
            if ev["type"] == "session" and ev.get("id"):
                thread["session"] = ev["id"]
            if ev["type"] == "result" and ev.get("session"):
                thread["session"] = ev["session"]
            ev["at"] = time.time()
            run["events"].append(ev)
            reply["events"].append(ev)
            if ev["type"] in ("text", "result", "error"):
                brain.save_thread(thread)
    code = await proc.wait()
    await err_task
    if code != 0 and not any(e["type"] in ("result", "error") for e in run["events"]):
        tail = (run.get("stderr") or "").strip().splitlines()[-6:]
        msg = brain.explain_error(" ".join(tail)) if tail else f"код {code}"
        if run.get("stopped"):
            msg = "Остановлено по кнопке."
        ev = {"type": "error", "text": f"{engine} завершился с ошибкой: {msg}", "at": time.time()}
        run["events"].append(ev)
        reply["events"].append(ev)
    run["done"] = True
    brain.save_thread(thread)


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
    busy = [t for t, r in runs.items() if not r["done"]]
    if busy:
        # один мозг за раз: два агента наперегонки запустят два тяжёлых процесса
        raise HTTPException(409, "Мозг уже работает над другим запросом — дождись или останови его")
    if data.get("stem") is not None:
        thread["stem"] = data.get("stem") or None
    if thread["title"] == "Новый разговор":
        thread["title"] = text[:60]
    thread["messages"].append({"role": "user", "text": text, "at": time.time()})
    brain.save_thread(thread)
    runs[thread["id"]] = {"events": [], "done": False, "started": time.time()}
    mode = data.get("mode", "safe")
    model = (data.get("model") or "").strip() or None
    asyncio.create_task(_run_turn(thread, text, mode, model))
    return {"ok": True, "thread": thread["id"]}


@router.post("/api/brain/stop/{thread_id}")
def brain_stop(thread_id: str):
    run = runs.get(thread_id)
    if not run or run["done"] or not run.get("proc"):
        return {"ok": False, "error": "нечего останавливать"}
    run["stopped"] = True
    try:
        os.killpg(run["proc"].pid, signal.SIGTERM)       # агент и всё, что он запустил
    except (ProcessLookupError, PermissionError):
        pass
    return {"ok": True}


@router.get("/api/brain/stream/{thread_id}")
async def brain_stream(thread_id: str, since: int = 0):
    """События текущего хода; переподключение с since продолжает с места."""
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
                sent += 1
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            if run["done"]:
                yield f"data: {json.dumps({'type': 'done', 'index': sent})}\n\n"
                return
            idle += 1
            if idle % 40 == 0:
                yield ": живой\n\n"                     # держим соединение
            await asyncio.sleep(0.25)
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
