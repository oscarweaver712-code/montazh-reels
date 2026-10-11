#!/usr/bin/env python3
"""Пачка роликов из терминала: каждый ролик — в своей новой сессии мозга.

Правило Валеры (11.10.2026): одно видео — одна сессия. Контекст у сессии конечный, и если
монтировать всю пачку в одном разговоре, каждый следующий ролик выходит хуже. Поэтому на
«смонтируй новые из input/» агент в терминале не монтирует их сам, а запускает пачку в
студии: она берёт ролики по одному, на каждый открывает новую сессию Claude или Codex и
сама продолжает разговор, когда очередь отработала.

  .venv/bin/python scripts/batch.py                    # все новые (без выпусков) — Claude
  .venv/bin/python scripts/batch.py IMG_3330 IMG_3331 --engine codex
  .venv/bin/python scripts/batch.py --watch            # и следить, пока пачка не кончится
  .venv/bin/python scripts/batch.py --status
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import studio_up

LABELS = {"queued": "ждёт", "working": "монтирует", "waiting_queue": "ждёт очередь", "done": "готово",
          "needs_human": "нужен человек", "failed": "не вышло", "skipped": "пропущен"}


def call(path: str, data: dict | None = None, token: str = "") -> dict:
    request = urllib.request.Request(studio_up.URL + path)
    if data is not None:
        request.data = json.dumps(data).encode("utf-8")
        request.add_header("Content-Type", "application/json")
        request.add_header("X-Studio-Token", token)
    try:
        with urllib.request.urlopen(request, timeout=30) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8")).get("detail")
        except (ValueError, AttributeError):
            detail = None
        sys.exit(f"✗ {detail or f'студия ответила {e.code}'}")


def token() -> str:
    with urllib.request.urlopen(studio_up.URL + "/", timeout=10) as res:
        found = re.search(r'STUDIO_TOKEN = "([^"]+)"', res.read().decode("utf-8"))
    if not found:
        sys.exit("✗ Студия не отдала ключ страницы — это точно наша студия на этом порту?")
    return found.group(1)


def show(state: dict) -> str:
    lines = [f"  {LABELS.get(i['status'], i['status']):<14} {i['stem']}" + (f" — {i['note']}" if i.get("note") else "")
             for i in state.get("items", [])]
    return "\n".join(lines) or "  пачки нет"


def main():
    ap = argparse.ArgumentParser(description="Пачка роликов: каждый — в своей сессии мозга")
    ap.add_argument("stems", nargs="*", help="ролики (имя без расширения); по умолчанию — все новые")
    ap.add_argument("--engine", choices=("claude", "codex"), default="claude")
    ap.add_argument("--mode", choices=("safe", "full"), default="safe")
    ap.add_argument("--watch", action="store_true", help="следить, пока пачка не кончится")
    ap.add_argument("--status", action="store_true", help="только показать ход пачки")
    args = ap.parse_args()

    state = studio_up.ping()
    if state and state.get("foreign"):
        sys.exit(f"✗ Порт {studio_up.PORT} занят чужой программой")
    if not state and not studio_up.start_server():
        sys.exit("✗ Студия не поднялась — см. work/_studio/server.log")

    if args.status:
        print(show(call("/api/brain/batch")))
        return
    started = call("/api/brain/batch", {"stems": args.stems, "engine": args.engine, "mode": args.mode}, token())
    print(f"✓ Пачка запущена ({args.engine}): каждый ролик — в своей сессии, ход виден в студии {studio_up.URL}")
    print(show(started))
    last = ""
    while args.watch:
        time.sleep(10)
        state = call("/api/brain/batch")
        text = show(state)
        if text != last:
            print(time.strftime("%H:%M:%S"), "\n" + text, flush=True)
            last = text
        if not state.get("running"):
            break


if __name__ == "__main__":
    main()
