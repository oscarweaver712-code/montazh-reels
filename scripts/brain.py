#!/usr/bin/env python3
"""Мозг студии: GPT через Codex CLI, запущенный из веб-студии.

Студия (web/studio.html) отправляет реплику — сервер запускает
`codex exec` в папке проекта, читает поток событий (JSONL) и показывает их в чате.
Диалог продолжается той же сессией агента (exec resume), поэтому мозг
помнит, о чём шла речь, а правила проекта (AGENTS.md, скилл reels) он читает сам.

Здесь только логика без сервера: какие команды, как разбирать события, где лежат
диалоги. Тяжёлое мозг не запускает сам — кладёт задачи в очередь (jobqueue.py), и
очередь выполняет их по одной: так пока считается ролик, ноутбуком можно пользоваться.

Режимы доступа:
  safe — правка файлов и скрипты проекта: песочница workspace-write с сетью. Не защита от злого умысла, а страховка от
         случайного «rm -rf»: мозг может переписать скрипт и запустить его.
  full — без ограничений (bypass sandbox).
"""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import host
import gpt_client
from common import ROOT, WORK_DIR

THREADS = WORK_DIR / "_studio" / "threads"
CHILD_ENV = "REELS_STUDIO_CHILD"      # хук автозапуска студии не срабатывает в агентах студии

PY = ".venv/Scripts/python.exe" if host.IS_WINDOWS else ".venv/bin/python"

STUDIO_PROMPT = f"""Тебя вызывают из локальной студии монтажа (web/studio.html): человек видит твои
ответы в чате студии, терминала он не видит. Работай по AGENTS.md и скиллу reels
(.agents/skills/reels/SKILL.md). Один разговор — один ролик: другие ролики монтируются
в своих сессиях, их не трогай.
— Отвечай по-русски, коротко и по делу. В конце: что сделано, где файл, как откатить.
— Питон проекта здесь: {PY}.
— Тяжёлое (transcribe, prep, track, matte, reframe, render_reel, reels.py) не запускай сам:
  клади в очередь — {PY} scripts/jobqueue.py add <NN>-<имя> "python scripts/prep.py projects/<проект>/input/X.MOV"
  ["следующий шаг" …] (порядок по номеру: 05-render, 10-transcribe, 20-prep, 30-fast).
  Очередь выполняет студия сама, по одной. Ход: work/_queue/logs/, готовое — done/, упавшее — failed/.
— Ролик принадлежит проекту (projects/<проект>/: input/, output/, rules.md, project.json, references/);
  чей он — {PY} scripts/projects.py where <имя>. Правила проекта (rules.md) важнее стиля, и правила
  одного проекта в другой не переносятся. Новый проект — {PY} scripts/projects.py new <имя>.
  Папка input/<имя>/ с несколькими видео — СБОРКА: один ролик из кусков разных клипов (scripts/pack.py:
  разбор → pack.json → --build → обычный конвейер). Референсы проекта (references/) — на все его ролики.
— Бриф ролика (стиль, формат, цели, варианты) — work/<имя>/brief.json, текст для тебя:
  {PY} scripts/styles.py --brief <имя>. Каталог стилей: presets/styles/.
— Вопрос задавай, только если без ответа дальше нельзя; иначе выбирай разумно и пиши, что выбрал.
— Рядом в своих сессиях могут монтироваться другие ролики: трогай только work/<свой ролик>/ и
  studio/<свой ролик>/; общие файлы (scripts/, presets/, правила проекта) — только по прямой просьбе.
  В имени задачи очереди — имя ролика (20-prep-IMG_3317): по нему студия понимает, чья задача.
— Человек может дописать просьбы посреди хода: студия соберёт их в один следующий запрос. Исправляй весь список
  вместе, сохраняй удачную идею и ручные правки timeline.json; механические правки делай скриптами без нового ИИ.
— Приёмы рилса @tenfoldmarc (оглавление, чек-лист, телефон, интерфейс, стена, орбита, рамка, вертиго,
  пролёт, отъезд, рост, сцена, коллаж, каракули, обложка, стекло) — scripts/fx.py, когда к месту —
  docs/ПРИЁМЫ-17.md. Ставь по плану и к смыслу, не ради набора: не больше двух крупных приёмов на мысль.
— Если в этом запуске доступны инструменты Computer Use, используй Chrome человека: монтаж из студии должен быть не хуже монтажа из терминала. ИИ-футаж (Google Flow / Omni) делай
  сам по скиллу flow (.agents/skills/flow/SKILL.md), бонусы — в пределах budget из footage.json; лоу-фай — из
  фонотеки YouTube (rules.md проекта, scripts/music.py add). Приём клипа (footage.py --take) — через очередь.
  Инструментов браузера нет или он не отвечает — не подменяй видео картинкой молча: напиши человеку, чего не хватает, до рендера.
— Ждать задачу очереди — только {PY} scripts/jobqueue.py wait <задача>, не своим циклом по логу.
— Дизайн и готовые движения — DESIGN.md проекта, scripts/design.py, score.py и montage.py. Выбирай готовые
  приёмы, их содержание и тайминги; свои сцены пиши только там, где они усиливают новую идею этого ролика.
— Порядок инструментов проекта — его rules.md (у antishkola п.18: всегда → часто → иногда → редко); субтитры не
  на лице и текст за головой виден — проверяет verify_page, рендер не пойдёт.
"""


# ---------------------------------------------------------------- движки

# Где обычно живут CLI агентов, если PATH урезан (сервер, поднятый из Finder или хука)
EXTRA_BIN = (["~/.local/bin", "~/AppData/Roaming/npm"] if host.IS_WINDOWS else
             ["~/.local/bin", "/opt/homebrew/bin", "/usr/local/bin", "~/.npm-global/bin"])


def require_engine(name: str) -> None:
    if name != "codex":
        raise ValueError("Монтаж переведён на GPT: выбери codex; Claude больше не запускается")


def find_binary(name: str) -> str | None:
    """CLI агента: PATH сервера бывает урезан (запуск из Finder), поэтому смотрим и в типичные места."""
    found = shutil.which(name)
    if found:
        return found
    for folder in EXTRA_BIN:
        found = shutil.which(name, path=str(Path(folder).expanduser()))   # на Windows — с .exe/.cmd
        if found:
            return found
    return None


def engines() -> dict:
    """Какие мозги есть на машине и их версии."""
    out = {}
    for name in ("codex",):
        path = find_binary(name)
        version = None
        if path:
            try:
                version = subprocess.run([path, "--version"], capture_output=True, encoding="utf-8", errors="replace",
                                         timeout=15).stdout.strip().splitlines()[0]
            except (subprocess.TimeoutExpired, OSError, IndexError):
                version = None
        out[name] = {"available": bool(path), "path": path, "version": version}
    return out


def auth_status(name: str, path: str) -> dict:
    """Вход Codex, без запроса к модели. Не удалось проверить — logged_in None."""
    require_engine(name)
    try:
        out = subprocess.run([path, "login", "status"], capture_output=True, encoding="utf-8", errors="replace",
                             timeout=20, env=clean_env(), stdin=subprocess.DEVNULL)
        text = f"{out.stdout} {out.stderr}"
        ok = out.returncode == 0 and "not logged" not in text.lower()
        plan = "ChatGPT" if "ChatGPT" in text else ("API-ключ" if "API key" in text else None)
        return {"logged_in": ok, "plan": plan if ok else None}
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        return {"logged_in": None}


def connect_command(engine: str, action: str) -> str:
    """Команда для терминала: поставить мозг (официальный способ) или войти в него через браузер."""
    require_engine(engine)
    path = find_binary(engine)
    quoted = (f'& "{path}"' if host.IS_WINDOWS else f'"{path}"') if path else engine
    if action == "install":
        return "npm install -g @openai/codex"          # npm есть: на Node работает HyperFrames
    if action == "login":
        if not path:
            raise ValueError(f"{engine} ещё не установлен — сначала «Установить»")
        return f"{quoted} login"
    raise ValueError("действие — install или login")


# Переменные сессии агента, в которой подняли сервер студии (хук старта, терминал агента).
# Сервер живёт дольше этой сессии, и без чистки каждый ход мозга и каждая задача очереди
# получали чужие номер сессии, сокет и ключ для сообщений, «я дочерняя сессия» и даже её
# уровень усилий. Настройки пользователя (вход, прокси, CLAUDE_CODE_USE_BEDROCK…) не трогаем.
SESSION_VARS = {
    "CLAUDECODE", "CLAUDE_PID", "CLAUDE_EFFORT", "CLAUDE_PROJECT_DIR", "CLAUDE_ENV_FILE",
    "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_EXECPATH", "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_BRIDGE_SESSION_ID", "CLAUDE_CODE_SSE_PORT",
    "CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_THREAD_ID",
}


def clean_env() -> dict:
    """Окружение без следов сессии агента, которая случайно оказалась родителем сервера."""
    return {k: v for k, v in os.environ.items() if k not in SESSION_VARS}


def child_env(thread_id: str | None = None) -> dict:
    env = host.utf8_env(clean_env())
    env[CHILD_ENV] = "1"
    if thread_id:
        env["REELS_THREAD"] = thread_id       # идентификатор разговора для скриптов студии
    # из Finder PATH короткий — без него агент не найдёт ffmpeg, node и npx
    extra = [str(Path(folder).expanduser()) for folder in EXTRA_BIN]
    env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "")])
    return env


def command(engine: str, prompt: str, session: str | None = None, mode: str = "safe",
            model: str | None = None, context: str = "", thread_id: str | None = None) -> list:
    """Режиссёр GPT; продолжение — только сессией того же ролика."""
    require_engine(engine)
    binary = find_binary(engine)
    if not binary:
        raise RuntimeError("Codex не найден — установи его в студии → «Подключить GPT» и войди в ChatGPT")
    text = prompt if session else f"{STUDIO_PROMPT}\n{context}\n\nЗапрос:\n{prompt}".strip()
    return gpt_client.command(binary, text, session=session, mode=mode, model=model)


# ---------------------------------------------------------------- разбор событий

def _short(value, limit: int = 160) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _tool_summary(name: str, data: dict) -> str:
    if name == "Bash":
        return _short(data.get("command", ""))
    for key in ("file_path", "path", "pattern", "url", "query", "description"):
        if data.get(key):
            return _short(str(data[key]))
    return _short(data)


def _codex_name(item: dict) -> str:
    kind = item.get("type")
    if kind == "command_execution":
        return "Bash"
    if kind == "mcp_tool_call":
        return f"{item.get('server', 'mcp')}.{item.get('tool', '?')}"
    return {"file_change": "Правка", "web_search": "Поиск"}.get(kind, kind or "действие")


def _codex_summary(item: dict) -> str:
    kind = item.get("type")
    if kind == "command_execution":
        return _short(item.get("command", ""))
    if kind == "file_change":
        return _short(", ".join(c.get("path", "?") for c in item.get("changes") or []))
    if kind == "web_search":
        return _short(item.get("query", ""))
    if kind == "mcp_tool_call":
        return _short(item.get("arguments", ""))
    return _short({k: v for k, v in item.items() if k not in ("id", "type", "status")})


def parse_line(engine: str, line: str) -> list:
    """Строка JSONL агента → события чата: text, tool, tool_done, session, result, error."""
    line = line.strip()
    if not line.startswith("{"):
        return []
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        return []
    kind = ev.get("type")
    out = []

    if engine == "codex":
        item = ev.get("item") or {}
        itype = item.get("type")
        quiet = ("agent_message", "reasoning", "error", "todo_list", None)
        if kind == "thread.started":
            out.append({"type": "session", "id": ev.get("thread_id")})
        elif kind == "item.started" and itype not in quiet:
            out.append({"type": "tool", "id": item.get("id"), "name": _codex_name(item),
                        "summary": _codex_summary(item)})
        elif kind == "item.completed":
            if itype == "agent_message" and item.get("text", "").strip():
                out.append({"type": "text", "text": item["text"]})
            elif itype == "error":
                message = item.get("message", "")
                # служебный шум Codex (метаданные модели, ужатые описания скиллов) в чат не несём
                if "metadata" not in message and "Skill descriptions" not in message:
                    out.append({"type": "note", "text": message})
            elif itype not in quiet:
                if itype in ("file_change", "web_search"):
                    # у этих нет события старта — показываем действие сразу
                    out.append({"type": "tool", "id": item.get("id"), "name": _codex_name(item),
                                "summary": _codex_summary(item)})
                failed = (item.get("status") in ("failed", "declined") or bool(item.get("error"))
                          or (item.get("exit_code") not in (None, 0)))
                output = item.get("aggregated_output") or item.get("error") or item.get("result") or ""
                out.append({"type": "tool_done", "id": item.get("id"), "error": failed,
                            "output": _short(output, 300)})
        elif kind == "turn.completed":
            out.append({"type": "result", "ok": True, "text": "", "usage": ev.get("usage"),
                        "context": context_size(ev.get("usage")), "cost": None})
        elif kind in ("turn.failed", "error"):
            message = (ev.get("error") or {}).get("message") if kind == "turn.failed" else ev.get("message")
            out.append({"type": "error", "text": explain_error(message or "")})
        return out
    return out


def context_size(usage: dict | None) -> int | None:
    """Входные токены хода Codex, включая закэшированные (их повторно не прибавляем)."""
    if not isinstance(usage, dict) or usage.get("input_tokens") is None:
        return None
    try:
        return int(usage["input_tokens"])
    except (TypeError, ValueError):
        return None


def explain_error(message: str) -> str:
    """Ошибки агента — человеческим языком, с тем, что делать."""
    try:
        inner = json.loads(message)
        message = ((inner.get("error") or {}).get("message")) or message
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    low = message.lower()
    # лимит — первым: у Claude в нём есть «/upgrade», и раньше это читалось как «Codex устарел»
    # 15.10.2026: «You've hit your session limit · resets 6:20am» не узнавался — пачка пробежала по всем роликам
    if "rate limit" in low or "usage limit" in low or "session limit" in low or "429" in low:
        return f"Лимит подписки исчерпан — дождись сброса лимита ChatGPT. ({message})"
    if "newer version of codex" in low or ("codex" in low and "upgrade" in low):
        return f"Codex устарел для выбранной модели — обнови Codex: `npm install -g @openai/codex`. ({message})"
    if "unexpected argument" in low or "unknown option" in low:
        return f"Codex не понимает опции запуска — обнови CLI: `npm install -g @openai/codex`. ({message})"
    if ("not logged in" in low or "login" in low or "unauthorized" in low or "401" in low
            or "failed to authenticate" in low or "403" in low):
        return f"Мозг не авторизован — открой терминал и войди (codex login). ({message})"
    return message


# ---------------------------------------------------------------- диалоги

def _thread_path(thread_id: str) -> Path:
    if not thread_id or not all(c.isalnum() or c == "-" for c in thread_id):
        raise ValueError("плохой номер диалога")
    return THREADS / f"{thread_id}.json"


def new_thread(engine: str, title: str = "", stem: str | None = None, project: str | None = None) -> dict:
    require_engine(engine)
    THREADS.mkdir(parents=True, exist_ok=True)
    thread = {"id": uuid.uuid4().hex[:12], "engine": engine, "title": title or "Новый разговор",
              "stem": stem, "project": project, "session": None, "created": time.time(), "updated": time.time(),
              "messages": []}
    save_thread(thread)
    return thread


def load_thread(thread_id: str) -> dict:
    path = _thread_path(thread_id)
    if not path.exists():
        raise FileNotFoundError(f"Диалога {thread_id} нет")
    thread = json.loads(path.read_text(encoding="utf-8"))
    if thread.get("engine") == "claude":
        # История нужна человеку; идентификатор сессии другого поставщика Codex не понимает.
        thread["handoff"] = handoff(thread, why="монтаж переведён с Claude на GPT/Codex")
        thread.update(engine="codex", session=None, legacy_engine="claude")
        save_thread(thread)
    return thread


def save_thread(thread: dict) -> None:
    THREADS.mkdir(parents=True, exist_ok=True)
    thread["updated"] = time.time()
    path = _thread_path(thread["id"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(thread, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def turn_cost(messages: list, result: dict) -> float | None:
    """Цена хода по итогу Claude: разница с прошлым итогом той же сессии в разговоре.

    total_cost_usd у Claude Code — нарастающий итог сессии, а не цена хода (у IMG_1803 итоги ходов
    0,36 → 0,71 → … → 3,90). Студия показывала его под каждым ходом как цену хода, и сумма по ходам
    выходила $13,41 вместо $3,90. Новая сессия (номер сменился) считается с нуля.
    """
    total = result.get("cost")
    if total is None:
        return None
    for message in reversed(messages):
        prev = next((e for e in message.get("events") or [] if e.get("type") == "result"), None)
        if prev is None or prev.get("cost") is None:
            continue
        if prev.get("session") == result.get("session") and prev["cost"] <= total:
            return round(total - prev["cost"], 4)
        return total
    return total


def fill_turn_costs(messages: list) -> None:
    """Цена хода — итогам, у которых её нет (разговоры, сохранённые до 13.10.2026)."""
    for i, message in enumerate(messages):
        for ev in message.get("events") or []:
            if ev.get("type") == "result" and "turn" not in ev:
                ev["turn"] = turn_cost(messages[:i], ev)


# ---------------------------------------------------------------- свежая сессия ролика

# Сессия одного ролика тоже растёт: пятнадцать заходов «поправь то, поправь это» — и монтаж
# деградирует так же, как в пачке в одном разговоре (Валера, 16.10.2026: «свежая сессия автоматом»).
# Порог — входные токены хода Codex и число просьб человека. Состояние ролика живёт в
# файлах work/<имя>/, поэтому свежей сессии хватает короткой передачи дел.
FRESH_CONTEXT = 120_000
FRESH_REQUESTS = 8


def needs_fresh(thread: dict) -> str | None:
    """Почему разговор пора продолжить свежей сессией, или None."""
    if not thread.get("session"):
        return None
    msgs = thread.get("messages") or []
    for m in reversed(msgs):
        res = next((e for e in m.get("events") or [] if e.get("type") == "result"), None)
        if res and res.get("context"):
            if res["context"] >= FRESH_CONTEXT:
                return f"последний ход использовал ≈{res['context'] // 1000} тыс. входных токенов"
            break
    asks = sum(1 for m in msgs if m.get("role") == "user" and not m.get("auto"))   # ходы пачки «продолжай» — не просьбы
    if asks >= FRESH_REQUESTS:
        return f"в разговоре уже {asks} просьб"
    return None


def _final_text(message: dict, limit: int) -> str:
    texts = [e.get("text", "") for e in message.get("events") or [] if e.get("type") == "text" and e.get("text")]
    text = " ".join((texts[-1] if texts else "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def handoff(thread: dict, keep: int = 6, why: str = "прошлая разрослась, и монтаж в ней стал бы хуже") -> str:
    """Передача дел свежей сессии: последние просьбы человека и итоги ответов. Подробности — в файлах."""
    msgs = thread.get("messages") or []
    pairs = []
    for i, m in enumerate(msgs):
        if m.get("role") != "user":
            continue
        reply = msgs[i + 1] if i + 1 < len(msgs) and msgs[i + 1].get("role") == "assistant" else {}
        ask = " ".join(m.get("text", "").split())
        pairs.append(f"— просьба: {ask[:400]}" + (f"\n  итог: {_final_text(reply, 500)}" if _final_text(reply, 500) else ""))
    stem = thread.get("stem")
    where = (f"Состояние ролика — в файлах work/{stem}/ (plan.md, edit.json, director.json, page.py, timeline.json — "
             f"ручные правки человека, их не затирать). Читай их, а не полагайся на этот пересказ.") if stem else \
        "Состояние — в файлах проекта; читай их, а не полагайся на этот пересказ."
    return (f"Это продолжение работы в свежей сессии: {why}.\n"
            f"Что было в прошлой сессии ({len(pairs)} просьб, последние {min(keep, len(pairs))}):\n"
            + "\n".join(pairs[-keep:]) + "\n" + where)


# ---------------------------------------------------------------- дописанное по ходу

INBOX = WORK_DIR / "_studio" / "inbox"


def inbox_add(thread_id: str, text: str) -> str:
    """Просьба человека к идущему ходу: файл для общего списка следующего хода."""
    _thread_path(thread_id)                          # проверка номера
    box = INBOX / thread_id
    box.mkdir(parents=True, exist_ok=True)
    msg_id = f"{time.time():.6f}".replace(".", "")
    tmp = box / f"{msg_id}.part"
    tmp.write_text(json.dumps({"text": text, "at": time.time()}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(box / f"{msg_id}.json")
    return msg_id


def inbox_state(thread_id: str) -> dict:
    """{id: доставлено ли} по дописанному в этот разговор."""
    box = INBOX / thread_id
    if not box.exists():
        return {}
    return {p.stem: p.suffix == ".done" for p in sorted(box.iterdir()) if p.suffix in (".json", ".done")}


def inbox_take(thread_id: str) -> list:
    """Забрать весь список дописанного для одного следующего хода Codex."""
    box = INBOX / thread_id
    texts = []
    for path in sorted(box.glob("*.json")) if box.exists() else []:
        try:
            texts.append(json.loads(path.read_text(encoding="utf-8"))["text"])
            path.replace(path.with_suffix(".done"))
        except (OSError, ValueError, KeyError):
            continue
    return texts


def list_threads() -> list:
    if not THREADS.exists():
        return []
    items = []
    for path in THREADS.glob("*.json"):
        try:
            t = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        items.append({k: t.get(k) for k in ("id", "engine", "title", "stem", "project", "updated", "fresh_of")}
                     | {"count": len(t.get("messages", []))})
    return sorted(items, key=lambda t: -(t["updated"] or 0))


def status_report() -> str:
    """Подключён ли GPT через Codex — для установщика."""
    e = engines()["codex"]
    if not e["available"]:
        return "  ✗ Codex не установлен. Студия → «Подключить GPT» → установка и вход в ChatGPT."
    auth = auth_status("codex", e["path"])
    if auth.get("logged_in") is False:
        return "  ✗ Codex установлен, но вход не выполнен: codex login."
    if auth.get("logged_in") is None:
        return "  ? Codex установлен, проверить вход не удалось. Студия → «Проверить подключение»."
    spec = gpt_client.profile("director")
    return f"  ✓ GPT / Codex готов · {auth.get('plan') or 'вход выполнен'} · {spec['model']} ({spec['effort']})"


if __name__ == "__main__":
    if sys.argv[1:] == ["--status"]:
        host.utf8_console()
        print(status_report())
    else:
        sys.exit("Использование: brain.py --status — подключён ли GPT / Codex")
