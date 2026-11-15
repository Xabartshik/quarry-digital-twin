"""
Модуль фильтрации и комплексирования данных (Sensor Fusion).
Реализует трехмерный фильтр Калмана (Constant Velocity Model)
для сглаживания координат X, Y, Z, устранения шумов и расчета мгновенной скорости.
"""

import logging

import numpy as np

logger = logging.getLogger("KalmanFilter3D")


class VehicleKalmanFilter:
    """
    Трехмерный фильтр Калмана для одной единицы техники.
    Вектор состояния: [x, y, z, vx, vy, vz]^T
    Вектор измерений: [x, y, z]^T
    """

    def __init__(self, init_x: float, init_y: float, init_z: float, process_noise: float = 1e-2, measurement_noise: float = 1e-1):
        """
        Инициализация фильтра Калмана для начальной позиции.
        :param init_x, init_y, init_z: начальные координаты в миллиметрах
        :param process_noise: дисперсия шума процесса (динамики машинки)
        :param measurement_noise: дисперсия шума измерений (погрешность камеры)
        """
        # Вектор состояния 6x1: координаты и скорости
        self.state = np.array([[init_x], [init_y], [init_z], [0.0], [0.0], [0.0]], dtype=np.float64)

        # Ковариационная матрица ошибки 6x6
        self.P = np.eye(6, dtype=np.float64) * 100.0

        # Матрица измерений H (3x6) - мы напрямую наблюдаем только x, y, z
        self.H = np.zeros((3, 6), dtype=np.float64)
        self.H[0, 0] = 1.0
        self.H[1, 1] = 1.0
        self.H[2, 2] = 1.0

        # Ковариация шума измерений R (3x3)
        self.R = np.eye(3, dtype=np.float64) * measurement_noise

        # Базовая дисперсия шума процесса
        self.q_noise = process_noise

    def predict(self, dt: float) -> tuple[float, float, float]:
        """
        Этап экстраполяции (прогноза) положения на время dt вперед.
        :param dt: интервал времени в секундах
        :return: спрогнозированные координаты (x, y, z)
        """
        # Матрица перехода состояния F (6x6)
        F = np.eye(6, dtype=np.float64)
        F[0, 3] = dt
        F[1, 4] = dt
        F[2, 5] = dt

        # Матрица шума процесса Q (6x6)
        # Шум воздействует на ускорение
        G = np.array([
            [0.5 * dt**2, 0, 0],
            [0, 0.5 * dt**2, 0],
            [0, 0, 0.5 * dt**2],
            [dt, 0, 0],
            [0, dt, 0],
            [0, 0, dt]
        ], dtype=np.float64)
        Q = G @ (np.eye(3, dtype=np.float64) * self.q_noise) @ G.T

        # Прогноз состояния: x_hat = F * x
        self.state = F @ self.state
        # Прогноз ковариации: P_hat = F * P * F.T + Q
        self.P = F @ self.P @ F.T + Q

        return float(self.state[0, 0]), float(self.state[1, 0]), float(self.state[2, 0])

    def update(self, measured_x: float, measured_y: float, measured_z: float) -> tuple[float, float, float, float]:
        """
        Этап коррекции состояния по новому измерению от камеры или радиометки.
        :param measured_x, measured_y, measured_z: координаты из детектора
        :return: (filtered_x, filtered_y, filtered_z, calculated_speed)
        """
        z = np.array([[measured_x], [measured_y], [measured_z]], dtype=np.float64)

        # Невязка измерения: y = z - H * x
        y = z - (self.H @ self.state)

        # Ковариация невязки: S = H * P * H.T + R
        S = self.H @ self.P @ self.H.T + self.R

        # Коэффициент усиления Калмана: K = P * H.T * inv(S)
        K = self.P @ self.H.T @ np.linalg.inv(S)

        # Обновление вектора состояния: x = x + K * y
        self.state = self.state + (K @ y)

        # Обновление матрицы ковариации: P = (I - K * H) * P
        I = np.eye(6, dtype=np.float64)
        self.P = (I - K @ self.H) @ self.P

        filtered_x = float(self.state[0, 0])
        filtered_y = float(self.state[1, 0])
        filtered_z = float(self.state[2, 0])

        vx = float(self.state[3, 0])
        vy = float(self.state[4, 0])
        vz = float(self.state[5, 0])

        # Полная пространственная скорость (мм/с)
        speed = float(np.sqrt(vx**2 + vy**2 + vz**2))

        # Порог зоны нечувствительности (Deadband Threshold):
        # Оптический шум пикселей камеры при неподвижном маркере составляет 0.2-1.2 мм/с.
        # Если скорость ниже 1.5 мм/с, объект считается строго неподвижным в покое.
        if speed < 1.5:
            speed = 0.0
            self.state[3, 0] = 0.0
            self.state[4, 0] = 0.0
            self.state[5, 0] = 0.0

        return filtered_x, filtered_y, filtered_z, speed
