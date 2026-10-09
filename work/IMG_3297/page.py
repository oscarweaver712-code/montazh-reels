"""Страница графики IMG_3297: почему минус на минус даёт плюс.

Время ударов записано по исходнику и сдвигается на начало дубля из aroll.json —
так раскладку можно писать, пока дубль ещё готовится.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import audio, build_page, card  # noqa: E402

meta = json.loads((ROOT / "work/IMG_3297/aroll.json").read_text(encoding="utf-8"))
OFF = meta["segments"][0][0]
DUR = meta["duration"]


def t(x: float) -> str:
    return f"{x - OFF:.2f}"


def stick(sid: str, left: int, top: int) -> str:
    """Стикмен в профиль: нос показывает, куда он смотрит; ноги — отдельные группы для шага."""
    return f'''        <svg id="{sid}" class="g" viewBox="0 0 200 320" style="left: {left}px; top: {top}px; width: 190px; height: 304px; overflow: visible;">
          <g fill="none" stroke="#F2EBDD" stroke-width="13" stroke-linecap="round" stroke-linejoin="round">
            <line x1="100" y1="112" x2="100" y2="212" />
            <g class="arm"><line x1="100" y1="140" x2="70" y2="200" /><line x1="100" y1="140" x2="130" y2="200" /></g>
            <g class="leg-a"><line x1="100" y1="212" x2="100" y2="300" /></g>
            <g class="leg-b"><line x1="100" y1="212" x2="100" y2="300" /></g>
          </g>
          <circle cx="100" cy="66" r="36" fill="#F2EBDD" />
          <path d="M 134 62 L 152 70 L 134 76 Z" fill="#F2EBDD" />
        </svg>'''


wifi = '''        <svg id="ic-wifi" class="g" viewBox="0 0 200 200" style="left: 170px; top: 1270px; width: 200px; height: 200px;">
          <g fill="none" stroke="#F2EBDD" stroke-width="16" stroke-linecap="round">
            <path d="M 30 80 Q 100 20 170 80" /><path d="M 55 110 Q 100 70 145 110" /><path d="M 80 140 Q 100 122 120 140" /></g>
          <circle cx="100" cy="166" r="12" fill="#F2EBDD" />
          <line id="x-wifi" x1="25" y1="25" x2="175" y2="175" stroke="#F0352C" stroke-width="18" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
        </svg>'''
bulb = '''        <svg id="ic-bulb" class="g" viewBox="0 0 200 200" style="left: 710px; top: 1270px; width: 200px; height: 200px;">
          <path d="M 100 20 C 55 20 35 55 45 88 C 52 110 72 120 74 142 L 126 142 C 128 120 148 110 155 88 C 165 55 145 20 100 20 Z" fill="none" stroke="#F2EBDD" stroke-width="14" stroke-linejoin="round" />
          <line x1="78" y1="162" x2="122" y2="162" stroke="#F2EBDD" stroke-width="14" stroke-linecap="round" />
          <line x1="86" y1="182" x2="114" y2="182" stroke="#F2EBDD" stroke-width="14" stroke-linecap="round" />
          <line id="x-bulb" x1="25" y1="25" x2="175" y2="175" stroke="#F0352C" stroke-width="18" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />
        </svg>'''

behind = "\n".join([
    '        <div id="h-a" class="g glyph mono" style="left: 40px; width: 200px; top: 110px; font-size: 260px;">−</div>',
    '        <div id="h-x" class="g glyph mono" style="left: 240px; width: 200px; top: 110px; font-size: 220px; color: rgba(242,235,221,0.7);">×</div>',
    '        <div id="h-b" class="g glyph mono" style="left: 440px; width: 200px; top: 110px; font-size: 260px;">−</div>',
    '        <div id="h-eq" class="g glyph mono" style="left: 640px; width: 200px; top: 110px; font-size: 260px;">=</div>',
    '        <div id="h-plus" class="g glyph mono" style="left: 840px; width: 200px; top: 110px; font-size: 260px; color: var(--red);">+</div>',
    '        <div id="logic" class="g eq-line" style="top: 120px;">−2 + (−3) = −5</div>',
    '        <div id="logic-lab" class="g lead" style="top: 60px;">логично же: минусы складываются</div>',
    '        <div id="plus" class="g glyph mono" style="left: 0; width: 1080px; top: 20px; font-size: 300px; color: var(--red);">+</div>',
    '        <div id="rub" class="g big" style="top: 40px; font-size: 260px;">₽</div>',
    '        <div id="debt" class="g big red" style="top: 40px; font-size: 260px;">−₽</div>',
    '        <div id="vii" class="g big" style="top: 90px; font-size: 220px; white-space: nowrap;">VII век</div>',
    '        <div id="k1000" class="g big" style="top: 60px; font-size: 240px;">1000 лет</div>',
    '        <div id="mm" class="g glyph mono" style="left: 0; width: 1080px; top: 120px; font-size: 150px; white-space: nowrap;">(−)·(−) = <span style="color: var(--red);">+</span></div>',
])
front = "\n".join([
    wifi, bulb,
    '        <div id="pill-in" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 300px; background: none; border: none; font-size: 38px; white-space: nowrap;">Индия: каждый <span style="color: var(--red);">6-й</span> человек на Земле</div>',
    '        <div id="stamp-ru" class="g stamp" style="left: 250px; top: 300px; font-size: 74px; background: rgba(12,12,14,0.55);">я не по русскому</div>',
    '        <div id="pill-brahma" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 330px; background: none; border: none; font-size: 40px;">Брахмагупта, Индия, 628 год</div>',
    '        <div id="c-plus" class="g paper" style="left: 90px; top: 1260px; width: 430px; text-align: center; white-space: nowrap;"><div class="paper-text" style="font-style: normal; font-weight: 700; font-size: 60px; color: #1E8F4C;">+ имущество</div></div>',
    '        <div id="c-minus" class="g paper" style="left: 560px; top: 1260px; width: 430px; text-align: center; white-space: nowrap;"><div class="paper-text" style="font-style: normal; font-weight: 700; font-size: 60px; color: #C7271F;">− долг</div></div>',
    '        <div id="debt-eq" class="g paper" style="left: 140px; top: 1260px; width: 800px; text-align: center;"><div class="hand" style="color: #22303F; font-size: 100px;">−(−100 ₽) = +100 ₽</div><div class="note">забрали долг — стал богаче</div></div>',
    card("card-descartes", "descartes.jpg", "Рене Декарт", "называл их «ложными»", "left"),
    '        <div id="stamp-false" class="g stamp" style="left: 380px; top: 220px; font-size: 72px; white-space: nowrap; background: rgba(12,12,14,0.55);">ложные корни</div>',
    '        <div id="zoom" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 300px; background: none; border: none; font-size: 46px;">объяснение для зумеров</div>',
    '        <div id="screen" class="g" style="left: 110px; top: 1250px; width: 860px; height: 400px; border-radius: 28px; background: rgba(10,10,12,0.82); border: 2px solid rgba(242,235,221,0.16);">',
    '          <div id="rec" style="position: absolute; left: 30px; top: 22px; font-family: \'Manrope\'; font-weight: 800; font-size: 30px; color: var(--cream);"><span style="color: var(--red);">●</span> видео</div>',
    '          <div id="rev" style="position: absolute; right: 30px; top: 18px; font-family: \'JBMono\'; font-weight: 700; font-size: 40px; color: #4FE3E6; opacity: 0;">◀◀ задом наперёд</div>',
    '          <div id="sgn1" style="position: absolute; right: 40px; bottom: 26px; font-family: \'JBMono\'; font-weight: 700; font-size: 90px; color: var(--red); opacity: 0;">−</div>',
    '          <div id="sgn2" style="position: absolute; right: 120px; bottom: 26px; font-family: \'JBMono\'; font-weight: 700; font-size: 90px; color: var(--red); opacity: 0;">−</div>',
    '          <div id="sgn3" style="position: absolute; right: 40px; bottom: 26px; font-family: \'JBMono\'; font-weight: 700; font-size: 90px; color: #3BD16F; opacity: 0;">+</div>',
    '        </div>',
    stick("walker", 470, 1320),
    '        <div id="stamp-done" class="g stamp" style="left: 300px; top: 300px; font-size: 92px; color: #3BD16F; border-color: #3BD16F; background: rgba(12,12,14,0.55);">долг списан</div>',
])

beats = f'''
      // ---------- хук: (−) × (−) = (+)? ----------
      slam("#h-a", {t(0.88)}, {{ fromScale: 1.6 }});
      slam("#h-x", {t(1.26)}, {{ fromScale: 1.6 }});
      slam("#h-b", {t(1.38)}, {{ fromScale: 1.6 }});
      slam("#h-eq", {t(2.08)}, {{ fromScale: 1.6 }});
      slam("#h-plus", {t(2.08)}, {{ fromScale: 1.8 }});
      flash({t(2.08)});
      leave(["#h-a", "#h-x", "#h-b", "#h-eq", "#h-plus"], {t(2.90)}, {{ y: -60 }});
      enter("#logic", {t(3.14)}, {{ fromScale: 1, fromY: 30, dur: 0.35, ease: "power3.out" }});
      enter("#logic-lab", {t(3.80)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave(["#logic", "#logic-lab"], {t(5.45)}, {{ y: -50 }});

      // ---------- интернет и свет: два минуса → плюс ----------
      enter("#ic-wifi", {t(6.52)}, {{ fromScale: 0.5, fromY: 60, dur: 0.3 }});
      draw("#x-wifi", {t(6.98)}, 0.25);
      enter("#ic-bulb", {t(7.42)}, {{ fromScale: 0.5, fromY: 60, dur: 0.3 }});
      draw("#x-bulb", {t(7.58)}, 0.25);
      leave(["#ic-wifi", "#ic-bulb"], {t(9.30)}, {{ y: 80 }});
      slam("#plus", {t(9.42)}, {{ fromScale: 1.8 }});
      leave("#plus", {t(10.30)}, {{ y: -60, scale: 1.1 }});

      // ---------- дело в деньгах — в долгах ----------
      slam("#rub", {t(12.16)}, {{ fromScale: 1.5 }});
      leave("#rub", {t(12.85)}, {{ y: -40 }});
      slam("#debt", {t(12.92)}, {{ fromScale: 1.5 }});
      leave("#debt", {t(13.60)}, {{ y: -60 }});

      // ---------- индийцы, «я преподаватель не по русскому» ----------
      enter("#pill-in", {t(17.34)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#pill-in", {t(19.90)}, {{ y: 60 }});
      slam("#stamp-ru", {t(21.40)}, {{ fromScale: 2.2, rot: -6, blur: 10 }});
      leave("#stamp-ru", {t(22.95)}, {{ scale: 0.6, y: 0, rot: -18 }});

      // ---------- VII век, Брахмагупта: имущество и долг ----------
      slam("#vii", {t(23.46)}, {{ fromScale: 1.4 }});
      enter("#pill-brahma", {t(24.32)}, {{ fromScale: 0.9, dur: 0.25 }});
      leave(["#vii", "#pill-brahma"], {t(26.40)}, {{ y: -60 }});
      enter("#c-plus", {t(26.62)}, {{ fromX: -260, fromScale: 0.9, rot: -3 }});
      enter("#c-minus", {t(28.26)}, {{ fromX: 260, fromScale: 0.9, rot: 3 }});
      leave(["#c-plus", "#c-minus"], {t(29.55)}, {{ y: 80 }});
      doc("#debt-eq", {t(29.66)}, {t(33.90)}, {{ fromRot: 5, rot: -1 }});
      slam("#mm", {t(32.48)}, {{ fromScale: 1.4 }});
      flash({t(33.34)});
      leave("#mm", {t(33.90)}, {{ y: -60 }});

      // ---------- тысячу лет не признавали, Декарт: «ложные» ----------
      slam("#k1000", {t(36.30)}, {{ fromScale: 1.4 }});
      leave("#k1000", {t(38.95)}, {{ y: -60 }});
      card("#card-descartes", {t(39.40)}, {t(46.40)}, "left");
      slam("#stamp-false", {t(45.72)}, {{ fromScale: 2.2, rot: 6, blur: 10 }});
      leave("#stamp-false", {t(46.40)}, {{ scale: 0.6, y: 0, rot: 18 }});

      // ---------- по-зумерски: видео спиной вперёд, перемотанное назад ----------
      enter("#zoom", {t(48.22)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#zoom", {t(49.30)}, {{ y: -30 }});
      enter("#screen", {t(48.98)}, {{ fromScale: 0.85, dur: 0.3, ease: "power3.out" }});
      tl.set("#walker", {{ opacity: 1, x: 220 }}, {t(49.70)});
      // идёт спиной вперёд: смотрит вправо, а едет влево
      tl.to("#walker", {{ x: -220, duration: 1.8, ease: "none" }}, {t(49.88)});
      tl.fromTo("#walker .leg-a", {{ rotation: 22 }}, {{ rotation: -22, svgOrigin: "100 212", duration: 0.3, ease: "sine.inOut", yoyo: true, repeat: 5 }}, {t(49.88)});
      tl.fromTo("#walker .leg-b", {{ rotation: -22 }}, {{ rotation: 22, svgOrigin: "100 212", duration: 0.3, ease: "sine.inOut", yoyo: true, repeat: 5 }}, {t(49.88)});
      tl.set("#sgn1", {{ opacity: 1 }}, {t(51.26)});
      tl.set("#rev", {{ opacity: 1 }}, {t(52.44)});
      tl.set("#sgn2", {{ opacity: 1 }}, {t(54.46)});
      // перемотка задом наперёд: теперь идёт нормально — вперёд, вправо
      tl.set("#walker", {{ x: -220 }}, {t(55.70)});
      tl.to("#walker", {{ x: 220, duration: 1.8, ease: "none" }}, {t(55.88)});
      tl.fromTo("#walker .leg-a", {{ rotation: -22 }}, {{ rotation: 22, svgOrigin: "100 212", duration: 0.3, ease: "sine.inOut", yoyo: true, repeat: 5, immediateRender: false }}, {t(55.88)});
      tl.fromTo("#walker .leg-b", {{ rotation: 22 }}, {{ rotation: -22, svgOrigin: "100 212", duration: 0.3, ease: "sine.inOut", yoyo: true, repeat: 5, immediateRender: false }}, {t(55.88)});
      tl.set(["#sgn1", "#sgn2"], {{ opacity: 0 }}, {t(57.50)});
      tl.set("#sgn3", {{ opacity: 1 }}, {t(57.50)});
      leave(["#screen", "#walker"], {t(58.40)}, {{ y: 80 }});

      // ---------- списываешь долг — плюс ----------
      slam("#stamp-done", {t(61.36)}, {{ fromScale: 2.2, rot: -8, blur: 10 }});
      leave("#stamp-done", {t(62.95)}, {{ scale: 0.6, y: 0, rot: -20 }});
'''
sounds = [
    audio("ha", "click", float(t(0.86)), 0.40), audio("hx", "click", float(t(1.24)), 0.36),
    audio("hb", "click", float(t(1.36)), 0.40), audio("heq", "impact-bass-1", float(t(2.06)), 0.42),
    audio("logic", "whoosh-short", float(t(3.12)), 0.26),
    audio("wifi", "error", float(t(6.96)), 0.20), audio("bulb", "error", float(t(7.56)), 0.20),
    audio("plus", "ping", float(t(9.40)), 0.34),
    audio("rub", "click", float(t(12.14)), 0.38), audio("debt", "impact-bass-1", float(t(12.90)), 0.30),
    audio("in", "pop", float(t(17.32)), 0.30), audio("ru", "impact-bass-1", float(t(21.38)), 0.28),
    audio("vii", "whoosh-short", float(t(23.44)), 0.30),
    audio("cplus", "pop", float(t(26.60)), 0.32), audio("cminus", "pop", float(t(28.24)), 0.32),
    audio("debteq", "whoosh", float(t(29.64)), 0.24), audio("mm", "impact-bass-1", float(t(32.46)), 0.36),
    audio("k1000", "whoosh-short", float(t(36.28)), 0.30),
    audio("descartes", "whoosh-short", float(t(39.38)), 0.28), audio("false", "impact-bass-1", float(t(45.70)), 0.28),
    audio("screen", "whoosh", float(t(48.96)), 0.24), audio("s1", "click", float(t(51.24)), 0.36),
    audio("rev", "glitch-3", float(t(52.42)), 0.22, duration=0.8, fade_out=0.3), audio("s2", "click", float(t(54.44)), 0.36),
    audio("s3", "chime", float(t(57.48)), 0.28, duration=1.0, fade_out=0.4),
    audio("done", "chime", float(t(61.34)), 0.28, duration=1.0, fade_out=0.4),
]
fg = [(float(t(0.80)), float(t(2.95))), (float(t(3.05)), float(t(5.55))), (float(t(9.35)), float(t(10.40))),
      (float(t(12.10)), float(t(13.70))), (float(t(23.40)), float(t(26.50))), (float(t(32.40)), float(t(34.00))),
      (float(t(36.20)), float(t(39.05)))]
page = build_page("Почему минус на минус даёт плюс", DUR, behind, front, beats, sounds, fg,
                  cta_at=float(t(63.52)), cta_small="раскладываю экзамен на атомы")
out = ROOT / "studio/IMG_3297/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")
print("ok", len(page.splitlines()), "строк, сдвиг", round(OFF, 3))

director = {
    "_note": "Минус на минус. Время по дублю.",
    "punches": [[float(t(2.08)), float(t(2.90)), 1.20, 0.10], [float(t(9.42)), float(t(10.20)), 1.20, 0.10],
                [float(t(32.48)), float(t(33.50)), 1.20, 0.10]],
    "text_fixes": {"73": "VII", "147": "CapCut", "184": "+", "193": "атомы"},
    "keep_case": ["России", "Индии", "Брахмагупта", "Декарт", "Путина", "CapCut", "ЕГЭ", "VII"],
    "accent_words": ["минус", "плюс", "долгом", "долг", "ложными"],
    "hide_captions": [[float(t(0.85)), float(t(2.95))], [float(t(9.40)), float(t(10.10))],
                      [float(t(32.45)), float(t(33.50))], [float(t(63.40)), DUR]],
}
(ROOT / "work/IMG_3297/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("director ok")
