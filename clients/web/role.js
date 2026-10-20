// Owner / Field / Area — sectioned app shell (left sidebar sections, like admin).
const ROLE = location.pathname.replace(/\//g, "") || "owner";
let persona = getPersona(ROLE);
let lastSeq = 0;

const SECTIONS = {
  owner: [["overview", "▦ Overview"], ["chat", "💬 Chat"], ["offers", "🧾 Job offers"], ["techs", "🔧 Technicians"], ["statement", "📄 Statement"]],
  field: [["overview", "▦ Overview"], ["chat", "💬 Chat"], ["today", "🧾 Today's jobs"], ["earnings", "💰 Earnings"], ["pos", "🏪 Store counter"]],
  area: [["overview", "▦ Overview"], ["chat", "💬 Chat"], ["exceptions", "⚠ Exceptions"], ["jobs", "🧾 Jobs"], ["actions", "📝 Action register"], ["digest", "📊 Digest"]],
};
const STATE_COLORS = {
  Requested: "#8795A8", Promised: "#E8820E", Assigned: "#3b82f6", EnRoute: "#6366f1",
  OnSite: "#0ea5e9", WorkDone: "#14b8a6", Confirmed: "#13855A", Closed: "#15935E",
  WaitingForPart: "#f59e0b", WaitingForApproval: "#a855f7", Cancelled: "#CF3D3D",
  WithBrand: "#64748b", Revisit: "#ef4444",
};
const PANEL_META = {
  overview: ["Overview", "Your snapshot. Tap a slice or a card to dive in."],
  offers: ["Job offers", "Jobs offered to you. Accept to assign a technician."],
  techs: ["Technicians", "Your field technicians. Add more in Admin → People."],
  statement: ["Statement", "What is payable to you — after the customer confirms + cooling."],
  today: ["Today's jobs", "Jobs assigned to you. Tap a card for its timeline."],
  earnings: ["Earnings", "What you have earned — paid after the cooling period."],
  pos: ["Store counter", "Bind a serial to a household at the till and send the WhatsApp opt-in."],
  exceptions: ["Exceptions", "Act only on these. The agent handles everything else."],
  jobs: ["Jobs", "Every job and its state. Tap a row for the timeline."],
  actions: ["Action register", "Every agent suggestion, with Accept / Reject."],
  digest: ["Digest", "The 8am / 6pm summary."],
};

// ─── chat ───────────────────────────────────────────────────────────────────
function bubble(text, cls, buttons) {
  const chat = document.getElementById("chat");
  const b = document.createElement("div"); b.className = "bubble " + cls; b.textContent = text;
  chat.appendChild(b);
  if (buttons && buttons.length) {
    const row = document.createElement("div"); row.className = "btns";
    buttons.forEach((bt) => {
      const chip = document.createElement("button"); chip.className = "chip"; chip.textContent = bt.title;
      chip.onclick = () => send({ button_id: bt.id, label: bt.title });
      row.appendChild(chip);
    });
    chat.appendChild(row);
  }
  chat.scrollTop = chat.scrollHeight;
}
const PROOF = ["work_done", "part_fitted"];
let firstPoll = true;
function showTyping() {
  const chat = document.getElementById("chat");
  const t = document.createElement("div"); t.className = "bubble in typing";
  t.innerHTML = "<span></span><span></span><span></span>";
  chat.appendChild(t); chat.scrollTop = chat.scrollHeight; return t;
}
async function send(payload) {
  const echo = payload.text || payload.label;
  if (echo) bubble(echo, "out");
  const typing = showTyping();
  if (payload.button_id && PROOF.some((p) => payload.button_id.startsWith(p))) {
    payload.proof_link = "https://capture.resq/" + Date.now(); payload.place = "Andheri 400069";
  }
  try { await sim(ROLE, persona.id, payload); } catch (e) { console.error(e); }
  typing.remove();
  await pollInbox(); if (currentSec !== "chat") renderPanel(currentSec);
}
let polling = false;
const seen = new Set();
async function pollInbox() {
  if (!persona || polling) return;                   // lock: no overlapping polls (no dupes)
  polling = true;
  try {
    const { messages } = await api(`/api/inbox/${encodeURIComponent(persona.id)}?after=${lastSeq}`);
    messages.forEach((m) => {
      lastSeq = m.seq;
      if (seen.has(m.seq)) return;                    // already rendered — never twice
      seen.add(m.seq);
      if (!firstPoll && m.role === "self") return;
      bubble(m.text, m.role === "self" ? "out" : "in", m.buttons);
    });
    firstPoll = false;
  } catch {} finally { polling = false; }
}

// ─── timelines + cards ────────────────────────────────────────────────────────
async function jobTimeline(jobId) {
  const { events } = await api("/api/events?job=" + jobId);
  return `<div class="timeline">${events.map((e) =>
    `<div class="tl"><span class="tl-dot"></span><span class="tl-type">${e.type}</span>
     <span class="tl-at">${new Date(e.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span></div>`).join("")}</div>`;
}
function jobCardsHtml(list, empty) {
  return list.length ? list.map((j) =>
    `<div class="jobcard" data-job="${j.id}"><div class="jobcard-top"><code>${j.id}</code>
      <span class="state">${j.state}</span></div>
      <div class="muted">${j.type}${j.slot ? " · " + j.slot : ""} · tap for timeline</div></div>`).join("")
    : `<div class="muted">${empty}</div>`;
}
function wireJobCards(root) {
  root.querySelectorAll(".jobcard").forEach((el) => el.onclick = async () => {
    if (el.querySelector(".timeline")) { el.querySelector(".timeline").remove(); return; }
    el.insertAdjacentHTML("beforeend", await jobTimeline(el.dataset.job));
  });
}

// ─── panel renderers ──────────────────────────────────────────────────────────
async function renderPanel(name) {
  const panel = document.getElementById("panel");
  const [title, lead] = PANEL_META[name] || [name, ""];
  document.getElementById("panel-title").textContent = title;
  document.getElementById("panel-lead").textContent = lead;
  panel.innerHTML = "";
  if (name === "overview") {
    const [{ jobs }, al, p, ev] = await Promise.all([
      api("/api/jobs"), api("/api/alerts"), api("/api/personas"), api("/api/events?limit=10")]);
    let mine = jobs, jobSec = "jobs";
    if (ROLE === "owner") { mine = jobs.filter((j) => j.partner === persona.id); jobSec = "offers"; }
    if (ROLE === "field") { mine = jobs.filter((j) => j.technician === persona.id); jobSec = "today"; }
    const open = mine.filter((j) => !["Closed", "Cancelled"].includes(j.state)).length;
    const done = mine.filter((j) => ["Confirmed", "Closed"].includes(j.state)).length;
    const stats = [["Open jobs", open, jobSec], ["Done", done, jobSec], ["Exceptions", al.alerts.length, "exceptions"]];
    if (ROLE === "area") stats.push(["Technicians", p.field.length, null]);
    if (ROLE === "owner") stats.push(["My technicians", p.field.filter((t) => t.partner === persona.id).length, "techs"]);
    // jobs-by-state pie
    const byState = {}; mine.forEach((j) => (byState[j.state] = (byState[j.state] || 0) + 1));
    const data = Object.entries(byState).map(([s, v]) => ({ label: s, value: v, color: STATE_COLORS[s] || "#94a3b8", sec: jobSec }));
    const total = data.reduce((s, d) => s + d.value, 0) || 1; let acc = 0;
    const stops = data.map((d) => { const f = acc / total * 100; acc += d.value; return `${d.color} ${f}% ${acc / total * 100}%`; }).join(",");
    const legend = data.map((d) => `<button class="legend" data-sec="${d.sec}"><span class="ldot" style="background:${d.color}"></span>${d.label}<b>${d.value}</b></button>`).join("") || "<div class='muted'>No jobs yet.</div>";
    const quick = (SECTIONS[ROLE] || []).filter(([s]) => !["overview", "chat"].includes(s))
      .map(([s, lbl]) => `<button class="ql" data-sec="${s}">${lbl} →</button>`).join("");
    panel.innerHTML = `
      <div class="stats">${stats.map(([l, n, sec]) => `<button class="stat ${sec ? "stat-link" : ""}" ${sec ? `data-sec="${sec}"` : ""}>
        <div class="stat-n">${n}</div><div class="stat-l">${l}</div></button>`).join("")}</div>
      <div class="ov-grid">
        <div class="card"><h3>Jobs by state</h3>
          <div class="pie-wrap"><div class="pie" style="background:conic-gradient(${stops})"></div>
          <div class="legend-list">${legend}</div></div></div>
        <div class="card"><h3>Quick links</h3><div class="ql-list">${quick}</div></div>
      </div>
      <div class="card"><h3>Recent activity</h3><div class="events">${ev.events.map((e) =>
        `<div class="ev"><div class="ev-row"><span class="type">${e.type}</span>
         <span class="meta">${e.job || e.machine || "—"} · ${e.actor}</span></div></div>`).join("") || "<div class='muted'>No activity yet.</div>"}</div></div>`;
    panel.querySelectorAll("[data-sec]").forEach((el) => el.onclick = () => showSec(el.dataset.sec));
    return;
  }
  if (name === "offers" || name === "today") {
    const { jobs } = await api("/api/jobs");
    const mine = jobs.filter((j) => (name === "today" ? j.technician : j.partner) === persona.id);
    panel.innerHTML = `<div class="card">${jobCardsHtml(mine, "Nothing yet.")}</div>`;
    wireJobCards(panel);
  } else if (name === "techs") {
    const p = await api("/api/personas");
    const techs = p.field.filter((t) => t.partner === persona.id);
    panel.innerHTML = `<div class="card">${techs.length ? techs.map((t) =>
      `<div class="machine">${t.name}<div class="cover ${t.approved ? "in" : "out"}">${t.approved ? "active" : "pending"}</div></div>`).join("")
      : "<div class='muted'>None yet — add in Admin → People.</div>"}</div>`;
  } else if (name === "statement" || name === "earnings") {
    const { jobs } = await api("/api/jobs");
    const key = name === "earnings" ? "technician" : "partner";
    const mine = jobs.filter((j) => j[key] === persona.id);
    const done = mine.filter((j) => ["Confirmed", "Closed"].includes(j.state)).length;
    const amt = name === "earnings" ? done * 350 : mine.filter((j) => j.state === "Confirmed").reduce((s, j) => s + (j.rate || 1500), 0);
    panel.innerHTML = `<div class="stats"><div class="stat"><div class="stat-n">${mine.length}</div><div class="stat-l">jobs</div></div>
      <div class="stat"><div class="stat-n">${done}</div><div class="stat-l">done</div></div>
      <div class="stat"><div class="stat-n">₹${amt.toLocaleString("en-IN")}</div><div class="stat-l">payable after cooling</div></div></div>`;
  } else if (name === "pos") {
    panel.innerHTML = `<div class="card" style="max-width:460px">
      <label class="pos-l">Customer id<input class="cell" id="pos-cust" value="cust-sharma"></label>
      <label class="pos-l">Serial / IMEI<input class="cell" id="pos-serial" value="SN-NEW-9001"></label>
      <label class="pos-l">Product / model<input class="cell" id="pos-model" value="Samsung 1.5T Split AC"></label>
      <label class="pos-l">Category<input class="cell" id="pos-cat" value="AC"></label>
      <button class="btn primary" id="pos-send" style="margin-top:12px">Send WhatsApp opt-in</button>
      <div class="muted" id="pos-out" style="margin-top:8px"></div></div>`;
    panel.querySelector("#pos-send").onclick = () => {
      const c = panel.querySelector("#pos-cust").value.trim(), s = panel.querySelector("#pos-serial").value.trim(),
        cat = panel.querySelector("#pos-cat").value.trim() || "AC",
        model = panel.querySelector("#pos-model").value.trim();
      send({ button_id: `send_optin:${c}:${s}:${cat}:${model}`, label: `Opt-in sent · ${model || s}` });
      panel.querySelector("#pos-out").textContent = `Opt-in sent for ${s}. The customer can accept on their phone.`;
    };
  } else if (name === "exceptions") {
    const { alerts } = await api("/api/alerts");
    panel.innerHTML = `<div class="card alerts">${alerts.length ? alerts.map((a) =>
      `<div class="alert"><div><span class="cause">${a.cause}</span><br>${a.text}</div>
       <button class="btn primary" onclick="takeover('${a.job}')">${a.action || "take over"}</button></div>`).join("")
      : "<div class='muted'>No open alerts. The agent is handling everything.</div>"}</div>`;
  } else if (name === "jobs") {
    const { jobs } = await api("/api/jobs");
    panel.innerHTML = `<div class="card"><table><thead><tr><th>Job</th><th>State</th><th>Tech</th></tr></thead>
      <tbody>${jobs.map((j) => `<tr class="jobrow" data-job="${j.id}"><td>${j.id}</td>
      <td><span class="state">${j.state}</span></td><td>${j.technician || "—"}</td></tr>`).join("")}</tbody></table></div>`;
    panel.querySelectorAll(".jobrow").forEach((tr) => tr.onclick = async () => {
      const next = tr.nextElementSibling;
      if (next && next.classList.contains("tl-row")) { next.remove(); return; }
      const row = document.createElement("tr"); row.className = "tl-row";
      row.innerHTML = `<td colspan="3">${await jobTimeline(tr.dataset.job)}</td>`; tr.after(row);
    });
  } else if (name === "actions") {
    const { items } = await api("/api/action-register");
    panel.innerHTML = `<div class="card alerts">${items.length ? items.map((it) =>
      `<div class="alert"><div><span class="cause">${it.job || ""}</span><br>${it.suggestion}
       ${it.decision !== "pending" ? `<br><span class="muted">→ ${it.decision}</span>` : ""}</div>
       ${it.decision === "pending" ? `<div><button class="btn primary" onclick="decide('${it.id}','accept')">Accept</button>
       <button class="btn" onclick="decide('${it.id}','reject')" style="margin-left:6px">Reject</button></div>` : ""}</div>`).join("")
      : "<div class='muted'>No suggestions yet.</div>"}</div>`;
  } else if (name === "digest") {
    const d = await api("/api/digest");
    panel.innerHTML = `<div class="card"><div class="digest">${d.digest}</div></div>`;
  }
}
async function takeover(job) { await api("/api/takeover/" + job, { method: "POST" }); renderPanel("exceptions"); }
async function decide(id, decision) {
  const reason = decision === "reject" ? (prompt("Reason?") || "") : "accepted";
  await api("/api/action-register/" + id + "/decision", { method: "POST", body: JSON.stringify({ decision, reason }) });
  renderPanel("actions");
}

// ─── section switching ────────────────────────────────────────────────────────
let currentSec = "chat";
function showSec(name) {
  currentSec = name;
  document.getElementById("sec-chat").classList.toggle("active", name === "chat");
  document.getElementById("sec-panel").classList.toggle("active", name !== "chat");
  document.querySelectorAll("#viewnav a").forEach((a) => a.classList.toggle("active", a.dataset.sec === name));
  if (name === "chat") pollInbox(); else renderPanel(name);
}

// ─── composer per role ────────────────────────────────────────────────────────
function setupChat() {
  const quick = document.getElementById("quick"), hint = document.getElementById("hint");
  const chip = (t, fn) => { const b = document.createElement("button"); b.className = "chip"; b.textContent = t; b.onclick = fn; quick.appendChild(b); };
  if (ROLE === "field") {
    const i = document.createElement("input"); i.type = "file"; i.accept = "image/*"; i.style.display = "none";
    const b = document.createElement("button"); b.className = "chip"; b.textContent = "📷 Serial plate"; b.onclick = () => i.click();
    i.onchange = async () => {
      if (!i.files[0]) return;
      const { jobs } = await api("/api/jobs"); const job = (jobs.find((j) => j.state === "OnSite") || {}).id;
      const { value } = await uploadFile("/api/vision/serial", i.files[0], { hint: "SN-AC-4471" }); i.value = "";
      if (job) send({ button_id: `serial:${job}:${value || "SN-AC-4471"}` }); else bubble(`read: ${value || "?"} (no on-site job)`, "in");
    };
    quick.append(b, i);
    hint.textContent = "Tap job cards from the chat; snap the serial plate on site.";
  } else if (ROLE === "area") {
    ["status R-1001", "late jobs", "digest"].forEach((t) => chip(t, () => send({ text: t })));
    hint.textContent = "Ask for a status, or act on an alert in Exceptions.";
  } else {
    hint.textContent = "Accept/Decline job offers from the chat, or assign a technician.";
  }
  document.getElementById("send").onclick = () => {
    const i = document.getElementById("msg"); const t = i.value.trim(); if (!t) return; i.value = ""; send({ text: t });
  };
  document.getElementById("msg").addEventListener("keydown", (e) => { if (e.key === "Enter") document.getElementById("send").click(); });
}

// ─── boot ───────────────────────────────────────────────────────────────────
(async () => {
  try { await api("/api/seed", { method: "POST" }); } catch {}
  if (!persona) {
    try { const p = await api("/api/personas"); persona = (p[ROLE] || [])[0]; if (persona) setPersona(ROLE, persona); } catch {}
  }
  if (!persona) { location.href = "/"; return; }
  const meta = ROLE_META[ROLE];
  document.getElementById("roletag").textContent = meta.label;
  document.getElementById("whoami").textContent = `${meta.icon} ${persona.name}`;
  document.getElementById("whoid").textContent = persona.id;
  document.getElementById("phone-head").innerHTML = `${meta.icon} ${persona.name} <small>· ${meta.label}</small>`;

  // sidebar: this role's sections
  const vnav = document.getElementById("viewnav");
  vnav.innerHTML = '<div class="side-sec">' + meta.label + "</div>";
  (SECTIONS[ROLE] || SECTIONS.owner).forEach(([sec, label], idx) => {
    const a = document.createElement("a"); a.dataset.sec = sec; a.textContent = label;
    if (idx === 0) a.classList.add("active"); a.onclick = () => showSec(sec); vnav.appendChild(a);
  });
  document.getElementById("reset").onclick = async () => {
    if (!confirm("Wipe all jobs/events and re-seed?")) return;
    await api("/api/reset", { method: "POST" }); location.reload();
  };
  setupChat();
  try { await api("/health"); document.getElementById("conn").style.color = "var(--accent)"; } catch {}
  await pollInbox();
  showSec((SECTIONS[ROLE] || SECTIONS.owner)[0][0]);  // default to Overview
  // poll only the chat inbox (cross-page message delivery); panels refresh on
  // navigation/action, not on a timer — no auto-refresh of listings.
  setInterval(() => { pollInbox(); }, 3000);
})();
