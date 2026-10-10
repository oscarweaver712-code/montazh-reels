#!/usr/bin/env python3
"""Цвет кадра: приведение к стандартному диапазону и яркость в шкале CapCut.

Айфон пишет видео в полном диапазоне (0–255), соцсети и браузер ждут стандартный
(16–235). Если не привести, одни плееры покажут чёрное серым, другие провалят тени.
Поэтому диапазон приводится всегда, первым делом, а яркость крутится уже поверх.

Яркость задаётся как в CapCut, от −50 до +50. Его формула нигде не опубликована,
поэтому здесь своя, но с тем же смыслом: двигаются средние тона, а чёрное и белое
остаются на месте. Наивное «прибавить константу» (eq=brightness) так не умеет: оно
поднимает чёрное в серое или срезает белое, и картинка выглядит застиранной.

Подобрать значение на своём кадре, без экспорта откуда-либо:

  .venv/bin/python scripts/look.py input/IMG_3279.MOV --at 12 --at 40
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import FONT_DIR, WORK_DIR, ffmpeg_bin

# Границы стандартного диапазона яркости в 8 битах
BLACK, WHITE = 16, 235
SPAN = WHITE - BLACK

# Грейды стилей (presets/styles/*.json → color.grade). Мягкие: кожа не должна уезжать
# в оранжевый или зелёный, проверяется глазами на лице, а не на тестовой таблице.
# Контраст считается кривой внутри 16–235, а не через eq=contrast: тот вращает яркость
# вокруг 128 полного диапазона и выталкивает чёрное ниже 16, белое выше 235 — на
# телефоне это срезанные тени и пересвет. Насыщенность и баланс цвета диапазон не трогают.
GRADES = {
    "natural": {},                                                     # как снято
    "warm": {"balance": "rm=0.04:gm=0.01:bm=-0.04:rh=0.03:bh=-0.03", "saturation": 1.04},
    "punchy": {"contrast": 1.08, "saturation": 1.12},                  # под экран телефона
    "cinematic": {"balance": "rs=-0.03:bs=0.04:rh=0.04:bh=-0.03", "contrast": 1.05,
                  "saturation": 0.9},                                  # лёгкий teal/orange
    "editorial": {"balance": "bs=0.03:rh=0.02", "contrast": 1.12, "saturation": 0.85,
                  "vignette": "PI/3.6"},                               # тень уходит, лицо светится
    "bw": {"contrast": 1.1, "saturation": 0.0},
}


def brightness_gamma(brightness: float) -> float:
    """−50…+50 → показатель степени для кривой средних тонов.

    −50 — средний серый уходит вдвое темнее (γ=2), +50 — вдвое светлее (γ=0.5),
    0 — без изменений. −8 даёт γ≈1.12: лицо темнеет примерно на 5%, тени не проваливаются.
    """
    value = max(-50.0, min(50.0, float(brightness)))
    return 2.0 ** (-value / 50.0)


def range_filter() -> str:
    """Любой исходник → стандартный диапазон 16–235, 8 бит 4:2:0."""
    return "scale=out_range=tv,format=yuv420p"


def look_filter(look: dict | None) -> str:
    """Кривая яркости и грейд стиля поверх уже приведённого диапазона. Пустая строка — трогать нечего."""
    if not look or not look.get("enabled", True):
        return ""
    chain = []
    brightness = float(look.get("brightness", 0))
    if abs(brightness) >= 1e-6:
        gamma = brightness_gamma(brightness)
        # запятые внутри выражения экранированы: иначе граф фильтров примет их за разделители
        chain.append(f"lutyuv=y={BLACK}+{SPAN}*pow(clip((val-{BLACK})/{SPAN}\\,0\\,1)\\,{gamma:.5f})")
    chain += grade_chain(look.get("grade") or "natural")
    return ",".join(chain)


def grade_chain(name: str) -> list:
    """Фильтры грейда; на выходе снова стандартный диапазон 16–235, 8 бит 4:2:0."""
    if name not in GRADES:
        raise ValueError(f"Грейд «{name}» не знаю. Есть: {', '.join(GRADES)}")
    g, chain = GRADES[name], []
    if g.get("balance"):
        # баланс цвета считается в RGB: возвращаемся в 16–235 явно, а не как решит ffmpeg
        chain.append(f"colorbalance={g['balance']},scale=out_range=tv,format=yuv420p")
    contrast = float(g.get("contrast", 1.0))
    if abs(contrast - 1.0) > 1e-6:
        chain.append(f"lutyuv=y={BLACK}+{SPAN}*clip(0.5+((val-{BLACK})/{SPAN}-0.5)*{contrast:g}\\,0\\,1)")
    saturation = g.get("saturation")
    if saturation is not None and abs(float(saturation) - 1.0) > 1e-6:
        chain.append(f"eq=saturation={float(saturation):g}")
    if g.get("vignette"):
        # виньетка множит яркость и уводит чёрное ниже 16 — зажимаем обратно в диапазон
        chain.append(f"vignette=angle={g['vignette']},lutyuv=y=clip(val\\,{BLACK}\\,{WHITE})")
    return chain


def expected_luma(y_tv: float, brightness: float) -> float:
    """Чего ждать на выходе для яркости y_tv (уже в 16–235). Нужна самопроверке."""
    norm = min(1.0, max(0.0, (y_tv - BLACK) / SPAN))
    return BLACK + SPAN * norm ** brightness_gamma(brightness)


def strip(video: Path, moments: list, values: list, out: Path) -> Path:
    """Полоска вариантов яркости на настоящих кадрах: выбрать глазами за секунду.

    Это один кадр на строку, а не рендер: split здесь размножает одну картинку и
    памяти не копит. В сборке ролика такого графа быть не должно (см. CLAUDE.md).
    """
    font = WORK_DIR / "fonts" / "Montserrat-ExtraBold.ttf"
    if not font.exists():
        font.parent.mkdir(parents=True, exist_ok=True)
        font.write_bytes((FONT_DIR / "Montserrat-ExtraBold.ttf").read_bytes())

    n_cols = len(values)
    branches, labels = [], []
    for r in range(len(moments)):
        branches.append(f"[{r}:v]split={n_cols}" + "".join(f"[s{r}_{c}]" for c in range(n_cols)))
        for c, value in enumerate(values):
            chain = ",".join(part for part in (
                "scale=360:640:force_original_aspect_ratio=increase:out_range=tv",
                "format=yuv420p", "crop=360:640",
                look_filter({"brightness": value}),
                f"drawtext=fontfile=fonts/{font.name}:text='{value:+g}':x=16:y=16"
                ":fontsize=34:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=8",
            ) if part)
            branches.append(f"[s{r}_{c}]{chain}[r{r}c{c}]")
            labels.append(f"[r{r}c{c}]")

    layout = "|".join(f"{c * 364}_{r * 644}" for r in range(len(moments)) for c in range(n_cols))
    graph = ";".join(branches + [
        "".join(labels) + f"xstack=inputs={len(labels)}:layout={layout}:fill=white[out]"])

    cmd = [ffmpeg_bin(), "-y", "-v", "error"]
    for at in moments:
        cmd += ["-ss", f"{at:.3f}", "-i", str(video.resolve())]
    cmd += ["-filter_complex", graph, "-map", "[out]", "-frames:v", "1", str(out.resolve())]
    # шрифт ищется относительно рабочей папки: в пути проекта пробел и кириллица
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=WORK_DIR)
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-8:])
        sys.exit(f"Не получилось собрать полоску яркости:\n{tail}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Варианты яркости на кадрах ролика")
    ap.add_argument("video")
    ap.add_argument("--at", type=float, action="append", help="секунда кадра (можно несколько)")
    ap.add_argument("--values", default="0,-4,-8,-12,-16", help="значения яркости через запятую")
    args = ap.parse_args()

    video = Path(args.video).resolve()
    if not video.exists():
        sys.exit(f"Нет файла: {video}")
    moments = args.at or [5.0]
    values = [float(v) for v in args.values.split(",") if v.strip()]

    WORK_DIR.mkdir(exist_ok=True)
    out = WORK_DIR / f"{video.stem}.look.jpg"
    strip(video, moments, values, out)
    print(f"  → варианты яркости: {out}")


if __name__ == "__main__":
    main()
