// 4-phone live demo — all four WhatsApp numbers on one screen (driving /api/sim).
const API = location.origin;
async function api(path, opts) {
  const r = await fetch(API + path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error(path + " " + r.status);
  return r.json();
}

const PHONES = {};
document.querySelectorAll(".phone").forEach((p) => {
  PHONES[p.dataset.id] = { el: p, role: p.dataset.role, lastSeq: 0, firstPoll: true };
  const note = document.createElement("div");
  note.className = "wa-note"; note.textContent = "WhatsApp screen — mock for the demo";
  p.querySelector(".chat").before(note);
});

// poll every phone's own inbox so the demo reflects chats done on the dedicated pages too
async function pollAll() {
  for (const [id, phone] of Object.entries(PHONES)) {
    try {
      const { messages } = await api(`/api/inbox/${encodeURIComponent(id)}?after=${phone.lastSeq}`);
      messages.forEach((m) => {
        phone.lastSeq = m.seq;
        if (!phone.firstPoll && m.role === "self") return;   // already echoed
        bubble(id, m.text, m.role === "self" ? "out" : "in", m.buttons);
      });
      phone.firstPoll = false;
    } catch {}
  }
}
function showTyping(phoneId) {
  const chat = PHONES[phoneId].el.querySelector(".chat");
  const t = document.createElement("div"); t.className = "bubble in typing";
  t.innerHTML = "<span></span><span></span><span></span>";
  chat.appendChild(t); chat.scrollTop = chat.scrollHeight; return t;
}

function bubble(phoneId, text, cls, buttons) {
  const phone = PHONES[phoneId];
  if (!phone) return;
  const chat = phone.el.querySelector(".chat");
  const b = document.createElement("div"); b.className = "bubble " + cls; b.textContent = text;
  chat.appendChild(b);
  if (buttons && buttons.length) {
    const row = document.createElement("div"); row.className = "btns";
    buttons.forEach((bt) => {
      const chip = document.createElement("button"); chip.className = "chip"; chip.textContent = bt.title;
      chip.onclick = () => drive(phone.role, phoneId, { button_id: bt.id, label: bt.title });
      row.appendChild(chip);
    });
    chat.appendChild(row);
  }
  chat.scrollTop = chat.scrollHeight;
}

const PROOF_ACTIONS = ["work_done", "part_fitted"];
async function drive(role, fromId, payload) {
  const echo = payload.text || payload.label;      // instant echo of the user's message
  if (echo) bubble(fromId, echo, "out");
  const typing = showTyping(fromId);
  if (payload.button_id && PROOF_ACTIONS.some((p) => payload.button_id.startsWith(p))) {
    payload.proof_link = "https://capture.resq/" + Date.now(); payload.place = "Andheri 400069";
  }
  try { await api("/api/sim", { method: "POST", body: JSON.stringify({ role, from_id: fromId, ...payload }) }); }
  catch (e) { console.error(e); typing.remove(); return; }
  typing.remove();
  await pollAll();   // renders replies from the shared inbox (self already echoed)
  refreshRail();
}

document.querySelectorAll(".phone").forEach((p) => {
  const input = p.querySelector("input");
  const send = () => { const t = input.value.trim(); if (!t) return; input.value = ""; drive(p.dataset.role, p.dataset.id, { text: t }); };
  p.querySelector(".send").onclick = send;
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
});

const quick = document.querySelector('.phone[data-role="customer"] .quick');
["install my AC", "not cooling", "moving house", "talk to a person"].forEach((t) => {
  const c = document.createElement("button"); c.className = "chip"; c.textContent = t;
  c.onclick = () => drive("customer", "cust-sharma", { text: t }); quick.appendChild(c);
});

// a short, human detail line from an event's payload
function eventDetail(p) {
  if (!p || typeof p !== "object") return "";
  const bits = [];
  if (p.slot) bits.push("slot " + p.slot);
  if (p.serial) bits.push("serial " + p.serial);
  if (p.technician_id) bits.push("tech " + p.technician_id);
  if (p.partner_id) bits.push("partner " + p.partner_id);
  if (p.rate != null) bits.push("₹" + p.rate);
  if (p.total != null) bits.push("₹" + p.total);
  if (p.likely) bits.push("likely " + p.likely);
  if (p.part) bits.push("part " + p.part);
  if (p.code) bits.push("code " + p.code);
  if (p.in_warranty != null) bits.push(p.in_warranty ? "in warranty" : "out of warranty");
  if (p.reason) bits.push(p.reason);
  if (p.cause) bits.push(p.cause);
  if (p.approver) bits.push("by " + p.approver);
  return bits.join(" · ");
}

async function refreshRail() {
  try {
    const { events } = await api("/api/events?limit=40");
    const box = document.getElementById("events"); box.innerHTML = "";
    events.forEach((e) => {
      const d = document.createElement("div"); d.className = "ev";
      const t = new Date(e.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      const detail = eventDetail(e.payload);
      d.innerHTML = `<div class="ev-row"><span class="type">${e.type}</span>
        <span class="meta">${e.job || e.machine || "—"} · ${e.actor} · ${t}</span></div>
        ${detail ? `<div class="ev-detail">${detail}</div>` : ""}`;
      box.appendChild(d);
    });
  } catch {}
  try {
    const l = await api("/api/ledger/cust-sharma");
    const box = document.getElementById("ledger"); box.innerHTML = "";
    if (!l.machines.length) box.innerHTML = '<div class="muted">No machines yet.</div>';
    l.machines.forEach((m) => {
      const inW = m.wty_end && new Date(m.wty_end) > new Date();
      const d = document.createElement("div"); d.className = "machine";
      d.innerHTML = `<div>${m.brand || ""} ${m.category || ""} · <code>${m.serial}</code></div>
        <div class="cover ${inW ? "in" : "out"}">${inW ? "in warranty" : "out of warranty"}</div>`;
      box.appendChild(d);
    });
  } catch {}
}

document.getElementById("reset").onclick = async () => {
  if (!confirm("Wipe all jobs/events and re-seed?")) return;
  await api("/api/reset", { method: "POST" });
  document.querySelectorAll(".chat").forEach((c) => (c.innerHTML = ""));
  Object.values(PHONES).forEach((p) => { p.lastSeq = 0; p.firstPoll = true; });
  pollAll(); refreshRail();
};

(async () => {
  try { const h = await api("/health"); document.getElementById("env").textContent = h.env + (h.use_mocks ? " · mocks" : " · live"); document.getElementById("conn").style.color = "var(--accent)"; }
  catch { document.getElementById("conn").style.color = "var(--bad)"; }
  try { await api("/api/seed", { method: "POST" }); } catch {}
  await pollAll(); refreshRail();
  setInterval(() => { pollAll(); refreshRail(); }, 3000);
})();
