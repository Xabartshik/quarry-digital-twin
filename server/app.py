"""
Главное FastAPI приложение сервера цифрового двойника карьера.
Объединяет:
- Видеозахват с камеры макета
- Модули машинного зрения и распознавания техники
- Серверную синхронизацию состояния (State Manager)
- WebSocket-трансляцию телеметрии и MJPEG-видеопоток
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ai.aruco_detector import ArucoDetector
from config.settings import settings
from core.models import DetectionSource
from core.state_manager import quarry_manager
from database.database import init_db
from server.websocket_manager import ws_manager
from vision.camera_stream import VideoCameraStream

logger = logging.getLogger("QuarryTwinServer")

# Инициализация глобального видеопотока и детектора
camera_stream = VideoCameraStream(source=settings.CAMERA_SOURCE, demo_mode=settings.DEMO_MODE)
aruco_detector = ArucoDetector(
    marker_size_mm=48.0,
    quarry_width_mm=settings.QUARRY_DEFAULT_WIDTH_MM,
    quarry_length_mm=settings.QUARRY_DEFAULT_LENGTH_MM,
    quarry_depth_mm=settings.QUARRY_DEFAULT_DEPTH_MM
)

# Переменная для хранения последнего размеченного кадра (для MJPEG стрима)
latest_annotated_frame = None


async def cv_processing_and_broadcast_loop():
    """
    Основной асинхронный цикл обработки машинного зрения и рассылки телеметрии.
    """
    global latest_annotated_frame
    logger.info("Запущен основной конвейер компьютерного зрения и вещания телеметрии.")

    # По умолчанию работаем с базовым карьером 'lab_model_1'
    target_quarry_id = "lab_model_1"
    quarry_state = quarry_manager.get_quarry(target_quarry_id)

    db_save_timer = time.time()
    sleep_interval = 1.0 / settings.TELEMETRY_RATE_HZ

    while True:
        try:
            start_t = time.time()
            frame = camera_stream.get_latest_frame()

            if frame is not None and quarry_state is not None:
                # 1. Детекция техники на кадре (ArUco маркеры / нейросеть)
                detections = aruco_detector.detect(frame)

                # 2. Обновление состояния в менеджере карьера (прогон через фильтр Калмана)
                for det in detections:
                    quarry_state.update_vehicle_position(
                        vehicle_id=det.object_id,
                        raw_x=det.pos_3d_mm[0],
                        raw_y=det.pos_3d_mm[1],
                        raw_z=det.pos_3d_mm[2],
                        yaw=det.yaw_deg,
                        source=DetectionSource.ARUCO,
                        confidence=det.confidence
                    )

                # Проверка объектов, вышедших из поля зрения камеры (поворот камеры)
                quarry_state.update_visibility_decay(max_visible_age_s=0.8)

                # 3. Отрисовка рамок и подписей для видеопотока
                annotated = aruco_detector.draw_detections(frame, detections)
                latest_annotated_frame = annotated

                # 4. Формирование пакета телеметрии для отправки по WebSocket
                vehicles = quarry_state.get_all_vehicles()
                telemetry_payload = {
                    "quarry_id": target_quarry_id,
                    "timestamp": time.time(),
                    "vehicles": [v.model_dump(mode="json") for v in vehicles]
                }

                # 5. Рассылка клиентам
                await ws_manager.broadcast_to_quarry(target_quarry_id, telemetry_payload)

                # 6. Периодическое сохранение среза в БД (каждые 3 секунды)
                if time.time() - db_save_timer > 3.0:
                    quarry_manager.save_telemetry_batch(target_quarry_id)
                    db_save_timer = time.time()

            elapsed = time.time() - start_t
            await asyncio.sleep(max(0.005, sleep_interval - elapsed))

        except Exception as e:
            logger.exception("Ошибка в конвейере машинного зрения: %s", e)
            await asyncio.sleep(0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения: инициализация ресурсов при старте и очистка при выходе."""
    logger.info("Запуск серверной платформы Цифровой Двойник Карьера...")
    init_db()
    camera_stream.start()

    # Запуск фонового конвейера компьютерного зрения
    cv_task = asyncio.create_task(cv_processing_and_broadcast_loop())

    yield

    logger.info("Остановка серверной платформы...")
    cv_task.cancel()
    camera_stream.stop()


# Создание экземпляра FastAPI
app = FastAPI(
    title="Цифровой Двойник Карьера - Платформа мониторинга",
    description="API и ядро трекинга техники на макете карьера с использованием компьютерного зрения и ИИ",
    version="1.0.0",
    lifespan=lifespan
)

# Подключение статических файлов веб-интерфейса
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
WEB_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Отдает главную страницу панели диспетчера."""
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Интерфейс цифрового двойника загружается...</h1>")


@app.get("/api/quarries")
async def get_quarries():
    """Возвращает список всех зарегистрированных карьеров (мульти-объектность)."""
    return quarry_manager.list_quarries()


@app.get("/api/quarries/{quarry_id}/vehicles")
async def get_vehicles(quarry_id: str):
    """Возвращает список техники конкретного карьера."""
    q = quarry_manager.get_quarry(quarry_id)
    if not q:
        return {"error": "Карьер не найден"}
    return [v.model_dump() for v in q.get_all_vehicles()]


@app.get("/api/cameras")
async def get_cameras():
    """
    Возвращает список доступных видеоисточников:
    - Обнаруженные подключенные USB-камеры
    - Режим симулятора DEMO
    - Текущий активный источник
    """
    detected_usb = VideoCameraStream.detect_available_cameras(max_tested=4)
    return {
        "current_source": camera_stream.source,
        "is_demo_mode": camera_stream.demo_mode,
        "usb_cameras": detected_usb
    }


@app.post("/api/cameras/select")
async def select_camera(payload: dict):
    """
    Выбирает активный видеоисточник для текущей сессии:
    payload: {"source": 0} или {"source": "rtsp://..."} или {"demo_mode": true}
    """
    demo_mode = payload.get("demo_mode", False)
    source = payload.get("source", 0)

    # Если передан числовой индекс в виде строки
    if isinstance(source, str) and source.isdigit():
        source = int(source)

    camera_stream.set_source(source=source, demo_mode=demo_mode)

    return {
        "status": "success",
        "current_source": camera_stream.source,
        "demo_mode": camera_stream.demo_mode
    }


def generate_mjpeg_stream():
    """Генератор кадров для видеостриминга MJPEG в браузер."""
    global latest_annotated_frame
    while True:
        if latest_annotated_frame is not None:
            ret, buffer = cv2.imencode('.jpg', latest_annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.04)  # ~25 FPS


@app.get("/video_feed")
async def video_feed():
    """Эндпоинт видеопотока с камеры с наложенной разметкой детекции машинок."""
    return StreamingResponse(
        generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.websocket("/ws/telemetry/{quarry_id}")
async def websocket_telemetry_endpoint(websocket: WebSocket, quarry_id: str):
    """
    WebSocket эндпоинт для трансляции 3D-координат (X, Y, Z) техники в реальном времени.
    """
    await ws_manager.connect(websocket, quarry_id)
    try:
        while True:
            # Слушаем сообщения от клиента (например, пинг-понг или команды управления)
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, quarry_id)
    except Exception as e:
        logger.debug("Исключение в WebSocket соединении: %s", e)
        ws_manager.disconnect(websocket, quarry_id)
