"""Страница графики IMG_1798: почему в круге 360 градусов.

Время ударов — по исходнику, на шкалу дубля (0.83–70.87, вырез 27.56–29.42 «год, круг, день, радиус»,
хвост «Хорошо. Пока…» убран) переводит Take. План — work/IMG_1798/plan.md.
Проверено: делители 360 среди 1–10 — 1, 2, 3, 4, 5, 6, 8, 9, 10; на 7 не делится (360/7 ≈ 51,4) — верно.
360 = 6 · 60 — верно. Нарезка пиццы: 360/2 = 180, /3 = 120, /4 = 90, /6 = 60, /8 = 45, /12 = 30 — целые.
Град (гон): 400 в полном круге, 100 в прямом угле — французская метрическая реформа конца XVIII века — верно;
«ничего не получилось» — шутка автора (грады живут в геодезии), не спорим. Полный круг = 2π рад — верно.
«Год ≈ 360 дней», «солнце ≈ на 1° в день» — популярная версия, как он и говорит.
Распознавание: «вздвигается» → «сдвигается», «1 четвертая» → «одна четвёртая».
Картинки — Wikimedia Commons, качает work/IMG_1798/fetch.py; лицензии и авторы — downloads/candidates.json.
"""
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, doc_img  # noqa: E402

STEM = "IMG_1798"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
IMG = ROOT / f"studio/{STEM}/assets/img"
IMG.mkdir(parents=True, exist_ok=True)
# фоны и табличка — выбраны глазами из кандидатов fetch.py (лицензии — downloads/candidates.json):
#   ворота Иштар, Пергамский музей (CC0); закат в пустыне Намиб, Giles Laurent (CC BY-SA 4.0);
#   Эйфелева башня (PD); табличка YBC 7289 (CC0)
PICK = {"bg_babylon.jpg": "babylon_1.jpg", "bg_sky.jpg": "sky_1.jpg", "bg_paris.jpg": "paris_1.jpg",
        "tablet.jpg": "tablet_1.jpg"}
for dst_name, src_name in PICK.items():
    src = ROOT / f"work/{STEM}/downloads/{src_name}"
    if not src.exists():
        sys.exit(f"✗ нет {src.name} — запусти work/{STEM}/fetch.py (картинки с Wikimedia Commons)")
    dst = IMG / dst_name
    if not (dst.exists() and dst.samefile(src)):
        shutil.copyfile(src, dst)

CHEST = 1290        # верх плашек на груди: подбородок при базе 1.2 доходит до y ~1263 (как IMG_1812)
GOLD, RED, CREAM = "#F5B82E", "#F0352C", "#F2EBDD"
css = f'''      .panel {{ border-radius: 28px; background: rgba(12,12,14,0.88); border: 2px solid rgba(242,235,221,0.16);
               box-shadow: 0 30px 80px rgba(0,0,0,0.6); overflow: hidden; }}
      .panel svg {{ position: absolute; left: 0; top: 0; }}
      .p-big {{ position: absolute; font-family: "Oswald"; font-weight: 700; color: var(--cream); line-height: 1; white-space: nowrap; }}
      .p-note {{ position: absolute; font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.08em;
                text-transform: uppercase; color: rgba(242,235,221,0.78); white-space: nowrap; }}
      .p-big .katex-src, .p-big .katex-display {{ margin: 0; display: inline-block; }}
      .num-card {{ top: 300px; width: 250px; padding: 14px 10px 16px; background: var(--paper); border-radius: 8px; text-align: center;
                  box-shadow: 0 24px 60px rgba(0,0,0,0.55); }}
      .num-card b {{ display: block; font-family: "Oswald"; font-weight: 700; font-size: 120px; line-height: 1; color: var(--ink); }}
      .num-card i {{ display: block; margin-top: 6px; font-family: "Cormorant"; font-weight: 700; font-size: 30px; color: #5A4E3C; }}
      .dv {{ position: absolute; width: 92px; height: 92px; border-radius: 16px; display: flex; align-items: center; justify-content: center;
            font-family: "Oswald"; font-weight: 700; font-size: 58px; color: var(--cream); background: rgba(242,235,221,0.12);
            border: 3px solid rgba(242,235,221,0.3); opacity: 0; }}
      .strike {{ position: absolute; height: 9px; border-radius: 5px; background: var(--red); transform-origin: 0 50%; transform: scaleX(0); }}
      .pz-lab {{ position: absolute; left: 330px; top: 70px; width: 240px; text-align: center; opacity: 0; }}
      .pz-lab b {{ display: block; font-family: "Oswald"; font-weight: 700; font-size: 92px; line-height: 1; color: {GOLD}; }}
      .pz-lab i {{ display: block; margin-top: 8px; font-family: "Manrope"; font-weight: 800; font-style: normal; font-size: 30px;
                  letter-spacing: 0.06em; color: rgba(242,235,221,0.8); }}
      /* подменённый фон за спиной: сверху, низ переходит в родной кадр (там руки и банка) */
      .bg {{ left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden;
             -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%);
             mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%); }}
      .bg img {{ position: absolute; left: -54px; top: -96px; width: 1188px; height: 2112px; object-fit: cover; }}
      .bg .vig {{ position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 38%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.6) 100%); }}
      #d-tab .formula-line {{ position: absolute; left: 0; width: 100%; top: 232px; text-align: center; opacity: 0; }}
      #d-tab .formula-line span {{ display: inline-block; padding: 4px 22px 8px; border-radius: 14px; background: rgba(12,12,14,0.86);
                                   font-family: "Oswald"; font-weight: 700; font-size: 60px; color: {GOLD}; }}
      #bg-sky img {{ object-position: 30% 50%; }}
'''

SAFE = 'data-safe="лицо важнее серой зоны: плашка ниже подбородка (Валера, 12.10)"'
STK = 'top: 300px; font-size: 56px; white-space: nowrap;'
W, H = 590, 330
CX, CY, R = 165, 165, 125


def panel(pid: str, inner: str, height: int = H) -> str:
    return (f'        <div id="{pid}" class="g panel" {SAFE} style="left: 245px; top: {CHEST}px; width: {W}px; height: {height}px;">\n'
            f'{inner}\n        </div>')


def svg(inner: str, height: int = H) -> str:
    return f'          <svg viewBox="0 0 {W} {height}" style="width: {W}px; height: {height}px;">{inner}</svg>'


def pt(deg: float, r: float) -> tuple:
    """Точка на окружности: 0° — вверх, по часовой."""
    a = math.radians(deg)
    return CX + r * math.sin(a), CY - r * math.cos(a)


def ticks(n: int, r0: float, r1: float, every: int = 0, r_long: float = 0, width: float = 2.0,
          color: str = "rgba(242,235,221,0.55)") -> str:
    out = []
    for i in range(n):
        d = 360 * i / n
        a = r_long if every and i % every == 0 else r0
        (x0, y0), (x1, y1) = pt(d, a), pt(d, r1)
        out.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" />')
    return f'<g stroke="{color}" stroke-width="{width}" stroke-linecap="round">{"".join(out)}</g>'


RING = f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="rgba(242,235,221,0.28)" stroke-width="6" />'
TRAIL = (f'd="M {CX} {CY - R} A {R} {R} 0 1 1 {CX - 0.01} {CY - R}" fill="none" stroke-width="10" stroke-linecap="round" '
         'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"')
ARROW = (f'<line x1="{CX}" y1="{CY}" x2="{CX}" y2="{CY - R + 26}" stroke="{CREAM}" stroke-width="10" stroke-linecap="round" />'
         f'<path d="M {CX - 22} {CY - R + 40} L {CX} {CY - R + 8} L {CX + 22} {CY - R + 40} Z" fill="{CREAM}" />'
         f'<circle cx="{CX}" cy="{CY}" r="14" fill="{RED}" />')

# 1. круг: стрелка «он» делает полный оборот и встаёт на старт
spin = panel("p-spin", "\n".join([
    svg(f'{RING}<path id="spin-trail" {TRAIL} stroke="{RED}" /><g id="spin-arrow">{ARROW}</g>'),
    '          <div id="spin-eq" class="p-big" style="left: 312px; top: 92px; font-size: 62px; opacity: 0;">0° = 360°</div>',
    '          <div id="spin-full" class="p-note" style="left: 318px; top: 196px; opacity: 0;">полный круг</div>',
]))

# 2. часы: минутная стрелка проходит 60 делений
HAND = (f'<line x1="{CX}" y1="{CY}" x2="{CX}" y2="{CY - R + 22}" stroke="{RED}" stroke-width="8" stroke-linecap="round" />'
        f'<circle cx="{CX}" cy="{CY}" r="12" fill="{CREAM}" />')
clock = panel("p-clock", "\n".join([
    svg(f'<circle cx="{CX}" cy="{CY}" r="{R + 4}" fill="rgba(242,235,221,0.06)" stroke="rgba(242,235,221,0.4)" stroke-width="5" />'
        f'{ticks(60, R - 14, R - 4, every=5, r_long=R - 28, width=3)}<g id="clock-hand">{HAND}</g>'),
    f'          <div id="clock-n" class="p-big" style="left: 330px; top: 50px; font-size: 150px; color: {GOLD};">60</div>',
    '          <div class="p-note" style="left: 334px; top: 222px;">минут в часе</div>',
]))

# 3. год как круг: 360 делений, солнце шагает, одно деление — день
SUN = (f'<circle cx="{CX}" cy="{CY - R - 4}" r="17" fill="{GOLD}" />'
       f'<circle cx="{CX}" cy="{CY - R - 4}" r="27" fill="none" stroke="{GOLD}" stroke-width="3" opacity="0.6" />')
x0, y0 = pt(0, R - 30)
x1, y1 = pt(0, R + 6)
sun = panel("p-sun", "\n".join([
    svg(f'{ticks(360, R - 12, R + 2, every=30, r_long=R - 24, width=1.4)}'
        f'<g id="sun-g" opacity="0">{SUN}<line id="sun-tick" x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" '
        f'stroke="{RED}" stroke-width="7" stroke-linecap="round" opacity="0" /></g>'),
    f'          <div class="p-big" style="left: 318px; top: 36px; font-size: 104px;">≈<span id="sun-n">365</span></div>',
    '          <div class="p-note" style="left: 322px; top: 150px;">дней в году</div>',
    f'          <div id="sun-day" class="p-big" style="left: 318px; top: 216px; font-size: 52px; color: {GOLD}; opacity: 0;">1 день ≈ 1°</div>',
]))

# 4. делители 360 среди 1–10: семь перечёркнута
tiles = []
for i in range(10):
    left, top = 37 + (i % 5) * 106, 64 + (i // 5) * 112
    tiles.append(f'          <div id="dv{i + 1}" class="dv" style="left: {left}px; top: {top}px;">{i + 1}</div>')
div = panel("p-div", "\n".join([
    '          <div class="p-note" style="left: 0; width: 590px; text-align: center; top: 18px;">360 делится на</div>',
    *tiles,
    '          <div id="dv7-x" class="strike" style="left: 143px; top: 249px; width: 112px;"></div>',
]), height=290)

# 5. пицца: режется на 2, 3, 4, 6, 8, 12 кусков — каждый кусок целое число градусов
CUTS = [2, 3, 4, 6, 8, 12]
pep = "".join(f'<circle cx="{pt(d, rr)[0]:.1f}" cy="{pt(d, rr)[1]:.1f}" r="13" fill="#B8331F" />'
              for d, rr in [(20, 80), (75, 50), (130, 90), (200, 70), (250, 95), (310, 55), (345, 95), (160, 30)])
cut_groups = []
for n in CUTS:
    lines = "".join(f'<line x1="{CX}" y1="{CY}" x2="{pt(360 * k / n, R)[0]:.1f}" y2="{pt(360 * k / n, R)[1]:.1f}" />'
                    for k in range(n))
    cut_groups.append(f'<g id="pz{n}" stroke="#2A1A10" stroke-width="5" stroke-linecap="round" opacity="0">{lines}</g>')
labels = [f'          <div id="pzl{n}" class="pz-lab"><b>{360 // n}°</b><i>360 : {n}</i></div>' for n in CUTS]
pizza = panel("p-pizza", "\n".join([
    svg(f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="#F2B544" stroke="#C7761E" stroke-width="12" />'
        f'<circle cx="{CX}" cy="{CY}" r="{R - 14}" fill="#E8A33A" opacity="0.5" />{pep}{"".join(cut_groups)}'),
    *labels,
    '          <div id="pz-all" class="p-note" style="left: 318px; top: 262px; color: #F5B82E; opacity: 0;">всегда целое</div>',
]))

# 6. четверть круга: 90° → 100 град (французы), прямой угол
QX, QY, QR = 70, 300, 230
quad = panel("p-quad", "\n".join([
    svg(f'<path id="q-sector" d="M {QX} {QY} L {QX} {QY - QR} A {QR} {QR} 0 0 1 {QX + QR} {QY} Z" fill="rgba(240,53,44,0.22)" '
        f'stroke="{CREAM}" stroke-width="6" stroke-linejoin="round" />'
        f'<path d="M {QX} {QY - 46} L {QX + 46} {QY - 46} L {QX + 46} {QY}" fill="none" stroke="{CREAM}" stroke-width="5" />'),
    '          <div id="q-90" class="p-big" style="left: 350px; top: 34px; font-size: 96px; opacity: 0;">90°</div>',
    '          <div id="q-90x" class="strike" style="left: 340px; top: 82px; width: 150px;"></div>',
    f'          <div id="q-100" class="p-big" style="left: 330px; top: 150px; font-size: 96px; color: {GOLD}; opacity: 0;">100<span style="font-size: 44px;"> град</span></div>',
    '          <div id="q-100x" class="strike" style="left: 320px; top: 200px; width: 240px;"></div>',
    '          <div class="p-note" style="left: 334px; top: 272px;">прямой угол</div>',
]))

# 7. ЕГЭ: полный круг — 2π
rx, ry = pt(90, R)
rad = panel("p-rad", "\n".join([
    svg(f'{RING}<path id="rad-trail" {TRAIL} stroke="{GOLD}" />'
        f'<line id="rad-r" x1="{CX}" y1="{CY}" x2="{rx:.1f}" y2="{ry:.1f}" stroke="{CREAM}" stroke-width="6" stroke-linecap="round" '
        'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />'
        f'<circle cx="{CX}" cy="{CY}" r="10" fill="{CREAM}" />'),
    '          <div id="rad-note" class="p-note" style="left: 330px; top: 52px; opacity: 0;">в радианах</div>',
    f'          <div id="rad-eq" class="p-big" style="left: 300px; top: 104px; font-size: 50px; opacity: 0;">'
    '<span class="katex-src" data-tex="360^\\circ = 2\\pi"></span></div>',
]))

# YBC 7289 (CC0, Йель): цифры на фото — подпись музея к шестидесятеричной записи √2 = 1;24,51,10
tablet = doc_img("d-tab", "tablet.jpg", "табличка вавилонян: числа шестидесятками", left=250, top=CHEST, width=580,
                 height=320, position="68% 50%")
tablet = tablet.replace('class="g doc"', f'class="g doc" {SAFE}', 1).replace(
    '\n          <div class="doc-cap">',
    '\n          <div class="formula-line"><span id="tab-eq">6 · 60 = 360</span></div>\n          <div class="doc-cap">', 1)


def bg(bid: str, img: str) -> str:
    return f'        <div id="{bid}" class="g bg"><img src="assets/img/{img}" alt="" /><div class="vig"></div></div>'


behind = "\n".join([
    '        <div id="b-360" class="g big" style="top: 300px; font-size: 270px;">360°</div>',
    bg("bg-bab", "bg_babylon.jpg"),
    '        <div id="b-bab-lead" class="g lead" style="top: 272px;">всё дело в</div>',
    '        <div id="b-bab" class="g big" style="top: 320px; font-size: 190px; color: #F5B82E;">вавилоне</div>',
    bg("bg-sky", "bg_sky.jpg"),
    # в этом месте он стоит выше (макушка ~y 430): 60 — выше и мельче, без подписи над ним
    '        <div id="b-60" class="g big red" style="top: 262px; font-size: 160px;">×60</div>',
    bg("bg-paris", "bg_paris.jpg"),
    # как ×60: без подписи и наезда, выше и мельче — в v1 голова с наездом закрывала середину числа
    '        <div id="b-400" class="g big" style="top: 262px; font-size: 170px;">400°</div>',
])

front = "\n".join([
    f'        <div id="st-quote" class="g sticker" style="left: 200px; {STK}">«я изменился на 360°»</div>',
    '        <div id="st-run" class="g stamp" style="left: 380px; top: 290px; font-size: 130px; background: rgba(12,12,14,0.55);">беги</div>',
    spin,
    f'        <div id="st-same" class="g sticker" style="left: 330px; {STK}">тот же самый</div>',
    f'        <div id="st-why" class="g sticker" style="left: 320px; {STK}">почему 360?</div>',
    '        <div id="c-100" class="g num-card" style="left: 128px;"><b>100?</b><i>градусов</i></div>',
    '        <div id="c-400" class="g num-card" style="left: 702px;"><b>400?</b><i>градусов</i></div>',
    f'        <div id="st-again" class="g sticker" style="left: 360px; {STK}">опять они</div>',
    clock,
    f'        <div id="st-ver" class="g sticker" style="left: 210px; {STK}">самая популярная версия</div>',
    sun,
    tablet,
    '        <div id="st-cheat" class="g stamp" style="left: 250px; top: 290px; font-size: 110px; background: rgba(12,12,14,0.55);">читерское</div>',
    div,
    pizza,
    f'        <div id="st-fr" class="g sticker" style="left: 370px; {STK}">французы</div>',
    quad,
    '        <div id="st-fail" class="g stamp" style="left: 270px; top: 290px; font-size: 110px; background: rgba(12,12,14,0.55);">не вышло</div>',
    f'        <div id="st-always" class="g sticker" style="left: 350px; {STK}">как всегда</div>',
    f'        <div id="st-ege" class="g sticker" style="left: 280px; {STK}">в ЕГЭ — радианы</div>',
    rad,
    f'        <div id="st-story" class="g sticker" style="left: 250px; {STK}">другая история</div>',
])

PANEL_IN = '{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }'


def pop(sel: str, at: float, dur: float = 0.2) -> str:
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.5, filter: BLUR(10) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: {dur}, ease: "power4.out" }}, {at});')


def strike(sel: str, at: float) -> str:
    return f'      tl.to("{sel}", {{ scaleX: 1, duration: 0.18, ease: "power2.out" }}, {at});'


def bg_in(sel: str, a: float, b: float) -> str:
    """Фон наплывом со смазом, медленный наезд внутри, уход со смазом; на показе резкий."""
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.08, filter: BLUR(14) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.45, ease: "power2.out" }}, {a});\n'
            f'      tl.fromTo("{sel} img", {{ scale: 1 }}, {{ scale: 1.06, duration: {b - a + 0.35:.2f}, ease: "none" }}, {a});\n'
            f'      tl.to("{sel}", {{ opacity: 0, scale: 1.04, filter: BLUR(12), duration: 0.35, ease: "power2.in" }}, {b});')


# пицца: каждая нарезка сменяет прошлую
PZ_AT = [45.30, 45.80, 46.30, 46.80, 47.30, 47.90]
pz_js = []
for k, (n, at) in enumerate(zip(CUTS, PZ_AT)):
    a = t(at)
    if k:
        prev = CUTS[k - 1]
        pz_js.append(f'      tl.to("#pz{prev}", {{ opacity: 0, duration: 0.08 }}, {a});')
        pz_js.append(f'      tl.to("#pzl{prev}", {{ opacity: 0, y: -30, filter: BLUR(8), duration: 0.12, ease: "power2.in" }}, {a});')
    pz_js.append(f'      tl.fromTo("#pz{n}", {{ opacity: 0, scale: 1.12, svgOrigin: "{CX} {CY}" }}, '
                 f'{{ opacity: 1, scale: 1, duration: 0.14, ease: "power3.out" }}, {a});')
    pz_js.append(f'      tl.fromTo("#pzl{n}", {{ opacity: 0, y: 30, filter: BLUR(8) }}, '
                 f'{{ opacity: 1, y: 0, filter: BLUR(0), duration: 0.14, ease: "power3.out" }}, {round(a + 0.06, 2)});')

beats = f'''
      // ---------- хук: «я изменился на 360°» — 360° за спиной — БЕГИ ----------
      enter("#st-quote", {t(0.96)}, {{ fromScale: 0.6, rot: -3 }});
      leave("#st-quote", {t(3.85)}, {{ y: -30, rot: -10 }});
      slam("#b-360", {t(4.00)}, {{ fromScale: 1.5 }});
      leave("#b-360", {t(5.10)}, {{ y: -60 }});
      slam("#st-run", {t(5.16)}, {{ fromScale: 2.2, rot: -6, blur: 10 }});
      leave("#st-run", {t(6.20)}, {{ scale: 0.6, y: 0, rot: -18 }});

      // ---------- круг: полный оборот — тот же самый ----------
      enter("#p-spin", {t(6.30)}, {PANEL_IN});
      tl.fromTo("#spin-arrow", {{ rotation: 0, svgOrigin: "{CX} {CY}" }}, {{ rotation: 360, svgOrigin: "{CX} {CY}", duration: 1.9, ease: "power1.inOut" }}, {t(6.56)});
      draw("#spin-trail", {t(6.56)}, 1.9);
      enter("#spin-eq", {t(8.10)}, {{ fromScale: 0.8, dur: 0.25 }});
      enter("#st-same", {t(8.20)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-same", {t(9.60)}, {{ y: -30, rot: 10 }});
      enter("#spin-full", {t(10.46)}, {{ fromScale: 0.8, dur: 0.25 }});
      tl.fromTo("#spin-trail", {{ strokeWidth: 10 }}, {{ strokeWidth: 18, duration: 0.22, yoyo: true, repeat: 1, ease: "sine.inOut", immediateRender: false }}, {t(10.50)});
      leave("#p-spin", {t(11.30)}, {{ y: 80 }});

      // ---------- почему 360? не 100, не 400 ----------
      enter("#st-why", {t(11.50)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-why", {t(13.20)}, {{ y: -30, rot: -10 }});
      enter("#c-100", {t(13.62)}, {{ fromX: -300, fromScale: 0.8, rot: -5, dur: 0.35, ease: "power3.out" }});
      enter("#c-400", {t(14.05)}, {{ fromX: 300, fromScale: 0.8, rot: 5, dur: 0.35, ease: "power3.out" }});
      leave("#c-100", {t(14.75)}, {{ x: -300, rot: -15 }});
      leave("#c-400", {t(14.75)}, {{ x: 300, rot: 15 }});

      // ---------- Вавилон за спиной; опять они; 60 минут ----------
{bg_in("#bg-bab", t(14.85), t(19.10))}
      enter("#b-bab-lead", {t(14.90)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-bab", {t(15.40)}, {{ fromScale: 1.5 }});
      leave(["#b-bab", "#b-bab-lead"], {t(16.30)}, {{ y: -60 }});
      enter("#st-again", {t(16.40)}, {{ fromScale: 0.6, rot: 3 }});
      leave("#st-again", {t(17.55)}, {{ y: -30, rot: 10 }});
      enter("#p-clock", {t(17.55)}, {PANEL_IN});
      tl.fromTo("#clock-hand", {{ rotation: 0, svgOrigin: "{CX} {CY}" }}, {{ rotation: 360, svgOrigin: "{CX} {CY}", duration: 1.0, ease: "power1.inOut" }}, {t(17.90)});
      leave("#p-clock", {t(19.10)}, {{ y: 80 }});
      enter("#st-ver", {t(19.20)}, {{ fromScale: 0.6, rot: -3 }});
      leave("#st-ver", {t(20.80)}, {{ y: -30, rot: -10 }});

      // ---------- солнце за спиной: год ≈ 360 дней, 1 день ≈ 1° ----------
{bg_in("#bg-sky", t(20.90), t(27.10))}
      enter("#p-sun", {t(20.95)}, {PANEL_IN});
      tl.fromTo("#sun-n", {{ textContent: 365 }}, {{ textContent: 360, snap: {{ textContent: 1 }}, duration: 0.6, ease: "power2.out", immediateRender: false }}, {t(22.10)});
      tl.fromTo("#sun-g", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.25, ease: "power2.out" }}, {t(23.10)});
      tl.fromTo("#sun-g", {{ rotation: 0, svgOrigin: "{CX} {CY}" }}, {{ rotation: 40, svgOrigin: "{CX} {CY}", duration: 1.6, ease: "steps(40)", immediateRender: false }}, {t(23.40)});
      tl.fromTo("#sun-tick", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.12, ease: "none" }}, {t(24.95)});
      enter("#sun-day", {t(25.00)}, {{ fromScale: 0.8, dur: 0.25 }});
      leave("#p-sun", {t(27.10)}, {{ y: 80 }});

      // ---------- (склейка) считали шестидесятками: 60 за спиной, табличка ----------
      slam("#b-60", {t(32.15)}, {{ fromScale: 1.5 }});
      leave("#b-60", {t(33.30)}, {{ y: -60 }});
      doc("#d-tab", {t(33.30)}, {t(38.70)}, {{ fromRot: -5, rot: 1 }});
      tl.fromTo(".formula-line", {{ opacity: 0, scale: 1.5, filter: BLUR(10) }}, {{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.2, ease: "power4.out" }}, {t(37.40)});

      // ---------- читерское: делители 1–10, кроме 7 ----------
      slam("#st-cheat", {t(39.00)}, {{ fromScale: 2.2, rot: -5, blur: 10 }});
      leave("#st-cheat", {t(40.30)}, {{ scale: 0.6, y: 0, rot: -14 }});
      enter("#p-div", {t(40.40)}, {PANEL_IN});
      tl.fromTo("#p-div .dv", {{ opacity: 0, scale: 0.4 }}, {{ opacity: 1, scale: 1, duration: 0.18, ease: "back.out(2)", stagger: 0.04 }}, {t(41.00)});
      tl.to(["#dv1", "#dv2", "#dv3", "#dv4", "#dv5", "#dv6", "#dv8", "#dv9", "#dv10"], {{ backgroundColor: "rgba(59,178,115,0.85)", borderColor: "#3BB273", duration: 0.12, stagger: 0.07 }}, {t(42.50)});
      tl.to("#dv7", {{ backgroundColor: "rgba(240,53,44,0.35)", borderColor: "#F0352C", duration: 0.12 }}, {t(43.60)});
      tl.fromTo("#dv7-x", {{ rotation: -35, scaleX: 0 }}, {{ rotation: -35, scaleX: 1, duration: 0.18, ease: "power2.out" }}, {t(43.60)});
      leave("#p-div", {t(44.50)}, {{ y: 80 }});

      // ---------- пицца: как угодно — всё целое ----------
      enter("#p-pizza", {t(44.60)}, {PANEL_IN});
{chr(10).join(pz_js)}
      enter("#pz-all", {t(48.00)}, {{ fromScale: 0.8, dur: 0.25 }});
      leave("#p-pizza", {t(48.90)}, {{ y: 80 }});

      // ---------- французы: Эйфелева башня, 400° ----------
{bg_in("#bg-paris", t(49.10), t(55.40))}
      enter("#st-fr", {t(49.90)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-fr", {t(51.60)}, {{ y: -30, rot: -10 }});
      slam("#b-400", {t(54.45)}, {{ fromScale: 1.5 }});
      leave("#b-400", {t(55.40)}, {{ y: -60 }});

      // ---------- четверть круга: 90° → 100 град; не вышло ----------
      enter("#p-quad", {t(55.50)}, {PANEL_IN});
      enter("#q-90", {t(55.80)}, {{ fromScale: 0.8, dur: 0.25 }});
{strike("#q-90x", t(57.10))}
{pop("#q-100", t(57.15))}
      slam("#st-fail", {t(59.74)}, {{ fromScale: 2.2, rot: -6, blur: 10 }});
{strike("#q-100x", t(59.74))}
      leave("#p-quad", {t(60.50)}, {{ y: 80 }});
      leave("#st-fail", {t(60.60)}, {{ scale: 0.6, y: 0, rot: -18 }});
      enter("#st-always", {t(60.80)}, {{ fromScale: 0.6, rot: 3 }});
      leave("#st-always", {t(62.30)}, {{ y: -30, rot: 10 }});

      // ---------- ЕГЭ: 360° = 2π ----------
      enter("#st-ege", {t(62.50)}, {{ fromScale: 0.6, rot: -3 }});
      leave("#st-ege", {t(64.40)}, {{ y: -30, rot: -10 }});
      enter("#p-rad", {t(64.10)}, {PANEL_IN});
      enter("#rad-note", {t(64.30)}, {{ fromScale: 0.8, dur: 0.25 }});
      draw("#rad-r", {t(64.50)}, 0.3);
      draw("#rad-trail", {t(64.90)}, 0.8);
{pop("#rad-eq", t(65.65))}
      enter("#st-story", {t(66.90)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-story", {t(68.50)}, {{ y: -30, rot: 10 }});
      leave("#p-rad", {t(68.55)}, {{ y: 80 }});
'''

# Звуки — мало (бриф: few), правила 12.10: только на главных ударах, семейства не подряд,
# каждый файл ≤ 2 раз, между звуками ≥ 1 с. Фоны, визуализации и стикеры — без звука.
sounds = [
    audio("s360", "whoosh-cinematic", t(3.98), 0.7),
    audio("run", "impact-bass-1", t(5.14), 0.9),
    audio("bab", "whoosh", t(15.38), 0.7),
    audio("cheat", "impact-bass-2", t(38.98), 0.8),
    audio("fail", "error", t(59.72), 0.6),
]
# человек поверх фонов и слов за спиной: 360°, Вавилон, солнце, 60, Париж + 400°
fg = [(t(3.90), t(5.45)), (t(14.80), t(19.55)), (t(20.85), t(27.50)), (t(30.00), t(33.70)), (t(49.05), t(55.85))]

page = build_page("Почему в круге 360 градусов", DUR, behind, front, beats, sounds, fg, cta_at=t(68.84),
                  extra_css=css, fmt=tk.fmt, captions=tk.captions)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

fixes = tk.fixes({68: "сдвигается", 149: "одна", 150: "четвёртая"})

JOIN = t(29.45)        # склейка после выреза «год, круг, день, радиус»
director = {
    "_note": "Почему 360 градусов. Время по дублю; раскладка — work/IMG_1798/page.py, план — plan.md.",
    "punches": [[t(4.00), t(5.10), 1.16, 0.10], [t(5.16), t(6.20), 1.22, 0.05], [t(15.40), t(16.30), 1.18, 0.10],
                [JOIN, round(JOIN + 0.9, 2), 1.2, 0.0, 0.6],
                [t(39.00), t(40.30), 1.22, 0.10],[t(59.74), t(60.70), 1.22, 0.10],
                [t(65.65), t(66.70), 1.16, 0.10]],
    "text_fixes": fixes,
    "keep_case": ["ЕГЭ"],
    "accent_words": ["360", "беги", "вавилонянах", "читерское", "7", "400", "2π"],
    # плашки на груди — на их время субтитров нет
    "hide_captions": [[t(6.25), t(11.60)], [t(17.50), t(19.40)], [t(20.90), t(27.40)], [t(33.25), t(39.00)],
                      [t(40.35), t(49.20)], [t(55.45), t(60.80)], [t(64.05), t(68.80)], [t(68.80), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
