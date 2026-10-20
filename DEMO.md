# resQ 2.0 — demo runbook (deployed)

**Live app:** https://resq-2-jrec.onrender.com
(Free tier may cold-start — open the base URL once and wait ~30s before recording.)

> **Reset first, every time.** Open https://resq-2-jrec.onrender.com/demo and click
> **↺ Reset demo** (top-right). This wipes jobs/events and re-seeds the demo household,
> partner and technician so every run starts clean.

## Direct links (open each in its own tab)
| Page | Link |
|---|---|
| Login (pick any persona) | https://resq-2-jrec.onrender.com/ |
| 👤 Customer app | https://resq-2-jrec.onrender.com/customer |
| 🏪 Service owner | https://resq-2-jrec.onrender.com/owner |
| 🔧 Field technician | https://resq-2-jrec.onrender.com/field |
| 🧭 Area manager | https://resq-2-jrec.onrender.com/area |
| 📱 4-phone demo (all roles on one screen) | https://resq-2-jrec.onrender.com/demo |
| ⚙ Admin · Overview | https://resq-2-jrec.onrender.com/admin#overview |
| ⚙ Admin · People (list + onboard) | https://resq-2-jrec.onrender.com/admin#people |
| ⚙ Admin · Rate card | https://resq-2-jrec.onrender.com/admin#ratecard |
| ⚙ Admin · Routing & diagnosis | https://resq-2-jrec.onrender.com/admin#routing |

For the fastest, cleanest demo use **`/demo`** — all four WhatsApp numbers are on one
screen, so you don't switch tabs mid-journey.

---

## 3-minute script — step by step
Each row: **[time]** · **Open** (link) · **Do** · **Caption** (on-screen) · **Say** · **Expect**.

### 0:00–0:15 — Hook
- **Open:** https://resq-2-jrec.onrender.com/ then https://resq-2-jrec.onrender.com/demo
- **Caption:** resQ 2.0 — service as the reason to buy
- **Say:** "Electronics retail sells a box; the customer wants a working machine. resQ 2.0
  closes that gap on WhatsApp — the AI does the routine work, people act only on exceptions.
  Here are all four numbers on one screen."
- **Expect:** login grid, then the 4 phones.

### 0:15–1:05 — One job, end to end (the core)
- **Open:** https://resq-2-jrec.onrender.com/demo
- **Do (Customer phone):** type `install my AC` → tap **Sun 10-12**.
  - **Expect:** "Your Samsung AC is ready to install" → "Booked for Sun 10-12".
  - **Say:** "The customer books — grounded in the machine they actually own."
- **Do (Service owner phone):** tap **Accept** → tap **Ravi · suggested**.
  - **Expect:** customer sees "Ravi from Reliance Digital will install…"; technician gets a job card.
  - **Say:** "The owner accepts and assigns — the customer only ever sees 'from Reliance Digital'."
- **Do (Field phone):** **On my way** → **Arrived** → **📷 Scan serial** → **Work done**.
  - **Expect:** "Serial matches", then "Is your AC working well?"
  - **Say:** "The technician travels, scans the serial at the door, finishes — proof via the capture link."
- **Do (Customer phone):** tap **Yes**.
  - **Caption:** Serial → household, bound at the job
  - **Say:** "Confirmed. The AC is in their Reliance record, warranty started — every step an event."

### 1:05–1:35 — AI-native (customer experience)
- **Open:** https://resq-2-jrec.onrender.com/customer → tap **Chat** (bottom nav)
- **Do:** type `my AC is making a loud noise`.
  - **Say:** "Free text, not menus — a self-check tailored to the symptom."
- **Do:** type in Hindi, e.g. `AC thanda nahi kar raha`.
  - **Caption:** AI triage — grounded, in your language
  - **Say:** "And it replies in the customer's language."
- **Do:** tap **🎤 Voice** or **📷 Error code** (optional).
  - **Say:** "Voice notes and a photo of the error code work too."

### 1:35–2:05 — Protective rules + exceptions (the jury's attack surface)
- **Open:** https://resq-2-jrec.onrender.com/demo (reset, then run the loop to the Field "Arrived" step)
- **Do (Field phone):** tap **Wrong serial (test)**.
  - **Caption:** Protective rules — enforced in code, not the model
  - **Expect:** "Serial does not match. The job is stopped."
  - **Say:** "The rules can't be talked around — the wrong serial stops the job."
- **Do (Service owner phone):** on a fresh booking, tap **Decline** twice.
  - **Caption:** Exceptions — backup, then escalate + retry
  - **Expect:** first decline → backup offer; second → area alert + customer gets new slots.
  - **Say:** "Decline once → backup partner. Decline again → escalate and offer the customer a new slot. No dead ends."

### 2:05–2:35 — Humans on exceptions + monitoring
- **Open:** https://resq-2-jrec.onrender.com/customer → **Chat** → type `talk to a person`.
  - **Caption:** A person, only when it's an exception
  - **Expect:** "A person from the resQ desk will reply…"; the agent goes quiet.
  - **Say:** "Ask for a person and the resQ desk takes over — the agent stays quiet."
- **Open:** https://resq-2-jrec.onrender.com/area (Overview is the default)
  - **Caption:** Area manager — act only on what's off
  - **Do:** show the **pie chart** + stats; click **Chat**, type `status R-1001`, then `late jobs`.
  - **Say:** "The area manager gets one screen — jobs by state, exceptions, the live event log — and answers 'status R-1001' or 'late jobs'."

### 2:35–2:55 — The registry + admin
- **Open:** https://resq-2-jrec.onrender.com/admin#ratecard
  - **Caption:** Prices from the card · config editable live
  - **Say:** "Prices only come from the rate card — editable here, never invented by the agent."
- **Open:** https://resq-2-jrec.onrender.com/admin#people
  - **Say:** "Onboard partners and technicians, and download the full event log for proof to brands."
- **Open:** https://resq-2-jrec.onrender.com/admin#overview → click **⬇ Download event log**.
- **Open:** https://resq-2-jrec.onrender.com/customer → **My devices**
  - **Say:** "Underneath it all is the registry — every serial, bound to a household, with its warranty and history."

### 2:55–3:00 — Close
- **Caption:** resQ 2.0 · WhatsApp · one weekend · AI-native
- **Say:** "One job, four roles, zero dead ends — the registry of India's machines, answered on WhatsApp."

---

## Editing notes
- **Zoom/pan** into the active phone on `/demo` as each role acts (follow one conversation at a time).
- **Lower-third captions** carry the story if played muted — judges often watch sound-off first.
- Spend the most time on the **one-job loop (0:15–1:05)** — it's the heart.
- Optional **end card**: the live-week switches (WhatsApp token · Kapture checksum key ·
  Pub/Sub SA) to show it's production-wired, not a toy.

## 30-second teaser cut
Hook (0:00–0:08) → one-job loop sped 2× (0:08–0:22) → wrong-serial block + Hindi reply
(0:22–0:30). Caption throughout: "AI does the routine; people handle exceptions."

---

## Hand-in checklist
- **Live app:** https://resq-2-jrec.onrender.com
- **Repo:** https://github.com/hansrajdeghun-ai/resq2.0
- **Test-evidence PDF (real screenshots of every journey):** `resQ_2.0_Submission.pdf`
- **Event-log export:** Admin → **Download event log** (or `GET /api/export`)
- **All 13 journeys proven:** `python -m scripts.run_all_journeys`
- **Tests:** `python -m pytest -q` (55 passing)
- **3-minute recording:** follow the script above
