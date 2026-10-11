#!/usr/bin/env python3
"""Поднять студию монтажа и открыть её в браузере — хук на старт Claude Code и Codex.

Открыл папку проекта в `claude` или `codex` — студия сама встаёт на 127.0.0.1:8765 и
открывается вкладкой. Сервер уже работает — второй не запускается; вкладка уже открыта —
вторая не открывается. Агенты, которых запускает сама студия (мозг), хук пропускают:
иначе каждый ответ мозга открывал бы новую вкладку.

Хук никогда не роняет сессию агента: при любой беде он пишет одну строку и выходит с 0.

  .venv/bin/python scripts/studio_up.py            # поднять и открыть
  .venv/bin/python scripts/studio_up.py --no-open  # только поднять
  .venv/bin/python scripts/studio_up.py --stop     # погасить сервер студии

Отключить автозапуск: переменная REELS_NO_STUDIO=1 (например, в ~/.zshrc).
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import host  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("REELS_STUDIO_PORT", "8765"))
URL = f"http://127.0.0.1:{PORT}"
LOG = ROOT / "work" / "_studio" / "server.log"


def ping(timeout: float = 0.6) -> dict | None:
    """Ответ студии или None. Чужой сервер на порту — {"foreign": True}."""
    try:
        with urllib.request.urlopen(f"{URL}/api/ping", timeout=timeout) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data if data.get("app") == "montazh-reels" else {"foreign": True}
    except urllib.error.HTTPError:
        return {"foreign": True}
    except (urllib.error.URLError, OSError, ValueError):
        return None


def start_server() -> bool:
    """Сервер отдельной сессией процессов: переживёт и хук, и закрытый терминал.

    Окружение — без переменных сессии агента, из которой его подняли: сервер её переживёт,
    а мозг и очередь, которых он запускает, не должны выдавать себя за её часть.
    """
    python = host.venv_python(ROOT)
    if not python.exists():
        print("Студия не запущена: нет окружения .venv — сначала установка "
              f"({'Установка.bat' if host.IS_WINDOWS else 'Установка.command'})")
        return False
    from brain import clean_env
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as log:
        log.write(f"\n--- запуск {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.flush()
        subprocess.Popen([str(python), "-u", "scripts/server.py", str(PORT)], cwd=ROOT,
                         stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         env=host.utf8_env(clean_env()), **host.detached())
    for _ in range(40):                       # до 10 секунд
        time.sleep(0.25)
        if ping():
            return True
    print(f"Студия не ответила за 10 с — лог: {LOG.relative_to(ROOT)}")
    return False


def stop_server() -> None:
    state = ping()
    if not state or state.get("foreign"):
        print("Студия и так не работает")
        return
    os.kill(int(state["pid"]), signal.SIGTERM)
    print("Студия остановлена")


def main():
    ap = argparse.ArgumentParser(description="Поднять студию монтажа и открыть вкладку")
    ap.add_argument("--no-open", action="store_true", help="не открывать браузер")
    ap.add_argument("--stop", action="store_true", help="погасить сервер студии")
    args = ap.parse_args()

    # stdin не читаем: JSON события хука нам не нужен, а чтение из чужого открытого канала
    # (запуск не из терминала) висло бы вечно. Маленький JSON и так помещается в буфер канала.

    if args.stop:
        stop_server()
        return
    # git на Windows кладёт вместо ссылок на скиллы текстовые файлы — чиним при каждом старте:
    # скилл, пришедший с git pull, тоже должен стать виден Claude
    try:
        fixed = host.link_skills()
        if fixed:
            print(f"Скиллы для Claude подключены ссылками: {', '.join(fixed)} — видны со следующей сессии.")
    except OSError as e:
        print(f"⚠ Скиллы для Claude не подключились: {e}")
    if os.environ.get("REELS_STUDIO_CHILD") == "1" or os.environ.get("REELS_NO_STUDIO") == "1":
        return

    state = ping()
    if state and state.get("foreign"):
        print(f"Порт {PORT} занят чужой программой — студия не запущена. "
              f"Освободи порт или задай REELS_STUDIO_PORT.")
        return
    if not state:
        if not start_server():
            return
        state = ping() or {}
    if not args.no_open and not state.get("tab_open") and os.environ.get("REELS_NO_BROWSER") != "1":
        webbrowser.open(URL)
    py = ".venv/Scripts/python.exe" if host.IS_WINDOWS else ".venv/bin/python"
    print(f"Студия монтажа открыта: {URL} — ролики, бриф (стиль, формат, цели), очередь и чат "
          f"с мозгом. Бриф ролика лежит в work/<имя>/brief.json, текст брифа: "
          f"{py} scripts/styles.py --brief <имя>. Один ролик — одна сессия агента.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                    # хук не имеет права ронять сессию агента
        print(f"Студия не запустилась: {e}")
    sys.exit(0)
