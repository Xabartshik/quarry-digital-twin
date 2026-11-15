"""
Базовый абстрактный класс для всех детекторов техники и объектов карьера.
Обеспечивает единый контракт для нейросетевых моделей (YOLO, Faster R-CNN),
оптических маркеров (ArUco, ChArUco) и радио-локационных датчиков.
"""

from abc import ABC, abstractmethod

import numpy as np
from pydantic import BaseModel


class DetectionResult(BaseModel):
    """
    Унифицированный результат детекции одного объекта на кадре.
    """
    object_id: str                      # Распознанный ID объекта или метки
    label: str                          # Класс объекта (dump_truck, excavator, marker)
    confidence: float                   # Оценка уверенности модели (0.0 - 1.0)
    
    # Координаты на 2D-изображении кадра (в пикселях)
    bbox_xyxy: tuple[int, int, int, int] # [x_min, y_min, x_max, y_max]
    center_px: tuple[int, int]          # Центр объекта на кадре
    
    # 3D-координаты в пространстве макета карьера (в миллиметрах)
    pos_3d_mm: tuple[float, float, float] # (X, Y, Z)
    yaw_deg: float                      # Угол курса / ориентации (градусы)


class BaseDetector(ABC):
    """
    Абстрактный интерфейс детектора техники.
    """

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        """
        Метод обработки одного кадра изображения.
        :param frame: трехканальное BGR изображение (numpy array)
        :return: список обнаруженных объектов
        """

    @abstractmethod
    def draw_detections(self, frame: np.ndarray, detections: list[DetectionResult]) -> np.ndarray:
        """
        Отрисовка результатов распознавания на кадре для видеопотока оператора.
        """
