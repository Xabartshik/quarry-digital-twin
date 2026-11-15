@echo off
chcp 65001 > nul
echo ========================================================
echo  Запуск программного комплекса «Цифровой Двойник Карьера»
echo ========================================================

:: Активация окружения, если оно есть
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo [*] Запуск главного модуля main.py...
python main.py

pause
