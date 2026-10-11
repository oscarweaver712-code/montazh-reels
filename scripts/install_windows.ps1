# Установка на Windows 10/11. Запускается из Установка.bat (двойной клик).
# Повторный запуск безопасен: ставится только то, чего не хватает. В конце — самопроверка.
# Файл сохранён в UTF-8 с BOM: иначе Windows PowerShell 5 прочтёт кириллицу как кракозябры.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$Hyperframes = "hyperframes@0.8.141"
$Python = ".venv\Scripts\python.exe"

function Step($text) { Write-Host ""; Write-Host "▶ $text" }
function Fail($text) { Write-Host ""; Write-Host "✗ $text" -ForegroundColor Red; exit 1 }
function Check($what) { if ($LASTEXITCODE -ne 0) { Fail $what } }
function Refresh-Path {
  # winget дописывает PATH в реестр — в этом окне его надо перечитать
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

Step "Проверяю машину"
if (-not [Environment]::Is64BitOperatingSystem) { Fail "Нужна 64-битная Windows 10 или 11." }
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  Fail "Нет winget. Поставь «App Installer» из Microsoft Store и запусти установку снова."
}

Step "Системные программы: ffmpeg (полная сборка с libass), Node.js, uv, Git"
$packages = [ordered]@{ ffmpeg = "Gyan.FFmpeg"; node = "OpenJS.NodeJS.LTS"; uv = "astral-sh.uv"; git = "Git.Git" }
foreach ($command in $packages.Keys) {
  if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
    winget install --id $packages[$command] -e --silent --accept-source-agreements --accept-package-agreements
    Check "Не поставился $($packages[$command]) через winget."
    Refresh-Path
  }
}
Refresh-Path
# без libass субтитры не наложатся: в «essentials»-сборке ffmpeg его нет
# stderr не перенаправляем: в PowerShell 5 при "Stop" любая строка в нём стала бы ошибкой
$filters = (& ffmpeg -hide_banner -filters) -join "`n"
if ($filters -notmatch "(?m)^\s*\S+\s+ass\s") {
  Fail "ffmpeg в PATH собран без libass. Нужна полная сборка: winget install Gyan.FFmpeg — и запусти установку снова."
}

Step "Окружение Python (.venv)"
if (-not (Test-Path $Python)) { uv venv .venv --python 3.12; Check "Не создалось окружение Python." }
uv pip install --python $Python -r requirements.txt
Check "Не поставились пакеты Python — проверь интернет."

Step "Модели: речь (~1,6 ГБ), лица, маска человека, текст в кадре (один раз)"
& $Python -c "from huggingface_hub import snapshot_download; snapshot_download('mobiuslabsgmbh/faster-whisper-large-v3-turbo')"
Check "Не скачалась модель распознавания речи — проверь интернет и запусти установку снова."
& $Python scripts\models.py
Check "Не скачались модели — проверь интернет и запусти установку снова."
& $Python -c "import easyocr; easyocr.Reader(['ru', 'en'], gpu=False, verbose=False)" | Out-Null
Check "Не скачалась модель распознавания текста (EasyOCR) — проверь интернет."

Step "HyperFrames: браузер для рендера графики"
npx --yes $Hyperframes telemetry disable | Out-Null
Check "Не запускается HyperFrames через npx."
npx --yes $Hyperframes browser ensure
Check "Не скачался браузер HyperFrames — проверь интернет."

Step "Звуки и GSAP на месте"
if (-not (Test-Path "studio\_vendor\gsap.min.js")) { Fail "Нет studio\_vendor\gsap.min.js — репозиторий скачан не целиком." }
if (-not (Get-ChildItem "presets\sfx\*.mp3" -ErrorAction SilentlyContinue)) { Fail "Нет звуков в presets\sfx — репозиторий скачан не целиком." }

Step "Самопроверка (около минуты: честно кодирует видео)"
& $Python scripts\selfcheck.py
Check "Самопроверка не прошла — пришли её вывод тому, кто ведёт проект."

Write-Host ""
Write-Host "✓ Готово. Открой папку в терминале и запусти claude или codex — студия откроется в браузере сама."
Write-Host "  Без агента: двойной клик по Монтаж.bat. Подробности в README.md"
exit 0
