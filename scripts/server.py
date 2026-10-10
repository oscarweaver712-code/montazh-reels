#!/usr/bin/env python3
"""Локальный веб-интерфейс монтажа. Поднимается на этой машине, наружу не смотрит.

  .venv/bin/python scripts/server.py     → http://127.0.0.1:8765

  /        студия: ролики, бриф и стили, очередь, мозг (Claude или Codex) — web/studio.html
  /quick   быстрая панель: рез пауз, субтитры, голос — web/index.html

Сервер умеет запускать агента с правом править файлы, поэтому он закрыт от чужих
страниц: принимает запросы только на 127.0.0.1/localhost (защита от DNS rebinding), а
всё, что что-то меняет (POST), — только с ключом, который знает лишь наша страница.
Чужой сайт в соседней вкладке ключ не прочтёт: страницы с другого адреса браузер
к ответам не пускает, а заголовок с ключом без нашего разрешения не отправит.
"""
import asyncio
import json
import secrets
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (FONT_DIR, INPUT_DIR, OUTPUT_DIR, PRESET_DIR, ROOT,
                    ffmpeg_bin, ffprobe_bin, load_preset, probe)
import studio_api

WEB_DIR = ROOT / "web"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv"}
TOKEN = secrets.token_urlsafe(24)         # новый на каждый запуск сервера
LOCAL_HOSTS = ("127.0.0.1", "localhost")

app = FastAPI(title="Монтаж Reels")
app.include_router(studio_api.router)
jobs: dict[str, dict] = {}


@app.middleware("http")
async def local_only(request: Request, call_next):
    """Только эта машина и только наша страница: Host, Origin и ключ на изменения."""
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
    if host not in LOCAL_HOSTS:
        return JSONResponse({"error": "студия отвечает только на 127.0.0.1"}, status_code=403)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).hostname not in LOCAL_HOSTS:
            return JSONResponse({"error": "запрос с чужой страницы"}, status_code=403)
        if not secrets.compare_digest(request.headers.get("x-studio-token", ""), TOKEN):
            return JSONResponse({"error": "нет ключа студии — обнови страницу"}, status_code=403)
    return await call_next(request)


def page(name: str) -> str:
    """Страница с ключом студии: без него её запросы на изменения не пройдут."""
    html = (WEB_DIR / name).read_text(encoding="utf-8")
    tag = f'<script>window.STUDIO_TOKEN = "{TOKEN}";</script>'
    return html.replace("<head>", "<head>\n  " + tag, 1)


@app.get("/", response_class=HTMLResponse)
def index():
    return page("studio.html")


@app.get("/quick", response_class=HTMLResponse)
def quick():
    return page("index.html")


@app.get("/api/state")
def state():
    """Исходники, готовые ролики и текущие настройки — всё, что нужно странице при загрузке."""
    def describe(path: Path, folder: str):
        item = {"name": path.name, "size_mb": round(path.stat().st_size / 1_048_576, 1),
                "folder": folder, "mtime": path.stat().st_mtime}
        try:
            info = probe(path)
            item["duration"] = round(info["duration"], 1)
            item["vertical"] = info["vertical"]
        except Exception:
            item["duration"] = None
            item["vertical"] = True
        return item

    inputs = sorted((p for p in INPUT_DIR.glob("*") if p.suffix.lower() in VIDEO_EXT),
                    key=lambda p: -p.stat().st_mtime)
    outputs = sorted((p for p in OUTPUT_DIR.glob("*") if p.suffix.lower() in VIDEO_EXT),
                     key=lambda p: -p.stat().st_mtime)

    return {
        "inputs": [describe(p, "input") for p in inputs],
        "outputs": [describe(p, "output") for p in outputs],
        "preset": load_preset("viral"),
    }


def forget_frames(stem: str):
    """Снимает кэш кадров: иначе новый файл со старым именем покажет чужое превью."""
    for shot in (ROOT / "work" / "frames").glob(f"{stem}_*.jpg"):
        shot.unlink(missing_ok=True)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    INPUT_DIR.mkdir(exist_ok=True)
    target = INPUT_DIR / Path(file.filename).name
    forget_frames(target.stem)
    with open(target, "wb") as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)
    return {"name": target.name}


def video_seconds(path: Path) -> float | None:
    """Длительность видео или None, если это не видео.

    Своя проверка вместо probe(): у файлов из кэша мессенджеров часто нет расширения,
    а probe() на не-видео завершает процесс — сервер обязан пережить чужой файл.
    """
    out = subprocess.run([
        ffprobe_bin(), "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_type:format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], capture_output=True, text=True).stdout.split()

    if "video" not in out:
        return None
    for token in out:
        try:
            seconds = float(token)
        except ValueError:
            continue
        if seconds > 0.05:      # у картинки длительности нет или она в один кадр
            return seconds
    return None


def free_name(name: str) -> Path:
    """Имя в input/, которое ничего не затрёт: video.mp4 → video_2.mp4."""
    target = INPUT_DIR / name
    stem, suffix, n = target.stem, target.suffix, 2
    while target.exists():
        target = INPUT_DIR / f"{stem}_{n}{suffix}"
        n += 1
    return target


def import_local_file(raw: str) -> dict:
    """Кладёт в input/ файл, который перетащили ссылкой, а не содержимым.

    Telegram и Почта отдают браузеру путь к файлу, а не сам файл: страница по такому
    пути прочитать ничего не может, а сервер может — он на этой же машине.
    """
    raw = (raw or "").strip()
    if not raw:
        return {"error": "пустой путь"}

    if raw.startswith("file:"):
        raw = unquote(urlparse(raw).path)
    source = Path(raw).expanduser()

    if not source.is_file():
        return {"error": f"по этому пути файла нет: {source}"}
    if source.parent == INPUT_DIR:
        return {"name": source.name}          # уже лежит где надо, копировать нечего

    if video_seconds(source) is None:
        return {"error": f"это не видео: {source.name}"}

    INPUT_DIR.mkdir(exist_ok=True)
    # файл из кэша мессенджера бывает без расширения — иначе пайплайн его не увидит
    name = source.name if source.suffix.lower() in VIDEO_EXT else source.stem + ".mp4"
    target = free_name(name)
    shutil.copy2(source, target)
    return {"name": target.name}


@app.post("/api/import-path")
def import_path(path: str = Form(...)):
    return import_local_file(path)


@app.post("/api/render")
def start_render(
    video: str = Form(...),
    max_silence: float = Form(0.28),
    font_size: int = Form(92),
    margin_v: int = Form(420),
    words_per_phrase: int = Form(3),
    color_active: str = Form("FFE24B"),
    font: str = Form("Montserrat ExtraBold"),
    subs: bool = Form(True),
    motion: bool = Form(True),
    cut: bool = Form(True),
    audio_fix: bool = Form(True),
    denoise: bool = Form(True),
    normalize: bool = Form(True),
    remove_fillers: bool = Form(True),
    hook: str = Form(""),
    quality: str = Form("fast"),
):
    """Собирает пресет из настроек UI и запускает пайплайн отдельным процессом."""
    source = INPUT_DIR / Path(video).name
    if not source.exists():
        return {"error": f"файл не найден: {video}"}

    preset = load_preset("viral")
    preset["cut"]["enabled"] = cut
    preset["cut"]["max_silence"] = max_silence
    preset["cut"]["remove_fillers"] = remove_fillers
    preset["audio"]["enabled"] = audio_fix
    preset["audio"]["normalize"] = normalize
    preset["subs"]["enabled"] = subs
    preset["subs"]["font_size"] = font_size
    preset["subs"]["margin_v"] = margin_v
    preset["subs"]["words_per_phrase"] = words_per_phrase
    preset["subs"]["color_active"] = color_active.lstrip("#").upper()
    preset["subs"]["font"] = font
    preset["motion"]["punch_in"] = motion
    preset["audio"]["denoise"] = denoise
    preset["video"]["encoder"] = "libx264" if quality == "best" else "h264_videotoolbox"

    (PRESET_DIR / "_ui.json").write_text(
        json.dumps(preset, ensure_ascii=False, indent=1), encoding="utf-8")

    cmd = [sys.executable, "-u", "scripts/reels.py", str(source), "--preset", "_ui"]
    if hook.strip():
        cmd += ["--hook", hook.strip()]

    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {"cmd": cmd, "video": source.name, "done": False, "output": None}
    return {"job_id": job_id}


@app.get("/api/stream/{job_id}")
async def stream(job_id: str):
    """Прогресс идёт в браузер построчно, по мере работы пайплайна."""
    job = jobs.get(job_id)
    if not job:
        return StreamingResponse(iter(["data: {\"error\": \"задача не найдена\"}\n\n"]),
                                 media_type="text/event-stream")

    async def events():
        proc = await asyncio.create_subprocess_exec(
            *job["cmd"], cwd=ROOT,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            line = raw.decode("utf-8", "replace").rstrip()
            # прогресс-бары загрузчика моделей в интерфейсе только мешают
            if not line or "it/s]" in line or "%|" in line or line.startswith("Fetching"):
                continue
            yield f"data: {json.dumps({'line': line}, ensure_ascii=False)}\n\n"

        await proc.wait()
        job["done"] = True

        produced = None
        if proc.returncode == 0:
            stem = Path(job["video"]).stem
            candidate = OUTPUT_DIR / f"{stem}_reels.mp4"
            if candidate.exists():
                produced = candidate.name
                job["output"] = produced

        payload = {"finished": True, "code": proc.returncode, "output": produced}
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/video/{folder}/{name}")
def serve_video(folder: str, name: str):
    base = OUTPUT_DIR if folder == "output" else INPUT_DIR
    path = base / Path(name).name
    if not path.exists():
        return {"error": "нет файла"}
    return FileResponse(path, media_type="video/mp4")


FONT_EXT = {".ttf", ".otf"}


def font_info(path: Path) -> dict | None:
    """Имя семейства (по нему libass ищет шрифт) и наличие кириллицы."""
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(path, fontNumber=0, lazy=True)
        family = f["name"].getDebugName(1) or path.stem
        cmap = f.getBestCmap()
        # без кириллицы русские субтитры превратятся в пустые квадраты
        cyrillic = all(ord(c) in cmap for c in "АЖЁЫЭЮЯёщ")
        f.close()
        return {"file": path.name, "family": family, "cyrillic": cyrillic}
    except Exception:
        return None


@app.get("/api/fonts")
def fonts():
    found = []
    for p in sorted(FONT_DIR.glob("*")):
        if p.suffix.lower() in FONT_EXT and "-var" not in p.stem:
            info = font_info(p)
            if info:
                found.append(info)
    return {"fonts": found}


@app.get("/api/font")
def font(file: str = "Montserrat-ExtraBold.ttf"):
    """Отдаёт шрифт странице — превью набирается ровно тем, что уйдёт в видео."""
    path = FONT_DIR / Path(file).name
    if not path.exists() or path.suffix.lower() not in FONT_EXT:
        path = FONT_DIR / "Montserrat-ExtraBold.ttf"
    media = "font/otf" if path.suffix.lower() == ".otf" else "font/ttf"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "max-age=3600"})


@app.post("/api/upload-font")
async def upload_font(file: UploadFile = File(...)):
    name = Path(file.filename).name
    if Path(name).suffix.lower() not in FONT_EXT:
        return {"error": "нужен файл .ttf или .otf"}

    FONT_DIR.mkdir(parents=True, exist_ok=True)
    target = FONT_DIR / name
    with open(target, "wb") as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)

    info = font_info(target)
    if not info:
        target.unlink(missing_ok=True)
        return {"error": "не удалось прочитать шрифт — похоже, файл повреждён"}
    return info


@app.get("/api/frame/{name}")
def frame(name: str, at: float = 0.35, folder: str = "input"):
    """Кадр из видео для превью: субтитры видно на реальной картинке, а не на заглушке."""
    base = OUTPUT_DIR if folder == "output" else INPUT_DIR
    video = base / Path(name).name
    if not video.exists():
        return {"error": "нет файла"}

    at = min(max(at, 0.0), 0.99)
    cache_dir = ROOT / "work" / "frames"
    cache_dir.mkdir(parents=True, exist_ok=True)
    shot = cache_dir / f"{video.stem}_{int(at * 100):03d}.jpg"

    if not shot.exists():
        try:
            seconds = probe(video)["duration"] * at
        except Exception:
            seconds = 1.0
        subprocess.run([
            ffmpeg_bin(), "-y", "-loglevel", "error", "-ss", f"{seconds:.2f}",
            "-i", str(video), "-frames:v", "1", "-vf", "scale=540:-2",
            "-q:v", "4", str(shot),
        ], capture_output=True)

    if not shot.exists():
        return {"error": "не удалось вытащить кадр"}
    return FileResponse(shot, media_type="image/jpeg")


@app.get("/api/phrase/{name}")
def phrase(name: str, count: int = 6):
    """Настоящие слова из его речи — длина слов важна для оценки вёрстки субтитров."""
    path = ROOT / "work" / f"{Path(name).stem}.words.json"
    if not path.exists():
        return {"words": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    words = [w["word"].strip() for w in data.get("words", []) if w.get("word")]
    # берём кусок из середины: там обычно содержательная речь, а не приветствие
    start = max(0, len(words) // 3)
    return {"words": words[start:start + count]}


@app.get("/api/plan/{stem}")
def plan(stem: str):
    path = ROOT / "work" / f"{Path(stem).stem}.plan.json"
    if not path.exists():
        return {"error": "нет карты реза"}
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/reveal")
def reveal(name: str = Form(...), folder: str = Form("output")):
    base = OUTPUT_DIR if folder == "output" else INPUT_DIR
    path = base / Path(name).name
    if path.exists():
        subprocess.run(["open", "-R", str(path)])
    return {"ok": True}


@app.post("/api/delete")
def delete(name: str = Form(...), folder: str = Form("output")):
    base = OUTPUT_DIR if folder == "output" else INPUT_DIR
    path = base / Path(name).name
    if not path.exists() or path.suffix.lower() not in VIDEO_EXT:
        return {"ok": False, "error": f"нечего удалять: {path.name}"}

    path.unlink()
    forget_frames(path.stem)
    # транскрипт (work/*.words.json) остаётся: он считается минутами, файл — килобайты
    return {"ok": True, "name": path.name}


@app.post("/api/save-preset")
def save_preset():
    """Настройки из UI закрепляются как основной пресет (их же использует CLI)."""
    ui = PRESET_DIR / "_ui.json"
    if ui.exists():
        shutil.copy2(ui, PRESET_DIR / "viral.json")
        return {"ok": True}
    return {"ok": False, "error": "нечего сохранять — сначала смонтируй ролик"}


if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"\n  Монтаж Reels → http://127.0.0.1:{port}\n  Ctrl+C чтобы остановить\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
