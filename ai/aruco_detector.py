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
    Класс оптического детектора меток ArUco.
    """

    def __init__(self, marker_size_mm: float = 40.0,
                 quarry_width_mm: float = 2000.0,
                 quarry_length_mm: float = 3000.0,
                 quarry_depth_mm: float = 500.0):
        """
        :param marker_size_mm: физический размер стороны маркера на крыше машинки (в мм)
        :param quarry_width_mm, quarry_length_mm, quarry_depth_mm: размеры макета карьера
        """
        self.marker_size_mm = marker_size_mm
        self.quarry_width_mm = quarry_width_mm
        self.quarry_length_mm = quarry_length_mm
        self.quarry_depth_mm = quarry_depth_mm

        # Инициализация словаря ArUco маркеров (DICT_4X4_50 или DICT_6X6_50)
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)

        logger.info("Инициализирован ArUco детектор (размер метки: %.1f мм)", marker_size_mm)

    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        """
        Обнаруживает маркеры ArUco на кадре и рассчитывает координаты.
        """
        results: list[DetectionResult] = []
        if frame is None or frame.size == 0:
            return results

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected = self.detector.detectMarkers(gray)

        if ids is None or len(ids) == 0:
            return results

        h, w = frame.shape[:2]

        for i, marker_id in enumerate(ids.flatten()):
            c = corners[i][0]  # 4 угла маркера [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]

            # Координаты центра маркера на пиксельной сетке кадра
            center_x = int(np.mean(c[:, 0]))
            center_y = int(np.mean(c[:, 1]))

            # Ограничивающий прямоугольник (bounding box)
            x_min, y_min = int(np.min(c[:, 0])), int(np.min(c[:, 1]))
            x_max, y_max = int(np.max(c[:, 0])), int(np.max(c[:, 1]))

            # Вычисление угла поворота маркера (угол между верхними точками c[0] и c[1])
            dx = c[1][0] - c[0][0]
            dy = c[1][1] - c[0][1]
            yaw_deg = float(np.degrees(np.arctan2(dy, dx)))

            # Масштабирование пиксельных координат в координаты пространства карьера (мм)
            # При съемке сверху: X вдоль длины, Y вдоль ширины
            pos_x_mm = float((center_x / max(1, w)) * self.quarry_length_mm)
            pos_y_mm = float((center_y / max(1, h)) * self.quarry_width_mm)

            # Вычисление псевдо-высоты (Z) по размеру маркера в пикселях:
            # чем ближе машинка к верхней камере (выше на уступе), тем маркер крупнее
            marker_px_size = np.linalg.norm(c[1] - c[0])
            expected_px = 60.0  # эталонный размер на дне карьера
            # Смещение по Z (высота уступа от дна карьера)
            pos_z_mm = float(max(0.0, min(self.quarry_depth_mm, (marker_px_size - expected_px) * 8.0)))

            results.append(DetectionResult(
                object_id=f"marker_{marker_id}",
                label=f"Машинка #{marker_id}",
                confidence=0.98,
                bbox_xyxy=(x_min, y_min, x_max, y_max),
                center_px=(center_x, center_y),
                pos_3d_mm=(round(pos_x_mm, 1), round(pos_y_mm, 1), round(pos_z_mm, 1)),
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
