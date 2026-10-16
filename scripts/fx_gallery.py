"""Галерея приёмов scripts/fx.py на дубле IMG_1799 — посмотреть все 17 подряд, по 3 с на приём.

Не ролик: страница собирается в studio/_fx_gallery (подчёркивание — verify_page --all её пропускает), дубль,
вырезка и камера берутся у IMG_1799 жёсткими ссылками. Снимки — hyperframes snapshot в той папке.

  .venv/bin/python scripts/fx_gallery.py && .venv/bin/python scripts/verify_page.py _fx_gallery
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))  # noqa: E402
import fx  # noqa: E402
from kit import build_page  # noqa: E402

SRC, DST = ROOT / "studio" / "IMG_1799", ROOT / "studio" / "_fx_gallery"
CAM = (-83, -135, 1.2)                       # камера IMG_1799 почти стоит: экран = дубль × 1.2 + сдвиг


def el(x, y):
    """Точка экрана → точка дубля (клип и вертиго считаются внутри камеры)."""
    return round((x - CAM[0]) / CAM[2]), round((y - CAM[1]) / CAM[2])


def stage():
    if not (SRC / "index.html").exists() or not (SRC / "assets" / "cutout.webm").exists():
        sys.exit("✗ галерее нужен собранный ролик IMG_1799 (studio/IMG_1799 с вырезкой) — на этой машине его нет")
    DST.mkdir(exist_ok=True)
    for name in ("camera.js", "captions.js", "layers.js", "edits.js", "hyperframes.json", "package.json"):
        shutil.copy2(SRC / name, DST / name)
    for src in (SRC / "assets").rglob("*"):
        if src.is_file():
            out = DST / "assets" / src.relative_to(SRC / "assets")
            out.parent.mkdir(parents=True, exist_ok=True)
            if not out.exists():
                os.link(src, out)
    (DST / "captions.js").write_text("window.CAPTIONS = [];\n", encoding="utf-8")


def main():
    stage()
    S = 3.2                                       # приём на экране
    at = [0.6 + i * S for i in range(17)]
    names = ["orbit", "couch wall", "ui world", "frame break", "digital zoom", "phone mockup", "checklist",
             "headline wall", "zoom-through cut", "chart grow", "pull-back reveal", "green screen", "paper cut",
             "doodle boil", "vertigo", "cover story", "glass type"]
    imgs = ["wallis.jpg", "charles.jpg", "oxford_1.jpg", "night_1.jpg", "war_1.jpg", "conic.jpg"]
    a = lambda i: at[i]
    b = lambda i: at[i] + S - 0.35
    x0, y0 = el(150, 470)
    x1, y1 = el(930, 1450)
    parts = fx.merge(
        fx.toc("toc", names, at, at[-1] + S, top=1020),
        fx.orbit("orb", imgs[:5], a(0), b(0), center=(560, 1050), rx=420, ry=80),
        fx.wall("cw", imgs[:5], [a(1) + 0.2 * k for k in range(5)], b(1), kind="shot"),
        fx.ui_chat("ui", imgs[:5], "/монтаж-рилс", a(2), a(2) + 0.6, a(2) + 1.3, b(2)),
        fx.frame_break("fb", a(3), b(3), box=(170, 470, 910, 1450)),
        fx.phone("ph", [("me", "Смонтируй ролик"), ("ai", "Готово: 4 склейки, субтитры, звук"),
                        ("me", "Добавь чек-лист")], [a(5) + 0.5, a(5) + 1.2, a(5) + 1.9], b(5)),
        fx.checklist("ck", "Всё, что нужно", ["Закинь дубль", "Нажми «Смонтировать»", "Прими версию"],
                     [a(6) + 0.6, a(6) + 1.3, a(6) + 2.0], b(6)),
        fx.wall("hw", ["Claude монтирует ролики", "Минус 4 часа в неделю", "Субтитры сами", "Звук по норме"],
                [a(7) + 0.25 * k for k in range(4)], b(7)),
        fx.zoom_through(a(8) + 1.6),
        fx.chart_grow("ch", a(9), b(9), label="РОСТ ↗"),
        fx.pullback("pb", a(10), b(10), ["Распознал речь", "Вырезал паузы", "Сделал субтитры", "Свёл звук"]),
        fx.backdrop("gs", a(11), b(11)),
        fx.paper_cut("pc", a(12), b(12), "100%"),
        fx.doodle("dd", a(13), b(13)),
        fx.vertigo(a(14), b(14), amount=0.86, origin=(600, 920)),
        fx.cover("cv", a(15), b(15), "EDIT", kicker="выпуск №17 · октябрь", lines=("Монтаж без монтажёра", "17 приёмов")),
        fx.glass_word("gl", a(16), b(16), "ДИЗАЙН"),
    )
    labels = "\n".join(f'        <div id="lb{i}" class="fx fx-sans" style="left: 0; width: 1080px; text-align: center; top: 1330px; '
                       f'font-size: 44px; color: #fff; text-shadow: 0 2px 12px rgba(0,0,0,.6);">{i + 1:02d} · {n}</div>'
                       for i, n in enumerate(names))
    label_js = "\n".join(f'      tl.set("#lb{i}", {{ opacity: 1 }}, {at[i]:.2f}); tl.set("#lb{i}", {{ opacity: 0 }}, {at[i] + S - 0.05:.2f});'
                         for i in range(17))
    dz = f'      tl.fromTo("#aroll, #cutout", {{ scale: 1, transformOrigin: "{el(600, 920)[0]}px {el(600, 920)[1]}px" }}, ' \
         f'{{ scale: 1.35, duration: 0.18, ease: "power3.out", immediateRender: false }}, {a(4) + 0.8:.2f});\n' \
         f'      tl.to("#aroll, #cutout", {{ scale: 1, duration: 0.18, ease: "power3.in" }}, {b(4) - 0.2:.2f});'
    duration = at[-1] + S + 0.5
    page = build_page("Галерея приёмов fx", duration, parts.behind, parts.front + "\n" + labels,
                      parts.js + "\n" + label_js + "\n" + dz, [], parts.windows + [(a(4), b(4))], cta_at=duration - 1,
                      extra_css=parts.css, cta=False)
    page = parts.finalize(page)
    (DST / "index.html").write_text(page, encoding="utf-8")
    print(f"  ✓ {DST.relative_to(ROOT)}/index.html, {duration:.1f} с; приёмы с {', '.join(f'{t:.1f}' for t in at)}")


if __name__ == "__main__":
    main()
