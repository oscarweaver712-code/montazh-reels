#!/usr/bin/env python3
"""Стоки для перебивок: поиск листом превью, скачивание с лицензией, кусок под вертикальный кадр ролика.

Источники — бесплатные без указания автора: Coverr (Coverr License, https://coverr.co/license — у бесплатных клипов есть
original.mp4, часто 4K) и Mixkit (Stock Video Free License, https://mixkit.co/license/#videoFree — бесплатно отдаёт
720p, старые клипы — 4K). Платные «premium» Coverr пропускаются. Стиль «Живой отзыв» (scripts/testimonial.py) ставит
готовый кусок перебивкой; инструменты были в work/IMG_6668 (13.10.2026) и не попадали в git — теперь здесь.

  .venv/bin/python scripts/stock.py sheet IMG_9665 coverr "worried woman phone" "autumn leaves"
                                                     → work/IMG_9665/broll/cv_<запрос>.jpg и .txt (номер → slug)
  .venv/bin/python scripts/stock.py sheet IMG_9665 mixkit "hourglass"     → mx_<запрос>.jpg (номер → id)
  .venv/bin/python scripts/stock.py sheet IMG_9665 pexels "graduation dress"  → pe_<запрос>.jpg: только вертикальные,
                                                     не мутнее 720p во весь кадр (ключ — scripts/keys.py, у каждого свой)
  .venv/bin/python scripts/stock.py get IMG_9665 pexels 3195394 gown       → самый лёгкий файл, который даёт 1080p
  .venv/bin/python scripts/stock.py get IMG_9665 coverr coverr-worried-woman-talking-on-phone-in-city phone
  .venv/bin/python scripts/stock.py get IMG_9665 mixkit 28889 hourglass   → broll/<имя>.mp4 + <имя>.md (лицензия)
  .venv/bin/python scripts/stock.py fit IMG_9665 phone --from 0.4 --dur 3.0 --x 0.52
                                                     → materials/broll-phone.mp4: 1080×1920, 30 к/с, без звука
  .venv/bin/python scripts/stock.py take IMG_3666 phone --from 0.4 --dur 4 --x 0.5 --say "…" --shot "…"
                                                     → footage/phone.mp4 + takes.json: автопилот ставит его как клип
                                                       (kind clip) вместо Flow; тяжёлое — через очередь

--x — где центр окна 9:16 по ширине исходника (доля): объект клипа, а не середина кадра. Клип 1080p в вертикали
растягивается ×1,8 — мягче 4K дубля: держи перебивку коротко (1–2,5 с) и с наездом.
"""
import argparse
import io
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import host  # noqa: E402
from common import QUALITY_FLOOR, QUALITY_GOOD, WORK_DIR, ffmpeg_bin, probe, require_queue, sharpness, vertical_crop  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
LICENSE = {
    "coverr": "Coverr License (https://coverr.co/license): бесплатно, в том числе коммерческое, без указания автора",
    "mixkit": "Mixkit Stock Video Free License (https://mixkit.co/license/#videoFree): коммерческое, без указания автора",
    "pexels": ("Pexels License (https://www.pexels.com/license/): бесплатно, в том числе коммерческое, без указания автора; "
               "нельзя продавать без изменений и показывать узнаваемых людей в дурном свете"),
}
PEXELS = "https://api.pexels.com/videos"


class StockError(Exception):
    """Понятная ошибка для человека."""


def fetch(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()


def folder(stem: str) -> Path:
    path = WORK_DIR / stem / "broll"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pexels_api(path: str) -> dict:
    """Запрос к API Pexels со своим ключом (scripts/keys.py): 200 в час, 20 000 в месяц на ключ."""
    import json
    import urllib.error
    import keys
    try:
        key = keys.require("pexels")
    except keys.KeyMissing as e:
        raise StockError(str(e)) from None
    req = urllib.request.Request(f"{PEXELS}/{path}", headers={**UA, "Authorization": key})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise StockError({401: "Pexels не принял ключ — keys.py setup заново",
                          429: "лимит Pexels на этот час кончился (200 запросов) — через час или Mixkit/Coverr"}.get(
                              e.code, f"Pexels ответил {e.code}")) from None


def pexels_pick(files: list) -> dict | None:
    """Какой файл Pexels брать: самый лёгкий из тех, что во весь вертикальный кадр дают 1080p; таких нет — самый чёткий
    не мутнее 720p; и таких нет — None (common.sharpness, 23.10.2026)."""
    rated = [(sharpness(*vertical_crop(f["width"], f["height"]), 1080, 1920), f["width"] * f["height"], f)
             for f in files if f.get("width") and f.get("height") and f.get("file_type", "video/mp4") == "video/mp4"]
    good = [r for r in rated if r[0] >= QUALITY_GOOD]
    if good:
        return min(good, key=lambda r: r[1])[2]
    ok = [r for r in rated if r[0] >= QUALITY_FLOOR]
    return max(ok, key=lambda r: (r[0], r[1]))[2] if ok else None


def search(source: str, query: str) -> list:
    """[(ключ, адрес превью)] по запросу: ключ — slug Coverr, id Mixkit или id Pexels."""
    if source == "pexels":                      # только вертикальные и не меньше Full HD — мыло не показываем вовсе
        data = pexels_api("search?" + urllib.parse.urlencode({"query": query, "orientation": "portrait",
                                                               "size": "medium", "per_page": 24}))
        return [(str(v["id"]), v["image"]) for v in data.get("videos", []) if pexels_pick(v.get("video_files") or [])]
    if source == "coverr":
        html = fetch("https://coverr.co/s?" + urllib.parse.urlencode({"q": query})).decode("utf-8", "replace")
        slugs = list(dict.fromkeys(s for s in re.findall(r"cdn\.coverr\.co/videos/([a-z0-9-]+)/", html) if "premium" not in s))
        return [(s, f"https://cdn.coverr.co/videos/{s}/thumbnail?width=385") for s in slugs[:24]]
    # Mixkit поиск по ?q= игнорирует — запрос живёт в адресе /discover/<слова>/
    slug = urllib.parse.quote(re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-"))
    html = fetch(f"https://mixkit.co/free-stock-video/discover/{slug}/").decode("utf-8", "replace")
    found = dict.fromkeys(re.findall(r"assets\.mixkit\.co/videos/(\d+)/\1-thumb-360-(\d+)\.jpg", html))
    return [(vid, f"https://assets.mixkit.co/videos/{vid}/{vid}-thumb-360-{frame}.jpg") for vid, frame in list(found)[:24]]


def sheet(stem: str, source: str, query: str) -> Path:
    from PIL import Image, ImageDraw
    thumbs = []
    for key, url in search(source, query):
        try:
            thumbs.append((key, Image.open(io.BytesIO(fetch(url))).convert("RGB")))
        except Exception:
            continue
    if not thumbs:
        raise StockError(f"«{query}» в {source}: ничего не нашлось — перефразируй по-английски")
    w, h, cols = 300, 169, 4
    canvas = Image.new("RGB", (w * cols, (h + 34) * ((len(thumbs) + cols - 1) // cols)), "black")
    for k, (key, im) in enumerate(thumbs):
        im.thumbnail((w, h))
        x, y = (k % cols) * w, (k // cols) * (h + 34)
        canvas.paste(im, (x, y))
        name = key.removeprefix("coverr-")
        ImageDraw.Draw(canvas).text((x + 3, y + h + 2), f"{k:02d} {name[:44]}", fill="yellow")
        ImageDraw.Draw(canvas).text((x + 3, y + h + 16), name[44:88], fill="yellow")
    out = folder(stem) / f"{source[:2]}_{re.sub(r'[^a-z0-9]+', '_', query.lower())}.jpg"
    canvas.save(out)
    out.with_suffix(".txt").write_text("\n".join(f"{k:02d} {key}" for k, (key, _) in enumerate(thumbs)) + "\n",
                                       encoding="utf-8")
    return out


def get(stem: str, source: str, key: str, name: str) -> Path:
    if source == "pexels":
        video = pexels_api(f"videos/{int(key)}")
        best = pexels_pick(video.get("video_files") or [])
        if not best:
            raise StockError(f"pexels {key}: нет файла не мутнее {QUALITY_FLOOR}p во весь вертикальный кадр")
        author = (video.get("user") or {}).get("name", "")
        urls = [(f"{best['width']}×{best['height']}", best["link"])]
        page = (video.get("url") or f"https://www.pexels.com/video/{key}/") + (f", автор {author}" if author else "")
    elif source == "coverr":
        urls = [(r, f"https://cdn.coverr.co/videos/{key}/{r}.mp4") for r in ("original", "2160p", "1080p")]
        page = f"https://coverr.co/videos/{key}"
    else:
        urls = [(r, f"https://assets.mixkit.co/videos/{key}/{key}-{r}.mp4") for r in ("2160", "1440", "1080", "720")]
        page = f"https://mixkit.co/free-stock-video/{key}/"
    for res, url in urls:
        try:
            data = fetch(url)
            break
        except Exception:
            continue
    else:
        raise StockError(f"не скачалось видео {key} с {source}")
    out = folder(stem) / f"{name}.mp4"
    out.write_bytes(data)
    info = probe(out)
    p = sharpness(*vertical_crop(info["width"], info["height"]), 1080, 1920)
    if p < QUALITY_FLOOR:                   # не складывать мыло: во весь вертикальный кадр его всё равно не взять
        out.unlink()
        raise StockError(f"{source} {key}: лучшее, что отдают, — {info['width']}×{info['height']}; во весь вертикальный "
                         f"кадр это {p}p, ниже {QUALITY_FLOOR}p — не берём. Нужен вертикальный исходник или 4K")
    out.with_suffix(".md").write_text(f"{source}, {key} ({res}): {page} — {LICENSE[source]}.\n", encoding="utf-8")
    return out


def fit(stem: str, name: str, start: float, dur: float, cx: float) -> Path:
    """Кусок клипа → вертикаль 1080×1920, 30 к/с, без звука, в материалы ролика (одним ffmpeg, память постоянная)."""
    src = folder(stem) / f"{name}.mp4"
    if not src.exists():
        raise StockError(f"нет клипа work/{stem}/broll/{name}.mp4 — сначала stock.py get")
    info = probe(src)
    w, h = info["width"], info["height"]
    if start + dur > info["duration"] + 0.01:
        raise StockError(f"{name}: клип {info['duration']:.1f} с, а взять {start}–{start + dur:.1f} с")
    cw = vertical_crop(w, h)[0]
    p = sharpness(cw, h, 1080, 1920)
    if p < QUALITY_FLOOR:
        raise StockError(f"{name}: {w}×{h} во весь вертикальный кадр — {p}p (из {cw} px ширины растянуто до 1080), ниже "
                         f"{QUALITY_FLOOR}p — не берём. Нужен вертикальный исходник или 4K")
    if p < QUALITY_GOOD:
        print(f"  · {name}: во весь кадр {p}p — ниже {QUALITY_GOOD}p, держи коротко и с наездом", flush=True)
    x = max(0, min(w - cw, int(round(w * cx - cw / 2))))
    out = WORK_DIR / stem / "materials" / f"broll-{name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = (f"crop={cw}:{h}:{x}:0,scale=1080:1920:flags=lanczos,unsharp=5:5:0.5:5:5:0.0,fps=30,"
          f"trim=duration={dur},setpts=PTS-STARTPTS,format=yuv420p")
    ffmpeg = ffmpeg_bin()
    subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", f"{start}", "-i", str(src), "-an", "-vf", vf,
                    "-c:v", host.video_encoder(None, ffmpeg), "-b:v", "16M", "-threads", str(host.encoder_threads()),
                    str(out)], check=True)
    return out


def source_size(stem: str, name: str) -> tuple:
    info = probe(folder(stem) / f"{name}.mp4")
    return info["width"], info["height"]


def take(stem: str, name: str, start: float, dur: float, cx: float, say: str, shot: str) -> dict:
    """Сток на место ИИ-клипа (23.10.2026, Валера: «не используй google flow в этот раз, юзай стоки с интернета»):
    кусок под кадр → work/<имя>/footage/<имя>.mp4 и запись в takes.json, как у footage.py --take. Аналитик автопилота
    и kit.footage берут его так же, как клип Flow; в .md — честно: сток, источник и лицензия, бонусов Flow — 0."""
    import time
    import footage
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise StockError(f"имя «{name}» — только латиница, цифры и «_» (это имя файла)")
    licence = folder(stem) / f"{name}.md"
    if not licence.exists():
        raise StockError(f"нет work/{stem}/broll/{name}.md — сначала stock.py get (там источник и лицензия)")
    piece = fit(stem, name, start, dur, cx)
    out = footage.folder(stem) / f"{name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    piece.replace(out)
    info = probe(out)
    frames = int(round(float(info["duration"]) * footage.FPS))
    data = footage.takes(stem)
    data[name] = {"from": start, "to": round(start + dur, 3), "speed": 1.0, "frames": frames,
                  "duration": round(frames / footage.FPS, 3), "source": "stock", "credits": 0,
                  "source_name": f"broll/{name}.mp4", "sharp": sharpness(*vertical_crop(*source_size(stem, name)), 1080, 1920),
                  "taken": time.strftime("%Y-%m-%d %H:%M"), "need": dur}
    footage._save_takes(stem, data)
    (footage.folder(stem) / f"{name}.md").write_text(
        f"# {name}.mp4\n\nСток, не ИИ и не съёмка: {licence.read_text(encoding='utf-8').strip()}\nФраза: {say}\n"
        f"Кадр: {shot}\nОригинал — broll/{name}.mp4; взято {start}–{start + dur:.2f} с.\nБонусы Flow: 0.\n",
        encoding="utf-8")
    return data[name]


def main():
    host.utf8_console()
    ap = argparse.ArgumentParser(description="Стоки для перебивок: поиск, скачивание, кусок под кадр")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sheet")
    s.add_argument("stem")
    s.add_argument("source", choices=list(LICENSE))
    s.add_argument("queries", nargs="+")
    g = sub.add_parser("get")
    g.add_argument("stem")
    g.add_argument("source", choices=list(LICENSE))
    g.add_argument("key", help="slug Coverr, id Mixkit или id Pexels — из листа превью (.txt рядом)")
    g.add_argument("name")
    f = sub.add_parser("fit")
    f.add_argument("stem")
    f.add_argument("name")
    f.add_argument("--from", dest="start", type=float, default=0.0)
    f.add_argument("--dur", type=float, required=True)
    f.add_argument("--x", type=float, default=0.5, help="центр окна 9:16 по ширине исходника, доля")
    t = sub.add_parser("take", help="сток на место ИИ-клипа: footage/<имя>.mp4 + takes.json (автопилот возьмёт как клип)")
    t.add_argument("stem")
    t.add_argument("name")
    t.add_argument("--from", dest="start", type=float, default=0.0)
    t.add_argument("--dur", type=float, required=True)
    t.add_argument("--x", type=float, default=0.5, help="центр окна 9:16 по ширине исходника, доля")
    t.add_argument("--say", required=True, help="под какую фразу ролика")
    t.add_argument("--shot", required=True, help="что в кадре — словами, для аналитика")
    a = ap.parse_args()
    try:
        if a.cmd == "sheet":
            for q in a.queries:
                print(f"✓ {sheet(a.stem, a.source, q)}")
        elif a.cmd == "get":
            print(f"✓ {get(a.stem, a.source, a.key, a.name)}")
        elif a.cmd == "fit":
            print(f"✓ {fit(a.stem, a.name, a.start, a.dur, a.x)}")
        else:
            require_queue("приём стока")
            got = take(a.stem, a.name, a.start, a.dur, a.x, a.say, a.shot)
            print(f"✓ work/{a.stem}/footage/{a.name}.mp4 — {got['duration']} с, сток")
    except StockError as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
