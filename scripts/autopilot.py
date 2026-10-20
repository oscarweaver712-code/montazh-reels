#!/usr/bin/env python3
"""Автопилот ролика: видео на вход → готовый ролик на выход, без длинного хода мозга (этап 3, 19.10.2026).

Мозг студии монтировал ролик одним ходом на 200–300 тыс. токенов ($2–31): сам готовил дубль, писал page.py и гонял
проверки. Здесь всё, что не требует ума, делает машина, а ИИ — два коротких хода со своей ценой:

  распознавание → события дубля (edit.json) → дубль, слежение, маска → проект   — очередь (инвариант 2)
  аналитик: партитура по словам дубля → страница (score.py) → verify_page          — ИИ, ~$0,4–1 за ход
  критик: лист кадров черновика → правки партитуры                                  — ИИ, ~$0,6
  рендер → мастеринг → verify_render                                                — очередь

Готовые шаги пропускаются (файлы на месте). Чего машина решить не может (согласие на долгую маску, сорванный дубль),
автопилот называет и останавливается — громко, с тем, что сделать.

  .venv/bin/python scripts/autopilot.py IMG_3330              # до готового ролика в output/ проекта
  .venv/bin/python scripts/autopilot.py IMG_3330 --no-render  # до страницы — посмотреть в студии
  .venv/bin/python scripts/autopilot.py IMG_3330 --no-critic
"""
import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jobqueue  # noqa: E402
import projects  # noqa: E402
from common import ROOT, WORK_DIR  # noqa: E402


class Stop(RuntimeError):
    """Автопилот дальше не может — по-русски, что сделать человеку."""


def queued(name: str, steps: list, timeout_min: float = 120) -> None:
    """Задача в очередь и ждать её: тяжёлое — только через очередь, по одному процессу на машине."""
    jobqueue.write_job(name, [shlex.split(s) for s in steps], title=name)        # как jobqueue.py add
    jobqueue.wake()
    print(f"  → очередь: {name}", flush=True)
    code = jobqueue.wait(name, timeout_min * 60)
    if code != 0:
        log = jobqueue.QUEUE / "logs" / f"{name}.log"
        tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-8:] if log.exists() else []
        raise Stop(f"шаг {name} {'упал' if code == 1 else 'не дождался'} — лог {log.relative_to(ROOT)}:\n    "
                   + "\n    ".join(tail))


def prepare(stem: str) -> None:
    """Дубль до проекта: всё, чего ещё нет. Решения о вырезах — events.py --apply (предложение в edit.json)."""
    source = projects.source(stem)
    if not source:
        raise Stop(f"исходника {stem} нет ни в одном input/ проектов")
    if source.is_dir():
        # сборка из нескольких видео (scripts/pack.py): отобрать куски — работа режиссёра с глазами, не аналитика
        raise Stop(f"{stem} — сборка из нескольких видео, ещё не собрана: куски отбирает сессия ИИ (batch.py "
                   f"--brain или «Запустить ИИ-монтаж» в студии) — pack.py {stem}, pack.json, pack.py {stem} --build")
    project = projects.of(stem)
    # дубль, забракованный в правилах проекта («IMG_3308 — сорван, не монтировать»), не готовится зря: маска — десятки
    # минут счёта (19.10.2026: автопилот готовил IMG_3308, а аналитик потом нашёл его в п.6 правил)
    rules = project.rules.read_text(encoding="utf-8") if project.rules.exists() else ""
    for sentence in re.split(r"(?<=[.!?])\s+", rules):
        if stem in sentence and re.search(r"не монтир|сорван|брак", sentence, re.I):
            raise Stop(f"в правилах проекта: «{' '.join(sentence.split())[:160]}» — монтаж только по просьбе")
    src = str(source.relative_to(ROOT))
    work = WORK_DIR / stem
    if not (WORK_DIR / f"{stem}.words.json").exists():
        queued(f"30-words-{stem}", [f"python scripts/transcribe.py {src}"])
    if not (work / "edit.json").exists():
        print("  → события дубля: events.py --apply", flush=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "events.py"), stem, "--apply"], check=True)
    edit = json.loads((work / "edit.json").read_text(encoding="utf-8"))
    steps = []
    if not (work / "aroll.json").exists():
        steps.append(f"python scripts/prep.py {src}")
    if edit.get("hq") and not (work / "aroll.hq.mp4").exists():
        steps.append(f"python scripts/prep.py {src} --hq")
    if not (work / "aroll.faces.json").exists() or "python scripts/prep.py" in " ".join(steps):
        steps.append(f"python scripts/track.py work/{stem}/aroll.mp4")
    if steps:
        queued(f"20-prep-{stem}", steps)
    if not (work / "aroll.cutout.webm").exists():
        project = projects.of(stem)
        if not project.config.get("long_matte"):
            raise Stop(f"маска человека для {stem} — долгий счёт, а согласия проекта нет (project.json → long_matte): "
                       f"запусти matte.py work/{stem}/aroll.mp4 --cutout --yes сам или включи long_matte")
        queued(f"25-matte-{stem}", [f"python scripts/matte.py work/{stem}/aroll.mp4 --cutout"], timeout_min=240)
    if edit.get("hq") and not (work / "aroll.hq.cutout.webm").exists():
        mattes = sorted(work.glob("aroll.matte_*.mkv"), key=lambda p: p.stat().st_mtime)
        if not mattes:
            raise Stop(f"для hq-вырезки нет маски work/{stem}/aroll.matte_*.mkv")
        queued(f"25-matte-hq-{stem}", [f"python scripts/matte.py work/{stem}/aroll.hq.mp4 --cutout "
                                       f"--out work/{stem}/{mattes[-1].name}"])


def run(stem: str, critic: bool = True, render: bool = True) -> None:
    import analyst
    import compose
    started = time.time()
    print(f"▶ автопилот {stem}", flush=True)
    prepare(stem)
    compose.compose(stem)                                  # камера и ассеты: сплиту и словам над головой нужно лицо
    analyst.run(stem, None)
    if critic:
        analyst.critique(stem, None)
    # ИИ-клипы Flow автопилот не генерирует (это браузер и бонусы подписки) — берёт только уже принятые; правило проекта
    # «ИИ-видео 1–2 на ролик» тогда не выполнено — сказать до рендера, а не молча (AGENTS.md: «чего-то не может — говорит»)
    import score as sc
    if not any(item.get("kind") == "clip" for item in sc.load(stem).get("items") or []):
        print(f"  · ИИ-клипов Flow нет: автопилот их не делает — нужен клип, попроси в чате «оживи» про {stem}", flush=True)
    if render:
        queued(f"05-render-{stem}", [f"python scripts/render_reel.py {stem}"], timeout_min=60)
    spent = [json.loads(line) for line in (WORK_DIR / stem / "analyst.jsonl").read_text(encoding="utf-8").splitlines()]
    cost = sum(e.get("cost") or 0 for e in spent if e.get("at", "") >= time.strftime("%Y-%m-%d %H:%M:%S",
                                                                                     time.localtime(started)))
    print(f"✓ {stem}: автопилот за {(time.time() - started) / 60:.0f} мин, ИИ — ${cost:.2f}", flush=True)


def main():
    ap = argparse.ArgumentParser(description="Видео на вход → готовый ролик: подготовка, аналитик, критик, рендер")
    ap.add_argument("stems", nargs="+")
    ap.add_argument("--no-critic", action="store_true")
    ap.add_argument("--no-render", action="store_true", help="остановиться на странице — посмотреть в студии")
    args = ap.parse_args()
    import analyst
    human, failed = [], []
    for stem in args.stems:                # роликов несколько — по одному: тяжёлое всё равно одной очередью
        try:
            run(stem, critic=not args.no_critic, render=not args.no_render)
        except (Stop, analyst.Skipped) as e:   # решать человеку: брак, согласие на маску
            print(f"✗ {stem}: нужен человек — {e}", flush=True)
            human.append(stem)
        except RuntimeError as e:
            print(f"✗ {stem}: {e}", flush=True)
            failed.append(stem)
    # код выхода — для студии: 0 готово, 3 нужен человек, 1 не вышло
    if failed:
        sys.exit(1)
    if human:
        sys.exit(3)


if __name__ == "__main__":
    main()
