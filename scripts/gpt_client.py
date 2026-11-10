"""Общий запуск GPT через Codex CLI и подписку ChatGPT, без отдельного API-ключа.

Роли — presets/gpt.json. Переменные REELS_GPT_<РОЛЬ>_MODEL / _EFFORT — переопределение
на машине. Кэш ведёт OpenAI: здесь нет фоновых запросов ради его «подогрева».
CLI сообщает токены, но не точную цену подписочного хода: cost остаётся None.
"""
import json
import os
from pathlib import Path

from common import ROOT

PROFILES = ROOT / "presets" / "gpt.json"
EFFORTS = {"low", "medium", "high", "xhigh", "max", "ultra"}


def profile(role: str, model: str | None = None) -> dict:
    try:
        profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
        spec = profiles[role]
        prefix = f"REELS_GPT_{role.upper()}"
        chosen = model or os.environ.get(prefix + "_MODEL") or spec["model"]
        effort = os.environ.get(prefix + "_EFFORT") or spec["effort"]
        # Старое переопределение режиссёра не должно незаметно сменить поставщика.
        if role == "director":
            chosen = model or os.environ.get(prefix + "_MODEL") or os.environ.get("REELS_BRAIN_MODEL") or chosen
            effort = os.environ.get(prefix + "_EFFORT") or os.environ.get("REELS_BRAIN_EFFORT") or effort
        if not isinstance(chosen, str) or not chosen.startswith("gpt-") or effort not in EFFORTS:
            raise ValueError(f"роль {role}: нужна модель gpt-* и усилие {', '.join(sorted(EFFORTS))}")
        return {"model": chosen, "effort": effort}
    except (OSError, KeyError, TypeError, ValueError) as e:
        raise ValueError(f"Настройки GPT ({PROFILES.name}): {e}") from e


def command(binary: str, prompt: str, *, cwd: Path = ROOT, role: str = "director",
            session: str | None = None, mode: str = "safe", model: str | None = None,
            images: list | None = None, isolated: bool = False, effort: str | None = None) -> list:
    """Один запуск или продолжение того же ролика. prompt='-' — читать весь запрос из stdin."""
    if mode not in ("safe", "full"):
        raise ValueError(f"Режим доступа «{mode}» не знаю: safe или full")
    spec = profile(role, model)
    chosen_effort = effort or spec["effort"]
    if chosen_effort not in EFFORTS:
        raise ValueError(f"Неизвестное усилие GPT: {chosen_effort}")
    cmd = [binary, "exec", "--json", "--skip-git-repo-check", "-C", str(cwd), "-m", spec["model"],
           "-c", f'model_reasoning_effort="{chosen_effort}"', "-c", 'model_provider="openai"',
           "-c", 'approval_policy="never"']
    if isolated:
        # Короткие роли получают весь материал явно и не загружают MCP, личные правила,
        # навыки и историю основного проекта. Вход ChatGPT остаётся в штатном CODEX_HOME.
        instructions = ROOT / "presets" / "gpt-editor.md"
        if not instructions.is_file():
            raise ValueError(f"Нет коротких инструкций GPT: {instructions}")
        cmd += ["--ignore-user-config", "--ignore-rules", "-s", "read-only", "-c", "project_doc_max_bytes=0",
                "-c", "model_instructions_file=" + json.dumps(str(instructions), ensure_ascii=False)]
    elif mode == "full":
        cmd += ["--dangerously-bypass-approvals-and-sandbox"]
    else:
        cmd += ["-s", "workspace-write", "-c", "sandbox_workspace_write.network_access=true"]
    if session:
        cmd += ["resume", session]
    for path in images or []:
        cmd += ["--image", str(Path(path).resolve())]
    cmd += ["-" if isolated else prompt]
    return cmd


def read_result(stdout: str, stderr: str, returncode: int) -> dict:
    """Полный JSONL: требуем успешный конец хода и непустой ответ, а не просто валидный JSON."""
    text, session, usage, errors, completed = [], None, {}, [], False
    for line in stdout.splitlines():
        try:
            ev = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(ev, dict):
            continue
        kind = ev.get("type")
        if kind == "thread.started":
            session = ev.get("thread_id")
        elif kind == "item.completed" and isinstance(ev.get("item"), dict):
            item = ev["item"]
            if item.get("type") == "agent_message" and item.get("text", "").strip():
                text.append(item["text"])
        elif kind == "turn.completed":
            completed, usage = True, ev.get("usage") or {}
        elif kind in ("turn.failed", "error"):
            err = ev.get("error")
            errors.append((err.get("message") if isinstance(err, dict) else err) or ev.get("message") or "сбой GPT")
    if returncode != 0 or errors or not completed or not text:
        detail = "; ".join(map(str, errors)) or stderr[-1000:] or "нет завершённого ответа"
        raise RuntimeError(f"Codex не завершил ход (код {returncode}): {detail}")
    tokens = {key: usage.get(key) for key in ("input_tokens", "cached_input_tokens", "output_tokens")}
    return {"text": text[-1], "session": session, "cost": None, "tokens": tokens}


def usage_text(reply: dict) -> str:
    """Не приписывать цену $0, когда Codex её не сообщает."""
    cost = reply.get("cost")
    if cost is not None:
        return f"${cost:.2f}"
    tokens = reply.get("tokens") or {}
    total = sum(tokens.get(k) or 0 for k in ("input_tokens", "output_tokens"))
    cached = tokens.get("cached_input_tokens")
    return f"{total:,} токенов" + (f", из кэша {cached:,}" if cached is not None else "") + "; цена не сообщена"
