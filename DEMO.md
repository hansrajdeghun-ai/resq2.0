# resQ 2.0 — 3-minute demo

Open **http://localhost:8000** (or the deployed URL). The login screen lets you sign in
as any persona — open a few in separate tabs.

## The one-job loop (90 seconds) — the contest's core
1. **Customer** (`/customer`) → tap **Air Conditioner** (or type "install my AC") → a slot
   (e.g. Sun 10-12). The reply is grounded in the machine on the account.
2. **Service owner** (`/owner`) → the job offer arrives → **Accept** → assign the suggested
   technician. (Decline twice and watch it escalate + offer the customer a retry.)
3. **Field** (`/field`) → **On my way** → **Arrived** → **📷 Scan serial** → **Work done**
   (proof goes "through the capture link").
4. **Customer** → **Yes** → the AC is in their Reliance record, warranty started.
5. **Area manager** (`/area`) → **Overview**: pie chart, the job in state, the live event log.

## Show the differentiators (60 seconds)
- **Protective rules**: on Field, tap **"Wrong serial (test)"** → the job is stopped.
- **AI-native**: on Customer, type a symptom like *"my AC is making a loud noise"* → the
  agent returns a tailored self-check; type in **Hindi** → it replies in Hindi.
- **Price certainty**: out-of-warranty flow shows the visit charge before booking and the
  estimate before work; pay by **UPI QR** (scan it).
- **Human on exceptions**: Customer → **"talk to a person"** → the resQ desk takes over
  (`/area`); the agent goes quiet and acknowledges the customer.
- **Monitoring**: Area → *"status R-1001"*, *"late jobs"*, the 6pm **digest**.

## Everything at a glance (30 seconds)
- **Admin** (`/admin`) → Overview (counts), People (list + onboard), Rate card & Routing
  (edit prices/keywords live), **⬇ Download event log**.
- **4-phone demo** (`/demo`) → all four WhatsApp numbers on one screen.

## Hand-in checklist
- Running build: `uvicorn app.main:app` (or Docker / Render — see DEPLOY.md)
- Code repository: this folder
- Event-log export: Admin → **Download event log** (or `GET /api/export`)
- All 13 journeys proven: `python -m scripts.run_all_journeys`
- Tests: `python -m pytest -q` (44 passing)
- 3-minute recording: follow the loop above
