"""Страница графики IMG_3300: теорема Пифагора, которую знали за тысячу лет до Пифагора.

Время ударов — по исходнику, сдвигается на начало дубля из aroll.json.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import audio, build_page, card, doc_img  # noqa: E402

STEM = "IMG_3300"
meta = json.loads((ROOT / f"work/{STEM}/aroll.json").read_text(encoding="utf-8"))
OFF = meta["segments"][0][0]
DUR = meta["duration"]


def t(x: float) -> str:
    return f"{x - OFF:.2f}"


def f(x: float) -> float:
    return round(x - OFF, 2)


triangle = '''        <svg id="tri" class="g" viewBox="0 0 640 440" style="left: 220px; top: 1230px; width: 640px; height: 440px; overflow: visible;">
          <path id="tri-p" d="M 120 380 L 120 90 L 520 380 Z" fill="rgba(240,53,44,0.10)" stroke="#F2EBDD" stroke-width="10" stroke-linejoin="round"
                pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
          <path d="M 120 345 L 155 345 L 155 380" fill="none" stroke="#F2EBDD" stroke-width="6" />
          <text x="78" y="250" font-family="Cormorant" font-style="italic" font-weight="700" font-size="74" fill="#F2EBDD">a</text>
          <text x="300" y="432" font-family="Cormorant" font-style="italic" font-weight="700" font-size="74" fill="#F2EBDD">b</text>
          <text x="340" y="215" font-family="Cormorant" font-style="italic" font-weight="700" font-size="74" fill="#F0352C">c</text>
        </svg>'''

behind = "\n".join([
    '        <div id="h-lead" class="g lead" style="top: 56px;">это знали за 1000 лет до него</div>',
    '        <div id="formula" class="g eq-line" style="top: 95px; font-size: 150px;">a² + b² = c²</div>',
    '        <div id="qm" class="g big" style="top: 110px; font-size: 300px;">?</div>',
    '        <div id="lines0" class="g big" style="top: 80px; font-size: 200px; white-space: nowrap;">0 строк</div>',
    '        <div id="k1000" class="g big red" style="top: 70px; font-size: 190px; white-space: nowrap;">−1000 лет</div>',
])
front = "\n".join([
    triangle,
    '        <div id="pill-bab" class="g pill" style="left: 120px; top: 1270px; font-size: 38px;">Вавилонская?</div>',
    '        <div id="pill-ind" class="g pill" style="left: 600px; top: 1270px; font-size: 38px;">Индийская?</div>',
    card("card-pyth", "pythagoras.jpg", "Пифагор", "«Афинская школа», Рафаэль", "right"),
    '        <div id="stamp-sect" class="g stamp" style="left: 150px; top: 250px; font-size: 84px; background: rgba(12,12,14,0.55);">глава секты</div>',
    '        <div id="pill-club" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 1265px; background: none; border: none; font-size: 46px;">закрытый клуб <span style="color: var(--red);">по подписке</span></div>',
    '        <div id="rule" class="g paper" style="left: 130px; top: 1255px; width: 820px; text-align: center;"><div class="paper-text" style="font-style: normal; font-weight: 700;">Правило №1:</div><div class="paper-text">никому не рассказывать, что изучаешь</div></div>',
    '        <div id="pill-teacher" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 1265px; background: none; border: none; font-size: 46px;">все открытия → <span style="color: var(--red);">учителю</span></div>',
    doc_img("card-plim", "plimpton322.jpg", "Плимптон 322 · Вавилон, ок. 1800 до н. э.", left=170, top=1240, width=740, height=420, position="50% 50%"),
    '        <div id="pill-in" class="g pill" style="left: 170px; top: 1270px; font-size: 40px;">Индия ✓</div>',
    '        <div id="pill-ch" class="g pill" style="left: 600px; top: 1270px; font-size: 40px;">Китай ✓</div>',
])
beats = f'''
      // ---------- хук: это знали за тысячу лет, а назвали Пифагоровой ----------
      enter("#h-lead", {t(1.24)}, {{ fromScale: 1, fromY: 20, dur: 0.3, ease: "power2.out" }});
      tl.set("#tri", {{ opacity: 1 }}, {t(1.24)});
      draw("#tri-p", {t(1.30)}, 0.9);
      slam("#formula", {t(3.24)}, {{ fromScale: 1.4 }});
      flash({t(3.24)});
      leave(["#h-lead", "#formula"], {t(5.90)}, {{ y: -60 }});
      leave("#tri", {t(6.20)}, {{ y: 80, scale: 0.8 }});
      enter("#pill-bab", {t(7.22)}, {{ fromX: -220, fromScale: 0.9, rot: -3 }});
      enter("#pill-ind", {t(8.22)}, {{ fromX: 220, fromScale: 0.9, rot: 3 }});
      leave(["#pill-bab", "#pill-ind"], {t(9.10)}, {{ y: 60 }});

      // ---------- Пифагор — глава секты, клуб по подписке ----------
      card("#card-pyth", {t(10.18)}, {t(28.60)}, "right");
      slam("#stamp-sect", {t(13.22)}, {{ fromScale: 2.2, rot: -6, blur: 10 }});
      leave("#stamp-sect", {t(14.20)}, {{ scale: 0.6, y: 0, rot: -18 }});
      enter("#pill-club", {t(15.80)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#pill-club", {t(18.40)}, {{ y: 60 }});

      // ---------- как в «Бойцовском клубе»: молчать, открытия — учителю ----------
      doc("#rule", {t(21.92)}, {t(26.80)}, {{ fromRot: -5, rot: 1 }});
      enter("#pill-teacher", {t(27.48)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#pill-teacher", {t(28.90)}, {{ y: 60 }});

      // ---------- никто не знает, не оставил ни строчки ----------
      slam("#qm", {t(36.08)}, {{ fromScale: 1.6 }});
      leave("#qm", {t(37.00)}, {{ y: -60 }});
      slam("#lines0", {t(40.22)}, {{ fromScale: 1.4 }});
      leave("#lines0", {t(42.90)}, {{ y: -60 }});

      // ---------- знали за тысячу лет до него: вавилонская табличка ----------
      slam("#k1000", {t(45.32)}, {{ fromScale: 1.5 }});
      flash({t(45.32)});
      leave("#k1000", {t(46.45)}, {{ y: -60 }});
      doc("#card-plim", {t(47.74)}, {t(52.90)}, {{ fromRot: 6, rot: -2 }});
      tl.fromTo("#card-plim img", {{ scale: 1 }}, {{ scale: 1.12, duration: 5.2, ease: "none" }}, {t(47.74)});
      enter("#pill-in", {t(54.36)}, {{ fromX: -220, fromScale: 0.9, rot: -3 }});
      enter("#pill-ch", {t(54.84)}, {{ fromX: 220, fromScale: 0.9, rot: 3 }});
      leave(["#pill-in", "#pill-ch"], {t(55.80)}, {{ y: 60 }});
'''
sounds = [
    audio("lead", "whoosh", f(1.22), 0.26), audio("tri", "sparkle", f(1.30), 0.24),
    audio("formula", "impact-bass-1", f(3.22), 0.42),
    audio("bab", "pop", f(7.20), 0.32), audio("ind", "pop", f(8.20), 0.32),
    audio("pyth", "whoosh", f(10.16), 0.28), audio("sect", "impact-bass-1", f(13.20), 0.34),
    audio("club", "pop", f(15.78), 0.30), audio("rule", "whoosh", f(21.90), 0.24),
    audio("teacher", "pop", f(27.46), 0.30), audio("qm", "pop", f(36.06), 0.30),
    audio("lines", "click", f(40.20), 0.38), audio("k1000", "impact-bass-1", f(45.30), 0.40),
    audio("plim", "whoosh", f(47.72), 0.24), audio("pin", "pop", f(54.34), 0.30), audio("pch", "pop", f(54.82), 0.30),
]
fg = [(f(1.20), f(6.00)), (f(36.00), f(37.10)), (f(40.15), f(43.00)), (f(45.25), f(46.55))]
page = build_page("Теорема Пифагора — не Пифагора", DUR, behind, front, beats, sounds, fg,
                  cta_at=f(56.04), cta_small="объясню сложное простым языком")
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

director = {
    "_note": "Теорема Пифагора. Время по дублю.",
    "punches": [[f(3.24), f(4.20), 1.20, 0.10], [f(13.22), f(14.00), 1.18, 0.10], [f(45.32), f(46.20), 1.20, 0.10]],
    "text_fixes": {"13": "Пифагоровой", "82": "Маркаряна", "167": "+"},
    "keep_case": ["Пифагоровой", "Вавилонской", "Индийской", "Пифагор", "Блиновской", "Арсена", "Маркаряна",
                  "Пифагора", "Индии", "Китае", "ЕГЭ", "4000"],
    "accent_words": ["Пифагор", "секты", "4000", "тысячу"],
    "hide_captions": [[f(3.20), f(4.00)], [f(13.20), f(13.75)], [f(45.30), f(46.10)], [f(55.95), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, сдвиг", round(OFF, 3))
