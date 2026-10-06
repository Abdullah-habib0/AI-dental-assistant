"""The booking rules: find free times, book, cancel, reschedule, list.

Both the website routes and the AI agent's tools call these functions, so every rule
lives here exactly once.

One rule for callers: pass a session that has no transaction open yet. Each public
function opens its own transaction with `session.begin()` and closes it before it
returns, so an operation either happens completely or not at all, and the database
lock is never held for longer than the operation itself.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.time import utcnow
from app.features.auth.models import User
from app.features.clinic import service as clinic_service
from app.features.scheduling import repository
from app.features.scheduling.models import Appointment, AppointmentSlot, Patient
from app.features.scheduling.opening_hrs import is_slot_start, slots_between

_STEP = timedelta(minutes=settings.slot_minutes)
_CLINIC_TZ = ZoneInfo(settings.clinic_timezone)
MAX_SEARCH_DAYS = 31
MAX_DAYS_AHEAD = 90


# --- Errors -----------------------------------------------------------------------
# Every message here is written to be shown straight to a patient.


class SchedulingError(Exception):
    """A request that breaks a booking rule."""


class SlotTaken(SchedulingError):
    """Someone else got that time first."""


class AppointmentNotFound(SchedulingError):
    """No such appointment - or it isn't yours. Deliberately the same error for both,
    so a stranger can't find out which appointment numbers exist."""


# --- What these functions take and give back ----------------------------------------


@dataclass
class FreeSlot:
    dentist_id: int
    dentist_slug: str  # what book_appointment asks for, so a shown slot can be booked as-is
    start_time: datetime  # UTC
    end_time: datetime  # UTC


@dataclass
class PatientDetails:
    full_name: str
    phone: str
    email: str | None = None


# --- Small helpers ------------------------------------------------------------------


def _tidy_phone(phone: str) -> str:
    """Keep only the digits, plus a leading '+'.

    Without this, "07700 900123" and "07700-900123" would be two different guests, and
    the second one could never find the appointments the first one made.
    """
    phone = phone.strip()
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        raise SchedulingError("That doesn't look like a full phone number.")
    return ("+" if phone.startswith("+") else "") + digits


def _slots_needed(duration_minutes: int) -> int:
    return duration_minutes // settings.slot_minutes


def _slot_times(start: datetime, count: int) -> list[datetime]:
    """The start of every 30-minute block an appointment covers."""
    return [start + _STEP * i for i in range(count)]


def _check_start_time(start: datetime, slots_needed: int) -> None:
    """Refuse times in the past, too far ahead, or not on the clinic's timetable."""
    now = utcnow()
    if start <= now:
        raise SchedulingError("That time has already passed.")
    if start > now + timedelta(days=MAX_DAYS_AHEAD):
        raise SchedulingError(f"We only take bookings up to {MAX_DAYS_AHEAD} days ahead.")

    # Every block must be a real opening-hours slot. This one check catches 14:17,
    # weekends, 3am, and a 60-minute treatment starting at 16:30 that would run past
    # closing time.
    if not all(is_slot_start(t) for t in _slot_times(start, slots_needed)):
        raise SchedulingError("That time isn't available for this treatment.")


async def _find_or_create_patient(
    session: AsyncSession, details: PatientDetails, user: User | None
) -> Patient:
    """Account holders are found by their account. Guests are found by phone number.

    The two lookups never cross: a guest typing an account holder's phone number gets
    a separate guest record, never the account holder's.
    """
    phone = _tidy_phone(details.phone)
    email = details.email.strip() if details.email else None

    if user is not None:
        patient = await repository.get_patient_by_user_id(session, user.id)
        if patient is None:
            patient = Patient(user_id=user.id, full_name="", phone=phone)
            repository.add_patient(session, patient)
        patient.phone = phone
    else:
        patient = await repository.get_guest_patient_by_phone(session, phone)
        if patient is None:
            patient = Patient(full_name="", phone=phone)
            repository.add_patient(session, patient)

    # Keep details current, so a name typed wrong last time is fixed by booking again.
    patient.full_name = details.full_name.strip()
    if email:
        patient.email = email
    return patient


async def _find_patient(
    session: AsyncSession, user: User | None, phone: str | None
) -> Patient | None:
    """Look someone up without creating anything."""
    if user is not None:
        return await repository.get_patient_by_user_id(session, user.id)
    if phone:
        return await repository.get_guest_patient_by_phone(session, _tidy_phone(phone))
    return None


async def _get_owned_appointment(
    session: AsyncSession, appointment_id: int, user: User | None, phone: str | None
) -> Appointment:
    """The appointment, but only if it belongs to whoever is asking.

    Logged in: it must be linked to your account.
    Guest:     it must be a guest booking made with the phone number you gave.
    """
    appointment = await repository.get_appointment_by_id(session, appointment_id)
    patient = await _find_patient(session, user, phone)

    if appointment is None or patient is None or appointment.patient_id != patient.id:
        raise AppointmentNotFound("I couldn't find that appointment.")
    if appointment.status != "confirmed":
        raise SchedulingError("That appointment has already been cancelled.")
    if appointment.start_time <= utcnow():
        raise SchedulingError("That appointment has already started or passed.")
    return appointment


async def _hold_slots(session: AsyncSession, appointment: Appointment, slots_needed: int) -> None:
    """Write one slot row per 30 minutes, and turn a clash into SlotTaken.

    This is where double-booking is actually stopped. The database refuses a second row
    for the same dentist and time, no matter how close together two requests arrive.
    """
    for t in _slot_times(appointment.start_time, slots_needed):
        repository.add_appointment_slot(
            session,
            AppointmentSlot(
                dentist_id=appointment.dentist_id,
                slot_start_time=t,
                appointment_id=appointment.id,
            ),
        )
    try:
        await session.flush()
    except IntegrityError as exc:
        raise SlotTaken("Sorry, that time was just taken. Please pick another.") from exc


# --- The public functions -----------------------------------------------------------


async def find_available_slots(
    session: AsyncSession,
    service_slug: str,
    first_day: date,
    last_day: date,
    dentist_slug: str | None = None,
) -> list[FreeSlot]:
    """Every time this treatment could be booked in the date range.

    Leave dentist_slug out for "I don't mind who".
    """
    if (last_day - first_day).days > MAX_SEARCH_DAYS:
        raise SchedulingError(f"Please search {MAX_SEARCH_DAYS} days or fewer at a time.")

    async with session.begin():
        treatment = await clinic_service.get_service(session, service_slug)
        if dentist_slug:
            dentists = [await clinic_service.get_dentist(session, dentist_slug)]
        else:
            dentists = await clinic_service.get_dentists(session)

        possible = slots_between(first_day, last_day)
        if not possible:
            return []  # closed every day in the range

        taken = await repository.get_taken_slots(
            session,
            possible[0],
            possible[-1] + _STEP,  # the end is excluded, so go one step past the last slot
            dentist_id=dentists[0].id if dentist_slug else None,
        )

    needed = _slots_needed(treatment.duration_minutes)
    possible_set = set(possible)
    now = utcnow()

    free = []
    for dentist in dentists:
        for start in possible:
            if start <= now:
                continue
            blocks = _slot_times(start, needed)
            fits_opening_hours = all(t in possible_set for t in blocks)
            nothing_booked = all((dentist.id, t) not in taken for t in blocks)
            if fits_opening_hours and nothing_booked:
                free.append(FreeSlot(dentist.id, dentist.slug, start, blocks[-1] + _STEP))

    free.sort(key=lambda slot: (slot.start_time, slot.dentist_id))
    return free


async def book_appointment(
    session: AsyncSession,
    service_slug: str,
    dentist_slug: str,
    start_time: datetime,
    details: PatientDetails,
    user: User | None = None,
) -> Appointment:
    """Book one appointment. Raises SlotTaken if someone else got there first."""
    async with session.begin():
        treatment = await clinic_service.get_service(session, service_slug)
        dentist = await clinic_service.get_dentist(session, dentist_slug)
        needed = _slots_needed(treatment.duration_minutes)
        _check_start_time(start_time, needed)

        patient = await _find_or_create_patient(session, details, user)
        await session.flush()  # gives the new patient an id

        appointment = Appointment(
            patient_id=patient.id,
            dentist_id=dentist.id,
            service_id=treatment.id,
            start_time=start_time,
            end_time=start_time + _STEP * needed,
            status="confirmed",
        )
        repository.add_appointment(session, appointment)
        await session.flush()  # gives the appointment an id, which the slot rows need

        await _hold_slots(session, appointment, needed)

    return appointment


async def cancel_appointment(
    session: AsyncSession,
    appointment_id: int,
    user: User | None = None,
    phone: str | None = None,
) -> Appointment:
    """Mark it cancelled and free the time. The appointment row is kept as history."""
    async with session.begin():
        appointment = await _get_owned_appointment(session, appointment_id, user, phone)
        appointment.status = "cancelled"
        await repository.delete_slots_for_appointment(session, appointment.id)

    return appointment


async def reschedule_appointment(
    session: AsyncSession,
    appointment_id: int,
    new_start_time: datetime,
    user: User | None = None,
    phone: str | None = None,
    new_dentist_slug: str | None = None,
) -> Appointment:
    """Move an appointment to a new time, and optionally a different dentist.

    All in one go. If the new time is taken, nothing moves - the old booking stays
    exactly as it was.
    """
    async with session.begin():
        appointment = await _get_owned_appointment(session, appointment_id, user, phone)
        needed = (appointment.end_time - appointment.start_time) // _STEP
        _check_start_time(new_start_time, needed)

        if new_dentist_slug:
            dentist = await clinic_service.get_dentist(session, new_dentist_slug)
            appointment.dentist_id = dentist.id

        # Free the old time first, so moving 14:00 to 14:30 doesn't clash with itself.
        await repository.delete_slots_for_appointment(session, appointment.id)

        appointment.start_time = new_start_time
        appointment.end_time = new_start_time + _STEP * needed
        await _hold_slots(session, appointment, needed)

    return appointment


async def get_my_upcoming_appointments(
    session: AsyncSession, user: User | None = None, phone: str | None = None
) -> list[Appointment]:
    """Upcoming confirmed appointments for an account holder, or a guest by phone."""
    async with session.begin():
        patient = await _find_patient(session, user, phone)
        if patient is None:
            return []
        return await repository.get_upcoming_appointments(session, patient.id, utcnow())


# --- Checks that change nothing -----------------------------------------------------
# Used to show the patient a summary before anything happens. They apply the same rules
# as the real actions above - and the real actions still check everything again in
# their own transaction, because things can change between the summary and the "yes".


async def check_booking(
    session: AsyncSession, service_slug: str, dentist_slug: str, start_time: datetime, phone: str
):
    """Raise the same error book_appointment would, if this booking wouldn't work right now.
    Returns the treatment and the dentist, for the summary."""
    async with session.begin():
        treatment = await clinic_service.get_service(session, service_slug)
        dentist = await clinic_service.get_dentist(session, dentist_slug)
    _tidy_phone(phone)
    _check_start_time(start_time, _slots_needed(treatment.duration_minutes))

    clinic_day = start_time.replace(tzinfo=UTC).astimezone(_CLINIC_TZ).date()
    free = await find_available_slots(session, service_slug, clinic_day, clinic_day, dentist_slug)
    if start_time not in {slot.start_time for slot in free}:
        raise SlotTaken("Sorry, that time isn't free. Please pick another.")
    return treatment, dentist


async def check_owned_appointment(
    session: AsyncSession, appointment_id: int, user: User | None = None, phone: str | None = None
) -> Appointment:
    """The appointment, if it's upcoming, confirmed and belongs to whoever is asking."""
    async with session.begin():
        return await _get_owned_appointment(session, appointment_id, user, phone)


async def check_reschedule(
    session: AsyncSession,
    appointment_id: int,
    new_start_time: datetime,
    user: User | None = None,
    phone: str | None = None,
) -> Appointment:
    """Raise the same error reschedule_appointment would for the patient or the time.

    Whether the new time is free is only checked when the move really happens: the
    appointment's own current slots can overlap the new time, and only the real move
    (which frees them first) can tell.
    """
    appointment = await check_owned_appointment(session, appointment_id, user, phone)
    _check_start_time(new_start_time, (appointment.end_time - appointment.start_time) // _STEP)
    return appointment
