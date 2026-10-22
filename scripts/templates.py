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
    if sig.get("pace") not in (None, "fast", "calm"):
        bad.append(f"{where}: signals.pace «{sig.get('pace')}» — бывает fast или calm")
    # эталон — внутри шаблона: проекты и work/ — данные клиентов, на другой машине их нет (23.10.2026)
    source = ROOT / t["exemplar"].get("source", "")
    if not t["exemplar"].get("source") or not source.is_file():
        bad.append(f"{where}: эталон без страницы или партитуры — exemplar.source «{t['exemplar'].get('source')}» не найден")
    elif t["dir"] not in source.resolve().parents:
        bad.append(f"{where}: exemplar.source «{t['exemplar']['source']}» вне папки шаблона — положи копию рядом с template.json")
    if t["design"]:
        import design
        path = t["dir"] / design.FILE
        if not path.exists():
            bad.append(f"{where}: design true, а DESIGN.md нет")
        else:
            # шаблон раздаётся всем проектам и всем машинам: его шрифты — только движка (presets/fonts, OFL, в git).
            # Шрифт заказчика здесь — провал, а не «на этой машине нет» (23.10.2026: шаблон expert-premium ссылался на
            # SF Pro и Nicoletta, на Mac проверка была зелёной — шрифты лежали, на чистой Windows — красной)
            try:
                d = design.Design(path, t["id"])
                foreign = [p.name for p in d.font_paths.values() if p.parent != design.FONT_DIR]
                if foreign:
                    bad.append(f"{where}: DESIGN.md — шрифты не из presets/fonts: {', '.join(sorted(set(foreign)))}")
            except design.DesignError as e:
                bad.append(f"{where}: DESIGN.md — {e}")
    if proven(t) and not (t["dir"] / "exemplar.jpg").exists():
        bad.append(f"{where}: нет exemplar.jpg — templates.py sheets")
    return bad


# ---------------------------------------------------------------- подбор

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower().replace("ё", "е"))


# Подбор (23.10.2026, аудит docs/АУДИТ-23-10.md): мешок слов ошибался на простых анкетах — психолог-эксперт получал
# «Живой отзыв» (профессия стояла в признаках отзыва), влог-разговор — сборку из клипов (тип раздела не штрафовался),
# «без музыки» голосовало за лирик. Теперь так:
#   1. твёрдые факты отсекают чужие жанры: тип раздела (сборка / говорящая голова) и свой трек автора (keep_audio);
#   2. очки — по словам анкеты (о чём ×3, остальное ×1, слова в отрицании «без/не/нет» не считаются), тону (×2),
#      по речи самих видео проекта (×1: «что подаём на вход») и по разобранным референсам (analyze_reference: темп
#      склеек и ближайший стиль, ×2);
#   3. проверенный на заказе шаблон (exemplar.video) при равных очках — раньше базового;
#   4. ничего не совпало — умолчание по тону (динамичный → вирусный эксперт, спокойный → премиальный), а не «своё»:
#      «своё» — только выбором человека. Отрыв первого от второго меньше 2 очков — шаблон всё равно ставится, но
#      помечается «неуверенно»: студия показывает второй вариант рядом.
W_ABOUT, W_TEXT, W_TONE, W_SPEECH, W_REF = 3, 1, 2, 1, 2
MIN_MARGIN = 2
NEGATE = ("без", "не", "нет", "никаких", "ни", "кроме", "no", "without", "not")
# умолчание по тону, если анкета не назвала жанр словами: шаблон на каждую ветку «говорящей головы»
TONE_DEFAULT = (("дерзк", "expert-viral"), ("юмор", "expert-viral"), ("динамичн", "expert-viral"), ("вирусн", "expert-viral"),
                ("премиальн", "expert-premium"), ("спокойн", "expert-premium"), ("минимал", "expert-premium"))


def _hits(words: list, text: str) -> list:
    """Признаки, которые есть в тексте не под отрицанием: «без музыки» за лирик не голосует."""
    out = []
    for w in words:
        stem = _norm(w)
        for m in re.finditer(re.escape(stem), text):
            before = re.findall(r"[\w-]+", text[max(0, m.start() - 24):m.start()])[-2:]
            if not any(b in NEGATE for b in before):
                out.append(w)
                break
    return out


def project_facts(project) -> dict:
    """Что известно о проекте помимо анкеты: тип (pack, если хоть один раздел — сборка), свой трек автора, речь первых
    видео (транскрипты work/<имя>.txt — «что подаём на вход») и разборы референсов (analyze_reference → work/_refs)."""
    from common import WORK_DIR
    project = project.home
    kinds = {s.config.get("kind") for s in project.sections()} | {project.config.get("kind")}
    stems = []
    for part in [project, *project.sections()]:
        stems += [p.stem for p in part.sources()] + [p.name for p in part.packs()]
        packs = {p.name for p in part.packs()}
        if packs and all(p.stem in packs for p in part.sources()):
            kinds.add("pack")              # в input/ только сборки (папка клипов и её собранный <имя>.mov, pack.py --build)
    speech = " ".join((WORK_DIR / f"{s}.txt").read_text(encoding="utf-8")[:4000]
                      for s in stems[:3] if (WORK_DIR / f"{s}.txt").is_file())
    refs = []
    if project.references.is_dir():
        for p in sorted(project.references.iterdir()):
            cached = WORK_DIR / "_refs" / f"{p.stem}.json"
            if cached.is_file():
                try:
                    refs.append(json.loads(cached.read_text(encoding="utf-8")))
                except ValueError:
                    continue
    return {"kind": "pack" if "pack" in kinds else "talking", "keep_audio": bool(project.config.get("keep_audio")),
            "speech": _norm(speech), "refs": refs}


def score(t: dict, answers: dict, kind: str | None = None, keep_audio: bool = False, speech: str = "",
          refs: list | None = None) -> tuple:
    """(очки или None — жанр отсечён фактами, почему) шаблона для анкеты."""
    def text(key):
        v = answers.get(key) or ""
        return _norm(", ".join(v) if isinstance(v, list) else v)
    sig, why = t["signals"], []
    if sig.get("kind") and kind and sig["kind"] != kind:
        return None, [f"другой тип: шаблон — {'сборка из клипов' if sig['kind'] == 'pack' else 'говорящая голова'}"]
    if (sig.get("audio") == "keep") != bool(keep_audio):
        return None, ["звук автора не трогаем — только лирик" if keep_audio else "шаблон под свой трек автора"]
    about = text("about")
    rest = " ".join(text(k) for k in ("audience", "graphics", "sound", "references", "extra", "length", "captions"))
    tone = " | ".join(_norm(x) for x in answers.get("tone") or []) if isinstance(answers.get("tone"), list) else text("tone")
    hit_about = _hits(sig["about"], about)
    hit_rest = [w for w in _hits(sig["about"], rest) if w not in hit_about]
    hit_speech = [w for w in _hits(sig["about"], speech) if w not in hit_about + hit_rest] if speech else []
    hit_tone = _hits(sig.get("tone", []), tone)
    pts = W_ABOUT * len(hit_about) + W_TEXT * len(hit_rest) + W_TONE * len(hit_tone) + W_SPEECH * min(3, len(hit_speech))
    if hit_about or hit_rest:
        why.append("о чём: " + ", ".join(hit_about + hit_rest))
    if hit_tone:
        why.append("характер: " + ", ".join(hit_tone))
    if hit_speech:
        why.append("в речи видео: " + ", ".join(hit_speech[:3]))
    style = t["brief"]["style"]
    for ref in refs or []:
        near = [m.get("style") for m in ref.get("matches") or []]
        pace = ref.get("cuts_per_min") or 0
        name = Path(str(ref.get("file", "референс"))).stem
        if near[:1] == [style]:
            pts += W_REF
            why.append(f"референс {name}: ближе всего стиль «{style}»")
        want = sig.get("pace")
        if want and pace and ((want == "fast" and pace >= 18) or (want == "calm" and pace <= 8)):
            pts += W_REF
            why.append(f"референс {name}: {pace:g} склеек в минуту")
    if sig.get("kind") == "pack" and kind == "pack":
        pts += W_ABOUT
        why.append("сборка из нескольких клипов")
    if sig.get("audio") == "keep" and keep_audio:
        pts += 4
        why.append("звук автора не трогаем")
    return pts, why


def match(answers: dict, kind: str | None = None, keep_audio: bool = False, speech: str = "", refs: list | None = None) -> list:
    """Годные по фактам шаблоны по убыванию очков: [(очки, шаблон, почему)]. Равные — проверенный на заказе раньше."""
    ranked = []
    for t in all_templates():
        pts, why = score(t, answers, kind, keep_audio, speech, refs)
        if pts is not None:
            ranked.append((pts, t, why))
    return sorted(ranked, key=lambda x: (-x[0], not proven(x[1]), x[1]["id"]))


def proven(t: dict) -> bool:
    """Шаблон проверен на заказе: у эталона есть принятое видео. Базовый (по стилю и референсам) — нет."""
    return bool((t.get("exemplar") or {}).get("video"))


def suggest(project) -> tuple:
    """(шаблон или None, очки, почему) — лучший для проекта по анкете, речи видео и референсам. Ничего не совпало —
    умолчание ветки по тону. None — только когда анкеты нет совсем или факты отсекли всё."""
    t, pts, why, _ = decide(project)
    return t, pts, why


def decide(project) -> tuple:
    """(шаблон или None, очки, почему, второй вариант или None) для проекта: анкета + речь его видео + референсы."""
    import projects
    facts = project_facts(project)
    return choose(projects.load_setup(project.home) or {}, facts["kind"], facts["keep_audio"], facts["speech"], facts["refs"])


def choose(answers: dict, kind: str | None = None, keep_audio: bool = False, speech: str = "", refs: list | None = None) -> tuple:
    """(шаблон или None, очки, почему, второй вариант или None) — второй есть, когда отрыв меньше MIN_MARGIN."""
    ranked = match(answers, kind, keep_audio, speech, refs)
    if not ranked:
        return None, 0, [], None
    best = ranked[0]
    if best[0] <= 0:
        tone = " ".join(answers.get("tone") or []) if isinstance(answers.get("tone"), list) else str(answers.get("tone") or "")
        fallback = next((tid for stem, tid in TONE_DEFAULT if stem in _norm(tone)), None)
        pick = next((r for r in ranked if r[1]["id"] == fallback), None)
        if pick is None:
            return None, 0, [], None
        return pick[1], pick[0], [f"жанр по анкете не назван — умолчание по характеру монтажа ({tone.strip()})"], None
    second = ranked[1] if len(ranked) > 1 and best[0] - ranked[1][0] < MIN_MARGIN and ranked[1][0] > 0 else None
    return best[1], best[0], best[2], (second[1] if second else None)


# ---------------------------------------------------------------- применение

def rules_block(t: dict, why: list, alt: dict | None = None) -> str:
    ex = t["exemplar"]
    video = ex.get("video")
    seen = (f"видео — {video}, если оно есть на этой машине ({ex['verdict']})" if video
            else f"принятого видео ещё нет — шаблон базовый: {ex['verdict']}")
    lines = [BEGIN, f"## Шаблон проекта: «{t['name']}» ({t['id']})", "",
             f"{t['summary']}", "",
             f"Почему этот: {'; '.join(why) if why else 'выбран человеком'}. Сменить — «Проект → Настроить проект» → шаблон."
             + (f" Выбран неуверенно: рядом «{alt['name']}» ({alt['id']}) — если ролик о другом, смени." if alt else ""),
             "",
             f"**Эталон — посмотри до плана:** лист кадров presets/templates/{t['id']}/exemplar.jpg (есть на любой машине); "
             f"{seen}; как собран — {ex['source']}. Это мерка качества и почерка, не копия: идея, слова и картинки — из этого ролика.",
             "", "**Бренд — свой:** цвета и шрифты шаблона стартовые. Если в анкете есть «Шрифт, цвета» — перенеси их в DESIGN.md "
             "проекта до первого монтажа; шрифты заказчика — в projects/<проект>/fonts (студия: «Настроить проект» → «Шрифты "
             "проекта», или scripts/fonts.py add).",
             "", "**Уже выучено на эталоне (правила проекта, пока автор не скажет иначе):**"]
    lines += [f"- {r}" for r in t["rules"]]
    lines += ["", f"**Как монтировать:** {t['how']}", "", END]
    return "\n".join(lines)


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.is_file() else ""


def apply(project, tid: str | None = None, why: list | None = None, force: bool = False) -> dict:
    """Ставит шаблон проекту: бриф и умолчания в project.json, DESIGN.md, блок «Шаблон проекта» в rules.md.
    Возвращает {"template", "name", "why", "set", "design", "alt"}.

    Смена шаблона честная (23.10.2026; до этого второй apply менял только блок в правилах — стиль и умолчания оставались
    от первого): что записал прошлый шаблон, помнится в project.json → template_set; если человек это значение не
    трогал — его заменяет новый шаблон (или убирает, если у нового такого нет). Поставленное руками не трогается, кроме
    force. DESIGN.md прошлого шаблона (хэш в template_design) заменяется; DESIGN.md, который человек правил, — нет."""
    import design
    import projects
    import styles
    project = project.home
    alt = None
    if tid is None:
        t, _, why, alt = decide(project)
        if t is None:
            raise TemplateError(f"проект {project.name}: шаблон не подобрать — анкеты нет или в ней не назван ни жанр, ни "
                                f"характер монтажа; выбери сам ({', '.join(ids())}) или оставь «своё»")
    else:
        t = load(tid)
        why = why or ["выбран человеком"]
    path = project.root / "project.json"
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    brief = config.setdefault("brief", {})
    old = config.get("template_set") or {}
    wanted = {f"brief.{k}": v for k, v in t["brief"].items()} | dict(t["project"])

    def get(key):
        return brief.get(key[6:]) if key.startswith("brief.") else config.get(key)

    def put(key, value):
        target, name = (brief, key[6:]) if key.startswith("brief.") else (config, key)
        if value is None:
            target.pop(name, None)
        else:
            target[name] = value

    def unset(key):
        """Значение «не задано человеком»: пусто, умолчание брифа или записано прошлым шаблоном и не тронуто."""
        value = get(key)
        if key in old:
            return value == old[key]
        if value in (None, "", {}, []):
            return True
        return key == "brief.style" and value == styles.DEFAULT_BRIEF["style"] and not config.get("template")

    changed, now_set = [], {}
    for key in sorted(set(old) | set(wanted)):
        if not (force or unset(key)):
            continue                                        # поставил человек — его решение
        value = wanted.get(key)
        if get(key) != value:
            put(key, value)
            changed.append(key if value is not None else f"{key} (снято: было от прошлого шаблона)")
        if value is not None:
            now_set[key] = value
    config["template"] = t["id"]
    config["template_set"] = now_set
    path.write_text(json.dumps(config, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    projects.load_config(path, project.name)                 # проверка: записанное читается

    target = project.root / design.FILE
    ours = target.is_file() and _sha(target) == config.get("template_design")
    if target.is_file() and not ours and not force:
        design_note = "у проекта своя — не трогаю"
    elif t["design"]:
        try:
            design.Design(t["dir"] / design.FILE, project.name)
            target.write_text((t["dir"] / design.FILE).read_text(encoding="utf-8"), encoding="utf-8")
            config["template_design"] = _sha(target)
            design_note = "положена стартовая — цвета и шрифты бренда правятся в DESIGN.md"
        except design.DesignError as e:
            design_note = f"не положена: {e}"
    elif ours:
        target.unlink()
        config["template_design"] = ""
        design_note = "снята: была от прошлого шаблона, у этого своей нет"
    else:
        design_note = "у шаблона нет"
    path.write_text(json.dumps(config, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    rules = project.rules_text() or ""
    block = rules_block(t, why or [], alt)
    if BEGIN in rules and END in rules:
        head, rest = rules.split(BEGIN, 1)
        rules = head + block + rest.split(END, 1)[1]
    elif projects.SETUP_END in rules:
        head, rest = rules.split(projects.SETUP_END, 1)
        rules = head + projects.SETUP_END + "\n\n" + block + rest
    else:
        rules = rules.rstrip() + "\n\n" + block + "\n"
    project.rules.write_text(rules, encoding="utf-8")
    return {"template": t["id"], "name": t["name"], "why": why or [], "set": changed, "design": design_note,
            "alt": {"id": alt["id"], "name": alt["name"]} if alt else None}


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
    return [{"id": t["id"], "name": t["name"], "summary": t["summary"], "stem": t["exemplar"].get("stem") or "",
             "verdict": t["exemplar"]["verdict"], "design": t["design"], "proven": proven(t),
             "sheet": (t["dir"] / "exemplar.jpg").is_file()} for t in all_templates()]


# ---------------------------------------------------------------- листы кадров эталонов

def sheet(t: dict) -> Path:
    """exemplar.jpg — 20 кадров принятого ролика сеткой 5×4 (один ffmpeg, кадры идут по одному)."""
    if not proven(t):
        raise TemplateError(f"{t['id']}: шаблон базовый — принятого видео ещё нет, лист кадров собирается после первого апрува")
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
            f = project_facts(p)
            ranked = match(projects.load_setup(p) or {}, f["kind"], f["keep_audio"], f["speech"], f["refs"])
            for pts, t, why in ranked:
                print(f"  {pts:>3}  {t['id']:<22} {t['name']}" + (f" — {'; '.join(why)}" if why else ""))
            best, pts, why, alt = decide(p)
            print(f"→ {best['id'] if best else 'не подобрать (нет анкеты или жанра и характера)'}"
                  + (f" ({'; '.join(why)})" if best and not ranked[0][2] else "")
                  + (f"; неуверенно, рядом {alt['id']}" if alt else "") + f"; сейчас у проекта: {current(p) or '—'}")
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
                print(f"  {t['id']:<16} {t['name']} — " + (f"эталон {t['exemplar']['stem']}" if proven(t) else "базовый") + (" · DESIGN.md" if t["design"] else ""))
    except (TemplateError, projects.ProjectError) as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
