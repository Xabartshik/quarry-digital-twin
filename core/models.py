"""
Pydantic-модели данных для валидации, сериализации и обмена между модулями.
Определяет форматы 3D-координат, телеметрии техники и состояния карьера.
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class VehicleType(str, Enum):
    """Типы карьерной техники."""
    DUMP_TRUCK = "DUMP_TRUCK"        # Карьерный самосвал (БелАЗ, CAT)
    EXCAVATOR = "EXCAVATOR"          # Карьерный экскаватор
    BULLDOZER = "BULLDOZER"          # Бульдозер
    DRILL_RIG = "DRILL_RIG"          # Буровой станок
    LOADER = "LOADER"                # Фронтальный погрузчик
    GENERIC_VEHICLE = "VEHICLE"      # Общий тип машинки на макете


class DetectionSource(str, Enum):
    """Источник детекции положения объекта."""
    ARUCO = "ARUCO"                  # Оптический маркер ArUco
    AI_YOLO = "AI_YOLO"              # Нейросетевая модель детекции
    RADIO_TAG = "RADIO_TAG"          # Радио-/BLE-метка
    FUSED_KALMAN = "FUSED_KALMAN"    # Комплексированное сглаженное значение
    SIMULATED = "SIMULATED"          # Синтетический генератор


class Vector3D(BaseModel):
    """Трехмерный вектор координат в системе координат карьера (в миллиметрах)."""
    x: float = Field(..., description="Координата X (длина карьера)")
    y: float = Field(..., description="Координата Y (ширина карьера)")
    z: float = Field(..., description="Координата Z (высота / глубина карьера)")


class Rotation3D(BaseModel):
    """Ориентация объекта в пространстве (углы Эйлера в градусах)."""
    roll: float = Field(0.0, description="Крен")
    pitch: float = Field(0.0, description="Тангаж")
    yaw: float = Field(0.0, description="Рыскание / курс направления движения")


class VehicleState(BaseModel):
    """
    Текущее состояние единицы техники в цифровом двойнике.
    """
    id: str = Field(..., description="Уникальный идентификатор техники (бортовой номер)")
    quarry_id: str = Field(..., description="Идентификатор карьера, в котором находится техника")
    name: str = Field(..., description="Отображаемое имя (например, 'БелАЗ-01')")
    vehicle_type: VehicleType = Field(VehicleType.DUMP_TRUCK, description="Тип техники")
    
    # Пространственное положение и динамика
    position: Vector3D = Field(..., description="Координаты X, Y, Z в карьере")
    rotation: Rotation3D = Field(default_factory=Rotation3D, description="Углы поворота")
    speed_mm_s: float = Field(0.0, description="Линейная скорость движения (мм/с)")
    
    # Метаданные обнаружения
    source: DetectionSource = Field(DetectionSource.FUSED_KALMAN, description="Источник координат")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Достоверность определения (0..1)")
    is_visible: bool = Field(True, description="Виден ли объект в текущем кадре камеры")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Время последнего обновления")


class QuarryInfo(BaseModel):
    """Информация о карьере (модуле)."""
    id: str = Field(..., description="Уникальный ID карьера")
    name: str = Field(..., description="Название карьера или макета")
    width_mm: float = Field(..., description="Ширина пространства карьера (мм)")
    length_mm: float = Field(..., description="Длина пространства карьера (мм)")
    depth_mm: float = Field(..., description="Максимальная глубина карьера (мм)")
    description: str | None = Field(None, description="Описание или назначение")


class TelemetryFrame(BaseModel):
    """
    Пакет телеметрии, отправляемый клиентам через WebSocket.
    Включает метку времени, ID карьера и список активных машинок.
    """
    quarry_id: str
    timestamp: float
    vehicles: list[VehicleState]
