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
      {"kind": "clip",   "w": [34, 41], "name": "a_india", "label": "Индия, V век"}      # клип Flow, уже принятый
    ]
  }

  .venv/bin/python scripts/score.py IMG_3292 --variant montage           # страница studio/IMG_3292--montage
  .venv/bin/python scripts/score.py IMG_3292 --variant auto --check      # только проверить партитуру
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import blueprint as bp  # noqa: E402
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
    "clip": ({"w", "name"}, {"label"}),
}
TOP = {"title", "hook", "cta", "accent", "text_fixes", "keep_case", "hide", "items", "_note"}
SAME_RUN = 2           # приёмов подряд в одной раскладке — больше однообразно
TEXT_MAX = {"word": 12, "stamp": 14, "write": 18}     # знаков в одну строку: крупное слово, штамп, запись
SUB_MAX, LABEL_MAX = 30, 14                             # подпись под записью или у клипа; метка маршрута и оси
WORD_MIN = 96          # px: меньше кегль слова над головой не читается — тогда слово на груди
CTA_TAIL = 2.8          # с: от призыва до конца речи — субтитры спрятаны с призыва − 0,2 с (verify_page: не дольше 3 с)
MIN_SHOW = 0.9          # с: короче окно приёма сборка продлевает — «Чертёж» не успеть прочесть быстрее 0,8 с


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
        for key in ("at", "over", "until"):
            if key in item:
                word(item[key], f"{where}.{key}")
        # надпись — одна строка без переноса: предложение в подписи уходит за кадр (19.10.2026, аналитик IMG_3303:
        # «плоскости теряют даже плотно уложенные круги» вылезла на 785 px). Длиннее — короче или в субтитры
        texts = [("text", item.get("text"), TEXT_MAX.get(kind, 18)), ("sub", item.get("sub"), SUB_MAX),
                 ("label", item.get("label"), SUB_MAX)]
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


def where_of(item: dict) -> str:
    """Где приём на экране: раскладка «Чертежа», а для своих видов — их место."""
    fixed = {"word": "behind", "stamp": "chest", "clip": "full"}
    defaults = {"write": "split", "route": "behind", "timeline": "split", "compass": "behind", "hexes": "behind",
                "cuboid": "split", "plot": "split"}
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

    for k, item in enumerate(score.get("items") or []):
        kind, pid = item["kind"], f"s{k}-{item['kind']}"
        a, b = (start(item["w"][0]), end(item["w"][1])) if "w" in item else (None, None)
        if a is not None and b - a < MIN_SHOW:
            b = round(a + MIN_SHOW, 2)
        try:
            if kind == "word":
                _word(m, pid, item, a, b, start(item.get("at", item["w"][0])))
            elif kind == "stamp":
                _stamp(m, pid, item, a, b)
            elif kind == "clip":
                m.footage(pid, item["name"], a, round(b - a, 2), label=item.get("label", ""))
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
    wide = int(min(170, 0.9 * bp.W / em))

    def hidden(px: int) -> float:
        line = 0.92 * px
        return max(0.0, bp.TOP_LINE + 2 + line - top) / line * min(1.0, head_w / (em * px))
    size = item.get("size") or next((px for px in range(wide, 59, -2) if hidden(px) <= 0.2), 0)
    color = f" color: {RED};" if item.get("red", True) else ""
    if size >= WORD_MIN:
        m.behind(f'        <div id="{pid}" class="g big" style="top: {bp.TOP_LINE + 2}px; font-size: {size}px;{color}">{text}</div>')
        m.fg(min(a, at) - 0.3, leave + 0.25)
    else:                                       # над головой тесно — на груди, под линией субтитров, поверх человека
        size = min(wide, 150)
        m.front(f'        <div id="{pid}" class="g big" data-safe="крупное слово на груди: над головой нет места" '
                f'data-safe-zones="низ" style="top: 1240px; font-size: {size}px;{color}">{text}</div>')
        m.notes.append(f"слово «{text}» — на груди: над головой (верх головы y {top:.0f}) не встаёт и в {WORD_MIN} px")
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
            build(args.stem, args.variant)
    except ScoreError as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
