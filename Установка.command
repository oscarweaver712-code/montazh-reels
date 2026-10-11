#!/bin/bash
# Установка на новом Mac. Двойной клик в Finder или ./Установка.command в терминале.
# Повторный запуск безопасен: ставится только то, чего не хватает. В конце — самопроверка.
set -euo pipefail
cd "$(dirname "$0")"

HYPERFRAMES="hyperframes@0.8.141"
WHISPER="mlx-community/whisper-large-v3-turbo"

step() { printf '\n▶ %s\n' "$1"; }
fail() {
  printf '\n✗ %s\n' "$1" >&2
  [ -t 0 ] && read -r -p "Enter — закрыть" _
  exit 1
}

step "Проверяю машину"
[ "$(uname -s)" = Darwin ] || fail "Нужен macOS: лица и вырезка фона идут через Apple Vision."
[ "$(uname -m)" = arm64 ] || fail "Нужен Mac на Apple Silicon (M1 и новее): речь распознаётся на MLX."
# вывод сначала в переменную: под pipefail «команда | grep -q» врёт кодом возврата
xcrun_says="$(/usr/bin/xcrun clang 2>&1 || true)"
if grep -qi license <<<"$xcrun_says"; then
  fail "Не принята лицензия Xcode — без неё не работают Homebrew и git. Открой Терминал,
  выполни: sudo xcodebuild -license accept (спросит пароль от Mac) — и запусти установку снова."
fi
command -v brew >/dev/null || fail "Нет Homebrew. Поставь его по инструкции с https://brew.sh и запусти установку снова."

step "Системные программы: ffmpeg-full, node, uv"
for pkg in ffmpeg-full node uv; do
  brew list --formula "$pkg" >/dev/null 2>&1 || brew install "$pkg" || fail "Не поставился $pkg через Homebrew."
done
# обычный ffmpeg собран без libass — субтитры не наложатся
filters="$(ffmpeg -hide_banner -filters 2>/dev/null || true)"
if ! grep -qE '^\s*\S+\s+ass\s' <<<"$filters"; then
  fail "В PATH ffmpeg без libass (наверное, стоит и обычный ffmpeg). Выполни:
  brew unlink ffmpeg && brew link --overwrite ffmpeg-full — и запусти установку снова."
fi

step "Окружение Python (.venv)"
[ -x .venv/bin/python ] || uv venv .venv --python 3.12 || fail "Не создалось окружение Python."
uv pip install --python .venv/bin/python -r requirements.txt || fail "Не поставились пакеты Python — проверь интернет."

step "Модели: речь (~1,6 ГБ), лица, маска человека, текст в кадре (один раз)"
.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('$WHISPER')" \
  || fail "Не скачалась модель $WHISPER — проверь интернет и запусти установку снова."
.venv/bin/python scripts/models.py || fail "Не скачались модели — проверь интернет и запусти установку снова."
.venv/bin/python -c "import easyocr; easyocr.Reader(['ru', 'en'], gpu=False, verbose=False)" >/dev/null \
  || fail "Не скачалась модель распознавания текста (EasyOCR) — проверь интернет."

step "HyperFrames: браузер для рендера графики"
npx --yes "$HYPERFRAMES" telemetry disable >/dev/null || fail "Не запускается HyperFrames через npx."
npx --yes "$HYPERFRAMES" browser ensure || fail "Не скачался браузер HyperFrames — проверь интернет."

step "Звуки и GSAP на месте"
[ -f studio/_vendor/gsap.min.js ] || fail "Нет studio/_vendor/gsap.min.js — репозиторий скачан не целиком."
ls presets/sfx/*.mp3 >/dev/null 2>&1 || fail "Нет звуков в presets/sfx — репозиторий скачан не целиком."

step "Самопроверка (около минуты: честно кодирует видео)"
.venv/bin/python scripts/selfcheck.py || fail "Самопроверка не прошла — пришли её вывод тому, кто ведёт проект."

printf '\n✓ Готово. Открой папку в терминале и запусти claude или codex — студия откроется в браузере сама.\n  Без агента: двойной клик по Монтаж.command. Подробности в README.md\n'
[ -t 0 ] && read -r -p "Enter — закрыть" _
exit 0
