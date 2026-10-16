"""Тихие звуки монтажа — свой синтез, без чужих файлов (16.10.2026, тест удержания на IMG_3303).

Валера: звуки на переходы и вылеты текста «должны быть минимально заметны, но они должны быть», «ограниченный пакет…
самые приятные». Библиотечные whoosh и pop под такую тихую громкость слишком жирные (длинный хвост, бас), поэтому пакет
собирается здесь: короткий, без низа, у каждого звука 2–3 варианта по высоте — один и тот же файл подряд не звучит.

  swell-1..3   тёмный мягкий накат, 0,35 с, пик в конце — склейка со вспышкой, вход и выход перебивки, смена плана
               (заменил air-1..3 — шумовой свист на 1–3 кГц; Валера 16.10: «по ушам ездят»)
  tap-1..3     касание стекла, < 0,1 с — влёт слова, подписи, карточки
  tick-1..2    еле слышный тик, 0,04 с — линия схемы рисуется, число бежит
  bubble-1..2  мягкий пузырёк, 0,06 с — штамп, счётчик, плашка

Звуки детерминированные (зерно шума фиксировано): пересборка даёт те же файлы, замер в манифесте не уплывает.
Запуск: .venv/bin/python scripts/sfx_soft.py — пишет presets/sfx/<имя>.mp3 и замер в manifest.json.
"""
import json
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ffmpeg_bin, ffprobe_bin  # noqa: E402

SR = 44100
SFX = Path(__file__).resolve().parent.parent / "presets" / "sfx"


def sweep_noise(dur: float, f0: float, f1: float, q: float, seed: int) -> np.ndarray:
    """Белый шум через полосовой фильтр, центр которого едет f0 → f1 (state-variable, по сэмплу)."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    x = rng.standard_normal(n)
    fc = f0 * (f1 / f0) ** np.linspace(0, 1, n)          # экспоненциально — на слух ровно
    low = band = 0.0
    out = np.empty(n)
    damp = 1.0 / q
    for i in range(n):
        f = 2 * np.sin(np.pi * fc[i] / SR)
        low += f * band
        high = x[i] - low - damp * band
        band += f * high
        out[i] = band
    return out


def env(n: int, peak: float, attack_pow: float = 2.0, release_pow: float = 3.0) -> np.ndarray:
    """Огибающая: плавный подъём до peak (доля длины), спад без щелчка в ноль."""
    t = np.linspace(0, 1, n)
    rise = np.clip(t / peak, 0, 1) ** attack_pow
    fall = np.clip((1 - t) / (1 - peak), 0, 1) ** release_pow
    return np.where(t < peak, rise, fall)


def swell(dur, f0, f1, seed):
    """Накат как обратный вдох: шум ниже 1 кГц, медленный подъём к концу и быстрый уход — пик ложится на вспышку."""
    s = sweep_noise(dur, f0, f1, q=2.0, seed=seed)
    return s * env(len(s), peak=0.8, attack_pow=2.5, release_pow=1.5)


def soft_start(n: int, ms: float = 1.5) -> np.ndarray:
    """Подъём за полторы миллисекунды: мгновенная атака на слух — щелчок по всей полосе."""
    return np.clip(np.arange(n) / (ms / 1000 * SR), 0, 1)


def tap(freq, seed, dur=0.09):
    n = int(dur * SR)
    t = np.arange(n) / SR
    glide = freq * (1 - 0.04 * t / dur)                   # чуть вниз — мягче «пиканья»
    tone = np.sin(2 * np.pi * np.cumsum(glide) / SR) * np.exp(-t / 0.016)
    rng = np.random.default_rng(seed)
    click = rng.standard_normal(n) * np.exp(-t / 0.0015) * 0.08
    return (tone + np.diff(click, prepend=0)) * soft_start(n)    # переходный щелчок — только верх


def tick(freq, dur=0.04):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.0035) * soft_start(n, 1.0)


def bubble(f0, f1, dur=0.06):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.6 * np.exp(-t / 0.03)


PACK = {
    "swell-1": (lambda: swell(0.35, 250, 700, 31), "Dark soft swell peaking at its end — a flash cut, entering a cutaway. No hiss."),
    "swell-2": (lambda: swell(0.35, 300, 900, 32), "Dark soft swell, a little brighter — leaving a cutaway back to the speaker."),
    "swell-3": (lambda: swell(0.32, 220, 600, 33), "Darkest soft swell — slide change, framing switch."),
    "tap-1": (lambda: tap(1450, 21), "Glass-like soft tap — a word or label flies in."),
    "tap-2": (lambda: tap(1750, 22), "Glass-like soft tap, slightly higher — next word or card."),
    "tap-3": (lambda: tap(2050, 23), "Glass-like soft tap, highest — third in a row of items."),
    "tick-1": (lambda: tick(3600), "Barely audible tick — a line of a diagram draws, a number steps."),
    "tick-2": (lambda: tick(4300), "Barely audible tick, higher — next line or step."),
    "bubble-1": (lambda: bubble(620, 300), "Soft bubble pop — stamp lands, counter starts, plate appears."),
    "bubble-2": (lambda: bubble(760, 360), "Soft bubble pop, higher — the next stamp or plate."),
}


REMOVED = {f"air-{i}": "убран 16.10.2026: Валера про звуки на вспышках-переходах — «по ушам ездят» (шумовой свист на "
                         "1–3 кГц); вместо него swell-1..3" for i in (1, 2, 3)}


def write_mp3(name: str, signal: np.ndarray, top: int, low: int = 250) -> Path:
    signal = signal * np.clip(np.arange(len(signal))[::-1] / (0.004 * SR), 0, 1)   # хвост в ноль за 4 мс — без щелчка
    signal = signal / max(1e-9, np.abs(signal).max()) * 0.5        # пик −6 dBFS; громкость дальше — по замеру
    pad = np.zeros(int(0.01 * SR))
    pcm = (np.concatenate([pad, signal, pad]) * 32767).astype(np.int16)
    out = SFX / f"{name}.mp3"
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "x.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        # срез низа ниже low — звук не спорит с голосом; верх выше top — без шипения
        run = subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(wav), "-af", f"highpass=f={low},lowpass=f={top}",
                              "-ar", str(SR), "-c:a", "libmp3lame", "-b:a", "192k", str(out)],
                             capture_output=True, encoding="utf-8", errors="replace")
        if run.returncode:
            raise RuntimeError(f"{name}: ffmpeg не записал mp3 — {run.stderr.strip()[-300:]}")
    return out


def loudness(path: Path) -> float:
    """Как у библиотеки (selfcheck, materials): пиковая мгновенная громкость, LUFS."""
    err = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-af", "apad=pad_dur=1,ebur128",
                          "-f", "null", "-"], capture_output=True, encoding="utf-8", errors="replace").stderr
    return round(max(float(x) for x in re.findall(r"M:\s*(-?[\d.]+)", err)), 1)


def main():
    manifest_path = SFX / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in REMOVED:                         # убранное — из манифеста и с диска, причина — в _removed
        manifest.pop(name, None)
        (SFX / f"{name}.mp3").unlink(missing_ok=True)
        manifest.setdefault("_removed", {})[name] = REMOVED[name]
    for name, (make, about) in PACK.items():
        path = write_mp3(name, make(), *((1400, 120) if name.startswith("swell") else (9000, 250)))
        dur = round(float(subprocess.run([ffprobe_bin(), "-v", "error", "-show_entries",
                                          "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                                         capture_output=True, encoding="utf-8").stdout.strip() or 0), 2)
        manifest[name] = {"file": path.name, "duration": dur, "description": about, "loudness_m": loudness(path),
                          "soft": True, "source": "свой синтез, scripts/sfx_soft.py (16.10.2026)"}
        print(f"  ✓ {name:9s} {dur:.2f} с, {manifest[name]['loudness_m']} LUFS")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
