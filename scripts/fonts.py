#!/usr/bin/env python3
"""Шрифты: где лежат и как догрузить свой — одинаково на Mac и Windows (23.10.2026).

Валера 23.10.2026: «нужна возможность догружать шрифты», «шрифты ток на маке — это плохо, нам надо унифицироваться под все
устройства». До этого шрифты заказчицы (SF Pro, Nicoletta) жили в presets/fonts мимо git, а собирал их make_fonts.py
из .dmg Apple — только на Mac; шаблон дизайн-системы на них ссылался, и на чистой Windows самопроверка краснела.

Теперь шрифт — всегда файл, системные шрифты не используются нигде. Три места, поиск по порядку:
  projects/<проект>/fonts/   шрифты бренда проекта — любой лицензии (их дал заказчик), живут с проектом, в git движка
                             не попадают (проекты — данные клиентов, scripts/clients.py)
  presets/fonts/local/       догруженные на этой машине без проекта (быстрая панель) — тоже мимо git
  presets/fonts/             шрифты движка: только OFL, с кириллицей, в git — есть на любой машине

Шрифт проекта с тем же именем файла, что у движка, главнее. Шаблоны дизайн-систем (presets/templates) берут шрифты
только из presets/fonts — шаблон раздаётся всем, а чужой бренд и чужая лицензия — нет.

  .venv/bin/python scripts/fonts.py list [проект]
  .venv/bin/python scripts/fonts.py add <проект> ~/Downloads/Brand-Bold.otf [...]    # проект "-" — presets/fonts/local
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import PRESET_DIR  # noqa: E402

ENGINE = PRESET_DIR / "fonts"
LOCAL = ENGINE / "local"
EXT = (".ttf", ".otf")
CYRILLIC = "АаЖжЁёЫыЭэЮюЯя"


class FontError(ValueError):
    """Шрифт не принять — по-русски, с причиной."""


def project_dir(project) -> Path | None:
    """Папка шрифтов проекта (у раздела — его проекта: бренд один на все разделы) или None."""
    if project is None:
        return None
    if isinstance(project, str):
        import projects
        try:
            project = projects.get(project)
        except projects.ProjectError:
            return None
    return getattr(project, "home", project).root / "fonts"


def dirs(project=None) -> list:
    return [d for d in (project_dir(project), LOCAL, ENGINE) if d is not None]


def find(name: str, project=None) -> Path | None:
    """Файл шрифта по имени: проект → догруженные → движок."""
    name = Path(str(name)).name
    for d in dirs(project):
        if (d / name).is_file():
            return d / name
    return None


def files(project=None) -> dict:
    """{имя файла: путь} — все шрифты, видимые проекту; верхнее место главнее. Вариативные (-var) — нет: libass берёт
    из них базовое начертание."""
    out = {}
    for d in reversed(dirs(project)):
        if d.is_dir():
            for p in sorted(d.iterdir()):
                if p.suffix.lower() in EXT and "-var" not in p.stem and not p.name.startswith("."):
                    out[p.name] = p
    return out


def info(path: Path) -> dict:
    """Семейство, вес, курсив, кириллица — из самого файла. Битый файл — FontError."""
    from fontTools.ttLib import TTFont
    try:
        f = TTFont(path, fontNumber=0, lazy=True)
        try:
            family = f["name"].getDebugName(16) or f["name"].getDebugName(1) or path.stem
            os2 = f["OS/2"] if "OS/2" in f else None
            weight = int(os2.usWeightClass) if os2 else 400
            italic = bool(os2.fsSelection & 1) if os2 else False
            cmap = f.getBestCmap() or {}
            cyrillic = all(ord(c) in cmap for c in CYRILLIC)
        finally:
            f.close()
    except Exception as e:                                   # noqa: BLE001 — fontTools падает по-разному на битом файле
        raise FontError(f"«{path.name}» не читается как шрифт ({type(e).__name__}) — файл повреждён или это не .ttf/.otf") from None
    return {"file": path.name, "family": family, "weight": weight, "italic": italic, "cyrillic": cyrillic}


def where(path: Path) -> str:
    if path.parent == ENGINE:
        return "движок"
    if path.parent == LOCAL:
        return "эта машина"
    return "проект"


def listing(project=None) -> list:
    out = []
    for name, path in files(project).items():
        try:
            out.append({**info(path), "where": where(path)})
        except FontError:
            continue
    return sorted(out, key=lambda x: (x["where"] != "проект", x["family"].lower(), x["weight"]))


def add(project, name: str, data: bytes) -> dict:
    """Кладёт шрифт в проект (или presets/fonts/local без проекта). Проверяет, что это шрифт; без кириллицы — принимает,
    но говорит: русский текст им не набрать (латиница бренда бывает нужна)."""
    name = Path(str(name)).name
    if Path(name).suffix.lower() not in EXT:
        raise FontError(f"«{name}»: нужен файл .ttf или .otf (woff/woff2 libass и субтитры быстрого конвейера не читают)")
    if not data:
        raise FontError(f"«{name}»: пустой файл")
    target_dir = project_dir(project) if project not in (None, "", "-") else LOCAL
    if target_dir is None:
        raise FontError(f"нет проекта «{project}»")
    target_dir.mkdir(parents=True, exist_ok=True)
    tmp = target_dir / f".{name}.part"
    tmp.write_bytes(data)
    try:
        meta = info(tmp)
    except FontError:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(target_dir / name)
    return {**meta, "where": where(target_dir / name)}


def main():
    import host
    host.utf8_console()
    ap = argparse.ArgumentParser(description="Шрифты движка, машины и проекта")
    sub = ap.add_subparsers(dest="cmd")
    ls = sub.add_parser("list")
    ls.add_argument("project", nargs="?")
    ad = sub.add_parser("add")
    ad.add_argument("project", help="проект (у раздела — его проект) или «-» — на эту машину без проекта")
    ad.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()
    try:
        if args.cmd == "add":
            for path in args.files:
                r = add(args.project, path.name, path.read_bytes())
                print(f"✓ {r['file']}: {r['family']} {r['weight']}{' курсив' if r['italic'] else ''} → {r['where']}"
                      + ("" if r["cyrillic"] else " · без кириллицы: русский текст им не набрать"))
        else:
            for f in listing(getattr(args, "project", None)):
                print(f"  {f['where']:<10} {f['family']:<28} {f['weight']:>3}{' i' if f['italic'] else '  '} "
                      f"{'' if f['cyrillic'] else 'без кириллицы '}· {f['file']}")
    except FontError as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
