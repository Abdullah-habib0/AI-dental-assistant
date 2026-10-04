"""Turns the clinic's opening hours into bookable start times.

This answers one question: "what times could someone book, if nobody had booked anything
yet?" It knows nothing about bookings. service.py takes this list and removes the times
already in appointment_slots - what is left is what is free.

Every time returned here is UTC with no timezone label, like everything in the database.
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings

_CLINIC_TZ = ZoneInfo(settings.clinic_timezone)
_STEP = timedelta(minutes=settings.slot_minutes)


def slots_for_day(day: date) -> list[datetime]:
    """Every slot start time on one date. Empty if the clinic is closed that day."""
    if day.weekday() not in settings.open_weekdays:
        return []

    # Built in clinic time, because the clinic opens at 9:00 London time all year round.
    # Converting each slot to UTC afterwards handles the clock changes automatically.
    slot = datetime(day.year, day.month, day.day, settings.opening_hour, tzinfo=_CLINIC_TZ)
    closing = datetime(day.year, day.month, day.day, settings.closing_hour, tzinfo=_CLINIC_TZ)

    slots = []
    # "slot + _STEP" is when this slot ENDS. Checking that, not the start, is what makes
    # the last slot 16:30 - a slot starting at 17:00 would end after closing.
    while slot + _STEP <= closing:
        slots.append(slot.astimezone(UTC).replace(tzinfo=None))
        slot += _STEP

    return slots


def slots_between(first_day: date, last_day: date) -> list[datetime]:
    """Every slot start time from first_day to last_day, including both days."""
    slots = []
    day = first_day
    while day <= last_day:
        slots.extend(slots_for_day(day))
        day += timedelta(days=1)
    return slots


def is_slot_start(moment: datetime) -> bool:
    """Is this exactly one of the bookable start times?

    Stops a booking at 14:17, or on a Sunday, or at 3am, from ever getting through.
    """
    if moment.tzinfo is not None:
        # Every time in this app is UTC with no label. A labelled time here means a
        # bug somewhere upstream, so fail loudly rather than quietly give a wrong answer.
        raise ValueError("Expected a UTC time with no timezone label.")

    # Which clinic day does this moment fall on? Usually the same as the UTC date, but
    # not always - so ask, rather than assume.
    clinic_day = moment.replace(tzinfo=UTC).astimezone(_CLINIC_TZ).date()
    return moment in slots_for_day(clinic_day)
