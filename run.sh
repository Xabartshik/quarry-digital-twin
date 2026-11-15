#!/usr/bin/env bash
# Скрипт запуска для Linux / macOS

set -e

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "[*] Запуск программного комплекса «Цифровой Двойник Карьера»..."
python3 main.py
