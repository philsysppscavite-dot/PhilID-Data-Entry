const scoped = window.TRANSMITTAL_SCOPED === true;

const personnelSelect = document.getElementById("filter-personnel");
const statusSelect = document.getElementById("filter-status");
const reloadBtn = document.getElementById("reload-btn");
const printBtn = document.getElementById("print-list-btn");
const exportBtn = document.getElementById("export-csv-btn");
const body = document.getElementById("transmittal-body");
const printMeta = document.getElementById("print-meta");

let currentResults = [];
let currentPersonnel = null;

function getUrlPersonnelId() {
    const params = new URLSearchParams(window.location.search);
    return params.get("personnel_id") || "";
}

function renderRows(data) {
    currentResults = data.results;
    currentPersonnel = data.personnel;

    if (!data.results.length) {
        body.innerHTML = `<div class="empty-state">
            <span class="eyebrow">No records</span>
            No IDs match this personnel/status combination.
        </div>`;
        printMeta.textContent = "";
        return;
    }

    body.innerHTML = `
        <table class="data-table">
            <thead>
                <tr>
                    <th style="width:34px;">#</th>
                    <th>ID Number</th>
                    <th>Full Name</th>
                    <th>Address</th>
                    <th>Contact No.</th>
                    <th>Checked Out</th>
                    <th class="no-print">Signature / Received By</th>
                </tr>
            </thead>
            <tbody>
                ${data.results.map((r, i) => `
                    <tr>
                        <td>${i + 1}</td>
                        <td class="mono">${r.id_number}</td>
                        <td>${r.full_name}</td>
                        <td>${[r.address_line, r.barangay, r.city_municipality, r.province].filter(Boolean).join(", ")}</td>
                        <td>${r.contact_number || "-"}</td>
                        <td class="mono">${r.checked_out_at || "-"}</td>
                        <td class="no-print"></td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `;

    const statusLabel = statusSelect.value
        ? statusSelect.options[statusSelect.selectedIndex].text
        : "All statuses";
    printMeta.textContent = `Assigned to: ${data.personnel.full_name} (${data.personnel.username}) \u00b7 ${statusLabel} \u00b7 Generated ${data.generated_at} \u00b7 Total: ${data.results.length}`;
}

async function loadTransmittal() {
    const params = new URLSearchParams();
    if (statusSelect.value) params.set("status", statusSelect.value);

    if (!scoped) {
        const personnelId = personnelSelect.value;
        if (!personnelId) {
            body.innerHTML = `<div class="empty-state">Select a delivery personnel/user above to generate their transmittal.</div>`;
            printMeta.textContent = "";
            return;
        }
        params.set("personnel_id", personnelId);
    }

    body.innerHTML = `<div class="empty-state">Loading...</div>`;
    try {
        const res = await fetch(`/api/transmittal?${params.toString()}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Couldn't load the transmittal.");
        renderRows(data);
    } catch (e) {
        body.innerHTML = `<div class="empty-state">${e.message}</div>`;
    }
}

async function loadPersonnelOptions() {
    if (scoped) return;
    const res = await fetch("/api/personnel-list");
    const people = await res.json();
    const preselect = getUrlPersonnelId();
    personnelSelect.innerHTML =
        `<option value="">Select delivery personnel / user...</option>` +
        people.map(p => `<option value="${p.id}" ${String(p.id) === preselect ? "selected" : ""}>${p.full_name} (${p.username})</option>`).join("");
}

if (personnelSelect) personnelSelect.addEventListener("change", loadTransmittal);
statusSelect.addEventListener("change", loadTransmittal);
reloadBtn.addEventListener("click", loadTransmittal);
printBtn.addEventListener("click", () => window.print());

exportBtn.addEventListener("click", () => {
    if (!currentResults.length) return;
    const header = ["#", "ID Number", "Full Name", "Address", "Contact No.", "Checked Out"];
    const lines = [header.join(",")];
    currentResults.forEach((r, i) => {
        const address = [r.address_line, r.barangay, r.city_municipality, r.province].filter(Boolean).join(", ");
        const row = [i + 1, r.id_number, r.full_name, address, r.contact_number || "", r.checked_out_at || ""]
            .map(v => `"${String(v).replace(/"/g, '""')}"`);
        lines.push(row.join(","));
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const who = currentPersonnel ? currentPersonnel.username : "transmittal";
    a.download = `transmittal_${who}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
});

(async function init() {
    if (!scoped) {
        await loadPersonnelOptions();
        if (getUrlPersonnelId()) {
            loadTransmittal();
        } else {
            body.innerHTML = `<div class="empty-state">Select a delivery personnel/user above to generate their transmittal.</div>`;
        }
    } else {
        loadTransmittal();
    }
})();
