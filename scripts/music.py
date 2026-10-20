"""Фоновая музыка ролика — лоу-фай из фонотеки YouTube (17.10.2026).

Валера: «фоновую музыку будем менять постоянно, но по громкости негромко, вот как сейчас хорошо, и тоже в стиле
лоуфай». Трек скачивается из фонотеки YouTube Studio (фильтр «указывать автора не требуется», поиск «lofi», жанр
«Хип-хоп и рэп» или «Эмбиент», настроение «Спокойное») — руками или агентом в Chrome. Этот скрипт:

  .venv/bin/python scripts/music.py add IMG_XXXX ~/Downloads/"No Rush - Dyalla.mp3" […]
      кладёт треки в work/<имя>/materials/ как yt-<название>.mp3 (не в git — условия фонотеки), меряет и советует
  .venv/bin/python scripts/music.py used
      какой трек в каком ролике уже стоит — один и тот же в двух роликах verify_page не пустит
  .venv/bin/python scripts/music.py pool antishkola ~/Downloads/*.mp3 --yt-library     # или --mixkit (mx-*.mp3)
      запас треков проекта (projects/<проект>/music/, не в git): montage.py берёт оттуда сам. --yt-library — подтверждение,
      что каждый файл из фонотеки YouTube с пометкой «указывать автора не требуется» (Валера 19.10: «музыка без авторских
      прав, на ютуб выкладываем»); без него запас файл не примет. Учёт — music/pool.json: откуда, когда, кто подтвердил

Запас (19.10.2026): раньше трек скачивался в каждый ролик руками или агентом в Chrome — шаг, на котором монтаж без
человека вставал (IMG_3292 v2 вышла без музыки). Теперь лоу-фай качается пачкой в запас проекта, а сборка
(montage.Montage.build → pick) берёт трек, который подходит под голос и ещё не стоит ни в одном ролике.

Замер — под голос, не под вкус: лучше трек тёмный (энергия ниже 250 Гц), с малой долей в полосе голоса 1–4 кГц и
ровный по громкости (разброс по секундам). На IMG_3303 так выбран No Rush: 1 % в полосе голоса, разброс 3,4 дБ.
В странице — kit.background_music(STEM, "yt-….mp3", DUR): уровень проекта сам.
"""
import argparse
import json
import re
import subprocess
import sys
import time
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


def slug(path: Path, prefix: str = kit.BGM_PREFIX) -> str:
    title = path.stem.split(" - ")[0]                      # «No Rush - Dyalla» → «No Rush»
    title = re.sub(r"^mixkit-|-\d+$", "", title.lower())   # «mixkit-sleepy-cat-135» → «sleepy-cat»
    return prefix + re.sub(r"[^a-z0-9]+", "-", title).strip("-") + path.suffix.lower()


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
        for name in set(re.findall(r'src="assets/materials/((?:yt|mx)-[^"]+)"', page.read_text(encoding="utf-8"))):
            found.setdefault(name, []).append(page.parent.name)
    return found


def pool_dir(project: str) -> Path:
    return ROOT / "projects" / project / "music"


POOL_SOURCE = "фонотека YouTube, «указывать автора не требуется»"
# источники фона: только те, где YouTube прямо разрешён и автора указывать не нужно (ролики идут на YouTube)
SOURCES = {
    "yt": ("yt-", POOL_SOURCE),
    # 20.10.2026, Валера: «найди другой ресурс для музыки» (фонотека YouTube за VPN отдаёт 503). Лицензия Mixkit на музыку:
    # «YouTube videos» — можно, коммерческое — можно, без указания автора; нельзя регистрировать в системах прав (Content
    # ID); пришла заявка — переслать её на team@mixkit.co. Pixabay не берём: часть авторов там сама в Content ID
    "mixkit": ("mx-", "Mixkit, Stock Music Free License: YouTube можно, автора не указывать; заявку — на team@mixkit.co"),
}


def pool_ledger(project: str) -> dict:
    path = pool_dir(project) / "pool.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def pool_add(project: str, files: list, source: str | None) -> None:
    if source not in SOURCES:
        raise SystemExit("✗ В запас кладётся только музыка, которую YouTube пропустит: фонотека YouTube с пометкой «указывать "
                         "автора не требуется» (--yt-library) или Mixkit по Stock Music Free License (--mixkit). Чужой трек "
                         "— Content ID и блок. Скажи, откуда файлы, одним из этих флагов")
    prefix, label = SOURCES[source]
    box = pool_dir(project)
    box.mkdir(parents=True, exist_ok=True)
    ledger = pool_ledger(project)
    for f in files:
        src = Path(f).expanduser()
        if not src.exists():
            raise SystemExit(f"✗ нет файла {src}")
        m = measure(src)
        target = box / slug(src, prefix)
        target.write_bytes(src.read_bytes())
        ledger[target.name] = {"source": label, "file": src.name, "added": time.strftime("%Y-%m-%d %H:%M")}
        (box / "pool.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
        fits = m["voice"] <= VOICE_BAND_MAX and m["spread"] <= SPREAD_MAX
        print(f"  {'✓' if fits else '·'} {target.name:28s} голос 1–4 кГц {m['voice']:.1f}%, разброс {m['spread']:.1f} дБ"
              + ("" if fits else " — под голос не годится, сборка его не возьмёт"))


def pick(stem: str, project: str) -> str:
    """Трек ролику: уже стоящий в его странице → из его материалов → из запаса проекта и чужих неиспользованных.

    Возвращает имя yt-*.mp3 или mx-*.mp3 в материалах ролика (из запаса копирует). Ни один трек не годится — громкая ошибка:
    ролик без музыки verify_page всё равно не пустит, а молча собранный без неё — то, что ломалось (IMG_3292 v2).
    """
    taken = used()
    mine = [n for n, stems in taken.items() if any(s.split("--")[0] == stem for s in stems)]
    busy = {n for n, stems in taken.items() if any(s.split("--")[0] != stem for s in stems)}
    if mine and mine[0] not in busy and (materials.folder(stem) / mine[0]).exists():
        return mine[0]
    # только то, что точно из фонотеки YouTube без указания автора: yt-* в материалах кладёт music.py add (п.9 правил),
    # из запаса — файлы с записью в pool.json (подтверждены при pool --yt-library или --mixkit); прочие mp3 в папке не берутся
    ledger = pool_ledger(project)
    candidates = [p for pre in kit.BGM_PREFIXES for p in sorted(materials.folder(stem).glob(f"{pre}*.mp3"))] \
        + [p for p in sorted(pool_dir(project).glob("*.mp3")) if p.name in ledger] \
        + [p for pre in kit.BGM_PREFIXES for p in sorted((ROOT / "work").glob(f"*/materials/{pre}*.mp3"))]
    best, seen = None, set()
    for path in candidates:
        name = path.name if path.name.startswith(kit.BGM_PREFIXES) else kit.BGM_PREFIX + path.name
        name = re.sub(r"^(yt-)+", kit.BGM_PREFIX, name)
        if name in busy or name in seen:
            continue
        seen.add(name)
        m = measure(path)
        if m["voice"] > VOICE_BAND_MAX or m["spread"] > SPREAD_MAX:
            continue
        if best is None or m["voice"] + m["spread"] < best[0]:
            best = (m["voice"] + m["spread"], name, path)
    if best is None:
        raise RuntimeError(f"Для {stem} нет свободного лоу-фая под голос: запас projects/{project}/music/ кончился. "
                           f"Скачай 3–5 спокойных лоу-фай из фонотеки YouTube (фильтр «указывать автора не требуется») или "
                           f"Mixkit и положи: music.py pool {project} <файлы> --yt-library | --mixkit")
    _, name, path = best
    if not (materials.folder(stem) / name).exists():
        materials.add(stem, name, path)
    return name


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
    pool = sub.add_parser("pool", help="положить треки в запас проекта — сборка возьмёт сама")
    pool.add_argument("project")
    pool.add_argument("files", nargs="+")
    src = pool.add_mutually_exclusive_group()
    src.add_argument("--yt-library", action="store_const", const="yt", dest="source",
                     help="подтверждаю: все файлы из фонотеки YouTube, «указывать автора не требуется»")
    src.add_argument("--mixkit", action="store_const", const="mixkit", dest="source",
                     help="подтверждаю: все файлы с Mixkit, Stock Music Free License")
    args = ap.parse_args()
    if args.cmd == "add":
        add(args.stem, args.files)
    elif args.cmd == "pool":
        pool_add(args.project, args.files, args.source)
    else:
        for name, stems in sorted(used().items()):
            print(f"  {name:28s} {', '.join(stems)}")


if __name__ == "__main__":
    main()
