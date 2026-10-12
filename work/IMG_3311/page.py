"""Страница графики IMG_3311: почему алгебра называется алгеброй.

Время ударов — по исходнику, на шкалу дубля переводит Take.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, card  # noqa: E402

STEM = "IMG_3311"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
GREEN = "#3BD16F"

css = '''      .eqp { height: 170px; border-radius: 28px; background: rgba(12,12,14,0.86); border: 2px solid rgba(242,235,221,0.16); }
      .eqp .m { position: absolute; top: 36px; font-family: "JBMono"; font-weight: 700; font-size: 84px; color: var(--cream);
                white-space: nowrap; line-height: 1.1; }
      /* системные шрифты macOS: через @font-face с local(), иначе lint HyperFrames (--strict) не пустит в рендер */
      @font-face { font-family: "Geeza Pro"; src: local("Geeza Pro Bold"), local("GeezaPro-Bold"); font-weight: 700; }
      .arab { font-family: "Geeza Pro", serif; font-weight: 700; text-transform: none; }
      .ico { width: 290px; height: 330px; border-radius: 26px; background: rgba(12,12,14,0.86); border: 2px solid rgba(242,235,221,0.16); }
'''


def nb(nid: str, left: int, title: str, sub: str, color: str) -> str:
    return (f'        <div id="{nid}" class="g notebook" style="left: {left}px; top: 1262px; width: 400px; text-align: center;">\n'
            f'          <div style="font-family: \'Oswald\'; font-weight: 700; font-size: 66px; text-transform: uppercase; color: {color};">{title}</div>\n'
            f'          <div class="note" style="margin-top: 6px;">{sub}</div>\n        </div>')


def icon(iid: str, left: int, svg: str, label: str) -> str:
    return (f'        <div id="{iid}" class="g ico" style="left: {left}px; top: 1262px;">\n'
            f'          <svg viewBox="0 0 290 250" style="position: absolute; left: 0; top: 10px; width: 290px; height: 250px;">{svg}</svg>\n'
            f'          <div class="label" style="position: absolute; left: 0; top: 270px; width: 290px; font-size: 26px; letter-spacing: 0.08em;">{label}</div>\n'
            f'        </div>')


pie = ('<circle cx="145" cy="125" r="95" fill="#F5B82E" stroke="#F2EBDD" stroke-width="5" />'
       '<path d="M 145 125 L 145 30 A 95 95 0 0 1 227.3 172.5 Z" fill="#F0352C" stroke="#F2EBDD" stroke-width="5" />'
       '<path d="M 145 125 L 227.3 172.5 A 95 95 0 0 1 62.7 172.5 Z" fill="#2F6FC6" stroke="#F2EBDD" stroke-width="5" />')
land = ('<path d="M 40 190 L 70 60 L 240 40 L 255 200 Z" fill="rgba(59,209,111,0.30)" stroke="#3BD16F" stroke-width="6" stroke-linejoin="round" />'
        '<path d="M 40 222 H 255 M 40 210 V 234 M 255 210 V 234" stroke="#F2EBDD" stroke-width="4" fill="none" />'
        '<text x="148" y="246" text-anchor="middle" font-family="JBMono" font-weight="700" font-size="26" fill="#F2EBDD">40 м</text>')
scales = ('<path d="M 145 40 V 210 M 95 210 H 195 M 55 75 H 235" stroke="#F2EBDD" stroke-width="7" stroke-linecap="round" fill="none" />'
          '<path d="M 55 75 L 25 150 H 85 Z M 235 75 L 205 150 H 265 Z" stroke="#F2EBDD" stroke-width="5" fill="rgba(245,184,46,0.35)" stroke-linejoin="round" />'
          '<circle cx="145" cy="40" r="12" fill="#F5B82E" />')

behind = "\n".join([
    '        <div id="w-alg" class="g big red" style="top: 120px; font-size: 220px;">алгебра</div>',
    '        <div id="q" class="g big" style="top: 90px; font-size: 300px;">?</div>',
    '        <div id="ar-jabr" class="g big arab" style="top: 90px; font-size: 230px;">الجبر</div>',
    '        <div id="ld-jabr" class="g lead" style="top: 56px;">аль-джабр — «восстановление»</div>',
    '        <div id="ar-muq" class="g big arab" style="top: 90px; font-size: 200px;">المقابلة</div>',
    '        <div id="ld-muq" class="g lead" style="top: 56px;">аль-мукабала — «противопоставление»</div>',
    '        <div id="w-alg2" class="g big red" style="top: 110px; font-size: 230px;">алгебра</div>',
])
front = "\n".join([
    nb("nb-math", 110, "Математика", "5–6 класс", "#22303F"),
    nb("nb-alg", 570, "Алгебра", "7 класс", "#C7271F"),
    '        <div id="st-harder" class="g sticker" style="left: 250px; top: 300px; font-size: 56px; white-space: nowrap;">название усложнили?</div>',
    '        <div id="p-bag" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 300px; background: none; border: none; font-size: 40px;">Багдад, IX век</div>',
    card("card-kh", "khwarizmi_stamp.jpg", "аль-Хорезми", "марка СССР, 1983", "right"),
    '        <div id="title" class="g paper" style="left: 90px; top: 1250px; width: 900px; text-align: center;">'
    '<div class="arab" style="font-size: 50px; color: #2A2219; line-height: 1.3;">الكتاب المختصر في حساب الجبر والمقابلة</div>'
    '<div class="paper-text" style="margin-top: 8px; font-size: 44px;">«Краткая книга об исчислении <b id="t-jabr">аль-джабра</b> и <b id="t-muq">аль-мукабалы</b>»</div></div>',
    # аль-джабр: член с минусом переходит через «=» и меняет знак
    '        <div id="eq1" class="g eqp" style="left: 90px; top: 1262px; width: 900px;">',
    '          <div id="e1-x" class="m" style="left: 150px;">x</div>',
    '          <div id="e1-m" class="m" style="left: 260px; color: var(--red);">− 5</div>',
    '          <div class="m" style="left: 470px;">=</div>',
    '          <div class="m" style="left: 590px;">3</div>',
    f'          <div id="e1-p" class="m" style="left: 700px; color: {GREEN}; opacity: 0;">+ 5</div>',
    '        </div>',
    # аль-мукабала: одинаковое с обеих сторон сокращается
    '        <div id="eq2" class="g eqp" style="left: 90px; top: 1262px; width: 900px;">',
    '          <div class="m" style="left: 150px;">x</div>',
    '          <div id="e2-a" class="m" style="left: 260px; color: #F5B82E;">+ 2</div>',
    '          <div class="m" style="left: 470px;">=</div>',
    '          <div class="m" style="left: 590px;">7</div>',
    '          <div id="e2-b" class="m" style="left: 700px; color: #F5B82E;">+ 2</div>',
    '          <svg viewBox="0 0 900 170" style="position: absolute; left: 0; top: 0; width: 900px; height: 170px;">'
    '<path id="e2-xa" d="M 250 125 L 410 55" stroke="#F0352C" stroke-width="10" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />'
    '<path id="e2-xb" d="M 690 125 L 850 55" stroke="#F0352C" stroke-width="10" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" /></svg>',
    '        </div>',
    '        <div id="p-nomath" class="g pill" style="left: 70px; top: 300px; font-size: 36px;"><s>про математику</s></div>',
    f'        <div id="p-prac" class="g pill" style="left: 560px; top: 300px; font-size: 36px;">про практику <span style="color: {GREEN};">✓</span></div>',
    icon("ic-inh", 50, pie, "наследство"),
    icon("ic-land", 395, land, "земля"),
    icon("ic-trade", 740, scales, "торговля"),
    '        <div id="st-lab" class="g sticker" style="left: 160px; top: 300px; font-size: 56px; white-space: nowrap;">капиталистическая лабуда</div>',
    '        <div id="latin" class="g paper" style="left: 90px; top: 1262px; width: 900px; text-align: center;">'
    '<div class="paper-text" style="font-size: 64px; font-style: italic;">Liber <span id="la-alg" style="display: inline-block;">algebrae</span> '
    '<span id="la-rest" style="display: inline-block;">et almucabala</span></div>'
    '<div class="paper-sign" style="text-align: center;">латинский перевод, XII век</div></div>',
])

beats = f'''
      // ---------- хук: в 6-м классе математика, в 7-м уже алгебра ----------
      enter("#nb-math", {t(10.04)}, {{ fromX: -240, fromScale: 0.9, rot: -3 }});
      enter("#nb-alg", {t(11.18)}, {{ fromX: 240, fromScale: 0.9, rot: 3 }});
      slam("#w-alg", {t(11.84)}, {{ fromScale: 1.5 }});
      flash({t(11.84)});
      leave("#w-alg", {t(12.60)}, {{ y: -60 }});
      leave(["#nb-math", "#nb-alg"], {t(12.70)}, {{ y: 80 }});
      slam("#q", {t(13.40)}, {{ fromScale: 1.6 }});
      leave("#q", {t(14.20)}, {{ y: -60 }});
      enter("#st-harder", {t(15.34)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-harder", {t(16.30)}, {{ y: -30, rot: -10 }});

      // ---------- книжка из Багдада, аль-Хорезми ----------
      enter("#p-bag", {t(19.58)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#p-bag", {t(21.20)}, {{ y: -30 }});
      card("#card-kh", {t(21.42)}, {t(28.00)}, "right");
      doc("#title", {t(24.16)}, {t(28.05)}, {{ fromRot: -5, rot: 1 }});
      tl.to("#t-jabr", {{ color: "#C7271F", duration: 0.15 }}, {t(26.24)});
      tl.to("#t-muq", {{ color: "#C7271F", duration: 0.15 }}, {t(27.18)});

      // ---------- аль-джабр: перенос с противоположным знаком ----------
      slam("#ar-jabr", {t(28.22)}, {{ fromScale: 1.5 }});
      enter("#ld-jabr", {t(29.38)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave(["#ar-jabr", "#ld-jabr"], {t(30.40)}, {{ y: -60 }});
      enter("#eq1", {t(31.72)}, {{ fromY: 120, fromScale: 0.92, dur: 0.35, ease: "power3.out" }});
      tl.to("#e1-m", {{ keyframes: [{{ x: 220, y: -70, duration: 0.3, ease: "power2.out" }}, {{ x: 440, y: 0, duration: 0.3, ease: "power2.in" }}] }}, {t(32.66)});
      tl.to("#e1-x", {{ x: 110, duration: 0.4, ease: "power2.inOut" }}, {t(32.80)});
      tl.to("#e1-m", {{ opacity: 0, duration: 0.1 }}, {t(34.54)});
      tl.fromTo("#e1-p", {{ opacity: 0, scale: 1.4 }}, {{ opacity: 1, scale: 1, duration: 0.18, ease: "power3.out" }}, {t(34.54)});
      leave("#eq1", {t(35.60)}, {{ y: 80 }});

      // ---------- аль-мукабала: сократить одинаковое с обеих сторон ----------
      slam("#ar-muq", {t(36.42)}, {{ fromScale: 1.5 }});
      enter("#ld-muq", {t(37.36)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave(["#ar-muq", "#ld-muq"], {t(38.60)}, {{ y: -60 }});
      enter("#eq2", {t(38.68)}, {{ fromY: 120, fromScale: 0.92, dur: 0.35, ease: "power3.out" }});
      draw("#e2-xa", {t(40.02)}, 0.2);
      draw("#e2-xb", {t(40.30)}, 0.2);
      tl.to(["#e2-a", "#e2-b", "#e2-xa", "#e2-xb"], {{ opacity: 0, duration: 0.2 }}, {t(41.34)});
      leave("#eq2", {t(41.95)}, {{ y: 80 }});

      // ---------- книга про практику: наследство, земля, торговля ----------
      enter("#p-nomath", {t(44.14)}, {{ fromX: -220, fromScale: 0.9, rot: -3 }});
      enter("#p-prac", {t(45.06)}, {{ fromX: 220, fromScale: 0.9, rot: 3 }});
      leave(["#p-nomath", "#p-prac"], {t(46.00)}, {{ y: -30 }});
      enter("#ic-inh", {t(46.26)}, {{ fromY: 120, fromScale: 0.8, rot: -3 }});
      enter("#ic-land", {t(47.44)}, {{ fromY: 120, fromScale: 0.8 }});
      enter("#ic-trade", {t(48.42)}, {{ fromY: 120, fromScale: 0.8, rot: 3 }});
      leave(["#ic-inh", "#ic-land", "#ic-trade"], {t(49.40)}, {{ y: 80 }});
      enter("#st-lab", {t(49.94)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-lab", {t(51.60)}, {{ y: -30, rot: -10 }});

      // ---------- латинский перевод: осталось первое слово ----------
      doc("#latin", {t(52.86)}, {t(55.90)}, {{ fromRot: 5, rot: -1 }});
      tl.to("#la-rest", {{ opacity: 0.25, filter: BLUR(2), duration: 0.25 }}, {t(54.70)});
      tl.to("#la-alg", {{ color: "#C7271F", y: -8, duration: 0.18, ease: "power2.out" }}, {t(54.96)});
      tl.to("#la-alg", {{ y: 0, duration: 0.25, ease: "bounce.out" }}, {t(55.16)});
      slam("#w-alg2", {t(55.98)}, {{ fromScale: 1.6 }});
      flash({t(55.98)});
      leave("#w-alg2", {t(56.85)}, {{ y: -60 }});
'''
sounds = [
    audio("math", "pop", t(10.02), 0.30), audio("alg", "pop", t(11.16), 0.30),
    audio("walg", "impact-bass-1", t(11.82), 0.40), audio("q", "pop", t(13.38), 0.30),
    audio("harder", "pop", t(15.32), 0.26), audio("bag", "whoosh", t(19.56), 0.24),
    audio("kh", "whoosh", t(21.40), 0.28), audio("title", "whoosh", t(24.14), 0.22),
    audio("jabr", "impact-bass-1", t(28.20), 0.34), audio("eq1", "whoosh", t(31.70), 0.24),
    audio("move", "whoosh", t(32.64), 0.26), audio("sign", "ping", t(34.52), 0.30),
    audio("muq", "impact-bass-1", t(36.40), 0.32), audio("eq2", "whoosh", t(38.66), 0.24),
    audio("xa", "click", t(40.00), 0.36), audio("xb", "click", t(40.28), 0.36),
    audio("nomath", "error", t(44.12), 0.18), audio("prac", "pop", t(45.04), 0.30),
    audio("inh", "click", t(46.24), 0.34), audio("land", "click", t(47.42), 0.34), audio("trade", "click", t(48.40), 0.34),
    audio("lab", "pop", t(49.92), 0.26), audio("latin", "whoosh", t(52.84), 0.22), audio("first", "ping", t(54.94), 0.28),
    audio("walg2", "impact-bass-1", t(55.96), 0.42),
]
fg = [(t(11.74), t(12.95)), (t(13.30), t(14.55)), (t(28.12), t(30.75)), (t(36.32), t(38.95)), (t(55.88), t(57.20))]
page = build_page("Почему алгебра — алгебра", DUR, behind, front, beats, sounds, fg, cta_at=t(59.34),
                  extra_css=css, cta_small="ЕГЭ на 80+ — объясню мега доходчиво")
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

director = {
    "_note": "Алгебра. Время по дублю; раскладка — work/IMG_3311/page.py.",
    "punches": [[t(11.84), t(12.60), 1.18, 0.10], [t(28.22), t(29.20), 1.16, 0.10], [t(55.98), t(56.90), 1.22, 0.10]],
    "text_fixes": tk.fixes({21: "чёрт", 46: "аль-Хорезми", 47: "", 55: "аль-джабр", 56: "", 58: "аль-мукабала", 59: "",
                            60: "аль-джабр", 61: "", 81: "аль-мукабала", 82: "", 148: "+"}),
    "keep_case": ["аль-Хорезми", "Багдада", "ЕГЭ"],
    "accent_words": ["алгебра", "восстановление", "противопоставление"],
    "hide_captions": [[t(11.80), t(12.55)], [t(55.95), t(56.80)], [t(59.25), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
