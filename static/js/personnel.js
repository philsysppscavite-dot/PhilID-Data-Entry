const tbody = document.getElementById("personnel-tbody");
const printBtn = document.getElementById("print-report-btn");
const exportBtn = document.getElementById("export-csv-btn");
const printMeta = document.getElementById("print-meta");

const statPersonnel = document.getElementById("stat-personnel");
const statDelivered = document.getElementById("stat-delivered");
const statPending = document.getElementById("stat-pending");
const statReturned = document.getElementById("stat-returned");
const statReturnedOffice = document.getElementById("stat-returned-office");

let currentRows = [];

function renderRows(rows) {
    currentRows = rows;
    if (!rows.length) {
        tbody.innerHTML = `<tr><td colspan="9" class="empty-state">
            <span class="eyebrow">No records</span>
            No delivery personnel accounts have been registered yet.
        </td></tr>`;
        return;
    }
    tbody.innerHTML = rows.map(r => `
        <tr>
            <td>${r.full_name}</td>
            <td class="mono">${r.username}</td>
            <td><span class="badge ${r.is_active ? "badge-active" : "badge-disabled"}">${r.is_active ? "Active" : "Disabled"}</span></td>
            <td>${r.checked_out_total}</td>
            <td>${r.delivered_total}</td>
            <td>${r.pending}</td>
            <td>${r.returned_total}</td>
            <td>${r.returned_to_office_total}</td>
            <td class="no-print"><a class="btn btn-outline btn-sm" href="/transmittal?personnel_id=${r.id}">Transmittal</a></td>
        </tr>
    `).join("");
}

async function loadPersonnelReport() {
    tbody.innerHTML = `<tr><td colspan="9" class="empty-state">Loading records...</td></tr>`;
    try {
        const res = await fetch("/api/personnel-report");
        const data = await res.json();
        if (statPersonnel) statPersonnel.textContent = data.summary.total_personnel;
        statDelivered.textContent = data.summary.total_delivered;
        statPending.textContent = data.summary.total_pending;
        statReturned.textContent = data.summary.total_returned;
        statReturnedOffice.textContent = data.summary.total_returned_to_office;
        renderRows(data.personnel);
        printMeta.textContent = `Generated ${new Date().toLocaleString()} \u00b7 ${data.summary.total_personnel} personnel`;
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="9" class="empty-state">Couldn't load the report. Try refreshing.</td></tr>`;
    }
}

printBtn.addEventListener("click", () => window.print());

exportBtn.addEventListener("click", () => {
    if (!currentRows.length) return;
    const header = ["Full Name", "Username", "Status", "Total Checked Out", "Total Delivered", "Total Pending (Out)", "Total Returned/Not Delivered", "Returned to Office"];
    const lines = [header.join(",")];
    currentRows.forEach(r => {
        const row = [r.full_name, r.username, r.is_active ? "Active" : "Disabled", r.checked_out_total, r.delivered_total, r.pending, r.returned_total, r.returned_to_office_total]
            .map(v => `"${String(v).replace(/"/g, '""')}"`);
        lines.push(row.join(","));
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `delivery_personnel_report_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
});

loadPersonnelReport();
