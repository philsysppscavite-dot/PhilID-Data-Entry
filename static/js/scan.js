const scanStatus = document.getElementById("scan-status");
const resultPanel = document.getElementById("result-panel");
const registerModal = document.getElementById("register-modal");
const modalIdNumber = document.getElementById("modal-id-number");
const registerForm = document.getElementById("register-form");
const registerError = document.getElementById("register-error");
const cancelRegisterBtn = document.getElementById("cancel-register");

const provinceSelect = document.getElementById("province");
const citySelect = document.getElementById("city");
const barangaySelect = document.getElementById("barangay");

let pendingIdNumber = null;
let processing = false;
let scanner = null;

function showResultLogged(data) {
    const cls = data.log_type === "IN" ? "in" : "out";
    const icon = data.log_type === "IN" ? "IN" : "OUT";
    resultPanel.innerHTML = `
        <span class="bracket-bl"></span><span class="bracket-br"></span>
        <div class="result-icon ${cls}">${icon}</div>
        <div class="result-name">${data.resident.full_name}</div>
        <div class="result-meta mono">${data.resident.id_number}</div>
        <div class="result-meta">${data.resident.barangay}, ${data.resident.city_municipality}, ${data.resident.province}</div>
        <div class="result-meta mono" style="margin-top:6px;">${data.timestamp}</div>
    `;
}

function showResultError(message) {
    resultPanel.innerHTML = `
        <span class="bracket-bl"></span><span class="bracket-br"></span>
        <div class="eyebrow" style="color: var(--red);">Scan failed</div>
        <p style="color: var(--ink-soft); font-size: 13.5px;">${message}</p>
    `;
}

async function loadProvincesIntoForm() {
    const res = await fetch("/api/provinces");
    const provinces = await res.json();
    provinceSelect.innerHTML =
        `<option value="">Select province...</option>` +
        provinces.map(p => `<option value="${p}">${p}</option>`).join("");
}

provinceSelect.addEventListener("change", async () => {
    citySelect.disabled = true;
    barangaySelect.disabled = true;
    citySelect.innerHTML = `<option value="">Loading...</option>`;
    barangaySelect.innerHTML = `<option value="">Select city/municipality first...</option>`;
    if (!provinceSelect.value) {
        citySelect.innerHTML = `<option value="">Select province first...</option>`;
        return;
    }
    const res = await fetch(`/api/cities?province=${encodeURIComponent(provinceSelect.value)}`);
    const cities = await res.json();
    citySelect.innerHTML =
        `<option value="">Select city/municipality...</option>` +
        cities.map(c => `<option value="${c}">${c}</option>`).join("");
    citySelect.disabled = false;
});

citySelect.addEventListener("change", async () => {
    barangaySelect.disabled = true;
    barangaySelect.innerHTML = `<option value="">Loading...</option>`;
    if (!citySelect.value) {
        barangaySelect.innerHTML = `<option value="">Select city/municipality first...</option>`;
        return;
    }
    const res = await fetch(`/api/barangays?province=${encodeURIComponent(provinceSelect.value)}&city=${encodeURIComponent(citySelect.value)}`);
    const barangays = await res.json();
    barangaySelect.innerHTML =
        `<option value="">Select barangay...</option>` +
        barangays.map(b => `<option value="${b.name}" data-geocode="${b.geocode}">${b.name}</option>`).join("");
    barangaySelect.disabled = false;
});

function openRegisterModal(idNumber) {
    pendingIdNumber = idNumber;
    modalIdNumber.textContent = idNumber;
    registerForm.reset();
    registerError.style.display = "none";
    citySelect.innerHTML = `<option value="">Select province first...</option>`;
    citySelect.disabled = true;
    barangaySelect.innerHTML = `<option value="">Select city/municipality first...</option>`;
    barangaySelect.disabled = true;
    registerModal.style.display = "flex";
}

function closeRegisterModal() {
    registerModal.style.display = "none";
    pendingIdNumber = null;
    resumeScanning();
}

cancelRegisterBtn.addEventListener("click", closeRegisterModal);

registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    registerError.style.display = "none";

    const geocodeOpt = barangaySelect.selectedOptions[0];
    const payload = {
        id_number: pendingIdNumber,
        first_name: document.getElementById("first_name").value.trim(),
        middle_name: document.getElementById("middle_name").value.trim(),
        last_name: document.getElementById("last_name").value.trim(),
        province: provinceSelect.value,
        city_municipality: citySelect.value,
        barangay: barangaySelect.value,
        geocode: geocodeOpt ? geocodeOpt.dataset.geocode : "",
    };

    try {
        const res = await fetch("/api/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Registration failed.");

        registerModal.style.display = "none";
        showResultLogged({ log_type: "IN", resident: data.resident, timestamp: data.timestamp });
        pendingIdNumber = null;
        resumeScanning();
    } catch (err) {
        registerError.textContent = err.message;
        registerError.style.display = "block";
    }
});

async function handleDecodedText(decodedText) {
    if (processing) return;
    processing = true;
    scanStatus.textContent = "Processing scan...";

    try {
        const res = await fetch("/api/scan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_number: decodedText }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Scan failed.");

        if (data.status === "new") {
            pauseScanning();
            loadProvincesIntoForm();
            openRegisterModal(data.id_number);
        } else if (data.status === "logged") {
            showResultLogged(data);
            resumeScanning();
        }
    } catch (err) {
        showResultError(err.message);
        resumeScanning();
    }
}

function pauseScanning() {
    scanStatus.textContent = "Scanner paused";
}

function resumeScanning() {
    processing = false;
    scanStatus.textContent = "Point a QR code at the camera";
}

// ---------- Camera init ----------
function initScanner() {
    scanner = new Html5Qrcode("qr-reader");
    Html5Qrcode.getCameras().then(cameras => {
        if (!cameras || !cameras.length) {
            scanStatus.textContent = "No camera found on this device.";
            return;
        }
        const cameraId = cameras[0].id;
        scanner.start(
            cameraId,
            { fps: 10, qrbox: { width: 250, height: 250 } },
            (decodedText) => handleDecodedText(decodedText),
            () => { /* ignore per-frame decode errors */ }
        );
    }).catch(() => {
        scanStatus.textContent = "Camera access was denied. Please allow camera permissions.";
    });
}

initScanner();
