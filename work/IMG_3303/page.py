"""Страница графики IMG_3303 v3: почему соты у пчёл шестиугольные.

v3 (16.10.2026) — после разноса v2 («вставки не к месту, субтитры пропадают, текст за головой не видно, стиль
проебан»). Стиль — IMG_1799 v5 (rules.md п.14) + новые правила п.13, 15–18:
  - первые 2 с — человек и крупное слово; ИИ-перебивки без человека поверх, с переходами проекта (kit.footage,
    kit.slides — в behind, вход вспышкой и наводом, выход splice), субтитры идут поверх;
  - субтитры — одна линия по лицу (compose.caption_lane, y 1150); прячутся только под текстом, который повторяет
    речь, не дольше 3 с и без двойного текста (rules.md п.16, v3 → v4: «дублировались… надолго пропали»);
    схемы на груди — под линией субтитров (SCHEME), мельче на 15 %;
  - схемы v1 (паркеты, упаковка кругов, периметры) — крупно на груди, без плашек, крем и красный;
  - из приёмов fx — один: вертиго на «шестиугольник самый выгодный» (п.18, редко);
  - серия картинок вместо видео — тест на «меньше воска» (п.15).
v2 — page_v2.py.bak, director_v2.json.bak, plan_v2.md.bak. Время — секунды ролика (drop нет).

Проверено: замостить плоскость одинаковыми правильными многоугольниками можно только треугольниками, квадратами и
шестиугольниками (углы у вершины: 6×60°, 4×90°, 3×120°). Периметр при площади 1: треугольник ≈ 4,56, квадрат 4,
шестиугольник ≈ 3,72 (гипотеза о сотах, Т. Хейлз, 1999). Дарвин о сотах: «absolutely perfect in economising labour
and wax» («Происхождение видов», гл. 7). «хиган» в распознавании — «ЕГЭ».
Картинки — Wikimedia Commons (downloads/candidates.json): Дарвин — Дж. М. Камерон, 1868 (PD); соты с пыльцой
«Alveoles pleines de pollen» (CC BY 2.0); соты с мёдом «Honey comb with capped honey» (CC BY 4.0).
Футажи — сгенерированы в Google Flow (Nano Banana → Omni 1.1 Flash), не съёмка: footage/*.md.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import fx  # noqa: E402
from kit import Take, audio, build_page, card, footage, slides  # noqa: E402

STEM = "IMG_3303"
tk = Take(STEM)
DUR = tk.duration
fx.use_for(STEM)
for name in ("darwin_4.jpg", "bg_comb.jpg", "comb_2.jpg"):
    if not (ROOT / f"work/{STEM}/downloads/{name}").exists():
        sys.exit(f"✗ нет downloads/{name} — запусти work/{STEM}/fetch.py")

HEAD = 290
CHEST = 1160          # текст и схемы на груди: подбородок в этом ролике до y ~1090
SCHEME = 1240         # схемы — под линией субтитров (y 1150, строка ~77 px): субтитры над ними не прячутся
SK = 0.85             # схемы мельче, чтобы под линией субтитров не уйти глубоко в ник
RED, CREAM = "#F0352C", "#F2EBDD"
SHADOW = "0 3px 8px rgba(0,0,0,0.65), 0 14px 46px rgba(0,0,0,0.55)"
DRAW = 'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"'
SAFE = 'data-safe="лицо важнее серой зоны: схема на груди ниже подбородка (Валера, 12.10)"'
css = f'''      .tx {{ left: 0; width: 1080px; text-align: center; white-space: nowrap; }}
      .tx-lead {{ font-family: "Manrope"; font-weight: 800; font-size: 36px; letter-spacing: 0.24em; text-transform: uppercase;
                 color: var(--cream); text-shadow: {SHADOW}; }}
      .tx-big {{ font-family: "Oswald"; font-weight: 700; text-transform: uppercase; line-height: 0.9; letter-spacing: -0.01em;
                color: var(--cream); text-shadow: {SHADOW}; }}
      .tx-q {{ font-family: "Cormorant"; font-style: italic; font-weight: 700; color: var(--cream); text-shadow: {SHADOW}; }}
      .tx span {{ display: inline-block; }}
      .chest-svg {{ position: absolute; left: 0; top: 0; overflow: visible; filter: drop-shadow(0 8px 22px rgba(0,0,0,0.6)); }}
      .lbl {{ font-family: "Manrope"; font-weight: 800; font-size: 28px; letter-spacing: 0.14em; text-transform: uppercase; fill: {CREAM}; }}
      .num {{ font-family: "Oswald"; font-weight: 700; font-size: 64px; }}
      .cta {{ background: none; border: none; box-shadow: none; padding: 0; }}
      .cta-big {{ font-size: 112px; text-shadow: {SHADOW}; }}
      .cta-small {{ text-shadow: {SHADOW}; }}
      #c-darwin {{ left: 120px; top: 1070px; width: 240px; padding: 12px 12px 10px; }}
      #c-darwin .ph, #c-darwin img {{ width: 216px; height: 200px; }}
      #c-darwin .card-name {{ font-size: 19px; }}
      #c-darwin .card-sub {{ font-size: 22px; }}
'''


def lead(lid, text, top, color=CREAM, extra=""):
    return f'        <div id="{lid}" class="g tx tx-lead" {extra} style="top: {top}px; color: {color};">{text}</div>'


def big(bid, inner, top, size, color=CREAM, extra="", cls="tx-big"):
    return f'        <div id="{bid}" class="g tx {cls}" {extra} style="top: {top}px; font-size: {size}px; color: {color};">{inner}</div>'


def stamp(sid, text, top, size=120, rot=-4, extra=""):
    return (f'        <div id="{sid}" class="g tx" {extra} style="top: {top}px;">'
            f'<span class="stamp" style="font-size: {size}px; display: inline-block; transform: rotate({rot}deg);">{text}</span></div>')


def chest(cid, height, inner):
    w, h = round(1080 * SK), round(height * SK)
    return (f'        <div id="{cid}" class="g" {SAFE} style="left: {(1080 - w) // 2}px; top: {SCHEME}px; width: {w}px; height: {h}px;">'
            f'<svg class="chest-svg" viewBox="0 0 1080 {height}" style="width: {w}px; height: {h}px;">{inner}</svg></div>')


def hexagon(cx, cy, r, pointy=True):
    start = -90 if pointy else 0
    pts = [(cx + r * math.cos(math.radians(start + 60 * k)), cy + r * math.sin(math.radians(start + 60 * k))) for k in range(6)]
    return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"


# 9.0–12.9: круги естественнее → квадраты проще
roundsq = chest("rs", 230, "".join(
    f'<circle id="rs-c{i}" cx="{x}" cy="110" r="92" fill="none" stroke="{CREAM}" stroke-width="14" {DRAW} />'
    for i, x in enumerate((250, 540, 830))) + "".join(
    f'<rect id="rs-s{i}" x="{x - 88}" y="22" width="176" height="176" fill="none" stroke="{RED}" stroke-width="14" {DRAW} />'
    for i, x in enumerate((250, 540, 830))))

# 19.8–25.6: круги вплотную, щели — лишний воск
R0 = 54
circ = "".join(f'<circle class="pk-c" cx="{162 + i * 2 * R0}" cy="{70 + j * 2 * R0}" r="{R0 - 4}" fill="none" stroke="{CREAM}" stroke-width="9" />'
               for i in range(8) for j in range(2))
gaps = "".join(f'<path class="pk-g" d="M {gx} {124 - 26} Q {gx} 124 {gx + 26} 124 Q {gx} 124 {gx} {124 + 26} Q {gx} 124 {gx - 26} 124 '
               f'Q {gx} 124 {gx} {124 - 26} Z" fill="{RED}" opacity="0" />' for gx in (162 + R0 + i * 2 * R0 for i in range(7)))
pack = chest("pk", 240, circ + gaps)


# 30.5–33.2: три паркета — каждый на своё слово
def tile(x0, shapes, label, tid, color):
    return (f'<g id="{tid}" opacity="0"><clipPath id="cl-{tid}"><rect x="{x0}" y="0" width="280" height="200" rx="10" /></clipPath>'
            f'<g clip-path="url(#cl-{tid})" fill="none" stroke="{color}" stroke-width="4" stroke-linejoin="round">{shapes}</g></g>')


a = 64
h = a * math.sqrt(3) / 2
tri = "".join(f'<path d="M {70 + i * a + (j % 2) * a / 2:.1f} {j * h + h:.1f} L {70 + i * a + (j % 2) * a / 2 + a / 2:.1f} {j * h:.1f} '
              f'L {70 + i * a + (j % 2) * a / 2 + a:.1f} {j * h + h:.1f} Z" />' for i in range(-1, 5) for j in range(0, 4))
sqr = "".join(f'<rect x="{400 + 56 * i}" y="{56 * j}" width="56" height="56" />' for i in range(5) for j in range(4))
r2 = 36
hexs = "".join(f'<path d="{hexagon(730 + i * r2 * math.sqrt(3) + (j % 2) * r2 * math.sqrt(3) / 2, j * r2 * 1.5, r2)}" />'
               for i in range(5) for j in range(5))
tiles = chest("tl", 200, tile(70, tri, "треугольники", "tl-t", CREAM) + tile(400, sqr, "квадраты", "tl-s", CREAM)
              + tile(730, hexs, "шестиугольники", "tl-h", RED))

# 35.3–40.4: площадь одна — периметр короче у шестиугольника
A = 21000.0
ta = math.sqrt(4 * A / math.sqrt(3))
th = ta * math.sqrt(3) / 2
qs = math.sqrt(A)
hs = math.sqrt(2 * A / (3 * math.sqrt(3)))
cy = 115
perim = chest("pm", 270,
              f'<path id="pm-t" d="M 250 {cy - th / 2:.1f} L {250 + ta / 2:.1f} {cy + th / 2:.1f} L {250 - ta / 2:.1f} {cy + th / 2:.1f} Z" '
              f'fill="none" stroke="{CREAM}" stroke-width="10" stroke-linejoin="round" {DRAW} />'
              f'<rect id="pm-s" x="{540 - qs / 2:.1f}" y="{cy - qs / 2:.1f}" width="{qs:.1f}" height="{qs:.1f}" fill="none" stroke="{CREAM}" '
              f'stroke-width="10" {DRAW} />'
              f'<path id="pm-h" d="{hexagon(830, cy, hs, pointy=False)}" fill="none" stroke="{RED}" stroke-width="10" stroke-linejoin="round" {DRAW} />'
              f'<g class="num" text-anchor="middle"><text id="pm-n1" x="250" y="268" fill="{CREAM}" opacity="0">4,56</text>'
              f'<text id="pm-n2" x="540" y="268" fill="{CREAM}" opacity="0">4,00</text>'
              f'<text id="pm-n3" x="830" y="268" fill="{RED}" opacity="0">3,72</text></g>')

# перебивки (п.15): без человека поверх, в behind, переходы делает kit
f_tower = footage("ft-tower", STEM, "a_tower", 2.43, 2.15)
f_bees = footage("ft-bees", STEM, "b_bees", 6.21, 2.70)
f_taxi = footage("ft-taxi", STEM, "c_taxi", 13.05, 3.05)
s_wax = slides("sl-wax", ["bg_comb.jpg", "comb_2.jpg"], 40.52, [1.30, 1.30])

behind = "\n".join([
    f_tower[0], f_bees[0], f_taxi[0], s_wax[0],
])

front = "\n".join([
    lead("b-pik-lead", "застройщик", CHEST - 20, CREAM, SAFE),
    big("b-pik", "пик", CHEST + 30, 230, CREAM, SAFE),
    stamp("st-steal", "украдут", 880, 140),
    big("b-why", "почему?", CHEST, 190, RED, SAFE),
    lead("bz-lead", "соты у пчёл", 1050),
    big("bz-big", "шестиугольные", 1105, 80),
    roundsq,
    lead("mx-lead", "карл маркс", CHEST, CREAM, SAFE),
    big("mx-eco", "экономика", CHEST + 55, 120, CREAM, SAFE),
    big("mx-math", "+ математика", CHEST + 175, 96, RED, SAFE),
    pack,
    big("pk-wax", "лишний воск", 1120, 92, RED, SAFE),
    big("b-3", "3 способа", CHEST, 190, CREAM, SAFE),
    tiles,
    stamp("st-best", "самый выгодный", CHEST + 40, 110, -4, SAFE),
    perim,
    big("wx-big", "меньше воска", 1105, 84),
    card("c-darwin", "darwin_4.jpg", "Чарльз Дарвин", "о сотах, 1859", side="left"),
    '        <div id="q-darwin" class="g tx-q" style="left: 390px; top: 1170px; width: 520px; font-size: 60px; '
    'line-height: 1.05;">«совершенство<br>экономии и труда»</div>',
    '        <div id="cn-bleep" class="g censor" style="top: 1232px;"><span>***</span><b>18+</b></div>',
    big("b-80", '<span id="n80">0</span>+', CHEST - 10, 250, RED, SAFE),
])

parts = fx.vertigo(33.61, 35.25, amount=0.86, origin=(560, 760))

TX_IN = '{ fromY: 60, fromScale: 0.9, dur: 0.3, ease: "power3.out" }'
TX_OUT = '{ y: -20 }'

beats = f'''
      // ---------- хук: ты в кадре, «застройщик ПИК» на груди (за головой не видно — голова высоко) ----------
      enter("#b-pik-lead", 0.05, {TX_IN});
      slam("#b-pik", 0.63, {{ fromScale: 1.4 }});
      leave("#b-pik-lead", 2.15, {TX_OUT});
      leave("#b-pik", 2.15, {{ y: -60, dur: 0.2 }});

      // ---------- перебивка: ЖК из шестигранных башен, УКРАДУТ ----------
{f_tower[1]}
      slam("#st-steal", 3.70, {{ fromScale: 2.2, blur: 10 }});
      tl.set("#st-steal", {{ opacity: 0 }}, 4.46);

      // ---------- почему? ----------
      slam("#b-why", 4.66, {{ fromScale: 1.4 }});
      leave("#b-why", 6.00, {{ y: 30, dur: 0.18 }});

      // ---------- перебивка: пчёлы на сотах — ШЕСТИУГОЛЬНЫЕ ----------
{f_bees[1]}
      enter("#bz-lead", 7.70, {TX_IN});
      slam("#bz-big", 7.77, {{ fromScale: 1.3, blur: 8 }});
      tl.set(["#bz-lead", "#bz-big"], {{ opacity: 0 }}, 8.85);

      // ---------- круглые естественнее, квадратные проще ----------
      tl.set("#rs", {{ opacity: 1 }}, 9.70);
      draw("#rs-c0", 9.73, 0.3); draw("#rs-c1", 9.90, 0.3); draw("#rs-c2", 10.07, 0.3);
      tl.to("#rs circle", {{ opacity: 0.25, duration: 0.2 }}, 11.45);
      draw("#rs-s0", 11.53, 0.25); draw("#rs-s1", 11.70, 0.25); draw("#rs-s2", 11.87, 0.25);
      leave("#rs", 12.85, {TX_OUT});

      // ---------- перебивка: пчела-таксист с «Капиталом» ----------
{f_taxi[1]}

      // ---------- читали Маркса: экономика + математика ----------
      enter("#mx-lead", 16.30, {TX_IN});
      slam("#mx-eco", 17.80, {{ fromScale: 1.3, blur: 8 }});
      slam("#mx-math", 18.60, {{ fromScale: 1.5, blur: 8 }});
      leave("#mx-lead", 19.00, {TX_OUT}); leave("#mx-eco", 19.00, {TX_OUT}); leave("#mx-math", 19.00, {TX_OUT});

      // ---------- ячейки вплотную, круглые не встанут — лишний воск ----------
      tl.set("#pk", {{ opacity: 1 }}, 19.81);
      tl.fromTo("#pk .pk-c", {{ opacity: 0, scale: 0.4, transformOrigin: "50% 50%" }}, {{ opacity: 1, scale: 1, duration: 0.22, ease: "back.out(2)", stagger: 0.04, immediateRender: false }}, 19.81);
      tl.to("#pk .pk-g", {{ attr: {{ opacity: 1 }}, duration: 0.12, stagger: 0.08 }}, 22.25);
      slam("#pk-wax", 24.87, {{ fromScale: 1.4, blur: 10 }});
      leave("#pk", 25.62, {TX_OUT}); leave("#pk-wax", 25.62, {TX_OUT});

      // ---------- три способа и три паркета ----------
      slam("#b-3", 29.11, {{ fromScale: 1.3 }});
      leave("#b-3", 30.40, {TX_OUT});
      tl.set("#tl", {{ opacity: 1 }}, 30.50);
      tl.fromTo("#tl-t", {{ opacity: 0, y: 40 }}, {{ opacity: 1, y: 0, duration: 0.25, ease: "power3.out" }}, 30.53);
      tl.fromTo("#tl-s", {{ opacity: 0, y: 40 }}, {{ opacity: 1, y: 0, duration: 0.25, ease: "power3.out" }}, 31.37);
      tl.fromTo("#tl-h", {{ opacity: 0, y: 40 }}, {{ opacity: 1, y: 0, duration: 0.25, ease: "power3.out" }}, 32.29);
      leave("#tl", 33.45, {TX_OUT});

      // ---------- шестиугольник самый выгодный: вертиго ----------
      slam("#st-best", 34.30, {{ fromScale: 2.0, blur: 10 }});
      leave("#st-best", 35.20, {{ scale: 0.8, y: 0, dur: 0.18 }});

      // ---------- площадь одна — периметр короче ----------
      tl.set("#pm", {{ opacity: 1 }}, 35.35);
      draw("#pm-t", 35.53, 0.35); draw("#pm-s", 36.37, 0.35); draw("#pm-h", 37.61, 0.35);
      tl.to("#pm-n1", {{ attr: {{ opacity: 1 }}, duration: 0.15 }}, 38.60);
      tl.to("#pm-n2", {{ attr: {{ opacity: 1 }}, duration: 0.15 }}, 38.90);
      tl.to("#pm-n3", {{ attr: {{ opacity: 1 }}, duration: 0.15 }}, 39.27);
      leave("#pm", 40.40, {TX_OUT});

      // ---------- серия картинок: соты — МЕНЬШЕ ВОСКА ----------
{s_wax[1]}
      slam("#wx-big", 42.17, {{ fromScale: 1.3, blur: 8 }});
      tl.set("#wx-big", {{ opacity: 0 }}, 43.07);

      // ---------- Дарвин ----------
      card("#c-darwin", 43.45, 46.40, "left");
      enter("#q-darwin", 44.73, {TX_IN});
      leave("#q-darwin", 46.40, {TX_OUT});

      // ---------- [пип] ----------
      slam("#cn-bleep", 47.13, {{ fromScale: 1.6, blur: 10 }});
      leave("#cn-bleep", 47.95, {{ scale: 0.6, y: 0 }});

      // ---------- ЕГЭ на 80+ ----------
      slam("#b-80", 52.15, {{ fromScale: 1.3 }});
      tl.fromTo("#n80", {{ textContent: 0 }}, {{ textContent: 80, snap: {{ textContent: 1 }}, duration: 0.9, ease: "power2.out", immediateRender: false }}, 52.20);
      leave("#b-80", 53.55, {{ y: -60 }});
''' + parts.js

sounds = [
    audio("pik", "impact-bass-1", 0.63, 0.9),
    audio("tower", "whoosh-cinematic", 2.40, 0.7),
    audio("best", "impact-bass-2", 34.28, 0.9),
    audio("n80", "ping", 52.18, 0.8),
]
fg = parts.windows                        # человек поверх — только на вертиго (текст за головой в этом ролике не помещается)

switch, whips = tk.framing(keep_wide=[(2.3, 4.7), (6.1, 9.0), (12.9, 16.2), (40.4, 43.2), (43.4, 46.5)])
beats += whips

CTA = 54.55
page = build_page("Почему соты у пчёл шестиугольные", DUR, behind, front + "\n" + parts.front, beats, sounds, fg,
                  cta_at=CTA, extra_css=css + parts.css, fmt=tk.fmt, captions=tk.captions)
page = parts.finalize(page)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

director = {
    "_note": "IMG_3303 v3: соты. Время — секунды ролика (drop нет); раскладка — work/IMG_3303/page.py, план — plan.md.",
    "punches": [[0.63, 2.10, tk.punch, 0.10, 0.25], [4.63, 5.95, tk.punch, 0.10], [47.13, 47.95, tk.punch, 0.05],
                [50.0, 53.5, tk.punch, 0.10]] + switch,
    "text_fixes": tk.fixes({126: "ЕГЭ", 59: "Круглые", 2: "ПИК", 118: "***", 81: "квадратами и", 82: ""}),
    "keep_case": ["ЕГЭ", "ЖК", "ПИК"],
    "accent_words": ["ПИК", "шестиугольные.", "воск.", "шестиугольниками.", "периметр.", "Дарвин", "80"],
    # субтитры прячутся только под текстом, который повторяет речь (rules.md п.16): ПИК, ПОЧЕМУ?, ШЕСТИУГОЛЬНЫЕ, Маркс,
    # ЛИШНИЙ ВОСК, 3 СПОСОБА, САМЫЙ ВЫГОДНЫЙ, МЕНЬШЕ ВОСКА, цитата, 80+, финал; под пипом — звёзды только на плашке, субтитр «себе»; схемы и перебивки — с субтитрами
    "hide_captions": [[0.0, 2.40], [4.60, 6.05], [7.70, 8.90], [16.20, 19.05], [24.80, 25.70], [29.05, 30.45], [34.25, 35.25],
                      [42.10, 43.10], [44.70, 46.45], [47.10, 47.62], [52.10, 53.60], [CTA - 0.2, DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
