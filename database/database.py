"""
Модуль инициализации реляционной базы данных SQLAlchemy.
Обеспечивает подключение, создание таблиц и управление сессиями.
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import settings

logger = logging.getLogger("Database")

# Базовый класс для декларативных ORM-моделей
Base = declarative_base()

# Создание движка базы данных
engine = create_engine(
    settings.DB_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DB_URL else {},
    echo=False
)

# Фабрика сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """
    Инициализирует базу данных: создает все таблицы, если они отсутствуют.
    """
    try:
        logger.info("Инициализация таблиц базы данных...")
        Base.metadata.create_all(bind=engine)
        logger.info("Таблицы базы данных успешно инициализированы.")
    except Exception as e:
        logger.exception("Ошибка при инициализации базы данных: %s", e)
        raise


def get_db():
    """
    Генератор сессии для внедрения зависимостей в FastAPI эндпоинтах.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
