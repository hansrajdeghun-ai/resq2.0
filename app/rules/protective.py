"""The 8 protective rules (spec 4.2). Hard gates enforced in code.

The jury actively tries to break these (cancel as technician, skip the serial scan,
send an old photo, charge an off-card price). Each check raises ProtectiveRuleError;
callers log it to RuleViolation. The LLM can never bypass these.

  1. Only the customer can cancel.
  2. One visit, one payout. Another visit needs a reason in the event log.
  3. The serial at the door must match the machine sold.
  4. Proof comes through the capture link, with time and place.
  5. Prices come only from the rate card, and the customer approves them in the thread.
  6. The technician does not take cash.
  7. Walk-in handover only with the one-time code.
  8. No payout without CustomerConfirmed. A person approves each payout run.
"""
from __future__ import annotations

from datetime import datetime

from app.data import rate_card
from app.domain import CANCELLABLE_BEFORE, JobState
from app.errors import OptInRequired, ProtectiveRuleError

CASH_METHODS = {"cash", "card_at_door", "cheque"}


# ─── before production: opt-in gate ────────────────────────────────────────
def assert_opted_in(opted_in: bool) -> None:
    if not opted_in:
        raise OptInRequired()


# ─── rule 1 ────────────────────────────────────────────────────────────────
def assert_can_cancel(state: JobState | str, actor_role: str) -> None:
    cur = JobState(state) if isinstance(state, str) else state
    if actor_role != "customer":
        raise ProtectiveRuleError("only_customer_cancels",
                                  f"{actor_role} cannot cancel; only the customer can")
    if cur not in CANCELLABLE_BEFORE:
        raise ProtectiveRuleError("only_customer_cancels",
                                  f"cannot cancel after Work done (state={cur.value})")


# ─── rule 2 ────────────────────────────────────────────────────────────────
def assert_visit_payout(visit_number: int, payable: bool, reason: str | None) -> None:
    """A visit after the first is paid only with a reason in the log (part needed,
    revisit, site not ready). A same-job revisit for a repeat fault is NOT payable."""
    if visit_number > 1 and payable and not reason:
        raise ProtectiveRuleError(
            "one_visit_one_payout",
            "a second payable visit needs a reason in the event log",
        )


# ─── rule 3 ────────────────────────────────────────────────────────────────
def assert_serial_matches(scanned: str | None, expected: str | None) -> None:
    if not scanned:
        raise ProtectiveRuleError("serial_match", "serial not scanned at the door")
    if expected and scanned.strip() != expected.strip():
        raise ProtectiveRuleError(
            "serial_match",
            f"serial at the door ({scanned}) does not match the machine sold ({expected})",
        )


# ─── rule 4 ────────────────────────────────────────────────────────────────
def assert_proof(proof_link: str | None, at: datetime | None, place: str | None) -> None:
    """Proof comes through the capture link, with time and place. Photos pasted into
    the chat lose time and place and are rejected."""
    if not proof_link:
        raise ProtectiveRuleError("proof_capture",
                                  "proof must come through the capture link, not the chat")
    if at is None or not place:
        raise ProtectiveRuleError("proof_capture",
                                  "proof is missing time or place (old/pasted photo)")


# ─── rule 5 ────────────────────────────────────────────────────────────────
def assert_price_on_card(category: str, amount: float) -> None:
    valid = rate_card.all_prices(category)
    if amount not in valid:
        raise ProtectiveRuleError(
            "price_on_card",
            f"{amount} is not on the rate card for {category} (allowed: {sorted(valid)})",
        )


def assert_price_approved(approved_in_thread: bool) -> None:
    if not approved_in_thread:
        raise ProtectiveRuleError("price_on_card",
                                  "the customer must approve the price in the thread")


# ─── rule 6 ────────────────────────────────────────────────────────────────
def assert_no_cash(payment_method: str) -> None:
    if payment_method.lower() in CASH_METHODS:
        raise ProtectiveRuleError("no_cash",
                                  "the technician does not take cash; pay by UPI link only")


# ─── rule 7 ────────────────────────────────────────────────────────────────
def assert_handover_code(entered: str | None, expected: str | None) -> None:
    if not expected:
        raise ProtectiveRuleError("handover_code", "no handover code was issued")
    if (entered or "").strip() != expected.strip():
        raise ProtectiveRuleError("handover_code",
                                  "walk-in handover only with the correct one-time code")


# ─── rule 8 ────────────────────────────────────────────────────────────────
def assert_payout_allowed(customer_confirmed: bool, approver: str | None) -> None:
    if not customer_confirmed:
        raise ProtectiveRuleError("payout_guard",
                                  "no payout without CustomerConfirmed")
    if not approver:
        raise ProtectiveRuleError("payout_guard",
                                  "a person must approve each payout run")
