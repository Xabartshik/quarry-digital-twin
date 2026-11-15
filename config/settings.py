"""
Модуль конфигурации параметров системы Цифрового Двойника Карьера.
Содержит настройки видеопотока, сетевого взаимодействия, базы данных и логирования.
"""

import logging
from pathlib import Path

from pydantic import BaseModel

# Корневая директория проекта
BASE_DIR = Path(__file__).resolve().parent.parent

# Директории для сохранения данных и логов
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Настройка единого логгера приложения
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "quarry_twin.log", encoding="utf-8")
    ]
)

logger = logging.getLogger("QuarryTwinConfig")


class Settings(BaseModel):
    """
    Класс глобальных настроек проекта.
    """
    # Настройки веб-сервера
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # Настройки базы данных SQLite по умолчанию
    DB_URL: str = f"sqlite:///{DATA_DIR / 'quarry_twin.db'}"

    # Настройки видеопотока по умолчанию: IP-камера смартфона
    CAMERA_SOURCE: int | str = "http://192.168.0.103:8080/video"
    CAMERA_FPS: int = 30
    FRAME_WIDTH: int = 1280
    FRAME_HEIGHT: int = 720

    # Режим симуляции (по умолчанию выключен, чтобы сразу шла прямая трансляция с камеры)
    DEMO_MODE: bool = False

    # Частота отправки телеметрии по WebSocket (Гц)
    TELEMETRY_RATE_HZ: float = 20.0

    # Настройки калибровки пространства карьера (в миллиметрах)
    QUARRY_DEFAULT_WIDTH_MM: float = 2000.0   # 2 метра
    QUARRY_DEFAULT_LENGTH_MM: float = 3000.0  # 3 метра
    QUARRY_DEFAULT_DEPTH_MM: float = 500.0    # 0.5 метра глубина


# Создание синглтона настроек
settings = Settings()
logger.info("Конфигурация системы успешно загружена. Режим DEMO_MODE: %s", settings.DEMO_MODE)
