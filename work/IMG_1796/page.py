"""Страница графики IMG_1796: кто придумал процент — Рим, итальянские банкиры, байка 1685, промилле, ЕГЭ.

Время ударов — по исходнику, на шкалу дубля (хвост «Это было...» убран, edit.json) переводит Take.
План — work/IMG_1796/plan.md. Второй ролик про процент — IMG_1821 (другой текст): графику там не
повторять один в один — что здесь стоит, перечислено в plan.md.
Проверено:
  • при Августе введён налог с продаж centesima rerum venalium — 1 % (Тацит, «Анналы» I.78) — верно;
  • знак % вырос из итальянского «per cento» → «p cento» → «p c°» → «°/₀» → «%» (рукописи XV–XVII вв.) — верно;
  • байка: в 1685 году в книге М. де ла Порта «Le Guide des Négociants» наборщик вместо «cto»
    набрал «%» — это известная легенда, знак к тому времени уже был в ходу — так он и говорит;
    распознавание дало «CTU» — в субтитрах «cto», как в легенде;
  • промилле ‰ — тысячная доля, внизу два нолика — верно; 20 % = ·0,2 — верно.
Ответов задач он не озвучивает — на экран ничего сверх речи не выносим (п.7 rules.md).
Картинки — Wikimedia Commons, качает work/IMG_1796/fetch.py; лицензии и авторы — downloads/candidates.json.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, card  # noqa: E402

STEM = "IMG_1796"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
IMG = ROOT / f"studio/{STEM}/assets/img"
IMG.mkdir(parents=True, exist_ok=True)
# фон за спиной (п.13 rules.md): выбран глазами из кандидатов fetch.py, лицензии — candidates.json
#   Рим — «Roman Forum looking East panorama.jpg», CC BY-SA 4.0; Флоренция — «Ponte Vecchio at dusk 1.JPG»,
#   CC BY-SA 3.0; типография — «Druckerpresse.jpg» (гравюра XVII в., фото), CC BY-SA 3.0; Август из Прима Порта — PD.
#   Ничего не сгенерировано.
BG = {"bg_rome.jpg": "rome_1.jpg", "bg_flor.jpg": "bank_1.jpg", "bg_press.jpg": "press_1.jpg"}
for dst_name, src_name in {"augustus.jpg": "augustus.jpg", **BG}.items():
    src = ROOT / f"work/{STEM}/downloads/{src_name}"
    if not src.exists():
        sys.exit(f"✗ нет {src.name} — запусти work/{STEM}/fetch.py (картинки с Wikimedia Commons)")
    dst = IMG / dst_name
    if not (dst.exists() and dst.samefile(src)):
        shutil.copyfile(src, dst)

CHEST = 1290        # верх плашек на груди: подбородок при базе 1.2 (как в IMG_1812)
SAFE = 'data-safe="лицо важнее серой зоны: плашка ниже подбородка (Валера, 12.10)"'
PANEL = f"left: 245px; width: 590px; top: {CHEST}px;"

css = '''      .panel { border-radius: 28px; background: rgba(12,12,14,0.88); border: 2px solid rgba(242,235,221,0.16);
               box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      .row { position: relative; display: flex; justify-content: space-between; align-items: center; min-height: 92px;
             padding: 4px 6px; opacity: 0; border-bottom: 2px solid rgba(242,235,221,0.14); }
      .row:last-child { border-bottom: none; }
      .row-w { font-family: "Manrope"; font-weight: 800; font-size: 28px; letter-spacing: 0.06em; text-transform: uppercase;
               color: rgba(242,235,221,0.8); }
      .row-m { display: inline-flex; align-items: center; color: var(--cream); font-family: "Oswald"; font-size: 60px; white-space: nowrap; }
      .row-m .katex-src { display: inline-block; font-size: 46px; }
      .row-m .katex-display { margin: 0; }
      .gold { color: #F5B82E; }
      .strike { position: absolute; right: 0; top: 46%; width: 170px; height: 8px; border-radius: 4px; background: var(--red);
                transform-origin: 0 50%; transform: scaleX(0); }
      .tag { font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.1em; text-transform: uppercase;
             color: rgba(242,235,221,0.75); text-align: center; }
      /* подменённый фон за спиной: сверху, низ переходит в родной кадр (там руки) */
      .bg { left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden;
            -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%);
            mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%); }
      .bg img { position: absolute; left: -54px; top: -96px; width: 1188px; height: 2112px; object-fit: cover; }
      .bg .vig { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 38%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.6) 100%); }
      /* сотня клеток: centesima — одна из ста */
      .cell { position: absolute; width: 26px; height: 26px; border-radius: 5px; background: rgba(242,235,221,0.3); opacity: 0; }
      .big-n { position: absolute; font-family: "Oswald"; font-weight: 700; color: var(--cream); text-align: center; opacity: 0; }
      /* рукопись: как per cento становится знаком */
      .ms { padding: 0; background: #F3EAD6; border-radius: 8px; box-shadow: 0 30px 80px rgba(0,0,0,0.6); overflow: hidden; }
      .ms-st { position: absolute; left: 0; top: 70px; width: 590px; text-align: center; font-family: "Cormorant"; font-style: italic;
               font-weight: 700; font-size: 104px; line-height: 1; color: #2A2219; opacity: 0; white-space: nowrap; }
      .ms-st span { display: inline-block; }
      .ms-note { position: absolute; left: 0; top: 22px; width: 590px; text-align: center; font-family: "Manrope"; font-weight: 800;
                 font-size: 24px; letter-spacing: 0.12em; text-transform: uppercase; color: #6A5A44; opacity: 0; }
      /* литеры наборщика */
      .sort { position: absolute; top: 60px; width: 120px; height: 150px; border-radius: 10px; background: linear-gradient(180deg, #5C5F66, #2E3036);
              box-shadow: inset 0 -8px 0 rgba(0,0,0,0.35), 0 18px 40px rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center;
              font-family: "Cormorant"; font-weight: 700; font-size: 110px; color: #E9E4D8; opacity: 0; }
      .sort.hot { color: #F5B82E; }
      /* линия времени */
      .tdot { position: absolute; top: 104px; width: 34px; height: 34px; border-radius: 17px; background: var(--cream); opacity: 0; }
      .tlab { position: absolute; width: 180px; text-align: center; font-family: "Manrope"; font-weight: 800; font-size: 26px; line-height: 1.15;
              color: var(--cream); opacity: 0; }
      .tlab b { display: block; font-family: "Oswald"; font-size: 44px; color: #F5B82E; }
      /* «экономическая задача» и ошибки */
      .x-mark { position: absolute; font-family: "Oswald"; font-weight: 700; font-size: 44px; color: #C7271F; opacity: 0;
                border: 4px solid #C7271F; border-radius: 8px; padding: 0 10px; transform: rotate(-8deg); }
      /* Август — статуя целиком, в карточке нужен крупный план головы */
      #c-aug { top: 268px; left: 716px; width: 236px; padding: 12px 12px 10px; }
      #c-aug .ph { width: 212px; height: 220px; }
      #c-aug img { width: 600px; height: 900px; max-width: none; object-fit: fill; margin-left: -284px; margin-top: -14px; }
      #c-aug .card-name { font-size: 20px; margin-top: 8px; }
      #c-aug .card-sub { font-size: 22px; }
      .line-g { height: 14px; border-radius: 7px; background: rgba(42,34,25,0.18); margin-top: 18px; }
'''


def tex(s: str) -> str:
    return f'<span class="katex-src" data-tex="{s}"></span>'


def bg(bid: str, img: str) -> str:
    return f'        <div id="{bid}" class="g bg"><img src="assets/img/{img}" alt="" /><div class="vig"></div></div>'


# ---------- сотня клеток (11.0–14.2): одна из ста ----------
G0X, G0Y, STEP = 32, 32, 30
cells = "".join(f'<div class="cell" id="cl{i * 10 + j}" style="left: {G0X + j * STEP}px; top: {G0Y + i * STEP}px;"></div>'
                for i in range(10) for j in range(10))
grid = (f'        <div id="p-grid" class="g panel" {SAFE} style="{PANEL} height: 364px;">\n'
        f'          {cells}\n'
        '          <div id="gn1" class="tag" style="position: absolute; left: 350px; top: 52px; width: 220px; opacity: 0;">centesima</div>\n'
        '          <div id="gn2" class="big-n" style="left: 350px; top: 96px; width: 220px; font-size: 66px;">сотая</div>\n'
        '          <div id="gn3" class="big-n" style="left: 350px; top: 196px; width: 220px; font-size: 104px; color: #F0352C;">1%</div>\n'
        '        </div>')

# ---------- рукопись (19.4–30.3): per cento → p cento → p c° → °/₀ → % ----------
ms = (f'        <div id="p-ms" class="g ms" {SAFE} style="{PANEL} height: 240px;">\n'
      '          <div id="ms-note" class="ms-note">итальянцы · «на сотню»</div>\n'
      '          <div id="ms1" class="ms-st">per cento</div>\n'
      '          <div id="ms2" class="ms-st">p cento</div>\n'
      '          <div id="ms3" class="ms-st"><span id="ms3-p">p</span>&nbsp;c<sup style="font-size: 0.55em;">o</sup></div>\n'
      '          <div id="ms4" class="ms-st"><sup style="font-size: 0.55em;">o</sup>/<sub style="font-size: 0.55em;">o</sub></div>\n'
      '          <div id="ms5" class="ms-st" style="font-family: Oswald; font-style: normal; color: #C7271F;">%</div>\n'
      '        </div>')

# ---------- литеры наборщика (36.9–39.4): c t o → % ----------
typeset = (f'        <div id="p-type" class="g panel" {SAFE} style="{PANEL} height: 270px;">\n'
           '          <div class="tag" style="position: absolute; left: 0; top: 18px; width: 590px;">париж · 1685 · наборщик</div>\n'
           '          <div id="so1" class="sort" style="left: 95px;">c</div>\n'
           '          <div id="so2" class="sort" style="left: 235px;">t</div>\n'
           '          <div id="so3" class="sort" style="left: 375px;">o</div>\n'
           '          <div id="so4" class="sort hot" style="left: 235px; font-family: Oswald;">%</div>\n'
           '        </div>')

# ---------- линия времени (40.3–42.6): знак гулял по бумагам задолго до байки ----------
ARROW = 'fill="none" stroke="#F2EBDD" stroke-width="6" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"'
tline = (f'        <div id="p-line" class="g panel" {SAFE} style="{PANEL} height: 250px;">\n'
         f'          <svg viewBox="0 0 590 250" style="position: absolute; left: 0; top: 0; width: 590px; height: 250px;">'
         f'<path id="tl-ax" d="M 40 121 L 550 121" {ARROW} /></svg>\n'
         '          <div id="td1" class="tdot" style="left: 78px;"></div>\n'
         '          <div id="td2" class="tdot" style="left: 278px;"></div>\n'
         '          <div id="td3" class="tdot" style="left: 478px; background: #F0352C;"></div>\n'
         '          <div id="tl1" class="tlab" style="left: 5px; top: 150px;"><b>Рим</b>1% налог</div>\n'
         '          <div id="tl2" class="tlab" style="left: 205px; top: 150px;"><b>%</b>банкиры</div>\n'
         '          <div id="tl3" class="tlab" style="left: 405px; top: 150px;"><b style="color: #F0352C;">1685</b>байка</div>\n'
         '          <div id="tl-doc" class="big-n" style="left: 60px; top: 18px; width: 70px; font-size: 64px; color: #F5B82E;">%</div>\n'
         '        </div>')

# ---------- процент и промилле (42.7–49.0): нолик внизу второй ----------
def glyph(gid: str, mil: bool) -> str:
    z = '<circle id="{0}-z2" cx="128" cy="150" r="20" fill="none" stroke="#F2EBDD" stroke-width="12" style="opacity: 0;" />'.format(gid) if mil else ""
    return (f'<svg id="{gid}" viewBox="0 0 160 180" style="position: absolute; top: 28px; width: 160px; height: 180px;'
            f' left: {70 if not mil else 360}px;">'
            '<circle cx="34" cy="36" r="20" fill="none" stroke="#F2EBDD" stroke-width="12" />'
            '<path d="M 112 14 L 40 166" stroke="#F2EBDD" stroke-width="12" stroke-linecap="round" />'
            f'<circle cx="{78 if mil else 98}" cy="150" r="20" fill="none" stroke="#F2EBDD" stroke-width="12" />{z}</svg>')


mil = (f'        <div id="p-mil" class="g panel" {SAFE} style="{PANEL} height: 330px;">\n'
       f'          {glyph("gp", False)}\n          {glyph("gm", True)}\n'
       '          <div id="mn1" class="tag" style="position: absolute; left: 30px; top: 216px; width: 240px; opacity: 0;">на сотню</div>\n'
       '          <div id="mn2" class="tag" style="position: absolute; left: 320px; top: 216px; width: 240px; opacity: 0;">на тысячу</div>\n'
       '          <div id="mb1" class="big-n" style="left: 30px; top: 258px; width: 240px; font-size: 44px; color: #F5B82E;">банк</div>\n'
       '          <div id="mb2" class="big-n" style="left: 320px; top: 258px; width: 240px; font-size: 44px; color: #F5B82E;">гаишник</div>\n'
       '        </div>')

# ---------- ЕГЭ: процент — сотая; 20 % — это ·0,2 (51.5–57.2), а не ÷20 и не ·20 (57.4–61.9) ----------
rule1 = (f'        <div id="p-r1" class="g panel" {SAFE} style="{PANEL} padding: 10px 26px;">\n'
         f'          <div id="r1" class="row"><span class="row-w">процент</span><span class="row-m">1% = {tex(r"\tfrac{1}{100}")}</span></div>\n'
         '          <div id="r2" class="row"><span class="row-w">20%</span><span class="row-m gold">× 0,2</span></div>\n'
         '        </div>')
rule2 = (f'        <div id="p-r2" class="g panel" {SAFE} style="{PANEL} padding: 10px 26px;">\n'
         '          <div id="r3" class="row"><span class="row-w">не делить</span><span class="row-m">÷ 20</span><div id="r3-x" class="strike"></div></div>\n'
         '          <div id="r4" class="row"><span class="row-w">не умножать</span><span class="row-m">× 20</span><div id="r4-x" class="strike"></div></div>\n'
         '          <div id="r5" class="row"><span class="row-w">именно</span><span class="row-m gold">число × 0,2</span></div>\n'
         '        </div>')

# ---------- экономическая задача (62.4–65.3): ошибки растут отсюда ----------
econ = (f'        <div id="p-econ" class="g paper" {SAFE} style="left: 200px; top: {CHEST}px; width: 680px; padding: 24px 36px 30px;">\n'
        '          <div class="tag" style="color: #2B3A67; text-align: left;">ЕГЭ · экономическая задача</div>\n'
        '          <div class="line-g" style="width: 92%;"></div><div class="line-g" style="width: 78%;"></div>'
        '<div class="line-g" style="width: 86%;"></div><div class="line-g" style="width: 60%;"></div>\n'
        '          <div id="ex1" class="x-mark" style="left: 420px; top: 66px;">× 20 ?</div>\n'
        '          <div id="ex2" class="x-mark" style="left: 120px; top: 120px;">÷ 20 ?</div>\n'
        '          <div id="ex3" class="x-mark" style="left: 470px; top: 150px;">ошибка</div>\n'
        '        </div>')

behind = "\n".join([
    '        <div id="b-proc-lead" class="g lead" style="top: 272px;">кто первым придумал брать</div>',
    '        <div id="b-proc" class="g big red" style="top: 318px; font-size: 190px;">процент?</div>',
    bg("bg-rome", "bg_rome.jpg"),
    bg("bg-flor", "bg_flor.jpg"),
    '        <div id="b-pct" class="g big" style="top: 300px; font-size: 290px; color: #F0352C;">%</div>',
    bg("bg-press", "bg_press.jpg"),
    '        <div id="b-1685-lead" class="g lead" style="top: 272px;">парижский наборщик</div>',
    '        <div id="b-1685" class="g big" style="top: 318px; font-size: 250px;"><span id="b-1685-n">1685</span></div>',
    '        <div id="b-ege-lead" class="g lead" style="top: 272px;">главное про проценты на</div>',
    '        <div id="b-ege" class="g big" style="top: 318px; font-size: 250px;">ЕГЭ</div>',
    '        <div id="b-x02" class="g big" style="top: 318px; font-size: 230px; color: #F5B82E; white-space: nowrap;">× 0,2</div>',
])

STK = 'top: 300px; font-size: 56px; white-space: nowrap;'
front = "\n".join([
    '        <div id="st-tax" class="g stamp" style="left: 330px; top: 290px; font-size: 96px; background: rgba(12,12,14,0.55); white-space: nowrap;">налоги ↑</div>',
    f'        <div id="st-meme" class="g sticker" style="left: 170px; {STK}">каждый день думает о Риме</div>',
    card("c-aug", "augustus.jpg", "Октавиан Август", "налог на продажи — 1%", side="right"),
    grid,
    f'        <div id="st-modest" class="g sticker" style="left: 300px; {STK}">скромно, да?</div>',
    f'        <div id="st-bank" class="g sticker" style="left: 230px; {STK}">итальянские банкиры</div>',
    ms,
    typeset,
    '        <div id="st-bayka" class="g stamp" style="left: 380px; top: 290px; font-size: 110px; background: rgba(12,12,14,0.55);">байка</div>',
    tline,
    f'        <div id="st-mil" class="g sticker" style="left: 330px; {STK}">а ещё промилле</div>',
    mil,
    rule1,
    rule2,
    econ,
])

ROW = '{ opacity: 0, x: -30 }, { opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }'


def row(sel: str, at: float) -> str:
    return f'      tl.fromTo("{sel}", {ROW}, {at});'


def bg_in(sel: str, a: float, b: float) -> str:
    """Фон наплывом со смазом, медленный наезд внутри, уход со смазом; на показе резкий."""
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.08, filter: BLUR(14) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.45, ease: "power2.out" }}, {a});\n'
            f'      tl.fromTo("{sel} img", {{ scale: 1 }}, {{ scale: 1.06, duration: {b - a + 0.35:.2f}, ease: "none" }}, {a});\n'
            f'      tl.to("{sel}", {{ opacity: 0, scale: 1.04, filter: BLUR(12), duration: 0.35, ease: "power2.in" }}, {b});')


def swap(a: str, b: str, at: float) -> str:
    """Стадия рукописи сменяется следующей: старая уходит вверх со смазом, новая встаёт."""
    return (f'      tl.to("{a}", {{ opacity: 0, y: -40, filter: BLUR(10), duration: 0.18, ease: "power2.in" }}, {at});\n'
            f'      tl.fromTo("{b}", {{ opacity: 0, y: 40, scale: 0.9, filter: BLUR(10) }}, '
            f'{{ opacity: 1, y: 0, scale: 1, filter: BLUR(0), duration: 0.24, ease: "power3.out" }}, {round(at + 0.12, 2)});')


PANEL_IN = '{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }'
beats = f'''
      // ---------- хук: налоги ↑ — кто первым придумал ПРОЦЕНТ? ----------
      slam("#st-tax", {t(0.30)}, {{ fromScale: 2.0, rot: -5, blur: 10 }});
      leave("#st-tax", {t(1.55)}, {{ scale: 0.6, y: 0, rot: -14 }});
      enter("#b-proc-lead", {t(1.70)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-proc", {t(3.24)}, {{ fromScale: 1.5 }});
      leave(["#b-proc", "#b-proc-lead"], {t(3.84)}, {{ y: -60 }});

      // ---------- Рим за спиной: император, мем про Римскую империю, Август и centesima ----------
{bg_in("#bg-rome", t(3.86), t(14.20))}
      enter("#st-meme", {t(5.66)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-meme", {t(7.80)}, {{ y: -30, rot: -10 }});
      card("#c-aug", {t(8.30)}, {t(10.90)}, "right");
      enter("#p-grid", {t(11.04)}, {PANEL_IN});
      tl.fromTo("#p-grid .cell", {{ opacity: 0, scale: 0.3 }}, {{ opacity: 1, scale: 1, duration: 0.14, ease: "back.out(2)", stagger: 0.006 }}, {t(11.20)});
      enter("#gn1", {t(11.40)}, {{ fromScale: 0.8, dur: 0.25 }});
      enter("#gn2", {t(12.42)}, {{ fromScale: 0.8, dur: 0.25 }});
      tl.to("#cl0", {{ backgroundColor: "#F0352C", scale: 1.5, duration: 0.18, ease: "power2.out" }}, {t(13.38)});
      tl.to("#cl0", {{ scale: 1, duration: 0.25, ease: "power2.out" }}, {t(13.60)});
      slam("#gn3", {t(13.62)}, {{ fromScale: 1.6 }});
      leave("#p-grid", {t(14.20)}, {{ y: 80 }});
      enter("#st-modest", {t(14.28)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-modest", {t(15.45)}, {{ y: -30, rot: 10 }});

      // ---------- Флоренция за спиной: итальянские банкиры и рукопись ----------
{bg_in("#bg-flor", t(15.70), t(21.40))}
      enter("#st-bank", {t(17.58)}, {{ fromScale: 0.6, rot: -3 }});
      leave("#st-bank", {t(18.85)}, {{ y: -30, rot: -10 }});
      doc("#p-ms", {t(19.30)}, {t(30.30)}, {{ fromRot: -5, rot: 1 }});
      tl.fromTo("#ms1", {{ opacity: 0, y: 30, filter: BLUR(10) }}, {{ opacity: 1, y: 0, filter: BLUR(0), duration: 0.25, ease: "power3.out" }}, {t(19.78)});
      enter("#ms-note", {t(20.66)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave("#ms-note", {t(23.70)}, {{ y: -20 }});
{swap("#ms1", "#ms2", t(23.90))}
{swap("#ms2", "#ms3", t(25.14))}
      tl.to("#ms3-p", {{ y: 200, rotation: -70, opacity: 0, duration: 0.45, ease: "power2.in" }}, {t(27.68)});
{swap("#ms3", "#ms4", t(28.48))}
{swap("#ms4", "#ms5", t(30.00))}

      // ---------- знак процента — за спиной ----------
      slam("#b-pct", {t(30.38)}, {{ fromScale: 1.6, rot: -4 }});
      flash({t(30.38)});
      leave("#b-pct", {t(31.30)}, {{ y: -60, rot: 8 }});

      // ---------- байка: типография за спиной, 1685, cto → % ----------
{bg_in("#bg-press", t(31.42), t(39.30))}
      enter("#b-1685-lead", {t(34.22)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-1685", {t(35.28)}, {{ fromScale: 1.3 }});
      tl.fromTo("#b-1685-n", {{ textContent: 1500 }}, {{ textContent: 1685, snap: {{ textContent: 1 }}, duration: 0.8, ease: "power2.out",
                immediateRender: false }}, {t(35.28)});
      leave(["#b-1685", "#b-1685-lead"], {t(36.80)}, {{ y: -60 }});
      enter("#p-type", {t(36.92)}, {PANEL_IN});
      tl.fromTo("#so1, #so2, #so3", {{ opacity: 0, y: -160 }}, {{ opacity: 1, y: 0, duration: 0.25, ease: "bounce.out", stagger: 0.12 }}, {t(37.10)});
      tl.to("#so1", {{ x: 140, opacity: 0, scale: 0.6, duration: 0.22, ease: "power2.in" }}, {t(38.58)});
      tl.to("#so3", {{ x: -140, opacity: 0, scale: 0.6, duration: 0.22, ease: "power2.in" }}, {t(38.58)});
      tl.to("#so2", {{ opacity: 0, scale: 0.6, duration: 0.18, ease: "power2.in" }}, {t(38.62)});
      slam("#so4", {t(38.80)}, {{ fromScale: 1.8, rot: -6 }});
      leave("#p-type", {t(39.40)}, {{ y: 80 }});

      // ---------- «байка», а знак давно гулял по бумагам: линия времени ----------
      slam("#st-bayka", {t(39.50)}, {{ fromScale: 2.0, rot: -6, blur: 10 }});
      leave("#st-bayka", {t(40.30)}, {{ scale: 0.6, y: 0, rot: -16 }});
      enter("#p-line", {t(40.32)}, {PANEL_IN});
      draw("#tl-ax", {t(40.42)}, 0.45);
      tl.fromTo("#td1, #td2, #td3", {{ opacity: 0, scale: 0.3 }}, {{ opacity: 1, scale: 1, duration: 0.2, ease: "back.out(2)", stagger: 0.18 }}, {t(40.50)});
      tl.fromTo("#tl1, #tl2, #tl3", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.2, ease: "power2.out", stagger: 0.18 }}, {t(40.60)});
      enter("#tl-doc", {t(41.20)}, {{ fromScale: 0.4, dur: 0.2 }});
      tl.to("#tl-doc", {{ keyframes: [{{ x: 200, y: -6, rotation: 10, duration: 0.35, ease: "none" }},
                                     {{ x: 400, y: 0, rotation: -10, duration: 0.35, ease: "power2.out" }}] }}, {t(41.42)});
      leave("#p-line", {t(42.62)}, {{ y: 80 }});

      // ---------- промилле: нолик внизу второй; банк и гаишник ----------
      enter("#st-mil", {t(42.72)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-mil", {t(43.85)}, {{ y: -30, rot: -10 }});
      enter("#p-mil", {t(43.00)}, {PANEL_IN});
      enter("#gp", {t(43.20)}, {{ fromScale: 0.5 }});
      enter("#gm", {t(43.88)}, {{ fromScale: 0.5, rot: 6 }});
      enter("#mn1", {t(44.20)}, {{ fromScale: 0.8, dur: 0.2 }});
      enter("#mn2", {t(44.92)}, {{ fromScale: 0.8, dur: 0.2 }});
      tl.fromTo("#gm-z2", {{ opacity: 0, scale: 2.2, svgOrigin: "128 150" }}, {{ opacity: 1, scale: 1, duration: 0.25, ease: "back.out(2.5)",
                immediateRender: false }}, {t(46.28)});
      tl.fromTo("#gm", {{ scale: 1 }}, {{ scale: 1.1, duration: 0.18, yoyo: true, repeat: 1, ease: "sine.inOut", immediateRender: false }}, {t(46.60)});
      enter("#mb1", {t(47.84)}, {{ fromScale: 0.6, dur: 0.25 }});
      enter("#mb2", {t(48.44)}, {{ fromScale: 0.6, dur: 0.25 }});
      leave("#p-mil", {t(49.05)}, {{ y: 80 }});

      // ---------- главное на ЕГЭ ----------
      enter("#b-ege-lead", {t(49.50)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-ege", {t(51.14)}, {{ fromScale: 1.5 }});
      leave(["#b-ege", "#b-ege-lead"], {t(52.30)}, {{ y: -60 }});
      enter("#p-r1", {t(51.56)}, {PANEL_IN});
{row("#r1", t(52.42))}
{row("#r2", t(55.06))}
      leave("#p-r1", {t(57.20)}, {{ y: 80 }});
      enter("#p-r2", {t(57.42)}, {PANEL_IN});
{row("#r3", t(57.80))}
      tl.to("#r3-x", {{ scaleX: 1, duration: 0.18, ease: "power2.out" }}, {t(58.30)});
{row("#r4", t(58.62))}
      tl.to("#r4-x", {{ scaleX: 1, duration: 0.18, ease: "power2.out" }}, {t(59.10)});
{row("#r5", t(59.66))}
      leave("#p-r2", {t(61.90)}, {{ y: 80 }});
      slam("#b-x02", {t(61.00)}, {{ fromScale: 1.5 }});
      leave("#b-x02", {t(62.30)}, {{ y: -60 }});

      // ---------- экономическая задача: ошибки отсюда ----------
      doc("#p-econ", {t(62.42)}, {t(65.30)}, {{ fromRot: 5, rot: -1 }});
      tl.fromTo("#ex1, #ex2, #ex3", {{ opacity: 0, scale: 2, filter: BLUR(8) }}, {{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.16,
                ease: "power4.out", stagger: 0.3 }}, {t(62.90)});
'''

# Звуки — мало (бриф: few), по правилам 12.10: удары только на главном (ПРОЦЕНТ?, знак %, ×0,2),
# семейства не подряд, файл ≤ 2 раз, между звуками ≥ 1 с. Фоны и визуализации — без звука.
sounds = [
    audio("proc", "whoosh", t(3.22), 0.8),
    audio("aug", "pop", t(8.28), 0.7),
    audio("pct", "impact-bass-1", t(30.36), 0.9),
    audio("y1685", "whoosh-cinematic", t(35.26), 0.7),
    audio("strike", "click", t(58.28), 0.8),
    audio("x02", "impact-bass-2", t(60.98), 0.8),
]
# человек поверх фонов и слов за спиной
fg = [(t(1.65), t(14.65)), (t(15.60), t(21.85)), (t(30.30), t(39.70)), (t(49.45), t(52.60)), (t(60.90), t(62.60))]

CTA_AT = t(65.45)
page = build_page("Кто придумал процент", DUR, behind, front, beats, sounds, fg, cta_at=CTA_AT,
                  extra_css=css, cta_small="больше интересной математики — у меня в профиле",
                  fmt=tk.fmt, captions=tk.captions)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

# распознавание: «CTU» — в легенде «cto»; «0» + «,2.» — «0,2»
fixes = tk.fixes({105: "cto", 158: "0,2.", 159: "", 172: "0,2.", 173: ""})

director = {
    "_note": "Кто придумал процент. Время по дублю; раскладка — work/IMG_1796/page.py, план — plan.md.",
    "punches": [[t(3.24), t(3.90), 1.18, 0.10], [t(30.38), t(31.30), 1.22, 0.10], [t(35.28), t(36.60), 1.16, 0.10],
                [t(51.14), t(52.20), 1.20, 0.10], [t(61.00), t(62.20), 1.22, 0.10]],
    "text_fixes": fixes,
    "keep_case": ["ЕГЭ", "Августе", "Риме", "Римской", "Римский", "cto"],
    "accent_words": ["процент?", "1685", "промилле.", "0,2."],
    # плашки на груди стоят на уровне субтитров — на их время субтитров нет
    "hide_captions": [[t(11.00), t(14.45)], [t(19.25), t(30.60)], [t(36.88), t(49.30)],
                      [t(51.50), t(62.15)], [t(62.38), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
