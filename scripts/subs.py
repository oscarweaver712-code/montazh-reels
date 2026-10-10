#!/usr/bin/env python3
"""Генерирует ASS-субтитры в стиле Reels: слова появляются по одному, текущее подсвечено.

Внутри фразы каждое слово — отдельное событие, поэтому подсветка идёт ровно по речи.
"""
from pathlib import Path

from common import ass_color, ts

ASS_ESCAPE = {"{": "(", "}": ")", "\\": "/"}
SENTENCE_END = ".!?…"


def esc(text: str) -> str:
    for bad, good in ASS_ESCAPE.items():
        text = text.replace(bad, good)
    return text.strip()


def group_phrases(words: list, per_phrase: int, max_gap: float = 0.6) -> list:
    """Бьёт поток слов на короткие фразы — по длине, паузам и точкам."""
    phrases, current = [], []

    for i, w in enumerate(words):
        current.append(w)
        last = i == len(words) - 1
        gap_next = (words[i + 1]["start"] - w["end"]) if not last else 0.0
        ends_sentence = w["word"].rstrip()[-1:] in SENTENCE_END

        if last or len(current) >= per_phrase or gap_next > max_gap or ends_sentence:
            phrases.append(current)
            current = []

    if current:
        phrases.append(current)
    return phrases


def build_ass(words: list, cfg: dict, video_cfg: dict, hook: dict | None = None) -> str:
    width = video_cfg["width"]
    height = video_cfg["height"]

    base = ass_color(cfg.get("color_base", "FFFFFF"))
    active = ass_color(cfg.get("color_active", "FFE24B"))
    accent = ass_color(cfg.get("color_accent", "3BE8B0"))
    scale = int(cfg.get("active_scale", 112))
    pop = cfg.get("pop_in", True)
    upper = cfg.get("uppercase", False)
    accent_words = {w.lower() for w in cfg.get("accent_words", [])}
    # Плашка под текстом (стили «лоуфай», «объясняю на фоне»): в ASS это BorderStyle=3 —
    # непрозрачная коробка цвета обводки, толщина обводки — поля коробки. Тёмный текст без
    # плашки на тёмной одежде не читается (IMG_3305, стиль лоуфай).
    box = bool(cfg.get("box"))
    border_style = 3 if box else 1
    box_color = (ass_color(cfg.get("box_color", "0C0C0E"), int(cfg.get("box_alpha", 0)))
                 if box else "&H00000000")
    outline = cfg.get("box_pad", 14) if box else cfg.get("outline", 7)
    shadow = 0 if box else cfg.get("shadow", 3)

    head = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",  # длинные фразы переносятся, а не уезжают за край кадра
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Sub,{cfg.get('font', 'Montserrat ExtraBold')},{cfg.get('font_size', 92)},"
        f"{base},&H000000FF,{box_color},&H80000000,0,0,0,0,100,100,0,0,{border_style},"
        f"{outline},{shadow},2,"
        f"{cfg.get('margin_h', 110)},{cfg.get('margin_h', 110)},{cfg.get('margin_v', 420)},1",
        f"Style: Hook,{cfg.get('font', 'Montserrat ExtraBold')},{(hook or {}).get('font_size', 110)},"
        f"{ass_color((hook or {}).get('color', 'FFFFFF'))},&H000000FF,&H00000000,&H90000000,0,0,0,0,"
        f"100,100,0,0,1,8,4,5,80,80,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    events = []
    phrases = group_phrases(words, int(cfg.get("words_per_phrase", 3)))

    for phrase in phrases:
        for idx, word in enumerate(phrase):
            start = word["start"]
            # слово держится до следующего, чтобы подсветка не мигала на паузах
            if idx + 1 < len(phrase):
                end = phrase[idx + 1]["start"]
            else:
                end = word["end"] + 0.18

            if end <= start:
                continue

            parts = []
            for j, w in enumerate(phrase):
                text = esc(w["word"])
                if upper:
                    text = text.upper()

                if j == idx:
                    color = accent if w["word"].lower().strip(".,!?") in accent_words else active
                    if pop:
                        parts.append(
                            f"{{\\c{color}\\fscx100\\fscy100"
                            f"\\t(0,90,\\fscx{scale}\\fscy{scale})}}{text}{{\\r}}"
                        )
                    else:
                        parts.append(f"{{\\c{color}\\fscx{scale}\\fscy{scale}}}{text}{{\\r}}")
                else:
                    parts.append(text)

            fade = "{\\fad(50,0)}" if idx == 0 else ""
            events.append(
                f"Dialogue: 0,{ts(start)},{ts(end)},Sub,,0,0,0,,{fade}{' '.join(parts)}"
            )

    if hook and hook.get("enabled") and hook.get("text"):
        text = esc(hook["text"]).replace("|", "\\N")
        events.append(
            f"Dialogue: 1,{ts(0)},{ts(float(hook.get('duration', 2.5)))},Hook,,0,0,0,,"
            f"{{\\fad(120,220)\\pos({width // 2},{int(height * 0.32)})}}{text}"
        )

    return "\n".join(head + events) + "\n"


def write_ass(path: Path, words: list, cfg: dict, video_cfg: dict, hook: dict | None = None) -> Path:
    path.write_text(build_ass(words, cfg, video_cfg, hook), encoding="utf-8")
    return path
