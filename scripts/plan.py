#!/usr/bin/env python3
"""План монтажа — до страницы и рендера: что и чем делается в каждом месте ролика.

Правило Валеры (13.10.2026): «перед редактурой понимать, что именно и как будешь делать, —
подробный план действий и инструментов, которые в том или ином месте валиднее». Так же работают
сильные моушн-студии: сначала раскадровка, потом анимация; сначала идея и одобрение, потом сборка.

  .venv/bin/python scripts/plan.py IMG_3317           # разбор исходника → work/IMG_3317/plan.md (каркас)
  .venv/bin/python scripts/plan.py IMG_3317 --check   # план заполнен и годится — без этого рендер не идёт

Раздел «Исходник» считается здесь по файлам ролика (слова с таймингами, лицо по кадрам, длина,
бриф): паузы, числа и имена в речи, перечисления, вопросы, где лицо и куда можно ставить карточки.
Остальное пишет режиссёр: мысль, хук, раскадровку «время | реплика | на экране | инструмент |
почему | держится», звук и риски. Инструменты — только из арсенала (TOOLS, docs/АРСЕНАЛ.md): план
не может опереться на то, чего у конвейера нет.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ROOT, WORK_DIR  # noqa: E402  (заодно UTF-8 в консоли — common это делает)

# Инструменты конвейера: имя в плане → что это и когда к месту. Новое из арсенала попадает сюда,
# когда встроено в kit/viz и проверено, — не раньше.
TOOLS = {
    "слово за спиной": "крупное слово между фоном и человеком (вырезка): ключевое слово мысли, не чаще раза за мысль",
    "фон": "подмена фона за спиной: место, эпоха, метафора (свободное фото или gen_image); на показе резкий",
    "футаж": "ИИ-клип во весь кадр (скилл flow: Google Flow/Omni → footage.py → kit.footage): быт, место, процесс, "
             "которых нет в свободных фото; облако и бонусы — по брифу footage.json",
    "портрет": "карточка-портрет сбоку (kit.card): человек или вещь, о которой речь",
    "документ": "картинка-документ снизу (kit.doc_img): источник, доказательство, страница",
    "панель": "плашка-таблица на груди: сравнение, ряд чисел, определения — строки появляются по словам",
    "стикер": "наклейка-подпись у головы: короткий ярлык, ирония",
    "штамп": "штамп с размаха: вердикт одним словом",
    "счётчик": "viz: число набегает — суммы, проценты, просмотры",
    "столбики": "viz: сравнение величин",
    "линия": "viz: рост или падение во времени",
    "доли": "viz: части целого",
    "до/после": "viz: было и стало",
    "формула": "viz.formula (KaTeX): формула, которую произносят",
    "график": "viz.plot: график функции, корни, парабола",
    "доска": "ManimGX (manim_clip.py + viz.board): формула преобразуется, график строится, геометрия — как на доске",
    "карта": "viz: страны, города, маршрут",
    "схема": "viz: блок-схема, шаги решения",
    "наезд": "камера-акцент (director.json, punches): главное слово, смена мысли",
    # приёмы рилса @tenfoldmarc «17 video effects» (fx.py, docs/ПРИЁМЫ-17.md), 16.10.2026
    "оглавление": "fx.toc: список пунктов ролика сверху, текущий горит — ролики-подборки «N способов»",
    "чек-лист": "fx.checklist: стеклянная плашка, пункты отмечаются галочкой на своё слово — шаги, инструкция",
    "телефон": "fx.phone: телефон у лица, сообщения чата по одному — переписка, ответ ИИ, отзыв",
    "интерфейс": "fx.ui_chat: окно приложения сверху, файлы падают, команда набирается — «как это делается»",
    "стена": "fx.wall: заметки или скриншоты прикалываются к стене за спиной — заголовки, отзывы, доказательства",
    "орбита": "fx.orbit: карточки летят по кругу вокруг человека — много примеров разом, перечисление",
    "рамка": "fx.frame_break: кадр сжимается в карточку, человек выходит за край — смена темы, «вышел за рамки»",
    "вертиго": "fx.vertigo: комната отъезжает, человек на месте — озарение, шок, поворот мысли",
    "пролёт": "fx.zoom_through: влёт в камеру на склейке — переход к следующему пункту",
    "отъезд": "fx.pullback: кадр отъезжает в окно монтажки со шкалой и счётчиком — «вот как это сделано», прогресс",
    "рост": "fx.chart_grow: линия лезет вверх за головой, плашка на пике — рост, результат за неделю",
    "сцена": "fx.backdrop: человек на нарисованном фоне (градиент, интерфейс) вместо комнаты — смена темы",
    "коллаж": "fx.paper_cut: бумага, вырезанный человек с белым полем, слово из вырезанных букв — цифра, вывод",
    "каракули": "fx.doodle: кипящий белый контур и рисованные значки — шутка, лёгкая тема",
    "обложка": "fx.cover: человек — обложка журнала, название антиквой за головой — заголовок, тема ролика",
    "стекло": "fx.glass_word: стеклянное слово в перспективе за спиной — ключевое слово, вариант «слова за спиной»",
    "вспышка": "белая вспышка на главном ударе — пара раз за ролик",
    "ключевое слово": "kit.keyword_card: «напиши СЛОВО в комментариях»",
    "CTA": "финальная плашка: куда идти дальше",
    "субтитры": "бегущие субтитры — всегда, стиль из брифа",
    "звук": "удар, вжух, щелчок по норме (kit.audio): на главном, одинаковые не подряд",
}
NOT_VISUAL = {"субтитры", "звук"}          # экран сами по себе не меняют: для динамики не в счёт
HOOK_BY = 3.0                               # первая смена на экране — не позже, с
MAX_GAP = 5.0                               # дольше без запланированной смены на экране — провал, с
HOLD_MAX = 5.0                              # то же правило, что в verify_page: плашка не висит дольше, с
PAUSE = 0.7                                 # паузы в речи от этой длины — в разбор, с
SECTIONS = ("Мысль ролика", "Хук", "Раскадровка", "Звук", "Риски")
TODO = "✎"

NUMBER_STEMS = ("тысяч", "миллион", "миллиард", "биллион", "триллион", "процент", "половин", "четверт",
                "вдвое", "втрое", "сотн", "десятк", "дюжин")
LIST_STEMS = ("во-первых", "во-вторых", "в-третьих", "в-четвёртых", "первое", "второе", "третье", "шаг",
              "этап", "пункт", "причин", "способ", "совет", "ошибк", "правил", "приём", "лайфхак")


def clean(word: str) -> str:
    return re.sub(r"[^\w\-%]", "", word.lower())


def load_words(stem: str) -> list:
    path = WORK_DIR / stem / "aroll.words.json"
    if not path.exists():
        sys.exit(f"✗ нет work/{stem}/aroll.words.json — сначала prep.py (дубль и тайминги слов)")
    return [w for w in json.loads(path.read_text(encoding="utf-8")).get("words", []) if w.get("word", "").strip()]


def sentences(words: list) -> list:
    """[(начало, текст)] — по знакам конца фразы, которые ставит распознавание."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.!?…]$", w["word"].strip()):
            out.append((cur[0]["start"], " ".join(x["word"].strip() for x in cur)))
            cur = []
    if cur:
        out.append((cur[0]["start"], " ".join(x["word"].strip() for x in cur)))
    return out


def chin_line(stem: str) -> dict | None:
    """Где лицо на сцене: по слежению с движением камеры (verify_page.face_track), иначе — по дублю."""
    from verify_page import face_track

    project = ROOT / "studio" / stem
    track = face_track(project) if (project / "camera.js").exists() else []
    if track:
        bottoms = sorted(f[4] for f in track)
        tops = sorted(f[2] for f in track)
        source = "сцена с движением камеры"
    else:
        path = WORK_DIR / stem / "aroll.faces.json"
        if not path.exists():
            return None
        frames = [f for f in json.loads(path.read_text(encoding="utf-8")).get("frames", []) if f and f[4] >= 0.6]
        if not frames:
            return None
        bottoms = sorted(f[1] + f[3] / 2 for f in frames)
        tops = sorted(f[1] - f[3] / 2 for f in frames)
        source = "дубль без камеры (собери проект — будет точнее)"
    pick = lambda xs, q: round(xs[min(len(xs) - 1, int(q * len(xs)))])
    return {"chin_usual": pick(bottoms, 0.5), "chin_low": pick(bottoms, 0.99), "top_high": pick(tops, 0.01),
            "source": source}


def analysis(stem: str) -> list:
    """Строки раздела «Исходник»: цифры, по которым выбираются инструменты."""
    import styles

    meta_path = WORK_DIR / stem / "aroll.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    words = load_words(stem)
    duration = float(meta.get("duration") or (words[-1]["end"] if words else 0))
    fmt = meta.get("format", "9:16")
    brief = styles.load_brief(stem)
    style = brief.get("style") if brief.get("exists") else f"{brief.get('style')} (брифа нет — по умолчанию)"
    lines = [f"- длина {duration:.1f} с, формат {fmt}, стиль: {style}"
             + (f"; заметки брифа: {brief['notes']}" if brief.get("notes") else "")]
    speech = sum(w["end"] - w["start"] for w in words)
    lines.append(f"- речь: {len(words)} слов, {len(words) / max(duration, 1) * 60:.0f} слов/мин; "
                 f"говорит {speech / max(duration, 1) * 100:.0f}% времени")
    gaps = [(a["end"], b["start"] - a["end"]) for a, b in zip(words, words[1:]) if b["start"] - a["end"] >= PAUSE]
    if gaps:
        top = sorted(gaps, key=lambda g: -g[1])[:8]
        lines.append("- паузы ≥ 0,7 с: " + ", ".join(f"{t:.1f} с ({d:.1f})" for t, d in sorted(top))
                     + " — место для смены мысли, наезда или тишины")
    hook = " ".join(w["word"].strip() for w in words if w["start"] < HOOK_BY)
    lines.append(f"- первые 3 секунды: «{hook}» — это и есть хук или его надо найти дальше")
    nums = [(w["start"], w["word"].strip()) for w in words
            if re.search(r"\d", w["word"]) or any(clean(w["word"]).startswith(s) for s in NUMBER_STEMS)]
    if nums:
        lines.append("- числа в речи: " + ", ".join(f"{t:.1f} с «{x}»" for t, x in nums[:14])
                     + " → счётчик, столбики, до/после, панель")
    starts = {round(t, 2) for t, _ in sentences(words)}
    names = []
    for w in words:
        raw = w["word"].strip()
        if raw[:1].isupper() and len(clean(raw)) > 2 and round(w["start"], 2) not in starts:
            names.append((w["start"], raw.strip(",.!?…:;»«")))
    if names:
        lines.append("- имена и места: " + ", ".join(f"{t:.1f} с «{x}»" for t, x in names[:14])
                     + " → портрет, карта, документ")
    listed = [(w["start"], w["word"].strip()) for w in words if any(clean(w["word"]).startswith(s) for s in LIST_STEMS)]
    if listed:
        lines.append("- перечисления: " + ", ".join(f"{t:.1f} с «{x}»" for t, x in listed[:10])
                     + " → панель по строкам, схема шагов")
    asks = [(t, s) for t, s in sentences(words) if s.endswith("?")]
    if asks:
        lines.append("- вопросы: " + "; ".join(f"{t:.1f} с «{s}»" for t, s in asks[:6]) + " → интрига, хук")
    face = chin_line(stem)
    if face:
        lines.append(f"- лицо ({face['source']}): подбородок обычно до y {face['chin_usual']}, при наклоне до "
                     f"y {face['chin_low']}; макушка поднимается до y {face['top_high']} → карточки на груди — "
                     f"с y ≥ {face['chin_low'] + 20}, над головой — выше y {face['top_high'] - 20}")
    return lines


def decisions(stem: str, fmt: str) -> list:
    """Карта решений: что видно в исходнике и в проекте → что из этого следует для монтажа.

    Речь разбирает analysis(); здесь — то, что решается до раскадровки: чьи правила, какой язык,
    нужна ли финальная плашка, совпадает ли кадр с форматом, хватит ли записи на один ролик и
    видно ли лицо (14.10.2026, «на вход видео — и чётко понятно, что с ним делать»).
    """
    import projects
    from common import probe

    lines = []
    try:
        project, source = projects.of(stem), projects.source(stem)
    except projects.ProjectError as e:
        return [f"- проект: {e} → сначала положи исходник в projects/<проект>/input/"]
    cfg = project.config
    lines.append(f"- проект {project.name} («{project.title}») → правила projects/{project.name}/rules.md "
                 f"важнее стиля: прочитай до раскадровки" + ("" if project.rules.exists() else " (rules.md нет — спроси автора)"))
    if cfg["language"] != "ru":
        lines.append(f"- речь на «{cfg['language']}» → субтитры и надписи на этом языке; русские привычки текста "
                     f"(ё, «ёлочки», шутки серии) не переносить")
    lines.append("- CTA: " + ("финальная плашка «смотри у меня в профиле» — да" if cfg["cta"]
                              else "плашки нет → build_page(..., cta=False), verify_page это проверит"))
    info = probe(source) if source else None
    if info:
        src_w, src_h = info["width"], info["height"]
        want_w, want_h = (int(x) for x in fmt.split(":"))
        if (src_w > src_h) != (want_w > want_h) or (src_w == src_h) != (want_w == want_h):
            side = "горизонталь" if src_w > src_h else "вертикаль" if src_h > src_w else "квадрат"
            lines.append(f"- исходник {src_w}×{src_h} ({side}) под {fmt} → перекадрирование по лицу (prep с "
                         f"\"format\" в edit.json); слово за спиной и подмена фона — только если человек в кадре целиком")
        if info["duration"] > 90:
            lines.append(f"- запись {info['duration'] / 60:.1f} мин → больше одного ролика: нарежь по мыслям "
                         f"(раздел «Нарезка длинного урока» скилла), у каждой части своё имя и свой план")
    faces = WORK_DIR / stem / "aroll.faces.json"
    if faces.exists():
        data = json.loads(faces.read_text(encoding="utf-8"))
        seen = sum(1 for f in data.get("frames", []) if f and f[4] >= 0.6) / max(1, len(data.get("frames", [])))
        if seen < 0.8:
            lines.append(f"- лицо видно в {seen * 100:.0f}% кадров → камера по лицу будет терять его: в эти места — "
                         f"графика на весь кадр или перебивка, а не карточка у лица")
    else:
        lines.append(f"- лицо ещё не найдено (track.py) → раскадровку по лицу не ставь, пока его нет")
    return lines


def skeleton(stem: str) -> str:
    tools = " · ".join(TOOLS)
    meta_path = WORK_DIR / stem / "aroll.json"
    fmt = json.loads(meta_path.read_text(encoding="utf-8")).get("format", "9:16") if meta_path.exists() else "9:16"
    return f"""# План монтажа {stem}

> Сначала план, потом страница (правило Валеры, 13.10.2026). Раздел «Исходник» посчитал plan.py;
> строки со знаком {TODO} заменяет режиссёр. Проверка: .venv/bin/python scripts/plan.py {stem} --check —
> без неё рендер не пойдёт. Что каким инструментом делать — docs/АРСЕНАЛ.md.

## Исходник
{chr(10).join(analysis(stem))}

## Что видно → что делаю
{chr(10).join(decisions(stem, fmt))}

## Мысль ролика
{TODO} одной фразой: что зритель унесёт

## Хук
{TODO} что он увидит и услышит в первые 3 секунды и почему досмотрит

## Раскадровка
| время, с | реплика | что на экране | инструмент | почему он | держится, с |
|---|---|---|---|---|---|
| {TODO} | | | | | |

Инструменты: {tools}. Несколько в одном ударе — через «+».
Смена на экране — не реже раза в {MAX_GAP:g} с, первая — до {HOOK_BY:g} с; плашка без изменений —
не дольше {HOLD_MAX:g} с (иначе пометка «data-hold: причина»).

## Звук
{TODO} какие удары и где; одинаковые не подряд, громкость по норме

## Риски
{TODO} что может сломаться (лицо низко, предмет у края кадра, серые зоны) и чем проверю
"""


def section(text: str, name: str) -> str:
    found = re.search(rf"^## {re.escape(name)}[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return found.group(1).strip() if found else ""


def beats(table: str) -> list:
    """Строки раскадровки: (время, инструменты, держится или None, исходная строка)."""
    rows = []
    for line in table.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or not re.match(r"^\d", cells[0]):
            continue
        start = float(re.match(r"\d+(?:[.,]\d+)?", cells[0]).group(0).replace(",", "."))
        tools = [t.strip().lower() for t in re.split(r"[+,;]", cells[3]) if t.strip()]
        hold = re.match(r"\d+(?:[.,]\d+)?", cells[5])
        rows.append((start, tools, float(hold.group(0).replace(",", ".")) if hold else None, cells[5], line.strip()))
    return rows


def check(stem: str) -> list:
    """Провалы плана; пустой список — можно собирать страницу."""
    path = WORK_DIR / stem / "plan.md"
    if not path.exists():
        return [f"нет плана work/{stem}/plan.md — сначала .venv/bin/python scripts/plan.py {stem} и заполни его"]
    text = path.read_text(encoding="utf-8")
    problems = []
    for name in SECTIONS:
        body = section(text, name)
        if not body or TODO in body:
            problems.append(f"раздел «{name}» не заполнен (осталось {TODO} или пусто)")
    meta_path = WORK_DIR / stem / "aroll.json"
    duration = float(json.loads(meta_path.read_text(encoding="utf-8")).get("duration", 0)) if meta_path.exists() else 0.0
    rows = beats(section(text, "Раскадровка"))
    if not rows:
        problems.append("в раскадровке нет ни одной строки с временем")
        return problems
    lower = {name.lower(): name for name in TOOLS}
    for start, tools, hold, hold_text, line in rows:
        unknown = [t for t in tools if t not in lower]
        if not tools:
            problems.append(f"{start:.1f} с: не указан инструмент — {line}")
        elif unknown:
            problems.append(f"{start:.1f} с: нет в арсенале «{'», «'.join(unknown)}» — выбери из TOOLS (docs/АРСЕНАЛ.md)")
        if hold is not None and hold > HOLD_MAX + 1e-6 and "data-hold" not in hold_text:
            problems.append(f"{start:.1f} с: держится {hold:g} с без изменений — дольше {HOLD_MAX:g} с "
                            f"динамика проседает (оживи изнутри, раздели или пометь «data-hold: причина»)")
    visual = sorted(start for start, tools, *_ in rows if any(lower.get(t) not in NOT_VISUAL for t in tools if t in lower))
    if not visual:
        problems.append("в раскадровке ни одной смены на экране — одни субтитры и звук")
    elif visual[0] > HOOK_BY:
        problems.append(f"первая смена на экране — {visual[0]:.1f} с: хук — до {HOOK_BY:g} с")
    marks = visual + ([duration] if duration else [])
    for a, b in zip(marks, marks[1:]):
        if b - a > MAX_GAP + 1e-6:
            problems.append(f"{a:.1f}–{b:.1f} с: {b - a:.1f} с без смены на экране (дольше {MAX_GAP:g} с) — чем держим внимание?")
    return problems


def main():
    ap = argparse.ArgumentParser(description="План монтажа до страницы и рендера")
    ap.add_argument("stem", help="ролик: IMG_3317")
    ap.add_argument("--check", action="store_true", help="проверить заполненный план")
    ap.add_argument("--force", action="store_true", help="переписать план заново (заполненное пропадёт)")
    args = ap.parse_args()
    if args.check:
        problems = check(args.stem)
        if problems:
            print(f"✗ план {args.stem} не готов:")
            for p in problems:
                print(f"    — {p}")
            sys.exit(1)
        print(f"✓ план {args.stem} заполнен и годится: инструменты из арсенала, смена на экране не реже раза в {MAX_GAP:g} с")
        return
    path = WORK_DIR / args.stem / "plan.md"
    if path.exists() and not args.force:
        sys.exit(f"✗ план уже есть: {path.relative_to(ROOT)} — правь его; заново — с --force (заполненное пропадёт)")
    path.write_text(skeleton(args.stem), encoding="utf-8")
    print(f"✓ каркас плана: {path.relative_to(ROOT)} — заполни разделы со знаком {TODO}, потом --check")


if __name__ == "__main__":
    main()
