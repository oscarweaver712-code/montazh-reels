#!/usr/bin/env python3
"""Дорожки ролика для монтажной студии и ручные правки человека.

Монтаж делает агент: рез — edit.json, камера и субтитры — director.json, графика — page.py →
studio/<имя>/index.html. Студия показывает всё это дорожками, как CapCut, и даёт поправить руками.
Правки руками живут отдельно — в work/<имя>/timeline.json, — потому что page.py агента при каждом
запуске перезаписывает director.json: положи правку туда, и следующий запуск её молча сотрёт.
Здесь же правки ложатся поверх решений агента последними — и в сборке (compose.scene), и в
предпросмотре студии, — одной функцией.

Что можно поправить:
  камера     — сдвинуть, растянуть, убрать или добавить наезд;
  субтитры   — спрятать кусок или вернуть спрятанный, исправить слово;
  субтитры   — ещё шрифт, цвет, цвет акцента, размер и высота на кадре;
  графика    — сдвинуть блок во времени или выключить; подвинуть и масштабировать на кадре, сменить
               шрифт и цвет, переписать текст (presets/studio/layers.js — на самой странице);
  звуки      — сдвинуть или выключить.
Рез (какие куски дубля в ролике) руками не правится: он ставится по тишине (инвариант 3), и
двигать его мышкой мимо тишины — значит резать слова. Рез меняется словами через мозг.

  .venv/bin/python scripts/timeline.py IMG_1799             # дорожки ролика (JSON)
  .venv/bin/python scripts/timeline.py IMG_1799 --edits     # только ручные правки
"""
import argparse
import copy
import json
import os
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ROOT, WORK_DIR

LAYERS_JS = ROOT / "presets" / "studio" / "layers.js"
FONT_DIR = ROOT / "presets" / "fonts"
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
EDITS_NAME = "timeline.json"
HISTORY_DEPTH = 60
NEAR = 0.02                     # одна и та же граница наезда или зоны — с точностью до 20 мс
EMPTY = {"camera": {"remove": [], "add": []},
         "captions": {"hide_add": [], "hide_remove": [], "fixes": {}, "style": {}},
         "items": {}, "texts": []}
# Удары страницы, поставленные агентом прямо в beats: показываются на дорожке «Переходы»
# замком — правятся словами через мозг, а не мышкой (они часть графики страницы)
PAGE_BEATS = {"splice": "Склейка: смаз и вспышка", "whip": "Смена плана: смаз", "flash": "Вспышка"}
ITEM_KEYS = ("shift", "mute", "dx", "dy", "scale", "font", "color", "texts")
CAPTION_STYLE_KEYS = ("font", "color", "accent", "scale", "dy")
TEXT_ANIMS = {"pop": "Влёт с размытием", "fade": "Проявление", "slide": "Снизу вверх", "none": "Без анимации"}
TEXT_DEFAULT = {"size": 120, "font": "Oswald-Bold", "color": "#F2EBDD", "anim": "pop", "box": ""}


def fonts() -> list:
    """Шрифты, которые можно поставить слою или субтитрам: всё из presets/fonts (OFL, с кириллицей)."""
    return sorted(p.stem for p in FONT_DIR.glob("*.ttf"))


class EditError(ValueError):
    """Правку не принять — с понятной причиной по-русски."""


def edits_path(stem: str) -> Path:
    return WORK_DIR / stem / EDITS_NAME


def history_path(stem: str) -> Path:
    return WORK_DIR / stem / "timeline.history.json"


def future_path(stem: str) -> Path:
    """Отменённые правки — их возвращает «Повторить» (redo); новая правка этот список сбрасывает."""
    return WORK_DIR / stem / "timeline.future.json"


def normalize(raw: dict) -> dict:
    """Полная форма правок: недостающие разделы — пустые, лишние ключи сохраняются."""
    out = copy.deepcopy(EMPTY)
    for key, value in (raw or {}).items():
        if key in ("camera", "captions") and isinstance(value, dict):
            out[key].update(value)
        else:
            out[key] = value
    return out


def load_edits(stem: str) -> dict:
    path = edits_path(stem)
    if not path.exists():
        return normalize({})
    try:
        return normalize(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as e:
        raise EditError(f"work/{stem}/{EDITS_NAME} битый ({e.msg}, строка {e.lineno}) — "
                        f"поправь руками или удали файл: ручные правки пропадут, монтаж агента останется")


def is_empty(edits: dict) -> bool:
    e = normalize(edits)
    return not (e["camera"]["remove"] or e["camera"]["add"] or e["captions"]["hide_add"]
                or e["captions"]["hide_remove"] or e["captions"]["fixes"] or e["captions"]["style"] or e["items"]
                or e["texts"])


def _write_json(path: Path, data) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def save_edits(stem: str, edits: dict) -> None:
    path = edits_path(stem)
    if is_empty(edits):
        path.unlink(missing_ok=True)          # нет правок — нет и файла: агенту нечего читать
        return
    edits = dict(edits, _note="Ручные правки из студии поверх решений агента (scripts/timeline.py). "
                              "Агент их не затирает; убрать — на дорожке или удалив этот файл.")
    _write_json(path, edits)


def _near(a: list, b: list) -> bool:
    return abs(float(a[0]) - float(b[0])) <= NEAR and abs(float(a[1]) - float(b[1])) <= NEAR


def apply_director(director: dict, edits: dict) -> dict:
    """director.json агента + правки человека → то, по чему считаются камера и субтитры."""
    d = copy.deepcopy(director or {})
    e = normalize(edits)
    cam = e["camera"]
    punches = [p for p in d.get("punches") or [] if not any(_near(p, r) for r in cam["remove"])]
    d["punches"] = punches + [list(p) for p in cam["add"]]
    caps = e["captions"]
    hide = [h for h in d.get("hide_captions") or [] if not any(_near(h, r) for r in caps["hide_remove"])]
    d["hide_captions"] = hide + [list(h) for h in caps["hide_add"]]
    if caps["fixes"]:
        d["text_fixes"] = {**(d.get("text_fixes") or {}), **{str(k): v for k, v in caps["fixes"].items()}}
    return d


def edits_js(edits: dict) -> str:
    """edits.js проекта: то, что правится на самой странице, — слои графики и вид субтитров."""
    e = normalize(edits)
    data = {"items": {k: {f: v[f] for f in ITEM_KEYS if v.get(f) not in (None, "", 0, False)}
                      for k, v in e["items"].items()},
            "captions": e["captions"]["style"], "texts": e["texts"]}
    data["items"] = {k: v for k, v in data["items"].items() if v}
    return "window.EDITS = " + json.dumps(data, ensure_ascii=False) + ";\n"


# ---------- разметка страницы ----------

VOID = {"br", "img", "source", "meta", "link", "input", "hr", "wbr", "track", "area", "col", "embed", "param"}
SVG_LEAF = {"path", "circle", "line", "rect", "polyline", "polygon", "ellipse", "use", "stop"}


class _Page(HTMLParser):
    """Блоки графики (.g в #behind/#front), звуки и видео страницы — с местом тега в тексте."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.items, self.media, self.text = [], [], [], {}

    def _item(self):
        for tag, attrs in reversed(self.stack):
            if attrs.get("_item"):
                return attrs.get("id")
        return None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        parent = self.stack[-1][1].get("id") if self.stack else None
        classes = (a.get("class") or "").split()
        if tag in ("audio", "video"):
            self.media.append({"tag": tag, "id": a.get("id"), "attrs": a, "pos": self.getpos(),
                               "item": self._item(), "text": self.get_starttag_text()})
        if tag in VOID or tag in SVG_LEAF:
            return
        if parent in ("behind", "front") and "g" in classes and a.get("id"):
            a["_item"] = True
            self.items.append({"id": a["id"], "layer": parent, "classes": classes})
            self.text[a["id"]] = []
        self.stack.append((tag, a))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and tag not in SVG_LEAF and self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID or tag in SVG_LEAF:
            return
        while self.stack:
            if self.stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        item = self._item()
        if item and data.strip() and len(" ".join(self.text[item])) < 60:
            self.text[item].append(data.strip())


KIND_LABELS = (("bg", "фон"), ("card", "карточка"), ("doc", "документ"), ("censor", "цензура"),
               ("cta", "плашка в конце"), ("big", "крупное слово"), ("gk", "окно"))


def _kind_label(item: dict) -> str:
    """Подпись слоя без текста: по классу или имени — «фон ox», а не «#bg-ox»."""
    tail = item["id"].split("-", 1)[-1] if "-" in item["id"] else item["id"]
    for key, name in KIND_LABELS:
        if key in item["classes"] or item["id"].startswith(key + "-"):
            return f"{name} {tail}"
    return f"рисунок {item['id']}"


def parse_page(html: str) -> dict:
    p = _Page()
    p.feed(html)
    items = [{**it, "label": " ".join(p.text.get(it["id"], []))[:60] or _kind_label(it)} for it in p.items]
    return {"items": items, "media": p.media}


def _set_attr(tag_text: str, name: str, value: str | None) -> str:
    pattern = re.compile(rf'\s{re.escape(name)}="[^"]*"')
    if value is None:
        return pattern.sub("", tag_text)
    if pattern.search(tag_text):
        return pattern.sub(f' {name}="{value}"', tag_text, count=1)
    return re.sub(r"\s*/?>$", lambda m: f' {name}="{value}"' + m.group(0), tag_text, count=1)


HEAD_ANCHOR = '<script src="assets/gsap.min.js"></script>'
HOOK = "REELS_EDITS(tl)"
# ошибка в layers.js без переброса приходит как «Script error.» — строка страницы перебрасывает её с текстом
HOOK_LINE = "try { REELS_EDITS(tl); } catch (e) { throw new Error(`правки студии: ${e.message}`); }"
OLD_SCRIPT = '<script src="fx.js"></script>'      # страницы 16.10.2026 с эффектами света — те убраны
TIMELINE_LINE = 'window.__timelines["main"] = tl;'


def patch_page(html: str, edits: dict, fps: float = 30) -> str:
    """Страница + ручные правки: подключить layers.js и edits.js, вызвать их, сдвинуть звук в разметке.

    Повторный вызов ничего не меняет (исходные времена хранятся в data-orig-*), правку можно убрать —
    разметка вернётся к исходной. Страница не той формы — громкая ошибка, а не тихий пропуск.
    """
    e = normalize(edits)
    html = html.replace(OLD_SCRIPT, '<script src="layers.js"></script>')
    html = html.replace("throw new Error(`правки и свет: ${e.message}`)", "throw new Error(`правки студии: ${e.message}`)")
    if 'src="layers.js"' not in html:
        if HEAD_ANCHOR not in html:
            raise EditError("на странице нет подключения GSAP — правки студии некуда вставить")
        html = html.replace(HEAD_ANCHOR, HEAD_ANCHOR + '\n    <script src="layers.js"></script>'
                                                      '\n    <script src="edits.js"></script>', 1)
    if HOOK not in html:
        if html.count(TIMELINE_LINE) != 1:
            raise EditError("на странице не одна строка window.__timelines[\"main\"] = tl — "
                            "правки студии некуда вставить")
        html = html.replace(TIMELINE_LINE, f"{HOOK_LINE}\n      {TIMELINE_LINE}", 1)

    page = parse_page(html)
    known = {it["id"] for it in page["items"]} | {m["id"] for m in page["media"] if m["id"]}
    missing = [k for k, v in e["items"].items() if any(v.get(f) for f in ITEM_KEYS) and k not in known]
    if missing:
        raise EditError(f"на странице нет {', '.join('#' + m for m in missing)} — блок переименовали или "
                        f"убрали; сними правку на дорожке")
    # звук и видео: их время HyperFrames берёт из атрибутов, поэтому сдвиг — прямо в разметке
    out, cursor, lines = [], 0, html.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    for m in page["media"]:
        own = e["items"].get(m["id"] or "", {}) if m["tag"] == "audio" else {}
        holder = e["items"].get(m["item"] or "", {}) if m["item"] else {}
        shift = float(own.get("shift") or 0) + float(holder.get("shift") or 0)
        mute = bool(own.get("mute"))
        tag = m["text"]
        attrs = m["attrs"]
        orig_start = attrs.get("data-orig-start", attrs.get("data-start"))
        orig_vol = attrs.get("data-orig-volume", attrs.get("data-volume"))
        new = tag
        if orig_start is not None and attrs.get("id") not in ("aroll", "cutout"):
            if shift:
                start = round(float(orig_start) + shift, 3)
                if start < 0:
                    raise EditError(f"#{m['id'] or m['item']} после сдвига начинается раньше ролика")
                new = _set_attr(_set_attr(new, "data-start", f"{start:.3f}"), "data-orig-start", orig_start)
            elif "data-orig-start" in attrs:
                new = _set_attr(_set_attr(new, "data-start", orig_start), "data-orig-start", None)
        if m["tag"] == "audio":
            if mute:
                new = _set_attr(_set_attr(new, "data-volume", "0"), "data-orig-volume", orig_vol or "1")
            elif "data-orig-volume" in attrs:
                restored = attrs["data-orig-volume"]
                new = _set_attr(new, "data-orig-volume", None)
                new = _set_attr(new, "data-volume", restored) if restored else new
        if new != tag:
            line, col = m["pos"]
            at = offsets[line - 1] + col
            if html[at:at + len(tag)] != tag:
                raise EditError("разметка страницы разобралась не так, как записана — правку не вставляю")
            out.append(html[cursor:at])
            out.append(new)
            cursor = at + len(tag)
    out.append(html[cursor:])
    return "".join(out)


# ---------- дорожки ----------

def _load(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def page_beats(html: str) -> list:
    """Удары страницы с числом в скобках: splice(12.34), whip(…), flash(…) — для дорожки переходов."""
    script = html.split("const tl = gsap.timeline", 1)[-1]
    found = []
    for m in re.finditer(r"(?<![\w.])(" + "|".join(PAGE_BEATS) + r")\(\s*(-?\d+(?:\.\d+)?)", script):
        found.append({"kind": m.group(1), "t": float(m.group(2)), "label": PAGE_BEATS[m.group(1)]})
    return sorted(found, key=lambda b: b["t"])


def latest_output(stem: str) -> Path | None:
    import projects
    try:
        out = projects.output_dir(stem)
    except projects.ProjectError:
        return None
    found = [p for p in out.glob(f"{stem}_v*.mp4") if re.fullmatch(rf"{re.escape(stem)}_v\d+", p.stem)]
    return max(found, key=lambda p: int(p.stem.rsplit("_v", 1)[1])) if found else None


def tracks(stem: str) -> dict:
    """Всё, что монтажная показывает на дорожках, — одним ответом. Ничего не меняет."""
    import compose
    work = WORK_DIR / stem
    sc = compose.scene(stem)
    director = _load(work / "director.json", {}) or {}
    edits = sc["edits"]
    fps, duration = sc["fps"], sc["duration"]
    meta = sc["meta"]

    clips, acc = [], 0.0
    for s0, s1 in meta.get("segments", []):
        clips.append({"a": round(acc, 3), "b": round(acc + s1 - s0, 3), "src": [s0, s1]})
        acc += s1 - s0

    agent_punches = director.get("punches") or []
    camera = []
    for p in sc["director"]["punches"]:
        human = any(_near(p, h) for h in edits["camera"]["add"])
        camera.append({"a": p[0], "b": p[1], "zoom": p[2], "ease": p[3:5], "by": "human" if human else "agent"})
    zoom = [round(z, 3) for z, _, _ in sc["frames"][::max(1, int(fps // 10))]]

    hide = []
    for h in sc["director"].get("hide_captions") or []:
        human = any(_near(h, x) for x in edits["captions"]["hide_add"])
        hide.append({"a": h[0], "b": h[1], "by": "human" if human else "agent"})
    fixes = {int(k): v for k, v in (sc["director"].get("text_fixes") or {}).items()}
    words = [{"i": i, "a": w["start"], "b": w["end"], "text": fixes.get(i, w["word"]), "heard": w["word"],
              "fixed": str(i) in {str(k) for k in edits["captions"]["fixes"]}}
             for i, w in enumerate(sc["words"])]

    page = ROOT / "studio" / stem / "index.html"
    html = page.read_text(encoding="utf-8") if page.exists() else ""
    parsed = parse_page(html) if html else {"items": [], "media": []}
    items = [{**it, **{k: edits["items"].get(it["id"], {}).get(k) for k in ITEM_KEYS}}
             for it in parsed["items"]]
    sounds = []
    for m in parsed["media"]:
        if m["tag"] != "audio" or not m["id"]:
            continue
        a = m["attrs"]
        own = edits["items"].get(m["id"], {})
        start = float(a.get("data-orig-start", a.get("data-start", 0)))
        sounds.append({"id": m["id"], "name": Path(a.get("src", "")).stem, "start": start,
                       "dur": float(a.get("data-duration") or 0.5), "shift": own.get("shift"),
                       "mute": own.get("mute"), "volume": float(a.get("data-orig-volume", a.get("data-volume", 1)) or 1)})

    out = latest_output(stem)
    edited_at = edits_path(stem).stat().st_mtime if edits_path(stem).exists() else 0
    return {"stem": stem, "duration": duration, "fps": fps, "width": sc["width"], "height": sc["height"],
            "format": sc["fmt"], "clips": clips, "camera": camera, "zoom": zoom, "zoom_step": max(1, int(fps // 10)) / fps,
            "base_zoom": (sc["style"] or {}).get("params", {}).get("camera", {}).get("base_zoom"),
            "captions": [{k: c[k] for k in ("t0", "t1", "text", "accent")} for c in sc["chunks"]],
            "hide": hide, "words": words, "items": items, "sounds": sounds,
            "beats": page_beats(html), "fonts": fonts(), "caption_style": edits["captions"]["style"],
            "texts": edits["texts"], "text_anims": TEXT_ANIMS,
            "zones": [{"name": n, "rect": list(r)} for n, r in __import__("formats").grey_zones(sc["fmt"])],
            "can_undo": bool(_load(history_path(stem), [])), "can_redo": bool(_load(future_path(stem), [])),
            "caption_base": {k: v for k, v in (sc["caps"] or {}).items() if isinstance(v, (str, int, float))},
            "has_page": bool(html), "output": out.name if out else None,
            "stale": bool(out and edited_at > out.stat().st_mtime),
            "has_edits": not is_empty(edits), "agent_punches": len(agent_punches)}


PEAKS_RATE = 50                 # столбиков волны в секунду


def peaks(stem: str) -> dict:
    """Волна звука дубля для дорожки видео: максимум громкости на каждые 20 мс, 0…1.

    Считается один раз одним ffmpeg (звук в 2 кГц — это мегабайты, а не гигабайты), кладётся
    рядом с дублем и пересчитывается, только если дубль пересобран.
    """
    import subprocess
    from array import array
    from common import ffmpeg_bin
    aroll = WORK_DIR / stem / "aroll.mp4"
    cache = WORK_DIR / stem / "aroll.peaks.json"
    if not aroll.exists():
        raise EditError(f"у {stem} нет дубля — волну не из чего строить")
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("mtime") == aroll.stat().st_mtime:
            return data
    rate = 2000
    out = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(aroll), "-vn", "-ac", "1", "-ar", str(rate),
                          "-f", "s16le", "-"], capture_output=True)
    if out.returncode != 0:
        raise EditError(f"волну не построить: {out.stderr.decode('utf-8', 'replace').strip()[-200:]}")
    samples = array("h")
    samples.frombytes(out.stdout[:len(out.stdout) // 2 * 2])
    step = rate // PEAKS_RATE
    raw = [max((abs(x) for x in samples[i:i + step]), default=0) for i in range(0, len(samples), step)]
    top = max(raw, default=1) or 1
    data = {"rate": PEAKS_RATE, "peaks": [round(v / top, 3) for v in raw], "mtime": aroll.stat().st_mtime}
    _write_json(cache, data)
    return data


# ---------- правки ----------

def _time(x, duration: float, what: str) -> float:
    try:
        t = round(float(x), 3)
    except (TypeError, ValueError):
        raise EditError(f"{what}: не число")
    if not 0 <= t <= duration + 1e-6:
        raise EditError(f"{what}: {t} с — вне ролика (0–{duration:.2f})")
    return t


def _span(a, b, duration: float, what: str, shortest: float = 0.1) -> list:
    a, b = _time(a, duration, what), _time(b, duration, what)
    if b - a < shortest:
        raise EditError(f"{what}: короче {shortest} с")
    return [a, b]


def merge_item_style(cur: dict, changes: dict) -> dict:
    """Правка вида слоя: dx, dy, scale, font, color, texts. Пустое значение снимает свойство."""
    cur = dict(cur)
    for key, value in changes.items():
        if value is None or value == "":
            cur.pop(key, None)
        elif key in ("dx", "dy"):
            v = round(float(value), 1)
            if abs(v) > 3000:
                raise EditError("слой уехал за кадр — сдвиг больше 3000 px")
            cur[key] = v
        elif key == "scale":
            v = round(float(value), 3)
            if not 0.2 <= v <= 4:
                raise EditError("масштаб слоя — от 0.2 до 4")
            cur[key] = v
        elif key == "font":
            if value not in fonts():
                raise EditError(f"шрифта «{value}» нет в presets/fonts")
            cur[key] = value
        elif key == "color":
            if not COLOR_RE.match(str(value)):
                raise EditError("цвет — в виде #RRGGBB")
            cur[key] = str(value).upper()
        elif key == "texts":
            texts = [str(t) for t in value]
            if len(texts) > 40 or any(len(t) > 300 for t in texts):
                raise EditError("текст слоя — до 40 кусков по 300 знаков")
            cur[key] = texts
        else:
            raise EditError(f"у слоя нет свойства «{key}»")
    return {k: v for k, v in cur.items() if v not in (None, "", 0, False) and not (k == "scale" and v == 1)}


def merge_caption_style(style: dict, changes: dict) -> dict:
    """Правка вида субтитров: font, color, accent, scale, dy. Пустое значение снимает свойство."""
    style = dict(style)
    for key, value in changes.items():
        if key not in CAPTION_STYLE_KEYS:
            raise EditError(f"у субтитров нет свойства «{key}»")
        if value is None or value == "":
            style.pop(key, None)
        elif key == "font":
            if value not in fonts():
                raise EditError(f"шрифта «{value}» нет в presets/fonts")
            style[key] = value
        elif key in ("color", "accent"):
            if not COLOR_RE.match(str(value)):
                raise EditError("цвет — в виде #RRGGBB")
            style[key] = str(value).upper()
        elif key == "scale":
            v = round(float(value), 3)
            if not 0.4 <= v <= 2.5:
                raise EditError("размер субтитров — от 0.4 до 2.5")
            style[key] = v
        elif key == "dy":
            v = round(float(value), 1)
            if abs(v) > 1500:
                raise EditError("субтитры уехали за кадр")
            style[key] = v
    return {k: v for k, v in style.items() if not (k == "scale" and v == 1) and not (k == "dy" and v == 0)}


def merge_text(cur: dict, changes: dict, duration: float, width: int, height: int) -> dict:
    """Свой текст на кадре (кнопка «Текст» в монтажной): что, когда, где, каким шрифтом и как влетает."""
    cur = dict(cur)
    for key, value in changes.items():
        if key == "text":
            text = str(value).strip("\n")
            if not text.strip():
                raise EditError("пустой текст — убери слой, а не стирай текст")
            if len(text) > 160:
                raise EditError("текст на кадре — до 160 знаков: длиннее не прочесть за пару секунд")
            cur["text"] = text
        elif key in ("t0", "t1"):
            cur[key] = _time(value, duration, "время текста")
        elif key in ("x", "y"):
            v = round(float(value), 1)
            if not -200 <= v <= (width if key == "x" else height) + 200:
                raise EditError("текст за кадром")
            cur[key] = v
        elif key == "size":
            v = round(float(value))
            if not 24 <= v <= 400:
                raise EditError("размер текста — от 24 до 400 px")
            cur[key] = v
        elif key == "font":
            if value not in fonts():
                raise EditError(f"шрифта «{value}» нет в presets/fonts")
            cur[key] = value
        elif key in ("color", "box"):
            if value in (None, "") and key == "box":
                cur[key] = ""
            elif not COLOR_RE.match(str(value)):
                raise EditError("цвет — в виде #RRGGBB")
            else:
                cur[key] = str(value).upper()
        elif key == "anim":
            if value not in TEXT_ANIMS:
                raise EditError(f"анимации «{value}» нет: {', '.join(TEXT_ANIMS)}")
            cur[key] = value
        else:
            raise EditError(f"у текста нет свойства «{key}»")
    if cur.get("t1", 0) - cur.get("t0", 0) < 0.5:
        raise EditError("текст на экране короче полсекунды — не прочесть")
    return cur


def apply_op(stem: str, op: dict) -> dict:
    """Одна правка с дорожки. Предыдущее состояние уходит в историю — его вернёт undo."""
    import compose
    kind = op.get("op")
    edits = load_edits(stem)
    hist = _load(history_path(stem), []) or []
    future = _load(future_path(stem), []) or []
    if kind == "undo":
        if not hist:
            raise EditError("отменять нечего")
        future.append(edits)
        edits = normalize(hist.pop())
        save_edits(stem, edits)
        _write_json(history_path(stem), hist)
        _write_json(future_path(stem), future[-HISTORY_DEPTH:])
        return edits
    if kind == "redo":
        if not future:
            raise EditError("повторять нечего")
        hist.append(edits)
        edits = normalize(future.pop())
        save_edits(stem, edits)
        _write_json(history_path(stem), hist[-HISTORY_DEPTH:])
        _write_json(future_path(stem), future)
        return edits
    before = copy.deepcopy(edits)
    sc = compose.scene(stem)
    duration = sc["duration"]
    director = _load(WORK_DIR / stem / "director.json", {}) or {}
    cam, caps = edits["camera"], edits["captions"]

    if kind in ("camera.move", "camera.delete"):
        old = [float(x) for x in op.get("from") or op.get("at") or []]
        if len(old) != 2:
            raise EditError("какой наезд — не указано")
        mine = [p for p in cam["add"] if _near(p, old)]
        theirs = [p for p in director.get("punches") or [] if _near(p, old)]
        if not mine and not theirs:
            raise EditError(f"наезда {old[0]:.2f}–{old[1]:.2f} нет — дорожка устарела, обнови страницу")
        base = list(mine[0] if mine else theirs[0])
        if mine:
            cam["add"] = [p for p in cam["add"] if not _near(p, old)]
        else:
            cam["remove"].append(old)
        if kind == "camera.move":
            a, b = _span(op["a"], op["b"], duration, "наезд", 0.2)
            zoom = float(op.get("zoom", base[2]))
            if not 1.0 <= zoom <= 2.0:
                raise EditError("крупность наезда — от 1.0 до 2.0")
            cam["add"].append([a, b, round(zoom, 3), *base[3:5]])
    elif kind == "camera.add":
        a, b = _span(op["a"], op["b"], duration, "наезд", 0.2)
        zoom = float(op.get("zoom") or 1.36)
        if not 1.0 <= zoom <= 2.0:
            raise EditError("крупность наезда — от 1.0 до 2.0")
        cam["add"].append([a, b, round(zoom, 3), 0.1, 0.25])
    elif kind in ("captions.hide", "captions.unhide", "captions.move_hide"):
        if kind == "captions.hide":
            caps["hide_add"].append(_span(op["a"], op["b"], duration, "зона без субтитров"))
        else:
            old = [float(x) for x in op.get("from") or op.get("at") or []]
            if len(old) != 2:
                raise EditError("какая зона — не указано")
            if any(_near(h, old) for h in caps["hide_add"]):
                caps["hide_add"] = [h for h in caps["hide_add"] if not _near(h, old)]
            elif any(_near(h, old) for h in director.get("hide_captions") or []):
                caps["hide_remove"].append(old)
            else:
                raise EditError("такой зоны без субтитров нет — обнови страницу")
            if kind == "captions.move_hide":
                caps["hide_add"].append(_span(op["a"], op["b"], duration, "зона без субтитров"))
    elif kind == "captions.fix":
        i = int(op.get("i", -1))
        if not 0 <= i < len(sc["words"]):
            raise EditError("такого слова нет")
        text = str(op.get("text", ""))
        if len(text) > 40 or "\n" in text:
            raise EditError("слово субтитра — одна строка до 40 знаков")
        caps["fixes"][str(i)] = text
    elif kind == "captions.unfix":
        caps["fixes"].pop(str(int(op.get("i", -1))), None)
    elif kind in ("item.shift", "item.mute"):
        iid = str(op.get("id") or "")
        html_path = ROOT / "studio" / stem / "index.html"
        parsed = parse_page(html_path.read_text(encoding="utf-8")) if html_path.exists() else {"items": [], "media": []}
        known = {it["id"] for it in parsed["items"]} | {m["id"] for m in parsed["media"] if m["tag"] == "audio" and m["id"]}
        if iid not in known:
            raise EditError(f"#{iid} на странице нет")
        cur = dict(edits["items"].get(iid, {}))
        if kind == "item.shift":
            shift = round(float(op.get("shift", 0)), 3)
            if abs(shift) > duration:
                raise EditError("сдвиг длиннее ролика")
            cur["shift"] = shift
        else:
            cur["mute"] = bool(op.get("mute"))
        cur = {k: v for k, v in cur.items() if v}
        if cur:
            edits["items"][iid] = cur
        else:
            edits["items"].pop(iid, None)
    elif kind == "item.style":
        iid = str(op.get("id") or "")
        html_path = ROOT / "studio" / stem / "index.html"
        parsed = parse_page(html_path.read_text(encoding="utf-8")) if html_path.exists() else {"items": []}
        if iid not in {it["id"] for it in parsed["items"]}:
            raise EditError(f"слоя #{iid} на странице нет")
        cur = merge_item_style(edits["items"].get(iid, {}), op.get("set") or {})
        if cur:
            edits["items"][iid] = cur
        else:
            edits["items"].pop(iid, None)
    elif kind == "captions.style":
        caps["style"] = merge_caption_style(caps.get("style") or {}, op.get("set") or {})
    elif kind == "text.add":
        n = max([int(str(t.get("id", "t0"))[1:] or 0) for t in edits["texts"]] + [0]) + 1
        t0 = _time(op.get("t0", 0), duration, "время текста")
        base = {**TEXT_DEFAULT, "id": f"t{n}", "t0": t0, "t1": round(min(duration, t0 + 2.5), 3),
                "x": round(sc["width"] / 2), "y": round(sc["height"] * 0.17), "text": "Твой текст"}
        if sc["width"] > sc["height"]:
            base["size"] = 96
        base = merge_text(base, {k: v for k, v in op.items() if k not in ("op", "id")}, duration,
                          sc["width"], sc["height"])
        edits["texts"].append(base)
    elif kind in ("text.set", "text.delete"):
        tid = op.get("id")
        found = [t for t in edits["texts"] if t.get("id") == tid]
        if not found:
            raise EditError("такого текста нет — обнови страницу")
        if kind == "text.delete":
            edits["texts"] = [t for t in edits["texts"] if t.get("id") != tid]
        else:
            new = merge_text(found[0], op.get("set") or {}, duration, sc["width"], sc["height"])
            edits["texts"] = [new if t.get("id") == tid else t for t in edits["texts"]]
    elif kind == "reset":
        edits = normalize({})
    else:
        raise EditError(f"правки «{kind}» студия не знает")

    # правка, после которой сцена не собирается (камера за кадром), не сохраняется
    save_edits(stem, edits)
    try:
        compose.scene(stem)
    except compose.SceneError as e:
        save_edits(stem, before)
        raise EditError(f"так нельзя: {e}")
    hist.append(before)
    _write_json(history_path(stem), hist[-HISTORY_DEPTH:])
    future_path(stem).unlink(missing_ok=True)       # новая правка — старое «повторить» больше не к месту
    return edits


def main():
    ap = argparse.ArgumentParser(description="Дорожки ролика и ручные правки студии")
    ap.add_argument("stem")
    ap.add_argument("--edits", action="store_true", help="показать только ручные правки")
    args = ap.parse_args()
    try:
        data = load_edits(args.stem) if args.edits else tracks(args.stem)
    except (EditError, ValueError) as e:
        sys.exit(f"✗ {e}")
    print(json.dumps(data, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
