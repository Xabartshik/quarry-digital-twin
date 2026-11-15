@echo off
chcp 65001 > nul
echo ========================================================
echo  Установка окружения для проекта «Цифровой Двойник Карьера»
echo ========================================================

:: Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден! Установите Python 3.10+ и добавьте его в PATH.
    pause
    exit /b 1
)

:: Создание виртуального окружения, если отсутствует
if not exist ".venv" (
    echo [*] Создание виртуального окружения .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось создать виртуальное окружение.
        pause
        exit /b 1
    )
) else (
    echo [*] Виртуальное окружение .venv уже существует.
)

:: Активация и установка зависимостей
echo [*] Обновление pip и установка зависимостей из requirements.txt...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo [ОШИБКА] Произошла ошибка при установке зависимостей.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  Установка успешно завершена!
echo  Для запуска проекта используйте run.bat
echo ========================================================
pause
