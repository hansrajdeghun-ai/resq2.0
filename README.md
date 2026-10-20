# resQ 2.0 — AI-native service on WhatsApp

Reliance Digital service, rebuilt so the agent does the routine work and people act only
on exceptions. One event-sourced engine serves three surfaces (WhatsApp first; Chrome
extension + app next). All 13 journeys (J1–J13), an append-only event log, a job state
machine, the 8 protective rules, 11 timers and the area-manager monitoring thread.

## Quick start

```bash
cd resq
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # Kapture UAT creds already filled in .env
python -m pytest -q             # run the test suite (51 tests)
python -m scripts.run_all_journeys   # drive all 13 journeys, print event trails
uvicorn app.main:app --host 0.0.0.0 --port 8000   # then open http://localhost:8000
```

Web app pages: `/` login · `/customer` consumer app · `/owner` `/field` `/area` role apps
· `/admin` console · `/demo` 4-phone demo. Hand-in: **Admin → Download event log** (or
`GET /api/export`). Deploy/share: see `DEPLOY.md`. Demo script: `DEMO.md`.

Behind a TLS-inspecting proxy (e.g. Check Point Harmony SASE on a Fynd Mac):
`bash scripts/make_ca_bundle.sh` then set `KAPTURE_CA_BUNDLE=resq_ca_bundle.pem` in `.env`.

Real Kapture read against UAT: `USE_MOCKS=0 python -m scripts.verify_kapture 7259678000`.

## Architecture

```
WhatsApp Cloud API ─webhook─┐
Chrome ext / app ─REST /api─┤→ engine/router (intent dispatch, take-over guard)
web demo  ─POST /api/sim ───┘        │
                                     ▼
          protective rules (code) → journeys (J1–J13) → events.log (append-only)
                                     │                        │
                                     ▼                        ▼
                         outbound messages          projections → ledger/jobs/…
   timers (APScheduler) ──┐                                   │
   Pub/Sub consumer ──────┼── emit events ─────────► monitoring (area-manager thread)
   Kapture REST (live) ───┘
```

- **Event-sourced**: every change is an immutable event (`app/events`); read models are
  projections. A correction is a new event.
- **Channel-agnostic**: `app/channels/*` are the only surface-specific code. `app/engine`,
  `app/journeys`, `app/rules`, `app/monitoring` never know the surface.
- **Protective rules in code** (`app/rules/protective.py`), never the LLM.
- **Agent** (`app/agent`): routes free text to journeys (Claude when `ANTHROPIC_API_KEY`
  is set, keyword fallback otherwise); journeys handle structured taps deterministically.

## Status

- ✅ All 13 journeys, 8 protective rules, state machine, 11-timer scheduler, monitoring,
  live Kapture reads, Pub/Sub consumer, WhatsApp webhook+send, REST API, demo + 39 tests.
- ⏳ External blockers (don't block building): WhatsApp tokens/numbers, Kapture **checksum
  key** (writes), Pub/Sub **SA key**, UPI provider, Anthropic key. See the plan + `.env`.
- 🗒️ Backlog: `BACKLOG.md` (admin-panel journey builder).

## Key paths

| Area | Path |
|------|------|
| Event log + projections | `app/events/` |
| Ledger / records | `app/models/` |
| State machine | `app/journeys/state_machine.py` |
| Protective rules | `app/rules/protective.py` |
| Journeys J1–J13 | `app/journeys/j*.py` (+ `shared_assign.py`, `shared_visit.py`) |
| Agent / routing | `app/agent/`, `app/engine/` |
| Kapture | `app/integrations/kapture/` |
| Pub/Sub | `app/integrations/pubsub/` |
| Monitoring | `app/monitoring/` |
| Timers | `app/timers/` |
| WhatsApp channel | `app/channels/whatsapp/` |
| REST API | `app/api/routes.py` |
