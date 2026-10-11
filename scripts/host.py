"""Mac или Windows: всё, что зависит от системы, — в одном месте.

Проект работает на обеих системах. Различия здесь, а не размазаны по скриптам:
путь к питону окружения, «показать файл» (Finder или Проводник), фоновый процесс без
окна, остановка процесса со всеми его детьми, замок файла, кодек по умолчанию и
кодировка вывода.

Кодировка — не мелочь. На Windows вывод в файл или канал идёт в кодировке системы
(cp1251): символов «✓», «✗», «→» в ней нет, и скрипт очереди падал бы на первом же
print. Поэтому всем питонам, которые запускает проект, ставится UTF-8 (utf8_env), а
сам скрипт при старте переключает свой вывод (utf8_console).
"""
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
ROOT = Path(__file__).resolve().parent.parent


def venv_python(root: Path = ROOT) -> Path:
    """Питон окружения проекта: .venv/bin/python на Mac, .venv\\Scripts\\python.exe на Windows."""
    return root / ".venv" / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


def utf8_env(env: dict | None = None) -> dict:
    """Окружение для дочерних питонов: ввод-вывод и файлы по умолчанию — UTF-8."""
    env = dict(os.environ if env is None else env)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def utf8_console() -> None:
    """Вывод этого процесса — UTF-8, куда бы он ни шёл (консоль, файл, канал)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def detached() -> dict:
    """Аргументы Popen для фонового процесса, который переживёт родителя (сервер, очередь).

    На Mac — своя сессия процессов. На Windows — своя группа и без консоли: иначе закрытое
    окно терминала или хука уносило бы сервер с собой.
    """
    if IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS}
    return {"start_new_session": True}


def own_group() -> dict:
    """Аргументы Popen для процесса, которого потом гасят вместе с детьми (мозг)."""
    if IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def kill_tree(pid: int) -> None:
    """Погасить процесс и всё, что он запустил."""
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def reveal(path: Path) -> None:
    """Показать файл в Finder или Проводнике (папку — открыть)."""
    path = Path(path)
    if IS_MAC:
        subprocess.run(["open", "-R", str(path)] if path.is_file() else ["open", str(path)])
    elif IS_WINDOWS:
        subprocess.run(["explorer", f"/select,{path}"] if path.is_file() else ["explorer", str(path)])
    else:
        subprocess.run(["xdg-open", str(path.parent if path.is_file() else path)])


def try_lock(handle) -> bool:
    """Исключительный замок на открытый файл без ожидания. False — замок держит другой процесс.

    Держится, пока файл открыт (и снимается сам, если процесс умер). На Mac — flock,
    на Windows — msvcrt.locking на первый байт.
    """
    if IS_WINDOWS:
        import msvcrt
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def unlock(handle) -> None:
    if IS_WINDOWS:
        import msvcrt
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        return
    import fcntl
    fcntl.flock(handle, fcntl.LOCK_UN)


def tool(name: str) -> str:
    """Полный путь к программе (npx на Windows — npx.cmd) или само имя, если не нашлась."""
    return shutil.which(name) or name


def has_encoder(ffmpeg: str, name: str) -> bool:
    out = subprocess.run([ffmpeg, "-hide_banner", "-encoders"], capture_output=True,
                         encoding="utf-8", errors="replace").stdout
    return any(line.split()[1:2] == [name] for line in out.splitlines() if line.strip())


_ENCODER: dict = {}


def video_encoder(requested: str | None, ffmpeg: str) -> str:
    """Кодек H.264 для этой машины.

    «auto» (и старое «h264_videotoolbox» из пресетов) — аппаратный кодек Mac, если он
    есть: он не грузит процессор, и ноутбуком можно пользоваться, пока считается ролик.
    Иначе (Windows, Linux) — libx264, открытый программный кодек; число его потоков
    ограничено в render.vcodec, чтобы машина оставалась живой.
    """
    if requested == "libx264":
        return "libx264"
    if "videotoolbox" not in _ENCODER:
        _ENCODER["videotoolbox"] = IS_MAC and has_encoder(ffmpeg, "h264_videotoolbox")
    return "h264_videotoolbox" if _ENCODER["videotoolbox"] else "libx264"


def encoder_threads() -> int:
    """Потоков программному кодеку: все ядра, кроме двух, — машине остаётся на работу."""
    return max(1, (os.cpu_count() or 4) - 2)


def install_hint(package: str) -> str:
    """Как поставить системную программу на этой машине."""
    if IS_WINDOWS:
        return {"ffmpeg": "winget install Gyan.FFmpeg", "node": "winget install OpenJS.NodeJS.LTS"}.get(
            package, f"winget install {package}")
    return {"ffmpeg": "brew install ffmpeg-full"}.get(package, f"brew install {package}")
