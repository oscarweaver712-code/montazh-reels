"""Страница графики IMG_3322: Михаил Сергеевич кладёт 120 млн во вклад.

Время ударов — по исходнику, на шкалу дубля переводит Take.
Проверено: 120·1,15 = 138; (138+10)·1,15 = 170,2; (170,2+10)·1,15 = 207,23 млн ₽.
Михаил Сергеевич здесь — персонаж задачи: только стикмен, без чьих-либо портретов.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, keyword_beats, keyword_card  # noqa: E402

STEM = "IMG_3322"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
GREEN = "#3BD16F"
CREAM = "#F2EBDD"

css = '''      .task { padding: 26px 34px 30px; border-radius: 12px; background: #FBFBF8; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      .task-head { font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.12em; text-transform: uppercase; color: #2B3A67; }
      .task-row { margin-top: 14px; font-family: "JBMono"; font-weight: 700; font-size: 38px; color: #1A1A1A; opacity: 0; white-space: nowrap; }
      .calc-row { position: absolute; left: 30px; width: 940px; font-family: "JBMono"; font-weight: 700; font-size: 40px;
                  color: var(--cream); white-space: nowrap; opacity: 0; }
      .calc-row b { color: #F5B82E; font-weight: 700; }
      .col-mul { font-family: "JBMono"; font-weight: 700; font-size: 46px; line-height: 1.18; color: #1F3FA8; text-align: right; white-space: pre; }
'''

worker = f'''        <svg id="worker" class="g" viewBox="0 0 500 360" style="left: 290px; top: 1262px; width: 500px; height: 360px; overflow: visible;">
          <circle cx="250" cy="96" r="36" fill="{CREAM}" />
          <path d="M 206 92 C 206 50 294 50 294 92 Z" fill="#F28C28" /><rect x="198" y="88" width="104" height="10" rx="5" fill="#F28C28" />
          <g fill="none" stroke="{CREAM}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round">
            <path d="M 250 132 V 240 M 250 160 L 200 230 M 250 160 L 300 230 M 250 240 L 212 330 M 250 240 L 288 330" />
          </g>
          <text x="250" y="24" text-anchor="middle" font-family="Manrope" font-weight="800" font-size="28" letter-spacing="2" fill="#F5B82E">МИХАИЛ СЕРГЕЕВИЧ</text>
        </svg>'''

road = f'''        <svg id="road" class="g" viewBox="0 0 800 320" style="left: 140px; top: 1290px; width: 800px; height: 320px; overflow: visible;">
          <rect x="0" y="230" width="800" height="70" rx="8" fill="#6B5537" />
          <rect id="lay1" x="0" y="170" width="800" height="60" fill="#2E2E33" />
          <g id="lay2"><rect x="0" y="100" width="800" height="70" fill="#45454C" />
            <path d="M 40 135 H 760" stroke="#F2EBDD" stroke-width="8" stroke-dasharray="60 40" /></g>
          <g font-family="Manrope" font-weight="800" font-size="26" letter-spacing="2" fill="#F2EBDD">
            <text id="lb-l2" x="810" y="145" opacity="0">СЛОЙ 2</text><text id="lb-l1" x="810" y="210" opacity="0">СЛОЙ 1</text>
          </g>
          <path id="x-l2" d="M 808 112 L 920 160 M 920 112 L 808 160" stroke="#F0352C" stroke-width="8" stroke-linecap="round" opacity="0" />
        </svg>'''

bank = '''        <svg id="bank" class="g" viewBox="0 0 400 360" style="left: 340px; top: 1262px; width: 400px; height: 360px;">
          <path d="M 30 120 L 200 30 L 370 120 Z" fill="none" stroke="#F2EBDD" stroke-width="10" stroke-linejoin="round" />
          <g fill="#F2EBDD"><rect x="60" y="140" width="34" height="150" rx="4" /><rect x="140" y="140" width="34" height="150" rx="4" />
            <rect x="226" y="140" width="34" height="150" rx="4" /><rect x="306" y="140" width="34" height="150" rx="4" />
            <rect x="30" y="300" width="340" height="24" rx="6" /></g>
          <circle id="bank-pc" cx="200" cy="88" r="26" fill="#F5B82E" />
          <text x="200" y="99" text-anchor="middle" font-family="JBMono" font-weight="700" font-size="32" fill="#1A1612">%</text>
        </svg>'''

rows = [("tr1", "вклад: 120 млн ₽ на 3 года"), ("tr2", "в конце года: +15%"), ("tr3", "в начале 2-го и 3-го: +10 млн"),
        ("tr4", "сколько будет в конце?")]
task = ('        <div id="task" class="g task" style="left: 90px; top: 1235px; width: 900px;">\n'
        '          <div class="task-head">задача №13 · вклад</div>\n'
        + "\n".join(f'          <div id="{rid}" class="task-row">{txt}</div>' for rid, txt in rows)
        + '\n        </div>')

calc = '''        <div id="calc" class="g" style="left: 40px; top: 1240px; width: 1000px; height: 330px; border-radius: 26px; background: rgba(12,12,14,0.88); border: 2px solid rgba(242,235,221,0.16);">
          <div id="cr1" class="calc-row" style="top: 34px;"><b>1-й год:</b> 120 · 1,15 = <span id="cr1-r" style="color: #3BD16F; opacity: 0;">138</span></div>
          <div id="cr2" class="calc-row" style="top: 134px;"><b>2-й год:</b> (138 <span id="cr2-p" style="opacity: 0;">+ 10</span>) · 1,15 = <span id="cr2-r" style="color: #3BD16F; opacity: 0;">170,2</span></div>
          <div id="cr3" class="calc-row" style="top: 234px;"><b>3-й год:</b> (170,2 + 10) · 1,15 = <span style="color: #F0352C;">207,23</span></div>
        </div>'''

calculator = '''        <svg id="calcx" class="g" viewBox="0 0 260 340" style="left: 410px; top: 1262px; width: 260px; height: 340px; overflow: visible;">
          <rect x="10" y="10" width="240" height="320" rx="26" fill="#2A2A30" stroke="#F2EBDD" stroke-width="6" />
          <rect x="34" y="34" width="192" height="64" rx="10" fill="#9FC9A6" />
          <g fill="#F2EBDD">''' + "".join(f'<rect x="{36 + 52 * c}" y="{118 + 52 * r}" width="40" height="40" rx="8" />' for r in range(4) for c in range(4)) + '''</g>
          <path id="calcx-x" d="M -10 -10 L 270 350 M 270 -10 L -10 350" stroke="#F0352C" stroke-width="16" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
        </svg>'''

column = ('        <div id="colmul" class="g notebook" style="left: 330px; top: 1235px; width: 420px;">\n'
          '          <div class="col-mul">  180,2\n×   1,15\n───────\n   9010\n  1802 \n 1802  \n───────\n207,230</div>\n'
          '        </div>')

behind = "\n".join([
    '        <div id="b120" class="g big red" style="top: 110px; font-size: 220px; white-space: nowrap;">120 млн ₽</div>',
    '        <div id="b-inv-lead" class="g lead" style="top: 56px;">во вкладе всё</div>',
    '        <div id="b-inv" class="g big" style="top: 110px; font-size: 220px;">наоборот</div>',
    '        <div id="b-k" class="g glyph mono" style="left: 0; width: 1080px; top: 110px; font-size: 160px; white-space: nowrap;">k = <span style="color: var(--red);">1,15</span></div>',
    '        <div id="b207-lead" class="g lead" style="top: 56px;">в итоге во вкладе</div>',
    '        <div id="b207" class="g big red" style="top: 110px; font-size: 150px; white-space: nowrap;">207 230 000 ₽</div>',
])
front = "\n".join([
    worker,
    road,
    '        <div id="st-honest" class="g sticker" style="left: 260px; top: 300px; font-size: 56px; white-space: nowrap;">гражданин порядочный</div>',
    bank,
    '        <div id="p-ege" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 300px; background: none; border: none; font-size: 40px;">задача из реального ЕГЭ</div>',
    task,
    '        <div id="st-roads" class="g sticker" style="left: 150px; top: 300px; font-size: 52px; white-space: nowrap;">летом же снова дороги перекладывать</div>',
    '        <div id="p-owes" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 300px; background: none; border: none; font-size: 40px;">теперь банк должен <span style="color: #3BD16F;">тебе</span></div>',
    calc,
    '        <div id="p-logic" class="g pill" style="left: 110px; top: 300px; font-size: 38px;"><s>логика</s></div>',
    '        <div id="p-count" class="g pill" style="left: 600px; top: 300px; font-size: 38px;">счёт <span style="color: #F0352C;">!</span></div>',
    calculator,
    column,
    '        <div id="st-minus" class="g stamp" style="left: 340px; top: 260px; font-size: 100px; background: rgba(12,12,14,0.55);">−1 балл</div>',
    '        <div id="st-asph" class="g sticker" style="left: 230px; top: 300px; font-size: 52px; white-space: nowrap;">и тоже перекладывать асфальт</div>',
    keyword_card("экономика", "пиши в комментариях", "пришлю полный разбор"),
])

beats = f'''
      // ---------- хук: Михаил Сергеевич перекладывал дорогу ----------
      enter("#worker", {t(2.70)}, {{ fromY: 140, fromScale: 0.8, dur: 0.4, ease: "back.out(1.6)" }});
      leave("#worker", {t(5.10)}, {{ y: 80 }});
      tl.set("#road", {{ opacity: 1 }}, {t(5.34)});
      tl.fromTo("#road", {{ y: 140, scale: 0.92 }}, {{ y: 0, scale: 1, duration: 0.35, ease: "power3.out" }}, {t(5.34)});
      tl.to(["#lb-l2", "#lb-l1"], {{ opacity: 1, duration: 0.15, stagger: 0.15 }}, {t(6.86)});
      tl.to("#lay2", {{ x: 900, opacity: 0, duration: 0.45, ease: "power2.in" }}, {t(8.62)});
      tl.to("#x-l2", {{ opacity: 1, duration: 0.12 }}, {t(8.80)});
      leave("#road", {t(9.70)}, {{ y: 80 }});
      slam("#b120", {t(9.94)}, {{ fromScale: 1.5 }});
      flash({t(9.94)});
      leave("#b120", {t(11.40)}, {{ y: -60 }});

      // ---------- порядочный: отнёс в банк под процент ----------
      enter("#st-honest", {t(12.78)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-honest", {t(13.90)}, {{ y: -30, rot: -10 }});
      enter("#bank", {t(14.08)}, {{ fromY: 140, fromScale: 0.85, dur: 0.4, ease: "back.out(1.6)" }});
      tl.fromTo("#bank-pc", {{ scale: 0.3, svgOrigin: "200 88" }}, {{ scale: 1, duration: 0.25, ease: "back.out(2.5)", immediateRender: false }}, {t(14.68)});
      leave("#bank", {t(15.60)}, {{ y: 80 }});
      enter("#p-ege", {t(15.88)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#p-ege", {t(17.40)}, {{ y: -30 }});

      // ---------- условие ----------
      enter("#task", {t(17.60)}, {{ fromY: 140, fromScale: 0.92, rot: -2, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#tr1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(18.32)});
      tl.fromTo("#tr2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(21.20)});
      tl.fromTo("#tr3", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(25.98)});
      enter("#st-roads", {t(27.40)}, {{ fromScale: 0.6, rot: -3 }});
      leave("#st-roads", {t(28.70)}, {{ y: -30, rot: -8 }});
      tl.fromTo("#tr4", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(29.52)});
      leave("#task", {t(30.60)}, {{ y: 80 }});

      // ---------- во вкладе всё наоборот: банк должен тебе, k = 1,15 ----------
      enter("#b-inv-lead", {t(30.90)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-inv", {t(31.56)}, {{ fromScale: 1.5 }});
      leave(["#b-inv", "#b-inv-lead"], {t(32.60)}, {{ y: -60 }});
      enter("#p-owes", {t(33.00)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#p-owes", {t(35.20)}, {{ y: -30 }});
      slam("#b-k", {t(36.40)}, {{ fromScale: 1.5 }});
      leave("#b-k", {t(37.40)}, {{ y: -60 }});

      // ---------- три года по строчке ----------
      enter("#calc", {t(37.58)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#cr1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(38.16)});
      tl.to("#cr1-r", {{ opacity: 1, duration: 0.15 }}, {t(39.92)});
      tl.fromTo("#cr2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(40.58)});
      tl.to("#cr2-p", {{ opacity: 1, duration: 0.15 }}, {t(42.80)});
      tl.to("#cr2-r", {{ opacity: 1, duration: 0.15 }}, {t(45.42)});
      tl.fromTo("#cr3", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(46.30)});
      leave("#calc", {t(48.80)}, {{ y: 80 }});
      enter("#b207-lead", {t(47.88)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b207", {t(48.96)}, {{ fromScale: 1.5 }});
      flash({t(48.96)});
      leave(["#b207", "#b207-lead"], {t(51.20)}, {{ y: -60 }});

      // ---------- сложность — счёт: калькулятора нет, всё в столбик ----------
      enter("#p-logic", {t(53.80)}, {{ fromX: -220, fromScale: 0.9, rot: -3 }});
      enter("#p-count", {t(54.40)}, {{ fromX: 220, fromScale: 0.9, rot: 3 }});
      leave(["#p-logic", "#p-count"], {t(55.40)}, {{ y: -30 }});
      enter("#calcx", {t(55.02)}, {{ fromY: 120, fromScale: 0.85, dur: 0.35, ease: "power3.out" }});
      draw("#calcx-x", {t(55.86)}, 0.25);
      leave("#calcx", {t(56.70)}, {{ y: 80 }});
      doc("#colmul", {t(56.84)}, {t(58.95)}, {{ fromRot: -5, rot: 1 }});
      slam("#st-minus", {t(58.16)}, {{ fromScale: 2.2, rot: -6, blur: 10 }});
      leave("#st-minus", {t(59.00)}, {{ scale: 0.6, y: 0, rot: -18 }});

      // ---------- финал: асфальт и кодовое слово ----------
      enter("#st-asph", {t(65.90)}, {{ fromScale: 0.6, rot: -3 }});
      leave("#st-asph", {t(67.05)}, {{ y: -30, rot: -8 }});
{keyword_beats(t(67.16), t(68.66), t(69.80), len("экономика"), t_cta_out=t(67.00))}
'''
sounds = [
    audio("worker", "pop", t(2.68), 0.30), audio("road", "whoosh-short", t(5.32), 0.24),
    audio("layers", "click", t(6.84), 0.32), audio("strip", "whoosh", t(8.60), 0.26),
    audio("b120", "impact-bass-1", t(9.92), 0.42), audio("honest", "pop", t(12.76), 0.26),
    audio("bank", "whoosh-short", t(14.06), 0.26), audio("pc", "ping", t(14.66), 0.28),
    audio("ege", "pop", t(15.86), 0.26), audio("task", "whoosh", t(17.58), 0.24),
    *[audio(f"tr{k}", "click", t(x) - 0.02, 0.32) for k, x in enumerate([18.32, 21.20, 25.98, 29.52])],
    audio("roads", "pop", t(27.38), 0.26), audio("inv", "impact-bass-1", t(31.54), 0.34),
    audio("owes", "pop", t(32.98), 0.26), audio("k", "impact-bass-1", t(36.38), 0.32),
    audio("calc", "whoosh", t(37.56), 0.24),
    *[audio(f"cr{k}", "click", t(x) - 0.02, 0.32) for k, x in enumerate([38.16, 40.58, 46.30])],
    audio("r1", "ping", t(39.90), 0.24), audio("r2", "ping", t(45.40), 0.24),
    audio("b207", "impact-bass-1", t(48.94), 0.42),
    audio("logic", "error", t(53.78), 0.18), audio("count", "pop", t(54.38), 0.28),
    audio("calcx", "whoosh-short", t(55.00), 0.24), audio("calcxx", "error", t(55.84), 0.22),
    audio("colmul", "whoosh", t(56.82), 0.22), audio("minus", "impact-bass-1", t(58.14), 0.30),
    audio("asph", "pop", t(65.88), 0.26),
    audio("kw", "whoosh-short", t(67.14), 0.24), audio("type", "typing", t(68.64), 0.30, duration=0.6, fade_out=0.2),
    audio("note", "notification", t(69.78), 0.22),
]
fg = [(t(9.84), t(11.75)), (t(30.80), t(32.95)), (t(36.30), t(37.75)), (t(47.78), t(51.55))]
page = build_page("Михаил Сергеевич и вклад", DUR, behind, front, beats, sounds, fg, cta_at=t(59.22),
                  extra_css=css, cta_small="ЕГЭ на 80+ — разберу все такие задачи")
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

director = {
    "_note": "Вклад. Время по дублю; раскладка — work/IMG_3322/page.py.",
    "punches": [[t(9.94), t(10.90), 1.18, 0.10], [t(31.56), t(32.40), 1.16, 0.10],
                [t(48.96), t(50.00), 1.20, 0.10], [t(58.16), t(58.90), 1.20, 0.05]],
    "text_fixes": tk.fixes({9: "твоём", 13: "слоёв", 31: "отнёс", 94: "1,15", 95: "", 102: "1,15", 103: "", 143: "счёт"}),
    "keep_case": ["Михаил", "Сергеевич", "ЕГЭ"],
    "accent_words": ["120", "207", "столбик", "счёт"],
    "hide_captions": [[t(9.90), t(11.00)], [t(36.35), t(37.20)], [t(48.90), t(50.80)], [t(59.15), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
