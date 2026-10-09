#!/usr/bin/env python3
"""Ищет в длинной записи куски, годные на отдельный Reels.

Алгоритм находит только границы — по длинным паузам, там где мысль закончилась.
Какие из кусков реально стоит публиковать, решает человек (или Claude по транскрипту):
это вопрос смысла, а не длительности.
"""
import json
import sys
from pathlib import Path

from common import WORK_DIR

SENTENCE_END = ".!?…"


def blocks_by_pauses(words: list, seam: float = 0.9) -> list:
    """Режет поток слов там, где говорящий сделал заметную паузу."""
    if not words:
        return []
    blocks, current = [], [words[0]]
    for prev, w in zip(words, words[1:]):
        if w["start"] - prev["end"] >= seam:
            blocks.append(current)
            current = [w]
        else:
            current.append(w)
    blocks.append(current)
    return blocks


def find_candidates(words: list, min_len: float = 22.0, max_len: float = 75.0,
                    seam: float = 0.9) -> list:
    """Склеивает блоки в куски подходящей для Reels длины."""
    blocks = blocks_by_pauses(words, seam)
    if not blocks:
        return []

    candidates, i = [], 0
    while i < len(blocks):
        chunk, j = [], i
        while j < len(blocks):
            nxt = chunk + blocks[j]
            span = nxt[-1]["end"] - nxt[0]["start"]
            if chunk and span > max_len:
                break
            chunk, j = nxt, j + 1
            if span >= min_len:
                break

        if not chunk:
            break

        start = chunk[0]["start"]
        end = chunk[-1]["end"]
        span = end - start

        if span >= min_len * 0.6:
            text = " ".join(w["word"] for w in chunk).strip()
            prev_end = blocks[i - 1][-1]["end"] if i > 0 else None
            candidates.append({
                "index": len(candidates) + 1,
                "start": round(max(0.0, start - 0.25), 2),
                "end": round(end + 0.35, 2),
                "duration": round(span, 1),
                "words": len(chunk),
                "text": text,
                # начало после долгой паузы = мысль стартует здесь, а не обрывается с середины
                "clean_start": prev_end is None or (start - prev_end) >= 1.4,
                "ends_sentence": text.rstrip()[-1:] in SENTENCE_END,
            })
        i = j

    return candidates


def load_words(video_stem: str) -> list:
    path = WORK_DIR / f"{video_stem}.words.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("words", [])


def mmss(s: float) -> str:
    return f"{int(s // 60)}:{s % 60:04.1f}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Использование: split.py <видеофайл>")

    stem = Path(sys.argv[1]).stem
    words = load_words(stem)
    if not words:
        sys.exit(f"Нет транскрипта для «{stem}». Сначала: scripts/transcribe.py <файл>")

    found = find_candidates(words)
    print(f"Кандидатов: {len(found)}\n")
    for c in found:
        mark = "чистый старт" if c["clean_start"] else "начало с середины мысли"
        print(f"[{c['index']:2}] {mmss(c['start'])}–{mmss(c['end'])}  ({c['duration']} с, {mark})")
        print(f"     {c['text'][:150]}{'…' if len(c['text']) > 150 else ''}\n")
