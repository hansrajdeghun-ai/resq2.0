# resQ 2.0 — Backlog (not yet scheduled)

Deferred items captured during the build. Pull into the active plan when ready.

## Admin panel: add new forms/journeys dynamically
- **Ask (2026-10-20):** From the admin panel (Chrome extension staff console / admin UI)
  we should be able to **add a new form** — i.e. define a new journey/intent flow
  without a code change.
- **Shape:** a config-driven journey builder. A journey = a sequence of steps
  (message + buttons/list + the event it emits + the next intent). Store journey
  definitions as data (DB/JSON); the router loads registered intents from both code
  handlers and these admin-defined definitions.
- **Why it fits:** our engine is already event-sourced and intent-routed, so a
  declarative journey spec can drive the same `Ctx.emit` / reply primitives.
- **Status:** backlog — do NOT start yet (per user, 2026-10-20).
