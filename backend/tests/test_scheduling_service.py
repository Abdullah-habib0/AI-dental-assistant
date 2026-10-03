"""The booking rules, tested directly - no web requests.

Each call gets its own session, the same way each web request does.
"""

import asyncio
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.features.auth.models import User
from app.features.scheduling import service as svc
from app.features.scheduling.models import Appointment, AppointmentSlot, Patient
from tests.conftest import clinic_time, next_monday

ALI = svc.PatientDetails(full_name="Ali Guest", phone="07700 900123")
SARA = svc.PatientDetails(full_name="Sara", phone="07700 900456")


async def run(fn, *args, **kwargs):
    async with SessionLocal() as session:
        return await fn(session, *args, **kwargs)


async def book(start, dentist="omar-haddad", treatment="teeth-whitening", who=ALI, user=None):
    return await run(svc.book_appointment, treatment, dentist, start, who, user=user)


async def free_starts(day, dentist="omar-haddad", treatment="teeth-whitening"):
    slots = await run(svc.find_available_slots, treatment, day, day, dentist)
    return {s.start_time for s in slots}


async def make_user() -> User:
    async with SessionLocal() as session:
        async with session.begin():
            user = User(email="acct@example.com", password_hash="x", full_name="Acct Ali")
            session.add(user)
    return user


# --- Finding free times -------------------------------------------------------------


async def test_empty_day_has_45_whitening_options_across_3_dentists():
    day = next_monday()
    free = await run(svc.find_available_slots, "teeth-whitening", day, day)
    assert len(free) == 45  # 15 each: the 16:30 start would run past closing
    assert free[0].start_time == clinic_time(day, 9, 0)
    assert clinic_time(day, 16, 30) not in {s.start_time for s in free}


async def test_one_dentist_only():
    assert len(await free_starts(next_monday())) == 15


async def test_free_slots_carry_the_slug_needed_to_book_them():
    day = next_monday()
    free = await run(svc.find_available_slots, "teeth-whitening", day, day, "omar-haddad")
    assert {s.dentist_slug for s in free} == {"omar-haddad"}


async def test_weekend_has_nothing():
    saturday = next_monday() + timedelta(days=5)
    assert await free_starts(saturday) == set()


async def test_search_over_31_days_is_refused():
    day = next_monday()
    with pytest.raises(svc.SchedulingError):
        await run(svc.find_available_slots, "teeth-whitening", day, day + timedelta(days=40))


# --- Booking ------------------------------------------------------------------------


async def test_booking_removes_every_overlapping_start():
    day = next_monday()
    appt = await book(clinic_time(day, 13, 0))  # 60 minutes: 13:00 and 13:30

    assert appt.status == "confirmed"
    assert appt.end_time == clinic_time(day, 14, 0)

    free = await free_starts(day)
    assert len(free) == 12
    assert clinic_time(day, 12, 30) not in free  # would run into 13:00
    assert clinic_time(day, 13, 30) not in free
    assert clinic_time(day, 14, 0) in free  # straight after: fine


async def test_same_slot_twice_is_refused():
    start = clinic_time(next_monday(), 13, 0)
    await book(start)
    with pytest.raises(svc.SlotTaken):
        await book(start, who=SARA)


async def test_overlapping_start_is_refused():
    day = next_monday()
    await book(clinic_time(day, 13, 0))
    with pytest.raises(svc.SlotTaken):
        await book(clinic_time(day, 12, 30), who=SARA)


async def test_two_people_same_slot_same_moment_exactly_one_wins():
    """The whole reason the appointment_slots table exists."""
    start = clinic_time(next_monday(), 10, 0)
    outcomes = await asyncio.gather(
        book(start, dentist="mei-tanaka", treatment="check-up-and-clean",
             who=svc.PatientDetails("Racer A", "07700 111111")),
        book(start, dentist="mei-tanaka", treatment="check-up-and-clean",
             who=svc.PatientDetails("Racer B", "07700 222222")),
        return_exceptions=True,
    )
    assert sum(isinstance(o, Appointment) for o in outcomes) == 1
    assert sum(isinstance(o, svc.SlotTaken) for o in outcomes) == 1


@pytest.mark.parametrize(
    "start, reason",
    [
        (lambda d: clinic_time(d, 14, 17), "not on the half hour"),
        (lambda d: clinic_time(d, 16, 30), "60 minutes from 16:30 runs past closing"),
        (lambda d: clinic_time(date.today() - timedelta(days=3), 10, 0), "in the past"),
        (lambda d: clinic_time(d + timedelta(days=100), 10, 0), "over 90 days ahead"),
    ],
)
async def test_bad_times_are_refused(start, reason):
    with pytest.raises(svc.SchedulingError):
        await book(start(next_monday()))


async def test_bad_phone_number_is_refused():
    with pytest.raises(svc.SchedulingError):
        await book(clinic_time(next_monday(), 10, 0), who=svc.PatientDetails("X", "123"))


# --- Whose appointment is it? -------------------------------------------------------


async def test_guest_finds_their_booking_with_phone_written_differently():
    appt = await book(clinic_time(next_monday(), 13, 0))
    mine = await run(svc.get_my_upcoming_appointments, phone="07700-900123")
    assert [a.id for a in mine] == [appt.id]


async def test_unknown_phone_finds_nothing():
    assert await run(svc.get_my_upcoming_appointments, phone="07700 999999") == []


async def test_wrong_phone_and_made_up_id_give_the_same_error():
    appt = await book(clinic_time(next_monday(), 13, 0))
    with pytest.raises(svc.AppointmentNotFound):
        await run(svc.cancel_appointment, appt.id, phone=SARA.phone)
    with pytest.raises(svc.AppointmentNotFound):
        await run(svc.cancel_appointment, 99999, phone=ALI.phone)


async def test_guests_and_account_holders_never_cross():
    user = await make_user()
    await book(clinic_time(next_monday(), 13, 0))  # guest, Ali's phone
    acct_appt = await book(clinic_time(next_monday(), 9, 0), dentist="sarah-whitfield",
                           treatment="check-up-and-clean", who=ALI, user=user)

    async with SessionLocal() as session:
        patients = list(await session.scalars(select(Patient).where(Patient.phone == "07700900123")))
    assert len(patients) == 2  # same phone, but one guest record and one account record

    guest_view = await run(svc.get_my_upcoming_appointments, phone=ALI.phone)
    assert acct_appt.id not in [a.id for a in guest_view]
    with pytest.raises(svc.AppointmentNotFound):
        await run(svc.cancel_appointment, acct_appt.id, phone=ALI.phone)

    account_view = await run(svc.get_my_upcoming_appointments, user=user)
    assert [a.id for a in account_view] == [acct_appt.id]


# --- Rescheduling and cancelling ----------------------------------------------------


async def test_reschedule_onto_its_own_old_time():
    day = next_monday()
    appt = await book(clinic_time(day, 13, 0))
    moved = await run(svc.reschedule_appointment, appt.id, clinic_time(day, 13, 30), phone=ALI.phone)
    assert moved.start_time == clinic_time(day, 13, 30)

    async with SessionLocal() as session:
        slots = sorted(s.slot_start_time for s in await session.scalars(
            select(AppointmentSlot).where(AppointmentSlot.appointment_id == appt.id)))
    assert slots == [clinic_time(day, 13, 30), clinic_time(day, 14, 0)]


async def test_failed_reschedule_leaves_the_booking_untouched():
    day = next_monday()
    appt = await book(clinic_time(day, 13, 0))
    await book(clinic_time(day, 10, 0), treatment="check-up-and-clean", who=SARA)

    with pytest.raises(svc.SlotTaken):
        await run(svc.reschedule_appointment, appt.id, clinic_time(day, 9, 30), phone=ALI.phone)

    async with SessionLocal() as session:
        still = await session.get(Appointment, appt.id)
        slot_count = len(list(await session.scalars(
            select(AppointmentSlot).where(AppointmentSlot.appointment_id == appt.id))))
    assert still.start_time == clinic_time(day, 13, 0)
    assert slot_count == 2


async def test_cancel_frees_the_time_and_keeps_the_record():
    day = next_monday()
    appt = await book(clinic_time(day, 13, 0))

    cancelled = await run(svc.cancel_appointment, appt.id, phone=ALI.phone)
    assert cancelled.status == "cancelled"
    assert clinic_time(day, 13, 0) in await free_starts(day)

    async with SessionLocal() as session:
        assert await session.get(Appointment, appt.id) is not None

    with pytest.raises(svc.SchedulingError):
        await run(svc.cancel_appointment, appt.id, phone=ALI.phone)
