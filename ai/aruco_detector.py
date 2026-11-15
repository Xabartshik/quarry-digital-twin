"""
Детектор оптических маркеров ArUco на базе библиотеки OpenCV.
Используется для точного лабораторного трекинга машинок на физическом макете карьера,
калибровки системы координат и высокоточного расчета 3D-положения.
"""

import logging

import cv2
import numpy as np

from ai.base_detector import BaseDetector, DetectionResult

logger = logging.getLogger("ArucoDetector")


class ArucoDetector(BaseDetector):
    """
    Класс оптического детектора меток ArUco с компенсацией высоты камеры (Z-Scaling).
    """

    def __init__(self, marker_size_mm: float = 48.0,
                 quarry_width_mm: float = 2000.0,
                 quarry_length_mm: float = 3000.0,
                 quarry_depth_mm: float = 500.0):
        """
        :param marker_size_mm: физический размер внешнего чёрного контура маркера (в мм)
        :param quarry_width_mm, quarry_length_mm, quarry_depth_mm: размеры макета карьера
        """
        self.marker_size_mm = marker_size_mm
        self.quarry_width_mm = quarry_width_mm
        self.quarry_length_mm = quarry_length_mm
        self.quarry_depth_mm = quarry_depth_mm

        # Инициализация словаря ArUco маркеров (DICT_4X4_50)
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)

        logger.info("Инициализирован ArUco детектор (размер метки: %.1f мм)", marker_size_mm)

    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        """
        Обнаруживает маркеры ArUco на кадре и рассчитывает метрические координаты
        с компенсацией расстояния до камеры (инвариантность масштаба по Z).
        """
        results: list[DetectionResult] = []
        if frame is None or frame.size == 0:
            return results

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _rejected = self.detector.detectMarkers(gray)

        if ids is None or len(ids) == 0:
            return results

        h, w = frame.shape[:2]
        # Центр оптической оси камеры (принципиальная точка)
        cx0 = w / 2.0
        cy0 = h / 2.0
        # Эквивалентное фокусное расстояние стандартной камеры смартфона (в пикселях при угле обзора ~65-70 градусов)
        focal_length = w * 1.15

        for i, marker_id in enumerate(ids.flatten()):
            c = corners[i][0]  # 4 угла маркера [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]

            # Координаты центра маркера на пиксельной сетке кадра
            center_x = float(np.mean(c[:, 0]))
            center_y = float(np.mean(c[:, 1]))

            # Ограничивающий прямоугольник (bounding box)
            x_min, y_min = int(np.min(c[:, 0])), int(np.min(c[:, 1]))
            x_max, y_max = int(np.max(c[:, 0])), int(np.max(c[:, 1]))

            # Вычисление угла поворота маркера (рыскание Yaw)
            dx = c[1][0] - c[0][0]
            dy = c[1][1] - c[0][1]
            yaw_deg = float(np.degrees(np.arctan2(dy, dx)))

            # 1. Оценка видимого размера маркера в пикселях по 4 сторонам квадрата
            side_1 = np.linalg.norm(c[1] - c[0])
            side_2 = np.linalg.norm(c[2] - c[1])
            side_3 = np.linalg.norm(c[3] - c[2])
            side_4 = np.linalg.norm(c[0] - c[3])
            marker_px_size = max(1.0, float((side_1 + side_2 + side_3 + side_4) / 4.0))

            # 2. Вычисление физического расстояния от камеры до плоскости метки (Z в мм)
            # Формула перспективной проекции: Z = (Focal_Length * Real_Size_mm) / Px_Size
            distance_z_mm = (focal_length * self.marker_size_mm) / marker_px_size

            # 3. Метрическая компенсация смещения от центра оптической оси (в миллиметрах)
            # mm_per_px строго пропорционален расстоянию Z: при приближении камеры (Z падает) mm_per_px уменьшается!
            mm_per_px = self.marker_size_mm / marker_px_size
            offset_x_mm = (center_x - cx0) * mm_per_px
            offset_y_mm = (center_y - cy0) * mm_per_px

            # 4. Привязка к глобальной системе координат карьера (центр макета: X=1500 мм, Y=1000 мм)
            pos_x_mm = (self.quarry_length_mm / 2.0) + offset_x_mm
            pos_y_mm = (self.quarry_width_mm / 2.0) + offset_y_mm

            # Ограничение физическими границами карьера
            pos_x_mm = float(max(0.0, min(self.quarry_length_mm, pos_x_mm)))
            pos_y_mm = float(max(0.0, min(self.quarry_width_mm, pos_y_mm)))

            results.append(DetectionResult(
                object_id=f"marker_{marker_id}",
                label=f"Машинка #{marker_id}",
                confidence=0.98,
                bbox_xyxy=(x_min, y_min, x_max, y_max),
                center_px=(int(center_x), int(center_y)),
                pos_3d_mm=(round(pos_x_mm, 1), round(pos_y_mm, 1), round(distance_z_mm, 1)),
                yaw_deg=round(yaw_deg, 1)
            ))

        return results

    def draw_detections(self, frame: np.ndarray, detections: list[DetectionResult]) -> np.ndarray:
        """
        Отрисовывает контуры, центр и подписи координат на видеокадре.
        """
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det.bbox_xyxy
            cx, cy = det.center_px

            # Зеленая рамка вокруг распознанного объекта
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # Красная точка в центре
            cv2.circle(annotated, (cx, cy), 4, (0, 0, 255), -1)

            # Подпись с ID и 3D координатами
            x_mm, y_mm, z_mm = det.pos_3d_mm
            caption = f"{det.label} [X:{x_mm:.0f} Y:{y_mm:.0f} Z:{z_mm:.0f}]"
            cv2.putText(annotated, caption, (x1, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        return annotated
