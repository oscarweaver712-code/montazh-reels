"""Страница графики IMG_1827: почему плюс — это крест, а минус — черточка.

Время ударов — по исходнику, на шкалу дубля переводит Take. План — work/IMG_1827/plan.md.
Проверено: первые печатные «+» и «−» — у Иоганна Видмана, «Behende und hubsche Rechenung auff allen
kauffmanschafft», Лейпциг, 1489 (книга по торговому счёту; там знаки — излишек и недостача). 1489 →
2026 = 537 лет — «500 лет до ЕГЭ» Валеры сходится. Версия про пометки на бочках — одна из
распространённых гипотез происхождения знаков (другая — «+» из лигатуры «et»); на экране — только то,
что говорит Валера. Лука Пачоли, «Summa de arithmetica», 1494: плюс и минус записывал буквами p̄ и m̄ —
это и есть «буквы П и М», о которых он говорит. Чёрт — миниатюра Codex Gigas (XIII в., PD).
(a + b)² = a² + 2ab + b² — верно. Картинки — Wikimedia Commons, лицензии в downloads/candidates.json.
Доска (бочка → черта → плюс) — ManimGX, work/IMG_1827/manim/barrel.py.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import viz  # noqa: E402
from kit import Take, audio, build_page, card, doc_img  # noqa: E402

STEM = "IMG_1827"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
fmt = tk.fmt

# выбранные кандидаты из downloads/ (fetch.py) — выбор глазами
# порт с купцами на Commons не нашёлся (429 и ни одного свободного) — вместо него ряд бочек в погребе;
# основной фон — бочки с меловыми крестиками на днищах (barrels_3), прямо про «пометки на бочках».
# Документ — Видман 1489, страница с весом товара: «4 + 5», «4 — 17» (излишек и недостача, widmann_2)
IMG = {"grave_bg": "cemetery_4.jpg", "grave_card": "cemetery_2.jpg", "devil": "devil_1.jpg",
       "pacioli": "pacioli_1.jpg", "harbor": "barrels_1.jpg", "barrels": "barrels_3.jpg",
       "widmann": "widmann_2.jpg"}

SAFE = 'data-safe="лицо важнее серой зоны: карточка ниже подбородка (Валера, 12.10)"'
css = '''      /* знаки за спиной — брусками, а не шрифтом: «+» на «крест» вытягивается в крест */
      .sign { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; opacity: 0; }
      .sign i { position: absolute; display: block; background: var(--cream); border-radius: 6px;
                box-shadow: 0 14px 44px rgba(0,0,0,0.45); }
      .sign .h { left: 405px; top: 377px; width: 270px; height: 58px; }
      .sign .v { left: 511px; top: 272px; width: 58px; height: 268px; }
      .sign.red i { background: var(--red); }
      .panel { border-radius: 28px; background: rgba(12,12,14,0.88); border: 2px solid rgba(242,235,221,0.16);
               box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      .pm-row { display: flex; align-items: center; gap: 30px; padding: 6px 10px; opacity: 0; }
      .pm-l { display: inline-block; width: 120px; text-align: center; font-family: "Oswald"; font-weight: 700; font-size: 112px;
              line-height: 1; color: var(--red); }
      .pm-w { font-family: "Manrope"; font-weight: 800; font-size: 46px; color: var(--cream); }
      .pm-w b { color: var(--red); }
      .tr-row { position: relative; display: flex; justify-content: space-between; align-items: center; padding: 10px 12px;
                opacity: 0; border-bottom: 2px solid rgba(242,235,221,0.14); }
      .tr-row:last-child { border-bottom: none; }
      .tr-w { font-family: "Oswald"; font-weight: 700; font-size: 66px; text-transform: uppercase; color: var(--cream); }
      .tr-s { font-family: "Manrope"; font-weight: 800; font-size: 24px; letter-spacing: 0.1em; text-transform: uppercase;
              color: rgba(242,235,221,0.6); }
      .strike { position: absolute; left: 0; top: 50%; width: 100%; height: 9px; margin-top: -4px; background: var(--red);
                border-radius: 5px; transform-origin: 0 50%; transform: scaleX(0); }
      .st-x { position: relative; display: inline-block; }
      /* фоны за спиной: полный кадр под вырезкой, темнее студии, края притемнены */
      .bg { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden; opacity: 0; }
      .bg img { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover;
                filter: brightness(0.7) saturate(0.9) contrast(1.05); }
      .bg .vig { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px;
                 background: radial-gradient(ellipse at 50% 42%, rgba(0,0,0,0) 38%, rgba(0,0,0,0.55) 100%),
                             linear-gradient(to bottom, rgba(0,0,0,0) 72%, rgba(0,0,0,0.5) 100%); }
      .num { position: absolute; left: 0; width: 1080px; opacity: 0; }
      /* Пачоли — уже и правее: у 660 px карточка задевала лицо (verify_page) */
      #c-pacioli { left: 722px; width: 250px; padding: 12px 12px 10px; }
      #c-pacioli .ph, #c-pacioli img { width: 226px; height: 250px; }
      #c-pacioli img { object-position: 46% 18%; }
      #c-pacioli .card-name { font-size: 20px; }
      #c-pacioli .card-sub { font-size: 22px; }
'''


def bg(bid: str, img: str) -> str:
    return f'        <div id="{bid}" class="bg"><img src="assets/img/{img}" alt="" /><div class="vig"></div></div>'


def counter(cid: str, values: list, top: int, size: int, suffix: str = "") -> str:
    """Счётчик за спиной: цифры сменяются через set — покадровый рендер видит то же, что снимок."""
    spans = "".join(f'<span id="{cid}{k}" class="num">{v}{suffix}</span>' for k, v in enumerate(values))
    return (f'        <div id="{cid}" class="g big" style="top: {top}px; font-size: {size}px;">{spans}'
            f'<span style="visibility: hidden;">{values[-1]}{suffix}</span></div>')


def counter_js(cid: str, n: int, at: float, step: float) -> str:
    return "\n".join([f'      tl.set("#{cid}{k}", {{ opacity: 1 }}, {at + k * step:.2f});' for k in range(n)]
                     + [f'      tl.set("#{cid}{k}", {{ opacity: 0 }}, {at + (k + 1) * step:.2f});' for k in range(n - 1)])


Y500 = [0, 40, 110, 200, 290, 370, 430, 470, 490, 500]
Y80 = [0, 12, 30, 48, 62, 72, 78, 80]
A500, A80 = t(26.50) - 0.15, t(51.22) - 0.15

behind = "\n".join([
    bg("bg-grave", IMG["grave_bg"]),
    bg("bg-harbor", IMG["harbor"]),
    bg("bg-barrels", IMG["barrels"]),
    '        <div id="b-plus" class="sign"><i class="v"></i><i class="h"></i></div>',
    '        <div id="b-minus" class="sign"><i class="h"></i></div>',
    '        <div id="b-plus2" class="sign red"><i class="v"></i><i class="h"></i></div>',
    '        <div id="b-500-lead" class="g lead" style="top: 272px;">лет до ЕГЭ</div>',
    counter("b-500", Y500, 318, 230),
    '        <div id="b-80-lead" class="g lead" style="top: 272px;">ЕГЭ на</div>',
    counter("b-80", Y80, 318, 230, "+"),
])

# Квадрат суммы — вёрсткой, а не KaTeX: у KaTeX verify_page видел строки «a», «2» за правым краем
# (x > 834) при любой ширине плашки — так и не пустил. Плюсы красным — «кресты в математике».
P = '<b style="color: var(--red); font-family: \'Manrope\'; font-style: normal; font-weight: 800; font-size: 0.9em;">+</b>'
f_square = (f'        <div id="f-sq" class="g panel" style="left: 290px; top: 1240px; width: 500px; height: 120px; display: flex; '
            f'align-items: center; justify-content: center; font-family: \'Cormorant\'; font-style: italic; font-weight: 700; '
            f'font-size: 60px; color: var(--cream); font-variant-numeric: lining-nums; white-space: nowrap;">'
            f'(a {P} b)<sup style="font-size: 0.55em;">2</sup>&nbsp;= a<sup style="font-size: 0.55em;">2</sup> {P} 2ab {P} '
            f'b<sup style="font-size: 0.55em;">2</sup></div>',
            f'      slam("#f-sq", {t(4.62):.2f});\n      leave("#f-sq", {t(4.62) + 2.0:.2f}, {{ y: -60, dur: 0.28 }});')
f_signs = viz.formula("f-signs", r"a \color{#F0352C}{+} b \color{#F0352C}{-} c",
                      at=t(47.70), dur=2.2, fmt=fmt, size=84)
board = viz.board("bd", STEM, "Barrel.mp4", at=t(32.30), fmt=fmt, place=(245, 1180, 590, 393))
# доска на груди ниже подбородка — как карточки серии (IMG_1803): лицо важнее серой зоны
board = (board[0].replace('class="g viz"', f'class="g viz" {SAFE}', 1), board[1])

pm = (f'        <div id="d-pm" class="g panel" {SAFE} style="left: 245px; top: 1262px; width: 590px; padding: 10px 30px;">\n'
      '          <div id="pm1" class="pm-row"><span class="pm-l">П</span><span class="pm-w"><b>п</b>люс</span></div>\n'
      '          <div id="pm2" class="pm-row"><span class="pm-l">М</span><span class="pm-w"><b>м</b>инус</span></div>\n'
      '        </div>')
trade = (f'        <div id="d-trade" class="g panel" {SAFE} style="left: 245px; top: 1210px; width: 590px; padding: 14px 30px;">\n'
         '          <div id="tr1" class="tr-row"><span class="tr-w st-x">крипта<i id="tr1-x" class="strike"></i></span>'
         '<span class="tr-s">не торговали</span></div>\n'
         '          <div id="tr2" class="tr-row"><span class="tr-w" style="color: #F5B82E;">товар</span>'
         '<span class="tr-s">в бочках</span></div>\n'
         '        </div>')

front = "\n".join([
    f_square[0],
    card("c-grave", IMG["grave_card"], "кладбище", "кресты", side="left"),
    card("c-devil", IMG["devil"], "чёрт", "Codex Gigas, XIII век", side="right"),
    '        <div id="st-math" class="g sticker" style="left: 300px; top: 300px; font-size: 58px; white-space: nowrap;">и это — математика?!</div>',
    pm,
    card("c-pacioli", IMG["pacioli"], "Лука Пачоли", "1494: писал p и m с чертой", side="right"),
    '        <div id="st-names" class="g stamp" style="left: 330px; top: 300px; font-size: 92px; white-space: nowrap;">без имён</div>',
    '        <div id="st-easy" class="g sticker" style="left: 310px; top: 300px; font-size: 58px; white-space: nowrap;">предельно просто</div>',
    '        <div id="st-church" class="g sticker" style="left: 160px; top: 300px; font-size: 58px; white-space: nowrap;">'
    '<span class="st-x">церковь<i id="st-church-x" class="strike"></i></span></div>',
    '        <div id="st-devils" class="g sticker" style="left: 600px; top: 300px; font-size: 58px; white-space: nowrap;">'
    '<span class="st-x">черти<i id="st-devils-x" class="strike"></i></span></div>',
    '        <div id="st-bit" class="g sticker" style="left: 350px; top: 300px; font-size: 58px; white-space: nowrap;">ну, чуть-чуть</div>',
    trade,
    board[0],
    doc_img("d-wid", IMG["widmann"], "Видман, 1489: плюс — излишек, черта — недостача", left=245, top=1170, width=590,
            height=300, position="50% 4%").replace('class="g doc"', f'class="g doc" {SAFE}', 1),
    '        <div id="st-b2b" class="g sticker" style="left: 290px; top: 300px; font-size: 58px; white-space: nowrap;">B2B-арбитраж XV века</div>',
    f_signs[0],
])

beats = f'''
      // ---------- фоны за спиной: наплыв из размытия, медленный наезд, уход в студию ----------
      function bgIn(sel, tIn, tOut) {{
        tl.fromTo(sel, {{ opacity: 0, filter: "blur(14px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.7, ease: "power2.out" }}, tIn);
        tl.fromTo(`${{sel}} img`, {{ scale: 1.08 }}, {{ scale: 1.0, duration: tOut - tIn + 0.6, ease: "none" }}, tIn);
        tl.to(sel, {{ opacity: 0, filter: "blur(10px)", duration: 0.5, ease: "power2.in" }}, tOut);
      }}
      bgIn("#bg-grave", {t(3.20)}, {t(6.70)});
      bgIn("#bg-harbor", {t(27.40)}, {t(30.40)});
      bgIn("#bg-barrels", {t(30.30)}, {t(42.10)});

      // ---------- хук: «+» за спиной, на «крест?» вытягивается в крест ----------
      slam("#b-plus", {t(1.26)}, {{ fromScale: 1.5 }});
      tl.to("#b-plus .h", {{ y: -52, scaleX: 0.78, duration: 0.22, ease: "back.out(2)" }}, {t(2.02)});
      tl.to("#b-plus .v", {{ scaleY: 1.12, transformOrigin: "50% 0%", duration: 0.22, ease: "back.out(2)" }}, {t(2.02)});
      tl.to("#b-plus i", {{ backgroundColor: "#F0352C", duration: 0.15 }}, {t(2.02)});
      leave("#b-plus", {t(2.90)}, {{ y: -60 }});
{f_square[1]}

      // ---------- минус — черточка, черти ----------
      slam("#b-minus", {t(6.96)}, {{ fromScale: 1.6 }});
      tl.fromTo("#b-minus .h", {{ scaleX: 0.3 }}, {{ scaleX: 1.15, duration: 0.3, ease: "power3.out", immediateRender: false }}, {t(7.40)});
      leave("#b-minus", {t(8.60)}, {{ y: -60 }});
      card("#c-grave", {t(9.38)}, {t(11.00)}, "left");
      card("#c-devil", {t(9.98)}, {t(11.05)}, "right");
      enter("#st-math", {t(11.68)}, {{ fromScale: 0.85, rot: -4 }});
      leave("#st-math", {t(12.50)}, {{ y: -30, rot: -10 }});

      // ---------- буквы П и М ----------
      enter("#d-pm", {t(13.55)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#pm1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(13.84)});
      tl.fromTo("#pm2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(14.26)});
      tl.to("#pm1 .pm-l", {{ scale: 1.25, duration: 0.2, ease: "back.out(2)" }}, {t(15.58)});
      tl.to("#pm1 .pm-l", {{ scale: 1, duration: 0.25, ease: "power2.out" }}, {t(16.00)});
      tl.to("#pm2 .pm-l", {{ scale: 1.25, duration: 0.2, ease: "back.out(2)" }}, {t(16.44)});
      tl.to("#pm2 .pm-l", {{ scale: 1, duration: 0.25, ease: "power2.out" }}, {t(16.86)});
      leave("#d-pm", {t(17.20)}, {{ y: 80 }});
      card("#c-pacioli", {t(13.64)}, {t(16.20)}, "right");
      slam("#st-names", {t(17.40)}, {{ fromScale: 1.6, rot: -6 }});
      leave("#st-names", {t(19.30)}, {{ y: -30, rot: -14 }});

      // ---------- предельно просто: не в церкви и не в чертях ----------
      enter("#st-easy", {t(21.54)}, {{ fromScale: 0.85, rot: 4 }});
      leave("#st-easy", {t(22.45)}, {{ y: -30, rot: 10 }});
      enter("#st-church", {t(22.94)}, {{ fromScale: 0.85, rot: -4 }});
      tl.to("#st-church-x", {{ scaleX: 1, duration: 0.2, ease: "power2.out" }}, {t(23.34)});
      enter("#st-devils", {t(23.78)}, {{ fromScale: 0.85, rot: 4 }});
      tl.to("#st-devils-x", {{ scaleX: 1, duration: 0.2, ease: "power2.out" }}, {t(24.10)});
      leave(["#st-church", "#st-devils"], {t(24.80)}, {{ y: -30 }});
      enter("#st-bit", {t(25.12)}, {{ fromScale: 0.85, rot: -3 }});
      leave("#st-bit", {t(25.95)}, {{ y: -30, rot: -10 }});

      // ---------- 500 лет до ЕГЭ: торговали товаром ----------
      enter("#b-500", {A500:.2f}, {{ fromScale: 1.3, dur: 0.2 }});
      enter("#b-500-lead", {A500 + 0.3:.2f}, {{ fromScale: 0.9, dur: 0.25 }});
{counter_js("b-500", len(Y500), A500, 0.06)}
      leave(["#b-500", "#b-500-lead"], {t(28.00)}, {{ y: -60 }});
      enter("#d-trade", {t(28.00)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#tr1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(28.10)});
      tl.to("#tr1-x", {{ scaleX: 1, duration: 0.22, ease: "power2.out" }}, {t(28.50)});
      tl.fromTo("#tr2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(29.76)});
      leave("#d-trade", {t(31.80)}, {{ y: 80 }});

      // ---------- доска: бочка, черточка, вторая черта — плюс ----------
{board[1]}
      slam("#b-plus2", {t(41.54)}, {{ fromScale: 1.6 }});
      leave("#b-plus2", {t(42.80)}, {{ y: -60 }});

      // ---------- пометки B2B-арбитражников: Видман, 1489 ----------
      doc("#d-wid", {t(43.40)}, {t(46.10)}, {{ rot: -2, fromRot: 6 }});
      enter("#st-b2b", {t(44.32)}, {{ fromScale: 0.85, rot: -4 }});
      leave("#st-b2b", {t(45.90)}, {{ y: -30, rot: -10 }});

      // ---------- кресты и черти в математике ----------
{f_signs[1]}

      // ---------- ЕГЭ на 80+ ----------
      enter("#b-80", {A80:.2f}, {{ fromScale: 1.3, dur: 0.2 }});
      enter("#b-80-lead", {A80 + 0.3:.2f}, {{ fromScale: 0.9, dur: 0.25 }});
{counter_js("b-80", len(Y80), A80, 0.07)}
      leave(["#b-80", "#b-80-lead"], {t(54.00)}, {{ y: -60 }});
'''
# Звуки — по правилам проекта (12.10): удары только на хук «+» и «получался плюс», остальное тихо и
# по одному на событие; одинаковые не подряд, файл не больше двух раз (pop — карточки и плашка CTA).
sounds = [
    audio("plus", "impact-bass-1", t(1.24), 1.0),
    audio("grave", "whoosh", t(3.18), 0.7),
    audio("minus", "click", t(6.94), 0.9),
    audio("cards", "pop", t(9.36), 0.8),
    audio("y500", "ping", A500, 0.7),
    audio("barrels", "whoosh-cinematic", t(30.28), 0.6),
    audio("plus2", "impact-bass-2", t(41.52), 1.0),
    audio("y80", "chime", A80, 0.7),
]
CTA_AT = t(54.16)
# человек поверх знаков, фонов и счётчиков за спиной
fg = [(t(1.10), t(8.90)), (A500 - 0.1, t(43.10)), (A80 - 0.1, t(54.30))]
page = build_page("Почему плюс — это крест", DUR, behind, front, beats, sounds, fg, cta_at=CTA_AT,
                  extra_css=css, cta_small="подписывайся на меня", fmt=fmt, captions=tk.captions)
page = page.replace('<div class="cta-big">Больше математики</div>', '<div class="cta-big">80+ на ЕГЭ</div>', 1)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

# whisper: «80» + «+,» — «+» приклеивается сам; «B2B» + «-арбитражников» — дефисный хвост тоже
fixes = {}

director = {
    "_note": "Плюс — крест, минус — черти, бочки. Время по дублю; раскладка — work/IMG_1827/page.py.",
    "punches": [[t(1.26), t(2.70), 1.32, 0.10], [t(6.96), t(8.20), 1.28, 0.10],
                [t(19.62), t(25.80), 1.27, 1.80, 0.50],                       # медленный наезд через мысль
                [t(26.50), t(27.70), 1.28, 0.10], [t(41.54), t(42.90), 1.34, 0.10],
                [t(46.18), t(47.60), 1.26, 0.30], [t(51.22), t(52.40), 1.28, 0.10]],
    "text_fixes": fixes,
    "keep_case": ["П", "М", "ЕГЭ", "B2B"],
    "accent_words": ["плюс", "минус", "крест", "черточку", "черту"],
    # на время плашек на груди (П/М, крипта/товар, доска, Видман) и формул внизу — субтитров нет
    "hide_captions": [[t(4.55), t(7.00)], [t(13.50), t(17.50)], [t(27.95), t(32.10)], [t(32.25), t(42.20)],
                      [t(43.35), t(46.45)], [t(47.65), t(49.95)], [CTA_AT - 0.05, DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
