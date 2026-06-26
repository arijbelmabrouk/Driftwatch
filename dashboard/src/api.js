// api.js
// All calls to the FastAPI backend in one place.
// Components never call fetch() directly — they use these functions.

const BASE = "http://localhost:8000";

// ── Trackers ──────────────────────────────────────────────────────────────────

export async function getTrackers() {
  const res = await fetch(`${BASE}/trackers`);
  const data = await res.json();
  return data.trackers;
}

export async function createTracker({ topic, frequency, report_mode}) {
  const res = await fetch(`${BASE}/trackers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, frequency, report_mode}),
  });
  const data = await res.json();
  return data.tracker;
}

export async function deleteTracker(trackerId) {
  await fetch(`${BASE}/trackers/${trackerId}`, { method: "DELETE" });
}

// ── Pipeline ──────────────────────────────────────────────────────────────────

export async function runTracker(trackerId) {
  const res = await fetch(`${BASE}/trackers/${trackerId}/run`, {
    method: "POST",
  });
  return await res.json();
}

// ── Reports ───────────────────────────────────────────────────────────────────

export async function getLatestReport(trackerId) {
  const res = await fetch(`${BASE}/trackers/${trackerId}/report`);
  if (res.status === 404) return null;
  const data = await res.json();
  return data;
}

// ── Ask bar ───────────────────────────────────────────────────────────────────

export async function askAboutReport(trackerId, question) {
  const res = await fetch(`${BASE}/trackers/${trackerId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const data = await res.json();
  return data.answer;
}