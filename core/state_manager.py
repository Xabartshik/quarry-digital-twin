"""
Менеджер состояния цифрового двойника карьера (State Manager).
Отвечает за:
- Реестр карьеров (мульти-объектность).
- Отслеживание активных единиц техники в памяти в реальном времени.
- Прогон измерений через фильтр Калмана.
- Периодический сброс телеметрии в базу данных.
"""

import logging
import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from core.fusion import VehicleKalmanFilter
from core.models import DetectionSource, Rotation3D, Vector3D, VehicleState, VehicleType
from database.database import SessionLocal
from database.models import QuarryModel, TelemetryLogModel, VehicleModel

logger = logging.getLogger("StateManager")


class QuarryStateManager:
    """
    Класс управления состоянием конкретного карьера.
    """

    def __init__(self, quarry_id: str, name: str, width_mm: float, length_mm: float, depth_mm: float):
        self.quarry_id = quarry_id
        self.name = name
        self.width_mm = width_mm
        self.length_mm = length_mm
        self.depth_mm = depth_mm

        # Словарь активных машинок: vehicle_id -> VehicleState
        self.vehicles: dict[str, VehicleState] = {}

        # Словарь фильтров Калмана: vehicle_id -> VehicleKalmanFilter
        self.filters: dict[str, VehicleKalmanFilter] = {}

        # Время последнего обновления объекта для расчета dt
        self.last_update_times: dict[str, float] = {}
        # Время последнего оптического обнаружения камерой
        self.last_seen_times: dict[str, float] = {}

        logger.info("Инициализирован карьер ID='%s' (%s, размер: %.0fx%.0fx%.0f мм)",
                    quarry_id, name, length_mm, width_mm, depth_mm)

    def register_vehicle(self, vehicle_id: str, name: str, v_type: VehicleType,
                         init_x: float = 0.0, init_y: float = 0.0, init_z: float = 0.0) -> VehicleState:
        """Регистрирует новую технику в карьере."""
        initial_state = VehicleState(
            id=vehicle_id,
            quarry_id=self.quarry_id,
            name=name,
            vehicle_type=v_type,
            position=Vector3D(x=init_x, y=init_y, z=init_z),
            rotation=Rotation3D(roll=0.0, pitch=0.0, yaw=0.0),
            speed_mm_s=0.0,
            source=DetectionSource.SIMULATED,
            confidence=1.0,
            last_updated=datetime.now(UTC)
        )
        self.vehicles[vehicle_id] = initial_state
        self.filters[vehicle_id] = VehicleKalmanFilter(init_x, init_y, init_z)
        self.last_update_times[vehicle_id] = time.time()
        logger.info("[%s] Зарегистрирована техника '%s' (ID: %s)", self.quarry_id, name, vehicle_id)
        return initial_state

    def update_vehicle_position(self, vehicle_id: str, raw_x: float, raw_y: float, raw_z: float,
                                yaw: float = 0.0, source: DetectionSource = DetectionSource.ARUCO,
                                confidence: float = 1.0) -> VehicleState | None:
        """
        Обновляет координаты техники, пропуская через фильтр Калмана.
        """
        now = time.time()

        if vehicle_id not in self.vehicles:
            # Автоматическая регистрация нового обнаруженного объекта
            self.register_vehicle(
                vehicle_id=vehicle_id,
                name=f"Машинка-{vehicle_id}",
                v_type=VehicleType.DUMP_TRUCK,
                init_x=raw_x,
                init_y=raw_y,
                init_z=raw_z
            )

        kf = self.filters[vehicle_id]
        last_t = self.last_update_times.get(vehicle_id, now - 0.05)
        dt = max(0.001, now - last_t)
        self.last_update_times[vehicle_id] = now

        # Прогноз по модели динамики
        kf.predict(dt)

        # Коррекция измерением
        fx, fy, fz, speed = kf.update(raw_x, raw_y, raw_z)

        # Обновление состояния
        state = self.vehicles[vehicle_id]
        state.position.x = round(fx, 2)
        state.position.y = round(fy, 2)
        state.position.z = round(fz, 2)
        state.rotation.yaw = round(yaw, 1)
        state.speed_mm_s = round(speed, 2)
        state.source = source
        state.confidence = confidence
        state.is_visible = True
        state.last_updated = datetime.now(UTC)
        self.last_seen_times[vehicle_id] = now

        return state

    def update_visibility_decay(self, max_visible_age_s: float = 1.0):
        """
        Обновляет статус видимости объектов, если камера повернулась в сторону
        и метка перестала попадать в поле зрения. Объект сохраняет свое местоположение
        в цифровом двойнике («память системы»), но помечается как is_visible = False.
        """
        now = time.time()
        for v_id, state in self.vehicles.items():
            last_seen = self.last_seen_times.get(v_id, 0.0)
            if (now - last_seen) > max_visible_age_s:
                state.is_visible = False
                # Скорость объекта, потерянного из вида, затухает до 0 (не улетает по инерции)
                state.speed_mm_s = 0.0

    def get_all_vehicles(self) -> list[VehicleState]:
        """Возвращает список всех активных единиц техники."""
        return list(self.vehicles.values())


class MultiQuarryManager:
    """
    Глобальный менеджер нескольких независимых карьеров.
    Служит точкой входа для всей платформы цифрового двойника.
    """

    def __init__(self):
        self.quarry_instances: dict[str, QuarryStateManager] = {}
        # Гарантируем инициализацию таблиц перед загрузкой
        from database.database import init_db
        init_db()
        self._load_from_db_or_create_default()

    def _load_from_db_or_create_default(self):
        """Загружает карьер из БД или создает дефолтный лабораторный макет."""
        db: Session = SessionLocal()
        try:
            quarries = db.query(QuarryModel).all()
            if not quarries:
                # Создаем базовый карьер (лабораторный макет)
                default_quarry = QuarryModel(
                    id="lab_model_1",
                    name="Лабораторный макет карьера (Горный факультет)",
                    description="Физический макет с треногой и видеокамерой для отслеживания машинок",
                    width_mm=2000.0,
                    length_mm=3000.0,
                    depth_mm=500.0
                )
                db.add(default_quarry)

                # Добавляем две типовые тестовые машинки
                truck1 = VehicleModel(
                    id="truck_01",
                    quarry_id="lab_model_1",
                    name="Самосвал БелАЗ-01",
                    vehicle_type="DUMP_TRUCK",
                    aruco_id=0
                )
                excavator1 = VehicleModel(
                    id="excavator_01",
                    quarry_id="lab_model_1",
                    name="Экскаватор ЭКГ-01",
                    vehicle_type="EXCAVATOR",
                    aruco_id=1
                )
                db.add_all([truck1, excavator1])
                db.commit()
                quarries = [default_quarry]
                logger.info("Создан дефолтный карьер 'lab_model_1' в базе данных.")

            # Инициализируем менеджеры в памяти
            for q in quarries:
                instance = QuarryStateManager(
                    quarry_id=q.id,
                    name=q.name,
                    width_mm=q.width_mm,
                    length_mm=q.length_mm,
                    depth_mm=q.depth_mm
                )
                # Подгружаем технику карьера
                for v in q.vehicles:
                    instance.register_vehicle(
                        vehicle_id=v.id,
                        name=v.name,
                        v_type=VehicleType(v.vehicle_type) if v.vehicle_type in VehicleType.__members__ else VehicleType.DUMP_TRUCK,
                        init_x=500.0,
                        init_y=500.0,
                        init_z=0.0
                    )
                self.quarry_instances[q.id] = instance

        except Exception as e:
            logger.exception("Ошибка при загрузке карьеров из БД: %s", e)
        finally:
            db.close()

    def get_quarry(self, quarry_id: str) -> QuarryStateManager | None:
        """Возвращает менеджер указанного карьера."""
        return self.quarry_instances.get(quarry_id)

    def list_quarries(self) -> list[dict]:
        """Возвращает краткую информацию о всех зарегистрированных карьерах."""
        return [
            {
                "id": q.quarry_id,
                "name": q.name,
                "width_mm": q.width_mm,
                "length_mm": q.length_mm,
                "depth_mm": q.depth_mm,
                "active_vehicles_count": len(q.vehicles)
            }
            for q in self.quarry_instances.values()
        ]

    def save_telemetry_batch(self, quarry_id: str):
        """Сохраняет текущий срез телеметрии техники в историю базы данных."""
        q = self.get_quarry(quarry_id)
        if not q:
            return

        db: Session = SessionLocal()
        try:
            for v in q.get_all_vehicles():
                log_entry = TelemetryLogModel(
                    vehicle_id=v.id,
                    pos_x=v.position.x,
                    pos_y=v.position.y,
                    pos_z=v.position.z,
                    yaw=v.rotation.yaw,
                    speed=v.speed_mm_s,
                    source=v.source.value,
                    confidence=v.confidence
                )
                db.add(log_entry)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error("Ошибка сохранения телеметрии в БД: %s", e)
        finally:
            db.close()


# Глобальный синглтон менеджера карьеров
quarry_manager = MultiQuarryManager()
