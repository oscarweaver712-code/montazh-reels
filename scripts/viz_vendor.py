#!/usr/bin/env python3
"""Забрать визуализации из официального каталога HyperFrames в presets/viz/ — офлайн и по-русски.

Каталог HyperFrames (Apache-2.0) — графики, счётчики, карты, блок-схемы, сделанные под
покадровый рендер. Как есть они тянут при рендере GSAP, D3, карту мира и шрифты из интернета
и пишут числа по-английски («182,000»). Здесь каждый элемент один раз ставится командой
`hyperframes add` той же прибитой версии, что и рендер, и правится:
  • библиотеки — на наши копии в studio/_vendor (assets/…): рендер идёт без сети;
  • числа — «ru-RU» (182 000), шрифты — наши, с кириллицей (Inter → Manrope и т. д.);
  • ссылки на Google Fonts и прочие CDN убираются; осталась хоть одна — громкая ошибка.
Результат — presets/viz/compositions/ (в git) и presets/viz/catalog.json — что есть, какие у
элемента переменные. Перезапуск безопасен: обновит из той же версии HyperFrames.

  .venv/bin/python scripts/viz_vendor.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import host
from common import ROOT
from compose import HYPERFRAMES

VIZ = ROOT / "presets" / "viz"
# Что берём. Элементы с переменными студия ставит параметрами (viz.mount); шаблоны режиссёр
# копирует в проект ролика и правит данные руками. exploded-stack не берём: three.js по сети.
ITEMS = ["count-up", "chart-story", "decline-chart", "conic-progress-ring", "before-after-wipe",
         "star-rating-fill", "bar-chart-race", "oscilloscope-trace",
         "data-chart", "mk-line-graph", "mk-progress-stat", "mk-usage-arc",
         "flowchart-vertical", "flowchart", "hw-pipeline", "world-map"]

URLS = {
    "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js": "assets/gsap.min.js",
    "https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js": "assets/vendor/d3.min.js",
    "https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js":
        "assets/vendor/topojson-client.min.js",
    "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json": "assets/vendor/countries-110m.json",
}
FONTS = {'"Inter"': '"Manrope"', "'Inter'": "'Manrope'", '"Libre Baskerville"': '"Cormorant"',
         '"Libre Franklin"': '"Manrope"', "Inter, ": "Manrope, "}


# Рукописный Caveat в каталоге — только латиница: подписи по-русски вышли бы другим шрифтом.
# Кириллица того же шрифта (OFL, fontsource) лежит рядом и подключается своим диапазоном.
CAVEAT_CYRILLIC = """      @font-face {
        font-family: "Caveat";
        src: url("assets/fonts/Caveat-700-cyrillic.woff2") format("woff2");
        font-weight: 700;
        font-display: block;
        unicode-range: U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116;
      }
"""


def patch(text: str) -> str:
    if "Caveat-700-latin.woff2" in text and "Caveat-700-cyrillic.woff2" not in text:
        text = text.replace("      @font-face {\n        font-family: \"Caveat\";", CAVEAT_CYRILLIC +
                            "      @font-face {\n        font-family: \"Caveat\";", 1)
    for url, local in URLS.items():
        text = text.replace(url, local)
    # Google Fonts и предварительные соединения к ним: шрифты даёт страница ролика
    text = re.sub(r'\s*<link[^>]+fonts\.(?:googleapis|gstatic)\.com[^>]*>', "", text)
    text = re.sub(r'\s*<link\s+rel="stylesheet"\s+href="https://fonts[^"]*"\s*/?>', "", text)
    text = text.replace('toLocaleString("en-US"', 'toLocaleString("ru-RU"').replace(
        "toLocaleString()", 'toLocaleString("ru-RU")').replace('Intl.NumberFormat("en-US"', 'Intl.NumberFormat("ru-RU"')
    for old, new in FONTS.items():
        text = text.replace(old, new)
    return text


def variables(text: str) -> list:
    found = re.search(r"data-composition-variables='(\[.*?\])'", text, re.S)
    return json.loads(found.group(1)) if found else []


def main():
    with tempfile.TemporaryDirectory(prefix="reels_viz_") as tmp:
        project = Path(tmp)
        (project / "hyperframes.json").write_text('{"paths": {"assets": "assets"}}', encoding="utf-8")
        (project / "index.html").write_text('<!doctype html><html><head></head><body><div id="root" '
                                            'data-composition-id="main" data-start="0" data-duration="1" '
                                            'data-width="1080" data-height="1920"></div></body></html>',
                                            encoding="utf-8")
        catalog = json.loads(subprocess.run([host.tool("npx"), "--yes", HYPERFRAMES, "catalog", "--json"],
                                            cwd=project, capture_output=True, encoding="utf-8",
                                            errors="replace").stdout or "[]")
        meta = {item["name"]: item for item in catalog}
        for name in ITEMS:
            done = subprocess.run([host.tool("npx"), "--yes", HYPERFRAMES, "add", name, "--no-clipboard"],
                                  cwd=project, capture_output=True, encoding="utf-8", errors="replace")
            if done.returncode != 0:
                sys.exit(f"✗ HyperFrames не поставил {name}:\n{done.stderr[-400:]}")

        out = VIZ / "compositions"
        if out.exists():
            shutil.rmtree(out)
        entries, problems = [], []
        for src in sorted((project / "compositions").rglob("*.html")):
            rel = src.relative_to(project / "compositions")
            text = patch(src.read_text(encoding="utf-8"))
            leftovers = [u for u in re.findall(r"https?://[^\"' )>]+", text) if "www.w3.org" not in u]
            if leftovers:
                problems.append(f"{rel}: {', '.join(sorted(set(leftovers)))}")
            target = out / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            name = src.stem
            item = meta.get(name, {})
            vars_ = variables(text)
            entries.append({"name": name, "file": f"compositions/{rel.as_posix()}", "type": item.get("type"),
                            "title": item.get("title"), "description": item.get("description"),
                            "tags": item.get("tags", []), "dimensions": item.get("dimensions"),
                            "duration": item.get("duration"), "variables": vars_,
                            "mount": bool(vars_)})
        if problems:
            sys.exit("✗ В визуализациях остались ссылки в интернет — рендер не будет офлайн:\n  " + "\n  ".join(problems))
        fonts = project / "assets" / "fonts"
        if fonts.exists():
            shutil.copytree(fonts, VIZ / "assets" / "fonts", dirs_exist_ok=True)
        (VIZ / "catalog.json").write_text(json.dumps({"source": f"{HYPERFRAMES} (Apache-2.0)", "items": entries},
                                                     ensure_ascii=False, indent=1), encoding="utf-8")
    mountable = [e["name"] for e in entries if e["mount"]]
    print(f"✓ {len(entries)} визуализаций в presets/viz: параметрами — {', '.join(mountable)}; "
          f"шаблонами — {', '.join(e['name'] for e in entries if not e['mount'])}")


if __name__ == "__main__":
    main()
