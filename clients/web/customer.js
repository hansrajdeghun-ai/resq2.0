// Reliance resQ — customer consumer app. Home · All services · My devices · Chat.
// Tiles start a real journey by opening Chat (the WhatsApp mock) with the right message.
const ROLE = "customer";
let persona = getPersona("customer");
let lastSeq = 0;

// category -> message that triggers the right journey intent
// only Air Conditioner is live in this build; the rest show "Soon"
const REPAIR = [
  ["Air Conditioner", "❄️", "my AC needs repair", true],
  ["Washing Machine", "🧺", null, false],
  ["Water Purifier", "💧", null, false],
  ["Refrigerator", "🧊", null, false],
  ["LED TV", "📺", null, false],
  ["Air Cooler", "🌀", null, false],
];
const MAINT = [
  ["Split AC jet service", "💦", "book a service for my AC", true],
  ["Split AC dry service", "🧴", "book a service for my AC", true],
  ["Air Cooler service", "🌀", null, false],
];
const QUICK = [
  ["Book installation", "🔧", { text: "book installation" }],
  ["Buy care plan", "🛡️", { text: "care plan" }],
  ["Track service", "📍", { view: "devices" }],
  ["Talk to a person", "🧑‍💼", { text: "talk to a person" }],
];
const SERVICES = [
  ["Install a new machine", "🔧", "book installation"],
  ["Repair (in or out of warranty)", "🛠️", "my machine is not working"],
  ["Get the brand to repair it", "🏷️", "book with the brand"],
  ["House move — uninstall & reinstall", "🚚", "we are moving house"],
  ["Buy a care plan", "🛡️", "care plan"],
  ["Report dead-on-arrival", "📦", "my new product arrived dead"],
];

// ─── view switching ───────────────────────────────────────────────────────────
function showView(name) {
  document.querySelectorAll(".app-view").forEach((v) => v.classList.toggle("active", v.id === "v-" + name));
  document.querySelectorAll("#appnav button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  if (name === "devices") loadDevices();
  if (name === "chat") {
    pollInbox();
    const chat = document.getElementById("chat");
    setTimeout(() => { chat.scrollTop = chat.scrollHeight; }, 50);
  }
}

// ─── chat (WhatsApp mock) ──────────────────────────────────────────────────────
function bubble(text, cls, buttons) {
  const chat = document.getElementById("chat");
  const b = document.createElement("div"); b.className = "bubble " + cls; b.textContent = text;
  chat.appendChild(b);
  // a payment link (UPI) renders as a scannable QR
  const upi = (text.match(/upi:\/\/\S+/) || [])[0];
  if (upi) {
    const wrap = document.createElement("div"); wrap.className = "qr-wrap " + cls;
    wrap.innerHTML = `<img class="qr" alt="Scan to pay" src="/api/qr?data=${encodeURIComponent(upi)}">
      <div class="qr-cap">Scan with any UPI app to pay</div>`;
    chat.appendChild(wrap);
  }
  if (buttons && buttons.length) {
    const row = document.createElement("div"); row.className = "btns";
    buttons.forEach((bt) => {
      const c = document.createElement("button"); c.className = "chip"; c.textContent = bt.title;
      c.onclick = () => send({ button_id: bt.id, label: bt.title }); row.appendChild(c);
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
  const echo = payload.text || payload.label;   // show the user's message instantly
  if (echo) bubble(echo, "out");
  const typing = showTyping();
  if (payload.button_id && PROOF.some((p) => payload.button_id.startsWith(p))) {
    payload.proof_link = "https://capture.resq/" + Date.now(); payload.place = "Andheri 400069";
  }
  try { await sim(ROLE, persona.id, payload); } catch (e) { console.error(e); }
  typing.remove();
  await pollInbox();
}
async function pollInbox() {
  if (!persona) return;
  try {
    const { messages } = await api(`/api/inbox/${encodeURIComponent(persona.id)}?after=${lastSeq}`);
    messages.forEach((m) => {
      lastSeq = m.seq;
      if (!firstPoll && m.role === "self") return;   // already echoed optimistically
      bubble(m.text, m.role === "self" ? "out" : "in", m.buttons);
    });
    firstPoll = false;
  } catch {}
}
// open chat and send a message (used by tiles)
function chatSend(payload) { showView("chat"); send(payload); }

// ─── devices (ledger) ──────────────────────────────────────────────────────────
async function loadDevices() {
  const box = document.getElementById("devices");
  try {
    const l = await api("/api/ledger/" + persona.id);
    const machines = l.machines.map((m) => {
      const inW = m.wty_end && new Date(m.wty_end) > new Date();
      return `<div class="dev-card"><div class="dev-top"><b>${m.brand || ""} ${m.category || ""}</b>
        <span class="cover ${inW ? "in" : "out"}">${inW ? "in warranty" : "out of warranty"}</span></div>
        <code>${m.serial}</code></div>`;
    }).join("") || "<div class='muted'>No machines yet — they appear after your first delivery.</div>";
    const jobs = l.jobs.length ? l.jobs.map((j) =>
      `<div class="jobcard" data-job="${j.id}"><div class="jobcard-top"><code>${j.id}</code>
        <span class="state">${j.state}</span></div><div class="muted">${j.type} · tap for timeline</div></div>`).join("")
      : "<div class='muted'>No service jobs yet.</div>";
    box.innerHTML = `<div class="app-sec-head"><h3>Machines</h3></div>${machines}
      <div class="app-sec-head"><h3>Service jobs</h3></div>${jobs}`;
    box.querySelectorAll(".jobcard").forEach((el) => el.onclick = async () => {
      if (el.querySelector(".timeline")) { el.querySelector(".timeline").remove(); return; }
      const { events } = await api("/api/events?job=" + el.dataset.job);
      el.insertAdjacentHTML("beforeend", `<div class="timeline">${events.map((e) =>
        `<div class="tl"><span class="tl-dot"></span><span class="tl-type">${e.type}</span></div>`).join("")}</div>`);
    });
  } catch {}
}

// ─── render home + services ────────────────────────────────────────────────────
function renderHome() {
  const tile = (name, ico, msg, on, extra = "") => on
    ? `<button class="tile ${extra}" data-text="${msg}"><span class="tile-ico">${ico}</span><span>${name}</span></button>`
    : `<button class="tile ${extra} disabled"><span class="soon">Soon</span><span class="tile-ico">${ico}</span><span>${name}</span></button>`;
  document.getElementById("repair-tiles").innerHTML = REPAIR.map(([n, i, m, on]) => tile(n, i, m, on)).join("");
  document.getElementById("maint-tiles").innerHTML = MAINT.map(([n, i, m, on]) => tile(n, i, m, on, "tile-sm")).join("");
  document.getElementById("quick-actions").innerHTML = QUICK.map(([name, ico], i) =>
    `<button class="qa" data-qa="${i}"><span>${ico}</span>${name}</button>`).join("");
  document.getElementById("service-list").innerHTML = SERVICES.map(([name, ico, msg]) =>
    `<button class="service-item" data-text="${msg}"><span class="tile-ico">${ico}</span>
      <span class="service-name">${name}</span><span class="service-go">→</span></button>`).join("");

  document.querySelectorAll("[data-text]").forEach((el) =>
    el.onclick = () => chatSend({ text: el.dataset.text }));
  document.querySelectorAll("[data-qa]").forEach((el) => el.onclick = () => {
    const a = QUICK[+el.dataset.qa][2];
    if (a.view) showView(a.view); else chatSend(a);
  });
  document.querySelector(".app-cta").onclick = () => chatSend({ text: "talk to a person" });
}

// ─── composer + nav wiring ──────────────────────────────────────────────────────
function setupChat() {
  const quick = document.getElementById("quick");
  [["my AC is making a loud noise"], ["warranty is over, AC not cooling"], ["moving house"]]
    .forEach(([t]) => { const c = document.createElement("button"); c.className = "chip"; c.textContent = t;
      c.onclick = () => send({ text: t }); quick.appendChild(c); });
  const mk = (label, accept, handler) => {
    const i = document.createElement("input"); i.type = "file"; i.accept = accept; i.style.display = "none";
    const b = document.createElement("button"); b.className = "chip"; b.textContent = label;
    b.onclick = () => i.click(); i.onchange = () => { if (i.files[0]) handler(i.files[0]); i.value = ""; };
    quick.append(b, i);
  };
  mk("🎤 Voice", "audio/*", async (f) => {
    const { text } = await uploadFile("/api/voice", f);
    if (text) send({ text }); else bubble("(no transcript — add an OpenAI key)", "in");
  });
  mk("📷 Error code", "image/*", async (f) => {
    const { value } = await uploadFile("/api/vision/error_code", f, { hint: "E21" });
    send({ text: `my AC shows error ${value || "E21"}` });
  });
  document.getElementById("send").onclick = () => {
    const i = document.getElementById("msg"); const t = i.value.trim(); if (!t) return; i.value = ""; send({ text: t });
  };
  document.getElementById("msg").addEventListener("keydown", (e) => { if (e.key === "Enter") document.getElementById("send").click(); });
}

// ─── boot ───────────────────────────────────────────────────────────────────────
(async () => {
  try { await api("/api/seed", { method: "POST" }); } catch {}
  if (!persona) {
    try { const p = await api("/api/personas"); persona = (p.customer || [])[0]; if (persona) setPersona("customer", persona); } catch {}
  }
  if (!persona) { location.href = "/"; return; }
  document.getElementById("greet").textContent = persona.name;
  document.getElementById("hero-hi").textContent = `Namaste, ${persona.name} 👋`;
  document.getElementById("avatar").textContent = (persona.name || "U").split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();

  renderHome(); setupChat();
  document.querySelectorAll("#appnav button, [data-view]").forEach((b) =>
    b.dataset.view && (b.onclick = () => showView(b.dataset.view)));
  await pollInbox();
  setInterval(() => { if (document.getElementById("v-chat").classList.contains("active")) pollInbox(); }, 2500);
})();
