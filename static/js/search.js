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
let currentIdNumber = null;

function resetResultPanel() {
    resultPanel.classList.remove("showing-profile");
    currentIdNumber = null;
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
    currentIdNumber = null;
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

function gpsNote(p) {
    if (p.delivery_gps_reference === "unverified" || p.delivery_gps_matched === null || p.delivery_gps_matched === undefined) {
        return `<div class="result-meta">GPS: not verified</div>`;
    }
    const label = p.delivery_gps_matched
        ? `&#10003; Matches resident's ${p.delivery_gps_reference === "address" ? "exact address" : "barangay"}`
        : `&#9888; ${p.delivery_gps_distance_m ? p.delivery_gps_distance_m + "m from" : "Outside"} the resident's barangay`;
    const color = p.delivery_gps_matched ? "var(--green)" : "var(--red)";
    return `<div class="result-meta" style="color:${color};">${label}</div>`;
}

function deliverySection(p) {
    const status = p.delivery_status;

    if (status === "delivered") {
        return `
            <div class="history-title">ID Delivery</div>
            <div class="delivery-box delivered">
                <div class="delivery-row"><span class="badge badge-in">DELIVERED</span><span class="mono">${p.delivered_at || ""}</span></div>
                <div class="result-meta" style="margin-top:6px;">By: ${p.delivered_by || "-"}${p.delivery_remarks ? " &middot; " + p.delivery_remarks : ""}</div>
                ${gpsNote(p)}
                ${p.delivery_photo_url ? `<img src="${p.delivery_photo_url}" class="delivery-photo" alt="Proof of delivery">` : ""}
                <button type="button" class="btn btn-outline btn-sm" id="undo-delivery-btn" style="margin-top:10px;">Undo (mark pending)</button>
            </div>
        `;
    }

    if (status === "returned") {
        return `
            <div class="history-title">ID Delivery</div>
            <div class="delivery-box returned">
                <div class="delivery-row"><span class="badge badge-out">RETURNED / NOT DELIVERED</span><span class="mono">${p.returned_at || ""}</span></div>
                <div class="result-meta" style="margin-top:6px;"><strong>Reason:</strong> ${p.delivery_remarks || "-"}</div>
                <div class="result-meta">By: ${p.delivered_by || "-"}</div>
                ${gpsNote(p)}
                ${p.delivery_photo_url ? `<img src="${p.delivery_photo_url}" class="delivery-photo" alt="Return documentation">` : ""}
                <div style="display:flex; gap:8px; margin-top:10px; flex-wrap:wrap;">
                    <button type="button" class="btn btn-primary btn-sm" id="return-office-btn">Scan: Returned to Office</button>
                    <button type="button" class="btn btn-outline btn-sm" id="checkout-delivery-btn">Check Out Again</button>
                    <button type="button" class="btn btn-outline btn-sm" id="undo-delivery-btn">Undo (mark pending)</button>
                </div>
            </div>
        `;
    }

    if (status === "returned_to_office") {
        return `
            <div class="history-title">ID Delivery</div>
            <div class="delivery-box office">
                <div class="delivery-row"><span class="badge badge-admin">RETURNED TO DELIVERY OFFICE</span><span class="mono">${p.returned_to_office_at || ""}</span></div>
                <div class="result-meta" style="margin-top:6px;">Received by: ${p.returned_to_office_by || "-"}</div>
                ${p.delivery_remarks ? `<div class="result-meta"><strong>Original reason:</strong> ${p.delivery_remarks}</div>` : ""}
                <div style="display:flex; gap:8px; margin-top:10px;">
                    <button type="button" class="btn btn-primary btn-sm" id="checkout-delivery-btn">Check Out Again</button>
                    <button type="button" class="btn btn-outline btn-sm" id="undo-delivery-btn">Undo (mark pending)</button>
                </div>
            </div>
        `;
    }

    if (status === "out_for_delivery") {
        return `
            <div class="history-title">ID Delivery</div>
            <div class="delivery-box out">
                <div class="delivery-row"><span class="badge badge-delivery">OUT FOR DELIVERY</span><span class="mono">${p.checked_out_at || ""}</span></div>
                <div class="result-meta" style="margin-top:6px;">Taken by: ${p.checked_out_by || "-"}</div>
                <div style="display:flex; gap:8px; margin-top:10px;">
                    <button type="button" class="btn btn-primary btn-sm" id="mark-delivered-btn">Mark Delivered</button>
                    <button type="button" class="btn btn-outline btn-sm" id="mark-returned-btn">Not Delivered</button>
                </div>
            </div>
        `;
    }

    // pending
    return `
        <div class="history-title">ID Delivery</div>
        <div class="delivery-box">
            <div class="delivery-row"><span class="badge badge-staff">PENDING</span></div>
            <button type="button" class="btn btn-primary btn-sm" id="checkout-delivery-btn" style="margin-top:10px;">Check Out for Delivery</button>
        </div>
    `;
}

function showProfile(p) {
    currentIdNumber = p.id_number;
    resultPanel.classList.add("showing-profile");
    resultPanel.innerHTML = `
        <span class="bracket-bl"></span><span class="bracket-br"></span>
        <div class="profile-view">
            <div class="profile-header">
                <div class="profile-avatar">${p.first_name[0].toUpperCase()}</div>
                <div style="flex:1;">
                    <div class="profile-name">${p.full_name}</div>
                    <div class="profile-sub mono">${p.id_number}</div>
                </div>
                ${typeof CAN_EDIT_RESIDENTS !== "undefined" && CAN_EDIT_RESIDENTS ? `
                <div style="display:flex; gap:6px;">
                    <button type="button" class="btn btn-outline btn-sm" id="edit-resident-btn">Edit</button>
                    <button type="button" class="btn btn-danger-outline btn-sm" id="delete-resident-btn">Delete</button>
                </div>` : ""}
            </div>
            <div class="profile-grid">
                <div class="profile-field"><div class="label">Barangay</div><div class="value">${p.barangay}</div></div>
                <div class="profile-field"><div class="label">City/Municipality</div><div class="value">${p.city_municipality}</div></div>
                <div class="profile-field"><div class="label">Province</div><div class="value">${p.province}</div></div>
                <div class="profile-field"><div class="label">Contact No.</div><div class="value">${p.contact_number || "-"}</div></div>
                <div class="profile-field"><div class="label">Registered On</div><div class="value">${p.registered_on}</div></div>
                <div class="profile-field"><div class="label">Total Visits</div><div class="value">${p.total_visits}</div></div>
            </div>
            ${deliverySection(p)}
            <div class="history-title">Visit History</div>
            <div class="history-list">
                ${p.history.length ? p.history.map(historyRow).join("") : '<div class="keyword-empty">No visits logged yet.</div>'}
            </div>
        </div>
    `;
    const checkoutBtn = document.getElementById("checkout-delivery-btn");
    if (checkoutBtn) checkoutBtn.addEventListener("click", checkoutDelivery);
    const markDeliveredBtn = document.getElementById("mark-delivered-btn");
    if (markDeliveredBtn) markDeliveredBtn.addEventListener("click", () => openResolveModal("delivered"));
    const markReturnedBtn = document.getElementById("mark-returned-btn");
    if (markReturnedBtn) markReturnedBtn.addEventListener("click", () => openResolveModal("returned"));
    const undoBtn = document.getElementById("undo-delivery-btn");
    if (undoBtn) undoBtn.addEventListener("click", undoDelivery);
    const returnOfficeBtn = document.getElementById("return-office-btn");
    if (returnOfficeBtn) returnOfficeBtn.addEventListener("click", returnToOffice);
    const editBtn = document.getElementById("edit-resident-btn");
    if (editBtn) editBtn.addEventListener("click", () => openEditModal(p));
    const deleteBtn = document.getElementById("delete-resident-btn");
    if (deleteBtn) deleteBtn.addEventListener("click", deleteResident);
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
const ID_NUMBER_RE = /^\d{29}$/;

async function handleDecodedText(decodedText) {
    if (processing) return;
    processing = true;

    const idNumber = (decodedText || "").trim();
    if (!ID_NUMBER_RE.test(idNumber)) {
        showError(`Invalid QR code. A PhilSys ID number must be exactly 29 digits (got ${idNumber.length}).`);
        setTimeout(() => {
            processing = false;
            scanStatus.textContent = "Point a QR code at the camera to look someone up";
        }, 1200);
        return;
    }

    scanStatus.textContent = "Looking up ID...";
    await loadProfile(idNumber);
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

// ---------- Check Out for Delivery (scan OUT) ----------
async function checkoutDelivery() {
    if (!currentIdNumber) return;
    try {
        const res = await fetch(`/api/delivery/${encodeURIComponent(currentIdNumber)}/checkout`, { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Could not check out this ID.");
        loadProfile(currentIdNumber);
    } catch (err) {
        alert(err.message);
    }
}

async function undoDelivery() {
    if (!currentIdNumber) return;
    if (!confirm("Mark this ID back to pending delivery?")) return;
    try {
        await fetch(`/api/delivery/${encodeURIComponent(currentIdNumber)}/undo`, { method: "POST" });
        loadProfile(currentIdNumber);
    } catch (err) {
        alert("Couldn't update delivery status. Try again.");
    }
}

// ---------- Scan the returned ID back in at the office (tally step) ----------
async function returnToOffice() {
    if (!currentIdNumber) return;
    if (!confirm("Confirm this ID has been physically handed back to the delivery office?")) return;
    try {
        const res = await fetch(`/api/delivery/${encodeURIComponent(currentIdNumber)}/return-to-office`, { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Could not update this record.");
        loadProfile(currentIdNumber);
    } catch (err) {
        alert(err.message);
    }
}

// ---------- Resolve (mark Delivered / Returned): GPS + photo required ----------
const resolveModal = document.getElementById("resolve-modal");
const resolveForm = document.getElementById("resolve-form");
const resolveError = document.getElementById("resolve-error");
const resolveTitle = document.getElementById("resolve-title");
const resolveDesc = document.getElementById("resolve-desc");
const resolveRemarksLabel = document.getElementById("resolve-remarks-label");
const resolveRemarksInput = document.getElementById("resolve-remarks");
const resolveSubmitBtn = document.getElementById("resolve-submit");
const resolveGpsStatus = document.getElementById("resolve-gps-status");
const cancelResolveBtn = document.getElementById("cancel-resolve");

let resolveOutcome = null;
let capturedLat = null;
let capturedLng = null;

function openResolveModal(outcome) {
    resolveOutcome = outcome;
    resolveForm.reset();
    resolveError.style.display = "none";
    capturedLat = null;
    capturedLng = null;

    if (outcome === "delivered") {
        resolveTitle.textContent = "Mark ID as Delivered";
        resolveDesc.textContent = "Attach a photo showing the ID was delivered (e.g. resident holding the ID, or ID at the doorstep). Location is captured automatically.";
        resolveRemarksLabel.textContent = "Remarks (optional)";
        resolveRemarksInput.placeholder = "e.g. Received by spouse";
        resolveRemarksInput.required = false;
        resolveSubmitBtn.textContent = "Confirm Delivery";
    } else {
        resolveTitle.textContent = "Mark as Not Delivered";
        resolveDesc.textContent = "Explain why the ID could not be delivered and attach a photo (e.g. of the location, or the closed gate/vacant address). Location is captured automatically.";
        resolveRemarksLabel.textContent = "Reason (required)";
        resolveRemarksInput.placeholder = "e.g. No one home, wrong address, resident moved out";
        resolveRemarksInput.required = true;
        resolveSubmitBtn.textContent = "Confirm Not Delivered";
    }

    resolveModal.style.display = "flex";
    captureGps();
}

function closeResolveModal() {
    resolveModal.style.display = "none";
}

function captureGps() {
    resolveGpsStatus.textContent = "Getting your location...";
    resolveGpsStatus.style.color = "var(--ink-soft)";
    resolveSubmitBtn.disabled = true;

    if (!("geolocation" in navigator)) {
        resolveGpsStatus.textContent = "Location isn't available on this device/browser.";
        resolveGpsStatus.style.color = "var(--red)";
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (pos) => {
            capturedLat = pos.coords.latitude;
            capturedLng = pos.coords.longitude;
            resolveGpsStatus.textContent = `Location captured (accuracy ~${Math.round(pos.coords.accuracy)}m).`;
            resolveGpsStatus.style.color = "var(--green)";
            resolveSubmitBtn.disabled = false;
        },
        () => {
            resolveGpsStatus.textContent = "Couldn't get your location. Please allow location access and retry.";
            resolveGpsStatus.style.color = "var(--red)";
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
}

cancelResolveBtn.addEventListener("click", closeResolveModal);
resolveModal.addEventListener("click", (e) => { if (e.target === resolveModal) closeResolveModal(); });

resolveForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    resolveError.style.display = "none";
    if (!currentIdNumber || !resolveOutcome) return;

    const fileInput = document.getElementById("resolve-photo-input");
    const remarks = resolveRemarksInput.value.trim();

    if (!fileInput.files.length) {
        resolveError.textContent = "Please attach a photo.";
        resolveError.style.display = "block";
        return;
    }
    if (resolveOutcome === "returned" && !remarks) {
        resolveError.textContent = "Please provide a reason for the non-delivery.";
        resolveError.style.display = "block";
        return;
    }
    if (capturedLat === null || capturedLng === null) {
        resolveError.textContent = "Location hasn't been captured yet. Please wait or retry.";
        resolveError.style.display = "block";
        return;
    }

    const formData = new FormData();
    formData.append("outcome", resolveOutcome);
    formData.append("photo", fileInput.files[0]);
    formData.append("remarks", remarks);
    formData.append("lat", capturedLat);
    formData.append("lng", capturedLng);

    try {
        const res = await fetch(`/api/delivery/${encodeURIComponent(currentIdNumber)}/resolve`, {
            method: "POST",
            body: formData,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Could not save this record.");

        closeResolveModal();
        loadProfile(currentIdNumber);
    } catch (err) {
        resolveError.textContent = err.message;
        resolveError.style.display = "block";
    }
});

startScanner();

// ---------- Delete resident ----------
async function deleteResident() {
    if (!currentIdNumber) return;
    if (!confirm(`Permanently delete this resident and all their visit/delivery history? This can't be undone.`)) return;
    try {
        const res = await fetch(`/api/resident/${encodeURIComponent(currentIdNumber)}`, { method: "DELETE" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || "Could not delete this record.");
        resetResultPanel();
        keywordResults.innerHTML = "";
        keywordInput.value = "";
    } catch (err) {
        alert(err.message);
    }
}

// ---------- Edit resident ----------
const editModal = document.getElementById("edit-modal");
const editForm = document.getElementById("edit-form");
const editError = document.getElementById("edit-error");
const editIdNumberLabel = document.getElementById("edit-id-number");
const cancelEditBtn = document.getElementById("cancel-edit");

const editProvinceSelect = document.getElementById("edit_province");
const editCitySelect = document.getElementById("edit_city");
const editBarangaySelect = document.getElementById("edit_barangay");

let editingProfile = null;

// Data-entry fields (name/address) are always stored in ALL CAPS, matching
// the masterlist/reference data convention -- force it as the person types.
["edit_first_name", "edit_middle_name", "edit_last_name", "edit_suffix", "edit_address_line"].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
        el.addEventListener("input", () => {
            const pos = el.selectionStart;
            el.value = el.value.toUpperCase();
            el.setSelectionRange(pos, pos);
        });
    }
});

async function loadEditProvinces() {
    const res = await fetch("/api/provinces");
    const provinces = await res.json();
    editProvinceSelect.innerHTML =
        `<option value="">Select province...</option>` +
        provinces.map(p => `<option value="${p}">${p}</option>`).join("");
}

async function loadEditCities(province, selected) {
    editCitySelect.disabled = true;
    editCitySelect.innerHTML = `<option value="">Loading...</option>`;
    if (!province) {
        editCitySelect.innerHTML = `<option value="">Select province first...</option>`;
        return;
    }
    const res = await fetch(`/api/cities?province=${encodeURIComponent(province)}`);
    const cities = await res.json();
    editCitySelect.innerHTML =
        `<option value="">Select city/municipality...</option>` +
        cities.map(c => `<option value="${c}" ${c === selected ? "selected" : ""}>${c}</option>`).join("");
    editCitySelect.disabled = false;
}

async function loadEditBarangays(province, city, selected) {
    editBarangaySelect.disabled = true;
    editBarangaySelect.innerHTML = `<option value="">Loading...</option>`;
    if (!province || !city) {
        editBarangaySelect.innerHTML = `<option value="">Select city/municipality first...</option>`;
        return;
    }
    const res = await fetch(`/api/barangays?province=${encodeURIComponent(province)}&city=${encodeURIComponent(city)}`);
    const barangays = await res.json();
    editBarangaySelect.innerHTML =
        `<option value="">Select barangay...</option>` +
        barangays.map(b => `<option value="${b.name}" data-geocode="${b.geocode}" ${b.name === selected ? "selected" : ""}>${b.name}</option>`).join("");
    editBarangaySelect.disabled = false;
}

editProvinceSelect.addEventListener("change", async () => {
    await loadEditCities(editProvinceSelect.value);
    editBarangaySelect.innerHTML = `<option value="">Select city/municipality first...</option>`;
    editBarangaySelect.disabled = true;
});
editCitySelect.addEventListener("change", async () => {
    await loadEditBarangays(editProvinceSelect.value, editCitySelect.value);
});

async function openEditModal(p) {
    editingProfile = p;
    editError.style.display = "none";
    editIdNumberLabel.textContent = p.id_number;

    document.getElementById("edit_first_name").value = p.first_name || "";
    document.getElementById("edit_middle_name").value = p.middle_name || "";
    document.getElementById("edit_last_name").value = p.last_name || "";
    document.getElementById("edit_suffix").value = p.suffix || "";
    document.getElementById("edit_address_line").value = p.address_line || "";
    document.getElementById("edit_contact_number").value = p.contact_number || "";

    editModal.style.display = "flex";

    await loadEditProvinces();
    editProvinceSelect.value = p.province || "";
    await loadEditCities(p.province, p.city_municipality);
    await loadEditBarangays(p.province, p.city_municipality, p.barangay);
}

function closeEditModal() {
    editModal.style.display = "none";
    editingProfile = null;
}

cancelEditBtn.addEventListener("click", closeEditModal);
editModal.addEventListener("click", (e) => { if (e.target === editModal) closeEditModal(); });

editForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    editError.style.display = "none";
    if (!editingProfile) return;

    const geocodeOpt = editBarangaySelect.selectedOptions[0];
    const payload = {
        first_name: document.getElementById("edit_first_name").value.trim(),
        middle_name: document.getElementById("edit_middle_name").value.trim(),
        last_name: document.getElementById("edit_last_name").value.trim(),
        suffix: document.getElementById("edit_suffix").value.trim(),
        province: editProvinceSelect.value,
        city_municipality: editCitySelect.value,
        barangay: editBarangaySelect.value,
        geocode: geocodeOpt ? geocodeOpt.dataset.geocode : "",
        address_line: document.getElementById("edit_address_line").value.trim(),
        contact_number: document.getElementById("edit_contact_number").value.trim(),
    };

    try {
        const res = await fetch(`/api/resident/${encodeURIComponent(editingProfile.id_number)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Could not save changes.");

        closeEditModal();
        loadProfile(editingProfile.id_number);
    } catch (err) {
        editError.textContent = err.message;
        editError.style.display = "block";
    }
});
