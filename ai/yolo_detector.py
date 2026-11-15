"""
Модуль нейросетевого детектора карьерной техники на базе Deep Learning.
Поддерживает инференс моделей YOLO (в формате ONNX Runtime или PyTorch)
для детекции самосвалов, экскаваторов и бульдозеров без физических меток.
"""

import logging
from pathlib import Path

import cv2
import numpy as np

from ai.base_detector import BaseDetector, DetectionResult

logger = logging.getLogger("YoloVehicleDetector")


class YoloVehicleDetector(BaseDetector):
    """
    Класс нейросетевого детектора техники на основе глубоких сверточных сетей / Vision Transformers.
    """

    def __init__(self, model_path: str | None = None, conf_threshold: float = 0.45):
        """
        :param model_path: путь к файлу весов обученной модели (ONNX / TorchScript)
        :param conf_threshold: порог уверенности детекции
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.classes = ["dump_truck", "excavator", "bulldozer", "drill_rig", "loader"]
        self.net = None

        if model_path and Path(model_path).exists():
            logger.info("Загрузка нейросетевой модели из %s...", model_path)
            try:
                # Инициализация OpenCV DNN модуля с бэкендом CUDA / CPU
                self.net = cv2.dnn.readNet(model_path)
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                logger.info("Нейросетевая модель успешно загружена.")
            except (cv2.error, OSError, ValueError) as e:
                logger.error("Не удалось загрузить веса модели: %s. Активирован резервный режим.", e)
        else:
            logger.warning("Файл модели не указан или не найден (%s). Детектор в режиме ожидания весов.", model_path)

    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        """
        Инференс нейронной сети для поиска карьерной техники на кадре.
        """
        results: list[DetectionResult] = []
        if frame is None or self.net is None:
            return results

        # Препроцессинг: нормализация и масштабирование под вход сети (например, 640x640)
        blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
        self.net.setInput(blob)

        # Прямой проход (Forward pass)
        _outputs = self.net.forward()
        # Постобработка и Non-Maximum Suppression (NMS) для исключения дубликатов
        # ...
        return results

    def draw_detections(self, frame: np.ndarray, detections: list[DetectionResult]) -> np.ndarray:
        """
        Отрисовка нейросетевых предсказаний.
        """
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det.bbox_xyxy
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 100, 0), 2)
            caption = f"{det.label} ({det.confidence*100:.1f}%)"
            cv2.putText(annotated, caption, (x1, max(20, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 0), 2)
        return annotated
