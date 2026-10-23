#!/usr/bin/env python3
"""Автопилот ролика: видео на вход → готовый ролик на выход, без длинного хода мозга (этап 3, 19.10.2026).

Мозг студии монтировал ролик одним ходом на 200–300 тыс. токенов ($2–31): сам готовил дубль, писал page.py и гонял
проверки. Здесь всё, что не требует ума, делает машина, а ИИ — два коротких хода со своей ценой:

  распознавание → события дубля (edit.json) → дубль, слежение → проект             — очередь (инвариант 2)
  нужна ли маска (matte.need: стиль, место над головой) — до аналитика, ему же в материал
  аналитик: партитура по словам дубля → страница (score.py) → verify_page          — ИИ, ~$0,4–1 за ход
  маска только по окнам «человек поверх» этой страницы (matte.py --windows page)    — очередь
  критик: лист кадров черновика → правки партитуры (окна сдвинулись — маска досчитывается) — ИИ, ~$0,6
  рендер → мастеринг → verify_render                                                — очередь

Маска — самый долгий шаг (~15 мин на минуту дубля у BiRefNet). До 22.10.2026 она считалась по всему дублю ДО
аналитика, а видна только в окнах страницы (у партитур — 0–24% ролика) или не нужна вовсе (IMG_0930: голова во весь
кадр, страница cutout=False). Теперь сначала страница, потом маска по её окнам; замер — docstring matte.py.

Готовые шаги пропускаются (файлы на месте). Чего машина решить не может (согласие на долгую маску, сорванный дубль),
автопилот называет и останавливается — громко, с тем, что сделать.

  .venv/bin/python scripts/autopilot.py IMG_3330              # до готового ролика в output/ проекта
  .venv/bin/python scripts/autopilot.py IMG_3330 --no-render  # до страницы — посмотреть в студии
  .venv/bin/python scripts/autopilot.py IMG_3330 --no-critic
  .venv/bin/python scripts/autopilot.py IMG_3330 --probe      # проба: до графики, без маски и рендера (код выхода 4)
  .venv/bin/python scripts/autopilot.py IMG_3330 --finish     # после пробы: маска и рендер по готовой партитуре, без ИИ

Проба (24.10.2026, Валера: «окно с предпросмотром… как там будут выглядеть шрифты и монтаж»): первый ролик проекта в
пачке останавливается, как только собрана страница, — шрифты, субтитры и вставки видны в живом предпросмотре студии,
а долгие маска и рендер не тратятся на то, что человек всё равно бы переделал.
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


class Probe(RuntimeError):
    """Проба готова: страница собрана, дальше — по слову человека (autopilot.py --finish)."""


PROBE_EXIT = 4


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
    rules = project.all_rules_text()                  # проекта и раздела
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


def cut_on_windows(stem: str) -> None:
    """Маска и вырезка только по окнам «человек поверх» страниц ролика — после страницы; потом compose кладёт её в проект.
    Окон нет — маска не считается, это пишется в итог. Долго (дольше пяти минут) без согласия проекта — стоп."""
    import compose
    import matte
    windows = matte.stem_windows(stem)
    aroll = WORK_DIR / stem / "aroll.mp4"
    if not windows:
        ok, why = matte.need(stem)
        matte.record_skip(aroll, why if not ok else "на странице нет окон «человек поверх»")
        print(f"  · маска не считается: {why if not ok else 'на странице нет окон «человек поверх»'}", flush=True)
        return
    info = matte.probe(aroll)
    frames = sum(b - a for a, b in matte.frame_ranges(windows, info["fps"], matte.frame_count(aroll)))
    if matte.needs_consent("birefnet", frames) and not projects.of(stem).config.get("long_matte"):
        raise Stop(f"маска по окнам {stem} — {frames} кадров, дольше пяти минут, а согласия проекта нет (project.json → "
                   f"long_matte): запусти matte.py work/{stem}/aroll.mp4 --windows page --yes сам или включи long_matte")
    queued(f"25-matte-{stem}", [f"python scripts/matte.py work/{stem}/aroll.mp4 --windows page"], timeout_min=240)
    compose.compose(stem)


def run(stem: str, critic: bool = True, render: bool = True, probe: bool = False, finish: bool = False) -> None:
    import analyst
    import compose
    import score as sc
    started = time.time()
    print(f"▶ автопилот {stem}{' — после пробы' if finish else ''}", flush=True)
    prepare(stem)
    compose.compose(stem)                                  # камера и ассеты: сплиту и словам над головой нужно лицо
    import matte
    ok, why = matte.need(stem)
    print(f"  → маска {'по окнам страницы' if ok else 'не нужна'}: {why}", flush=True)
    if finish:                                             # партитура уже принята на пробе — ИИ не зовётся
        if not sc.path_of(stem).exists():
            raise Stop(f"у {stem} нет партитуры work/{stem}/score.json — пробы не было, запусти без --finish")
        sc.build(stem)
        compose.compose(stem)                              # правки человека из монтажной (timeline.json) — поверх
        critic = False
    else:
        analyst.run(stem, None)
    if probe:
        if critic:
            analyst.critique(stem, None)
        raise Probe(f"проба {stem} готова: открой ролик в студии — шрифты, субтитры и вставки в предпросмотре; "
                    f"дальше — «Дальше» в пачке (маска и рендер без ИИ)")
    cut_on_windows(stem)                                   # до критика: на листе кадров человек поверх — настоящий
    if critic and analyst.critique(stem, None):
        cut_on_windows(stem)                               # окна сдвинулись — досчитывается только новое
    # ИИ-клипы Flow автопилот не генерирует (это браузер и бонусы подписки) — берёт только уже принятые; правило проекта
    # «ИИ-видео 1–2 на ролик» тогда не выполнено — сказать до рендера, а не молча (AGENTS.md: «чего-то не может — говорит»)
    if not any(item.get("kind") == "clip" for item in sc.load(stem).get("items") or []):
        print(f"  · ИИ-клипов Flow нет: автопилот их не делает — нужен клип, попроси в чате «оживи» про {stem}", flush=True)
    if render:
        queued(f"05-render-{stem}", [f"python scripts/render_reel.py {stem}"], timeout_min=60)
    log = WORK_DIR / stem / "analyst.jsonl"
    spent = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    cost = sum(e.get("cost") or 0 for e in spent if e.get("at", "") >= time.strftime("%Y-%m-%d %H:%M:%S",
                                                                                     time.localtime(started)))
    print(f"✓ {stem}: автопилот за {(time.time() - started) / 60:.0f} мин, ИИ — ${cost:.2f}", flush=True)


def main():
    ap = argparse.ArgumentParser(description="Видео на вход → готовый ролик: подготовка, аналитик, критик, рендер")
    ap.add_argument("stems", nargs="+")
    ap.add_argument("--no-critic", action="store_true")
    ap.add_argument("--no-render", action="store_true", help="остановиться на странице — посмотреть в студии")
    ap.add_argument("--probe", action="store_true", help="проба: до графики, без маски и рендера (код выхода 4)")
    ap.add_argument("--finish", action="store_true", help="после пробы: маска и рендер по готовой партитуре, без ИИ")
    args = ap.parse_args()
    import analyst
    human, failed, probes = [], [], []
    for stem in args.stems:                # роликов несколько — по одному: тяжёлое всё равно одной очередью
        try:
            run(stem, critic=not args.no_critic, render=not args.no_render, probe=args.probe, finish=args.finish)
        except Probe as e:
            print(f"· {e}", flush=True)
            probes.append(stem)
        except (Stop, analyst.Skipped) as e:   # решать человеку: брак, согласие на маску
            print(f"✗ {stem}: нужен человек — {e}", flush=True)
            human.append(stem)
        except RuntimeError as e:
            print(f"✗ {stem}: {e}", flush=True)
            failed.append(stem)
    # код выхода — для студии: 0 готово, 3 нужен человек, 4 проба готова, 1 не вышло
    if failed:
        sys.exit(1)
    if human:
        sys.exit(3)
    if probes:
        sys.exit(PROBE_EXIT)


if __name__ == "__main__":
    main()
