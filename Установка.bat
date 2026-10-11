@echo off
chcp 65001 >nul
rem Установка на Windows: двойной клик. Всё делает scripts\install_windows.ps1.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_windows.ps1"
set "code=%errorlevel%"
echo.
pause
exit /b %code%
