"""
Модуль непрерывного видеозахвата (Camera Streamer).
Осуществляет чтение кадров в фоновом потоке, снижая задержки буферизации OpenCV.
Автоматически переключается между физической веб-камерой и симулятором макета.
"""

import logging
import threading
import time

import cv2
import numpy as np

from ai.synthetic_generator import SyntheticQuarrySimulator
from config.settings import settings
from vision.scrcpy_stream import ScrcpyCameraStream

logger = logging.getLogger("CameraStreamer")


class VideoCameraStream:
    """
    Класс управления видеопотоком с камеры наблюдения или симулятора.
    """

    def __init__(self, source: int | str = 0, demo_mode: bool = True):
        self.source = source
        self.demo_mode = demo_mode
        self.cap: cv2.VideoCapture | None = None
        self.simulator: SyntheticQuarrySimulator | None = None
        self.scrcpy_stream: ScrcpyCameraStream | None = None

        self.current_frame: np.ndarray | None = None
        self.is_running = False
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None

        self._init_source()

    def _init_source(self):
        """Инициализирует источник видеопотока."""
        if self.demo_mode:
            logger.info("Активирован синтетический генератор видеопотока макета карьера.")
            self.simulator = SyntheticQuarrySimulator(
                width_px=settings.FRAME_WIDTH,
                height_px=settings.FRAME_HEIGHT
            )
        elif self.source in ("scrcpy", "android", "usb_phone"):
            logger.info("Подключение к камере телефона через scrcpy по USB...")
            self.scrcpy_stream = ScrcpyCameraStream(camera_id=0)
            if not self.scrcpy_stream.start():
                logger.warning("Не удалось запустить scrcpy. Возврат в DEMO-режим.")
                self.demo_mode = True
                self.simulator = SyntheticQuarrySimulator(
                    width_px=settings.FRAME_WIDTH,
                    height_px=settings.FRAME_HEIGHT
                )
        else:
            logger.info("Попытка подключения к видеоисточнику: %s", self.source)
            self.cap = cv2.VideoCapture(self.source)
            if not self.cap.isOpened():
                logger.warning("Не удалось открыть физическую камеру %s! Переключение в DEMO-режим.", self.source)
                self.demo_mode = True
                self.simulator = SyntheticQuarrySimulator(
                    width_px=settings.FRAME_WIDTH,
                    height_px=settings.FRAME_HEIGHT
                )
            else:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.FRAME_WIDTH)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.FRAME_HEIGHT)
                logger.info("Физическая камера успешно подключена (%dx%d).",
                            settings.FRAME_WIDTH, settings.FRAME_HEIGHT)

    def start(self):
        """Запускает фоновый поток непрерывного захвата кадров."""
        if self.is_running:
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True, name="CameraCaptureThread")
        self.thread.start()
        logger.info("Фоновый поток захвата видео запущен.")

    def _capture_loop(self):
        """Бесконечный цикл чтения кадров с заданной частотой."""
        fps_delay = 1.0 / max(1, settings.CAMERA_FPS)

        while self.is_running:
            start_time = time.time()

            if self.demo_mode and self.simulator:
                frame = self.simulator.generate_frame()
            elif self.scrcpy_stream and self.scrcpy_stream.is_running:
                sc_frame = self.scrcpy_stream.get_latest_frame()
                frame = sc_frame if sc_frame is not None else np.zeros((settings.FRAME_HEIGHT, settings.FRAME_WIDTH, 3), dtype=np.uint8)
            elif self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("Сбой чтения кадра с камеры. Повтор...")
                    time.sleep(0.1)
                    continue
            else:
                frame = np.zeros((settings.FRAME_HEIGHT, settings.FRAME_WIDTH, 3), dtype=np.uint8)

            with self.lock:
                self.current_frame = frame

            elapsed = time.time() - start_time
            sleep_time = max(0.001, fps_delay - elapsed)
            time.sleep(sleep_time)

    def get_latest_frame(self) -> np.ndarray | None:
        """Возвращает последний считанный кадр."""
        with self.lock:
            if self.current_frame is None:
                return None
            return self.current_frame.copy()

    def set_source(self, source: int | str, demo_mode: bool = False):
        """
        Динамическое переключение источника видеопотока без остановки сервера.
        :param source: индекс USB-камеры (0, 1...), RTSP URL, HTTP URL или путь к видеофайлу.
        :param demo_mode: включить синтетический генератор.
        """
        with self.lock:
            logger.info("Смена источника видео: source=%s, demo_mode=%s", source, demo_mode)
            if self.cap and self.cap.isOpened():
                self.cap.release()
                self.cap = None

            if self.scrcpy_stream:
                self.scrcpy_stream.stop()
                self.scrcpy_stream = None

            self.demo_mode = demo_mode
            self.source = source

            if self.demo_mode:
                self.simulator = SyntheticQuarrySimulator(
                    width_px=settings.FRAME_WIDTH,
                    height_px=settings.FRAME_HEIGHT
                )
            elif str(source).lower() in ("scrcpy", "android", "usb_phone"):
                self.simulator = None
                self.scrcpy_stream = ScrcpyCameraStream(camera_id=0)
                if not self.scrcpy_stream.start():
                    logger.warning("Не удалось запустить scrcpy. Возврат в режим DEMO.")
                    self.demo_mode = True
                    self.simulator = SyntheticQuarrySimulator(
                        width_px=settings.FRAME_WIDTH,
                        height_px=settings.FRAME_HEIGHT
                    )
            else:
                self.simulator = None
                # Пробуем открыть источник через VideoCapture
                backend = cv2.CAP_DSHOW if isinstance(source, int) and source >= 0 else cv2.CAP_ANY
                self.cap = cv2.VideoCapture(source, backend) if backend == cv2.CAP_DSHOW else cv2.VideoCapture(source)
                
                if not self.cap.isOpened() and backend == cv2.CAP_DSHOW:
                    # Резервная попытка через стандартный бэкенд
                    self.cap = cv2.VideoCapture(source)

                if self.cap.isOpened():
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.FRAME_WIDTH)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.FRAME_HEIGHT)
                    logger.info("Источник успешно переключен на: %s", source)
                else:
                    logger.warning("Не удалось открыть источник %s. Возврат в режим DEMO.", source)
                    self.demo_mode = True
                    self.simulator = SyntheticQuarrySimulator(
                        width_px=settings.FRAME_WIDTH,
                        height_px=settings.FRAME_HEIGHT
                    )

    @staticmethod
    def detect_available_cameras(max_tested: int = 4) -> list[dict]:
        """
        Сканирует систему на наличие физически подключенных USB-камер.
        """
        available = []
        for index in range(max_tested):
            # Проверяем DirectShow (Windows) и стандартный бэкенд
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(index)

            if cap.isOpened():
                available.append({
                    "id": index,
                    "name": f"USB-камера (Индекс {index})",
                    "type": "usb"
                })
                cap.release()
        return available

    def stop(self):
        """Останавливает поток захвата и освобождает ресурсы."""
        logger.info("Остановка видеозахвата...")
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.scrcpy_stream:
            self.scrcpy_stream.stop()
            self.scrcpy_stream = None
        if self.cap:
            self.cap.release()
        logger.info("Видеозахват остановлен.")
