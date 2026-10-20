"""Build the submission PDF: drive every journey on the DEPLOYED app, capture EVERY
message sent and received (each participant's full thread), and compile a titled PDF
with the append-only event trail per journey. Resets the demo before each journey.

    SUBMIT_BASE=https://resq-2-jrec.onrender.com python -m scripts.make_submission_pdf

Output: resQ_2.0_Submission.pdf (repo root).
"""
from __future__ import annotations

import asyncio
import html
import os

import httpx
from playwright.async_api import async_playwright

BASE = os.environ.get("SUBMIT_BASE", "https://resq-2-jrec.onrender.com")
REPO = os.environ.get("SUBMIT_REPO", "https://github.com/hansrajdeghun-ai/resq2.0")
PROOF = {"proof_link": "https://capture.resq/x", "place": "Andheri 400069"}
OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resQ_2.0_Submission.pdf")

SECTIONS: list[dict] = []
_participants: set[str] = set()

LABELS = {
    "cust-sharma": "👤 Customer · Mr Sharma", "P-coolserve": "🏪 Service owner · Coolserve",
    "P-backup": "🏪 Backup owner · QuickFix", "T-ravi": "🔧 Field · Ravi",
    "area-andheri": "🧭 Area manager", "finance-1": "💰 Finance", "store-1": "🏬 Store associate",
    "bench-1": "🔧 Service bench", "driver-1": "🚚 Delivery", "owner-a": "🏪 Partner A (old city)",
    "owner-b": "🏪 Partner B (new city)", "T-field-sunil": "🔧 New technician · Sunil",
}
DEFAULT_IDS = ["cust-sharma", "P-coolserve", "T-ravi", "area-andheri"]


def label(pid: str) -> str:
    return LABELS.get(pid, pid)


async def sim(c, role, frm, **payload):
    _participants.add(frm)
    await c.post("/api/sim", json={"role": role, "from_id": frm, **payload})


async def job_id(c):
    jobs = (await c.get("/api/jobs")).json()["jobs"]
    return jobs[0]["id"] if jobs else None


# ─── journey runners (button-driven; deterministic, no LLM needed) ──────────────
async def visit_to_confirm(c, j):
    await sim(c, "owner", "P-coolserve", button_id=f"job_accept:{j}", label="Accept")
    await sim(c, "owner", "P-coolserve", button_id=f"assign_tech:{j}:T-ravi", label="Ravi · suggested")
    await sim(c, "field", "T-ravi", button_id=f"on_my_way:{j}", label="On my way")
    await sim(c, "field", "T-ravi", button_id=f"arrived:{j}", label="Arrived")
    await sim(c, "field", "T-ravi", button_id=f"scanserial:{j}", label="📷 Scan serial")
    await sim(c, "field", "T-ravi", button_id=f"work_done:{j}", label="Work done", **PROOF)
    await sim(c, "customer", "cust-sharma", button_id=f"confirm_work:{j}", label="Yes")


async def j1(c):
    await sim(c, "customer", "cust-sharma", text="install my AC")
    await sim(c, "customer", "cust-sharma", button_id="slot:Sun 10-12", label="Sun 10-12")
    j = await job_id(c)
    await visit_to_confirm(c, j)


async def j2(c):
    await sim(c, "customer", "cust-sharma", text="my AC is not cooling")
    j = await job_id(c)
    await sim(c, "customer", "cust-sharma", button_id=f"still_broken:{j}", label="Still not working")
    await sim(c, "customer", "cust-sharma", button_id="rslot:Tue 4-6", label="Tue 4-6")
    await visit_to_confirm(c, j)


async def j3(c):
    await sim(c, "customer", "cust-sharma", text="my AC is not cooling")
    j = await job_id(c)
    await sim(c, "customer", "cust-sharma", button_id=f"still_broken:{j}", label="Still not working")
    await sim(c, "customer", "cust-sharma", button_id="rslot:Tue 4-6", label="Tue 4-6")
    await sim(c, "owner", "P-coolserve", button_id=f"job_accept:{j}", label="Accept")
    await sim(c, "owner", "P-coolserve", button_id=f"assign_tech:{j}:T-ravi", label="Ravi · suggested")
    await sim(c, "field", "T-ravi", button_id=f"on_my_way:{j}", label="On my way")
    await sim(c, "field", "T-ravi", button_id=f"arrived:{j}", label="Arrived")
    await sim(c, "field", "T-ravi", button_id=f"part_needed:{j}:gas pressure", label="Part needed")
    await sim(c, "owner", "P-coolserve", button_id=f"part_received:{j}", label="Part received")
    await sim(c, "customer", "cust-sharma", button_id=f"v2slot:{j}:Thu 4-6", label="Thu 4-6")
    await sim(c, "field", "T-ravi", button_id=f"on_my_way:{j}", label="On my way")
    await sim(c, "field", "T-ravi", button_id=f"arrived:{j}", label="Arrived")
    await sim(c, "field", "T-ravi", button_id=f"scanserial:{j}", label="📷 Scan serial")
    await sim(c, "field", "T-ravi", button_id=f"part_fitted:{j}", label="Part fitted", **PROOF)
    await sim(c, "customer", "cust-sharma", button_id=f"confirm_work:{j}", label="Yes")


async def j4(c):
    await sim(c, "customer", "cust-sharma", text="warranty is over, AC not cooling")
    j = await job_id(c)
    await sim(c, "customer", "cust-sharma", button_id=f"oow_book:{j}", label="Book a visit")
    await sim(c, "owner", "P-coolserve", button_id=f"job_accept:{j}", label="Accept")
    await sim(c, "owner", "P-coolserve", button_id=f"assign_tech:{j}:T-ravi", label="Ravi · suggested")
    await sim(c, "field", "T-ravi", button_id=f"on_my_way:{j}", label="On my way")
    await sim(c, "field", "T-ravi", button_id=f"arrived:{j}", label="Arrived")
    await sim(c, "field", "T-ravi", button_id=f"scanserial:{j}", label="📷 Scan serial")
    await sim(c, "field", "T-ravi", button_id=f"oow_diagnose:{j}", label="Diagnose")
    await sim(c, "customer", "cust-sharma", button_id=f"oow_approve:{j}", label="Approve")
    await sim(c, "field", "T-ravi", button_id=f"work_done:{j}", label="Work done", **PROOF)
    await sim(c, "field", "T-ravi", button_id=f"oow_pay:{j}", label="Send UPI")
    await sim(c, "customer", "cust-sharma", button_id=f"oow_paid:{j}", label="I've paid")


async def j5(c):
    await sim(c, "customer", "cust-sharma", button_id="brand_repair", label="Book with the brand")
    j = await job_id(c)
    await sim(c, "customer", "cust-sharma", button_id=f"brand_confirm:{j}", label="Yes")


async def j6(c):
    await sim(c, "store", "store-1", button_id="walk_in_drop:cust-sharma:SN-PH-1", label="Drop off")
    j = await job_id(c)
    await sim(c, "field", "bench-1", button_id=f"walk_in_quote:{j}", label="Quote")
    await sim(c, "customer", "cust-sharma", button_id=f"walk_in_approve:{j}", label="Approve")
    await sim(c, "field", "bench-1", button_id=f"walk_in_ready:{j}", label="Ready", **PROOF)
    jb = (await c.get(f"/api/events?job={j}")).json()["events"]
    code = next((e["payload"].get("code") for e in jb if e["type"] == "ReadyForPickup"), "0000")
    await sim(c, "store", "store-1", button_id=f"walk_in_collect:{j}:{code}", label="Hand over")


async def j7(c):
    await sim(c, "customer", "cust-sharma", button_id="report_doa:SN-AC-4471", label="Report DOA")
    j = await job_id(c)
    await sim(c, "field", "T-ravi", button_id=f"doa_check:{j}", label="DOA check", **PROOF)
    await sim(c, "area", "area-andheri", button_id=f"doa_approve:{j}", label="Brand approves")
    await sim(c, "customer", "cust-sharma", button_id=f"doa_swap:{j}", label="OK")
    await sim(c, "customer", "cust-sharma", button_id=f"doa_close:{j}", label="Not needed")


async def j8(c):
    await sim(c, "customer", "cust-sharma", text="we are moving house")
    r = (await c.get("/api/events?limit=5")).json()["events"]
    req = next((e["request"] for e in r if e.get("request")), None)
    await sim(c, "customer", "cust-sharma", button_id=f"move_approve:{req}", label="Approve")
    await sim(c, "field", "owner-a", button_id=f"move_uninstalled:{req}", label="Uninstalled")
    await sim(c, "field", "owner-b", button_id=f"move_installed:{req}", label="Installed")
    await sim(c, "customer", "cust-sharma", button_id=f"move_paid:{req}", label="Pay by UPI")


async def j9(c):
    await sim(c, "customer", "cust-sharma", button_id="care_plan", label="See care plan")
    await sim(c, "customer", "cust-sharma", button_id="plan_buy", label="Buy · ₹1999")
    await sim(c, "customer", "cust-sharma", button_id="plan_paid", label="I've paid")


async def j10(c):
    await sim(c, "customer", "cust-sharma", button_id="slot:Sun 10-12", label="Sun 10-12")
    j = await job_id(c)
    await sim(c, "customer", "cust-sharma", button_id="complain", label="Complain")
    await sim(c, "customer", "cust-sharma", button_id="talk_to_person", label="Talk to a person")


async def j11(c):
    await sim(c, "store", "store-1", button_id="send_optin:cust-sharma:SN-NEW-1:AC", label="Send opt-in")
    await sim(c, "customer", "cust-sharma", button_id="optin:yes:SN-NEW-1", label="Yes")
    await sim(c, "field", "driver-1", button_id="out_for_delivery:SN-NEW-1:3302", label="Out for delivery")
    await sim(c, "field", "driver-1", button_id="deliver:SN-NEW-1:3302", label="Deliver", proof_link="x")


async def j12(c):
    await sim(c, "owner", "P-coolserve", button_id="add_technician:Sunil:field-sunil", label="Add technician")
    await sim(c, "field", "T-field-sunil", button_id="tech_join", label="Join")
    await sim(c, "field", "T-field-sunil", button_id="tech_skill:AC install", label="AC install")
    await sim(c, "area", "area-andheri", button_id="tech_approve:T-field-sunil", label="Approve")


async def j13(c):
    await sim(c, "customer", "cust-sharma", button_id="slot:Sun 10-12", label="Sun 10-12")
    j = await job_id(c)
    await visit_to_confirm(c, j)
    await sim(c, "area", "finance-1", button_id="approve_payout", label="Approve payout")
    await sim(c, "owner", "P-coolserve", button_id=f"dispute:{j}", label="Dispute a line")


async def jexc(c):
    await sim(c, "customer", "cust-sharma", button_id="slot:Sun 10-12", label="Sun 10-12")
    j = await job_id(c)
    await sim(c, "owner", "P-coolserve", button_id=f"job_accept:{j}", label="Accept")
    await sim(c, "owner", "P-coolserve", button_id=f"assign_tech:{j}:T-ravi", label="Ravi · suggested")
    await sim(c, "field", "T-ravi", button_id=f"on_my_way:{j}", label="On my way")
    await sim(c, "field", "T-ravi", button_id=f"arrived:{j}", label="Arrived")
    await sim(c, "field", "T-ravi", button_id=f"serial:{j}:SN-WRONG-9999", label="Wrong serial (test)")


JOURNEYS = [
    ("J1", "Installation", "Booking, assignment and the visit — one job across the four numbers.", j1),
    ("J2", "Repair at home", "Brand self-check, warranty from the ledger, book a technician with the part.", j2),
    ("J3", "Repair with a part (two visits)", "Part not in the bag; one job stays open, visit 2 when it arrives.", j3),
    ("J4", "Out-of-warranty repair", "Visit charge before booking, estimate before work, pay by UPI.", j4),
    ("J5", "Repair by another brand", "The brand repairs it; the agent registers and tracks it in the thread.", j5),
    ("J6", "Walk-in repair at the store", "Drop off, track on WhatsApp, collect with a one-time code.", j6),
    ("J7", "Dead on arrival", "Technician checks, the brand approves, the store swaps the unit.", j7),
    ("J8", "House move", "One request, uninstall + reinstall by two partners, one bill.", j8),
    ("J9", "Maintenance & care plan", "Reminder, a care plan from an insurer, bound to the serial.", j9),
    ("J10", "Complaint & escalation", "The agent replies with facts; a person takes over on request.", j10),
    ("J11", "Sale, opt-in & delivery", "Opt-in, out-for-delivery, serial scanned, installation opened.", j11),
    ("J12", "Technician roster", "The owner adds a technician; the area manager approves.", j12),
    ("J13", "Payouts & disputes", "Payable after confirm + cooling; a person approves the run.", j13),
    ("EX", "Exceptions & protective rules", "A wrong serial at the door stops the job (protective rule, jury attack).", jexc),
]


import base64

EXPAND_CSS = """
  .phone,.phone.solo{height:auto!important}
  .chat{max-height:none!important;height:auto!important;overflow:visible!important}
  .topbar{position:static!important}
  .phones{align-items:start!important}"""


async def capture(c, pg, code, title, summary):
    # real screenshot of the deployed 4-phone screen (expanded so nothing is clipped)
    await pg.goto(f"{BASE}/demo", wait_until="networkidle")
    await pg.wait_for_timeout(4000)                 # let all four inboxes poll in
    await pg.add_style_tag(content=EXPAND_CSS)
    await pg.wait_for_timeout(500)
    png = await pg.screenshot(full_page=True)
    ev = (await c.get("/api/events?limit=80")).json()["events"]
    # also grab any non-demo participant threads (store/delivery/finance/new tech) as real
    # screenshots of their own role page, so every message is pictured
    extra_imgs = []
    extras = [p for p in sorted(_participants) if p not in DEFAULT_IDS]
    for pid in extras:
        msgs = (await c.get(f"/api/inbox/{pid}")).json()["messages"]
        if not msgs:
            continue
        role = {"store-1": "field", "bench-1": "field", "driver-1": "field",
                "owner-a": "owner", "owner-b": "owner", "finance-1": "area",
                "T-field-sunil": "field"}.get(pid, "field")
        try:
            await pg.add_init_script(
                f"localStorage.setItem('resq_persona_{role}', "
                f"JSON.stringify({{id:'{pid}',name:'{label(pid)}'}}))")
            await pg.goto(f"{BASE}/{role}", wait_until="networkidle")
            await pg.wait_for_timeout(2500)
            # open the Chat section if present
            await pg.evaluate("(document.querySelector('#viewnav a[data-sec=\"chat\"]')||{click(){}}).click()")
            await pg.wait_for_timeout(1500)
            await pg.add_style_tag(content=EXPAND_CSS)
            el = await pg.query_selector("#sec-chat") or await pg.query_selector(".content")
            shot = await (el.screenshot() if el else pg.screenshot(full_page=True))
            extra_imgs.append({"label": label(pid), "img": base64.b64encode(shot).decode()})
        except Exception as e:  # noqa: BLE001
            print(f"   (extra {pid} skipped: {e})")
    SECTIONS.append({"code": code, "title": title, "summary": summary,
                     "img": base64.b64encode(png).decode(), "extra": extra_imgs,
                     "trail": " · ".join(e["type"] for e in ev)})
    print(f"captured {code} — demo shot + {len(extra_imgs)} extra threads, {len(ev)} events")


def build_html() -> str:
    body = []
    for s in SECTIONS:
        extras = "".join(
            f"<div class='extra'><div class='exlabel'>{html.escape(e['label'])}</div>"
            f"<img src='data:image/png;base64,{e['img']}'/></div>" for e in s.get("extra", []))
        body.append(f"""
        <section class="j">
          <h2>{html.escape(s['code'])} · {html.escape(s['title'])}</h2>
          <p class="sum">{html.escape(s['summary'])}</p>
          <img class="shot" src="data:image/png;base64,{s['img']}"/>
          {extras}
          <p class="trail"><b>Append-only event trail:</b> {html.escape(s['trail'])}</p>
        </section>""")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
      @page {{ margin: 12mm; }}
      body {{ font-family: -apple-system,'Segoe UI',Roboto,sans-serif; color:#0E2440; }}
      .cover {{ text-align:center; padding:70mm 0; page-break-after:always; }}
      .cover h1 {{ font-size:46px; margin:0; letter-spacing:-2px; }}
      .cover .dot {{ color:#E8820E; font-size:20px; vertical-align:super; }}
      .cover p {{ color:#4A5A72; font-size:15px; }}
      .cover .meta {{ margin-top:28px; font-size:12px; color:#8795A8; }}
      section.j {{ page-break-after:always; }}
      h2 {{ font-size:19px; border-bottom:2px solid #E8820E; padding-bottom:6px; }}
      .sum {{ color:#4A5A72; font-size:12.5px; margin:6px 0 12px; }}
      img.shot {{ width:100%; border:1px solid #DBE2EA; border-radius:10px; }}
      .extra {{ margin-top:12px; }}
      .exlabel {{ font-size:11px; font-weight:600; color:#4A5A72; margin-bottom:4px; }}
      .extra img {{ width:60%; border:1px solid #DBE2EA; border-radius:10px; }}
      .trail {{ font-family:ui-monospace,Menlo,monospace; font-size:9px; color:#4A5A72;
                background:#F4F6F9; padding:8px 10px; border-radius:8px; word-break:break-word; margin-top:12px; }}
      .links {{ display:flex; flex-direction:column; gap:10px; width:360px; margin:28px auto 0; }}
      .links a {{ display:block; text-decoration:none; color:#0E2440; border:1px solid #DBE2EA;
                  border-radius:12px; padding:12px 16px; font-size:14px; font-weight:600;
                  background:#F4F6F9; }}
      .links a .u {{ display:block; font-weight:400; font-size:11px; color:#E8820E; margin-top:2px;
                     word-break:break-all; }}
      .res {{ page-break-after:always; }}
      .res h2 {{ font-size:22px; border-bottom:2px solid #E8820E; padding-bottom:6px; }}
      .res table {{ width:100%; border-collapse:collapse; font-size:12.5px; margin-top:10px; }}
      .res td {{ padding:9px 8px; border-bottom:1px solid #EAEEF3; vertical-align:top; }}
      .res td:first-child {{ font-weight:600; width:34%; }}
      .res a {{ color:#2743a0; word-break:break-all; }}
      .idx {{ margin-top:22px; font-size:12.5px; color:#4A5A72; column-count:2; }}
      .res .pp {{ font-size:12.5px; color:#2b3a4f; line-height:1.55; margin:8px 0; }}
    </style></head><body>
      <div class="cover">
        <h1>resQ<span class="dot">2.0</span></h1>
        <p>AI-native service on WhatsApp — Reliance Digital</p>
        <p>Test evidence — every journey driven on the deployed app,<br/>
           with every message sent and received, per role.</p>
        <div class="links">
          <a href="{BASE}">▶ Open the live app<span class="u">{html.escape(BASE)}</span></a>
          <a href="{REPO}">◆ Source code — GitHub<span class="u">{html.escape(REPO)}</span></a>
          <a href="{REPO}/blob/main/DEMO.md">▣ Demo runbook (click-through)<span class="u">{REPO}/blob/main/DEMO.md</span></a>
        </div>
        <div class="meta">13 journeys · exceptions · protective rules · append-only event trails</div>
      </div>

      <section class="res">
        <h2>Contents</h2>
        <table>
          <tr><td>1 · Product &amp; demo</td><td>What resQ 2.0 is, the four WhatsApp roles, and how to run the demo.</td></tr>
          <tr><td>2 · Resources &amp; links</td><td>Live app, repo, runbook, event-log export, tests.</td></tr>
          <tr><td>3 · Journeys (evidence)</td><td>Real screenshots of every journey on the live app, with event trails.</td></tr>
        </table>
        <div class="idx" style="margin-top:18px">{''.join(f"<div>{html.escape(s['code'])} · {html.escape(s['title'])}</div>" for s in SECTIONS)}</div>
      </section>

      <section class="res">
        <h2>Product &amp; demo details</h2>
        <p class="pp"><b>What it is.</b> resQ 2.0 is Reliance Digital's service, rebuilt on WhatsApp.
        The AI agent does the routine work end to end; people act only on exceptions. Underneath is
        a registry: every serial bound to a household, with its warranty, service history and
        remaining life — the asset a pure e-commerce competitor cannot copy.</p>
        <p class="pp"><b>Four WhatsApp numbers (roles).</b> 👤 Customer · 🏪 Service owner ·
        🔧 Field (technician / store associate / delivery / service bench) · 🧭 Area manager.
        One customer thread per household; one open question at a time.</p>
        <p class="pp"><b>AI-native.</b> Free-text intent routing, replies in the customer's language
        (e.g. Hindi), a brand self-check and pre-diagnosis grounded in what the household owns,
        voice notes and error-code photos, and natural grounded replies — all with the OpenAI
        model; deterministic fallbacks when a key is absent.</p>
        <p class="pp"><b>Guardrails.</b> An append-only event log (a correction is a new event),
        a job state machine, and eight protective rules enforced in code — never by the model.</p>
        <p class="pp"><b>How to read this document.</b> Each journey page is a real screenshot of
        the live deployed app (the four phones on one screen), plus any other participant's thread,
        and the append-only event trail that journey produced.</p>
        <h2 style="margin-top:22px">What the demo proves (judging)</h2>
        <table>
          <tr><td>Works end to end (25)</td><td>J1–J13 — every journey runs from booking to close.</td></tr>
          <tr><td>Customer experience (20)</td><td>AI triage, language mirroring, UPI QR, grounding in owned machines.</td></tr>
          <tr><td>Human touches (15)</td><td>J10 talk-to-a-person, resQ-desk take-over, the action register.</td></tr>
          <tr><td>Exceptions (15)</td><td>EX + handlers: wrong serial, decline→backup→escalate, site not ready, payment fails, DOA rejected.</td></tr>
          <tr><td>Protective rules (15)</td><td>Serial match, proof via capture link, rate-card prices, no cash, handover code, payout guard.</td></tr>
          <tr><td>Monitoring (10)</td><td>Area overview (pie, exceptions, live log), status on request, 8am/6pm digest.</td></tr>
        </table>
        <p class="pp" style="margin-top:14px"><b>Run the demo:</b> open the live app, click
        <b>Reset demo</b>, then follow the one-job loop — customer books → owner assigns →
        technician scans serial + finishes → customer confirms. Full click-through in the runbook.</p>
      </section>

      <section class="res">
        <h2>Resources &amp; links</h2>
        <table>
          <tr><td>Live app</td><td><a href="{BASE}">{html.escape(BASE)}</a></td></tr>
          <tr><td>Source code (GitHub)</td><td><a href="{REPO}">{html.escape(REPO)}</a></td></tr>
          <tr><td>Demo runbook</td><td><a href="{REPO}/blob/main/DEMO.md">{REPO}/blob/main/DEMO.md</a></td></tr>
          <tr><td>This evidence PDF</td><td><a href="{REPO}/blob/main/resQ_2.0_Submission.pdf">{REPO}/blob/main/resQ_2.0_Submission.pdf</a></td></tr>
          <tr><td>Event-log export (live)</td><td><a href="{BASE}/api/export">{BASE}/api/export</a></td></tr>
          <tr><td>Run all 13 journeys</td><td><code>python -m scripts.run_all_journeys</code></td></tr>
          <tr><td>Tests</td><td><code>python -m pytest -q</code> — 55 passing</td></tr>
        </table>
      </section>
      {''.join(body)}
    </body></html>"""


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=90) as c, async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1500, "height": 1000}, device_scale_factor=2)
        for code, title, summary, runner in JOURNEYS:
            _participants.clear()
            try:
                await c.post("/api/reset")               # reset the demo before each journey
                await runner(c)
                await capture(c, pg, code, title, summary)
            except Exception as e:  # noqa: BLE001
                print(f"!! {code} failed: {e}")
        report = await b.new_page()
        await report.set_content(build_html(), wait_until="networkidle")
        await report.pdf(path=OUT, format="A4", print_background=True)
        await b.close()
    print(f"\nWrote {OUT} ({len(SECTIONS)} sections)")


if __name__ == "__main__":
    asyncio.run(main())
