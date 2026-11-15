"""
Главная точка входа для запуска серверной платформы Цифровой Двойник Карьера.
Запускает асинхронный ASGI веб-сервер Uvicorn с приложением FastAPI.
"""

import logging

import uvicorn

from config.settings import settings

logger = logging.getLogger("Main")


def main():
    """Точка входа запуска системы."""
    print("=" * 70)
    print("  ЦИФРОВОЙ ДВОЙНИК КАРЬЕРА (ВКР)")
    print("  Платформа трекинга техники на базе компьютерного зрения и ИИ")
    print(f"  Веб-интерфейс: http://localhost:{settings.SERVER_PORT}")
    print(f"  Видеопоток:    http://localhost:{settings.SERVER_PORT}/video_feed")
    print(f"  Режим DEMO:    {settings.DEMO_MODE}")
    print("=" * 70)

    uvicorn.run(
        "server.app:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
