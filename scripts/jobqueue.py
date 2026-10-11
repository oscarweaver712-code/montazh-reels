#!/usr/bin/env python3
"""Очередь тяжёлых задач для пакетного монтажа: строго по одной, в порядке имён файлов.

Задача — файл work/_queue/<приоритет>-<имя>.json: список шагов, каждый шаг — команда
списком слов. Раннер берёт первую задачу по имени, выполняет шаги по порядку (упал шаг —
задача упала, следующие шаги не идут), пишет лог в work/_queue/logs/ и переносит файл в
done/ или failed/. Пока идёт одна задача, вторая не стартует: это правило «один тяжёлый
процесс за раз» (AGENTS.md) для работы пачкой. Номер в начале имени — приоритет: 05-render-…
обгоняет 20-prep-…, поэтому готовые ролики выходят раньше, чем закончится подготовка остальных.

Задачи — JSON, а не скрипты оболочки: одна и та же задача идёт на Mac и на Windows, и
никакие кавычки в именах файлов её не ломают. «python» в шаге — питон окружения проекта.
Старые задачи .sh (до 11.10.2026) на Mac всё ещё выполняются через bash.

  .venv/bin/python scripts/jobqueue.py add 20-prep-IMG_3317 \\
      "python scripts/prep.py input/IMG_3317.MOV" "python scripts/track.py work/IMG_3317/aroll.mp4"
  .venv/bin/python scripts/jobqueue.py --idle 900      # обработчик: живёт, пока очередь не пустует 15 мин

`add` сам будит обработчик, если его нет. Каждая строка вывода обработчика — событие
(старт, конец, ошибка): за ним удобно следить.

Обработчик на машине один: второй запуск видит замок (work/_queue/runner.lock) и тихо
выходит. Так студия может «будить» очередь сколько угодно раз, а тяжёлый процесс всё равно
идёт один. Что выполняется сейчас — work/_queue/current.json (его показывает студия).
"""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import host
from common import ROOT, VENV_PY, WORK_DIR

QUEUE = WORK_DIR / "_queue"
LOCK = QUEUE / "runner.lock"
CURRENT = QUEUE / "current.json"
NAME_RE = re.compile(r"\d\d-[\w.\-]+")
SUFFIXES = (".json",) if host.IS_WINDOWS else (".json", ".sh")


def job_files(folder: Path) -> list:
    """Задачи в папке очереди (или done/, failed/), по имени."""
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.suffix in SUFFIXES and not p.name.startswith("."))


def find_job(folder: Path, name: str) -> Path | None:
    for suffix in SUFFIXES:
        path = folder / f"{name}{suffix}"
        if path.exists():
            return path
    return None


def next_job() -> Path | None:
    jobs = job_files(QUEUE)
    return jobs[0] if jobs else None


def write_job(name: str, steps: list, cleanup: list | None = None, title: str = "",
              queue: Path | None = None) -> Path:
    """Кладёт задачу в очередь. Файл появляется целиком: недописанную обработчик не возьмёт."""
    queue = queue or QUEUE
    if not NAME_RE.fullmatch(name):
        raise ValueError(f"Плохое имя задачи «{name}»: нужно <две цифры>-<имя>, например 20-prep-IMG_3317")
    if not steps or not all(isinstance(s, list) and s and all(isinstance(w, str) for w in s) for s in steps):
        raise ValueError("Шаги задачи — списки слов команды, хотя бы один")
    queue.mkdir(parents=True, exist_ok=True)
    if find_job(queue, name):
        raise FileExistsError(f"Задача {name} уже в очереди")
    path = queue / f"{name}.json"
    tmp = queue / f".{name}.json.tmp"
    tmp.write_text(json.dumps({"title": title, "steps": steps, "cleanup": cleanup or []},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
    return path


def program(word: str) -> str:
    """«python» — питон окружения проекта; npx, node и прочее — полный путь (на Windows npx.cmd)."""
    if word == "python":
        return str(VENV_PY if VENV_PY.exists() else Path(sys.executable))
    return host.tool(word)


def run_job(job: Path, log) -> int:
    """Выполняет задачу; код возврата первого упавшего шага или 0."""
    if job.suffix == ".sh":
        return subprocess.run(["/bin/bash", str(job)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                              env=host.utf8_env()).returncode
    try:
        spec = json.loads(job.read_text(encoding="utf-8"))
        steps = [shlex.split(s) if isinstance(s, str) else list(s) for s in spec["steps"]]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        log.write(f"✗ задача {job.name} описана с ошибкой: {e}\n")
        return 2
    code = 0
    try:
        for step in steps:
            log.write(f"$ {shlex.join(step)}\n")
            log.flush()
            try:
                code = subprocess.run([program(step[0]), *step[1:]], cwd=ROOT, stdout=log,
                                      stderr=subprocess.STDOUT, env=host.utf8_env()).returncode
            except OSError as e:
                log.write(f"✗ не запустилось «{step[0]}»: {e}\n")
                code = 127
            if code != 0:
                break
    finally:
        # временное задачи (файл настроек панели и т.п.) — только внутри work/
        for rel in spec.get("cleanup") or []:
            path = (ROOT / rel).resolve()
            if path.is_relative_to(WORK_DIR.resolve()) and path.is_file():
                path.unlink(missing_ok=True)
    return code


def take_lock(owner: bool = True, tries: int = 1):
    """Замок обработчика: файл держится открытым, пока процесс жив. None — уже занят.

    owner=False — только проверить замок: номер процесса в файле не переписывается
    (раньше там оказывался номер сервера студии, который просто спрашивал).
    tries — сколько раз попробовать: студия проверяет замок, взяв его на миг, и
    обработчик, стартовавший ровно в этот миг, иначе решал, что второй уже работает.
    """
    QUEUE.mkdir(parents=True, exist_ok=True)
    for attempt in range(tries):
        handle = open(LOCK, "a+", encoding="utf-8")
        if not host.try_lock(handle):
            handle.close()
            if attempt + 1 < tries:
                time.sleep(0.25)
            continue
        if owner:
            handle.seek(0)
            handle.truncate()
            handle.write(str(os.getpid()))
            handle.flush()
        return handle
    return None


def runner_alive() -> bool:
    """Живёт ли обработчик очереди (замок занят другим процессом)."""
    handle = take_lock(owner=False)
    if handle is None:
        return True
    host.unlock(handle)
    handle.close()
    return False


def wake(idle: float = 1800) -> bool:
    """Запускает обработчик в фоне, если его нет. Второго он сам не допустит (замок)."""
    if runner_alive():
        return False
    QUEUE.mkdir(parents=True, exist_ok=True)
    with open(QUEUE / "runner.out", "a", encoding="utf-8") as out:   # у обработчика своя копия
        subprocess.Popen([program("python"), "-u", str(ROOT / "scripts" / "jobqueue.py"), "--idle", str(idle)],
                         cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         env=host.utf8_env(clean_session_env()), **host.detached())
    return True


def clean_session_env() -> dict:
    """Окружение без следов сессии агента, из которой будят очередь (см. brain.SESSION_VARS)."""
    from brain import clean_env
    return clean_env()


def serve(idle: float) -> None:
    for sub in ("logs", "done", "failed"):
        (QUEUE / sub).mkdir(parents=True, exist_ok=True)
    lock = take_lock(tries=5)
    if lock is None:
        print("обработчик очереди уже работает — второй не нужен", flush=True)
        return
    CURRENT.unlink(missing_ok=True)
    print(f"очередь: {QUEUE.relative_to(ROOT)}", flush=True)

    idle_since = time.time()
    while True:
        job = next_job()
        if job is None:
            if time.time() - idle_since > idle:
                print("очередь пуста — выхожу", flush=True)
                return
            time.sleep(2)
            continue

        name = job.stem
        running = QUEUE / "logs" / f"{name}.log"
        started = time.time()
        print(f"▶ {name}", flush=True)
        CURRENT.write_text(json.dumps({"job": name, "started": started, "pid": os.getpid()}),
                           encoding="utf-8")
        try:
            with open(running, "w", encoding="utf-8") as log:
                code = run_job(job, log)
        finally:
            CURRENT.unlink(missing_ok=True)
        spent = time.time() - started
        target = QUEUE / ("done" if code == 0 else "failed") / job.name
        shutil.move(str(job), target)
        if code == 0:
            print(f"✓ {name} за {spent:.0f} с", flush=True)
        else:
            tail = running.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:]
            print(f"✗ {name} упал через {spent:.0f} с: {' | '.join(tail)}", flush=True)
        idle_since = time.time()


def main():
    ap = argparse.ArgumentParser(description="Очередь тяжёлых задач, по одной за раз")
    sub = ap.add_subparsers(dest="cmd")
    add = sub.add_parser("add", help="положить задачу в очередь (и разбудить обработчик)")
    add.add_argument("name", help="<две цифры>-<имя>: 05-render-IMG_3317, 20-prep-IMG_3317")
    add.add_argument("steps", nargs="+", help="шаги — каждый одной строкой: \"python scripts/prep.py input/X.MOV\"")
    add.add_argument("--no-wake", action="store_true", help="не будить обработчик")
    ap.add_argument("--idle", type=float, default=900, help="выйти после стольких секунд пустой очереди")
    args = ap.parse_args()

    if args.cmd == "add":
        try:
            path = write_job(args.name, [shlex.split(s) for s in args.steps])
        except (ValueError, FileExistsError) as e:
            sys.exit(f"✗ {e}")
        woke = False if args.no_wake else wake()
        print(f"✓ в очереди: {path.relative_to(ROOT)}" + (" — обработчик запущен" if woke else ""))
        return
    serve(args.idle)


if __name__ == "__main__":
    main()
