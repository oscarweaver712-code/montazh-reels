"""Страница графики IMG_1816: «π = …» — откуда у числа π его буква (короткий дубль, без 1736 года).

Запасной дубль IMG_1818 (правило 6 rules.md); смонтирован по прямой просьбе из студии 16.10.2026.
Стиль — проекта (rules.md п.14, образец IMG_1799 v5): крупное — Oswald заглавными, крем/красный, подвод —
Manrope разрядкой, штамп — красная рамка с наклоном, формулы — Cormorant/KaTeX; тёмных плашек нет, текст
прямо в кадре — за головой или на груди; смена плана — tk.framing, акценты — tk.punch.
Время ударов — по исходнику, на шкалу дубля (trim 0.72–67.20, вырезов нет) переводит Take. План — plan.md.
«пиздец» (62.86–63.26) — под «пип» в edit.json, в субтитрах «***», за спиной — «πЗДЕЦ» с цензурной плашкой
поверх «ЗДЕЦ»: шутка читается, слова нет.
Проверено (как в IMG_1818):
  π = C/d (длина окружности к диаметру) — верно; 3,14159265358979323846264338327950288419716939937510… —
  первые 50 знаков сверены. περιφέρεια (периферия, «окружность») начинается с π — верно.
  Эйлер: 13 детей (выжили пятеро) — верно; в Петербургской академии с 1727, Анна Иоанновна правила
  1730–1740 — верно; π у Эйлера — с «Механики» 1736 г., массово — после «Введения в анализ» 1748 г.
  «Не благодаря грекам» — оценка автора: первым π так записал Уильям Джонс (1706); на экран не выносим — в отчёт.
Распознавание: «Ивановне» → «Иоанновне», «Эллер» → «Эйлер», «емкое» → «ёмкое», тире-слова whisper убраны.
Картинки — Wikimedia Commons, те же, что у парного дубля: work/IMG_1818/downloads (качал work/IMG_1818/fetch.py,
лицензии и авторы — downloads/candidates.json); что выбрано — PICK ниже.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, card  # noqa: E402

STEM = "IMG_1816"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
IMG = ROOT / f"studio/{STEM}/assets/img"
IMG.mkdir(parents=True, exist_ok=True)
SRC = ROOT / "work/IMG_1818/downloads"      # парный дубль: картинки уже отобраны глазами
PICK = {"euler.jpg": "euler_1.jpg", "anna.jpg": "anna_1.jpg",
        "bg_spb.jpg": "spb_1.jpg", "bg_kunst.jpg": "kunst_1.jpg", "bg_court.jpg": "court_1.jpg"}
for dst_name, src_name in PICK.items():
    src = SRC / src_name
    if not src.exists():
        sys.exit(f"✗ нет {src} — запусти work/IMG_1818/fetch.py (картинки с Wikimedia Commons)")
    dst = IMG / dst_name
    if not (dst.exists() and dst.samefile(src)):
        shutil.copyfile(src, dst)

CHEST = 1290        # верх текста на груди: подбородок с камерой доходит до y ~1258 (как в IMG_1799)
HEAD = 290          # верх текста за головой: вкладки TikTok — до y 260; макушка ~y 570
RED, CREAM = "#F0352C", "#F2EBDD"
SHADOW = "0 3px 8px rgba(0,0,0,0.65), 0 14px 46px rgba(0,0,0,0.55)"
SAFE = 'data-safe="лицо важнее серой зоны: текст ниже подбородка (Валера, 12.10)"'
PI = "3,14159265358979323846264338327950288419716939937510582097494459230781640628620899862803482534211706798…"

css = f'''      .tx {{ left: 0; width: 1080px; text-align: center; white-space: nowrap; }}
      .tx-lead {{ font-family: "Manrope"; font-weight: 800; font-size: 36px; letter-spacing: 0.24em; text-transform: uppercase;
                 color: var(--cream); text-shadow: {SHADOW}; }}
      .tx-big {{ font-family: "Oswald"; font-weight: 700; text-transform: uppercase; line-height: 0.9; letter-spacing: -0.01em;
                color: var(--cream); text-shadow: {SHADOW}; }}
      .tx span {{ display: inline-block; }}
      .katex-src, .katex-display {{ margin: 0 !important; display: inline-block; }}
      .wide-svg {{ position: absolute; left: 0; top: 0; overflow: visible; filter: drop-shadow(0 10px 26px rgba(0,0,0,0.55)); }}
      .tile {{ position: absolute; top: 0; width: 170px; height: 200px; display: flex; align-items: center; justify-content: center;
              font-family: "Oswald"; font-weight: 700; font-size: 190px; line-height: 1; color: var(--cream);
              text-shadow: {SHADOW}; opacity: 0; }}
      .tile.pi {{ color: var(--red); font-family: "Cormorant"; font-style: italic; }}
      .tile .x {{ position: absolute; left: 10px; top: 96px; width: 150px; height: 14px; border-radius: 7px; background: var(--red);
                 transform-origin: 0 50%; box-shadow: 0 4px 14px rgba(0,0,0,0.5); }}
      .ticker {{ left: 102px; width: 876px; height: 180px; overflow: hidden;
                -webkit-mask-image: linear-gradient(90deg, transparent 0, #000 12%, #000 88%, transparent 100%);
                mask-image: linear-gradient(90deg, transparent 0, #000 12%, #000 88%, transparent 100%); }}
      .ticker .run {{ position: absolute; left: 0; top: 0; white-space: nowrap; font-family: "Oswald"; font-weight: 700;
                     font-size: 150px; line-height: 1.1; color: var(--cream); text-shadow: {SHADOW}; }}
      .ticker .run b {{ color: var(--red); font-family: "Cormorant"; font-style: italic; }}
      .greek {{ font-family: "Cormorant"; font-weight: 700; font-size: 132px; line-height: 1; color: #2A2219; white-space: nowrap; }}
      .greek span {{ display: inline-block; }}
      .greek .first {{ color: #C7271F; }}
      .lbl {{ font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.12em; text-transform: uppercase; color: #6A5A44; }}
      .kid {{ position: absolute; top: 96px; width: 34px; height: 74px; opacity: 0; filter: drop-shadow(0 6px 14px rgba(0,0,0,0.6)); }}
      .kid i {{ position: absolute; left: 7px; top: 0; width: 20px; height: 20px; border-radius: 10px; background: var(--cream); }}
      .kid u {{ position: absolute; left: 3px; top: 24px; width: 28px; height: 50px; border-radius: 14px 14px 6px 6px; background: var(--cream); }}
      .brow {{ position: absolute; left: 230px; height: 56px; border-radius: 8px; transform-origin: 0 50%;
              box-shadow: 0 14px 40px rgba(0,0,0,0.5); }}
      .bname {{ position: absolute; left: 0; width: 210px; text-align: right; font-family: "Manrope"; font-weight: 800; font-size: 30px;
               letter-spacing: 0.14em; text-transform: uppercase; color: var(--cream); text-shadow: {SHADOW}; }}
      .fx {{ position: absolute; color: var(--cream); opacity: 0; text-shadow: {SHADOW}; }}
      .fx .katex-display {{ margin: 0; }}
      /* портреты в верхних углах — компактнее: макушка при базе 1.2 высоко */
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
      /* финальная плашка тоже без рамки — как весь текст ролика (IMG_1799 v5) */
      .cta {{ background: none; border: none; box-shadow: none; padding: 0; }}
      .cta-big {{ font-size: 112px; text-shadow: {SHADOW}; }}
      .cta-small {{ text-shadow: {SHADOW}; }}
'''


def tex(src: str) -> str:
    return f'<span class="katex-src" data-tex="{src}"></span>'


def lead(lid: str, text: str, top: int, color: str = CREAM, extra: str = "") -> str:
    return f'        <div id="{lid}" class="g tx tx-lead" {extra} style="top: {top}px; color: {color};">{text}</div>'


def big(bid: str, inner: str, top: int, size: int, color: str = CREAM, extra: str = "") -> str:
    return f'        <div id="{bid}" class="g tx tx-big" {extra} style="top: {top}px; font-size: {size}px; color: {color};">{inner}</div>'


def stamp(sid: str, text: str, top: int = HEAD, size: int = 120) -> str:
    return (f'        <div id="{sid}" class="g tx" style="top: {top}px;">'
            f'<span class="stamp" style="font-size: {size}px; display: inline-block; transform: rotate(-4deg);">{text}</span></div>')


def bg(bid: str, img: str) -> str:
    return f'        <div id="{bid}" class="g bg"><img src="assets/img/{img}" alt="" /><div class="vig"></div></div>'


DRAW = 'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"'

# 1. буквы: π против З, Д, С — над головой
letters = (f'        <div id="p-let" class="g" style="left: 165px; top: {HEAD}px; width: 750px; height: 200px;">\n'
           '          <div id="l-pi" class="tile pi" style="left: 0;">π</div>\n'
           '          <div id="l-z" class="tile" style="left: 193px;">З<div class="x"></div></div>\n'
           '          <div id="l-d" class="tile" style="left: 386px;">Д<div class="x"></div></div>\n'
           '          <div id="l-s" class="tile" style="left: 579px;">С<div class="x"></div></div>\n'
           '        </div>')

# 2. π = C/d: окружность, диаметр, развёртка длины в три диаметра с хвостиком — на груди, без подложки
R, CX, CY = 70, 110, 120
L0, LY = 40, 268
circ = round(2 * 3.14159265 * R)            # 440 px — длина окружности на развёртке
ticks = "".join(f'<line x1="{L0 + 2 * R * k}" y1="{LY - 16}" x2="{L0 + 2 * R * k}" y2="{LY + 16}" />' for k in range(4))
circle = (f'        <div id="p-circ" class="g" {SAFE} style="left: 245px; top: {CHEST}px; width: 590px; height: 330px;">\n'
          '          <svg class="wide-svg" viewBox="0 0 590 330" style="width: 590px; height: 330px;">\n'
          f'            <circle id="cc" cx="{CX}" cy="{CY}" r="{R}" fill="none" stroke="#F2EBDD" stroke-width="9" {DRAW} '
          f'transform="rotate(90 {CX} {CY})" />\n'
          f'            <path id="cd" d="M {CX - R} {CY} L {CX + R} {CY}" fill="none" stroke="#F0352C" stroke-width="9" stroke-linecap="round" {DRAW} />\n'
          f'            <path id="cl" d="M {L0} {LY} L {L0 + circ} {LY}" fill="none" stroke="#F2EBDD" stroke-width="9" stroke-linecap="round" {DRAW} />\n'
          f'            <g id="cticks" stroke="#F0352C" stroke-width="7" stroke-linecap="round" opacity="0">{ticks}</g>\n'
          '          </svg>\n'
          f'          <div id="cf" class="fx" style="left: 250px; top: 18px; width: 320px; text-align: center; font-size: 72px;">{tex(r"\pi = \dfrac{C}{d}")}</div>\n'
          f'          <div id="cn" class="fx" style="left: {L0 + 3 * 2 * R - 6}px; top: 186px; width: 170px; font-family: Oswald; font-weight: 700; '
          'font-size: 50px; color: #F0352C;">≈ 3,14</div>\n'
          '        </div>')

# 3. περιφέρεια: первая буква — π — бумажкой на груди (документ снизу)
greek_word = "".join(f'<span{" class=first id=g-pi" if k == 0 else ""}>{ch}</span>' for k, ch in enumerate("περιφέρεια"))
greek = (f'        <div id="p-greek" class="g paper" {SAFE} style="left: 195px; top: {CHEST}px; width: 690px; padding: 26px 40px 30px; text-align: center;">\n'
         '          <div class="lbl">окружность по-гречески</div>\n'
         f'          <div class="greek" style="margin-top: 10px;">{greek_word}</div>\n'
         '          <div id="g-note" class="lbl" style="margin-top: 8px; color: #C7271F; opacity: 0;">первая буква — π</div>\n'
         '        </div>')

# 4. знаки π бегут без конца — над головой
ticker = (f'        <div id="p-tick" class="g ticker" data-safe="бегущая строка обрезана маской в 102–978 px, за край кадра не выходит" style="top: {HEAD}px;">'
          f'<div id="tick-run" class="run"><b>π</b> = {PI}</div></div>')

# 5. 13 детей: 13 фигурок в ряд и счётчик — на груди
kids = "".join(f'<div class="kid" style="left: {38 + k * 40}px;"><i></i><u></u></div>' for k in range(13))
family = (f'        <div id="p-kids" class="g" {SAFE} style="left: 245px; top: {CHEST}px; width: 590px; height: 190px;">\n'
          f'          <div class="tx-lead" style="position: absolute; left: 0; top: 30px; width: 400px; text-align: left; font-size: 30px;">у Эйлера детей</div>\n'
          '          <div id="kids-n" class="tx-big" style="position: absolute; right: 20px; top: -6px; font-size: 110px; color: #F0352C;">0</div>\n'
          f'          {kids}\n        </div>')

# 6. на что шли деньги: балы против академии — столбики на груди
money = (f'        <div id="p-money" class="g" {SAFE} style="left: 140px; top: {CHEST}px; width: 800px; height: 200px;">\n'
         '          <div class="bname" style="top: 40px;">балы</div>\n'
         '          <div id="m-court" class="brow" style="top: 28px; width: 520px; background: var(--red);"></div>\n'
         '          <div class="bname" style="top: 124px;">академия</div>\n'
         '          <div id="m-acad" class="brow" style="top: 112px; width: 30px; background: var(--cream);"></div>\n'
         '        </div>')

# 7. π пишется сам — над головой
pen = (f'        <svg id="p-pen" class="g wide-svg" viewBox="0 0 240 200" style="left: 420px; top: {HEAD}px; width: 240px; height: 200px;">'
       '<g fill="none" stroke="#F0352C" stroke-width="18" stroke-linecap="round" stroke-linejoin="round">'
       f'<path id="pen1" d="M 22 48 Q 60 22 118 30 L 222 26" {DRAW} />'
       f'<path id="pen2" d="M 88 34 Q 88 120 50 182" {DRAW} />'
       f'<path id="pen3" d="M 160 30 L 158 150 Q 160 184 206 170" {DRAW} />'
       '</g></svg>')

# ЕГЭ: бланк с формулами, где стоит π — снизу
ege = (f'        <div id="d-ege" class="g ege" {SAFE} style="left: 200px; top: {CHEST}px; width: 680px;">\n'
       '          <div class="ege-head">ЕГЭ · профиль · справочные материалы</div>\n'
       f'          <div class="fx" id="ege-f" style="position: relative; opacity: 1; margin-top: 12px; text-align: center; font-size: 44px; color: #1A1A1A; text-shadow: none;">'
       f'{tex(r"S = \pi R^2 \qquad C = 2\pi R")}</div>\n'
       '        </div>')

# за головой — между фоном и вырезанным человеком (окна fg ниже)
behind = "\n".join([
    big("b-one", f'<span style="color: {RED};">1</span> число', 300, 230),
    '        <div id="b-pi" class="g big serif" data-safe="строка π заходит в шапку, сам знак в Cormorant сидит низко — ниже 300 px, над головой" '
    'style="top: 110px; font-size: 470px; text-transform: none; font-style: italic;">π</div>',
    bg("bg-spb", "bg_spb.jpg"),
    bg("bg-kunst", "bg_kunst.jpg"),
    bg("bg-court", "bg_court.jpg"),
    lead("b-pz-lead", "тем более слово", 262),
    # 180 px и верх 300: в наезде 1.36 макушка поднимается до y ~500 — 250 px слово закрывалось головой
    '        <div id="b-pz" class="g" style="left: 0; top: 300px; width: 1080px; height: 200px;">'
    '<div style="position: absolute; left: 0; width: 1080px; text-align: center; font-family: Oswald; font-weight: 700; font-size: 180px; '
    f'line-height: 1.05; color: var(--cream); text-shadow: {SHADOW};"><span style="font-family: Cormorant; font-style: italic; color: {RED};">π</span>ЗДЕЦ</div>'
    '<div id="censor-bar" style="left: 380px; width: 440px; top: 14px; height: 186px;"><b>пип</b></div></div>',
])

front = "\n".join([
    lead("st-all-lead", "одно число описывает", HEAD),
    big("st-all", "всю ситуацию<br>в стране", HEAD + 56, 104),
    big("st-wtf", f'какого чёрта <span style="color: {RED}; font-family: Cormorant; font-style: italic; text-transform: none;">π</span>?', HEAD, 110),
    letters,
    big("st-greek", "откуда у греков?", HEAD, 104),
    lead("st-spb-lead", "ответ кроется", HEAD),
    big("st-spb", "в Петербурге", HEAD + 56, 130, RED),
    big("st-rus", "и мы, русские,<br>тоже", HEAD, 104),
    circle,
    stamp("st-mem", "просто запомни", top=HEAD + 30, size=96),     # с наклоном и влётом ×2 заходил в шапку
    greek,
    big("st-zh", f'<span style="color: {RED}; font-family: Cormorant; font-style: italic; text-transform: none;">π</span> = полная жопа', HEAD, 104),
    ticker,
    stamp("st-nu", "но есть нюанс", size=110),
    ege,
    big("st-notgr", "не благодаря<br>грекам", HEAD, 104),
    card("c-eul", "euler.jpg", "Леонард Эйлер", "тот самый товарищ", side="right"),
    family,
    stamp("st-nif", "нифига себе", size=104),
    lead("st-acad-lead", "петербургская", CHEST, CREAM, SAFE),
    big("st-acad", "академия наук", CHEST + 56, 100, extra=SAFE),
    card("c-anna", "anna.jpg", "Анна Иоанновна", "царица, 1730–1740", side="left"),
    big("st-b1", "балы", HEAD, 110),
    big("st-b2", "фейерверки", HEAD, 110, RED),
    big("st-b3", "свадьбы", HEAD, 110),
    money,
    big("st-und", "Эйлер всё<br>понимал", HEAD, 104),
    pen,
])

TX_IN = '{ fromY: 60, fromScale: 0.9, dur: 0.3, ease: "power3.out" }'
PANEL_IN = '{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }'


def word_in(sel: str, at: float, out: float) -> str:
    """Крупное слово над головой: впечатывается и уходит вверх."""
    return (f'      slam("{sel}", {at}, {{ fromScale: 1.35, blur: 8 }});\n'
            f'      leave("{sel}", {out}, {{ y: -20 }});')


def bg_in(sel: str, a: float, b: float) -> str:
    """Фон наплывом со смазом, медленный наезд внутри, уход со смазом; на показе резкий."""
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.08, filter: BLUR(14) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.45, ease: "power2.out" }}, {a});\n'
            f'      tl.fromTo("{sel} img", {{ scale: 1 }}, {{ scale: 1.06, duration: {b - a + 0.35:.2f}, ease: "none" }}, {a});\n'
            f'      tl.to("{sel}", {{ opacity: 0, scale: 1.04, filter: BLUR(12), duration: 0.35, ease: "power2.in" }}, {b});')


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
      slam("#b-one", {t(1.96)}, {{ fromScale: 1.5 }});
      leave("#b-one", {t(3.30)}, {{ y: -60 }});
      enter("#st-all-lead", {t(3.40)}, {TX_IN});
      slam("#st-all", {t(3.48)}, {{ fromScale: 1.35, blur: 8 }});
      leave(["#st-all", "#st-all-lead"], {t(5.40)}, {{ y: -20 }});
      slam("#b-pi", {t(5.74)}, {{ fromScale: 1.6, blur: 18 }});
      leave("#b-pi", {t(6.36)}, {{ scale: 0.5, y: -120, rot: -20 }});

      // ---------- почему π, а не З, Д или С ----------
{word_in("#st-wtf", t(6.48), t(7.92))}
      tl.set("#p-let", {{ opacity: 1 }}, {t(8.06)});
{tile("#l-pi", t(8.80))}
{tile("#l-z", t(9.48))}
{tile("#l-d", t(9.84))}
{tile("#l-s", t(10.30))}
{strike("#l-z", t(10.56))}
{strike("#l-d", t(10.64))}
{strike("#l-s", t(10.72))}
      tl.fromTo("#l-pi", {{ scale: 1 }}, {{ scale: 1.14, duration: 0.18, yoyo: true, repeat: 1, ease: "sine.inOut", immediateRender: false }}, {t(10.80)});
      leave("#p-let", {t(11.30)}, {{ y: -60 }});
{word_in("#st-greek", t(11.46), t(13.66))}

      // ---------- ответ в Петербурге: Нева за спиной ----------
{bg_in("#bg-spb", t(14.60), t(18.50))}
      enter("#st-spb-lead", {t(14.66)}, {TX_IN});
      slam("#st-spb", {t(15.56)}, {{ fromScale: 1.35, blur: 8 }});
      leave(["#st-spb", "#st-spb-lead"], {t(16.10)}, {{ y: -20 }});
{word_in("#st-rus", t(16.22), t(18.40))}

      // ---------- π = C/d: окружность, развёртка, три диаметра с хвостиком ----------
      enter("#p-circ", {t(18.78)}, {PANEL_IN});
      draw("#cc", {t(19.30)}, 0.6);
      draw("#cl", {t(21.32)}, 0.5);
      draw("#cd", {t(22.08)}, 0.3);
      tl.fromTo("#cticks", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.15 }}, {t(21.80)});
{eq("#cf", t(20.22))}
{eq("#cn", t(22.40))}
      leave("#p-circ", {t(23.70)}, {{ y: 80 }});
      slam("#st-mem", {t(23.84)}, {{ fromScale: 2.0, rot: -5, blur: 10 }});
      leave("#st-mem", {t(24.50)}, {{ scale: 0.6, y: -30, rot: -14 }});

      // ---------- περιφέρεια → π ----------
      doc("#p-greek", {t(24.90)}, {t(29.80)}, {{ fromRot: -5, rot: 1 }});
      tl.fromTo("#p-greek .greek span", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.12, stagger: 0.04, ease: "power2.out" }}, {t(27.34)});
      tl.fromTo("#g-pi", {{ scale: 1 }}, {{ scale: 1.5, y: -14, duration: 0.2, ease: "back.out(2)", immediateRender: false }}, {t(28.78)});
      enter("#g-note", {t(28.84)}, {{ fromScale: 0.8, dur: 0.25 }});
{word_in("#st-zh", t(30.44), t(31.86))}

      // ---------- бесконечное число: знаки π без конца ----------
      enter("#p-tick", {t(31.94)}, {{ fromScale: 0.9, dur: 0.3 }});
      tl.fromTo("#tick-run", {{ x: 60 }}, {{ x: -4200, duration: 3.5, ease: "power1.in" }}, {t(31.94)});
      leave("#p-tick", {t(35.44)}, {{ y: -40 }});
      slam("#st-nu", {t(35.72)}, {{ fromScale: 2.0, rot: -4, blur: 10 }});
      leave("#st-nu", {t(36.72)}, {{ scale: 0.6, y: -30, rot: -14 }});

      // ---------- на ЕГЭ π стоит благодаря Эйлеру ----------
      doc("#d-ege", {t(36.86)}, {t(39.40)}, {{ fromRot: -5, rot: 1 }});
{word_in("#st-notgr", t(39.52), t(40.44))}
      card("#c-eul", {t(41.42)}, {t(46.20)}, "right");
      enter("#p-kids", {t(43.16)}, {PANEL_IN});
      tl.fromTo("#p-kids .kid", {{ opacity: 0, y: 40, scale: 0.4 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.16, ease: "back.out(2)", stagger: 0.04 }}, {t(45.14)});
      tl.fromTo("#kids-n", {{ textContent: 0 }}, {{ textContent: 13, snap: {{ textContent: 1 }}, duration: 0.55, ease: "none", immediateRender: false }}, {t(45.14)});
      leave("#p-kids", {t(46.28)}, {{ y: 80 }});
      slam("#st-nif", {t(46.34)}, {{ fromScale: 2.0, rot: -4, blur: 10 }});
      leave("#st-nif", {t(47.10)}, {{ scale: 0.6, y: -30, rot: -14 }});

      // ---------- Академия, Анна Иоанновна, балы ----------
{bg_in("#bg-kunst", t(47.26), t(50.95))}
      enter("#st-acad-lead", {t(48.04)}, {TX_IN});
      slam("#st-acad", {t(48.70)}, {{ fromScale: 1.3, blur: 8 }});
      leave(["#st-acad", "#st-acad-lead"], {t(49.85)}, {{ y: 40 }});
      card("#c-anna", {t(49.90)}, {t(52.40)}, "left");
{bg_in("#bg-court", t(50.90), t(55.00))}
{word_in("#st-b1", t(52.64), t(53.76))}
{word_in("#st-b2", t(53.82), t(54.48))}
{word_in("#st-b3", t(54.54), t(54.98))}
      enter("#p-money", {t(55.06)}, {PANEL_IN});
      bars("#m-court", {t(55.20)});
      bars("#m-acad", {t(55.86)});
      tl.to("#m-acad", {{ backgroundColor: "#F0352C", duration: 0.2, yoyo: true, repeat: 1, immediateRender: false }}, {t(56.28)});
      leave("#p-money", {t(56.86)}, {{ y: 80 }});
{word_in("#st-und", t(57.16), t(59.40))}
      tl.set("#p-pen", {{ opacity: 1 }}, {t(59.72)});
      draw("#pen1", {t(59.72)}, 0.3);
      draw("#pen2", {t(60.06)}, 0.25);
      draw("#pen3", {t(60.40)}, 0.3);
      leave("#p-pen", {t(61.76)}, {{ y: -40, rot: 12 }});

      // ---------- панчлайн под «пип» ----------
      enter("#b-pz-lead", {t(61.90)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-pz", {t(62.86)}, {{ fromScale: 1.5 }});
      tl.fromTo("#censor-bar", {{ scaleX: 0, transformOrigin: "0 50%" }}, {{ scaleX: 1, duration: 0.1, ease: "power3.out", immediateRender: false }}, {t(62.92)});
      leave(["#b-pz", "#b-pz-lead"], {t(64.30)}, {{ y: -60 }});
'''

# Смена плана общий ↔ крупный каждые ~2,4 с (стиль проекта, IMG_1799 v5); портреты сбоку — общий план.
# Склеек в дубле нет — splice() не нужен.
switch, whips = tk.framing(keep_wide=[(t(41.30), t(46.60)), (t(49.80), t(52.80))])
beats += whips

# Звуки — мало (бриф few), правила 12.10: удары только на главном, семейства не подряд, файл ≤ 2,
# между звуками ≥ 1 с. На «пип» своего звука нет — там тон самого «пипа». Финальный pop — у плашки.
sounds = [
    audio("pi", "whoosh", t(5.72), 0.8),
    audio("nuans", "impact-bass-1", t(35.70), 0.9),
    audio("euler", "whoosh-cinematic", t(41.40), 0.7),
]
CTA_AT = t(64.50)
# человек поверх слов и фонов за спиной: 1 число, π, Петербург, Академия + двор, π-здец
fg = [(t(1.90), t(3.60)), (t(5.70), t(6.70)), (t(14.55), t(18.90)), (t(47.20), t(55.40)), (t(61.85), t(64.60))]

page = build_page("π — откуда буква", DUR, behind, front, beats, sounds, fg, cta_at=CTA_AT,
                  extra_css=css, fmt=tk.fmt, captions=tk.captions)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

# «А» whisper начал в тишине (0.0, звук с 0.86) — из дубля оно выпало, первое «ты» → «А ты»
fixes = tk.fixes({1: "А ты", 21:"чёрта", 39: "ёмкое", 58: "", 78: "", 147: "Иоанновне.", 170: "Эйлер", 180: "***"})

director = {
    "_note": "π и Эйлер, короткий дубль. Время по дублю; раскладка — work/IMG_1816/page.py, план — plan.md.",
    # акценты — уровнем стиля с правкой проекта (tk.punch, 1.36 при базе 1.2), а не числом
    "punches": [[t(5.74), t(6.36), tk.punch, 0.10], [t(23.84), t(24.46), tk.punch, 0.10],
                [t(35.72), t(36.66), tk.punch, 0.10], [t(62.86), t(64.20), tk.punch, 0.10]] + switch,
    "text_fixes": fixes,
    "keep_case": ["Пи", "ЕГЭ", "Эйлер", "Петербурге", "Петербургской", "Академии", "Наук", "Академию", "Анне", "Иоанновне",
                  "З", "Д", "С"],
    "accent_words": ["Пи", "периферия", "бесконечное", "нюанс", "Эйлер", "13", "***"],
    # текст на груди — на его время субтитров нет; за головой — субтитры идут
    "hide_captions": [[t(18.74), t(24.00)], [t(24.86), t(30.15)], [t(36.82), t(39.75)], [t(43.12), t(46.30)],
                      [t(48.00), t(50.10)], [t(55.02), t(57.10)], [round(CTA_AT - 0.05, 2), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
