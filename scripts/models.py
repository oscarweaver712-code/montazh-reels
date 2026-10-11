#!/usr/bin/env python3
"""Файлы моделей: откуда, какой лицензии и какой контрольной суммы.

Модели скачиваются один раз при установке в models/ (вне git) и сверяются по sha256:
во время монтажа сеть не нужна, и через полгода ролик соберётся той же моделью. Маленькая
модель поиска лиц лежит прямо в репозитории (presets/models/).

Всё открытое: распознавание речи — Whisper (MIT, скачивает сам движок), лица — YuNet (MIT),
маска человека — MediaPipe Selfie Multiclass (Apache-2.0), запасная маска — RVM (GPL-3.0).

  .venv/bin/python scripts/models.py           # скачать недостающие и проверить все
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import MODEL_DIR, ROOT

DOWNLOADS = ROOT / "models"

MODELS = {
    "yunet": {
        "path": MODEL_DIR / "face_detection_yunet_2023mar.onnx",
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        "license": "MIT", "what": "поиск лиц (OpenCV YuNet)",
    },
    "selfie_multiclass": {
        "path": DOWNLOADS / "selfie_multiclass_256x256.tflite",
        "url": "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/1/selfie_multiclass_256x256.tflite",
        "sha256": "c6748b1253a99067ef71f7e26ca71096cd449baefa8f101900ea23016507e0e0",
        "license": "Apache-2.0", "what": "маска человека (MediaPipe)",
    },
    "rvm": {
        "path": DOWNLOADS / "rvm_mobilenetv3_fp32.torchscript",
        "url": "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.torchscript",
        "sha256": "f01e0c9338b9a6a31b881ea6d4360d70c1e549701b3792e14c9ed88d6196c5a1",
        "license": "GPL-3.0", "what": "запасная маска (Robust Video Matting)", "optional": True,
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure(name: str, download: bool = True) -> Path:
    """Путь к модели. Нет файла — скачивает; сумма не сходится — громкая ошибка, а не тихая подмена."""
    spec = MODELS[name]
    path = spec["path"]
    if not path.exists():
        if not download:
            raise RuntimeError(f"Нет модели «{spec['what']}»: {path.relative_to(ROOT)}. "
                               f"Скачай: .venv/bin/python scripts/models.py")
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(f".{path.name}.part")
        try:
            print(f"  → качаю модель: {spec['what']} ({spec['license']})", flush=True)
            with urllib.request.urlopen(spec["url"], timeout=60) as res, open(part, "wb") as out:
                while block := res.read(1 << 20):
                    out.write(block)
            if sha256(part) != spec["sha256"]:
                raise RuntimeError(f"Модель «{spec['what']}» скачалась не та (контрольная сумма не сошлась): {spec['url']}")
            part.replace(path)
        except OSError as e:
            raise RuntimeError(f"Не скачалась модель «{spec['what']}»: {e}. Проверь интернет и запусти "
                               f".venv/bin/python scripts/models.py") from e
        finally:
            part.unlink(missing_ok=True)
    return path


def main():
    bad = []
    for name, spec in MODELS.items():
        try:
            path = ensure(name)
            ok = sha256(path) == spec["sha256"]
            print(f"  {'✓' if ok else '✗'} {spec['what']}: {path.relative_to(ROOT)} ({spec['license']})")
            if not ok:
                bad.append(name)
        except RuntimeError as e:
            print(f"  {'·' if spec.get('optional') else '✗'} {e}")
            if not spec.get("optional"):
                bad.append(name)
    if bad:
        sys.exit(f"✗ Модели не в порядке: {', '.join(bad)}")


if __name__ == "__main__":
    main()
