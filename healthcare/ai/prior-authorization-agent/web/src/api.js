// REST client for the FastAPI backend. Role travels in the X-Role header (planv3: simple
// role switch, no auth yet). The active role is kept in localStorage.
const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// Roles map 1:1 to backend RBAC (clinician | reviewer | admin).
export function getRole() {
  return localStorage.getItem("role") || "clinician";
}
export function setRole(role) {
  localStorage.setItem("role", role);
}

async function req(path, { method = "GET", body } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: { "Content-Type": "application/json", "X-Role": getRole() },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  listCases: ({ status, q } = {}) => {
    const p = new URLSearchParams();
    if (status) p.set("status", status);
    if (q) p.set("q", q);
    const qs = p.toString();
    return req(`/cases${qs ? "?" + qs : ""}`);
  },
  getCase: (id) => req(`/cases/${id}`),
  run: (id) => req(`/cases/${id}/run`, { method: "POST" }),
  approve: (id) => req(`/cases/${id}/approve`, { method: "POST" }),
  sendBack: (id, note) => req(`/cases/${id}/send-back`, { method: "POST", body: { note } }),
  escalate: (id, reason) => req(`/cases/${id}/escalate`, { method: "POST", body: { reason } }),
};
