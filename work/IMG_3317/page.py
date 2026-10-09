"""Страница графики IMG_3317: Тим Кук берёт айфон в кредит — аннуитет за два шага.

Время ударов — по исходнику, на шкалу дубля переводит Take.
Проверено: x = 182 000 · 1,2³ · 0,2 / (1,2³ − 1) = 86 400 ₽, всего 259 200 ₽, переплата 77 200 ₽.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, keyword_beats, keyword_card  # noqa: E402

STEM = "IMG_3317"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
GREEN = "#3BD16F"

css = '''      .task { padding: 26px 34px 30px; border-radius: 12px; background: #FBFBF8; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      .task-head { font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.12em; text-transform: uppercase; color: #2B3A67; }
      .task-row { margin-top: 14px; font-family: "JBMono"; font-weight: 700; font-size: 44px; color: #1A1A1A; opacity: 0; white-space: nowrap; }
      .tc { position: absolute; width: 333px; height: 105px; display: flex; align-items: center; justify-content: center;
            font-family: "JBMono"; font-weight: 700; font-size: 42px; color: var(--cream); white-space: nowrap; opacity: 0; }
      .th { position: absolute; top: 0; width: 333px; height: 70px; display: flex; align-items: center; justify-content: center;
            font-family: "Manrope"; font-weight: 800; font-size: 28px; letter-spacing: 0.08em; text-transform: uppercase; color: #F5B82E; opacity: 0; }
'''

phone = '''        <svg id="phone" class="g" viewBox="0 0 300 520" style="left: 390px; top: 1235px; width: 300px; height: 520px;">
          <defs><linearGradient id="ph-grad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3A2A6B" /><stop offset="1" stop-color="#C44A6A" /></linearGradient></defs>
          <rect x="10" y="10" width="280" height="500" rx="46" fill="#1C1C1F" stroke="#B8B2A6" stroke-width="6" />
          <rect x="24" y="24" width="252" height="472" rx="34" fill="url(#ph-grad)" />
          <rect x="112" y="40" width="76" height="22" rx="11" fill="#0B0B0D" />
          <text x="150" y="262" text-anchor="middle" font-family="Oswald" font-weight="700" font-size="110" fill="#F2EBDD">18</text>
          <text x="150" y="316" text-anchor="middle" font-family="Manrope" font-weight="800" font-size="30" letter-spacing="3" fill="#F2EBDD">PRO MAX</text>
        </svg>'''

rows = [("tr1", "S = 182 000 ₽"), ("tr2", "срок: 3 года"), ("tr3", "каждый январь: +20%"),
        ("tr4", "платежи равные: x"), ("tr5", "всего заплатит: ?")]
task = ('        <div id="task" class="g task" style="left: 90px; top: 1235px; width: 900px;">\n'
        '          <div class="task-head">задача №13 · кредит</div>\n'
        + "\n".join(f'          <div id="{rid}" class="task-row">{txt}</div>' for rid, txt in rows)
        + '\n        </div>')

cells = [["S", "S·k", "S·k − x"], ["S·k − x", "(…)·k", "(…)·k − x"], ["…", "…·k", "…·k − x = 0"]]
tbl = ['        <div id="tbl" class="g" style="left: 40px; top: 1225px; width: 1000px; height: 386px; border-radius: 24px; '
       'background: rgba(12,12,14,0.88); border: 2px solid rgba(242,235,221,0.16); overflow: hidden;">',
       '          <svg viewBox="0 0 1000 386" style="position: absolute; left: 0; top: 0; width: 1000px; height: 386px;">'
       '<g stroke="rgba(242,235,221,0.22)" stroke-width="2"><path d="M 0 70 H 1000 M 0 175 H 1000 M 0 280 H 1000 M 333 0 V 386 M 666 0 V 386" /></g></svg>']
for k, title in enumerate(["долг", "+ процент", "− платёж"]):
    tbl.append(f'          <div id="th{k + 1}" class="th" style="left: {333 * k}px;">{title}</div>')
for r, row in enumerate(cells):
    for c, txt in enumerate(row):
        tbl.append(f'          <div id="c{r + 1}{c + 1}" class="tc" style="left: {333 * c}px; top: {70 + 105 * r}px;">{txt}</div>')
tbl.append("        </div>")
tbl = "\n".join(tbl)

behind = "\n".join([
    '        <div id="b-credit" class="g big red" style="top: 110px; font-size: 220px;">в кредит</div>',
    '        <div id="b13-lead" class="g lead" style="top: 56px;">экономика — теперь в 1-й части</div>',
    '        <div id="b13" class="g big red" style="top: 100px; font-size: 280px;">№ 13</div>',
    '        <div id="b-ann-lead" class="g lead" style="top: 56px;">одинаковые платежи —</div>',
    '        <div id="b-ann" class="g big red" style="top: 110px; font-size: 190px;">аннуитет</div>',
    '        <div id="b-2" class="g big" style="top: 110px; font-size: 220px;">2 шага</div>',
    '        <div id="b-s1" class="g big" style="top: 110px; font-size: 220px;">шаг 1</div>',
    '        <div id="b-s2" class="g big" style="top: 110px; font-size: 220px;">шаг 2</div>',
    '        <div id="b77-lead" class="g lead" style="top: 56px;">переплата банку</div>',
    '        <div id="b77" class="g big red" style="top: 100px; font-size: 200px;">77 200 ₽</div>',
])
front = "\n".join([
    phone,
    '        <div id="st-ex" class="g sticker" style="left: 300px; top: 225px; font-size: 56px; white-space: nowrap;">бывший глава Apple</div>',
    '        <div id="p-ege" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 300px; background: none; border: none; font-size: 40px;">задача из реального ЕГЭ</div>',
    task,
    '        <div id="st-tem" class="g sticker" style="left: 320px; top: 300px; font-size: 56px; white-space: nowrap;">настоящий темщик</div>',
    '        <div id="step1" class="g" style="left: 90px; top: 1250px; width: 900px; height: 230px; border-radius: 28px; background: rgba(12,12,14,0.86); border: 2px solid rgba(242,235,221,0.16);">',
    '          <div class="label" style="position: absolute; left: 0; top: 26px; width: 900px; font-size: 28px; color: #F5B82E;">коэффициент</div>',
    '          <div style="position: absolute; left: 0; top: 86px; width: 900px; text-align: center; font-family: \'JBMono\'; font-weight: 700; font-size: 80px; color: var(--cream); white-space: nowrap;">'
    '<span id="k-a" style="display: inline-block; opacity: 0;">k =</span> <span id="k-b" style="display: inline-block; opacity: 0;">1 + 0,2</span> '
    '<span id="k-c" style="display: inline-block; opacity: 0; color: var(--red);">= 1,2</span></div>',
    '        </div>',
    tbl,
    '        <div id="p-ans" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 1290px; background: none; border: none; font-size: 38px;">платёж 86 400 ₽ × 3 = <span style="color: var(--red);">259 200 ₽</span></div>',
    '        <div id="st-bank" class="g sticker" style="left: 360px; top: 300px; font-size: 56px; white-space: nowrap;">банк доволен</div>',
    keyword_card("экономика", "кодовое слово", "пришлю полный разбор", placeholder="Сообщение…"),
])

beats = f'''
      // ---------- хук: Тим Кук берёт айфон в кредит ----------
      enter("#phone", {t(2.22)}, {{ fromY: 140, fromScale: 0.8, rot: -6, dur: 0.4, ease: "power3.out" }});
      slam("#b-credit", {t(3.92)}, {{ fromScale: 1.5 }});
      flash({t(3.92)});
      leave("#b-credit", {t(4.70)}, {{ y: -60 }});
      leave("#phone", {t(4.80)}, {{ y: 80, rot: 8 }});
      enter("#st-ex", {t(5.40)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-ex", {t(7.60)}, {{ y: -30, rot: -10 }});
      enter("#p-ege", {t(8.62)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#p-ege", {t(10.40)}, {{ y: -30 }});
      enter("#b13-lead", {t(12.24)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b13", {t(13.58)}, {{ fromScale: 1.6 }});
      leave(["#b13", "#b13-lead"], {t(14.90)}, {{ y: -60 }});

      // ---------- условие: бланк задачи заполняется по словам ----------
      enter("#task", {t(17.86)}, {{ fromY: 140, fromScale: 0.92, rot: -2, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#tr1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(20.12)});
      tl.fromTo("#tr2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(21.94)});
      enter("#st-tem", {t(23.90)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-tem", {t(24.90)}, {{ y: -30, rot: -10 }});
      tl.fromTo("#tr3", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(25.90)});
      tl.fromTo("#tr4", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(30.46)});
      tl.fromTo("#tr5", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(33.18)});
      leave("#task", {t(35.00)}, {{ y: 80 }});

      // ---------- одинаковые платежи — аннуитет; решаем в два шага ----------
      enter("#b-ann-lead", {t(36.86)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-ann", {t(39.76)}, {{ fromScale: 1.5 }});
      flash({t(39.76)});
      leave(["#b-ann", "#b-ann-lead"], {t(41.20)}, {{ y: -60 }});
      slam("#b-2", {t(42.78)}, {{ fromScale: 1.5 }});
      leave("#b-2", {t(43.38)}, {{ y: -60, dur: 0.15 }});
      slam("#b-s1", {t(43.48)}, {{ fromScale: 1.4 }});
      leave("#b-s1", {t(44.60)}, {{ y: -60 }});

      // ---------- шаг 1: коэффициент 1,2 ----------
      enter("#step1", {t(44.18)}, {{ fromY: 120, fromScale: 0.92, dur: 0.35, ease: "power3.out" }});
      enter("#k-a", {t(44.70)}, {{ fromScale: 1.4, dur: 0.15, blur: 6 }});
      enter("#k-b", {t(48.18)}, {{ fromScale: 1.4, dur: 0.15, blur: 6 }});
      enter("#k-c", {t(51.78)}, {{ fromScale: 1.4, dur: 0.15, blur: 6 }});
      leave("#step1", {t(54.50)}, {{ y: 80 }});

      // ---------- шаг 2: табличка из трёх столбцов ----------
      slam("#b-s2", {t(54.74)}, {{ fromScale: 1.4 }});
      leave("#b-s2", {t(55.80)}, {{ y: -60 }});
      enter("#tbl", {t(56.02)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.to(["#th1", "#th2", "#th3"], {{ opacity: 1, duration: 0.15, stagger: 0.12 }}, {t(58.84)});
      tl.to("#c11", {{ opacity: 1, duration: 0.15 }}, {t(62.14)});
      tl.to("#c12", {{ opacity: 1, duration: 0.15 }}, {t(65.22)});
      tl.to("#c13", {{ opacity: 1, duration: 0.15 }}, {t(68.16)});
      tl.to("#c21", {{ opacity: 1, duration: 0.15 }}, {t(70.22)});
      tl.to("#c22", {{ opacity: 1, duration: 0.15 }}, {t(72.70)});
      tl.to("#c23", {{ opacity: 1, duration: 0.15 }}, {t(73.44)});
      tl.to(["#c31", "#c32", "#c33"], {{ opacity: 1, duration: 0.12, stagger: 0.18 }}, {t(74.38)});
      tl.to("#c33", {{ color: "{GREEN}", scale: 1.08, duration: 0.2, ease: "back.out(2)" }}, {t(79.92)});
      tl.to("#c33", {{ scale: 1, duration: 0.3, ease: "power2.out" }}, {t(82.22)});
      leave("#tbl", {t(83.00)}, {{ y: 80 }});

      // ---------- итог: переплата 77 200 ₽ ----------
      enter("#b77-lead", {t(84.36)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b77", {t(85.14)}, {{ fromScale: 1.5 }});
      flash({t(85.14)});
      leave(["#b77", "#b77-lead"], {t(86.60)}, {{ y: -60 }});
      enter("#p-ans", {t(85.54)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#p-ans", {t(88.90)}, {{ y: 60 }});
      enter("#st-bank", {t(87.88)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-bank", {t(88.95)}, {{ y: -30, rot: -10 }});

      // ---------- кодовое слово ----------
{keyword_beats(t(93.78), t(94.72), t(95.74), len("экономика"), t_cta_out=t(93.60))}
'''
sounds = [
    audio("phone", "whoosh", t(2.20), 0.24), audio("credit", "impact-bass-1", t(3.90), 0.42),
    audio("ex", "pop", t(5.38), 0.28), audio("ege", "pop", t(8.60), 0.28), audio("b13", "impact-bass-1", t(13.56), 0.38),
    audio("task", "whoosh", t(17.84), 0.24),
    *[audio(f"tr{k}", "click", t(x) - 0.02, 0.32) for k, x in enumerate([20.12, 21.94, 25.90, 30.46, 33.18])],
    audio("tem", "pop", t(23.88), 0.26), audio("ann", "impact-bass-1", t(39.74), 0.38),
    audio("two", "click", t(42.76), 0.34), audio("s1", "whoosh-short", t(43.46), 0.26),
    audio("ka", "click", t(44.68), 0.32), audio("kb", "click", t(48.16), 0.32), audio("kc", "ping", t(51.76), 0.30),
    audio("s2", "whoosh-short", t(54.72), 0.26), audio("tbl", "whoosh", t(56.00), 0.24),
    *[audio(f"c{k}", "click-soft", t(x) - 0.02, 0.36) for k, x in enumerate([62.14, 65.22, 68.16, 70.22, 72.70, 73.44, 74.38])],
    audio("zero", "ping", t(79.90), 0.30), audio("b77", "impact-bass-1", t(85.12), 0.42),
    audio("bank", "pop", t(87.86), 0.26),
    audio("kw", "whoosh-short", t(93.76), 0.24), audio("type", "typing", t(94.70), 0.30, duration=0.6, fade_out=0.2),
    audio("note", "notification", t(95.72), 0.22),
]
fg = [(t(3.82), t(5.10)), (t(12.14), t(15.25)), (t(36.76), t(41.55)), (t(42.68), t(44.95)),
      (t(54.64), t(56.15)), (t(84.26), t(86.95))]
page = build_page("Тим Кук и кредит на айфон", DUR, behind, front, beats, sounds, fg, cta_at=t(89.26),
                  extra_css=css, cta_small="решаю экономику легко — переходи")
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

director = {
    "_note": "Аннуитет. Время по дублю; раскладка — work/IMG_3317/page.py.",
    "punches": [[t(3.92), t(4.70), 1.18, 0.10], [t(13.58), t(14.50), 1.18, 0.10],
                [t(39.76), t(40.60), 1.16, 0.10], [t(85.14), t(86.10), 1.20, 0.10]],
    "text_fixes": tk.fixes({143: "1,2", 144: ""}),
    "keep_case": ["Тим", "Кук", "iPhone", "Pro", "Max", "Apple", "ЕГЭ", "S", "SK", "X", "K"],
    "accent_words": ["кредит", "аннуитетной", "нулю", "77"],
    "hide_captions": [[t(3.85), t(4.60)], [t(13.50), t(14.40)], [t(39.70), t(40.70)], [t(42.70), t(44.40)],
                      [t(54.70), t(55.60)], [t(85.10), t(86.20)], [t(89.20), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
