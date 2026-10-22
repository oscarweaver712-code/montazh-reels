# Установка на Windows 10/11. Запускается из «1 Установка — Windows.bat» (двойной клик).
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
  # winget дописывает PATH в реестр — в этом окне его надо перечитать, не теряя того, что в нём уже есть
  $env:Path = @($env:Path, [Environment]::GetEnvironmentVariable("Path", "Machine"),
                [Environment]::GetEnvironmentVariable("Path", "User")) -join ";"
}

Step "Проверяю машину"
if (-not [Environment]::Is64BitOperatingSystem) { Fail "Нужна 64-битная Windows 10 или 11." }

Step "Системные программы: ffmpeg (полная сборка с libass), Node.js, uv, Git"
$packages = [ordered]@{ ffmpeg = "Gyan.FFmpeg"; node = "OpenJS.NodeJS.LTS"; uv = "astral-sh.uv"; git = "Git.Git" }
$missing = @($packages.Keys | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) })
# winget нужен, только если чего-то не хватает
if ($missing.Count -gt 0 -and -not (Get-Command winget -ErrorAction SilentlyContinue)) {
  Fail "Нет winget, а поставить нужно: $($missing -join ', '). Поставь «App Installer» из Microsoft Store и запусти установку снова."
}
foreach ($command in $missing) {
  winget install --id $packages[$command] -e --silent --accept-source-agreements --accept-package-agreements
  Check "Не поставился $($packages[$command]) через winget."
  Refresh-Path
}
# без libass субтитры не наложатся: в «essentials»-сборке ffmpeg его нет
# stderr не перенаправляем: в PowerShell 5 при "Stop" любая строка в нём стала бы ошибкой
$filters = (& ffmpeg -hide_banner -filters) -join "`n"
if ($filters -notmatch "(?m)^\s*\S+\s+ass\s") {
  Fail "ffmpeg в PATH собран без libass. Нужна полная сборка: winget install Gyan.FFmpeg — и запусти установку снова."
}
# HDR с айфона переводится в обычный цвет фильтром zscale (libzimg)
if ($filters -notmatch "(?m)^\s*\S+\s+zscale\s") {
  Fail "ffmpeg в PATH собран без zscale — HDR-видео с айфона выйдут бледными. Нужна полная сборка: winget install Gyan.FFmpeg."
}
# сборка ролика читает граф из файла через «-/filter_complex» — так умеет ffmpeg 7.0 и новее
$ffmpegVersion = (& ffmpeg -version | Select-Object -First 1)
if ($ffmpegVersion -match "version (\d+)\." -and [int]$Matches[1] -lt 7) {
  Fail "ffmpeg в PATH слишком старый ($ffmpegVersion). Нужен 7.0 или новее: winget upgrade Gyan.FFmpeg — и запусти установку снова."
}

Step "Окружение Python (.venv)"
if (-not (Test-Path $Python)) { uv venv .venv --python 3.12; Check "Не создалось окружение Python." }
uv pip install --python $Python -r requirements.txt
Check "Не поставились пакеты Python — проверь интернет."

Step "Математика движением: ManimGX (своё окружение — ему нужен Python 3.13)"
$ManimPython = ".venv-manim\Scripts\python.exe"
if (-not (Test-Path $ManimPython)) { uv venv .venv-manim --python 3.13; Check "Не создалось окружение для ManimGX." }
uv pip install --python $ManimPython -r requirements-manim.txt
Check "Не поставился ManimGX — проверь интернет."

Step "Модели: речь (~1,6 ГБ), лица, маска человека, текст в кадре (один раз)"
& $Python -c "from huggingface_hub import snapshot_download; snapshot_download('mobiuslabsgmbh/faster-whisper-large-v3-turbo')"
Check "Не скачалась модель распознавания речи — проверь интернет и запусти установку снова."
& $Python scripts\transcribe.py --check
Check "Распознавание речи не запускается на этой машине — пришли вывод выше тому, кто ведёт проект."
& $Python scripts\models.py
Check "Не скачались модели — проверь интернет и запусти установку снова."
& $Python -c "import easyocr; easyocr.Reader(['ru', 'en'], gpu=False, verbose=False)" | Out-Null
Check "Не скачалась модель распознавания текста (EasyOCR) — проверь интернет."

Step "HyperFrames: браузер для рендера графики"
npx --yes $Hyperframes telemetry disable | Out-Null
Check "Не запускается HyperFrames через npx."
npx --yes $Hyperframes browser ensure
Check "Не скачался браузер HyperFrames — проверь интернет."

Step "Скиллы для Claude: ссылки на общие (git на Windows кладёт вместо них текстовые файлы)"
& $Python scripts\host.py --link-skills
Check "Не подключились скиллы для Claude."

Step "Звуки и GSAP на месте"
if (-not (Test-Path "studio\_vendor\gsap.min.js")) { Fail "Нет studio\_vendor\gsap.min.js — репозиторий скачан не целиком." }
if (-not (Get-ChildItem "presets\sfx\*.mp3" -ErrorAction SilentlyContinue)) { Fail "Нет звуков в presets\sfx — репозиторий скачан не целиком." }

Step "Проекты: у каждого свои клиенты (projects/ — не в git движка)"
& $Python scripts\clients.py ensure
Check "Не создался проект по умолчанию."

Step "Самопроверка (около минуты: честно кодирует видео)"
& $Python scripts\selfcheck.py
Check "Самопроверка не прошла — пришли её вывод тому, кто ведёт проект."

Step "ИИ, который монтирует: Claude (Codex — по желанию)"
& $Python scripts\brain.py --status

Write-Host ""
Write-Host "✓ Готово. Открой папку в терминале и запусти claude — студия откроется в браузере сама. Первые шаги — docs\СТАРТ.md"
Write-Host "  Без агента: двойной клик по «2 Монтаж — Windows.bat». Подробности в README.md"
exit 0
