const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = { qr: document.getElementById("tab-qr"), manual: document.getElementById("tab-manual") };
const resultPanel = document.getElementById("result-panel");
const keywordInput = document.getElementById("keyword-input");
const keywordResults = document.getElementById("keyword-results");
const scanStatus = document.getElementById("scan-status");

let scanner = null;
let scannerRunning = false;
let processing = false;
let keywordDebounce = null;

function resetResultPanel() {
    resultPanel.classList.remove("showing-profile");
    resultPanel.innerHTML = `
        <span class="bracket-bl"></span><span class="bracket-br"></span>
        <div class="eyebrow">No record selected</div>
        <p style="color: var(--ink-soft); font-size: 13.5px; max-width: 320px;">
            Scan a QR code or search by keyword to view a resident's profile and visit history.
        </p>
    `;
}

function showError(message) {
    resultPanel.classList.remove("showing-profile");
    resultPanel.innerHTML = `
        <span class="bracket-bl"></span><span class="bracket-br"></span>
        <div class="eyebrow" style="color: var(--red);">Not found</div>
        <p style="color: var(--ink-soft); font-size: 13.5px;">${message}</p>
    `;
}

function historyRow(h) {
    const cls = h.type === "IN" ? "badge-in" : "badge-out";
    const label = h.type === "IN" ? "TIME-IN" : "TIME-OUT";
    return `
        <div class="history-row">
            <span class="badge ${cls}">${label}</span>
            <span class="mono">${h.timestamp}</span>
        </div>
    `;
}

function showProfile(p) {
    resultPanel.classList.add("showing-profile");
    resultPanel.innerHTML = `
        <span class="bracket-bl"></span><span class="bracket-br"></span>
        <div class="profile-view">
            <div class="profile-header">
                <div class="profile-avatar">${p.first_name[0].toUpperCase()}</div>
                <div>
                    <div class="profile-name">${p.full_name}</div>
                    <div class="profile-sub mono">${p.id_number}</div>
                </div>
            </div>
            <div class="profile-grid">
                <div class="profile-field"><div class="label">Barangay</div><div class="value">${p.barangay}</div></div>
                <div class="profile-field"><div class="label">City/Municipality</div><div class="value">${p.city_municipality}</div></div>
                <div class="profile-field"><div class="label">Province</div><div class="value">${p.province}</div></div>
                <div class="profile-field"><div class="label">Registered On</div><div class="value">${p.registered_on}</div></div>
                <div class="profile-field"><div class="label">Total Visits</div><div class="value">${p.total_visits}</div></div>
                <div class="profile-field"><div class="label">Geocode</div><div class="value geocode">${p.geocode || '-'}</div></div>
            </div>
            <div class="history-title">Visit History</div>
            <div class="history-list">
                ${p.history.length ? p.history.map(historyRow).join("") : '<div class="keyword-empty">No visits logged yet.</div>'}
            </div>
        </div>
    `;
}

async function loadProfile(idNumber) {
    try {
        const res = await fetch(`/api/resident/${encodeURIComponent(idNumber)}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "No record found.");
        showProfile(data);
    } catch (err) {
        showError(err.message);
    }
}

// ---------- Tabs ----------
tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
        tabButtons.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const target = btn.dataset.tab;
        Object.entries(tabPanels).forEach(([key, panel]) => {
            panel.style.display = key === target ? "block" : "none";
        });
        if (target === "qr") {
            startScanner();
        } else {
            stopScanner();
        }
    });
});

// ---------- Manual keyword search ----------
keywordInput.addEventListener("input", () => {
    clearTimeout(keywordDebounce);
    const q = keywordInput.value.trim();
    if (!q) {
        keywordResults.innerHTML = "";
        return;
    }
    keywordDebounce = setTimeout(async () => {
        try {
            const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
            const rows = await res.json();
            if (!rows.length) {
                keywordResults.innerHTML = `<div class="keyword-empty">No matches for "${q}".</div>`;
                return;
            }
            keywordResults.innerHTML = `<div class="keyword-list">${rows.map(r => `
                <button type="button" class="keyword-item" data-id="${r.id_number}">
                    <div>
                        <div class="ki-name">${r.full_name}</div>
                        <div class="ki-meta">${r.barangay}, ${r.city_municipality}</div>
                    </div>
                    <div class="ki-id">${r.id_number}</div>
                </button>
            `).join("")}</div>`;
            keywordResults.querySelectorAll(".keyword-item").forEach(item => {
                item.addEventListener("click", () => loadProfile(item.dataset.id));
            });
        } catch (e) {
            keywordResults.innerHTML = `<div class="keyword-empty">Search failed. Try again.</div>`;
        }
    }, 250);
});

// ---------- QR scanning (lookup only, no logging) ----------
async function handleDecodedText(decodedText) {
    if (processing) return;
    processing = true;
    scanStatus.textContent = "Looking up ID...";
    await loadProfile(decodedText);
    setTimeout(() => {
        processing = false;
        scanStatus.textContent = "Point a QR code at the camera to look someone up";
    }, 1200);
}

function startScanner() {
    if (scannerRunning) return;
    if (!scanner) scanner = new Html5Qrcode("qr-reader");
    Html5Qrcode.getCameras().then(cameras => {
        if (!cameras || !cameras.length) {
            scanStatus.textContent = "No camera found on this device.";
            return;
        }
        scanner.start(
            cameras[0].id,
            { fps: 10, qrbox: { width: 250, height: 250 } },
            (decodedText) => handleDecodedText(decodedText),
            () => { /* ignore per-frame decode errors */ }
        ).then(() => { scannerRunning = true; });
    }).catch(() => {
        scanStatus.textContent = "Camera access was denied. Please allow camera permissions.";
    });
}

function stopScanner() {
    if (scanner && scannerRunning) {
        scanner.stop().then(() => { scannerRunning = false; }).catch(() => {});
    }
}

startScanner();
