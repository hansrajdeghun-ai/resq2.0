// Admin product: Overview · People (list + onboard per role) · Rate card & routing.
const LIST_FIELDS = { pincodes: 1, authority: 1, skills: 1 };
let peopleSub = "owner", routingSub = "keywords";

// per-role onboard form definition
const ONBOARD = {
  owner: { title: "🏪 Service owners", add: "service owner",
    fields: [["name", "Name (e.g. Frostline)", ""], ["pincodes", "Pincodes, comma-sep", ""],
             ["authority", "Authority (AC,TV or ALL)", "ALL"]], check: "is_backup", checkLabel: "backup partner" },
  field: { title: "🔧 Technicians", add: "technician",
    fields: [["name", "Name (e.g. Amit)", ""], ["partner_id", "Partner id (P-coolserve)", ""],
             ["skills", "Skills, comma-sep (AC install)", ""], ["pincode", "Pincode", ""]] },
  area: { title: "🧭 Area managers", add: "area manager",
    fields: [["name", "Area name (e.g. Bandra)", ""]] },
  customer: { title: "👤 Customers", add: "customer",
    fields: [["name", "Name (e.g. Mrs Iyer)", ""], ["phone", "Phone (optional)", ""],
             ["postal_code", "Pincode", ""]] },
};
const ROLE_ORDER = ["owner", "field", "area", "customer"];

// ─── section + sub nav ─────────────────────────────────────────────────────────
// highlight the active sub item in a section's subnav
function markSub(section, sub) {
  const nav = document.querySelector(`.subnav[data-for="${section}"]`);
  if (nav) nav.querySelectorAll("a").forEach((x) => x.classList.toggle("active", x.dataset.sub === sub));
}
function showSection(name) {
  document.querySelectorAll(".section").forEach((s) => s.classList.toggle("active", s.id === "sec-" + name));
  document.querySelectorAll("#sidenav a[data-section]").forEach((a) =>
    a.classList.toggle("active", a.dataset.section === name));
  if (name === "overview") loadOverview();
  if (name === "people") { peopleSub = "owner"; markSub("people", peopleSub); loadPeople(); }
  if (name === "ratecard") loadRateCard();
  if (name === "routing") { routingSub = "keywords"; markSub("routing", routingSub); loadRouting(); }
  location.hash = name;
}
document.querySelectorAll("#sidenav a[data-section]").forEach((a) =>
  (a.onclick = () => showSection(a.dataset.section)));
document.querySelectorAll(".subnav").forEach((sub) =>
  sub.querySelectorAll("a[data-sub]").forEach((a) => (a.onclick = async () => {
    const parent = sub.dataset.for;
    if (!document.getElementById("sec-" + parent).classList.contains("active")) {
      showSection(parent); await new Promise((r) => setTimeout(r, 60));
    }
    markSub(parent, a.dataset.sub);
    if (parent === "people") { peopleSub = a.dataset.sub; applyPeopleFilter(); }
    if (parent === "routing") { routingSub = a.dataset.sub; applyRoutingFilter(); }
  })));

function applyPeopleFilter() {
  document.querySelectorAll("#people [data-group]").forEach((el) =>
    el.style.display = (peopleSub === "all" || el.dataset.group === peopleSub) ? "" : "none");
}
function applyRoutingFilter() {
  document.querySelectorAll("#routing-editors [data-cfg]").forEach((el) =>
    el.style.display = (el.dataset.cfg === routingSub) ? "" : "none");
}

// ─── overview ─────────────────────────────────────────────────────────────────
async function loadOverview() {
  const [p, jobs, alerts, events] = await Promise.all([
    api("/api/personas"), api("/api/jobs"), api("/api/alerts"), api("/api/events?limit=12"),
  ]);
  const openJobs = jobs.jobs.filter((j) => !["Closed", "Cancelled"].includes(j.state)).length;
  const stats = [
    ["Customers", p.customer.length, "👤"], ["Owners", p.owner.length, "🏪"],
    ["Technicians", p.field.length, "🔧"], ["Area managers", p.area.length, "🧭"],
    ["Open jobs", openJobs, "🧾"], ["Exceptions", alerts.alerts.length, "⚠"],
  ];
  document.getElementById("stats").innerHTML = stats.map(([label, n, icon]) =>
    `<div class="stat"><div class="stat-ico">${icon}</div><div class="stat-n">${n}</div>
     <div class="stat-l">${label}</div></div>`).join("");
  document.getElementById("ov-events").innerHTML = events.events.map((e) =>
    `<div class="ev"><span class="type">${e.type}</span>
     <span class="meta">${e.job || e.machine || ""} · ${e.actor}</span></div>`).join("")
    || "<div class='muted'>No activity yet.</div>";
  const dl = document.getElementById("export-log");
  if (dl) dl.onclick = () => (window.location = "/api/export");
}

// ─── people: list + onboard per role ────────────────────────────────────────────
async function loadPeople() {
  const p = await api("/api/personas");
  const sub = (role, x) => role === "field" ? `${x.id}${x.partner ? " · " + x.partner : ""}`
    : role === "owner" ? `${x.id}${x.backup ? " · backup" : ""}` : x.id;
  const box = document.getElementById("people");
  box.innerHTML = ROLE_ORDER.map((role) => {
    const o = ONBOARD[role]; const list = p[role] || [];
    const rows = list.length ? `<table><tbody>${list.map((x) =>
      `<tr><td>${x.name}</td><td class="muted">${sub(role, x)}</td>
       <td style="text-align:right"><a class="btn" href="/${role}"
         onclick="localStorage.setItem('resq_persona_${role}', JSON.stringify(${JSON.stringify(x).replace(/"/g, "&quot;")}))">Open →</a></td></tr>`).join("")}</tbody></table>`
      : "<div class='muted'>None yet — add one below.</div>";
    const fields = o.fields.map(([n, ph, val]) =>
      `<input name="${n}" placeholder="${ph}" value="${val}">`).join("");
    const check = o.check ? `<label class="chk"><input type="checkbox" name="${o.check}"> ${o.checkLabel}</label>` : "";
    return `<div class="card" data-group="${role}"><h3>${o.title} · ${list.length}</h3>
      ${rows}
      <form class="inline-onboard" data-kind="${role}">
        <div class="onb-fields">${fields}${check}</div>
        <button class="btn primary">＋ Add ${o.add}</button><span class="out"></span>
      </form></div>`;
  }).join("");
  box.querySelectorAll("form[data-kind]").forEach(wireOnboard);
  applyPeopleFilter();
}

function wireOnboard(form) {
  form.onsubmit = async (e) => {
    e.preventDefault();
    const body = {};
    new FormData(form).forEach((v, k) => {
      if (form[k] && form[k].type === "checkbox") { body[k] = form[k].checked; return; }
      if (LIST_FIELDS[k]) body[k] = String(v).split(",").map((s) => s.trim()).filter(Boolean);
      else body[k] = v;
    });
    const out = form.querySelector(".out");
    try {
      const r = await api("/api/onboard/" + form.dataset.kind, { method: "POST", body: JSON.stringify(body) });
      out.className = "out ok"; out.textContent = `✓ ${r.id}`;
      setTimeout(loadPeople, 500);
    } catch { out.className = "out err"; out.textContent = "error"; }
  };
}

// ─── config editors ─────────────────────────────────────────────────────────────
async function saveConfig(key, value, msg) {
  const r = await api("/api/config/" + key, { method: "PUT", body: JSON.stringify({ value }) });
  msg.className = r.status === "saved" ? "ok" : "err";
  msg.textContent = r.status === "saved" ? "Saved — live now" : (r.detail || "Error");
  setTimeout(() => (msg.textContent = ""), 2500);
}
// a top toolbar: title on the left, "+ Add" + "Save" (+ status) on the right, one line
function cfgHead(title, addLabel, onAdd, onSave) {
  const head = document.createElement("div"); head.className = "cfg-head";
  const h = document.createElement("h3"); h.textContent = title;
  const actions = document.createElement("div"); actions.className = "cfg-actions";
  const add = document.createElement("button"); add.className = "btn"; add.textContent = addLabel; add.onclick = onAdd;
  const save = document.createElement("button"); save.className = "btn primary"; save.textContent = "Save";
  const msg = document.createElement("span"); msg.className = "cfg-msg"; save.onclick = () => onSave(msg);
  actions.append(add, save, msg); head.append(h, actions);
  return head;
}
function rateCardEditor(card) {
  const wrap = document.createElement("div"); wrap.className = "card cfg"; wrap.dataset.cfg = "rate_card"; wrap.style.gridColumn = "1/-1";
  const table = document.createElement("table");
  table.innerHTML = `<thead><tr><th>Category</th><th>Line</th><th>Label</th><th>Price ₹</th><th></th></tr></thead><tbody></tbody>`;
  const tb = table.querySelector("tbody");
  const addRow = (cat = "", line = "", label = "", price = "") => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td><input class="cell" value="${cat}" placeholder="AC"></td>
      <td><input class="cell" value="${line}" placeholder="gas_refill"></td>
      <td><input class="cell wide" value="${label}" placeholder="Gas refill"></td>
      <td><input class="cell num" type="number" value="${price}" placeholder="0"></td>
      <td><button class="icon-btn">✕</button></td>`;
    tr.querySelector(".icon-btn").onclick = () => tr.remove(); tb.appendChild(tr);
  };
  const save = (msg) => {
    const out = {};
    tb.querySelectorAll("tr").forEach((tr) => {
      const [cat, line, label, price] = [...tr.querySelectorAll("input")].map((i) => i.value.trim());
      if (!cat || !line) return;
      const C = cat.toUpperCase(); out[C] = out[C] || {};
      out[C][line] = { label, price: parseFloat(price) || 0 };
    });
    saveConfig("rate_card", out, msg);
  };
  wrap.appendChild(cfgHead("Rate card · prices the agent may quote", "+ Add line", () => addRow(), save));
  Object.entries(card).forEach(([cat, lines]) =>
    Object.entries(lines).forEach(([line, v]) => addRow(cat, line, v.label, v.price)));
  wrap.appendChild(table);
  return wrap;
}
function dictEditor(key, label, obj, keyHead, valHead) {
  const wrap = document.createElement("div"); wrap.className = "card cfg"; wrap.dataset.cfg = key;
  const table = document.createElement("table");
  table.innerHTML = `<thead><tr><th>${keyHead}</th><th>${valHead}</th><th></th></tr></thead><tbody></tbody>`;
  const tb = table.querySelector("tbody");
  const addRow = (k = "", v = "") => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td><input class="cell" value="${k.replace(/"/g, "&quot;")}"></td>
      <td><input class="cell wide" value="${String(v).replace(/"/g, "&quot;")}"></td>
      <td><button class="icon-btn">✕</button></td>`;
    tr.querySelector(".icon-btn").onclick = () => tr.remove(); tb.appendChild(tr);
  };
  const save = (msg) => {
    const out = {};
    tb.querySelectorAll("tr").forEach((tr) => {
      const [k, v] = [...tr.querySelectorAll("input")].map((i) => i.value);
      if (k.trim()) out[k.trim()] = v;
    });
    saveConfig(key, out, msg);
  };
  wrap.appendChild(cfgHead(label, "+ Add row", () => addRow(), save));
  Object.entries(obj).forEach(([k, v]) => addRow(k, v));
  wrap.appendChild(table);
  return wrap;
}
let _cfg = null;
async function _config() { if (!_cfg) _cfg = (await api("/api/config")).config; return _cfg; }

async function loadRateCard() {
  const c = await _config();
  const box = document.getElementById("ratecard-box"); box.innerHTML = "";
  box.appendChild(rateCardEditor(c.rate_card || {}));
}
async function loadRouting() {
  const c = await _config();
  const box = document.getElementById("routing-editors"); box.innerHTML = "";
  box.appendChild(dictEditor("keywords", "Intent keywords (offline routing)", c.keywords || {}, "Keyword", "Intent"));
  box.appendChild(dictEditor("self_check", "Self-check fallback", c.self_check || {}, "Category", "Message (offline)"));
  box.appendChild(dictEditor("likely_fault", "Pre-diagnosis fallback", c.likely_fault || {}, "Category", "Likely part (offline)"));
  applyRoutingFilter();
}

document.getElementById("reset").onclick = async () => {
  if (!confirm("Wipe all jobs/events and re-seed?")) return;
  await api("/api/reset", { method: "POST" });
  const b = document.getElementById("reset"); b.textContent = "✓ Reset";
  setTimeout(() => (b.textContent = "↺ Reset demo"), 1500);
  loadOverview();
};

// boot
(async () => {
  try { await api("/api/seed", { method: "POST" }); } catch {}
  showSection(location.hash.replace("#", "") || "overview");
})();
