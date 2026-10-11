#!/usr/bin/env python3
"""Разбор референса: «сделай как у этого ролика» — в числах, а не на глаз.

Идея из video-edit-skill (analyze_reference.py): прежде чем копировать стиль, измерить
его. Отсюда выходит не мнение, а цифры и ближайший стиль из presets/styles:

  • темп: склейки в минуту, средняя длина плана, самый долгий кадр без смены;
  • текст в кадре (Apple Vision, по кадру в секунду): как часто он есть, где стоит,
    сколько слов за раз, капсом ли — это субтитры и надписи референса;
  • цвет: яркость, насыщенность, тёплый или холодный;
  • громкость: интегральная LUFS;
  • речь (по --speech): слов в минуту — нужна распознавалка, это дольше.

Один процесс ffmpeg за раз, кадры идут по одному через канал: память постоянная.

  .venv/bin/python scripts/analyze_reference.py work/downloads/ref.mp4
  .venv/bin/python scripts/analyze_reference.py "https://www.instagram.com/reel/…"   # через uvx yt-dlp
  → work/_refs/<имя>.json и сводка с ближайшими стилями
"""
import argparse
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import styles
from common import WORK_DIR, ffmpeg_bin, probe

REFS = WORK_DIR / "_refs"
SCENE = 0.32          # порог смены плана для ffmpeg scene (0–1)


# ---------------------------------------------------------------- измерения

def fetch(url: str) -> Path:
    """Скачать референс через yt-dlp (uvx — без установки в окружение проекта)."""
    REFS.mkdir(parents=True, exist_ok=True)
    out_tpl = str(REFS / "%(id)s.%(ext)s")
    result = subprocess.run(["uvx", "yt-dlp", "-f", "mp4/best", "-o", out_tpl, "--print", "after_move:filepath",
                             "--no-progress", url], capture_output=True, text=True)
    path = (result.stdout.strip().splitlines() or [""])[-1]
    if result.returncode != 0 or not Path(path).exists():
        raise RuntimeError("Не скачалось через yt-dlp (у Instagram бывает нужен вход). Скачай руками и "
                           "передай путь к файлу.\n" + "\n".join(result.stderr.strip().splitlines()[-4:]))
    return Path(path)


def scene_cuts(video: Path) -> list:
    """Моменты смены плана (с). Кадр уменьшается заранее — ffmpeg считает втрое быстрее."""
    out = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(video), "-an",
                          "-vf", f"scale=320:-2,select='gt(scene,{SCENE})',metadata=print:file=-",
                          "-f", "null", "-"], capture_output=True, text=True).stdout
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", out)]


def color_stats(video: Path) -> dict:
    """Средние яркость, насыщенность и «теплота» (V − U) по двум кадрам в секунду."""
    out = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(video), "-an",
                          "-vf", "fps=2,scale=320:-2,signalstats,metadata=print:file=-",
                          "-f", "null", "-"], capture_output=True, text=True).stdout
    def mean(key: str) -> float | None:
        values = [float(v) for v in re.findall(rf"lavfi\.signalstats\.{key}=([\d.]+)", out)]
        return round(statistics.fmean(values), 1) if values else None
    u, v = mean("UAVG"), mean("VAVG")
    return {"luma": mean("YAVG"), "saturation": mean("SATAVG"),
            "warmth": round(v - u, 1) if u is not None and v is not None else None}


def loudness(video: Path) -> float | None:
    err = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(video), "-vn",
                          "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    found = re.findall(r"I:\s*(-?[\d.]+) LUFS", err)
    return float(found[-1]) if found else None


def screen_text(video: Path, width: int = 540) -> dict:
    """Текст в кадре по кадру в секунду (Apple Vision): где стоит, сколько слов, капс ли."""
    import objc
    import Quartz
    import Vision

    info = probe(video)
    w = width
    h = int(round(info["height"] * w / info["width"] / 2) * 2)
    size = w * h * 4
    proc = subprocess.Popen([ffmpeg_bin(), "-v", "error", "-i", str(video), "-an", "-vf",
                             f"fps=1,scale={w}:{h}", "-pix_fmt", "rgba", "-f", "rawvideo", "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    colorspace = Quartz.CGColorSpaceCreateDeviceRGB()
    frames, with_text, centers, words, heights, upper = 0, 0, [], [], [], []
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            frames += 1
            with objc.autorelease_pool():
                # только CFData: иначе кадр не освобождается (см. track.py)
                provider = Quartz.CGDataProviderCreateWithCFData(Quartz.CFDataCreate(None, buf, size))
                image = Quartz.CGImageCreate(w, h, 8, 32, w * 4, colorspace, Quartz.kCGImageAlphaNoneSkipLast,
                                             provider, None, False, Quartz.kCGRenderingIntentDefault)
                request = Vision.VNRecognizeTextRequest.alloc().init()
                request.setRecognitionLevel_(1)                 # быстрый режим
                request.setUsesLanguageCorrection_(False)
                request.setRecognitionLanguages_(["ru-RU", "en-US"])
                handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
                ok, _ = handler.performRequests_error_([request], None)
                found = False
                for obs in (request.results() or []) if ok else []:
                    candidate = obs.topCandidates_(1)
                    if not candidate:
                        continue
                    text = str(candidate[0].string()).strip()
                    letters = [c for c in text if c.isalpha()]
                    if len(letters) < 2:
                        continue
                    (x, y), (bw, bh) = obs.boundingBox()
                    found = True
                    centers.append(1 - (y + bh / 2))            # 0 — верх кадра, 1 — низ
                    heights.append(bh)
                    words.append(len(text.split()))
                    upper.append(sum(c.isupper() for c in letters) / len(letters))
                with_text += found
    finally:
        proc.stdout.close()
        proc.wait()
    if not frames:
        return {"frames": 0}
    med = (lambda xs: round(statistics.median(xs), 3) if xs else None)
    return {"frames": frames, "share": round(with_text / frames, 2), "y": med(centers),
            "words": med(words), "height": med(heights),
            "upper": round(statistics.fmean(upper), 2) if upper else None}


def speech_rate(video: Path) -> float | None:
    """Слов в минуту по распознаванию (mlx-whisper, тот же, что в конвейере).

    Транскрипт чужого ролика — в work/_refs/, а не рядом с нашими: там .gitignore пропускает
    *.words.json и *.txt в git, и референс уезжал в репозиторий как будто это наш ролик."""
    from transcribe import run_transcribe
    words = run_transcribe(video, cache_dir=REFS)["words"]
    if len(words) < 5:
        return None
    span = words[-1]["end"] - words[0]["start"]
    return round(len(words) / span * 60, 1) if span > 1 else None


# ---------------------------------------------------------------- вывод: какой это стиль

def read_style(m: dict) -> dict:
    """Числа → черты стиля в терминах presets/styles.

    Темп здесь — только настоящие склейки. Наезды и графику на говорящей голове по пикселям
    не отличить от жестов: сырой дубль даёт почти столько же «событий», сколько готовый
    ролик (замерено на IMG_3279). Это честно видно глазами — через timeline_view.py.
    """
    text = m["text"]
    traits = {"cuts_per_min": m["cuts_per_min"]}
    if not text.get("share") or text["share"] < 0.2:
        traits["captions"] = "none"
    elif (text.get("words") or 0) <= 2.2:
        traits["captions"] = "words"
    elif text["words"] <= 4.5:
        traits["captions"] = "phrase"
    else:
        traits["captions"] = "sentence"
    traits["case"] = "upper" if (text.get("upper") or 0) > 0.6 else "lower"
    y = text.get("y")
    traits["position"] = (None if y is None else "top" if y < 0.3 else "center" if y < 0.55
                          else "chest" if y < 0.7 else "lower")
    c = m["color"]
    sat, warm = c.get("saturation") or 0, c.get("warmth") or 0
    # цвет сильно зависит от декорации, поэтому грейд называем только при явных признаках
    traits["grade"] = "bw" if sat < 2.5 else "punchy" if sat > 35 else "warm" if warm > 12 else "natural"
    return traits


def match_styles(traits: dict, fmt: str | None) -> list:
    """Ближайшие стили каталога: субтитры (режим, регистр, место), монтажность, цвет, формат."""
    ranked = []
    for style in styles.all_styles():
        p = style["params"]
        caps = p["captions"]
        # караоке — 2–3 слова за раз: по кадрам это и «по слову-два», и «фраза»
        modes = ("words", "phrase") if caps["mode"] == "karaoke" else (caps["mode"],)
        score = 30 * (traits["captions"] in modes)
        score += 15 * (caps["case"] == traits["case"] or traits["captions"] == "none")
        score += 15 * (traits["position"] is None or caps["position"] == traits["position"])
        fast = 0 < p["pace"]["change_every"] <= 2.5
        if traits["cuts_per_min"] > 15:
            score += 15 * fast                    # нарезка: стиль обязан быть быстрым
        elif traits["cuts_per_min"] < 3:
            score += 15 * (not fast or p["pace"]["cut_pauses"] is False)   # говорящая голова
        else:
            score += 8
        score += 10 * (p["color"]["grade"] == traits["grade"])
        score += 15 * (fmt is None or fmt in style["formats"])
        ranked.append((round(score, 1), style))
    return sorted(ranked, key=lambda pair: -pair[0])


def analyze(video: Path, with_speech: bool = False) -> dict:
    info = probe(video)
    print(f"  → {video.name}: {info['width']}×{info['height']}, {info['duration']:.1f} с", flush=True)
    print("  → склейки", flush=True)
    cuts = scene_cuts(video)
    bounds = [0.0] + cuts + [info["duration"]]
    shots = [b - a for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]
    print("  → текст в кадре (Apple Vision)", flush=True)
    text = screen_text(video)
    print("  → цвет и громкость", flush=True)
    color = color_stats(video)
    fmt = next((k for k, f in styles.formats.FORMATS.items()
                if abs(f["width"] / f["height"] - info["width"] / info["height"]) < 0.03), None)
    m = {"file": str(video), "width": info["width"], "height": info["height"], "format": fmt,
         "duration": round(info["duration"], 2), "cuts": len(cuts),
         "cuts_per_min": round(len(cuts) / info["duration"] * 60, 1) if info["duration"] else 0,
         "avg_shot": round(statistics.fmean(shots), 2) if shots else None,
         "longest_shot": round(max(shots), 2) if shots else None,
         "text": text, "color": color, "lufs": loudness(video) if info["has_audio"] else None}
    if with_speech and info["has_audio"]:
        print("  → речь (распознавание)", flush=True)
        m["wpm"] = speech_rate(video)
    m["traits"] = read_style(m)
    m["matches"] = [{"style": s["id"], "name": s["name"], "score": score}
                    for score, s in match_styles(m["traits"], fmt)[:3]]
    return m


def report(m: dict) -> str:
    t, tr = m["text"], m["traits"]
    pos = {"top": "сверху", "center": "по центру", "chest": "на уровне груди", "lower": "в нижней трети",
           None: "—"}[tr["position"]]
    lines = [
        f"Формат {m['format'] or f'{m['width']}×{m['height']}'}, {m['duration']:.0f} с.",
        f"Темп: {m['cuts']} склеек ({m['cuts_per_min']} в минуту), план в среднем {m['avg_shot']} с, "
        f"самый долгий {m['longest_shot']} с. (наезды и графику на говорящей голове смотри глазами: "
        "timeline_view.py)",
        f"Текст в кадре на {int((t.get('share') or 0) * 100)}% секунд, стоит {pos}, по {t.get('words')} слова, "
        f"{'капсом' if tr['case'] == 'upper' else 'строчными'} → субтитры «{tr['captions']}».",
        f"Цвет: яркость {m['color']['luma']}, насыщенность {m['color']['saturation']}, "
        f"теплота {m['color']['warmth']} → грейд «{tr['grade']}». Громкость {m['lufs']} LUFS.",
    ]
    if m.get("wpm"):
        lines.append(f"Речь: {m['wpm']} слов в минуту.")
    lines.append("Ближе всего: " + "; ".join(f"{x['name']} ({x['score']})" for x in m["matches"]) + ".")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Разбор референса: темп, текст в кадре, цвет, звук → стиль")
    ap.add_argument("source", help="файл или ссылка (скачается через uvx yt-dlp)")
    ap.add_argument("--speech", action="store_true", help="ещё и темп речи (распознавание, дольше)")
    args = ap.parse_args()
    try:
        video = fetch(args.source) if re.match(r"https?://", args.source) else Path(args.source).resolve()
        if not video.exists():
            sys.exit(f"Нет файла: {video}")
        m = analyze(video, args.speech)
    except (RuntimeError, ValueError, styles.StyleError) as e:
        sys.exit(f"✗ {e}")
    REFS.mkdir(parents=True, exist_ok=True)
    out = REFS / f"{video.stem}.json"
    out.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n" + report(m))
    print(f"\n  · цифры: {out.relative_to(WORK_DIR.parent)}")


if __name__ == "__main__":
    main()
