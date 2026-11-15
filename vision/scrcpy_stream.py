"""
Модуль прямой интеграции со scrcpy для захвата камеры Android смартфона по USB.
Не требует установки сторонних приложений на сам смартфон.
"""

import os
import time
import ctypes
import subprocess
import threading
import logging
from typing import Optional
import numpy as np
import cv2

try:
    import win32gui
    import win32ui
    import win32con
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False

from config.settings import settings

logger = logging.getLogger("ScrcpyCameraCapture")

# Стандартный путь к scrcpy, установленному через winget
DEFAULT_SCRCPY_PATH = r"C:\Users\Xabartshik\AppData\Local\Microsoft\WinGet\Packages\Genymobile.scrcpy_Microsoft.Winget.Source_8wekyb3d8bbwe\scrcpy-win64-v5.0.1\scrcpy.exe"


class ScrcpyCameraStream:
    """
    Класс управления фоновым процессом scrcpy и захватом видеокадров с камеры телефона.
    """

    def __init__(self, camera_id: int = 0, scrcpy_path: Optional[str] = None):
        self.camera_id = camera_id
        self.scrcpy_path = scrcpy_path or DEFAULT_SCRCPY_PATH
        # Человекочитаемый заголовок окна, чтобы пользователь видел его на рабочем столе
        self.window_title = f"Камера смартфона (Цифровой Двойник) #{os.getpid()}"
        
        self.process: Optional[subprocess.Popen] = None
        self.hwnd: Optional[int] = None
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.current_frame: Optional[np.ndarray] = None

    def start(self) -> bool:
        """Запускает процесс scrcpy и захват кадров."""
        if not PYWIN32_AVAILABLE:
            logger.error("Библиотека pywin32 не найдена!")
            return False

        if not os.path.exists(self.scrcpy_path):
            logger.error("Исполняемый файл scrcpy не найден: %s", self.scrcpy_path)
            return False

        # Очищаем старые зависшие процессы scrcpy
        try:
            subprocess.run(["taskkill", "/F", "/IM", "scrcpy.exe"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        except Exception:
            pass

        # Снимаем блокировку камеры встроенным приложением Xiaomi HyperOS/MIUI
        adb_path = os.path.join(os.path.dirname(self.scrcpy_path), "adb.exe")
        if os.path.exists(adb_path):
            try:
                subprocess.run([adb_path, "shell", "am", "force-stop", "com.android.camera"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            except Exception:
                pass

        logger.info("Запуск scrcpy для камеры ID %d (режим software renderer)...", self.camera_id)
        cmd = [
            self.scrcpy_path,
            "--video-source=camera",
            f"--camera-id={self.camera_id}",
            "-m", "1280",
            "--video-codec=h264",
            "--video-encoder=c2.android.avc.encoder",
            "--render-driver=software",
            f"--window-title={self.window_title}",
            "--window-width=640",
            "--window-height=480",
            "--no-audio"
        ]

        try:
            # Запуск процесса в фоновом режиме без всплывающего черного консольного окна
            creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            self.process = subprocess.Popen(
                cmd,
                creationflags=creation_flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.is_running = True
            
            # Ждем появления окна до 10 секунд (30 попыток по 0.35с)
            for _ in range(30):
                time.sleep(0.35)
                # Ищем окно именно класса SDL_app с нашим уникальным заголовком
                self.hwnd = win32gui.FindWindow("SDL_app", self.window_title)
                if not self.hwnd:
                    self.hwnd = win32gui.FindWindow(None, self.window_title)
                if self.hwnd:
                    break

            if not self.hwnd:
                logger.warning("Окно scrcpy не появилось за отведенное время.")
                return False

            self.thread = threading.Thread(target=self._capture_loop, daemon=True, name="ScrcpyCaptureThread")
            self.thread.start()
            logger.info("Захват камеры смартфона через scrcpy успешно запущен!")
            return True

        except Exception as e:
            logger.exception("Ошибка при запуске scrcpy: %s", e)
            self.stop()
            return False

    def _capture_loop(self):
        """Цикл захвата кадров из окна scrcpy."""
        user32 = ctypes.windll.user32

        while self.is_running and self.hwnd:
            try:
                if not win32gui.IsWindow(self.hwnd):
                    break

                left, top, right, bot = win32gui.GetClientRect(self.hwnd)
                w = right - left
                h = bot - top

                if w <= 0 or h <= 0:
                    time.sleep(0.03)
                    continue

                hwndDC = win32gui.GetWindowDC(self.hwnd)
                mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                saveDC = mfcDC.CreateCompatibleDC()
                saveBitMap = win32ui.CreateBitmap()
                saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
                saveDC.SelectObject(saveBitMap)

                # Захват содержимого окна в память (флаг 0 для GDI совместимости)
                user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 0)

                bmpinfo = saveBitMap.GetInfo()
                bmpstr = saveBitMap.GetBitmapBits(True)
                img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4))
                frame_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                # Очистка ресурсов GDI
                win32gui.DeleteObject(saveBitMap.GetHandle())
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(self.hwnd, hwndDC)

                # Записываем и масштабируем кадр под разрешение проекта
                if frame_bgr is not None and frame_bgr.shape[0] > 0 and frame_bgr.shape[1] > 0:
                    frame_resized = cv2.resize(frame_bgr, (settings.FRAME_WIDTH, settings.FRAME_HEIGHT))
                    with self.lock:
                        self.current_frame = frame_resized

                time.sleep(0.03)  # ~30 FPS

            except Exception as e:
                time.sleep(0.05)

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Возвращает последний кадр."""
        with self.lock:
            if self.current_frame is None:
                return None
            return self.current_frame.copy()

    def stop(self):
        """Останавливает процесс."""
        self.is_running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        self.hwnd = None
        logger.info("Scrcpy поток остановлен.")
