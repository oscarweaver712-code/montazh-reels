"""IMG_9665 v2 — отзыв клиентки Ольги Статировой (тестовое, ТЗ Ольги 22.10.2026), страница через montage.Montage.

v1 («Внутренняя погода») забракован Валерой 22.10: «монтаж как будто делал ребёнок», «нет логического завершения — кого
благодарит; там было охуенное "спасибо" в конце», «маленькие комментарии в округлых рамках — ИИшно и уёбищно», «погода
упорото — лучше стоки на фон, перебивки в тему», «висело слово, которое не произносилось», «нет переходов для удержания».
Референс — отзыв DeQ_y8IIvWY (work/IMG_9665/downloads): крупный текст по центру внизу без плашек — узкая контрастная
антиква капсом (подводка) + жирный кремовый гротеск, печатаются по буквам; вставки — по делу.

Мысль: «Я не знаю, как ты это делаешь — я называю это чудо»: в апреле — сложные отношения с мамой, агрессия и нервы, в
октябре — любовь ко всем, нет агрессии и обиды, спокойно; жалеет только, что ждала 48 лет. Финал — её «Олечка, спасибо
тебе огромное… Спасибо» и улыбка, подпись «Ольга Статирова» — кого благодарят.
Идея ролика — «живой отзыв»: её лицо и голос — главное, перебивки — настоящие люди и осень в момент каждой фразы
(тревожный звонок, раздражение, жёлтые кроны «октября», объятие, солнце, песочные часы), слова-ключи — типографикой.

Дубль — сборка из 18 кусков (pack.json): ×1.1, финал «Олечка, спасибо…» — ×1.0, живым темпом; паузы вырезаны кусками по
огибающей (edit.json cut_pauses false — последняя пауза перед «Спасибо» остаётся). Шкала дубля 54,57 с.
Слова — whisper по собранному дублю, подтянуты по громкости (tighten_words): whisper тянул «я» на 2 с через «э-э» и
поставил последнее «Спасибо» на улыбку (53,5 с), а сказано оно на 51,3 с; «Олечка» он не услышал — слово вставлено.
Стоки — Coverr License и Mixkit Stock Video Free License (work/IMG_9665/broll/*.md), без указания автора; вертикаль —
broll_prep.py. Музыка — Mixkit «Tears of Joy» (Stock Music Free License).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import kit  # noqa: E402
from common import ffmpeg_bin  # noqa: E402

STEM = "IMG_9665"
TAKE = ROOT / "work" / STEM
TRACK = "mx-tears-of-joy.mp3"
VOICED = -24.0          # дБ огибающей дубля (голос после чистки ~ −12): тише — «э-э», вдох, тишина


def envelope(a: float, b: float) -> tuple:
    out = subprocess.run([ffmpeg_bin(), "-v", "error", "-ss", f"{a}", "-to", f"{b}", "-i", str(TAKE / "aroll.mp4"),
                          "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(out, dtype=np.int16).astype(np.float32) / 32768
    hop = 320
    db = np.array([20 * np.log10(np.sqrt(np.mean(x[k:k + hop] ** 2)) + 1e-9) for k in range(0, len(x) - hop + 1, hop)])
    return db, a, hop / 16000


def voiced_runs(db, t0, step, a, b, bridge=0.2):
    runs = []
    for k, v in enumerate(db):
        t = t0 + k * step
        if a <= t < b and v > VOICED:
            if runs and t - runs[-1][1] <= bridge:
                runs[-1][1] = t + step
            else:
                runs.append([t, t + step])
    return runs


def tighten_words():
    """Слова на шкале дубля — по звуку: начало и конец слова там, где голос, а не где их растянул whisper.

    Слово, внутри которого после голоса ≥ 0,3 с без голоса («я… э-э… называю»), кончается с первым куском голоса —
    иначе субтитр висит, пока человек молчит. Пропущенное «Олечка» вставляется, последнее «Спасибо» встаёт на свой звук.
    """
    path = TAKE / "aroll.words.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    words = data["words"]
    db, t0, step = envelope(0, words[-1]["end"] + 1.2)
    for w in words:
        runs = voiced_runs(db, t0, step, w["start"] - 0.02, w["end"] + 0.02)
        if not runs:
            continue
        end = runs[0][1] if len(runs) > 1 and runs[1][0] - runs[0][1] >= 0.3 else runs[-1][1]
        w["start"] = round(max(w["start"], runs[0][0] - 0.02), 2)
        w["end"] = round(max(w["start"] + 0.12, min(w["end"], end + 0.04)), 2)
    # «Олечка,» (кусок 17 сборки, 48,60–49,17 с) whisper не услышал
    if not any(48.5 <= w["start"] < 49.1 for w in words):
        run = voiced_runs(db, t0, step, 48.6, 49.17)
        k = next(i for i, w in enumerate(words) if w["start"] >= 49.1)
        words.insert(k, {"word": "Олечка,", "start": round(run[0][0], 2), "end": round(run[-1][1] + 0.03, 2)})
    # последнее «Спасибо.»: голос — после «огромное», дальше только улыбка
    last = words[-1]
    big = [r for r in voiced_runs(db, t0, step, 50.5, 54.5) if r[1] - r[0] >= 0.3]
    if last["word"].lower().startswith("спасибо") and big:
        last["start"], last["end"] = round(big[0][0], 2), round(big[0][1] + 0.04, 2)
    data["words"], data["tightened"] = words, "page.py IMG_9665 v2: границы слов по огибающей"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return words


WORDS = tighten_words()
from montage import Montage  # noqa: E402  — после tighten_words: Take читает слова при создании

m = Montage(STEM)
DUR = m.duration
CREAM = "#F4EAD2"
SH = "0 3px 10px rgba(0,0,0,0.35), 0 10px 40px rgba(0,0,0,0.35)"
CHEST = 'data-safe="крупный текст по центру внизу, как в референсе отзыва: на груди, лицо открыто"'


def at(word: str, near: float) -> float:
    """Начало слова на шкале дубля — ближайшее к near: удары ставятся по звуку, а не на глаз."""
    norm = lambda s: re.sub(r"[^\wё-]", "", s.lower())       # noqa: E731
    found = [w for w in WORDS if norm(w["word"]) == norm(word)]
    if not found:
        raise ValueError(f"слова «{word}» в дубле нет")
    return min(found, key=lambda w: abs(w["start"] - near))["start"]


m.css(f"""
      @font-face {{ font-family: "Oranienbaum"; src: url("assets/fonts/Oranienbaum-Regular.ttf"); font-weight: 400; }}
      @font-face {{ font-family: "MontBlack"; src: url("assets/fonts/Montserrat-Black.ttf"); font-weight: 900; }}
      .tw {{ left: 0; width: 1080px; text-align: center; color: {CREAM}; text-shadow: {SH}; }}
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


def title(tid: str, serif: str, heavy: list, top: int, t_in: float, t_heavy: list, t_out: float, size: int = 128):
    """Подводка антиквой печатается по буквам, жирные строки — каждая на своём слове; уход — вверх со смазом."""
    lines = "".join(f'<div class="tw-h" style="font-size: {size}px;">{spans(h)}</div>' for h in heavy)
    head = f'<div class="tw-s">{spans(serif)}</div>' if serif else ""
    m.front(f'        <div id="{tid}" class="g tw" {CHEST} style="top: {top}px;">{head}{lines}</div>')
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


def broll(bid: str, name: str, a: float, b: float, push: float = 1.1):
    """Перебивка стоком во весь кадр: вход — наезд из смаза (кадр «проваливается» в сток), выход — склейка проекта
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


# ---------------------------------------------------------------- 1. хук: «Я не знаю, как ты это делаешь, но я называю это чудо»
title("t1", "я не знаю,", ["как ты это", "делаешь"], 1410, 0.05, [at("как", 1.0), at("делаешь,", 1.4)], 1.74, size=118)
title("t2", "но я называю это", ["чудо"], 1410, 2.0, [at("чудо.", 5.0)], 5.55, size=230)
m.hide(0.0, 1.9)
m.hide(1.95, 5.6)
m.punch(at("чудо.", 5.0), 5.6)
m.hook(at("Потому", 5.7), "конец хука — «Потому что, когда мы начали…»")

# ---------------------------------------------------------------- 2. апрель: «я не думала, что вообще возможно изменить…»
title("t3", "", ["возможно", "изменить"], 1410, at("возможно", 11.1), [at("возможно", 11.1), at("изменить", 11.8)], 13.1, size=150)
m.hide(at("возможно", 11.1) - 0.05, 13.2)
# «мои сложные отношения с мамой» — тревожный звонок; «и моё агрессивное нервное состояние» — раздражение
A1 = at("мои", 13.4)
broll("b-phone", "phone", A1 + 0.02, at("и", 15.5))
broll("b-angry", "angry", at("и", 15.5), at("нервное", 17.4) + 0.1)

# ---------------------------------------------------------------- 3. «Но вот сейчас октябрь» — жёлтые кроны, поворот
B0 = at("Но", 18.5)
broll("b-oct", "october2", B0 + 0.02, at("и", 20.9) - 0.02, push=1.06)
title("t4", "но сейчас", ["октябрь"], 1410, at("сейчас", 19.2), [at("октябрь,", 19.6)], 20.62, size=170)
m.hide(at("сейчас", 19.2), 20.85)
m.sound("riser", "riser", B0 - 0.55, 0.6)

# «у меня очень странное состояние, непривычное»
title("t5", "очень странное,", ["непривычное"], 1410, at("странное", 23.0), [at("непривычное.", 24.6)], 25.32, size=122)
m.hide(at("странное", 23.0) - 0.05, 25.45)

# ---------------------------------------------------------------- 4. «наполнена какой-то любовью ко всем» — объятие
broll("b-hug", "hug", 28.17, at("всем.", 29.5) + 0.32)     # с «-то любовью» — на склейке 28.17
# «У меня нет агрессии, нет обиды» — две строки на своих словах
title("t6", "", ["нет агрессии", "нет обиды"], 1410, at("нет", 31.2), [at("нет", 31.2), at("нет", 32.7)], 33.6, size=104)
m.hide(at("нет", 31.2) - 0.05, 33.66)

# ---------------------------------------------------------------- 5. «Мне хорошо» — солнце; «И мне спокойно» — лицо
broll("b-sun", "sun", at("Мне", 33.8) - 0.12, at("И", 35.1) - 0.08, push=1.05)

# ---------------------------------------------------------------- 6. «всем рекомендую, всем тебя советую… бесценны»
title("t7", "всем", ["рекомендую"], 1410, at("Всем", 36.8), [at("рекомендую,", 37.0)], 37.8, size=128)
m.hide(at("Всем", 36.8) - 0.05, 37.86)
title("t7b", "те", ["трансформации"], 1410, at("трансформации", 40.9) - 0.25, [at("трансформации", 40.9)], 42.3, size=88)
m.hide(at("трансформации", 40.9) - 0.3, 42.36)
title("t8", "для меня это", ["бесценно"], 1410, at("для", 43.8), [at("бесценны.", 44.2)], 44.86, size=150)
m.hide(at("для", 43.8) - 0.05, 44.9)
m.punch(at("бесценны.", 44.2), 44.9)

# ---------------------------------------------------------------- 7. «что я 48 лет ждала?» — песочные часы
H0 = at("что", 45.7)
broll("b-glass", "hourglass", H0 - 0.08, at("Почему", 46.9) - 0.04, push=1.12)
title("t9", "что я", ["48 лет", "ждала?"], 1330, H0, [at("48", 45.9), at("ждала?", 46.5)], at("Почему", 46.9) - 0.2, size=150)
m.hide(H0 - 0.05, at("Почему", 46.9) - 0.04)

# ---------------------------------------------------------------- 8. финал: «Олечка, спасибо тебе огромное… Спасибо» — лицо
END0 = at("Олечка,", 48.7)
m.punch(at("Спасибо", 49.2), DUR - 0.1, level=1.1, ease_in=4.0, ease_out=0.0)   # медленный наезд на её лицо до конца
LAST = at("Спасибо.", 51.3)
LAST_END = next(w["end"] for w in WORDS if w["start"] == LAST)
m.hide(LAST_END + 0.3, DUR)                              # она договорила — дальше улыбка и подпись, без субтитра
m.front(f'        <div id="sig" class="g tw" {CHEST} style="top: 1430px;"><div class="tw-s" style="font-size: 92px;">'
        f'{spans("Ольга Статирова")}</div></div>')
m.js(f'      tl.set("#sig", {{ opacity: 1 }}, {LAST + 0.85:.2f});\n'
     f'      tl.fromTo("#sig .tw-s span", {{ opacity: 0, y: 10 }}, {{ opacity: 1, y: 0, duration: 0.12, stagger: 0.05, ease: "power2.out", '
     f'immediateRender: false }}, {LAST + 0.85:.2f});\n'
     f'      tl.to("#sig", {{ opacity: 0, duration: 0.3, ease: "power1.in" }}, {DUR - 0.32:.2f});')
m.sound("end", "swell-2", LAST + 0.8, 0.8)

# субтитр не висит в тишине: после слова пауза дольше 0,7 с — уходит через 0,35 с (Валера: «висело слово, которое не
# произносилось»; compose держит вспышку до следующей или секунду после слова)
for w0, w1 in zip(WORDS, WORDS[1:]):
    if w1["start"] - w0["end"] > 0.7:
        m.hide(round(w0["end"] + 0.35, 2), round(w1["start"] - 0.02, 2))

FIX = {"спокоит.": "спокойно.", "мое": "моё"}             # whisper по сборке: «спокойно» услышал как «спокоит»
fixes = {i: FIX[w["word"]] for i, w in enumerate(WORDS) if w["word"] in FIX}
fixes.update({i + 1: "спасибо" for i, w in enumerate(WORDS[:-1]) if w["word"] == "Олечка,"})   # «Олечка, спасибо…»
page = m.build("IMG_9665 v2 — живой отзыв", cta_at=None, track=TRACK, music_fade=1.8, text_fixes=fixes,
               accent_words=["чудо", "апреле", "изменить", "мамой", "агрессивное", "нервное", "октябрь", "очень", "любовью", "хорошо",
                             "спокойно", "советую", "трансформации", "раньше", "Олечка", "огромное"])

# музыка: под апрелем тише (×0.6), на «Но вот сейчас октябрь» поднимается до уровня проекта — поворот истории в звуке
index = ROOT / "studio" / STEM / "index.html"
html = index.read_text(encoding="utf-8")
bgm = kit.background_music(STEM, TRACK, DUR, lane=[[0, 0.6], [B0 - 0.4, 0.6], [B0 + 0.4, 1.0]], fade_out=1.8)
html, n = re.subn(r'      <audio id="sfx-bgm"[^\n]*</audio>', lambda _: bgm, html)
if n != 1:
    sys.exit(f"музыка: тег sfx-bgm в странице найден {n} раз — лента громкости не встала")
index.write_text(html, encoding="utf-8")
print("  → музыка: ×0.6 в апреле → ×1 с «октября»")
