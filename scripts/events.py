#!/usr/bin/env python3
"""События дубля: что в исходнике просит монтажного решения — до prep и до плана.

19.10.2026, Валера: «где-то вспышку с отъездом и звуком после хука, где-то вырезать неудачную часть дубля и склеить в
удачную, где-то, где запороли дубль, — серый фильтр, запикать маты, 3 секунды угара и продолжить». До этого сбивки,
маты и смех режиссёр искал глазами по транскрипту, и каждый ролик — заново. Здесь они ищутся одинаково всегда:

  сбивка   — фраза начата заново (те же слова подряд, между попытками мат, «ещё раз», «заново», пауза)
             → вырез от начала первой попытки до начала последней (drop в edit.json);
  мат      — слово из списка → «пип» (bleep), если оно не уходит в вырез;
  без слов — громко, а слов нет: смех, сбивка, которую whisper не записал, шум (смех — по ритму «ха-ха»);
  угар     — сбивка с матом или смехом → кандидат вставки-угара (серый фильтр, «пип», ≤ 3 с, дальше дубль);
  мусор    — отсчёт и реплики до дубля, хвост после призыва → trim;
  хук      — где может кончаться хук: границы фраз 2–14 с дубля, по рангу (решает режиссёр — это смысл, не пауза).

Всё на шкале ИСХОДНИКА (как edit.json); хук — ещё и на шкале дубля, если prep уже был. Решения не принимает:
предлагает edit.json, режиссёр смотрит и правит (правила проекта — что резать, что оставить).

  .venv/bin/python scripts/events.py IMG_3292           # отчёт + work/IMG_3292/events.json
  .venv/bin/python scripts/events.py IMG_3292 --apply   # и edit.json из предложения, если его ещё нет
  .venv/bin/python scripts/events.py --eval             # сверка с решениями прошлых роликов
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import WORK_DIR, ffmpeg_bin  # noqa: E402

HOP = 0.02                 # огибающая громкости — по 20 мс, как rms.py
RETAKE_WINDOW = 6.0        # с: повтор без маркеров дальше этого — риторика или объяснение («25/36 … 1 − 25/36»)
RETAKE_WINDOW_MARKED = 40.0  # с маркером («заново», мат) попытки бывают и через полминуты (IMG_3292)
CLAUSE_PAUSE = 0.25        # с: пауза, на которой начинается попытка
UNWORDED_MIN = 0.45        # с: короче — вдох, щелчок
UNWORDED_DB = 16.0         # дБ над шумом пауз — уже голос или смех, а не фон
BLOOPER_MAX = 3.0          # с: угар длиннее не держит (Валера: «3 секунды того, как мы угарали»)
HOOK_FROM, HOOK_TO = 2.0, 14.0

# Мат — по началу слова (с приставками), а не по подстроке: «требует», «колебания», «хуже» — не мат
MAT = re.compile(r"^(?:ни|на|по|за|вы|у|о|об|от|до|про|раз|рас|пере|при|под|недо|съ|с)?"
                 r"(?:[её]б(?:а|у|и|л|н|ыв|ок|ош|ет)|хуй|хуе|хуё|хуя|хуи|хул|пизд|бля|муда[кч]|сук[аи]$|сучк|залуп|"
                 r"долбо|пид[оа]р|гандон|шлюх|хер$|херн|херов)")
SOFT_SWEAR = {"черт", "блин", "епт", "ешкин", "капец", "трындец", "фак"}
# «ещё раз» само по себе — часто содержание («сложим ещё раз», IMG_3309); маркер — только с «давай»
META = ("давай еще раз", "еще раз давай", "давай еще", "заново", "перезапиш", "перезапис", "с этого момента", "давай с",
        "сначала давай", "стоп", "не так", "записываем", "поехали", "раз два три", "камера", "не не", "ничего ничего",
        "сорян", "еще дубль", "давай дубль")
SHORT = {"а", "и", "но", "так", "вот", "ну", "ведь", "то", "же", "что"}   # с них начинается вторая попытка
TURN = {"и", "но", "а", "все", "всё", "дело", "вообще", "знаете", "казалось", "если", "сейчас", "смотрите",
        "оказывается", "поэтому", "так", "короче", "давайте", "на"}
CTA = ("в профил", "подпис", "переходи", "ко мне в", "лайк", "в комментари", "у меня в")

# Концы хуков, размеченные 09.10.2026 для превью «вспышки после хука» (шкала дубля, первое слово основы) — для --eval
HOOK_LABELS = {"IMG_3279": 7.64, "IMG_3287": 11.49, "IMG_3290": 9.63, "IMG_3292": 4.16, "IMG_3295": 5.39,
               "IMG_3297": 11.02, "IMG_3300": 8.09, "IMG_3303": 8.98, "IMG_3305": 8.60, "IMG_3309": 9.76,
               "IMG_3311": 9.34, "IMG_3313": 4.85, "IMG_3320": 10.85, "IMG_3322": 12.95}


def norm(word: str) -> str:
    return re.sub(r"[^\w]", "", word.lower().replace("ё", "е"))


def is_mat(word: str) -> bool:
    return bool(MAT.match(norm(word)))


def ends_sentence(word: dict) -> bool:
    return bool(re.search(r"[.!?…]$", word["word"].strip()))


def load_words(stem: str) -> list:
    path = WORK_DIR / f"{stem}.words.json"
    if not path.exists():
        sys.exit(f"✗ нет {path.relative_to(WORK_DIR.parent)} — сначала transcribe.py по исходнику")
    words = [w for w in json.loads(path.read_text(encoding="utf-8"))["words"] if norm(w["word"])]
    for w in words:
        w["n"] = norm(w["word"])
    return words


def envelope(source: Path) -> np.ndarray:
    """Громкость по 20 мс, дБ (моно 16 кГц из исходника; память — пара мегабайт на минуту)."""
    result = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
                             "-f", "s16le", "-"], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"Не получилось достать звук из {source.name}: {result.stderr.decode(errors='replace')[-300:]}")
    x = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768
    hop = int(16000 * HOP)
    frames = x[: len(x) // hop * hop].reshape(-1, hop)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)


# ---------------------------------------------------------------- сбивки

def _clause_start(words: list, i: int, floor: int) -> int:
    """Начало попытки: назад до конца прошлой фразы или паузы, не дальше шести слов."""
    k = i
    while k - 1 > floor and i - (k - 1) <= 6:
        prev, cur = words[k - 1], words[k]
        if ends_sentence(prev) or cur["start"] - prev["end"] >= CLAUSE_PAUSE:
            break
        k -= 1
    return k


def _boundary(words: list, k: int) -> bool:
    """Перед словом k начинается кусок речи: конец фразы, запятая или пауза."""
    prev = words[k - 1]
    return bool(re.search(r"[.!?…,]$", prev["word"].strip())) or words[k]["start"] - prev["end"] >= 0.2


def _restart_start(words: list, j: int, floor: int) -> int | None:
    """Начало последней попытки — с куска речи, не дальше двух слов назад (IMG_1805: «Атрет, через несколько
    лет…» — заново начал с «через»; IMG_3292: «А на Руси»). Повтор посреди фразы («1 минус 25/36») — None."""
    for k in range(j, max(floor, j - 2) - 1, -1):
        if k <= floor:
            break
        said = " ".join(w["n"] for w in words[max(0, k - 3):k])          # «…давай ещё раз | А на Руси»
        if _boundary(words, k) or words[k - 1]["n"] in SOFT_SWEAR or is_mat(words[k - 1]["word"]) \
                or any(said.endswith(m) for m in META):
            return k
    return None


def retakes(words: list) -> list:
    """Сбивки с повтором: [(i0, j0, маркеры, совпало слов)] — вырез от слова i0 до слова j0 (не включая)."""
    n, found = len(words), []
    for i in range(n):
        best = None
        for j in range(i + 1, n):
            span = words[j]["start"] - words[i]["start"]
            if span > RETAKE_WINDOW_MARKED:
                break
            if words[j]["n"] != words[i]["n"]:
                continue
            k = 0
            while i + k < j and j + k < n and words[i + k]["n"] == words[j + k]["n"]:
                k += 1
            matched = [words[i + m]["n"] for m in range(k)]
            if k < 2 or not any(len(m) >= 4 for m in matched):
                continue
            between = words[i + k:j]
            text = " ".join(w["n"] for w in between)
            markers = sorted({w["word"].strip(",.!?…") for w in between if is_mat(w["word"]) or w["n"] in SOFT_SWEAR}
                             | {m for m in META if m in text})
            filler = all(w["n"] in SHORT for w in between)        # «с первого класса и с первого класса» — риторика
            # без маркера сбивка — короткая (≤ 6 с), повтор от 3 слов и вторая попытка начинает кусок речи; первая
            # попытка, договорённая до точки, при коротком повторе — цитата («слова „хотя бы один“. Видишь „хотя бы
            # один“…», IMG_1812), а не сбивка
            j0 = _restart_start(words, j, i + k - 1)
            strong = bool(markers) or (k >= 3 and span <= RETAKE_WINDOW and not filler and j0 is not None
                                       and (k >= 4 or not ends_sentence(words[j0 - 1])))
            if not strong:
                continue
            best = (j, markers, k)            # последняя попытка — та, что дальше всех
        if best:
            found.append((i, *best))
    # вложенные и цепочки попыток: одна сбивка — один вырез от первой попытки до последней
    # Повтор, у которого первая попытка уже внутри выреза, его не удлиняет: она и так ушла, а дальше идёт хороший
    # дубль (IMG_3292: «Но главное…» из вырезанного куска повторено после «А на Руси…» — вырез доехал до 74 с вместо
    # 62 и съел 12 с чистой речи). Удлиняет только следующая попытка той же фразы («А в Америке…» ×3, IMG_3290).
    merged = []
    for i, j, markers, k in sorted(found):
        if merged and i < merged[-1][1]:
            continue
        if merged and i - merged[-1][1] <= 2:
            pi, pj, pm, pk = merged[-1]
            merged[-1] = (pi, j, sorted(set(pm) | set(markers)), max(pk, k))
        else:
            merged.append((i, j, markers, k))
    out, floor = [], -1
    for i, j, markers, k in merged:
        i0 = _clause_start(words, i, floor)
        j0 = _restart_start(words, j, i)
        out.append((i0, j if j0 is None else j0, markers, k))
        floor = j0
    return out


# ---------------------------------------------------------------- звук без слов

def unworded(words: list, env: np.ndarray, start: float, end: float) -> list:
    """Громкие места без распознанных слов: [(от, до, похоже на смех)]."""
    if not len(env):
        return []
    t = np.arange(len(env)) * HOP
    floor = float(np.percentile(env, 15))
    loud = env > floor + UNWORDED_DB
    covered = np.zeros(len(env), dtype=bool)
    for w in words:
        if not re.fullmatch(r"(?:ха|хе|хи|хаха|ахах|ахаха)+", w["n"]):       # «ха-ха» — тоже смех, а не слово
            covered[(t >= w["start"] - 0.12) & (t <= w["end"] + 0.12)] = True
    mask = loud & ~covered & (t >= start) & (t <= end)
    out, k = [], 0
    while k < len(mask):
        if not mask[k]:
            k += 1
            continue
        a = k
        while k < len(mask) and (mask[k] or (k + 5 < len(mask) and mask[k + 1:k + 6].any())):   # дыры до 100 мс
            k += 1
        if (k - a) * HOP >= UNWORDED_MIN:
            seg = env[a:k] - env[a:k].mean()
            ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
            ac = ac / (ac[0] + 1e-9)
            lags = ac[int(0.12 / HOP):int(0.35 / HOP) + 1]          # «ха-ха-ха» — 3–8 толчков в секунду
            out.append((round(a * HOP, 2), round(k * HOP, 2), bool(len(lags) and lags.max() > 0.35)))
    return out


# ---------------------------------------------------------------- мусор в начале и в конце

def opening_restarts(words: list) -> list:
    """Заходы с начала: где ещё раз звучат первые три слова речи (IMG_3295 — «Смотрим итоги выборов…» четыре раза,
    между заходами мат и смех). Дубль — последний заход; всё до него — сорванные начала."""
    head = [w["n"] for w in words[:3]]
    if len(head) < 3 or not any(len(x) >= 4 for x in head):
        return []
    return [k for k in range(3, len(words) - 2) if [w["n"] for w in words[k:k + 3]] == head]


def edges(words: list) -> tuple:
    """(с какого слова начинать, на каком кончать, почему) — отсчёт до дубля и реплики после призыва."""
    first, why = 0, []
    again = opening_restarts(words)
    if again:
        why.append(f"начало: заходов с первой фразы {len(again) + 1} — дубль с последнего ({words[again[-1]]['start']:.2f} с), "
                   f"до него сорванные начала (угар оттуда — кандидат во вставку)")
        first = again[-1]
    for k, w in enumerate(words[:40]):
        if w["start"] > 25 or again:
            break
        text = " ".join(x["n"] for x in words[max(0, k - 3):k + 1])
        nxt = words[k + 1] if k + 1 < len(words) else None
        if nxt and any(m in text for m in META) and nxt["start"] - w["end"] >= 0.6:
            first = k + 1
    # реплика до дубля: несколько слов и долгая пауза в первые 15 с («а я не это сделал. … Почему знак равенства» —
    # 5 с, IMG_3279; «Раз, два, взорвалась голова. …» IMG_3311; «Можно. …» IMG_3303)
    if not again:
        for k in range(min(len(words) - 1, 12)):
            gap = words[k + 1]["start"] - words[k]["end"]
            if words[k + 1]["start"] > 15:
                break
            if k + 1 - first <= 8 and (gap >= 1.8 or (k + 1 - first <= 3 and gap >= 1.0)):
                first = k + 1
    if first and not again:
        why.append(f"начало: «{' '.join(x['word'] for x in words[:first])}» — отсчёт и реплики до дубля")
    last = len(words) - 1
    for k in range(len(words) - 1, max(first, len(words) - 60), -1):
        text = " ".join(x["n"] for x in words[max(0, k - 4):k + 1])
        if any(m in text for m in CTA):
            nxt = words[k + 1] if k + 1 < len(words) else None
            if nxt and nxt["start"] - words[k]["end"] >= 0.6:
                last = k
                why.append(f"конец: после «…{' '.join(x['word'] for x in words[max(0, k - 4):k + 1])}» — "
                           f"«{' '.join(x['word'] for x in words[k + 1:])}» за кадром")
            break
    return first, last, why


# ---------------------------------------------------------------- хук

def hook_candidates(words: list, top: int = 4) -> list:
    """Где может начинаться основа после хука: [(с, слово, балл)] по шкале этих слов. Ранг — подсказка:
    по 14 размеченным роликам конец хука всегда на границе фразы, но на какой — решает смысл, а не пауза."""
    out = []
    for a, b in zip(words, words[1:]):
        if not HOOK_FROM <= b["start"] <= HOOK_TO:
            continue
        gap = b["start"] - a["end"]
        if not (ends_sentence(a) or gap >= 0.3):
            continue
        score = (1.0 if ends_sentence(a) else 0.0) + (1.5 if b["n"] in TURN else 0.0) + min(gap, 0.8) \
            + (0.5 if 4.0 <= b["start"] <= 12.0 else 0.0)
        out.append((round(b["start"], 2), b["word"].strip(), round(score, 2)))
    return sorted(out, key=lambda c: -c[2])[:top]


# ---------------------------------------------------------------- всё вместе

def analyze(stem: str, env: np.ndarray | None = None) -> dict:
    words = load_words(stem)
    if env is None:
        import projects
        source = projects.source(stem)
        env = envelope(source) if source else np.zeros(0)
    first, last, edge_why = edges(words)
    start, end = words[first]["start"], words[last]["end"]
    takes = retakes(words[first:last + 1])
    drops, items = [], []
    for i0, j0, markers, k in takes:
        a, b = words[first + i0], words[first + j0]
        span = [round(a["start"] - 0.05, 2), round(b["start"] - 0.05, 2)]
        drops.append(span)
        items.append({"drop": span, "attempt": " ".join(w["word"] for w in words[first + i0:first + j0])[:160],
                      "restart": " ".join(w["word"] for w in words[first + j0:first + j0 + 8]),
                      "markers": markers, "matched": k})
    inside = lambda t0, t1: any(d0 <= t0 and t1 <= d1 + 0.05 for d0, d1 in drops)   # noqa: E731
    bleeps = [{"at": [round(w["start"] - 0.04, 2), round(w["end"] + 0.04, 2)], "word": w["word"].strip(",.!?…"),
               "dropped": inside(w["start"], w["end"])}
              for w in words[first:last + 1] if is_mat(w["word"])]
    sounds = [{"at": [a, b], "laugh": laugh, "dropped": inside(a, b)}
              for a, b, laugh in unworded(words, env, start, end)]
    bloopers = []
    for item in items:
        d0, d1 = item["drop"]
        mats = [b["at"][0] for b in bleeps if d0 <= b["at"][0] <= d1]
        laughs = [s["at"][0] for s in sounds if s["laugh"] and d0 <= s["at"][0] <= d1]
        if mats or laughs:
            at = min(mats + laughs)
            bloopers.append({"at": [round(max(d0, at - 0.6), 2), round(min(d1, at - 0.6 + BLOOPER_MAX), 2)],
                             "why": ("мат" if mats else "") + (" и смех" if mats and laughs else "смех" if laughs else "")})
    if first:                              # сорванные начала: мат или смех там — тоже кандидат во вставку-угар
        lead = [w["start"] for w in words[:first] if is_mat(w["word"])]
        lead_laughs = [a for a, b, laugh in unworded(words, env, words[0]["start"], start) if laugh]
        # смешнее всего — мат рядом со смехом («Хуй ты ржёшь» и смех за кадром, IMG_3295)
        ranked = sorted(lead, key=lambda t: (not any(abs(t - x) < 3 for x in lead_laughs), t)) or lead_laughs[:1]
        for at in ranked[:1]:
            bloopers.append({"at": [round(max(0.0, at - 0.6), 2), round(at - 0.6 + BLOOPER_MAX, 2)],
                             "why": "сорванное начало: мат" + (" и смех" if any(abs(at - x) < 3 for x in lead_laughs) else "")})
    edit = {"trim": [round(max(0.0, start - 0.3), 2), round(end + 0.3, 2)], "cut_pauses": False}
    if drops:
        edit["drop"] = drops
    kept = [b["at"] for b in bleeps if not b["dropped"]]
    if kept:
        edit["bleep"] = kept
    # что проверить ушами: whisper растянул слово на секунды — под ним спрятана речь (IMG_1803: «года.» 2,8 с, внутри
    # сбивка «до 17…»); слово, в котором он не уверен, — оговорка («год, круг, день, радиус», IMG_1798)
    doubts = [{"at": [round(w["start"], 2), round(w["end"], 2)], "word": w["word"].strip(),
               "why": "растянуто — внутри может быть сбивка" if w["end"] - w["start"] > 1.4 else "распознано неуверенно"}
              for w in words[first:last + 1] if not inside(w["start"], w["end"])
              and (w["end"] - w["start"] > 1.4 or (w.get("prob", 1) < 0.2 and len(w["n"]) > 2))]
    return {"stem": stem, "words": len(words), "trim_why": edge_why, "retakes": items, "bleeps": bleeps,
            "unworded": sounds, "bloopers": bloopers, "doubts": doubts, "hook": hook_on_take(stem, words[first:]),
            "edit": edit}


def hook_on_take(stem: str, words: list) -> list:
    """Кандидаты конца хука: по дублю, если prep уже был, иначе по исходнику от начала речи."""
    take = WORK_DIR / stem / "aroll.words.json"
    if take.exists():
        aroll = [w for w in json.loads(take.read_text(encoding="utf-8"))["words"] if norm(w["word"])]
        for w in aroll:
            w["n"] = norm(w["word"])
        return [{"t": t, "word": w, "score": s, "scale": "дубль"} for t, w, s in hook_candidates(aroll)]
    shift = words[0]["start"] if words else 0.0
    shifted = [{**w, "start": w["start"] - shift, "end": w["end"] - shift} for w in words]
    return [{"t": round(t + shift, 2), "word": w, "score": s, "scale": "исходник"} for t, w, s in hook_candidates(shifted)]


def report(ev: dict) -> str:
    lines = [f"События {ev['stem']} (шкала исходника; решения — твои, это предложение):"]
    for why in ev["trim_why"]:
        lines.append(f"  мусор   {why if len(why) < 160 else why[:150] + '…»'}")
    lines.append(f"  trim    {ev['edit']['trim']}")
    for r in ev["retakes"]:
        mk = f", маркеры: {', '.join(r['markers'])}" if r["markers"] else ""
        lines.append(f"  сбивка  вырез {r['drop'][0]:.2f}–{r['drop'][1]:.2f} ({r['drop'][1] - r['drop'][0]:.1f} с{mk}) "
                     f"— «{r['attempt'][:70]}…» → заново «{r['restart']}»")
    for b in ev["bleeps"]:
        lines.append(f"  мат     «{b['word']}» {b['at'][0]:.2f}–{b['at'][1]:.2f}" + (" — уходит в вырез" if b["dropped"] else " → пип"))
    for s in ev["unworded"]:
        lines.append(f"  без слов {s['at'][0]:.2f}–{s['at'][1]:.2f}" + (" — похоже на смех" if s["laugh"] else "")
                     + (" (в вырезе)" if s["dropped"] else " — посмотри: сбивка, смех или шум"))
    for d in ev["doubts"][:8]:
        lines.append(f"  проверь «{d['word']}» {d['at'][0]:.2f}–{d['at'][1]:.2f} — {d['why']} (rms.py, перепроверка whisper)")
    for b in ev["bloopers"]:
        lines.append(f"  угар?   {b['at'][0]:.2f}–{b['at'][1]:.2f} ({b['why']}) — можно оставить вставкой-угаром "
                     f"(edit.json \"blooper\") вместо выреза, если смешно; не больше одного на ролик")
    if ev["hook"]:
        lines.append("  хук     основа может начинаться: " + ", ".join(
            f"{h['t']:.2f} «{h['word']}»" for h in ev["hook"]) + f" (шкала: {ev['hook'][0]['scale']}; первое — вероятнее)")
    lines.append("  edit.json → " + json.dumps(ev["edit"], ensure_ascii=False))
    return "\n".join(lines)


# ---------------------------------------------------------------- сверка с решениями прошлых роликов

def evaluate() -> int:
    """Сколько решений прошлых роликов (edit.json — их принимал режиссёр, часть смотрел Валера) находит детектор."""
    hit = miss = extra = b_hit = b_miss = t_hit = t_miss = tails = 0
    rows = []
    for edit_path in sorted(WORK_DIR.glob("IMG_*/edit.json")):
        stem = edit_path.parent.name
        if not (WORK_DIR / f"{stem}.words.json").exists():
            continue
        edit = json.loads(edit_path.read_text(encoding="utf-8"))
        ev = analyze(stem, env=np.zeros(0))
        lo, hi = (edit.get("trim") or [0, 1e9])[:2]
        mine = ev["edit"].get("drop", [])
        tails += sum(1 for d in edit.get("drop") or [] if lo < d[0] < hi and d[0] > hi - 1.0)   # подрезка хвоста
        theirs = [d for d in edit.get("drop") or [] if lo < d[0] < hi - 1.0]
        ok = abs(ev["edit"]["trim"][0] - lo) < 1.0 or (lo < 1.5 and ev["edit"]["trim"][0] < 1.5)
        t_hit, t_miss = t_hit + ok, t_miss + (not ok)
        if not ok:
            rows.append(f"  ✗ {stem} начало: у них {lo:.2f}, у меня {ev['edit']['trim'][0]:.2f}")
        for d in theirs:
            ok = any(min(d[1], m[1]) - max(d[0], m[0]) > 0.5 * (d[1] - d[0]) for m in mine)
            hit, miss = hit + ok, miss + (not ok)
            rows.append(f"  {'✓' if ok else '✗'} {stem} вырез {d[0]:.2f}–{d[1]:.2f}")
        for m in mine:
            if lo < m[0] < hi and not any(min(d[1], m[1]) - max(d[0], m[0]) > 0 for d in theirs):
                extra += 1
                rows.append(f"  + {stem} лишний вырез {m[0]:.2f}–{m[1]:.2f}: «{next(r['attempt'] for r in ev['retakes'] if r['drop'] == m)[:60]}»")
        for b in edit.get("bleep") or []:
            ok = any(abs(x["at"][0] - b[0]) < 0.4 for x in ev["bleeps"])
            b_hit, b_miss = b_hit + ok, b_miss + (not ok)
            rows.append(f"  {'✓' if ok else '✗'} {stem} пип {b[0]:.2f}–{b[1]:.2f}")
    h_top1 = h_top3 = 0
    for stem, label in HOOK_LABELS.items():
        cands = analyze(stem, env=np.zeros(0))["hook"] if (WORK_DIR / f"{stem}.words.json").exists() else []
        near = [abs(c["t"] - label) < 0.35 for c in cands]
        h_top1 += bool(near[:1] and near[0])
        h_top3 += any(near[:3])
    print("\n".join(rows))
    print(f"\nсбивки: нашёл {hit} из {hit + miss}, лишних {extra} (подрезок хвоста не считаю: {tails}); "
          f"начало дубля: {t_hit} из {t_hit + t_miss}; пип: {b_hit} из {b_hit + b_miss}; "
          f"хук: первым {h_top1} из {len(HOOK_LABELS)}, в тройке {h_top3}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="События дубля: сбивки, мат, смех, мусор, конец хука")
    ap.add_argument("stem", nargs="?")
    ap.add_argument("--apply", action="store_true", help="записать edit.json из предложения, если его ещё нет")
    ap.add_argument("--eval", action="store_true", help="сверка с решениями прошлых роликов")
    args = ap.parse_args()
    if args.eval:
        sys.exit(evaluate())
    if not args.stem:
        ap.error("нужно имя ролика или --eval")
    ev = analyze(args.stem)
    out = WORK_DIR / args.stem / "events.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    print(report(ev))
    edit_path = WORK_DIR / args.stem / "edit.json"
    if args.apply:
        if edit_path.exists():
            print(f"  edit.json уже есть — не трогаю (решения режиссёра и человека); сравни с предложением выше")
        else:
            edit = {**ev["edit"], "_note": "Предложение events.py — проверь сбивки и пипы по звуку (rms.py), потом prep."}
            edit_path.write_text(json.dumps(edit, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  ✓ {edit_path.relative_to(WORK_DIR.parent)} записан из предложения")


if __name__ == "__main__":
    main()
