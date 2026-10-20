#!/usr/bin/env python3
"""Решает, что оставить: режет паузы, слова-паразиты и заикания.

Возвращает сегменты в исходном времени + слова, пересчитанные на время готового ролика
(тайминги сдвигаются, иначе субтитры разъедутся с речью).
"""
import re

from common import snap_segments

PUNCT = re.compile(r"[^\w\s\-]", re.UNICODE)
MIN_WORD_LAP = 0.15     # с: слово, которое дубль задевает меньше, — мусор за краем, а не речь (слог короче не бывает)


def norm(word: str) -> str:
    return PUNCT.sub("", word.lower()).strip()


def mark_fillers(words: list, cfg: dict) -> list:
    """Помечает слова-паразиты и заикания как drop=True."""
    fillers = {norm(w) for w in cfg.get("fillers", [])}
    phrases = [tuple(norm(p) for p in ph.split()) for ph in cfg.get("filler_phrases", [])]

    for w in words:
        w["drop"] = False
        w["norm"] = norm(w["word"])

    if cfg.get("remove_fillers", True):
        for w in words:
            if w["norm"] in fillers:
                w["drop"] = True

        # фразы-паразиты целиком ("как бы", "в общем")
        for ph in phrases:
            n = len(ph)
            if n < 1:
                continue
            for i in range(len(words) - n + 1):
                if tuple(words[i + k]["norm"] for k in range(n)) == ph:
                    for k in range(n):
                        words[i + k]["drop"] = True

    # заикания: одно слово подряд дважды за короткий промежуток — оставляем последнее
    if cfg.get("remove_stutters", True):
        window = cfg.get("stutter_window", 0.8)
        for i in range(len(words) - 1):
            a, b = words[i], words[i + 1]
            if a["drop"] or not a["norm"] or len(a["norm"]) < 2:
                continue
            if a["norm"] == b["norm"] and (b["start"] - a["end"]) < window:
                a["drop"] = True

    return words


def build_segments(words: list, cfg: dict, duration: float) -> list:
    """Склеивает оставшиеся слова в непрерывные куски, схлопывая паузы между ними."""
    kept = [w for w in words if not w["drop"]]
    if not kept:
        return [(0.0, duration)]

    max_silence = cfg.get("max_silence", 0.30)
    keep_silence = cfg.get("keep_silence", 0.08)
    pad_start = cfg.get("pad_start", 0.06)
    pad_end = cfg.get("pad_end", 0.10)
    min_segment = cfg.get("min_segment", 0.18)

    segments = []
    for w in kept:
        start = w["start"] - pad_start
        end = w["end"] + pad_end

        if segments and (start - segments[-1][1]) <= max_silence:
            segments[-1][1] = max(segments[-1][1], end)
        else:
            if segments:
                # оставляем короткий «воздух» на стыке — иначе речь звучит захлёбывающейся
                segments[-1][1] += keep_silence / 2
                start -= keep_silence / 2
            segments.append([start, end])

    segments = [[max(0.0, s), min(duration, e)] for s, e in segments]
    segments = [(s, e) for s, e in segments if (e - s) >= min_segment]

    if not cfg.get("trim_head_tail", True) and segments:
        segments[0] = (0.0, segments[0][1])
        segments[-1] = (segments[-1][0], duration)

    return segments


def snap_to_silence(segments: list, silences: list, cfg: dict, duration: float) -> list:
    """Двигает границы кусков в настоящую тишину, а не в конец распознанного слова.

    Whisper сворачивает произнесённое «ноль целых восемь десятых» в «0 ,8» и ставит
    конец слова на 0.3–0.4 с раньше, чем человек договорил. Рез по такому концу срезает
    хвост: в ролике остаётся «де» и обрыв. Здесь конец куска продлевается до начала
    настоящей паузы, а начало отодвигается назад до её конца.

    Если рядом паузы нет — граница остаётся как была. Тянуться дальше `silence_reach`
    нельзя: значит, речь там идёт сплошняком и двигать нечего.
    """
    if not silences:
        return segments

    keep = cfg.get("keep_silence", 0.08) / 2
    reach = cfg.get("silence_reach", 1.2)
    ends = [(s, min(e, duration)) for s, e in silences]

    moved = []
    for start, end in segments:
        # конец куска: первая тишина, которая к этому моменту ещё не кончилась.
        # Речь смолкает ровно на её начале — туда и ставим рез, с крохой воздуха.
        after = next(((s, e) for s, e in ends if e > end), None)
        if after and (after[0] - end) <= reach:
            candidate = min(after[0] + keep, after[1])
            if candidate > start:
                end = candidate

        # начало куска: последняя тишина, начавшаяся раньше него. Речь стартует на её конце.
        before = None
        for s, e in ends:
            if s < start:
                before = (s, e)
            else:
                break
        if before and (start - before[1]) <= reach:
            candidate = max(before[1] - keep, before[0])
            if candidate < end:
                start = candidate

        moved.append([max(0.0, start), min(duration, end)])

    # после сдвига куски могли наехать друг на друга — значит, паузы между ними не было
    merged = []
    for start, end in moved:
        if end - start <= 0:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    return [(s, e) for s, e in merged]


def remap_words(words: list, segments: list) -> list:
    """Пересчитывает тайминги слов на шкалу готового ролика."""
    offsets, acc = [], 0.0
    for s, e in segments:
        offsets.append(acc)
        acc += e - s

    out = []
    for w in words:
        if w["drop"]:
            continue
        # Слово принадлежит куску, где лежит его середина: whisper ставит начало раньше
        # звука, и по началу первое слово дубля выпадало из субтитров. Если середина
        # попала в вырезанную паузу — по-старому, по началу.
        mid = (w["start"] + w["end"]) / 2
        home = next((i for i, (s, e) in enumerate(segments) if s <= mid < e), None)
        if home is None:
            home = next((i for i, (s, e) in enumerate(segments) if s <= w["start"] < e), None)
        if home is None:
            # Первое слово файла whisper начинает с 0.00 (IMG_3647: «Открываешь» 0.00–1.12, голос с 0.68): середина
            # до дубля, начало тоже — а слово звучит внутри. Кусок, где его больше всего, если там хотя бы слог
            lap = [(min(w["end"], e) - max(w["start"], s), i) for i, (s, e) in enumerate(segments)]
            most, i = max(lap)
            home = i if most >= MIN_WORD_LAP else None
        for i, (s, e) in enumerate(segments):
            if i == home:
                new_start = offsets[i] + (max(w["start"], s) - s)
                new_end = offsets[i] + (min(w["end"], e) - s)
                if new_end > new_start:
                    out.append({
                        "word": w["word"],
                        "start": new_start,
                        "end": new_end,
                        "seg": i,
                    })
                break
    return out


def plan_cut(words: list, cfg: dict, duration: float, start: float = 0.0,
             fps: float = 30.0, silences: list | None = None) -> dict:
    """start/duration задают окно внутри исходника — так из длинной записи режется один Reels.

    silences — карта настоящей тишины из common.detect_silence. Если она есть, границы
    кусков ставятся по ней: тайминги распознавания на концах слов врут и режут речь.

    Сегменты возвращаются уже уложенными на сетку кадров: субтитры считаются от их
    длительностей, и она должна совпадать с той, что реально получится при сборке.
    """
    if not cfg.get("enabled", True):
        segments = snap_segments([(start, duration)], fps)
        for w in words:
            w["drop"] = False
        return {
            "segments": segments,
            "words": remap_words(words, segments),
            "kept_duration": sum(e - s for s, e in segments),
            "dropped_words": 0,
        }

    words = mark_fillers(words, cfg)
    segments = build_segments(words, cfg, duration)
    segments = snap_to_silence(segments, silences or [], cfg, duration)
    segments = [(max(start, s), e) for s, e in segments if e > start]
    segments = snap_segments(segments, fps)
    new_words = remap_words(words, segments)
    kept = sum(e - s for s, e in segments)

    return {
        "segments": segments,
        "words": new_words,
        "kept_duration": kept,
        "dropped_words": sum(1 for w in words if w["drop"]),
    }
