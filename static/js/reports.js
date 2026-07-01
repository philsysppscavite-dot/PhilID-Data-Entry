const reportWrap = document.getElementById("report-wrap");
const provinceSelect = document.getElementById("filter-province");
const citySelect = document.getElementById("filter-city");
const statusSelect = document.getElementById("filter-status");
const dateFrom = document.getElementById("filter-date-from");
const dateTo = document.getElementById("filter-date-to");
const clearBtn = document.getElementById("clear-filters");
const printBtn = document.getElementById("print-report-btn");
const printMeta = document.getElementById("print-meta");

const statTotal = document.getElementById("stat-total");
const statDelivered = document.getElementById("stat-delivered");
const statPending = document.getElementById("stat-pending");
const statOut = document.getElementById("stat-out");
const statReturned = document.getElementById("stat-returned");
const statReturnedOffice = document.getElementById("stat-returned-office");

const exportBtn = document.getElementById("export-csv-btn");
let currentResults = [];

const photoModal = document.getElementById("photo-modal");
const photoModalImg = document.getElementById("photo-modal-img");
const photoModalCaption = document.getElementById("photo-modal-caption");
document.getElementById("photo-modal-close").addEventListener("click", () => photoModal.style.display = "none");
photoModal.addEventListener("click", (e) => { if (e.target === photoModal) photoModal.style.display = "none"; });

function statusBadge(status) {
    if (status === "delivered") return `<span class="badge badge-in">DELIVERED</span>`;
    if (status === "returned") return `<span class="badge badge-out">RETURNED</span>`;
    if (status === "returned_to_office") return `<span class="badge badge-admin">RETURNED TO OFFICE</span>`;
    if (status === "out_for_delivery") return `<span class="badge badge-delivery">OUT FOR DELIVERY</span>`;
    return `<span class="badge badge-staff">PENDING</span>`;
}

function gpsBadge(r) {
    if (r.delivery_gps_matched === null || r.delivery_gps_matched === undefined) return "-";
    return r.delivery_gps_matched
        ? `<span class="badge badge-in">MATCH</span>`
        : `<span class="badge badge-out">MISMATCH</span>`;
}

function renderTable(rows) {
    if (!rows.length) {
        reportWrap.innerHTML = `<div class="empty-state"><span class="eyebrow">No records</span>No residents match these filters.</div>`;
        return;
    }
    reportWrap.innerHTML = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>ID Number</th>
                    <th>Full Name</th>
                    <th>Barangay</th>
                    <th>City/Municipality</th>
                    <th>Province</th>
                    <th>Status</th>
                    <th>Resolved On</th>
                    <th>Resolved By</th>
                    <th>Reason (if returned)</th>
                    <th>GPS</th>
                    <th>Photo</th>
                </tr>
            </thead>
            <tbody>
                ${rows.map(r => `
                    <tr>
                        <td class="mono">${r.id_number}</td>
                        <td>${r.full_name}</td>
                        <td>${r.barangay}</td>
                        <td>${r.city_municipality}</td>
                        <td>${r.province}</td>
                        <td>${statusBadge(r.delivery_status)}</td>
                        <td class="mono">${r.returned_to_office_at || r.delivered_at || r.returned_at || "-"}</td>
                        <td>${r.delivery_status === "returned_to_office" ? (r.returned_to_office_by || "-") : (r.delivered_by || "-")}</td>
                        <td>${(r.delivery_status === "returned" || r.delivery_status === "returned_to_office") ? (r.delivery_remarks || "-") : "-"}</td>
                        <td>${gpsBadge(r)}</td>
                        <td>${r.delivery_photo_url
                            ? `<img src="${r.delivery_photo_url}" class="report-thumb" data-full="${r.delivery_photo_url}" data-caption="${r.full_name} \u00b7 ${r.delivered_at || r.returned_at || ''}${r.delivery_remarks ? ' \u00b7 ' + r.delivery_remarks : ''}">`
                            : "-"}</td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `;
    reportWrap.querySelectorAll(".report-thumb").forEach(img => {
        img.addEventListener("click", () => {
            photoModalImg.src = img.dataset.full;
            photoModalCaption.textContent = img.dataset.caption;
            photoModal.style.display = "flex";
        });
    });
}

async function loadReport() {
    const params = new URLSearchParams();
    if (provinceSelect.value) params.set("province", provinceSelect.value);
    if (citySelect.value) params.set("city", citySelect.value);
    if (statusSelect.value) params.set("status", statusSelect.value);
    if (dateFrom.value) params.set("date_from", dateFrom.value);
    if (dateTo.value) params.set("date_to", dateTo.value);

    reportWrap.innerHTML = `<div class="empty-state">Loading records...</div>`;
    try {
        const res = await fetch(`/api/delivery-report?${params.toString()}`);
        const data = await res.json();
        statTotal.textContent = data.summary.total;
        statDelivered.textContent = data.summary.delivered;
        statPending.textContent = data.summary.pending;
        statOut.textContent = data.summary.out_for_delivery;
        statReturned.textContent = data.summary.returned;
        statReturnedOffice.textContent = data.summary.returned_to_office;
        currentResults = data.results;
        renderTable(data.results);
        const areaLabel = [provinceSelect.value, citySelect.value].filter(Boolean).join(" \u2192 ") || "All areas";
        printMeta.textContent = `${areaLabel} \u00b7 Generated ${new Date().toLocaleString()} \u00b7 Delivered ${data.summary.delivered} / ${data.summary.total}`;
    } catch (e) {
        reportWrap.innerHTML = `<div class="empty-state">Couldn't load the report. Try refreshing.</div>`;
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

provinceSelect.addEventListener("change", async () => {
    await loadCities(provinceSelect.value);
    loadReport();
});
[citySelect, statusSelect, dateFrom, dateTo].forEach(el => el.addEventListener("change", loadReport));

clearBtn.addEventListener("click", () => {
    provinceSelect.value = "";
    citySelect.innerHTML = `<option value="">All cities/municipalities</option>`;
    statusSelect.value = "";
    dateFrom.value = "";
    dateTo.value = "";
    loadReport();
});

printBtn.addEventListener("click", () => window.print());

exportBtn.addEventListener("click", () => {
    if (!currentResults.length) return;
    const header = ["ID Number", "Full Name", "Barangay", "City/Municipality", "Province", "Status", "Resolved On", "Resolved By", "Reason (if returned)"];
    const lines = [header.join(",")];
    currentResults.forEach(r => {
        const resolvedOn = r.returned_to_office_at || r.delivered_at || r.returned_at || "";
        const resolvedBy = r.delivery_status === "returned_to_office" ? (r.returned_to_office_by || "") : (r.delivered_by || "");
        const reason = (r.delivery_status === "returned" || r.delivery_status === "returned_to_office") ? (r.delivery_remarks || "") : "";
        const row = [r.id_number, r.full_name, r.barangay, r.city_municipality, r.province, r.delivery_status, resolvedOn, resolvedBy, reason]
            .map(v => `"${String(v).replace(/"/g, '""')}"`);
        lines.push(row.join(","));
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `delivery_report_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
});

loadProvinces();
loadReport();
