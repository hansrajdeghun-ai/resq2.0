"""Every event the system can record (spec 5.3 + all journey pages J1-J13).

Events are never changed. A correction is a new event.
Each event carries: event_id, machine_id, job_id, visit/task_id, actor, time,
place (if known), proof_link — see events/log.py.
"""
from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    # ─── Sale and delivery (J11) ───────────────────────────────────────────
    SOLD = "Sold"
    OPTED_IN = "OptedIn"
    SERIAL_BOUND = "SerialBound"
    OUT_FOR_DELIVERY = "OutForDelivery"
    DELIVERED = "Delivered"

    # ─── Job lifecycle ─────────────────────────────────────────────────────
    INSTALL_REQUESTED = "InstallRequested"
    FAULT_REPORTED = "FaultReported"
    SELF_CHECK_SENT = "SelfCheckSent"
    SELF_FIXED = "SelfFixed"
    REPAIR_REQUESTED = "RepairRequested"
    WARRANTY_CHECKED = "WarrantyChecked"
    AUTHORITY_CHECKED = "AuthorityChecked"  # J5
    PRE_DIAGNOSED = "PreDiagnosed"
    PROMISED = "Promised"
    CANCELLED = "Cancelled"
    CUSTOMER_CONFIRMED = "CustomerConfirmed"
    CLOSED = "Closed"
    REOPENED = "Reopened"

    # ─── Assignment ────────────────────────────────────────────────────────
    PARTNER_OFFERED = "PartnerOffered"
    PARTNER_DECLINED = "PartnerDeclined"
    PARTNER_ASSIGNED = "PartnerAssigned"
    TECHNICIAN_ASSIGNED = "TechnicianAssigned"

    # ─── Visit ─────────────────────────────────────────────────────────────
    EN_ROUTE = "EnRoute"
    ARRIVED = "Arrived"
    SERIAL_VERIFIED = "SerialVerified"
    SERIAL_MISMATCH = "SerialMismatch"
    DIAGNOSED = "Diagnosed"
    NOT_AT_HOME = "NotAtHome"
    SITE_NOT_READY = "SiteNotReady"
    WORK_DONE = "WorkDone"
    VISIT_OPENED = "VisitOpened"  # J3 visit 2

    # ─── Money ─────────────────────────────────────────────────────────────
    VISIT_FEE_ACCEPTED = "VisitFeeAccepted"  # J4
    ESTIMATE_SENT = "EstimateSent"
    ESTIMATE_APPROVED = "EstimateApproved"
    ESTIMATE_DECLINED = "EstimateDeclined"
    EXTRAS_APPROVED = "ExtrasApproved"
    PAYMENT_RECEIVED = "PaymentReceived"
    INVOICE_SENT = "InvoiceSent"
    PAYABLE = "Payable"
    HELD = "Held"
    STATEMENT_SENT = "StatementSent"  # J13
    DISPUTE_RAISED = "DisputeRaised"
    DISPUTE_TO_FINANCE = "DisputeToFinance"  # J13
    DISPUTE_RESOLVED = "DisputeResolved"
    PAYOUT_APPROVED = "PayoutApproved"
    PAID = "Paid"

    # ─── Parts (J3) ────────────────────────────────────────────────────────
    PART_NEEDED = "PartNeeded"
    PART_RESERVED = "PartReserved"
    PART_DISPATCHED = "PartDispatched"
    PART_RECEIVED = "PartReceived"
    PART_USED = "PartUsed"
    RETURN_OPENED = "ReturnOpened"

    # ─── Brand and plan ────────────────────────────────────────────────────
    BRAND_TICKET_OPENED = "BrandTicketOpened"
    BRAND_VISIT_PROMISED = "BrandVisitPromised"  # J5
    BRAND_MISSED = "BrandMissed"
    ESCALATED = "Escalated"
    CLAIMED = "Claimed"  # warranty claim to brand (J1)
    DOA_CHECK_OPENED = "DOACheckOpened"  # J7
    DOA_REPORTED = "DOAReported"
    DOA_APPROVED = "DOAApproved"
    REPLACEMENT_RESERVED = "ReplacementReserved"  # J7
    COLLECTED = "Collected"  # old unit collected (J7)
    REPLACED = "Replaced"
    PLAN_QUOTED = "PlanQuoted"  # J9
    PLAN_BOUGHT = "PlanBought"
    POLICY_BOUND = "PolicyBound"  # J9

    # ─── Walk-in (J6) ──────────────────────────────────────────────────────
    WALK_IN_RECEIVED = "WalkInReceived"
    CONDITION_RECORDED = "ConditionRecorded"
    READY_FOR_PICKUP = "ReadyForPickup"
    HANDED_OVER = "HandedOver"

    # ─── House move / request (J8) ─────────────────────────────────────────
    REQUEST_OPENED = "RequestOpened"
    JOBS_OPENED = "JobsOpened"
    QUOTE_APPROVED = "QuoteApproved"
    UNINSTALLED = "Uninstalled"
    ADDRESS_MOVED = "AddressMoved"
    INSTALLED = "Installed"
    REQUEST_CLOSED = "RequestClosed"

    # ─── Maintenance / care plan (J9) ──────────────────────────────────────
    REMINDER_SENT = "ReminderSent"
    SERVICE_BOOKED = "ServiceBooked"
    SERVICE_DONE = "ServiceDone"
    HEALTH_REPORTED = "HealthReported"
    RENEWAL_SENT = "RenewalSent"

    # ─── Complaint / escalation (J10) ──────────────────────────────────────
    COMPLAINT_RAISED = "ComplaintRaised"
    HANDED_TO_PERSON = "HandedToPerson"
    FIX_PROPOSED = "FixProposed"
    FIX_ACCEPTED = "FixAccepted"
    GOODWILL_ISSUED = "GoodwillIssued"
    COMPLAINT_CLOSED = "ComplaintClosed"
    PATTERN_FLAGGED = "PatternFlagged"

    # ─── People / roster (J12) ─────────────────────────────────────────────
    TECHNICIAN_INVITED = "TechnicianInvited"
    TECHNICIAN_JOINED = "TechnicianJoined"
    ID_CHECKED = "IDChecked"
    SKILL_ADDED = "SkillAdded"
    TECHNICIAN_APPROVED = "TechnicianApproved"
    DAY_STARTED = "DayStarted"
    ON_LEAVE = "OnLeave"
    CAPACITY_CONFIRMED = "CapacityConfirmed"
    TECHNICIAN_INACTIVE = "TechnicianInactive"

    # ─── Monitoring (area manager) ─────────────────────────────────────────
    ALERT_SENT = "AlertSent"
    ALERT_CLOSED = "AlertClosed"
    STATUS_ASKED = "StatusAsked"
    DIGEST_SENT = "DigestSent"
    TAKEN_OVER = "TakenOver"
    RETURNED_TO_AGENT = "ReturnedToAgent"
