#!/usr/bin/env python3
"""Ключи внешних сервисов этой машины — в .keys/ папки проекта, мимо git (.gitignore), или в переменной окружения.

Pexels — обязателен (Валера, 23.10.2026: «добавь ключ как обязалово при настройке репо другим человеком под себя»):
вертикальные стоки в 1080p и 4K есть почти только там, а у Mixkit и Coverr — горизонталь, которая во весь вертикальный
кадр выходит мутнее 720p (common.sharpness). Ключ у каждого свой и бесплатный: лимит — на ключ, условия — на человека.

  .venv/bin/python scripts/keys.py setup     # спросить недостающие ключи и проверить их запросом (установка зовёт сама)
  .venv/bin/python scripts/keys.py status    # что есть на этой машине

В CI (переменная CI) ключ не спрашивается: там нет человека, а стоки самопроверка не качает.
"""
import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import host  # noqa: E402
from common import ROOT  # noqa: E402

KEYS = ROOT / ".keys"
SERVICES = {
    "pexels": {
        "env": "PEXELS_API_KEY",
        "what": "Pexels — вертикальные стоки 1080p/4K без водяных знаков",
        "how": ("1) открой https://www.pexels.com/api/ и нажми «Get Started» (вход — можно через Google);\n"
                "  2) заполни форму: зачем ключ — «монтаж своих роликов», сайт — можно ссылку на свой профиль;\n"
                "  3) скопируй ключ со страницы https://www.pexels.com/api/key/ и вставь сюда"),
    },
}


class KeyMissing(RuntimeError):
    """Ключа нет — по-русски, где его взять."""


def get(name: str) -> str | None:
    """Ключ сервиса: из переменной окружения, иначе из .keys/<сервис>.txt."""
    service = SERVICES[name]
    value = os.environ.get(service["env"], "").strip()
    if value:
        return value
    path = KEYS / f"{name}.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip() or None


def require(name: str) -> str:
    key = get(name)
    if not key:
        raise KeyMissing(f"нет ключа {SERVICES[name]['what']}. Запусти: .venv/bin/python scripts/keys.py setup "
                         f"(или переменная {SERVICES[name]['env']}). Где взять:\n  {SERVICES[name]['how']}")
    return key


def check_pexels(key: str) -> tuple:
    """(годен, почему) — один запрос поиска: 200 — ключ живой."""
    req = urllib.request.Request("https://api.pexels.com/videos/search?query=ocean&per_page=1",
                                 headers={"Authorization": key, "User-Agent": "reels-montage"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            json.loads(resp.read())
            return True, f"ключ работает, осталось запросов: {resp.headers.get('X-Ratelimit-Remaining', '?')}"
    except urllib.error.HTTPError as e:
        return False, ("Pexels не принял ключ (401) — скопируй его заново" if e.code in (401, 403)
                       else f"Pexels ответил {e.code}")
    except (urllib.error.URLError, TimeoutError) as e:
        return False, f"нет связи с Pexels: {e}"


CHECKS = {"pexels": check_pexels}


def save(name: str, key: str) -> Path:
    KEYS.mkdir(exist_ok=True)
    path = KEYS / f"{name}.txt"
    path.write_text(key.strip() + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)                            # ключ — только владельцу (на Windows chmod ничего не делает)
    except OSError:
        pass
    return path


def setup() -> int:
    """Спросить недостающие ключи и проверить. 0 — всё есть, 1 — ключа нет (установка не закончена)."""
    if os.environ.get("CI"):
        print("· CI: ключи не спрашиваю — человека нет, стоки самопроверка не качает")
        return 0
    missing = 0
    for name, service in SERVICES.items():
        key = get(name)
        if key:
            ok, why = CHECKS[name](key)
            print(f"{'✓' if ok else '✗'} {service['what']}: {why}")
            if ok:
                continue
        if not sys.stdin.isatty():
            print(f"✗ нет ключа: {service['what']}. Запусти в терминале: .venv/bin/python scripts/keys.py setup")
            missing += 1
            continue
        print(f"\nНужен ключ: {service['what']}. Бесплатно, минуты три:\n  {service['how']}")
        for _ in range(3):
            key = getpass.getpass("Ключ (не виден при вводе, Enter — вставить): ").strip()
            if not key:
                continue
            ok, why = CHECKS[name](key)
            print(f"{'✓' if ok else '✗'} {why}")
            if ok:
                print(f"✓ сохранён: {save(name, key).relative_to(ROOT)} (не в git)")
                break
        else:
            print(f"✗ без ключа {service['what']} установка не закончена — запусти её снова, когда будет ключ")
            missing += 1
    return 1 if missing else 0


def main():
    host.utf8_console()
    ap = argparse.ArgumentParser(description="Ключи внешних сервисов этой машины")
    ap.add_argument("cmd", choices=["setup", "status"])
    a = ap.parse_args()
    if a.cmd == "setup":
        sys.exit(setup())
    for name, service in SERVICES.items():
        print(f"{'✓' if get(name) else '✗'} {name}: {service['what']}")


if __name__ == "__main__":
    main()
