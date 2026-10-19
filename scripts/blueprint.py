#!/usr/bin/env python3
"""«Чертёж» — один мотив для всех вставок ролика (19.10.2026).

Валера: «вставки, сгенерированные ИИ, — просто оживлённые ИИ-фотки без общего мотива, выглядят стрёмно; нужно уйти в
математический стиль». Выбрал «Чертёж»: чёрная бумага, кремовые линии построения, красный акцент, сетка, засечки и
подписи Manrope. Условие: «хочу, чтобы в 50+% видео было моё лицо — личный бренд качаем». Поэтому у каждой вставки три
раскладки, и две из трёх лицо не убирают:

  behind — линии рисуются на шторе за спиной и вокруг головы, человек стоит поверх (окно вырезки); подписи — по бокам
           (x < 0.25 или > 0.75) или над головой: за голову ушла подпись — verify_page краснеет;
  chest  — на груди под линией субтитров, поверх человека (как схемы IMG_3303 v5): размер предмета в руке, мини-схема;
  split  — кадр с человеком уезжает в окно внизу листа, сверху лист с построением; субтитры — под подбородком в окне;
  full   — лист во весь кадр, человека нет: 1–2 раза за ролик, в доле лица (project.json → face_min) это перебивка.

Приёмы — построение линиями по словам (время каждого шага задаёт режиссёр, по шкале дубля):

  route(pid, [(подпись, x, y), …], [t…], until)     — маршрут: точки и дуги (откуда куда пришло — цифры, идеи, люди)
  timeline(pid, [(подпись, под), …], [t…], until)   — ось эпох: засечки, подписи, красная метка едет к последней
  write(pid, "0 1 2 3", t, until, sub="…")          — число или формула пишется линией и заливается; over — черта сверху
  compass(pid, t, until, label="r = 5")             — построение циркулем: центр, радиус, окружность
  hexes(pid, t, until, cols, rows, red=k)           — соты ложатся по одной, одна красная (упаковка, экономия)
  cuboid(pid, t, until, ("a", "b", "h"))            — каркас-параллелепипед с размерными линиями (площадь, объём)
  plot(pid, [y…], t, until, mark=k)                 — оси и кривая по точкам, отмеченная точка (рост, функция)
  measure(pid, (x0, y0), (x1, y1), "3 м", t, until) — размерная линия между двумя точками экрана
  look("Хорезм, IX век")                            — рамка для ИИ-клипа или фото: приглушённый цвет, сетка, подпись места

x, y у точек — доли поля раскладки (0…1). Каждый приём возвращает Piece; в страницу — Montage.blueprint(piece):
раскладку (окно вырезки, лист, сцена, переходы, доля лица, линия субтитров) сборка делает сама.

  .venv/bin/python scripts/blueprint.py --gallery    # все приёмы во всех раскладках на дубле IMG_3292 → studio/_bp_gallery
"""
import functools
import math
import re
import sys
from pathlib import Path

import formats

INK, CREAM, RED = "#141210", "#F2EBDD", "#F0352C"
W, H = 1080, 1920
LAYOUTS = ("behind", "chest", "split", "full")
FONT_DIR = Path(__file__).resolve().parents[1] / "presets" / "fonts"
FONT_FILES = {"Oswald": "Oswald-Bold.ttf", "Manrope": "Manrope-ExtraBold.ttf", "Cormorant": "CormorantGaramond.ttf",
              "Cormorant-i": "CormorantGaramond-Italic.ttf", "JBMono": "JetBrainsMono.ttf"}
# серые зоны площадок (formats.GREY_ZONES): верх во всю ширину до TOP_LINE, кнопки справа — ниже BUTTONS_LINE
ZONES = [z for _, z in formats.grey_zones("9:16")]
TOP_LINE = max(z[3] for z in ZONES if z[0] <= 0 and z[2] >= W and z[1] <= 0)
BUTTONS_LINE = min(z[1] for z in ZONES if 0 < z[0] and 0 < z[1] and z[2] >= W)
SAFE_PAD = 16                # запас от края серой зоны, px
LEAD = 24                    # подпись у края начинается (кончается) на столько левее (правее) своей точки
# поле приёма на экране (x, y, ширина, высота): за спиной — вокруг головы над грудью; в сплите — верх листа над окном;
# во весь кадр — середина листа. Подписи внутри серых зон площадок (formats.GREY_ZONES: верх 260, кнопки справа)
# Все поля — симметрично по центру кадра (x = 540): поле «во весь кадр» было 110–870 ради подписей у кнопок справа, и
# середина ушла на 490 (19.10.2026, Валера: «почему не оцентрована графика»). Кнопки площадок мешают только подписям ниже
# y 727 — их держат сами приёмы и ловит verify_page, а не сужение поля
BOXES = {"behind": (60, 280, 960, 460), "chest": (190, 1225, 700, 400), "split": (60, 280, 960, 440),
         "full": (90, 320, 900, 1060)}
WRITE_MAX = {"behind": 230, "chest": 210, "split": 320, "full": 460}     # предел кегля числа, которое пишется
CHEST_SAFE = 'data-safe="«Чертёж» на груди ниже подбородка, под линией субтитров (как схемы IMG_3303 v5)"'
SPLIT_FACE_H = 380           # высота лица в окне сплита, px
SPLIT_FACE_Y = 1050          # середина лица в окне
SPLIT_TOP = 760              # верх окна: выше — поле построения
DRAW = 'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"'

CSS = f'''
      /* «Чертёж» (scripts/blueprint.py, 19.10.2026): кремовые линии, красный акцент, подписи Manrope */
      /* толщина и кегли — под экран телефона (19.10.2026: «почему такая маленькая»): 3,5 px линии и 30 px подписи
         читались как тонкий технический чертёж, рядом со словом за головой в 150 px — мелко */
      .bp-svg {{ position: absolute; left: 0; top: 0; overflow: visible; filter: drop-shadow(0 4px 12px rgba(0,0,0,0.6)); }}
      .bp-ln {{ fill: none; stroke: {CREAM}; stroke-width: 6; stroke-linecap: round; stroke-linejoin: round; }}
      .bp-ln.red {{ stroke: {RED}; stroke-width: 7; }}
      .bp-ln.thin {{ stroke-width: 3; stroke: rgba(242,235,221,0.6); }}
      .bp-dot {{ fill: {CREAM}; opacity: 0; }}
      .bp-dot.red {{ fill: {RED}; }}
      .bp-fill {{ fill: {RED}; opacity: 0; }}
      .bp-lbl {{ position: absolute; transform: translate(-50%, -50%); white-space: nowrap; opacity: 0; text-align: center;
                font-family: "Manrope"; font-weight: 800; font-size: 40px; letter-spacing: 0.12em; text-transform: uppercase;
                color: {CREAM}; text-shadow: 0 2px 10px rgba(0,0,0,0.65); }}
      .bp-lbl.red {{ color: {RED}; }}
      /* у края кадра подпись выравнивается внутрь: left или right от точки, по вертикали — середина (GSAP читает
         только translate −50% как xPercent, поэтому сдвиг по x — не transform) */
      .bp-lbl.al, .bp-lbl.ar {{ transform: translate(0, -50%); }}
      .bp-lbl.al {{ text-align: left; }}
      .bp-lbl.ar {{ text-align: right; }}
      [data-safe] .bp-lbl {{ background: rgba(20,18,16,0.78); padding: 4px 14px 6px; border-radius: 4px; }}
      .bp-lbl.big {{ font-family: "Oswald"; font-weight: 700; font-size: 80px; letter-spacing: 0.02em; line-height: 1; }}
      .bp-lbl .sub {{ display: block; margin-top: 4px; font-family: "Cormorant"; font-style: italic; font-weight: 600;
                     font-size: 38px; letter-spacing: 0; text-transform: none; opacity: 0.9; }}
      .bp-write {{ fill: rgba(242,235,221,0); stroke: {CREAM}; stroke-width: 5; stroke-dasharray: 3000; stroke-dashoffset: 3000;
                  font-family: "Oswald"; font-weight: 700; paint-order: stroke; direction: ltr; unicode-bidi: bidi-override; }}
      /* порядок знаков — как написан (19.10.2026: восточные цифры «١ ٢ ٣ ٤ ٥» через пробел браузер клал справа налево) */
      .bp-mark {{ fill: {RED}; opacity: 0; }}
      .bp-sheet {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; opacity: 0; }}
'''


class Piece(dict):
    """Один приём «Чертежа»: html и js приёма, раскладка и окно [t0, t1] (выход доигрывает до t1 + 0.35)."""

    def __init__(self, pid: str, layout: str, t0: float, t1: float, html: str, js: str):
        if layout not in LAYOUTS:
            raise ValueError(f"«Чертёж» {pid}: раскладки «{layout}» нет — есть {', '.join(LAYOUTS)}")
        if t1 - t0 < 0.8:
            raise ValueError(f"«Чертёж» {pid}: на экране {t1 - t0:.2f} с — построение не успеть прочесть (≥ 0,8 с)")
        super().__init__(pid=pid, layout=layout, t0=round(t0, 2), t1=round(t1, 2), html=html, js=js)

    pid = property(lambda self: self["pid"])
    layout = property(lambda self: self["layout"])
    t0 = property(lambda self: self["t0"])
    t1 = property(lambda self: self["t1"])
    html = property(lambda self: self["html"])
    js = property(lambda self: self["js"])


# ---------------------------------------------------------------- общее

def _box(layout: str, box: tuple | None) -> tuple:
    if layout not in LAYOUTS:
        raise ValueError(f"«Чертёж»: раскладки «{layout}» нет — есть {', '.join(LAYOUTS)}")
    return box or BOXES[layout]


def _times(what: str, items: list, times: list) -> None:
    if len(items) != len(times) or not items:
        raise ValueError(f"«Чертёж» {what}: пунктов {len(items)}, времён {len(times)} — должно совпадать и быть > 0")
    if any(b < a for a, b in zip(times, times[1:])):
        raise ValueError(f"«Чертёж» {what}: времена не по порядку: {times}")


@functools.lru_cache(maxsize=None)
def _font(family: str) -> tuple:
    """(cmap, hmtx, единиц на кегль, высота заглавных, асцент, десцент) — метрики файла шрифта страницы."""
    from fontTools.ttLib import TTFont
    if family not in FONT_FILES:
        raise ValueError(f"«Чертёж»: шрифта «{family}» нет в presets/fonts — есть {', '.join(FONT_FILES)}")
    f = TTFont(FONT_DIR / FONT_FILES[family], lazy=True)
    upm = f["head"].unitsPerEm
    return (f.getBestCmap(), f["hmtx"], upm, f["OS/2"].sCapHeight / upm, f["hhea"].ascent / upm, -f["hhea"].descent / upm)


def _em(text: str, family: str, track: float = 0.0) -> float:
    """Ширина строки в кеглях, как её наберёт Chrome (без кернинга); track — letter-spacing на каждую букву, em."""
    cmap, hmtx, upm = _font(family)[:3]
    return sum(hmtx[cmap.get(ord(ch), ".notdef")][0] / upm + track for ch in text)


def _band(y0: float, y1: float) -> tuple:
    """Где по x может стоять текст, занимающий по высоте экрана y0…y1: между боковыми обрезками Instagram и левее
    кнопок площадок, если строка опускается ниже их верха (formats.GREY_ZONES), с запасом SAFE_PAD."""
    lo, hi = 0.0, float(W)
    for x0, zy0, x1, zy1 in ZONES:
        if zy1 <= y0 or zy0 >= y1 or (x0 <= 0 and x1 >= W):      # не на этой высоте или поперёк кадра (верх, низ)
            continue
        if x0 <= 0:
            lo = max(lo, x1)
        else:
            hi = min(hi, x0)
    return lo + SAFE_PAD, hi - SAFE_PAD


def _place(text: str, x: float, y: float, box: tuple, sub: str = "", cls: str = "", size: float | None = None) -> tuple:
    """(css-позиция, классы, рамка x0, y0, x1, y1 в поле) подписи с серединой в (x, y) поля box. Если по центру она
    заедет в боковую обрезку или под кнопки площадок, выравнивается внутрь: у левого края начинается от точки вправо,
    у правого — кончается на ней (19.10.2026: «Индия», «Европа» у краёв маршрута уходили в обрезку Instagram).
    Ширина — по метрикам шрифта, с плашкой chest; size — свой кегль вместо 40 (80 у big)."""
    big = "big" in cls.split()
    size = size or (80 if big else 40)
    wl = _em(text.upper(), "Oswald" if big else "Manrope", 0.02 if big else 0.12) * size + 28
    if sub:
        wl = max(wl, _em(sub, "Cormorant-i") * 38 + 28)
    hh = (0.55 if big else 0.7) * size + (26 if sub else 0)
    sx, sy = box[0] + x, box[1] + y
    lo, hi = _band(sy - hh, sy + hh)
    pos, x0 = f"left: {x:.0f}px", x - wl / 2
    if sx - wl / 2 < lo or sx + wl / 2 > hi:
        if sx < W / 2:
            x0 = max(sx - LEAD, lo) - box[0]
            pos, cls = f"left: {x0:.0f}px", f"{cls} al"
        else:
            x0 = min(sx + LEAD, hi) - box[0] - wl
            pos, cls = f"right: {box[2] - x0 - wl:.0f}px", f"{cls} ar"
    return pos, cls.strip(), (x0, y - hh, x0 + wl, y + hh)


def _label(lid: str, text: str, x: float, y: float, box: tuple, sub: str = "", cls: str = "", size: float | None = None) -> str:
    """Подпись с серединой в (x, y) поля box — по центру или, у края кадра, выровненная внутрь (_place)."""
    pos, cls, _ = _place(text, x, y, box, sub, cls, size)
    inner = text + (f'<span class="sub">{sub}</span>' if sub else "")
    font = f" font-size: {size:.0f}px;" if size else ""
    return f'          <div id="{lid}" class="bp-lbl {cls}" style="{pos}; top: {y:.0f}px;{font}">{inner}</div>\n'


def _pop(sel: str, t: float) -> str:
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 0, transformOrigin: "50% 50%" }}, '
            f'{{ opacity: 1, scale: 1, duration: 0.22, ease: "back.out(2.5)" }}, {t:.2f});')


def _enter(sel: str, t: float) -> str:
    return f'      enter("{sel}", {t:.2f}, {{ fromY: 24, fromScale: 0.9, dur: 0.28 }});'


def _piece(pid: str, layout: str, box: tuple, t0: float, t1: float, svg: list, labels: list, js: list) -> Piece:
    """Обёртка приёма: появление, построение по шагам, уход — линии стираются, точки сжимаются, подписи улетают."""
    x, y, w, h = box
    safe = f" {CHEST_SAFE}" if layout == "chest" else ""
    html = (f'        <div id="{pid}" class="g bp"{safe} style="left: {x}px; top: {y}px; width: {w}px; height: {h}px;">\n'
            f'          <svg class="bp-svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n'
            + "".join(f"            {s}\n" for s in svg) + "          </svg>\n" + "".join(labels) + "        </div>")
    has = lambda cls: f'class="{cls}' in html                    # noqa: E731  уход — только по тому, что есть
    pops = ", ".join(f"#{pid} .{c}" for c in ("bp-dot", "bp-fill", "bp-mark") if has(c))
    out = [f'      tl.set("#{pid}", {{ opacity: 1 }}, {t0 - 0.02:.2f});', *js]
    if has("bp-ln"):
        out.append(f'      tl.to("#{pid} .bp-ln", {{ strokeDashoffset: 1, duration: 0.3, ease: "power2.in" }}, {t1:.2f});')
    if pops:
        out.append(f'      tl.to("{pops}", {{ scale: 0, opacity: 0, transformOrigin: "50% 50%", duration: 0.22, ease: "power2.in" }}, '
                   f'{t1:.2f});')
    if has("bp-write"):
        out.append(f'      tl.to("#{pid} .bp-write", {{ strokeDashoffset: 3000, fill: "rgba(242,235,221,0)", duration: 0.3, '
                   f'ease: "power2.in" }}, {t1:.2f});')
    if labels:
        out.append(f'      leave("#{pid} .bp-lbl", {t1:.2f}, {{ y: -30, dur: 0.24 }});')
    out.append(f'      tl.set("#{pid}", {{ opacity: 0 }}, {t1 + 0.35:.2f});')
    return Piece(pid, layout, t0, t1, html, "\n".join(out) + "\n")


def _smooth(points: list) -> str:
    """Кривая через точки (Catmull-Rom → кубические Безье)."""
    d = f"M {points[0][0]:.1f} {points[0][1]:.1f}"
    for i in range(len(points) - 1):
        p0 = points[max(0, i - 1)]
        p1, p2 = points[i], points[i + 1]
        p3 = points[min(len(points) - 1, i + 2)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d


def _arrow(x: float, y: float, angle: float, size: float = 24) -> str:
    a1, a2 = angle + math.radians(150), angle - math.radians(150)
    return (f"M {x + size * math.cos(a1):.1f} {y + size * math.sin(a1):.1f} L {x:.1f} {y:.1f} "
            f"L {x + size * math.cos(a2):.1f} {y + size * math.sin(a2):.1f}")


# ---------------------------------------------------------------- приёмы

def route(pid: str, stops: list, times: list, until: float, layout: str = "behind", box: tuple | None = None,
          bend: float = 0.22) -> Piece:
    """Маршрут: точка за точкой, дуга приходит в точку на её слове; последняя — красная.

    bend — прогиб дуги в долях её длины: + вверх, − вниз (маршрут над головой: дуги провисают за волосы, подписи
    над точками свободны). Подпись — над точкой или под ней: где её не режет дуга и нет шапки площадки
    (19.10.2026: у краёв, выровненные внутрь, подписи легли на дуги, уходящие из точки вверх)."""
    _times("route", stops, times)
    bx = _box(layout, box)
    w, h = bx[2], bx[3]
    pts = [(sx * w, sy * h) for _, sx, sy in stops]
    ctrl = [((ax + px) / 2, (ay + py) / 2 - bend * math.hypot(px - ax, py - ay)) for (ax, ay), (px, py) in zip(pts, pts[1:])]
    trail = [((1 - u) ** 2 * a[0] + 2 * (1 - u) * u * c[0] + u * u * b[0], (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * c[1] + u * u * b[1])
             for a, c, b in zip(pts, ctrl, pts[1:]) for u in (k / 40 for k in range(41))]

    def cost(text: str, x: float, y: float, cls: str) -> tuple:
        x0, y0, x1, y1 = _place(text, x, y, bx, cls=cls)[2]
        cut = sum(x0 - 10 <= tx <= x1 + 10 and y0 - 10 <= ty <= y1 + 10 for tx, ty in trail)
        return (bx[1] + y0 < TOP_LINE + SAFE_PAD, cut)

    svg, labels, js = [], [], []
    for i, ((label, *_), (px, py), t) in enumerate(zip(stops, pts, times)):
        last = i == len(stops) - 1
        red = "red" if last else ""
        if i:
            (ax, ay), (mx, my) = pts[i - 1], ctrl[i - 1]
            svg.append(f'<path id="{pid}-a{i}" class="{('bp-ln ' + red).strip()}" d="M {ax:.0f} {ay:.0f} Q {mx:.0f} {my:.0f} {px:.0f} {py:.0f}" {DRAW} />')
            js.append(f'      draw("#{pid}-a{i}", {max(times[i - 1], t - 0.42):.2f}, 0.42);')
        svg.append(f'<circle id="{pid}-p{i}" class="{('bp-dot ' + red).strip()}" cx="{px:.0f}" cy="{py:.0f}" r="{18 if last else 14}" />')
        js.append(_pop(f"#{pid}-p{i}", t))
        ly = min((py - 58, py + 58), key=lambda y: cost(label, px, y, red))      # при равенстве — над точкой
        labels.append(_label(f"{pid}-l{i}", label, px, ly, bx, cls=red))
        js.append(_enter(f"#{pid}-l{i}", t + 0.04))
    return _piece(pid, layout, bx, times[0], until, svg, labels, js)


def timeline(pid: str, marks: list, times: list, until: float, layout: str = "split", box: tuple | None = None) -> Piece:
    """Ось эпох: засечка и подпись на своё слово, красная метка переезжает к каждой новой. Кегль подписей — не больше
    шага засечек (19.10.2026: «IX век», «XII век», «1700» в 80 px налезали друг на друга)."""
    _times("timeline", marks, times)
    bx = _box(layout, box)
    w, h = bx[2], bx[3]
    ay, x0, x1 = h * 0.42, w * 0.06, w * 0.94
    xs = [x0 + (x1 - x0) * (i + 0.5) / len(marks) for i in range(len(marks))]
    step = (x1 - x0) / len(marks) - 28
    size = min(80.0, *(step / _em(m[0].upper(), "Oswald", 0.02) for m in marks))
    svg = [f'<path id="{pid}-ax" class="bp-ln" d="M {x0:.0f} {ay:.0f} L {x1:.0f} {ay:.0f} {_arrow(x1, ay, 0)}" {DRAW} />',
           f'<path id="{pid}-m" class="bp-mark" d="M -24 -70 L 24 -70 L 0 -32 Z" />']
    js = [f'      draw("#{pid}-ax", {times[0] - 0.3:.2f}, 0.3);']
    labels = []
    for i, ((label, sub), x, t) in enumerate(zip(marks, xs, times)):
        svg.append(f'<path id="{pid}-k{i}" class="bp-ln" d="M {x:.0f} {ay - 28:.0f} L {x:.0f} {ay + 28:.0f}" {DRAW} />')
        js.append(f'      draw("#{pid}-k{i}", {t:.2f}, 0.15);')
        labels.append(_label(f"{pid}-l{i}", label, x, ay + 120, bx, sub, "big" + (" red" if i == len(marks) - 1 else ""),
                             None if size >= 80 else size))
        js.append(_enter(f"#{pid}-l{i}", t + 0.03))
        if i == 0:
            js.append(f'      tl.fromTo("#{pid}-m", {{ opacity: 0, x: {x:.0f}, y: {ay:.0f} }}, {{ opacity: 1, duration: 0.15 }}, {t:.2f});')
        else:
            js.append(f'      tl.to("#{pid}-m", {{ x: {x:.0f}, duration: 0.35, ease: "power3.inOut" }}, {t - 0.1:.2f});')
    return _piece(pid, layout, bx, times[0], until, svg, labels, js)


def _fit(text: str, family: str, bx: tuple, cap: float, upper: bool, size: float | None = None) -> tuple:
    """(кегль, базовая линия в поле) строки, которая пишется: ~0,92 ширины поля по метрикам шрифта, но не шире полосы
    без серых зон на высоте строки — симметрично относительно середины поля, иначе она уедет с центра.

    upper — строка в верхней части поля, над линией кнопок площадок (лист во весь кадр, 19.10.2026): по центру листа
    число шире 2·(834−540) уходило под кнопки справа, а ужатое до этой ширины выходило мельче v1 («такая маленькая»).
    verify_page меряет строку по области шрифта (асцент…десцент) в рамке поля — по ней и считается полоса."""
    x, y, w, h = bx
    em = _em(text, family) or 1.0
    capk, asc, desc = _font(family)[3:]
    cx = x + w / 2

    def wide(y0: float, y1: float) -> float:
        lo, hi = _band(y0, y1)
        return min(0.92 * w, 2 * min(cx - lo, hi - cx))

    if upper:
        bottom = min(h, BUTTONS_LINE - SAFE_PAD - y)
        size = size or min(cap, wide(y, y + bottom) / em, bottom / (capk + desc))
        return int(size), bottom / 2 + (capk - desc) / 2 * int(size)
    if not size:
        size = min(cap, 0.92 * w / em, 0.75 * h)
        base = h * 0.5 + size * 0.36
        size = min(size, wide(y + max(0.0, base - asc * size), y + min(h, base + desc * size)) / em)
    return int(size), h * 0.5 + int(size) * 0.36


def write(pid: str, text: str, t: float, until: float, layout: str = "split", box: tuple | None = None,
          size: int | None = None, sub: str = "", red: bool = False, dur: float = 0.9, font: str = "Oswald",
          over: float | None = None, titlo: bool = False) -> Piece:
    """Число или формула пишется линией и заливается (цвет — крем или красный). Кегль — по ширине поля, если не задан;
    во весь кадр — в верхней части листа, над кнопками площадок (_fit).

    over — время, когда над каждым словом текста красным прочерчивается черта: отрезок AB, период дроби; titlo —
    черта ломаная, как титло над славянской цифрой («А В Г» = 1 2 3, 19.10.2026: «писали числа буквами… с чёрточкой
    сверху»)."""
    bx = _box(layout, box)
    w, h = bx[2], bx[3]
    size, base = _fit(text, font, bx, WRITE_MAX[layout], layout == "full", size)
    fill = RED if red else CREAM
    style = f' style="font-family: {font};"' if font != "Oswald" else ""
    svg = [f'<text id="{pid}-w" class="bp-write" x="{w / 2:.0f}" y="{base:.0f}" text-anchor="middle" '
           f'font-size="{size}"{style}>{text}</text>']
    js = [f'      tl.fromTo("#{pid}-w", {{ strokeDashoffset: 3000 }}, {{ strokeDashoffset: 0, duration: {dur}, '
          f'ease: "power1.inOut" }}, {t:.2f});',
          f'      tl.to("#{pid}-w", {{ fill: "{fill}", duration: 0.3, ease: "power1.out" }}, {t + dur * 0.75:.2f});']
    if over is not None:
        left = w / 2 - _em(text, font) * size / 2
        y, a = base - _font(font)[3] * size - 0.16 * size, 0.045 * size
        for k, word in enumerate(re.finditer(r"\S+", text)):
            x0, x1 = left + _em(text[:word.start()], font) * size, left + _em(text[:word.end()], font) * size
            d = (f"M {x0:.0f} {y + a:.0f} L {x0 + (x1 - x0) / 3:.0f} {y - a:.0f} L {x0 + 2 * (x1 - x0) / 3:.0f} {y + a:.0f} "
                 f"L {x1:.0f} {y - a:.0f}") if titlo else f"M {x0:.0f} {y:.0f} L {x1:.0f} {y:.0f}"
            svg.append(f'<path id="{pid}-o{k}" class="bp-ln red" d="{d}" {DRAW} />')
            js.append(f'      draw("#{pid}-o{k}", {over + 0.12 * k:.2f}, 0.25);')
    labels = []
    if sub:
        labels.append(_label(f"{pid}-s", sub, w / 2, base + 70, bx))
        js.append(_enter(f"#{pid}-s", t + dur * 0.8))
    return _piece(pid, layout, bx, t, until, svg, labels, js)


def compass(pid: str, t: float, until: float, label: str = "", layout: str = "behind", box: tuple | None = None,
            center: tuple = (0.5, 0.5), radius: float = 0.34) -> Piece:
    """Построение циркулем: центр, радиус, ножки циркуля, окружность, подпись."""
    bx = _box(layout, box)
    w, h = bx[2], bx[3]
    cx, cy, r = center[0] * w, center[1] * h, radius * min(w, h)
    apex = (cx + r / 2, cy - 1.15 * r)
    svg = [f'<path id="{pid}-legs" class="bp-ln thin" d="M {cx:.0f} {cy:.0f} L {apex[0]:.0f} {apex[1]:.0f} L {cx + r:.0f} {cy:.0f}" {DRAW} />',
           f'<path id="{pid}-r" class="bp-ln" d="M {cx:.0f} {cy:.0f} L {cx + r:.0f} {cy:.0f}" {DRAW} />',
           f'<path id="{pid}-c" class="bp-ln red" d="M {cx + r:.0f} {cy:.0f} A {r:.0f} {r:.0f} 0 1 1 {cx - r:.0f} {cy:.0f} '
           f'A {r:.0f} {r:.0f} 0 1 1 {cx + r:.0f} {cy:.0f}" {DRAW} />',
           f'<circle id="{pid}-o" class="bp-dot" cx="{cx:.0f}" cy="{cy:.0f}" r="12" />']
    js = [_pop(f"#{pid}-o", t), f'      draw("#{pid}-legs", {t + 0.05:.2f}, 0.25);', f'      draw("#{pid}-r", {t + 0.15:.2f}, 0.25);',
          f'      draw("#{pid}-c", {t + 0.4:.2f}, 0.8);',
          f'      tl.to("#{pid}-legs", {{ strokeDashoffset: 1, duration: 0.25, ease: "power2.in" }}, {t + 1.3:.2f});']
    labels = []
    if label:
        labels.append(_label(f"{pid}-l", label, cx + r / 2, cy + 34, bx))
        js.append(_enter(f"#{pid}-l", t + 0.45))
    return _piece(pid, layout, bx, t, until, svg, labels, js)


def hexes(pid: str, t: float, until: float, cols: int = 5, rows: int = 3, red: int | None = None, label: str = "",
          layout: str = "behind", box: tuple | None = None, step: float = 0.06) -> Piece:
    """Соты: шестиугольники ложатся по одному, один заливается красным; подпись снизу."""
    bx = _box(layout, box)
    w, h = bx[2], bx[3]
    s = min(0.86 * w / (math.sqrt(3) * (cols + 0.5)), 0.7 * h / (1.5 * rows + 0.5))
    x0 = (w - math.sqrt(3) * s * (cols + 0.5)) / 2 + math.sqrt(3) * s / 2
    y0 = (h * 0.82 - (1.5 * rows - 0.5) * s) / 2 + s
    svg, js, k = [], [], 0
    for r in range(rows):
        for c in range(cols):
            cx, cy = x0 + math.sqrt(3) * s * (c + 0.5 * (r % 2)), y0 + 1.5 * s * r
            pts = " L ".join(f"{cx + s * math.cos(math.radians(60 * i + 30)):.1f} {cy + s * math.sin(math.radians(60 * i + 30)):.1f}"
                             for i in range(6))
            if red == k:
                svg.append(f'<path id="{pid}-f" class="bp-fill" d="M {pts} Z" />')
            svg.append(f'<path id="{pid}-h{k}" class="bp-ln{" red" if red == k else ""}" d="M {pts} Z" {DRAW} />')
            js.append(f'      draw("#{pid}-h{k}", {t + k * step:.2f}, 0.25);')
            k += 1
    if red is not None:
        js.append(f'      tl.fromTo("#{pid}-f", {{ opacity: 0 }}, {{ opacity: 0.85, duration: 0.25 }}, {t + k * step + 0.15:.2f});')
    labels = []
    if label:
        labels.append(_label(f"{pid}-l", label, w / 2, y0 + 1.5 * s * (rows - 1) + s + 64, bx))
        js.append(_enter(f"#{pid}-l", t + k * step + 0.1))
    return _piece(pid, layout, bx, t, until, svg, labels, js)


def cuboid(pid: str, t: float, until: float, dims: tuple = ("a", "b", "h"), layout: str = "split",
           box: tuple | None = None, step: float = 0.06) -> Piece:
    """Каркас-параллелепипед в изометрии, ребро за ребром, потом размерные линии с подписями a, b, h."""
    bx = _box(layout, box)
    w, h = bx[2], bx[3]
    u = min(w * 0.26, h * 0.32)
    cos30, sin30 = math.cos(math.radians(30)), 0.5
    # середина фигуры — в середине поля: вправо ребро 1.4, влево 1 → сдвиг влево; по высоте фигура 2,3 u над нижней точкой
    ox, oy = w / 2 - 0.2 * u * cos30, h / 2 + 1.15 * u
    a = lambda k: (k * u * cos30, -k * u * sin30)                  # noqa: E731  вправо-вверх
    b = lambda k: (-k * u * cos30, -k * u * sin30)                 # noqa: E731  влево-вверх
    p = {}
    for i, (da, db, dh) in enumerate([(0, 0, 0), (1.4, 0, 0), (1.4, 1, 0), (0, 1, 0), (0, 0, 1.1), (1.4, 0, 1.1), (1.4, 1, 1.1), (0, 1, 1.1)]):
        x = ox + a(da)[0] + b(db)[0]
        y = oy + a(da)[1] + b(db)[1] - dh * u
        p[i] = (x, y)
    edges = [(0, 1), (1, 2), (0, 4), (1, 5), (4, 5), (5, 6), (4, 7), (6, 7), (0, 3), (2, 6), (3, 7), (2, 3)]
    hidden = {(2, 3), (3, 7), (2, 6)}
    svg, js = [], []
    for k, (i, j) in enumerate(edges):
        cls = "bp-ln thin" if (i, j) in hidden else "bp-ln"
        svg.append(f'<path id="{pid}-e{k}" class="{cls}" d="M {p[i][0]:.0f} {p[i][1]:.0f} L {p[j][0]:.0f} {p[j][1]:.0f}" {DRAW} />')
        js.append(f'      draw("#{pid}-e{k}", {t + k * step:.2f}, 0.2);')
    td = t + len(edges) * step + 0.1
    off = 30
    dims_at = [((p[0][0], p[0][1] + off), (p[1][0], p[1][1] + off)), ((p[0][0], p[0][1] + off), (p[3][0], p[3][1] + off)),
               ((p[1][0] + off, p[1][1]), (p[5][0] + off, p[5][1]))]
    labels = []
    for k, ((x0, y0), (x1, y1)) in enumerate(dims_at):
        ang = math.atan2(y1 - y0, x1 - x0)
        svg.append(f'<path id="{pid}-d{k}" class="bp-ln red" d="M {x0:.0f} {y0:.0f} L {x1:.0f} {y1:.0f} {_arrow(x1, y1, ang, 12)} '
                   f'{_arrow(x0, y0, ang + math.pi, 12)}" {DRAW} />')
        js.append(f'      draw("#{pid}-d{k}", {td + k * 0.2:.2f}, 0.3);')
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        nx, ny = ((-math.sin(ang), math.cos(ang)) if k == 0 else (math.sin(ang), -math.cos(ang)) if k == 1 else (1, 0))
        labels.append(_label(f"{pid}-l{k}", dims[k], mx + nx * 40, my + ny * 40, bx, cls="red"))
        js.append(_enter(f"#{pid}-l{k}", td + k * 0.2 + 0.15))
    return _piece(pid, layout, bx, t, until, svg, labels, js)


def plot(pid: str, ys: list, t: float, until: float, mark: int | None = None, xlabel: str = "", ylabel: str = "",
         label: str = "", layout: str = "split", box: tuple | None = None, dur: float = 0.9) -> Piece:
    """Оси и кривая по точкам ys (0…1 снизу вверх, x — поровну); отмеченная точка — красная с проекциями на оси."""
    if len(ys) < 2:
        raise ValueError(f"«Чертёж» plot {pid}: нужна хотя бы пара точек")
    bx = _box(layout, box)
    w, h = bx[2], bx[3]
    x0, y0, x1, y1 = w * 0.1, h * 0.86, w * 0.92, h * 0.08
    pts = [(x0 + (x1 - x0) * i / (len(ys) - 1), y0 - (y0 - y1) * v) for i, v in enumerate(ys)]
    svg = [f'<path id="{pid}-ax" class="bp-ln" d="M {x0:.0f} {y1 - 20:.0f} L {x0:.0f} {y0:.0f} L {x1 + 30:.0f} {y0:.0f} '
           f'{_arrow(x1 + 30, y0, 0)} {_arrow(x0, y1 - 20, -math.pi / 2)}" {DRAW} />',
           f'<path id="{pid}-cv" class="bp-ln red" d="{_smooth(pts)}" {DRAW} />']
    js = [f'      draw("#{pid}-ax", {t:.2f}, 0.3);', f'      draw("#{pid}-cv", {t + 0.3:.2f}, {dur});']
    labels = []
    if xlabel:
        labels.append(_label(f"{pid}-x", xlabel, x1 - 70, y0 + 42, bx))
        js.append(_enter(f"#{pid}-x", t + 0.2))
    if ylabel:
        labels.append(_label(f"{pid}-y", ylabel, x0 + 10, y1 - 50, bx))
        js.append(_enter(f"#{pid}-y", t + 0.2))
    if mark is not None:
        mx, my = pts[mark]
        tm = t + 0.3 + dur * mark / (len(ys) - 1)
        svg += [f'<path id="{pid}-pr" class="bp-ln thin" d="M {mx:.0f} {my:.0f} L {mx:.0f} {y0:.0f} M {mx:.0f} {my:.0f} L {x0:.0f} {my:.0f}" {DRAW} />',
                f'<circle id="{pid}-pt" class="bp-dot red" cx="{mx:.0f}" cy="{my:.0f}" r="18" />']
        js += [_pop(f"#{pid}-pt", tm), f'      draw("#{pid}-pr", {tm + 0.05:.2f}, 0.3);']
        if label:
            labels.append(_label(f"{pid}-l", label, mx, my - 50, bx, cls="red"))
            js.append(_enter(f"#{pid}-l", tm + 0.1))
    return _piece(pid, layout, bx, t, until, svg, labels, js)


def measure(pid: str, a: tuple, b: tuple, label: str, t: float, until: float, layout: str = "chest", off: float = 0) -> Piece:
    """Размерная линия между двумя точками экрана (px): выносные засечки, стрелки, подпись посередине."""
    pad = 70
    box = (round(min(a[0], b[0]) - pad), round(min(a[1], b[1]) - pad),
           round(abs(b[0] - a[0]) + 2 * pad), round(abs(b[1] - a[1]) + 2 * pad))
    ax, ay, bx2, by = a[0] - box[0], a[1] - box[1], b[0] - box[0], b[1] - box[1]
    ang = math.atan2(by - ay, bx2 - ax)
    nx, ny = -math.sin(ang) * off, math.cos(ang) * off
    p0, p1 = (ax + nx, ay + ny), (bx2 + nx, by + ny)
    svg = [f'<path id="{pid}-x" class="bp-ln thin" d="M {ax:.0f} {ay:.0f} L {p0[0]:.0f} {p0[1]:.0f} M {bx2:.0f} {by:.0f} '
           f'L {p1[0]:.0f} {p1[1]:.0f}" {DRAW} />',
           f'<path id="{pid}-d" class="bp-ln red" d="M {p0[0]:.0f} {p0[1]:.0f} L {p1[0]:.0f} {p1[1]:.0f} '
           f'{_arrow(p1[0], p1[1], ang, 14)} {_arrow(p0[0], p0[1], ang + math.pi, 14)}" {DRAW} />']
    js = [f'      draw("#{pid}-x", {t:.2f}, 0.2);', f'      draw("#{pid}-d", {t + 0.1:.2f}, 0.35);']
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    labels = [_label(f"{pid}-l", label, mx - math.sin(ang) * 36, my + math.cos(ang) * 36 - 30, box, cls="red")]
    js.append(_enter(f"#{pid}-l", t + 0.3))
    return _piece(pid, layout, box, t, until, svg, labels, js)


# ---------------------------------------------------------------- лист, сплит, рамка клипа

def _paper(sid: str, hole: tuple | None = None) -> str:
    """Лист: чёрная бумага, мелкая и крупная сетка, рамка с отступом; hole — окно (x0, y0, x1, y1), где виден кадр."""
    outer = f"M 0 0 H {W} V {H} H 0 Z"
    cut = f" M {hole[0]} {hole[1]} V {hole[3]} H {hole[2]} V {hole[1]} Z" if hole else ""
    marks = "".join(f'<path d="M {x - 22} {y} H {x + 22} M {x} {y - 22} V {y + 22}" stroke="{CREAM}" stroke-width="2" '
                    f'stroke-opacity="0.6" fill="none" />' for x, y in ((54, 54), (W - 54, 54), (54, H - 54), (W - 54, H - 54)))
    frame = ""
    if hole:
        x0, y0, x1, y1 = hole
        frame = (f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="none" stroke="{CREAM}" stroke-width="3" />'
                 f'<path d="M {x0 - 26} {y0} H {x0 - 8} M {x1 + 8} {y0} H {x1 + 26} M {x0 - 26} {y1} H {x0 - 8} M {x1 + 8} {y1} '
                 f'H {x1 + 26} M {x0 - 17} {y0} V {y1} M {x1 + 17} {y0} V {y1}" stroke="{CREAM}" stroke-opacity="0.5" '
                 f'stroke-width="2" fill="none" />')
    return (f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="position: absolute; left: 0; top: 0;">'
            f'<defs><pattern id="{sid}-g1" width="36" height="36" patternUnits="userSpaceOnUse">'
            f'<path d="M 36 0 L 0 0 0 36" fill="none" stroke="{CREAM}" stroke-opacity="0.07" stroke-width="1" /></pattern>'
            f'<pattern id="{sid}-g2" width="180" height="180" patternUnits="userSpaceOnUse">'
            f'<path d="M 180 0 L 0 0 0 180" fill="none" stroke="{CREAM}" stroke-opacity="0.14" stroke-width="1.5" /></pattern></defs>'
            f'<path d="{outer}{cut}" fill="{INK}" fill-rule="evenodd" />'
            f'<path d="{outer}{cut}" fill="url(#{sid}-g1)" fill-rule="evenodd" />'
            f'<path d="{outer}{cut}" fill="url(#{sid}-g2)" fill-rule="evenodd" />'
            f'<rect x="30" y="30" width="{W - 60}" height="{H - 60}" fill="none" stroke="{CREAM}" stroke-opacity="0.35" stroke-width="2" />'
            f'{marks}{frame}</svg>')


def full_sheet(piece: Piece, at: float, until: float) -> tuple:
    """Лист во весь кадр с приёмом внутри: (html для behind, js). Перебивка: класс footage и data-fullframe — её видят
    доля лица и проверки «человека поверх нет»; вход и выход — переходами проекта (kit._cutaway_js)."""
    import kit
    sid = f"{piece.pid}-sheet"
    html = (f'        <div id="{sid}" class="g footage" data-fullframe="чертёж во весь кадр" '
            f'style="left: 0; top: 0; width: {W}px; height: {H}px; overflow: hidden; background: {INK};">\n'
            f'          {_paper(sid)}\n{piece.html}\n        </div>')
    return html, piece.js + kit._cutaway_js(sid, at, until - at) + "\n"


def split_geometry(face: tuple) -> dict:
    """Сплит по лицу на экране (x0, y0, x1, y1 при обычном кадре): масштаб и сдвиг сцены, окно листа, линия субтитров.

    Лицо в окне — SPLIT_FACE_H px, середина — на SPLIT_FACE_Y; окно ровно по кадру сцены (кадр полный — п.2 правил),
    сверху обрезано до SPLIT_TOP: выше — поле построения. Субтитры — под подбородком в окне, выше ника Instagram.
    """
    x0, y0, x1, y1 = face
    k = min(0.62, SPLIT_FACE_H / max(1.0, y1 - y0))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    tx, ty = W / 2 - k * cx, SPLIT_FACE_Y - k * cy
    tx = min(max(tx, 40.0), W - W * k - 40.0)                    # окно не прилипает к краю листа
    hole = (round(tx), round(max(ty, SPLIT_TOP)), round(tx + W * k), round(min(ty + H * k, H - 70)))
    return {"k": round(k, 4), "x": round(tx, 1), "y": round(ty, 1), "hole": hole,
            "lane": round(ty + k * y1 + 34), "face": (round(tx + k * x0), round(ty + k * y0), round(tx + k * x1), round(ty + k * y1))}


def split_parts(piece: Piece, geo: dict) -> tuple:
    """Сплит: (лист с окном — в front первым, js сцены и листа). Вход и выход — переходом проекта: вспышка в 3 кадра, под
    ней сцена встаёт в окно (#stage — fx.FX.finalize), лист — целиком, кадр наводится из смаза. Раскатка листа сверху
    при сжатии сцены оставляла по краям чёрную пустоту на треть секунды (19.10.2026, кадр 13.6 демо IMG_3292) — п.2
    правил: кадр всегда полный. Субтитры на время сплита — над листом (#caps zIndex)."""
    sid, a, b = f"{piece.pid}-sheet", piece.t0 - 0.25, piece.t1 + 0.3
    html = f'        <div id="{sid}" class="bp-sheet">{_paper(sid, geo["hole"])}</div>'
    k, x, y = geo["k"], geo["x"], geo["y"]
    js = (f'      // «Чертёж», сплит: человек в окне листа {geo["hole"]}, лицо {geo["face"]}\n'
          f'      tl.fromTo("#flash", {{ opacity: 0 }}, {{ opacity: 0.55, duration: 0.033, ease: "none", immediateRender: false }}, {a - 0.033:.3f});\n'
          f'      tl.to("#flash", {{ opacity: 0, duration: 0.16, ease: "power1.out" }}, {a:.3f});\n'
          f'      tl.set("#{sid}", {{ opacity: 1 }}, {a:.3f});\n'
          f'      tl.set("#caps", {{ zIndex: 5 }}, {a:.3f});\n'
          f'      tl.fromTo("#stage", {{ scale: {k * 1.08:.4f}, x: {x - (k * 0.08) * 540:.1f}, y: {y - (k * 0.08) * 1050:.1f}, filter: BLUR(14) }}, '
          f'{{ scale: {k}, x: {x}, y: {y}, filter: BLUR(0), duration: 0.3, ease: "power3.out", immediateRender: false }}, {a:.3f});\n'
          f'      tl.fromTo("#flash", {{ opacity: 0 }}, {{ opacity: 0.55, duration: 0.033, ease: "none", immediateRender: false }}, {b - 0.033:.3f});\n'
          f'      tl.to("#flash", {{ opacity: 0, duration: 0.16, ease: "power1.out" }}, {b:.3f});\n'
          f'      tl.set("#{sid}", {{ opacity: 0 }}, {b:.3f});\n'
          f'      tl.set("#caps", {{ zIndex: 0 }}, {b:.3f});\n'
          f'      tl.fromTo("#stage", {{ scale: 1.06, x: -32, y: -58, filter: BLUR(14) }}, {{ scale: 1, x: 0, y: 0, filter: BLUR(0), '
          f'duration: 0.3, ease: "power3.out", immediateRender: false }}, {b:.3f});\n')
    return html, piece.js + js


SPLIT_CSS = ("      #stage { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; transform-origin: 0 0; }\n"
             "      #caps { position: absolute; left: 0; top: 0; width: 100%; height: 100%; }\n")


def look(label: str = "", fig: int = 1) -> tuple:
    """Рамка мотива для ИИ-клипа или фото во весь кадр: (overlay, clip_css) для kit.footage/slides.

    Клип — приглушённый, но в цвете, поверх — сетка листа, рамка, метки углов и короткая подпись места.
    Разные генерации так читаются одной серией, а не стоком. fig — номер рамки на странице (id сетки).

    19.10.2026, Валера на демо IMG_3292: «очень жёсткое затемнение, ч/б слишком сильное… кадр полностью теряется,
    можно оставить немного цвета» и «"Фиг. 1" — убирай, отнимает место, внимание и время». Было: полный ч/б,
    контраст 1,25, яркость 0,92, крем умножением и чёрное в коричневый — на тёмных клипах Flow кадр пропадал."""
    sid = f"lk{fig}"
    grid = (f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="position: absolute; left: 0; top: 0;">'
            f'<defs><pattern id="{sid}-g" width="90" height="90" patternUnits="userSpaceOnUse">'
            f'<path d="M 90 0 L 0 0 0 90" fill="none" stroke="{CREAM}" stroke-opacity="0.1" stroke-width="1.2" /></pattern></defs>'
            f'<rect width="{W}" height="{H}" fill="url(#{sid}-g)" />'
            f'<rect x="36" y="36" width="{W - 72}" height="{H - 72}" fill="none" stroke="{CREAM}" stroke-opacity="0.55" stroke-width="2.5" />'
            + "".join(f'<path d="M {x - 26} {y} H {x + 26} M {x} {y - 26} V {y + 26}" stroke="{RED}" stroke-width="3" fill="none" />'
                      for x, y in ((80, 300), (W - 80, 300), (80, 1300), (W - 80, 1300)))
            + "</svg>")
    # подпись места — сверху слева (ниже вкладок TikTok): внизу справа её закрывают кнопки площадок
    caption = (f'          <div style="position: absolute; left: 120px; top: 340px; max-width: 840px; font-family: Manrope; '
               f'font-weight: 800; font-size: 32px; letter-spacing: 0.18em; text-transform: uppercase; color: {CREAM}; '
               f'text-shadow: 0 2px 8px rgba(0,0,0,0.7);">{label}</div>\n') if label else ""
    # лёгкий тёплый налёт крема — серия читается одной, а цвет и свет клипа остаются
    overlay = (f'          <div style="position: absolute; inset: 0; background: {CREAM}; mix-blend-mode: soft-light; opacity: 0.22;"></div>\n'
               f'          {grid}\n{caption}')
    return overlay, " filter: saturate(0.55) contrast(1.04) brightness(1.1);"


# ---------------------------------------------------------------- галерея

def gallery() -> None:
    """Все приёмы во всех раскладках на дубле IMG_3292 — studio/_bp_gallery (подчёркивание: --all её пропускает)."""
    import json
    import os
    import shutil
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import fx
    import kit
    root = Path(__file__).resolve().parents[1]
    src, dst = root / "studio" / "IMG_3292", root / "studio" / "_bp_gallery"
    if not (src / "index.html").exists() or not (src / "assets" / "cutout.webm").exists():
        sys.exit("✗ галерее нужен собранный ролик IMG_3292 (studio/IMG_3292 с вырезкой) — на этой машине его нет")
    dst.mkdir(exist_ok=True)
    for name in ("camera.js", "captions.js", "layers.js", "edits.js", "hyperframes.json", "package.json"):
        shutil.copy2(src / name, dst / name)
    for f in (src / "assets").rglob("*"):
        if f.is_file():
            out = dst / "assets" / f.relative_to(src / "assets")
            out.parent.mkdir(parents=True, exist_ok=True)
            if not out.exists():
                os.link(f, out)
    (dst / "captions.js").write_text("window.CAPTIONS = [];\n", encoding="utf-8")
    import verify_page
    track = verify_page.face_track(src)
    med = lambda i: sorted(f[i] for f in track)[len(track) // 2] if track else (330, 440, 750, 1060)[i - 1]   # noqa: E731
    geo = split_geometry((med(1), med(2), med(3), med(4)))
    S = 3.4
    at = [0.5 + i * S for i in range(9)]
    pieces = [
        route("g-route", [("Индия", 0.9, 0.2), ("Багдад", 0.5, 0.18), ("Европа", 0.1, 0.2)],
              [at[0], at[0] + 0.7, at[0] + 1.4], at[0] + 2.9, layout="behind", bend=-0.22),
        timeline("g-time", [("IX век", "Багдад"), ("XII век", "латынь"), ("1700", "Пётр I"), ("2026", "мы")],
                 [at[1], at[1] + 0.5, at[1] + 1.0, at[1] + 1.5], at[1] + 2.9, layout="split"),
        write("g-write", "0 1 2 3 4 5 6 7 8 9", at[2], at[2] + 2.9, layout="split", sub="придумали в Индии"),
        compass("g-comp", at[3], at[3] + 2.9, label="r", layout="behind", center=(0.82, 0.45), radius=0.3),
        hexes("g-hex", at[4], at[4] + 2.9, cols=6, rows=4, red=9, label="соты — без щелей", layout="full"),
        cuboid("g-box", at[5], at[5] + 2.9, ("12 м", "8 м", "3 м"), layout="split"),
        plot("g-plot", [0.08, 0.12, 0.2, 0.35, 0.6, 0.95], at[6], at[6] + 2.9, mark=4, xlabel="годы", ylabel="цена",
             label="+70%", layout="full"),
        measure("g-meas", (290, 1250), (290, 1520), "12 см", at[7], at[7] + 2.9, off=-40),
    ]
    behind, front, sheets, js, windows, css, lanes = [], [], [], [], [], [CSS], []
    for p in pieces:
        if p.layout == "behind":
            behind.append(p.html)
            js.append(p.js)
            windows.append((p.t0 - 0.05, p.t1 + 0.4))
        elif p.layout == "chest":
            front.append(p.html)
            js.append(p.js)
        elif p.layout == "full":
            html, j = full_sheet(p, p.t0 - 0.25, p.t1 + 0.35)
            behind.append(html)
            js.append(j)
        else:
            html, j = split_parts(p, geo)
            sheets.append(html)
            front.append(p.html)
            js.append(j)
            lanes.append((p.t0, p.t1, geo["lane"]))
    overlay, clip = look("Хорезм, IX век", 2)
    ft = kit.footage("g-ft", "IMG_3292", "b_khorezm", at[8], 2.4, overlay=overlay, clip_css=clip)
    behind.append(ft[0])
    js.append(ft[1])
    css.append(SPLIT_CSS)
    dur = at[8] + 3.0
    page = kit.build_page("«Чертёж» — галерея", dur, "\n".join(behind), "\n".join(sheets + front), "\n".join(js), [], windows,
                          dur - 1, extra_css="".join(css), cta=False)
    page = fx.FX(stage=True).finalize(page)
    (dst / "index.html").write_text(page, encoding="utf-8")
    shots = [round(a + x, 2) for a in at for x in (0.6, 2.2)]
    print(f"✓ {dst.relative_to(root)}/index.html · {dur:.1f} с · сплит: {json.dumps(geo, ensure_ascii=False)}")
    print(f"  снимки: cd {dst.relative_to(root)} && npx --yes hyperframes@0.8.141 snapshot --no-end --describe false "
          f"--at {','.join(map(str, shots))}")


if __name__ == "__main__":
    if "--gallery" in sys.argv:
        gallery()
    else:
        print(__doc__)
