#!/usr/bin/env python3
"""Вкус автора: что он принял и что забраковал — и почему (24.10.2026, Валера: «чтобы ты смог точнее определять, что
именно автор хотел бы видеть на монтаже»).

Каждый апрув (approve.py, «✓ принять» в студии) и каждый брак («✗ брак» с причиной) пишутся строкой в
projects/<проект>/taste.jsonl: ролик, решение, слова человека, идея и приёмы партитуры. Аналитик перед партитурой
получает выжимку — что у этого автора сработало и что нет. Это не шаблон (правило «каждый ролик — своя идея»), а мерка:
принятое показывает уровень и меру, брак — то, чего не делать.

  .venv/bin/python scripts/taste.py IMG_3684 брак "стоки мутные, графика мелкая"
  .venv/bin/python scripts/taste.py --show antishkola
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import host  # noqa: E402
import projects  # noqa: E402
from common import WORK_DIR  # noqa: E402

VERDICTS = ("принят", "брак")
SHOW = 8                 # решений в выжимке аналитику: последних, принятых и забракованных вместе


def path_of(project) -> Path:
    """Вкус — у проекта, а не у раздела: дизайн и стиль у них общие (Section.home — сам проект)."""
    return getattr(project, "home", project).root / "taste.jsonl"


def record(stem: str, verdict: str, why: str = "", file: str = "") -> dict:
    """Решение человека по ролику — в вкус проекта. why — его слова (для брака обязательны: без причины учиться нечему)."""
    if verdict not in VERDICTS:
        raise ValueError(f"решение — {' или '.join(VERDICTS)}, а не «{verdict}»")
    why = " ".join(str(why).split())
    if verdict == "брак" and not why:
        raise ValueError("брак без причины ничему не учит — напиши словами, что не так")
    project = projects.of(stem)
    score_file = WORK_DIR / stem / "score.json"
    score = {}
    if score_file.exists():
        try:
            score = json.loads(score_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            score = {}
    kinds = {}
    for item in score.get("items") or []:
        if isinstance(item, dict) and item.get("kind"):
            kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
    entry = {"at": time.strftime("%Y-%m-%d %H:%M"), "stem": stem, "verdict": verdict, "why": why, "file": file,
             "concept": score.get("concept") or {}, "kinds": kinds}
    with path_of(project).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def entries(project) -> list:
    path = path_of(project)
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue                       # битая строка не роняет монтаж, остальные решения читаются
    return out


def lines(project, show: int = SHOW) -> list:
    """Выжимка для аналитика: последние решения автора словами."""
    last = entries(project)[-show:]
    if not last:
        return []
    out = ["ВКУС АВТОРА — его решения по прошлым роликам (мерка, не шаблон; брак — не повторять):"]
    for e in reversed(last):
        idea = (e.get("concept") or {}).get("motif") or (e.get("concept") or {}).get("idea") or ""
        kinds = ", ".join(f"{k} {n}" for k, n in sorted((e.get("kinds") or {}).items(), key=lambda kv: -kv[1])[:5])
        out.append(f"- {e['stem']} — {e['verdict'].upper()}" + (f": {e['why']}" if e.get("why") else "")
                   + (f"; мотив «{idea}»" if idea else "") + (f"; приёмы {kinds}" if kinds else ""))
    return out + [""]


def main():
    host.utf8_console()
    ap = argparse.ArgumentParser(description="Вкус автора: принятое и брак с причиной")
    ap.add_argument("stem", nargs="?")
    ap.add_argument("verdict", nargs="?", choices=VERDICTS)
    ap.add_argument("why", nargs="?", default="")
    ap.add_argument("--show", metavar="ПРОЕКТ", help="выжимка вкуса проекта, как её видит аналитик")
    a = ap.parse_args()
    try:
        if a.show:
            print("\n".join(lines(projects.get(a.show))) or "решений пока нет")
            return
        if not (a.stem and a.verdict):
            ap.error("нужны ролик и решение (принят / брак) или --show ПРОЕКТ")
        e = record(a.stem, a.verdict, a.why)
        print(f"✓ {e['stem']}: {e['verdict']} — записано в вкус проекта")
    except (ValueError, projects.ProjectError) as err:
        sys.exit(f"✗ {err}")


if __name__ == "__main__":
    main()
