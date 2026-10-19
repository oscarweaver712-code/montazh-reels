#!/usr/bin/env python3
"""Мозг студии: Claude Code или Codex, запущенные без интерфейса из веб-студии.

Студия (web/studio.html) отправляет реплику — сервер запускает `claude -p` или
`codex exec` в папке проекта, читает поток событий (JSONL) и показывает их в чате.
Диалог продолжается той же сессией агента (--resume / exec resume), поэтому мозг
помнит, о чём шла речь, а правила проекта (AGENTS.md, скилл reels) он читает сам.

Здесь только логика без сервера: какие команды, как разбирать события, где лежат
диалоги. Тяжёлое мозг не запускает сам — кладёт задачи в очередь (jobqueue.py), и
очередь выполняет их по одной: так пока считается ролик, ноутбуком можно пользоваться.

Режимы доступа:
  safe — правка файлов и скрипты проекта (Claude: список разрешённых команд; Codex:
         песочница workspace-write с сетью). Не защита от злого умысла, а страховка от
         случайного «rm -rf»: мозг может переписать скрипт и запустить его.
  full — без ограничений (--dangerously-skip-permissions / bypass sandbox).
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
from common import ROOT, WORK_DIR

THREADS = WORK_DIR / "_studio" / "threads"
CHILD_ENV = "REELS_STUDIO_CHILD"      # хук автозапуска студии не срабатывает в агентах студии

# Что мозгу можно без спроса в безопасном режиме (Claude). Команды проекта и чтение —
# да; удаление, git push, установка пакетов — нет: отказ вернётся в чат, человек решит.
SAFE_TOOLS = [
    "Read", "Glob", "Grep", "Edit", "Write", "WebSearch", "WebFetch", "TodoWrite",
    # питон окружения: на Mac .venv/bin/python, на Windows .venv/Scripts/python.exe
    "Bash(.venv/bin/python scripts/*)", "Bash(./.venv/bin/python scripts/*)",
    "Bash(.venv/Scripts/python.exe scripts/*)", "Bash(./.venv/Scripts/python.exe scripts/*)",
    "Bash(npx --yes hyperframes@0.8.141 *)", "Bash(ffprobe *)", "Bash(/opt/homebrew/bin/ffprobe *)",
    "Bash(ls *)", "Bash(cat *)", "Bash(head *)", "Bash(tail *)", "Bash(wc *)", "Bash(grep *)",
    "Bash(mkdir -p *)", "Bash(cp *)", "Bash(curl -L -o work/*)", "Bash(curl -sL -o work/*)",
    "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)", "Bash(du *)",
    # страница ролика (work/<имя>/page.py) — тот же питон проекта; 17.10.2026 мозгу IMG_3292 её запуск запрещали
    "Bash(.venv/bin/python work/*)", "Bash(./.venv/bin/python work/*)",
    "Bash(.venv/Scripts/python.exe work/*)", "Bash(./.venv/Scripts/python.exe work/*)",
    # браузер (Claude in Chrome): Flow, фонотека, свободные фото — как у агента в терминале
    "mcp__claude-in-chrome", "ToolSearch", "Monitor",
]

PY = ".venv/Scripts/python.exe" if host.IS_WINDOWS else ".venv/bin/python"

# Модель и усилие режиссёра Claude — в проекте, а не в личных настройках того, кто запустил студию
# (19.10.2026, Валера: «для анализа точно опус 5.5 на очень высоком уровне рассуждений»). До этого
# `claude -p` брал их из ~/.claude/settings.json: на другой машине команды монтаж шёл бы чем угодно.
# Поменять на машине — REELS_BRAIN_MODEL / REELS_BRAIN_EFFORT; на один ход — model из студии.
CLAUDE_MODEL = os.environ.get("REELS_BRAIN_MODEL") or "claude-opus-5-5"
CLAUDE_EFFORT = os.environ.get("REELS_BRAIN_EFFORT") or "xhigh"

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
— Бриф ролика (стиль, формат, цели, варианты) — work/<имя>/brief.json, текст для тебя:
  {PY} scripts/styles.py --brief <имя>. Каталог стилей: presets/styles/.
— Вопрос задавай, только если без ответа дальше нельзя; иначе выбирай разумно и пиши, что выбрал.
— Рядом в своих сессиях могут монтироваться другие ролики: трогай только work/<свой ролик>/ и
  studio/<свой ролик>/; общие файлы (scripts/, presets/, правила проекта) — только по прямой просьбе.
  В имени задачи очереди — имя ролика (20-prep-IMG_3317): по нему студия понимает, чья задача.
— Человек может дописать просьбу посреди хода — придёт строкой «Человек дописал…»: учти её с текущего шага.
— Приёмы рилса @tenfoldmarc (оглавление, чек-лист, телефон, интерфейс, стена, орбита, рамка, вертиго,
  пролёт, отъезд, рост, сцена, коллаж, каракули, обложка, стекло) — scripts/fx.py, когда к месту —
  docs/ПРИЁМЫ-17.md. Ставь по плану и к смыслу, не ради набора: не больше двух крупных приёмов на мысль.
— Браузер у тебя есть — тот же Chrome человека, что у агента в терминале (Claude — Claude in Chrome, Codex —
  Computer Use): монтаж из студии должен быть не хуже монтажа из терминала. ИИ-футаж (Google Flow / Omni) делай
  сам по скиллу flow (.agents/skills/flow/SKILL.md), бонусы — в пределах budget из footage.json; лоу-фай — из
  фонотеки YouTube (rules.md проекта, scripts/music.py add). Приём клипа (footage.py --take) — через очередь.
  Браузер не отвечает — не подменяй видео картинкой молча: напиши человеку, чего не хватает, до рендера.
— Ждать задачу очереди — только {PY} scripts/jobqueue.py wait <задача>, не своим циклом по логу.
— Порядок инструментов проекта — его rules.md (у antishkola п.18: всегда → часто → иногда → редко); субтитры не
  на лице и текст за головой виден — проверяет verify_page, рендер не пойдёт.
"""


# ---------------------------------------------------------------- движки

# Где обычно живут CLI агентов, если PATH урезан (сервер, поднятый из Finder или хука)
EXTRA_BIN = (["~/.local/bin", "~/AppData/Roaming/npm", "~/AppData/Local/Programs/claude",
              "~/.claude/local"] if host.IS_WINDOWS else
             ["~/.local/bin", "/opt/homebrew/bin", "/usr/local/bin", "~/.claude/local", "~/.npm-global/bin"])


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
    for name in ("claude", "codex"):
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
    """Вошёл ли человек в мозг и на каком тарифе: claude auth status / codex login status.

    Ничего не запускает в модели и ничего не тратит. Не смогли узнать — logged_in None (не «нет»).
    """
    try:
        if name == "claude":
            out = subprocess.run([path, "auth", "status", "--json"], capture_output=True, encoding="utf-8",
                                 errors="replace", timeout=20, env=clean_env())
            data = json.loads(out.stdout or "{}")
            plan = data.get("subscriptionType") or ("API-ключ" if data.get("authMethod") == "apiKey" else data.get("authMethod"))
            return {"logged_in": bool(data.get("loggedIn")), "plan": plan}
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
    path = find_binary(engine)
    quoted = (f'& "{path}"' if host.IS_WINDOWS else f'"{path}"') if path else engine
    if action == "install":
        if engine == "claude":
            return ("irm https://claude.ai/install.ps1 | iex" if host.IS_WINDOWS
                    else "curl -fsSL https://claude.ai/install.sh | bash")
        return "npm install -g @openai/codex"          # npm есть: на Node работает HyperFrames
    if action == "login":
        if not path:
            raise ValueError(f"{engine} ещё не установлен — сначала «Установить»")
        return f"{quoted} auth login" if engine == "claude" else f"{quoted} login"
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
        env["REELS_THREAD"] = thread_id       # хук дописанных просьб (scripts/inbox_hook.mjs) знает, чей ход
    # из Finder PATH короткий — без него агент не найдёт ffmpeg, node и npx
    extra = [str(Path(folder).expanduser()) for folder in EXTRA_BIN]
    env["PATH"] = os.pathsep.join(extra + [env.get("PATH", "")])
    return env


# Хук «после каждого действия»: дописанное человеком посреди монтажа агент получает сразу, а не в конце
# хода (замер 16.10.2026: Claude видит его после ближайшего действия). Только агентам студии — через
# --settings, в настройки проекта его не кладём. Codex в режиме exec хуки после действий не вызывает
# (проверено на 0.162) — ему дописанное студия отдаёт следующим ходом.
INBOX_HOOK = {"hooks": {"PostToolUse": [{"matcher": "", "hooks": [
    {"type": "command", "command": 'node "$CLAUDE_PROJECT_DIR/scripts/inbox_hook.mjs"', "timeout": 10}]}]}}


def command(engine: str, prompt: str, session: str | None = None, mode: str = "safe",
            model: str | None = None, context: str = "", thread_id: str | None = None) -> list:
    """Команда запуска одного хода агента. prompt — реплика человека."""
    binary = find_binary(engine)
    if not binary:
        raise RuntimeError(f"{engine} не найден на этой машине — установи его или выбери другой мозг")
    if mode not in ("safe", "full"):
        raise ValueError(f"Режим доступа «{mode}» не знаю: safe или full")

    if engine == "claude":
        cmd = [binary, "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--append-system-prompt", STUDIO_PROMPT + ("\n" + context if context else "")]
        # --chrome: браузер человека, как у агента в терминале (17.10.2026: «чтобы монтаж из студии был идентичен»)
        cmd += ["--chrome"]
        if mode == "full":
            cmd += ["--dangerously-skip-permissions"]
        else:
            cmd += ["--permission-mode", "acceptEdits", "--allowedTools", *SAFE_TOOLS]
        cmd += ["--model", model or CLAUDE_MODEL, "--effort", CLAUDE_EFFORT]
        if thread_id:
            cmd += ["--settings", json.dumps(INBOX_HOOK)]
        if session:
            cmd += ["--resume", session]
        return cmd

    if engine == "codex":
        # у Codex нет отдельной системной подсказки: правила студии идут в первую реплику
        text = prompt if session else f"{STUDIO_PROMPT}\n{context}\n\nЗапрос:\n{prompt}".strip()
        cmd = [binary, "exec", "--json", "--skip-git-repo-check", "-C", str(ROOT)]
        if mode == "full":
            cmd += ["--dangerously-bypass-approvals-and-sandbox"]
        else:
            cmd += ["-s", "workspace-write", "-c", "sandbox_workspace_write.network_access=true"]
        if model:
            cmd += ["-m", model]
        if session:
            cmd += ["resume", session, text]
        else:
            cmd += [text]
        return cmd

    raise ValueError(f"Мозг «{engine}» не знаю: claude или codex")


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

    if engine == "claude":
        if kind == "system" and ev.get("subtype") == "init":
            out.append({"type": "session", "id": ev.get("session_id"), "model": ev.get("model")})
        elif kind == "assistant":
            for block in (ev.get("message") or {}).get("content") or []:
                if block.get("type") == "text" and block.get("text", "").strip():
                    out.append({"type": "text", "text": block["text"]})
                elif block.get("type") == "tool_use":
                    out.append({"type": "tool", "id": block.get("id"), "name": block.get("name"),
                                "summary": _tool_summary(block.get("name", ""), block.get("input") or {})})
        elif kind == "user":
            for block in (ev.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content")
                    if isinstance(content, list):
                        content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                    out.append({"type": "tool_done", "id": block.get("tool_use_id"),
                                "error": bool(block.get("is_error")), "output": _short(content or "", 300)})
        elif kind == "result":
            denials = [_tool_summary(d.get("tool_name", ""), d.get("tool_input") or {})
                       for d in ev.get("permission_denials") or []]
            out.append({"type": "result", "ok": not ev.get("is_error"), "text": ev.get("result") or "",
                        "session": ev.get("session_id"), "cost": ev.get("total_cost_usd"),
                        "denied": denials, "context": context_size(ev.get("usage"))})
            if ev.get("is_error"):
                # 14.10.2026: «Failed to authenticate. API Error: 403» приходил только текстом результата —
                # пачка не видела ошибки и прожгла на ней оставшиеся ходы ролика
                out.append({"type": "error", "text": explain_error(ev.get("result") or "агент закончил ход ошибкой")})
        return out

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
            out.append({"type": "result", "ok": True, "text": "", "usage": ev.get("usage")})
        elif kind in ("turn.failed", "error"):
            message = (ev.get("error") or {}).get("message") if kind == "turn.failed" else ev.get("message")
            out.append({"type": "error", "text": explain_error(message or "")})
        return out
    return out


def context_size(usage: dict | None) -> int | None:
    """Сколько токенов занимал разговор в последнем обращении к модели — по нему видно, что сессия разрослась.

    usage итога Claude — сумма за ход; размер контекста — у последнего обращения (iterations[-1]):
    вход + прочитанное из кэша + записанное в кэш.
    """
    if not isinstance(usage, dict):
        return None
    last = (usage.get("iterations") or [None])[-1] or usage
    try:
        return int(last.get("input_tokens", 0)) + int(last.get("cache_read_input_tokens", 0)) \
            + int(last.get("cache_creation_input_tokens", 0))
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
        return f"Лимит подписки исчерпан — подожди или переключи мозг. ({message})"
    if "newer version of codex" in low or ("codex" in low and "upgrade" in low):
        return f"Codex устарел для выбранной модели — выполни в терминале `codex update`. ({message})"
    if ("not logged in" in low or "login" in low or "unauthorized" in low or "401" in low
            or "failed to authenticate" in low or "403" in low):
        return f"Мозг не авторизован — открой терминал и войди (claude → /login или codex login). ({message})"
    return message


# ---------------------------------------------------------------- диалоги

def _thread_path(thread_id: str) -> Path:
    if not thread_id or not all(c.isalnum() or c == "-" for c in thread_id):
        raise ValueError("плохой номер диалога")
    return THREADS / f"{thread_id}.json"


def new_thread(engine: str, title: str = "", stem: str | None = None, project: str | None = None) -> dict:
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
    return json.loads(path.read_text(encoding="utf-8"))


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
# Порог — размер контекста у Claude и число просьб человека у любого мозга. Состояние ролика живёт в
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
                return f"разговор занял ≈{res['context'] // 1000} тыс. токенов"
            break
    asks = sum(1 for m in msgs if m.get("role") == "user" and not m.get("auto"))   # ходы пачки «продолжай» — не просьбы
    if asks >= FRESH_REQUESTS:
        return f"в разговоре уже {asks} просьб"
    return None


def _final_text(message: dict, limit: int) -> str:
    texts = [e.get("text", "") for e in message.get("events") or [] if e.get("type") == "text" and e.get("text")]
    text = " ".join((texts[-1] if texts else "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def handoff(thread: dict, keep: int = 6) -> str:
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
    return ("Это продолжение работы в свежей сессии: прошлая разрослась, и монтаж в ней стал бы хуже.\n"
            f"Что было в прошлой сессии ({len(pairs)} просьб, последние {min(keep, len(pairs))}):\n"
            + "\n".join(pairs[-keep:]) + "\n" + where)


# ---------------------------------------------------------------- дописанное по ходу

INBOX = WORK_DIR / "_studio" / "inbox"


def inbox_add(thread_id: str, text: str) -> str:
    """Просьба человека к идущему ходу: файл, который хук агента заберёт после ближайшего действия."""
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
    """Недоставленное хуком (Codex, или ход кончился раньше) — забрать, чтобы отдать следующим ходом."""
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
    """Подключены ли Claude и Codex — для установщика: монтирует ИИ, без него только ручные правки."""
    lines, ready = [], []
    for name, e in engines().items():
        title = "Claude" if name == "claude" else "Codex"
        if not e["available"]:
            lines.append(f"  ✗ {title}: не установлен")
            continue
        auth = auth_status(name, e["path"])
        if auth.get("logged_in") is False:
            lines.append(f"  ✗ {title}: установлен, но вход не выполнен")
        else:
            ready.append(title)
            lines.append(f"  ✓ {title}: готов{' · ' + auth['plan'] if auth.get('plan') else ''}")
    tail = ("  Монтирует ИИ — без него студия умеет только ручные правки. Подключить лучше оба (кончится лимит у одного —\n"
            "  продолжит второй): студия → кнопка «Подключи ИИ» вверху справа, установка и вход — в пару кликов.")
    return "\n".join(lines + ([tail] if len(ready) < 2 else []))


if __name__ == "__main__":
    if sys.argv[1:] == ["--status"]:
        host.utf8_console()
        print(status_report())
    else:
        sys.exit("Использование: brain.py --status — подключены ли Claude и Codex")
