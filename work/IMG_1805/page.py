"""Страница графики IMG_1805: логарифмы придумал «колдун» Непер — и придумал, чтобы было проще.

Время ударов — по исходнику, на шкалу дубля переводит Take (вырез 66.72–69.12 — первый заход
«А несколько лет тот самый Атрет»). План — work/IMG_1805/plan.md.
Проверено: Джон Непер (1550–1617), барон Мерчистон, Шотландия; легенда о чёрном петухе и саже — известный
анекдот о нём (слуги гладили петуха в тёмной комнате, у вора руки оставались чистыми). Главная книга —
«A Plaine Discovery of the Whole Revelation of Saint John», 1593: конец света между 1688 и 1700 годом.
Логарифмы — «Mirifici Logarithmorum Canonis Descriptio», 1614. Лаплас: логарифмы, сократив труд, «удвоили
жизнь астрономов». Слово — λόγος (отношение) + ἀριθμός (число). Уильям Отред (Oughtred, 1574–1660): знак «×»
(Clavis Mathematicae, 1631) и логарифмическая линейка (~1622–1630); линейками считали до 1970-х — около 350
лет. Базз Олдрин брал на Аполлон-11 линейку Pickett N600-ES. 100 · 1000 = 10⁵ — верно.
Картинки — Wikimedia Commons, лицензии в downloads/candidates.json. Доска — ManimGX, work/IMG_1805/manim/log.py.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import viz  # noqa: E402
from kit import Take, audio, build_page, card, doc_img  # noqa: E402

STEM = "IMG_1805"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
fmt = tk.fmt

# выбранные кандидаты из downloads/ (fetch.py) — выбор глазами
# Портрет Непера — масло 1616 г. (National Galleries of Scotland, PG 2228, PD). napier_1 — «портрет
# Шекспира», napier_3 — другой Непер: не брать. Титул «A Plaine Discovery» (1593) со свободной лицензией
# на Commons не нашёлся — на «считал не логарифмы» стикер, даты книги — на линии времени. Замок — настоящая башня Мерчистон
# (дневное фото, притемнено «в чёрное»). Луна за спиной — след ботинка Олдрина (Аполлон-11, AS11-40-5878):
# кадр с чёрным небом (Аполлон-17) verify_render v1 счёл пустой полосой сверху; сам Олдрин — на карточке.
IMG = {"napier": "napierp_2.jpg", "castle": "merchiston_2.jpg", "rooster": "rooster_2.jpg",
       "descriptio": "descriptio_1.jpg", "laplace": "laplace_1.jpg",
       "stars": "stars_1.jpg", "oughtred": "oughtred_1.jpg", "sliderule": "sliderule_2.jpg",
       "aldrin": "aldrin_1.jpg", "moon": "moon_2.jpg"}

SAFE = 'data-safe="лицо важнее серой зоны: плашка ниже подбородка (Валера, 12.10)"'
css = '''      .panel { border-radius: 28px; background: rgba(12,12,14,0.88); border: 2px solid rgba(242,235,221,0.16);
               box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      .row { display: flex; align-items: center; gap: 22px; padding: 8px 6px; opacity: 0;
             border-bottom: 2px solid rgba(242,235,221,0.12); }
      .row:last-child { border-bottom: none; }
      .row-n { display: inline-block; width: 54px; height: 54px; border-radius: 27px; background: var(--red);
               font-family: "Oswald"; font-weight: 700; font-size: 34px; line-height: 54px; text-align: center; color: var(--cream); }
      .row-w { font-family: "Manrope"; font-weight: 800; font-size: 40px; color: var(--cream); }
      .row-s { margin-left: auto; font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.08em;
               text-transform: uppercase; color: rgba(242,235,221,0.6); }
      .hand-dot { display: inline-block; width: 54px; height: 54px; border-radius: 14px; }
      .bg { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden; opacity: 0; }
      .bg img { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover;
                filter: brightness(0.7) saturate(0.9) contrast(1.05); }
      .bg .vig { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px;
                 background: radial-gradient(ellipse at 50% 42%, rgba(0,0,0,0) 38%, rgba(0,0,0,0.55) 100%),
                             linear-gradient(to bottom, rgba(0,0,0,0) 72%, rgba(0,0,0,0.5) 100%); }
      .num { position: absolute; left: 0; width: 1080px; opacity: 0; }
      .lc { text-transform: none; }
      #bg-castle img { filter: brightness(0.42) saturate(0.6) contrast(1.15); }
      #c-napier img { object-position: 58% 20%; }
      #c-rooster img { object-position: 32% 22%; }
      #c-laplace img { object-position: 45% 25%; }
      #c-oughtred img { object-position: 50% 28%; }
      #c-aldrin img { object-position: 52% 10%; }
      /* карточки уже и у краёв: лицо при наезде шире обычного (verify_page, 15.10) */
      .card { width: 230px; padding: 12px 12px 10px; }
      .card .ph, .card img { width: 206px; height: 230px; }
      .card-name { font-size: 19px; }
      .card-sub { font-size: 21px; }
      .card-right { left: 760px; }
      .card-left { left: 85px; }
      /* линия времени */
      .tl-axis { position: absolute; left: 40px; top: 118px; width: 510px; height: 6px; border-radius: 3px;
                 background: rgba(242,235,221,0.5); transform-origin: 0 50%; }
      .tl-mark { position: absolute; top: 100px; width: 6px; height: 42px; margin-left: -3px; border-radius: 3px; background: var(--cream); }
      .tl-lab { position: absolute; width: 200px; margin-left: -100px; text-align: center; font-family: "Oswald"; font-weight: 700;
                font-size: 40px; color: var(--cream); font-variant-numeric: lining-nums; }
      .tl-sub { position: absolute; width: 220px; margin-left: -110px; text-align: center; font-family: "Manrope"; font-weight: 800;
                font-size: 22px; letter-spacing: 0.08em; text-transform: uppercase; color: rgba(242,235,221,0.65); }
      .tl-range { position: absolute; top: 108px; height: 26px; border-radius: 6px; background: var(--red); transform-origin: 0 50%; }
      /* логос + арифмос */
      .gr { position: absolute; top: 28px; width: 250px; text-align: center; opacity: 0; }
      .gr-w { font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 72px; color: var(--cream); line-height: 1; }
      .gr-s { margin-top: 6px; font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.08em;
              text-transform: uppercase; color: rgba(242,235,221,0.65); }
      .gr-res { position: absolute; left: 0; top: 145px; width: 590px; text-align: center; font-family: "Oswald"; font-weight: 700;
                font-size: 84px; text-transform: uppercase; color: var(--red); opacity: 0; }
      .bar-l { font-family: "Manrope"; font-weight: 800; font-size: 28px; letter-spacing: 0.06em; text-transform: uppercase;
               color: rgba(242,235,221,0.75); margin: 8px 0 8px; }
      .bar2 { height: 64px; border-radius: 10px; transform-origin: 0 50%; display: flex; align-items: center; justify-content: flex-end;
              padding-right: 18px; font-family: "Oswald"; font-weight: 700; font-size: 40px; color: var(--ink); }
'''


def bg(bid: str, img: str, pos: str = "50% 50%") -> str:
    return (f'        <div id="{bid}" class="bg"><img src="assets/img/{img}" alt="" style="object-position: {pos};" />'
            f'<div class="vig"></div></div>')


def counter(cid: str, values: list, top: int, size: int, suffix: str = "") -> str:
    """Счётчик за спиной: цифры сменяются через set — покадровый рендер видит то же, что снимок."""
    spans = "".join(f'<span id="{cid}{k}" class="num">{v}{suffix}</span>' for k, v in enumerate(values))
    return (f'        <div id="{cid}" class="g big" style="top: {top}px; font-size: {size}px;">{spans}'
            f'<span style="visibility: hidden;">{values[-1]}{suffix}</span></div>')


def counter_js(cid: str, n: int, at: float, step: float) -> str:
    return "\n".join([f'      tl.set("#{cid}{k}", {{ opacity: 1 }}, {at + k * step:.2f});' for k in range(n)]
                     + [f'      tl.set("#{cid}{k}", {{ opacity: 0 }}, {at + (k + 1) * step:.2f});' for k in range(n - 1)])


T0 = max(t(0.10), 0.10)
Y350 = [0, 30, 80, 150, 220, 280, 320, 340, 350]
A350 = t(76.16) - 0.3

behind = "\n".join([
    bg("bg-castle", IMG["castle"]),
    bg("bg-stars", IMG["stars"]),
    bg("bg-moon", IMG["moon"], "60% 50%"),
    '        <div id="b-log" class="g big serif lc" style="top: 285px; font-size: 280px; font-style: italic;">log</div>',
    '        <div id="b-koldun" class="g big red" style="top: 300px; font-size: 200px;">колдун</div>',
    '        <div id="b-sazha" class="g big" style="top: 290px; font-size: 230px;">сажа</div>',
    '        <div id="b-x" class="g big red" style="top: 260px; font-size: 340px;">×</div>',
    '        <div id="b-350-lead" class="g lead" style="top: 262px;">лет считали на линейке</div>',
    counter("b-350", Y350, 310, 230),
    '        <div id="b-noi" class="g big" style="top: 300px; font-size: 200px;">не ной</div>',
    '        <div id="b-easy" class="g big red" style="top: 300px; font-size: 200px;">проще</div>',
])

# уравнение ЕГЭ — вёрсткой, а не KaTeX: у KaTeX «4» уезжала за правый край плашки в кнопки (verify_page)
f_ege = ('        <div id="f-ege" class="g panel" style="left: 290px; top: 1250px; width: 500px; height: 110px; display: flex; '
         'align-items: center; justify-content: center; font-family: \'Cormorant\'; font-style: italic; font-weight: 700; '
         'font-size: 64px; color: var(--cream); font-variant-numeric: lining-nums; white-space: nowrap;">'
         'log<sub style="font-size: 0.55em;">3</sub>(x + 4) = 2</div>',
         f'      slam("#f-ege", {t(4.12):.2f});\n      leave("#f-ege", {t(6.62):.2f}, {{ y: -60, dur: 0.28 }});')

STICK = 'class="g sticker" style="left: {l}px; top: {top}px; font-size: 58px; white-space: nowrap;"'
st = lambda sid, text, l, top=300: f'        <div id="{sid}" {STICK.format(l=l, top=top)}>{text}</div>'

steps = (f'        <div id="d-steps" class="g panel" {SAFE} style="left: 245px; top: 1250px; width: 590px; padding: 6px 26px;">\n'
         '          <div id="sp1" class="row"><span class="row-n">1</span><span class="row-w">пропажа в замке</span></div>\n'
         '          <div id="sp2" class="row"><span class="row-n">2</span><span class="row-w">слуги по одному</span></div>\n'
         '          <div id="sp3" class="row"><span class="row-n">3</span><span class="row-w">тёмная комната</span></div>\n'
         '          <div id="sp4" class="row"><span class="row-n">4</span><span class="row-w">погладить петуха</span></div>\n'
         '        </div>')
hands = (f'        <div id="d-hands" class="g panel" {SAFE} style="left: 245px; top: 1250px; width: 590px; padding: 8px 26px;">\n'
         '          <div id="hd1" class="row"><i class="hand-dot" style="background: #0B0B0B; border: 3px solid rgba(242,235,221,0.5);"></i>'
         '<span class="row-w">честные</span><span class="row-s">руки в саже</span></div>\n'
         '          <div id="hd2" class="row"><i class="hand-dot" style="background: var(--cream);"></i>'
         '<span class="row-w">вор</span><span class="row-s">чистые руки</span></div>\n'
         '        </div>\n'
         '        <div id="st-thief" class="g stamp" style="left: 445px; top: 300px; font-size: 100px;">вор</div>')


def x_of(year: float) -> float:
    """Год → x на оси линии времени. Ось с разрывом: 1580…1720 — на 40…380 px, 2026 — у правого края,
    иначе подписи 1593 и 1688–1700 налезали друг на друга (снимок 15.10)."""
    if year > 1800:
        return 500
    return 40 + (year - 1580) / 140 * 340


timeline = (f'        <div id="d-time" class="g panel" {SAFE} style="left: 245px; top: 1250px; width: 590px; height: 205px;">\n'
            '          <div id="tl-axis" class="tl-axis"></div>\n'
            '          <span class="tl-lab" style="left: 430px; top: 92px; width: 60px; margin-left: -30px; '
            'color: rgba(242,235,221,0.7); background: rgba(12,12,14,1);">⋯</span>\n'
            f'          <div id="tl-1593" style="opacity: 0;"><i class="tl-mark" style="left: {x_of(1593):.0f}px;"></i>'
            f'<span class="tl-lab" style="left: {x_of(1593):.0f}px; top: 34px;">1593</span>'
            f'<span class="tl-sub" style="left: {x_of(1593) + 30:.0f}px; top: 152px;">книга</span></div>\n'
            f'          <div id="tl-end" style="opacity: 0;"><i id="tl-range" class="tl-range" style="left: {x_of(1688):.0f}px; '
            f'width: {x_of(1700) - x_of(1688):.0f}px;"></i>'
            f'<span class="tl-lab" style="left: {x_of(1694):.0f}px; top: 34px; color: var(--red);">1688–1700</span>'
            f'<span class="tl-sub" style="left: {x_of(1694):.0f}px; top: 152px; color: var(--red);">конец света</span></div>\n'
            f'          <div id="tl-now" style="opacity: 0;"><i class="tl-mark" style="left: {x_of(2026):.0f}px; background: #F5B82E;"></i>'
            f'<span class="tl-lab" style="left: {x_of(2026):.0f}px; top: 34px; color: #F5B82E;">2026</span>'
            f'<span class="tl-sub" style="left: {x_of(2026):.0f}px; top: 152px; color: #F5B82E;">мы тут</span></div>\n'
            '        </div>\n'
            '        <div id="st-mimo" class="g stamp" style="left: 385px; top: 300px; font-size: 110px;">мимо</div>')
bars2 = (f'        <div id="d-bars" class="g panel" {SAFE} style="left: 245px; top: 1250px; width: 590px; padding: 8px 30px 16px;">\n'
         '          <div class="bar-l">расчёт без логарифмов</div>\n'
         '          <div id="bar-a" class="bar2" style="width: 530px; background: var(--cream);">100%</div>\n'
         '          <div class="bar-l">с логарифмами</div>\n'
         '          <div id="bar-b" class="bar2" style="width: 265px; background: var(--red); color: var(--cream);">50%</div>\n'
         '        </div>')
greek = (f'        <div id="d-greek" class="g panel" {SAFE} style="left: 245px; top: 1250px; width: 590px; height: 235px;">\n'
         '          <div id="gr1" class="gr" style="left: 0px;"><div class="gr-w">λόγος</div><div class="gr-s">отношение</div></div>\n'
         '          <div id="gr-plus" class="gr" style="left: 170px; width: 250px;"><div class="gr-w" style="color: var(--red);">+</div></div>\n'
         '          <div id="gr2" class="gr" style="left: 335px;"><div class="gr-w">ἀριθμός</div><div class="gr-s">число</div></div>\n'
         '          <div id="gr-res" class="gr-res">логарифм</div>\n'
         '        </div>')
board = viz.board("bd", STEM, "Log.mp4", at=t(50.90), fmt=fmt, place=(260, 1250, 560, 373))
board = (board[0].replace('class="g viz"', f'class="g viz" {SAFE}', 1), board[1])

DOC = dict(left=270, top=1250, width=540, height=200)
front = "\n".join([
    f_ege[0],
    card("c-napier", IMG["napier"], "Джон Непер", "1550–1617, Шотландия", side="right"),
    st("st-stress", "НЕпер? НепЕр?", 300),
    st("st-night", "бродит ночью", 330),
    card("c-rooster", IMG["rooster"], "чёрный петух", "находит вора", side="left"),
    st("st-how", "как?", 470),
    steps,
    st("st-crow", "кукареку = вор", 320),
    hands,
    st("st-magic", "магия", 140, 290),
    st("st-psy", "психология", 380, 380),
    st("st-soot", "немного сажи", 300, 470),
    st("st-stress2", "НЕпер? НепЕр?", 300),
    st("st-notlog", "вообще не логарифмы", 260),
    timeline,
    doc_img("d-desc", IMG["descriptio"], "Непер, «Описание таблицы логарифмов» (1614; изд. 1620)", position="50% 12%", **DOC)
    .replace('class="g doc"', f'class="g doc" {SAFE}', 1),
    board[0],
    card("c-laplace", IMG["laplace"], "Лаплас", "«удвоили жизнь астрономов»", side="left"),
    bars2,
    greek,
    card("c-oughtred", IMG["oughtred"], "Уильям Отред", "«×» и линейка", side="right"),
    doc_img("d-rule", IMG["sliderule"], "логарифмическая линейка", position="50% 42%", **DOC)
    .replace('class="g doc"', f'class="g doc" {SAFE}', 1),
    card("c-aldrin", IMG["aldrin"], "Базз Олдрин", "Аполлон-11, 1969", side="left"),
    st("st-backup", "на всякий случай", 300),
])

beats = f'''
      // ---------- фоны за спиной: наплыв из размытия, медленный наезд, уход в студию ----------
      function bgIn(sel, tIn, tOut) {{
        tl.fromTo(sel, {{ opacity: 0, filter: "blur(14px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.7, ease: "power2.out" }}, tIn);
        tl.fromTo(`${{sel}} img`, {{ scale: 1.08 }}, {{ scale: 1.0, duration: tOut - tIn + 0.6, ease: "none" }}, tIn);
        tl.to(sel, {{ opacity: 0, filter: "blur(10px)", duration: 0.5, ease: "power2.in" }}, tOut);
      }}
      bgIn("#bg-castle", {t(10.85)}, {t(16.90)});
      bgIn("#bg-stars", {t(56.00)}, {t(59.30)});
      bgIn("#bg-moon", {t(77.20)}, {t(80.60)});

      // ---------- хук: «log» за спиной → «КОЛДУН» ----------
      slam("#b-log", {T0}, {{ fromScale: 1.5 }});
      leave("#b-log", {t(2.62)}, {{ y: -40, dur: 0.12 }});
      slam("#b-koldun", {t(2.70)}, {{ fromScale: 1.6 }});
      leave("#b-koldun", {t(4.00)}, {{ y: -60 }});
{f_ege[1]}

      // ---------- Непер, замок, петух ----------
      card("#c-napier", {t(7.10)}, {t(9.20)}, "right");
      enter("#st-stress", {t(9.40)}, {{ fromScale: 0.85, rot: -4 }});
      leave("#st-stress", {t(10.70)}, {{ y: -30, rot: -10 }});
      enter("#st-night", {t(12.70)}, {{ fromScale: 0.85, rot: 3 }});
      leave("#st-night", {t(13.90)}, {{ y: -30, rot: 8 }});
      card("#c-rooster", {t(14.00)}, {t(16.60)}, "left");
      enter("#st-how", {t(16.96)}, {{ fromScale: 0.7, rot: -6 }});
      leave("#st-how", {t(18.00)}, {{ y: -30, rot: -12 }});

      // ---------- как это работало: шаги ----------
      enter("#d-steps", {t(18.20)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#sp1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(18.40)});
      tl.fromTo("#sp2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(20.32)});
      tl.fromTo("#sp3", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(21.84)});
      tl.fromTo("#sp4", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(22.66)});
      leave("#d-steps", {t(24.10)}, {{ y: 80 }});
      enter("#st-crow", {t(24.20)}, {{ fromScale: 0.85, rot: -4 }});
      leave("#st-crow", {t(25.15)}, {{ y: -30, rot: -10 }});

      // ---------- разгадка: сажа ----------
      slam("#b-sazha", {t(26.74)}, {{ fromScale: 1.6 }});
      leave("#b-sazha", {t(28.00)}, {{ y: -60 }});
      enter("#d-hands", {t(27.10)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#hd1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(27.30)});
      tl.fromTo("#hd2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(29.94)});
      slam("#st-thief", {t(32.04)}, {{ fromScale: 1.6, rot: -8 }});
      leave(["#d-hands", "#st-thief"], {t(32.55)}, {{ y: 80 }});
      enter("#st-magic", {t(33.18)}, {{ fromScale: 0.85, rot: -4 }});
      enter("#st-psy", {t(33.48)}, {{ fromScale: 0.85, rot: 3 }});
      enter("#st-soot", {t(34.36)}, {{ fromScale: 0.85, rot: -3 }});
      leave(["#st-magic", "#st-psy", "#st-soot"], {t(35.10)}, {{ y: -30 }});

      // ---------- главная работа жизни: конец света ----------
      enter("#st-stress2", {t(37.44)}, {{ fromScale: 0.85, rot: 4 }});
      leave("#st-stress2", {t(38.80)}, {{ y: -30, rot: 10 }});
      enter("#st-notlog", {t(39.66)}, {{ fromScale: 0.85, rot: -4 }});
      leave("#st-notlog", {t(41.10)}, {{ y: -30, rot: -10 }});
      enter("#d-time", {t(41.22)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#tl-axis", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.5, ease: "power2.out", immediateRender: false }}, {t(41.40)});
      tl.fromTo("#tl-1593", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.25, ease: "power2.out" }}, {t(41.70)});
      tl.fromTo("#tl-end", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.25, ease: "power2.out" }}, {t(44.50)});
      tl.fromTo("#tl-range", {{ scaleX: 0.2 }}, {{ scaleX: 1, duration: 0.6, ease: "power2.out", immediateRender: false }}, {t(45.54)});
      tl.fromTo("#tl-now", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.2, ease: "power2.out" }}, {t(47.40)});
      slam("#st-mimo", {t(47.64)}, {{ fromScale: 1.7, rot: -8 }});
      leave(["#d-time", "#st-mimo"], {t(48.30)}, {{ y: 80 }});

      // ---------- зачем логарифмы: умножение → сложение ----------
      doc("#d-desc", {t(48.42)}, {t(50.70)}, {{ rot: 2, fromRot: -6 }});
{board[1]}

      // ---------- Лаплас: вдвое меньше времени ----------
      card("#c-laplace", {t(56.06)}, {t(59.20)}, "left");
      enter("#d-bars", {t(59.46)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      bars("#bar-a", {t(59.70)});
      bars("#bar-b", {t(60.64)});
      leave("#d-bars", {t(62.05)}, {{ y: 80 }});

      // ---------- логос + арифмос ----------
      enter("#d-greek", {t(62.20)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#gr1", {{ opacity: 0, x: -40 }}, {{ opacity: 1, x: 0, duration: 0.25, ease: "power2.out" }}, {t(64.20)});
      tl.fromTo("#gr2", {{ opacity: 0, x: 40 }}, {{ opacity: 1, x: 0, duration: 0.25, ease: "power2.out" }}, {t(65.36)});
      tl.fromTo("#gr-plus", {{ opacity: 0, scale: 0.4 }}, {{ opacity: 1, scale: 1, duration: 0.2, ease: "back.out(2)" }}, {t(65.20)});
      tl.fromTo("#gr-res", {{ opacity: 0, y: 30, scale: 0.8 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.25, ease: "back.out(1.7)" }}, {t(65.84)});
      leave("#d-greek", {t(66.55)}, {{ y: 80 }});

      // ---------- Отред: крестик умножения и линейка ----------
      card("#c-oughtred", {t(69.22)}, {t(71.30)}, "right");
      slam("#b-x", {t(71.56)}, {{ fromScale: 1.6, rot: 0 }});
      leave("#b-x", {t(72.90)}, {{ y: -60 }});
      doc("#d-rule", {t(73.10)}, {t(75.30)}, {{ rot: -2, fromRot: 6 }});
      enter("#b-350", {A350:.2f}, {{ fromScale: 1.3, dur: 0.2 }});
      enter("#b-350-lead", {A350 + 0.3:.2f}, {{ fromScale: 0.9, dur: 0.25 }});
{counter_js("b-350", len(Y350), A350, 0.06)}
      leave(["#b-350", "#b-350-lead"], {t(77.10)}, {{ y: -60 }});

      // ---------- Олдрин и Луна ----------
      card("#c-aldrin", {t(77.50)}, {t(79.05)}, "left");
      enter("#st-backup", {t(79.18)}, {{ fromScale: 0.85, rot: -4 }});
      leave("#st-backup", {t(80.50)}, {{ y: -30, rot: -10 }});

      // ---------- итог: не ной — проще ----------
      slam("#b-noi", {t(81.22)}, {{ fromScale: 1.6 }});
      leave("#b-noi", {t(83.00)}, {{ y: -40, dur: 0.12 }});
      slam("#b-easy", {t(83.14)}, {{ fromScale: 1.6 }});
      leave("#b-easy", {t(83.70)}, {{ y: -60 }});
'''
# Звуки — по правилам проекта (12.10): удары только на «колдуном» и «сажей», остальное тихо и по одному
# на событие; одинаковые семейства не подряд, файл не больше двух раз (pop — Непер и плашка CTA).
sounds = [
    audio("koldun", "impact-bass-1", t(2.68), 1.0),
    audio("napier", "pop", t(7.08), 0.8),
    audio("castle", "whoosh", t(10.85), 0.7),
    audio("sazha", "impact-bass-2", t(26.72), 1.0),
    audio("mimo", "click", t(47.62), 0.9),
    audio("stars", "chime", t(56.00), 0.6),
    audio("y350", "ping", A350, 0.7),
    audio("moon", "whoosh-cinematic", t(77.20), 0.6),
]
CTA_AT = t(83.76)
# человек поверх слов, фонов и счётчиков за спиной
# окно вырезки с самого 0 рендер не включает (tl.set в 0 не срабатывает на первом кадре — verify_page):
# начинаем с 0.1 с дубля, «log» влетает тогда же
fg = [(T0, t(4.30)), (t(10.80), t(17.40)), (t(26.65), t(28.30)), (t(55.95), t(59.85)),
      (t(71.50), t(73.20)), (A350 - 0.1, t(83.76))]
page = build_page("Логарифмы придумал колдун", DUR, behind, front, beats, sounds, fg, cta_at=CTA_AT,
                  extra_css=css, fmt=fmt, captions=tk.captions)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")


def src_idx(word: str, after: float = 0.0) -> list:
    """Номера слов исходника с таким текстом (после секунды after) — не считаем номера руками."""
    return [i for i, w in enumerate(tk.src_words) if w["word"] == word and w["start"] >= after]


# whisper: «немного Саша» — это «сажи» (петуха мазали сажей); «Атрет» — Отред (Oughtred); «Бас» — Базз
fixes = tk.fixes({**{i: "сажи." for i in src_idx("Саша.")},
                  **{i: "Отред," for i in src_idx("Атрет,", after=69.2)},
                  **{i: "Базз" for i in src_idx("Бас")},
                  **{i: "вора" for i in src_idx("вору")}})

director = {
    "_note": "Логарифмы придумал колдун. Время по дублю; раскладка — work/IMG_1805/page.py.",
    "punches": [[t(2.70), t(4.00), 1.30, 0.10], [t(16.96), t(18.10), 1.26, 0.10], [t(26.74), t(27.90), 1.30, 0.10],
                [t(35.18), t(40.90), 1.26, 1.80, 0.50],                       # медленный наезд через мысль
                [t(47.64), t(48.40), 1.30, 0.10],
                [t(69.14), t(70.40), 1.24, 0.0, 0.6],                         # прячет склейку после выреза
                [t(71.56), t(72.80), 1.28, 0.10], [t(81.22), t(83.50), 1.30, 0.10]],
    "text_fixes": fixes,
    "keep_case": ["ЕГЭ"],
    "accent_words": ["колдуном", "логарифмы", "сажей", "мимо.", "сложение,", "проще."],
    # на время плашек на груди, документов, доски и формул — субтитров нет
    "hide_captions": [[t(4.05), t(7.00)], [t(18.15), t(24.15)], [t(27.05), t(32.85)], [t(41.15), t(48.35)],
                      [t(48.40), t(50.95)], [t(50.85), t(56.60)], [t(59.40), t(62.35)], [t(62.15), t(66.70)],
                      [t(73.05), t(75.65)], [CTA_AT - 0.05, DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
