"""Страница графики IMG_1821: почему процент — «два нолика и палочка» и при чём тут «затрёхсотили».

Время ударов — по исходнику, на шкалу дубля (начало «Бля, убийца… записываем» убрано, edit.json) переводит Take.
План — work/IMG_1821/plan.md. Первый ролик про процент — IMG_1796: его приёмы (сотня клеток, рукопись
per cento → %, литеры, промилле, фоны Рим/Флоренция/типография) здесь не повторяем.
Проверено:
  • percentum / per centum (лат.) — «на сотню», процент — сотая доля — верно;
  • знак % вырос из итальянского «per cento» в счетах купцов: «per c°» → к XVII в. «per °/₀» →
    «°/₀» → «%» — верно (общепринятая история знака, рукописи XV–XVII вв.);
  • «300 лет» — от сокращений XV в. до чистого знака в XVIII в. — порядок верный;
  • «Антонио Маргаретти» — псевдоним-итальянец из «Бесславных ублюдков» Тарантино (Antonio Margheriti);
    в субтитрах — как произнёс, на карточке — «Антонио Маргерити».
Ответов задач он не озвучивает — на экран ничего сверх речи не выносим (п.7 rules.md).
Вспышка не ставится: п.5 rules.md — вспышки отложены автором.
Картинки — Wikimedia Commons, качает work/IMG_1821/fetch.py; лицензии и авторы — downloads/candidates.json.
Ничего не сгенерировано.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, card  # noqa: E402

STEM = "IMG_1821"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
IMG = ROOT / f"studio/{STEM}/assets/img"
IMG.mkdir(parents=True, exist_ok=True)
# фон за спиной (п.13 rules.md): выбран глазами из кандидатов fetch.py, лицензии — candidates.json
#   забор — «Old wooden fence in Nygårds, Gotland.jpg», CC BY-SA 4.0 (W.carter);
#   латинская надпись — «Luxembourg Cathédrale Notre-Dame Latin inscription 1613.jpg», CC BY-SA 3.0;
#   купцы — Квентин Массейс, «Меняла с женой», 1514, PD; Тарантино — Gage Skidmore, CC BY-SA 3.0.
BG = {"bg_fence.jpg": "fence_1.jpg", "bg_latin.jpg": "latin_2.jpg", "bg_merch.jpg": "merchant_1.jpg"}
for dst_name, src_name in {"tarantino.jpg": "tarantino.jpg", **BG}.items():
    src = ROOT / f"work/{STEM}/downloads/{src_name}"
    if not src.exists():
        sys.exit(f"✗ нет {src.name} — запусти work/{STEM}/fetch.py (картинки с Wikimedia Commons)")
    dst = IMG / dst_name
    if not (dst.exists() and dst.samefile(src)):
        shutil.copyfile(src, dst)


def word(text: str, near: float) -> int:
    """Номер слова исходника по тексту и примерному времени — не считать номера руками."""
    best = min((i for i, w in enumerate(tk.src_words) if w["word"] == text),
               key=lambda i: abs(tk.src_words[i]["start"] - near), default=None)
    if best is None or abs(tk.src_words[best]["start"] - near) > 0.5:
        raise ValueError(f"слово «{text}» около {near} с не нашлось в распознавании")
    return best


CHEST = 1290        # верх плашек на груди: подбородок при базе 1.2 (та же съёмка, что IMG_1796)
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
      #bg-merch img { object-position: 50% 30%; }
      /* Тарантино — слева и уже: справа карточка закрывала лицо (verify_page) */
      #c-tar { left: 100px; top: 280px; width: 236px; padding: 12px 12px 10px; }
      #c-tar .ph { width: 212px; height: 240px; }
      #c-tar img { width: 212px; height: 240px; }
      #c-tar .card-name { font-size: 20px; margin-top: 8px; }
      #c-tar .card-sub { font-size: 22px; }
      /* пластырь крест-накрест на знаке */
      .plaster { left: 340px; top: 410px; width: 400px; height: 74px; border-radius: 14px; background: #E9C9A2;
                 box-shadow: 0 10px 30px rgba(0,0,0,0.45);
                 background-image: radial-gradient(circle, rgba(120,80,40,0.35) 3px, transparent 4px); background-size: 22px 22px; }
      /* знак на детали */
      .part { position: absolute; left: 195px; top: 40px; width: 200px; height: 225px; opacity: 0; }
      .plab { position: absolute; top: 272px; width: 170px; text-align: center; font-family: "Manrope"; font-weight: 800;
              font-size: 26px; letter-spacing: 0.08em; text-transform: uppercase; color: #F5B82E; opacity: 0; }
      /* одна сотая */
      .frm { position: absolute; color: var(--cream); font-family: "Oswald"; font-size: 60px; opacity: 0; }
      .frm .katex-src { display: inline-block; font-size: 54px; }
      .frm .katex-display { margin: 0; }
      /* лист счёта купца */
      .ledger { padding: 22px 34px 26px; background: #F3EAD6; border-radius: 8px; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      .lg-h { font-family: "Manrope"; font-weight: 800; font-size: 24px; letter-spacing: 0.12em; text-transform: uppercase;
              color: #6A5A44; text-align: center; margin-bottom: 6px; }
      .lg-r { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 2px solid rgba(42,34,25,0.15);
              font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 44px; line-height: 1.25; color: #2A2219;
              font-variant-numeric: lining-nums; opacity: 0; }
      .lg-r b { color: #A3241C; }
      .lg-stamp { position: absolute; left: 300px; top: 120px; font-family: "Oswald"; font-weight: 700; font-size: 70px;
                  text-transform: uppercase; color: #C7271F; border: 6px solid #C7271F; border-radius: 10px; padding: 0 16px;
                  transform: rotate(-10deg); opacity: 0; }
      /* слово укорачивается */
      .st { position: absolute; left: 0; top: 64px; width: 590px; text-align: center; font-family: "Cormorant"; font-style: italic;
            font-weight: 700; font-size: 104px; line-height: 1.1; color: var(--cream); opacity: 0; white-space: nowrap; }
      .st sup, .st sub { font-size: 0.55em; }
      .pp { position: relative; display: inline-block; }
      .pstrike { position: absolute; left: -6px; right: -6px; top: 52%; height: 9px; border-radius: 5px; background: var(--red);
                 transform-origin: 0 50%; transform: scaleX(0); }
      .pcens { position: absolute; left: -16px; right: -16px; top: 12%; height: 86%; border-radius: 10px; background: #0C0C0D;
               border: 2px solid rgba(242,235,221,0.35); display: flex; align-items: center; justify-content: center;
               font-family: "Oswald"; font-style: normal; font-size: 26px; letter-spacing: 0.08em; color: var(--cream); opacity: 0; }
      .ltrack { position: absolute; left: 40px; top: 236px; width: 510px; height: 26px; border-radius: 13px; background: rgba(242,235,221,0.14); }
      .lfill { position: absolute; left: 40px; top: 236px; width: 510px; height: 26px; border-radius: 13px; background: #F5B82E;
               transform-origin: 0 50%; opacity: 0; }
      /* до / после */
      .ba-l { position: absolute; left: 10px; top: 76px; width: 250px; text-align: center; font-family: "Cormorant"; font-style: italic;
              font-weight: 700; font-size: 66px; color: var(--cream); opacity: 0; white-space: nowrap; }
      .ba-r { position: absolute; left: 390px; top: 30px; width: 180px; text-align: center; font-family: "Oswald"; font-weight: 700;
              font-size: 150px; line-height: 1; color: #F0352C; opacity: 0; }
'''


def tex(s: str) -> str:
    return f'<span class="katex-src" data-tex="{s}"></span>'


def bg(bid: str, img: str) -> str:
    return f'        <div id="{bid}" class="g bg"><img src="assets/img/{img}" alt="" /><div class="vig"></div></div>'


STROKE = 'fill="none" stroke="#F2EBDD" stroke-width="12" stroke-linecap="round"'


def part(pid: str, shape: str) -> str:
    return f'<svg id="{pid}" class="part" viewBox="0 0 160 180">{shape}</svg>'


C1 = f'<circle cx="34" cy="36" r="20" {STROKE} />'
SL = f'<path d="M 112 14 L 40 166" {STROKE} />'
C2 = f'<circle cx="98" cy="150" r="20" {STROKE} />'

# ---------- знак на детали (15.7–21.1): нолик · палочка · нолик ----------
parts = (f'        <div id="p-parts" class="g panel" {SAFE} style="{PANEL} height: 330px;">\n'
         f'          {part("pc1", C1)}{part("psl", SL)}{part("pc2", C2)}\n'
         '          <div id="pl1" class="plab" style="left: 40px;">нолик</div>\n'
         '          <div id="pl2" class="plab" style="left: 210px;">палочка</div>\n'
         '          <div id="pl3" class="plab" style="left: 380px;">нолик</div>\n'
         '        </div>')

# ---------- одна сотая (32.3–34.0): круг на сто долей, одна красная ----------
RING = 'cx="110" cy="110" r="78" fill="none" stroke-width="34"'
share = (f'        <div id="p-share" class="g panel" {SAFE} style="{PANEL} height: 260px;">\n'
         '          <svg viewBox="0 0 220 220" style="position: absolute; left: 24px; top: 20px; width: 220px; height: 220px;">'
         f'<circle id="ring" {RING} stroke="rgba(242,235,221,0.35)" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"'
         ' transform="rotate(-90 110 110)" />'
         f'<circle id="ring1" {RING} stroke="#F0352C" pathLength="100" stroke-dasharray="2.2 97.8" transform="rotate(-90 110 110)"'
         ' style="opacity: 0;" /></svg>\n'
         '          <div id="sh-t" class="tag" style="position: absolute; left: 260px; top: 40px; width: 300px; opacity: 0;">одна сотая</div>\n'
         f'          <div id="sh-f" class="frm" style="left: 270px; top: 92px; width: 290px; text-align: center;">{tex(r"1\% = \tfrac{1}{100}")}</div>\n'
         '        </div>')

# ---------- счёт купца (38.3–43.0): в каждой строчке per cento ----------
ITEMS = [("lana", "5"), ("seta", "8"), ("spezie", "12"), ("vino", "6"), ("sale", "10")]
rows = "".join(f'<div id="lr{i}" class="lg-r"><span>{a}</span><span>{n} <b>per cento</b></span></div>'
               for i, (a, n) in enumerate(ITEMS))
ledger = (f'        <div id="p-ledger" class="g ledger" {SAFE} style="left: 245px; top: {CHEST - 40}px; width: 590px;">\n'
          f'          <div class="lg-h">libro dei conti · счёт купца</div>{rows}\n'
          '          <div id="lg-st" class="lg-stamp">надоело</div>\n'
          '        </div>')

# ---------- слово укорачивается (43.4–57.6): запись и её длина ----------
shrink = (f'        <div id="p-shrink" class="g panel" {SAFE} style="{PANEL} height: 300px;">\n'
          '          <div class="tag" style="position: absolute; left: 34px; top: 20px; width: 320px; text-align: left;">сокращение</div>\n'
          '          <div id="sh-17" class="tag gold" style="position: absolute; left: 400px; top: 20px; width: 170px; opacity: 0;'
          ' font-size: 30px;">XVII век</div>\n'
          '          <div id="s1" class="st">per cento</div>\n'
          '          <div id="s2" class="st">per c<sup>o</sup></div>\n'
          '          <div id="s3" class="st"><span class="pp">per<span id="s3-x" class="pstrike"></span>'
          '<span id="s3-c" class="pcens">ЦЕНЗУРА</span></span>&nbsp;<sup>o</sup>/<sub>o</sub></div>\n'
          '          <div id="s4" class="st"><sup>o</sup>/<sub>o</sub></div>\n'
          '          <div class="ltrack"></div><div id="lfill" class="lfill"></div>\n'
          '        </div>')

# ---------- до / после (65.1–68.4): per cento → % за 300 лет ----------
ARROW = 'fill="none" stroke="#F2EBDD" stroke-width="8" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"'
before = (f'        <div id="p-ba" class="g panel" {SAFE} style="{PANEL} height: 220px;">\n'
          '          <div id="ba-l" class="ba-l">per cento</div>\n'
          '          <svg viewBox="0 0 120 60" style="position: absolute; left: 262px; top: 100px; width: 120px; height: 60px;">'
          f'<path id="ba-ar" d="M 6 30 L 110 30 M 88 12 L 110 30 L 88 48" {ARROW} /></svg>\n'
          '          <div id="ba-y" class="tag gold" style="position: absolute; left: 252px; top: 58px; width: 140px; opacity: 0;">300 лет</div>\n'
          '          <div id="ba-r" class="ba-r">%</div>\n'
          '        </div>')

# ---------- знак собирается за головой (59.4–60.9) ----------
BIGSTROKE = 'fill="none" stroke="#F0352C" stroke-width="16" stroke-linecap="round"'
big_parts = "".join(
    f'<svg id="{pid}" viewBox="0 0 160 180" style="position: absolute; left: 0; top: 0; width: 230px; height: 258px;">{s}</svg>'
    for pid, s in (("bc1", C1.replace(STROKE, BIGSTROKE)), ("bsl", SL.replace(STROKE, BIGSTROKE)),
                   ("bc2", C2.replace(STROKE, BIGSTROKE))))

behind = "\n".join([
    '        <div id="b-pct-lead" class="g lead" style="top: 272px;">знак процента</div>',
    '        <div id="b-pct" class="g big" style="top: 318px; font-size: 290px; color: #F0352C;">%</div>',
    '        <div id="pl-a" class="g plaster" style="transform: rotate(32deg);"></div>',
    '        <div id="pl-b" class="g plaster" style="transform: rotate(-32deg);"></div>',
    bg("bg-fence", "bg_fence.jpg"),
    '        <div id="fence-cens" class="g censor" style="top: 330px;"><span>ЦЕНЗУРА</span></div>',
    bg("bg-latin", "bg_latin.jpg"),
    '        <div id="b-lat-lead" class="g lead" style="top: 272px;">по-латыни</div>',
    '        <div id="b-lat-lead2" class="g lead" style="top: 272px;">«на сотню»</div>',
    '        <div id="b-lat" class="g big" style="top: 326px; font-size: 170px;">per centum</div>',
    bg("bg-merch", "bg_merch.jpg"),
    f'        <div id="b-asm" class="g" style="left: 425px; top: 236px; width: 230px; height: 258px;">{big_parts}</div>',
    '        <div id="b-300-lead" class="g lead" style="top: 272px;">вся эта лабуда длилась</div>',
    '        <div id="b-300" class="g big" style="top: 318px; font-size: 250px;"><span id="b-300-n">0</span> лет</div>',
])

STK = 'top: 300px; font-size: 56px; white-space: nowrap;'
STAMP = 'top: 290px; background: rgba(12,12,14,0.55); white-space: nowrap;'
front = "\n".join([
    f'        <div id="st-news" class="g stamp" style="left: 200px; {STAMP} font-size: 62px;">неприятная новость</div>',
    f'        <div id="st-joke" class="g stamp" style="left: 330px; {STAMP} font-size: 100px;">не шутка</div>',
    parts,
    f'        <div id="st-int" class="g sticker" style="left: 300px; {STK}">интересные вещи</div>',
    f'        <div id="st-why" class="g sticker" style="left: 380px; {STK}">в чём дело?</div>',
    share,
    card("c-tar", "tarantino.jpg", "Тарантино", "«Антонио Маргерити»", side="left"),
    ledger,
    shrink,
    f'        <div id="st-two" class="g sticker" style="left: 220px; {STK}">два нолика и чёрточка</div>',
    f'        <div id="st-300" class="g sticker" style="left: 330px; {STK}">затрёхсотили?</div>',
    before,
    f'        <div id="st-ege" class="g stamp" style="left: 340px; {STAMP} font-size: 110px;">ЕГЭ 80+</div>',
])


def bg_in(sel: str, a: float, b: float) -> str:
    """Фон наплывом со смазом, медленный наезд внутри, уход со смазом; на показе резкий."""
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.08, filter: BLUR(14) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.45, ease: "power2.out" }}, {a});\n'
            f'      tl.fromTo("{sel} img", {{ scale: 1 }}, {{ scale: 1.06, duration: {b - a + 0.35:.2f}, ease: "none" }}, {a});\n'
            f'      tl.to("{sel}", {{ opacity: 0, scale: 1.04, filter: BLUR(12), duration: 0.35, ease: "power2.in" }}, {b});')


def swap(a: str, b: str, at: float) -> str:
    """Стадия записи сменяется следующей: старая уходит вверх со смазом, новая встаёт."""
    return (f'      tl.to("{a}", {{ opacity: 0, y: -40, filter: BLUR(10), duration: 0.18, ease: "power2.in" }}, {at});\n'
            f'      tl.fromTo("{b}", {{ opacity: 0, y: 40, scale: 0.9, filter: BLUR(10) }}, '
            f'{{ opacity: 1, y: 0, scale: 1, filter: BLUR(0), duration: 0.24, ease: "power3.out" }}, {round(at + 0.12, 2)});')


def bar(at: float, sx: float) -> str:
    return f'      tl.to("#lfill", {{ scaleX: {sx}, duration: 0.4, ease: "power3.out" }}, {at});'


PANEL_IN = '{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }'
MOVE = 'duration: 0.35, ease: "back.out(1.6)"'
beats = f'''
      // ---------- хук: неприятная новость — знак процента — затрёхсотили ----------
      slam("#st-news", {t(8.70)}, {{ fromScale: 2.0, rot: -4, blur: 10 }});
      leave("#st-news", {t(10.20)}, {{ scale: 0.6, y: 0, rot: -12 }});
      enter("#b-pct-lead", {t(10.30)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-pct", {t(10.62)}, {{ fromScale: 1.6, rot: -4 }});
      slam("#pl-a", {t(13.20)}, {{ fromScale: 1.8, rot: 32, blur: 8 }});
      slam("#pl-b", {t(13.42)}, {{ fromScale: 1.8, rot: -32, blur: 8 }});
      leave(["#b-pct", "#b-pct-lead", "#pl-a", "#pl-b"], {t(14.30)}, {{ y: -80 }});
      slam("#st-joke", {t(14.56)}, {{ fromScale: 2.0, rot: -6, blur: 10 }});
      leave("#st-joke", {t(15.40)}, {{ scale: 0.6, y: 0, rot: -16 }});

      // ---------- почему процент — два нолика и палочка: знак на детали ----------
      enter("#p-parts", {t(15.62)}, {PANEL_IN});
      tl.fromTo("#pc1, #psl, #pc2", {{ opacity: 0, scale: 0.5 }}, {{ opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2)", stagger: 0.08 }}, {t(17.20)});
      tl.to("#pc1", {{ x: -170, {MOVE} }}, {t(18.16)});
      tl.to("#pc2", {{ x: 170, {MOVE} }}, {t(18.16)});
      enter("#pl1, #pl3", {t(18.30)}, {{ fromScale: 0.7, dur: 0.22 }});
      enter("#pl2", {t(18.80)}, {{ fromScale: 0.7, dur: 0.22 }});
      leave("#pl1, #pl2, #pl3", {t(19.70)}, {{ y: 20 }});
      tl.to("#pc1", {{ y: 71, {MOVE} }}, {t(19.90)});
      tl.to("#pc2", {{ y: -71, {MOVE} }}, {t(19.90)});
      tl.to("#psl", {{ rotation: -26, transformOrigin: "50% 50%", {MOVE} }}, {t(19.90)});
      leave("#p-parts", {t(21.10)}, {{ y: 80 }});
      enter("#st-int", {t(22.00)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-int", {t(24.60)}, {{ y: -30, rot: -10 }});

      // ---------- пишут на заборе: забор за спиной, цензура ----------
{bg_in("#bg-fence", t(24.95), t(27.05))}
      slam("#fence-cens", {t(26.18)}, {{ fromScale: 1.6, rot: -3 }});
      leave("#fence-cens", {t(27.00)}, {{ y: -60 }});
      enter("#st-why", {t(27.40)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-why", {t(28.30)}, {{ y: -30, rot: 10 }});

      // ---------- латынь за спиной: PER CENTUM, «на сотню» ----------
{bg_in("#bg-latin", t(28.40), t(32.05))}
      enter("#b-lat-lead", {t(29.52)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-lat", {t(30.22)}, {{ fromScale: 1.5 }});
{swap("#b-lat-lead", "#b-lat-lead2", t(31.26))}
      leave(["#b-lat", "#b-lat-lead2"], {t(31.95)}, {{ y: -60 }});

      // ---------- одна сотая доля: круг и формула ----------
      enter("#p-share", {t(32.24)}, {PANEL_IN});
      draw("#ring", {t(32.34)}, 0.35);
      enter("#sh-t", {t(32.54)}, {{ fromScale: 0.8, dur: 0.22 }});
      tl.fromTo("#ring1", {{ opacity: 0, scale: 1.25, svgOrigin: "110 110" }}, {{ opacity: 1, scale: 1, duration: 0.25, ease: "back.out(2.5)",
                immediateRender: false }}, {t(32.84)});
      enter("#sh-f", {t(33.10)}, {{ fromScale: 0.7, dur: 0.25 }});
      leave("#p-share", {t(34.05)}, {{ y: 80 }});

      // ---------- как у Тарантино ----------
      card("#c-tar", {t(34.30)}, {t(36.35)}, "left");

      // ---------- купцы за спиной и их счёт ----------
{bg_in("#bg-merch", t(36.48), t(42.80))}
      doc("#p-ledger", {t(38.30)}, {t(43.05)}, {{ fromRot: -6, rot: 1 }});
      tl.fromTo("#p-ledger .lg-r", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out", stagger: 0.55 }}, {t(38.84)});
      slam("#lg-st", {t(42.14)}, {{ fromScale: 2.2, rot: -10, blur: 8 }});

      // ---------- слово укорачивается: per cento → per c° → per °/₀ → °/₀ ----------
      enter("#p-shrink", {t(43.40)}, {PANEL_IN});
      tl.fromTo("#s1", {{ opacity: 0, y: 30, filter: BLUR(10) }}, {{ opacity: 1, y: 0, filter: BLUR(0), duration: 0.25, ease: "power3.out" }}, {t(44.54)});
      tl.fromTo("#lfill", {{ opacity: 0, scaleX: 0 }}, {{ opacity: 1, scaleX: 1, duration: 0.45, ease: "expo.out" }}, {t(44.60)});
{swap("#s1", "#s2", t(46.20))}
{bar(t(46.32), 0.62)}
      enter("#sh-17", {t(47.52)}, {{ fromScale: 0.6, dur: 0.25 }});
{swap("#s2", "#s3", t(48.90))}
{bar(t(49.10), 0.5)}
      tl.to("#s3-x", {{ scaleX: 1, duration: 0.2, ease: "power2.out" }}, {t(52.46)});
      slam("#s3-c", {t(53.78)}, {{ fromScale: 1.8, rot: -4, blur: 8 }});
{swap("#s3", "#s4", t(56.20))}
{bar(t(56.32), 0.24)}
      leave("#p-shrink", {t(57.60)}, {{ y: 80 }});
      enter("#st-two", {t(57.70)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-two", {t(58.90)}, {{ y: -30, rot: -10 }});

      // ---------- чистый знак процента: собирается из деталей за головой ----------
      tl.set("#b-asm", {{ opacity: 1 }}, {t(59.40)});
      tl.fromTo("#bc1", {{ opacity: 0, x: -520, rotation: -90, filter: BLUR(14) }}, {{ opacity: 1, x: 0, rotation: 0, filter: BLUR(0),
                duration: 0.5, ease: "power3.out" }}, {t(59.46)});
      tl.fromTo("#bc2", {{ opacity: 0, x: 520, rotation: 90, filter: BLUR(14) }}, {{ opacity: 1, x: 0, rotation: 0, filter: BLUR(0),
                duration: 0.5, ease: "power3.out" }}, {t(59.62)});
      tl.fromTo("#bsl", {{ opacity: 0, y: -360, filter: BLUR(14) }}, {{ opacity: 1, y: 0, filter: BLUR(0), duration: 0.16,
                ease: "power4.out" }}, {t(60.00)});
      tl.fromTo("#b-asm", {{ scale: 1 }}, {{ scale: 1.12, duration: 0.14, yoyo: true, repeat: 1, ease: "sine.inOut", immediateRender: false }}, {t(60.16)});
      leave("#b-asm", {t(60.85)}, {{ y: -60 }});

      // ---------- что значит «затрёхсотили»: 300 лет ----------
      enter("#st-300", {t(61.00)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-300", {t(62.90)}, {{ y: -30, rot: 10 }});
      enter("#b-300-lead", {t(63.10)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-300", {t(63.80)}, {{ fromScale: 1.3 }});
      tl.fromTo("#b-300-n", {{ textContent: 0 }}, {{ textContent: 300, snap: {{ textContent: 1 }}, duration: 0.5, ease: "power2.out",
                immediateRender: false }}, {t(63.80)});
      leave(["#b-300", "#b-300-lead"], {t(64.90)}, {{ y: -60 }});
      enter("#p-ba", {t(65.00)}, {PANEL_IN});
      enter("#ba-l", {t(65.20)}, {{ fromScale: 0.8, dur: 0.25 }});
      draw("#ba-ar", {t(65.45)}, 0.4);
      enter("#ba-y", {t(65.55)}, {{ fromScale: 0.7, dur: 0.22 }});
      slam("#ba-r", {t(66.94)}, {{ fromScale: 1.7, rot: -6 }});
      leave("#p-ba", {t(68.30)}, {{ y: 80 }});

      // ---------- ЕГЭ на 80+ ----------
      slam("#st-ege", {t(72.12)}, {{ fromScale: 2.0, rot: -5, blur: 10 }});
      leave("#st-ege", {t(73.80)}, {{ scale: 0.6, y: 0, rot: -14 }});
'''

# Звуки — мало (бриф: few), правила 12.10: удары на главном (%, % собрался, 300 лет), семейства не подряд,
# файл ≤ 2 раз, между звуками ≥ 1 с. Фоны, стикеры и визуализации — без звука.
sounds = [
    audio("pct", "whoosh", t(10.60), 0.8),
    audio("tar", "pop", t(34.28), 0.7),
    audio("cens", "click", t(53.76), 0.8),
    audio("asm", "impact-bass-1", t(60.00), 0.9),
    audio("y300", "whoosh-cinematic", t(63.78), 0.7),
]
# человек поверх фонов и слов за спиной
fg = [(t(10.25), t(14.75)), (t(24.90), t(27.45)), (t(28.35), t(32.45)), (t(36.43), t(43.20)),
      (t(59.35), t(61.25)), (t(63.05), t(65.30))]

CTA_AT = t(68.55)
page = build_page("Почему процент — два нолика и палочка", DUR, behind, front, beats, sounds, fg, cta_at=CTA_AT,
                  extra_css=css, cta_small="больше интересной математики — у меня в профиле",
                  fmt=tk.fmt, captions=tk.captions)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

# распознавание: «за трехсотили» — одно слово; «слова 100» — «сто»; «Продолжение следует...» — галлюцинация
# whisper на тишине −82 дБ (edit.json), не сказано
fixes = tk.fixes({word("за", 12.92): "затрёхсотили.", word("трехсотили.", 13.20): "",
                  word("за", 62.00): "затрёхсотили?", word("трехсотили?", 62.20): "",
                  word("100", 66.18): "сто", word("Продолжение", 73.82): ""})

director = {
    "_note": "Почему процент — два нолика и палочка. Время по дублю; раскладка — work/IMG_1821/page.py, план — plan.md.",
    "punches": [[t(10.62), t(11.60), 1.18, 0.10], [t(30.22), t(31.20), 1.20, 0.10], [t(60.00), t(60.90), 1.22, 0.10],
                [t(63.80), t(64.80), 1.20, 0.10]],
    "text_fixes": fixes,
    "keep_case": ["ЕГЭ", "Тарантино", "Антонио", "Маргаретти."],
    "accent_words": ["процента", "percentum", "300"],
    # плашки на груди — на их время субтитров нет (как в серии)
    "hide_captions": [[t(15.55), t(21.35)], [t(32.20), t(34.30)], [t(38.25), t(57.85)], [t(64.95), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
