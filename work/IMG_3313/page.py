"""Страница графики IMG_3313: почему корень называется корнем.

Время ударов — по исходнику, на шкалу дубля (с вырезом сбивки 36.16–38.24) переводит Take.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, card  # noqa: E402

STEM = "IMG_3313"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
AMBER = "#F5B82E"
GREEN = "#3BD16F"

css = '''      /* системные шрифты macOS: через @font-face с local(), иначе lint HyperFrames (--strict) не пустит в рендер */
      @font-face { font-family: "Geeza Pro"; src: local("Geeza Pro Bold"), local("GeezaPro-Bold"); font-weight: 700; }
      @font-face { font-family: "Kohinoor Devanagari"; src: local("Kohinoor Devanagari Bold"), local("KohinoorDevanagari-Bold"); font-weight: 700; }
      .arab { font-family: "Geeza Pro", serif; font-weight: 700; text-transform: none; }
      .deva { font-family: "Kohinoor Devanagari", sans-serif; font-weight: 700; text-transform: none; }
      .chain { position: absolute; top: 120px; height: 200px; text-align: center; color: var(--cream); line-height: 1;
               text-shadow: 0 10px 36px rgba(0,0,0,0.45); }
'''

sprout = '''        <svg id="sprout" class="g" viewBox="0 0 400 480" style="left: 340px; top: 1240px; width: 400px; height: 480px; overflow: visible;">
          <path d="M 20 250 H 380" stroke="#8C6A43" stroke-width="10" stroke-linecap="round" />
          <path id="sp-stem" d="M 200 250 C 196 200 206 150 200 90" fill="none" stroke="#3BD16F" stroke-width="12" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
          <path id="sp-leaf1" d="M 200 150 C 150 140 120 110 112 70 C 160 76 190 104 200 150 Z" fill="#3BD16F" opacity="0" />
          <path id="sp-leaf2" d="M 201 120 C 250 104 276 70 280 34 C 236 44 206 76 201 120 Z" fill="#2E9E57" opacity="0" />
          <g fill="none" stroke="#E8D3B0" stroke-width="7" stroke-linecap="round">
            <path class="sp-root" d="M 200 250 C 198 300 190 350 170 420" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
            <path class="sp-root" d="M 199 290 C 170 310 140 330 110 380" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
            <path class="sp-root" d="M 199 300 C 230 330 260 350 290 400" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
            <path class="sp-root" d="M 186 370 C 160 390 150 410 140 450" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
          </g>
        </svg>'''

cells = "".join(f'<rect class="cell" x="{120 + 120 * i + 4}" y="{60 + 120 * j + 4}" width="112" height="112" rx="10" '
                f'fill="rgba(245,184,46,0.85)" opacity="0" />' for j in range(3) for i in range(3))
square = f'''        <svg id="sq" class="g" viewBox="0 0 600 560" style="left: 240px; top: 1225px; width: 600px; height: 560px; overflow: visible;">
          <g id="sq-grid">
            {cells}
            <path id="sq-out" d="M 120 60 H 480 V 420 H 120 Z" fill="none" stroke="#F2EBDD" stroke-width="8" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
            <text id="sq-9" x="300" y="268" text-anchor="middle" font-family="JBMono" font-weight="700" font-size="150" fill="#1A1612" opacity="0">9</text>
          </g>
          <path id="sq-side" d="M 120 420 H 480" stroke="#F0352C" stroke-width="12" stroke-linecap="round" opacity="0" />
          <g font-family="JBMono" font-weight="700" font-size="56" fill="#F2EBDD" text-anchor="middle">
            <text id="sq-3b" x="300" y="482" opacity="0">3</text>
            <text id="sq-3l" x="78" y="258" opacity="0">3</text>
          </g>
          <g fill="none" stroke="#E8D3B0" stroke-width="7" stroke-linecap="round">
            <path class="sq-root" d="M 200 420 C 194 460 180 500 160 548" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
            <path class="sq-root" d="M 300 420 C 304 470 296 510 306 556" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
            <path class="sq-root" d="M 400 420 C 410 460 430 500 452 546" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
          </g>
        </svg>'''

r2root = f'''        <div id="r2r" class="g" style="left: 140px; top: 1240px; width: 800px; height: 330px; border-radius: 28px; background: rgba(12,12,14,0.86); border: 2px solid rgba(242,235,221,0.16);">
          <div id="rr-r" style="position: absolute; left: 90px; top: 0; width: 200px; text-align: center; font-family: 'Cormorant'; font-style: italic; font-weight: 700; font-size: 230px; color: var(--cream); line-height: 1.1; opacity: 0;">r</div>
          <div id="rr-arrow" style="position: absolute; left: 320px; top: 70px; width: 160px; text-align: center; font-family: 'JBMono'; font-weight: 700; font-size: 100px; color: rgba(242,235,221,0.6); opacity: 0;">→</div>
          <div id="rr-root" style="position: absolute; left: 500px; top: 20px; width: 220px; text-align: center; font-family: 'JBMono'; font-weight: 700; font-size: 200px; color: var(--red); line-height: 1.1; opacity: 0;">√</div>
          <div id="rr-word" style="position: absolute; left: 0; top: 250px; width: 800px; text-align: center; font-family: 'Cormorant'; font-style: italic; font-weight: 700; font-size: 60px; color: var(--cream); opacity: 0;"><span style="color: var(--red);">r</span>adix — «корень»</div>
        </div>'''

radical = f'''        <svg id="rad" class="g" viewBox="0 0 760 300" style="left: 160px; top: 1250px; width: 760px; height: 300px; overflow: visible;">
          <rect x="0" y="0" width="760" height="300" rx="28" fill="rgba(12,12,14,0.86)" stroke="rgba(242,235,221,0.16)" stroke-width="2" />
          <path id="rad-v" d="M 60 170 L 100 150 L 160 250 L 230 50" fill="none" stroke="#F2EBDD" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
          <path id="rad-bar" d="M 230 50 H 700" fill="none" stroke="#F0352C" stroke-width="12" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
          <text id="rad-x" x="465" y="205" text-anchor="middle" font-family="JBMono" font-weight="700" font-size="110" fill="#F2EBDD" opacity="0">x + 1</text>
        </svg>'''

behind = "\n".join([
    '        <svg id="b-root" class="g" viewBox="0 0 640 300" style="left: 220px; top: 50px; width: 640px; height: 300px; overflow: visible;">'
    '<path id="b-root-p" d="M 40 170 L 110 135 L 200 280 L 320 30 H 610" fill="none" stroke="#F2EBDD" stroke-width="26" stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" /></svg>',
    '        <div id="b-koren" class="g big red" style="top: 110px; font-size: 220px;">корень</div>',
    '        <div id="ch-1" class="g chain deva" style="left: 20px; width: 320px; font-size: 130px;">मूल</div>',
    '        <div id="ch-2" class="g chain arab" style="left: 380px; width: 320px; font-size: 130px;">جذر</div>',
    '        <div id="ch-3" class="g chain" style="left: 740px; width: 320px; font-size: 120px; font-family: \'Cormorant\'; font-style: italic; font-weight: 700;">radix</div>',
    '        <div id="ch-lead" class="g lead" style="top: 56px;">санскрит · арабский · латынь</div>',
    '        <div id="b-xvi" class="g big" style="top: 110px; font-size: 220px;">XVI век</div>',
    '        <div id="b-xvi-lead" class="g lead" style="top: 56px;">знак √ появился в</div>',
    '        <div id="b-rad" class="g big red" style="top: 70px; font-size: 190px;">радикал</div>',
])
front = "\n".join([
    sprout,
    '        <div id="st-smoke" class="g sticker" style="left: 320px; top: 300px; font-size: 56px; white-space: nowrap;">что-то курили</div>',
    square,
    r2root,
    radical,
    card("card-desc", "descartes.jpg", "Рене Декарт", "добавил черту, 1637", "left"),
    '        <div id="st-wall" class="g sticker" style="left: 400px; top: 330px; font-size: 52px; white-space: nowrap;">сосед по стене в кабинете</div>',
    '        <div id="st-msk" class="g sticker" style="left: 240px; top: 300px; font-size: 58px; white-space: nowrap;">радикальные москвичи</div>',
])

beats = f'''
      // ---------- хук: почему корень — корень, при чём тут растение ----------
      tl.set("#b-root", {{ opacity: 1 }}, {t(2.12)});
      draw("#b-root-p", {t(2.12)}, 0.45);
      flash({t(2.12)});
      leave("#b-root", {t(3.30)}, {{ y: -60 }});
      tl.set("#sprout", {{ opacity: 1 }}, {t(4.56)});
      draw("#sp-stem", {t(4.56)}, 0.5);
      tl.fromTo(["#sp-leaf1", "#sp-leaf2"], {{ opacity: 0, scale: 0.3, svgOrigin: "200 140" }}, {{ opacity: 1, scale: 1, duration: 0.3, ease: "back.out(2)", stagger: 0.12 }}, {t(5.10)});
      tl.fromTo("#sprout .sp-root", {{ strokeDashoffset: 1 }}, {{ strokeDashoffset: 0, duration: 0.5, ease: "power1.inOut", stagger: 0.08 }}, {t(5.62)});
      leave("#sprout", {t(6.40)}, {{ y: 80 }});
      enter("#st-smoke", {t(9.80)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-smoke", {t(10.50)}, {{ y: -30, rot: -10 }});

      // ---------- квадрат — настоящая фигура: 9 = 3 × 3 ----------
      tl.set("#sq", {{ opacity: 1 }}, {t(10.84)});
      draw("#sq-out", {t(10.84)}, 0.5);
      tl.to("#sq .cell", {{ opacity: 1, duration: 0.1, stagger: 0.07 }}, {t(14.36)});
      tl.to("#sq-9", {{ opacity: 1, duration: 0.15 }}, {t(15.20)});
      tl.to("#sq-3b", {{ opacity: 1, duration: 0.12 }}, {t(16.36)});
      tl.to("#sq-3l", {{ opacity: 1, duration: 0.12 }}, {t(16.98)});
      tl.to("#sq-side", {{ opacity: 1, duration: 0.15 }}, {t(17.60)});
      // квадрат «растёт» из своей стороны
      tl.to("#sq-grid", {{ scaleY: 0.04, svgOrigin: "300 420", duration: 0.3, ease: "power2.in" }}, {t(19.42)});
      tl.to("#sq-grid", {{ scaleY: 1, svgOrigin: "300 420", duration: 0.6, ease: "back.out(1.4)" }}, {t(20.02)});
      tl.fromTo("#sq .sq-root", {{ strokeDashoffset: 1 }}, {{ strokeDashoffset: 0, duration: 0.5, ease: "power1.inOut", stagger: 0.1 }}, {t(21.36)});
      slam("#b-koren", {t(22.88)}, {{ fromScale: 1.5 }});
      flash({t(22.88)});
      leave("#b-koren", {t(23.50)}, {{ y: -60 }});
      leave("#sq", {t(23.60)}, {{ y: 80 }});

      // ---------- мула → джизр → radix ----------
      enter("#ch-lead", {t(24.68)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#ch-1", {t(25.12)}, {{ fromScale: 1.4 }});
      slam("#ch-2", {t(27.86)}, {{ fromScale: 1.4 }});
      slam("#ch-3", {t(29.38)}, {{ fromScale: 1.4 }});
      leave(["#ch-1", "#ch-2", "#ch-3", "#ch-lead"], {t(30.30)}, {{ y: -60 }});

      // ---------- знак — с XVI века, это маленькая r от radix ----------
      enter("#b-xvi-lead", {t(30.60)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-xvi", {t(31.34)}, {{ fromScale: 1.5 }});
      leave(["#b-xvi", "#b-xvi-lead"], {t(32.40)}, {{ y: -60 }});
      enter("#r2r", {t(32.90)}, {{ fromY: 120, fromScale: 0.92, dur: 0.35, ease: "power3.out" }});
      tl.fromTo("#rr-r", {{ opacity: 0, scale: 1.4 }}, {{ opacity: 1, scale: 1, duration: 0.18, ease: "power3.out" }}, {t(33.78)});
      tl.to("#rr-arrow", {{ opacity: 1, duration: 0.15 }}, {t(34.04)});
      tl.fromTo("#rr-root", {{ opacity: 0, scale: 1.4 }}, {{ opacity: 1, scale: 1, duration: 0.18, ease: "power3.out" }}, {t(34.20)});
      tl.to("#rr-word", {{ opacity: 1, duration: 0.2 }}, {t(35.40)});
      leave("#r2r", {t(35.95)}, {{ y: 80 }});

      // ---------- черту придумал Декарт: видно, из чего извлекается ----------
      tl.set("#rad", {{ opacity: 1 }}, {t(38.40)});
      tl.fromTo("#rad", {{ y: 120, scale: 0.92 }}, {{ y: 0, scale: 1, duration: 0.35, ease: "power3.out" }}, {t(38.40)});
      draw("#rad-v", {t(38.56)}, 0.35);
      draw("#rad-bar", {t(39.14)}, 0.35);
      card("#card-desc", {t(39.98)}, {t(45.40)}, "left");
      enter("#st-wall", {t(40.92)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-wall", {t(42.90)}, {{ y: -30, rot: 10 }});
      tl.fromTo("#rad-x", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.25, ease: "power2.out" }}, {t(43.30)});
      tl.to("#rad-x", {{ fill: "#F5B82E", duration: 0.2 }}, {t(44.96)});
      leave("#rad", {t(46.00)}, {{ y: 80 }});

      // ---------- радикал — от того же radix ----------
      slam("#b-rad", {t(48.10)}, {{ fromScale: 1.5 }});
      leave("#b-rad", {t(49.40)}, {{ y: -60 }});
      enter("#st-msk", {t(52.08)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-msk", {t(53.60)}, {{ y: -30, rot: -10 }});
'''
sounds = [
    audio("root", "impact-bass-1", t(2.10), 0.42), audio("sprout", "sparkle", t(4.54), 0.26),
    audio("roots", "whoosh", t(5.60), 0.22), audio("smoke", "pop", t(9.78), 0.26),
    audio("sq", "whoosh", t(10.82), 0.24), audio("cells", "click", t(14.34), 0.36),
    audio("three", "click", t(16.34), 0.32), audio("side", "pop", t(17.58), 0.28),
    audio("grow", "whoosh", t(20.00), 0.26), audio("sqroots", "whoosh", t(21.34), 0.22),
    audio("koren", "impact-bass-1", t(22.86), 0.40),
    audio("ch1", "click", t(25.10), 0.34), audio("ch2", "click", t(27.84), 0.34), audio("ch3", "click", t(29.36), 0.34),
    audio("xvi", "impact-bass-1", t(31.32), 0.32), audio("r", "pop", t(33.76), 0.28), audio("rroot", "ping", t(34.18), 0.28),
    audio("radv", "whoosh", t(38.54), 0.24), audio("bar", "click", t(39.12), 0.36),
    audio("desc", "whoosh", t(39.96), 0.28), audio("wall", "pop", t(40.90), 0.26),
    audio("x1", "pop", t(43.28), 0.28), audio("brad", "impact-bass-1", t(48.08), 0.36), audio("msk", "pop", t(52.06), 0.28),
]
fg = [(t(2.02), t(3.65)), (t(22.78), t(23.85)), (t(24.58), t(30.65)), (t(30.50), t(32.75)), (t(48.00), t(49.75))]
page = build_page("Почему корень — это корень", DUR, behind, front, beats, sounds, fg, cta_at=t(54.02),
                  extra_css=css, cta_small="радикально подготовлю к ЕГЭ")
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

director = {
    "_note": "Корень. Время по дублю; раскладка — work/IMG_3313/page.py. Вырез сбивки 36.16–38.24 исходника.",
    "punches": [[t(2.12), t(3.00), 1.18, 0.10], [t(22.88), t(23.50), 1.16, 0.10],
                [t(38.24), t(39.70), 1.20, 0.0, 0.6], [t(48.10), t(48.90), 1.18, 0.10]],
    "text_fixes": tk.fixes({69: "джизр", 72: "Европе", 99: "Декарт", 101: "Путина"}),
    "keep_case": ["Европе", "Декарт", "Путина", "ЕГЭ"],
    "accent_words": ["корень", "радикс", "радикалом", "радикальными"],
    "hide_captions": [[t(2.05), t(3.00)], [t(22.85), t(23.50)], [t(48.05), t(48.80)], [t(53.95), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
