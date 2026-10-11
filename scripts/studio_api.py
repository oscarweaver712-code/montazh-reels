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

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import approve
import brain
import formats
import host
import jobqueue
import styles
from common import INPUT_DIR, OUTPUT_DIR, ROOT, WORK_DIR, ffprobe_bin
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
                          "-of", "json", str(path)], capture_output=True, encoding="utf-8", errors="replace")
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
    final = (approve.approved(stem) or {}).get("file")
    for path in OUTPUT_DIR.glob(f"{stem}*"):
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


def video_state(path: Path) -> dict:
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
        "outputs": outputs_for(stem),
        "approved": (approve.approved(stem) or {}).get("file"),
    }


@router.get("/api/ping")
def ping():
    # вкладка студии опрашивает состояние раз в 3 с: если она открыта, вторую не открываем
    return {"app": "montazh-reels", "studio": True, "pid": os.getpid(),
            "tab_open": time.time() - seen["at"] < 12}


@router.get("/api/studio/state")
def studio_state():
    seen["at"] = time.time()
    # скрытые — недописанные загрузки и служебные «._имя» macOS на внешних дисках
    inputs = sorted((p for p in INPUT_DIR.glob("*") if p.suffix.lower() in VIDEO_EXT
                     and not p.name.startswith(".")), key=lambda p: -p.stat().st_mtime)
    queue = queue_state()
    if queue["pending"] and not queue["alive"]:
        # задачи мозг кладёт в очередь файлами; выполняет их студия — сама, без кнопки
        ensure_runner()
        queue = queue_state()
    return {"videos": [video_state(p) for p in inputs], "queue": queue, "batch": batch_view(),
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
    # шаг — список слов, а не строка оболочки: имя файла с пробелами или кавычками его не сломает
    steps = [["python", "scripts/reels.py", f"input/{source.name}", "--style", style_id, "--format", fmt]]
    return {"job": enqueue(name, steps, title=f"Быстрый монтаж {stem}: {style_id}, {fmt}"), **queue_state()}


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
    if target.exists():
        host.reveal(target)               # Finder на Mac, Проводник на Windows
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
    lines = [f"Выбран ролик {stem} ({path.name if path else 'исходника в input/ нет'}). Эта сессия — только "
             f"про него: другие ролики монтируются в своих сессиях, не трогай их."]
    if path:
        state = video_state(path)
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


async def _run_turn(thread: dict, text: str, mode: str, model: str | None):
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
                add(ev)
                if ev["type"] in ("text", "result", "error"):
                    brain.save_thread(thread)
        return proc.wait()

    try:
        try:
            cmd = brain.command(engine, text, thread.get("session"), mode, model,
                                context=studio_context(thread.get("stem")))
        except (RuntimeError, ValueError) as e:
            add({"type": "error", "text": str(e)})
            return
        try:
            proc = subprocess.Popen(cmd, cwd=ROOT, env=brain.child_env(), stdin=subprocess.DEVNULL,
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
        run["done"] = True
        try:
            brain.save_thread(thread)
        except OSError:
            pass


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
    if batch["running"]:
        raise HTTPException(409, "Идёт пачка: мозг занят роликами по очереди — дождись или останови пачку")
    stem = data.get("stem") or None
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
BATCH_FIRST = """Смонтируй {stem} по брифу (work/{stem}/brief.json; нет брифа — по умолчанию, вирусный 9:16).
Это пачка: человек не отвечает по ходу — решай сам, каждое решение с откатом в отчёт.
Тяжёлое — в очередь (scripts/jobqueue.py add …): когда очередь отработает, студия сама напишет тебе сюда.
В конце КАЖДОГО ответа — одна строка:
  СТАТУС: ГОТОВО — ролик в output/ и прошёл verify_render;
  СТАТУС: ЖДУ ОЧЕРЕДЬ — поставил задачи, продолжу после них;
  СТАТУС: НУЖЕН ЧЕЛОВЕК — <что решить> — если без человека дальше нельзя (сорванный дубль и т.п.)."""
batch: dict = {"running": False, "items": [], "engine": None, "mode": "safe", "stop": False, "started": None}


def batch_view() -> dict:
    return {k: batch[k] for k in ("running", "items", "engine", "mode", "started")}


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
    runs[thread["id"]] = {"events": [], "done": False, "started": time.time()}
    await _run_turn(thread, text, batch["mode"], None)
    return thread["messages"][-1]


async def run_batch() -> None:
    try:
        for item in batch["items"]:
            if batch["stop"]:
                item.update(status="skipped", note="пачку остановили")
                continue
            stem = item["stem"]
            thread = brain.new_thread(batch["engine"], f"{stem}: пачка", stem)
            item.update(thread=thread["id"], status="working", note="")
            batch_save()
            text = BATCH_FIRST.format(stem=stem)
            for turn in range(BATCH_TURNS):
                before = all_jobs()
                reply = await batch_turn(thread, text)
                errors = [e["text"] for e in reply.get("events", []) if e["type"] == "error"]
                status, why = status_of(reply)
                if errors:
                    item.update(status="failed", note=errors[-1][:300])
                    if any(w in errors[-1] for w in ("Лимит", "не авторизован", "не найден")):
                        batch["stop"] = True           # с этим мозгом дальше не пойдёт ни один ролик
                    break
                if status == "ГОТОВО":
                    item.update(status="done", note=why[:300])
                    break
                if status == "НУЖЕН ЧЕЛОВЕК":
                    item.update(status="needs_human", note=why[:300])
                    break
                # задачи, появившиеся за этот ход, — его (мозг в студии один, второго хода нет)
                mine = [j for j in all_jobs() if j not in before]
                if mine:
                    item.update(status="waiting_queue", note=", ".join(mine)[:300])
                    batch_save()
                    while not batch["stop"] and any(all_jobs().get(j) == "queued" for j in mine):
                        ensure_runner()
                        await asyncio.sleep(5)
                    if batch["stop"]:
                        item.update(status="skipped", note="пачку остановили, пока шла очередь")
                        break
                    result = all_jobs()
                    lines = []
                    for job in mine:
                        state = result.get(job, "?")
                        tail = " | ".join(_tail(QUEUE / "logs" / f"{job}.log", 3)) if state == "failed" else ""
                        lines.append(f"{job}: {'✓ готово' if state == 'done' else '✗ упала — ' + tail}")
                    text = ("Очередь отработала:\n" + "\n".join(lines) +
                            f"\nПродолжай монтаж {stem}. В конце — строка СТАТУС.")
                elif status == "ЖДУ ОЧЕРЕДЬ":
                    text = ("Новых задач в очереди от тебя нет — проверь work/_queue/ (и failed/) и продолжай. "
                            "В конце — строка СТАТУС.")
                else:
                    text = f"Продолжай монтаж {stem}. Если ролик готов и проверен — «СТАТУС: ГОТОВО»."
                item.update(status="working")
                batch_save()
            else:
                item.update(status="failed", note=f"не уложился в {BATCH_TURNS} ходов")
            batch_save()
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
    for path in sorted(INPUT_DIR.glob("*")):
        if path.suffix.lower() in VIDEO_EXT and not path.name.startswith("."):
            if not outputs_for(path.stem) and not approve.approved(path.stem):
                found.append(path.stem)
    return found


@router.get("/api/brain/batch")
def batch_state():
    return {**batch_view(), "new": new_videos()}


@router.post("/api/brain/batch")
async def batch_start(data: dict = Body(...)):
    """Пачка роликов: по одному, каждый в своей новой сессии мозга."""
    if batch["running"]:
        raise HTTPException(409, "Пачка уже идёт")
    if [t for t, r in runs.items() if not r["done"]]:
        raise HTTPException(409, "Мозг сейчас занят разговором — дождись или останови его")
    engine = data.get("engine", "claude")
    if engine not in ("claude", "codex"):
        raise HTTPException(400, "мозг бывает claude или codex")
    stems = [safe_stem(s) for s in (data.get("stems") or new_videos())]
    if not stems:
        raise HTTPException(400, "Новых роликов нет: у всех есть выпуски")
    batch.update(running=True, stop=False, engine=engine, mode=data.get("mode", "safe"),
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
