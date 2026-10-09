"""Страница графики IMG_3309: почему лист А4 размером 210 × 297.

Время ударов — по исходнику, на шкалу дубля переводит Take.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page  # noqa: E402

STEM = "IMG_3309"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
PAPER = "#FBFBF6"

lines = "".join(f'<rect x="58" y="{60 + 26 * k}" width="{244 if k % 4 != 3 else 150}" height="7" rx="3" fill="#D9D5CA" />'
                for k in range(14))
sheet = f'''        <svg id="sheet" class="g" viewBox="0 0 480 520" style="left: 300px; top: 1240px; width: 480px; height: 520px; overflow: visible;">
          <rect x="30" y="20" width="300" height="424" rx="6" fill="{PAPER}" />
          {lines}
          <g stroke="#F2EBDD" stroke-width="4" fill="none">
            <path d="M 30 474 H 330 M 30 462 V 486 M 330 462 V 486" />
            <path d="M 360 20 V 444 M 348 20 H 372 M 348 444 H 372" />
          </g>
          <g font-family="JBMono" font-weight="700" font-size="38" fill="#F2EBDD">
            <text id="sz-w" x="180" y="514" text-anchor="middle" opacity="0">210</text>
            <text id="sz-h" x="380" y="246" opacity="0">297</text>
            <text id="sz-w2" x="180" y="514" text-anchor="middle" fill="#F0352C" opacity="0">200?</text>
            <text id="sz-h2" x="380" y="246" fill="#F0352C" opacity="0">300?</text>
          </g>
        </svg>'''

fold = f'''        <svg id="fold" class="g" viewBox="0 0 600 560" style="left: 240px; top: 1222px; width: 600px; height: 560px; overflow: visible;">
          <rect id="ghost" x="160" y="40" width="280" height="396" rx="4" fill="none" stroke="#F2EBDD" stroke-width="4" stroke-dasharray="14 10" opacity="0" />
          <g id="half">
            <rect x="160" y="238" width="280" height="198" rx="4" fill="{PAPER}" />
            <g id="flap"><rect x="160" y="40" width="280" height="198" rx="4" fill="#ECE7DA" stroke="#D9D5CA" stroke-width="2" /></g>
          </g>
          <path id="fold-line" d="M 160 238 H 440" stroke="#F0352C" stroke-width="6" stroke-linecap="round" fill="none" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
          <text id="same" x="300" y="530" text-anchor="middle" font-family="JBMono" font-weight="700" font-size="36" fill="#F2EBDD" opacity="0">та же форма: 1 : √2</text>
        </svg>'''


def doll(x: float, s: float, color: str) -> str:
    return f'''<g transform="translate({x} 300) scale({s})">
              <path d="M -82 0 C -98 -62 -74 -118 -56 -140 C -78 -172 -70 -232 0 -242 C 70 -232 78 -172 56 -140 C 74 -118 98 -62 82 0 Z" fill="{color}" stroke="#F2EBDD" stroke-width="5" />
              <ellipse cx="0" cy="-62" rx="46" ry="50" fill="#F6E9D6" />
              <circle cx="0" cy="-62" r="16" fill="{color}" /><circle cx="0" cy="-62" r="6" fill="#F5B82E" />
              <circle cx="0" cy="-182" r="38" fill="#F6E3CF" />
              <circle cx="-13" cy="-186" r="4" fill="#2A2219" /><circle cx="13" cy="-186" r="4" fill="#2A2219" />
              <circle cx="-20" cy="-172" r="6" fill="#F27C6E" /><circle cx="20" cy="-172" r="6" fill="#F27C6E" />
            </g>'''


matr = f'''        <svg id="matr" class="g" viewBox="0 0 600 320" style="left: 240px; top: 1262px; width: 600px; height: 320px; overflow: visible;">
            {doll(130, 1.0, "#C62F28")}
            {doll(330, 0.78, "#2F6FC6")}
            {doll(480, 0.6, "#2E9E57")}
        </svg>'''

X0, Y0, W, H = 170, 20, 360, 509.1
iso = f'''        <svg id="iso" class="g" viewBox="0 0 700 560" style="left: 190px; top: 1215px; width: 700px; height: 560px; overflow: visible;">
          <rect x="{X0}" y="{Y0}" width="{W}" height="{H}" rx="4" fill="rgba(251,251,246,0.92)" />
          <rect id="a4-cell" x="350" y="401.8" width="90" height="127.3" fill="#F0352C" opacity="0" />
          <g fill="none" stroke="#2A2219" stroke-width="5" stroke-linecap="round">
            <path id="l1" d="M 170 274.6 H 530" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
            <path id="l2" d="M 350 274.6 V 529.1" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
            <path id="l3" d="M 350 401.8 H 530" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
            <path id="l4" d="M 440 401.8 V 529.1" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
            <path id="l5" d="M 440 465.5 H 530" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
          </g>
          <g font-family="JBMono" font-weight="700" fill="#2A2219" text-anchor="middle" dominant-baseline="central">
            <text id="lb0" x="350" y="250" font-size="120" opacity="0">A0</text>
            <text id="lb-m2" x="350" y="350" font-size="56" fill="#F0352C" opacity="0">1 м²</text>
            <text id="lb1" x="350" y="147" font-size="92" opacity="0">A1</text>
            <text id="lb2" x="260" y="402" font-size="64" opacity="0">A2</text>
            <text id="lb3" x="440" y="338" font-size="46" opacity="0">A3</text>
            <text id="lb4" x="395" y="465" font-size="32" opacity="0">A4</text>
            <text id="lb5" x="485" y="434" font-size="22" opacity="0">A5</text>
          </g>
        </svg>'''

comment = '''        <div id="comment" class="g" style="left: 80px; top: 1300px; width: 920px; height: 128px; border-radius: 64px; background: rgba(22,22,26,0.94); border: 2px solid rgba(242,235,221,0.22);">
          <div style="position: absolute; left: 24px; top: 24px; width: 80px; height: 80px; border-radius: 40px; background: linear-gradient(135deg, #F5B82E, #F0352C 60%, #A23BD1);"></div>
          <div id="cm-ph" style="position: absolute; left: 132px; top: 38px; font-family: 'Manrope'; font-weight: 800; font-size: 40px; color: rgba(242,235,221,0.38);">Добавьте комментарий…</div>
          <div style="position: absolute; left: 132px; top: 22px; font-family: 'JBMono'; font-weight: 700; font-size: 70px; color: var(--cream);">
            <span id="cm-3" style="opacity: 0;">3</span><span id="cm-0a" style="opacity: 0;">0</span><span id="cm-0b" style="opacity: 0;">0</span>
          </div>
          <svg viewBox="0 0 60 60" style="position: absolute; right: 34px; top: 34px; width: 60px; height: 60px;">
            <path d="M 6 30 L 54 8 L 40 54 L 30 34 Z" fill="none" stroke="#F2EBDD" stroke-width="5" stroke-linejoin="round" />
          </svg>
        </div>'''

behind = "\n".join([
    '        <div id="a4" class="g big" style="top: 80px; font-size: 300px;">A4</div>',
    '        <div id="sqrt2" class="g glyph mono" style="left: 0; width: 1080px; top: 70px; font-size: 260px; color: var(--red);">√2</div>',
    '        <div id="eq-half" class="g glyph mono" style="left: 0; width: 1080px; top: 170px; font-size: 90px; white-space: nowrap;">210 : 148,5 = <span style="color: var(--red);">√2</span></div>',
    '        <div id="lead300" class="g lead" style="top: 56px;">3 экзамена × 100 баллов</div>',
    '        <div id="b300" class="g big red" style="top: 100px; font-size: 300px;">300</div>',
])
front = "\n".join([
    sheet,
    '        <div id="div" class="g" style="left: 90px; top: 1262px; width: 900px; height: 150px; border-radius: 28px; background: rgba(12,12,14,0.86); border: 2px solid rgba(242,235,221,0.16);">',
    '          <div style="position: absolute; left: 0; top: 34px; width: 900px; text-align: center; font-family: \'JBMono\'; font-weight: 700; font-size: 72px; color: var(--cream); white-space: nowrap;">'
    '<span id="dv-a" style="display: inline-block; opacity: 0;">297</span> <span id="dv-b" style="display: inline-block; opacity: 0;">: 210</span> '
    '<span id="dv-c" style="display: inline-block; opacity: 0; color: var(--red);">≈ 1,414</span></div>',
    '        </div>',
    '        <div id="st-uniq" class="g stamp" style="left: 160px; top: 250px; font-size: 70px; white-space: nowrap; background: rgba(12,12,14,0.55);">уникальное свойство</div>',
    fold,
    '        <div id="st-none" class="g stamp" style="left: 300px; top: 260px; font-size: 92px; white-space: nowrap; background: rgba(12,12,14,0.55);">больше никто</div>',
    matr,
    '        <div id="ru" class="g sticker" style="left: 230px; top: 300px; font-size: 56px; white-space: nowrap;">русские снова впереди</div>',
    iso,
    '        <div id="p-comm" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 1215px; background: none; border: none; font-size: 40px;">пиши в комментариях</div>',
    comment,
    '        <div id="free" class="g sticker" style="left: 200px; top: 1470px; font-size: 56px; white-space: nowrap;">получай бесплатные материалы</div>',
])

beats = f'''
      // ---------- хук: почему А4 — 210 на 297 ----------
      slam("#a4", {t(23.96)}, {{ fromScale: 1.6 }});
      flash({t(23.96)});
      leave("#a4", {t(25.00)}, {{ y: -60 }});
      enter("#sheet", {t(24.48)}, {{ fromY: 120, fromScale: 0.85, rot: -4, dur: 0.4, ease: "power3.out" }});
      tl.to("#sz-w", {{ opacity: 1, duration: 0.12 }}, {t(25.08)});
      tl.to("#sz-h", {{ opacity: 1, duration: 0.12 }}, {t(25.84)});
      tl.to("#sz-w", {{ opacity: 0, duration: 0.1 }}, {t(28.30)});
      tl.to("#sz-w2", {{ opacity: 1, duration: 0.12 }}, {t(28.34)});
      tl.to("#sz-h", {{ opacity: 0, duration: 0.1 }}, {t(29.20)});
      tl.to("#sz-h2", {{ opacity: 1, duration: 0.12 }}, {t(29.24)});
      leave("#sheet", {t(30.45)}, {{ y: 80, rot: 6 }});

      // ---------- 297 : 210 = √2 ----------
      enter("#div", {t(32.32)}, {{ fromY: 120, fromScale: 0.92, dur: 0.35, ease: "power3.out" }});
      enter("#dv-a", {t(32.68)}, {{ fromScale: 1.4, dur: 0.15, blur: 6 }});
      enter("#dv-b", {t(33.76)}, {{ fromScale: 1.4, dur: 0.15, blur: 6 }});
      enter("#dv-c", {t(34.50)}, {{ fromScale: 1.4, dur: 0.15, blur: 6 }});
      slam("#sqrt2", {t(34.94)}, {{ fromScale: 1.6 }});
      flash({t(34.94)});
      leave("#sqrt2", {t(36.05)}, {{ y: -60 }});
      leave("#div", {t(36.30)}, {{ y: 80 }});
      slam("#st-uniq", {t(37.80)}, {{ fromScale: 2.2, rot: -5, blur: 10 }});
      leave("#st-uniq", {t(38.95)}, {{ scale: 0.6, y: 0, rot: -16 }});

      // ---------- сложить пополам — та же форма ----------
      enter("#fold", {t(39.16)}, {{ fromY: 120, fromScale: 0.9, dur: 0.35, ease: "power3.out" }});
      draw("#fold-line", {t(39.76)}, 0.3);
      tl.to("#fold-line", {{ opacity: 0, duration: 0.1 }}, {t(40.55)});
      tl.fromTo("#flap", {{ scaleY: 1 }}, {{ scaleY: -1, svgOrigin: "300 238", duration: 0.5, ease: "power2.inOut", immediateRender: false }}, {t(40.10)});
      tl.to("#ghost", {{ opacity: 0.55, duration: 0.25 }}, {t(40.65)});
      tl.fromTo("#half", {{ rotation: 0, y: 0 }}, {{ rotation: 90, y: -99, svgOrigin: "300 337", duration: 0.5, ease: "power3.inOut", immediateRender: false }}, {t(41.10)});
      tl.to("#same", {{ opacity: 1, duration: 0.2 }}, {t(42.96)});
      slam("#eq-half", {t(45.94)}, {{ fromScale: 1.4 }});
      leave("#eq-half", {t(47.00)}, {{ y: -60 }});
      leave("#fold", {t(47.90)}, {{ y: 80 }});
      slam("#st-none", {t(49.30)}, {{ fromScale: 2.2, rot: 6, blur: 10 }});
      leave("#st-none", {t(50.10)}, {{ scale: 0.6, y: 0, rot: 18 }});

      // ---------- как матрёшка; русские снова впереди ----------
      enter("#matr", {t(51.14)}, {{ fromY: 140, fromScale: 0.7, dur: 0.4, ease: "back.out(1.6)" }});
      leave("#matr", {t(52.20)}, {{ y: 80 }});
      enter("#ru", {t(52.76)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#ru", {t(53.40)}, {{ y: -30, rot: -10 }});

      // ---------- А0 = 1 м², дальше каждый раз пополам ----------
      enter("#iso", {t(53.46)}, {{ fromY: 120, fromScale: 0.9, dur: 0.4, ease: "power3.out" }});
      enter("#lb0", {t(54.64)}, {{ fromScale: 1.4, dur: 0.18 }});
      enter("#lb-m2", {t(56.74)}, {{ fromScale: 1.4, dur: 0.18 }});
      leave(["#lb0", "#lb-m2"], {t(58.30)}, {{ y: 0, scale: 0.6, dur: 0.15 }});
      draw("#l1", {t(58.42)}, 0.3);
      enter("#lb1", {t(59.22)}, {{ fromScale: 1.4, dur: 0.18 }});
      draw("#l2", {t(60.66)}, 0.3);
      enter("#lb2", {t(61.22)}, {{ fromScale: 1.4, dur: 0.18 }});
      draw("#l3", {t(62.12)}, 0.2);
      enter("#lb3", {t(62.30)}, {{ fromScale: 1.4, dur: 0.15 }});
      draw("#l4", {t(62.64)}, 0.2);
      enter("#lb4", {t(62.80)}, {{ fromScale: 1.4, dur: 0.15 }});
      tl.to("#a4-cell", {{ opacity: 0.45, duration: 0.2 }}, {t(62.80)});
      draw("#l5", {t(63.20)}, 0.2);
      enter("#lb5", {t(63.36)}, {{ fromScale: 1.4, dur: 0.15 }});
      leave("#iso", {t(64.40)}, {{ y: 80 }});

      // ---------- затрёхсотить три экзамена ----------
      slam("#b300", {t(66.90)}, {{ fromScale: 1.6 }});
      flash({t(66.90)});
      enter("#lead300", {t(67.42)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave(["#b300", "#lead300"], {t(67.95)}, {{ y: -60 }});

      // ---------- комментарий «300» ----------
      leave(["#cta", "#cta-arrow"], {t(71.70)}, {{ y: 80 }});
      enter("#p-comm", {t(71.86)}, {{ fromScale: 0.85, dur: 0.25 }});
      enter("#comment", {t(71.92)}, {{ fromY: 160, fromScale: 0.9, dur: 0.4, ease: "power3.out" }});
      tl.to("#cm-ph", {{ opacity: 0, duration: 0.05 }}, {t(72.86)});
      tl.to("#cm-3", {{ opacity: 1, duration: 0.03 }}, {t(72.88)});
      tl.to("#cm-0a", {{ opacity: 1, duration: 0.03 }}, {t(72.96)});
      tl.to("#cm-0b", {{ opacity: 1, duration: 0.03 }}, {t(73.04)});
      enter("#free", {t(73.90)}, {{ fromScale: 0.6, rot: -3 }});
'''
sounds = [
    audio("a4", "impact-bass-1", t(23.94), 0.40), audio("sheet", "whoosh", t(24.46), 0.22),
    audio("szw", "click", t(25.06), 0.34), audio("szh", "click", t(25.82), 0.34),
    audio("szw2", "error", t(28.32), 0.18), audio("szh2", "error", t(29.22), 0.18),
    audio("div", "whoosh-short", t(32.30), 0.24), audio("dva", "click", t(32.66), 0.34),
    audio("dvb", "click", t(33.74), 0.34), audio("dvc", "click", t(34.48), 0.34),
    audio("sqrt", "impact-bass-1", t(34.92), 0.40), audio("uniq", "impact-bass-1", t(37.78), 0.28),
    audio("fold", "whoosh-short", t(39.14), 0.24), audio("flap", "whoosh", t(40.08), 0.26),
    audio("half", "whoosh-short", t(41.08), 0.26), audio("same", "ping", t(42.94), 0.30),
    audio("eqh", "pop", t(45.92), 0.30), audio("none", "impact-bass-1", t(49.28), 0.28),
    audio("matr", "pop", t(51.12), 0.32), audio("ru", "pop", t(52.74), 0.28),
    audio("iso", "whoosh", t(53.44), 0.24), audio("a0", "click", t(54.62), 0.34), audio("m2", "ping", t(56.72), 0.28),
    audio("l1", "click-soft", t(58.40), 0.40), audio("l2", "click-soft", t(60.64), 0.40),
    audio("l3", "click-soft", t(62.10), 0.36), audio("l4", "click-soft", t(62.62), 0.36), audio("l5", "click-soft", t(63.18), 0.36),
    audio("b300", "impact-bass-1", t(66.88), 0.42),
    audio("comm", "whoosh-short", t(71.84), 0.24), audio("type", "key-press", t(72.86), 0.40, duration=0.35),
    audio("free", "notification", t(73.88), 0.24),
]
fg = [(t(23.86), t(25.35)), (t(34.84), t(36.40)), (t(45.84), t(47.35)), (t(66.80), t(68.30))]
page = build_page("Почему А4 — это 210 на 297", DUR, behind, front, beats, sounds, fg, cta_at=t(68.02),
                  cta_small="объясню все темы доходчиво")
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

fixes = {1: "лист", 2: "A4", 73: "матрёшка", 81: "A0", 92: "A1", 98: "A2", 104: "матрёшка",
         110: "затрёхсотить", 111: "", 112: ""}
fixes.update(json.loads((ROOT / f"work/{STEM}/recheck_fixes.json").read_text(encoding="utf-8"))
             if (ROOT / f"work/{STEM}/recheck_fixes.json").exists() else {})
director = {
    "_note": "А4. Время по дублю; раскладка — work/IMG_3309/page.py.",
    "punches": [[t(23.96), t(24.80), 1.18, 0.10], [t(34.94), t(35.90), 1.20, 0.10], [t(66.90), t(67.80), 1.20, 0.10]],
    "text_fixes": tk.fixes({int(k): v for k, v in fixes.items()}),
    "keep_case": ["A4", "A0", "A1", "A2", "ЕГЭ"],
    "accent_words": ["корень", "матрёшка", "300"],
    "hide_captions": [[t(23.90), t(24.45)], [t(34.90), t(35.95)], [t(45.90), t(46.95)], [t(66.85), t(67.95)],
                      [t(67.95), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
