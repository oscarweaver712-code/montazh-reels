"""Страница графики IMG_3292 v3: почему «арабские» цифры на самом деле узбекские.

v3 (19.10.2026) — монтаж с нуля после разноса v2 («как будто анализ видео вообще не проводился, и музыки нет»).
Решения v2 — work/IMG_3292/_архив-v2-17.10/ (не образец). План — plan.md, раскадровка от сетки дубля (sheets/take.jpg):
банка «Добрый кола» в левой руке у груди весь ролик, правая рука считает на «1, 2, 3, 4, 5» и «X, V, I, I, I» —
цифры и буквы выскакивают под счёт; улыбка на «гениально» — штамп; на «вебинары, курс» палец вверх — бейдж LIVE.
Стиль — IMG_3303 v5 (rules.md п.14): Oswald крем/красный, подвод Manrope, Cormorant; схемы на груди под линией
субтитров; 2 ИИ-видео Flow (п.15: топ-места — Индия и Хорезм); тихие звуки монтажа + свой лоу-фай (п.9).

Время: tk.t(секунда ИСХОДНИКА). После склейки (дубль 31.57) исходник = дубль + 30.37.

Проверено: цифры 0–9 — индийского происхождения (брахми → гупта); Мухаммад аль-Хорезми, IX век, Багдад, трактат об
индийском счёте (~825); латинский перевод XII века «Algoritmi de numero Indorum»; арабы на Востоке зовут свои цифры
«индийскими» (أرقام هندية); в России арабские цифры при Петре I (с ~1700, «Арифметика» Магницкого 1703); до того
кириллические цифры с титлом: А=1, В=2, Г=3, Д=4, Е=5 (буквы Б нет); XVIII = 18; Хорезм — низовья Амударьи, сегодня
Хорезмская область Узбекистана (и север Туркменистана).
Картинки: марка «Почта СССР 1983, Мухаммед аль-Хорезми» (знак почтовой оплаты — PD), Пётр I — П. Деларош, 1838 (PD).
Футажи — Google Flow (Omni 1.1 Flash), первые кадры GPT: footage/*.md.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, background_music, build_page, footage, slides, soft_track  # noqa: E402

STEM = "IMG_3292"
VARIANT = globals().get("VARIANT")
tk = Take(STEM, VARIANT)
t = tk.t
DUR = tk.duration
for name in ("khwarizmi_stamp.jpg", "peter.jpg"):
    if not (ROOT / f"work/{STEM}/downloads/{name}").exists():
        sys.exit(f"✗ нет downloads/{name}")

HEAD = 262            # крупное слово за головой: верх строки (ниже вкладок TikTok 260)
SCHEME = 1240         # схемы — под линией субтитров (≈1150)
CX = 615              # схемы — колонкой справа от банки (банка в левой руке у груди, x ≈ 40–380) и левее кнопок (834)
COLW = 430            # ширина колонки: 400–830
RED, CREAM = "#F0352C", "#F2EBDD"
SHADOW = "0 3px 8px rgba(0,0,0,0.65), 0 14px 46px rgba(0,0,0,0.55)"
DRAW = 'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"'
SAFE = 'data-safe="лицо и банка важнее серой зоны: схема на груди ниже подбородка (Валера, 12.10)"'

css = f'''      @font-face {{ font-family: "Geeza"; src: local("Geeza Pro Bold"), local("GeezaPro-Bold"); font-weight: 700; }}
      .tx {{ left: 0; width: 1080px; text-align: center; white-space: nowrap; }}
      .tx-lead {{ font-family: "Manrope"; font-weight: 800; font-size: 36px; letter-spacing: 0.24em; text-transform: uppercase;
                 color: var(--cream); text-shadow: {SHADOW}; }}
      .tx-big {{ font-family: "Oswald"; font-weight: 700; text-transform: uppercase; line-height: 0.9; letter-spacing: -0.01em;
                color: var(--cream); text-shadow: {SHADOW}; }}
      .tx-q {{ font-family: "Cormorant"; font-style: italic; font-weight: 700; color: var(--cream); text-shadow: {SHADOW}; }}
      .tx span, .row span {{ display: inline-block; }}
      .row {{ left: {CX - COLW // 2}px; width: {COLW}px; text-align: center; white-space: nowrap; }}
      [data-col] {{ left: {CX - COLW // 2}px !important; width: {COLW}px !important; }}
      .dg {{ font-family: "Oswald"; font-weight: 700; color: var(--cream); text-shadow: {SHADOW}; line-height: 1; margin: 0 6px; }}
      .ar {{ font-family: "Geeza"; font-weight: 700; color: var(--cream); text-shadow: {SHADOW}; line-height: 1.1; margin: 0 8px; }}
      .chest-svg {{ position: absolute; left: 0; top: 0; overflow: visible; filter: drop-shadow(0 8px 22px rgba(0,0,0,0.6)); }}
      .lbl {{ font-family: "Manrope"; font-weight: 800; font-size: 24px; letter-spacing: 0.1em; text-transform: uppercase; fill: {CREAM}; }}
      .lat {{ font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 32px; fill: {CREAM}; }}
      .cy {{ font-family: "Cormorant"; font-weight: 700; font-size: 120px; fill: {CREAM}; }}
      .cyn {{ font-family: "Manrope"; font-weight: 800; font-size: 40px; fill: {CREAM}; }}
      .cta {{ background: none; border: none; box-shadow: none; padding: 0; }}
      .cta-big {{ font-size: 112px; text-shadow: {SHADOW}; }}
      .cta-small {{ text-shadow: {SHADOW}; }}
      #book {{ left: {CX - COLW // 2}px; width: {COLW}px; top: {SCHEME}px; text-align: center; font-size: 50px; line-height: 1.05; }}
'''


def lead(lid, text, top, color=CREAM, extra=""):
    return f'        <div id="{lid}" class="g tx tx-lead" {extra} style="top: {top}px; color: {color};">{text}</div>'


def big(bid, inner, top, size, color=CREAM, extra=""):
    return f'        <div id="{bid}" class="g tx tx-big" {extra} style="top: {top}px; font-size: {size}px; color: {color};">{inner}</div>'


def stamp(sid, text, top, size=120, rot=-4, extra=""):
    return (f'        <div id="{sid}" class="g tx" {extra} style="top: {top}px; left: {CX - 540}px;">'
            f'<span class="stamp" style="font-size: {size}px; display: inline-block; transform: rotate({rot}deg);">{text}</span></div>')


def chest(cid, height, inner, width=COLW):
    left = CX - width // 2
    return (f'        <div id="{cid}" class="g" {SAFE} style="left: {left}px; top: {SCHEME}px; width: {width}px; height: {height}px;">'
            f'<svg class="chest-svg" viewBox="0 0 {width} {height}" style="width: {width}px; height: {height}px;">{inner}</svg></div>')


# ---------- схемы ----------
# 4.6–10.9: 1 2 3 4 5 под счёт пальцев → подпись АРАБСКИЕ → зачёркнута на «не арабы»
digits = (f'        <div id="d15" class="g row" {SAFE} style="top: {SCHEME - 10}px;">'
          + "".join(f'<span id="d15-{i}" class="dg" style="font-size: 130px; opacity: 0;">{n}</span>' for i, n in enumerate("12345"))
          + '</div>')
arab_lbl = (f'        <div id="d15-lbl" class="g row" {SAFE} style="top: {SCHEME + 130}px;">'
            f'<span class="dg" style="font-size: 66px; color: {CREAM}; position: relative;">«АРАБСКИЕ»'
            f'<svg viewBox="0 0 100 10" preserveAspectRatio="none" style="position: absolute; left: -4%; top: 38%; width: 108%; height: 22px; overflow: visible;">'
            f'<path id="d15-x" d="M 0 6 L 100 3" stroke="{RED}" stroke-width="9" vector-effect="non-scaling-stroke" fill="none" {DRAW} /></svg></span></div>')

# 20.0–22.7: путь книги — Индия → Багдад → латынь XII века
route = chest("rt", 250, inner=
              f'<path id="rt-l1" d="M 55 70 L 215 70" stroke="{CREAM}" stroke-width="8" stroke-linecap="round" fill="none" {DRAW} />'
              f'<path id="rt-l2" d="M 215 70 L 375 70" stroke="{RED}" stroke-width="8" stroke-linecap="round" fill="none" {DRAW} />'
              + "".join(f'<g id="rt-n{i}" opacity="0"><circle cx="{x}" cy="70" r="20" fill="{c}" />'
                        f'<text class="lbl" x="{x}" y="132" text-anchor="middle">{lb}</text></g>'
                        for i, (x, c, lb) in enumerate(((55, CREAM, "ИНДИЯ"), (215, CREAM, "БАГДАД"),
                                                        (375, RED, "XII ВЕК"))))
              + '<text id="rt-lat" class="lat" x="215" y="190" text-anchor="middle" opacity="0">Algoritmi de numero Indorum</text>')

# 22.7–25.2: 2026 против MMXXVI
year = (f'        <div id="yr" class="g row" {SAFE} style="top: {SCHEME - 10}px;"><span class="dg" style="font-size: 140px;">2026</span></div>\n'
        f'        <div id="yr-rom" class="g row" {SAFE} style="top: {SCHEME + 140}px;">'
        f'<span class="tx-q" style="font-size: 78px; color: {RED};">= MMXXVI</span></div>')

# 25.3–29.15: арабские цифры у самих арабов — и они «индийские»
arabic = (f'        <div id="ar" class="g row" {SAFE} style="top: {SCHEME - 30}px; direction: ltr;">'
          + "".join(f'<span id="ar-{i}" class="ar" style="font-size: 120px; opacity: 0;">{c}</span>' for i, c in enumerate("١٢٣٤٥"))
          + '</div>\n'
          f'        <div id="ar-lat" class="g row" {SAFE} style="top: {SCHEME + 140}px;">'
          + "".join(f'<span class="dg" style="font-size: 48px; margin: 0 22px; color: rgba(242,235,221,0.7);">{n}</span>' for n in "12345")
          + '</div>')

# 32.75–37.1: на Руси — буквы с титлом
cyr_letters = "АВГДЕ"
cyr = chest("cy", 270,
            "".join(f'<g id="cy-{i}" opacity="0"><text class="cy" x="{55 + 80 * i}" y="160" text-anchor="middle">{ch}</text></g>'
                    for i, ch in enumerate(cyr_letters))
            + "".join(f'<path class="cy-t" id="cy-t{i}" d="M {33 + 80 * i} 52 Q {44 + 80 * i} 30 {55 + 80 * i} 46 T {77 + 80 * i} 40" '
                      f'stroke="{RED}" stroke-width="8" stroke-linecap="round" fill="none" {DRAW} />' for i in range(5))
            + "".join(f'<text class="cyn cy-n" x="{55 + 80 * i}" y="235" text-anchor="middle" opacity="0">{i + 1}</text>' for i in range(5)))

# 41.3–43.75: римский счёт X V I I I = 18
roman = (f'        <div id="rm" class="g row" {SAFE} style="top: {SCHEME - 10}px;">'
         + "".join(f'<span id="rm-{i}" class="dg" style="font-size: 130px; opacity: 0;">{c}</span>' for i, c in enumerate("XVIII"))
         + f'</div>\n        <div id="rm-eq" class="g row" {SAFE} style="top: {SCHEME + 140}px;">'
         f'<span class="dg" style="font-size: 84px; color: {RED};">= 18</span></div>')

# ---------- перебивки Flow (п.15): без человека поверх, в behind ----------
IN_A, OUT_A = t(11.0), t(13.45)
IN_B, OUT_B = t(78.27), t(80.77)
f_india = footage("ft-india", STEM, "a_india", IN_A, round(OUT_A - IN_A, 2))
f_khor = footage("ft-khor", STEM, "b_khorezm", IN_B, round(OUT_B - IN_B, 2))
# портреты — полноэкранной серией (карточка в углу задевала лицо: камера держит его крупно); Пётр уходит ровно на
# склейке — выход перебивки и прячет рез
S = tk.splices[0]                   # склейка после «Пётр I.» (31.57 дубля)
IN_K, IN_P = t(14.24), t(29.60)
s_khw = slides("sl-khw", ["khwarizmi_stamp.jpg"], IN_K, [round(t(16.40) - IN_K, 2)], push=1.12)
s_peter = slides("sl-peter", ["peter.jpg"], IN_P, [round(S - IN_P, 2)], push=1.12)

behind = "\n".join([
    f_india[0], f_khor[0], s_khw[0], s_peter[0],
    # за головой: хук, развязка, ЕГЭ на 80+ — выше головы с запасом на наезд (п.17)
    big("h-uz", "узбекские", HEAD, 150, RED),
    big("p-ar", '<span style="position: relative;">арабские<svg viewBox="0 0 100 10" preserveAspectRatio="none" '
        'style="position: absolute; left: -3%; top: 40%; width: 106%; height: 26px; overflow: visible;">'
        f'<path id="p-ar-x" d="M 0 7 L 100 2" stroke="{RED}" stroke-width="12" vector-effect="non-scaling-stroke" fill="none" {DRAW} />'
        '</svg></span>', HEAD, 100, CREAM),
    big("p-uz", "узбекские", HEAD, 150, RED),
])

front = "\n".join([
    digits, arab_lbl,
    f'        <div id="book" class="g tx-q" {SAFE}>«Китаб аль-хисаб<br>аль-хинди»<br><span style="font-size: 34px;">Багдад, около 825 г.</span></div>',
    stamp("st-web", "вебинар", SCHEME + 10, 84, -6, SAFE),
    route, year, arabic,
    big("ar-ind", "индийские", 1100, 92, RED, SAFE + ' data-col="1"'),
    cyr,
    stamp("st-gen", "гениально", SCHEME + 10, 72, -5, SAFE),
    roman,
    lead("uz-lead", "хорезм сегодня —", SCHEME - 10, CREAM, SAFE + ' data-col="1"'),
    big("uz-big", "узбекистан", SCHEME + 40, 84, RED, SAFE + ' data-col="1"'),
])

TX_IN = '{ fromY: 60, fromScale: 0.9, dur: 0.3, ease: "power3.out" }'
TX_OUT = '{ y: -20 }'

beats = f'''
      // ---------- хук: «цифры на самом деле УЗБЕКСКИЕ» за головой ----------
      slam("#h-uz", {t(1.94):.2f}, {{ fromScale: 1.5 }});
      flash({t(1.94):.2f});
      leave("#h-uz", {t(2.70):.2f}, {{ y: -60, dur: 0.2 }});

      // ---------- 1 2 3 4 5 под счёт пальцев, «АРАБСКИЕ» → зачёркнуто на «не арабы» ----------
      tl.set("#d15", {{ opacity: 1 }}, {t(4.66):.2f});
''' + "".join(
    f'      tl.fromTo("#d15-{i}", {{ opacity: 0, y: 70, scale: 0.6, filter: BLUR(10) }}, {{ opacity: 1, y: 0, scale: 1, filter: BLUR(0), '
    f'duration: 0.14, ease: "back.out(2)", immediateRender: false }}, {t(x):.2f});\n'
    for i, x in enumerate((4.70, 5.10, 5.28, 5.44, 5.58))) + f'''
      slam("#d15-lbl", {t(6.26):.2f}, {{ fromScale: 1.3, blur: 8 }});
      draw("#d15-x", {t(10.30):.2f}, 0.22);
      leave("#d15", {t(10.85):.2f}, {TX_OUT});
      leave("#d15-lbl", {t(10.85):.2f}, {TX_OUT});

      // ---------- ИИ-видео: Индия — «цифры от 0 до 9 придумали в Индии» ----------
{f_india[1]}

      // ---------- Аль-Хорезми: марка СССР во весь кадр, книга, «вебинар» ----------
{s_khw[1]}
      enter("#book", {t(16.46):.2f}, {TX_IN});
      leave("#book", {t(19.10):.2f}, {TX_OUT});
      slam("#st-web", {t(19.36):.2f}, {{ fromScale: 2.0, blur: 10, rot: -6 }});
      leave("#st-web", {t(19.98):.2f}, {{ scale: 0.8, y: 0, dur: 0.18 }});

      // ---------- путь книги: Индия → Багдад → латынь XII века ----------
      tl.set("#rt", {{ opacity: 1 }}, {t(20.04):.2f});
      tl.fromTo("#rt-n0", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.22, ease: "power3.out", immediateRender: false }}, {t(20.04):.2f});
      draw("#rt-l1", {t(20.30):.2f}, 0.35);
      tl.fromTo("#rt-n1", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.22, ease: "power3.out", immediateRender: false }}, {t(20.62):.2f});
      draw("#rt-l2", {t(21.14):.2f}, 0.4);
      tl.fromTo("#rt-n2", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.22, ease: "power3.out", immediateRender: false }}, {t(21.55):.2f});
      tl.fromTo("#rt-lat", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.25, ease: "power3.out", immediateRender: false }}, {t(21.80):.2f});
      leave("#rt", {t(22.60):.2f}, {TX_OUT});

      // ---------- «нормальные цифры, а не только римские»: 2026 = MMXXVI ----------
      slam("#yr", {t(22.76):.2f}, {{ fromScale: 1.3, blur: 8 }});
      slam("#yr-rom", {t(24.58):.2f}, {{ fromScale: 1.5, blur: 8 }});
      leave("#yr", {t(25.20):.2f}, {TX_OUT});
      leave("#yr-rom", {t(25.20):.2f}, {TX_OUT});

      // ---------- у арабов свои цифры — и они «индийские» ----------
      tl.set("#ar", {{ opacity: 1 }}, {t(26.08):.2f});
      tl.fromTo("#ar .ar", {{ opacity: 0, y: 60, filter: BLUR(10) }}, {{ opacity: 1, y: 0, filter: BLUR(0), duration: 0.16, ease: "power3.out", stagger: 0.09, immediateRender: false }}, {t(26.10):.2f});
      enter("#ar-lat", {t(27.14):.2f}, {TX_IN});
      slam("#ar-ind", {t(28.32):.2f}, {{ fromScale: 1.4, blur: 8 }});
      leave("#ar", {t(29.10):.2f}, {TX_OUT});
      leave("#ar-lat", {t(29.10):.2f}, {TX_OUT});
      leave("#ar-ind", {t(29.10):.2f}, {TX_OUT});

      // ---------- Пётр I во весь кадр — выход перебивки (splice) ровно на склейке дубля ----------
{s_peter[1]}

      // ---------- на Руси: буквы с чёрточкой сверху ----------
      tl.set("#cy", {{ opacity: 1 }}, {t(64.70):.2f});
''' + "".join(
    f'      tl.fromTo("#cy-{i}", {{ opacity: 0, y: 50 }}, {{ opacity: 1, y: 0, duration: 0.18, ease: "back.out(2)", immediateRender: false }}, {t(64.72) + 0.12 * i:.2f});\n'
    for i in range(5)) + f'''      tl.to("#cy .cy-n", {{ attr: {{ opacity: 1 }}, duration: 0.12, stagger: 0.08 }}, {t(65.46):.2f});
''' + "".join(f'      draw("#cy-t{i}", {t(66.56) + 0.07 * i:.2f}, 0.2);\n' for i in range(5)) + f'''      leave("#cy", {t(67.45):.2f}, {TX_OUT});

      // ---------- «тоже, конечно, гениально» ----------
      slam("#st-gen", {t(68.66):.2f}, {{ fromScale: 2.0, blur: 10, rot: -5 }});
      leave("#st-gen", {t(69.30):.2f}, {{ scale: 0.8, y: 0, dur: 0.18 }});

      // ---------- римский счёт: X V I I I = 18 ----------
      tl.set("#rm", {{ opacity: 1 }}, {t(71.70):.2f});
''' + "".join(
    f'      tl.fromTo("#rm-{i}", {{ opacity: 0, y: 70, scale: 0.6, filter: BLUR(10) }}, {{ opacity: 1, y: 0, scale: 1, filter: BLUR(0), '
    f'duration: 0.14, ease: "back.out(2)", immediateRender: false }}, {t(x):.2f});\n'
    for i, x in enumerate((71.78, 72.44, 72.82, 73.34, 73.56))) + f'''      slam("#rm-eq", {t(73.88):.2f}, {{ fromScale: 1.4, blur: 8 }});
      leave("#rm", {t(74.12):.2f}, {TX_OUT});
      leave("#rm-eq", {t(74.12):.2f}, {TX_OUT});

      // ---------- развязка: не АРАБСКИЕ, а УЗБЕКСКИЕ ----------
      enter("#p-ar", {t(76.56):.2f}, {{ fromY: 40, fromScale: 0.9, dur: 0.22, ease: "power3.out" }});
      draw("#p-ar-x", {t(76.98):.2f}, 0.16);
      leave("#p-ar", {t(77.18):.2f}, {{ y: -80, dur: 0.14 }});
      slam("#p-uz", {t(77.22):.2f}, {{ fromScale: 1.6 }});
      flash({t(77.22):.2f});
      leave("#p-uz", {t(78.05):.2f}, {{ y: -60, dur: 0.2 }});

      // ---------- ИИ-видео: Хорезм ----------
{f_khor[1]}

      // ---------- Хорезм сегодня — Узбекистан ----------
      enter("#uz-lead", {t(80.82):.2f}, {TX_IN});
      slam("#uz-big", {t(81.64):.2f}, {{ fromScale: 1.4, blur: 8 }});
      leave("#uz-lead", {t(82.26):.2f}, {TX_OUT});
      leave("#uz-big", {t(82.26):.2f}, {TX_OUT});
'''

# финал: «ЕГЭ на 80+» — в подписи плашки (за головой не помещается: в конце он наклоняется к камере, голова до верха кадра)
CTA = t(85.72)        # на «хотите сдать»: «у меня в профиле» идёт субтитрами, без субтитров в конце — меньше 3 с
sounds = [
    audio("uz1", "impact-bass-1", t(1.94), 0.9),
    audio("india", "whoosh-cinematic", IN_A - 0.15, 0.7),
    audio("uz2", "impact-bass-2", t(77.22), 0.9),
]
# человек поверх текста за головой: хук и развязка
fg = [(t(0.95), t(2.95)), (t(76.50), t(78.30))]

switch, whips = tk.framing(keep_wide=[(t(76.5), t(78.3))])     # на развязке крупный план поднял бы голову в слово
beats += whips


def soft_events():
    """Тихие звуки монтажа (kit.soft_track решает, что прозвучит): склейка и перебивки — накат, штамп и удар словом —
    пузырёк, влёт подписи и карточки — тап, линия схемы и шаг числа — тик, смена плана — тише и в последнюю очередь."""
    ev = [(x, "frame") for a, b, *_ in switch for x in (a, b)]
    ev += [(S, "cut"), (OUT_A, "cut"), (IN_B, "cut"), (OUT_B, "cut")]
    ev += [(t(6.26), "stamp"), (t(19.40), "stamp"), (t(22.76), "stamp"), (t(28.32), "stamp"), (t(68.66), "stamp"),
           (t(73.88), "stamp"), (t(81.64), "stamp"), (t(24.58), "stamp")]
    ev += [(IN_K, "cut"), (t(16.40), "cut"), (IN_P, "cut")]
    ev += [(t(16.46), "text"), (t(80.82), "text"), (t(76.56), "text")]
    ev += [(t(4.70), "line"), (t(5.28), "line"), (t(10.30), "line"), (t(20.30), "line"), (t(21.14), "line"),
           (t(26.10), "line"), (t(64.72), "line"), (t(66.56), "line"), (t(71.78), "line"), (t(72.82), "line")]
    return ev


sounds += soft_track(soft_events(), sounds)
sounds.append(background_music(STEM, "yt-misdirection.mp3", DUR))
page = build_page("Почему цифры на самом деле узбекские", DUR, behind, front, beats, sounds, fg,
                  cta_at=CTA, extra_css=css, fmt=tk.fmt, captions=tk.captions, cta_small="ЕГЭ на 80+ — переходи ко мне")
out = ROOT / f"studio/{tk.project}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

director = {
    "_note": "IMG_3292 v3 (19.10.2026): узбекские цифры, монтаж с нуля. Раскладка — work/IMG_3292/page.py, план — plan.md.",
    "punches": [[t(1.94), t(2.70), tk.punch, 0.08, 0.25], [t(68.66), t(69.30), tk.punch, 0.06, 0.2],
                [t(81.64), t(82.26), tk.punch, 0.06, 0.2]]          # на развязке наезда нет: голова закрыла бы «УЗБЕКСКИЕ»
               + tk.splice_punches() + switch,
    # номера слов — по aroll.words.json (после склейки номера исходника другие)
    "text_fixes": {"47": "Аль-Хорезми", "48": "", "62": "вебинары,", "97": "Пётр", "99": "А на", "104": "писали",
                   "111": "сверху,", "118": "гениально.", "124": "счёта,", "126": "X,", "127": "V,", "128": "I,", "129": "I,",
                   "130": "I.", "132": "так.", "137": "цифры", "142": "арабские,", "144": "узбекские.", "145": "Аль-Хорезми",
                   "148": "Хорезма,", "154": "Узбекистана.", "157": "друзья,", "164": "профиле,", "169": "ЕГЭ",
                   "171": "80+", "172": ""},
    "keep_case": ["ЕГЭ", "X,", "V,", "I,", "I.", "Аль-Хорезми", "Хорезма,", "Узбекистана.", "Пётр", "I."],
    "accent_words": ["узбекские.", "Индии.", "Аль-Хорезми", "римские.", "индийскими,", "гениально.", "Узбекистана.", "80+"],
    # субтитры прячутся только под текстом, который повторяет речь (rules.md п.16): УЗБЕКСКИЕ, 1–5 АРАБСКИЕ, ИНДИЙСКИЕ,
    # ГЕНИАЛЬНО, X V I I I, АРАБСКИЕ→УЗБЕКСКИЕ, УЗБЕКИСТАН, финал; схемы, портреты и футажи — с субтитрами
    "hide_captions": [[t(0.95), t(2.75)], [t(4.62), t(7.20)], [t(28.25), t(29.15)], [t(68.60), t(69.32)],
                      [t(71.70), t(74.14)], [t(76.50), t(78.10)], [t(80.80), t(82.28)], [CTA - 0.2, DUR]],
}
(ROOT / f"work/{STEM}/director{'.' + VARIANT if VARIANT else ''}.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
