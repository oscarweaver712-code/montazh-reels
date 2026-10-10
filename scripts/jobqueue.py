#!/usr/bin/env python3
"""Очередь тяжёлых задач для пакетного монтажа: строго по одной, в порядке имён файлов.

Задача — это файл work/_queue/<приоритет>-<имя>.sh. Раннер берёт первый по имени,
запускает, пишет лог в work/_queue/logs/ и переносит файл в done/ или failed/. Пока идёт
одна задача, вторая не стартует: это правило «один тяжёлый процесс за раз» (CLAUDE.md)
для работы пачкой. Номер в начале имени — приоритет: 05-render-… обгоняет 20-prep-…,
поэтому готовые ролики выходят раньше, чем закончится подготовка остальных.

  .venv/bin/python scripts/jobqueue.py --idle 900      # живёт, пока очередь не пустует 15 мин

Каждая строка вывода — событие (старт, конец, ошибка): за ним удобно следить.

Обработчик на машине один: второй запуск видит замок (work/_queue/runner.lock) и тихо
выходит. Так студия может «будить» очередь сколько угодно раз, а тяжёлый процесс всё равно
идёт один. Что выполняется сейчас — work/_queue/current.json (его показывает студия).
"""
import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ROOT, WORK_DIR

QUEUE = WORK_DIR / "_queue"


LOCK = QUEUE / "runner.lock"
CURRENT = QUEUE / "current.json"


def next_job() -> Path | None:
    jobs = sorted(p for p in QUEUE.glob("*.sh") if p.is_file())
    return jobs[0] if jobs else None


def take_lock():
    """Замок обработчика: файл держится открытым, пока процесс жив. None — уже занят."""
    QUEUE.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK, "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def runner_alive() -> bool:
    """Живёт ли обработчик очереди (замок занят другим процессом)."""
    handle = take_lock()
    if handle is None:
        return True
    fcntl.flock(handle, fcntl.LOCK_UN)
    handle.close()
    return False


def main():
    ap = argparse.ArgumentParser(description="Очередь тяжёлых задач, по одной за раз")
    ap.add_argument("--idle", type=float, default=900, help="выйти после стольких секунд пустой очереди")
    args = ap.parse_args()

    for sub in ("logs", "done", "failed"):
        (QUEUE / sub).mkdir(parents=True, exist_ok=True)
    lock = take_lock()
    if lock is None:
        print("обработчик очереди уже работает — второй не нужен", flush=True)
        return
    CURRENT.unlink(missing_ok=True)
    print(f"очередь: {QUEUE.relative_to(ROOT)}", flush=True)

    idle_since = time.time()
    while True:
        job = next_job()
        if job is None:
            if time.time() - idle_since > args.idle:
                print("очередь пуста — выхожу", flush=True)
                return
            time.sleep(2)
            continue

        running = QUEUE / "logs" / f"{job.stem}.log"
        started = time.time()
        print(f"▶ {job.stem}", flush=True)
        CURRENT.write_text(json.dumps({"job": job.stem, "started": started, "pid": os.getpid()}),
                           encoding="utf-8")
        try:
            with open(running, "w", encoding="utf-8") as log:
                result = subprocess.run(["/bin/bash", str(job)], cwd=ROOT, stdout=log,
                                        stderr=subprocess.STDOUT)
        finally:
            CURRENT.unlink(missing_ok=True)
        spent = time.time() - started
        target = QUEUE / ("done" if result.returncode == 0 else "failed") / job.name
        shutil.move(str(job), target)
        if result.returncode == 0:
            print(f"✓ {job.stem} за {spent:.0f} с", flush=True)
        else:
            tail = running.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:]
            print(f"✗ {job.stem} упал через {spent:.0f} с: {' | '.join(tail)}", flush=True)
        idle_since = time.time()


if __name__ == "__main__":
    main()
