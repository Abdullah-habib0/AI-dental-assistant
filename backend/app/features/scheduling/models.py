from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        # One record per phone number for guests. Account holders are not affected,
        # because this rule only looks at rows where user_id is empty.
        Index(
            "one_guest_per_phone",
            "phone",
            unique=True,
            sqlite_where=text("user_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Empty for guests, filled in for people with an account.
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), unique=True, index=True, nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("status IN ('confirmed', 'cancelled')", name="status_is_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id"), index=True, nullable=False
    )
    dentist_id: Mapped[int] = mapped_column(Integer, ForeignKey("dentists.id"), nullable=False)
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class AppointmentSlot(Base):
    """One row for every 30 minutes that is taken."""

    __tablename__ = "appointment_slots"
    __table_args__ = (
        # The rule that makes double-booking impossible.
        UniqueConstraint("dentist_id", "slot_start_time", name="one_booking_per_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dentist_id: Mapped[int] = mapped_column(Integer, ForeignKey("dentists.id"), nullable=False)
    slot_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    appointment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False
    )
