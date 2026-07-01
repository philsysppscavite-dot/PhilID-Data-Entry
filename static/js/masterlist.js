const tbody = document.getElementById("masterlist-tbody");
const provinceSelect = document.getElementById("filter-province");
const citySelect = document.getElementById("filter-city");
const barangaySelect = document.getElementById("filter-barangay");
const statusSelect = document.getElementById("filter-status");
const clearBtn = document.getElementById("clear-filters");
const printBtn = document.getElementById("print-list-btn");
const exportBtn = document.getElementById("export-csv-btn");
const printMeta = document.getElementById("print-meta");

let currentRows = [];

function statusBadge(status) {
    if (status === "delivered") return `<span class="badge badge-in">DELIVERED</span>`;
    if (status === "returned") return `<span class="badge badge-out">RETURNED</span>`;
    if (status === "returned_to_office") return `<span class="badge badge-admin">RETURNED TO OFFICE</span>`;
    if (status === "out_for_delivery") return `<span class="badge badge-delivery">OUT FOR DELIVERY</span>`;
    return `<span class="badge badge-staff">PENDING</span>`;
}

function renderRows(rows) {
    currentRows = rows;
    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state">
            <span class="eyebrow">No records</span>
            No residents match these filters.
        </td></tr>`;
        return;
    }
    tbody.innerHTML = rows.map((r, i) => `
        <tr>
            <td>${i + 1}</td>
            <td class="mono">${r.id_number}</td>
            <td>${r.full_name}</td>
            <td>${[r.address_line, r.barangay, r.city_municipality, r.province].filter(Boolean).join(", ")}</td>
            <td class="mono">${r.contact_number || "-"}</td>
            <td>${statusBadge(r.delivery_status)}</td>
            <td class="no-print"></td>
        </tr>
    `).join("");
}

async function loadMasterlist() {
    const params = new URLSearchParams();
    if (provinceSelect.value) params.set("province", provinceSelect.value);
    if (citySelect.value) params.set("city", citySelect.value);
    if (barangaySelect.value) params.set("barangay", barangaySelect.value);
    if (statusSelect.value) params.set("status", statusSelect.value);

    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Loading records...</td></tr>`;
    try {
        const res = await fetch(`/api/masterlist?${params.toString()}`);
        const rows = await res.json();
        renderRows(rows);
        const areaLabel = [provinceSelect.value, citySelect.value, barangaySelect.value].filter(Boolean).join(" \u2192 ") || "All areas";
        const statusLabel = statusSelect.value ? ` \u00b7 ${statusSelect.options[statusSelect.selectedIndex].text}` : "";
        printMeta.textContent = `${areaLabel}${statusLabel} \u00b7 Generated ${new Date().toLocaleString()} \u00b7 ${rows.length} record(s)`;
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Couldn't load records. Try refreshing.</td></tr>`;
    }
}

async function loadProvinces() {
    const res = await fetch("/api/provinces");
    const provinces = await res.json();
    provinceSelect.innerHTML =
        `<option value="">All provinces</option>` +
        provinces.map(p => `<option value="${p}">${p}</option>`).join("");
}

async function loadCities(province) {
    if (!province) {
        citySelect.innerHTML = `<option value="">All cities/municipalities</option>`;
        return;
    }
    const res = await fetch(`/api/cities?province=${encodeURIComponent(province)}`);
    const cities = await res.json();
    citySelect.innerHTML =
        `<option value="">All cities/municipalities</option>` +
        cities.map(c => `<option value="${c}">${c}</option>`).join("");
}

async function loadBarangays(province, city) {
    if (!province || !city) {
        barangaySelect.innerHTML = `<option value="">All barangays</option>`;
        return;
    }
    const res = await fetch(`/api/barangays?province=${encodeURIComponent(province)}&city=${encodeURIComponent(city)}`);
    const barangays = await res.json();
    barangaySelect.innerHTML =
        `<option value="">All barangays</option>` +
        barangays.map(b => `<option value="${b.name}">${b.name}</option>`).join("");
}

provinceSelect.addEventListener("change", async () => {
    barangaySelect.innerHTML = `<option value="">All barangays</option>`;
    await loadCities(provinceSelect.value);
    loadMasterlist();
});
citySelect.addEventListener("change", async () => {
    await loadBarangays(provinceSelect.value, citySelect.value);
    loadMasterlist();
});
[barangaySelect, statusSelect].forEach(el => el.addEventListener("change", loadMasterlist));

clearBtn.addEventListener("click", () => {
    provinceSelect.value = "";
    citySelect.innerHTML = `<option value="">All cities/municipalities</option>`;
    barangaySelect.innerHTML = `<option value="">All barangays</option>`;
    statusSelect.value = "";
    loadMasterlist();
});

printBtn.addEventListener("click", () => window.print());

exportBtn.addEventListener("click", () => {
    if (!currentRows.length) return;
    const header = ["ID Number", "Full Name", "Address Line", "Barangay", "City/Municipality", "Province", "Contact Number", "Status"];
    const lines = [header.join(",")];
    currentRows.forEach(r => {
        const row = [r.id_number, r.full_name, r.address_line || "", r.barangay, r.city_municipality, r.province, r.contact_number || "", r.delivery_status]
            .map(v => `"${String(v).replace(/"/g, '""')}"`);
        lines.push(row.join(","));
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `masterlist_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
});

loadProvinces();
loadMasterlist();

// ---------- Admin: import masterlist/RTS spreadsheet ----------
if (window.MASTERLIST_IS_ADMIN) {
    const importBtn = document.getElementById("import-masterlist-btn");
    const fileInput = document.getElementById("import-file-input");
    const resultBox = document.getElementById("import-result");

    importBtn.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", async () => {
        const file = fileInput.files[0];
        if (!file) return;

        importBtn.disabled = true;
        importBtn.textContent = "Importing...";
        resultBox.style.display = "none";

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("/api/masterlist/import", { method: "POST", body: formData });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Import failed.");

            resultBox.className = "flash flash-success no-print";
            resultBox.textContent =
                `Imported ${data.inserted} new resident(s) from ${data.sheets_processed} sheet(s). ` +
                `${data.already_existed} already existed (untouched). ` +
                `${data.barangay_corrected} barangay name(s) auto-corrected (mergers/renumbering/typos), ` +
                `${data.barangay_fuzzy_matched} more fixed by nearest-spelling match. ` +
                `Skipped: ${data.invalid_trn} invalid ID number(s), ${data.missing_fields} missing field(s), ` +
                `${data.duplicate_in_file} duplicate(s) in file, ${data.unmatched_city} unmatched municipality name(s), ` +
                `${data.unmatched_barangay} barangay name(s) we couldn't confidently match.`;
            resultBox.style.display = "block";
            loadMasterlist();
        } catch (e) {
            resultBox.className = "flash flash-danger no-print";
            resultBox.textContent = e.message;
            resultBox.style.display = "block";
        } finally {
            importBtn.disabled = false;
            importBtn.textContent = "Import Masterlist (.xlsx)";
            fileInput.value = "";
        }
    });
}
