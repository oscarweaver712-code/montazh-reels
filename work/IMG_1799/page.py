"""Страница графики IMG_1799: знак бесконечности придумал британский шифровальщик.

Время ударов — по исходнику, на шкалу дубля (0.53–111.73; вырезы 4.37–44.73 — ругань про «англичанку»,
65.07–70.00 — ремарка «На экране Джеймс Бонд…»; «хер его знает» под «пипом» 76.28–76.96) переводит Take.
План — work/IMG_1799/plan.md.
Проверено: Джон Уоллис (1616–1703) — савилианский профессор геометрии в Оксфорде с 1649; в гражданскую войну
(1642–1651) расшифровывал для парламента перехваченные письма роялистов и Карла I — верно. Знак ∞ впервые —
«De sectionibus conicis», 1655 — верно. Версии: римская запись тысячи CIƆ (ↀ) и омега — обе ходят у историков.
Корень из 53-значного числа в уме ночью, ответ продиктован утром — рассказ самого Уоллиса (27 цифр) — верно;
цифр на экране нет: точки вместо выдуманного числа. «Первый британский айтишник» — шутка автора.
Распознавание: «Уоллес» → «Уоллис», «диаметрии» → «геометрии», «Оксфорте» → «Оксфорде»; «Когда» (0.0–0.86
у whisper, по звуку с 0.62) выпало из дубля — первое «ты» в субтитрах → «когда ты».
Бонда на экране нет: свободной картинки нет, людей не генерируем — вместо него «007» за спиной.
Картинки — Wikimedia Commons, качает work/IMG_1799/fetch.py; лицензии и авторы — downloads/candidates.json.
v2 (15.10.2026, Валера): текст без плашек — крупно за головой или на груди; вырезка — Apple Vision как исключение
(work/IMG_1799/vision_matte.py). v1 — page_v1.py.bak, director_v1.json.bak.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, card  # noqa: E402

STEM = "IMG_1799"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
IMG = ROOT / f"studio/{STEM}/assets/img"
IMG.mkdir(parents=True, exist_ok=True)
# выбраны глазами из кандидатов fetch.py (лицензии — downloads/candidates.json; oxford_1 скачан первым
# прогоном, и в candidates.json второго прогона его имя записано не то — настоящий файл ниже):
#   Уоллис — Годфри Неллер (PD, «John Wallis by Sir Godfrey Kneller, Bt (cropped)»); Карл I — ван Дейк (PD,
#   «King Charles I of England, three-quarter portrait»); Оксфорд — «Radcliffe Camera Oxford 2018 04» (CC BY 4.0,
#   здание 1749 г. — символ Оксфорда, не времён Уоллиса); битва — Чарльз Ландсир «Cromwell, Battle of Naseby»
#   (PD: после Нейзби, 1645, захвачен ларец с письмами короля — ровно «перехваченные письма»); ночь — Нильс
#   Шилльмарк, «Натюрморт со свечой» (PD); чертежи конических сечений — «De sectionibus conicis Fleuron T110328-23»
#   (PD; гравюра из старинной книги о конических сечениях, не сама книга Уоллиса — подпись без «1655»).
# Шифрованного письма в свободном доступе не скачалось (429 Commons) — вместо документа схема «шифр → письмо».
# war_1.jpg в downloads — Геттисберг (США), отброшен.
PICK = {"wallis.jpg": "wallis_2.jpg", "charles.jpg": "charles_3.jpg", "bg_oxford.jpg": "oxford_1.jpg",
        "bg_war.jpg": "civilwar_3.jpg", "bg_night.jpg": "night_2.jpg", "conic.jpg": "conic_1.jpg"}
for dst_name, src_name in PICK.items():
    src = ROOT / f"work/{STEM}/downloads/{src_name}"
    if not src.exists():
        sys.exit(f"✗ нет {src.name} — запусти work/{STEM}/fetch.py (картинки с Wikimedia Commons)")
    dst = IMG / dst_name
    if not (dst.exists() and dst.samefile(src)):
        shutil.copyfile(src, dst)

CHEST = 1290        # верх текста на груди: подбородок с камерой доходит до y 1258 (verify_page)
HEAD = 290          # верх текста за головой: вкладки TikTok — до y 260, уход вверх — ещё 20; макушка ~y 570
# v5 (15.10, Валера: «v4 лучше, но по субтитрам v3 была лучше… не стоит задачи один шрифт и один цвет… найти свой
# стиль… больше всего нравились самые первые видео — тот стиль вернуть и живость»). Почерк первого пака
# (IMG_3279–3322): крупное — Oswald заглавными, крем или красный; подвод — мелкий Manrope разрядкой; штамп красный
# с наклоном; формулы — Cormorant. Палитра — только крем и красный: жёлтого в первом паке не было.
RED, CREAM = "#F0352C", "#F2EBDD"
GOLD = RED
# v2 (Валера, 15.10.2026): «текст больше нравится, когда он не в рамочке узенько написан, а стильно, как
# вайб-монтаж, — большим текстом на экране либо за головой». Тёмных плашек нет: всё, что в v1 стояло в
# них, — крупная типографика прямо в кадре: за головой (между фоном и вырезкой) или на груди поверх.
# Иерархия — мелкий подвод разрядкой + КРУПНОЕ узким жирным гротеском; читается за счёт тени, а не подложки.
SHADOW = "0 3px 8px rgba(0,0,0,0.65), 0 14px 46px rgba(0,0,0,0.55)"
css = f'''      .tx {{ left: 0; width: 1080px; text-align: center; white-space: nowrap; }}
      .tx-lead {{ font-family: "Manrope"; font-weight: 800; font-size: 36px; letter-spacing: 0.24em; text-transform: uppercase;
                 color: var(--cream); text-shadow: {SHADOW}; }}
      .tx-big {{ font-family: "Oswald"; font-weight: 700; text-transform: uppercase; line-height: 0.9; letter-spacing: -0.01em;
                color: var(--cream); text-shadow: {SHADOW}; }}
      .tx-mono {{ font-family: "JBMono"; font-weight: 700; color: var(--cream); text-shadow: {SHADOW}; }}
      .tx-tex {{ color: var(--cream); text-shadow: {SHADOW}; }}
      .tx span {{ display: inline-block; }}
      .katex-src, .katex-display {{ margin: 0 !important; display: inline-block; }}
      .cx {{ display: inline-block; width: 150px; text-align: center; }}
      .mirror {{ display: inline-block; transform: scaleX(-1); }}
      .gk-win {{ left: 110px; width: 860px; height: 230px; overflow: hidden;   /* бока — под обрезкой Instagram */
                -webkit-mask-image: linear-gradient(90deg, transparent 0%, #000 14%, #000 86%, transparent 100%);
                mask-image: linear-gradient(90deg, transparent 0%, #000 14%, #000 86%, transparent 100%); }}
      .gk {{ position: absolute; left: 0; top: 0; white-space: nowrap; }}
      .wide-svg {{ position: absolute; left: 0; top: 0; overflow: visible; filter: drop-shadow(0 10px 26px rgba(0,0,0,0.55)); }}
      .bg {{ left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden;
             -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%);
             mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%); }}
      .bg img {{ position: absolute; left: -54px; top: -96px; width: 1188px; height: 2112px; object-fit: cover; }}
      .bg .vig {{ position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 38%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.6) 100%); }}
      #bg-war img {{ object-position: 57% 50%; }}
      /* король справа — компактнее: голова в этом месте правее и выше, полная карточка заходила на лицо */
      #c-king {{ top: 262px; }}
      #c-king .ph, #c-king img {{ height: 220px; }}
      #bg-night img {{ object-position: 49% 50%; }}
      #bg-ox img {{ object-position: 50% 30%; }}
      /* финальная плашка тоже без рамки — как весь текст ролика */
      .cta {{ background: none; border: none; box-shadow: none; padding: 0; }}
      .cta-big {{ font-size: 112px; text-shadow: {SHADOW}; }}
      .cta-small {{ text-shadow: {SHADOW}; }}

'''

SAFE = 'data-safe="лицо важнее серой зоны: текст ниже подбородка (Валера, 12.10)"'


def tex(src: str) -> str:
    return f'<span class="katex-src" data-tex="{src}"></span>'


def lead(lid: str, text: str, top: int, color: str = CREAM, extra: str = "") -> str:
    return f'        <div id="{lid}" class="g tx tx-lead" {extra} style="top: {top}px; color: {color};">{text}</div>'


def big(bid: str, inner: str, top: int, size: int, color: str = CREAM, extra: str = "", cls: str = "tx-big") -> str:
    return f'        <div id="{bid}" class="g tx {cls}" {extra} style="top: {top}px; font-size: {size}px; color: {color};">{inner}</div>'


def word(sid: str, text: str, top: int = 300, size: int = 96, color: str = CREAM) -> str:
    """То, что в v1 было стикером-пилюлей, — крупное слово над головой, без подложки."""
    return big(sid, text, top, size, color)


def stamp(sid: str, text: str, top: int = 290, size: int = 120) -> str:
    return (f'        <div id="{sid}" class="g tx" style="top: {top}px;">'
            f'<span class="stamp" style="font-size: {size}px; display: inline-block; transform: rotate(-4deg);">{text}</span></div>')


def bg(bid: str, img: str) -> str:
    return f'        <div id="{bid}" class="g bg"><img src="assets/img/{img}" alt="" /><div class="vig"></div></div>'


DRAW = 'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"'


def lemniscate(color: str) -> str:
    """∞ линией (лемниската Бернулли): глиф KaTeX вышел тонким и низким — голова его закрывала.

    680×240 над макушкой (макушка с камерой ~y 570): y 285–525, ниже вкладок TikTok (260).
    """
    import math
    a, cx_, cy, pts = 330, 540, 125, []
    for k in range(181):
        u = 2 * math.pi * k / 180
        d = 1 + math.sin(u) ** 2
        pts.append(f"{cx_ + a * math.cos(u) / d:.1f} {cy + a * math.sin(u) * math.cos(u) / d:.1f}")
    path = "M " + " L ".join(pts) + " Z"
    return (f'<svg viewBox="0 0 1080 250" style="position: absolute; left: 0; top: 0; width: 1080px; height: 250px; overflow: visible;">'
            f'<path class="lem" d="{path}" fill="none" stroke="{color}" stroke-width="44" stroke-linejoin="round" stroke-linecap="round" '
            f'style="filter: drop-shadow(0 12px 30px rgba(0,0,0,0.4));" {DRAW} /></svg>')

LEM_GOLD = lemniscate(GOLD)

# 1. шифр за головой: «ЗНАК» перебирает буквы и становится шифровкой
PLAIN = "ЗНАК"
CIPHER = ["ЖQ7Ф", "Ъ9ЮR", "Ψ4ЩЯ", "Ѣ2ΞД"]
cx = "".join(f'<span id="cx{i}" class="cx">{ch}</span>' for i, ch in enumerate(PLAIN))
cipher = "\n".join([
    lead("cx-lead", "британский шифровальщик", HEAD),
    big("cx-row", cx, HEAD + 70, 200, cls="tx-mono"),
])

# 2. днём — профессор геометрии (Оксфорд за спиной, Уоллис слева) — на груди
day = "\n".join([
    lead("d-lead", "днём", CHEST, GOLD, SAFE),
    big("d-big", "профессор<br>геометрии", CHEST + 60, 120, extra=SAFE),
])

# 3. гражданская война: 1642 → 1651, линия рисуется — на груди, битва за спиной
war = "\n".join([
    lead("w-lead", "гражданская война в Англии", CHEST, CREAM, SAFE),
    big("w-big", '<span>1642</span> <span id="w-arrow" style="color: rgba(242,235,221,0.6);">→</span> '
                 f'<span id="w-y2" style="color: {RED};">1651</span>', CHEST + 64, 150, extra=SAFE),
    f'        <div id="w-line" class="g" {SAFE} style="left: 0; top: {CHEST + 230}px; width: 1080px; height: 30px;">'
    f'<svg class="wide-svg" viewBox="0 0 1080 30" style="width: 1080px; height: 30px;">'
    f'<line id="war-line" x1="190" y1="15" x2="890" y2="15" stroke="{RED}" stroke-width="12" stroke-linecap="round" {DRAW} /></svg></div>',
])

# 4. перехваченное письмо: строка шифра → ПИСЬМО КОРОЛЯ — на груди
letter = "\n".join([
    lead("lt-lead", "перехваченное письмо", CHEST, CREAM, SAFE),
    big("lt-code", "Ж7Ψ Ф·Q9 Ъ4", CHEST + 64, 96, "rgba(242,235,221,0.7)", SAFE, cls="tx-mono"),
    big("lt-plain", "письмо короля", CHEST + 64, 140, RED, SAFE),
])

# 5. книга 1655: конические сечения рисуются огромными линиями за головой
conic = "\n".join([
    lead("cn-lead", "конические сечения", HEAD),
    f'        <div id="cn-svg" class="g" style="left: 0; top: {HEAD + 60}px; width: 1080px; height: 210px;">'
    f'<svg class="wide-svg" viewBox="0 0 1080 210" style="width: 1080px; height: 210px;">'
    f'<ellipse id="cn-el" cx="250" cy="105" rx="130" ry="80" fill="none" stroke="{GOLD}" stroke-width="18" {DRAW} />'
    f'<path id="cn-pa" d="M 440 200 Q 540 -90 640 200" fill="none" stroke="{CREAM}" stroke-width="18" stroke-linecap="round" {DRAW} />'
    f'<path id="cn-hy" d="M 700 200 Q 760 60 880 20" fill="none" stroke="{RED}" stroke-width="18" stroke-linecap="round" {DRAW} /></svg></div>',
])

# 6. лежачая восьмёрка: огромная 8 за головой ложится на бок
eight = "\n".join([
    big("e8", "8", HEAD - 30, 470, GOLD),
    lead("e8-lead", "лежачая восьмёрка", HEAD),
])

# 7. версия 1: римская тысяча CIƆ = 1000 → ∞ за головой
v1 = "\n".join([
    lead("v1-lead", "версия 1 · Рим", HEAD),
    big("v1-roman", 'CI<span class="mirror">C</span>', HEAD + 60, 230, cls="tx-big serif"),
    big("v1-eq", "= 1000", HEAD + 95, 170, GOLD),
    f'        <div id="v1-inf" class="g" style="left: 0; top: {HEAD + 70}px; width: 1080px; height: 250px;">{LEM_GOLD}</div>',
    lead("v1-many", "≈ «очень много»", HEAD, GOLD),
])

# 8. версия 2: греческий алфавит бежит к омеге, ω ложится в ∞ — за головой
GREEK = r"\mathrm{A\;B\;\Gamma\;\Delta\;E\;Z\;H\;\Theta\;I\;K\;\Lambda\;M\;N\;\Xi\;O\;\Pi\;P\;\Sigma\;T\;\Upsilon\;\Phi\;X\;\Psi\;}"
v2 = "\n".join([
    lead("v2-lead", "версия 2 · Греция", HEAD),
    f'        <div id="gk-win" class="g gk-win" style="top: {HEAD + 60}px;">'
    f'<div id="gk-strip" class="gk tx-tex" style="font-size: 160px; top: 10px;">{tex(GREEK)}'
    f'<span id="gk-om" style="display: inline-block;">{tex(chr(92) + "Omega")}</span></div></div>',
    big("gk-w", tex(chr(92) + "omega"), HEAD + 30, 300, GOLD, cls="tx-tex"),
    f'        <div id="gk-inf" class="g" style="left: 0; top: {HEAD + 40}px; width: 1080px; height: 250px;">{LEM_GOLD}</div>',
])

# 9. корень из 53-значного числа: огромный √ рисуется за головой, внутри счётчик
root = "\n".join([
    lead("rt-lead", "в уме, ночью", HEAD),
    f'        <div id="rt-svg" class="g" style="left: 0; top: {HEAD + 50}px; width: 1080px; height: 300px;">'
    f'<svg class="wide-svg" viewBox="0 0 1080 300" style="width: 1080px; height: 300px;">'
    f'<path id="rt-sign" d="M 150 150 L 210 115 L 290 250 L 350 20 L 950 20" fill="none" stroke="{GOLD}" stroke-width="18" '
    f'stroke-linejoin="round" stroke-linecap="round" {DRAW} /></svg></div>',
    f'        <div id="rt-num" class="g tx tx-big" style="top: {HEAD + 75}px; left: 360px; width: 570px; font-size: 170px;">'
    '<span id="rt-n">0</span><span style="font-size: 56px; letter-spacing: 0;">-значное</span></div>',
    lead("rt-dawn", "☀ утром — ответ", HEAD + 330, GOLD),
])

# 10. ЕГЭ: ответ (−∞; +∞) крупно на груди, числовая прямая рисуется в обе стороны
ege = "\n".join([
    lead("eg-lead", "ответ в ЕГЭ", CHEST, CREAM, SAFE),
    big("eg-big", "в ЕГЭ", CHEST + 60, 150, extra=SAFE),
    big("eg-ans", tex(chr(92) + "boldsymbol{(-" + chr(92) + "infty;" + chr(92) + ",+" + chr(92) + "infty)}"),
        CHEST + 60, 110, extra=SAFE, cls="tx-tex"),
    f'        <div id="eg-line" class="g" {SAFE} style="left: 0; top: {CHEST + 250}px; width: 1080px; height: 60px;">'
    f'<svg class="wide-svg" viewBox="0 0 1080 60" style="width: 1080px; height: 60px;">'
    f'<line id="eg-l" x1="540" y1="30" x2="150" y2="30" stroke="{CREAM}" stroke-width="10" stroke-linecap="round" {DRAW} />'
    f'<line id="eg-r" x1="540" y1="30" x2="930" y2="30" stroke="{CREAM}" stroke-width="10" stroke-linecap="round" {DRAW} />'
    f'<path id="eg-al" d="M 180 8 L 146 30 L 180 52" fill="none" stroke="{CREAM}" stroke-width="10" stroke-linecap="round" opacity="0" />'
    f'<path id="eg-ar" d="M 900 8 L 934 30 L 900 52" fill="none" stroke="{CREAM}" stroke-width="10" stroke-linecap="round" opacity="0" />'
    f'<line x1="540" y1="12" x2="540" y2="48" stroke="{GOLD}" stroke-width="8" /></svg></div>',
])

censor = ('        <div id="cn-bleep" class="g censor" style="top: 290px;"><span>***</span><b>18+</b></div>')


# за головой — между фоном и вырезанным человеком (окна fg ниже)
behind = "\n".join([
    f'        <div id="b-inf" class="g" style="left: 0; top: 285px; width: 1080px; height: 250px;">{lemniscate(CREAM)}</div>',
    cipher,
    bg("bg-ox", "bg_oxford.jpg"),
    '        <div id="b-hack" class="g big red" style="top: 300px; font-size: 170px;">взломщик</div>',
    bg("bg-war", "bg_war.jpg"),
    '        <div id="b-007" class="g big" style="top: 280px; font-size: 260px;">007</div>',
    f'        <div id="b-1655" class="g big" style="top: 290px; font-size: 230px; color: {GOLD};"><span id="yr">1600</span></div>',
    conic,
    eight,
    v1,
    v2,
    bg("bg-night", "bg_night.jpg"),
    root,
    f'        <div id="b-inf2" class="g" style="left: 0; top: 285px; width: 1080px; height: 250px;">{lemniscate(GOLD)}</div>',
])

front = "\n".join([
    stamp("st-secret", "секретно"),
    card("c-wallis", "wallis.jpg", "Джон Уоллис", "1616–1703, Оксфорд", side="left"),
    day,
    word("st-parl", "на службе<br>парламента", top=290, size=96),
    war,
    letter,
    card("c-king", "charles.jpg", "Карл I", "король Англии", side="right"),
    word("st-it", "первый британский<br>айтишник", top=290, size=92),
    word("st-why", "почему именно она?", size=92),
    censor,
    word("st-hist", "историки спорят<br>до сих пор", top=290, size=92),
    stamp("st-end", "конец всего", top=HEAD),
    word("st-insom", "бессонница", size=120),
    word("st-head", "чтобы занять<br>голову", top=290, size=100),
    ege,
    stamp("st-secret2", "секретно"),
])

TX_IN = '{ fromY: 60, fromScale: 0.9, dur: 0.3, ease: "power3.out" }'
TX_OUT = '{ y: -20 }'


def pop(sel: str, at: float, dur: float = 0.2) -> str:
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.5, filter: BLUR(10) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: {dur}, ease: "power4.out" }}, {at});')


def bg_in(sel: str, a: float, b: float) -> str:
    """Фон наплывом со смазом, медленный наезд внутри, уход со смазом; на показе резкий."""
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.08, filter: BLUR(14) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.45, ease: "power2.out" }}, {a});\n'
            f'      tl.fromTo("{sel} img", {{ scale: 1 }}, {{ scale: 1.06, duration: {b - a + 0.35:.2f}, ease: "none" }}, {a});\n'
            f'      tl.to("{sel}", {{ opacity: 0, scale: 1.04, filter: BLUR(12), duration: 0.35, ease: "power2.in" }}, {b});')


def word_in(sel: str, at: float, out: float, rot: float = 0) -> str:
    """Крупное слово над головой: впечатывается и уходит вверх."""
    return (f'      slam("{sel}", {at}, {{ fromScale: 1.35, blur: 8 }});\n'
            f'      leave("{sel}", {out}, {{ y: -20 }});')


# шифр: каждая буква перебирает знаки и встаёт на шифровку
cx_js = []
for k, w in enumerate(CIPHER):
    at = round(t(46.70) + 0.12 * k, 2)
    for i, ch in enumerate(w):
        cx_js.append(f'      tl.set("#cx{i}", {{ textContent: "{ch}", color: "{RED if k == len(CIPHER) - 1 else CREAM}" }}, {at});')
RT0 = t(99.02)

# склейки дубля (хук → «Знак бесконечности придумал», вырез ремарки про Бонда). 15.10 (Валера: «склейки не
# спрятаны за переходами вспышками»): на каждой — splice(): смаз-навод и вспышка, кадр бьёт крупнее
# (tk.splice_punches), надпись уходит ДО реза, новая влетает НА нём.
J1, J2 = tk.splices
assert abs(J1 - t(44.74)) < 0.05 and abs(J2 - t(70.0)) < 0.05, (J1, J2)

beats = f'''
      // ---------- хук: ∞ за спиной — СЕКРЕТНО ----------
      slam("#b-inf", {t(1.50)}, {{ fromScale: 1.3 }});
      draw("#b-inf .lem", {t(1.50)}, 0.55);
      leave("#b-inf", {t(3.40)}, {{ y: -60 }});
      slam("#st-secret", {t(3.48)}, {{ fromScale: 2.2, blur: 10 }});
      leave("#st-secret", {J1 - 0.2:.2f}, {{ scale: 0.8, y: -30, dur: 0.18 }});
      splice({J1:.2f});

      // ---------- (склейка) придумал британский шифровальщик: ЗНАК → шифр за головой ----------
      enter("#cx-lead", {J1 + 0.02:.2f}, {TX_IN});
      slam("#cx-row", {J1 + 0.1:.2f}, {{ fromScale: 1.3, blur: 10 }});
{chr(10).join(cx_js)}
      leave("#cx-lead", {t(47.95)}, {TX_OUT});
      leave("#cx-row", {t(47.95)}, {TX_OUT});

      // ---------- Джон Уоллис; днём — Оксфорд; на груди «профессор геометрии» ----------
      card("#c-wallis", {t(48.50)}, {t(51.30)}, "left");
{bg_in("#bg-ox", t(49.40), t(51.36))}
      enter("#d-lead", {t(49.45)}, {TX_IN});
      slam("#d-big", {t(49.60)}, {{ fromScale: 1.3, blur: 8 }});
      leave("#d-lead", {t(51.30)}, {TX_OUT});
      leave("#d-big", {t(51.30)}, {TX_OUT});

      // ---------- взломщик шифров парламента ----------
      slam("#b-hack", {t(52.92)}, {{ fromScale: 1.5 }});
      leave("#b-hack", {t(54.00)}, {{ y: -60 }});
{word_in("#st-parl", t(54.05), t(55.25), -2)}

      // ---------- гражданская война: битва за спиной, 1642 → 1651; письма короля ----------
{bg_in("#bg-war", t(55.30), t(61.20))}
      enter("#w-lead", {t(55.35)}, {TX_IN});
      tl.set("#w-y2", {{ opacity: 0 }}, {t(55.35)});
      slam("#w-big", {t(55.45)}, {{ fromScale: 1.3, blur: 8 }});
      tl.set("#w-line", {{ opacity: 1 }}, {t(55.80)});
      draw("#war-line", {t(55.80)}, 1.1);
{pop("#w-y2", t(56.92))}
      leave("#w-lead", {t(57.45)}, {TX_OUT});
      leave("#w-big", {t(57.45)}, {TX_OUT});
      leave("#w-line", {t(57.45)}, {TX_OUT});
      enter("#lt-lead", {t(57.80)}, {TX_IN});
      enter("#lt-code", {t(57.85)}, {TX_IN});
      tl.to("#lt-code", {{ opacity: 0, scaleX: 0.6, filter: BLUR(10), duration: 0.3, ease: "power2.in" }}, {t(59.35)});
{pop("#lt-plain", t(59.60))}
      leave("#lt-lead", {t(61.10)}, {TX_OUT});
      leave("#lt-plain", {t(61.10)}, {TX_OUT});
      card("#c-king", {t(59.55)}, {t(61.85)}, "right");

      // ---------- первый айтишник; 007 ----------
{word_in("#st-it", t(61.95), t(63.70), 2)}
      slam("#b-007", {t(64.34)}, {{ fromScale: 1.6 }});
      leave("#b-007", {J2 - 0.2:.2f}, {{ y: -60, dur: 0.18 }});
      splice({J2:.2f});

      // ---------- (склейка) 1655, конические сечения, восьмёрка — всё за головой ----------
      tl.fromTo("#b-1655", {{ opacity: 0, y: 40, filter: BLUR(12) }}, {{ opacity: 1, y: 0, filter: BLUR(0), duration: 0.3, ease: "power3.out" }}, {J2 + 0.02:.2f});
      tl.fromTo("#yr", {{ textContent: 1600 }}, {{ textContent: 1655, snap: {{ textContent: 1 }}, duration: 0.8, ease: "power2.out", immediateRender: false }}, {t(70.50)});
      leave("#b-1655", {t(72.20)}, {{ y: -60 }});
      enter("#cn-lead", {t(72.25)}, {TX_IN});
      tl.set("#cn-svg", {{ opacity: 1 }}, {t(72.25)});
      draw("#cn-el", {t(72.40)}, 0.45);
      draw("#cn-pa", {t(72.85)}, 0.45);
      draw("#cn-hy", {t(73.30)}, 0.45);
      leave("#cn-lead", {t(74.25)}, {TX_OUT});
      leave("#cn-svg", {t(74.25)}, {TX_OUT});
      slam("#e8", {t(74.32)}, {{ fromScale: 1.3, blur: 8 }});
      tl.to("#e8", {{ rotation: 90, duration: 0.45, ease: "back.out(1.6)" }}, {t(74.70)});
      enter("#e8-lead", {t(75.05)}, {{ fromY: -30, fromScale: 0.8, dur: 0.25 }});
      leave("#e8", {t(75.38)}, {TX_OUT});
      leave("#e8-lead", {t(75.38)}, {TX_OUT});

      // ---------- почему именно она — [пип] — историки спорят ----------
{word_in("#st-why", t(75.55), t(76.20), -2)}
      slam("#cn-bleep", {t(76.28)}, {{ fromScale: 1.6, blur: 10 }});
      leave("#cn-bleep", {t(77.00)}, {{ scale: 0.6, y: 0 }});
{word_in("#st-hist", t(77.80), t(79.05), 2)}

      // ---------- версия 1: римская тысяча → ∞ ----------
      enter("#v1-lead", {t(79.14)}, {TX_IN});
      slam("#v1-roman", {t(79.25)}, {{ fromScale: 1.3, blur: 8 }});
      tl.to("#v1-roman", {{ x: -230, duration: 0.3, ease: "power3.out" }}, {t(80.85)});
{pop("#v1-eq", t(80.94))}
      tl.set("#v1-eq", {{ x: 160 }}, {t(80.94)});
      tl.to(["#v1-roman", "#v1-eq"], {{ scaleX: 0.45, opacity: 0, filter: BLUR(8), duration: 0.35, ease: "power2.in" }}, {t(83.30)});
      tl.to("#v1-lead", {{ opacity: 0, duration: 0.12, ease: "none" }}, {t(83.50)});
      slam("#v1-inf", {t(83.60)}, {{ fromScale: 1.2 }});
      draw("#v1-inf .lem", {t(83.60)}, 0.5);
      enter("#v1-many", {t(85.10)}, {{ fromScale: 0.8, dur: 0.25 }});
      leave("#v1-inf", {t(85.95)}, {TX_OUT});
      leave("#v1-many", {t(85.95)}, {TX_OUT});

      // ---------- версия 2: омега, последняя буква — конец всего ----------
      enter("#v2-lead", {t(86.05)}, {TX_IN});
      tl.set("#gk-win", {{ opacity: 1 }}, {t(86.10)});
      tl.fromTo("#gk-strip", {{ x: 700 }}, {{ x: () => -(document.getElementById("gk-strip").scrollWidth - 620), duration: 2.4, ease: "power2.inOut" }}, {t(86.10)});
      tl.to("#gk-om", {{ color: "{GOLD}", scale: 1.3, duration: 0.2, ease: "back.out(2)" }}, {t(88.74)});
      tl.to("#gk-win", {{ opacity: 0, duration: 0.2 }}, {t(89.15)});
{pop("#gk-w", t(89.26))}
      tl.to("#gk-w", {{ scaleY: 0.6, opacity: 0, filter: BLUR(6), duration: 0.3, ease: "power2.in" }}, {t(89.90)});
      slam("#gk-inf", {t(90.05)}, {{ fromScale: 1.2 }});
      draw("#gk-inf .lem", {t(90.05)}, 0.3);
      slam("#st-end", {t(90.42)}, {{ fromScale: 2.2, blur: 10 }});
      leave("#v2-lead", {t(90.30)}, {TX_OUT});
      leave("#gk-inf", {t(90.30)}, {TX_OUT});
      leave("#st-end", {t(91.25)}, {{ scale: 0.6, y: 0, y: -30 }});

      // ---------- бессонница: ночь за спиной ----------
{bg_in("#bg-night", t(91.35), t(97.00))}
{word_in("#st-insom", t(92.60), t(94.40), -2)}
{word_in("#st-head", t(95.75), t(97.00), 2)}

      // ---------- корень из 53-значного числа: огромный √ за головой ----------
      enter("#rt-lead", {t(97.06)}, {TX_IN});
      tl.set("#rt-svg", {{ opacity: 1 }}, {t(97.06)});
      draw("#rt-sign", {t(97.30)}, 0.8);
      enter("#rt-num", {t(98.20)}, {TX_IN});
      tl.fromTo("#rt-n", {{ textContent: 0 }}, {{ textContent: 53, snap: {{ textContent: 1 }}, duration: 1.38, ease: "none", immediateRender: false }}, {RT0});
      enter("#rt-dawn", {t(100.82)}, {{ fromScale: 0.8, dur: 0.25 }});
      leave("#rt-lead", {t(102.45)}, {TX_OUT});
      leave("#rt-svg", {t(102.45)}, {TX_OUT});
      leave("#rt-num", {t(102.45)}, {TX_OUT});
      leave("#rt-dawn", {t(102.45)}, {TX_OUT});

      // ---------- ЕГЭ: (−∞; +∞) крупно на груди ----------
      enter("#eg-lead", {t(102.55)}, {TX_IN});
      slam("#eg-big", {t(102.65)}, {{ fromScale: 1.3, blur: 8 }});
      tl.to("#eg-big", {{ opacity: 0, scale: 0.8, filter: BLUR(8), duration: 0.2, ease: "power2.in" }}, {t(105.08)});
{pop("#eg-ans", t(105.30))}
      tl.set("#eg-line", {{ opacity: 1 }}, {t(102.70)});
      tl.fromTo("#eg-line", {{ y: 30 }}, {{ y: 0, duration: 0.3, ease: "power3.out" }}, {t(102.70)});
      draw("#eg-l", {t(105.40)}, 0.6);
      draw("#eg-r", {t(106.40)}, 0.6);
      tl.fromTo("#eg-al", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.1, ease: "none" }}, {t(105.95)});
      tl.fromTo("#eg-ar", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.1, ease: "none" }}, {t(106.95)});
      leave("#eg-lead", {t(107.45)}, {TX_OUT});
      leave("#eg-ans", {t(107.45)}, {TX_OUT});
      leave("#eg-line", {t(107.45)}, {TX_OUT});

      // ---------- кольцо: ∞ за спиной — СЕКРЕТНО ----------
      slam("#b-inf2", {t(107.56)}, {{ fromScale: 1.3 }});
      draw("#b-inf2 .lem", {t(107.56)}, 0.55);
      leave("#b-inf2", {t(108.55)}, {{ y: -60 }});
      slam("#st-secret2", {t(108.80)}, {{ fromScale: 2.2, blur: 10 }});
      leave("#st-secret2", {t(109.75)}, {{ scale: 0.6, y: 0, y: -30 }});
'''

# Звуки — мало (бриф: few), правила 12.10: только на главных ударах, семейства не подряд,
# каждый файл ≤ 2 раз, между звуками ≥ 1 с. Фоны, визуализации, портреты и стикеры — без звука.
sounds = [
    audio("secret", "impact-bass-1", t(3.46), 0.9),
    audio("hack", "whoosh-cinematic", t(52.90), 0.7),
    # на склейке J2 звука нет: глитчи убраны навсегда (15.10, «звуки шумов помех… никогда не подойдут в рилы»),
    # вжух подряд с whoosh-cinematic нельзя; рез прячут вспышка, смаз и смена плана. Удар на «007» снят — до склейки 0.8 с

    audio("secret2", "impact-bass-1", t(108.78), 0.9),        # ≥ 1 с до щелчка финальной плашки
]
# человек поверх фонов и слов за спиной
fg = [(t(1.40), t(3.70)), (t(45.00), t(48.10)), (t(49.30), t(51.75)), (t(52.85), t(54.30)), (t(55.25), t(61.60)),
      (t(64.25), t(70.60)), (t(70.40), t(75.75)), (t(79.10), t(86.10)), (t(86.00), t(91.40)), (t(91.30), t(102.60)),
      (t(107.50), t(110.05))]
# окна могут слипнуться на склейке — сливаем пересекающиеся
fg.sort()
merged = [list(fg[0])]
for a, b in fg[1:]:
    if a <= merged[-1][1]:
        merged[-1][1] = max(merged[-1][1], b)
    else:
        merged.append([a, b])
fg = [tuple(w) for w in merged]

# v6 (16.10): framing и whips — до build_page. В v3–v5 строка `beats += whips` стояла после сборки
# страницы, и смаза на входе в крупный план в ролике не было (нашлось при разборе дорожек в студии).
# ---- v3: динамика как у риелтора — план меняется каждые 2–3 с. Говорящая голова одна, поэтому смена плана —
# мгновенный перескок общий ↔ крупный на границе фразы (пауза или знак препинания), как монтаж с двух камер;
# на входе в крупный — короткий смаз (whip). У склеек своё: до склейки общий, на ней — splice.
switch, whips = tk.framing(keep_wide=[(t(48.40), t(51.65)), (t(59.45), t(62.20))])   # портреты сбоку
beats += whips

CTA = t(109.82)
page = build_page("Знак бесконечности — знак британской разведки", DUR, behind, front, beats, sounds, fg, cta_at=CTA,
                  extra_css=css, fmt=tk.fmt, captions=tk.captions)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

fixes = tk.fixes({1: "когда ты", 3: "знак", 4: "бесконечности,", 8: "британскую", 52: "Уоллис,", 56: "геометрии",
                  58: "Оксфорде,", 115: "восьмёрку.", 118: "её", 119: "***", 120: "", 121: "", 131: "",
                  162: "ещё", 164: "Уоллиса", 179: "извлёк"})


director = {
    "_note": "Знак бесконечности — знак британской разведки. Время по дублю; раскладка — work/IMG_1799/page.py, план — plan.md.",
    # акценты — уровнем стиля с правкой проекта (tk.punch, 1.36 при базе 1.2), а не числом: 1.2 при базе 1.2
    # молча не давал ничего (15.10). Акцент перед склейкой отпускает до неё — иначе на резе нет смены плана.
    "punches": [[t(3.48), round(J1 - 0.35, 2), tk.punch, 0.10, 0.25],
                [t(52.92), t(54.00), tk.punch, 0.10], [t(64.34), round(J2 - 0.3, 2), tk.punch, 0.05, 0.2],
                [t(90.40), t(91.25), tk.punch, 0.10], [t(99.02), t(100.40), tk.punch, 0.10],
                [t(108.80), t(109.75), tk.punch, 0.05]] + tk.splice_punches() + switch,
    "text_fixes": fixes,
    "keep_case": ["ЕГЭ"],
    "accent_words": ["бесконечности", "разведку", "шифровальщик", "взломщик", "1655", "восьмёрку", "53", "разведки"],
    # плашки на груди — на их время субтитров нет
    # текст на груди — на его время субтитров нет; за головой — субтитры идут
    "hide_captions": [[t(49.40), t(51.40)], [t(55.30), t(61.20)], [t(102.50), t(107.55)],
                      [t(109.20), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
