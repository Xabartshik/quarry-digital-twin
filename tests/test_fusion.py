"""
Модульные тесты для проверки трехмерного фильтра Калмана (KalmanFilter3D).
Проверяет сглаживание координат, экстраполяцию и расчет скорости.
"""

import numpy as np

from core.fusion import VehicleKalmanFilter


def test_kalman_filter_initialization():
    """Проверка корректной инициализации начального состояния."""
    kf = VehicleKalmanFilter(init_x=100.0, init_y=200.0, init_z=50.0)
    assert kf.state[0, 0] == 100.0
    assert kf.state[1, 0] == 200.0
    assert kf.state[2, 0] == 50.0


def test_kalman_filter_predict_and_update():
    """Проверка сходимости фильтра Калмана при наличии шума измерений."""
    kf = VehicleKalmanFilter(init_x=0.0, init_y=0.0, init_z=0.0)

    # Истинная скорость 100 мм/с по оси X
    true_vx = 100.0
    dt = 0.1

    measured_x = 0.0
    fx, speed = 0.0, 0.0
    for step in range(1, 15):
        kf.predict(dt)
        # Добавляем измерение с искусственным случайным шумом ±5 мм
        noise = np.random.uniform(-5.0, 5.0)
        measured_x = step * true_vx * dt + noise
        fx, _fy, _fz, speed = kf.update(measured_x, 0.0, 0.0)

    # После 15 итераций фильтр должен сгладить координату близко к истинному значению
    expected_x = 15 * true_vx * dt
    assert abs(fx - expected_x) < 15.0
    # Скорость должна быть приблизительно 100 мм/с
    assert 70.0 < speed < 130.0
