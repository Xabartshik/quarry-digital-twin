/**
 * Клиентский модуль интерфейса цифрового двойника карьера.
 * Обрабатывает WebSocket телеметрию, отрисовывает 2D/3D проекцию карьера
 * и машинки в координатном пространстве (X, Y, Z).
 */

const canvas = document.getElementById("quarry-canvas");
const ctx = canvas.getContext("2d");

const wsStatusDot = document.getElementById("ws-status-dot");
const wsStatusText = document.getElementById("ws-status-text");
const activeVehiclesCountEl = document.getElementById("active-vehicles-count");
const telemetryTableBody = document.getElementById("telemetry-table-body");
const quarrySelect = document.getElementById("quarry-select");
const quarryDimsEl = document.getElementById("quarry-dims");

// Параметры текущего карьера (в мм)
let quarryWidthMm = 2000.0;
let quarryLengthMm = 3000.0;
let quarryDepthMm = 500.0;

let currentQuarryId = "lab_model_1";
let socket = null;

// Хранилище истории траекторий для отрисовки шлейфа: vehicleId -> Array<{x, y}>
const trajectoryHistory = {};
const MAX_TRAIL_POINTS = 30;

// Цвета для разных единиц техники
const vehicleColors = {
    "marker_0": "#38bdf8", // Самосвал (голубой)
    "marker_1": "#22c55e", // Экскаватор (зеленый)
    "truck_01": "#f59e0b", // Оранжевый
    "default": "#e2e8f0"
};

/**
 * Инициализация WebSocket соединения с сервером.
 */
function initWebSocket(quarryId) {
    if (socket) {
        socket.close();
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry/${quarryId}`;

    wsStatusText.textContent = "Подключение...";
    wsStatusDot.className = "status-dot disconnected";

    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log(`[WS] Успешно подключено к карьеру: ${quarryId}`);
        wsStatusText.textContent = "В сети (Онлайн)";
        wsStatusDot.className = "status-dot connected";
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleTelemetry(data);
        } catch (e) {
            console.error("Ошибка парсинга телеметрии:", e);
        }
    };

    socket.onclose = () => {
        console.warn("[WS] Соединение разорвано. Повторное подключение через 2с...");
        wsStatusText.textContent = "Отключено (Повтор...)";
        wsStatusDot.className = "status-dot disconnected";
        setTimeout(() => initWebSocket(currentQuarryId), 2000);
    };

    socket.onerror = (err) => {
        console.error("[WS] Ошибка сокета:", err);
    };
}

/**
 * Обработка пакета телеметрии.
 */
function handleTelemetry(data) {
    const vehicles = data.vehicles || [];
    activeVehiclesCountEl.textContent = `Техники на макете: ${vehicles.length}`;

    // Обновляем историю перемещений
    vehicles.forEach(v => {
        if (!trajectoryHistory[v.id]) {
            trajectoryHistory[v.id] = [];
        }
        trajectoryHistory[v.id].push({ x: v.position.x, y: v.position.y });
        if (trajectoryHistory[v.id].length > MAX_TRAIL_POINTS) {
            trajectoryHistory[v.id].shift();
        }
    });

    // Перерисовываем координатное пространство
    drawQuarrySpace(vehicles);

    // Обновляем сводную таблицу
    updateTable(vehicles);
}

/**
 * Отрисовка координатного пространства карьера и машинок на Canvas.
 */
function drawQuarrySpace(vehicles) {
    const w = canvas.width;
    const h = canvas.height;

    // Очистка холста
    ctx.fillStyle = "#0c1222";
    ctx.fillRect(0, 0, w, h);

    // Масштабирование: из миллиметров макета в пиксели Canvas
    const scaleX = w / quarryLengthMm;
    const scaleY = h / quarryWidthMm;

    // 1. Отрисовка координатной сетки (шаг 500 мм)
    ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
    ctx.lineWidth = 1;

    for (let x = 0; x <= quarryLengthMm; x += 500) {
        const px = x * scaleX;
        ctx.beginPath();
        ctx.moveTo(px, 0);
        ctx.lineTo(px, h);
        ctx.stroke();

        ctx.fillStyle = "rgba(255, 255, 255, 0.2)";
        ctx.font = "10px sans-serif";
        ctx.fillText(`${x} мм`, px + 4, 15);
    }

    for (let y = 0; y <= quarryWidthMm; y += 500) {
        const py = y * scaleY;
        ctx.beginPath();
        ctx.moveTo(0, py);
        ctx.lineTo(w, py);
        ctx.stroke();

        ctx.fillStyle = "rgba(255, 255, 255, 0.2)";
        ctx.font = "10px sans-serif";
        ctx.fillText(`${y} мм`, 4, py - 4);
    }

    // 2. Отрисовка контуров уступов карьера (эллипсы террас)
    const cx = w / 2;
    const cy = h / 2;
    ctx.lineWidth = 1.5;
    for (let i = 4; i >= 1; i--) {
        ctx.strokeStyle = `rgba(56, 189, 248, ${0.1 + i * 0.05})`;
        ctx.beginPath();
        ctx.ellipse(cx, cy, (w * 0.11 * i), (h * 0.11 * i), 0, 0, 2 * Math.PI);
        ctx.stroke();

        ctx.fillStyle = "rgba(56, 189, 248, 0.3)";
        ctx.fillText(`Горизонт -${(5 - i) * 100}мм`, cx + (w * 0.11 * i) - 70, cy - 5);
    }

    // 3. Отрисовка шлейфов траекторий
    for (const [vId, points] of Object.entries(trajectoryHistory)) {
        if (points.length < 2) continue;
        const color = vehicleColors[vId] || vehicleColors.default;

        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.3;
        ctx.beginPath();
        ctx.moveTo(points[0].x * scaleX, points[0].y * scaleY);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i].x * scaleX, points[i].y * scaleY);
        }
        ctx.stroke();
        ctx.globalAlpha = 1.0;
    }

    // 4. Отрисовка машинок
    vehicles.forEach(v => {
        const px = v.position.x * scaleX;
        const py = v.position.y * scaleY;
        const color = vehicleColors[v.id] || vehicleColors.default;
        const isVisible = v.is_visible !== false;

        // Если объект вне поля зрения камеры (повернули камеру), делаем его полупрозрачным
        ctx.save();
        if (!isVisible) {
            ctx.globalAlpha = 0.45;
        }

        // Внешнее кольцо подсветки
        ctx.beginPath();
        ctx.arc(px, py, 14, 0, 2 * Math.PI);
        ctx.fillStyle = isVisible ? "rgba(255, 255, 255, 0.08)" : "rgba(255, 255, 255, 0.02)";
        ctx.fill();

        // Точка-маркер машинки
        ctx.beginPath();
        ctx.arc(px, py, 8, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = isVisible ? "#ffffff" : "#94a3b8";
        ctx.lineWidth = 2;
        ctx.stroke();

        // Отрисовка вектора направления движения (Yaw)
        const yawRad = (v.rotation.yaw * Math.PI) / 180.0;
        const arrowLen = 22;
        const endX = px + arrowLen * Math.cos(yawRad);
        const endY = py + arrowLen * Math.sin(yawRad);

        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(endX, endY);
        ctx.strokeStyle = isVisible ? "#ffffff" : "#94a3b8";
        ctx.lineWidth = 2.5;
        ctx.stroke();

        // Подпись с координатами (X, Y, Z) и статусом видимости
        ctx.fillStyle = isVisible ? "#ffffff" : "#94a3b8";
        ctx.font = "bold 11px sans-serif";
        const statusBadge = isVisible ? "" : " [В памяти]";
        ctx.fillText(`${v.name}${statusBadge}`, px + 14, py - 4);

        ctx.fillStyle = "var(--text-secondary)";
        ctx.font = "10px sans-serif";
        ctx.fillText(`X:${v.position.x.toFixed(0)} Y:${v.position.y.toFixed(0)} Z:${v.position.z.toFixed(0)} мм`, px + 14, py + 10);
        ctx.restore();
    });
}

/**
 * Обновление таблицы с параметрами техники.
 */
function updateTable(vehicles) {
    if (vehicles.length === 0) {
        telemetryTableBody.innerHTML = `<tr><td colspan="10" class="no-data">Техника не обнаружена на макете</td></tr>`;
        return;
    }

    telemetryTableBody.innerHTML = vehicles.map(v => {
        const isVis = v.is_visible !== false;
        const statusText = isVis ? "В поле зрения" : "В памяти (скрыт)";
        const statusColor = isVis ? "var(--accent-green)" : "var(--text-secondary)";

        return `
        <tr style="${isVis ? '' : 'opacity: 0.65;'}">
            <td><strong>${v.id}</strong></td>
            <td>${v.name}</td>
            <td><span class="badge">${v.vehicle_type}</span></td>
            <td>${v.position.x.toFixed(1)}</td>
            <td>${v.position.y.toFixed(1)}</td>
            <td>${v.position.z.toFixed(1)}</td>
            <td>${v.rotation.yaw.toFixed(1)}°</td>
            <td>${v.speed_mm_s.toFixed(1)}</td>
            <td style="color:${statusColor}; font-weight:500;">${statusText}</td>
            <td>${(v.confidence * 100).toFixed(0)}%</td>
        </tr>
    `;
    }).join("");
}

const cameraSelect = document.getElementById("camera-select");
const btnCustomCamera = document.getElementById("btn-custom-camera");

/**
 * Загрузка доступных камер и источников с бэкенда.
 */
async function loadAvailableCameras() {
    try {
        const res = await fetch("/api/cameras");
        if (!res.ok) return;
        const data = await res.json();

        cameraSelect.innerHTML = "";

        // Опция симулятора DEMO
        const demoOpt = document.createElement("option");
        demoOpt.value = "demo";
        demoOpt.textContent = "Виртуальный симулятор (DEMO)";
        if (data.is_demo_mode) demoOpt.selected = true;
        cameraSelect.appendChild(demoOpt);

        // Опция Android телефона через scrcpy по USB кабелю (без приложений)
        const scrcpyOpt = document.createElement("option");
        scrcpyOpt.value = "scrcpy";
        scrcpyOpt.textContent = "📱 Камера Android смартфона (по USB через scrcpy)";
        if (!data.is_demo_mode && data.current_source === "scrcpy") {
            scrcpyOpt.selected = true;
        }
        cameraSelect.appendChild(scrcpyOpt);

        // Физически обнаруженные USB-камеры
        if (data.usb_cameras && data.usb_cameras.length > 0) {
            data.usb_cameras.forEach(cam => {
                const opt = document.createElement("option");
                opt.value = cam.id;
                opt.textContent = cam.name;
                if (!data.is_demo_mode && data.current_source === cam.id) {
                    opt.selected = true;
                }
                cameraSelect.appendChild(opt);
            });
        }

        // Если текущий источник - произвольный URL (RTSP или видеофайл)
        if (!data.is_demo_mode && typeof data.current_source === "string") {
            const customOpt = document.createElement("option");
            customOpt.value = data.current_source;
            customOpt.textContent = `Поток: ${data.current_source}`;
            customOpt.selected = true;
            cameraSelect.appendChild(customOpt);
        }
    } catch (err) {
        console.error("Ошибка загрузки списка камер:", err);
    }
}

/**
 * Обработчик переключения камеры из выпадающего списка.
 */
cameraSelect.addEventListener("change", async () => {
    const val = cameraSelect.value;
    const payload = (val === "demo") ? { demo_mode: true } : { source: val, demo_mode: false };

    try {
        await fetch("/api/cameras/select", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        console.log("Камера переключена на:", val);

        // Перезапускаем MJPEG видеопоток в браузере, чтобы обновить картинку
        const videoEl = document.getElementById("video-stream");
        if (videoEl) {
            videoEl.src = "/video_feed?t=" + new Date().getTime();
        }
    } catch (err) {
        console.error("Ошибка переключения камеры:", err);
    }
});

/**
 * Кнопка для ручного ввода RTSP / HTTP URL камеры (смартфон, дрон, IP-камера).
 */
btnCustomCamera.addEventListener("click", async () => {
    const url = prompt("Введите RTSP, HTTP URL потока или индекс камеры (например: 0, http://192.168.1.50:4747/video или rtsp://...):");
    if (!url) return;

    try {
        await fetch("/api/cameras/select", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ source: url, demo_mode: false })
        });
        await loadAvailableCameras();
    } catch (err) {
        alert("Ошибка подключения к камере: " + err);
    }
});

// Запуск при загрузке страницы
document.addEventListener("DOMContentLoaded", () => {
    initWebSocket(currentQuarryId);
    loadAvailableCameras();
});
