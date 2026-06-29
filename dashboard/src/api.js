// api.js
// All calls to the FastAPI backend in one place.
// Components never call fetch() directly — they use these functions.

const BASE = "http://localhost:8000";

function getToken() {
  return localStorage.getItem("driftwatch_token");
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  });

  const text = await res.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!res.ok) {
    throw new Error(data.detail || "Request failed");
  }

  return data;
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function registerUser(email, password) {
  return request("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function loginUser(email, password) {
  return request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function getCurrentUser() {
  return request("/auth/me");
}

// ── Trackers ──────────────────────────────────────────────────────────────────

export async function getTrackers() {
  const data = await request("/trackers");
  return data.trackers;
}

export async function createTracker({ topic, frequency, report_mode }) {
  const data = await request("/trackers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, frequency, report_mode }),
  });
  return data.tracker;
}

export async function deleteTracker(trackerId) {
  await request(`/trackers/${trackerId}`, { method: "DELETE" });
}

// ── Pipeline ──────────────────────────────────────────────────────────────────

export async function runTracker(trackerId) {
  return request(`/trackers/${trackerId}/run`, { method: "POST" });
}

// ── Reports ───────────────────────────────────────────────────────────────────

export async function getLatestReport(trackerId) {
  try {
    return await request(`/trackers/${trackerId}/report`);
  } catch (error) {
    if (error.message === "No reports found for this period. Run the tracker first.") {
      return null;
    }
    throw error;
  }
}

// ── Ask bar ───────────────────────────────────────────────────────────────────

export async function askAboutReport(trackerId, question) {
  const data = await request(`/trackers/${trackerId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  return data.answer;
}