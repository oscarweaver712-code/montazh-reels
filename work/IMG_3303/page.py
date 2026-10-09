"""Страница графики IMG_3303: почему соты шестиугольные.

Время ударов — по исходнику (work/IMG_3303.words.json), на шкалу дубля переводит Take.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, card  # noqa: E402

STEM = "IMG_3303"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
AMBER = "#F5B82E"


def hexagon(cx: float, cy: float, r: float, pointy: bool = True) -> str:
    start = -90 if pointy else 0
    pts = [(cx + r * math.cos(math.radians(start + 60 * k)), cy + r * math.sin(math.radians(start + 60 * k)))
           for k in range(6)]
    return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"


# соты за головой: шестиугольники «остриём вверх», как в настоящих сотах
R = 58
comb = []
for j in range(5):
    for i in range(12):
        cx = 40 + i * R * math.sqrt(3) + (j % 2) * R * math.sqrt(3) / 2
        cy = 60 + j * R * 1.5
        comb.append(f'<path class="hx" d="{hexagon(cx, cy, R - 3)}" fill="rgba(245,184,46,0)" stroke="{AMBER}" '
                    f'stroke-width="5" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />')
comb_svg = ('        <svg id="comb" class="g" viewBox="0 0 1080 420" style="left: 0; top: 40px; width: 1080px; height: 420px;">\n          '
            + "\n          ".join(comb) + "\n        </svg>")


def tile_panel(pid: str, left: int, label: str, shapes: str) -> str:
    return (f'        <div id="{pid}" class="g" style="left: {left}px; top: 1262px; width: 310px; height: 352px; border-radius: 24px; '
            f'background: rgba(12,12,14,0.86); border: 2px solid rgba(242,235,221,0.16); overflow: hidden;">\n'
            f'          <svg viewBox="0 0 310 290" style="position: absolute; left: 0; top: 0; width: 310px; height: 290px;">'
            f'<defs><clipPath id="clip-{pid}"><rect x="14" y="14" width="282" height="262" rx="14" /></clipPath></defs>'
            f'<g clip-path="url(#clip-{pid})" fill="none" stroke="#F2EBDD" stroke-width="4" stroke-linejoin="round">{shapes}</g></svg>\n'
            f'          <div class="label" style="position: absolute; left: 0; top: 296px; width: 310px; font-size: 24px; letter-spacing: 0.08em;">{label}</div>\n'
            f'        </div>')


# паркеты: одинаковые правильные фигуры без щелей
a = 74
h = a * math.sqrt(3) / 2
tri = []
for j in range(-1, 6):
    for i in range(-1, 6):
        x0 = i * a + (j % 2) * a / 2
        y0 = j * h
        tri.append(f'<path d="M {x0:.1f} {y0 + h:.1f} L {x0 + a / 2:.1f} {y0:.1f} L {x0 + a:.1f} {y0 + h:.1f} Z" />')
        tri.append(f'<path d="M {x0 + a / 2:.1f} {y0:.1f} L {x0 + a * 1.5:.1f} {y0:.1f} L {x0 + a:.1f} {y0 + h:.1f} Z" />')
sq = [f'<rect x="{x}" y="{y}" width="66" height="66" />' for x in range(14, 300, 66) for y in range(14, 290, 66)]
hx = []
r2 = 40
for j in range(-1, 6):
    for i in range(-1, 6):
        hx.append(f'<path d="{hexagon(i * r2 * math.sqrt(3) + (j % 2) * r2 * math.sqrt(3) / 2, j * r2 * 1.5, r2)}" />')

# упаковка кругов: щели между ними — потерянное место
pack = "".join(f'<circle cx="{80 + 100 * i}" cy="{90 + 100 * j}" r="48" fill="{AMBER}" stroke="#C98E12" stroke-width="4" />'
               for i in range(8) for j in range(3))
pack_html = f'''        <svg id="pack" class="g" viewBox="0 0 860 380" style="left: 110px; top: 1252px; width: 860px; height: 380px;">
          <rect id="pack-bg" x="0" y="0" width="860" height="380" rx="26" fill="#16130F" />
          <g id="pack-g">{pack}</g>
        </svg>'''

# сравнение при равной площади: у шестиугольника периметр короче всех
A = 19000.0
ta_ = math.sqrt(4 * A / math.sqrt(3))
th = ta_ * math.sqrt(3) / 2
qs = math.sqrt(A)
hs = math.sqrt(2 * A / (3 * math.sqrt(3)))
cy = 165
cmp_svg = f'''        <div id="cmp" class="g" style="left: 60px; top: 1252px; width: 960px; height: 430px; border-radius: 28px; background: rgba(12,12,14,0.86); border: 2px solid rgba(242,235,221,0.16);">
          <svg viewBox="0 0 960 430" style="position: absolute; left: 0; top: 0; width: 960px; height: 430px;">
            <g fill="rgba(242,235,221,0.10)" stroke="#F2EBDD" stroke-width="6" stroke-linejoin="round">
              <path d="M 160 {cy - th / 2:.1f} L {160 + ta_ / 2:.1f} {cy + th / 2:.1f} L {160 - ta_ / 2:.1f} {cy + th / 2:.1f} Z" />
              <rect x="{480 - qs / 2:.1f}" y="{cy - qs / 2:.1f}" width="{qs:.1f}" height="{qs:.1f}" />
            </g>
            <path id="cmp-hex" d="{hexagon(800, cy, hs, pointy=False)}" fill="rgba(245,184,46,0.30)" stroke="{AMBER}" stroke-width="6" stroke-linejoin="round" />
            <g font-family="JBMono" font-weight="700" font-size="34" fill="#F2EBDD" text-anchor="middle">
              <text x="160" y="300">S = 1</text><text x="480" y="300">S = 1</text><text x="800" y="300">S = 1</text>
            </g>
            <g font-family="JBMono" font-weight="700" font-size="40" text-anchor="middle">
              <text class="pl" x="160" y="372" fill="rgba(242,235,221,0.75)" opacity="0">P ≈ 4,56</text>
              <text class="pl" x="480" y="372" fill="rgba(242,235,221,0.75)" opacity="0">P = 4</text>
              <text id="pl-hex" class="pl" x="800" y="372" fill="#3BD16F" opacity="0">P ≈ 3,72</text>
            </g>
          </svg>
        </div>'''

bee = f'''        <svg id="bee" class="g" viewBox="0 0 300 220" style="left: 700px; top: 220px; width: 300px; height: 220px; overflow: visible;">
          <defs><clipPath id="bee-clip"><ellipse cx="150" cy="130" rx="78" ry="54" /></clipPath></defs>
          <g id="bee-wings">
            <ellipse cx="128" cy="66" rx="36" ry="54" fill="rgba(235,245,255,0.72)" stroke="#F2EBDD" stroke-width="4" transform="rotate(-18 128 66)" />
            <ellipse cx="176" cy="64" rx="36" ry="54" fill="rgba(235,245,255,0.72)" stroke="#F2EBDD" stroke-width="4" transform="rotate(18 176 64)" />
          </g>
          <g clip-path="url(#bee-clip)">
            <rect x="60" y="70" width="190" height="130" fill="{AMBER}" />
            <rect x="112" y="70" width="24" height="130" fill="#17130E" /><rect x="160" y="70" width="24" height="130" fill="#17130E" />
            <rect x="207" y="70" width="24" height="130" fill="#17130E" />
          </g>
          <ellipse cx="150" cy="130" rx="78" ry="54" fill="none" stroke="#F2EBDD" stroke-width="5" />
          <path d="M 226 124 L 266 134 L 226 144 Z" fill="#F2EBDD" />
          <circle cx="70" cy="120" r="36" fill="#17130E" stroke="#F2EBDD" stroke-width="5" />
          <circle cx="58" cy="110" r="8" fill="#F2EBDD" />
          <path d="M 54 88 Q 40 52 20 42 M 74 86 Q 74 50 60 30" fill="none" stroke="#F2EBDD" stroke-width="5" stroke-linecap="round" />
        </svg>'''

behind = "\n".join([
    '        <div id="w-lead" class="g lead" style="top: 64px;">украдёт у меня эту идею</div>',
    '        <div id="w-pik" class="g big" style="top: 60px; font-size: 250px;">ПИК</div>',
    '        <div id="w-sam" class="g big red" style="top: 130px; font-size: 210px;">«Самолёт»</div>',
    '        <div id="q" class="g big" style="top: 90px; font-size: 300px;">?</div>',
    comb_svg,
    '        <div id="w-3" class="g big" style="top: 120px; font-size: 220px;">3 способа</div>',
])
front = "\n".join([
    tile_panel("t-circ", 110, "круги",
               "".join(f'<circle cx="{60 + 95 * i}" cy="{75 + 100 * j}" r="40" fill="rgba(242,235,221,0.08)" />'
                       for i in range(3) for j in range(2))),
    tile_panel("t-sqr", 660, "квадраты",
               "".join(f'<rect x="{25 + 95 * i}" y="{35 + 100 * j}" width="80" height="80" fill="rgba(242,235,221,0.08)" />'
                       for i in range(3) for j in range(2))),
    bee,
    '        <div id="taxi" class="g sticker" style="left: 90px; top: 300px; font-size: 54px; white-space: nowrap;">товарищи-таксисты</div>',
    card("card-marx", "marx.jpg", "Карл Маркс", "«Капитал», 1867", "left"),
    '        <div id="p-eco" class="g pill" style="left: 110px; top: 1270px; font-size: 40px;">экономика ✓</div>',
    '        <div id="p-math" class="g pill" style="left: 560px; top: 1270px; font-size: 40px;">математика ✓</div>',
    pack_html,
    '        <div id="p-wax" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 1655px; background: none; border: none; font-size: 44px;">щели = <span style="color: var(--red);">лишний воск</span></div>',
    tile_panel("ti-tri", 45, "треугольники", "".join(tri)),
    tile_panel("ti-sq", 385, "квадраты", "".join(sq)),
    tile_panel("ti-hex", 725, "шестиугольники", "".join(hx)),
    '        <div id="st-best" class="g stamp" style="left: 220px; top: 230px; font-size: 80px; white-space: nowrap; color: #3BD16F; border-color: #3BD16F; background: rgba(12,12,14,0.55);">самый выгодный</div>',
    cmp_svg,
    '        <div id="p-7" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 1290px; background: none; border: none; font-size: 34px;">на <span style="color: #3BD16F;">7%</span> меньше стенок, чем у квадратов</div>',
    card("card-darwin", "darwin.jpg", "Чарльз Дарвин", "«Происхождение видов», 1859", "right"),
    '        <div id="quote" class="g paper" style="left: 110px; top: 1255px; width: 860px; text-align: center;"><div class="paper-text">«…абсолютно совершенны в экономии труда и воска»</div><div class="paper-sign">Чарльз Дарвин о сотах</div></div>',
    '        <div id="censor" class="g censor"><span>Цензура</span><b>18+</b></div>',
])

beats = f'''
      // ---------- хук: застройщики украдут идею ----------
      slam("#w-pik", {t(6.36)}, {{ fromScale: 1.6 }});
      flash({t(6.36)});
      enter("#w-lead", {t(6.72)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave(["#w-pik", "#w-lead"], {t(8.10)}, {{ y: -60 }});
      slam("#w-sam", {t(9.55)}, {{ fromScale: 1.5 }});
      leave("#w-sam", {t(10.25)}, {{ y: -60 }});
      slam("#q", {t(10.36)}, {{ fromScale: 1.6 }});
      leave("#q", {t(11.35)}, {{ y: -60 }});

      // ---------- соты шестиугольные: рисуются за головой и заливаются мёдом ----------
      tl.set("#comb", {{ opacity: 1 }}, {t(12.06)});
      tl.fromTo("#comb .hx", {{ strokeDashoffset: 1 }}, {{ strokeDashoffset: 0, duration: 0.35, ease: "power1.inOut", stagger: 0.012 }}, {t(12.06)});
      tl.to("#comb .hx", {{ fill: "rgba(245,184,46,0.78)", duration: 0.2, ease: "power1.out", stagger: {{ each: 0.008, from: "center" }} }}, {t(13.50)});
      leave("#comb", {t(14.70)}, {{ y: -60, scale: 1 }});

      // ---------- казалось бы, круги естественнее, квадраты проще ----------
      enter("#t-circ", {t(15.46)}, {{ fromX: -220, fromScale: 0.9, rot: -3 }});
      enter("#t-sqr", {t(17.26)}, {{ fromX: 220, fromScale: 0.9, rot: 3 }});
      leave(["#t-circ", "#t-sqr"], {t(18.70)}, {{ y: 80 }});

      // ---------- чёрно-жёлтые товарищи-таксисты ----------
      tl.fromTo("#bee", {{ opacity: 0, x: 420, y: -40, rotation: -8 }}, {{ opacity: 1, x: 0, y: 0, rotation: 0, duration: 0.6, ease: "power2.out" }}, {t(19.44)});
      tl.fromTo("#bee-wings", {{ scaleY: 1 }}, {{ scaleY: 0.5, svgOrigin: "150 100", duration: 0.06, ease: "sine.inOut", yoyo: true, repeat: 41 }}, {t(19.44)});
      tl.to("#bee", {{ y: 14, duration: 0.4, ease: "sine.inOut", yoyo: true, repeat: 3 }}, {t(20.10)});
      enter("#taxi", {t(20.18)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#taxi", {t(21.90)}, {{ y: -30, rot: -10 }});
      tl.to("#bee", {{ x: 520, y: -120, rotation: 12, opacity: 0, duration: 0.45, ease: "power2.in" }}, {t(21.95)});

      // ---------- читали Маркса: экономика и математика ----------
      card("#card-marx", {t(22.08)}, {t(25.40)}, "left");
      enter("#p-eco", {t(23.62)}, {{ fromX: -220, fromScale: 0.9, rot: -3 }});
      enter("#p-math", {t(24.32)}, {{ fromX: 220, fromScale: 0.9, rot: 3 }});
      leave(["#p-eco", "#p-math"], {t(25.40)}, {{ y: 60 }});

      // ---------- вплотную, без щелей: круги так не встанут ----------
      enter("#pack", {t(25.54)}, {{ fromY: 120, fromScale: 0.9, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#pack-g", {{ x: 0 }}, {{ x: 10, duration: 0.06, ease: "sine.inOut", yoyo: true, repeat: 5, immediateRender: false }}, {t(27.98)});
      tl.to("#pack-bg", {{ fill: "#F0352C", duration: 0.3, ease: "power2.out" }}, {t(29.62)});
      enter("#p-wax", {t(30.60)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave(["#pack", "#p-wax"], {t(31.50)}, {{ y: 80 }});

      // ---------- только три паркета ----------
      slam("#w-3", {t(34.84)}, {{ fromScale: 1.5 }});
      leave("#w-3", {t(36.05)}, {{ y: -60 }});
      enter("#ti-tri", {t(36.26)}, {{ fromY: 120, fromScale: 0.8, rot: -3 }});
      enter("#ti-sq", {t(37.10)}, {{ fromY: 120, fromScale: 0.8 }});
      enter("#ti-hex", {t(38.02)}, {{ fromY: 120, fromScale: 0.8, rot: 3 }});
      leave(["#ti-tri", "#ti-sq"], {t(39.34)}, {{ y: 80 }});
      tl.to("#ti-hex", {{ x: -340, scale: 1.12, rotation: 0, duration: 0.4, ease: "power3.inOut" }}, {t(39.50)});
      slam("#st-best", {t(40.50)}, {{ fromScale: 2.2, rot: -6, blur: 10 }});
      leave("#ti-hex", {t(41.00)}, {{ y: 80 }});
      leave("#st-best", {t(41.60)}, {{ scale: 0.6, y: 0, rot: -18 }});

      // ---------- при той же площади — самый короткий периметр ----------
      enter("#cmp", {t(42.36)}, {{ fromY: 120, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.to("#cmp .pl", {{ opacity: 1, duration: 0.2, stagger: 0.12 }}, {t(45.00)});
      tl.fromTo("#cmp-hex", {{ scale: 1 }}, {{ scale: 1.08, svgOrigin: "800 165", duration: 0.25, ease: "sine.inOut", yoyo: true, repeat: 1, immediateRender: false }}, {t(45.56)});
      leave("#cmp", {t(46.25)}, {{ y: 80 }});
      enter("#p-7", {t(47.90)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#p-7", {t(48.95)}, {{ y: 60 }});

      // ---------- Дарвин: совершенство экономии ----------
      card("#card-darwin", {t(49.22)}, {t(52.55)}, "right");
      doc("#quote", {t(50.46)}, {t(52.55)}, {{ fromRot: -5, rot: 1 }});
      slam("#censor", {t(53.04)}, {{ fromScale: 1.5, rot: -3 }});
      leave("#censor", {t(54.25)}, {{ scale: 0.6, y: 0, rot: 8 }});
'''
sounds = [
    audio("pik", "impact-bass-1", t(6.34), 0.40), audio("lead", "whoosh-short", t(6.70), 0.24),
    audio("sam", "impact-bass-1", t(9.53), 0.34), audio("q", "pop", t(10.34), 0.30),
    audio("comb", "sparkle", t(12.04), 0.26), audio("honey", "whoosh-short", t(13.48), 0.26),
    audio("circ", "pop", t(15.44), 0.30), audio("sqr", "pop", t(17.24), 0.30),
    audio("bee", "whoosh", t(19.40), 0.26), audio("taxi", "pop", t(20.16), 0.28),
    audio("marx", "whoosh-short", t(22.06), 0.28), audio("eco", "pop", t(23.60), 0.30), audio("math", "pop", t(24.30), 0.30),
    audio("pack", "whoosh", t(25.52), 0.24), audio("shake", "click-soft", t(27.96), 0.36),
    audio("gaps", "error", t(29.60), 0.22), audio("wax", "pop", t(30.58), 0.30),
    audio("three", "impact-bass-1", t(34.82), 0.36),
    audio("tri", "click", t(36.24), 0.36), audio("sq", "click", t(37.08), 0.36), audio("hex", "click", t(38.00), 0.36),
    audio("best", "impact-bass-1", t(40.48), 0.30), audio("cmp", "whoosh", t(42.34), 0.24),
    audio("per", "ping", t(44.98), 0.30), audio("seven", "pop", t(47.88), 0.30),
    audio("darwin", "whoosh-short", t(49.20), 0.28), audio("quote", "whoosh", t(50.44), 0.22),
    audio("censor", "glitch-3", t(53.04), 0.22, duration=0.9, fade_out=0.3),
]
fg = [(t(6.26), t(8.45)), (t(9.45), t(11.70)), (t(11.96), t(15.05)), (t(34.74), t(36.40))]
page = build_page("Почему соты шестиугольные", DUR, behind, front, beats, sounds, fg,
                  cta_at=t(57.00), cta_small="ЕГЭ на 80+ — переходи ко мне")
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

director = {
    "_note": "Соты. Время по дублю; раскладка — work/IMG_3303/page.py.",
    "punches": [[t(6.36), t(7.40), 1.18, 0.10], [t(13.50), t(14.50), 1.20, 0.10],
                [t(34.84), t(35.90), 1.18, 0.10], [t(53.04), t(53.80), 1.25, 0.05]],
    "text_fixes": tk.fixes({2: "ПИК", 13: "Самолёт", 37: "чёрно", 38: "-жёлтые", 59: "круги", 126: "ЕГЭ"}),
    "keep_case": ["ПИК", "ЖК", "Самолёт", "Карла", "Маркса", "Дарвин", "ЕГЭ"],
    "accent_words": ["шестиугольные", "воск", "воска", "периметр"],
    "hide_captions": [[t(52.80), t(53.75)], [t(56.90), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
