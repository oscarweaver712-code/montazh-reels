#!/usr/bin/env python3
"""Апрув готового ролика и уборка его копий.

Пока ролик не принят, всё лежит на случай правок: черновые версии в output/ (v1 при
готовой v2), сырые рендеры до мастеринга в studio/<имя>/renders/. Это копии одного и того же
ролика — по 100–200 МБ на версию. После апрува конечного варианта они не нужны (правило
Валеры, 11.10.2026): апрув записывается в work/<имя>/approved.json (это решение, оно в git),
а отмеченное удаляется.

Удаляется только то, что выбрали: черновики и копии отмечены сразу, промежуточные файлы
(маска, перекадрированный исходник) — нет: без них ролик всё ещё пересобирается, но вырезку
и перекадрирование пришлось бы считать заново. Исходник, дубль, решения и сам принятый
ролик не трогаются никогда.

  .venv/bin/python scripts/approve.py IMG_3317 IMG_3317_v2.mp4            # что будет удалено
  .venv/bin/python scripts/approve.py IMG_3317 IMG_3317_v2.mp4 --apply    # апрув и уборка копий
  .venv/bin/python scripts/approve.py IMG_3317 IMG_3317_v2.mp4 --apply --intermediates
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import projects
from common import ROOT, WORK_DIR, plural

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv"}
GROUPS = {
    "drafts": "Черновые версии и копии этого ролика",
    "intermediates": "Промежуточные файлы (маска, перекадрированный исходник)",
}


def studio_dir() -> Path:
    return ROOT / "studio"


def belongs(name: str, stem: str) -> bool:
    """Файл из output/ — этого ролика? IMG_32790 не принадлежит IMG_3279."""
    rest = Path(name).stem[len(stem):] if Path(name).stem.startswith(stem) else None
    return rest is not None and (rest == "" or rest[0] in "_-")


def output_dir(stem: str) -> Path:
    """output/ проекта ролика. Ролика нет ни в одном проекте — ValueError с объяснением."""
    try:
        return projects.of(stem).output
    except projects.ProjectError as e:
        raise ValueError(str(e))


def outputs(stem: str) -> list:
    return sorted(p for p in output_dir(stem).glob(f"{stem}*")
                  if p.suffix.lower() in VIDEO_EXT and not p.name.startswith(".") and belongs(p.name, stem))


def item(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)), "size": path.stat().st_size}


def plan(stem: str, final: str) -> dict:
    """Что останется и что можно удалить. Ничего не трогает."""
    approved = output_dir(stem) / Path(final).name
    if not approved.exists() or not belongs(approved.name, stem):
        raise ValueError(f"В {approved.parent.relative_to(ROOT)}/ нет ролика {final} от {stem}")
    drafts = []
    for path in outputs(stem):
        if path == approved:
            continue
        drafts.append(path)
        sheet = path.with_suffix(".sheet.jpg")
        if sheet.exists():
            drafts.append(sheet)
    # сырые рендеры до мастеринга — в проекте ролика и в проектах его вариантов
    for project in [studio_dir() / stem, *studio_dir().glob(f"{stem}--*")]:
        renders = project / "renders"
        if renders.is_dir():
            drafts += sorted(p for p in renders.iterdir() if p.is_file())
    work = WORK_DIR / stem
    intermediates = sorted([*work.glob("aroll.matte_*.mkv"), *work.glob(f"{stem}.*x*.mov")]) if work.is_dir() else []
    groups = {"drafts": [item(p) for p in drafts], "intermediates": [item(p) for p in intermediates]}
    return {"stem": stem, "file": approved.name, "keep": item(approved),
            "groups": {key: {"title": GROUPS[key], "items": items,
                             "size": sum(i["size"] for i in items), "default": key == "drafts"}
                       for key, items in groups.items()}}


def apply(stem: str, final: str, remove: list) -> dict:
    """Записывает апрув и удаляет выбранные группы. Неизвестная группа — громкая ошибка."""
    unknown = [g for g in remove if g not in GROUPS]
    if unknown:
        raise ValueError(f"Не знаю, что удалять: {', '.join(unknown)}. Есть: {', '.join(GROUPS)}")
    p = plan(stem, final)
    removed, freed = [], 0
    for key in remove:
        for entry in p["groups"][key]["items"]:
            path = ROOT / entry["path"]
            # страховка: принятый ролик, исходник и решения не удаляются ни при каком плане
            if path == ROOT / p["keep"]["path"] or path.suffix in (".json", ".py") or "input" in path.parts:
                continue
            path.unlink(missing_ok=True)
            removed.append(entry["path"])
            freed += entry["size"]
    record = {"file": p["file"], "at": time.strftime("%Y-%m-%d %H:%M"), "removed": removed}
    (WORK_DIR / stem).mkdir(parents=True, exist_ok=True)
    (WORK_DIR / stem / "approved.json").write_text(json.dumps(record, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    return {"approved": p["file"], "removed": removed, "freed": freed}


def approved(stem: str) -> dict | None:
    path = WORK_DIR / stem / "approved.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except (json.JSONDecodeError, OSError):
        return None


def mb(size: int) -> str:
    return f"{size / 1_048_576:.0f} МБ"


def main():
    ap = argparse.ArgumentParser(description="Апрув ролика и уборка его копий")
    ap.add_argument("stem", help="имя ролика, например IMG_3317")
    ap.add_argument("file", help="принятый файл из output/, например IMG_3317_v2.mp4")
    ap.add_argument("--apply", action="store_true", help="записать апрув и удалить отмеченное")
    ap.add_argument("--keep-drafts", action="store_true", help="черновики и копии не удалять")
    ap.add_argument("--intermediates", action="store_true", help="удалить ещё и маску с перекадрированием")
    args = ap.parse_args()
    if not re.fullmatch(r"[\w.\-]+", args.stem):
        sys.exit(f"✗ Плохое имя ролика: {args.stem}")
    try:
        p = plan(args.stem, args.file)
        remove = ([] if args.keep_drafts else ["drafts"]) + (["intermediates"] if args.intermediates else [])
        print(f"Апрув: {p['file']} ({mb(p['keep']['size'])}) — остаётся")
        for key, group in p["groups"].items():
            mark = "удалю" if key in remove else "оставлю"
            print(f"  {mark}: {group['title'].lower()} — {len(group['items'])} шт., {mb(group['size'])}")
            for entry in group["items"]:
                print(f"      {entry['path']}  ({mb(entry['size'])})")
        if not args.apply:
            print("\nНичего не тронуто. Записать апрув и удалить: --apply")
            return
        done = apply(args.stem, args.file, remove)
    except ValueError as e:
        sys.exit(f"✗ {e}")
    print(f"\n✓ Апрув записан в work/{args.stem}/approved.json. "
          f"Удалено {plural(len(done['removed']), 'файл', 'файла', 'файлов')}, "
          f"освобождено {mb(done['freed'])}.")


if __name__ == "__main__":
    main()
