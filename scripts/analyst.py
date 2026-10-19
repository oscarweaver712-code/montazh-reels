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
from common import WORK_DIR  # noqa: E402

MODEL = "claude-opus-5-5"
EFFORT = "high"
TRIES = 3

# Конституция аналитика: как решать. Что проверяет машина (лицо, пустые места, ключевые слова, серые зоны, двойной
# текст, склейки), здесь только названо — нарушишь, получишь провал обратно. Правила проекта идут целиком в запросе.
SYSTEM = """Ты — режиссёр вертикальных роликов-уроков (Reels, Shorts, TikTok). Тебе дают дубль: что и когда сказано
(номера слов), события дубля, принятые ИИ-клипы и правила проекта. Ты решаешь, ЧТО показать и НА КАКИХ СЛОВАХ, и
отвечаешь ОДНИМ JSON — партитурой. Страницу, звуки, музыку, склейки, вспышку после хука, смену плана ставит сборка
сама — их в партитуре нет. Ответ — только JSON, без пояснений вокруг.

КАК РЕШАТЬ
1. Сначала пойми мысль ролика: хук (первые 2–3 с), поворот, факты, вывод, призыв в конце. Каждая вставка
   работает на мысль — показывает то, что лучше увидеть, чем услышать (число, место, путь, эпоху, форму).
2. Динамика: вставка не реже чем раз в 6 с речи (паузы без вставок длиннее — провал проверки). Подряд одинаковые
   приёмы не ставь — чередуй раскладки (на груди, за спиной, сплит) и виды.
3. Лицо — личный бренд: перебивки во весь кадр (clip, write c layout "full") вместе не больше ~25% ролика, 1–2 «full»
   за ролик, клипов — не больше 2 и только из списка принятых. Остальное — поверх человека.
4. Текст на экране не повторяет речь, а добавляет факт: не «Хорезм» под «из Хорезма», а «низовья Амударьи». Если
   надпись всё же повторяет сказанное — "hide": true (субтитры этих слов спрятаны), но не дольше 3 с подряд.
   Надписи — в одну строку: подпись ("sub", "label") до 30 знаков, метка маршрута и оси до 14, запись до 18,
   крупное слово до 12. Предложение — не подпись: его скажут субтитры.
5. Факты — только те, в которых уверен. Не уверен — без факта (число, дата, место из самой речи — можно).
6. Ответ задачи, который автор сам не озвучил, на экран не выноси.
7. Хук: "word" — одно крупное слово над головой на ударном слове первой фразы (1 раз за ролик, до ~11 букв).
8. Ключевые слова субтитров ("accent") — одно на 5–8 с речи: главные существительные, имена, числа, повороты.
   Хотя бы одно в первые 10 с. Пишутся как в транскрипте, без знаков.
9. Распознавание ошибается в именах и терминах: исправь их в "text_fixes" (номер слова → верное написание,
   знаки препинания оставь как были). Имена, которые должны остаться с большой буквы, — в "keep_case".
10. "cta" — слово финального призыва («переходите», «у меня в профиле»); с него и до конца идёт плашка, а
    субтитры спрятаны — поэтому до конца речи от него не больше 3 с, и после него вставок нет.
11. Автор диктует то, что на экране (цифры подряд, буквы «икс, вэ, и»), — у приёма "hide": true, иначе субтитры
    «x v i» задвоят число на листе.
12. Окна приёмов не пересекаются друг с другом и не висят через склейку дубля. Окно — не короче 0,8 с.
    Сплит, клип и «full» — со стыком не меньше 0,3 с между ними.

ПРИЁМЫ («Чертёж»: чёрная бумага, кремовые линии, красный акцент — один мотив на весь ролик)
Раскладки: "chest" — на груди под субтитрами, поверх человека (короткое число, формула, мини-схема);
"behind" — за спиной над головой, человек поверх (маршрут над головой, циркуль сбоку; место над головой и по бокам
дано в запросе — вне его подписи прячутся за головой); "split" — лист сверху,
человек в окне снизу (ось эпох, график, длинная запись, каркас); "full" — лист во весь кадр (самое главное число).
- {"kind": "word", "w": [от, до], "at": номер ударного слова, "text": "слово"} — хук над головой.
- {"kind": "stamp", "w": [i, i], "text": "гениально"} — штамп на груди на эмоциональном слове.
- {"kind": "write", "w": [от, до], "layout": "chest|split|full", "text": "1 2 3 4 5", "sub": "подпись-факт",
   "over": номер слова, "titlo": true} — число/формула пишется линией; "over" — красная черта над словами
   на этом слове (отрезок AB, период), "titlo": true — черта ломаная, как титло над славянской цифрой.
- {"kind": "route", "layout": "behind", "until": номер, "bend": -0.22, "stops": [{"label": "Индия", "x": 0.9,
   "y": 0.2, "w": номер}, …]} — путь точка за точкой на своих словах; за спиной — над головой: y 0.15–0.22,
   x 0.1 / 0.5 / 0.9; в сплите — y 0.2–0.8 свободно.
- {"kind": "timeline", "layout": "split", "until": номер, "marks": [{"label": "IX век", "sub": "Багдад", "w": номер}, …]}
   — ось эпох, засечка на своём слове (2–4 метки, слева направо по времени).
- {"kind": "compass", "w": [от, до], "layout": "behind", "label": "r = 5", "center": [0.82, 0.45], "radius": 0.3}
- {"kind": "hexes", "w": [от, до], "layout": "...", "cols": 5, "rows": 3, "red": 7, "label": "..."} — соты.
- {"kind": "cuboid", "w": [от, до], "layout": "split", "dims": ["12 м", "8 м", "3 м"]} — каркас с размерами.
- {"kind": "plot", "w": [от, до], "layout": "split", "ys": [0.1, 0.2, 0.5, 0.9], "mark": 2, "xlabel": "годы",
   "ylabel": "цена", "label": "+70%"} — кривая по точкам (0…1), отмеченная точка.
- {"kind": "clip", "w": [от, до], "name": "имя из списка принятых", "label": "место, век"} — ИИ-клип во весь кадр.
Любой приём кроме word/stamp/clip может взять "hide": true.

ФОРМАТ ОТВЕТА
{"title": "…", "hook": "auto", "cta": {"w": номер}, "accent": ["…"], "text_fixes": {"номер": "…"},
 "keep_case": ["…"], "hide": [[от, до]], "items": [ …по порядку времени… ]}
"hook": "auto" — место вспышки после хука выберет сборка; {"w": номер} — первое слово основы, если знаешь лучше.
Если дубль не годится в ролик (сорван, оборван на полуслове, одни пробы и мат, нет мысли) — партитуру не выдумывай,
ответь {"skip": "почему — одной фразой"}: монтаж остановится и спросит человека.
Если сборка или проверка найдут ошибки, тебе вернут их списком — ответь исправленной партитурой целиком."""


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
    for name, took in (json.loads(takes.read_text(encoding="utf-8")) if takes.exists() else {}).items():
        note = WORK_DIR / stem / "footage" / f"{name}.md"
        about = re.search(r"Фраза:\s*(.+)", note.read_text(encoding="utf-8")) if note.exists() else None
        shot = re.search(r"Кадр:\s*(.+)", note.read_text(encoding="utf-8")) if note.exists() else None
        clips.append(f"- {name}: {took['duration']:.1f} с; под фразу «{about.group(1) if about else '?'}»; "
                     f"в кадре: {shot.group(1)[:160] if shot else '?'}")
    head = head_room(stem)
    events = WORK_DIR / stem / "events.json"
    ev = json.loads(events.read_text(encoding="utf-8")) if events.exists() else {}
    cfg = project.config
    rules = project.rules.read_text(encoding="utf-8") if project.rules.exists() else "(правил проекта нет)"
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
        "ПРИНЯТЫЕ ИИ-КЛИПЫ (kind clip — только эти имена, клип не длиннее своей длины):",
        *(clips or ["- нет: kind clip не используй"]),
        "",
        f"ПРАВИЛА ПРОЕКТА (projects/{project.name}/rules.md — главнее общих; что про сборку и инфраструктуру — не твоё):",
        rules,
        "",
        "Ответь партитурой (JSON).",
    ])


def head_room(stem: str) -> str:
    """Где голова на экране и сколько места над ней и по бокам — по слежению с камерой (как verify_page: лицо плюс
    0,2 его высоты на волосы, по 0,15 ширины с боков). Без этого аналитик ставил «за спиной» вслепую, и в IMG_3303
    (голова выше) слово хука и подписи сот ушли за голову (19.10.2026)."""
    import verify_page
    from common import ROOT
    track = verify_page.face_track(ROOT / "studio" / stem)
    if not track:
        return "ГОЛОВА В КАДРЕ: слежения нет — «за спиной» ставь только маршрут над головой (y ≤ 0.15)."
    q = lambda i, k: sorted(f[i] for f in track)[min(len(track) - 1, int(k * len(track)))]     # noqa: E731
    x0, y0, x1, y1 = q(1, 0.5), q(2, 0.5), q(3, 0.5), q(4, 0.9)      # подбородок — по наклонам вниз, как Montage._face
    top, high = y0 - 0.2 * (y1 - y0), q(2, 0.1) - 0.2 * (y1 - y0)
    hx0, hx1 = x0 - 0.15 * (x1 - x0), x1 + 0.15 * (x1 - x0)
    box_y, box_h = 280, 460                                         # поле «за спиной» (blueprint.BOXES["behind"])
    free = max(0.0, top - box_y)
    return (f"ГОЛОВА В КАДРЕ (экран 1080×1920, по слежению): голова x {hx0:.0f}–{hx1:.0f}, верх головы обычно y {top:.0f}, "
            f"в самом высоком месте y {high:.0f}. Поле «за спиной» — y 280–740: над головой свободно {free:.0f} px "
            f"(y доли поля 0–{free / box_h:.2f}, точки маршрута — на нижней границе, подписи встанут над ними); сбоку от головы — x 118–{hx0:.0f} и {hx1:.0f}–962. Подписи и линии "
            f"«за спиной» — только в этих местах (за голову уходит не больше трети подписи); свободно над головой меньше 60 px — "
            f"маршрут и подписи над головой не ставь, бери split или chest.")


def home() -> Path:
    """Папка запуска аналитика и критика — вне проекта (иначе Claude Code сам подтянет CLAUDE.md, ~20 КБ, и память
    проекта) и постоянная: сессии Claude Code живут по папке запуска, продолжение разговора ищется в той же."""
    path = Path(tempfile.gettempdir()) / "reels-analyst"
    path.mkdir(exist_ok=True)
    return path


def ask(prompt: str, session: str | None = None, system: str = SYSTEM, tools: str = "") -> dict:
    """Один ход: Claude без CLAUDE.md, со своей системной подсказкой и только с tools. → текст, сессия, цена."""
    import brain
    binary = brain.find_binary("claude")
    if not binary:
        raise RuntimeError("claude не найден на этой машине — аналитику нужен Claude Code")
    cmd = [binary, "-p", prompt, "--output-format", "json", "--model", MODEL, "--effort", EFFORT, "--tools", tools,
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


def assemble(stem: str, variant: str | None, score: dict) -> list:
    """Партитура → страница → проверка. Возвращает провалы (пусто — можно рендерить)."""
    import compose
    import verify_page
    name = compose.project_name(stem, variant)
    project = compose.STUDIO / name
    with page_slot():
        if not (project / "camera.js").exists():
            compose.compose(stem, variant=variant)      # первая сборка: камера и ассеты — сплиту нужна камера
        sc.build(stem, variant, score)
        compose.compose(stem, variant=variant)          # субтитры с решениями партитуры
        return verify_page.verify(name)


def run(stem: str, variant: str | None = "auto", tries: int = TRIES) -> Path:
    log = WORK_DIR / stem / "analyst.jsonl"
    prompt, session = material(stem), None
    for attempt in range(1, tries + 1):
        reply = ask(prompt, session)
        session = reply["session"]
        entry = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "stem": stem, "variant": variant, "attempt": attempt,
                 "cost": reply["cost"], "seconds": reply["seconds"], "tokens": reply["tokens"]}
        try:
            score = parse(reply["text"])
            if score.get("skip"):                       # дубль не годится — не вымучивать ролик из брака
                entry["skip"] = str(score["skip"])
                _log(log, entry)
                raise Skipped(f"аналитик: дубль не годится — {score['skip']}")
            path = sc.path_of(stem, variant)
            path.write_text(json.dumps(score, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            failed = assemble(stem, variant, score)
        except (sc.ScoreError, ValueError) as e:
            failed = [str(e)]
        entry["failed"] = failed
        _log(log, entry)
        print(f"  ход {attempt}: ${reply['cost'] or 0:.2f}, {reply['seconds']:.0f} с, "
              f"{'чисто' if not failed else f'провалов {len(failed)}'}", flush=True)
        if not failed:
            print(f"✓ {sc.path_of(stem, variant).relative_to(WORK_DIR.parent)} → страница готова к рендеру")
            return sc.path_of(stem, variant)
        prompt = ("Сборка и проверка нашли ошибки — исправь партитуру и ответь ею целиком (только JSON):\n- "
                  + "\n- ".join(str(x) for x in failed))
    raise RuntimeError(f"за {tries} хода партитура не прошла проверку — последние провалы в "
                       f"{log.relative_to(WORK_DIR.parent)}")


CRITIC = """Ты — критик монтажа вертикального ролика-урока. Тебе дают партитуру (JSON решений режиссёра: что на каких
словах показать) и лист кадров черновика — файл sheet.png (прочитай его инструментом Read): под каждым кадром время
и что идёт. Машинные проверки (серые зоны, лицо, субтитры, пустые места) уже пройдены — их не ищи.

Смотри глазами зрителя телефона:
- что не читается (мелко, на пёстром, на руке или банке, тёмное на тёмном);
- что не к месту: вставка не про то, что говорится в этот момент, или факт в подписи сомнительный;
- где однообразно: подряд похожие кадры, одна раскладка, нет удара в хуке;
- где вставка закрывает главное — лицо, жест, предмет, о котором речь.

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
    session = None
    for attempt in range(1, tries + 1):
        reply = ask(prompt, session, system=CRITIC, tools="Read")
        session = reply["session"]
        entry = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "stem": stem, "variant": variant, "role": "critic",
                 "attempt": attempt, "cost": reply["cost"], "seconds": reply["seconds"], "tokens": reply["tokens"]}
        try:
            answer = parse(reply["text"])
        except sc.ScoreError as e:
            answer, entry["failed"] = {}, [str(e)]
        entry["notes"] = answer.get("notes") or []
        if answer.get("ok"):
            entry["failed"] = []
            _log(log, entry)
            print(f"  критик: править нечего (${reply['cost'] or 0:.2f}) — {'; '.join(entry['notes'])[:300]}")
            return False
        if "items" in answer:
            fixed = {k: v for k, v in answer.items() if k != "notes"}
            backup = dict(score)
            try:
                failed = assemble(stem, variant, fixed)
            except (sc.ScoreError, ValueError) as e:
                failed = [str(e)]
            entry["failed"] = failed
            _log(log, entry)
            if not failed:
                sc.path_of(stem, variant).write_text(json.dumps(fixed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                print(f"  критик поправил (${reply['cost'] or 0:.2f}): {'; '.join(entry['notes'])[:400]}")
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
            run(args.stem, args.variant or None)
        if args.critic or args.critic_only:
            critique(args.stem, args.variant or None)
    except RuntimeError as e:                   # Skipped — тоже: дубль не годится, нужен человек
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
