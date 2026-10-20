// Mock login: list every persona by role; pick one -> store + go to that role page.
(async () => {
  const stats = [["13", "journeys"], ["4", "WhatsApp roles"], ["8", "protective rules"], ["1", "agent"]];
  document.getElementById("hero-stats").innerHTML = stats.map(([n, l]) =>
    `<div class="hstat"><span class="hstat-n">${n}</span><span class="hstat-l">${l}</span></div>`).join("");
  try { await api("/api/seed", { method: "POST" }); } catch {}
  let personas;
  try { personas = await api("/api/personas"); }
  catch { document.getElementById("roles").innerHTML = "<p class='muted'>Backend not reachable.</p>"; return; }

  const box = document.getElementById("roles");
  box.innerHTML = "";
  ["customer", "owner", "field", "area"].forEach((role) => {
    const meta = ROLE_META[role];
    const card = document.createElement("div");
    card.className = "login-card";
    card.innerHTML = `<h3>${meta.icon} ${meta.label}</h3>`;
    const list = document.createElement("div");
    list.className = "login-list";
    (personas[role] || []).forEach((p) => {
      const b = document.createElement("button");
      b.className = "persona";
      const sub = p.partner ? ` · ${p.partner}` : (p.backup ? " · backup" : "");
      b.innerHTML = `<span>${p.name}</span><small>${p.id}${sub}</small>`;
      b.onclick = () => { setPersona(role, p); location.href = "/" + role; };
      list.appendChild(b);
    });
    if (!(personas[role] || []).length) {
      const e = document.createElement("div"); e.className = "muted"; e.textContent = "none — add in Admin";
      list.appendChild(e);
    }
    card.appendChild(list);
    box.appendChild(card);
  });
})();
