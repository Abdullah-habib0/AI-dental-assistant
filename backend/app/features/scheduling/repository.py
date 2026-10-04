"""Database queries for scheduling.

Queries only - nothing here decides anything, and nothing here commits. Adding and
deleting is fine; saving is service.py's job, so a booking happens completely or not at all.
"""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.scheduling.models import Appointment, AppointmentSlot, Patient

# --- Patients ---------------------------------------------------------------------


def add_patient(session: AsyncSession, patient: Patient) -> None:
    session.add(patient)


async def get_patient_by_user_id(session: AsyncSession, user_id: int) -> Patient | None:
    return await session.scalar(select(Patient).where(Patient.user_id == user_id))


async def get_guest_patient_by_phone(session: AsyncSession, phone_number: str) -> Patient | None:
    # user_id must be empty. Without that check, anyone could type an account holder's
    # phone number and be handed their patient record - and their appointments.
    return await session.scalar(
        select(Patient).where(Patient.phone == phone_number, Patient.user_id.is_(None))
    )


# --- Appointments -----------------------------------------------------------------


def add_appointment(session: AsyncSession, appointment: Appointment) -> None:
    session.add(appointment)


async def get_appointment_by_id(session: AsyncSession, appointment_id: int) -> Appointment | None:
    return await session.get(Appointment, appointment_id)


async def get_upcoming_appointments(
    session: AsyncSession, patient_id: int, now: datetime
) -> list[Appointment]:
    """Confirmed appointments from `now` onward, earliest first.

    `now` is passed in rather than worked out here, so the caller decides what "now"
    is. service.py passes utcnow(); a test can pass any date it likes.
    """
    result = await session.scalars(
        select(Appointment)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.status == "confirmed",
            Appointment.start_time >= now,
        )
        .order_by(Appointment.start_time)
    )
    return list(result)


# --- Slots ------------------------------------------------------------------------


def add_appointment_slot(session: AsyncSession, appointment_slot: AppointmentSlot) -> None:
    session.add(appointment_slot)


async def delete_slots_for_appointment(session: AsyncSession, appointment_id: int) -> None:
    """Frees up the time an appointment was holding. Used by cancel and reschedule."""
    await session.execute(
        delete(AppointmentSlot).where(AppointmentSlot.appointment_id == appointment_id)
    )


async def get_taken_slots(
    session: AsyncSession,
    start_time: datetime,
    end_time: datetime,
    dentist_id: int | None = None,
) -> set[tuple[int, datetime]]:
    """Every taken slot from start_time up to (not including) end_time.

    Returns (dentist_id, slot_start_time) pairs. Leave dentist_id out to get every
    dentist's - that is what a patient who says "I don't mind who" needs.
    """
    query = select(AppointmentSlot).where(
        AppointmentSlot.slot_start_time >= start_time,
        AppointmentSlot.slot_start_time < end_time,
    )
    if dentist_id is not None:
        query = query.where(AppointmentSlot.dentist_id == dentist_id)

    result = await session.scalars(query)
    return {(row.dentist_id, row.slot_start_time) for row in result}
