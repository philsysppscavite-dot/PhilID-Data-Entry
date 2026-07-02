const tbody = document.getElementById("logs-tbody");
const searchInput = document.getElementById("filter-search");
const provinceSelect = document.getElementById("filter-province");
const citySelect = document.getElementById("filter-city");
const typeSelect = document.getElementById("filter-type");
const dateFrom = document.getElementById("filter-date-from");
const dateTo = document.getElementById("filter-date-to");
const clearBtn = document.getElementById("clear-filters");

let searchDebounce = null;

function badge(type) {
    return type === "IN"
        ? `<span class="badge badge-in">TIME-IN</span>`
        : `<span class="badge badge-out">TIME-OUT</span>`;
}

function renderRows(rows) {
    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="empty-state">
            <span class="eyebrow">No records</span>
            No scans match these filters yet.
        </td></tr>`;
        return;
    }
    tbody.innerHTML = rows.map(r => `
        <tr>
            <td class="mono">${r.id_number}</td>
            <td>${r.full_name}</td>
            <td>${r.barangay}</td>
            <td>${r.city_municipality}</td>
            <td>${r.province}</td>
            <td>${badge(r.type)}</td>
            <td class="mono">${r.timestamp}</td>
            <td>${r.scanned_by}</td>
        </tr>
    `).join("");
}

async function loadLogs() {
    const params = new URLSearchParams();
    if (searchInput.value.trim()) params.set("q", searchInput.value.trim());
    if (provinceSelect.value) params.set("province", provinceSelect.value);
    if (citySelect.value) params.set("city", citySelect.value);
    if (typeSelect.value) params.set("type", typeSelect.value);
    if (dateFrom.value) params.set("date_from", dateFrom.value);
    if (dateTo.value) params.set("date_to", dateTo.value);

    tbody.innerHTML = `<tr><td colspan="8" class="empty-state">Loading records...</td></tr>`;
    try {
        const res = await fetch(`/api/logs?${params.toString()}`);
        const rows = await res.json();
        renderRows(rows);
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="8" class="empty-state">Couldn't load records. Try refreshing.</td></tr>`;
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

searchInput.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(loadLogs, 300);
});

provinceSelect.addEventListener("change", async () => {
    await loadCities(provinceSelect.value);
    loadLogs();
});

[citySelect, typeSelect, dateFrom, dateTo].forEach(el => el.addEventListener("change", loadLogs));

clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    provinceSelect.value = "";
    citySelect.innerHTML = `<option value="">All cities/municipalities</option>`;
    typeSelect.value = "";
    dateFrom.value = "";
    dateTo.value = "";
    loadLogs();
});

loadProvinces();
loadLogs();
setInterval(loadLogs, 15000); // keep the table fresh
