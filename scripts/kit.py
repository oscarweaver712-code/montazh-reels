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
import functools as _functools
import json as _json
import re as _re
import sys as _sys
from collections import Counter as _Counter
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import formats  # noqa: E402

STYLE = '\n      @font-face { font-family: "Oswald"; src: url("assets/fonts/Oswald-Bold.ttf"); font-weight: 700; }\n      @font-face { font-family: "Manrope"; src: url("assets/fonts/Manrope-ExtraBold.ttf"); font-weight: 800; }\n      @font-face { font-family: "Cormorant"; src: url("assets/fonts/CormorantGaramond.ttf"); font-weight: 300 700; }\n      @font-face { font-family: "Cormorant"; src: url("assets/fonts/CormorantGaramond-Italic.ttf"); font-weight: 300 700; font-style: italic; }\n\n      :root {\n        --cream: #F2EBDD;\n        --red: #F0352C;\n        --ink: #141210;\n        --paper: #F1E9D8;\n      }\n      * { margin: 0; padding: 0; box-sizing: border-box; }\n      html, body { width: 1080px; height: 1920px; overflow: hidden; background: #000; }\n      #root { position: relative; width: 100%; height: 100%; overflow: hidden; font-family: "Manrope", sans-serif; }\n\n      /* камера: две обёртки с одинаковым движением — фон и вырезанный человек */\n      .cam { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }\n      .cam video { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover; }\n      #cam-fg { opacity: 0; }\n      .layer { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }\n\n      /* всё графическое скрыто, пока таймлайн не покажет */\n      .g { position: absolute; opacity: 0; }\n\n      /* подменённый фон: картина XVI века */\n      #plate { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden; opacity: 0; }\n      #plate-img { position: absolute; left: -200px; top: 0; width: 1480px; height: 1920px; object-fit: cover; object-position: 52% 50%;\n                   filter: sepia(0.45) saturate(0.85) brightness(0.58) contrast(1.08); }\n      #plate-vignette { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px;\n                        background: radial-gradient(ellipse at 50% 42%, rgba(0,0,0,0) 35%, rgba(0,0,0,0.75) 100%); }\n\n      /* крупная типографика за спиной */\n      .big { left: 0; width: 1080px; text-align: center; font-family: "Oswald"; font-weight: 700; text-transform: uppercase;\n             color: var(--cream); line-height: 0.92; letter-spacing: -0.01em; text-shadow: 0 12px 40px rgba(0,0,0,0.35); }\n      .red { color: var(--red); }\n      .lead { left: 0; width: 1080px; text-align: center; font-family: "Manrope"; font-weight: 800; font-size: 34px;\n              letter-spacing: 0.22em; text-transform: uppercase; color: var(--cream); text-shadow: 0 2px 12px rgba(0,0,0,0.6); }\n      .serif { font-family: "Cormorant"; font-weight: 700; }\n      #aeq-full span { display: inline-block; }\n      .bar { height: 118px; border-radius: 8px; background: var(--cream); box-shadow: 0 18px 50px rgba(0,0,0,0.45); }\n\n      /* бегущие субтитры: по слову-два на уровне груди, как в референсах */\n      .cap { position: absolute; left: 245px; width: 590px; top: 1150px; text-align: center; opacity: 0;\n             font-family: "Manrope"; font-weight: 800; font-size: 58px; line-height: 1.1; color: var(--cream);\n             text-shadow: 0 2px 4px rgba(0,0,0,0.55), 0 6px 24px rgba(0,0,0,0.5); }\n      .cap.accent { color: #FF4A3D; }\n\n      /* карточки-портреты */\n      .card { width: 300px; padding: 16px 16px 14px; background: var(--paper); border-radius: 6px;\n              box-shadow: 0 24px 60px rgba(0,0,0,0.55); }\n      .card .ph { width: 268px; height: 300px; overflow: hidden; }\n      .card img { display: block; width: 268px; height: 300px; object-fit: cover; object-position: 50% 25%; }\n      .card-name { margin-top: 12px; font-family: "Manrope"; font-weight: 800; font-size: 24px; letter-spacing: 0.06em;\n                   text-transform: uppercase; color: var(--ink); }\n      .card-sub { font-family: "Cormorant"; font-style: italic; font-weight: 600; font-size: 27px; color: #5A4E3C; }\n      .card-right { left: 660px; top: 270px; }\n      .card-left { left: 120px; top: 270px; }\n\n      /* штампы и стикеры */\n      .stamp { font-family: "Oswald"; font-weight: 700; text-transform: uppercase; color: var(--red);\n               border: 6px solid var(--red); border-radius: 10px; padding: 2px 18px; letter-spacing: 0.04em; }\n      .sticker { font-family: "Cormorant"; font-style: italic; font-weight: 700; color: var(--ink); background: var(--cream);\n                 border-radius: 40px; padding: 4px 26px 8px; box-shadow: 0 10px 30px rgba(0,0,0,0.45); }\n      .pill { font-family: "Manrope"; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; color: var(--cream);\n              background: rgba(16,14,12,0.82); border: 2px solid rgba(242,235,221,0.25); border-radius: 40px; padding: 10px 28px; }\n\n      /* документы снизу: страницы книги, формулы, бланк */\n      .doc { padding: 20px; background: #F6F1E4; border-radius: 8px; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }\n      .doc-cap { margin-top: 10px; text-align: center; font-family: "Cormorant"; font-style: italic; font-weight: 600;\n                 font-size: 30px; color: #4A3F30; }\n      .formula { font-family: "Cormorant"; font-weight: 600; font-size: 70px; color: var(--ink); text-align: center; line-height: 1.25;\n                  font-variant-numeric: lining-nums; }\n      .formula.small { font-size: 56px; }\n      .formula sub { font-size: 0.55em; }\n\n      .censor { left: 280px; top: 230px; width: 520px; height: 150px; border-radius: 18px; background: #0C0C0D;\n                display: flex; align-items: center; justify-content: center; gap: 22px; box-shadow: 0 20px 60px rgba(0,0,0,0.6); }\n      .censor span { font-family: "Oswald"; font-weight: 700; font-size: 86px; letter-spacing: 0.08em; color: var(--cream); }\n      .censor b { font-family: "Manrope"; font-weight: 800; font-size: 34px; color: #fff; background: var(--red);\n                  width: 84px; height: 84px; border-radius: 42px; display: flex; align-items: center; justify-content: center; }\n\n      .rows { left: 40px; width: 1000px; text-align: center; font-family: "Cormorant"; font-style: italic; font-weight: 600;\n              font-size: 50px; color: rgba(242,235,221,0.62); }\n\n      .ege { padding: 26px 30px 30px; background: #FBFBF8; border-radius: 10px; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }\n      .ege-head { font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.12em; text-transform: uppercase; color: #2B3A67; }\n      .ege-row { margin-top: 18px; display: flex; align-items: center; gap: 22px; }\n      .ege-label { font-family: "Manrope"; font-weight: 800; font-size: 34px; color: var(--ink); }\n      .cells { display: flex; }\n      .cells i { width: 82px; height: 104px; border: 3px solid #2B3A67; margin-left: -3px; display: flex; align-items: center;\n                 justify-content: center; font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 76px; color: #1F3FA8;\n                 font-variant-numeric: lining-nums; }\n\n      #flash { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; background: #fff; opacity: 0; }\n      .cta { padding: 34px 40px 40px; border-radius: 34px; background: rgba(12,12,14,0.86); border: 2px solid rgba(242,235,221,0.16);\n             box-shadow: 0 30px 80px rgba(0,0,0,0.6); }\n      .cta-big { font-family: "Oswald"; font-weight: 700; font-size: 94px; line-height: 0.95; text-transform: uppercase; color: var(--cream); }\n      .cta-small { margin-top: 14px; font-family: "Manrope"; font-weight: 800; font-size: 40px; color: rgba(242,235,221,0.85); }\n    ' + '      #plate { -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 50%, transparent 68%);\n               mask-image: linear-gradient(to bottom, #000 0%, #000 50%, transparent 68%); }\n      .eq-line { left: 0; width: 1080px; text-align: center; font-family: "Cormorant"; font-style: italic; font-weight: 700;\n                 font-size: 110px; color: var(--cream); font-variant-numeric: lining-nums; text-shadow: 0 6px 30px rgba(0,0,0,0.45); }\n      .letter { top: 150px; width: 230px; text-align: center; font-family: "Oswald"; font-weight: 700; font-size: 300px;\n                line-height: 0.95; color: var(--cream); text-shadow: 0 12px 40px rgba(0,0,0,0.35); }\n      .tale { left: 0; width: 1080px; text-align: center; font-family: "Cormorant"; font-weight: 700; color: var(--cream);\n              line-height: 0.95; text-shadow: 0 6px 30px rgba(0,0,0,0.7); }\n      #scan { position: absolute; left: 0; top: 0; width: 100%; height: 90px; opacity: 0;\n              background: linear-gradient(180deg, rgba(90,220,255,0) 0%, rgba(90,220,255,0.55) 50%, rgba(90,220,255,0) 100%); }\n      .diamond { width: 150px; height: 150px; }\n' + '      @font-face { font-family: "JBMono"; src: url("assets/fonts/JetBrainsMono.ttf"); font-weight: 100 800; }\n      .mono { font-family: "JBMono"; font-weight: 700; }\n      .glyph { text-align: center; line-height: 1; color: var(--cream); text-shadow: 0 12px 40px rgba(0,0,0,0.4); }\n      .dot { width: 150px; height: 150px; border-radius: 75px; background: var(--red); box-shadow: 0 16px 50px rgba(0,0,0,0.45); }\n      .label { font-family: "Manrope"; font-weight: 800; font-size: 32px; letter-spacing: 0.2em; text-transform: uppercase;\n               color: var(--cream); text-align: center; text-shadow: 0 2px 12px rgba(0,0,0,0.6); }\n      .notebook { padding: 30px 40px 26px; border-radius: 8px; box-shadow: 0 30px 80px rgba(0,0,0,0.6); background-color: #FBFBF6;\n                  background-image: linear-gradient(#C9DBF2 2px, transparent 2px), linear-gradient(90deg, #C9DBF2 2px, transparent 2px);\n                  background-size: 44px 44px; }\n      .legal { padding: 30px 40px 26px 90px; border-radius: 8px; box-shadow: 0 30px 80px rgba(0,0,0,0.6); background-color: #FFF4AE;\n               background-image: linear-gradient(90deg, transparent 64px, #E86A6A 64px, #E86A6A 67px, transparent 67px),\n                                 repeating-linear-gradient(#FFF4AE 0px, #FFF4AE 52px, #8FB0D8 52px, #8FB0D8 54px); }\n      .hand { font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 120px; color: #1F3FA8;\n              font-variant-numeric: lining-nums; line-height: 1.1; }\n      .note { font-family: "Manrope"; font-weight: 800; font-size: 26px; letter-spacing: 0.1em; text-transform: uppercase; color: #5B6B86; }\n      .code { padding: 34px 40px; border-radius: 18px; background: #16181D; border: 2px solid #2A2E37; box-shadow: 0 30px 80px rgba(0,0,0,0.6);\n              font-family: "JBMono"; font-weight: 600; font-size: 54px; color: #E6E6E6; }\n      .code .k { color: #FF7AB6; } .code .n { color: #9CDCFE; } .code .v { color: #F7C873; } .code .s { color: #F0352C; }\n      .code .c { color: #6B7385; font-size: 34px; }\n      .keys { display: flex; gap: 34px; }\n      .key { position: relative; width: 170px; height: 170px; border-radius: 26px; display: flex; align-items: center; justify-content: center;\n             background: linear-gradient(180deg, #F7F7F4, #D6D6D0); box-shadow: 0 10px 0 #A9A9A2, 0 26px 50px rgba(0,0,0,0.55);\n             font-family: "JBMono"; font-weight: 700; font-size: 104px; color: #23252B; }\n      .key .no { position: absolute; left: 18px; top: 80px; width: 134px; height: 12px; border-radius: 6px; background: var(--red); }\n      .key-glow { position: absolute; left: -16px; top: -16px; width: 202px; height: 202px; border-radius: 34px; border: 6px solid #4FE3E6; }\n      .paper { padding: 34px 44px 30px; border-radius: 8px; background: #F3EAD6; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }\n      .paper-text { font-family: "Cormorant"; font-style: italic; font-weight: 600; font-size: 52px; line-height: 1.2; color: #2A2219; }\n      .paper-sign { margin-top: 14px; text-align: right; font-family: "Cormorant"; font-weight: 700; font-size: 34px; color: #6A5A44; }\n      .xs { font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 96px; color: var(--cream); line-height: 1; }\n'

HELPERS = '      // ---------- словарь движения: всё входит И выходит движением, а не растворением ----------\n      const BLUR = (px) => `blur(${px}px)`;\n\n      // влёт со смазом: элемент прилетает размытым и встаёт в фокус\n      function enter(sel, t, o = {}) {\n        const from = { opacity: 0, scale: o.fromScale ?? 0.7, x: o.fromX ?? 0, y: o.fromY ?? 0, filter: BLUR(o.blur ?? 12) };\n        const to = { opacity: 1, scale: 1, x: 0, y: 0, filter: BLUR(0), duration: o.dur ?? 0.32, ease: o.ease ?? "back.out(1.7)" };\n        if (o.rot !== undefined || o.fromRot !== undefined) { from.rotation = o.fromRot ?? o.rot; to.rotation = o.rot ?? 0; }\n        tl.fromTo(sel, from, to, t);\n      }\n      // уход: улетает, сжимается и смазывается\n      function leave(sel, t, o = {}) {\n        const to = { opacity: 0, scale: o.scale ?? 0.82, x: o.x ?? 0, y: o.y ?? -40, filter: BLUR(o.blur ?? 12),\n                     duration: o.dur ?? 0.24, ease: o.ease ?? "power2.in" };\n        if (o.rot !== undefined) to.rotation = o.rot;\n        tl.to(sel, to, t);\n      }\n      // «впечатывание»: крупное слово или штамп бьёт в кадр с размаха\n      function slam(sel, t, o = {}) {\n        const from = { opacity: 0, scale: o.fromScale ?? 1.45, filter: BLUR(o.blur ?? 16) };\n        const to = { opacity: 1, scale: 1, filter: BLUR(0), duration: o.dur ?? 0.16, ease: "power4.out" };\n        if (o.rot !== undefined) { from.rotation = o.fromRot ?? o.rot; to.rotation = o.rot; }\n        tl.fromTo(sel, from, to, t);\n      }\n      function draw(sel, t, dur = 0.4) {\n        tl.fromTo(sel, { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: dur, ease: "power1.inOut" }, t);\n      }\n      // портрет: вылет сбоку с поворотом, медленный наезд внутри картинки, улёт обратно\n      function card(sel, tIn, tOut, side) {\n        const s = side === "right" ? 1 : -1;\n        tl.fromTo(sel, { opacity: 0, x: 460 * s, rotation: 16 * s, filter: BLUR(14) },\n                  { opacity: 1, x: 0, rotation: 4 * s, filter: BLUR(0), duration: 0.45, ease: "power3.out" }, tIn);\n        tl.fromTo(`${sel} img`, { scale: 1 }, { scale: 1.12, duration: tOut - tIn + 0.3, ease: "none" }, tIn);\n        tl.to(sel, { opacity: 0, x: 460 * s, rotation: 18 * s, filter: BLUR(14), duration: 0.32, ease: "power2.in" }, tOut);\n      }\n      // документ снизу: выезжает с поворотом и уезжает вниз\n      function doc(sel, tIn, tOut, o = {}) {\n        tl.fromTo(sel, { opacity: 0, y: 560, rotation: o.fromRot ?? 7, filter: BLUR(12) },\n                  { opacity: 1, y: 0, rotation: o.rot ?? -2, filter: BLUR(0), duration: 0.42, ease: "power3.out" }, tIn);\n        if (tOut !== null) {\n          tl.to(sel, { opacity: 0, y: 520, rotation: (o.rot ?? -2) - 8, filter: BLUR(12), duration: 0.32, ease: "power2.in" }, tOut);\n        }\n      }\n      // белая вспышка на главном ударе\n      let flashes = 0;\n      function flash(t) {\n        tl.fromTo("#flash", { opacity: 0 }, { opacity: 0.38, duration: 0.04, ease: "none", immediateRender: flashes++ === 0 }, t);\n        tl.to("#flash", { opacity: 0, duration: 0.18, ease: "power1.out" }, t + 0.04);\n      }\n      // склейка (Валера 15.10: «склейки не спрятаны за переходами вспышками»): кадр приходит смазанным\n      // и наводится за 5 кадров, поверх — вспышка в 3 кадра; крупность бьёт наезд Take.splice_punches.\n      // Надписи через склейку не висят — уходят до неё, новая влетает на ней (verify_page).\n      function splice(t) {\n        tl.fromTo("#flash", { opacity: 0 }, { opacity: 0.55, duration: 0.033, ease: "none", immediateRender: flashes++ === 0 }, t - 0.033);\n        tl.to("#flash", { opacity: 0, duration: 0.16, ease: "power1.out" }, t);\n        tl.fromTo(".cam", { filter: BLUR(16) }, { filter: BLUR(0), duration: 0.17, ease: "power2.out", immediateRender: false }, t);\n      }\n      // смена плана как у риелтора (15.10): кадр перескакивает крупнее с коротким смазом, без вспышки\n      function whip(t) {\n        tl.fromTo(".cam", { filter: BLUR(9) }, { filter: BLUR(0), duration: 0.12, ease: "power2.out", immediateRender: false }, t);\n      }\n      function bars(sel, t, stagger = 0.06) {\n        tl.fromTo(sel, { opacity: 0, scaleX: 0, filter: BLUR(10) },\n                  { opacity: 1, scaleX: 1, filter: BLUR(0), duration: 0.2, ease: "expo.out", stagger }, t);\n      }\n\n      // ---------- бегущие субтитры ----------\n      const caps = document.getElementById("caps");\n      window.CAPTIONS.forEach((c) => {\n        const el = document.createElement("div");\n        el.className = "cap" + (c.accent ? " accent" : "");\n        el.textContent = c.text;\n        if (c.y !== undefined) el.style.top = c.y + "px";\n        caps.appendChild(el);\n        // вход не длиннее самой вспышки: уход, сработавший посреди входа, в покадровом рендере\n        // проигрывает недоигравшему fromTo — и слово висит до конца ролика\n        tl.fromTo(el, { opacity: 0, y: 12, scale: 0.92, filter: BLUR(4) },\n                  { opacity: 1, y: 0, scale: 1, filter: BLUR(0), duration: Math.min(0.09, c.t1 - c.t0), ease: "power2.out" }, c.t0);\n        tl.set(el, { opacity: 0 }, c.t1);\n      });\n\n'

CTA_HTML = '        <div id="cta" class="g cta" data-hold="призыв держится до конца ролика — так задумано" data-safe="плашка в конце — ниже лица, показывает на ник автора" style="left: 245px; top: 1170px; width: 590px;">\n          <div class="cta-big">Больше математики</div>\n          <div class="cta-small">смотри у меня в профиле — переходи</div>\n        </div>\n        <svg id="cta-arrow" class="g" data-hold="призыв держится до конца ролика — так задумано" viewBox="0 0 220 200" style="left: 70px; top: 1480px; width: 220px; height: 200px;">\n          <path id="arrow-path" d="M 190 20 C 150 90, 110 130, 40 160" fill="none" stroke="#F2EBDD" stroke-width="12"\n                stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />\n          <path id="arrow-head" d="M 40 160 L 92 168 M 40 160 L 66 116" fill="none" stroke="#F2EBDD" stroke-width="12" stroke-linecap="round" />\n        </svg>\n'

CTA_JS = '      tl.fromTo("#cta", { opacity: 0, y: 300, filter: BLUR(12) }, { opacity: 1, y: 0, filter: BLUR(0), duration: 0.42, ease: "power3.out" }, 58.40);\n      tl.set("#cta-arrow", { opacity: 1 }, 58.75);\n      draw("#arrow-path", 58.75, 0.35);\n      tl.fromTo("#arrow-head", { opacity: 0 }, { opacity: 1, duration: 0.1 }, 59.07);\n      tl.to("#cta", { scale: 1.03, duration: 0.6, ease: "sine.inOut", yoyo: true, repeat: 1 }, 59.4);\n\n'


# Звуки (правила Валеры, 12.10.2026: «звуки слишком громкие», «одинаковые звуки подряд»).
# Файлы записаны с разницей в 30+ дБ: басовый удар — −2 LUFS, щелчок — −26. С общей громкостью
# 0.36 удар в IMG_1803 звучал громче голоса. Теперь каждый звук приводится к одной норме по
# замеру файла (presets/sfx/manifest.json → loudness_m): уровень 1 — на ~11 дБ тише голоса
# (−14 LUFS), громче нормы сделать нельзя.
SFX_DIR = _Path(__file__).resolve().parent.parent / "presets" / "sfx"
SFX_TARGET = -25.0       # LUFS, пиковая мгновенная громкость звука при уровне 1
SFX_MIN_GAP = 1.0        # с между звуками: ближе — сливаются в кашу
SFX_MAX_USES = 2         # один и тот же файл — не больше двух раз за ролик
_AUDIO_TAG = _re.compile(r'<audio id="sfx-[^"]*" src="assets/sfx/([\w.\-]+)\.mp3" data-start="([\d.]+)"')


@_functools.lru_cache(maxsize=1)
def sfx_manifest() -> dict:
    return _json.loads((SFX_DIR / "manifest.json").read_text(encoding="utf-8"))


def sfx_family(name: str) -> str:
    """Семейство звука по первому слову: impact-bass-1 и -2, whoosh и whoosh-cinematic на слух — одно."""
    return name.split("-")[0]


def audio(sid: str, name: str, start: float, level: float = 1.0,
          duration: float | None = None, fade_out: float | None = None) -> str:
    """Звук на шкале дубля. level — доля нормы: 1 — норма (на ~11 дБ тише голоса), 0.5 — вдвое тише.

    Громкость считается от замера файла, а не задаётся числом наугад; громче нормы — нельзя.
    Убранный звук (manifest → _removed) — громкая ошибка с причиной, а не тишина в ролике.
    """
    manifest = sfx_manifest()
    if name in manifest.get("_removed", {}):
        raise ValueError(f"звука «{name}» больше нет: {manifest['_removed'][name]}")
    info = manifest.get(name) if not name.startswith("_") else None
    if not info or "loudness_m" not in info:
        known = ", ".join(k for k in manifest if not k.startswith("_"))
        raise ValueError(f"звука «{name}» нет в presets/sfx (или он без замера громкости). Есть: {known}")
    if not 0 < level <= 1:
        raise ValueError(f"уровень звука «{name}» = {level}: бывает от 0 до 1 (1 — норма, громче нельзя)")
    gain = min(1.0, level * 10 ** ((SFX_TARGET - info["loudness_m"]) / 20))
    extra = (f' data-duration="{duration}"' if duration else "") + \
            (f' data-fade-out="{fade_out}"' if fade_out else "")
    return (f'      <audio id="sfx-{sid}" src="assets/sfx/{info["file"]}" data-start="{start:.2f}"'
            f'{extra} data-volume="{gain:.3f}"></audio>')


def material_audio(sid: str, stem: str, name: str, start: float, level: float = 1.0,
                   duration: float | None = None, fade_out: float | None = None) -> str:
    """Звук, который человек положил в материалы ролика (work/<имя>/materials/, студия → «Материалы»).

    Громкость — по замеру файла, как у библиотеки: level 1 — норма (на ~11 дБ тише голоса), громче нельзя.
    Музыку под голос обычно ставят тише — level 0.4–0.6.
    """
    import materials
    if not 0 < level <= 1:
        raise ValueError(f"уровень звука «{name}» = {level}: бывает от 0 до 1 (1 — норма, громче нельзя)")
    if materials.kind_of(name) != "audio":
        raise ValueError(f"«{name}» — не звук: material_audio берёт mp3, wav, m4a, aac, ogg из материалов")
    gain = min(1.0, level * 10 ** ((SFX_TARGET - materials.loudness(stem, name)) / 20))
    extra = (f' data-duration="{duration}"' if duration else "") + \
            (f' data-fade-out="{fade_out}"' if fade_out else "")
    return (f'      <audio id="sfx-{sid}" src="assets/materials/{name}" data-start="{start:.2f}"'
            f'{extra} data-volume="{gain:.3f}"></audio>')


def check_sounds(sounds: list) -> None:
    """Звуки ролика: одно семейство не звучит дважды подряд, файл — не чаще двух раз, между
    звуками — не меньше секунды. Ошибка — при сборке страницы, до рендера, со всеми нарушениями.
    """
    found = sorted((float(m.group(2)), m.group(1)) for s in sounds for m in _AUDIO_TAG.finditer(s))
    problems = []
    for (t1, a), (t2, b) in zip(found, found[1:]):
        if sfx_family(a) == sfx_family(b):
            problems.append(f"{a} ({t1:.2f} с) и {b} ({t2:.2f} с) — одно семейство «{sfx_family(a)}» подряд: "
                            "на слух это один и тот же звук")
        if t2 - t1 < SFX_MIN_GAP:
            problems.append(f"{a} ({t1:.2f} с) и {b} ({t2:.2f} с) ближе {SFX_MIN_GAP:g} с — слипаются")
    problems += [f"{name} — {n} раз(а) за ролик, можно {SFX_MAX_USES}"
                 for name, n in _Counter(name for _, name in found).items() if n > SFX_MAX_USES]
    if problems:
        raise ValueError("Звуки ролика нарушают правила (kit.check_sounds):\n  " + "\n  ".join(problems))


def card(cid: str, img: str, name: str, sub: str, side: str = "right") -> str:
    return (f'        <div id="{cid}" class="g card card-{side}">\n'
            f'          <div class="ph"><img src="assets/img/{img}" alt="" /></div>\n'
            f'          <div class="card-name">{name}</div>\n'
            f'          <div class="card-sub">{sub}</div>\n        </div>')


def _cutaway_js(fid: str, at: float, dur: float, inner: str = "") -> str:
    """Вход и выход перебивки — переходом проекта (rules.md п.14–15), а не жёстким резом (Валера 16.10: «органично,
    с переходами, а не рывками»): на входе вспышка в 3 кадра и картинка наводится из смаза с лёгкого наезда, на
    выходе — склейка проекта splice() обратно в человека (смаз-навод камеры и вспышка)."""
    a, b = at, at + dur
    return (f'      tl.fromTo("#flash", {{ opacity: 0 }}, {{ opacity: 0.5, duration: 0.033, ease: "none", immediateRender: false }}, {a - 0.033:.3f});\n'
            f'      tl.to("#flash", {{ opacity: 0, duration: 0.16, ease: "power1.out" }}, {a:.3f});\n'
            f'      tl.set("#{fid}", {{ opacity: 1 }}, {a:.3f});\n'
            f'      tl.fromTo("#{fid}", {{ scale: 1.12, filter: BLUR(16) }}, {{ scale: 1, filter: BLUR(0), duration: 0.22, ease: "power2.out", '
            f'immediateRender: false }}, {a:.3f});\n{inner}'
            f'      tl.to("#{fid}", {{ scale: 1.06, filter: BLUR(14), duration: 0.12, ease: "power2.in" }}, {b - 0.12:.3f});\n'
            f'      tl.set("#{fid}", {{ opacity: 0, scale: 1, filter: BLUR(0) }}, {b:.3f});\n'
            f'      splice({b:.3f});')


def footage(fid: str, stem: str, name: str, at: float, dur: float, fmt: str = "9:16", push: float = 1.08,
            track: int = 2) -> tuple:
    """ИИ-футаж (scripts/footage.py, Google Flow) — перебивка во весь кадр. (html для behind, js для beats).

    16.10.2026 (Валера, после IMG_3303 v2: «вставки не к месту», «субтитры пропадают», «меня поверх не надо — вырезка
    криво»): футаж кладётся в слой behind — под субтитры и графику переднего слоя; человек на это время уходит
    (окна вырезки на футаж не ставить — verify_page краснеет). Вход и выход — переходом (_cutaway_js), внутри — наезд
    push. Субтитры идут поверх как есть. Клип короче окна или не принят — громкая ошибка: сначала footage.py --take.
    """
    from common import WORK_DIR
    path = WORK_DIR / stem / "footage" / f"{name}.mp4"
    took = (_json.loads((path.parent / "takes.json").read_text(encoding="utf-8")).get(name)
            if (path.parent / "takes.json").exists() else None)
    if not path.exists() or not took:
        raise FileNotFoundError(f"нет футажа work/{stem}/footage/{name}.mp4 — сначала footage.py {stem} --take {name}")
    if took["duration"] + 1e-3 < dur:
        raise ValueError(f"футаж {name}: {took['duration']} с, а окно {dur:.2f} с — меньше --speed или короче окно")
    width, height = formats.size(fmt)
    html = (f'        <div id="{fid}" class="g footage" style="left: 0; top: 0; width: {width}px; height: {height}px; '
            f'overflow: hidden; background: #000;">\n'
            f'          <video id="{fid}-clip" class="clip" src="assets/footage/{name}.mp4" muted playsinline '
            f'data-start="{at:.2f}" data-duration="{dur:.2f}" data-track-index="{track}"\n'
            f'                 style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover;"></video>\n'
            f'        </div>')
    inner = (f'      tl.fromTo("#{fid}-clip", {{ scale: 1 }}, {{ scale: {push}, duration: {dur:.2f}, ease: "none", '
             f'immediateRender: false }}, {at:.3f});\n')
    return html, _cutaway_js(fid, at, dur, inner)


def slides(sid: str, images: list, at: float, durs: list, fmt: str = "9:16", push: float = 1.1) -> tuple:
    """Перебивка серией картинок (Валера 16.10: «несколько фото подряд, сабы бегут по ним — перебивка вместо видео»).

    images — картинки assets/img (сгенерированные gen_image/Nano Banana или свободные фото), durs — сколько держится
    каждая, с. Каждая медленно наезжает (push), смена — смаз со сдвигом в 0,15 с; вход и выход серии — переходом
    проекта, как у футажа. html — в behind, js — в beats; субтитры идут поверх.
    """
    if len(images) != len(durs) or not images:
        raise ValueError(f"slides {sid}: картинок {len(images)}, длительностей {len(durs)} — должно совпадать и быть > 0")
    if min(durs) < 0.6:
        raise ValueError(f"slides {sid}: картинка держится {min(durs)} с — меньше 0,6 с глаз не успевает")
    width, height = formats.size(fmt)
    imgs = "\n".join(f'          <img id="{sid}-{i}" src="assets/img/{img}" alt="" style="position: absolute; inset: 0; '
                     f'width: 100%; height: 100%; object-fit: cover; opacity: 0;" />' for i, img in enumerate(images))
    html = (f'        <div id="{sid}" class="g footage" style="left: 0; top: 0; width: {width}px; height: {height}px; '
            f'overflow: hidden; background: #000;">\n{imgs}\n        </div>')
    inner, t = [], at
    for i, d in enumerate(durs):
        inner.append(f'      tl.set("#{sid}-{i}", {{ opacity: 1 }}, {t:.3f});')
        inner.append(f'      tl.fromTo("#{sid}-{i}", {{ scale: 1 }}, {{ scale: {push}, duration: {d:.2f}, ease: "none", '
                     f'immediateRender: false }}, {t:.3f});')
        if i:
            inner.append(f'      tl.fromTo("#{sid}-{i}", {{ x: 140, filter: BLUR(18) }}, {{ x: 0, filter: BLUR(0), duration: 0.15, '
                         f'ease: "power3.out", immediateRender: false }}, {t:.3f});')
        if i < len(durs) - 1:
            inner.append(f'      tl.set("#{sid}-{i}", {{ opacity: 0 }}, {t + d:.3f});')
        t += d
    return html, _cutaway_js(sid, at, sum(durs), "\n".join(inner) + "\n")


def doc_img(did: str, img: str, caption: str, left: int = 300, top: int = 1060, width: int = 480,
            height: int = 520, position: str = "50% 30%") -> str:
    inner = width - 32
    return (f'        <div id="{did}" class="g doc" style="left: {left}px; top: {top}px; width: {width}px; padding: 16px;">\n'
            f'          <div style="width: {inner}px; height: {height}px; overflow: hidden;"><img src="assets/img/{img}" alt="" '
            f'style="display: block; width: {inner}px; height: {height}px; object-fit: cover; object-position: {position};" /></div>\n'
            f'          <div class="doc-cap">{caption}</div>\n        </div>')


# Где стоят субтитры на сцене каждого формата: (left, width, top) для позиций стиля.
# Вертикаль: серые зоны площадок (formats.GREY_ZONES, замер по скринам 12.10.2026). Субтитры на
# груди и внизу — на высоте кнопок YouTube с подписями: ширина 590 по центру экрана (середина та же,
# 540: короткие стоят ровно там же, длинные переносятся раньше); «внизу» поднято с 1370 до 1260 —
# там уже ник Instagram; «по центру» — 650 (кнопки Instagram); «сверху» — ниже вкладок TikTok;
# «сбоку» — правее обрезки Instagram.
CAPTION_BOX = {
    "9:16": {"chest": (245, 590, 1150), "lower": (245, 590, 1260), "center": (215, 650, 880),
             "top": (102, 876, 280), "side": (110, 620, 1180)},
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
CTA_AT = {"9:16": (245, 1170, 70, 1480), "4:5": (90, 700, 70, 1040), "1:1": (90, 470, 70, 810),
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
        from styles import is_dark
        bg = "#FFFFFF" if is_dark(caps["color"]) else "rgba(12,12,14,0.78)"
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
        if (c.y !== undefined) el.style.top = c.y + "px";   // линия ролика по лицу (compose.caption_lane)
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
               fmt: str = "9:16", captions: dict | None = None, cutout: bool = True, cta: bool = True) -> str:
    """Собирает index.html. Время — по дублю (aroll), секунды.

    fmt — формат сцены (formats.py), captions — субтитры стиля (styles.kit_captions).
    cutout=False — без слоя вырезанного человека: стилю без текста за спиной не нужна
    маска (matte.py — самые долгие 4 минуты подготовки).
    cta=False — без финальной плашки «смотри у меня в профиле» и её щелчка: ролик не для
    нашего профиля (тестовое для заказчика, 13.10.2026).
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
        # в вертикали плашка уже серых зон площадок; в остальных форматах — прежняя ширина 900
        cta_html = (cta_html.replace("left: 245px; top: 1170px; width: 590px;",
                                     f"left: {cl}px; top: {ct}px; width: 900px;")
                    .replace("left: 70px; top: 1480px;", f"left: {al}px; top: {at}px;"))
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
    if not cta:
        cta_html = cta_js = ""
    else:
        # щелчок финальной плашки — такой же звук ролика: с нормой громкости и под теми же правилами
        sounds = [*sounds, audio("cta", "pop", t)]
    check_sounds(sounds)
    page = _page(d, width, height, fmt, title, style_css, extra_css, plate, behind, cutout_html, front,
                 cta_html, sounds, t, windows, helpers, beats, cta_js)
    if "katex-src" in behind or "katex-src" in front:
        # формулы (viz.formula/plot): KaTeX рисует их синхронно до первого кадра; ошибка в LaTeX —
        # исключение на странице, его ловит verify_page. Страницы без формул не меняются ни на байт
        page = page.replace('    <script src="camera.js"></script>',
                            '    <link rel="stylesheet" href="assets/vendor/katex/katex.min.css" />\n'
                            '    <script src="assets/vendor/katex/katex.min.js"></script>\n'
                            '    <script src="camera.js"></script>', 1)
        # ошибка KaTeX приходит из файла библиотеки, и браузер прячет её текст («Script error»);
        # перевыброс из страницы несёт саму формулу и причину — их и покажет verify_page
        page = page.replace("      const tl = gsap.timeline({ paused: true });",
                            "      document.querySelectorAll(\".katex-src\").forEach((el) => {\n"
                            "        try { katex.render(el.dataset.tex, el, { throwOnError: true, displayMode: true }); }\n"
                            "        catch (e) { throw new Error(`формула «${el.dataset.tex}»: ${e.message}`); }\n"
                            "      });\n"
                            "      const tl = gsap.timeline({ paused: true });", 1)
    return page


def _page(d, width, height, fmt, title, style_css, extra_css, plate, behind, cutout_html, front,
          cta_html, sounds, t, windows, helpers, beats, cta_js) -> str:
    return f'''<!doctype html>
<html lang="ru" data-resolution="{formats.get(fmt)["resolution"]}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={width}, height={height}" />
    <meta name="reels-sfx-norm" content="2026-10-12" />
    <title>{title}</title>
    <script src="assets/gsap.min.js"></script>
    <script src="camera.js"></script>
    <script src="captions.js"></script>
    <script src="layers.js"></script>
    <script src="edits.js"></script>
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
      try {{ REELS_EDITS(tl); }} catch (e) {{ throw new Error(`правки студии: ${{e.message}}`); }}
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
        # камера стиля с правками проекта: наезды пишутся от неё, а не числом наугад (15.10.2026 база
        # стала 1.2, наезды 1.2 молча пропали). Без брифа — умолчания track.py и стиля viral-behind.
        cam = (self.style or {}).get("params", {}).get("camera", {})
        self.base_zoom = float(cam.get("base_zoom", 1.12))
        self.punch = float(cam.get("punch_level", self.base_zoom + 0.1))
        # склейки на шкале дубля: здесь кончается один кусок и начинается следующий
        acc, self.splices = 0.0, []
        for s0, s1 in self.segments[:-1]:
            acc += s1 - s0
            self.splices.append(round(acc, 3))
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

    def splice_punches(self, hold: float = 0.9) -> list:
        """Наезды director.json на каждую склейку: кадр мгновенно бьёт заметно крупнее (+0.16 к базе),
        держится hold с и отпускает за 0.6 с. Пара на странице — splice(t) в beats: смаз-навод и вспышка.

        Так режут референсы (Арсен, риелтор): на склейке меняется весь план, а не дёргается кадр.
        """
        return [[j, round(j + hold, 2), round(self.base_zoom + 0.16, 2), 0.0, 0.6] for j in self.splices]

    def framing(self, keep_wide: list = (), every: float = 2.4) -> tuple:
        """Смена плана общий ↔ крупный, как монтаж с двух камер (стиль antishkola, IMG_1799 v5, 15.10.2026).

        Перескок — мгновенный, на границе фразы (пауза ≥ 0.08 с или знак препинания) не чаще раза в 1.6 с и не
        реже раза в every с. Крупный — база + 0.12; перед склейкой — общий (там бьёт splice), keep_wide —
        окна [(от, до)] по шкале дубля, где крупный нельзя (портрет сбоку ляжет на лицо).
        Возвращает (наезды для director.json, строки beats со whip() на входе в крупный).
        """
        tight = round(self.base_zoom + 0.12, 2)
        edges, last = [], 0.0
        for a, b in zip(self.words, self.words[1:]):
            gap = b["start"] - a["end"]
            edge = round(a["end"] + min(gap, 0.12) / 2, 2) if gap > 0 else round(b["start"], 2)
            natural = gap >= 0.08 or a["word"][-1:] in ",.?!—:"
            if ((natural and edge - last >= 1.6) or edge - last >= every) and edge < self.duration - 3.0:
                edges.append(edge)
                last = edge
        punches = []
        for a, b in zip(edges[0::2], edges[1::2]):
            for j in self.splices:
                if a < j + 0.9 and b > j - 0.35:
                    b = round(j - 0.35, 2)
            for c0, c1 in keep_wide:
                if a < c1 and b > c0:
                    a, b = (a, c0) if c0 - a >= b - c1 else (c1, b)
            if b - a >= 1.2:
                punches.append([a, b, tight, 0.0, 0.0])
        whips = [a for a, *_ in punches if all(abs(a - j) > 1.0 for j in self.splices)]
        return punches, "\n".join(f"      whip({a:.2f});" for a in whips) + "\n"

    def fixes(self, by_src: dict) -> dict:
        """text_fixes по номерам исходника → по номерам дубля."""
        return {str(self.idx(int(i))): v for i, v in by_src.items()}


def keyword_card(word: str, label: str, note: str, top: int = 1250, placeholder: str = "Добавьте комментарий…",
                 width: int = 1080) -> str:
    """Плашка «кодовое слово»: поле ввода, в котором печатается слово. Пара — keyword_beats.

    width — ширина сцены (1920 для горизонтали): поле встаёт по центру.
    """
    letters = "".join(f'<span class="kw-ch" style="opacity: 0;">{ch}</span>' for ch in word)
    return f'''        <div id="kw-label" class="g pill" data-hold="призыв держится до конца ролика — так задумано" style="left: 0; width: {width}px; text-align: center; top: {top - 70}px; background: none; border: none; font-size: 40px;">{label}</div>
        <div id="kw" class="g" data-hold="призыв держится до конца ролика — так задумано" style="left: {(width - 920) // 2}px; top: {top}px; width: 920px; height: 140px; border-radius: 70px; background: rgba(22,22,26,0.94); border: 2px solid rgba(242,235,221,0.22);">
          <div style="position: absolute; left: 26px; top: 28px; width: 84px; height: 84px; border-radius: 42px; background: linear-gradient(135deg, #F5B82E, #F0352C 60%, #A23BD1);"></div>
          <div id="kw-ph" style="position: absolute; left: 136px; top: 44px; font-family: 'Manrope'; font-weight: 800; font-size: 40px; color: rgba(242,235,221,0.38);">{placeholder}</div>
          <div style="position: absolute; left: 136px; top: 30px; font-family: 'Oswald'; font-weight: 700; font-size: 74px; letter-spacing: 0.04em; color: var(--cream); text-transform: uppercase; line-height: 1.1;">{letters}</div>
          <svg viewBox="0 0 60 60" style="position: absolute; right: 36px; top: 40px; width: 60px; height: 60px;">
            <path d="M 6 30 L 54 8 L 40 54 L 30 34 Z" fill="none" stroke="#F2EBDD" stroke-width="5" stroke-linejoin="round" />
          </svg>
        </div>
        <div id="kw-note" class="g sticker" data-hold="призыв держится до конца ролика — так задумано" style="left: 0; width: {width}px; text-align: center; top: {top + 175}px; background: none; box-shadow: none; color: var(--cream); font-size: 54px;">{note}</div>'''


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
