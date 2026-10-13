#!/usr/bin/env python3
"""Математика движением: сцена ManimGX (API Manim CE) → клип «доска» для страницы ролика.

  .venv/bin/python scripts/manim_clip.py IMG_3317 work/IMG_3317/manim/roots.py           # класс сцены один
  .venv/bin/python scripts/manim_clip.py IMG_3317 work/IMG_3317/manim/roots.py Roots     # их несколько
  → work/IMG_3317/manim/Roots.mp4 и раскадровка Roots.storyboard.png рядом — посмотреть глазами

Когда к месту: формула, которая преобразуется (разложение, перенос, выделение квадрата), график,
который строится, геометрия, — то, что учитель пишет на доске. Неподвижная формула — viz.formula
(KaTeX): быстрее и легче. На страницу клип ставит viz.board (плашка или во весь кадр за спиной).

ManimGX (MIT, academa-labs/manimgx) живёт в своём окружении .venv-manim — ему нужен Python 3.13;
путь — host.manim_bin, версия — requirements-manim.txt. Сцена пишется в work/<имя>/manim/<файл>.py
(в git): `import manimgx as m`, фон страницы #141210, текст #F2EBDD, акцент #F0352C. Справочник по
API — vendor/video-use/skills/manim-video. Клип — 30 кадров в секунду, как ролик.
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import host  # noqa: E402
from common import ROOT, WORK_DIR, ffmpeg_bin, probe  # noqa: E402

FPS = 30
SIZES = {"square": "1080x1080", "wide": "1080x720", "full": "1080x1920"}


def render(scene: Path, out: Path, name: str | None = None, size: str = SIZES["square"]) -> dict:
    """Рендерит сцену в out (.mp4); вернёт {"duration", "width", "height"}. Сбой — RuntimeError с причиной."""
    tool = host.manim_bin()
    if not tool.exists():
        raise RuntimeError("ManimGX не установлен: запусти установку заново или "
                           "uv venv .venv-manim --python 3.13 && uv pip install --python "
                           f"{'.venv-manim/Scripts/python.exe' if host.IS_WINDOWS else '.venv-manim/bin/python'} "
                           "-r requirements-manim.txt")
    if not scene.exists():
        raise RuntimeError(f"нет сцены {scene}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)               # прошлый клип с тем же именем не должен сойти за свежий
    cmd = [str(tool), "render", str(scene)] + ([name] if name else []) + [
        "-r", size, "--fps", str(FPS), "-o", str(out)]
    done = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace",
                          env=host.utf8_env(), timeout=600)
    report = (done.stdout + done.stderr).strip()
    if done.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"ManimGX не отрендерил {scene.name} (код {done.returncode}):\n{report[-1200:]}")
    # ManimGX пишет паузу одним долгим кадром (переменная частота): 139 кадров на 5,4 с. Поиск по
    # времени промахивается мимо последнего кадра, покадровый рендер — тоже; у нас тайминги на сетке
    # кадров, поэтому клип сразу выравнивается в постоянные 30 к/с (звук доске не нужен)
    even = out.with_name(f".{out.stem}.cfr.mp4")
    try:
        fixed = subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(out), "-an", "-vf", f"fps={FPS},format=yuv420p",
                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                                "-threads", str(host.encoder_threads()), str(even)],
                               capture_output=True, encoding="utf-8", errors="replace")
        if fixed.returncode != 0 or not even.exists():
            raise RuntimeError(f"клип {out.name} не выровнялся в {FPS} к/с:\n{fixed.stderr[-600:]}")
        even.replace(out)
    finally:
        even.unlink(missing_ok=True)
    info = probe(out)
    problems = [line for line in report.splitlines() if line.lower().startswith("layout") and "no problems" not in line]
    return {"duration": round(float(info["duration"]), 3), "width": info["width"], "height": info["height"],
            "layout": problems}


def main():
    ap = argparse.ArgumentParser(description="Сцена ManimGX → клип «доска» для страницы ролика")
    ap.add_argument("stem", help="ролик: IMG_3317")
    ap.add_argument("scene", help="файл сцены: work/IMG_3317/manim/roots.py")
    ap.add_argument("name", nargs="?", help="класс сцены, если в файле их несколько")
    ap.add_argument("--size", default="square", choices=sorted(SIZES),
                    help="square — плашка 1080×1080, wide — 1080×720, full — во весь кадр 9:16")
    args = ap.parse_args()
    scene = Path(args.scene).resolve()
    folder = WORK_DIR / args.stem / "manim"
    if folder.resolve() not in scene.parents:
        sys.exit(f"✗ сцена должна лежать в work/{args.stem}/manim/ — там её видят план, git и compose")
    out = folder / f"{args.name or scene.stem}.mp4"
    try:
        stats = render(scene, out, args.name, SIZES[args.size])
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        sys.exit(f"✗ {e}")
    print(f"✓ {out.relative_to(ROOT)}: {stats['duration']:.2f} с, {stats['width']}×{stats['height']}, "
          f"раскадровка — {out.with_suffix('.storyboard.png').name} рядом")
    for line in stats["layout"]:
        print(f"  · {line}")


if __name__ == "__main__":
    main()
