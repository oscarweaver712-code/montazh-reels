"""Страница графики IMG_1793: закон Индианы о числе π (1897), что такое π, Джонс, Эйлер, NASA, ЕГЭ.

Время ударов — по исходнику, на шкалу дубля (начало «релочный рилс.» и щелчок в конце убраны,
edit.json) переводит Take. План — work/IMG_1793/plan.md.
Проверено:
  • 1897, Индиана, House Bill № 246, автор — врач Эдвин Гудвин; Палата представителей — 67 : 0;
    Сенат отложил законопроект после того, как профессор Purdue К. А. Уолдо объяснил депутатам
    абсурдность — верно; из текста законопроекта выходит в том числе π = 3,2 — так он и говорит;
  • π — отношение длины окружности к диаметру, «чуть больше трёх» (3,14159…) — верно;
  • обозначение π — Уильям Джонс, 1706 («Synopsis Palmariorum Matheseos») — верно;
    περιφέρεια — «окружность» — верно; популярным знак сделал Эйлер — верно;
  • JPL/NASA для межпланетной навигации берёт 15 знаков: 3,141592653589793 — верно.
    «Знаки, которые повторяются» — оговорка (у π они не повторяются): на экран не выносим.
Сверх речи на экран ничего не выносим (п.7 rules.md): 3,14159… и 15 знаков — то, о чём он говорит.
Портрета Гудвина свободного нет — вместо фото карточка-монограмма (людей не генерируем).
Картинки — Wikimedia Commons (work/IMG_1793/fetch.py), лицензии и авторы — downloads/candidates.json.
Ничего не сгенерировано.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, card  # noqa: E402

STEM = "IMG_1793"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
IMG = ROOT / f"studio/{STEM}/assets/img"
IMG.mkdir(parents=True, exist_ok=True)
# фон за спиной (п.13 rules.md), выбран глазами из кандидатов fetch.py:
#   Капитолий Индианы — «Indiana Statehouse at night.jpg», CC BY-SA 4.0 (Presidentman);
#   Парфенон — «Parthenon from west.jpg», PD; Сатурн — Cassini, NASA, PD.
# Портреты: Уолдо (PD), Джонс — Хогарт (PD), Эйлер — Хандман (PD).
FILES = {"bg_indiana.jpg": "statehouse_1.jpg", "bg_greece.jpg": "greece_3.jpg", "bg_space.jpg": "space_5.jpg",
         "waldo.jpg": "waldo_1.jpg", "jones.jpg": "jones_1.jpg", "euler.jpg": "euler_2.jpg"}
for dst_name, src_name in FILES.items():
    src = ROOT / f"work/{STEM}/downloads/{src_name}"
    if not src.exists():
        sys.exit(f"✗ нет {src.name} — запусти work/{STEM}/fetch.py (картинки с Wikimedia Commons)")
    dst = IMG / dst_name
    if not (dst.exists() and dst.samefile(src)):
        shutil.copyfile(src, dst)

CHEST = 1290        # верх плашек на груди: подбородок при базе 1.2 (как в IMG_1796)
SAFE = 'data-safe="лицо важнее серой зоны: плашка ниже подбородка (Валера, 12.10)"'
PANEL = f"left: 245px; width: 590px; top: {CHEST}px;"

css = '''      .panel { border-radius: 28px; background: rgba(12,12,14,0.88); border: 2px solid rgba(242,235,221,0.16);
               box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      .tag { font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.1em; text-transform: uppercase;
             color: rgba(242,235,221,0.75); text-align: center; }
      .gold { color: #F5B82E; }
      /* подменённый фон за спиной: сверху, низ переходит в родной кадр (там руки и банка) */
      .bg { left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden;
            -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%);
            mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%); }
      .bg img { position: absolute; left: -54px; top: -96px; width: 1188px; height: 2112px; object-fit: cover; }
      .bg .vig { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 38%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.6) 100%); }
      #bg-ind img { object-position: 38% 50%; }
      #bg-space img { object-position: 56% 50%; }
      /* бланк законопроекта */
      .bill { padding: 22px 30px 26px; border-radius: 8px; background: #F3EAD6; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      .bill-head { font-family: "Manrope"; font-weight: 800; font-size: 24px; letter-spacing: 0.14em; text-transform: uppercase;
                   color: #6A5A44; text-align: center; }
      .bill-title { margin-top: 6px; font-family: "Cormorant"; font-weight: 700; font-size: 64px; line-height: 1.05; color: #2A2219;
                    text-align: center; font-variant-numeric: lining-nums; }
      .bill-line { height: 12px; border-radius: 6px; background: rgba(42,34,25,0.16); margin: 14px auto 0; }
      .brow { position: relative; display: flex; justify-content: space-between; align-items: center; min-height: 72px;
              border-top: 2px solid rgba(42,34,25,0.14); opacity: 0; }
      .brow-w { font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.06em; text-transform: uppercase; color: #6A5A44; }
      .brow-m { font-family: "Cormorant"; font-weight: 700; font-size: 54px; color: #2A2219; font-variant-numeric: lining-nums; white-space: nowrap; }
      .brow-m.bad { color: #C7271F; }
      .brow-m.good { color: #1E7A3A; }
      .stamp-in { position: absolute; font-family: "Oswald"; font-weight: 700; text-transform: uppercase; color: #C7271F; opacity: 0;
                  border: 6px solid #C7271F; border-radius: 10px; padding: 0 16px; letter-spacing: 0.04em; white-space: nowrap; }
      /* голосование */
      .vrow { position: absolute; left: 30px; width: 530px; height: 90px; }
      .vlab { position: absolute; left: 0; top: 26px; width: 150px; font-family: "Manrope"; font-weight: 800; font-size: 28px;
              letter-spacing: 0.08em; text-transform: uppercase; color: var(--cream); }
      .vbar { position: absolute; left: 150px; top: 18px; height: 54px; border-radius: 10px; transform-origin: 0 50%; transform: scaleX(0); }
      .vnum { position: absolute; right: 0; top: 4px; width: 110px; text-align: right; font-family: "Oswald"; font-weight: 700;
              font-size: 72px; line-height: 1; color: var(--cream); opacity: 0; }
      /* монограмма вместо портрета (свободного фото Гудвина нет) */
      .mono-ph { display: flex; align-items: center; justify-content: center; background: #2B2620; font-family: "Cormorant";
                 font-weight: 700; font-size: 130px; color: #F3EAD6; }
      /* карточки уже и правее стандартной: при базе 1.2 лицо крупное (как #c-aug в IMG_1796) */
      .card.slim { top: 268px; left: 716px; width: 236px; padding: 12px 12px 10px; }
      .card.slim .ph { width: 212px; height: 220px; }
      .card.slim img { width: 212px; height: 220px; }
      .card.slim .card-name { font-size: 20px; margin-top: 8px; }
      .card.slim .card-sub { font-size: 22px; }
      .card.slim .mono-ph { font-size: 100px; }
      #c-waldo img { width: 400px; height: 787px; max-width: none; object-fit: fill; margin-left: -134px; margin-top: -17px; }
      #c-jones img { width: 480px; height: 608px; max-width: none; object-fit: fill; margin-left: -144px; margin-top: -20px; }
      #c-euler img { object-position: 45% 30%; }
      /* окружность и три диаметра */
      .lbl { position: absolute; font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 44px; color: var(--cream);
             text-align: center; opacity: 0; font-variant-numeric: lining-nums; }
      /* περιφέρεια */
      .greek { position: absolute; left: 0; top: 40px; width: 590px; text-align: center; font-family: "Cormorant"; font-weight: 700;
               font-size: 96px; color: var(--cream); line-height: 1; opacity: 0; white-space: nowrap; }
      .greek span { display: inline-block; }
      /* бегущая строка цифр π и 15 знаков */
      .ticker { left: 0; top: 330px; font-family: "Oswald"; font-weight: 700; font-size: 150px; line-height: 1; color: var(--cream);
                white-space: nowrap; text-shadow: 0 12px 40px rgba(0,0,0,0.4); }
      .digits { position: absolute; left: 0; top: 40px; width: 590px; text-align: center; font-family: "JBMono"; font-weight: 700;
                font-size: 38px; color: var(--cream); white-space: nowrap; }
      .digits span { display: inline-block; opacity: 0; }
      .digits span.on { color: #F5B82E; }
      .cnt { position: absolute; left: 0; top: 116px; width: 590px; text-align: center; font-family: "Oswald"; font-weight: 700;
             font-size: 92px; line-height: 1; color: #F5B82E; opacity: 0; }
      /* строчная π сидит на строке ниже заглавных: поднимаем саму букву, рамка блока остаётся ниже шапки */
      .lift { display: inline-block; transform: translateY(var(--lift)); }
'''


def bg(bid: str, img: str) -> str:
    return f'        <div id="{bid}" class="g bg"><img src="assets/img/{img}" alt="" /><div class="vig"></div></div>'


def lines(*widths: int) -> str:
    return "".join(f'<div class="bill-line" style="width: {w}%;"></div>' for w in widths)


# ---------- бланк «Госдума» (хук) ----------
law = (f'        <div id="p-law" class="g bill" {SAFE} style="{PANEL} height: 230px;">\n'
       '          <div class="bill-head">госдума · законопроект</div>\n'
       '          <div class="bill-title">О числе π</div>\n'
       f'          {lines(86, 70, 78)}\n'
       '        </div>')

# ---------- House Bill № 246: π = 3,2; штату — бесплатно; остальным — платно ----------
bill = (f'        <div id="p-bill" class="g bill" {SAFE} style="{PANEL} height: 470px;">\n'
        '          <div class="bill-head">indiana · 1897</div>\n'
        '          <div class="bill-title" style="font-size: 56px;">House Bill № 246</div>\n'
        '          <div style="height: 18px;"></div>\n'
        '          <div id="br1" class="brow"><span class="brow-w">выходит</span><span class="brow-m bad">π = 3,2</span></div>\n'
        '          <div id="br1-t" class="brow"><span class="brow-w">на деле</span><span class="brow-m good">π = 3,14159…</span></div>\n'
        '          <div id="br2" class="brow"><span class="brow-w">штату</span><span class="brow-m">бесплатно</span></div>\n'
        '          <div id="br3" class="brow"><span class="brow-w">остальным</span><span class="brow-m">платно $</span></div>\n'
        '        </div>')

# ---------- голосование: 67 за, 0 против ----------
vote = (f'        <div id="p-vote" class="g panel" {SAFE} style="{PANEL} height: 300px;">\n'
        '          <div class="tag" style="position: absolute; left: 0; top: 24px; width: 590px;">палата представителей</div>\n'
        '          <div class="vrow" style="top: 80px;"><div class="vlab">за</div>'
        '<div id="v-yes" class="vbar" style="width: 260px; background: #3DBE6A;"></div>'
        '<div id="v-yes-n" class="vnum">67</div></div>\n'
        '          <div class="vrow" style="top: 186px;"><div class="vlab">против</div>'
        '<div id="v-no" class="vbar" style="width: 8px; background: #F0352C;"></div>'
        '<div id="v-no-n" class="vnum">0</div></div>\n'
        '        </div>')

# ---------- Сенат: остановлен ----------
stop = (f'        <div id="p-stop" class="g bill" {SAFE} style="{PANEL} height: 250px;">\n'
        '          <div class="bill-head">сенат индианы · 1897</div>\n'
        '          <div class="bill-title" style="font-size: 56px;">House Bill № 246</div>\n'
        f'          {lines(84, 66)}\n'
        '          <div id="st-stop" class="stamp-in" style="left: 100px; top: 116px; font-size: 62px;">остановлен</div>\n'
        '        </div>')

# ---------- окружность раскатывается в три диаметра с хвостиком ----------
D = 150                       # диаметр, px; длина окружности π·D ≈ 471
X0 = 60
STROKE = 'fill="none" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"'
ticks = "".join(f'<path id="tk{i}" d="M {X0 + i * D} 238 L {X0 + i * D} 262" stroke="#F2EBDD" stroke-width="5" {STROKE} />'
                for i in range(4))
segs = "".join(f'<path id="sg{i}" d="M {X0 + i * D} 250 L {X0 + (i + 1) * D} 250" stroke="#F5B82E" stroke-width="10" {STROKE} />'
               for i in range(3))
circ = (f'        <div id="p-circ" class="g panel" {SAFE} style="{PANEL} height: 330px;">\n'
        '          <svg viewBox="0 0 590 330" style="position: absolute; left: 0; top: 0; width: 590px; height: 330px;">'
        '<circle id="cc" cx="295" cy="110" r="75" stroke="#F2EBDD" stroke-width="8" fill="none" pathLength="1" '
        'stroke-dasharray="1" stroke-dashoffset="1" transform="rotate(90 295 110)" />'
        f'<path id="cd" d="M 220 110 L 370 110" stroke="#F5B82E" stroke-width="8" {STROKE} />'
        f'<path id="cl" d="M {X0} 250 L {X0 + round(3.14159 * D)} 250" stroke="#F2EBDD" stroke-width="10" {STROKE} />'
        f'{segs}<path id="sg3" d="M {X0 + 3 * D} 250 L {X0 + round(3.14159 * D)} 250" stroke="#F0352C" stroke-width="10" {STROKE} />'
        f'{ticks}</svg>\n'
        '          <div id="l-d" class="lbl" style="left: 270px; top: 118px; width: 50px;">d</div>\n'
        '          <div id="l-c" class="lbl" style="left: 380px; top: 22px; width: 200px; font-size: 34px;">окружность</div>\n'
        + "".join(f'          <div id="l-d{i}" class="lbl" style="left: {X0 + i * D + 50}px; top: 262px; width: 50px;">d</div>\n'
                  for i in range(3)) +
        f'          <div id="l-tail" class="lbl" style="left: {X0 + 3 * D - 30}px; top: 262px; width: 120px; color: #F0352C; font-size: 36px;">0,14…</div>\n'
        '        </div>')

# ---------- περιφέρεια = окружность ----------
greek = (f'        <div id="p-greek" class="g panel" {SAFE} style="{PANEL} height: 250px;">\n'
         '          <div id="gw" class="greek"><span id="gp" class="gold">π</span>εριφέρεια</div>\n'
         '          <div id="gt" class="tag" style="position: absolute; left: 0; top: 168px; width: 590px; font-size: 34px; opacity: 0;">'
         '= окружность</div>\n'
         '        </div>')

# ---------- 15 знаков после запятой ----------
PI15 = "3,141592653589793"
spans = "".join(f'<span id="dg{i}"{" class=\"on\"" if i >= 2 else ""}>{ch}</span>' for i, ch in enumerate(PI15))
nasa = (f'        <div id="p-nasa" class="g panel" {SAFE} style="{PANEL} height: 250px;">\n'
        f'          <div class="digits">{spans}</div>\n'
        '          <div id="nc" class="cnt"><span id="nc-n">15</span> знаков</div>\n'
        '        </div>')

TICK = "3,14159265358979323846264338327950288…"
behind = "\n".join([
    '        <div id="b-pi3" class="g big" style="top: 290px; font-size: 270px; white-space: nowrap; text-transform: none;">'
    '<span class="lift" style="--lift: -40px;">π</span> = 3</div>',
    bg("bg-ind", "bg_indiana.jpg"),
    '        <div id="b-almost" class="g lead" style="top: 300px;">почти приняли</div>',
    '        <div id="b-1897" class="g big" style="top: 300px; font-size: 250px;"><span id="b-1897-n">1897</span></div>',
    '        <div id="b-ind" class="g lead" style="top: 300px;">штат индиана</div>',
    '        <div id="b-bred" class="g big red" style="top: 320px; font-size: 230px;">бред</div>',
    '        <div id="b-pi" class="g big" style="top: 290px; font-size: 360px; text-transform: none;">'
    '<span class="lift" style="--lift: -110px;">π</span></div>',
    '        <div id="b-greek-lead" class="g lead" style="top: 264px;">греческая буква</div>',
    '        <div id="b-pi-serif" class="g big serif" style="top: 330px; font-size: 480px; text-transform: none;">'
    '<span class="lift" style="--lift: -200px;">π</span></div>',
    '        <div id="b-1706" class="g big" style="left: 40px; width: 700px; top: 330px; font-size: 230px;"><span id="b-1706-n">1706</span></div>',
    bg("bg-greece", "bg_greece.jpg"),
    f'        <div id="b-tick" class="g ticker" data-safe="бегущая строка цифр уходит за края — так задумано">{TICK}</div>',
    bg("bg-space", "bg_space.jpg"),
    '        <div id="b-nasa" class="g lead" style="top: 300px;">полёты nasa</div>',
    '        <div id="b-ege-lead" class="g lead" style="top: 290px;">а тебе на егэ</div>',
    '        <div id="b-314" class="g big red" style="top: 320px; font-size: 220px;"><span class="lift" style="--lift: -36px;">3,14</span></div>',
])

def slim(html: str) -> str:
    return html.replace("class=\"g card card-right\"", "class=\"g card card-right slim\"", 1)


STK = 'top: 300px; font-size: 56px; white-space: nowrap;'
front = "\n".join([
    law,
    f'        <div id="st-easy" class="g sticker" style="left: 190px; {STK}">чтобы школьникам было проще</div>',
    '        <div id="st-bred" class="g stamp" style="left: 360px; top: 290px; font-size: 110px; background: rgba(12,12,14,0.55);">бред?</div>',
    '        <div id="c-good" class="g card card-right slim">\n'
    '          <div class="ph mono-ph">Э.Г.</div>\n'
    '          <div class="card-name">Эдвин Гудвин</div>\n'
    '          <div class="card-sub">местный врач</div>\n        </div>',
    f'        <div id="st-secret" class="g sticker" style="left: 170px; {STK}">разгадал тайну математики</div>',
    bill,
    vote,
    stop,
    f'        <div id="st-luck" class="g sticker" style="left: 330px; {STK}">и то случайно</div>',
    slim(card("c-waldo", "waldo.jpg", "Кларенс Уолдо", "профессор", side="right")),
    circ,
    slim(card("c-jones", "jones.jpg", "Уильям Джонс", "англичанин", side="right")),
    greek,
    slim(card("c-euler", "euler.jpg", "Леонард Эйлер", "сделал знак модным", side="right")),
    nasa,
])

PANEL_IN = '{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }'
ROW = '{ opacity: 0, x: -30 }, { opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }'


def row(sel: str, at: float) -> str:
    return f'      tl.fromTo("{sel}", {ROW}, {at});'


def bg_in(sel: str, a: float, b: float) -> str:
    """Фон наплывом со смазом, медленный наезд внутри, уход со смазом; на показе резкий."""
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.08, filter: BLUR(14) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.45, ease: "power2.out" }}, {a});\n'
            f'      tl.fromTo("{sel} img", {{ scale: 1 }}, {{ scale: 1.06, duration: {b - a + 0.35:.2f}, ease: "none" }}, {a});\n'
            f'      tl.to("{sel}", {{ opacity: 0, scale: 1.04, filter: BLUR(12), duration: 0.35, ease: "power2.in" }}, {b});')


def count(sel: str, a: int, b: int, at: float, dur: float) -> str:
    return (f'      tl.fromTo("{sel}", {{ textContent: {a} }}, {{ textContent: {b}, snap: {{ textContent: 1 }}, duration: {dur}, '
            f'ease: "power2.out", immediateRender: false }}, {at});')


beats = f'''
      // ---------- хук: бланк «О числе π» — и за головой «π = 3» ----------
      doc("#p-law", {t(1.90)}, {t(4.30)}, {{ fromRot: -5, rot: 1 }});
      slam("#b-pi3", {t(4.36)}, {{ fromScale: 1.6, rot: -3 }});
      leave("#b-pi3", {t(5.30)}, {{ y: -60, rot: 6 }});
      enter("#st-easy", {t(5.50)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-easy", {t(6.42)}, {{ y: -30, rot: -10 }});
      slam("#st-bred", {t(6.90)}, {{ fromScale: 2.0, rot: -6, blur: 10 }});
      leave("#st-bred", {t(7.45)}, {{ scale: 0.6, y: 0, rot: -16 }});

      // ---------- Индиана: Капитолий за спиной, «почти приняли», 1800 → 1897 ----------
{bg_in("#bg-ind", t(7.50), t(12.30))}
      enter("#b-almost", {t(8.42)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave("#b-almost", {t(9.50)}, {{ y: -30 }});
      slam("#b-1897", {t(9.76)}, {{ fromScale: 1.3 }});
{count("#b-1897-n", 1800, 1897, t(9.76), 0.9)}
      leave("#b-1897", {t(11.40)}, {{ y: -60 }});
      enter("#b-ind", {t(11.62)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave("#b-ind", {t(12.25)}, {{ y: -30 }});

      // ---------- врач Гудвин, «разгадал тайну» ----------
      enter("#c-good", {t(12.86)}, {{ fromX: 460, rot: 4, fromRot: 16, dur: 0.45, ease: "power3.out" }});
      leave("#c-good", {t(14.20)}, {{ x: 460, y: 0, rot: 18, dur: 0.32 }});
      enter("#st-secret", {t(14.40)}, {{ fromScale: 0.6, rot: -3 }});
      leave("#st-secret", {t(16.20)}, {{ y: -30, rot: -10 }});

      // ---------- законопроект: π = 3,2 против настоящего; бесплатно штату, платно остальным ----------
      doc("#p-bill", {t(16.60)}, {t(25.70)}, {{ fromRot: 5, rot: -1 }});
{row("#br1", t(19.44))}
      tl.fromTo("#br1 .brow-m", {{ scale: 1.6, filter: BLUR(8) }}, {{ scale: 1, filter: BLUR(0), duration: 0.18, ease: "power4.out",
                immediateRender: false }}, {t(19.72)});
{row("#br1-t", t(20.30))}
{row("#br2", t(21.98))}
{row("#br3", t(24.24))}
      tl.fromTo("#br3 .brow-m", {{ scale: 1 }}, {{ scale: 1.12, duration: 0.18, yoyo: true, repeat: 1, ease: "sine.inOut",
                immediateRender: false }}, {t(25.04)});

      // ---------- голосование: 67 за, ноль против ----------
      enter("#p-vote", {t(25.90)}, {PANEL_IN});
      tl.fromTo("#v-yes", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.9, ease: "power2.out" }}, {t(28.12)});
      enter("#v-yes-n", {t(28.12)}, {{ fromScale: 0.6, dur: 0.2 }});
{count("#v-yes-n", 0, 67, t(28.12), 0.9)}
      tl.fromTo("#v-no", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.2, ease: "power2.out" }}, {t(29.28)});
      slam("#v-no-n", {t(29.28)}, {{ fromScale: 1.8 }});
      leave("#p-vote", {t(30.10)}, {{ y: 80 }});

      // ---------- Сенат: остановлен, и то случайно ----------
      doc("#p-stop", {t(30.22)}, {t(32.50)}, {{ fromRot: -6, rot: 1 }});
      slam("#st-stop", {t(31.26)}, {{ fromScale: 2.0, rot: -8, blur: 10 }});
      enter("#st-luck", {t(31.70)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-luck", {t(32.80)}, {{ y: -30, rot: 10 }});

      // ---------- профессор Уолдо ----------
      card("#c-waldo", {t(33.72)}, {t(37.30)}, "right");

      // ---------- «узаконить бред» ----------
      slam("#b-bred", {t(38.20)}, {{ fromScale: 1.5, rot: -4 }});
      leave("#b-bred", {t(38.90)}, {{ y: -60, rot: 8 }});

      // ---------- что такое π на самом деле? ----------
      slam("#b-pi", {t(39.72)}, {{ fromScale: 1.6 }});
      leave("#b-pi", {t(41.30)}, {{ y: -60 }});
      enter("#p-circ", {t(40.90)}, {PANEL_IN});
      draw("#cc", {t(41.36)}, 0.6);
      draw("#cd", {t(42.20)}, 0.35);
      enter("#l-d", {t(42.50)}, {{ fromScale: 0.6, dur: 0.2 }});
      enter("#l-c", {t(43.88)}, {{ fromScale: 0.8, dur: 0.25 }});
      tl.to("#cc", {{ strokeDashoffset: 1, duration: 0.7, ease: "power1.inOut" }}, {t(44.60)});
      leave(["#l-d", "#l-c"], {t(44.60)}, {{ y: -20 }});
      tl.to("#cd", {{ opacity: 0, y: 60, duration: 0.3, ease: "power2.in" }}, {t(44.60)});
      draw("#cl", {t(44.60)}, 0.7);
      tl.fromTo("#tk0, #tk1, #tk2, #tk3", {{ strokeDashoffset: 1 }}, {{ strokeDashoffset: 0, duration: 0.12, stagger: 0.2 }}, {t(44.90)});
      tl.fromTo("#sg0, #sg1, #sg2", {{ strokeDashoffset: 1 }}, {{ strokeDashoffset: 0, duration: 0.18, ease: "power2.out", stagger: 0.22 }}, {t(45.00)});
      tl.fromTo("#l-d0, #l-d1, #l-d2", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.15, stagger: 0.22 }}, {t(45.05)});
      draw("#sg3", {t(45.66)}, 0.15);
      slam("#l-tail", {t(45.70)}, {{ fromScale: 1.6 }});
      leave("#p-circ", {t(46.30)}, {{ y: 80 }});

      // ---------- греческая буква, Уильям Джонс, 1706 ----------
      enter("#b-greek-lead", {t(46.90)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-pi-serif", {t(47.36)}, {{ fromScale: 1.5, rot: -4 }});
      leave(["#b-pi-serif", "#b-greek-lead"], {t(49.40)}, {{ y: -60 }});
      card("#c-jones", {t(49.60)}, {t(52.40)}, "right");
      slam("#b-1706", {t(50.34)}, {{ fromScale: 1.3 }});
{count("#b-1706-n", 1600, 1706, t(50.34), 0.8)}
      leave("#b-1706", {t(51.70)}, {{ y: -60 }});

      // ---------- Парфенон за спиной: περιφέρεια = окружность ----------
{bg_in("#bg-greece", t(51.80), t(55.80))}
      enter("#p-greek", {t(52.10)}, {PANEL_IN});
      slam("#gw", {t(53.22)}, {{ fromScale: 1.3 }});
      tl.fromTo("#gp", {{ scale: 1 }}, {{ scale: 1.35, duration: 0.2, yoyo: true, repeat: 1, ease: "sine.inOut",
                immediateRender: false }}, {t(54.20)});
      enter("#gt", {t(55.10)}, {{ fromScale: 0.8, dur: 0.25 }});
      leave("#p-greek", {t(55.85)}, {{ y: 80 }});

      // ---------- Эйлер ----------
      card("#c-euler", {t(56.08)}, {t(58.40)}, "right");

      // ---------- бесконечные знаки — бегущей строкой за головой ----------
      tl.fromTo("#b-tick", {{ opacity: 0, x: 1100, filter: BLUR(10) }}, {{ opacity: 1, x: 300, filter: BLUR(0), duration: 0.4, ease: "power2.out" }}, {t(58.68)});
      tl.fromTo("#b-tick", {{ x: 300 }}, {{ x: -2600, duration: 2.0, ease: "none", immediateRender: false }}, {t(59.08)});
      leave("#b-tick", {t(60.90)}, {{ y: -40, scale: 0.9 }});

      // ---------- космос за спиной: NASA, 15 знаков ----------
{bg_in("#bg-space", t(61.00), t(65.70))}
      enter("#b-nasa", {t(61.98)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave("#b-nasa", {t(64.90)}, {{ y: -30 }});
      enter("#p-nasa", {t(65.00)}, {PANEL_IN});
      tl.to("#p-nasa .digits span", {{ opacity: 1, duration: 0.03, stagger: 0.06 }}, {t(65.30)});
      enter("#nc", {t(65.80)}, {{ fromScale: 0.6, dur: 0.2 }});
{count("#nc-n", 0, 15, t(65.80), 0.7)}
      leave("#p-nasa", {t(67.40)}, {{ y: 80 }});

      // ---------- панчлайн: а тебе на ЕГЭ не хватит 3,14 ----------
      enter("#b-ege-lead", {t(67.60)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave("#b-ege-lead", {t(68.70)}, {{ y: -30 }});
      slam("#b-314", {t(68.94)}, {{ fromScale: 1.6, rot: -3 }});
      tl.to("#b-314", {{ keyframes: [{{ x: -18, duration: 0.05 }}, {{ x: 16, duration: 0.07 }}, {{ x: -10, duration: 0.06 }},
                                    {{ x: 0, duration: 0.06 }}] }}, {t(69.40)});
      leave("#b-314", {t(70.15)}, {{ y: -60 }});
'''

# Звуки — мало (бриф: few), по правилам 12.10: удары только на главном,
# семейства не подряд, файл ≤ 2 раз, между звуками ≥ 1 с. Фоны и визуализации — без звука.
sounds = [
    audio("pi3", "whoosh", t(4.34), 0.8),
    audio("good", "pop", t(12.84), 0.7),
    audio("vote", "impact-bass-1", t(28.10), 0.9),
    audio("pi", "whoosh-cinematic", t(39.70), 0.7),
    audio("n15", "click", t(65.78), 0.8),
    audio("314", "impact-bass-2", t(68.92), 0.8),
]
# человек поверх фонов и слов за спиной
fg = [(t(4.30), t(6.30)), (t(7.45), t(12.70)), (t(38.15), t(41.60)), (t(46.85), t(56.20)),
      (t(58.60), t(66.10)), (t(67.55), t(70.45))]

CTA_AT = t(70.30)
page = build_page("Закон о числе пи", DUR, behind, front, beats, sounds, fg, cta_at=CTA_AT,
                  extra_css=css, cta_small="больше интересной математики — у меня в профиле",
                  fmt=tk.fmt, captions=tk.captions)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

# распознавание: «пи» → «π» как в остальном ролике; «3» + «,2» и «3» + «,14.» — одним словом;
# «А,» — союз «а»; тире словом убрано; «трех», «полетов» — с ё
fixes = tk.fixes({8: "π", 47: "π", 49: "3,2", 50: "", 69: "а,", 117: "трёх", 132: "",
                  162: "полётов", 180: "3,14.", 181: ""})

director = {
    "_note": "Закон о числе π. Время по дублю; раскладка — work/IMG_1793/page.py, план — plan.md.",
    "punches": [[t(4.36), t(5.80), 1.22, 0.10], [t(28.12), t(29.80), 1.20, 0.10], [t(39.72), t(41.10), 1.20, 0.10],
                [t(50.34), t(51.50), 1.16, 0.10], [t(68.94), t(70.10), 1.22, 0.10]],
    "text_fixes": fixes,
    # сверяются со словом без знаков препинания (compose.py)
    "keep_case": ["ЕГЭ", "NASA", "Госдума", "Америке", "Индиана", "Эдвин", "Гудвин", "Сенате", "Уильям", "Джонс",
                  "Эйлер", "Солнечной"],
    "accent_words": ["трём", "бред", "1897", "67", "окружность", "15", "3,14"],
    # плашки на груди стоят на уровне субтитров — на их время субтитров нет
    "hide_captions": [[t(1.85), t(4.65)], [t(16.55), t(32.85)], [t(40.85), t(46.60)],
                      [t(52.05), t(56.15)], [t(64.95), t(67.70)], [t(70.25), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
