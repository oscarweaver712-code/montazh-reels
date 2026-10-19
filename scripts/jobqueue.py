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
      "python scripts/prep.py projects/antishkola/input/IMG_3317.MOV" "python scripts/track.py work/IMG_3317/aroll.mp4"
  .venv/bin/python scripts/jobqueue.py --idle 900      # обработчик: живёт, пока очередь не пустует 15 мин

  .venv/bin/python scripts/jobqueue.py wait 20-prep-IMG_3317   # дождаться: 0 — готово, 1 — упала

Ждать задачу — только `wait`, а не своим циклом по логу: формат лога не обещан.
`add` сам будит обработчик, если его нет. Каждая строка вывода обработчика — событие
(старт, конец, ошибка): за ним удобно следить.

Обработчик на машине один: второй запуск видит замок (work/_queue/runner.lock) и тихо
выходит. Так студия может «будить» очередь сколько угодно раз, а тяжёлый процесс всё равно
идёт один. Что выполняется сейчас — work/_queue/current.json (его показывает студия).

Идущую задачу можно остановить: кнопка «Остановить» в студии или `jobqueue.py stop`. Шаг
гасится со всеми своими процессами, задача падает с пометкой «остановлено вручную», очередь
идёт дальше. Шаг, который 15 минут не тратит ни процессора, ни вывода, считается зависшим и
гасится сам: долгий, но работающий шаг (маска часовой лекции, распознавание на процессоре)
процессор тратит всё время и под это не попадает.
"""
import argparse
import json
import os
import re
import shlex
import shutil
import signal
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
STOP = QUEUE / "stop"                    # имя задачи, которую просят остановить
HANG_SECONDS = 15 * 60                   # столько шаг может не делать ничего, прежде чем его сочтут зависшим
NAME_RE = re.compile(r"\d\d-[\w.\-]+")
SUFFIXES = (".json",) if host.IS_WINDOWS else (".json", ".sh")


def job_files(folder: Path) -> list:
    """Задачи в папке очереди (или done/, failed/), по имени.

    Только файлы с именем задачи (05-render-IMG_3317.json): «что идёт сейчас» (current.json) лежит
    рядом с ними, и студия показывала его в очереди призрачной задачей «current».
    """
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.suffix in SUFFIXES and NAME_RE.fullmatch(p.stem))


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


def request_stop(name: str, queue: Path | None = None) -> None:
    """Попросить обработчик остановить задачу (её гасит сам обработчик: процессы — его)."""
    (queue or QUEUE).mkdir(parents=True, exist_ok=True)
    ((queue or QUEUE) / "stop").write_text(name, encoding="utf-8")


def stop_requested(name: str) -> bool:
    try:
        wanted = STOP.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if wanted != name:
        return False
    STOP.unlink(missing_ok=True)
    return True


def tree_cpu(pid: int) -> float | None:
    """Процессорное время шага со всеми потомками, с. None — psutil нет, зависание не распознать."""
    try:
        import psutil
    except ImportError:
        return None
    try:
        root = psutil.Process(pid)
        tree = [root, *root.children(recursive=True)]
    except psutil.Error:
        return 0.0
    total = 0.0
    for proc in tree:
        try:
            t = proc.cpu_times()
            # children_* — уже закончившиеся дети (на Mac): иначе их время пропадало бы из суммы
            total += t.user + t.system + getattr(t, "children_user", 0.0) + getattr(t, "children_system", 0.0)
        except psutil.Error:
            pass
    return total


def stop_tree(proc: subprocess.Popen) -> None:
    """Погасить шаг со всеми потомками: сначала по-хорошему, потом наверняка.

    На Mac — SIGINT каждому процессу дерева: питон-скрипты успевают убрать временные файлы в
    finally (инвариант 5), ffmpeg дописывает и выходит. Кто не ушёл за 10 с — SIGKILL; потомки
    берутся из дерева, а не из группы, — браузер рендера живёт в своей. На Windows мягкого
    сигнала чужому процессу нет — дерево гасит taskkill.
    """
    if host.IS_WINDOWS:
        host.kill_tree(proc.pid)
    else:
        try:
            import psutil
            tree = [psutil.Process(proc.pid), *psutil.Process(proc.pid).children(recursive=True)]
        except Exception:
            tree = []
        for each in tree:
            try:
                each.send_signal(signal.SIGINT)
            except Exception:
                pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        for each in tree:
            try:
                each.kill()                 # psutil сверяет время запуска: чужой процесс не заденет
            except Exception:
                pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def run_step(argv: list, log, name: str, hang: float) -> int:
    """Один шаг: ждёт конца, кнопки «Остановить» или зависания (ни процессора, ни вывода)."""
    log.flush()
    env = host.utf8_env()
    env["REELS_QUEUE_STEP"] = "1"                 # тяжёлым скриптам: «я из очереди» (common.require_queue)
    proc = subprocess.Popen(argv, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
    cpu, size, busy = tree_cpu(proc.pid), os.fstat(log.fileno()).st_size, time.time()
    while True:
        try:
            return proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        if stop_requested(name):
            stop_tree(proc)
            log.write("\n✗ остановлено вручную — кнопкой «Остановить» в студии или jobqueue.py stop\n")
            return 130
        now_cpu, now_size = tree_cpu(proc.pid), os.fstat(log.fileno()).st_size
        if now_cpu is None:
            continue                                  # без psutil остаётся только кнопка
        if abs(now_cpu - cpu) >= 1.0 or now_size != size:
            cpu, size, busy = now_cpu, now_size, time.time()
        elif time.time() - busy > hang:
            stop_tree(proc)
            log.write(f"\n✗ шаг {hang / 60:g} мин ничего не делал — ни процессора, ни вывода: похоже, завис. "
                      "Остановлен, очередь идёт дальше.\n")
            return 124


TIMINGS = QUEUE / "timings.jsonl"


def note_timing(step: list, seconds: float) -> None:
    """Сколько шёл удачный шаг — студия по этим замерам пишет «≈ 4 мин» у шагов монтажа на этой машине."""
    script = next((Path(a).name for a in step if a.endswith(".py")), None)
    stem = next((m.group(1) for a in step for m in [re.search(r"(IMG_\d+\w*|[A-Z]+_\d+)", a)] if m), None)
    if not script:
        return
    try:
        with open(TIMINGS, "a", encoding="utf-8") as f:
            f.write(json.dumps({"script": script, "stem": stem, "hq": "--hq" in step, "seconds": round(seconds, 1),
                                "at": round(time.time())}) + "\n")
    except OSError:
        pass                                   # замер — подсказка, а не условие работы очереди


def run_job(job: Path, log) -> int:
    """Выполняет задачу; код возврата первого упавшего шага или 0."""
    if job.suffix == ".sh":
        return run_step(["/bin/bash", str(job)], log, job.stem, HANG_SECONDS)
    try:
        spec = json.loads(job.read_text(encoding="utf-8"))
        steps = [shlex.split(s) if isinstance(s, str) else list(s) for s in spec["steps"]]
        hang = float(spec.get("hang_minutes") or HANG_SECONDS / 60) * 60
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        log.write(f"✗ задача {job.name} описана с ошибкой: {e}\n")
        return 2
    code = 0
    try:
        for step in steps:
            log.write(f"$ {shlex.join(step)}\n")
            log.flush()
            try:
                began = time.time()
                code = run_step([program(step[0]), *step[1:]], log, job.stem, hang)
                if code == 0:
                    note_timing(step, time.time() - began)
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
        try:                                   # просьба остановить ту задачу, что уже кончилась
            if STOP.read_text(encoding="utf-8").strip() != name:
                STOP.unlink(missing_ok=True)
        except OSError:
            pass
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


def wait(name: str, timeout: float, queue: Path | None = None, poll: float = 5) -> int:
    """Ждёт, пока задача окажется в done/ или failed/; 0 — прошла, 1 — упала, 2 — её нет или не дождался.

    Агенты ждали задачу самодельным циклом по логу («until grep ^exit …») — такой строки обработчик не
    пишет, и ход ИИ по IMG_3292 (17.10.2026) крутился после готового рендера, пока его не погасили руками.
    """
    queue = queue or QUEUE
    deadline = time.time() + timeout
    while True:
        # задача ещё в очереди — ждём её, даже если в done/ лежит прошлая с тем же именем: 19.10.2026
        # 05-render-IMG_3292 от v2 лежал в done/, и wait нового рендера сразу отдал старый итог
        if any(p.stem == name for p in job_files(queue)):
            if time.time() > deadline:
                print(f"✗ {name} ещё идёт — не дождался за {timeout / 60:g} мин; позови wait снова")
                return 2
            time.sleep(poll)
            continue
        for state, code in (("done", 0), ("failed", 1)):
            found = [p for p in job_files(queue / state) if p.stem == name]
            if found:
                log = queue / "logs" / f"{name}.log"
                try:
                    tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-12:]
                except OSError:
                    tail = []
                print("\n".join(tail))
                print(f"{'✓' if code == 0 else '✗'} {name}: {'готово' if code == 0 else 'упала'} (лог — {log.relative_to(ROOT) if log.is_relative_to(ROOT) else log})")
                return code
        print(f"✗ задачи {name} нет ни в очереди, ни в done/, ни в failed/ — проверь имя")
        return 2


def main():
    ap = argparse.ArgumentParser(description="Очередь тяжёлых задач, по одной за раз")
    sub = ap.add_subparsers(dest="cmd")
    add = sub.add_parser("add", help="положить задачу в очередь (и разбудить обработчик)")
    add.add_argument("name", help="<две цифры>-<имя>: 05-render-IMG_3317, 20-prep-IMG_3317")
    add.add_argument("steps", nargs="+", help="шаги — каждый одной строкой: \"python scripts/prep.py projects/<проект>/input/X.MOV\"")
    add.add_argument("--no-wake", action="store_true", help="не будить обработчик")
    sub.add_parser("stop", help="остановить задачу, которая выполняется сейчас")
    w = sub.add_parser("wait", help="дождаться задачи: выход 0 — готово, 1 — упала, 2 — нет такой или не дождался")
    w.add_argument("name", help="имя задачи, как в add: 05-render-IMG_3317")
    w.add_argument("--timeout", type=float, default=50, help="минут ждать (по умолчанию 50)")
    ap.add_argument("--idle", type=float, default=900, help="выйти после стольких секунд пустой очереди")
    args = ap.parse_args()

    if args.cmd == "wait":
        sys.exit(wait(args.name, args.timeout * 60))
    if args.cmd == "stop":
        try:
            name = json.loads(CURRENT.read_text(encoding="utf-8"))["job"]
        except (OSError, ValueError, KeyError):
            sys.exit("сейчас ничего не выполняется")
        request_stop(name)
        print(f"✓ попросил остановить {name}: задача упадёт с пометкой «остановлено вручную», очередь пойдёт дальше")
        return
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
