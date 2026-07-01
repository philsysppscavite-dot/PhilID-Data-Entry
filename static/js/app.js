// Shared helpers used across pages.

async function fetchJSON(url, options = {}) {
    const res = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        throw new Error(data.error || "Something went wrong. Please try again.");
    }
    return data;
}

/**
 * Opens a small popup window with a printable time-in/time-out slip and
 * triggers the browser's print dialog. Used by the Scan and Search pages.
 * fields: { type, id_number, full_name, address, timestamp, scanned_by }
 */
function printCheckSlip(fields) {
    const w = window.open("", "_blank", "width=380,height=560");
    if (!w) {
        alert("Please allow popups to print the slip.");
        return;
    }
    const typeLabel = fields.type === "IN" ? "TIME-IN" : "TIME-OUT";
    const typeColor = fields.type === "IN" ? "#16794f" : "#ce1126";
    w.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
        <title>Slip - ${fields.id_number}</title>
        <style>
            * { box-sizing: border-box; }
            body { font-family: 'Courier New', monospace; padding: 18px; color: #111; }
            .center { text-align: center; }
            h1 { font-size: 15px; margin: 0 0 2px; letter-spacing: 0.04em; }
            .sub { font-size: 11px; color: #555; margin-bottom: 14px; }
            hr { border: none; border-top: 1px dashed #999; margin: 12px 0; }
            .type { font-size: 20px; font-weight: bold; color: ${typeColor}; margin: 6px 0; }
            .row { display: flex; justify-content: space-between; font-size: 12.5px; margin: 4px 0; gap: 10px; }
            .row .label { color: #555; }
            .row .value { text-align: right; font-weight: 600; }
            .footer { margin-top: 16px; font-size: 10.5px; color: #777; text-align: center; }
        </style>
        </head>
        <body onload="window.print(); setTimeout(() => window.close(), 300);">
            <div class="center">
                <h1>PHILSYS ID CHECK-IN SYSTEM</h1>
                <div class="sub">Official Visit Slip</div>
            </div>
            <hr>
            <div class="center type">${typeLabel}</div>
            <div class="row"><span class="label">ID Number</span><span class="value">${fields.id_number}</span></div>
            <div class="row"><span class="label">Name</span><span class="value">${fields.full_name}</span></div>
            <div class="row"><span class="label">Address</span><span class="value">${fields.address}</span></div>
            <div class="row"><span class="label">Date/Time</span><span class="value">${fields.timestamp}</span></div>
            <div class="row"><span class="label">Recorded by</span><span class="value">${fields.scanned_by || "-"}</span></div>
            <hr>
            <div class="footer">Please keep this slip for your records.</div>
        </body>
        </html>
    `);
    w.document.close();
}
