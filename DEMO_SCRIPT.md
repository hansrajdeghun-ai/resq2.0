# resQ 2.0 — 3-minute demo script (voiceover + captions + edit notes)

Record against the live app: **https://resq-2-jrec.onrender.com**
Tip: hit **Reset demo** first. Keep two things open: `/demo` (4 phones on one screen)
and the role pages (`/customer`, `/area`, `/admin`). Screen-record at 1440×900.

Format below — **[time]** · *what you do on screen* · **CAPTION** (lower-third) · “voiceover”.

---

### 0:00–0:15 — The hook
*Open on the login screen (`/`), then the `/demo` 4-phone view.*
**CAPTION:** resQ 2.0 — service as the reason to buy
> “Electronics retail sells a box. The customer wants a working machine. resQ 2.0 closes
> that gap on WhatsApp — the AI agent does the routine work, and people act only on
> exceptions. Here are all four numbers on one screen.”

### 0:15–1:05 — The one job, end to end (the core)
*On `/demo`. Customer phone → type “install my AC” → tap a slot (Sun 10-12).*
**CAPTION:** One job · four roles · one thread
> “The customer books an installation. Notice the agent grounds it in the machine they
> actually own.”
*Owner phone → Accept → assign the suggested technician.*
> “The service owner accepts and assigns a technician — the customer never sees the
> partner’s name, only ‘from Reliance Digital’.”
*Field phone → On my way → Arrived → 📷 Scan serial → Work done.*
> “The technician travels, scans the serial at the door, and finishes — proof goes
> through the capture link, with time and place.”
*Customer phone → Yes.*
**CAPTION:** Serial → household, bound at the job
> “The customer confirms. The machine is now in their Reliance record, warranty started —
> and every step is an event in an append-only log.”

### 1:05–1:35 — AI-native (customer experience)
*Switch to `/customer`. Type “my AC is making a loud noise”.*
**CAPTION:** AI triage — grounded, in your language
> “Free text, not menus. The agent runs a brand self-check tailored to the symptom.”
*Type in Hindi, e.g. “AC thanda nahi kar raha”.*
> “And it replies in the customer’s language — here, Hindi.”
*Tap 🎤 Voice or 📷 Error code (optional).*
> “Voice notes and a photo of the error code work too.”

### 1:35–2:05 — Protective rules + exceptions (the jury’s attack surface)
*On `/demo` (or field), start a job, at the serial step tap “Wrong serial (test)”.*
**CAPTION:** Protective rules — enforced in code, not the model
> “The rules can’t be talked around. Scan the wrong serial and the job stops.”
*Owner phone → Decline a job twice.*
**CAPTION:** Exceptions — offer backup, then escalate + retry
> “Decline once, it goes to the backup partner. Decline again, it escalates to the area
> manager and offers the customer a new slot — no dead ends.”

### 2:05–2:35 — Humans on exceptions + monitoring
*On `/customer`, tap “talk to a person”.*
**CAPTION:** A person, only when it’s an exception
> “Ask for a person and the resQ desk takes over — the agent goes quiet, and the customer
> is told someone’s on it.”
*Switch to `/area` → Overview.*
**CAPTION:** Area manager — act only on what’s off
> “The area manager doesn’t get a dashboard to babysit. One screen: jobs by state, open
> exceptions, the live event log. Ask it ‘status R-1001’ or ‘late jobs’.”

### 2:35–2:55 — The registry + admin
*Switch to `/admin` → Overview, then Rate card.*
**CAPTION:** Prices from the card · config editable live
> “Prices only come from the rate card — editable here, never invented by the agent.
> Onboard partners and technicians, and download the full event log for proof to brands.”
*Briefly show `/customer` → My devices (the ledger).*
> “Underneath it all is the registry — every serial, bound to a household, with its
> warranty and service history.”

### 2:55–3:00 — Close
**CAPTION:** resQ 2.0 · WhatsApp · one weekend · AI-native
> “One job, four roles, zero dead ends — the registry of India’s machines, answered on
> WhatsApp.”

---

## Edit notes
- **Zoom/pan** into the active phone as each role acts (Ken Burns), so the viewer follows one
  conversation at a time on the `/demo` screen.
- **Lower-third captions** (the CAPTION lines) carry the story if played muted — judges often
  watch without sound first.
- **Pace:** the one-job loop (0:15–1:05) is the heart — spend the most time there.
- **Reset demo** before recording; if Render cold-starts, load a page once to warm it (~30s).
- Optional end card: the four pending creds (WhatsApp / checksum / Pub/Sub) as “live-week
  switches” to show it’s production-wired, not a toy.

## 30-second cut (if you need a teaser)
Hook (0:00–0:08) → one-job loop sped 2× (0:08–0:22) → wrong-serial block + Hindi reply
(0:22–0:30). Caption throughout: “AI does the routine, people handle exceptions.”
