"""
Тест интеграции FastAPI: эндпоинты, статика, видеострим и API карьеров.
"""

from fastapi.testclient import TestClient

from server.app import app

client = TestClient(app)


def test_root_endpoint():
    """Проверка доступности веб-интерфейса."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Цифровой Двойник Карьера" in response.text


def test_api_quarries():
    """Проверка REST API списка карьеров."""
    response = client.get("/api/quarries")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == "lab_model_1"


def test_cameras_endpoint():
    """Проверка эндпоинта получения доступных камер."""
    response = client.get("/api/cameras")
    assert response.status_code == 200
    data = response.json()
    assert "current_source" in data
    assert "is_demo_mode" in data
    assert "usb_cameras" in data


def test_select_camera_endpoint():
    """Проверка переключения источника видео."""
    response = client.post("/api/cameras/select", json={"demo_mode": True})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["demo_mode"] is True
