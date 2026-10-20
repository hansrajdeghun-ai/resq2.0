// Shared helpers for all resQ web pages.
const API = location.origin;

async function api(path, opts) {
  const r = await fetch(API + path, {
    headers: { "Content-Type": "application/json" }, ...opts,
  });
  if (!r.ok) throw new Error(path + " " + r.status);
  return r.json();
}

async function uploadFile(path, file, extra) {
  const fd = new FormData();
  fd.append("file", file);
  if (extra) Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
  const r = await fetch(API + path, { method: "POST", body: fd });
  return r.json();
}

// per-role persona (mock login), stored separately so each role page/tab can be a
// different person at once.
function getPersona(role) {
  try { return JSON.parse(localStorage.getItem("resq_persona_" + role)); }
  catch { return null; }
}
function setPersona(role, persona) {
  localStorage.setItem("resq_persona_" + role, JSON.stringify(persona));
}

const ROLE_META = {
  customer: { icon: "👤", label: "Customer" },
  owner: { icon: "🏪", label: "Service owner" },
  field: { icon: "🔧", label: "Field technician" },
  area: { icon: "🧭", label: "Area manager" },
};

async function sim(role, fromId, payload) {
  return api("/api/sim", {
    method: "POST",
    body: JSON.stringify({ role, from_id: fromId, ...payload }),
  });
}
