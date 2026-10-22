"""Страница графики IMG_5688 — лирик-ролик Насти (@oxpulc) в почерке IMG_5677 (проект «Настюха»).

21.10.2026, Валера: «смонтировать 5688 как 5677», «Настя уже подложила музыку, нам надо визуал подбить только»,
«определи, что у Насти за музыка играет, и подпиши так же — полный дубликат по смыслу и вайбу, но для Насти».
Трек — Макс Корж, «В темноте» (подсказал Валера; whisper слышал «путём ими» — в песне «путём иным»).

Что взято из IMG_5677 (разбор кадров по 0.25 с):
  текст песни широким жирным гротеском печатается по буквам на своём слове, строки копятся столбиком над головой,
  цвета — красный, розовый, жёлтый, белый, чёрный; блок уходит на следующей фразе;
  ник с иконкой Instagram справа сверху и под ним мелко «Исполнитель · Трек», потом ник уезжает влево вниз;
  белые штрихи-лучи вокруг головы;
  огромное красное слово, пролетающее над головой; линза-круг на чёрном с белыми «кипящими» каракулями;
  растровое слово со свечением за «Огоньки»; ч/б фото в белой рамке поверх кадра (кадр не уменьшаем — Валера 21.10); наезд-рывок;
  финальные слова по одному по центру; аутро — кадр гаснет, иконка Instagram переливается, ник.
Звук не трогаем: трек Насти как есть (project.json → keep_audio), ни музыки, ни тихих звуков монтажа.
Раскадровка и почему — work/IMG_5688/plan.md.
"""
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, build_page  # noqa: E402

STEM = "IMG_5688"
tk = Take(STEM)
W = tk.words
DUR = tk.duration
END = round(DUR, 2)
HANDLE, CREDIT = "@OXPULC", "Макс Корж · В темноте"

RED, PINK, YELLOW, WHITE, INK = "#E8291C", "#F59BBB", "#F6D64A", "#F7F4EE", "#191919"
BIG, MID, SMALL = 86, 58, 40
L = 104                # левый край строк: Instagram режет бок до x 102 (formats.GREY_ZONES)
# строки — в полосе y 262–540 над головой: выше — статус-бар и вкладки площадок, ниже — макушка (до y≈490 на 18–19.5 с)


# линза-тоннель («Выхода нет»): круг целиком в кадре, лицо внутри (на 13.8–16 с лицо y 760–880, x 445–656)
LX, LY, LR = 540, 990, 462
# «в темноте»: ч/б фото в белой рамке поверх полного кадра, справа — она уходит по тропинке в центре (x 470–600)
PHOTO = (640, 430, 370, 650)                   # left, top, width, height (рамка 10 px)


def at(i: int) -> float:
    return round(W[i]["start"], 3)


def till(i: int) -> float:
    return round(W[i]["end"], 3)


css = f'''      @font-face {{ font-family: "Unbounded"; src: url("assets/fonts/Unbounded-ExtraBold.ttf"); font-weight: 800; }}
      /* строки песни: широкий жирный гротеск как в 5677, печатается по буквам */
      .ln {{ font-family: "Unbounded"; font-weight: 800; line-height: 1; white-space: nowrap; letter-spacing: -0.01em;
             text-shadow: 0 3px 12px rgba(0,0,0,0.28); }}
      .ln .ch {{ opacity: 0; }}
      .glow {{ text-shadow: 0 0 18px rgba(246,214,74,0.85), 0 0 46px rgba(246,214,74,0.55); }}
      .tone {{ font-family: "Unbounded"; font-weight: 800; line-height: 1; white-space: nowrap; color: transparent;
               background: radial-gradient(circle, rgba(246,214,74,0.75) 34%, transparent 37%) 0 0 / 13px 13px;
               -webkit-background-clip: text; background-clip: text; }}
      #slab-win {{ left: 0; top: 500px; width: 1080px; height: 190px; overflow: hidden; }}
      #slab {{ position: absolute; left: 0; top: 0; font-family: "Unbounded"; font-weight: 800; font-size: 180px; line-height: 1;
               white-space: nowrap; color: {RED}; }}
      /* ник с иконкой: справа сверху с подписью трека, потом слева на груди */
      .ig {{ text-align: center; font-family: "Manrope"; font-weight: 800; color: {WHITE};
             text-shadow: 0 2px 8px rgba(0,0,0,0.45); }}
      .ig svg {{ display: block; margin: 0 auto; }}
      #ig-a {{ left: 760px; top: 470px; width: 212px; font-size: 21px; letter-spacing: 0.04em; }}
      #ig-a .credit {{ margin-top: 10px; font-size: 17px; font-weight: 800; letter-spacing: 0; color: rgba(247,244,238,0.78); }}
      #ig-b {{ left: 106px; top: 1060px; width: 150px; font-size: 19px; letter-spacing: 0.04em; }}
      #ig-c {{ left: 340px; top: 1010px; width: 400px; font-size: 34px; letter-spacing: 0.05em; }}
      #ig-c .grad {{ position: absolute; left: 140px; top: 0; opacity: 0; }}
      /* линза-тоннель: чёрное вокруг круга */
      #lens {{ left: 0; top: 0; width: 1080px; height: 1920px;
               background: radial-gradient(circle at {LX}px {LY}px, rgba(0,0,0,0) 0, rgba(0,0,0,0) {LR - 150}px,
                                           rgba(0,0,0,0.38) {LR - 12}px, #060606 {LR}px, #060606 100%); }}
      #doodles {{ left: 0; top: 0; width: 1080px; height: 1920px; }}
      #rays {{ left: 0; top: 0; width: 1080px; height: 1920px; }}
      /* ч/б фото в белой рамке поверх кадра */
      #photo {{ left: {PHOTO[0]}px; top: {PHOTO[1]}px; width: {PHOTO[2]}px; height: {PHOTO[3]}px; background: #fff; padding: 10px;
                box-shadow: 0 24px 60px rgba(0,0,0,0.6); overflow: hidden; }}
      #photo img {{ display: block; width: {PHOTO[2] - 20}px; height: {PHOTO[3] - 20}px; object-fit: cover; }}
      #dim {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; background: #050505; opacity: 0; }}
'''

# ---------------------------------------------------------------- блоки песни
# строка: (номер слова, на котором печатается, текст, размер, цвет, top, left|"c", класс)
C = "c"
BLOCKS = [
    ("b1", 4, [(0, "ЛЕТЕТЬ", BIG, RED, 268, L, ""), (1, "КУДА НИ", BIG, RED, 362, L, ""),
               (3, "ПОПАДЯ", BIG, WHITE, 456, L, "")]),
    ("b2", 8, [(4, "Или идти", MID, WHITE, 282, C, ""), (6, "Путём иным", BIG - 6, PINK, 352, C, "")]),
    ("b3", 12, [(8, "Заполнять", MID, WHITE, 272, L, ""), (9, "Вагоны", BIG, PINK, 340, L, ""),
                (10, "Под землёй", SMALL + 4, WHITE, 436, L + 4, "")]),
    ("b4", None, [(12, "Или", SMALL, WHITE, 272, C, ""), (13, "Покинуть", MID, WHITE, 320, C, ""),
                  (14, "Города", BIG - 6, RED, 388, C, "")]),
    ("b5", 19, [(15, "Тебе,", BIG, RED, 268, L, ""), (16, "Конечно,", SMALL, PINK, 362, L + 4, ""),
                (17, "Будут", MID - 2, WHITE, 410, L, ""), (18, "Говорить", MID - 2, WHITE, 474, L, "")]),
    ("b6", 25, [(19, "Выхода нет,", BIG - 8, RED, 268, C, ""),
                (21, "Но выход", MID - 4, WHITE, 362, C, ""), (23, "Есть всегда", MID - 4, WHITE, 424, C, "")]),
    ("b7", 27, [(25, "в", SMALL, WHITE, 282, L + 4, ""), (26, "Темноте", BIG + 10, WHITE, 330, L, "")]),
    ("b8", 29, [(27, "Летай,", BIG, INK, 270, C, ""), (28, "Летай", BIG + 14, YELLOW, 366, C, "glow")]),
    ("b9", 33, [(29, "Со мной", MID - 2, WHITE, 290, L, ""), (31, "В темноте", MID - 2, PINK, 362, L, "")]),
    ("b10", 35, [(33, "ЛЕТАЙ,", BIG + 14, RED, 300, C, ""), (34, "ЛЕТАЙ", BIG + 44, PINK, 420, C, "")]),
    ("b11", 37, [(35, "Со мной", BIG + 14, YELLOW, 560, C, "")]),
    ("b12", None, [(37, "В темноте", BIG + 6, WHITE, 560, C, "")]),
]
B4_OUT = 10.6          # «Города» висит в проигрыше, потом кадр чистый до «Тебе»
B12_OUT = None         # финальная строка остаётся в аутро до конца


def line_html(bid: str, k: int, text: str, size: int, color: str, top: int, left, cls: str) -> str:
    chars = "".join(f'<span class="ch">{c if c != " " else "&nbsp;"}</span>' for c in text)
    pos = "left: 0; width: 1080px; text-align: center;" if left == C else f"left: {left}px;"
    return (f'        <div id="{bid}-{k}" class="g ln {cls}" style="{pos} top: {top}px; font-size: {size}px; '
            f'color: {color};">{chars}</div>')


def type_js(bid: str, k: int, text: str, t0: float, span: float) -> str:
    """Печать по буквам: строка видна с t0, буквы появляются за span секунд (не дольше 0.5 с)."""
    n = len(text)
    step = min(span, 0.5) / max(n, 1)
    t0 = max(t0, 0.04)                 # set на нуле покадровый рендер не видит в первом кадре (verify_page)
    out = [f'      tl.set("#{bid}-{k}", {{ opacity: 1 }}, {t0:.3f});']
    out += [f'      tl.set("#{bid}-{k} .ch:nth-child({j + 1})", {{ opacity: 1 }}, {t0 + j * step:.3f});' for j in range(n)]
    return "\n".join(out)


front_lines, lines_js = [], []
for bid, nxt, lines in BLOCKS:
    for k, (i, text, size, color, top, left, cls) in enumerate(lines):
        front_lines.append(line_html(bid, k, text, size, color, top, left, cls))
        # печатается за время своего слова (или слов строки): от начала до начала следующей строки
        nxt_line = lines[k + 1][0] if k + 1 < len(lines) else i + 1
        span = (at(nxt_line) if nxt_line < len(W) else till(i)) - at(i)
        lines_js.append(type_js(bid, k, text, at(i), max(span, 0.2)))
    out = at(nxt) - 0.12 if nxt is not None else (B4_OUT if bid == "b4" else None)
    if out is not None:
        sel = ", ".join(f"#{bid}-{k}" for k in range(len(lines)))
        lines_js.append(f'      tl.to("{sel}", {{ opacity: 0, y: -18, filter: BLUR(8), duration: 0.12, ease: "power1.in" }}, {out:.3f});')

# ---------------------------------------------------------------- ник и трек
IG = ('<svg width="{s}" height="{s}" viewBox="0 0 48 48"><rect x="4" y="4" width="40" height="40" rx="12" fill="none" '
      'stroke="{c}" stroke-width="4.2" /><circle cx="24" cy="24" r="9.2" fill="none" stroke="{c}" stroke-width="4.2" />'
      '<circle cx="35.2" cy="12.8" r="2.7" fill="{c}" /></svg>')
IG_GRAD = ('<svg class="grad" width="120" height="120" viewBox="0 0 48 48"><defs><linearGradient id="igg" x1="0" y1="1" x2="1" y2="0">'
           '<stop offset="0" stop-color="#FEDA75" /><stop offset="0.3" stop-color="#FA7E1E" /><stop offset="0.6" stop-color="#D62976" />'
           '<stop offset="1" stop-color="#4F5BD5" /></linearGradient></defs><rect x="4" y="4" width="40" height="40" rx="12" '
           'fill="none" stroke="url(#igg)" stroke-width="4.2" /><circle cx="24" cy="24" r="9.2" fill="none" stroke="url(#igg)" '
           'stroke-width="4.2" /><circle cx="35.2" cy="12.8" r="2.7" fill="url(#igg)" /></svg>')
ig_html = f'''        <div id="ig-a" class="g ig" data-hold="ник и трек в начале ролика — как в 5677" data-safe="ник автора сбоку, лицо не закрывает">
          {IG.format(s=46, c=WHITE)}<div style="margin-top: 8px;">{HANDLE}</div><div class="credit">{CREDIT}</div>
        </div>
        <div id="ig-b" class="g ig" data-hold="ник автора весь ролик — как в 5677" data-safe="ник автора мелко на куртке, лицо не закрывает">
          {IG.format(s=38, c=WHITE)}<div style="margin-top: 6px;">{HANDLE}</div>
        </div>
        <div id="ig-c" class="g ig" data-hold="аутро: иконка и ник держатся до конца — как в 5677" data-safe="аутро на погасшем кадре">
          <div style="position: relative; width: 400px; height: 120px;">
            <div style="position: absolute; left: 140px; top: 0;">{IG.format(s=120, c=WHITE)}</div>{IG_GRAD}
          </div>
          <div id="ig-c-name" style="margin-top: 16px;">{HANDLE}</div>
        </div>'''

# ---------------------------------------------------------------- лучи вокруг головы («путём иным»)
rnd = random.Random(5688)
CX, CY = 440, 830          # среднее лицо на 2.6–5.1 с (aroll.faces.json); лицо ходит по x 270–600
rays = []
for k, deg in enumerate([52, 82, 112, 140, 168, 196, 224, 254, 284, 308]):     # сверху, где текст, лучей нет
    a = math.radians(deg - 90)
    r1, r2 = 345 + rnd.randint(0, 30), 480 + rnd.randint(0, 60)
    bend = rnd.choice([-1, 1]) * rnd.randint(18, 40)
    x1, y1 = CX + r1 * math.cos(a), CY + r1 * math.sin(a)
    x2, y2 = CX + r2 * math.cos(a), CY + r2 * math.sin(a)
    mx, my = (x1 + x2) / 2 - bend * math.sin(a), (y1 + y2) / 2 + bend * math.cos(a)
    rays.append(f'<path class="ray" d="M {x1:.0f} {y1:.0f} Q {mx:.0f} {my:.0f} {x2:.0f} {y2:.0f}" stroke="{WHITE}" '
                f'stroke-width="15" stroke-linecap="round" fill="none" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />')
rays_html = (f'        <svg id="rays" class="g" viewBox="0 0 1080 1920" data-safe="штрихи вокруг головы, лицо не закрывают">\n'
             + "".join(f"          {r}\n" for r in rays) + "        </svg>")


# ---------------------------------------------------------------- кольца от руки по краю линзы («кипят» по 0.2 с)
def ring(r: float, wob: float, over: float) -> str:
    """Неровный круг от руки вокруг линзы: радиус плавает, конец заходит на начало (over — доля оборота сверх круга)."""
    phases = [rnd.uniform(0, 2 * math.pi) for _ in range(3)]
    a0 = rnd.uniform(0, 2 * math.pi)
    n = 72
    pts = []
    for j in range(n + 1):
        a = a0 + 2 * math.pi * (1 + over) * j / n
        rr = r * (1 + wob * (math.sin(2 * a + phases[0]) + 0.6 * math.sin(3 * a + phases[1]) + 0.3 * math.sin(5 * a + phases[2])) / 1.9)
        pts.append((LX + rr * math.cos(a), LY + rr * math.sin(a)))
    d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        d += f" Q {x0:.1f} {y0:.1f} {(x0 + x1) / 2:.1f} {(y0 + y1) / 2:.1f}"
    return d


ring_sets = []
for k in range(3):
    paths = [f'<path class="rg" d="{ring(LR + 6 + rnd.randint(-4, 6), 0.022, 0.12)}" stroke="{WHITE}" stroke-width="13" '
             f'stroke-linecap="round" fill="none" pathLength="1" stroke-dasharray="1" stroke-dashoffset="0" />',
             f'<path class="rg" d="{ring(LR + 30 + rnd.randint(-4, 8), 0.03, 0.06)}" stroke="{WHITE}" stroke-width="8" '
             f'stroke-linecap="round" fill="none" pathLength="1" stroke-dasharray="1" stroke-dashoffset="0" opacity="0.85" />']
    ring_sets.append(f'          <g id="dd{k}" style="opacity: 0;">' + "".join(paths) + "</g>")
doodles_html = ('        <svg id="doodles" class="g" viewBox="0 0 1080 1920" data-safe="кольца по краю линзы, лицо в центре круга">\n'
                + "\n".join(ring_sets) + "\n        </svg>")

# ---------------------------------------------------------------- времена
T_LENS_IN, T_LENS_OUT = at(19) - 0.05, at(25) - 0.02          # «Выхода нет…» — до «В темноте»
T_PIP_IN, T_PIP_OUT = at(31), at(33) - 0.03                  # «в темноте» — фото поверх до «Летай»
T_SLAB = at(14)                                              # «Города»
T_DIM = at(37) + 0.3                                         # финальное «в темноте» — кадр гаснет
T_IG_B = at(8) - 0.1                                         # ник переезжает влево, когда пошёл второй куплет

behind = "\n".join([
    '        <div id="lens" class="g" data-safe="линза-тоннель: лицо в центре круга"></div>',
    doodles_html, rays_html,
])
front = "\n".join([
    '        <div id="dim"></div>',
    '        <div id="tone" class="g tone" style="left: 0; width: 1080px; text-align: center; top: 290px; font-size: 176px;" '
    'data-safe="растровое слово над головой">ЛЕТАЙ</div>',
    '        <div id="slab-win" class="g" data-safe="красное слово пролетает над головой"><div id="slab">ГОРОДА ГОРОДА</div></div>',
    '        <div id="photo" class="g" data-safe="ч/б фото справа от неё, лицо не закрывает"><img src="assets/img/still_bw.jpg" alt="" /></div>',
    *front_lines, ig_html,
])

doodle_js = []
k, tt = 0, T_LENS_IN + 0.32                    # первые 0.3 с кольцо рисуется, дальше кипит
while tt < T_LENS_OUT - 0.2:
    doodle_js.append(f'      tl.set("#dd{k % 3}", {{ opacity: 1 }}, {tt:.3f}); tl.set("#dd{(k + 2) % 3}", {{ opacity: 0 }}, {tt:.3f});')
    k, tt = k + 1, tt + 0.2
doodle_js = "\n".join(doodle_js)

ray_boil = "\n".join(f'      tl.set("#rays", {{ rotation: {(-1.6 if j % 2 else 1.6)}, transformOrigin: "{CX}px {CY}px" }}, {at(5) + 0.2 * j:.3f});'
                     for j in range(int((at(8) - at(5)) / 0.2)))

beats = f'''
      // ---------- ник и трек: справа сверху, потом слева на груди ----------
      tl.fromTo("#ig-a", {{ opacity: 0, y: 10 }}, {{ opacity: 1, y: 0, duration: 0.25, ease: "power2.out" }}, 0.1);
      tl.to("#ig-a", {{ opacity: 0, x: -30, filter: BLUR(6), duration: 0.18, ease: "power1.in" }}, {T_IG_B - 0.2:.2f});
      tl.fromTo("#ig-b", {{ opacity: 0, x: -20 }}, {{ opacity: 0.92, x: 0, duration: 0.25, ease: "power2.out" }}, {T_IG_B:.2f});
      tl.to("#ig-b", {{ opacity: 0, duration: 0.15 }}, {T_DIM - 0.1:.2f});

      // ---------- строки песни: печать по буквам ----------
{chr(10).join(lines_js)}

      // ---------- лучи вокруг головы: «путём иным» ----------
      tl.set("#rays", {{ opacity: 1 }}, {at(5):.2f});
      tl.fromTo("#rays .ray", {{ strokeDashoffset: 1 }}, {{ strokeDashoffset: 0, duration: 0.22, ease: "power2.out", stagger: 0.05 }}, {at(5):.2f});
{ray_boil}
      tl.to("#rays", {{ opacity: 0, scale: 1.15, filter: BLUR(10), duration: 0.2, ease: "power1.in" }}, {at(8) - 0.25:.2f});

      // ---------- «Города»: огромное красное слово пролетает над головой ----------
      tl.set("#slab-win", {{ opacity: 1 }}, {T_SLAB - 0.05:.2f});
      tl.fromTo("#slab", {{ x: 1100 }}, {{ x: -2100, duration: 1.1, ease: "power1.inOut", immediateRender: false }}, {T_SLAB - 0.05:.2f});
      tl.set("#slab-win", {{ opacity: 0 }}, {T_SLAB + 1.08:.2f});

      // ---------- «Выхода нет»: линза-тоннель на чёрном, каракули по краю ----------
      tl.set(["#lens", "#doodles"], {{ opacity: 1 }}, {T_LENS_IN:.3f});
      tl.fromTo(["#lens", "#doodles"], {{ scale: 2.2, transformOrigin: "{LX}px {LY}px" }}, {{ scale: 1, duration: 0.3, ease: "power3.out", immediateRender: false }}, {T_LENS_IN:.3f});
      tl.set("#dd0", {{ opacity: 1 }}, {T_LENS_IN:.3f});
      tl.fromTo("#dd0 .rg", {{ strokeDashoffset: 1 }}, {{ strokeDashoffset: 0, duration: 0.32, ease: "power2.out", stagger: 0.06, immediateRender: false }}, {T_LENS_IN + 0.04:.3f});
      tl.fromTo("#aroll", {{ scale: 1, transformOrigin: "{LX}px {LY}px" }}, {{ scale: 1.12, duration: 0.3, ease: "power3.out", immediateRender: false }}, {T_LENS_IN:.3f});
      tl.to("#aroll", {{ scale: 1.17, duration: {T_LENS_OUT - T_LENS_IN - 0.5:.2f}, ease: "none" }}, {T_LENS_IN + 0.3:.3f});
{doodle_js}
      // выход: линза раскрывается за край кадра, кадр возвращается к полному
      tl.to(["#lens", "#doodles"], {{ scale: 2.6, duration: 0.2, ease: "power2.in" }}, {T_LENS_OUT - 0.2:.3f});
      tl.to("#aroll", {{ scale: 1, duration: 0.2, ease: "power2.in" }}, {T_LENS_OUT - 0.2:.3f});
      tl.set(["#lens", "#doodles"], {{ opacity: 0 }}, {T_LENS_OUT:.3f});

      // ---------- «Летай, летай»: растровое слово за строками ----------
      tl.fromTo("#tone", {{ opacity: 0, scale: 0.9 }}, {{ opacity: 1, scale: 1, duration: 0.3, ease: "power2.out" }}, {at(28):.2f});
      tl.to("#tone", {{ x: -40, duration: {at(29) - at(28):.2f}, ease: "none" }}, {at(28):.2f});
      tl.to("#tone", {{ opacity: 0, filter: BLUR(10), duration: 0.12, ease: "power1.in" }}, {at(29) - 0.12:.2f});

      // ---------- «в темноте»: ч/б фото поверх полного кадра ----------
      tl.set("#photo", {{ opacity: 1 }}, {T_PIP_IN + 0.1:.3f});
      tl.fromTo("#photo", {{ x: 520, y: 60, rotation: 14 }}, {{ x: 0, y: 0, rotation: 3, duration: 0.42, ease: "power3.out", immediateRender: false }}, {T_PIP_IN + 0.1:.3f});
      tl.fromTo("#photo img", {{ scale: 1.0 }}, {{ scale: 1.06, duration: {T_PIP_OUT - T_PIP_IN:.2f}, ease: "none", immediateRender: false }}, {T_PIP_IN + 0.1:.3f});
      tl.to("#photo", {{ x: 520, y: 40, rotation: 12, duration: 0.24, ease: "power2.in" }}, {T_PIP_OUT - 0.4:.3f});
      tl.set("#photo", {{ opacity: 0 }}, {T_PIP_OUT - 0.16:.3f});

      // ---------- финал: кадр гаснет «в темноте», иконка переливается, ник ----------
      tl.to("#dim", {{ opacity: 0.74, duration: 0.6, ease: "power1.inOut" }}, {T_DIM:.2f});
      tl.fromTo("#ig-c", {{ opacity: 0, scale: 0.7, y: 20 }}, {{ opacity: 1, scale: 1, y: 0, duration: 0.3, ease: "back.out(1.8)" }}, {T_DIM + 0.35:.2f});
      tl.to("#ig-c .grad", {{ opacity: 1, duration: 0.3, ease: "none" }}, {T_DIM + 0.65:.2f});
      tl.to("#ig-c .grad", {{ opacity: 0, duration: 0.3, ease: "none" }}, {T_DIM + 1.15:.2f});
'''

page = build_page("Летай со мной", DUR, behind, front, beats, [], [], cta_at=END,
                  extra_css=css, fmt=tk.fmt, captions=tk.captions, cutout=False, cta=False)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

director = {
    "_note": "Лирик-ролик Насти в почерке IMG_5677; раскладка — work/IMG_5688/page.py, план — plan.md. Субтитров нет "
             "(бриф: captions.mode none) — вместо них строки песни на странице.",
    # наезд-рывок на втором «летай» в общем плане (как наезд 5677 на 25.3 с)
    "punches": [[round(at(34) - 0.05, 2), round(at(35) - 0.1, 2), 1.14, 0.06, 0.2]],
    "text_fixes": {"7": "иным"},
    "keep_case": [],
    "accent_words": [],
    "hide_captions": [],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", END)
