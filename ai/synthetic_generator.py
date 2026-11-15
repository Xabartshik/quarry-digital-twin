"""
Модуль синтетического генератора видеопотока и симуляции карьера.
Позволяет тестировать платформу цифрового двойника без подключенной физической камеры:
генерирует виртуальный вид макета карьера сверху с уступами и движущимися машинками
с реальными маркерами ArUco на крышах.
"""

import logging
import math
import time

import cv2
import numpy as np

logger = logging.getLogger("SyntheticGenerator")


class SyntheticQuarrySimulator:
    """
    Симулятор физического макета карьера и движения техники.
    """

    def __init__(self, width_px: int = 1280, height_px: int = 720):
        self.width_px = width_px
        self.height_px = height_px

        # Словарь ArUco маркеров для генерации реальных маркеров на крышах машинок
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

        # Подготовка маркеров для двух машинок (ID: 0 и ID: 1)
        self.marker_0 = cv2.aruco.generateImageMarker(self.aruco_dict, 0, 50)
        self.marker_1 = cv2.aruco.generateImageMarker(self.aruco_dict, 1, 50)

        # Начальное время симуляции
        self.start_time = time.time()
        logger.info("Инициализирован синтетический симулятор макета карьера (%dx%d)", width_px, height_px)

    def generate_frame(self) -> np.ndarray:
        """
        Генерирует один кадр вида сверху на макет карьера.
        """
        t = time.time() - self.start_time

        # Фон: текстура макета карьера (песочно-скальный цвет)
        frame = np.full((self.height_px, self.width_px, 3), (120, 150, 180), dtype=np.uint8)

        # Отрисовка уступов (концентрические овалы карьера)
        center = (self.width_px // 2, self.height_px // 2)
        for i in range(5, 0, -1):
            axes = (int(self.width_px * 0.08 * i), int(self.height_px * 0.08 * i))
            color = (int(80 + i * 15), int(100 + i * 15), int(130 + i * 15))
            cv2.ellipse(frame, center, axes, 0, 0, 360, color, -1)
            cv2.ellipse(frame, center, axes, 0, 0, 360, (70, 70, 70), 2)

        # Траектория машинки №0 (самосвал - курсирует по серпантину)
        radius_x = self.width_px * 0.32
        radius_y = self.height_px * 0.30
        x0 = int(center[0] + radius_x * math.cos(t * 0.4))
        y0 = int(center[1] + radius_y * math.sin(t * 0.4))

        # Траектория машинки №1 (экскаватор / вспомогательная техника - медленно в забое)
        x1 = int(center[0] + 100 * math.cos(t * 0.15))
        y1 = int(center[1] + 60 * math.sin(t * 0.15))

        # Наложение машинки №0 с маркером ArUco
        self._overlay_vehicle(frame, x0, y0, self.marker_0, angle_rad=t * 0.4 + math.pi/2,
                              color=(40, 180, 240), label="Самосвал-01")

        # Наложение машинки №1 с маркером ArUco
        self._overlay_vehicle(frame, x1, y1, self.marker_1, angle_rad=t * 0.15,
                              color=(50, 200, 50), label="Экскаватор-01")

        # Служебная надпись режима симуляции
        cv2.putText(frame, "[SIMULATED CAMERA - DEMO MODE]", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        return frame

    def _overlay_vehicle(self, frame: np.ndarray, cx: int, cy: int, marker_img: np.ndarray,
                         angle_rad: float, color: tuple, label: str):
        """Отрисовывает корпус машинки и накладывает маркер ArUco на её крышу."""
        h, w = frame.shape[:2]
        mw, mh = marker_img.shape[:2]

        # Рисуем корпус машинки (прямоугольник с закруглением)
        body_len = 80
        body_width = 50
        pts = np.array([
            [-body_len // 2, -body_width // 2],
            [body_len // 2, -body_width // 2],
            [body_len // 2, body_width // 2],
            [-body_len // 2, body_width // 2]
        ], dtype=np.float32)

        # Матрица вращения
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        R = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
        rotated_pts = (pts @ R.T) + np.array([cx, cy])
        rotated_pts = rotated_pts.astype(np.int32)

        cv2.fillPoly(frame, [rotated_pts], color)
        cv2.polylines(frame, [rotated_pts], True, (30, 30, 30), 2)

        # Вклеиваем маркер на крышу (в центре)
        x_start = max(0, cx - mw // 2)
        y_start = max(0, cy - mh // 2)
        x_end = min(w, x_start + mw)
        y_end = min(h, y_start + mh)

        if (x_end - x_start) == mw and (y_end - y_start) == mh:
            # Преобразуем одноканальный маркер в трехканальный
            marker_bgr = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)
            frame[y_start:y_end, x_start:x_end] = marker_bgr
