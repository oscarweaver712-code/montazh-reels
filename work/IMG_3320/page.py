"""Страница графики IMG_3320: Тимофей и дифференцированный платёж.

Время ударов — по исходнику, на шкалу дубля (вырезана оговорка 54.06–57.92) переводит Take.
Ответ задачи (r = 2% в месяц: 1 + r·(14+1)/2 = 1,15) в ролике не звучит — на экран не выносим,
полный разбор он отдаёт по кодовому слову.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, keyword_beats, keyword_card  # noqa: E402

STEM = "IMG_3320"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
GREEN = "#3BD16F"
CREAM = "#F2EBDD"

css = '''      .task { padding: 26px 34px 30px; border-radius: 12px; background: #FBFBF8; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      .task-head { font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.12em; text-transform: uppercase; color: #2B3A67; }
      .task-row { margin-top: 14px; font-family: "JBMono"; font-weight: 700; font-size: 40px; color: #1A1A1A; opacity: 0; white-space: nowrap; }
      .tc { position: absolute; width: 333px; height: 80px; display: flex; align-items: center; justify-content: center;
            font-family: "JBMono"; font-weight: 700; font-size: 40px; color: var(--cream); white-space: nowrap; opacity: 0; }
      .th { position: absolute; top: 0; width: 333px; height: 70px; display: flex; align-items: center; justify-content: center;
            font-family: "Manrope"; font-weight: 800; font-size: 28px; letter-spacing: 0.08em; text-transform: uppercase; color: #F5B82E; opacity: 0; }
'''


def figure(fid: str, x: float, base: float, h: float, extra: str = "") -> str:
    """Стикмен ростом h, стоит на линии base."""
    r = h * 0.12
    head_y = base - h + r
    neck, hip = head_y + r, base - h * 0.42
    w = 8 if h > 200 else 6
    return (f'<g id="{fid}"{extra}><circle cx="{x}" cy="{head_y:.1f}" r="{r:.1f}" fill="{CREAM}" />'
            f'<g fill="none" stroke="{CREAM}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M {x} {neck:.1f} V {hip:.1f} M {x} {neck + h * 0.1:.1f} L {x - h * 0.16:.1f} {hip - h * 0.02:.1f} '
            f'M {x} {neck + h * 0.1:.1f} L {x + h * 0.16:.1f} {hip - h * 0.02:.1f} M {x} {hip:.1f} L {x - h * 0.13:.1f} {base} '
            f'M {x} {hip:.1f} L {x + h * 0.13:.1f} {base}" /></g></g>')


family = f'''        <svg id="family" class="g" viewBox="0 0 700 360" style="left: 190px; top: 1262px; width: 700px; height: 360px; overflow: visible;">
          {figure("tim", 150, 330, 300)}
          <text x="150" y="20" text-anchor="middle" font-family="Manrope" font-weight="800" font-size="30" letter-spacing="2" fill="#F5B82E">ТИМОФЕЙ</text>
          <g id="house"><path d="M 300 330 V 220 L 380 160 L 460 220 V 330 Z" fill="rgba(245,184,46,0.25)" stroke="{CREAM}" stroke-width="7" stroke-linejoin="round" />
            <rect x="358" y="262" width="44" height="68" fill="{CREAM}" /></g>
          {figure("kid1", 330, 330, 150, ' opacity="0"')}
          {figure("kid2", 430, 330, 130, ' opacity="0"')}
          {figure("kid3", 520, 330, 110, ' opacity="0"')}
        </svg>'''

rows = [("tr1", "срок: 14 месяцев"), ("tr2", "долг ↓ на одну и ту же сумму"), ("tr3", "выплатит на 15% больше"),
        ("tr4", "процент r — ?")]
task = ('        <div id="task" class="g task" style="left: 90px; top: 1235px; width: 900px;">\n'
        '          <div class="task-head">задача №13 · кредит</div>\n'
        + "\n".join(f'          <div id="{rid}" class="task-row">{txt}</div>' for rid, txt in rows)
        + '\n        </div>')

H, base = 300.0, 380.0
bars = "".join(f'<rect id="bar{i}" x="{32 + 64 * i}" y="{base - H * (14 - i) / 14:.1f}" width="52" height="{H * (14 - i) / 14:.1f}" '
               f'rx="6" fill="{"#F5B82E" if i else "#F0352C"}" opacity="0" />' for i in range(14))
stairs = f'''        <svg id="stairs" class="g" viewBox="0 0 960 430" style="left: 60px; top: 1240px; width: 960px; height: 430px;">
          <rect x="0" y="0" width="960" height="430" rx="28" fill="rgba(12,12,14,0.86)" stroke="rgba(242,235,221,0.16)" stroke-width="2" />
          {bars}
          <path d="M 20 {base} H 940" stroke="rgba(242,235,221,0.4)" stroke-width="3" />
          <text id="st-s" x="58" y="{base - H - 14}" text-anchor="middle" font-family="JBMono" font-weight="700" font-size="34" fill="{CREAM}" opacity="0">S</text>
          <text id="st-n" x="480" y="418" text-anchor="middle" font-family="Manrope" font-weight="800" font-size="26" letter-spacing="3" fill="rgba(242,235,221,0.7)" opacity="0">14 МЕСЯЦЕВ</text>
          <g id="st-step" opacity="0">
            <path d="M 96 {base - H:.1f} H 140 V {base - H * 13 / 14:.1f}" fill="none" stroke="#F0352C" stroke-width="5" />
            <text x="152" y="{base - H + 18:.1f}" font-family="JBMono" font-weight="700" font-size="36" fill="#F0352C">−S/14</text>
          </g>
        </svg>'''

cells = [["S", "S·k", "x₁"], ["13/14·S", "13/14·S·k", "x₂"], ["12/14·S", "12/14·S·k", "x₃"], ["…", "…", "…"]]
tbl = ['        <div id="tbl" class="g" style="left: 40px; top: 1225px; width: 1000px; height: 392px; border-radius: 24px; '
       'background: rgba(12,12,14,0.88); border: 2px solid rgba(242,235,221,0.16); overflow: hidden;">',
       '          <svg viewBox="0 0 1000 392" style="position: absolute; left: 0; top: 0; width: 1000px; height: 392px;">'
       '<g stroke="rgba(242,235,221,0.22)" stroke-width="2"><path d="M 0 70 H 1000 M 0 150 H 1000 M 0 230 H 1000 M 0 310 H 1000 M 333 0 V 392 M 666 0 V 392" /></g>'
       '<rect id="col3" x="668" y="72" width="330" height="318" fill="rgba(59,209,111,0.16)" opacity="0" /></svg>']
for k, title in enumerate(["остаток", "долг с %", "выплата"]):
    tbl.append(f'          <div id="th{k + 1}" class="th" style="left: {333 * k}px;">{title}</div>')
for r, row in enumerate(cells):
    for c, txt in enumerate(row):
        tbl.append(f'          <div class="tc col{c + 1}" style="left: {333 * c}px; top: {70 + 80 * r}px;">{txt}</div>')
tbl.append("        </div>")
tbl = "\n".join(tbl)

behind = "\n".join([
    '        <div id="b-credit" class="g big red" style="top: 110px; font-size: 230px;">кредит</div>',
    '        <div id="b-diff-lead" class="g lead" style="top: 56px;">задача на</div>',
    '        <div id="b-diff" class="g big red" style="top: 100px; font-size: 88px; white-space: nowrap;">дифференцированный<br />платёж</div>',
    '        <div id="b-prog-lead" class="g lead" style="top: 56px;">выплаты — это</div>',
    '        <div id="b-prog" class="g big" style="top: 110px; font-size: 170px;">прогрессия</div>',
])
front = "\n".join([
    family,
    '        <div id="st-lost" class="g stamp" style="left: 280px; top: 260px; font-size: 96px; background: rgba(12,12,14,0.55);">проиграл</div>',
    '        <div id="st-babka" class="g sticker" style="left: 240px; top: 300px; font-size: 56px; white-space: nowrap;">не на новую бабушку</div>',
    '        <div id="p-ege" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 300px; background: none; border: none; font-size: 40px;">задача из ЕГЭ</div>',
    task,
    '        <div id="st-vahta" class="g sticker" style="left: 380px; top: 300px; font-size: 56px; white-space: nowrap;">вахтовик</div>',
    '        <div id="st-nv" class="g stamp" style="left: 300px; top: 260px; font-size: 96px; background: rgba(12,12,14,0.55);">не важно</div>',
    f'        <div id="p-beacon" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 300px; background: none; border: none; font-size: 40px;"><span id="beacon-dot" style="color: #F0352C;">●</span> главный маячок</div>',
    '        <div id="q-phrase" class="g paper" style="left: 110px; top: 1255px; width: 860px; text-align: center;"><div class="paper-text">«долг уменьшается на одну и ту же сумму»</div><div class="paper-sign" style="text-align: center;">значит — дифференцированный платёж</div></div>',
    stairs,
    tbl,
    '        <div id="st-tim" class="g sticker" style="left: 140px; top: 300px; font-size: 52px; white-space: nowrap;">разбор про Тима Кука — в профиле</div>',
    '        <div id="sum" class="g paper" style="left: 160px; top: 1255px; width: 760px; text-align: center;"><div class="note">сумма арифметической прогрессии</div>'
    '<div class="hand" style="color: #22303F; font-size: 96px;">S = (x₁ + x₁₄)/2 · 14</div><div class="note" style="color: #C7271F;">→ отсюда процент r</div></div>',
    '        <div id="censor" class="g censor"><span>Цензура</span><b>18+</b></div>',
    keyword_card("экономика", "напиши в комментариях", "или в личку — пришлю полный разбор"),
])

beats = f'''
      // ---------- хук: Тимофей проиграл бабушкину квартиру ----------
      tl.set("#family", {{ opacity: 1 }}, {t(2.28)});
      tl.fromTo("#tim", {{ x: -260, opacity: 0 }}, {{ x: 0, opacity: 1, duration: 0.4, ease: "power3.out" }}, {t(2.28)});
      tl.fromTo("#house", {{ scale: 0.3, opacity: 0, svgOrigin: "380 330" }}, {{ scale: 1, opacity: 1, duration: 0.3, ease: "back.out(2)" }}, {t(4.88)});
      tl.to("#house", {{ x: 420, y: -260, rotation: 50, opacity: 0, duration: 0.45, ease: "power2.in" }}, {t(6.02)});
      slam("#st-lost", {t(6.02)}, {{ fromScale: 2.2, rot: -6, blur: 10 }});
      leave("#st-lost", {t(6.90)}, {{ scale: 0.6, y: 0, rot: -18 }});
      tl.fromTo(["#kid1", "#kid2", "#kid3"], {{ opacity: 0, y: 40 }}, {{ opacity: 1, y: 0, duration: 0.2, ease: "back.out(2)", stagger: 0.12 }}, {t(7.60)});
      slam("#b-credit", {t(9.24)}, {{ fromScale: 1.5 }});
      flash({t(9.24)});
      leave("#b-credit", {t(10.40)}, {{ y: -60 }});
      enter("#st-babka", {t(12.20)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-babka", {t(12.95)}, {{ y: -30, rot: -10 }});
      leave("#family", {t(12.70)}, {{ y: 80 }});
      enter("#p-ege", {t(13.36)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#p-ege", {t(14.70)}, {{ y: -30 }});

      // ---------- условие ----------
      enter("#task", {t(14.94)}, {{ fromY: 140, fromScale: 0.92, rot: -2, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#tr1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(15.74)});
      enter("#st-vahta", {t(19.02)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-vahta", {t(20.00)}, {{ y: -30, rot: 10 }});
      tl.fromTo("#tr2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(21.20)});
      tl.fromTo("#tr3", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(24.88)});
      tl.fromTo("#tr4", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(28.68)});
      leave("#task", {t(30.50)}, {{ y: 80 }});
      slam("#st-nv", {t(33.48)}, {{ fromScale: 2.2, rot: 6, blur: 10 }});
      leave("#st-nv", {t(34.50)}, {{ scale: 0.6, y: 0, rot: 18 }});

      // ---------- маячок: «долг уменьшается на одну и ту же сумму» ----------
      enter("#p-beacon", {t(36.30)}, {{ fromScale: 0.85, dur: 0.25 }});
      tl.fromTo("#beacon-dot", {{ opacity: 1 }}, {{ opacity: 0.2, duration: 0.25, yoyo: true, repeat: 5, ease: "none" }}, {t(36.55)});
      leave("#p-beacon", {t(39.00)}, {{ y: -30 }});
      doc("#q-phrase", {t(39.06)}, {t(41.90)}, {{ fromRot: -5, rot: 1 }});
      enter("#b-diff-lead", {t(42.82)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-diff", {t(43.48)}, {{ fromScale: 1.4 }});
      flash({t(43.48)});
      leave(["#b-diff", "#b-diff-lead"], {t(44.80)}, {{ y: -60 }});

      // ---------- долг делим на 14 месяцев: лесенка ----------
      tl.set("#stairs", {{ opacity: 1 }}, {t(46.10)});
      tl.fromTo("#stairs", {{ y: 120, scale: 0.92 }}, {{ y: 0, scale: 1, duration: 0.35, ease: "power3.out" }}, {t(46.10)});
      tl.to("#bar0", {{ opacity: 1, duration: 0.15 }}, {t(46.10)});
      tl.to("#st-s", {{ opacity: 1, duration: 0.15 }}, {t(46.20)});
      tl.fromTo("#stairs rect[id^=bar]", {{ scaleY: 0, svgOrigin: "480 {base}" }}, {{ scaleY: 1, opacity: 1, duration: 0.18, ease: "power2.out", stagger: 0.05, immediateRender: false }}, {t(49.24)});
      tl.to("#st-n", {{ opacity: 1, duration: 0.2 }}, {t(49.54)});
      tl.to("#st-step", {{ opacity: 1, duration: 0.2 }}, {t(52.40)});
      leave("#stairs", {t(53.70)}, {{ y: 80 }});

      // ---------- табличка: остаток, долг с процентом, выплаты ----------
      enter("#tbl", {t(58.08)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.to("#th1", {{ opacity: 1, duration: 0.15 }}, {t(58.50)});
      tl.to("#tbl .col1", {{ opacity: 1, duration: 0.12, stagger: 0.15 }}, {t(58.88)});
      tl.to("#th2", {{ opacity: 1, duration: 0.15 }}, {t(61.32)});
      tl.to("#tbl .col2", {{ opacity: 1, duration: 0.12, stagger: 0.15 }}, {t(61.66)});
      enter("#st-tim", {t(65.06)}, {{ fromScale: 0.6, rot: -3 }});
      leave("#st-tim", {t(66.30)}, {{ y: -30, rot: -8 }});
      tl.to("#th3", {{ opacity: 1, duration: 0.15 }}, {t(67.58)});
      tl.to("#tbl .col3", {{ opacity: 1, duration: 0.12, stagger: 0.15 }}, {t(67.98)});
      tl.to("#col3", {{ opacity: 1, duration: 0.25 }}, {t(69.42)});
      leave("#tbl", {t(71.00)}, {{ y: 80 }});

      // ---------- арифметическая прогрессия и её сумма ----------
      enter("#b-prog-lead", {t(69.10)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-prog", {t(70.10)}, {{ fromScale: 1.5 }});
      leave(["#b-prog", "#b-prog-lead"], {t(71.25)}, {{ y: -60 }});
      doc("#sum", {t(73.04)}, {t(78.40)}, {{ fromRot: 5, rot: -1 }});

      // ---------- «пип» и кодовое слово ----------
      slam("#censor", {t(82.28)}, {{ fromScale: 1.5, rot: -3 }});
      leave("#censor", {t(83.20)}, {{ scale: 0.6, y: 0, rot: 8 }});
{keyword_beats(t(83.44), t(85.54), t(86.36), len("экономика"), t_cta_out=t(83.30))}
'''
sounds = [
    audio("tim", "whoosh-short", t(2.26), 0.26), audio("house", "pop", t(4.86), 0.30),
    audio("lost", "impact-bass-1", t(6.00), 0.36), audio("kids", "pop", t(7.58), 0.28),
    audio("credit", "impact-bass-1", t(9.22), 0.40), audio("babka", "pop", t(12.18), 0.26),
    audio("ege", "pop", t(13.34), 0.26), audio("task", "whoosh", t(14.92), 0.24),
    *[audio(f"tr{k}", "click", t(x) - 0.02, 0.32) for k, x in enumerate([15.74, 21.20, 24.88, 28.68])],
    audio("vahta", "pop", t(19.00), 0.26), audio("nv", "impact-bass-1", t(33.46), 0.28),
    audio("beacon", "notification", t(36.28), 0.20), audio("phrase", "whoosh", t(39.04), 0.22),
    audio("diff", "impact-bass-1", t(43.46), 0.36), audio("stairs", "whoosh-short", t(46.08), 0.24),
    audio("bars", "click-soft", t(49.22), 0.36), audio("step", "ping", t(52.38), 0.28),
    audio("tbl", "whoosh", t(58.06), 0.24), audio("col1", "click-soft", t(58.86), 0.34),
    audio("col2", "click-soft", t(61.64), 0.34), audio("timcook", "pop", t(65.04), 0.26),
    audio("col3", "click-soft", t(67.96), 0.34), audio("prog", "impact-bass-1", t(70.08), 0.34),
    audio("sum", "whoosh", t(73.02), 0.22), audio("censor", "glitch-3", t(82.28), 0.22, duration=0.9, fade_out=0.3),
    audio("kw", "whoosh-short", t(83.42), 0.24), audio("type", "typing", t(85.52), 0.30, duration=0.6, fade_out=0.2),
    audio("note", "notification", t(86.34), 0.22),
]
fg = [(t(9.14), t(10.75)), (t(42.72), t(45.15)), (t(69.00), t(71.60))]
page = build_page("Тимофей и дифференцированный платёж", DUR, behind, front, beats, sounds, fg, cta_at=t(79.28),
                  extra_css=css, cta_small="разбираю экономику легко — переходи")
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

director = {
    "_note": "Дифференцированный платёж. Время по дублю; раскладка — work/IMG_3320/page.py. Вырез оговорки 54.06–57.92.",
    "punches": [[t(6.02), t(6.90), 1.18, 0.10], [t(9.24), t(10.10), 1.16, 0.10], [t(43.48), t(44.40), 1.16, 0.10],
                [t(57.92), t(59.40), 1.20, 0.0, 0.6], [t(82.28), t(83.00), 1.22, 0.05]],
    "text_fixes": tk.fixes({131: "1/14", 132: "", 204: "***", 227: "ЕГЭ"}),
    "keep_case": ["Тимофей", "Тимофея", "ЕГЭ"],
    "accent_words": ["проиграл", "дифференцированный", "прогрессию", "прогрессии"],
    "hide_captions": [[t(9.20), t(10.05)], [t(43.40), t(44.70)], [t(70.05), t(70.95)], [t(79.20), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
