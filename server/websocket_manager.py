"""
Менеджер WebSocket-соединений для рассылки телеметрии в реальном времени.
Обеспечивает группировку клиентов по ID карьера.
"""

import json
import logging

from fastapi import WebSocket

logger = logging.getLogger("WebSocketManager")


class ConnectionManager:
    """
    Класс управления активными WebSocket подключениями клиентов.
    """

    def __init__(self):
        # Словарь: quarry_id -> список подключенных WebSocket
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, quarry_id: str):
        """Регистрирует новое клиентское подключение к карьеру."""
        await websocket.accept()
        if quarry_id not in self.active_connections:
            self.active_connections[quarry_id] = []
        self.active_connections[quarry_id].append(websocket)
        logger.info("Подключен клиент WebSocket к карьеру '%s' (всего: %d)",
                    quarry_id, len(self.active_connections[quarry_id]))

    def disconnect(self, websocket: WebSocket, quarry_id: str):
        """Удаляет отключившегося клиента."""
        if quarry_id in self.active_connections:
            if websocket in self.active_connections[quarry_id]:
                self.active_connections[quarry_id].remove(websocket)
                logger.info("Клиент отключился от карьера '%s' (осталось: %d)",
                            quarry_id, len(self.active_connections[quarry_id]))

    async def broadcast_to_quarry(self, quarry_id: str, data: dict):
        """Рассылает пакет данных всем подписчикам данного карьера."""
        if quarry_id not in self.active_connections:
            return

        message_str = json.dumps(data, ensure_ascii=False)
        disconnected = []

        for connection in self.active_connections[quarry_id]:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.debug("Ошибка отправки данных клиенту: %s", e)
                disconnected.append(connection)

        for dead_conn in disconnected:
            self.disconnect(dead_conn, quarry_id)


# Синглтон менеджера соединений
ws_manager = ConnectionManager()
