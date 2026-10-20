"""Job state machine (spec 2.3). Validates transitions before an event is written.

The projector sets job.state from events; this guards *which* transitions are
legal so the agent cannot drive a job into an impossible state.
"""
from __future__ import annotations

from app.domain import ALLOWED_TRANSITIONS, CANCELLABLE_BEFORE, JobState
from app.errors import IllegalTransition


def can_transition(current: JobState | str, target: JobState | str) -> bool:
    cur = JobState(current) if isinstance(current, str) else current
    tgt = JobState(target) if isinstance(target, str) else target
    return tgt in ALLOWED_TRANSITIONS.get(cur, set())


def assert_transition(current: JobState | str, target: JobState | str) -> None:
    if not can_transition(current, target):
        raise IllegalTransition(
            f"cannot move job from {current} to {target}"
        )


def can_cancel(current: JobState | str, actor_role: str) -> bool:
    """Only the customer can cancel, and only before Work done (spec 2.3, 4.2 #1)."""
    cur = JobState(current) if isinstance(current, str) else current
    return actor_role == "customer" and cur in CANCELLABLE_BEFORE


def is_terminal(state: JobState | str) -> bool:
    s = JobState(state) if isinstance(state, str) else state
    return s in (JobState.CLOSED, JobState.CANCELLED)
