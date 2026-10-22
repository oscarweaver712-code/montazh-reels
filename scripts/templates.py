#!/usr/bin/env python3
"""Шаблоны дизайн-систем: новый проект сразу встаёт на почерк принятого — с первого раза годнота (22.10.2026).

Валера 22.10.2026: «сделать шаблоны дизайн-систем, чтобы система сразу понимала, на какой шаблон ориентироваться, когда
ей подаётся новый проект видео на вход, — чтобы с первого раза удавалось годноту сделать». До этого каждый новый проект
стартовал с нуля, и первая версия уходила в разнос («Ольга Статирова» v1 — «как будто делал ребёнок»).

Шаблон — presets/templates/<id>/, собран из принятого проекта:
  template.json   признаки для подбора (signals), бриф и умолчания project.json, переносимые уроки (rules), как
                  монтировать (how), эталон — принятый ролик и его страница/партитура (exemplar)
  DESIGN.md       дизайн-система эталона (если есть) — стартовая для нового проекта: шрифты и цвета бренда правятся
  exemplar.jpg    лист кадров принятого ролика — агент видит почерк и там, где самого видео нет

Подбор — по анкете проекта (setup.json): «о чём ролики» весит больше всего, потом характер монтажа, тип раздела
(сборка из клипов) и звук («поёт под трек»). Применение (apply) пишет в project.json бриф и умолчания шаблона (то,
что человек уже поставил руками, не трогает), кладёт DESIGN.md (если у проекта своего нет и шрифты на месте) и блок
«Шаблон проекта» в rules.md — его агент читает до плана: какой эталон посмотреть и какие уроки уже выучены.

  .venv/bin/python scripts/templates.py                       # каталог
  .venv/bin/python scripts/templates.py match olga-statirova  # какой шаблон подходит проекту и почему
  .venv/bin/python scripts/templates.py apply olga-statirova [testimonial]   # поставить (без id — лучший по анкете)
  .venv/bin/python scripts/templates.py check                 # все шаблоны валидны
  .venv/bin/python scripts/templates.py sheets                # листы кадров эталонов (exemplar.jpg)
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import PRESET_DIR, ROOT, ffmpeg_bin, ffprobe_bin  # noqa: E402

TEMPLATE_DIR = PRESET_DIR / "templates"
REQUIRED = ("id", "name", "summary", "signals", "exemplar", "brief", "project", "rules", "how", "design")
BEGIN = "<!-- шаблон проекта: этот блок пишет templates.py (studio: «Настроить проект» → шаблон) -->"
END = "<!-- /шаблон -->"
MIN_SCORE = 3            # слабее — «своё»: шаблон не ставится сам, человек выбирает в анкете
# вес признака: «о чём ролики» говорит о жанре больше всего; характер монтажа — общий для многих жанров
W_ABOUT, W_TEXT, W_TONE, W_KIND, W_AUDIO = 3, 1, 2, 3, 4


class TemplateError(ValueError):
    """Шаблон описан с ошибкой или не применяется — по-русски, с местом."""


def load(tid: str) -> dict:
    path = TEMPLATE_DIR / tid / "template.json"
    if not path.exists():
        raise TemplateError(f"шаблона «{tid}» нет: есть {', '.join(ids())}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["dir"] = path.parent
    return data


def ids() -> list:
    return sorted(p.parent.name for p in TEMPLATE_DIR.glob("*/template.json"))


def all_templates() -> list:
    return [load(t) for t in ids()]


def validate(t: dict) -> list:
    """Ошибки шаблона одним списком (пусто — годен). Видео эталона может не быть на этой машине — это не ошибка."""
    import styles
    where = f"presets/templates/{t.get('id', '?')}"
    bad = [f"{where}: нет полей {', '.join(k for k in REQUIRED if k not in t)}"] if any(k not in t for k in REQUIRED) else []
    if bad:
        return bad
    if t["id"] != t["dir"].name:
        bad.append(f"{where}: id «{t['id']}» не совпадает с папкой")
    try:
        styles.effective(styles.load_style(t["brief"]["style"]), t["brief"].get("overrides"))
    except Exception as e:                                   # noqa: BLE001 — стиль и правки проверяет styles
        bad.append(f"{where}: бриф не собирается в стиль — {e}")
    sig = t["signals"]
    if not sig.get("about"):
        bad.append(f"{where}: signals.about пуст — по чему узнавать жанр?")
    if sig.get("kind") not in (None, "talking", "pack"):
        bad.append(f"{where}: signals.kind «{sig.get('kind')}» — бывает talking или pack")
    source = ROOT / t["exemplar"].get("source", "")
    if not t["exemplar"].get("source") or not source.exists():
        bad.append(f"{where}: эталон без страницы или партитуры — exemplar.source «{t['exemplar'].get('source')}» не найден")
    if t["design"]:
        import design
        path = t["dir"] / design.FILE
        if not path.exists():
            bad.append(f"{where}: design true, а DESIGN.md нет")
        else:
            try:
                design.Design(path, t["id"])
            except design.DesignError as e:
                if "нет файла шрифта" not in str(e):         # шрифты не OFL (заказчика) — на этой машине может не быть
                    bad.append(f"{where}: DESIGN.md — {e}")
    if not (t["dir"] / "exemplar.jpg").exists():
        bad.append(f"{where}: нет exemplar.jpg — templates.py sheets")
    return bad


# ---------------------------------------------------------------- подбор

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower().replace("ё", "е"))


def score(t: dict, answers: dict, kind: str | None = None, keep_audio: bool = False) -> tuple:
    """(очки, почему) шаблона для анкеты: совпавшие признаки — словами для человека."""
    def text(key):
        v = answers.get(key) or ""
        return _norm(", ".join(v) if isinstance(v, list) else v)
    about = text("about")
    rest = " ".join(text(k) for k in ("audience", "graphics", "sound", "references", "extra", "length"))
    tone = [_norm(x) for x in (answers.get("tone") or [])] if isinstance(answers.get("tone"), list) else [text("tone")]
    sig, pts, why = t["signals"], 0, []
    hit_about = [w for w in sig["about"] if _norm(w) in about]
    hit_rest = [w for w in sig["about"] if _norm(w) in rest and w not in hit_about]
    hit_tone = [w for w in sig.get("tone", []) if any(_norm(w) in x for x in tone)]
    pts += W_ABOUT * len(hit_about) + W_TEXT * len(hit_rest) + W_TONE * len(hit_tone)
    if hit_about or hit_rest:
        why.append("о чём: " + ", ".join(hit_about + hit_rest))
    if hit_tone:
        why.append("характер: " + ", ".join(hit_tone))
    if sig.get("kind") and kind and sig["kind"] == kind:
        pts += W_KIND if kind == "pack" else 0               # «говорящая голова» — у многих жанров, сборка — признак
        if kind == "pack":
            why.append("сборка из нескольких клипов")
    if sig.get("audio") == "keep":
        if keep_audio:
            pts += W_AUDIO
            why.append("звук автора не трогаем")
        else:
            pts -= W_AUDIO                                  # лирик без своего трека — не лирик
    return pts, why


def match(answers: dict, kind: str | None = None, keep_audio: bool = False) -> list:
    """Шаблоны по убыванию очков: [(очки, шаблон, почему)]."""
    ranked = [(*score(t, answers, kind, keep_audio), t) for t in all_templates()]
    return sorted(((p, t, why) for p, why, t in ranked), key=lambda x: -x[0])


def _project_kind(project) -> tuple:
    """(тип: pack, если в проекте или разделе есть сборка; keep_audio проекта)."""
    kinds = {s.config.get("kind") for s in project.sections()} | {project.config.get("kind")}
    return ("pack" if "pack" in kinds else "talking"), bool(project.config.get("keep_audio"))


def suggest(project) -> tuple:
    """(шаблон или None, очки, почему) — лучший по анкете проекта; слабее MIN_SCORE — None."""
    import projects
    answers = projects.load_setup(project) or {}
    kind, keep = _project_kind(project)
    ranked = match(answers, kind, keep)
    if not ranked or ranked[0][0] < MIN_SCORE:
        return None, ranked[0][0] if ranked else 0, []
    best = ranked[0]
    return best[1], best[0], best[2]


# ---------------------------------------------------------------- применение

def rules_block(t: dict, why: list) -> str:
    ex = t["exemplar"]
    lines = [BEGIN, f"## Шаблон проекта: «{t['name']}» ({t['id']})", "",
             f"{t['summary']}", "",
             f"Почему этот: {'; '.join(why) if why else 'выбран человеком'}. Сменить — «Проект → Настроить проект» → шаблон.",
             "",
             f"**Эталон — посмотри до плана:** {ex['video']} ({ex['verdict']}); лист кадров — presets/templates/{t['id']}/exemplar.jpg; "
             f"как собран — {ex['source']}. Это мерка качества и почерка, не копия: идея, слова и картинки — из этого ролика.",
             "", "**Уже выучено на эталоне (правила проекта, пока автор не скажет иначе):**"]
    lines += [f"- {r}" for r in t["rules"]]
    lines += ["", f"**Как монтировать:** {t['how']}", "", END]
    return "\n".join(lines)


def apply(project, tid: str | None = None, why: list | None = None, force: bool = False) -> dict:
    """Ставит шаблон проекту: бриф и умолчания в project.json (заданное человеком не трогает, кроме force), DESIGN.md (если
    своего нет), блок «Шаблон проекта» в rules.md. Возвращает {"template", "why", "set", "design"}."""
    import projects
    project = project.home
    if tid is None:
        t, _, why = suggest(project)
        if t is None:
            raise TemplateError(f"проект {project.name}: ни один шаблон не подходит по анкете уверенно — выбери сам "
                                f"({', '.join(ids())}) или оставь «своё»")
    else:
        t = load(tid)
        why = why or ["выбран человеком"]
    path = project.root / "project.json"
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    changed = []
    brief = config.setdefault("brief", {})
    for key, value in t["brief"].items():
        if force or key not in brief or brief.get(key) in (None, "", {}, []) or (key == "style" and not config.get("template")):
            if brief.get(key) != value:
                brief[key] = value
                changed.append(f"brief.{key}")
    for key, value in t["project"].items():
        if force or key not in config:
            if config.get(key) != value:
                config[key] = value
                changed.append(key)
    config["template"] = t["id"]
    path.write_text(json.dumps(config, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    projects.load_config(path, project.name)                 # проверка: записанное читается

    design_note = "у шаблона нет"
    if t["design"]:
        import design
        target = project.root / design.FILE
        if target.exists() and not force:
            design_note = "у проекта своя — не трогаю"
        else:
            try:
                design.Design(t["dir"] / design.FILE, project.name)
                target.write_text((t["dir"] / design.FILE).read_text(encoding="utf-8"), encoding="utf-8")
                design_note = "положена стартовая — шрифты и цвета бренда правятся в DESIGN.md"
            except design.DesignError as e:
                design_note = f"не положена: {e}"

    rules = project.rules_text() or ""
    block = rules_block(t, why or [])
    if BEGIN in rules and END in rules:
        head, rest = rules.split(BEGIN, 1)
        rules = head + block + rest.split(END, 1)[1]
    elif projects.SETUP_END in rules:
        head, rest = rules.split(projects.SETUP_END, 1)
        rules = head + projects.SETUP_END + "\n\n" + block + rest
    else:
        rules = rules.rstrip() + "\n\n" + block + "\n"
    project.rules.write_text(rules, encoding="utf-8")
    return {"template": t["id"], "name": t["name"], "why": why or [], "set": changed, "design": design_note}


def current(project) -> str | None:
    return project.home.config.get("template") or None


def clear(project) -> None:
    """«Своё»: проект без шаблона — блок «Шаблон проекта» из rules.md уходит, бриф и умолчания остаются как есть."""
    project = project.home
    path = project.root / "project.json"
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    config["template"] = ""
    path.write_text(json.dumps(config, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rules = project.rules_text()
    if BEGIN in rules and END in rules:
        head, rest = rules.split(BEGIN, 1)
        project.rules.write_text(head.rstrip() + "\n\n" + rest.split(END, 1)[1].lstrip(), encoding="utf-8")


def catalog() -> list:
    """Для студии: [{id, name, summary, stem, verdict, design}]."""
    return [{"id": t["id"], "name": t["name"], "summary": t["summary"], "stem": t["exemplar"]["stem"],
             "verdict": t["exemplar"]["verdict"], "design": t["design"]} for t in all_templates()]


# ---------------------------------------------------------------- листы кадров эталонов

def sheet(t: dict) -> Path:
    """exemplar.jpg — 20 кадров принятого ролика сеткой 5×4 (один ffmpeg, кадры идут по одному)."""
    video = ROOT / t["exemplar"]["video"]
    if not video.exists():
        raise TemplateError(f"{t['id']}: нет видео эталона {t['exemplar']['video']} — лист не собрать на этой машине")
    dur = float(subprocess.run([ffprobe_bin(), "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True).stdout)
    out = t["dir"] / "exemplar.jpg"
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(video), "-vf",
                    f"fps=20/{dur:.3f},scale=216:-2,tile=5x4:padding=4:color=black", "-frames:v", "1", "-q:v", "4", str(out)],
                   check=True)
    return out


def main():
    import host
    import projects
    host.utf8_console()
    ap = argparse.ArgumentParser(description="Шаблоны дизайн-систем проектов")
    sub = ap.add_subparsers(dest="cmd")
    m = sub.add_parser("match")
    m.add_argument("project")
    a = sub.add_parser("apply")
    a.add_argument("project")
    a.add_argument("template", nargs="?")
    a.add_argument("--force", action="store_true", help="перезаписать и то, что человек поставил руками")
    sub.add_parser("check")
    sub.add_parser("sheets")
    args = ap.parse_args()
    try:
        if args.cmd == "match":
            p = projects.get(args.project).home
            kind, keep = _project_kind(p)
            for pts, t, why in match(projects.load_setup(p) or {}, kind, keep):
                print(f"  {pts:>3}  {t['id']:<16} {t['name']}" + (f" — {'; '.join(why)}" if why else ""))
            best, pts, _ = suggest(p)
            print(f"→ {best['id'] if best else 'своё (ни один не уверенно)'}; сейчас у проекта: {current(p) or '—'}")
        elif args.cmd == "apply":
            r = apply(projects.get(args.project), args.template, force=args.force)
            print(f"✓ {args.project}: шаблон «{r['name']}» ({r['template']}) — {'; '.join(r['why'])}")
            print(f"  project.json: {', '.join(r['set']) or 'всё уже стояло'}; DESIGN.md: {r['design']}; rules.md — блок «Шаблон проекта»")
        elif args.cmd == "check":
            bad = [b for t in all_templates() for b in validate(t)]
            if bad:
                sys.exit("✗ шаблоны:\n  " + "\n  ".join(bad))
            print(f"✓ шаблонов: {len(ids())}, все годны")
        elif args.cmd == "sheets":
            for t in all_templates():
                try:
                    print(f"✓ {sheet(t).relative_to(ROOT)}")
                except TemplateError as e:
                    print(f"  · {e}")
        else:
            for t in all_templates():
                print(f"  {t['id']:<16} {t['name']} — эталон {t['exemplar']['stem']}" + (" · DESIGN.md" if t["design"] else ""))
    except (TemplateError, projects.ProjectError) as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
