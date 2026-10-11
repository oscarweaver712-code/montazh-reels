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

from common import ROOT, WORK_DIR

THREADS = WORK_DIR / "_studio" / "threads"
CHILD_ENV = "REELS_STUDIO_CHILD"      # хук автозапуска студии не срабатывает в агентах студии

# Что мозгу можно без спроса в безопасном режиме (Claude). Команды проекта и чтение —
# да; удаление, git push, установка пакетов — нет: отказ вернётся в чат, человек решит.
SAFE_TOOLS = [
    "Read", "Glob", "Grep", "Edit", "Write", "WebSearch", "WebFetch", "TodoWrite",
    "Bash(.venv/bin/python scripts/*)", "Bash(./.venv/bin/python scripts/*)",
    "Bash(npx --yes hyperframes@0.8.141 *)", "Bash(ffprobe *)", "Bash(/opt/homebrew/bin/ffprobe *)",
    "Bash(ls *)", "Bash(cat *)", "Bash(head *)", "Bash(tail *)", "Bash(wc *)", "Bash(grep *)",
    "Bash(mkdir -p *)", "Bash(cp *)", "Bash(curl -L -o work/*)", "Bash(curl -sL -o work/*)",
    "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)", "Bash(du *)", "Bash(open *)",
]

STUDIO_PROMPT = """Тебя вызывают из локальной студии монтажа (web/studio.html): человек видит твои
ответы в чате студии, терминала он не видит. Работай по AGENTS.md и скиллу reels
(.agents/skills/reels/SKILL.md).
— Отвечай по-русски, коротко и по делу. В конце: что сделано, где файл, как откатить.
— Тяжёлое (transcribe, prep, track, matte, reframe, render_reel, reels.py) не запускай сам:
  клади задачу в очередь — файл work/_queue/<NN>-<имя>.sh с одной командой (порядок по
  номеру: 05-render, 10-transcribe, 20-prep, 30-fast). Очередь выполняет студия, по одной.
  Проверить ход: work/_queue/logs/, готовое — work/_queue/done/, упавшее — failed/.
— Бриф ролика (стиль, формат, цели, варианты) — work/<имя>/brief.json, текст для тебя:
  .venv/bin/python scripts/styles.py --brief <имя>. Каталог стилей: presets/styles/.
— Вопрос задавай, только если без ответа дальше нельзя; иначе выбирай разумно и пиши, что выбрал.
"""


# ---------------------------------------------------------------- движки

def find_binary(name: str) -> str | None:
    """CLI агента: PATH сервера бывает урезан (запуск из Finder), поэтому смотрим и в типичные места."""
    found = shutil.which(name)
    if found:
        return found
    for folder in ("~/.local/bin", "/opt/homebrew/bin", "/usr/local/bin", "~/.claude/local",
                   "~/.npm-global/bin"):
        path = Path(folder).expanduser() / name
        if path.exists():
            return str(path)
    return None


def engines() -> dict:
    """Какие мозги есть на машине и их версии."""
    out = {}
    for name in ("claude", "codex"):
        path = find_binary(name)
        version = None
        if path:
            try:
                version = subprocess.run([path, "--version"], capture_output=True, text=True,
                                         timeout=15).stdout.strip().splitlines()[0]
            except (subprocess.TimeoutExpired, OSError, IndexError):
                version = None
        out[name] = {"available": bool(path), "path": path, "version": version}
    return out


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


def child_env() -> dict:
    env = clean_env()
    env[CHILD_ENV] = "1"
    # из Finder PATH короткий — без него агент не найдёт ffmpeg, node и npx
    extra = ["/opt/homebrew/bin", str(Path("~/.local/bin").expanduser()), "/usr/local/bin"]
    env["PATH"] = ":".join(extra + [env.get("PATH", "/usr/bin:/bin")])
    return env


def command(engine: str, prompt: str, session: str | None = None, mode: str = "safe",
            model: str | None = None, context: str = "") -> list:
    """Команда запуска одного хода агента. prompt — реплика человека."""
    binary = find_binary(engine)
    if not binary:
        raise RuntimeError(f"{engine} не найден на этой машине — установи его или выбери другой мозг")
    if mode not in ("safe", "full"):
        raise ValueError(f"Режим доступа «{mode}» не знаю: safe или full")

    if engine == "claude":
        cmd = [binary, "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--append-system-prompt", STUDIO_PROMPT + ("\n" + context if context else "")]
        if mode == "full":
            cmd += ["--dangerously-skip-permissions"]
        else:
            cmd += ["--permission-mode", "acceptEdits", "--allowedTools", *SAFE_TOOLS]
        if model:
            cmd += ["--model", model]
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
                        "denied": denials})
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


def explain_error(message: str) -> str:
    """Ошибки агента — человеческим языком, с тем, что делать."""
    try:
        inner = json.loads(message)
        message = ((inner.get("error") or {}).get("message")) or message
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    low = message.lower()
    # лимит — первым: у Claude в нём есть «/upgrade», и раньше это читалось как «Codex устарел»
    if "rate limit" in low or "usage limit" in low or "429" in low:
        return f"Лимит подписки исчерпан — подожди или переключи мозг. ({message})"
    if "newer version of codex" in low or ("codex" in low and "upgrade" in low):
        return f"Codex устарел для выбранной модели — выполни в терминале `codex update`. ({message})"
    if "not logged in" in low or "login" in low or "unauthorized" in low or "401" in low:
        return f"Мозг не авторизован — открой терминал и войди (claude → /login или codex login). ({message})"
    return message


# ---------------------------------------------------------------- диалоги

def _thread_path(thread_id: str) -> Path:
    if not thread_id or not all(c.isalnum() or c == "-" for c in thread_id):
        raise ValueError("плохой номер диалога")
    return THREADS / f"{thread_id}.json"


def new_thread(engine: str, title: str = "", stem: str | None = None) -> dict:
    THREADS.mkdir(parents=True, exist_ok=True)
    thread = {"id": uuid.uuid4().hex[:12], "engine": engine, "title": title or "Новый разговор",
              "stem": stem, "session": None, "created": time.time(), "updated": time.time(),
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


def list_threads() -> list:
    if not THREADS.exists():
        return []
    items = []
    for path in THREADS.glob("*.json"):
        try:
            t = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        items.append({k: t.get(k) for k in ("id", "engine", "title", "stem", "updated")}
                     | {"count": len(t.get("messages", []))})
    return sorted(items, key=lambda t: -(t["updated"] or 0))
