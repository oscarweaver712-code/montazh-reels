#!/usr/bin/env python3
"""Ключи внешних сервисов этой машины — в .keys/ папки проекта, мимо git (.gitignore), или в переменной окружения.

Ключ стоков обязателен (Валера, 23.10.2026: «добавь ключ как обязалово при настройке репо другим человеком под себя»):
у Mixkit и Coverr почти всё горизонтальное и не 4K — во весь вертикальный кадр мутнее 720p (common.sharpness). Pixabay
отдаёт 4K (из него — 1080p во весь кадр), ключ виден сразу после входа — он обязателен. Pexels (вертикальные 1080p/4K) —
по желанию: 23.10.2026 новые ключи у них на паузе. Ключ у каждого свой и бесплатный: лимит — на ключ, условия — на человека.

  .venv/bin/python scripts/keys.py setup     # спросить недостающие ключи и проверить их запросом (установка зовёт сама)
  .venv/bin/python scripts/keys.py status    # что есть на этой машине
  pbpaste | .venv/bin/python scripts/keys.py set gemini   # положить ключ из буфера, не показывая его

Gemini (24.10.2026, Валера: «используй купленный») — не для монтажа, а для отсмотра больших съёмок: ключ куплен на
маркетплейсе, то есть это чужой аккаунт Google, и загруженное видит продавец. Владелец это решил сам; установка ключ не
спрашивает.

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
    "pixabay": {
        "env": "PIXABAY_API_KEY",
        "required": True,
        "what": "Pixabay — стоки 4K без водяных знаков",
        "how": ("1) зарегистрируйся или войди на https://pixabay.com (можно через Google);\n"
                "  2) открой https://pixabay.com/api/docs/ — в разделе «Parameters» у поля key виден твой ключ;\n"
                "  3) скопируй его и вставь сюда"),
    },
    "pexels": {
        "env": "PEXELS_API_KEY",
        "required": False,
        "what": "Pexels — вертикальные стоки 1080p/4K без водяных знаков",
        "how": ("https://www.pexels.com/api/ → «Get Started» → ключ на https://www.pexels.com/api/key/ (23.10.2026 новые ключи\n"
                "  у Pexels на паузе — тогда просто Enter, без него всё работает)"),
    },
    "gemini": {
        "env": "GEMINI_API_KEY",
        "required": False,
        "setup": False,
        "what": "Gemini API — отсмотр больших съёмок",
        "how": "скопируй ключ и выполни: pbpaste | .venv/bin/python scripts/keys.py set gemini",
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


def check_pixabay(key: str) -> tuple:
    """(годен, почему) — один запрос поиска видео: 200 — ключ живой (у Pixabay ключ — параметр адреса, так устроен API)."""
    import urllib.parse
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": key, "q": "ocean", "per_page": 3})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "reels-montage"}), timeout=30) as resp:
            json.loads(resp.read())
            return True, f"ключ работает, осталось запросов: {resp.headers.get('X-RateLimit-Remaining', '?')}"
    except urllib.error.HTTPError as e:
        return False, ("Pixabay не принял ключ — скопируй его заново" if e.code in (400, 401, 403)
                       else f"Pixabay ответил {e.code}")
    except (urllib.error.URLError, TimeoutError) as e:
        return False, f"нет связи с Pixabay: {e}"


def check_gemini(key: str) -> tuple:
    """(годен, почему) — список моделей: 200 — ключ живой, ничего не тратит."""
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=100",
                                 headers={"x-goog-api-key": key, "User-Agent": "reels-montage"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            names = [m["name"].split("/")[-1] for m in json.loads(resp.read()).get("models", [])]
            flash = [n for n in names if "flash" in n]
            return True, f"ключ работает, моделей: {len(names)}" + (f", flash: {', '.join(flash[:6])}" if flash else "")
    except urllib.error.HTTPError as e:
        return False, ("Gemini не принял ключ — скопируй его заново" if e.code in (400, 401, 403)
                       else f"Gemini ответил {e.code}")
    except (urllib.error.URLError, TimeoutError) as e:
        return False, f"нет связи с Gemini (нужен VPN?): {e}"


CHECKS = {"pexels": check_pexels, "pixabay": check_pixabay, "gemini": check_gemini}


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
        if not service.get("setup", True):
            continue
        key = get(name)
        if key:
            ok, why = CHECKS[name](key)
            print(f"{'✓' if ok else '✗'} {service['what']}: {why}")
            if ok:
                continue
        if not sys.stdin.isatty():
            print(f"{'✗' if service.get('required', True) else '·'} нет ключа: {service['what']}. "
                  f"Запусти в терминале: .venv/bin/python scripts/keys.py setup")
            missing += int(service.get("required", True))
            continue
        need = service.get("required", True)
        print(f"\n{'Нужен' if need else 'По желанию'} ключ: {service['what']}. Бесплатно, минуты три:\n  {service['how']}")
        for _ in range(3):
            key = getpass.getpass("Ключ (не виден при вводе" + ("" if need else "; Enter — пропустить") + "): ").strip()
            if not key:
                if not need:
                    print(f"· без ключа: {service['what']} — пропущено, можно добавить потом: keys.py setup")
                    break
                continue
            ok, why = CHECKS[name](key)
            print(f"{'✓' if ok else '✗'} {why}")
            if ok:
                print(f"✓ сохранён: {save(name, key).relative_to(ROOT)} (не в git)")
                break
        else:
            if service.get("required", True):
                print(f"✗ без ключа {service['what']} установка не закончена — запусти её снова, когда будет ключ")
                missing += 1
    return 1 if missing else 0


def main():
    host.utf8_console()
    ap = argparse.ArgumentParser(description="Ключи внешних сервисов этой машины")
    ap.add_argument("cmd", choices=["setup", "status", "set"])
    ap.add_argument("name", nargs="?", choices=list(SERVICES), help="для set: какой ключ положить")
    a = ap.parse_args()
    if a.cmd == "setup":
        sys.exit(setup())
    if a.cmd == "set":
        if not a.name:
            sys.exit("✗ какой ключ? например: pbpaste | .venv/bin/python scripts/keys.py set gemini")
        key = (getpass.getpass("Ключ (не виден при вводе): ") if sys.stdin.isatty() else sys.stdin.read()).strip()
        if not key:
            sys.exit("✗ ключ пустой — скопируй его в буфер и повтори")
        if any(c.isspace() for c in key):
            sys.exit(f"✗ в буфере не ключ — в нём пробелы («{key[:6]}…», {len(key)} символов): скопируй сам ключ и повтори")
        ok, why = CHECKS[a.name](key)
        print(f"{'✓' if ok else '✗'} {SERVICES[a.name]['what']}: {why}")
        if not ok:
            sys.exit(1)
        print(f"✓ сохранён: {save(a.name, key).relative_to(ROOT)} (не в git)")
        return
    for name, service in SERVICES.items():
        print(f"{'✓' if get(name) else '✗'} {name}: {service['what']}")


if __name__ == "__main__":
    main()
