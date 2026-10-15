"""Страница графики IMG_1818: «π = …» — откуда у числа π его буква.

Время ударов — по исходнику, на шкалу дубля (0.0–83.2, хвоста нет) переводит Take. План —
work/IMG_1818/plan.md (по п.13 rules.md). «пиздец» (61.22–61.60) — под «пип» в edit.json, в
субтитрах «***», за спиной — «π» и цензурная плашка поверх «здец»: шутка читается, слова нет.
Проверено:
  π = C/d (длина окружности к диаметру) — верно; 3,14159265358979323846264338327950288419716939937510…
  — первые 50 знаков сверены. περιφέρεια (периферия, «окружность») начинается с π — верно; так
  π объясняют и в учебниках (Джонс, 1706, писал π как первую букву periphery / περίμετρος).
  Эйлер: 13 детей (выжили пятеро) — верно; в Петербургской академии с 1727, Анна Иоанновна
  правила 1730–1740 — верно; π у Эйлера — с «Механики» 1736 г. (Mechanica sive motus scientia),
  массово — после «Введения в анализ» 1748 г.; Европа приняла обозначение за ним — верно.
  «Не благодаря грекам» — оценка автора: первым π так записал Уильям Джонс (1706); на экран это не
  выносим (поправлять автора в его ролике не наше дело) — в отчёт.
Распознавание: «ИГ» → «ЕГЭ», «Эллир» → «Эйлер», «80» + «+,» склеит compose.
Картинки — Wikimedia Commons, качает work/IMG_1818/fetch.py; лицензии и авторы — в
downloads/candidates.json; что выбрано — PICK ниже.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, card  # noqa: E402

STEM = "IMG_1818"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
IMG = ROOT / f"studio/{STEM}/assets/img"
IMG.mkdir(parents=True, exist_ok=True)
# выбрано глазами из кандидатов fetch.py (лицензии — downloads/candidates.json)
PICK = {"euler.jpg": "euler_1.jpg", "anna.jpg": "anna_1.jpg", "mechanica.jpg": "mechanica_1.jpg",
        "bg_spb.jpg": "spb_1.jpg", "bg_kunst.jpg": "kunst_1.jpg", "bg_court.jpg": "court_1.jpg"}
for dst_name, src_name in PICK.items():
    src = ROOT / f"work/{STEM}/downloads/{src_name}"
    if not src.exists():
        sys.exit(f"✗ нет {src.name} — запусти work/{STEM}/fetch.py (картинки с Wikimedia Commons)")
    dst = IMG / dst_name
    if not (dst.exists() and dst.samefile(src)):
        shutil.copyfile(src, dst)

CHEST = 1290        # верх плашек на груди: подбородок при базе 1.2 ниже 1263 (как в IMG_1812)
UP = 290            # верх полосы над головой: ниже вкладок TikTok (260), макушка — ниже 600
SAFE = 'data-safe="лицо важнее серой зоны: плашка ниже подбородка (Валера, 12.10)"'
STK = 'top: 300px; font-size: 56px; white-space: nowrap;'
PI = "3,14159265358979323846264338327950288419716939937510582097494459230781640628620899862803482534211706798…"

css = f'''      .panel {{ border-radius: 28px; background: rgba(12,12,14,0.88); border: 2px solid rgba(242,235,221,0.16);
               box-shadow: 0 30px 80px rgba(0,0,0,0.6); }}
      .tile {{ position: absolute; top: 0; width: 170px; height: 190px; border-radius: 22px; display: flex; align-items: center;
              justify-content: center; font-family: "Oswald"; font-weight: 700; font-size: 150px; line-height: 1;
              color: var(--cream); background: rgba(12,12,14,0.86); border: 3px solid rgba(242,235,221,0.25); opacity: 0; }}
      .tile.pi {{ color: var(--red); border-color: var(--red); font-family: "Cormorant"; font-style: italic; }}
      .tile .x {{ position: absolute; left: 14px; top: 88px; width: 142px; height: 10px; border-radius: 5px; background: var(--red);
                 transform-origin: 0 50%; }}
      .ticker {{ left: 102px; width: 876px; height: 170px; overflow: hidden;
                -webkit-mask-image: linear-gradient(90deg, transparent 0, #000 12%, #000 88%, transparent 100%);
                mask-image: linear-gradient(90deg, transparent 0, #000 12%, #000 88%, transparent 100%); }}
      .ticker .run {{ position: absolute; left: 0; top: 0; white-space: nowrap; font-family: "Oswald"; font-weight: 700;
                     font-size: 150px; line-height: 1.1; color: var(--cream); text-shadow: 0 10px 34px rgba(0,0,0,0.5); }}
      .ticker .run b {{ color: var(--red); }}
      .greek {{ font-family: "Cormorant"; font-weight: 700; font-size: 132px; line-height: 1; color: #2A2219; white-space: nowrap; }}
      .greek span {{ display: inline-block; }}
      .greek .first {{ color: #C7271F; }}
      .lbl {{ font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.12em; text-transform: uppercase; color: #6A5A44; }}
      .kid {{ position: absolute; top: 112px; width: 34px; height: 74px; opacity: 0; }}
      .kid i {{ position: absolute; left: 7px; top: 0; width: 20px; height: 20px; border-radius: 10px; background: var(--cream); }}
      .kid u {{ position: absolute; left: 3px; top: 24px; width: 28px; height: 50px; border-radius: 14px 14px 6px 6px; background: var(--cream); }}
      .kid.dad i, .kid.dad u {{ background: var(--red); }}
      .brow {{ position: absolute; left: 190px; height: 64px; border-radius: 10px; transform-origin: 0 50%; }}
      .bname {{ position: absolute; left: 26px; width: 150px; font-family: "Manrope"; font-weight: 800; font-size: 26px;
               letter-spacing: 0.06em; text-transform: uppercase; color: rgba(242,235,221,0.85); }}
      .city {{ position: absolute; font-family: "Manrope"; font-weight: 800; font-size: 30px; letter-spacing: 0.04em; color: var(--cream);
              background: rgba(12,12,14,0.86); border: 2px solid rgba(242,235,221,0.3); border-radius: 30px; padding: 6px 18px; opacity: 0;
              white-space: nowrap; }}
      .city em {{ font-family: "Cormorant"; font-weight: 700; color: var(--red); font-size: 38px; margin-right: 6px; }}
      .city.home {{ border-color: var(--red); }}
      .fx {{ position: absolute; color: var(--cream); opacity: 0; }}
      .fx .katex-display {{ margin: 0; }}
      /* портреты в верхних углах — чуть меньше обычных: макушка при базе 1.2 высоко */
      #c-eul, #c-anna {{ top: 268px; width: 236px; padding: 12px 12px 10px; }}
      #c-eul {{ left: 716px; }} #c-anna {{ left: 128px; }}
      #c-eul .ph, #c-eul img, #c-anna .ph, #c-anna img {{ width: 212px; height: 220px; }}
      #c-eul .card-name, #c-anna .card-name {{ font-size: 20px; margin-top: 8px; }}
      #c-eul .card-sub, #c-anna .card-sub {{ font-size: 22px; }}
      /* подменённый фон за спиной: сверху, низ переходит в родной кадр (там руки) */
      .bg {{ left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden;
             -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%);
             mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%); }}
      .bg img {{ position: absolute; left: -54px; top: -96px; width: 1188px; height: 2112px; object-fit: cover; }}
      .bg .vig {{ position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 38%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.6) 100%); }}
      #censor-bar {{ position: absolute; top: 40px; height: 250px; border-radius: 18px; background: #0C0C0D;
                    display: flex; align-items: center; justify-content: center; box-shadow: 0 20px 60px rgba(0,0,0,0.6); }}
      #censor-bar b {{ font-family: "Manrope"; font-weight: 800; font-size: 40px; color: #fff; background: var(--red);
                      padding: 10px 26px; border-radius: 40px; letter-spacing: 0.1em; }}
'''


def bg(bid: str, img: str) -> str:
    return f'        <div id="{bid}" class="g bg"><img src="assets/img/{img}" alt="" /><div class="vig"></div></div>'


def bg_in(sel: str, a: float, b: float) -> str:
    """Фон наплывом со смазом, медленный наезд внутри, уход со смазом; на показе резкий."""
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.08, filter: BLUR(14) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.45, ease: "power2.out" }}, {a});\n'
            f'      tl.fromTo("{sel} img", {{ scale: 1 }}, {{ scale: 1.06, duration: {b - a + 0.35:.2f}, ease: "none" }}, {a});\n'
            f'      tl.to("{sel}", {{ opacity: 0, scale: 1.04, filter: BLUR(12), duration: 0.35, ease: "power2.in" }}, {b});')


def tex(s: str) -> str:
    return f'<span class="katex-src" data-tex="{s}"></span>'


def sticker(sid: str, text: str, left: int, top: int = 300) -> str:
    return f'        <div id="{sid}" class="g sticker" style="left: {left}px; top: {top}px; font-size: 56px; white-space: nowrap;">{text}</div>'


ARROW = 'fill="none" stroke="#F2EBDD" stroke-width="5" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"'

# 1. буквы: π против З, Д, С — над головой
letters = ('        <div id="p-let" class="g" style="left: 165px; top: 300px; width: 750px; height: 190px;">\n'
           '          <div id="l-pi" class="tile pi" style="left: 0;">π</div>\n'
           '          <div id="l-z" class="tile" style="left: 193px;">З<div class="x"></div></div>\n'
           '          <div id="l-d" class="tile" style="left: 386px;">Д<div class="x"></div></div>\n'
           '          <div id="l-s" class="tile" style="left: 579px;">С<div class="x"></div></div>\n'
           '        </div>')

# 2. π = C/d: окружность, диаметр, развёртка длины в три диаметра с хвостиком — на груди
R, CX, CY = 70, 110, 120
L0, LY = 40, 268
circ = round(2 * 3.14159265 * R)            # 440 px — длина окружности на развёртке
ticks = "".join(f'<line class="tk" x1="{L0 + 2 * R * k}" y1="{LY - 16}" x2="{L0 + 2 * R * k}" y2="{LY + 16}" />' for k in range(4))
circle = (f'        <div id="p-circ" class="g panel" {SAFE} style="left: 245px; top: {CHEST}px; width: 590px; height: 330px;">\n'
          '          <svg viewBox="0 0 590 330" style="position: absolute; left: 0; top: 0; width: 590px; height: 330px;">\n'
          f'            <circle id="cc" cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="#F2EBDD" stroke-width="7" pathLength="1" '
          f'stroke-dasharray="1" stroke-dashoffset="1" transform="rotate(90 {CX} {CY})" />\n'
          f'            <path id="cd" d="M {CX - R} {CY} L {CX + R} {CY}" fill="none" stroke="#F0352C" stroke-width="7" stroke-linecap="round" '
          'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />\n'
          f'            <path id="cl" d="M {L0} {LY} L {L0 + circ} {LY}" fill="none" stroke="#F2EBDD" stroke-width="7" stroke-linecap="round" '
          'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />\n'
          f'            <g id="cticks" stroke="#F0352C" stroke-width="6" stroke-linecap="round" opacity="0">{ticks}</g>\n'
          '          </svg>\n'
          f'          <div id="cf" class="fx" style="left: 250px; top: 18px; width: 320px; text-align: center; font-size: 64px;">{tex(r"\pi = \dfrac{C}{d}")}</div>\n'
          f'          <div id="cn" class="fx" style="left: {L0 + 3 * 2 * R - 6}px; top: 190px; width: 170px; font-family: Oswald; font-weight: 700; '
          'font-size: 44px; color: #F0352C;">≈ 3,14</div>\n'
          '        </div>')

# 3. περιφέρεια: первая буква — π — бумажкой на груди
greek_word = "".join(f'<span{" class=first id=g-pi" if k == 0 else ""}>{ch}</span>' for k, ch in enumerate("περιφέρεια"))
greek = (f'        <div id="p-greek" class="g paper" {SAFE} style="left: 195px; top: {CHEST}px; width: 690px; padding: 26px 40px 30px; text-align: center;">\n'
         '          <div class="lbl">окружность по-гречески</div>\n'
         f'          <div class="greek" style="margin-top: 10px;">{greek_word}</div>\n'
         '          <div id="g-note" class="lbl" style="margin-top: 8px; color: #C7271F; opacity: 0;">первая буква — π</div>\n'
         '        </div>')

# 4. знаки π бегут без конца — над головой
ticker = (f'        <div id="p-tick" class="g ticker" data-safe="бегущая строка обрезана маской в 102–978 px, за край кадра не выходит" style="top: {UP}px;">'
          f'<div id="tick-run" class="run"><b>π</b> = {PI}</div></div>')

# 5. 13 детей: 13 фигурок в ряд на груди
kids = "".join(f'<div class="kid" style="left: {38 + k * 40}px;"><i></i><u></u></div>' for k in range(13))
family = (f'        <div id="p-kids" class="g panel" {SAFE} style="left: 245px; top: {CHEST}px; width: 590px; height: 210px;">\n'
          '          <div class="bname" style="left: 30px; top: 26px; width: 530px; font-size: 28px;">у Эйлера детей:</div>\n'
          '          <div id="kids-n" style="position: absolute; right: 34px; top: 4px; font-family: Oswald; font-weight: 700; font-size: 96px; '
          'line-height: 1; color: #F0352C;">0</div>\n'
          f'          {kids}\n        </div>')

# 6. на что шли деньги: двор против академии — столбики на груди
money = (f'        <div id="p-money" class="g panel" {SAFE} style="left: 245px; top: {CHEST}px; width: 590px; height: 200px;">\n'
         '          <div class="bname" style="top: 44px;">балы</div>\n'
         '          <div id="m-court" class="brow" style="top: 30px; width: 360px; background: var(--red);"></div>\n'
         '          <div class="bname" style="top: 124px;">академия</div>\n'
         '          <div id="m-acad" class="brow" style="top: 110px; width: 26px; background: var(--cream);"></div>\n'
         '        </div>')

# 7. π пишется сам — над головой
pen = ('        <svg id="p-pen" class="g" viewBox="0 0 240 200" style="left: 420px; top: 290px; width: 240px; height: 200px;">'
       '<g fill="none" stroke="#F0352C" stroke-width="16" stroke-linecap="round" stroke-linejoin="round">'
       '<path id="pen1" d="M 22 48 Q 60 22 118 30 L 222 26" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />'
       '<path id="pen2" d="M 88 34 Q 88 120 50 182" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />'
       '<path id="pen3" d="M 160 30 L 158 150 Q 160 184 206 170" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />'
       '</g></svg>')

# 8. Европа переняла: от Петербурга к столицам науки — над головой
CITIES = [("c-spb", "Петербург", 400, 300, True), ("c-ber", "Берлин", 170, 400, False), ("c-par", "Париж", 120, 500, False),
          ("c-lon", "Лондон", 640, 400, False), ("c-bas", "Базель", 700, 500, False)]
links = "".join(f'<path id="ln{k}" d="M 540 340 L {x + 80} {y + 24}" {ARROW} />' for k, (_, _, x, y, _) in enumerate(c for c in CITIES if not c[4]))
europe = ('        <div id="p-eu" class="g" style="left: 0; top: 0; width: 1080px; height: 570px;">\n'
          f'          <svg viewBox="0 0 1080 570" style="position: absolute; left: 0; top: 0; width: 1080px; height: 570px;">{links}</svg>\n'
          + "".join(f'          <div id="{cid}" class="city{" home" if home else ""}" style="left: {x}px; top: {y}px;"><em>π</em>{name}</div>\n'
                    for cid, name, x, y, home in CITIES)
          + '        </div>')

# документ: титул «Механики» 1736 — снизу
mech = (f'        <div id="d-mech" class="g doc" {SAFE} style="left: 330px; top: {CHEST}px; width: 420px; padding: 14px;">\n'
        '          <div style="width: 392px; height: 300px; overflow: hidden;"><img src="assets/img/mechanica.jpg" alt="" '
        'style="display: block; width: 392px; height: 300px; object-fit: cover; object-position: 50% 30%;" /></div>\n'
        '          <div class="doc-cap">Эйлер, «Механика», 1736</div>\n        </div>')

# ЕГЭ: бланк с формулой, где стоит π — снизу
ege = (f'        <div id="d-ege" class="g ege" {SAFE} style="left: 225px; top: {CHEST}px; width: 630px;">\n'
       '          <div class="ege-head">ЕГЭ · профиль · справочные материалы</div>\n'
       f'          <div class="fx" id="ege-f" style="position: relative; opacity: 1; margin-top: 12px; text-align: center; font-size: 58px; color: #1A1A1A;">'
       f'{tex(r"S = \pi R^2 \qquad C = 2\pi R")}</div>\n'
       '        </div>')

behind = "\n".join([
    '        <div id="b-one" class="g big" style="top: 300px; font-size: 230px;"><span class="red">1</span> число</div>',
    '        <div id="b-pi" class="g big serif" data-safe="строка π заходит в шапку, сам знак в Cormorant сидит низко — ниже 300 px, над головой" style="top: 110px; font-size: 470px; text-transform: none; font-style: italic;">π</div>',
    bg("bg-spb", "bg_spb.jpg"),
    bg("bg-kunst", "bg_kunst.jpg"),
    bg("bg-court", "bg_court.jpg"),
    '        <div id="b-pz-lead" class="g lead" style="top: 262px;">тем более слово</div>',
    '        <div id="b-pz" class="g" style="left: 0; top: 300px; width: 1080px; height: 330px;">'
    '<div style="position: absolute; left: 0; width: 1080px; text-align: center; font-family: Oswald; font-weight: 700; font-size: 250px; '
    'line-height: 1.1; color: var(--cream); text-shadow: 0 12px 40px rgba(0,0,0,0.35);"><span style="font-family: Cormorant; font-style: italic;">π</span>ЗДЕЦ</div>'
    '<div id="censor-bar" style="left: 395px; width: 600px;"><b>пип</b></div></div>',
    '        <div id="b-year-lead" class="g lead" style="top: 262px;">эйлер пишет π с</div>',
    '        <div id="b-year" class="g big" style="top: 300px; font-size: 250px;"><span id="b-year-n">1700</span></div>',
    '        <div id="b-inf-lead" class="g lead" style="top: 262px;">знаков после запятой</div>',
    '        <div id="b-inf" class="g big" data-safe="строка ∞ заходит в шапку, сам знак в Oswald посередине строки — ниже 300 px" style="top: 140px; font-size: 380px; color: var(--red);">∞</div>',
])

front = "\n".join([
    sticker("st-all", "вся ситуация в стране", 250),
    sticker("st-wtf", "какого чёрта π?", 330),
    letters,
    sticker("st-greek", "откуда у греков?", 300),
    sticker("st-spb", "ответ — в Петербурге", 270),
    sticker("st-rus", "и мы, русские, тоже", 280),
    circle,
    '        <div id="st-mem" class="g stamp" style="left: 210px; top: 300px; font-size: 80px; background: rgba(12,12,14,0.55); white-space: nowrap;">просто запомни</div>',
    greek,
    sticker("st-zh", "π = полная жопа", 300),
    ticker,
    '        <div id="st-nu" class="g stamp" style="left: 187px; top: 300px; font-size: 92px; background: rgba(12,12,14,0.55); white-space: nowrap;">но есть нюанс</div>',
    ege,
    sticker("st-notgr", "не благодаря грекам", 260, 300),
    card("c-eul", "euler.jpg", "Леонард Эйлер", "тот самый товарищ", side="right"),
    family,
    card("c-anna", "anna.jpg", "Анна Иоанновна", "царица, 1730–1740", side="left"),
    sticker("st-b1", "балы", 200, 300),
    sticker("st-b2", "фейерверки", 600, 300),
    sticker("st-b3", "свадьбы", 390, 420),
    money,
    sticker("st-und", "Эйлер всё понимал", 290),
    pen,
    mech,
    europe,
    sticker("st-notonly", "π — это не только…", 290),
    sticker("st-dum", "как на Думской", 330),
    '        <div id="n-80" class="g big" style="top: 300px; font-size: 200px;">ЕГЭ <span id="n-80-n" class="red">0</span><span class="red">+</span></div>',
])

PANEL_IN = '{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }'


def eq(sel: str, at: float) -> str:
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.5, filter: BLUR(10) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.18, ease: "power4.out" }}, {at});')


def tile(sel: str, at: float) -> str:
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, y: -80, scale: 0.6, filter: BLUR(10) }}, '
            f'{{ opacity: 1, y: 0, scale: 1, filter: BLUR(0), duration: 0.22, ease: "back.out(2)" }}, {at});')


def strike(sel: str, at: float) -> str:
    # трансформ целиком у GSAP (lint: gsap_css_transform_conflict); fromTo сразу ставит scaleX 0
    return (f'      tl.fromTo("{sel} .x", {{ rotation: -24, scaleX: 0 }}, '
            f'{{ rotation: -24, scaleX: 1, duration: 0.14, ease: "power2.out" }}, {at});')


beats = f'''
      // ---------- хук: одно число на всю страну — π ----------
      slam("#b-one", {t(1.32)}, {{ fromScale: 1.5 }});
      leave("#b-one", {t(2.36)}, {{ y: -60 }});
      enter("#st-all", {t(2.62)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-all", {t(4.55)}, {{ y: -30, rot: -10 }});
      slam("#b-pi", {t(5.76)}, {{ fromScale: 1.6, blur: 18 }});
      leave("#b-pi", {t(6.62)}, {{ scale: 0.5, y: -120, rot: -20 }});

      // ---------- почему π, а не З, Д или С ----------
      enter("#st-wtf", {t(6.72)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-wtf", {t(7.95)}, {{ y: -30, rot: 10 }});
{tile("#l-pi", t(8.12))}
      tl.set("#p-let", {{ opacity: 1 }}, {t(8.10)});
{tile("#l-z", t(9.28))}
{tile("#l-d", t(9.68))}
{tile("#l-s", t(10.12))}
{strike("#l-z", t(10.30))}
{strike("#l-d", t(10.36))}
{strike("#l-s", t(10.42))}
      tl.fromTo("#l-pi", {{ scale: 1 }}, {{ scale: 1.12, duration: 0.18, yoyo: true, repeat: 1, ease: "sine.inOut", immediateRender: false }}, {t(10.42)});
      leave("#p-let", {t(10.72)}, {{ y: -60 }});
      enter("#st-greek", {t(11.04)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-greek", {t(12.85)}, {{ y: -30, rot: -10 }});

      // ---------- Петербург за спиной ----------
{bg_in("#bg-spb", t(13.10), t(17.20))}
      enter("#st-spb", {t(13.94)}, {{ fromScale: 0.6, rot: 3 }});
      leave("#st-spb", {t(15.10)}, {{ y: -30, rot: 10 }});
      enter("#st-rus", {t(15.36)}, {{ fromScale: 0.6, rot: -3 }});
      leave("#st-rus", {t(17.10)}, {{ y: -30, rot: -10 }});

      // ---------- π = C/d: окружность, развёртка, три диаметра с хвостиком ----------
      enter("#p-circ", {t(17.40)}, {PANEL_IN});
      draw("#cc", {t(19.44)}, 0.5);
      draw("#cl", {t(19.50)}, 0.5);
      draw("#cd", {t(20.24)}, 0.3);
      tl.fromTo("#cticks", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.15 }}, {t(20.50)});
{eq("#cf", t(20.80))}
{eq("#cn", t(21.10))}
      slam("#st-mem", {t(22.04)}, {{ fromScale: 2.0, rot: -5, blur: 10 }});
      leave("#st-mem", {t(22.70)}, {{ scale: 0.6, y: 0, rot: -14 }});
      leave("#p-circ", {t(22.70)}, {{ y: 80 }});

      // ---------- περιφέρεια → π ----------
      enter("#p-greek", {t(24.30)}, {PANEL_IN});
      tl.fromTo("#p-greek .greek span", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.12, stagger: 0.04, ease: "power2.out" }}, {t(25.58)});
      tl.fromTo("#g-pi", {{ scale: 1 }}, {{ scale: 1.5, y: -14, duration: 0.2, ease: "back.out(2)", immediateRender: false }}, {t(26.74)});
      enter("#g-note", {t(26.80)}, {{ fromScale: 0.8, dur: 0.25 }});
      leave("#p-greek", {t(28.00)}, {{ y: 80 }});
      enter("#st-zh", {t(28.44)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-zh", {t(30.30)}, {{ y: -30, rot: -10 }});

      // ---------- знаки π без конца ----------
      enter("#p-tick", {t(30.50)}, {{ fromScale: 0.9, dur: 0.3 }});
      tl.fromTo("#tick-run", {{ x: 60 }}, {{ x: -4200, duration: 3.6, ease: "power1.in" }}, {t(30.50)});
      leave("#p-tick", {t(34.00)}, {{ y: -40 }});
      slam("#st-nu", {t(34.54)}, {{ fromScale: 2.0, rot: -4, blur: 10 }});
      leave("#st-nu", {t(35.24)}, {{ scale: 0.6, y: 0, rot: -14 }});

      // ---------- на ЕГЭ π стоит благодаря Эйлеру ----------
      doc("#d-ege", {t(35.40)}, {t(39.20)}, {{ fromRot: -5, rot: 1 }});
      enter("#st-notgr", {t(37.94)}, {{ fromScale: 0.6, rot: 3 }});
      leave("#st-notgr", {t(39.30)}, {{ y: -30, rot: 10 }});
      card("#c-eul", {t(40.90)}, {t(44.95)}, "right");
      enter("#p-kids", {t(43.30)}, {PANEL_IN});
      tl.fromTo("#p-kids .kid", {{ opacity: 0, y: 40, scale: 0.4 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.16, ease: "back.out(2)", stagger: 0.05 }}, {t(44.20)});
      tl.fromTo("#kids-n", {{ textContent: 0 }}, {{ textContent: 13, snap: {{ textContent: 1 }}, duration: 0.65, ease: "none", immediateRender: false }}, {t(44.20)});
      leave("#p-kids", {t(45.70)}, {{ y: 80 }});

      // ---------- Академия, Анна Иоанновна, балы ----------
{bg_in("#bg-kunst", t(45.86), t(49.40))}
      card("#c-anna", {t(48.18)}, {t(50.70)}, "left");
{bg_in("#bg-court", t(49.34), t(53.50))}
      enter("#st-b1", {t(50.98)}, {{ fromScale: 0.6, rot: -5 }});
      enter("#st-b2", {t(52.12)}, {{ fromScale: 0.6, rot: 4 }});
      enter("#st-b3", {t(52.90)}, {{ fromScale: 0.6, rot: -3 }});
      leave(["#st-b1", "#st-b2", "#st-b3"], {t(53.50)}, {{ y: -30 }});
      enter("#p-money", {t(53.54)}, {PANEL_IN});
      bars("#m-court", {t(53.70)});
      bars("#m-acad", {t(54.36)});
      tl.to("#m-acad", {{ backgroundColor: "#F0352C", duration: 0.2, yoyo: true, repeat: 1, immediateRender: false }}, {t(54.80)});
      leave("#p-money", {t(55.50)}, {{ y: 80 }});
      enter("#st-und", {t(55.60)}, {{ fromScale: 0.6, rot: 3 }});
      leave("#st-und", {t(57.80)}, {{ y: -30, rot: 10 }});
      tl.set("#p-pen", {{ opacity: 1 }}, {t(57.92)});
      draw("#pen1", {t(57.92)}, 0.3);
      draw("#pen2", {t(58.24)}, 0.25);
      draw("#pen3", {t(58.52)}, 0.3);
      leave("#p-pen", {t(59.85)}, {{ y: -40, rot: 12 }});

      // ---------- панчлайн под «пип» ----------
      enter("#b-pz-lead", {t(60.16)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-pz", {t(61.22)}, {{ fromScale: 1.5 }});
      tl.fromTo("#censor-bar", {{ scaleX: 0, transformOrigin: "0 50%" }}, {{ scaleX: 1, duration: 0.1, ease: "power3.out", immediateRender: false }}, {t(61.30)});
      leave(["#b-pz", "#b-pz-lead"], {t(62.70)}, {{ y: -60 }});

      // ---------- 1736: Эйлер пишет π, Европа перенимает ----------
      enter("#b-year-lead", {t(62.90)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-year", {t(63.14)}, {{ fromScale: 1.3 }});
      tl.fromTo("#b-year-n", {{ textContent: 1700 }}, {{ textContent: 1736, snap: {{ textContent: 1 }}, duration: 0.8, ease: "power2.out",
                immediateRender: false }}, {t(63.14)});
      leave(["#b-year", "#b-year-lead"], {t(66.90)}, {{ y: -60 }});
      doc("#d-mech", {t(64.60)}, {t(67.20)}, {{ fromRot: 6, rot: -2 }});
      tl.set("#p-eu", {{ opacity: 1 }}, {t(67.30)});
      enter("#c-spb", {t(67.30)}, {{ fromScale: 0.6, dur: 0.25 }});
      draw("#ln0", {t(68.70)}, 0.3);
      enter("#c-ber", {t(68.90)}, {{ fromScale: 0.6, dur: 0.22 }});
      draw("#ln1", {t(68.95)}, 0.3);
      enter("#c-par", {t(69.15)}, {{ fromScale: 0.6, dur: 0.22 }});
      draw("#ln2", {t(69.20)}, 0.3);
      enter("#c-lon", {t(69.40)}, {{ fromScale: 0.6, dur: 0.22 }});
      draw("#ln3", {t(69.45)}, 0.3);
      enter("#c-bas", {t(69.65)}, {{ fromScale: 0.6, dur: 0.22 }});
      leave("#p-eu", {t(70.80)}, {{ y: -40 }});

      // ---------- Думская и знаки без конца ----------
      enter("#st-notonly", {t(71.20)}, {{ fromScale: 0.6, rot: 3 }});
      leave("#st-notonly", {t(72.50)}, {{ y: -30, rot: 10 }});
      enter("#st-dum", {t(72.74)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-dum", {t(74.20)}, {{ y: -30, rot: -10 }});
      enter("#b-inf-lead", {t(75.26)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-inf", {t(75.62)}, {{ fromScale: 1.5 }});
      tl.fromTo("#b-inf", {{ rotation: 0 }}, {{ rotation: 8, duration: 1.0, ease: "sine.inOut", immediateRender: false }}, {t(75.80)});
      leave(["#b-inf", "#b-inf-lead"], {t(77.00)}, {{ y: -60 }});

      // ---------- CTA: ЕГЭ на 80+ над головой ----------
      enter("#n-80", {t(80.70)}, {{ fromScale: 0.7, dur: 0.3 }});
      tl.fromTo("#n-80-n", {{ textContent: 0 }}, {{ textContent: 80, snap: {{ textContent: 1 }}, duration: 0.6, ease: "power2.out",
                immediateRender: false }}, {t(80.70)});
      leave("#n-80", {t(82.60)}, {{ y: -60 }});
'''

# Звуки — мало (бриф few), правила 12.10: удары только на главном, семейства не подряд, файл ≤ 2,
# между звуками ≥ 1 с. На «пип» своего звука нет — там тон самого «пипа». Финальный pop — у плашки.
sounds = [
    audio("pi", "whoosh", t(5.74), 0.8),
    audio("nuans", "impact-bass-1", t(34.52), 0.9),
    audio("euler", "pop", t(40.88), 0.7),
    audio("year", "impact-bass-2", t(63.12), 0.8),
    audio("inf", "whoosh-cinematic", t(75.60), 0.7),
]
CTA_AT = t(77.40)
# человек поверх слов и фонов за спиной: 1 число, π, Петербург, Академия + двор, π-здец, 1736, ∞
fg = [(t(1.25), t(2.70)), (t(5.70), t(6.95)), (t(13.05), t(17.65)), (t(45.80), t(53.95)),
      (t(60.10), t(63.00)), (t(63.05), t(67.20)), (t(75.20), t(77.30))]

page = build_page("π — откуда буква", DUR, behind, front, beats, sounds, fg, cta_at=CTA_AT,
                  extra_css=css, fmt=tk.fmt, captions=tk.captions)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

fixes = tk.fixes({112: "ЕГЭ", 167: "Эйлер", 177: "***"})

director = {
    "_note": "π и Эйлер. Время по дублю; раскладка — work/IMG_1818/page.py, план — plan.md.",
    "punches": [[t(5.76), t(6.60), 1.22, 0.10], [t(34.54), t(35.20), 1.18, 0.10], [t(61.22), t(62.60), 1.22, 0.10],
                [t(63.14), t(64.40), 1.16, 0.10], [t(75.62), t(76.90), 1.18, 0.10]],
    "text_fixes": fixes,
    # compose сравнивает слово без знаков препинания по краям
    "keep_case": ["Пи", "ЕГЭ", "Эйлер", "Петербурге", "Петербургской", "Анне", "Иоанновне", "Европа", "Думской", "З", "Д", "С"],
    "accent_words": ["Пи", "периферия", "бесконечное", "Эйлер", "1736", "***"],
    # плашки на груди стоят на уровне субтитров — на их время субтитров нет
    "hide_captions": [[t(17.35), t(23.00)], [t(24.25), t(28.30)], [t(35.35), t(39.55)], [t(43.25), t(46.00)],
                      [t(53.50), t(55.80)], [t(64.55), t(67.55)], [round(CTA_AT - 0.05, 2), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
