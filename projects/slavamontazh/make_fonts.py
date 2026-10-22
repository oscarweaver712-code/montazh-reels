#!/usr/bin/env python3
"""Шрифты заказчицы «СлаваМонтаж» в presets/fonts — Nicoletta script и SF Pro Display (22.10.2026).

ТЗ Виктории: «Шрифты: Nicoletta + SF Pro Display». Оба не OFL, поэтому в git их нет — этот скрипт кладёт их
на машину заново:

  Nicoletta script (Nikola Kovanovic, 2005, кириллица) — «бесплатно для любого использования, кроме коммерческого»;
      шрифт выбрала заказчица, лицензия на её ролики — её решение. В исходнике нет Ё/ё: дорисовываем составными
      глифами (Е/е + dieresis) — design.py без Ё шрифт не пускает, а «ещё» в речи бывает.
  SF Pro Display (Apple, developer.apple.com/fonts) — пять начертаний, урезаны до латиницы и кириллицы
      (6 МБ → 110 КБ: страница грузит их в каждом кадре рендера).

  .venv/bin/python projects/slavamontazh/make_fonts.py
"""
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "presets" / "fonts"
NICOLETTA_URL = "https://db.onlinewebfonts.com/t/582dfb5520f2a43b5533a76959d1f9f7.ttf"
SF_URL = "https://devimages-cdn.apple.com/design/resources/download/SF-Pro.dmg"
SF_WEIGHTS = ("Light", "Regular", "Medium", "Semibold", "Bold")
UNICODES = ("U+0020-007E,U+00A0-00FF,U+0400-045F,U+2010-2027,U+2030-203A,U+20AC,U+20BD,U+2116,U+2122,"
            "U+2190-2193,U+2212,U+00D7")
# сдвиг точек над Е и е, единицы шрифта (1000 на кегль) — подобран на глаз по оттиску
YO_CAP, YO_LOW = (175, 520), (-95, 70)


def fetch(url: str, dst: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f)


def nicoletta(tmp: Path):
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
    src = tmp / "nicoletta.ttf"
    fetch(NICOLETTA_URL, src)
    f = TTFont(src)
    glyf, hmtx = f["glyf"], f["hmtx"]
    for name, base, (dx, dy) in (("afii10023", "afii10022", YO_CAP), ("afii10071", "afii10070", YO_LOW)):
        g = Glyph()
        g.numberOfContours, g.components = -1, []
        for gname, x, y, flags in ((base, 0, 0, 0x0200), ("dieresis", dx, dy, 0)):   # 0x0200 — метрики базы
            c = GlyphComponent()
            c.glyphName, c.x, c.y, c.flags = gname, x, y, flags
            g.components.append(c)
        glyf[name], hmtx[name] = g, hmtx[base]
        if name not in f.getGlyphOrder():
            f.setGlyphOrder(f.getGlyphOrder() + [name])
    for t in f["cmap"].tables:
        if t.isUnicode():
            t.cmap[0x401], t.cmap[0x451] = "afii10023", "afii10071"
    f["maxp"].numGlyphs = len(f.getGlyphOrder())
    f.save(FONTS / "NicolettaScript.ttf")


def sf_pro(tmp: Path):
    if sys.platform != "darwin":
        sys.exit("✗ SF Pro приходит в .dmg — распаковать его можно только на Mac; скопируй файлы SF-Pro-Display-*.otf "
                 "из presets/fonts с Mac")
    dmg, mnt, pkg = tmp / "SF-Pro.dmg", tmp / "mnt", tmp / "pkg"
    fetch(SF_URL, dmg)
    subprocess.run(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(mnt), str(dmg)],
                   check=True, capture_output=True)
    try:
        subprocess.run(["pkgutil", "--expand-full", str(next(mnt.glob("*.pkg"))), str(pkg)], check=True,
                       capture_output=True)
    finally:
        subprocess.run(["hdiutil", "detach", str(mnt)], capture_output=True)
    from fontTools import subset
    for w in SF_WEIGHTS:
        src = next(pkg.rglob(f"SF-Pro-Display-{w}.otf"))
        subset.main([str(src), f"--unicodes={UNICODES}", "--layout-features=*",
                     f"--output-file={FONTS / src.name}"])


def main():
    with tempfile.TemporaryDirectory() as tmp:
        nicoletta(Path(tmp))
        sf_pro(Path(tmp))
    print("✓ presets/fonts: NicolettaScript.ttf, " + ", ".join(f"SF-Pro-Display-{w}.otf" for w in SF_WEIGHTS))


if __name__ == "__main__":
    main()
