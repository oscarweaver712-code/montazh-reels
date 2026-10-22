#!/usr/bin/env python3
"""Стиль «Живой отзыв» (presets/styles/testimonial.json): приёмы страницы поверх montage.Montage.

Принят на IMG_9665 v2 (отзыв клиентки Ольги Статировой, 22.10.2026, Валера: «Ну мужчина, охуенно!») после того, как
v1 с мемами-плашками, виджетами и погодой поверх лица был забракован («как будто делал ребёнок», «ИИшно и уёбищно»).
Здесь — то, что делает стиль узнаваемым и что не надо писать в каждой странице заново:

  tighten_words(stem, fix)   границы слов aroll.words.json — по звуку дубля, а не по whisper (до Montage!)
  css(m)                     шрифты и классы стиля: антиква Oranienbaum + Montserrat Black кремом
  title(m, …)                крупная типографика по центру внизу: подводка печатается по буквам, жирные строки — на
                             своих словах, уход вверх со смазом; без плашек
  stock(m, …)                перебивка стоком во весь кадр: вход наездом из смаза, выход склейкой проекта
  quiet_holds(m, words)      субтитр уходит в паузе, а не висит до следующего слова
  signature(m, …)            подпись в финале — имя антиквой по буквам

Стоки ищутся и готовятся под кадр scripts/stock.py (work/<имя>/materials/broll-<имя>.mp4). Образец — work/IMG_9665/page.py.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import WORK_DIR, ffmpeg_bin  # noqa: E402

CREAM = "#F4EAD2"
SHADOW = "0 3px 10px rgba(0,0,0,0.35), 0 10px 40px rgba(0,0,0,0.35)"
VOICED = -24.0       # дБ огибающей дубля по 20 мс: голос после чистки prep ~ −12, «э-э», вдох и тишина — ниже
STEP = 0.02
SILENT_INSIDE = 0.3  # столько без голоса внутри слова whisper — конец слова раньше («я… э-э… называю»)
LOW = 'data-safe="крупный текст по центру внизу, как в референсе отзыва: на груди, лицо открыто"'


# ---------------------------------------------------------------- слова по звуку

class Voice:
    """Огибающая звука дубля (work/<имя>/aroll.mp4) по 20 мс — где на самом деле звучит голос."""

    def __init__(self, stem: str):
        out = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(WORK_DIR / stem / "aroll.mp4"), "-vn", "-ac", "1",
                              "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
        x = np.frombuffer(out, dtype=np.int16).astype(np.float32) / 32768
        hop = int(16000 * STEP)
        n = len(x) // hop
        frames = x[:n * hop].reshape(n, hop)
        self.db = 20 * np.log10(np.sqrt(np.mean(frames ** 2, axis=1)) + 1e-9)

    def runs(self, a: float, b: float, bridge: float = 0.2) -> list:
        """Куски голоса [[от, до]] в окне [a, b): щели короче bridge не рвут кусок."""
        return voiced_runs(self.db, a, b, bridge)


def voiced_runs(db, a: float, b: float, bridge: float = 0.2) -> list:
    runs = []
    for k in range(max(0, int(a / STEP)), min(len(db), int(np.ceil(b / STEP)))):
        if db[k] > VOICED:
            t = k * STEP
            if runs and t - runs[-1][1] <= bridge:
                runs[-1][1] = round(t + STEP, 3)
            else:
                runs.append([round(t, 3), round(t + STEP, 3)])
    return runs


def fit_word(word: dict, runs: list) -> dict:
    """Слово whisper → по куску голоса внутри него. После голоса ≥ SILENT_INSIDE тишины («я… э-э… называю») слово
    кончается с первым куском; начало — не раньше голоса. Без голоса внутри — как было."""
    if not runs:
        return word
    end = runs[0][1] if len(runs) > 1 and runs[1][0] - runs[0][1] >= SILENT_INSIDE else runs[-1][1]
    start = round(max(word["start"], runs[0][0] - 0.02), 2)
    return dict(word, start=start, end=round(max(start + 0.12, min(word["end"], end + 0.04)), 2))


def tighten_words(stem: str, fix=None) -> list:
    """aroll.words.json — по звуку дубля. fix(words, voice) — правки этого ролика (вставить слово, которое whisper не
    услышал; поставить на свой звук то, что он сдвинул). Вызывать ДО Montage: Take читает слова при создании."""
    path = WORK_DIR / stem / "aroll.words.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    voice = Voice(stem)
    words = [fit_word(w, voice.runs(w["start"] - 0.02, w["end"] + 0.02)) for w in data["words"]]
    if fix:
        words = fix(words, voice) or words
    data["words"], data["tightened"] = words, "testimonial.tighten_words: границы слов по огибающей"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return words


def at(words: list, word: str, near: float) -> float:
    """Начало слова на шкале дубля — ближайшее к near: удары ставятся по звуку, а не на глаз."""
    norm = lambda s: re.sub(r"[^\wё-]", "", s.lower())       # noqa: E731
    found = [w for w in words if norm(w["word"]) == norm(word)]
    if not found:
        raise ValueError(f"слова «{word}» в дубле нет")
    return min(found, key=lambda w: abs(w["start"] - near))["start"]


# ---------------------------------------------------------------- страница

def css(m):
    m.css(f"""
      @font-face {{ font-family: "Oranienbaum"; src: url("assets/fonts/Oranienbaum-Regular.ttf"); font-weight: 400; }}
      @font-face {{ font-family: "MontBlack"; src: url("assets/fonts/Montserrat-Black.ttf"); font-weight: 900; }}
      .tw {{ left: 0; width: 1080px; text-align: center; color: {CREAM}; text-shadow: {SHADOW}; }}
      .tw span {{ display: inline-block; opacity: 0; white-space: pre; }}
      .tw-s {{ font-family: "Oranienbaum"; font-weight: 400; font-size: 80px; line-height: 1; letter-spacing: 0.01em;
               text-transform: uppercase; }}
      .tw-h {{ margin-top: 6px; font-family: "MontBlack"; font-weight: 900; font-size: 128px; line-height: 0.9;
               letter-spacing: -0.02em; text-transform: uppercase; white-space: nowrap; }}
      .tw-h + .tw-h {{ margin-top: 0; }}
      .broll {{ left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
      .broll video {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
      .broll i {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0) 55%, rgba(0,0,0,0.35) 100%); }}
""")


def spans(text: str) -> str:
    return "".join(f"<span>{ch}</span>" for ch in text)


def title(m, tid: str, serif: str, heavy: list, top: int, t_in: float, t_heavy: list, t_out: float, size: int = 128):
    """Подводка антиквой печатается по буквам с t_in, жирные строки — каждая на своём слове (t_heavy); уход вверх
    со смазом в t_out. Субтитры на это время прячет страница (m.hide), если текст повторяет речь."""
    if len(heavy) != len(t_heavy):
        raise ValueError(f"{tid}: строк {len(heavy)}, а моментов {len(t_heavy)} — у каждой жирной строки своё слово")
    lines = "".join(f'<div class="tw-h" style="font-size: {size}px;">{spans(h)}</div>' for h in heavy)
    head = f'<div class="tw-s">{spans(serif)}</div>' if serif else ""
    m.front(f'        <div id="{tid}" class="g tw" {LOW} style="top: {top}px;">{head}{lines}</div>')
    js = f'      tl.set("#{tid}", {{ opacity: 1 }}, {t_in:.2f});\n'
    if serif:
        js += (f'      tl.fromTo("#{tid} .tw-s span", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.01, stagger: 0.035, ease: "none", '
               f'immediateRender: false }}, {t_in:.2f});\n')
    for k, t in enumerate(t_heavy):
        js += (f'      tl.fromTo("#{tid} .tw-h:nth-of-type({k + 1 + (1 if serif else 0)}) span", {{ opacity: 0, y: 18 }}, '
               f'{{ opacity: 1, y: 0, duration: 0.06, stagger: 0.04, ease: "power2.out", immediateRender: false }}, {t:.2f});\n')
    js += f'      tl.to("#{tid}", {{ opacity: 0, y: -26, filter: BLUR(10), duration: 0.2, ease: "power2.in" }}, {t_out:.2f});'
    m.js(js)
    m.soft(round(t_in, 2), "text")


def stock(m, bid: str, name: str, a: float, b: float, push: float = 1.1):
    """Перебивка стоком materials/broll-<name>.mp4 во весь кадр: вход — наезд из смаза, выход — склейка проекта
    обратно в лицо (смаз-навод и вспышка в 3 кадра). Субтитры идут поверх."""
    dur = round(b - a, 2)
    html = (f'        <div id="{bid}" class="g broll footage"><video id="{bid}-v" class="clip" '
            f'src="assets/materials/broll-{name}.mp4" muted playsinline data-start="{a:.2f}" data-duration="{dur:.2f}" '
            f'data-track-index="2"></video><i></i></div>')
    js = (f'      tl.set("#{bid}", {{ opacity: 1 }}, {a:.3f});\n'
          f'      tl.fromTo("#{bid}", {{ scale: 1.22, filter: BLUR(18) }}, {{ scale: 1, filter: BLUR(0), duration: 0.28, ease: "expo.out", '
          f'immediateRender: false }}, {a:.3f});\n'
          f'      tl.fromTo("#{bid}-v", {{ scale: 1 }}, {{ scale: {push}, duration: {dur:.2f}, ease: "none", immediateRender: false }}, {a:.3f});\n'
          f'      tl.to("#{bid}", {{ scale: 1.06, filter: BLUR(14), duration: 0.12, ease: "power2.in" }}, {b - 0.12:.3f});\n'
          f'      tl.set("#{bid}", {{ opacity: 0, scale: 1, filter: BLUR(0) }}, {b:.3f});\n'
          f'      splice({b:.3f});')
    m.cutaway(html, js, a, dur)
    m.soft(round(a, 2), "cut")


def quiet_holds(m, words: list, gap: float = 0.7, after: float = 0.35):
    """Субтитр не висит в тишине: после слова пауза дольше gap — уходит через after (compose держит вспышку до
    следующей или секунду после слова; Валера на IMG_9665 v1: «висело слово, которое не произносилось»)."""
    for w0, w1 in zip(words, words[1:]):
        if w1["start"] - w0["end"] > gap:
            m.hide(round(w0["end"] + after, 2), round(w1["start"] - 0.02, 2))


def signature(m, text: str, at_: float, top: int = 1430, size: int = 92):
    """Подпись в финале — кого благодарят: имя антиквой по буквам, уходит с концом ролика."""
    m.front(f'        <div id="sig" class="g tw" {LOW} style="top: {top}px;"><div class="tw-s" style="font-size: {size}px;">'
            f'{spans(text)}</div></div>')
    m.js(f'      tl.set("#sig", {{ opacity: 1 }}, {at_:.2f});\n'
         f'      tl.fromTo("#sig .tw-s span", {{ opacity: 0, y: 10 }}, {{ opacity: 1, y: 0, duration: 0.12, stagger: 0.05, '
         f'ease: "power2.out", immediateRender: false }}, {at_:.2f});\n'
         f'      tl.to("#sig", {{ opacity: 0, duration: 0.3, ease: "power1.in" }}, {m.duration - 0.32:.2f});')
