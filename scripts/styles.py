#!/usr/bin/env python3
"""Стили монтажа и бриф ролика: какой выхлоп мы хотим и чем его добиваемся.

Стиль — это файл presets/styles/<id>.json: что видит зритель, ради какой цели он
работает (охват, удержание, доверие, сохранения, продажи), где он на рынке — мейнстрим
или антитренд, — и числа для обоих конвейеров. Быстрый конвейер берёт из стиля пресет
целиком (to_fast_preset). Режиссёрский — субтитры, камеру и цвет (kit_captions,
camera_cfg, look), а графику по стилю пишет режиссёр: ему уходит director_brief.

Бриф ролика — work/<имя>/brief.json: формат(ы), стиль, варианты для A/B, цели и
заметки. Его пишет студия (web/studio.html), читает режиссёр и сборка.

  .venv/bin/python scripts/styles.py                       # каталог
  .venv/bin/python scripts/styles.py --goals reach=5,trust=2 --bold 0.7
  .venv/bin/python scripts/styles.py --check               # все стили валидны
"""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import formats
from common import FONT_DIR, PRESET_DIR, WORK_DIR, load_preset
from look import GRADES

STYLE_DIR = PRESET_DIR / "styles"

GOALS = {
    "reach": "охват",
    "retention": "удержание",
    "trust": "доверие",
    "saves": "сохранения",
    "sales": "продажи",
}
TIERS = {
    "mainstream": "мейнстрим",
    "rising": "на подъёме",
    "niche": "ниша",
    "contrarian": "антитренд",
}
# насколько «смело» выбирать: мейнстрим проверен рынком, антитренд — шанс выделиться
TIER_BOLDNESS = {"mainstream": 0.0, "rising": 0.4, "niche": 0.7, "contrarian": 1.0}

CAPTION_MODES = ("none", "words", "phrase", "sentence", "karaoke")
# как часто визуализации данных (скилл viz): счётчики, графики, формулы, карты
VIZ_LEVELS = {"never": "не ставить", "rare": "только на главное число ролика",
              "sometimes": "к месту — на ключевые числа, формулы, сравнения", "often": "часто — это язык стиля"}
POSITIONS = ("chest", "lower", "center", "top", "side")
ANIMATIONS = ("blur", "pop", "fade", "none")

# Шрифты стилей: файл (обязан быть в presets/fonts и с кириллицей), CSS-семейство для
# страниц HyperFrames и вес. Имя семейства для libass берётся из самого файла.
FONTS = {
    "manrope": {"file": "Manrope-ExtraBold.ttf", "css": "Manrope", "weight": 800},
    "montserrat": {"file": "Montserrat-ExtraBold.ttf", "css": "Montserrat", "weight": 800},
    "oswald": {"file": "Oswald-Bold.ttf", "css": "Oswald", "weight": 700},
    "cormorant": {"file": "CormorantGaramond.ttf", "css": "Cormorant", "weight": 700},
    "unbounded": {"file": "Unbounded-ExtraBold.ttf", "css": "Unbounded", "weight": 800},
    "rubik": {"file": "Rubik-Black.ttf", "css": "Rubik", "weight": 900},
    "golos": {"file": "GolosText-Black.ttf", "css": "Golos", "weight": 900},
    "onest": {"file": "Onest-Black.ttf", "css": "Onest", "weight": 900},
    "alumni": {"file": "AlumniSans-Black.ttf", "css": "Alumni", "weight": 900},
}

REQUIRED = ("id", "name", "tier", "summary", "looks_like", "why_works", "risks", "references",
            "best_for", "formats", "fit", "effort", "needs", "params", "director")


class StyleError(ValueError):
    """Стиль описан с ошибкой — сообщение по-русски, с именем файла."""


# ---------------------------------------------------------------- каталог

def validate(style: dict, source: str = "") -> dict:
    where = f"стиль {source or style.get('id', '?')}"
    missing = [k for k in REQUIRED if k not in style]
    if missing:
        raise StyleError(f"{where}: нет полей {', '.join(missing)}")
    if style["tier"] not in TIERS:
        raise StyleError(f"{where}: tier «{style['tier']}», а бывает {', '.join(TIERS)}")
    for goal in GOALS:
        value = style["fit"].get(goal)
        if not isinstance(value, (int, float)) or not 1 <= value <= 5:
            raise StyleError(f"{where}: fit.{goal} должен быть от 1 до 5, а не {value!r}")
    for fmt in style["formats"]:
        if fmt not in formats.FORMATS:
            raise StyleError(f"{where}: формат {fmt} неизвестен")
    p = style["params"]
    for block in ("pace", "camera", "captions", "graphics", "sound", "color", "transitions"):
        if block not in p:
            raise StyleError(f"{where}: в params нет блока {block}")
    caps = p["captions"]
    if caps["mode"] not in CAPTION_MODES:
        raise StyleError(f"{where}: captions.mode «{caps['mode']}» — бывает {', '.join(CAPTION_MODES)}")
    if caps["position"] not in POSITIONS:
        raise StyleError(f"{where}: captions.position «{caps['position']}» — бывает {', '.join(POSITIONS)}")
    if caps["animation"] not in ANIMATIONS:
        raise StyleError(f"{where}: captions.animation «{caps['animation']}» — бывает {', '.join(ANIMATIONS)}")
    for key in ("color", "highlight"):
        # цвет идёт и в ASS (там байты BGR по позициям), и в CSS: «#FFF» сломал бы оба молча
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(caps.get(key, ""))):
            raise StyleError(f"{where}: captions.{key} «{caps.get(key)}» — нужен цвет вида #RRGGBB")
    for key in ("active_box", "active_text"):
        # караоке с плашкой (20.10.2026, «Вкудесник»): активное слово — на цветной плашке, а не только цветом
        if key in caps and not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(caps[key])):
            raise StyleError(f"{where}: captions.{key} «{caps[key]}» — нужен цвет вида #RRGGBB")
    if "active_text" in caps and "active_box" not in caps:
        raise StyleError(f"{where}: captions.active_text без active_box — цвет текста на плашке, а плашки нет")
    if caps["font"] not in FONTS:
        raise StyleError(f"{where}: шрифт «{caps['font']}» не из набора: {', '.join(FONTS)}")
    if not (FONT_DIR / FONTS[caps["font"]]["file"]).exists():
        raise StyleError(f"{where}: нет файла шрифта presets/fonts/{FONTS[caps['font']]['file']}")
    if p["graphics"].get("viz", "sometimes") not in VIZ_LEVELS:
        raise StyleError(f"{where}: graphics.viz «{p['graphics'].get('viz')}» — бывает {', '.join(VIZ_LEVELS)}")
    if p["color"]["grade"] not in GRADES:
        raise StyleError(f"{where}: грейд «{p['color']['grade']}» — бывает {', '.join(GRADES)}")
    zoom = float(p["camera"]["base_zoom"])
    if not 1.0 <= zoom <= 1.3:
        raise StyleError(f"{where}: camera.base_zoom {zoom} вне 1.0–1.3 (дальше картинка мылится)")
    # 15.10.2026: база проекта поднялась до 1.2, а наезды стиля остались 1.22 — их не было видно
    if p["camera"].get("punch") != "none" and float(p["camera"]["punch_level"]) < zoom + 0.04:
        raise StyleError(f"{where}: camera.punch_level {p['camera']['punch_level']} почти равен базе {zoom} — "
                         f"наезда не будет видно; нужен не ниже {zoom + 0.04:.2f}")
    return style


def load_style(style_id: str) -> dict:
    # имя стиля — это имя файла: «../что-то» не должно читать JSON за пределами каталога
    valid = isinstance(style_id, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", style_id)
    path = STYLE_DIR / f"{style_id}.json"
    if not valid or not path.exists():
        known = ", ".join(sorted(p.stem for p in STYLE_DIR.glob("*.json")))
        raise StyleError(f"Стиля «{style_id}» нет. Есть: {known}")
    try:
        style = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise StyleError(f"{path.name}: битый JSON — {e}")
    if style.get("id") != path.stem:
        raise StyleError(f"{path.name}: id «{style.get('id')}» не совпадает с именем файла")
    return validate(style, path.name)


def all_styles() -> list:
    return [load_style(p.stem) for p in sorted(STYLE_DIR.glob("*.json"))]


# ---------------------------------------------------------------- подбор под цель

def score(style: dict, goals: dict, boldness: float = 0.3, fmt: str | None = None) -> float:
    """0–100: насколько стиль даёт нужный выхлоп.

    goals — веса целей 0–5 (что важнее). Совпадение по целям — основа; смелость
    сдвигает выбор от проверенного мейнстрима к нише и антитренду; формат, под который
    стиль не рассчитан, сильно штрафуется, но не запрещается.
    """
    weights = {g: max(0.0, float(goals.get(g, 0))) for g in GOALS}
    total = sum(weights.values()) or 1.0
    fit = sum(weights[g] * style["fit"][g] for g in GOALS) / (5 * total)      # 0..1
    tier_gap = abs(TIER_BOLDNESS[style["tier"]] - max(0.0, min(1.0, boldness)))
    value = 100 * (0.8 * fit + 0.2 * (1 - tier_gap))
    if fmt and fmt not in style["formats"]:
        value *= 0.6
    return round(value, 1)


def recommend(goals: dict, boldness: float = 0.3, fmt: str | None = None) -> list:
    """Стили по убыванию пользы для цели: [(балл, стиль)]."""
    ranked = [(score(s, goals, boldness, fmt), s) for s in all_styles()]
    return sorted(ranked, key=lambda pair: -pair[0])


# ---------------------------------------------------------------- бриф ролика

DEFAULT_BRIEF = {
    "style": "viral-behind",
    "formats": ["9:16"],
    "variants": [],
    "goals": {"reach": 4, "retention": 4, "trust": 3, "saves": 2, "sales": 2},
    "boldness": 0.3,
    "overrides": {},
    "notes": "",
}


def brief_path(stem: str) -> Path:
    return WORK_DIR / stem / "brief.json"


BRIEF_TYPES = {"style": (str, "строкой"), "formats": (list, "списком"), "variants": (list, "списком"),
               "goals": (dict, "объектом"), "boldness": ((int, float), "числом"),
               "overrides": (dict, "объектом"), "notes": (str, "строкой")}


def check_brief(brief, where: str) -> dict:
    """Типы полей брифа. Его пишут и студия, и агенты руками — ошибка должна называть поле.

    Раньше битый brief.json одного ролика ронял весь список роликов студии (ошибка 500,
    «сервер не отвечает»), а goals списком вместо объекта — разбор брифа для мозга.
    """
    if not isinstance(brief, dict):
        raise StyleError(f"{where}: бриф должен быть объектом JSON {{…}}")
    for key, (kind, name) in BRIEF_TYPES.items():
        value = brief.get(key)
        if key in brief and (not isinstance(value, kind) or isinstance(value, bool)):
            raise StyleError(f"{where}: поле {key} должно быть {name}, а не {value!r}")
    for key in ("formats", "variants"):
        if not all(isinstance(x, str) for x in brief.get(key, [])):
            raise StyleError(f"{where}: в {key} — только строки, а не {brief[key]!r}")
    for goal, value in brief.get("goals", {}).items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 5:
            raise StyleError(f"{where}: цель {goal} — число от 0 до 5, а не {value!r}")
    return brief


def project_brief(stem: str) -> dict:
    """Умолчания брифа из проекта ролика (projects/<проект>/project.json → brief).

    Без этого ролик заказчицы без своего brief.json собирался бы в стиле антишколы: проект —
    граница, через которую чужие умолчания не протекают (14.10.2026).
    """
    import projects
    try:
        project = projects.of_or_default(stem)
    except projects.ProjectError:
        return {}                   # проектов нет (чистая проверка) — умолчания скилла
    return check_brief(copy.deepcopy(project.config["brief"]), f"projects/{project.name}/project.json → brief")


def load_brief(stem: str) -> dict:
    """Бриф поверх умолчаний проекта и скилла. Сломанный файл — StyleError с именем файла и поля."""
    path = brief_path(stem)
    brief = copy.deepcopy(DEFAULT_BRIEF)
    brief.update(project_brief(stem))
    if path.exists():
        where = f"work/{stem}/brief.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise StyleError(f"{where}: битый JSON ({e}) — поправь файл или пересохрани бриф в студии")
        brief.update(check_brief(data, where))
        brief["exists"] = True
    return brief


def save_brief(stem: str, data: dict) -> dict:
    """Проверяет и пишет бриф. Ошибка — громкая, файл при ней не трогается."""
    brief = copy.deepcopy(DEFAULT_BRIEF)
    brief.update({k: v for k, v in check_brief(data, "бриф").items() if k in DEFAULT_BRIEF})
    load_style(brief["style"])
    for variant in brief["variants"]:
        load_style(variant)
    if not brief["formats"]:
        raise StyleError("В брифе не выбран ни один формат")
    for fmt in brief["formats"]:
        formats.get(fmt)
    brief["boldness"] = max(0.0, min(1.0, float(brief["boldness"])))
    path = brief_path(stem)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(brief, ensure_ascii=False, indent=1), encoding="utf-8")
    return brief


def effective(style: dict, overrides: dict | None = None) -> dict:
    """Стиль с ручными правками из брифа: {"captions.mode": "phrase", "camera.base_zoom": 1.05}."""
    style = copy.deepcopy(style)
    for key, value in (overrides or {}).items():
        block, _, field = key.partition(".")
        if block not in style["params"] or not field:
            raise StyleError(f"Правка «{key}» — нет такого параметра стиля")
        style["params"][block][field] = value
    return validate(style)


# ---------------------------------------------------------------- быстрый конвейер

def font_family(key: str) -> str:
    """Имя семейства из файла шрифта — по нему libass ищет шрифт (name ID 1)."""
    from fontTools.ttLib import TTFont
    path = FONT_DIR / FONTS[key]["file"]
    font = TTFont(path, fontNumber=0, lazy=True)
    try:
        return font["name"].getDebugName(1) or path.stem
    finally:
        font.close()


def to_fast_preset(style: dict, fmt: str = formats.DEFAULT, base: str = "viral") -> dict:
    """Пресет быстрого конвейера (reels.py) из стиля: рез, крупность, субтитры, цвет, формат.

    Размеры субтитров заданы для вертикали 1080×1920 и пересчитываются по высоте кадра:
    горизонталь в 1080 px высотой получает шрифт вдвое мельче — ровно как на экране.
    """
    preset = load_preset(base)
    p = style["params"]
    width, height = formats.size(fmt)
    k = height / 1920
    preset["name"] = f"style:{style['id']}"
    preset["video"]["width"], preset["video"]["height"] = width, height
    preset["format"] = fmt

    preset["cut"]["enabled"] = bool(p["pace"]["cut_pauses"])
    preset["cut"]["max_silence"] = float(p["pace"]["max_silence"])

    energy = p["camera"]["punch"]
    preset["motion"]["punch_in"] = energy != "none"
    level = float(p["camera"]["punch_level"])
    if energy == "often":
        preset["motion"]["zoom_cycle"] = [1.0, round(level, 3), 1.04, round((1 + level) / 2, 3)]
        preset["motion"]["min_hold_sec"] = 2.0
    elif energy == "rare":
        preset["motion"]["zoom_cycle"] = [1.0, round(level, 3)]
        preset["motion"]["min_hold_sec"] = 5.0

    caps = p["captions"]
    subs = preset["subs"]
    subs["enabled"] = caps["mode"] != "none"
    subs["words_per_phrase"] = {"words": 1, "karaoke": 3, "phrase": 3, "sentence": 6}.get(caps["mode"], 3)
    subs["uppercase"] = caps["case"] == "upper"
    subs["font"] = font_family(caps["font"])
    subs["font_size"] = int(round(92 * float(caps["size"]) * (k if fmt != "9:16" else 1.0)
                                  * (1.0 if caps["mode"] in ("words", "karaoke") else 0.85)))
    subs["color_base"] = caps["color"].lstrip("#").upper()
    subs["color_active"] = caps["highlight"].lstrip("#").upper()
    subs["pop_in"] = caps["animation"] == "pop"
    subs["active_scale"] = 112 if caps["mode"] in ("karaoke", "words") else 100
    # плашка под текстом: белая под тёмный текст (родной текст Reels), полупрозрачная тёмная — под светлый
    subs["box"] = bool(caps.get("box"))
    dark_text = is_dark(caps["color"])
    subs["box_color"] = "FFFFFF" if dark_text else "0C0C0E"
    subs["box_alpha"] = 0 if dark_text else 0x40
    subs["box_pad"] = int(round(14 * (k if fmt != "9:16" else 1.0)))
    margins = {"lower": 0.22, "chest": 0.36, "center": 0.48, "top": 0.72, "side": 0.5}
    subs["margin_v"] = int(round(height * margins[caps["position"]]))
    subs["margin_h"] = int(round(width * 0.1))

    preset["look"] = look(style)
    return preset


def is_dark(color: str) -> bool:
    """Тёмный ли цвет текста — под него плашка светлая. По яркости, а не по списку:
    правка брифа «#222222» иначе давала тёмный текст на тёмной плашке."""
    r, g, b = (int(color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.4


def look(style: dict) -> dict:
    """Цвет для prep.py и render.py: яркость в шкале CapCut и грейд стиля."""
    color = style["params"]["color"]
    return {"enabled": True, "brightness": float(color.get("brightness", 0)),
            "grade": color.get("grade", "natural")}


# ---------------------------------------------------------------- режиссёрский конвейер

def camera_cfg(style: dict) -> dict:
    """Настройки камеры-оператора (track.solve_camera) из стиля."""
    cam = style["params"]["camera"]
    cfg = {"base_zoom": float(cam["base_zoom"])}
    if cam.get("push_in"):
        cfg["push"] = 0.006        # +0.06 за 10 с мысли, сброс на пике следующего акцента (track.zoom_plan)
    if cam.get("punch") == "none" and cfg["base_zoom"] <= 1.0:
        # камера стоит: ни слежения, ни автоприближения — как поставили штатив
        cfg.update({"dead_zone_x": 1.0, "dead_zone_y": 1.0, "max_zoom": cfg["base_zoom"]})
    return cfg


def kit_captions(style: dict) -> dict:
    """Субтитры для страниц HyperFrames: группировка вспышек и вид."""
    caps = dict(style["params"]["captions"])
    caps["css_font"] = FONTS[caps["font"]]["css"]
    caps["font_file"] = FONTS[caps["font"]]["file"]
    caps["font_weight"] = FONTS[caps["font"]]["weight"]
    return caps


def director_brief(stem: str | None = None, brief: dict | None = None) -> str:
    """Текст для режиссёра (Claude или Codex): что за выхлоп нужен и как его делать."""
    brief = brief or (load_brief(stem) if stem else copy.deepcopy(DEFAULT_BRIEF))
    style = effective(load_style(brief["style"]), brief.get("overrides"))
    p = style["params"]
    goals = ", ".join(f"{GOALS[g]} {v}/5" for g, v in brief["goals"].items() if g in GOALS)
    lines = [
        f"Стиль: {style['name']} ({TIERS[style['tier']]}) — {style['summary']}",
        f"Как выглядит: {style['looks_like']}",
        f"Цели ролика: {goals}. Смелость {brief['boldness']:.1f} (0 — проверенное, 1 — эксперимент).",
        f"Форматы: {', '.join(brief['formats'])}.",
        f"Темп: что-то меняется в кадре примерно раз в {p['pace']['change_every']} с; "
        f"рез пауз в стиле: {'да' if p['pace']['cut_pauses'] else 'нет'} "
        "(в режиссёрском конвейере паузы режем только с явного «да» автора).",
        f"Камера: база {p['camera']['base_zoom']}, наезды — {p['camera']['punch']}, "
        f"уровень {p['camera']['punch_level']}{', медленный наезд через мысль' if p['camera']['push_in'] else ''}.",
        f"Субтитры: {p['captions']['mode']}, {p['captions']['case']}, шрифт {p['captions']['font']}, "
        f"позиция {p['captions']['position']}, анимация {p['captions']['animation']}.",
        f"Графика: плотность {p['graphics']['density']}/3; за спиной — {p['graphics']['behind_text']}, "
        f"карточки — {p['graphics']['cards']}, вырезка — {p['graphics']['cutout']}, плашки — {p['graphics']['lower_thirds']}.",
        f"Визуализации данных (скилл viz): {VIZ_LEVELS[p['graphics'].get('viz', 'sometimes')]}.",
        f"Звук: эффекты {p['sound']['sfx']}, музыка {p['sound']['music']}. Цвет: {p['color']['grade']}, "
        f"яркость {p['color']['brightness']}.",
        f"Указания стиля: {style['director']}",
        f"Риски: {style['risks']}",
    ]
    if brief.get("variants"):
        names = ", ".join(load_style(v)["name"] for v in brief["variants"])
        lines.append(f"Варианты для A/B: {names} — каждый отдельным проектом (compose --variant).")
    if brief.get("notes"):
        lines.append(f"Заметки автора: {brief['notes']}")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description="Стили монтажа: каталог, подбор под цель, проверка")
    ap.add_argument("--goals", default="reach=4,retention=4,trust=3,saves=2,sales=2",
                    help="веса целей 0–5: reach,retention,trust,saves,sales")
    ap.add_argument("--bold", type=float, default=0.3, help="смелость 0 (мейнстрим) … 1 (антитренд)")
    ap.add_argument("--format", default=None, help="9:16, 16:9, 1:1, 4:5")
    ap.add_argument("--check", action="store_true", help="только проверить все стили")
    ap.add_argument("--brief", help="показать текст брифа для ролика (имя без расширения)")
    args = ap.parse_args()

    try:
        if args.check:
            styles = all_styles()
            for s in styles:
                to_fast_preset(s, s["formats"][0])
            print(f"✓ стилей: {len(styles)}, все валидны и собираются в пресет")
            return
        if args.brief:
            print(director_brief(args.brief))
            return
        goals = {}
        for pair in args.goals.split(","):
            key, _, value = pair.partition("=")
            if key.strip() not in GOALS:
                sys.exit(f"Цель «{key}» не знаю. Есть: {', '.join(GOALS)}")
            goals[key.strip()] = float(value or 0)
        for value, style in recommend(goals, args.bold, args.format):
            print(f"{value:5.1f}  {style['name']:<32} {TIERS[style['tier']]:<11} {style['id']}")
    except StyleError as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
