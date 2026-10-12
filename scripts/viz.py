#!/usr/bin/env python3
"""Визуализации данных для страниц ролика: числа, графики, формулы, графики функций.

Когда в речи есть то, что лучше увидеть, чем услышать, — сумма, проценты, рост, сравнение,
формула, парабола, шаги решения, место на карте, — режиссёр ставит визуализацию. Решает он
сам, по скиллу viz (.agents/skills/viz/SKILL.md): к месту, не чаще раза за мысль, лицо не
закрывать. Здесь — только как поставить, чтобы рендер был детерминированным и офлайн.

Два источника:
  • каталог HyperFrames (Apache-2.0), вендорённый в presets/viz (scripts/viz_vendor.py):
    счётчик, график-история (столбики, линия, кольцо, прогресс), падение, кольцо прогресса,
    «до/после», рейтинг, гонка столбиков, осциллограф — mount() с переменными, проверенными по
    catalog.json; остальные (карта мира, блок-схемы, линейный график) — шаблоны: копируются в
    проект ролика и правятся руками;
  • своё, для математики: formula() — LaTeX через KaTeX (MIT, вендорён), plot() — график
    функции, путь считается здесь же, в Python, и рисуется линией по таймлайну.

У каждой визуализации — вход И выход движением (правило Валеры): обёртка .g влетает со смазом
(enter) и улетает (leave), как всё остальное на странице; verify_page.py ловит залипания.

  html, js = viz.mount("count-up", "kredit", at=12.4, dur=3.5, fmt=tk.fmt, where="upper",
                       values={"end": 182000, "suffix": " ₽"})
  html, js = viz.formula("disc", r"D = b^2 - 4ac", at=20.1, dur=4, fmt=tk.fmt)
  html, js = viz.plot("parab", lambda x: x * x - 4, x=(-3, 3), y=(-5, 6), at=31, dur=5, fmt=tk.fmt)
"""
import html as html_lib
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import formats
from common import PRESET_DIR

VIZ = PRESET_DIR / "viz"
# Палитра и шрифты страниц ролика — в переменные, которые читают элементы каталога
# --bg не трогаем: им элементы и заливают фон, и красят подпись на акцентной плашке (прозрачный
# --bg сделал её невидимой на демо 11.10) — их собственные значения по умолчанию верные.
THEME = ("--fg: #F2EBDD; --brand: #F0352C; --accent: #F0352C; --accent-2: #FF4A3D; "
         "--font-display: 'Oswald', sans-serif; --font-body: 'Manrope', sans-serif; --font-mono: 'JBMono', monospace; "
         "--mk-font: 'Manrope', sans-serif; --mk-ink: #F2EBDD; --mk-ink-dim: rgba(242,235,221,0.62); "
         "--mk-accent: #F0352C; --mk-paper: #141210; --mk-axis: rgba(242,235,221,0.3);")

# Куда ставить на сцене каждого формата: (left, top, width, height). Размечено по кадру (IMG_3317):
# в вертикали голова занимает y≈400–930, субтитры — на груди (y≈1150), снизу 420 px — интерфейс
# площадки, сверху 220. Отсюда зоны:
#   upper  — узкая полоса над головой: число, короткая подпись;
#   chest  — на груди: график, схема (субтитры в это окно прятать — hide_captions);
#   lower  — полоса под субтитрами: формула, короткая строка;
#   center — поверх лица: только короткий важный момент (график, к которому всё вело);
#   side   — в горизонтали — правая треть, лицо остаётся в центре.
ZONES = {
    # серые зоны площадок (formats.GREY_ZONES, по скринам 12.10.2026): верх до 260, низ от 1370,
    # кнопки справа, бока Instagram — зоны по центру экрана, ширина 590 там, где справа кнопки YouTube
    "9:16": {"upper": (102, 270, 876, 140), "chest": (245, 945, 590, 415), "lower": (245, 1240, 590, 120),
             "center": (245, 520, 590, 760)},
    "4:5": {"upper": (90, 85, 900, 150), "chest": (60, 640, 960, 480), "lower": (90, 960, 900, 220),
            "center": (90, 260, 900, 700)},
    "1:1": {"upper": (90, 65, 900, 140), "chest": (90, 560, 900, 400), "lower": (90, 780, 900, 220),
            "center": (90, 180, 900, 700)},
    "16:9": {"upper": (1080, 70, 760, 200), "side": (1080, 150, 760, 760), "lower": (300, 760, 1320, 220),
             "chest": (1080, 150, 760, 760), "center": (260, 120, 1400, 820)},
}


def box(fmt: str, where: str) -> tuple:
    """Место визуализации на сцене формата. Неизвестное — громкая ошибка, а не «куда-нибудь»."""
    zones = ZONES[formats.get(fmt)["id"]]
    if where not in zones:
        raise ValueError(f"Зона «{where}» не знаю для {fmt}. Есть: {', '.join(zones)}")
    return zones[where]


def catalog() -> dict:
    data = json.loads((VIZ / "catalog.json").read_text(encoding="utf-8"))
    return {item["name"]: item for item in data["items"]}


def check_values(item: dict, values: dict) -> dict:
    """Переменные по объявлению элемента: опечатка в имени или не тот тип — громкая ошибка."""
    declared = {v["id"]: v for v in item["variables"]}
    clean = {}
    for key, value in values.items():
        spec = declared.get(key)
        if spec is None:
            raise ValueError(f"У «{item['name']}» нет переменной «{key}». Есть: {', '.join(declared)}")
        kind = spec["type"]
        if kind == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise ValueError(f"{item['name']}.{key} — число, а не {value!r}")
        if kind == "boolean" and not isinstance(value, bool):
            raise ValueError(f"{item['name']}.{key} — да/нет (True/False), а не {value!r}")
        if kind == "enum" and value not in [o["value"] for o in spec.get("options", [])]:
            raise ValueError(f"{item['name']}.{key} бывает {', '.join(o['value'] for o in spec['options'])}, а не {value!r}")
        if kind in ("string", "color") and not isinstance(value, str):
            raise ValueError(f"{item['name']}.{key} — строка, а не {value!r}")
        clean[key] = value
    return clean


BOARD = ('<div class="viz-board" style="position: absolute; inset: 0; border-radius: 22px; '
         'background: rgba(12,12,14,0.86); box-shadow: 0 30px 80px rgba(0,0,0,0.55);"></div>')


def fit(place: tuple, dims: dict | None, pad: int) -> str:
    """Стиль монтажа элемента внутри обёртки.

    Компоненты каталога тянутся сами (контейнерные единицы) — им хватает inset. Блоки свёрстаны
    в своих пикселях (1920×1080): без масштаба карта мира на демо 11.10 вылезла за кадр. Им —
    исходный размер и transform: scale, по центру рамки.
    """
    if not dims or not dims.get("width"):
        return f"position: absolute; inset: {pad}px;"
    width, height = place[2] - 2 * pad, place[3] - 2 * pad
    k = min(width / dims["width"], height / dims["height"])
    left = pad + (width - dims["width"] * k) / 2
    top = pad + (height - dims["height"] * k) / 2
    return (f"position: absolute; left: {left:.1f}px; top: {top:.1f}px; width: {dims['width']}px; "
            f"height: {dims['height']}px; transform: scale({k:.4f}); transform-origin: 0 0;")


def frame(cid: str, place: tuple, inner: str, extra_style: str = "") -> str:
    left, top, width, height = place
    return (f'        <div id="{cid}" class="g viz" style="left: {left}px; top: {top}px; width: {width}px; '
            f'height: {height}px;{extra_style}">\n{inner}\n        </div>')


def motion(cid: str, at: float, dur: float, entry: str = "enter") -> str:
    """Вход И выход обёртки: влёт со смазом в начале, улёт за 0.3 с до конца окна."""
    out = max(at + 0.4, at + dur - 0.3)
    start = (f'      enter("#{cid}", {at:.2f}, {{ fromScale: 0.9, dur: 0.38, ease: "power3.out" }});' if entry == "enter"
             else f'      slam("#{cid}", {at:.2f});')
    return start + f'\n      leave("#{cid}", {out:.2f}, {{ y: -60, dur: 0.28 }});'


def mount(name: str, cid: str, at: float, dur: float, fmt: str = "9:16", where: str = "upper",
          values: dict | None = None, place: tuple | None = None, board: bool | None = None) -> tuple:
    """Элемент каталога HyperFrames с переменными — (html, js) для build_page.

    Свой выход у элемента выключается (exit=none): уходит вся обёртка, движением, как
    остальная графика страницы. Время — по шкале дубля (Take.t), окно — [at, at+dur].
    board — тёмная подложка: по умолчанию везде, кроме полосы над головой. Без неё столбики на
    груди спорят с одеждой (на демо 11.10 принт худи налез на подписи).
    """
    items = catalog()
    if name not in items:
        raise ValueError(f"Визуализации «{name}» нет в presets/viz. Есть: {', '.join(sorted(items))}")
    item = items[name]
    if not item["mount"]:
        raise ValueError(f"«{name}» — шаблон без переменных: скопируй {item['file']} в compositions/ ролика "
                         "и поправь данные (см. скилл viz)")
    vals = check_values(item, values or {})
    if any(v["id"] == "exit" for v in item["variables"]):
        vals.setdefault("exit", "none")
    if dur < 1.0:
        raise ValueError(f"{name}: окно {dur:.2f} с — не успеет построиться и прочитаться (меньше секунды)")
    attrs = html_lib.escape(json.dumps(vals, ensure_ascii=False), quote=True)
    board = where != "upper" if board is None else board
    pad = 24 if board else 0
    place = place or box(fmt, where)
    dims = item.get("dimensions") if item.get("type") == "block" else None
    inner = ((f"          {BOARD}\n" if board else "") +
             f'          <div id="{cid}-mount" data-composition-id="{name}" data-composition-src="{item["file"]}" '
             f'data-start="{at:.2f}" data-duration="{dur:.2f}" data-variable-values="{attrs}" '
             f'style="{fit(place, dims, pad)} {THEME}"></div>')
    return frame(cid, place, inner), motion(cid, at, dur)


def custom(name: str, cid: str, project: Path, new_name: str, replace: dict, at: float, dur: float,
           fmt: str = "9:16", where: str = "chest", place: tuple | None = None, board: bool = True) -> tuple:
    """Шаблон каталога без переменных (карта мира, блок-схема, линейный график…) со своими данными.

    Копия ложится в studio/<ролик>/compositions/custom/<new_name>.html; её пишет page.py — значит,
    правка воспроизводима из git. replace — {старый текст: новый}: каждый обязан найтись ровно
    один раз, иначе громкая ошибка (шаблон обновился, а правка тихо не применилась бы).
    """
    items = catalog()
    if name not in items:
        raise ValueError(f"Шаблона «{name}» нет в presets/viz. Есть: {', '.join(sorted(items))}")
    text = (VIZ / items[name]["file"]).read_text(encoding="utf-8")
    for old, new in replace.items():
        count = text.count(old)
        if count != 1:
            raise ValueError(f"{name}: фрагмент для замены найден {count} раз, а нужен ровно один: {old[:60]!r}")
        text = text.replace(old, new)
    rel = f"compositions/custom/{new_name}.html"
    target = Path(project) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    pad = 24 if board else 0
    place = place or box(fmt, where)
    dims = items[name].get("dimensions") or {"width": 1920, "height": 1080}
    inner = ((f"          {BOARD}\n" if board else "") +
             f'          <div id="{cid}-mount" data-composition-id="{new_name}" data-composition-src="{rel}" '
             f'data-start="{at:.2f}" data-duration="{dur:.2f}" style="{fit(place, dims, pad)} {THEME}"></div>')
    return frame(cid, place, inner), motion(cid, at, dur)


def formula(cid: str, latex: str, at: float, dur: float, fmt: str = "9:16", where: str = "lower",
            size: int = 76, place: tuple | None = None, color: str = "#F2EBDD") -> tuple:
    """Формула LaTeX (KaTeX, вендорён в studio/_vendor/katex) на плашке-доске.

    Ошибка в LaTeX — ошибка страницы: её поймает verify_page.py до рендера, а не зритель.
    """
    left, top, width, height = place or box(fmt, where)
    tex = html_lib.escape(latex, quote=True)
    inner = (f"          {BOARD}\n"
             f'          <div style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;">\n'
             f'            <span class="katex-src" data-tex="{tex}" style="font-size: {size}px; color: {color};"></span>\n'
             f'          </div>')
    return frame(cid, (left, top, width, height), inner), motion(cid, at, dur, entry="slam")


def plot(cid: str, fn, x: tuple, y: tuple, at: float, dur: float, fmt: str = "9:16", where: str = "chest",
         place: tuple | None = None, label: str = "", points: list | None = None, samples: int = 240,
         draw: float = 1.2) -> tuple:
    """График функции y = fn(x): оси, кривая рисуется линией, отмеченные точки появляются следом.

    Путь считается здесь (numpy не нужен): кадр от этого не зависит от браузера, а разрывы
    (деление на ноль, уход за пределы) рвут линию, а не тянут её через весь экран.
    """
    left, top, width, height = place or box(fmt, where)
    pad = 56
    x0, x1 = x
    y0, y1 = y
    if not (x1 > x0 and y1 > y0):
        raise ValueError(f"plot {cid}: пределы осей перепутаны: x={x}, y={y}")
    sx = lambda v: pad + (v - x0) / (x1 - x0) * (width - 2 * pad)
    sy = lambda v: height - pad - (v - y0) / (y1 - y0) * (height - 2 * pad)
    parts, pen = [], False
    for i in range(samples + 1):
        xv = x0 + (x1 - x0) * i / samples
        try:
            yv = float(fn(xv))
        except (ZeroDivisionError, ValueError, OverflowError):
            yv = math.nan
        if not math.isfinite(yv) or not (y0 - (y1 - y0) <= yv <= y1 + (y1 - y0)):
            pen = False
            continue
        parts.append(f"{'L' if pen else 'M'} {sx(xv):.1f} {sy(yv):.1f}")
        pen = True
    if not parts:
        raise ValueError(f"plot {cid}: функция не попала в окно осей ни одной точкой")
    axes = []
    if x0 < 0 < x1:
        axes.append(f'<line x1="{sx(0):.1f}" y1="{pad / 2:.1f}" x2="{sx(0):.1f}" y2="{height - pad / 2:.1f}" />')
    if y0 < 0 < y1:
        axes.append(f'<line x1="{pad / 2:.1f}" y1="{sy(0):.1f}" x2="{width - pad / 2:.1f}" y2="{sy(0):.1f}" />')
    dots = "".join(f'<circle class="viz-dot" cx="{sx(px):.1f}" cy="{sy(py):.1f}" r="12" />' for px, py in points or [])
    caption = (f'          <div class="katex-src" data-tex="{html_lib.escape(label, quote=True)}" '
               f'style="position: absolute; right: 28px; top: 18px; font-size: 44px; color: #F2EBDD;"></div>\n'
               if label else "")
    inner = (f"          {BOARD}\n"
             f'          <svg viewBox="0 0 {width} {height}" style="position: absolute; inset: 0; width: {width}px; height: {height}px;">\n'
             f'            <g stroke="rgba(242,235,221,0.45)" stroke-width="3">{"".join(axes)}</g>\n'
             f'            <path id="{cid}-curve" d="{" ".join(parts)}" fill="none" stroke="#F0352C" stroke-width="8" '
             f'stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />\n'
             f'            <g id="{cid}-dots" fill="#F2EBDD" opacity="0">{dots}</g>\n'
             f'          </svg>\n{caption}')
    js = motion(cid, at, dur) + f'\n      draw("#{cid}-curve", {at + 0.35:.2f}, {draw:.2f});'
    if points:
        js += (f'\n      tl.fromTo("#{cid}-dots", {{ opacity: 0, scale: 0.4, transformOrigin: "50% 50%" }}, '
               f'{{ opacity: 1, scale: 1, duration: 0.2, ease: "back.out(2)" }}, {at + 0.4 + draw:.2f});')
    return frame(cid, (left, top, width, height), inner), js


def assets_for(page: str, project: Path | None = None) -> dict:
    """Что из presets/viz и studio/_vendor нужно странице: {путь в проекте: исходник}. Для compose.py.

    Свои копии шаблонов (custom) лежат в самом проекте — их не копируем, но библиотеки и
    шрифты, которые они зовут, подкладываем так же.
    """
    root = Path(__file__).resolve().parent.parent
    need = {}
    texts = []
    for item in catalog().values():
        if f'data-composition-src="{item["file"]}"' in page:
            need[item["file"]] = VIZ / item["file"]
            texts.append((VIZ / item["file"]).read_text(encoding="utf-8"))
    for rel in re.findall(r'data-composition-src="(compositions/custom/[^"]+)"', page):
        if project is not None and (Path(project) / rel).exists():
            texts.append((Path(project) / rel).read_text(encoding="utf-8"))
    for text in texts:
        for lib in ("d3.min.js", "topojson-client.min.js", "countries-110m.json"):
            if f"assets/vendor/{lib}" in text:
                need[f"assets/vendor/{lib}"] = root / "studio" / "_vendor" / lib
        for font in (VIZ / "assets" / "fonts").glob("*.woff2"):
            if font.name.split("-700-")[0] in text:
                need[f"assets/fonts/{font.name}"] = font
    if "katex-src" in page:
        katex = root / "studio" / "_vendor" / "katex"
        for path in katex.rglob("*"):
            if path.is_file() and path.suffix in (".js", ".css", ".woff2"):
                need[f"assets/vendor/katex/{path.relative_to(katex).as_posix()}"] = path
    return need
