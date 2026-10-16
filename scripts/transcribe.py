#!/usr/bin/env python3
"""Распознавание речи с таймингом каждого слова — Whisper large-v3-turbo, локально.

Два движка, оба открытые (MIT) и на одной и той же модели:
  mlx-whisper     — Mac на Apple Silicon: считает на графическом ядре, минута речи ~10 с;
  faster-whisper  — Windows, Linux и Mac на Intel: процессор (int8) или видеокарта NVIDIA.

Выбирается сам (mlx, если он есть), заставить — REELS_ASR=mlx или REELS_ASR=faster-whisper.
Тайминги концов слов у обоих врут на десятые доли секунды; границы реза поэтому всё
равно ставятся по настоящей тишине (AGENTS.md, инвариант 3), а не по ним.
"""
import json
import os
import platform
import sys
import time
import wave
from pathlib import Path

import numpy as np

import host
from common import WORK_DIR, ffmpeg_bin, run
from common import require_queue

MODEL = "mlx-community/whisper-large-v3-turbo"        # mlx-whisper
FW_MODEL = "large-v3-turbo"                           # faster-whisper (mobiuslabsgmbh/faster-whisper-large-v3-turbo)


def extract_audio(video: Path, wav: Path):
    run([
        ffmpeg_bin(), "-y", "-loglevel", "error", "-i", str(video),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav),
    ], "извлекаю аудиодорожку")


def backend() -> str:
    """Движок распознавания на этой машине: mlx на Apple Silicon, иначе faster-whisper."""
    forced = os.environ.get("REELS_ASR", "").strip()
    if forced in ("mlx", "faster-whisper"):
        return forced
    if sys.platform == "darwin" and platform.machine() == "arm64":
        try:
            import mlx_whisper  # noqa: F401
            return "mlx"
        except ImportError:
            pass
    return "faster-whisper"


def word(text: str, start: float, end: float, prob: float) -> dict | None:
    text = (text or "").strip()
    return {"word": text, "start": float(start), "end": float(end), "prob": float(prob)} if text else None


def transcribe_mlx(wav: Path, language: str) -> dict:
    import mlx_whisper

    print(f"  → распознаю речь ({MODEL.split('/')[-1]}, mlx)", flush=True)
    result = mlx_whisper.transcribe(
        str(wav),
        path_or_hf_repo=MODEL,
        word_timestamps=True,
        language=language,
        condition_on_previous_text=False,  # меньше галлюцинаций на паузах
        verbose=None,
    )
    words = [w for seg in result.get("segments", []) for raw in seg.get("words", [])
             if (w := word(raw.get("word"), raw["start"], raw["end"], raw.get("probability", 1.0)))]
    return {"words": words, "text": result.get("text", "").strip()}


def transcribe_fw(wav: Path, language: str) -> dict:
    """faster-whisper: на процессоре в int8 и с ограничением потоков — машина остаётся живой."""
    from faster_whisper import WhisperModel

    device, compute = "cpu", "int8"
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            device, compute = "cuda", "float16"
    except Exception:
        pass
    seconds = os.path.getsize(wav) / (16000 * 2)
    print(f"  → распознаю речь ({FW_MODEL}, faster-whisper, {device}); на процессоре это примерно "
          f"{max(1, round(seconds * 0.6 / 60))} мин на {seconds / 60:.1f} мин речи", flush=True)
    model = WhisperModel(FW_MODEL, device=device, compute_type=compute,
                         cpu_threads=host.encoder_threads() if device == "cpu" else 0)
    started = time.time()
    # Звук отдаём готовым массивом: свой декодер faster-whisper (PyAV) ломается от версии к
    # версии (1.2.1 с av 19 падал на открытии файла), а дорожку 16 кГц мы и так сняли ffmpeg.
    with wave.open(str(wav), "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
    segments, _ = model.transcribe(audio, language=language, word_timestamps=True,
                                   condition_on_previous_text=False, vad_filter=False)
    words, text = [], []
    for seg in segments:                                 # генератор: распознаётся по мере чтения
        text.append(seg.text)
        words += [w for raw in seg.words or [] if (w := word(raw.word, raw.start, raw.end, raw.probability))]
    print(f"  → распознано за {time.time() - started:.0f} с", flush=True)
    return {"words": words, "text": "".join(text).strip()}


def transcribe(wav: Path, language: str = "ru") -> dict:
    return transcribe_mlx(wav, language) if backend() == "mlx" else transcribe_fw(wav, language)


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
            data = json.load(f)
        was = data.get("language", "ru")            # транскрипты до 13.10 — все русские
        if was != language:
            sys.exit(f"✗ Речь {video.name} распознана как «{was}», а просят «{language}». Субтитры и рез "
                     f"по словам чужого языка выйдут мусором. Распознай заново: .venv/bin/python "
                     f"scripts/transcribe.py {video} --language {language} --force")
        return data

    wav = cache / f"{stem}.16k.wav"
    try:
        extract_audio(video, wav)
        data = transcribe(wav, language)
        data["language"] = language
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


def check_engine() -> None:
    """Установщик: модель грузится и распознаёт на этой машине — три секунды тона, без файлов проекта.

    Ловит то, чего не видно по скачанной модели: движок не встаёт на эту систему, путь к кэшу
    моделей с кириллицей (имя пользователя Windows) не открывается библиотекой на C++.
    """
    import tempfile

    tone = (0.1 * np.sin(2 * np.pi * 440 * np.arange(16000 * 3) / 16000) * 32767).astype(np.int16)
    with tempfile.TemporaryDirectory(prefix="reels_asr_") as tmp:
        wav = Path(tmp) / "tone.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(tone.tobytes())
        started = time.time()
        transcribe(wav)
    print(f"✓ распознавание речи работает: {backend()}, {time.time() - started:.0f} с вместе с загрузкой модели")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        check_engine()
        sys.exit(0)
    if len(sys.argv) < 2:
        sys.exit("Использование: transcribe.py <видеофайл> [--language en] [--force] | --check")
    require_queue("распознавание речи")
    lang = sys.argv[sys.argv.index("--language") + 1] if "--language" in sys.argv else "ru"
    run_transcribe(Path(sys.argv[1]).resolve(), language=lang, force="--force" in sys.argv)
