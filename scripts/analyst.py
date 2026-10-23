#!/usr/bin/env python3
"""Аналитик: один короткий ход ИИ → партитура ролика (этап 3 автономного монтажа, 19.10.2026).

Мозг студии монтировал ролик одним ходом на 200–300 тыс. токенов: читал ~160 КБ правил и инструкций, писал page.py
с нуля и сам гонял проверки — 100–200 вызовов, каждый заново нёс весь контекст ($2–31 за ролик, «IMG_3292 — с нуля»
$9). Аналитик делает только то, где нужен ум, — решает, что показать на каких словах: получает транскрипт с номерами
слов, события дубля, принятые клипы и правила проекта целиком, а отвечает партитурой (scripts/score.py). Инструментов
у него нет, CLAUDE.md и память не подтягиваются (запуск вне папки проекта), системная подсказка — своя и короткая.
Страницу собирает score.py, проверяет verify_page; провалы уходят аналитику тем же разговором, не больше TRIES раз.

  .venv/bin/python scripts/analyst.py IMG_3292                  # партитура score.auto.json → studio/IMG_3292--auto
  .venv/bin/python scripts/analyst.py IMG_3292 --variant ""     # основная: score.json → studio/IMG_3292
  .venv/bin/python scripts/analyst.py IMG_3292 --dry            # только показать, что уйдёт аналитику

Цена каждого хода — в work/<имя>/analyst.jsonl (токены, $, секунды): так считается «до и после».
"""
import argparse
import contextlib
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import score as sc  # noqa: E402
import taste  # noqa: E402
from common import WORK_DIR  # noqa: E402

MODEL = "claude-opus-5-5"
EFFORT = "high"
FIX_EFFORT = "medium"   # исправление по списку провалов — правка JSON, не режиссура заново
TRIES = 3
AUTOFIX = 2             # проходов машинной правки (двойной текст → hide) до хода ИИ

# Конституция аналитика: как решать. Что проверяет машина (лицо, пустые места, ключевые слова, серые зоны, двойной
# текст, склейки), здесь только названо — нарушишь, получишь провал обратно. Правила проекта идут целиком в запросе.
SYSTEM = """Ты — режиссёр вертикальных роликов-уроков (Reels, Shorts, TikTok) уровня лучших вирусных авторов. Тебе дают
дубль: что и когда сказано (номера слов), где голова в кадре, события дубля, принятые ИИ-клипы, правила проекта и
недавние ролики проекта. Ты решаешь, ЧТО показать и НА КАКИХ СЛОВАХ, и отвечаешь ОДНИМ JSON — партитурой. Страницу,
звуки, музыку, склейки, вспышку после хука, смену плана ставит сборка сама. Ответ — только JSON, без пояснений вокруг.

ГЛАВНОЕ: КАЖДЫЙ РОЛИК — СВОЯ ИДЕЯ (правило владельца на всю систему)
Одинаковое не берём — каждый раз выдумываем. Прошлые удачные ролики — мерка качества, не шаблон: идея, мотив,
решение хука и основной набор приёмов у этого ролика свои. Общее у серии — только цвета и шрифты дизайн-системы.
Проверка сверяет партитуру с недавними роликами проекта (они в запросе) и вернёт провал, если повторишь.

КАК РЕШАТЬ — ПО ПОРЯДКУ
1. ИДЕЯ. Пойми мысль: обещание хука, поворот, факты, кульминация, вывод, призыв. Придумай визуальный МОТИВ именно
   этой истории — то, через что она рассказана на экране (про рукопожатия — цепочка лиц и связей; про письма —
   конверт, который идёт из рук в руки по карте; про деньги — купюры, которые множатся). Запиши в "concept".
2. ХУК — первые 1–2 секунды решают всё. Обещание хука покажи КАРТИНКОЙ сразу, на первых словах: не надпись того,
   что сказано, а то, что зритель захочет досмотреть (цепочка «ты → ? → ? → герой», невозможное число, предмет-загадка).
   В первые 3 с — не меньше трёх событий на экране. Сильнейший приём ролика — в хуке или в кульминации.
3. КАЖДЫЙ МОМЕНТ — САМЫМ СИЛЬНЫМ ПОДХОДЯЩИМ ПРИЁМОМ. Спроси себя: как это показать, чтобы зритель ахнул, а не
   прочёл? Число, которое растёт, — count, а не надпись; люди и связи, переписка, предмет из рук в руки — своя сцена;
   путь — route; миф — strike; список, ради которого досматривают, — promise; осознание — vertigo. Надпись (write) — когда показать нечего,
   и не больше трети вставок. Ровное «число на груди» там, где можно показать, — провал.
4. НАРАСТАНИЕ. Темп и масштаб растут к кульминации: в начале — быстро и цепко, в середине — меняй приёмы и раскладки,
   кульминация — самая большая сцена ролика (своя, "scene"), финал — чистый, под призыв.
5. СВОЯ СЦЕНА (kind "scene") — хотя бы одна на ролик: главный момент, который ты придумал сам под эту историю (см. ниже).
6. Динамика: вставка не реже раза в 6 с речи; графика не висит неподвижно дольше 5 с (оживи изнутри или смени);
   подряд одинаковые приёмы и раскладки не ставь.
7. Лицо — личный бренд: перебивки во весь кадр вместе не больше ~25% ролика. Остальное — поверх человека или за ним.
8. Текст на экране не повторяет речь, а добавляет: не «Хорезм» под «из Хорезма», а «низовья Амударьи». Повторяет —
   "hide": true (субтитры этих слов спрятаны), но не дольше 3 с подряд. Надписи — в одну строку, коротко.
9. Факты — только те, в которых уверен (число, дата, место из самой речи — можно). Ответ задачи, который автор сам
   не озвучил, на экран не выноси.
10. Ключевые слова субтитров ("accent") — одно на 5–8 с речи: главные существительные, имена, числа, повороты; хотя бы
   одно в первые 10 с. Пишутся как в транскрипте, без знаков. Ошибки распознавания в именах — "text_fixes" (номер →
   верное написание, знаки препинания как были); имена с большой буквы — "keep_case".
11. "cta" — слово финального призыва; с него до конца плашка, субтитры спрятаны — до конца речи от него не больше 3 с,
   и после него вставок нет.
12. Окна приёмов не пересекаются и не висят через склейку дубля; окно не короче 0,8 с; сплит, клип и «full» — со стыком
   не меньше 0,3 с. Автор диктует то, что на экране, — у приёма "hide": true.

ГДЕ МЕСТО НА ЭКРАНЕ (1080×1920)
Безопасное поле для текста — x 102–834, y 260–1370 (вне его — шапка, ник, кнопки площадок). Человек в центре; где
голова — дано в запросе. Субтитры — около y 1150–1260. Над головой тесно. ЗА человеком (слой behind, человек вырезан и
стоит поверх) графика может занимать весь фон — сеть, карта, линии, пути; текст за спиной — только сбоку от головы или
над ней. Поверх человека (front) — на груди под субтитрами (y 1262–1370) и по бокам; лицо не закрывать никогда.

АРСЕНАЛ (готовые приёмы — опора; главное — придумать, что ими сказать)
Время — номерами слов: "w": [от, до] — окно от начала слова «от» до конца слова «до».
- {"kind": "word", "w": [от, до], "at": номер, "text": "слово"} — одно крупное слово над головой ударом (1 раз за ролик).
- {"kind": "stamp", "w": [i, i], "text": "гениально"} — штамп на груди.
- {"kind": "count", "w": [от, до], "sub": "людей", "steps": [{"text": "100", "w": номер}, {"text": "10 000", "w": номер}, …]}
  — число растёт шагами на своих словах (2–6 шагов, до 11 знаков): каждый шаг выбивает прежний, на последнем — удар.
- {"kind": "wall", "w": [от, до], "notes": [{"text": "1929 — Каринти", "w": номер}, …]} — заметки прикалываются к стене
  за спиной по одной (до 5, до 28 знаков).
- {"kind": "paper", "w": [от, до], "text": "ЗНАКОМ"} — коллаж: бумага, человек вырезан, слово из вырезанных букв (во весь кадр).
- {"kind": "vertigo"|"frame"|"doodle"|"zoom", "w": [от, до]} — движения кадра: vertigo — комната отъезжает, человек на
  месте (момент осознания); frame — кадр сжимается в карточку, человек выходит за её край; doodle — рисованный контур
  и значки вокруг; zoom — пролёт сквозь камеру на начале окна (резкий переход к новой мысли).
- Дизайн-система проекта (если есть, описана ниже): hand, number, promise, strike.
- «Чертёж» — построения линиями (один из возможных мотивов, НЕ обязательный): write, route, timeline, compass, hexes,
  cuboid, plot, trilat; раскладки "chest" | "behind" | "split" (лист сверху, человек в окне снизу) | "full".
  {"kind": "write", "w": [от, до], "layout": "…", "text": "≤18 знаков", "sub": "факт ≤30"};
  {"kind": "route", "layout": "behind|split", "until": номер, "stops": [{"label": "Омаха", "x": 0.25, "y": 0.7, "w": номер}, …]};
  {"kind": "timeline", "layout": "split", "until": номер, "marks": [{"label": "1967", "sub": "Милгрэм", "w": номер}, …]};
  {"kind": "hexes"|"compass"|"cuboid"|"plot"|"trilat", …} — как в формате приёмов «Чертежа».
- {"kind": "clip", "w": [от, до], "name": "имя из списка принятых", "label": "…"} — клип (ИИ или сток) во весь кадр.
- {"kind": "stock", "w": [от, до], "q": ["graduation party", "prom dance"], "label": "…"} — живой клип со стока во весь
  кадр: 1–3 запроса по-английски, что именно в кадре (предмет, действие), от лучшего. Найдёт и проверит чёткость машина;
  не нашлось — вернётся провалом. Клипов (clip + stock) — не больше 2 на ролик, окно 1,5–4 с.
- {"kind": "photo", "w": [от, до], "files": ["имя из МАТЕРИАЛОВ"], "label": "…"} — фото, которое автор сам положил к
  ролику, во весь кадр (несколько — серией). Автор положил — значит, хочет его видеть: найди ему место по смыслу.
Любой приём, повторяющий речь, — с "hide": true (у word, stamp, clip, stock, photo, strike, wall, vertigo, frame, doodle, zoom
поля hide нет).

СВОЯ СЦЕНА — {"kind": "scene", "w": [от, до], "layer": "split"|"full"|"behind"|"front", "html": "…", "css": "…", "js": "…", "hide": bool}
Ты пишешь момент сам: HTML, стили и движение (GSAP-таймлайн tl). Так рождается то, чего не было в прошлых роликах.
МАСШТАБ — главное правило картинки: зритель смотрит с телефона. Главные сцены (хук, письмо, взрыв числа, кульминация) —
КРУПНО: "split" (человек в окне внизу, сцена — на всё поле над ним, размеры поля даны в запросе) или "full" (во весь
кадр, 1–2 раза). Фигуры — 200–700 px, текст — 56–160 px, линии — от 6 px. "front" — только мелочь на груди (подпись,
значок; у груди рука с микрофоном — не туда); "behind" — человек закрывает середину, видны только края и верх: годится
для фона-атмосферы, а не для главного. Мелкая цепочка или число на груди там, где мог быть сплит, — провал.
- html — один корень <div id="$id" class="g" style="left: …px; top: …px; width: …px; height: …px;">…</div>; все id внутри —
  "$id-что-то". Рисуй svg (линии, круги, пути, стрелки), div, текст. Без <img>, <script>, <style>, ссылок и url().
- css — только селекторы #$id и его потомков. Цвета — ТОЛЬКО переменные системы: var(--ds-text) (крем), var(--ds-plate)
  (чернила), var(--ds-acc) (лак), var(--ds-pen) (ручка), var(--ds-on-acc), var(--ds-grad) (лак-градиент, для фона и
  заливки); полупрозрачное — opacity или color-mix(in srgb, var(--ds-text) 40%, transparent). Шрифты — классами
  ds-f-caption, ds-f-headline, ds-f-number, ds-f-hand, ds-f-variable, ds-f-whisper; ds-lac — текст лаком; ds-halo —
  тень, чтобы текст читался на человеке. Другие цвета и шрифты проверка не пропустит.
- js — строки таймлайна; время — {w:N} (начало слова N) и {e:N} (конец слова N), можно {w:N}+0.2. Помощники:
  enter(sel, t, {fromY, fromX, fromScale, blur, dur}) — влёт; leave(sel, t, {y, dur}) — уход; slam(sel, t, {fromScale}) — удар;
  draw(sel, t, dur) — линия рисуется (у path: pathLength="1" stroke-dasharray="1" stroke-dashoffset="1");
  tl.fromTo / tl.to / tl.set — всё остальное. Корень сцены невидим, пока его не покажешь; всё входит И уходит движением,
  уход — до конца окна. Без своих часов и случайности (setTimeout, Math.random) — рендер шагает по кадрам.
- координаты — экранные (1080×1920): корень сцены ставь в её поле (split — над окном, full — весь кадр). Сцена — один
  момент, до 6000 знаков. Стык сплитов и full с другими — не меньше 0,3 с.

ФОРМАТ ОТВЕТА
{"concept": {"idea": "о чём ролик и как его показываем", "motif": "визуальный мотив этой истории",
             "hook": "чем бьёт первая секунда"},
 "title": "…", "hook": "auto", "cta": {"w": номер}, "accent": ["…"], "text_fixes": {"номер": "…"},
 "keep_case": ["…"], "hide": [[от, до]], "items": [ …по порядку времени… ]}
"hook": "auto" — место вспышки после хука выберет сборка; {"w": номер} — первое слово основы, если знаешь лучше.
Если дубль не годится в ролик (сорван, оборван, одни пробы, нет мысли) — ответь {"skip": "почему — одной фразой"}.
Если сборка или проверка найдут ошибки, тебе вернут их с подробностями — исправь именно их и ответь исправленной
партитурой целиком; то, что работало, не ломай."""


class Skipped(RuntimeError):
    """Аналитик решил, что дубль не годится в ролик (сорван, оборван) — нужен человек, а не партитура."""


def material(stem: str) -> str:
    """Что уходит аналитику: дубль словами с номерами, склейки, события, клипы, правила проекта."""
    import projects
    from kit import Take
    tk = Take(stem)
    project = projects.of(stem)
    lines, line = [], []
    for i, w in enumerate(tk.words):
        line.append(f"[{i}|{w['start']:.2f}] {w['word']}")
        if len(line) == 10 or re.search(r"[.!?…]$", w["word"]):
            lines.append(" ".join(line))
            line = []
    if line:
        lines.append(" ".join(line))
    splices = [f"{s:.2f} с (между словами {max(i for i, w in enumerate(tk.words) if w['start'] < s)} и "
               f"{min(i for i, w in enumerate(tk.words) if w['start'] >= s)})"
               for s in tk.splices if any(w["start"] >= s for w in tk.words)]
    clips = []
    takes = WORK_DIR / stem / "footage" / "takes.json"
    import footage as ft
    from common import QUALITY_FLOOR
    muddy = []
    for name, took in (json.loads(takes.read_text(encoding="utf-8")) if takes.exists() else {}).items():
        try:
            sharp = ft.take_sharpness(WORK_DIR / stem, took)[0]
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
            sharp = 0
        if sharp < QUALITY_FLOOR:                   # мыло аналитик не видит вовсе — verify_page всё равно не пустит
            muddy.append(f"{name} ({sharp}p)")
            continue
        note = WORK_DIR / stem / "footage" / f"{name}.md"
        about = re.search(r"Фраза:\s*(.+)", note.read_text(encoding="utf-8")) if note.exists() else None
        shot = re.search(r"Кадр:\s*(.+)", note.read_text(encoding="utf-8")) if note.exists() else None
        clips.append(f"- {name}{' (сток)' if took.get('source') == 'stock' else ''}: {took['duration']:.1f} с; "
                     f"под фразу «{about.group(1) if about else '?'}»; "
                     f"в кадре: {shot.group(1)[:160] if shot else '?'}")
    head = head_room(stem)
    wish = order(stem, project)
    events = WORK_DIR / stem / "events.json"
    ev = json.loads(events.read_text(encoding="utf-8")) if events.exists() else {}
    cfg = project.config
    rules = project.all_rules_text() or "(правил проекта нет)"         # проекта, затем раздела
    import design
    system = design.of(project)           # DESIGN.md проекта: приёмы системы и её правила — аналитику и критику
    ds_brief = ["", system.brief()] if system else []
    return "\n".join([
        f"РОЛИК {stem}: {tk.duration:.1f} с, формат {tk.fmt}. Проект «{project.name}».",
        f"Требования проекта: лицо в кадре ≥ {float(cfg.get('face_min', 0.6)) * 100:.0f}% (цель 70%+); без вставок не дольше "
        f"{cfg.get('insert_gap_max', 6)} с; призыв в конце: {'да' if cfg.get('cta', True) else 'нет'}.",
        "",
        "ДУБЛЬ — [номер|начало, с] слово:",
        *lines,
        "",
        head,
        "Склейки дубля (вырезанные куски): " + ("; ".join(splices) if splices else "нет"),
        "Угар (кусок со сбоем, сборка покажет его серым): " + (", ".join(f"{a:.2f}–{b:.2f} с" for a, b in tk.bloopers) or "нет"),
        "Кандидаты конца хука (сборка ставит вспышку на лучший): " + (", ".join(
            f"«{h['word']}» {h['t']:.2f} с" for h in (ev.get("hook") or [])[:3]) or "нет"),
        "",
        *wish,
        "ПРИНЯТЫЕ КЛИПЫ — ИИ или сток (kind clip — только эти имена, клип не длиннее своей длины):",
        *(clips or ["- нет: kind clip не используй"]),
        *([f"(не годятся — мутнее {QUALITY_FLOOR}p во весь кадр, не предлагай: {', '.join(muddy)})"] if muddy else []),
        "",
        f"ПРАВИЛА ПРОЕКТА ({', '.join(projects.rel(r) for r in project.rule_files())} — главнее общих; раздел уточняет "
        "проект; что про сборку и инфраструктуру — не твоё):",
        rules,
        *ds_brief,
        "",
        *recent_lines(stem),
        *taste.lines(project),
        "",
        "Ответь партитурой (JSON).",
    ])


# что из референса может взять режиссёр партитуры; цвет, шрифты и звук — дело сборки и DESIGN.md проекта
REF_ASPECTS = {
    "темп": lambda r: (f"склеек {r.get('cuts_per_min', 0):g}/мин, средний план {r.get('avg_shot', 0):g} с, "
                       f"речь {r.get('wpm') or '?'} слов/мин"),
    "текст": lambda r: (f"текст в кадре {round((r.get('text') or {}).get('share', 0) * 100)}% времени, "
                        f"субтитры: {(r.get('traits') or {}).get('captions', '?')}, "
                        f"где: {(r.get('traits') or {}).get('position', '?')}"),
    "структура": lambda r: f"длина {r.get('duration', 0):g} с, самый долгий план {r.get('longest_shot', 0):g} с",
}
REF_BUILD = {"шрифты", "цвет", "звук", "музыка", "переходы", "субтитры"}


def order(stem: str, project) -> list:
    """Заказ автора к ролику (23.10.2026, Валера: «результат — тем, чем задумывал его автор»): бриф (заметки, цели,
    смелость), материалы, которые он сам положил, и референсы с тем, ЧТО из них брать. Раньше аналитик не видел ни
    брифа, ни материалов, ни референсов — угадывал замысел по одному транскрипту."""
    import styles
    from common import QUALITY_FLOOR, sharpness
    lines = []
    try:
        brief = styles.load_brief(stem)
    except styles.StyleError as e:
        brief = {}
        lines.append(f"(бриф не прочитан: {e})")
    if brief.get("exists") or brief.get("notes"):
        goals = ", ".join(f"{k} {v}" for k, v in sorted((brief.get("goals") or {}).items(), key=lambda kv: -kv[1]))
        lines += ["ЗАКАЗ АВТОРА К РОЛИКУ (главнее твоих догадок):",
                  f"- что просит: {brief.get('notes').strip()}" if (brief.get("notes") or "").strip() else "- просьб словами нет",
                  f"- цели (0–5): {goals}" if goals else "",
                  f"- смелость монтажа {brief.get('boldness', 0.3):g} из 1 (0 — спокойно, 1 — на грани)"]
    folder = WORK_DIR / stem / "materials"
    photos, other = [], []
    for f in sorted(folder.glob("*")) if folder.is_dir() else []:
        if f.name.startswith(".") or f.name == "materials.json" or f.name.startswith("mx-") or f.name.startswith("yt-"):
            continue                                   # фонотеку (mx-, yt-) ставит сборка, это не материал автора
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            try:
                from PIL import Image
                with Image.open(f) as im:
                    w, h = im.size
            except OSError:
                continue
            p = sharpness(w, h, 1080, 1920)
            photos.append(f"- {f.name}: {w}×{h}, во весь кадр {p}p" + (f" — мутнее {QUALITY_FLOOR}p, не ставь" if p < QUALITY_FLOOR else ""))
        elif f.suffix.lower() in (".mp4", ".mov", ".m4v", ".webm", ".mp3", ".wav", ".m4a"):
            other.append(f.name)
    if photos or other:
        lines += ["МАТЕРИАЛЫ АВТОРА (сам положил к ролику — kind photo, только эти имена):", *photos]
        if other:
            lines.append(f"- видео и звук ({', '.join(other)}) партитура пока не ставит — скажи об этом в title, не молчи")
    refs = list(brief.get("refs") or [])
    take_file = project.references / "take.json" if getattr(project, "references", None) else None
    if take_file and take_file.exists():
        try:
            refs += json.loads(take_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            lines.append(f"(references/take.json битый: {e})")
    for ref in refs:
        name, take = str(ref.get("ref") or ref.get("url") or "?"), [str(t).lower() for t in ref.get("take") or []]
        measured = WORK_DIR / "_refs" / f"{name}.json"
        data = json.loads(measured.read_text(encoding="utf-8")) if measured.exists() else {}
        mine = [f"{t}: {REF_ASPECTS[t](data)}" if data and t in REF_ASPECTS else t for t in take if t not in REF_BUILD]
        lines += [f"РЕФЕРЕНС {name} — брать ТОЛЬКО: {', '.join(take) or 'настроение'}"
                  + (f" ({ref['note']})" if ref.get("note") else ""),
                  *(f"- {x}" for x in mine)]
        if not data and any(t in REF_ASPECTS for t in take):
            lines.append(f"- (не измерен: analyze_reference.py — цифр нет, бери по описанию)")
    return [x for x in lines if x] + ([""] if lines else [])


def recent_lines(stem: str) -> list:
    """Недавние ролики проекта — что в них уже было: идею, мотив, хук и основной набор приёмов не повторять."""
    found = sc.recent_scores(stem)
    if not found:
        return ["НЕДАВНИЕ РОЛИКИ ПРОЕКТА: партитур нет — всё равно придумай своё, а не «как обычно»."]
    out = ["НЕДАВНИЕ РОЛИКИ ПРОЕКТА — это уже было, НЕ повторяй ни идею, ни мотив, ни хук, ни набор приёмов:"]
    for name, old in found:
        items = [it for it in old.get("items") or [] if isinstance(it, dict)]
        concept = old.get("concept") or {}
        out.append(f"- {name}: открыт «{sc._opening(items) or '—'}»; приёмы {dict(sorted(sc._profile(items).items()))}"
                   + (f"; мотив «{concept.get('motif')}»; хук «{concept.get('hook')}»" if concept else ""))
    return out


def head_room(stem: str) -> str:
    """Где голова на экране и сколько места над ней и по бокам — по слежению с камерой (как verify_page: лицо плюс
    0,2 его высоты на волосы, по 0,15 ширины с боков). Без этого аналитик ставил «за спиной» вслепую, и в IMG_3303
    (голова выше) слово хука и подписи сот ушли за голову (19.10.2026)."""
    import verify_page
    from common import ROOT
    track = verify_page.face_track(ROOT / "studio" / stem)
    import matte
    ok, why = matte.need(stem)
    if not ok:                                  # маски не будет: за спиной не ставить ничего (22.10.2026, IMG_0930)
        return (f"ЗА СПИНОЙ — НЕЛЬЗЯ: маски человека у ролика не будет ({why}). Раскладка behind запрещена, слова, "
                f"пометки и числа сборка поставит на грудь сама; схемы — chest или split.")
    if not track:
        return "ГОЛОВА В КАДРЕ: слежения нет — «за спиной» ставь только маршрут над головой (y ≤ 0.15)."
    q = lambda i, k: sorted(f[i] for f in track)[min(len(track) - 1, int(k * len(track)))]     # noqa: E731
    x0, y0, x1, y1 = q(1, 0.5), q(2, 0.5), q(3, 0.5), q(4, 0.9)      # подбородок — по наклонам вниз, как Montage._face
    top, high = y0 - 0.2 * (y1 - y0), q(2, 0.1) - 0.2 * (y1 - y0)
    hx0, hx1 = x0 - 0.15 * (x1 - x0), x1 + 0.15 * (x1 - x0)
    box_y, box_h = 280, 460                                         # поле «за спиной» (blueprint.BOXES["behind"])
    free = max(0.0, top - box_y)
    import blueprint as bp
    hole = bp.split_geometry((x0, y0, x1, y1))["hole"]
    split = (f" СПЛИТ (layout \"split\"): человек уходит в окно x {hole[0]}–{hole[2]}, y {hole[1]}–{hole[3]}; поле сцены над ним — "
             f"x 110–970, y 270–{hole[1] - 20} ({860}×{hole[1] - 290} px) — место для главных сцен. ВО ВЕСЬ КАДР (\"full\"): "
             f"x 110–970, y 270–1360, человека нет.")
    return (f"ГОЛОВА В КАДРЕ (экран 1080×1920, по слежению): голова x {hx0:.0f}–{hx1:.0f}, верх головы обычно y {top:.0f}, "
            f"в самом высоком месте y {high:.0f}. Поле «за спиной» — y 280–740: над головой свободно {free:.0f} px "
            f"(y доли поля 0–{free / box_h:.2f}, точки маршрута — на нижней границе, подписи встанут над ними); сбоку от головы — x 118–{hx0:.0f} и {hx1:.0f}–962. Подписи и линии "
            f"«за спиной» — только в этих местах (за голову уходит не больше трети подписи); свободно над головой меньше 60 px — "
            f"маршрут и подписи над головой не ставь, бери split или chest." + split)


def home() -> Path:
    """Папка запуска аналитика и критика — вне проекта (иначе Claude Code сам подтянет CLAUDE.md, ~20 КБ, и память
    проекта) и постоянная: сессии Claude Code живут по папке запуска, продолжение разговора ищется в той же."""
    path = Path(tempfile.gettempdir()) / "reels-analyst"
    path.mkdir(exist_ok=True)
    return path


def ask(prompt: str, session: str | None = None, system: str = SYSTEM, tools: str = "", effort: str = EFFORT) -> dict:
    """Один ход: Claude без CLAUDE.md, со своей системной подсказкой и только с tools. → текст, сессия, цена."""
    import brain
    binary = brain.find_binary("claude")
    if not binary:
        raise RuntimeError("claude не найден на этой машине — аналитику нужен Claude Code")
    cmd = [binary, "-p", prompt, "--output-format", "json", "--model", MODEL, "--effort", effort, "--tools", tools,
           "--system-prompt", system]
    if tools:
        cmd += ["--allowedTools", tools]
    if session:
        cmd += ["--resume", session]
    started = time.time()
    proc = subprocess.run(cmd, cwd=home(), capture_output=True, text=True, env=brain.child_env(), timeout=1800)
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"ИИ не ответил JSON (код {proc.returncode}): {(proc.stderr or proc.stdout)[-600:]}")
    if out.get("is_error"):
        raise RuntimeError(f"ИИ упал: {brain.explain_error(str(out.get('result') or out))}")
    usage = out.get("usage") or {}
    return {"text": out.get("result") or "", "session": out.get("session_id"), "cost": out.get("total_cost_usd"),
            "seconds": round(time.time() - started, 1),
            "tokens": {k: usage.get(k) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
                                                 "output_tokens")}}


def parse(text: str) -> dict:
    """JSON партитуры из ответа: целиком или из блока ```json."""
    found = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    raw = found.group(1) if found else text[text.find("{"):text.rfind("}") + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise sc.ScoreError(f"ответ — не JSON партитуры: {e}") from None


@contextlib.contextmanager
def page_slot():
    """Сборка, проверка и снимки страницы — по одной на машине: в них Chromium, а пачка гонит несколько автопилотов
    разом (студия, до 4). ИИ думают параллельно, страницы проверяются по очереди (инвариант 2)."""
    import host
    path = WORK_DIR / "_studio" / "page.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+", encoding="utf-8")
    try:
        while not host.try_lock(handle):
            time.sleep(1)
        yield
    finally:
        handle.close()                                  # замок снимается вместе с файлом


class BuildBroken(RuntimeError):
    """Провал сборки, а не партитуры (переход на склейке, звук, ошибка JS): аналитик его не исправит — ходы ИИ впустую.
    23.10.2026: подпись оси уезжала за кадр из-за CSS, и аналитик IMG_3683/IMG_3684 переписал партитуру 6 раз."""


# проверки про решения партитуры, у которых в подробностях нет приёма (#s<k>-…): их правит аналитик
SCORE_CHECKS = ("субтитры не пропадают", "ключевое слово в субтитрах", "нет пустых мест без вставок",
                "человек в кадре не меньше", "ИИ-видео не больше")
PIECE = re.compile(r"#s(\d+)-([a-z]+)[\w-]*")


def assemble(stem: str, variant: str | None, score: dict, info: dict | None = None) -> list:
    """Партитура → страница → проверка. Возвращает провалы (пусто — можно рендерить); info — подробности (verify out)."""
    import compose
    import verify_page
    name = compose.project_name(stem, variant)
    project = compose.STUDIO / name
    with page_slot():
        if not (project / "camera.js").exists():
            compose.compose(stem, variant=variant)      # первая сборка: камера и ассеты — сплиту нужна камера
        sc.build(stem, variant, score)
        compose.compose(stem, variant=variant)          # субтитры с решениями партитуры
        # маска считается после страницы и только по её окнам (autopilot.cut_on_windows): здесь её ещё может не быть
        failed = verify_page.verify(name, matte_pending=True, out=info)
    novel = sc.novelty(stem, score, variant)            # своя идея: повтор прошлых роликов проекта — провал аналитику
    if info is not None:
        info["novelty"] = novel
    return failed + novel


def stock_name(query: str, k: int) -> str:
    """Имя файла стока по запросу: латиница, цифры и «_» (stock.take), номер приёма — чтобы два одинаковых не слиплись."""
    return f"st{k}_" + (re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:24] or "clip")


def resolve_stock(stem: str, score: dict, wait: float = 1200, words: list | None = None) -> list:
    """Приёмы stock → clip: найти годный сток очередью (stock.py auto: чёткость ≥ 720p во весь кадр, длина ≥ окна).
    Уже найденный (тот же файл в takes.json, не короче окна) не ищется заново. Не нашлось — приём убирается из
    партитуры на эту сборку, а аналитик получает провал с причиной. Возвращает провалы.
    Раньше автопилот брал только принятые клипы, и сток подбирала руками длинная сессия (23.10.2026: $36 за вечер)."""
    import jobqueue
    from kit import Take
    items = score.get("items") or []
    todo = [(k, it) for k, it in enumerate(items) if isinstance(it, dict) and it.get("kind") == "stock"]
    if not todo:
        return []
    words = words if words is not None else Take(stem).words
    takes_file = WORK_DIR / stem / "footage" / "takes.json"
    took = lambda: json.loads(takes_file.read_text(encoding="utf-8")) if takes_file.exists() else {}   # noqa: E731
    steps, plan = [], []
    for k, it in todo:
        a, b = it["w"]
        dur = round(max(sc.MIN_SHOW, words[b]["end"] - words[a]["start"]), 2)
        name = stock_name(it["q"][0], k)
        say = " ".join(w["word"] for w in words[a:b + 1])[:120]
        plan.append((k, it, name, dur))
        if (took().get(name) or {}).get("duration", 0) + 1e-3 < dur:
            steps.append(["python", "scripts/stock.py", "auto", stem, name, "--dur", f"{dur:g}", "--say", say,
                          "--q", *it["q"]])
    if steps:
        job = f"40-stock-{stem}-{int(time.time()) % 100000}"
        jobqueue.write_job(job, steps, title=f"сток для {stem}")
        jobqueue.wake()
        print(f"  → очередь: {job} (стоков: {len(steps)})", flush=True)
        jobqueue.wait(job, wait)
    failed, have = [], took()
    for k, it, name, dur in plan:
        if (have.get(name) or {}).get("duration", 0) + 1e-3 >= dur:
            items[k] = {"kind": "clip", "w": it["w"], "name": name, **({"label": it["label"]} if it.get("label") else {})}
        else:
            none = WORK_DIR / stem / "broll" / f"{name}.none"
            why = none.read_text(encoding="utf-8").strip() if none.exists() else "поиск стока не отработал"
            failed.append(f"items[{k}] (stock) по запросам {it['q']}: {why[:300]} — другой запрос или другой приём")
            items[k] = None
    score["items"] = [it for it in items if it is not None]
    return failed


def triage(failed: list, info: dict) -> list:
    """Провалы — словами партитуры: «items[9] (timeline) «долг = 0» вылезает…». Чего аналитик не исправит — BuildBroken."""
    mine, broken = [], []
    for title in [t for t in failed if t not in (info.get("novelty") or [])]:
        details = (info.get("details") or {}).get(title) or []
        if title.startswith("партитура с ошибками") or title.startswith("ответ — не JSON"):
            mine.append(title)
            continue
        ours = [d for d in details if PIECE.search(d)]
        rest = [d for d in details if not PIECE.search(d)]
        if title.startswith(SCORE_CHECKS):
            ours, rest = details, []
        if rest or not ours:
            broken.append(title + "".join(f"\n    {d}" for d in (rest or details)[:4]))
        if ours:
            lines = [PIECE.sub(lambda m: f"items[{m.group(1)}] ({m.group(2)})", d).replace("hide_captions", '"hide"')
                     for d in ours[:6]]
            mine.append(title + ":" + "".join(f"\n    {d}" for d in lines))
    mine += list(info.get("novelty") or [])
    if broken:
        raise BuildBroken("сборка, а не партитура — ходы аналитика её не исправят, нужен разработчик:\n  "
                          + "\n  ".join(broken))
    return mine


def autofix(words: list, score: dict, info: dict) -> bool:
    """Машинная правка без ИИ: субтитр, который повторяет надпись на экране, прячется ("hide" на эти слова). True —
    партитура поменялась. Это механика (какое слово под какой надписью), ход Opus на неё — $0,15 и ноль толку."""
    norm = lambda t: re.sub(r"[^\wё]+", " ", t.lower()).split()       # noqa: E731
    hide = [list(h) for h in score.get("hide") or []]
    added = 0
    for d in (info.get("res") or {}).get("dupes") or []:
        cap = set(norm(d.get("cap", "")))
        for i, w in enumerate(words):
            # субтитр виден и после конца слова: слово 331 с 43,88 с, а надпись встала на 44,0 (IMG_3683) — по перекрытию
            if w["start"] <= d["last"] + 0.25 and w["end"] >= d["from"] - 0.4 and set(norm(w["word"])) & cap \
                    and not any(a <= i <= b for a, b in hide):
                hide.append([i, i])
                added += 1
    if added:
        score["hide"] = sorted(hide)
    return bool(added)


def run(stem: str, variant: str | None = "auto", tries: int = TRIES, resume: bool = False) -> Path:
    """resume — довести готовую партитуру: аналитик получает её и её провалы и правит, не меняя идеи (21.10.2026: новый
    прогон с нуля выбрасывал удачную идею, которой не хватило ходов на мелкие провалы)."""
    log = WORK_DIR / stem / "analyst.jsonl"
    prompt, session, total = material(stem), None, 0.0
    if resume and sc.path_of(stem, variant).exists():
        current = sc.load(stem, variant)
        info = {}
        try:
            failed = triage(assemble(stem, variant, current, info), info)
        except (sc.ScoreError, ValueError, BuildBroken) as e:
            failed = [str(e)]
        if not failed:
            print(f"✓ {sc.path_of(stem, variant).relative_to(WORK_DIR.parent)} уже проходит проверку")
            return sc.path_of(stem, variant)
        prompt += ("\n\nТЕКУЩАЯ ПАРТИТУРА — доведи её: идею, мотив и удачные сцены сохрани, исправь только провалы ниже, "
                   "ответь партитурой целиком:\n" + json.dumps(current, ensure_ascii=False) + "\n\nПРОВАЛЫ:\n- "
                   + "\n- ".join(str(x) for x in failed))
    for attempt in range(1, tries + 1):
        reply = ask(prompt, session, effort=EFFORT if attempt == 1 else FIX_EFFORT)
        session = reply["session"]
        spent, total = (reply["cost"] or 0) - total, reply["cost"] or 0     # total_cost_usd — итог разговора, не хода
        entry = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "stem": stem, "variant": variant, "attempt": attempt,
                 "cost": round(spent, 4), "cost_total": round(total, 4), "seconds": reply["seconds"], "tokens": reply["tokens"]}
        try:
            score = parse(reply["text"])
            if score.get("skip"):                       # дубль не годится — не вымучивать ролик из брака
                entry["skip"] = str(score["skip"])
                _log(log, entry)
                raise Skipped(f"аналитик: дубль не годится — {score['skip']}")
            from kit import Take
            fixed = sc.fix_mechanics(score, Take(stem, variant).words)    # механика — машиной, до сборки
            if fixed:
                entry["fixed"] = fixed
            path = sc.path_of(stem, variant)
            path.write_text(json.dumps(score, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            stock_failed = resolve_stock(stem, score)       # сток — до сборки: страница ставит его как clip
            info = {}
            failed = assemble(stem, variant, score, info)
            for _ in range(AUTOFIX):                    # механику правит машина, ИИ — только решения
                if not failed or not autofix(Take(stem, variant).words, score, info):
                    break
                entry["autofix"] = entry.get("autofix", 0) + 1
                info = {}
                failed = assemble(stem, variant, score, info)
            path.write_text(json.dumps(score, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            failed = triage(failed, info) + stock_failed
        except (sc.ScoreError, ValueError) as e:
            failed = [str(e)]
        except BuildBroken as e:
            entry["failed"], entry["build"] = [str(e)], True
            _log(log, entry)
            raise
        entry["failed"] = failed
        _log(log, entry)
        print(f"  ход {attempt}: ${spent:.2f}, {reply['seconds']:.0f} с, "
              f"{'чисто' if not failed else f'провалов {len(failed)}'}", flush=True)
        if not failed:
            print(f"✓ {sc.path_of(stem, variant).relative_to(WORK_DIR.parent)} → страница готова к рендеру")
            return sc.path_of(stem, variant)
        prompt = ("Сборка и проверка нашли ошибки — исправь партитуру и ответь ею целиком (только JSON). items[k] — "
                  "k-й приём твоего списка items, с нуля:\n- " + "\n- ".join(str(x) for x in failed))
    raise RuntimeError(f"за {tries} хода партитура не прошла проверку — последние провалы в "
                       f"{log.relative_to(WORK_DIR.parent)}")


CRITIC = """Ты — критик монтажа вертикального ролика-урока. Тебе дают партитуру (JSON решений режиссёра: что на каких
словах показать) и лист кадров черновика — файл sheet.png (прочитай его инструментом Read): под каждым кадром время
и что идёт. Машинные проверки (серые зоны, лицо, субтитры, пустые места) уже пройдены — их не ищи.

Планка — лучшие вирусные авторы, а не «нормально». Владелец (21.10.2026): «визуал скучный… можно усиливать и усиливать,
делай сразу всё усиленно и идеально в конкретном моменте»; «одинаковое не берём — каждый раз выдумываем».
Смотри глазами зрителя телефона, который листает ленту и решает за секунду:
- хук: ударяет ли первая секунда КАРТИНКОЙ, захочется ли досмотреть? Нет — усиль первым делом;
- скучно: момент, который можно показать, а показан надписью; ровное «число на груди»; кадр, где ничего не
  происходит; приём, который ничего не добавляет к сказанному — замени сильным (своя сцена, count, движение кадра);
- нарастание: есть ли кульминация, бьёт ли она сильнее начала;
- МЕЛКО — главная беда: главный образ ролика ниточкой на груди, число поверх микрофона, сцена за спиной, которую
  закрыл человек. Главное — крупно: сцена в сплит (человек в окне внизу, сцена над ним) или во весь кадр;
- что не читается (мелко, на пёстром, на руке или банке, тёмное на тёмном);
- что не к месту: вставка не про то, что говорится в этот момент, или факт в подписи сомнительный;
- где однообразно: подряд похожие кадры, одна раскладка;
- где вставка закрывает главное — лицо, жест, предмет, о котором речь.
Свои сцены ("scene") правь смело — они для того и есть. Идею ролика ("concept") держи — усиливай её, а не подменяй
шаблоном прошлых роликов.

Если править нечего — ответь {"ok": true, "notes": ["что хорошо — коротко"]}. Если есть что — ответь исправленной
партитурой ЦЕЛИКОМ (тот же формат, все поля) и полем "notes": ["что поменял и почему"]. Меняй только то, что видно
плохо, удачное не трогай. Ответ — только JSON."""


def sheet(stem: str, variant: str | None, score: dict) -> Path:
    """Лист кадров черновой страницы для критика: середина каждого приёма и кадры между ними, под каждым — время и
    что идёт. Снимки — с самой страницы (hyperframes snapshot), рендер не нужен."""
    import compose
    from PIL import Image, ImageDraw, ImageFont
    from kit import Take
    project = compose.STUDIO / compose.project_name(stem, variant)
    words = Take(stem, variant).words
    marks = []
    for item in score.get("items") or []:
        steps = item.get("stops") or item.get("marks") or []
        a = words[item["w"][0]]["start"] if "w" in item else words[steps[0]["w"]]["start"]
        b = words[item["w"][1]]["end"] if "w" in item else words[item["until"]]["end"]
        marks.append((round((a + 2 * b) / 3, 2), f"{item['kind']} {item.get('layout', '')}".strip()))
    duration = words[-1]["end"]
    for t in [x * 6.0 + 3.0 for x in range(int(duration // 6))]:
        if all(abs(t - m) > 2.5 for m, _ in marks):
            marks.append((round(t, 2), "без вставки"))
    marks = sorted(marks)[:16]
    shots = project / "snapshots"
    if shots.exists():
        for f in shots.glob("*.png"):
            f.unlink()
    subprocess.run([host_tool("npx"), "--yes", compose.HYPERFRAMES, "snapshot", "--no-end", "--describe", "false",
                    "--at", ",".join(f"{t:g}" for t, _ in marks)], cwd=project, capture_output=True, timeout=600)
    files = sorted(shots.glob("frame-*.png"))
    if len(files) != len(marks):
        raise RuntimeError(f"снимков {len(files)} из {len(marks)} — hyperframes snapshot не отработал в {project.name}")
    cell_w, cell_h, cols = 270, 480, 4
    rows = (len(files) + cols - 1) // cols
    out = Image.new("RGB", (cols * cell_w, rows * (cell_h + 34)), "white")
    font = ImageFont.truetype(str(sc.bp.FONT_DIR / "Manrope-ExtraBold.ttf"), 18)
    draw = ImageDraw.Draw(out)
    for k, (f, (t, what)) in enumerate(zip(files, marks)):
        x, y = (k % cols) * cell_w, (k // cols) * (cell_h + 34)
        out.paste(Image.open(f).convert("RGB").resize((cell_w, cell_h)), (x, y))
        draw.text((x + 6, y + cell_h + 6), f"{t:.1f} с · {what}", fill="black", font=font)
    path = WORK_DIR / stem / f"critic{'.' + variant if variant else ''}.png"
    out.save(path)
    return path


def host_tool(name: str) -> str:
    import host
    return host.tool(name)


def critique(stem: str, variant: str | None = "auto", tries: int = 2) -> bool:
    """Критик: лист кадров + партитура → правки. True — партитуру поправили и она прошла проверку."""
    import shutil
    log = WORK_DIR / stem / "analyst.jsonl"
    score = sc.load(stem, variant)
    with page_slot():
        picture = sheet(stem, variant, score)
    shutil.copy2(picture, home() / "sheet.png")
    prompt = ("Партитура ролика:\n" + json.dumps(score, ensure_ascii=False, indent=1) + "\n\n" + material(stem)
              + "\n\nЛист кадров черновика — sheet.png. Ответь JSON.")
    session, total = None, 0.0
    for attempt in range(1, tries + 1):
        reply = ask(prompt, session, system=CRITIC, tools="Read", effort=EFFORT if attempt == 1 else FIX_EFFORT)
        session = reply["session"]
        spent, total = (reply["cost"] or 0) - total, reply["cost"] or 0     # total_cost_usd — итог разговора
        entry = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "stem": stem, "variant": variant, "role": "critic",
                 "attempt": attempt, "cost": round(spent, 4), "cost_total": round(total, 4), "seconds": reply["seconds"],
                 "tokens": reply["tokens"]}
        try:
            answer = parse(reply["text"])
        except sc.ScoreError as e:
            answer, entry["failed"] = {}, [str(e)]
        entry["notes"] = answer.get("notes") or []
        if answer.get("ok"):
            entry["failed"] = []
            _log(log, entry)
            print(f"  критик: править нечего (${spent:.2f}) — {'; '.join(entry['notes'])[:300]}")
            return False
        if "items" in answer:
            fixed = {k: v for k, v in answer.items() if k != "notes"}
            backup = dict(score)
            info = {}
            try:
                stock_failed = resolve_stock(stem, fixed)
                failed = triage(assemble(stem, variant, fixed, info), info) + stock_failed
            except (sc.ScoreError, ValueError) as e:
                failed = [str(e)]
            except BuildBroken as e:                    # правка критика ломает сборку — оставить партитуру аналитика
                entry["failed"], entry["build"] = [str(e)], True
                _log(log, entry)
                assemble(stem, variant, backup)
                print(f"  критик: {e}")
                return False
            entry["failed"] = failed
            _log(log, entry)
            if not failed:
                sc.path_of(stem, variant).write_text(json.dumps(fixed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                print(f"  критик поправил (${spent:.2f}): {'; '.join(entry['notes'])[:400]}")
                return True
            assemble(stem, variant, backup)                     # страница — снова по годной партитуре
            prompt = ("Твоя партитура не прошла сборку и проверку — исправь и ответь ею целиком (только JSON):\n- "
                      + "\n- ".join(str(x) for x in failed))
            continue
        _log(log, entry)
    print("  критик: правки не прошли проверку — оставлена партитура аналитика")
    return False


def _log(path: Path, entry: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Аналитик: партитура ролика одним коротким ходом ИИ")
    ap.add_argument("stem")
    ap.add_argument("--variant", default="auto", help="score.<вариант>.json (\"\" — основная партитура)")
    ap.add_argument("--dry", action="store_true", help="только показать, что уйдёт аналитику, и размер")
    ap.add_argument("--tries", type=int, default=TRIES, help=f"ходов аналитика до отказа (по умолчанию {TRIES})")
    ap.add_argument("--resume", action="store_true", help="довести готовую партитуру по её провалам, не меняя идеи")
    ap.add_argument("--critic", action="store_true", help="после аналитика — критик по листу кадров черновика")
    ap.add_argument("--critic-only", action="store_true", help="только критик по готовой партитуре")
    args = ap.parse_args()
    if args.dry:
        text = material(args.stem)
        print(text)
        print(f"\n— запрос {len(text)} знаков + системная подсказка {len(SYSTEM)} знаков")
        return
    try:
        if not args.critic_only:
            run(args.stem, args.variant or None, tries=args.tries, resume=args.resume)
        if args.critic or args.critic_only:
            critique(args.stem, args.variant or None)
    except RuntimeError as e:                   # Skipped — тоже: дубль не годится, нужен человек
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
