"""Service partners and technicians (spec 2.1, J12 roster)."""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db import Base


class ServicePartner(Base):
    """Service owner: owns technicians, accepts/declines jobs. Three classes:
    own / contracted / qualified-but-unaffiliated (Working Paper 7)."""

    __tablename__ = "service_partner"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))
    pincodes: Mapped[list] = mapped_column(JSON, default=list)
    authority: Mapped[list] = mapped_column(JSON, default=list)  # brands/categories
    partner_class: Mapped[str] = mapped_column(String(24), default="contracted")
    is_backup: Mapped[bool] = mapped_column(Boolean, default=False)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class Technician(Base):
    """Field technician. Active = started a day and closed a job in last 30 days."""

    __tablename__ = "technician"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))
    partner_id: Mapped[str | None] = mapped_column(String(32), index=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)  # AC install, TV...
    pincode: Mapped[str | None] = mapped_column(String(8))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    id_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    day_started_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_job_closed_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    on_leave: Mapped[bool] = mapped_column(Boolean, default=False)
    capacity_slots: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float | None] = mapped_column()
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
