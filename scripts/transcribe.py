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


def run_transcribe(video: Path, language: str = "ru", force: bool = False) -> dict:
    WORK_DIR.mkdir(exist_ok=True)
    stem = video.stem
    words_json = WORK_DIR / f"{stem}.words.json"

    if words_json.exists() and not force:
        print("  → транскрипт уже есть, использую готовый (--force чтобы пересчитать)")
        with open(words_json, encoding="utf-8") as f:
            return json.load(f)

    wav = WORK_DIR / f"{stem}.16k.wav"
    extract_audio(video, wav)
    data = transcribe(wav, language)

    with open(words_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    # текстовая расшифровка — удобно перечитать глазами и выбрать куски под нарезку
    with open(WORK_DIR / f"{stem}.txt", "w", encoding="utf-8") as f:
        f.write(data["text"])

    wav.unlink(missing_ok=True)
    print(f"  → распознано слов: {len(data['words'])}")
    return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Использование: transcribe.py <видеофайл> [--force]")
    run_transcribe(Path(sys.argv[1]).resolve(), force="--force" in sys.argv)
