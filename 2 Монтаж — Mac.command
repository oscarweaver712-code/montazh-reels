#!/bin/bash
# Двойной клик в Finder — открывается студия монтажа в браузере (сервер живёт в фоне).
# Остановить сервер: .venv/bin/python scripts/studio_up.py --stop
cd "$(dirname "$0")" || exit 1

if [ ! -x .venv/bin/python ]; then
  echo "Окружение не найдено — сначала двойной клик по «1 Установка — Mac.command»"
  read -r -p "Enter чтобы закрыть"
  exit 1
fi

.venv/bin/python scripts/studio_up.py
