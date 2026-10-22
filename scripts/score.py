#!/usr/bin/env python3
"""Партитура ролика: решения режиссёра данными, а не программой (19.10.2026, этап 3 автономного монтажа).

Мозг студии монтировал ролик одним ходом на 200–300 тыс. токенов ($2–31 за ролик): читал ~160 КБ правил и писал
page.py — программу с нуля. Партитура — только решения: что показать, на каких словах, каким приёмом. Страницу из неё
собирает этот модуль через Montage (обязательное — склейки, вспышку хука, звуки, музыку — ставит сборка), без ИИ.
Аналитик (scripts/analyst.py) пишет партитуру коротким ходом, verify_page проверяет страницу, критик правит партитуру.

Время — номерами слов дубля (work/<имя>/aroll.words.json, как в transcript аналитика): «w»: [от, до] — окно приёма
от начала слова «от» до конца слова «до». Так время ложится на речь само, и считать секунды не надо.

  work/<имя>/score.json (вариант — score.<вариант>.json):
  {
    "title": "…", "hook": "auto" | {"w": 11} | {"none": "почему без вспышки"}, "cta": {"w": 157},
    "accent": ["узбекские", "индии", …],           # ключевые слова субтитров: одно на 5–8 с речи
    "text_fixes": {"126": "X,"}, "keep_case": ["ЕГЭ"],
    "hide": [[12, 16]],                             # слова без субтитров: текст на экране повторяет речь
    "items": [
      {"kind": "word",   "w": [3, 7], "at": 7, "text": "узбекские"},           # крупное слово над головой, удар на «at»
      {"kind": "stamp",  "w": [118, 118], "text": "гениально"},                # штамп на груди
      {"kind": "write",  "w": [12, 20], "layout": "chest", "text": "1 2 3 4 5", "sub": "«арабские»", "hide": true},
      {"kind": "write",  "w": [100, 111], "layout": "split", "text": "А В Г", "sub": "= 1 2 3", "over": 110, "titlo": true},
      {"kind": "route",  "layout": "behind", "until": 75, "bend": -0.22,
       "stops": [{"label": "Индия", "x": 0.9, "y": 0.2, "w": 64}, …]},
      {"kind": "timeline", "layout": "split", "until": 56, "marks": [{"label": "IX век", "sub": "Багдад", "w": 43}, …]},
      {"kind": "compass" | "hexes" | "cuboid" | "plot", "w": [i, j], "layout": "…", …параметры приёма blueprint},
      {"kind": "trilat", "w": [55, 89], "sats": [56, 76, 80], "fix": 85, "roam": 71, "sphere": 89, "label": "ты"},
      {"kind": "clip",   "w": [34, 41], "name": "a_india", "label": "Индия, V век"},     # клип Flow, уже принятый
      # приёмы дизайн-системы проекта (projects/<проект>/DESIGN.md, scripts/design.py) — только там, где она есть:
      {"kind": "hand",    "w": [0, 2], "text": "почему соседняя", "line": true},       # пометка рукой над головой
      {"kind": "number",  "w": [30, 34], "at": 32, "text": "2/3", "sub": "шанс, что другая быстрее"},
      {"kind": "promise", "w": [40, 70], "title": "3 причины",                         # список-обещание на груди
       "rows": [{"text": "вероятность", "w": 45}, {"text": "память", "w": 58}, {"text": "теория очередей", "w": 66}]},
      {"kind": "strike",  "w": [80, 82], "at": 82, "text": "проклят"},              # красная ручка по мифу
      # 21.10.2026 — арсенал шире «Чертежа» (Валера: «визуал скучный… каждый раз что-то выдумываем»):
      {"kind": "count",   "w": [113, 140], "sub": "знакомых",                         # число растёт шагами на словах
       "steps": [{"text": "100", "w": 113}, {"text": "10 000", "w": 121}, {"text": "1 млн", "w": 125}]},
      {"kind": "scene",   "w": [60, 70], "layer": "front", "html": "<div id=\"$id\" class=\"g\">…</div>",
       "css": "#$id { … }", "js": "enter('#$id', {w:60}); leave('#$id', {e:70});"},       # своя сцена режиссёра
      {"kind": "wall",    "w": [30, 40], "notes": [{"text": "1929 — Каринти", "w": 31}]},   # заметки к стене за спиной
      {"kind": "paper",   "w": [5, 7], "text": "МАСК"},                               # коллаж: слово из вырезанных букв
      {"kind": "vertigo" | "frame" | "doodle" | "zoom", "w": [i, j]}               # движения кадра (zoom — на w[0])
    ],
    "concept": {"idea": "…", "motif": "…", "hook": "…"}   # идея ролика: своя, не как у прошлых (novelty)
  }

  .venv/bin/python scripts/score.py IMG_3292 --variant montage           # страница studio/IMG_3292--montage
  .venv/bin/python scripts/score.py IMG_3292 --variant auto --check      # только проверить партитуру
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import blueprint as bp  # noqa: E402
import design  # noqa: E402
from common import WORK_DIR  # noqa: E402

RED = bp.RED
SCORE_MARK = "reels-score"
LAYOUTS = bp.LAYOUTS
# поля каждого приёма: обязательные и необязательные (всё прочее — громкая ошибка: опечатка не должна молча пропасть)
KINDS = {
    "word": ({"w", "text"}, {"at", "red", "size"}),
    "stamp": ({"w", "text"}, {"rot"}),
    "write": ({"w", "text"}, {"layout", "sub", "red", "dur", "over", "titlo", "hide"}),
    "route": ({"stops", "until"}, {"layout", "bend", "hide"}),
    "timeline": ({"marks", "until"}, {"layout", "hide"}),
    "compass": ({"w"}, {"layout", "label", "center", "radius", "hide"}),
    "hexes": ({"w"}, {"layout", "cols", "rows", "red", "label", "hide"}),
    "cuboid": ({"w"}, {"layout", "dims", "hide"}),
    "plot": ({"w", "ys"}, {"layout", "mark", "xlabel", "ylabel", "label", "hide"}),
    "trilat": ({"w", "sats", "fix"}, {"layout", "roam", "sphere", "label", "hide"}),
    "clip": ({"w", "name"}, {"label"}),
    # дизайн-система проекта (DESIGN.md): пометка рукой, число отливом, список-обещание, красная ручка по мифу
    "hand": ({"w", "text"}, {"line", "hide"}),
    "number": ({"w", "text"}, {"at", "sub", "hide"}),
    "promise": ({"w", "title", "rows"}, set()),
    "strike": ({"w", "text"}, {"at"}),
    # 21.10.2026: свои сцены режиссёра и приёмы fx.py — в цветах и шрифтах дизайн-системы (fx.use_design)
    "count": ({"w", "steps"}, {"sub", "hide"}),
    "scene": ({"w", "html"}, {"js", "css", "layer", "fg", "hide"}),
    # orbit, phone, glass, cover из fx.py — нет: они рассчитаны на голову ниже (над ней ≥ 300 px), а у говорящей головы
    # в кадре проекта над головой 60–100 px — закрывают лицо или прячут текст за головой (проба IMG_3651, 21.10.2026).
    # Карточки по кругу или телефон под эту раскладку режиссёр рисует своей сценой ("scene") со своей геометрией.
    "wall": ({"w", "notes"}, set()),
    "paper": ({"w", "text"}, {"hide"}),
    "vertigo": ({"w"}, set()),
    "frame": ({"w"}, set()),
    "doodle": ({"w"}, set()),
    "zoom": ({"w"}, set()),
}
FX_KINDS = {"wall", "paper", "vertigo", "frame", "doodle", "zoom"}
SCENE_MAX = 6000           # знаков в html+css+js одной сцены: сцена — один момент, а не вторая страница
DESIGN_KINDS = {"hand", "number", "promise", "strike"}
TOP = {"title", "hook", "cta", "accent", "text_fixes", "keep_case", "hide", "items", "concept", "_note"}
SAME_RUN = 2           # приёмов подряд в одной раскладке — больше однообразно
TEXT_MAX = {"word": 12, "stamp": 14, "write": 18,      # знаков в одну строку: крупное слово, штамп, запись,
            "hand": 26, "number": 7, "strike": 14, "promise": 22,   # пометка, число, миф, заголовок списка
            "paper": 10}                                             # слово из вырезанных букв
ROW_MAX, ROWS = 24, (2, 4)                             # строка списка-обещания; строк в нём
LIST_TOP = 1262        # px: верх списка и мифа на груди — под линией субтитров (1150), над рукой с микрофоном
SUB_MAX, LABEL_MAX = 30, 14                             # подпись под записью или у клипа; метка маршрута и оси
WORD_MIN = 96          # px: меньше кегль слова над головой не читается — тогда слово на груди
CTA_TAIL = 2.8          # с: от призыва до конца речи — субтитры спрятаны с призыва − 0,2 с (verify_page: не дольше 3 с)
MIN_SHOW = 0.9          # с: короче окно приёма сборка продлевает — «Чертёж» не успеть прочесть быстрее 0,8 с
# px: ширина строки над головой — поле без боковых обрезов Instagram (x 102–978) с запасом; было 0,9 кадра (972 px), и
# «РУКОПОЖАТИЙ» и «100 000 000» уходили под обрез (IMG_3651, 21.10.2026)
SAFE_W = 840
# px: строка по центру на груди — справа там кнопки YouTube с x 834 (formats.SAFE_TEXT_WIDTH 590): было 0,9 × 700–760,
# и «100 млн», «10 млрд» на груди заезжали под кнопки (IMG_3651, 21.10.2026)
CHEST_W = 570


class ScoreError(ValueError):
    """Партитура с ошибкой — по-русски, с местом: аналитик или человек правит по этому тексту."""


def path_of(stem: str, variant: str | None = None) -> Path:
    return WORK_DIR / stem / (f"score.{variant}.json" if variant else "score.json")


def load(stem: str, variant: str | None = None) -> dict:
    path = path_of(stem, variant)
    if not path.exists():
        raise ScoreError(f"нет партитуры {path.relative_to(WORK_DIR.parent)} — её пишет scripts/analyst.py {stem}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ScoreError(f"{path.name}: не JSON — {e}") from None


def check(score: dict, words: list) -> list:
    """Все ошибки партитуры списком (пусто — годна). Проверяется форма; смысл — verify_page по собранной странице."""
    errs, n = [], len(words)
    for key in score:
        if key not in TOP:
            errs.append(f"поле «{key}» не знаю — есть {', '.join(sorted(TOP))}")

    def word(i, where: str) -> bool:
        if not isinstance(i, int) or not 0 <= i < n:
            errs.append(f"{where}: номер слова {i!r} — нужен целый от 0 до {n - 1}")
            return False
        return True

    def span(w, where: str) -> bool:
        if not (isinstance(w, list) and len(w) == 2):
            errs.append(f"{where}: «w» — пара номеров слов [от, до], а не {w!r}")
            return False
        ok = word(w[0], where) and word(w[1], where)
        if ok and w[0] > w[1]:
            errs.append(f"{where}: «w» {w} — начало позже конца")
            return False
        return ok

    hook = score.get("hook", "auto")
    if not (hook == "auto" or (isinstance(hook, dict) and ("w" in hook or hook.get("none")))):
        errs.append(f"hook: \"auto\", {{\"w\": номер}} или {{\"none\": \"почему\"}} — а не {hook!r}")
    elif isinstance(hook, dict) and "w" in hook:
        word(hook["w"], "hook")
    if "cta" in score:
        if not (isinstance(score["cta"], dict) and "w" in score["cta"]):
            errs.append("cta: {\"w\": номер слова, с которого плашка в конце}")
        else:
            word(score["cta"]["w"], "cta")
    if isinstance(score.get("cta"), dict) and isinstance(score["cta"].get("w"), int) and 0 <= score["cta"]["w"] < n:
        # с призыва субтитры спрятаны до конца (плашка сама говорит «переходи») — дольше 3 с без субтитров нельзя
        cta_at, last = words[score["cta"]["w"]]["start"], words[-1]["end"]
        if last - cta_at > CTA_TAIL:
            fit = [i for i, w in enumerate(words) if last - w["start"] <= CTA_TAIL]
            errs.append(f"cta на слове {score['cta']['w']}: до конца речи {last - cta_at:.1f} с, а с призыва субтитры "
                        f"спрятаны — не больше {CTA_TAIL:g} с: ставь на слово {fit[0] if fit else n - 1} или позже")
        for k, item in enumerate(score.get("items") or []):
            tail = item.get("w", [None, None])[1] if isinstance(item.get("w"), list) else item.get("until")
            if isinstance(tail, int) and 0 <= tail < n and words[tail]["end"] > cta_at:
                errs.append(f"items[{k}] ({item.get('kind')}): идёт после призыва (слово {score['cta']['w']}) — "
                            f"конец ролика занят плашкой, вставку убери или кончай раньше")
    for k, h in enumerate(score.get("hide") or []):
        span(h, f"hide[{k}]")
    for key in (score.get("text_fixes") or {}):
        if not str(key).isdigit() or not 0 <= int(key) < n:
            errs.append(f"text_fixes: ключ {key!r} — номер слова от 0 до {n - 1}")
    for k, item in enumerate(score.get("items") or []):
        where = f"items[{k}]"
        kind = item.get("kind")
        if kind not in KINDS:
            errs.append(f"{where}: приёма «{kind}» нет — есть {', '.join(KINDS)}")
            continue
        where = f"{where} ({kind})"
        need, may = KINDS[kind]
        for key in need - set(item):
            errs.append(f"{where}: нет поля «{key}»")
        for key in set(item) - need - may - {"kind"}:
            errs.append(f"{where}: поле «{key}» у этого приёма не бывает — есть {', '.join(sorted(need | may))}")
        if "w" in item:
            span(item["w"], where)
        if "layout" in item and item["layout"] not in LAYOUTS:
            errs.append(f"{where}: раскладки «{item['layout']}» нет — есть {', '.join(LAYOUTS)}")
        for key in ("at", "over", "until", "fix", "roam", "sphere"):
            if key in item:
                word(item[key], f"{where}.{key}")
        if kind == "trilat":
            # три спутника по порядку речи внутри окна, точка — не раньше третьего
            sats, win = item.get("sats"), item.get("w") if isinstance(item.get("w"), list) else [None, None]
            if not (isinstance(sats, list) and len(sats) == 3 and all(isinstance(i, int) for i in sats)):
                errs.append(f"{where}.sats: три номера слов — на каждом встаёт свой спутник")
            elif sats != sorted(sats) or not all(isinstance(x, int) for x in win) or not win[0] <= sats[0] or \
                    not (isinstance(item.get("fix"), int) and sats[2] <= item["fix"] <= win[1]):
                errs.append(f"{where}: нужно w[0] ≤ sats по порядку ≤ fix ≤ w[1] — а не w {win}, sats {sats}, "
                            f"fix {item.get('fix')}")
        _check_new(kind, item, where, errs, word)
        # надпись — одна строка без переноса: предложение в подписи уходит за кадр (19.10.2026, аналитик IMG_3303:
        # «плоскости теряют даже плотно уложенные круги» вылезла на 785 px). Длиннее — короче или в субтитры
        texts = [("text", item.get("text"), TEXT_MAX.get(kind, 18)), ("sub", item.get("sub"), SUB_MAX),
                 ("label", item.get("label"), SUB_MAX), ("title", item.get("title"), TEXT_MAX.get(kind, 18))]
        if kind == "promise" and isinstance(item.get("rows"), list):       # у hexes «rows» — число рядов
            texts += [(f"rows[{j}].text", r.get("text"), ROW_MAX) for j, r in enumerate(item["rows"]) if isinstance(r, dict)]
        if kind == "promise":
            # пункты — по порядку речи и внутри окна списка: квадрат заливается на слове пункта
            rows, prev = item.get("rows"), None
            if not isinstance(rows, list) or not ROWS[0] <= len(rows) <= ROWS[1]:
                errs.append(f"{where}.rows: {ROWS[0]}–{ROWS[1]} строки [{{\"text\": \"…\", \"w\": номер слова}}, …]")
                rows = []
            win = item.get("w") if isinstance(item.get("w"), list) and len(item["w"]) == 2 else None
            for j, r in enumerate(rows):
                if not isinstance(r, dict) or not isinstance(r.get("text"), str) or "w" not in r:
                    errs.append(f"{where}.rows[{j}]: нужны «text» и «w» (слово, на котором пункт пройден)")
                    continue
                if not word(r["w"], f"{where}.rows[{j}]"):
                    continue
                if win and all(isinstance(x, int) for x in win) and not win[0] <= r["w"] <= win[1]:
                    errs.append(f"{where}.rows[{j}]: слово {r['w']} вне окна списка {win}")
                if prev is not None and r["w"] <= prev:
                    errs.append(f"{where}.rows[{j}]: пункты по порядку речи — слово {r['w']} не позже {prev}")
                prev = r["w"]
        texts += [(f"{key}[{j}].{f}", step.get(f), LABEL_MAX if f == "label" else SUB_MAX)
                  for key in ("stops", "marks") for j, step in enumerate(item.get(key) or []) if isinstance(step, dict)
                  for f in ("label", "sub")]
        for field, value, limit in texts:
            if isinstance(value, str) and len(value) > limit:
                errs.append(f"{where}.{field}: «{value}» — {len(value)} знаков, а в строку влезает {limit}: скажи короче")
        for list_key in ("stops", "marks"):
            for j, step in enumerate(item.get(list_key) or []):
                if not isinstance(step, dict) or "label" not in step or "w" not in step:
                    errs.append(f"{where}.{list_key}[{j}]: нужны «label» и «w» (номер слова, на котором шаг)")
                else:
                    word(step["w"], f"{where}.{list_key}[{j}]")
                if list_key == "stops" and isinstance(step, dict) and not all(
                        isinstance(step.get(c), (int, float)) and 0 <= step[c] <= 1 for c in ("x", "y")):
                    errs.append(f"{where}.stops[{j}]: «x», «y» — доли поля от 0 до 1")
    # однообразие (19.10.2026, аналитик IMG_3292: пять вставок подряд «на груди» — все легли на банку в руке):
    # не больше SAME_RUN приёмов подряд в одной раскладке
    def first(item):
        w = item.get("w") or [None]
        steps = item.get("stops") or item.get("marks") or [{}]
        return w[0] if isinstance(w[0], int) else steps[0].get("w", 0)
    placed = sorted((first(it), where_of(it), k) for k, it in enumerate(score.get("items") or [])
                    if isinstance(it, dict) and it.get("kind") in KINDS and isinstance(first(it), int))
    for j in range(len(placed) - SAME_RUN):
        run = placed[j:j + SAME_RUN + 1]
        if len({r[1] for r in run}) == 1:
            errs.append(f"items {', '.join(str(r[2]) for r in run)}: {SAME_RUN + 1} подряд «{run[0][1]}» — однообразно, "
                        f"чередуй раскладки (за спиной, на груди, сплит) и виды приёмов")
            break
    return errs


def _steps(item: dict, key: str, where: str, errs: list, word, fields: tuple, limit: int, lo: int = 1, hi: int = 8):
    """Шаги приёма по словам (count.steps, wall.notes): по порядку речи и внутри окна."""
    rows, prev = item.get(key), None
    if not isinstance(rows, list) or not lo <= len(rows) <= hi:
        errs.append(f"{where}.{key}: {lo}–{hi} шагов [{{{', '.join(f'\"{f}\": …' for f in fields)}, \"w\": номер слова}}, …]")
        return
    win = item.get("w") if isinstance(item.get("w"), list) and len(item["w"]) == 2 else None
    for j, r in enumerate(rows):
        if not isinstance(r, dict) or "w" not in r or any(not isinstance(r.get(f), str) for f in fields):
            errs.append(f"{where}.{key}[{j}]: нужны {', '.join(fields)} и «w»")
            continue
        if not word(r["w"], f"{where}.{key}[{j}]"):
            continue
        if win and all(isinstance(x, int) for x in win) and not win[0] <= r["w"] <= win[1]:
            errs.append(f"{where}.{key}[{j}]: слово {r['w']} вне окна {win}")
        if prev is not None and r["w"] <= prev:
            errs.append(f"{where}.{key}[{j}]: по порядку речи — слово {r['w']} не позже {prev}")
        prev = r["w"]
        for f in fields:
            if f != "from" and len(r[f]) > limit:
                errs.append(f"{where}.{key}[{j}].{f}: «{r[f]}» — {len(r[f])} знаков, влезает {limit}")


def _check_new(kind: str, item: dict, where: str, errs: list, word) -> None:
    """Форма видов, пришедших 21.10.2026: счётчик, своя сцена, приёмы fx."""
    if kind == "count":
        _steps(item, "steps", where, errs, word, ("text",), 11, 2, 6)
    elif kind == "wall":
        _steps(item, "notes", where, errs, word, ("text",), 28, 1, 5)
    elif kind == "scene":
        _check_scene(item, where, errs, word)


SCENE_LAYERS = {"split": "человек в окне внизу, сцена над ним (главные сцены)", "full": "во весь кадр, без человека",
                "behind": "за человеком на весь фон (видны края и верх)", "front": "поверх человека, мимо лица (мелочь на груди)"}
SCENE_ID = re.compile(r"""\bid=["']([^"']*)["']""")       # кавычки любые: ИИ пишет и так, и так


def _check_scene(item: dict, where: str, errs: list, word) -> None:
    """Своя сцена режиссёра: корень <div id="$id" class="g …">, все id — от $id, стили — только своих элементов,
    время в js — словами {w:N} (начало) и {e:N} (конец), цвета и шрифты — переменными и классами системы
    (verify_page проверит то, что получится на экране)."""
    html_, css, js = item.get("html", ""), item.get("css", ""), item.get("js", "")
    if not all(isinstance(x, str) for x in (html_, css, js)):
        errs.append(f"{where}: html, css, js — строки")
        return
    if len(html_) + len(css) + len(js) > SCENE_MAX:
        errs.append(f"{where}: сцена {len(html_) + len(css) + len(js)} знаков — больше {SCENE_MAX}: это один момент, упрости")
    if not re.match(r"""\s*<div\s+id=["']\$id["']\s+class=["']g\b""", html_):
        errs.append(f'{where}.html: начинается с <div id="$id" class="g …"> — корень сцены')
    bad = [i for i in SCENE_ID.findall(html_) if not (i == "$id" or i.startswith("$id-"))]
    if bad:
        errs.append(f"{where}.html: id {', '.join(bad[:3])} — только $id и $id-что-то (иначе столкнётся с чужими)")
    if re.search(r"<\s*/?\s*(script|style|iframe|link|img)\b", html_ + css + js, re.I):
        errs.append(f"{where}: без <script>, <style>, <iframe>, <link>, <img> — стили в css, движение в js")
    if re.search(r"https?://|url\(", html_ + css):
        errs.append(f"{where}: без ссылок и url(): всё рисуется здесь (svg, css), сеть при рендере не нужна")
    for sel in re.findall(r"([^{}]+)\{", re.sub(r"@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)):
        for one in sel.split(","):
            if one.strip() and not one.strip().startswith("#$id"):
                errs.append(f"{where}.css: селектор «{one.strip()[:40]}» — только #$id и его потомки")
                break
    for n in re.findall(r"\{[we]:(-?\d+)\}", js + css + html_):
        word(int(n), f"{where}: {{w:{n}}}")
    if re.search(r"\b(setTimeout|setInterval|requestAnimationFrame|Date\.now|Math\.random|fetch)\b", js):
        errs.append(f"{where}.js: только таймлайн tl и помощники страницы — без своих часов и случайности "
                    "(рендер шагает по кадрам: один кадр — одна картинка)")
    if item.get("layer", "front") not in SCENE_LAYERS:
        errs.append(f"{where}.layer: " + ", ".join(f"\"{k}\" — {v}" for k, v in SCENE_LAYERS.items()))


# ---------------------------------------------------------------- каждый ролик — своя идея (21.10.2026)
# Валера после IMG_3651: «тупо скопировал стиль прошлого удачного видео — вообще не ок… в правила общие всей системы
# заложи, что мы не берём одинаковые вещи, мы каждый раз что-то выдумываем». Все партитуры до этого — в основном
# «write» (число текстом на груди): у IMG_3651 9 из 18. Проверка сверяет идею, хук и набор приёмов с прошлыми роликами
# проекта (и его разделов) и не пускает однообразие внутри ролика.
RECENT = 4             # с последними сколькими роликами проекта сверять
MOTIF_SAME = 0.5       # доля общих слов мотива (Жаккар) — с этой и выше мотив тот же
KINDS_SAME = 0.8       # косинус составов приёмов — с этого и выше «в основном те же приёмы»
ONE_KIND = 0.35        # один вид — не больше этой доли вставок ролика (от 6 вставок)
CONCEPT = ("idea", "motif", "hook")
STOP = set("и в во на с со по к а не но за из от до для как что это то же ли или у о об при над под".split())


def _words(text: str) -> set:
    return {w[:6] for w in re.findall(r"[\wё]+", str(text).lower()) if len(w) > 2 and w not in STOP}


def _profile(items: list) -> dict:
    out = {}
    for it in items:
        if isinstance(it, dict) and it.get("kind") in KINDS:
            out[it["kind"]] = out.get(it["kind"], 0) + 1
    return out


def _cos(a: dict, b: dict) -> float:
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in set(a) | set(b))
    na, nb = sum(v * v for v in a.values()) ** 0.5, sum(v * v for v in b.values()) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _opening(items: list) -> str:
    """Чем открыт ролик: вид первой вставки по времени."""
    firsts = [(it["w"][0], it["kind"]) for it in items if isinstance(it, dict) and isinstance(it.get("w"), list)
              and it["w"] and isinstance(it["w"][0], int)]
    return min(firsts)[1] if firsts else ""


def recent_scores(stem: str, limit: int = RECENT) -> list:
    """[(имя ролика, партитура)] последних роликов того же проекта (с разделами), свежие первыми; без этого ролика.
    У ролика с вариантами берётся самая свежая партитура."""
    import projects
    try:
        home = projects.of_or_default(stem).home
    except projects.ProjectError:
        return []
    found = []
    for other, (project, _) in projects.index().items():
        if other == stem or project.home != home:
            continue
        files = sorted((WORK_DIR / other).glob("score*.json"), key=lambda f: -f.stat().st_mtime)
        if files:
            try:
                found.append((files[0].stat().st_mtime, other, json.loads(files[0].read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, OSError):
                continue
    return [(name, sc) for _, name, sc in sorted(found, key=lambda x: -x[0])[:limit]]


def novelty(stem: str, score: dict, variant: str | None = None) -> list:
    """Провалы «одинакового»: нет идеи ролика, один приём на весь ролик, своей сцены нет, идея, хук или набор приёмов
    как у недавнего ролика проекта. Пусто — ролик свой."""
    errs, items = [], [it for it in score.get("items") or [] if isinstance(it, dict)]
    concept = score.get("concept")
    if not (isinstance(concept, dict) and all(isinstance(concept.get(k), str) and len(concept[k].strip()) >= 8 for k in CONCEPT)):
        errs.append("concept: идея ролика — {\"idea\": \"о чём и как показываем\", \"motif\": \"визуальный мотив именно этой "
                    "истории\", \"hook\": \"чем бьёт первая секунда\"} — каждое не короче 8 знаков; придумай своё, не как в "
                    "прошлых роликах")
        concept = {}
    prof = _profile(items)
    total = sum(prof.values())
    if total >= 6:
        kind, n = max(prof.items(), key=lambda kv: kv[1])
        if n / total > ONE_KIND:
            errs.append(f"однообразно: «{kind}» — {n} из {total} вставок (больше {ONE_KIND:.0%}). Каждый момент — своим "
                        f"самым сильным приёмом: число растёт — count, люди, связи, переписка — своя сцена, путь — route…")
    if not any(it.get("kind") == "scene" for it in items):
        errs.append("нет ни одной своей сцены (kind \"scene\"): готовые приёмы — опора, а главный момент ролика придумай "
                    "сам — html/css/js под эту историю")
    for name, old in recent_scores(stem):
        old_items = [it for it in old.get("items") or [] if isinstance(it, dict)]
        old_concept = old.get("concept") or {}
        if concept and old_concept:
            a, b = _words(concept.get("motif", "")), _words(old_concept.get("motif", ""))
            if a and b and len(a & b) / len(a | b) >= MOTIF_SAME:
                errs.append(f"мотив «{concept['motif']}» — как у {name} («{old_concept.get('motif')}»): придумай свой под эту историю")
        sim = _cos(prof, _profile(old_items))
        if total >= 4 and sim >= KINDS_SAME:
            errs.append(f"набор приёмов как у {name} (сходство {sim:.2f}: {dict(sorted(_profile(old_items).items()))}) — "
                        f"в основном те же приёмы; возьми другие под моменты этой истории")
        if _opening(items) and _opening(items) == _opening(old_items) and name == (recent_scores(stem, 1) or [("", {})])[0][0]:
            errs.append(f"хук открыт тем же приёмом «{_opening(items)}», что и прошлый ролик {name} — реши первую секунду иначе")
    return errs


def where_of(item: dict) -> str:
    """Где приём на экране: раскладка «Чертежа», а для своих видов — их место."""
    fixed = {"word": "behind", "stamp": "chest", "clip": "full", "hand": "behind", "number": "behind",
             "promise": "chest", "strike": "chest", "count": "behind", "wall": "wall", "paper": "full",
             "vertigo": "camera", "frame": "frame", "doodle": "doodle", "zoom": "camera"}
    if item.get("kind") == "scene":
        return f"scene-{item.get('layer', 'front')}"
    defaults = {"write": "split", "route": "behind", "timeline": "split", "compass": "behind", "hexes": "behind",
                "cuboid": "split", "plot": "split", "trilat": "split"}
    return fixed.get(item.get("kind")) or item.get("layout") or defaults.get(item.get("kind"), "?")


def build(stem: str, variant: str | None = None, score: dict | None = None) -> str:
    """Страница studio/<имя>[--вариант]/index.html из партитуры: каждый приём — через Montage и blueprint."""
    from montage import Montage
    m = Montage(stem, variant)
    words = m.tk.words
    score = score if score is not None else load(stem, variant)
    errs = check(score, words)
    if errs:
        raise ScoreError("партитура с ошибками:\n  " + "\n  ".join(errs))
    start = lambda i: round(words[i]["start"], 2)      # noqa: E731
    end = lambda i: round(words[i]["end"], 2)          # noqa: E731

    import fx
    fx.use_for(stem)                    # приёмы fx — в цветах и шрифтах системы проекта (или его темы)
    for k, item in enumerate(score.get("items") or []):
        kind, pid = item["kind"], f"s{k}-{item['kind']}"
        a, b = (start(item["w"][0]), end(item["w"][1])) if "w" in item else (None, None)
        if a is not None and b - a < MIN_SHOW:
            b = round(a + MIN_SHOW, 2)
        try:
            if kind in DESIGN_KINDS and not m.design:
                raise ValueError(f"приём {kind} — из дизайн-системы, а у проекта {m.project.name} нет DESIGN.md")
            if kind == "word":
                _word(m, pid, item, a, b, start(item.get("at", item["w"][0])))
            elif kind == "stamp":
                _stamp(m, pid, item, a, b)
            elif kind == "hand":
                _hand(m, pid, item, a, b)
            elif kind == "number":
                _number(m, pid, item, a, b, start(item.get("at", item["w"][0])))
            elif kind == "promise":
                _promise(m, pid, item, a, b, start, end)
            elif kind == "strike":
                _strike(m, pid, item, a, b, start(item.get("at", item["w"][1])))
            elif kind == "clip":
                m.footage(pid, item["name"], a, round(b - a, 2), label=item.get("label", ""))
            elif kind == "count":
                _count(m, pid, item, a, b, start, end)
            elif kind == "scene":
                _scene(m, pid, item, a, b, start, end)
            elif kind in FX_KINDS:
                _fx(m, pid, item, a, b, start)
            else:
                piece = _piece(kind, pid, item, a, b, start, end)
                m.blueprint(piece)
                if item.get("hide"):
                    m.hide(piece.t0 - 0.05, piece.t1)
        except (ValueError, FileNotFoundError) as e:
            raise ScoreError(f"items[{k}] ({kind}): {e}") from None
    for h in score.get("hide") or []:
        m.hide(start(h[0]) - 0.05, end(h[1]))
    hook = score.get("hook", "auto")
    if isinstance(hook, dict):
        m.hook(start(hook["w"]) if "w" in hook else None, hook.get("none", ""))
    cta = score.get("cta")
    page = m.build(score.get("title") or stem, cta_at=start(cta["w"]) if cta else None,
                   text_fixes=score.get("text_fixes") or {}, keep_case=score.get("keep_case") or [],
                   accent_words=score.get("accent") or [])
    # метка: страница собрана из партитуры — render_reel берёт её планом вместо plan.md (решения до сборки — те же)
    from compose import STUDIO, project_name
    name = path_of(stem, variant).name
    page = page.replace('<meta name="reels-montage"', f'<meta name="{SCORE_MARK}" content="{name}" />\n    <meta name="reels-montage"', 1)
    (STUDIO / project_name(stem, variant) / "index.html").write_text(page, encoding="utf-8")
    return page


def plan_problems(stem: str, variant: str | None, page: str) -> list | None:
    """Провалы «плана» страницы, собранной из партитуры: партитура и есть план (решения до сборки, по словам дубля).
    None — страница не из партитуры, план — plan.md (plan.py --check)."""
    found = re.search(rf'<meta name="{SCORE_MARK}" content="([^"]+)"', page)
    if not found:
        return None
    from kit import Take
    try:
        return [f"партитура: {e}" for e in check(load(stem, variant), Take(stem, variant).words)]
    except ScoreError as e:
        return [str(e)]


def _word(m, pid: str, item: dict, a: float, b: float, at: float) -> None:
    """Крупное слово над головой, как хук «УЗБЕКСКИЕ»: человек поверх (окно вырезки), удар камеры и звук на «at»,
    субтитры этих слов спрятаны — слово на экране и есть речь.

    Кегль — по месту над головой в этом окне (голова — как у verify_page: лицо и 0,2 его высоты на волосы): в IMG_3303
    голова выше, и слово в 170 px уходило за неё наполовину (19.10.2026). Места меньше WORD_MIN — слово на груди."""
    text = item["text"]
    leave = max(b, at + 0.6)
    x0, y0, x1, y1 = m._face(min(a, at), leave)
    # голова — как у verify_page (лицо, 0,2 высоты на волосы, по 0,15 ширины с боков), 25 px — на удар камеры (punch):
    # строка не должна уходить за голову больше чем на 0,2 своей площади (проверка допускает треть)
    top, head_w = y0 - 0.2 * (y1 - y0) - 25, (x1 - x0) * 1.3
    em = max(bp._em(text.upper(), "Oswald", -0.01), 1)
    wide = int(min(170, SAFE_W / em))

    def hidden(px: int) -> float:
        line = 0.92 * px
        return max(0.0, bp.TOP_LINE + 2 + line - top) / line * min(1.0, head_w / (em * px))
    size = item.get("size") or next((px for px in range(wide, 59, -2) if hidden(px) <= 0.2), 0)
    # в дизайн-системе красный — только ошибка: крупное слово кремом, если партитура не сказала "red": true
    color = f" color: {RED};" if item.get("red", not m.design) else ""
    body = design.letters(text) if m.design else text
    if size >= WORD_MIN:
        m.behind(f'        <div id="{pid}" class="g big" style="top: {bp.TOP_LINE + 2}px; font-size: {size}px;{color}">{body}</div>')
        m.fg(min(a, at) - 0.3, leave + 0.25)
    else:                                       # над головой тесно — на груди, под линией субтитров, поверх человека
        size = min(wide, 150)
        m.front(f'        <div id="{pid}" class="g big" data-safe="крупное слово на груди: над головой нет места" '
                f'data-safe-zones="низ" style="top: 1240px; font-size: {size}px;{color}">{body}</div>')
        m.notes.append(f"слово «{text}» — на груди: над головой (верх головы y {top:.0f}) не встаёт и в {WORD_MIN} px")
    if m.design:                                # буквы из дыма, слева направо; удар камеры и звук — на «at»
        m.js(f'      dsSmoke("#{pid}", {min(a, at):.2f});\n'
             f'      leave("#{pid}", {leave:.2f}, {{ y: -60, dur: 0.2 }});')
    else:
        m.js(f'      slam("#{pid}", {at:.2f}, {{ fromScale: 1.5 }});\n'
             f'      leave("#{pid}", {leave:.2f}, {{ y: -60, dur: 0.2 }});')
    m.hide(min(a, at) - 0.05, leave + 0.05)
    m.sound(f"{pid}-hit", "impact-bass-1", at, 0.9)
    m.punch(at, leave)


def _stamp(m, pid: str, item: dict, a: float, b: float) -> None:
    """Штамп на груди («гениально»): красная рамка, впечатывается с поворотом; субтитр этого слова спрятан."""
    text, rot = item["text"], item.get("rot", -5)
    width = bp._em(text.upper(), "Oswald", 0.04) * 72 + 48
    left = round((bp.W - width) / 2)
    m.front(f'        <div id="{pid}" class="g stamp" data-safe="на груди ниже подбородка" '
            f'style="left: {left}px; top: 1250px; font-size: 72px; transform: rotate({rot}deg); '
            f'background: rgba(20,18,16,0.72);">{text}</div>')   # подложка: красное на красной банке не читалось
    leave = max(b + 0.6, a + 1.0)
    m.js(f'      slam("#{pid}", {a:.2f}, {{ fromScale: 2.0, blur: 10, rot: {rot} }});\n'
         f'      leave("#{pid}", {leave:.2f}, {{ rot: {rot} }});')
    m.hide(a - 0.06, b + 0.05)


def _over_head(m, text: str, family: str, a: float, b: float, top: float, line: float, biggest: int,
               smallest: int) -> int:
    """Самый крупный кегль строки над головой в окне [a, b]: голова (как у _word и verify_page) закрывает не больше
    0,2 строки. 0 — строка не встаёт над головой и в smallest px: тогда приём идёт на грудь."""
    x0, y0, x1, y1 = m._face(a, b)
    head_top, head_w = y0 - 0.2 * (y1 - y0) - 25, (x1 - x0) * 1.3
    em = max(bp._em(text, family), 1e-3)
    wide = int(min(biggest, SAFE_W / em))

    def hidden(px: int) -> float:
        h = line * px
        return max(0.0, top + h - head_top) / h * min(1.0, head_w / (em * px))
    return next((px for px in range(wide, smallest - 1, -2) if hidden(px) <= 0.2), 0)


def _hand(m, pid: str, item: dict, a: float, b: float) -> None:
    """Пометка рукой над головой (Caveat, по буквам): вопрос хука, «ответ — в конце»; человек поверх, "line" — подчерк
    акцентом. Субтитры идут: пометка добавляет к речи, а не повторяет её (повторяет — "hide": true)."""
    text = item["text"]
    leave = max(b, a + 1.2)
    top = bp.TOP_LINE + 2
    size = _over_head(m, text, "Caveat", a, leave, top, 1.1, 116, 64)
    if size:
        layer, place = m.behind, f'style="top: {top}px; font-size: {size}px;"'
        m.fg(a - 0.3, leave + 0.25)
    else:                                       # над головой тесно — на груди, под субтитрами
        size = int(min(96, 0.9 * 700 / max(bp._em(text, "Caveat"), 1e-3)))
        layer, place = m.front, (f'data-safe="пометка на груди: над головой нет места" data-safe-zones="низ" '
                                 f'style="top: {LIST_TOP}px; font-size: {size}px;"')
        m.notes.append(f"пометка «{text}» — на груди: над головой не встаёт и в 64 px")
    underline = ""
    if item.get("line"):
        width = bp._em(text, "Caveat") * size
        underline = (f'<svg class="ds-uline" style="left: {(bp.W - width) / 2:.0f}px; top: {size * 1.02:.0f}px; '
                     f'width: {width:.0f}px; height: 34px;" viewBox="0 0 {width:.0f} 34" aria-hidden="true">'
                     f'<path d="M 6 22 C {width * 0.3:.0f} 10, {width * 0.65:.0f} 28, {width - 6:.0f} 12" pathLength="1" /></svg>')
    layer(f'        <div id="{pid}" class="g ds-hand" {place}>{design.letters(text)}{underline}</div>')
    written = a + 0.22 + (len(text) - 1) * m.design.hand_stagger
    js = f'      dsHand("#{pid}", {a:.2f});\n'
    if underline:
        js += f'      dsPen("#{pid} .ds-uline path", {written + 0.05:.2f}, 0.35);\n'
    m.js(js + f'      leave("#{pid}", {leave:.2f}, {{ y: -40, dur: 0.2 }});')
    if item.get("hide"):
        m.hide(a - 0.05, leave + 0.05)


def _number(m, pid: str, item: dict, a: float, b: float, at: float) -> None:
    """Число акцентом системы за головой (Unbounded), бьёт из крупного на «at»; над ним шёпотом подпись ("sub").
    Субтитры этих слов спрятаны — число на экране и есть речь (не повторяет — "hide": false)."""
    text, sub = item["text"], item.get("sub", "")
    a0, leave = min(a, at), max(b, at + 0.8)
    top = bp.TOP_LINE + 2
    size = _over_head(m, text, "Unbounded", a0, leave, top + (70 if sub else 0), 1.0, 270, 120)
    cap = f'<span class="ds-numcap">{html.escape(sub)}</span>' if sub else ""
    if size:
        m.behind(f'        <div id="{pid}" class="g ds-num-wrap" style="top: {top}px;">{cap}'
                 f'<span class="ds-num" style="font-size: {size}px;">{html.escape(text)}</span></div>')
        m.fg(a0 - 0.3, leave + 0.25)
    else:
        size = int(min(180, CHEST_W / max(bp._em(text, "Unbounded"), 1e-3)))
        # на груди подпись — в колонке под кнопками ленты (formats.GREY_ZONES: справа с x 834–865 от y 727)
        cap = cap.replace('class="ds-numcap"', 'class="ds-numcap" style="font-size: 44px;"')
        m.front(f'        <div id="{pid}" class="g ds-num-wrap" data-safe="число на груди: над головой нет места" '
                f'data-safe-zones="низ" style="top: {LIST_TOP - 12}px;">{cap}'
                f'<span class="ds-num" style="font-size: {size}px;">{html.escape(text)}</span></div>')
        m.notes.append(f"число «{text}» — на груди: над головой не встаёт и в 120 px")
    m.js(f'      slam("#{pid}", {at:.2f}, {{ fromScale: 1.4 }});\n'
         f'      leave("#{pid}", {leave:.2f}, {{ y: -50, dur: 0.2 }});')
    if item.get("hide", True):
        m.hide(a0 - 0.05, leave + 0.05)
    m.punch(at, leave)


def _promise(m, pid: str, item: dict, a: float, b: float, start, end) -> None:
    """Список-обещание на груди (из направления В): заголовок и 2–4 строки; квадрат строки заливается акцентом на слове
    пункта, строка разгорается из серого в крем. Субтитры идут как шли — прячется только слово пункта, его текст уже
    на экране (двойного текста нет, п.16)."""
    rows = item["rows"]
    title = re.sub(r"\d+", lambda g: f'<span class="ds-n">{g.group(0)}</span>', html.escape(item["title"]))
    body = "".join(f'<div id="{pid}-r{j}" class="ds-row"><i id="{pid}-b{j}" class="ds-box"></i>'
                   f'<span>{html.escape(r["text"])}</span></div>' for j, r in enumerate(rows))
    m.front(f'        <div id="{pid}" class="g ds-list" data-safe="список-обещание на груди ниже подбородка" '
            f'data-safe-zones="низ" style="top: {LIST_TOP}px;"><div class="ds-list-h">{title}</div>{body}</div>')
    times = [start(r["w"]) for r in rows]
    leave = max(b, times[-1] + 0.9)
    lit = "rgba({},{},{},1)".format(*design._rgb(m.design.colors["text"]))
    js = [f'      enter("#{pid}", {a:.2f}, {{ fromY: 40, fromScale: 0.96, blur: 10, dur: 0.3, ease: "expo.out" }});']
    for j, (r, t) in enumerate(zip(rows, times)):
        js.append(f'      dsBox("#{pid}-b{j}", {t:.2f});')
        js.append(f'      tl.to("#{pid}-r{j}", {{ color: "{lit}", duration: 0.12 }}, {t:.2f});')
        m.hide(t - 0.05, end(r["w"]) + 0.05)
    js.append(f'      leave("#{pid}", {leave:.2f}, {{ y: 30, dur: 0.22 }});')
    m.js("\n".join(js))


def _strike(m, pid: str, item: dict, a: float, b: float, at: float) -> None:
    """Миф на груди, красная ручка зачёркивает его на «at» — единственное место красного в системе. Субтитры этих слов
    спрятаны: слово на экране и есть речь."""
    text = item["text"]
    size = int(min(110, 0.9 * 700 / max(bp._em(text, "InterDisplay-800"), 1e-3)))
    at = max(at, a + 0.35)                      # слово успевают прочесть до черты
    leave = max(b, at + 0.7)
    m.front(f'        <div id="{pid}" class="g ds-strike-w" data-safe="слово на груди ниже подбородка" data-safe-zones="низ" '
            f'style="top: {LIST_TOP}px; font-size: {size}px;"><span class="ds-in">{html.escape(text)}'
            f'<svg class="ds-strike" viewBox="0 0 300 100" preserveAspectRatio="none" aria-hidden="true">'
            f'<path d="M 0 62 Q 150 42 300 48" pathLength="1" /></svg></span></div>')
    m.js(f'      enter("#{pid}", {a:.2f}, {{ fromY: 24, fromScale: 0.9, blur: 10, dur: 0.28, ease: "expo.out" }});\n'
         f'      dsPen("#{pid} .ds-strike path", {at:.2f});\n'
         f'      leave("#{pid}", {leave:.2f}, {{ y: -30, dur: 0.22 }});')
    m.hide(a - 0.05, leave + 0.05)


def _count(m, pid: str, item: dict, a: float, b: float, start, end) -> None:
    """Число растёт шагами на своих словах (100 → 10 000 → 1 млн): каждый шаг выбивает прежний и бьёт из крупного,
    на шагах — тихий тик, на последнем — удар камеры. Над головой, если строка встаёт; иначе — на груди. Субтитры окна
    спрятаны: число на экране и есть речь ("hide": false — если число не повторяет сказанное)."""
    steps, sub = item["steps"], item.get("sub", "")
    times = [start(s["w"]) for s in steps]
    leave = max(b, times[-1] + 0.9)
    longest = max((s["text"] for s in steps), key=lambda t: bp._em(t, "Unbounded"))
    top = bp.TOP_LINE + 2
    size = _over_head(m, longest, "Unbounded", a, leave, top + (70 if sub else 0), 1.0, 230, 110)
    chest = not size
    if chest:
        size = int(min(170, CHEST_W / max(bp._em(longest, "Unbounded"), 1e-3)))
        top = LIST_TOP - 12
    layer = m.front if chest else m.behind
    safe = ' data-safe="счётчик на груди: над головой нет места" data-safe-zones="низ"' if chest else ""
    num_cls = "ds-num" if m.design else "big"
    if sub:
        layer(f'        <div id="{pid}-cap" class="g ds-num-wrap"{safe} style="top: {top}px;">'
              f'<span class="ds-numcap">{html.escape(sub)}</span></div>')
    for j, s_ in enumerate(steps):
        layer(f'        <div id="{pid}-{j}" class="g ds-num-wrap"{safe} style="top: {top + (70 if sub else 0)}px;">'
              f'<span class="{num_cls}" style="font-size: {size}px;">{html.escape(s_["text"])}</span></div>')
    js = [f'      enter("#{pid}-cap", {times[0] - 0.1:.2f}, {{ fromY: 20, dur: 0.25 }});'] if sub else []
    for j, t in enumerate(times):
        js.append(f'      slam("#{pid}-{j}", {t:.2f}, {{ fromScale: {1.6 if j else 1.35} }});')
        nxt = times[j + 1] - 0.02 if j + 1 < len(times) else leave
        js.append(f'      leave("#{pid}-{j}", {nxt:.2f}, {{ y: {-70 if j + 1 < len(times) else -50}, dur: 0.14 }});')
        m.soft(t, "stamp" if j == len(times) - 1 else "line")
    if sub:
        js.append(f'      leave("#{pid}-cap", {leave:.2f}, {{ y: -40, dur: 0.2 }});')
    m.js("\n".join(js))
    if not chest:
        m.fg(a - 0.3, leave + 0.25)
    else:
        m.notes.append(f"счётчик «{longest}» — на груди: над головой не встаёт и в 110 px")
    if item.get("hide", True):                  # прячутся слова самих чисел: окно целиком — дольше 3 с без субтитров
        for s_, t in zip(steps, times):
            m.hide(t - 0.05, end(s_["w"]) + 0.3)
    m.punch(times[-1], leave)


def _scene(m, pid: str, item: dict, a: float, b: float, start, end) -> None:
    """Своя сцена режиссёра: его html, css и js с $id → своим id и {w:N}/{e:N} → секундами слов. За человеком
    ("layer": "behind") — человек поверх (окно вырезки), если не "fg": false."""
    def fill(text: str) -> str:
        text = re.sub(r"\{w:(\d+)\}", lambda g: f"{start(int(g.group(1))):.2f}", text)
        text = re.sub(r"\{e:(\d+)\}", lambda g: f"{end(int(g.group(1))):.2f}", text)
        return text.replace("$id", pid)
    layer = item.get("layer", "front")
    html_ = "        " + fill(item["html"]).strip()
    js = "\n".join("      " + line.strip() for line in fill(item["js"]).splitlines() if line.strip()) if item.get("js") else ""
    if item.get("css"):
        m.css(fill(item["css"]))
    if layer in ("split", "full"):
        # сцена на чистом листе: «split» — человек в окне внизу, сцена над ним; «full» — во весь кадр (перебивка)
        piece = bp.Piece(pid, layer, a, b, html_, js + "\n")
        piece["plain"] = True
        m.blueprint(piece)
        if item.get("hide"):
            m.hide(a - 0.05, b + 0.05)
        return
    (m.behind if layer == "behind" else m.front)(html_)
    if js:
        m.js(js)
    if layer == "behind" and item.get("fg", True):
        m.fg(a - 0.3, b + 0.25)
    if item.get("hide"):
        m.hide(a - 0.05, b + 0.05)


def _doodle_marks(m, a: float, b: float) -> list:
    """Значки doodle — в свободных углах у головы в этом окне (голова как у verify_page: лицо, 0,2 высоты на волосы,
    по 0,15 ширины с боков), мимо серых зон: в fx.doodle они стоят в жёстких точках и у IMG_3651 задели лицо."""
    import fx
    x0, y0, x1, y1 = m._face(a, b)
    hx0, hx1, top = x0 - 0.15 * (x1 - x0), x1 + 0.15 * (x1 - x0), y0 - 0.2 * (y1 - y0)
    size, colors = 160, fx.T("MARKS")
    spots = []
    if hx0 - 112 >= size:                                        # слева от головы
        spots += [(112, max(270, top)), (112, min(1370 - size, y1 - size))]
    if 860 - hx1 >= size:                                        # справа — до кнопок площадок (x 865 ниже y 727)
        spots += [(round(hx1) + 4, max(270, top))]
    elif 970 - hx1 >= size and top + size <= 727:                # выше кнопок — до бокового обреза
        spots += [(round(hx1) + 4, max(270, top))]
    if y1 + 20 + size <= 1150:                                   # под подбородком, до субтитров
        spots += [(round((x0 + x1) / 2 - size / 2), round(y1 + 20))]
    names = ["spark", "star", "heart", "clapper"]
    return [(names[k % len(names)], x, y, colors[k % len(colors)]) for k, (x, y) in enumerate(spots[:4])] or \
        [("spark", 112, 270, colors[0])]


def _fx(m, pid: str, item: dict, a: float, b: float, start) -> None:
    """Приём fx.py по словам партитуры; тема — дизайн-система проекта (fx.use_for в build)."""
    import fx
    kind = item["kind"]
    if kind == "wall":
        part = fx.wall(pid, [r["text"] for r in item["notes"]], [start(r["w"]) for r in item["notes"]], b)
    elif kind == "paper":
        part = fx.paper_cut(pid, a, b, item["text"])
    elif kind == "vertigo":
        part = fx.vertigo(a, b, amount=max(0.86, round(1 / m.tk.base_zoom + 0.02, 2)) if getattr(m.tk, "base_zoom", 0) else 0.86)
    elif kind == "frame":
        part = fx.frame_break(pid, a, b)
    elif kind == "doodle":
        part = fx.doodle(pid, a, b, marks=_doodle_marks(m, a, b))
    else:                               # zoom: пролёт сквозь камеру на начале окна
        part = fx.zoom_through(a)
    if part.behind:
        m.behind(part.behind)
    if part.front:
        m.front(part.front)
    if part.js:
        m.js(part.js)
    m.css(part.css)
    for w in part.windows:
        m.fg(*w)
    if part["stage"]:
        m.stage_fx = True
    m.soft(a, "text")
    if item.get("hide"):
        m.hide(a - 0.05, b + 0.05)


def _piece(kind: str, pid: str, item: dict, a, b, start, end):
    """Приём «Чертежа» из полей партитуры: окно — по словам, шаги — на словах своих меток."""
    layout = {"layout": item["layout"]} if "layout" in item else {}
    if kind == "write":
        return bp.write(pid, item["text"], a, b, sub=item.get("sub", ""), red=item.get("red", False), dur=item.get("dur", 0.9),
                        over=start(item["over"]) if "over" in item else None, titlo=item.get("titlo", False), **layout)
    if kind == "route":
        stops = item["stops"]
        return bp.route(pid, [(s["label"], s["x"], s["y"]) for s in stops], [start(s["w"]) for s in stops], end(item["until"]),
                        bend=item.get("bend", 0.22), **layout)
    if kind == "timeline":
        marks = item["marks"]
        return bp.timeline(pid, [(s["label"], s.get("sub", "")) for s in marks], [start(s["w"]) for s in marks],
                           end(item["until"]), **layout)
    if kind == "compass":
        extra = {key: tuple(item[key]) if key == "center" else item[key] for key in ("label", "center", "radius") if key in item}
        return bp.compass(pid, a, b, **extra, **layout)
    if kind == "hexes":
        return bp.hexes(pid, a, b, **{key: item[key] for key in ("cols", "rows", "red", "label") if key in item}, **layout)
    if kind == "cuboid":
        return bp.cuboid(pid, a, b, **({"dims": tuple(item["dims"])} if "dims" in item else {}), **layout)
    if kind == "trilat":
        return bp.trilat(pid, a, b, [start(i) for i in item["sats"]], start(item["fix"]), label=item.get("label", ""),
                         roam=start(item["roam"]) if "roam" in item else None,
                         sphere=start(item["sphere"]) if "sphere" in item else None, **layout)
    if kind == "plot":
        return bp.plot(pid, item["ys"], a, b, **{key: item[key] for key in ("mark", "xlabel", "ylabel", "label") if key in item},
                       **layout)
    raise ScoreError(f"приём {kind} не собирается")


def main():
    ap = argparse.ArgumentParser(description="Страница ролика из партитуры (work/<имя>/score.json)")
    ap.add_argument("stem")
    ap.add_argument("--variant", help="score.<вариант>.json → studio/<имя>--<вариант>")
    ap.add_argument("--check", action="store_true", help="только проверить партитуру, страницу не писать")
    args = ap.parse_args()
    try:
        if args.check:
            from kit import Take
            words = Take(args.stem, args.variant).words
            errs = check(load(args.stem, args.variant), words)
            if errs:
                sys.exit("✗ партитура с ошибками:\n  " + "\n  ".join(errs))
            print(f"✓ {path_of(args.stem, args.variant).name}: годна")
        else:
            # как analyst.assemble: субтитры (что спрятано, ключевые слова, линия в сплите) берутся из director.json,
            # который пишет сборка, — без compose после неё страница шла со старыми и verify_page краснел ложно (IMG_3647)
            import compose
            if not (compose.STUDIO / compose.project_name(args.stem, args.variant) / "camera.js").exists():
                compose.compose(args.stem, variant=args.variant)
            build(args.stem, args.variant)
            compose.compose(args.stem, variant=args.variant)
    except ScoreError as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
