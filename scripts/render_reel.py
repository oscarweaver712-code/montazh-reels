#!/usr/bin/env python3
"""Готовый ролик из проекта studio/<имя>/ одной командой — с громким отказом на любом шаге.

  compose (камера, субтитры) → verify_page (ничего не залипнет, ассеты на месте) →
  рендер HyperFrames (--strict: ошибка lint останавливает) → мастеринг звука → verify_render

Раньше эти шаги были строками в задаче очереди, и вывод рендера шёл через `| grep … || true`:
упавший рендер проходил молча, мастеринг брал прошлый renders/*.mp4, и в output/ уезжал
старый ролик с пометкой «готово». Здесь каждый шаг проверяет код возврата, файл рендера
обязан быть свежим, а ролик, не прошедший проверку, в output/ не остаётся.

  .venv/bin/python scripts/render_reel.py IMG_3317                # следующая версия: v2, v3…
  .venv/bin/python scripts/render_reel.py IMG_3317 --version v2
  .venv/bin/python scripts/render_reel.py IMG_3317 --variant hormozi   # вариант для A/B →
                                                     projects/antishkola/output/IMG_3317--hormozi_v1.mp4
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import host
import projects
from common import ROOT, WORK_DIR
from common import require_queue
from compose import HYPERFRAMES, STUDIO, compose, project_name
from master import master
from plan import check as plan_problems
from verify_page import verify

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# из многословного вывода рендера на экран идут только итог, lint и ошибки; всё — в лог
WORTH_SHOWING = re.compile(r"rendered in|Lint:|✗|[Ee]rror|failed")


class Failed(Exception):
    """Шаг сборки не прошёл: ролик не отдаётся, сообщение — человеку."""


def next_version(stem: str) -> str:
    taken = [int(m.group(1)) for p in projects.output_dir(stem.split("--")[0]).glob(f"{stem}_v*.mp4")
             if (m := re.fullmatch(rf"{re.escape(stem)}_v(\d+)\.mp4", p.name))]
    return f"v{max(taken, default=0) + 1}"


def run_logged(cmd: list, cwd: Path, log: Path) -> int:
    """Полный вывод — в лог, на экран — только важные строки."""
    with open(log, "w", encoding="utf-8") as f:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding="utf-8", errors="replace")
        for line in proc.stdout:
            line = ANSI.sub("", line).rstrip()
            f.write(line + "\n")
            if WORTH_SHOWING.search(line):
                print(f"    {line.strip()}", flush=True)
        return proc.wait()


def render_reel(stem: str, version: str, variant: str | None = None, need_plan: bool = True) -> Path:
    name = project_name(stem, variant)
    project = STUDIO / name
    page_py = f"work/{stem}/page.{variant}.py" if variant else f"work/{stem}/page.py"
    if not (project / "index.html").exists():
        raise Failed(f"Нет страницы {project.relative_to(ROOT)}/index.html — сначала {page_py}")
    try:
        out = projects.output_dir(stem) / f"{name}_{version}.mp4"
    except projects.ProjectError as e:
        raise Failed(str(e))
    if out.exists():
        raise Failed(f"{out.relative_to(ROOT)} уже есть — отданный ролик не перезаписываю, "
                     f"возьми другую версию (--version {next_version(name)})")
    # сначала план, потом сборка (правило Валеры 13.10.2026): без годного плана ролик не считается
    if need_plan:
        problems = plan_problems(stem)
        if problems:
            raise Failed("план не готов, рендер не запускаю (сначала план — потом сборка): "
                         + "; ".join(problems[:6]) + f". Проверка: .venv/bin/python scripts/plan.py {stem} --check")
    else:
        print("  · без плана (--no-plan): пересборка ролика, смонтированного до 13.10", flush=True)
    started = time.time()
    print(f"▶ {name} {version}", flush=True)

    compose(stem, variant=variant)
    try:
        failed = verify(name)
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        raise Failed(f"страницу не удалось проверить, рендер не запускаю: {e}")
    if failed:
        raise Failed("страница с ошибками, рендер не запускаю: " + "; ".join(failed))

    raw = project / "renders" / f"{name}_{version}.mp4"
    raw.parent.mkdir(exist_ok=True)
    raw.unlink(missing_ok=True)             # прошлый файл с тем же именем не должен сойти за свежий
    log = WORK_DIR / stem / (f"render_{variant}_{version}.log" if variant else f"render_{version}.log")
    print("  → рендер HyperFrames (одним воркером, машина остаётся живой)", flush=True)
    t0 = time.time()
    code = run_logged([host.tool("npx"), "--yes", HYPERFRAMES, "render", "--workers", "1", "--strict",
                       "-o", str(raw.relative_to(project))], project, log)
    if code != 0 or not raw.exists() or raw.stat().st_mtime < t0:
        tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-12:]
        raise Failed(f"рендер упал (код {code}), ролик не отдан. Полный лог: {log.relative_to(ROOT)}\n"
                     + "\n".join(f"      {line}" for line in tail))

    try:
        stats = master(raw, out)
    except RuntimeError as e:
        raise Failed(str(e))
    print(f"  → громкость {stats['before']['i']:.1f} → {stats['after']['i']:.1f} LUFS, "
          f"пики {stats['after']['tp']:.1f} dBTP", flush=True)

    check = subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_render.py"), str(out),
                            "--stem", stem])
    if check.returncode != 0:
        rejected = raw.with_name(f"{raw.stem}.rejected.mp4")
        out.replace(rejected)
        raise Failed(f"готовый ролик не прошёл проверку — убран из {out.parent.relative_to(ROOT)}/ "
                     f"в {rejected.relative_to(ROOT)}")

    spent = time.time() - started
    print(f"✓ {out.name} за {spent // 60:.0f} мин {spent % 60:.0f} с → {out.relative_to(ROOT)}", flush=True)
    return out


def main():
    require_queue("сборка ролика")
    ap = argparse.ArgumentParser(description="Готовый ролик из проекта HyperFrames, с проверками")
    ap.add_argument("stem", help="имя ролика, например IMG_3317")
    ap.add_argument("--version", help="v1, v2… (по умолчанию — следующая свободная в output/ проекта)")
    ap.add_argument("--variant", help="стиль варианта для A/B (проект studio/<имя>--<стиль>/)")
    ap.add_argument("--no-plan", action="store_true",
                    help="пересобрать ролик, смонтированный до 13.10, без плана (осознанно)")
    args = ap.parse_args()
    try:
        version = args.version or next_version(project_name(args.stem, args.variant))
    except projects.ProjectError as e:
        sys.exit(f"✗ {e}")
    if not re.fullmatch(r"v\d+", version):
        ap.error("версия пишется как v2")
    try:
        render_reel(args.stem, version, args.variant, need_plan=not args.no_plan)
    except Failed as e:
        print(f"✗ {project_name(args.stem, args.variant)} {version}: {e}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
