"""Protective rules + state machine — the jury actively tries to break these."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain import JobState
from app.errors import IllegalTransition, ProtectiveRuleError
from app.journeys import state_machine as sm
from app.rules import protective as pr


# ─── state machine ──────────────────────────────────────────────────────────
def test_legal_transition():
    sm.assert_transition(JobState.REQUESTED, JobState.PROMISED)
    assert sm.can_transition(JobState.ON_SITE, JobState.WORK_DONE)


def test_illegal_transition_blocked():
    with pytest.raises(IllegalTransition):
        sm.assert_transition(JobState.CLOSED, JobState.PROMISED)
    assert not sm.can_transition(JobState.REQUESTED, JobState.WORK_DONE)


# ─── rule 1: only the customer can cancel ──────────────────────────────────
def test_technician_cannot_cancel():
    with pytest.raises(ProtectiveRuleError):
        pr.assert_can_cancel(JobState.PROMISED, "field")


def test_customer_cannot_cancel_after_work_done():
    with pytest.raises(ProtectiveRuleError):
        pr.assert_can_cancel(JobState.WORK_DONE, "customer")


def test_customer_can_cancel_before_work_done():
    pr.assert_can_cancel(JobState.PROMISED, "customer")  # no raise


# ─── rule 3: serial must match ─────────────────────────────────────────────
def test_serial_mismatch_blocked():
    with pytest.raises(ProtectiveRuleError):
        pr.assert_serial_matches("SN-WRONG", "SN-RIGHT")
    with pytest.raises(ProtectiveRuleError):
        pr.assert_serial_matches(None, "SN-RIGHT")  # skipped scan
    pr.assert_serial_matches("SN-RIGHT", "SN-RIGHT")


# ─── rule 4: proof needs capture link + time + place ───────────────────────
def test_old_photo_rejected():
    now = datetime.now(timezone.utc)
    with pytest.raises(ProtectiveRuleError):
        pr.assert_proof(None, now, "Andheri")  # pasted in chat
    with pytest.raises(ProtectiveRuleError):
        pr.assert_proof("http://capture/x", None, None)  # no time/place
    pr.assert_proof("http://capture/x", now, "Andheri East 400069")


# ─── rule 5: price only from the rate card, approved in thread ─────────────
def test_off_card_price_blocked():
    with pytest.raises(ProtectiveRuleError):
        pr.assert_price_on_card("AC", 5000.0)  # not on card
    pr.assert_price_on_card("AC", 2200.0)  # gas refill is on the card
    with pytest.raises(ProtectiveRuleError):
        pr.assert_price_approved(False)


# ─── rule 6: no cash ───────────────────────────────────────────────────────
def test_technician_cannot_take_cash():
    with pytest.raises(ProtectiveRuleError):
        pr.assert_no_cash("cash")
    pr.assert_no_cash("upi")


# ─── rule 7: handover code ─────────────────────────────────────────────────
def test_walk_in_needs_code():
    with pytest.raises(ProtectiveRuleError):
        pr.assert_handover_code("0000", "4817")
    pr.assert_handover_code("4817", "4817")


# ─── rule 8: payout guard ──────────────────────────────────────────────────
def test_no_payout_without_confirm_and_approver():
    with pytest.raises(ProtectiveRuleError):
        pr.assert_payout_allowed(False, "area-manager")  # not confirmed
    with pytest.raises(ProtectiveRuleError):
        pr.assert_payout_allowed(True, None)  # no person approved
    pr.assert_payout_allowed(True, "area-manager")


# ─── rule 2: one visit, one payout ─────────────────────────────────────────
def test_second_payable_visit_needs_reason():
    with pytest.raises(ProtectiveRuleError):
        pr.assert_visit_payout(2, payable=True, reason=None)
    pr.assert_visit_payout(2, payable=True, reason="PartNeeded")
    pr.assert_visit_payout(2, payable=False, reason=None)  # free revisit ok
