"""Страница графики IMG_3305: почему в часе 60 минут, а не 100.

Время ударов — по исходнику, на шкалу дубля (с вырезом 9.78–13.37) переводит Take.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, doc_img  # noqa: E402

STEM = "IMG_3305"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
GREEN = "#3BD16F"


def pie(pid: str, left: int, sector: str, label: str) -> str:
    return f'''        <div id="{pid}" class="g" style="left: {left}px; top: 1262px; width: 330px; height: 360px; border-radius: 26px; background: rgba(12,12,14,0.86); border: 2px solid rgba(242,235,221,0.16);">
          <svg viewBox="0 0 330 270" style="position: absolute; left: 0; top: 0; width: 330px; height: 270px;">
            <circle cx="165" cy="140" r="110" fill="rgba(242,235,221,0.10)" stroke="#F2EBDD" stroke-width="6" />
            <path d="{sector}" fill="#F0352C" />
            <circle cx="165" cy="140" r="8" fill="#F2EBDD" />
          </svg>
          <div class="label" style="position: absolute; left: 0; top: 282px; width: 330px; font-size: 30px; letter-spacing: 0.06em;">{label}</div>
        </div>'''


def chips(cid: str, numbers: list, per_row: int, top: int) -> str:
    w, gap = 128, 14
    rows = [numbers[i:i + per_row] for i in range(0, len(numbers), per_row)]
    out = [f'        <div id="{cid}" class="g" style="left: 0; top: {top}px; width: 1080px; height: {len(rows) * 104}px;">']
    for r, row in enumerate(rows):
        x0 = (1080 - (len(row) * w + (len(row) - 1) * gap)) // 2
        for k, n in enumerate(row):
            out.append(f'          <div id="{cid}-{n}" class="chip" style="left: {x0 + k * (w + gap)}px; top: {r * 104}px;">{n}</div>')
    out.append("        </div>")
    return "\n".join(out)


css = '''      .chip { position: absolute; width: 128px; height: 90px; border-radius: 20px; background: rgba(12,12,14,0.86);
              border: 2px solid rgba(242,235,221,0.22); display: flex; align-items: center; justify-content: center;
              font-family: "JBMono"; font-weight: 700; font-size: 46px; color: var(--cream); }
      .eqn { left: 0; width: 1080px; text-align: center; font-family: "JBMono"; font-weight: 700; font-size: 120px;
             color: var(--cream); text-shadow: 0 10px 36px rgba(0,0,0,0.45); white-space: nowrap; }
'''

divs = [("2", "30"), ("3", "20"), ("4", "15"), ("5", "12"), ("6", "10")]
behind = "\n".join([
    '        <div id="h60" class="g big" style="left: 40px; width: 500px; top: 90px; font-size: 300px;">60</div>',
    '        <div id="h100" class="g big red" style="left: 500px; width: 560px; top: 120px; font-size: 250px;">100?</div>',
    '        <div id="d12-lead" class="g lead" style="top: 56px;">делителей у числа 60</div>',
    '        <div id="d12" class="g big" style="top: 70px; font-size: 260px;">12</div>',
    *[f'        <div id="eq{d}" class="g eqn" style="top: 150px;">60 : {d} = <span style="color: {GREEN};">{q}</span></div>' for d, q in divs],
    '        <div id="d100-lead" class="g lead" style="top: 56px;">делителей у числа 100</div>',
    '        <div id="d100" class="g big" style="top: 100px; font-size: 280px;">100</div>',
    '        <div id="d9" class="g big red" style="top: 50px; font-size: 260px;">9</div>',
    '        <div id="inf" class="g glyph mono" style="left: 0; width: 1080px; top: 30px; font-size: 330px;">∞</div>',
    '        <div id="y1793" class="g big" style="top: 110px; font-size: 230px;">1793</div>',
    '        <div id="dec" class="g eqn" style="top: 160px; font-size: 110px;"><span id="dec-a" style="display: inline-block;">10 ч</span> · <span id="dec-b" style="display: inline-block; color: var(--red);">100 мин</span></div>',
    '        <div id="lt2" class="g big red" style="top: 110px; font-size: 230px;">&lt; 2 лет</div>',
])
front = "\n".join([
    pie("pie-half", 170, "M 165 140 L 165 30 A 110 110 0 0 1 165 250 Z", "½ часа = 50 мин"),
    pie("pie-quart", 580, "M 165 140 L 165 30 A 110 110 0 0 1 275 140 Z", "¼ часа = 25 мин"),
    '        <div id="money" class="g sticker" style="left: 500px; top: 320px; font-size: 54px; white-space: nowrap;">как рубли и копейки</div>',
    chips("c60", ["1", "2", "3", "4", "5", "6", "10", "12", "15", "20", "30", "60"], 6, 1262),
    '        <div id="p-int" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 1490px; background: none; border: none; font-size: 42px;">каждый раз — <span style="color: #3BD16F;">целые минуты</span></div>',
    chips("c100", ["1", "2", "4", "5", "10", "20", "25", "50", "100"], 5, 1262),
    '        <div id="st-3" class="g stamp" style="left: 240px; top: 260px; font-size: 88px; background: rgba(12,12,14,0.55);">на 3 не делится</div>',
    '        <div id="third" class="g" style="left: 60px; top: 1262px; width: 960px; height: 150px; border-radius: 28px; background: rgba(12,12,14,0.86); border: 2px solid rgba(242,235,221,0.16); overflow: hidden;">',
    '          <div style="position: absolute; left: 40px; top: 30px; font-family: \'JBMono\'; font-weight: 700; font-size: 72px; color: var(--cream); white-space: nowrap;">1/3 ч =</div>',
    '          <div id="thr-win" style="position: absolute; left: 372px; top: 30px; width: 0; height: 100px; overflow: hidden;">',
    '            <div id="thr-digits" style="font-family: \'JBMono\'; font-weight: 700; font-size: 72px; color: var(--red); white-space: nowrap;">33,333333333333333333333333…</div>',
    '          </div>',
    '        </div>',
    '        <div id="p-third" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 1440px; background: none; border: none; font-size: 40px;">треть часа не записать <span style="color: var(--red);">ровно</span></div>',
    '        <div id="thanos" class="g sticker" style="left: 330px; top: 1290px; font-size: 56px; white-space: nowrap;">Танос, привет</div>',
    doc_img("dial", "decimal_dial.jpg", "десятичный циферблат, Франция, 1793", left=280, top=1235, width=520, height=440, position="50% 50%"),
    '        <div id="st-off" class="g stamp" style="left: 300px; top: 190px; font-size: 96px; background: rgba(12,12,14,0.55);">отменили</div>',
    '        <div id="p-355" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 1290px; background: none; border: none; font-size: 44px;">ЕГЭ по профилю — <span style="color: var(--red);">3 ч 55 мин</span></div>',
])

eq_js = []
times = [17.60, 18.20, 18.42, 18.74, 18.98]
for k, (d, _) in enumerate(divs):
    eq_js.append(f'      enter("#eq{d}", {t(times[k])}, {{ fromScale: 1.25, dur: 0.12, blur: 8, ease: "power3.out" }});')
    end = t(times[k + 1]) - 0.02 if k + 1 < len(times) else t(19.75)
    eq_js.append(f'      leave("#eq{d}", {end:.2f}, {{ y: -30, dur: 0.1 }});')
    eq_js.append(f'      tl.to("#c60-{d}", {{ backgroundColor: "#F0352C", borderColor: "#F0352C", scale: 1.12, duration: 0.12, ease: "power2.out" }}, {t(times[k])});')
eq_js = "\n".join(eq_js)

beats = f'''
      // ---------- хук: 60 минут, а не 100 ----------
      slam("#h60", {t(1.98)}, {{ fromScale: 1.5 }});
      slam("#h100", {t(3.12)}, {{ fromScale: 1.6 }});
      flash({t(3.12)});
      leave(["#h60", "#h100"], {t(3.62)}, {{ y: -60 }});

      // ---------- с сотней удобнее: полчаса 50, четверть 25 ----------
      enter("#pie-half", {t(5.20)}, {{ fromX: -220, fromScale: 0.9, rot: -3 }});
      enter("#pie-quart", {t(6.62)}, {{ fromX: 220, fromScale: 0.9, rot: 3 }});
      leave(["#pie-half", "#pie-quart"], {t(7.90)}, {{ y: 80 }});
      enter("#money", {t(8.64)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#money", {t(9.62)}, {{ y: -30, rot: 10 }});

      // ---------- у 60 двенадцать делителей ----------
      slam("#d12", {t(15.38)}, {{ fromScale: 1.6 }});
      enter("#d12-lead", {t(15.60)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave(["#d12", "#d12-lead"], {t(16.60)}, {{ y: -60 }});
      enter("#c60", {t(15.88)}, {{ fromY: 120, fromScale: 0.9, dur: 0.35, ease: "power3.out" }});
{eq_js}
      enter("#p-int", {t(21.26)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave(["#c60", "#p-int"], {t(22.70)}, {{ y: 80 }});

      // ---------- у 100 всего 9 и на 3 не делится ----------
      slam("#d100", {t(23.50)}, {{ fromScale: 1.5 }});
      enter("#c100", {t(24.02)}, {{ fromY: 120, fromScale: 0.9, dur: 0.35, ease: "power3.out" }});
      enter("#d100-lead", {t(24.02)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave("#d100", {t(25.48)}, {{ y: 0, scale: 0.6, dur: 0.1 }});
      slam("#d9", {t(25.60)}, {{ fromScale: 1.6 }});
      flash({t(25.60)});
      leave(["#d9", "#d100-lead"], {t(26.25)}, {{ y: -60 }});
      leave("#c100", {t(27.30)}, {{ y: 80 }});
      slam("#st-3", {t(26.98)}, {{ fromScale: 2.2, rot: -6, blur: 10 }});
      leave("#st-3", {t(27.95)}, {{ scale: 0.6, y: 0, rot: -18 }});

      // ---------- треть часа — бесконечная дробь ----------
      enter("#third", {t(28.30)}, {{ fromY: 120, fromScale: 0.92, dur: 0.35, ease: "power3.out" }});
      tl.fromTo("#thr-win", {{ width: 0 }}, {{ width: 550, duration: 1.0, ease: "none" }}, {t(28.48)});
      tl.fromTo("#thr-digits", {{ x: 0 }}, {{ x: -520, duration: 1.4, ease: "none", immediateRender: false }}, {t(29.48)});
      enter("#p-third", {t(29.24)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave(["#third", "#p-third"], {t(30.35)}, {{ y: 80 }});
      slam("#inf", {t(30.76)}, {{ fromScale: 1.6 }});
      leave("#inf", {t(32.20)}, {{ y: -60 }});
      enter("#thanos", {t(31.48)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#thanos", {t(32.40)}, {{ y: 60, rot: -10 }});

      // ---------- десятичное время во Франции ----------
      slam("#y1793", {t(33.58)}, {{ fromScale: 1.5 }});
      leave("#y1793", {t(35.30)}, {{ y: -60 }});
      doc("#dial", {t(33.18)}, {t(40.95)}, {{ fromRot: 6, rot: -2 }});
      tl.fromTo("#dial img", {{ rotation: -8 }}, {{ rotation: 8, duration: 7.8, ease: "none" }}, {t(33.18)});
      tl.set("#dec", {{ opacity: 1 }}, {t(36.66)});
      enter("#dec-a", {t(36.66)}, {{ fromScale: 1.4, dur: 0.18 }});
      enter("#dec-b", {t(38.12)}, {{ fromScale: 1.4, dur: 0.18 }});
      leave("#dec", {t(39.05)}, {{ y: -60 }});
      slam("#lt2", {t(40.30)}, {{ fromScale: 1.5 }});
      leave("#lt2", {t(41.20)}, {{ y: -60 }});
      slam("#st-off", {t(43.36)}, {{ fromScale: 2.2, rot: 6, blur: 10 }});
      leave("#st-off", {t(44.20)}, {{ scale: 0.6, y: 0, rot: 18 }});

      // ---------- 3 часа 55 минут ----------
      enter("#p-355", {t(46.48)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#p-355", {t(49.30)}, {{ y: 60 }});
'''
sounds = [
    audio("h60", "impact-bass-1", t(1.96), 0.40), audio("h100", "impact-bass-1", t(3.10), 0.42),
    audio("half", "pop", t(5.18), 0.30), audio("quart", "pop", t(6.60), 0.30), audio("money", "pop", t(8.62), 0.28),
    audio("d12", "impact-bass-1", t(15.36), 0.36), audio("c60", "whoosh", t(15.86), 0.22),
    *[audio(f"eq{d}", "click", t(times[k]) - 0.02, 0.36) for k, (d, _) in enumerate(divs)],
    audio("int", "ping", t(21.24), 0.28),
    audio("d100", "impact-bass-1", t(23.48), 0.34), audio("c100", "whoosh", t(24.00), 0.22),
    audio("d9", "impact-bass-1", t(25.58), 0.40), audio("st3", "error", t(26.96), 0.22),
    audio("third", "typing", t(28.48), 0.22, duration=1.0, fade_out=0.3),
    audio("inf", "whoosh-cinematic", t(30.74), 0.30), audio("thanos", "pop", t(31.46), 0.28),
    audio("dial", "whoosh", t(33.16), 0.24), audio("y1793", "impact-bass-1", t(33.56), 0.32),
    audio("deca", "click", t(36.64), 0.36), audio("decb", "click", t(38.10), 0.36),
    audio("lt2", "impact-bass-1", t(40.28), 0.34), audio("off", "error", t(43.34), 0.24),
    audio("p355", "pop", t(46.46), 0.30),
]
fg = [(t(1.90), t(3.95)), (t(15.30), t(16.95)), (t(17.50), t(20.05)), (t(23.40), t(26.60)),
      (t(30.66), t(32.55)), (t(33.48), t(35.65)), (t(36.56), t(39.40)), (t(40.20), t(41.55))]
page = build_page("Почему в часе 60 минут", DUR, behind, front, beats, sounds, fg, cta_at=t(49.94),
                  extra_css=css, cta_small="ЕГЭ на максимум — переходи ко мне")
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

director = {
    "_note": "60 минут. Время по дублю; раскладка — work/IMG_3305/page.py. Вырез 9.78–13.37 исходника.",
    "punches": [[t(3.12), t(3.90), 1.18, 0.10], [t(13.37), t(14.90), 1.20, 0.0, 0.6],
                [t(25.60), t(26.40), 1.18, 0.10], [t(30.76), t(31.60), 1.16, 0.10], [t(43.36), t(44.10), 1.22, 0.05]],
    "text_fixes": tk.fixes({24: "деньги"}),
    "keep_case": ["ЕГЭ", "Танос"],
    "accent_words": ["12", "9", "бесконечно", "дерьмо"],
    "hide_captions": [[t(1.95), t(3.65)], [t(15.30), t(16.10)], [t(17.55), t(19.95)], [t(25.55), t(26.05)],
                      [t(49.85), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
