@echo off
chcp 65001 >nul
rem Двойной клик — открывается студия монтажа в браузере (сервер живёт в фоне).
rem Остановить сервер: .venv\Scripts\python.exe scripts\studio_up.py --stop
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Окружение не найдено — сначала двойной клик по Установка.bat
  pause
  exit /b 1
)
set PYTHONUTF8=1
".venv\Scripts\python.exe" scripts\studio_up.py
