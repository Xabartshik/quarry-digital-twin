"""
Декларативные ORM-модели базы данных:
- QuarryModel: паспорта карьеров (мульти-объектность).
- VehicleModel: единицы техники, привязанные к конкретному карьеру.
- TelemetryLogModel: исторический лог траекторий и координат для аналитики.
"""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.database import Base


class QuarryModel(Base):
    """
    Таблица карьеров. Позволяет поддерживать неограниченное число независимых карьеров.
    """
    __tablename__ = "quarry_sites"

    id = Column(String(50), primary_key=True, index=True, doc="Уникальный идентификатор карьера")
    name = Column(String(100), nullable=False, doc="Название карьера (например, 'Лабораторный макет №1')")
    description = Column(Text, nullable=True, doc="Дополнительное описание объекта")
    
    # Геометрические габариты рабочего пространства карьера в миллиметрах
    width_mm = Column(Float, nullable=False, default=2000.0, doc="Ширина макета карьера (ось Y)")
    length_mm = Column(Float, nullable=False, default=3000.0, doc="Длина макета карьера (ось X)")
    depth_mm = Column(Float, nullable=False, default=500.0, doc="Глубина макета карьера (ось Z)")
    
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), doc="Дата создания записи")

    # Связи
    vehicles = relationship("VehicleModel", back_populates="quarry", cascade="all, delete-orphan")


class VehicleModel(Base):
    """
    Таблица зарегистрированной карьерной техники.
    """
    __tablename__ = "quarry_vehicles"

    id = Column(String(50), primary_key=True, index=True, doc="Бортовой номер техники")
    quarry_id = Column(String(50), ForeignKey("quarry_sites.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, doc="Наименование техники")
    vehicle_type = Column(String(50), default="DUMP_TRUCK", doc="Тип техники (DUMP_TRUCK, EXCAVATOR)")
    
    # Идентификаторы для систем отслеживания
    aruco_id = Column(Integer, nullable=True, unique=True, doc="ID оптического маркера ArUco на крыше")
    radio_tag_id = Column(String(100), nullable=True, unique=True, doc="ID радиометки / BLE UUID")
    
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Связи
    quarry = relationship("QuarryModel", back_populates="vehicles")
    telemetry_logs = relationship("TelemetryLogModel", back_populates="vehicle", cascade="all, delete-orphan")


class TelemetryLogModel(Base):
    """
    Таблица исторического лога координат перемещения техники.
    """
    __tablename__ = "telemetry_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(String(50), ForeignKey("quarry_vehicles.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    
    # Трехмерные координаты
    pos_x = Column(Float, nullable=False, doc="Координата X (мм)")
    pos_y = Column(Float, nullable=False, doc="Координата Y (мм)")
    pos_z = Column(Float, nullable=False, doc="Координата Z (мм)")
    yaw = Column(Float, default=0.0, doc="Угол поворота курса (градусы)")
    speed = Column(Float, default=0.0, doc="Скорость перемещения (мм/с)")
    
    source = Column(String(50), default="FUSED", doc="Источник координат")
    confidence = Column(Float, default=1.0, doc="Достоверность детекции (0..1)")

    # Связи
    vehicle = relationship("VehicleModel", back_populates="telemetry_logs")
