#!/usr/bin/env python3
"""Транскрибация с потайминговкой по каждому слову (mlx-whisper, ускорение Apple Silicon)."""
import json
import sys
from pathlib import Path

from common import WORK_DIR, ffmpeg_bin, run

MODEL = "mlx-community/whisper-large-v3-turbo"


def extract_audio(video: Path, wav: Path):
    run([
        ffmpeg_bin(), "-y", "-loglevel", "error", "-i", str(video),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav),
    ], "извлекаю аудиодорожку")


def transcribe(wav: Path, language: str = "ru", model: str = MODEL) -> dict:
    import mlx_whisper

    print(f"  → распознаю речь ({model.split('/')[-1]})", flush=True)
    result = mlx_whisper.transcribe(
        str(wav),
        path_or_hf_repo=model,
        word_timestamps=True,
        language=language,
        condition_on_previous_text=False,  # меньше галлюцинаций на паузах
        verbose=None,
    )

    words = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            text = w.get("word", "").strip()
            if not text:
                continue
            words.append({
                "word": text,
                "start": float(w["start"]),
                "end": float(w["end"]),
                "prob": float(w.get("probability", 1.0)),
            })

    return {"words": words, "text": result.get("text", "").strip()}


def check_source(video: Path, cache_dir: Path) -> None:
    """Готовый транскрипт сделан для этого же файла? Сверяется размер исходника.

    Кэш живёт по имени ролика, а у айфонов команды имена одинаковые (IMG_XXXX): новое видео
    под старым именем молча получало чужой транскрипт — с ним чужие субтитры, рез и решения
    режиссёра (text_fixes по номерам слов). Отметка лежит рядом, вне git
    (<имя>.source.json); нет её — ставится по текущему файлу.
    """
    mark_path = cache_dir / f"{video.stem}.source.json"
    size = video.stat().st_size
    if not mark_path.exists():
        mark_path.write_text(json.dumps({"name": video.name, "size": size}), encoding="utf-8")
        return
    was = json.loads(mark_path.read_text(encoding="utf-8")).get("size")
    if was != size:
        sys.exit(f"✗ {video.name} — не тот файл, для которого распознана речь: размер был {was} байт, "
                 f"стал {size}. Транскрипт и решения монтажа work/{video.stem}* — от другого видео. "
                 f"Новое видео — дай ему другое имя. То же, но пересохранённое — распознай заново: "
                 f".venv/bin/python scripts/transcribe.py {video} --force (text_fixes в director.json "
                 "после этого проверь: номера слов могли сдвинуться).")


def run_transcribe(video: Path, language: str = "ru", force: bool = False,
                   cache_dir: Path | None = None) -> dict:
    cache = cache_dir or WORK_DIR
    cache.mkdir(parents=True, exist_ok=True)
    stem = video.stem
    words_json = cache / f"{stem}.words.json"

    if words_json.exists() and not force:
        check_source(video, cache)
        print("  → транскрипт уже есть, использую готовый (--force чтобы пересчитать)")
        with open(words_json, encoding="utf-8") as f:
            return json.load(f)

    wav = cache / f"{stem}.16k.wav"
    try:
        extract_audio(video, wav)
        data = transcribe(wav, language)
    finally:
        wav.unlink(missing_ok=True)          # дорожка для распознавания — временная, даже при сбое

    with open(words_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    # текстовая расшифровка — удобно перечитать глазами и выбрать куски под нарезку
    with open(cache / f"{stem}.txt", "w", encoding="utf-8") as f:
        f.write(data["text"])
    (cache / f"{stem}.source.json").write_text(
        json.dumps({"name": video.name, "size": video.stat().st_size}), encoding="utf-8")

    print(f"  → распознано слов: {len(data['words'])}")
    return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Использование: transcribe.py <видеофайл> [--force]")
    run_transcribe(Path(sys.argv[1]).resolve(), force="--force" in sys.argv)
