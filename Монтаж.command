#!/bin/bash
# Двойной клик в Finder — открывается панель монтажа в браузере.
cd "$(dirname "$0")" || exit 1

if [ ! -x .venv/bin/python ]; then
  echo "Окружение не найдено. Собери его: uv venv .venv --python 3.12"
  read -r -p "Enter чтобы закрыть"
  exit 1
fi

( sleep 1.5; open "http://127.0.0.1:8765" ) &
.venv/bin/python scripts/server.py
