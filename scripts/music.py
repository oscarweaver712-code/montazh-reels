"""Фоновая музыка ролика — лоу-фай из фонотеки YouTube (17.10.2026).

Валера: «фоновую музыку будем менять постоянно, но по громкости негромко, вот как сейчас хорошо, и тоже в стиле
лоуфай». Трек скачивается из фонотеки YouTube Studio (фильтр «указывать автора не требуется», поиск «lofi», жанр
«Хип-хоп и рэп» или «Эмбиент», настроение «Спокойное») — руками или агентом в Chrome. Этот скрипт:

  .venv/bin/python scripts/music.py add IMG_XXXX ~/Downloads/"No Rush - Dyalla.mp3" […]
      кладёт треки в work/<имя>/materials/ как yt-<название>.mp3 (не в git — условия фонотеки), меряет и советует
  .venv/bin/python scripts/music.py used
      какой трек в каком ролике уже стоит — один и тот же в двух роликах verify_page не пустит

Замер — под голос, не под вкус: лучше трек тёмный (энергия ниже 250 Гц), с малой долей в полосе голоса 1–4 кГц и
ровный по громкости (разброс по секундам). На IMG_3303 так выбран No Rush: 1 % в полосе голоса, разброс 3,4 дБ.
В странице — kit.background_music(STEM, "yt-….mp3", DUR): уровень проекта сам.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import host  # noqa: E402
import kit  # noqa: E402
import materials  # noqa: E402
from common import ROOT, ffmpeg_bin  # noqa: E402

host.utf8_console()
SR = 22050
VOICE_BAND_MAX = 4.0      # % энергии в 1–4 кГц: больше — музыка спорит с голосом
SPREAD_MAX = 5.0          # дБ разброса громкости по секундам: больше — музыка «качается» под речью


def slug(path: Path) -> str:
    title = path.stem.split(" - ")[0]                      # «No Rush - Dyalla» → «No Rush»
    return kit.BGM_PREFIX + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") + path.suffix.lower()


def measure(path: Path, seconds: float = 70.0) -> dict:
    raw = subprocess.run([ffmpeg_bin(), "-v", "error", "-t", str(seconds), "-i", str(path), "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True).stdout
    pcm = np.frombuffer(raw, np.int16).astype(float)
    if len(pcm) < SR * 10:
        raise SystemExit(f"✗ {path.name}: меньше 10 с звука — это не трек?")
    spec = np.abs(np.fft.rfft(pcm[:SR * 60])) ** 2
    freq = np.fft.rfftfreq(min(len(pcm), SR * 60), 1 / SR)
    total = spec.sum()
    share = lambda a, b: float(spec[(freq >= a) & (freq < b)].sum() / total * 100)     # noqa: E731
    secs = [20 * np.log10(np.sqrt(np.mean(pcm[i:i + SR] ** 2)) + 1) for i in range(0, len(pcm) - SR, SR)]
    return {"bass": share(0, 250), "voice": share(1000, 4000), "spread": float(np.std(secs[2:60]))}


def used() -> dict:
    """{трек: [ролики]} — по страницам studio/*/index.html."""
    found = {}
    for page in sorted((ROOT / "studio").glob("*/index.html")):
        for name in set(re.findall(r'src="assets/materials/(yt-[^"]+)"', page.read_text(encoding="utf-8"))):
            found.setdefault(name, []).append(page.parent.name)
    return found


def add(stem: str, files: list) -> None:
    taken = used()
    rows = []
    for f in files:
        src = Path(f).expanduser()
        if not src.exists():
            raise SystemExit(f"✗ нет файла {src}")
        name = slug(src)
        if not (materials.folder(stem) / name).exists():
            name = materials.add(stem, name, src)["name"]
        m = measure(materials.folder(stem) / name)
        elsewhere = [s for s in taken.get(name, []) if s.split("--")[0] != stem]
        fits = m["voice"] <= VOICE_BAND_MAX and m["spread"] <= SPREAD_MAX and not elsewhere
        rows.append((not fits, m["voice"] + m["spread"], name, m, elsewhere))
    print(f"Музыка для {stem} (в материалах, не в git):")
    for bad, _, name, m, elsewhere in sorted(rows):
        why = ([f"в полосе голоса {m['voice']:.1f}% > {VOICE_BAND_MAX:g}"] if m["voice"] > VOICE_BAND_MAX else []) + \
              ([f"качается {m['spread']:.1f} дБ > {SPREAD_MAX:g}"] if m["spread"] > SPREAD_MAX else []) + \
              ([f"уже в {', '.join(elsewhere)}"] if elsewhere else [])
        print(f"  {'·' if bad else '✓'} {name:28s} бас {m['bass']:.0f}%, голос 1–4 кГц {m['voice']:.1f}%, "
              f"разброс {m['spread']:.1f} дБ" + (f" — {'; '.join(why)}" if why else ""))
    best = sorted(rows)[0]
    if best[0]:
        print("✗ ни один трек не подходит под голос — скачай другой лоу-фай")
        sys.exit(1)
    print(f'→ в page.py: sounds.append(kit.background_music(STEM, "{best[2]}", DUR))')


def main():
    ap = argparse.ArgumentParser(description="Фоновая музыка ролика (фонотека YouTube, лоу-фай)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="положить треки в материалы ролика и выбрать по замеру")
    a.add_argument("stem")
    a.add_argument("files", nargs="+")
    sub.add_parser("used", help="какой трек в каком ролике")
    args = ap.parse_args()
    if args.cmd == "add":
        add(args.stem, args.files)
    else:
        for name, stems in sorted(used().items()):
            print(f"  {name:28s} {', '.join(stems)}")


if __name__ == "__main__":
    main()
