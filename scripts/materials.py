#!/usr/bin/env python3
"""Материалы ролика: какие картинки, звуки и видео стоят в монтаже, откуда они — и свои файлы человека.

Валера, 16.10.2026: «в рамках монтажа конкретного видео видеть материалы — фото, сгенерированные
Codex, добавленные фото, аудио — чтобы было понятно, что тут использовано; и самому положить кусочек
в материалы и сказать ИИ "вот тут используй это"».

  work/<имя>/materials/            что положил человек (фото, видео, звук) — монтаж их не удаляет
  work/<имя>/materials/materials.json   замеры: размер картинки, длительность и громкость звука

Откуда взялось то, что уже в ролике, читается по самой странице studio/<имя>/index.html:
  assets/materials/…  — положил человек;
  assets/img/…        — рядом <файл>.md в work/<имя>/downloads/ → сгенерировано (gen_image.py, Codex),
                        запись в downloads/candidates.json → найдено ИИ (лицензия и источник оттуда);
  assets/sfx/…        — библиотека звуков presets/sfx; assets/manim/… — анимация ManimGX.

В странице картинка материала — assets/img/<имя> (compose.py копирует её туда же, где все картинки),
звук — kit.material_audio(…) (громкость по замеру, как у библиотеки), видео — assets/materials/<имя>.

  .venv/bin/python scripts/materials.py IMG_1799        # что в ролике и что лежит без дела
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ROOT, WORK_DIR, ffmpeg_bin, ffprobe_bin  # noqa: E402

KINDS = {
    "image": {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"},
    "audio": {".mp3", ".wav", ".m4a", ".aac", ".ogg"},
    "video": {".mp4", ".mov", ".m4v", ".webm"},
}
KIND_RU = {"image": "фото", "audio": "звук", "video": "видео"}
MANIFEST = "materials.json"


class MaterialError(Exception):
    """Понятная ошибка о материале — для человека."""


def folder(stem: str) -> Path:
    return WORK_DIR / stem / "materials"


def kind_of(name: str) -> str | None:
    ext = Path(name).suffix.lower()
    return next((k for k, exts in KINDS.items() if ext in exts), None)


def safe_name(name: str) -> str:
    """Имя файла без пути и без символов, которые ломают разметку страницы (кавычки, пробелы — в «_»)."""
    base = Path(name.replace("\\", "/")).name
    stem, ext = Path(base).stem, Path(base).suffix.lower()
    stem = re.sub(r"[^\w.\-]+", "_", stem, flags=re.UNICODE).strip("._") or "material"
    return f"{stem[:60]}{ext}"


def measure(path: Path, kind: str | None = None) -> dict:
    """Размер картинки или видео, длительность, громкость звука (пиковая мгновенная, как у presets/sfx).

    kind — по настоящему имени: недокачанный файл лежит под .part, и по нему тип не узнать.
    """
    kind = kind or kind_of(path.name)
    info = {"kind": kind}
    if kind in ("image", "video") and Path(path.name.removesuffix(".part")).suffix.lower() != ".svg":
        out = subprocess.run([ffprobe_bin(), "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=width,height", "-of", "csv=p=0", str(path)],
                             capture_output=True, encoding="utf-8", errors="replace").stdout.strip()
        try:
            info["width"], info["height"] = (int(x) for x in out.split(",")[:2])
        except ValueError:
            raise MaterialError(f"{path.name}: не открывается как {KIND_RU[kind]} — файл битый или это не {KIND_RU[kind]}")
    if kind in ("audio", "video"):
        out = subprocess.run([ffprobe_bin(), "-v", "error", "-show_entries", "format=duration", "-of",
                              "default=nw=1:nk=1", str(path)],
                             capture_output=True, encoding="utf-8", errors="replace").stdout.strip()
        try:
            info["duration"] = round(float(out), 2)
        except ValueError:
            raise MaterialError(f"{path.name}: не читается длительность — файл битый?")
    if kind == "audio":
        err = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-af", "apad=pad_dur=1,ebur128",
                              "-f", "null", "-"], capture_output=True, encoding="utf-8", errors="replace").stderr
        levels = [float(x) for x in re.findall(r"M:\s*(-?[\d.]+)", err)]
        if not levels:
            raise MaterialError(f"{path.name}: не удалось замерить громкость — в файле нет звука?")
        info["loudness_m"] = round(max(levels), 1)
    return info


def manifest(stem: str) -> dict:
    path = folder(stem) / MANIFEST
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _save_manifest(stem: str, data: dict) -> None:
    path = folder(stem) / MANIFEST
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def add(stem: str, name: str, source: Path) -> dict:
    """Положить файл в материалы ролика. Имя занято — рядом с номером, не поверх. Не тот тип — отказ."""
    name = safe_name(name)
    if not kind_of(name):
        raise MaterialError(f"{name}: в материалы кладутся фото, видео и звук "
                            f"({', '.join(sorted(set().union(*KINDS.values())))})")
    box = folder(stem)
    box.mkdir(parents=True, exist_ok=True)
    target, n = box / name, 2
    while target.exists():
        target = box / f"{Path(name).stem}_{n}{Path(name).suffix}"
        n += 1
    part = box / f".{target.name}.part"
    try:
        shutil.copyfile(source, part)
        info = measure(part, kind_of(target.name))
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)
    data = manifest(stem)
    data[target.name] = dict(info, added=time.time())
    _save_manifest(stem, data)
    return dict(data[target.name], name=target.name)


def remove(stem: str, name: str) -> None:
    path = folder(stem) / safe_name(name)
    if path.name != name or not path.exists():
        raise MaterialError(f"в материалах {stem} нет файла {name}")
    path.unlink()
    data = manifest(stem)
    data.pop(name, None)
    _save_manifest(stem, data)


def loudness(stem: str, name: str) -> float:
    """Громкость звука из материалов — по замеру; нет замера — меряем сейчас и запоминаем."""
    data = manifest(stem)
    if "loudness_m" not in data.get(name, {}):
        path = folder(stem) / name
        if not path.exists():
            raise MaterialError(f"звука {name} нет в work/{stem}/materials/ — положи его туда (студия: «Материалы»)")
        data[name] = dict(data.get(name, {}), **measure(path))
        _save_manifest(stem, data)
    return data[name]["loudness_m"]


def origin(stem: str, area: str, name: str) -> dict:
    """Откуда файл: положил человек, сгенерировано, найдено ИИ, библиотека звуков, анимация."""
    downloads = WORK_DIR / stem / "downloads"
    if area == "materials" and name.startswith("yt-"):
        return {"code": "library", "label": "фонотека YouTube · автора указывать не нужно",
                "detail": "условия фонотеки: только в своих роликах, отдельно не распространять (не в git)"}
    if area == "materials" or (area == "img" and (folder(stem) / name).exists()):
        return {"code": "mine", "label": "добавил ты"}
    if area == "img":
        note = downloads / f"{Path(name).stem}.md"
        if note.exists():
            lines = [x.strip() for x in note.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()]
            return {"code": "gen", "label": "сгенерировано (Codex)",
                    "detail": next((x for x in lines if not x.startswith("#")), "")[:200]}
        try:
            cand = json.loads((downloads / "candidates.json").read_text(encoding="utf-8")).get(name)
        except (OSError, json.JSONDecodeError):
            cand = None
        if cand:
            title = re.sub(r"<[^>]+>", "", str(cand.get("title", ""))).replace("File:", "").strip()
            return {"code": "found", "label": f"найдено ИИ · {cand.get('license') or 'лицензия не указана'}",
                    "detail": title[:200], "url": cand.get("url")}
        return {"code": "found", "label": "найдено ИИ"}
    if area == "sfx":
        return {"code": "library", "label": "библиотека звуков"}
    if area == "manim":
        return {"code": "anim", "label": "анимация (ManimGX)"}
    if area == "footage":
        note = WORK_DIR / stem / "footage" / f"{Path(name).stem}.md"
        lines = ([x.strip() for x in note.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()]
                 if note.exists() else [])
        return {"code": "gen", "label": "сгенерировано (Google Flow)",
                "detail": next((x for x in lines if x.startswith("Фраза:")), "")[:200]}
    return {"code": "other", "label": area}


_REF = re.compile(r'(?:src|href)="assets/(img|sfx|materials|manim|footage)/([^"]+)"')
_BLOCK = re.compile(r'<(?:div|audio|video|img)\b[^>]*\bid="([\w\-]+)"')


def used(stem: str) -> list:
    """Что стоит в странице ролика: файл, откуда он, в каком блоке. Без страницы — пусто."""
    page = ROOT / "studio" / stem / "index.html"
    if not page.exists():
        return []
    html = page.read_text(encoding="utf-8", errors="replace")
    blocks = [(m.start(), m.group(1)) for m in _BLOCK.finditer(html)]
    found = {}
    for m in _REF.finditer(html):
        area, name = m.group(1), m.group(2)
        if area == "img" and name.startswith("plate"):
            continue
        tag_start = html.rfind("<", 0, m.start())
        owner = next((bid for pos, bid in reversed(blocks) if pos <= tag_start), None)
        # картинка внутри блока графики: блок — ближайший открытый .g до неё
        g = [mm.group(1) for mm in re.finditer(r'<div id="([\w\-]+)" class="g[ "]', html[:m.start()])]
        block = g[-1] if area == "img" and g else owner
        key = f"{area}/{name}"
        item = found.setdefault(key, {"area": area, "name": name, "kind": kind_of(name) or ("audio" if area == "sfx" else "image"),
                                      "blocks": [], **origin(stem, area, name)})
        if block and block not in item["blocks"]:
            item["blocks"].append(block)
    return sorted(found.values(), key=lambda x: (x["code"] != "mine", x["kind"], x["name"]))


def listing(stem: str) -> dict:
    """{used: в ролике, unused: лежит без дела (свои материалы и найденное/сгенерированное ИИ)}."""
    in_page = used(stem)
    names = {(x["area"] if x["area"] != "img" else "img", x["name"]) for x in in_page}
    names_any = {x["name"] for x in in_page}
    unused = []
    data = manifest(stem)
    box = folder(stem)
    for path in sorted(box.iterdir()) if box.exists() else []:
        if path.name.startswith(".") or path.name == MANIFEST or not kind_of(path.name) or path.name in names_any:
            continue
        unused.append({"area": "materials", "name": path.name, "kind": kind_of(path.name),
                       **{k: v for k, v in data.get(path.name, {}).items() if k != "kind"}, **origin(stem, "materials", path.name)})
    downloads = WORK_DIR / stem / "downloads"
    for path in sorted(downloads.iterdir()) if downloads.exists() else []:
        if kind_of(path.name) == "image" and ("img", path.name) not in names:
            unused.append({"area": "img", "name": path.name, "kind": "image", **origin(stem, "img", path.name)})
    return {"used": in_page, "unused": unused}


def file_path(stem: str, area: str, name: str) -> Path:
    """Путь к файлу материала для показа в студии. Только из своих папок ролика и библиотеки."""
    name = Path(name).name
    places = {"materials": [folder(stem)], "img": [folder(stem), WORK_DIR / stem / "downloads",
                                                   ROOT / "studio" / stem / "assets" / "img"],
              "sfx": [ROOT / "presets" / "sfx"], "manim": [WORK_DIR / stem / "manim"],
              "footage": [WORK_DIR / stem / "footage"]}
    for base in places.get(area, []):
        if (base / name).is_file():
            return base / name
    raise MaterialError(f"нет файла {area}/{name} у ролика {stem}")


def context_line(stem: str) -> str:
    """Строка для мозга: что человек положил в материалы ролика и как это вставить."""
    data = manifest(stem)
    box = folder(stem)
    files = [p.name for p in sorted(box.iterdir())] if box.exists() else []
    files = [f for f in files if kind_of(f) and not f.startswith(".")]
    if not files:
        return ""
    def desc(name: str) -> str:
        info = data.get(name, {})
        bits = [KIND_RU.get(kind_of(name), "")]
        if info.get("width"):
            bits.append(f"{info['width']}×{info['height']}")
        if info.get("duration"):
            bits.append(f"{info['duration']:.1f} с")
        return f"{name} ({', '.join(b for b in bits if b)})"
    return (f"Материалы, которые человек положил к ролику (work/{stem}/materials/): " + "; ".join(desc(f) for f in files)
            + ". Просит «используй это» — вставляй именно их: картинка в странице — assets/img/<имя> (compose.py "
              "кладёт её туда), звук — kit.material_audio(id, stem, имя, старт), видео — assets/materials/<имя>.")


def main():
    if len(sys.argv) != 2:
        sys.exit("Использование: materials.py <имя ролика>")
    stem = sys.argv[1]
    data = listing(stem)
    print(f"В ролике {stem}:")
    for x in data["used"]:
        print(f"  {x['area']}/{x['name']} — {x['label']}" + (f" · блоки {', '.join(x['blocks'])}" if x["blocks"] else ""))
    if data["unused"]:
        print("Лежит без дела:")
        for x in data["unused"]:
            print(f"  {x['area']}/{x['name']} — {x['label']}")


if __name__ == "__main__":
    main()
