#!/usr/bin/env python3
"""Фон для ролика, которого нет в свободных фото, — генерация картинки через Codex (imagegen).

Подмена фона за вырезанным человеком (kit.build_page, plate_img) обычно берёт свободное фото
(Wikimedia, Pexels). Для атмосферы и того, что не сфотографировать (Вавилон, метафора), картинку
генерирует Codex своим инструментом imagegen — через ChatGPT пользователя, около полутора минут
(Валера, 12.10.2026: «используй codex для генерации задних фонов в некоторых ситуациях»).

  .venv/bin/python scripts/gen_image.py IMG_1803 babylon "древний Вавилон на закате, ворота Иштар"

Кладёт work/<имя>/downloads/<файл>.png и рядом <файл>.md: что, когда, с каким описанием —
это не фото, в ролике оно фон-иллюстрация, а не документ. Правила для запроса (без людей, без
надписей, спокойный центр под человека, вертикаль) добавляются сами. Реальных людей, логотипы
и «документы» не генерировать.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import host
from brain import clean_env, find_binary
from common import ROOT, WORK_DIR, ffprobe_bin

RULES = ("вертикальный кадр 9:16; без людей и без лиц; без надписей, букв, цифр и логотипов; "
         "центр кадра спокойный, без мелких деталей — там будет стоять человек; мягкий свет, без пересвета")
TIMEOUT = 360


def generated_dir() -> Path:
    """Куда imagegen Codex кладёт картинки: <CODEX_HOME или ~/.codex>/generated_images."""
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "generated_images"


def collect(out: Path, started: float, folder: Path | None = None) -> bool:
    """Картинка на месте? Codex то копирует её по просьбе, то только называет свой путь —
    тогда берём самую свежую из generated_images, созданную за этот запуск."""
    if out.exists() and out.stat().st_size:
        return True
    folder = folder or generated_dir()
    fresh = [f for f in folder.rglob("*") if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
             and f.stat().st_mtime >= started - 1] if folder.exists() else []
    if not fresh:
        return False
    shutil.copy2(max(fresh, key=lambda f: f.stat().st_mtime), out)
    return True


def build_prompt(description: str, out: Path) -> str:
    rel = out.relative_to(ROOT).as_posix()
    return (f"Сгенерируй ОДНУ картинку инструментом генерации изображений: {description}. "
            f"Обязательно: {RULES}. Сохрани файл в {rel} и в конце напиши только путь к файлу.")


def check_image(path: Path) -> tuple:
    """(годится ли как вертикальный фон, подробности): не меньше 720 px по ширине, пропорции ~9:16."""
    if not path.exists() or path.stat().st_size == 0:
        return False, "файла нет"
    out = subprocess.run([ffprobe_bin(), "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                          str(path)], capture_output=True, encoding="utf-8", errors="replace").stdout.strip()
    try:
        width, height = (int(x) for x in out.split(",")[:2])
    except ValueError:
        return False, "это не картинка"
    ratio = width / height
    ok = width >= 720 and 0.50 <= ratio <= 0.62
    return ok, f"{width}×{height}" + ("" if ok else " — нужна вертикаль ~9:16 от 720 px по ширине")


def main():
    ap = argparse.ArgumentParser(description="Фон для ролика через Codex (imagegen)")
    ap.add_argument("stem", help="ролик: IMG_1803")
    ap.add_argument("name", help="имя файла без расширения: babylon")
    ap.add_argument("description", help="что на фоне, по-русски")
    ap.add_argument("--force", action="store_true", help="перезаписать уже сгенерированный")
    args = ap.parse_args()

    out = WORK_DIR / args.stem / "downloads" / f"{args.name}.png"
    if out.exists() and not args.force:
        sys.exit(f"✗ {out.relative_to(ROOT)} уже есть — возьми его или запусти с --force")
    codex = find_binary("codex")
    if not codex:
        sys.exit("✗ Codex не найден: поставь его и войди (codex login) — или возьми свободное фото "
                 "(Wikimedia Commons, Pexels)")
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"  → генерирую фон «{args.description}» через Codex (около полутора минут)", flush=True)
    started = time.time()
    with tempfile.TemporaryFile() as err:
        try:
            done = subprocess.run([codex, "exec", "--skip-git-repo-check", "--sandbox", "workspace-write",
                                   build_prompt(args.description, out)],
                                  cwd=ROOT, env=host.utf8_env(clean_env()), stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=err, timeout=TIMEOUT)
            code = done.returncode
        except subprocess.TimeoutExpired:
            code = None
        err.seek(0)
        tail = err.read().decode("utf-8", "replace").strip().splitlines()[-6:]
    ok, detail = check_image(out) if collect(out, started) else (False, "картинки нет ни по пути, ни у Codex")
    if code != 0 or not ok:
        why = "не уложился в 6 минут" if code is None else f"код {code}" if code else detail
        sys.exit(f"✗ фон не получился ({why}). Вывод Codex:\n" + "\n".join(tail))
    out.with_suffix(".md").write_text(
        f"# {out.name}\n\nСгенерировано Codex (imagegen, через ChatGPT) {time.strftime('%d.%m.%Y %H:%M')}.\n"
        f"Описание: {args.description}\nПравила запроса: {RULES}\n\n"
        "Это не фото: в ролике — фон-иллюстрация, а не документ.\n", encoding="utf-8")
    print(f"  ✓ {out.relative_to(ROOT)} ({detail}) за {time.time() - started:.0f} с")


if __name__ == "__main__":
    main()
