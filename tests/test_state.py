"""
Модульные тесты для менеджера состояний карьера и детектора ArUco.
"""

import cv2
import numpy as np

from ai.aruco_detector import ArucoDetector
from core.models import DetectionSource
from core.state_manager import quarry_manager


def test_quarry_manager_initialization():
    """Проверка, что карьер по умолчанию загружен и доступен."""
    quarries = quarry_manager.list_quarries()
    assert len(quarries) >= 1
    assert any(q["id"] == "lab_model_1" for q in quarries)


def test_quarry_state_update():
    """Проверка обновления положения техники через фильтр Калмана."""
    q = quarry_manager.get_quarry("lab_model_1")
    assert q is not None

    state = q.update_vehicle_position(
        vehicle_id="truck_01",
        raw_x=550.0,
        raw_y=420.0,
        raw_z=30.0,
        yaw=45.0,
        source=DetectionSource.ARUCO
    )

    assert state is not None
    assert state.id == "truck_01"
    assert state.position.x > 0.0
    assert state.position.y > 0.0
    assert state.rotation.yaw == 45.0


def test_aruco_detector_detection():
    """Проверка обнаружения сгенерированного маркера ArUco."""
    detector = ArucoDetector()
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    # Генерируем тестовый кадр с маркером ID 0
    marker = cv2.aruco.generateImageMarker(aruco_dict, 0, 100)
    frame = np.full((400, 400, 3), 200, dtype=np.uint8)
    frame[150:250, 150:250] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)

    results = detector.detect(frame)
    assert len(results) == 1
    assert results[0].object_id == "marker_0"
    assert results[0].confidence > 0.9
