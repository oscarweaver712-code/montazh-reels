#!/usr/bin/env python3
"""Набор для страниц графики HyperFrames: общий стиль, словарь движения, камера, субтитры.

Под каждый ролик режиссёр пишет только его элементы и удары, а каркас собирает build_page:
камера (две обёртки с одинаковым движением), окна видимости вырезанного человека, бегущие
субтитры, вспышка, финальная плашка и звук. Всё это уже прошло lint HyperFrames и проверку
глазами на трёх роликах — менять осторожно, по одному и с перепроверкой.

Формат сцены (fmt) и субтитры стиля (captions = styles.kit_captions) — необязательные:
без них страница собирается байт в байт как раньше (1080×1920, субтитры по слову).
Горизонталь, квадрат и 4:5 получают ту же разметку, пересчитанную под свой размер.
"""
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import formats  # noqa: E402

STYLE = '\n      @font-face { font-family: "Oswald"; src: url("assets/fonts/Oswald-Bold.ttf"); font-weight: 700; }\n      @font-face { font-family: "Manrope"; src: url("assets/fonts/Manrope-ExtraBold.ttf"); font-weight: 800; }\n      @font-face { font-family: "Cormorant"; src: url("assets/fonts/CormorantGaramond.ttf"); font-weight: 300 700; }\n      @font-face { font-family: "Cormorant"; src: url("assets/fonts/CormorantGaramond-Italic.ttf"); font-weight: 300 700; font-style: italic; }\n\n      :root {\n        --cream: #F2EBDD;\n        --red: #F0352C;\n        --ink: #141210;\n        --paper: #F1E9D8;\n      }\n      * { margin: 0; padding: 0; box-sizing: border-box; }\n      html, body { width: 1080px; height: 1920px; overflow: hidden; background: #000; }\n      #root { position: relative; width: 100%; height: 100%; overflow: hidden; font-family: "Manrope", sans-serif; }\n\n      /* камера: две обёртки с одинаковым движением — фон и вырезанный человек */\n      .cam { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }\n      .cam video { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover; }\n      #cam-fg { opacity: 0; }\n      .layer { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }\n\n      /* всё графическое скрыто, пока таймлайн не покажет */\n      .g { position: absolute; opacity: 0; }\n\n      /* подменённый фон: картина XVI века */\n      #plate { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden; opacity: 0; }\n      #plate-img { position: absolute; left: -200px; top: 0; width: 1480px; height: 1920px; object-fit: cover; object-position: 52% 50%;\n                   filter: sepia(0.45) saturate(0.85) brightness(0.58) contrast(1.08); }\n      #plate-vignette { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px;\n                        background: radial-gradient(ellipse at 50% 42%, rgba(0,0,0,0) 35%, rgba(0,0,0,0.75) 100%); }\n\n      /* крупная типографика за спиной */\n      .big { left: 0; width: 1080px; text-align: center; font-family: "Oswald"; font-weight: 700; text-transform: uppercase;\n             color: var(--cream); line-height: 0.92; letter-spacing: -0.01em; text-shadow: 0 12px 40px rgba(0,0,0,0.35); }\n      .red { color: var(--red); }\n      .lead { left: 0; width: 1080px; text-align: center; font-family: "Manrope"; font-weight: 800; font-size: 34px;\n              letter-spacing: 0.22em; text-transform: uppercase; color: var(--cream); text-shadow: 0 2px 12px rgba(0,0,0,0.6); }\n      .serif { font-family: "Cormorant"; font-weight: 700; }\n      #aeq-full span { display: inline-block; }\n      .bar { height: 118px; border-radius: 8px; background: var(--cream); box-shadow: 0 18px 50px rgba(0,0,0,0.45); }\n\n      /* бегущие субтитры: по слову-два на уровне груди, как в референсах */\n      .cap { position: absolute; left: 60px; width: 960px; top: 1150px; text-align: center; opacity: 0;\n             font-family: "Manrope"; font-weight: 800; font-size: 58px; line-height: 1.1; color: var(--cream);\n             text-shadow: 0 2px 4px rgba(0,0,0,0.55), 0 6px 24px rgba(0,0,0,0.5); }\n      .cap.accent { color: #FF4A3D; }\n\n      /* карточки-портреты */\n      .card { width: 300px; padding: 16px 16px 14px; background: var(--paper); border-radius: 6px;\n              box-shadow: 0 24px 60px rgba(0,0,0,0.55); }\n      .card .ph { width: 268px; height: 300px; overflow: hidden; }\n      .card img { display: block; width: 268px; height: 300px; object-fit: cover; object-position: 50% 25%; }\n      .card-name { margin-top: 12px; font-family: "Manrope"; font-weight: 800; font-size: 24px; letter-spacing: 0.06em;\n                   text-transform: uppercase; color: var(--ink); }\n      .card-sub { font-family: "Cormorant"; font-style: italic; font-weight: 600; font-size: 27px; color: #5A4E3C; }\n      .card-right { left: 744px; top: 150px; }\n      .card-left { left: 36px; top: 150px; }\n\n      /* штампы и стикеры */\n      .stamp { font-family: "Oswald"; font-weight: 700; text-transform: uppercase; color: var(--red);\n               border: 6px solid var(--red); border-radius: 10px; padding: 2px 18px; letter-spacing: 0.04em; }\n      .sticker { font-family: "Cormorant"; font-style: italic; font-weight: 700; color: var(--ink); background: var(--cream);\n                 border-radius: 40px; padding: 4px 26px 8px; box-shadow: 0 10px 30px rgba(0,0,0,0.45); }\n      .pill { font-family: "Manrope"; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; color: var(--cream);\n              background: rgba(16,14,12,0.82); border: 2px solid rgba(242,235,221,0.25); border-radius: 40px; padding: 10px 28px; }\n\n      /* документы снизу: страницы книги, формулы, бланк */\n      .doc { padding: 20px; background: #F6F1E4; border-radius: 8px; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }\n      .doc-cap { margin-top: 10px; text-align: center; font-family: "Cormorant"; font-style: italic; font-weight: 600;\n                 font-size: 30px; color: #4A3F30; }\n      .formula { font-family: "Cormorant"; font-weight: 600; font-size: 70px; color: var(--ink); text-align: center; line-height: 1.25;\n                  font-variant-numeric: lining-nums; }\n      .formula.small { font-size: 56px; }\n      .formula sub { font-size: 0.55em; }\n\n      .censor { left: 280px; top: 230px; width: 520px; height: 150px; border-radius: 18px; background: #0C0C0D;\n                display: flex; align-items: center; justify-content: center; gap: 22px; box-shadow: 0 20px 60px rgba(0,0,0,0.6); }\n      .censor span { font-family: "Oswald"; font-weight: 700; font-size: 86px; letter-spacing: 0.08em; color: var(--cream); }\n      .censor b { font-family: "Manrope"; font-weight: 800; font-size: 34px; color: #fff; background: var(--red);\n                  width: 84px; height: 84px; border-radius: 42px; display: flex; align-items: center; justify-content: center; }\n\n      .rows { left: 40px; width: 1000px; text-align: center; font-family: "Cormorant"; font-style: italic; font-weight: 600;\n              font-size: 50px; color: rgba(242,235,221,0.62); }\n\n      .ege { padding: 26px 30px 30px; background: #FBFBF8; border-radius: 10px; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }\n      .ege-head { font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.12em; text-transform: uppercase; color: #2B3A67; }\n      .ege-row { margin-top: 18px; display: flex; align-items: center; gap: 22px; }\n      .ege-label { font-family: "Manrope"; font-weight: 800; font-size: 34px; color: var(--ink); }\n      .cells { display: flex; }\n      .cells i { width: 82px; height: 104px; border: 3px solid #2B3A67; margin-left: -3px; display: flex; align-items: center;\n                 justify-content: center; font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 76px; color: #1F3FA8;\n                 font-variant-numeric: lining-nums; }\n\n      #flash { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; background: #fff; opacity: 0; }\n      .cta { padding: 34px 40px 40px; border-radius: 34px; background: rgba(12,12,14,0.86); border: 2px solid rgba(242,235,221,0.16);\n             box-shadow: 0 30px 80px rgba(0,0,0,0.6); }\n      .cta-big { font-family: "Oswald"; font-weight: 700; font-size: 104px; line-height: 0.95; text-transform: uppercase; color: var(--cream); }\n      .cta-small { margin-top: 14px; font-family: "Manrope"; font-weight: 800; font-size: 40px; color: rgba(242,235,221,0.85); }\n    ' + '      #plate { -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 50%, transparent 68%);\n               mask-image: linear-gradient(to bottom, #000 0%, #000 50%, transparent 68%); }\n      .eq-line { left: 0; width: 1080px; text-align: center; font-family: "Cormorant"; font-style: italic; font-weight: 700;\n                 font-size: 110px; color: var(--cream); font-variant-numeric: lining-nums; text-shadow: 0 6px 30px rgba(0,0,0,0.45); }\n      .letter { top: 150px; width: 230px; text-align: center; font-family: "Oswald"; font-weight: 700; font-size: 300px;\n                line-height: 0.95; color: var(--cream); text-shadow: 0 12px 40px rgba(0,0,0,0.35); }\n      .tale { left: 0; width: 1080px; text-align: center; font-family: "Cormorant"; font-weight: 700; color: var(--cream);\n              line-height: 0.95; text-shadow: 0 6px 30px rgba(0,0,0,0.7); }\n      #scan { position: absolute; left: 0; top: 0; width: 100%; height: 90px; opacity: 0;\n              background: linear-gradient(180deg, rgba(90,220,255,0) 0%, rgba(90,220,255,0.55) 50%, rgba(90,220,255,0) 100%); }\n      .diamond { width: 150px; height: 150px; }\n' + '      @font-face { font-family: "JBMono"; src: url("assets/fonts/JetBrainsMono.ttf"); font-weight: 100 800; }\n      .mono { font-family: "JBMono"; font-weight: 700; }\n      .glyph { text-align: center; line-height: 1; color: var(--cream); text-shadow: 0 12px 40px rgba(0,0,0,0.4); }\n      .dot { width: 150px; height: 150px; border-radius: 75px; background: var(--red); box-shadow: 0 16px 50px rgba(0,0,0,0.45); }\n      .label { font-family: "Manrope"; font-weight: 800; font-size: 32px; letter-spacing: 0.2em; text-transform: uppercase;\n               color: var(--cream); text-align: center; text-shadow: 0 2px 12px rgba(0,0,0,0.6); }\n      .notebook { padding: 30px 40px 26px; border-radius: 8px; box-shadow: 0 30px 80px rgba(0,0,0,0.6); background-color: #FBFBF6;\n                  background-image: linear-gradient(#C9DBF2 2px, transparent 2px), linear-gradient(90deg, #C9DBF2 2px, transparent 2px);\n                  background-size: 44px 44px; }\n      .legal { padding: 30px 40px 26px 90px; border-radius: 8px; box-shadow: 0 30px 80px rgba(0,0,0,0.6); background-color: #FFF4AE;\n               background-image: linear-gradient(90deg, transparent 64px, #E86A6A 64px, #E86A6A 67px, transparent 67px),\n                                 repeating-linear-gradient(#FFF4AE 0px, #FFF4AE 52px, #8FB0D8 52px, #8FB0D8 54px); }\n      .hand { font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 120px; color: #1F3FA8;\n              font-variant-numeric: lining-nums; line-height: 1.1; }\n      .note { font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.1em; text-transform: uppercase; color: #5B6B86; }\n      .code { padding: 34px 40px; border-radius: 18px; background: #16181D; border: 2px solid #2A2E37; box-shadow: 0 30px 80px rgba(0,0,0,0.6);\n              font-family: "JBMono"; font-weight: 600; font-size: 54px; color: #E6E6E6; }\n      .code .k { color: #FF7AB6; } .code .n { color: #9CDCFE; } .code .v { color: #F7C873; } .code .s { color: #F0352C; }\n      .code .c { color: #6B7385; font-size: 34px; }\n      .keys { display: flex; gap: 34px; }\n      .key { position: relative; width: 170px; height: 170px; border-radius: 26px; display: flex; align-items: center; justify-content: center;\n             background: linear-gradient(180deg, #F7F7F4, #D6D6D0); box-shadow: 0 10px 0 #A9A9A2, 0 26px 50px rgba(0,0,0,0.55);\n             font-family: "JBMono"; font-weight: 700; font-size: 104px; color: #23252B; }\n      .key .no { position: absolute; left: 18px; top: 80px; width: 134px; height: 12px; border-radius: 6px; background: var(--red); }\n      .key-glow { position: absolute; left: -16px; top: -16px; width: 202px; height: 202px; border-radius: 34px; border: 6px solid #4FE3E6; }\n      .paper { padding: 34px 44px 30px; border-radius: 8px; background: #F3EAD6; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }\n      .paper-text { font-family: "Cormorant"; font-style: italic; font-weight: 600; font-size: 52px; line-height: 1.2; color: #2A2219; }\n      .paper-sign { margin-top: 14px; text-align: right; font-family: "Cormorant"; font-weight: 700; font-size: 34px; color: #6A5A44; }\n      .xs { font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 96px; color: var(--cream); line-height: 1; }\n'

HELPERS = '      // ---------- словарь движения: всё входит И выходит движением, а не растворением ----------\n      const BLUR = (px) => `blur(${px}px)`;\n\n      // влёт со смазом: элемент прилетает размытым и встаёт в фокус\n      function enter(sel, t, o = {}) {\n        const from = { opacity: 0, scale: o.fromScale ?? 0.7, x: o.fromX ?? 0, y: o.fromY ?? 0, filter: BLUR(o.blur ?? 12) };\n        const to = { opacity: 1, scale: 1, x: 0, y: 0, filter: BLUR(0), duration: o.dur ?? 0.32, ease: o.ease ?? "back.out(1.7)" };\n        if (o.rot !== undefined || o.fromRot !== undefined) { from.rotation = o.fromRot ?? o.rot; to.rotation = o.rot ?? 0; }\n        tl.fromTo(sel, from, to, t);\n      }\n      // уход: улетает, сжимается и смазывается\n      function leave(sel, t, o = {}) {\n        const to = { opacity: 0, scale: o.scale ?? 0.82, x: o.x ?? 0, y: o.y ?? -40, filter: BLUR(o.blur ?? 12),\n                     duration: o.dur ?? 0.24, ease: o.ease ?? "power2.in" };\n        if (o.rot !== undefined) to.rotation = o.rot;\n        tl.to(sel, to, t);\n      }\n      // «впечатывание»: крупное слово или штамп бьёт в кадр с размаха\n      function slam(sel, t, o = {}) {\n        const from = { opacity: 0, scale: o.fromScale ?? 1.45, filter: BLUR(o.blur ?? 16) };\n        const to = { opacity: 1, scale: 1, filter: BLUR(0), duration: o.dur ?? 0.16, ease: "power4.out" };\n        if (o.rot !== undefined) { from.rotation = o.fromRot ?? o.rot; to.rotation = o.rot; }\n        tl.fromTo(sel, from, to, t);\n      }\n      function draw(sel, t, dur = 0.4) {\n        tl.fromTo(sel, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: dur, ease: "power1.inOut" }, t);\n      }\n      // портрет: вылет сбоку с поворотом, медленный наезд внутри картинки, улёт обратно\n      function card(sel, tIn, tOut, side) {\n        const s = side === "right" ? 1 : -1;\n        tl.fromTo(sel, { opacity: 0, x: 460 * s, rotation: 16 * s, filter: BLUR(14) },\n                  { opacity: 1, x: 0, rotation: 4 * s, filter: BLUR(0), duration: 0.45, ease: "power3.out" }, tIn);\n        tl.fromTo(`${sel} img`, { scale: 1 }, { scale: 1.12, duration: tOut - tIn + 0.3, ease: "none" }, tIn);\n        tl.to(sel, { opacity: 0, x: 460 * s, rotation: 18 * s, filter: BLUR(14), duration: 0.32, ease: "power2.in" }, tOut);\n      }\n      // документ снизу: выезжает с поворотом и уезжает вниз\n      function doc(sel, tIn, tOut, o = {}) {\n        tl.fromTo(sel, { opacity: 0, y: 560, rotation: o.fromRot ?? 7, filter: BLUR(12) },\n                  { opacity: 1, y: 0, rotation: o.rot ?? -2, filter: BLUR(0), duration: 0.42, ease: "power3.out" }, tIn);\n        if (tOut !== null) {\n          tl.to(sel, { opacity: 0, y: 520, rotation: (o.rot ?? -2) - 8, filter: BLUR(12), duration: 0.32, ease: "power2.in" }, tOut);\n        }\n      }\n      // белая вспышка на главном ударе\n      let flashes = 0;\n      function flash(t) {\n        tl.fromTo("#flash", { opacity: 0 }, { opacity: 0.38, duration: 0.04, ease: "none", immediateRender: flashes++ === 0 }, t);\n        tl.to("#flash", { opacity: 0, duration: 0.18, ease: "power1.out" }, t + 0.04);\n      }\n      function bars(sel, t, stagger = 0.06) {\n        tl.fromTo(sel, { opacity: 0, scaleX: 0, filter: BLUR(10) },\n                  { opacity: 1, scaleX: 1, filter: BLUR(0), duration: 0.2, ease: "expo.out", stagger }, t);\n      }\n\n      // ---------- бегущие субтитры ----------\n      const caps = document.getElementById("caps");\n      window.CAPTIONS.forEach((c) => {\n        const el = document.createElement("div");\n        el.className = "cap" + (c.accent ? " accent" : "");\n        el.textContent = c.text;\n        caps.appendChild(el);\n        // вход не длиннее самой вспышки: уход, сработавший посреди входа, в покадровом рендере\n        // проигрывает недоигравшему fromTo — и слово висит до конца ролика\n        tl.fromTo(el, { opacity: 0, y: 12, scale: 0.92, filter: BLUR(4) },\n                  { opacity: 1, y: 0, scale: 1, filter: BLUR(0), duration: Math.min(0.09, c.t1 - c.t0), ease: "power2.out" }, c.t0);\n        tl.set(el, { opacity: 0 }, c.t1);\n      });\n\n'

CTA_HTML = '        <div id="cta" class="g cta" style="left: 90px; top: 1130px; width: 900px;">\n          <div class="cta-big">Больше математики</div>\n          <div class="cta-small">смотри у меня в профиле — переходи</div>\n        </div>\n        <svg id="cta-arrow" class="g" viewBox="0 0 220 200" style="left: 70px; top: 1470px; width: 220px; height: 200px;">\n          <path id="arrow-path" d="M 190 20 C 150 90, 110 130, 40 160" fill="none" stroke="#F2EBDD" stroke-width="12"\n                stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />\n          <path id="arrow-head" d="M 40 160 L 92 168 M 40 160 L 66 116" fill="none" stroke="#F2EBDD" stroke-width="12" stroke-linecap="round" />\n        </svg>\n'

CTA_JS = '      tl.fromTo("#cta", { opacity: 0, y: 300, filter: BLUR(12) }, { opacity: 1, y: 0, filter: BLUR(0), duration: 0.42, ease: "power3.out" }, 58.40);\n      tl.set("#cta-arrow", { opacity: 1 }, 58.75);\n      draw("#arrow-path", 58.75, 0.35);\n      tl.fromTo("#arrow-head", { opacity: 0 }, { opacity: 1, duration: 0.1 }, 59.07);\n      tl.to("#cta", { scale: 1.03, duration: 0.6, ease: "sine.inOut", yoyo: true, repeat: 1 }, 59.4);\n\n'


def audio(sid: str, name: str, start: float, volume: float = 0.3,
          duration: float | None = None, fade_out: float | None = None) -> str:
    extra = (f' data-duration="{duration}"' if duration else "") + \
            (f' data-fade-out="{fade_out}"' if fade_out else "")
    return (f'      <audio id="sfx-{sid}" src="assets/sfx/{name}.mp3" data-start="{start:.2f}"'
            f'{extra} data-volume="{volume:.2f}"></audio>')


def card(cid: str, img: str, name: str, sub: str, side: str = "right") -> str:
    return (f'        <div id="{cid}" class="g card card-{side}">\n'
            f'          <div class="ph"><img src="assets/img/{img}" alt="" /></div>\n'
            f'          <div class="card-name">{name}</div>\n'
            f'          <div class="card-sub">{sub}</div>\n        </div>')


def doc_img(did: str, img: str, caption: str, left: int = 300, top: int = 1060, width: int = 480,
            height: int = 520, position: str = "50% 30%") -> str:
    inner = width - 32
    return (f'        <div id="{did}" class="g doc" style="left: {left}px; top: {top}px; width: {width}px; padding: 16px;">\n'
            f'          <div style="width: {inner}px; height: {height}px; overflow: hidden;"><img src="assets/img/{img}" alt="" '
            f'style="display: block; width: {inner}px; height: {height}px; object-fit: cover; object-position: {position};" /></div>\n'
            f'          <div class="doc-cap">{caption}</div>\n        </div>')


# Где стоят субтитры на сцене каждого формата: (left, width, top) для позиций стиля.
CAPTION_BOX = {
    "9:16": {"chest": (60, 960, 1150), "lower": (60, 960, 1370), "center": (60, 960, 880),
             "top": (60, 960, 250), "side": (70, 620, 1180)},
    "4:5": {"chest": (60, 960, 800), "lower": (60, 960, 1030), "center": (60, 960, 620),
            "top": (60, 960, 110), "side": (64, 620, 820)},
    "1:1": {"chest": (60, 960, 640), "lower": (60, 960, 880), "center": (60, 960, 480),
            "top": (60, 960, 80), "side": (64, 620, 640)},
    "16:9": {"chest": (260, 1400, 760), "lower": (260, 1400, 880), "center": (260, 1400, 470),
             "top": (260, 1400, 70), "side": (1040, 800, 330)},
}
CAPTION_SIZE = {"words": 58, "karaoke": 64, "phrase": 52, "sentence": 44}
FORMAT_SCALE = {"9:16": 1.0, "4:5": 0.92, "1:1": 0.86, "16:9": 0.86}
# Финальная плашка: (left, top) карточки и (left, top) стрелки
# В горизонтали лицо стоит по центру — плашка уходит в правую нижнюю часть, не на рот
# (проверено по кадрам IMG_3305 в 16:9: по центру она закрывала лицо).
CTA_AT = {"9:16": (90, 1130, 70, 1470), "4:5": (90, 700, 70, 1040), "1:1": (90, 470, 70, 810),
          "16:9": (1000, 560, 880, 870)}
EXTRA_FONTS = {"Montserrat": "Montserrat-ExtraBold.ttf", "Unbounded": "Unbounded-ExtraBold.ttf",
               "Rubik": "Rubik-Black.ttf", "Golos": "GolosText-Black.ttf", "Alumni": "AlumniSans-Black.ttf"}


def stage_style(fmt: str = "9:16") -> str:
    """Общий стиль под размер сцены. Для 9:16 — ровно прежний STYLE."""
    if fmt == "9:16":
        return STYLE
    width, height = formats.size(fmt)
    style = STYLE.replace("1480px", f"{width + 400}px")       # фон шире сцены — есть куда ехать
    style = style.replace("1080px", "\0W").replace("1920px", "\0H")
    style = style.replace("\0W", f"{width}px").replace("\0H", f"{height}px")
    left, cap_w, top = CAPTION_BOX[fmt]["chest"]
    return style + (f"      .rows {{ left: 40px; width: {width - 80}px; }}\n"
                    f"      .cap {{ left: {left}px; width: {cap_w}px; top: {top}px; }}\n"
                    f"      .card-right {{ left: {width - 336}px; }}\n"
                    f"      .censor {{ left: {(width - 520) // 2}px; }}\n")


def caption_css(caps: dict, fmt: str = "9:16") -> str:
    """Вид субтитров стиля: шрифт, размер, место, регистр, плашка."""
    left, cap_w, top = CAPTION_BOX[fmt][caps["position"]]
    size = round(CAPTION_SIZE.get(caps["mode"], 52) * float(caps.get("size", 1.0)) * FORMAT_SCALE[fmt])
    css = []
    family = caps.get("css_font", "Manrope")
    if family in EXTRA_FONTS:
        css.append(f'      @font-face {{ font-family: "{family}"; src: url("assets/fonts/{EXTRA_FONTS[family]}"); '
                   f'font-weight: {caps.get("font_weight", 800)}; }}')
    align = "left" if caps["position"] == "side" else "center"
    case = {"upper": "uppercase", "lower": "none", "natural": "none"}[caps.get("case", "lower")]
    css.append(f'      .cap {{ left: {left}px; width: {cap_w}px; top: {top}px; text-align: {align}; '
               f'font-family: "{family}"; font-weight: {caps.get("font_weight", 800)}; font-size: {size}px; '
               f'line-height: 1.15; color: {caps["color"]}; text-transform: {case}; }}')
    css.append(f'      .cap.accent {{ color: {caps["highlight"]}; }}')
    css.append('      .cap .w { display: inline-block; }')
    if caps.get("box"):
        dark_text = caps["color"].upper() in ("#111111", "#000000", "#141210")
        bg = "#FFFFFF" if dark_text else "rgba(12,12,14,0.78)"
        css.append(f'      .cap .box {{ display: inline-block; padding: 8px 24px 12px; border-radius: 16px; '
                   f'background: {bg}; box-shadow: 0 10px 30px rgba(0,0,0,0.25); }}')
        css.append('      .cap { text-shadow: none; }')
    return "\n".join(css) + "\n"


CAPTIONS_JS = HELPERS[HELPERS.index("      // ---------- бегущие субтитры ----------"):]


def caption_js(caps: dict) -> str:
    """Субтитры стиля: вход по анимации стиля, караоке-подсветка по словам.

    Правило против залипания то же, что в старом блоке: вход не длиннее самой вспышки.
    """
    enter = {
        "blur": 'tl.fromTo(el, { opacity: 0, y: 12, scale: 0.92, filter: BLUR(4) }, '
                '{ opacity: 1, y: 0, scale: 1, filter: BLUR(0), duration: d, ease: "power2.out" }, c.t0);',
        "pop": 'tl.fromTo(el, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: d, ease: "back.out(2.2)" }, c.t0);',
        "fade": 'tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: d, ease: "power1.out" }, c.t0);',
        "none": 'tl.set(el, { opacity: 1 }, c.t0);',
    }[caps.get("animation", "blur")]
    longest = {"blur": 0.09, "pop": 0.12, "fade": 0.14, "none": 0.0}[caps.get("animation", "blur")]
    box = "true" if caps.get("box") else "false"
    return f'''      // ---------- бегущие субтитры: {caps["mode"]}, {caps.get("animation", "blur")} ----------
      const caps = document.getElementById("caps");
      const CAP_BASE = "{caps["color"]}", CAP_HL = "{caps["highlight"]}";
      window.CAPTIONS.forEach((c) => {{
        const el = document.createElement("div");
        el.className = "cap" + (c.accent ? " accent" : "");
        let inner = el;
        if ({box}) {{ inner = document.createElement("span"); inner.className = "box"; el.appendChild(inner); }}
        const spans = [];
        if (c.words) {{
          c.words.forEach((w, k) => {{
            const s = document.createElement("span");
            s.className = "w";
            s.textContent = w.text;
            inner.appendChild(s);
            if (k < c.words.length - 1) inner.appendChild(document.createTextNode(" "));
            spans.push(s);
          }});
        }} else {{
          inner.textContent = c.text;
        }}
        caps.appendChild(el);
        // вход не длиннее самой вспышки: уход посреди входа в покадровом рендере залипает
        const d = Math.min({longest}, c.t1 - c.t0);
        {enter}
        tl.set(el, {{ opacity: 0 }}, c.t1);
        (c.words || []).forEach((w, k) => {{
          // только цвет: увеличенное слово наезжает на пробел и склеивается с соседним
          tl.set(spans[k], {{ color: CAP_HL }}, Math.max(c.t0, w.t0));
          const next = k + 1 < c.words.length ? c.words[k + 1].t0 : c.t1;
          if (next < c.t1) tl.set(spans[k], {{ color: CAP_BASE }}, next);
        }});
      }});

'''


def build_page(title: str, duration: float, behind: str, front: str, beats: str, sounds: list,
               fg_windows: list, cta_at: float, plate_img: str | None = None,
               plate_style: str = "", extra_css: str = "", cta_small: str = "смотри у меня в профиле",
               fmt: str = "9:16", captions: dict | None = None, cutout: bool = True) -> str:
    """Собирает index.html. Время — по дублю (aroll), секунды.

    fmt — формат сцены (formats.py), captions — субтитры стиля (styles.kit_captions).
    cutout=False — без слоя вырезанного человека: стилю без текста за спиной не нужна
    маска (matte.py — самые долгие 4 минуты подготовки).
    """
    d = f"{duration:.3f}"
    width, height = formats.size(fmt)
    plate = ""
    if plate_img:
        plate = (f'      <div id="plate">\n        <img id="plate-img" src="assets/img/{plate_img}" alt="" style="{plate_style}" />\n'
                 f'        <div id="plate-vignette"></div>\n      </div>\n')
    cta_html = CTA_HTML.replace("смотри у меня в профиле — переходи", cta_small)
    if fmt != "9:16":
        cl, ct, al, at = CTA_AT[fmt]
        cta_html = (cta_html.replace("left: 90px; top: 1130px;", f"left: {cl}px; top: {ct}px;")
                    .replace("left: 70px; top: 1470px;", f"left: {al}px; top: {at}px;"))
    style_css = stage_style(fmt) + (caption_css(captions, fmt) if captions else "")
    if not cutout and fg_windows:
        raise ValueError("Окна вырезки (fg_windows) без слоя вырезки: передай cutout=True и сделай matte.py")
    helpers = HELPERS if not captions else HELPERS.replace(CAPTIONS_JS, caption_js(captions))
    cutout_html = ('      <div id="cam-fg" class="cam">\n'
                   '        <video id="cutout" class="clip" src="assets/cutout.webm" muted playsinline\n'
                   f'               data-start="0" data-duration="{d}" data-track-index="1"></video>\n'
                   '      </div>') if cutout else '      <div id="cam-fg" class="cam"></div>' 
    t = cta_at
    cta_js = (CTA_JS.replace("58.40", f"{t:.2f}").replace("58.75", f"{t + 0.35:.2f}")
              .replace("59.07", f"{t + 0.67:.2f}").replace("59.4", f"{t + 1.0:.2f}"))
    windows = ", ".join(f"[{a:.2f}, {b:.2f}]" for a, b in fg_windows)
    return f'''<!doctype html>
<html lang="ru" data-resolution="{formats.get(fmt)["resolution"]}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={width}, height={height}" />
    <title>{title}</title>
    <script src="assets/gsap.min.js"></script>
    <script src="camera.js"></script>
    <script src="captions.js"></script>
    <style>{style_css}{extra_css}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{d}" data-width="{width}" data-height="{height}">
      <div id="cam-bg" class="cam">
        <video id="aroll" class="clip" src="assets/aroll.mp4" playsinline data-has-audio="true"
               data-start="0" data-duration="{d}" data-track-index="0"></video>
      </div>
{plate}      <div id="behind" class="layer">
{behind}
      </div>
{cutout_html}
      <div id="front" class="layer">
        <div id="caps"></div>
{front}
{cta_html}        <div id="flash"></div>
      </div>
{chr(10).join(sounds)}
      <audio id="sfx-cta" src="assets/sfx/pop.mp3" data-start="{t:.2f}" data-volume="0.40"></audio>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      const cam = window.CAMERA, step = 1 / window.CAMERA_FPS;
      tl.set(".cam", {{ transformOrigin: "0 0", x: cam[0][0], y: cam[0][1], scale: cam[0][2] }}, 0);
      tl.to(".cam", {{
        keyframes: cam.slice(1).map(([x, y, s]) => ({{ x, y, scale: s, duration: step, ease: "none" }})),
      }}, 0);
      [{windows}]
        .forEach(([a, b]) => {{ tl.set("#cam-fg", {{ opacity: 1 }}, a); tl.set("#cam-fg", {{ opacity: 0 }}, b); }});

{helpers}{beats}
{cta_js}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
'''


class Take:
    """Шкала дубля: секунды и номера слов исходника → дубль, с учётом вырезов (drop).

    Раскладку ударов удобно писать по таймингам исходника — так её можно готовить,
    пока дубль ещё считается, а сдвиг начала и вырезы учтутся сами.
    """

    def __init__(self, stem: str, variant: str | None = None):
        import json
        from pathlib import Path
        work = Path(__file__).resolve().parents[1] / "work"
        meta = json.loads((work / stem / "aroll.json").read_text(encoding="utf-8"))
        self.segments = meta["segments"]
        self.duration = meta["duration"]
        self.fmt = meta.get("format") or "9:16"         # формат сцены для build_page(fmt=…)
        # Стиль брифа (или варианта A/B) — для build_page(captions=…). Нет брифа — None:
        # субтитры как раньше. Страница варианта пишется в studio/<имя>--<стиль>/.
        from compose import project_name, ruling_style
        import styles
        self.style = ruling_style(stem, variant)
        self.captions = styles.kit_captions(self.style) if self.style else None
        self.project = project_name(stem, variant)
        self.src_words = json.loads((work / f"{stem}.words.json").read_text(encoding="utf-8"))["words"]
        self.words = json.loads((work / stem / "aroll.words.json").read_text(encoding="utf-8"))["words"]

    def t(self, x: float) -> float:
        """Секунда исходника → секунда дубля. Момент внутри выреза — громкая ошибка."""
        acc = 0.0
        for k, (s, e) in enumerate(self.segments):
            # удар чуть раньше начала дубля — на его начало; после выреза куски стоят на
            # сетке кадров, и точка склейки из edit.json может не дотянуть до них на кадр
            lo = s - (0.4 if k == 0 else 0.04)
            if lo <= x <= e + 0.05:
                return round(acc + max(0.0, x - s), 2)
            acc += e - s
        raise ValueError(f"{x:.2f} с исходника нет в дубле (вырезано или за краем)")

    def idx(self, i: int) -> int:
        """Номер слова исходника → номер в aroll.words.json (для text_fixes)."""
        w = self.src_words[i]
        ta = self.t(w["start"])
        j = min(range(len(self.words)), key=lambda k: abs(self.words[k]["start"] - ta))
        if abs(self.words[j]["start"] - ta) > 0.06 or self.words[j]["word"] != w["word"]:
            raise ValueError(f"Слово [{i}] «{w['word']}» не нашлось в дубле — оно вырезано?")
        return j

    def fixes(self, by_src: dict) -> dict:
        """text_fixes по номерам исходника → по номерам дубля."""
        return {str(self.idx(int(i))): v for i, v in by_src.items()}


def keyword_card(word: str, label: str, note: str, top: int = 1250, placeholder: str = "Добавьте комментарий…",
                 width: int = 1080) -> str:
    """Плашка «кодовое слово»: поле ввода, в котором печатается слово. Пара — keyword_beats.

    width — ширина сцены (1920 для горизонтали): поле встаёт по центру.
    """
    letters = "".join(f'<span class="kw-ch" style="opacity: 0;">{ch}</span>' for ch in word)
    return f'''        <div id="kw-label" class="g pill" style="left: 0; width: {width}px; text-align: center; top: {top - 70}px; background: none; border: none; font-size: 40px;">{label}</div>
        <div id="kw" class="g" style="left: {(width - 920) // 2}px; top: {top}px; width: 920px; height: 140px; border-radius: 70px; background: rgba(22,22,26,0.94); border: 2px solid rgba(242,235,221,0.22);">
          <div style="position: absolute; left: 26px; top: 28px; width: 84px; height: 84px; border-radius: 42px; background: linear-gradient(135deg, #F5B82E, #F0352C 60%, #A23BD1);"></div>
          <div id="kw-ph" style="position: absolute; left: 136px; top: 44px; font-family: 'Manrope'; font-weight: 800; font-size: 40px; color: rgba(242,235,221,0.38);">{placeholder}</div>
          <div style="position: absolute; left: 136px; top: 30px; font-family: 'Oswald'; font-weight: 700; font-size: 74px; letter-spacing: 0.04em; color: var(--cream); text-transform: uppercase; line-height: 1.1;">{letters}</div>
          <svg viewBox="0 0 60 60" style="position: absolute; right: 36px; top: 40px; width: 60px; height: 60px;">
            <path d="M 6 30 L 54 8 L 40 54 L 30 34 Z" fill="none" stroke="#F2EBDD" stroke-width="5" stroke-linejoin="round" />
          </svg>
        </div>
        <div id="kw-note" class="g sticker" style="left: 0; width: {width}px; text-align: center; top: {top + 175}px; background: none; box-shadow: none; color: var(--cream); font-size: 54px;">{note}</div>'''


def keyword_beats(t_in: float, t_type: float, t_note: float, n_letters: int, t_cta_out: float | None = None) -> str:
    """Анимация для keyword_card: влёт, печать по буквам, подпись. Финальную плашку убирает до влёта."""
    out = []
    if t_cta_out is not None:
        out.append(f'      leave(["#cta", "#cta-arrow"], {t_cta_out:.2f}, {{ y: 80 }});')
    out.append(f'      enter("#kw-label", {t_in:.2f}, {{ fromScale: 0.85, dur: 0.25 }});')
    out.append(f'      enter("#kw", {t_in + 0.06:.2f}, {{ fromY: 160, fromScale: 0.9, dur: 0.4, ease: "power3.out" }});')
    out.append(f'      tl.to("#kw-ph", {{ opacity: 0, duration: 0.05 }}, {t_type - 0.02:.2f});')
    out.append(f'      tl.to("#kw .kw-ch", {{ opacity: 1, duration: 0.02, stagger: 0.06 }}, {t_type:.2f});')
    out.append(f'      enter("#kw-note", {t_note:.2f}, {{ fromScale: 0.8, dur: 0.3 }});')
    return "\n".join(out)
