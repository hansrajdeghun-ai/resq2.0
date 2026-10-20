"""Core domain enums shared across the engine (surface-agnostic)."""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    """The four WhatsApp numbers (spec 2.1) + store associate for POS."""

    CUSTOMER = "customer"
    OWNER = "owner"  # service owner / partner
    FIELD = "field"  # technician / store associate / service bench
    AREA = "area"  # area manager / resQ desk / finance
    STORE = "store"  # store associate (POS, drop-off)


class JobType(str, Enum):
    INSTALL = "install"
    REPAIR = "repair"
    SERVICE = "service"
    DOA = "doa"
    WALK_IN = "walk_in"
    HOUSE_MOVE = "house_move"
    BRAND_REPAIR = "brand_repair"


class JobState(str, Enum):
    """Job lifecycle (spec 2.3). Closed is terminal; Cancelled terminal."""

    REQUESTED = "Requested"
    PROMISED = "Promised"
    ASSIGNED = "Assigned"
    EN_ROUTE = "EnRoute"
    ON_SITE = "OnSite"
    WORK_DONE = "WorkDone"
    CONFIRMED = "Confirmed"
    CLOSED = "Closed"
    # side states
    WAITING_FOR_PART = "WaitingForPart"
    WAITING_FOR_APPROVAL = "WaitingForApproval"
    WITH_BRAND = "WithBrand"  # J5: brand repairs it
    REVISIT = "Revisit"  # repeat fault in cooling period
    CANCELLED = "Cancelled"


# Legal transitions. Keys are current state; values are allowed next states.
# Enforced by journeys/state_machine.py.
ALLOWED_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.REQUESTED: {
        JobState.PROMISED,
        JobState.WITH_BRAND,
        JobState.CANCELLED,
    },
    JobState.PROMISED: {
        JobState.ASSIGNED,
        JobState.WAITING_FOR_PART,
        JobState.CANCELLED,
    },
    JobState.ASSIGNED: {
        JobState.EN_ROUTE,
        JobState.PROMISED,  # reassign
        JobState.CANCELLED,
    },
    JobState.EN_ROUTE: {JobState.ON_SITE, JobState.PROMISED},
    JobState.ON_SITE: {
        JobState.WORK_DONE,
        JobState.WAITING_FOR_PART,
        JobState.WAITING_FOR_APPROVAL,
        JobState.PROMISED,  # not at home / site not ready -> rebook
    },
    JobState.WAITING_FOR_PART: {JobState.PROMISED},  # visit 2 booked when part arrives
    JobState.WAITING_FOR_APPROVAL: {JobState.WORK_DONE, JobState.ON_SITE},
    JobState.WORK_DONE: {JobState.CONFIRMED},
    JobState.CONFIRMED: {JobState.CLOSED, JobState.REVISIT},  # cooling period
    JobState.REVISIT: {JobState.PROMISED},  # same job, no new payout
    JobState.WITH_BRAND: {JobState.CONFIRMED, JobState.CLOSED},
    JobState.CLOSED: set(),
    JobState.CANCELLED: set(),
}

# Cancellation allowed only from the customer thread, before Work done (spec 2.3).
CANCELLABLE_BEFORE = {
    JobState.REQUESTED,
    JobState.PROMISED,
    JobState.ASSIGNED,
    JobState.EN_ROUTE,
    JobState.ON_SITE,
    JobState.WAITING_FOR_PART,
    JobState.WAITING_FOR_APPROVAL,
}
