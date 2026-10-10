#!/usr/bin/env python3
"""Форматы кадра: вертикаль, горизонталь, квадрат, 4:5 — размеры и окно камеры.

Пайплайн рождался под Reels 1080×1920, и эта цифра до сих пор зашита в старых страницах.
Всё новое берёт размер отсюда. Правило одно: формат ролика задаёт размер СЦЕНЫ, а
исходник может быть любым — если его пропорции другие, кадр перекадрируется по лицу
(reframe.py), а не режется по центру.

  9:16  1080×1920   Reels, TikTok, Shorts
  16:9  1920×1080   YouTube, VK Видео, вебинары
  1:1   1080×1080   лента, Telegram
  4:5   1080×1350   лента Instagram
"""

FORMATS = {
    "9:16": {"width": 1080, "height": 1920, "name": "вертикаль", "where": "Reels, TikTok, Shorts",
             "resolution": "portrait"},
    "16:9": {"width": 1920, "height": 1080, "name": "горизонталь", "where": "YouTube, VK Видео",
             "resolution": "landscape"},
    "1:1": {"width": 1080, "height": 1080, "name": "квадрат", "where": "лента, Telegram",
            "resolution": "square"},
    "4:5": {"width": 1080, "height": 1350, "name": "4:5", "where": "лента Instagram",
            "resolution": "portrait"},
}
DEFAULT = "9:16"

# Безопасные зоны: где интерфейс площадки закрывает кадр (кнопки, подпись, ник).
# Цифры для 9:16 — общепринятые для Reels/TikTok (сверху 220, снизу 420, справа колонка
# лайков); для горизонтали — плашка плеера снизу.
SAFE = {
    "9:16": {"top": 220, "bottom": 420, "left": 48, "right": 120},
    "16:9": {"top": 60, "bottom": 140, "left": 80, "right": 80},
    "1:1": {"top": 60, "bottom": 120, "left": 48, "right": 48},
    "4:5": {"top": 80, "bottom": 160, "left": 48, "right": 48},
}


def get(fmt: str | None) -> dict:
    """Описание формата с его именем; неизвестный формат — громкая ошибка, а не 9:16 молча."""
    fmt = fmt or DEFAULT
    if fmt not in FORMATS:
        raise ValueError(f"Формат «{fmt}» не знаю. Есть: {', '.join(FORMATS)}")
    return dict(FORMATS[fmt], id=fmt, safe=SAFE[fmt])


def size(fmt: str | None) -> tuple:
    f = get(fmt)
    return f["width"], f["height"]


def of_size(width: int, height: int) -> str | None:
    """Формат по размеру кадра (точное совпадение) или None."""
    for key, f in FORMATS.items():
        if (f["width"], f["height"]) == (width, height):
            return key
    return None


def aspect(fmt: str | None) -> float:
    w, h = size(fmt)
    return w / h


def same_aspect(width: int, height: int, fmt: str | None, tolerance: float = 0.01) -> bool:
    """Пропорции исходника совпадают с форматом — перекадрировать не нужно."""
    return abs(width / height - aspect(fmt)) <= tolerance * aspect(fmt)


def window(src_w: float, src_h: float, out_aspect: float) -> tuple:
    """Самое большое окно нужных пропорций внутри исходника (зум 1.0 камеры).

    Горизонтальный исходник под вертикаль: окно во всю высоту, узкое. Вертикальный под
    горизонталь: во всю ширину, низкое. Совпадают пропорции — окно равно исходнику.
    """
    if src_w / src_h > out_aspect:
        return src_h * out_aspect, float(src_h)
    return float(src_w), src_w / out_aspect
