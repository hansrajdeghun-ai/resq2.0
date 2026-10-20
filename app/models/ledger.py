"""Read-model projections for the ledger (spec 2.2 records).

Machine-first (Working Paper 7): the serial is the anchor; the household attaches
to it, so we can hold a machine we did not sell. These tables are rebuilt by
events/projections.py — never written to directly outside the projector.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Customer(Base):
    """A household = an address. Keyed by masked WhatsApp identity / bpid."""

    __tablename__ = "customer"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # bpid or wa id
    name: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))  # kept hidden to partners
    language: Mapped[str] = mapped_column(String(8), default="en")
    opted_in: Mapped[bool] = mapped_column(Boolean, default=False)
    address: Mapped[dict] = mapped_column(JSON, default=dict)


class Machine(Base):
    """One product: brand + model + serial (IMEI for phones). Serial = anchor."""

    __tablename__ = "machine"

    serial: Mapped[str] = mapped_column(String(64), primary_key=True)
    object_id: Mapped[str | None] = mapped_column(String(64), index=True)  # Kapture iObject
    brand: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    category: Mapped[str | None] = mapped_column(String(64))  # AC, TV, washer...
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customer.id"), index=True)
    sales_order_no: Mapped[str | None] = mapped_column(String(32))
    date_of_purchase: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    wty_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    wty_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authority: Mapped[str | None] = mapped_column(String(32))  # who may service (brand)
    replaced_by_serial: Mapped[str | None] = mapped_column(String(64))  # DOA swap link
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class Job(Base):
    """One customer need on one machine. R-xxxx. Install/repair/service/DOA."""

    __tablename__ = "job"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # R-1001
    type: Mapped[str] = mapped_column(String(24))  # JobType
    state: Mapped[str] = mapped_column(String(24), index=True)  # JobState
    machine_serial: Mapped[str | None] = mapped_column(ForeignKey("machine.serial"))
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customer.id"), index=True)
    request_id: Mapped[str | None] = mapped_column(String(32), index=True)
    partner_id: Mapped[str | None] = mapped_column(String(32))
    technician_id: Mapped[str | None] = mapped_column(String(32))
    in_warranty: Mapped[bool | None] = mapped_column(Boolean)
    slot: Mapped[str | None] = mapped_column(String(64))  # e.g. "Sun 10-12"
    rate: Mapped[float | None] = mapped_column(Numeric(10, 2))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cooling_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    crm_service_request_id: Mapped[str | None] = mapped_column(String(32))  # Kapture
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class Visit(Base):
    """One technician trip. A job can have many visits (J3)."""

    __tablename__ = "visit"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job.id"), index=True)
    technician_id: Mapped[str | None] = mapped_column(String(32))
    number: Mapped[int] = mapped_column(default=1)  # visit 1, visit 2...
    status: Mapped[str] = mapped_column(String(24), default="planned")
    slot: Mapped[str | None] = mapped_column(String(64))
    serial_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    payable: Mapped[bool] = mapped_column(Boolean, default=True)  # false if same-job revisit
    proof_links: Mapped[list] = mapped_column(JSON, default=list)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class Task(Base):
    """Work with no trip: part order, part return, brand ticket, payment, approval."""

    __tablename__ = "task"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("job.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # part_order/part_return/brand_ticket/...
    status: Mapped[str] = mapped_column(String(24), default="open")
    ref: Mapped[str | None] = mapped_column(String(64))  # part no, ticket no, awb...
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class ServiceRequest(Base):
    """A group of jobs, e.g. a house move with 6 jobs (spec 2.2 / J8)."""

    __tablename__ = "service_request"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customer.id"))
    kind: Mapped[str] = mapped_column(String(32), default="house_move")
    status: Mapped[str] = mapped_column(String(24), default="open")
    note: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
