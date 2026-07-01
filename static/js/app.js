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
