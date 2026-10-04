"""Opening hours -> 30-minute slots. Plain functions, no database.

Fixed dates are fine here: nothing in this file cares what today is. October and
November 2026 are used on purpose, because the UK clocks go back on 25 October.
"""

from datetime import UTC, date, datetime

import pytest

from app.features.scheduling.opening_hrs import is_slot_start, slots_between, slots_for_day


def test_summer_monday_has_16_slots_from_0800_utc():
    slots = slots_for_day(date(2026, 10, 5))  # London is UTC+1
    assert len(slots) == 16
    assert slots[0] == datetime(2026, 10, 5, 8, 0)
    assert slots[-1] == datetime(2026, 10, 5, 15, 30)


def test_winter_monday_has_16_slots_from_0900_utc():
    slots = slots_for_day(date(2026, 11, 2))  # London is UTC+0
    assert len(slots) == 16
    assert slots[0] == datetime(2026, 11, 2, 9, 0)
    assert slots[-1] == datetime(2026, 11, 2, 16, 30)


@pytest.mark.parametrize("day", [date(2026, 10, 3), date(2026, 10, 25)])
def test_weekends_are_closed(day):
    assert slots_for_day(day) == []  # 25 Oct is also the day the clocks change


def test_range_across_the_clock_change():
    slots = slots_between(date(2026, 10, 19), date(2026, 11, 1))  # 10 open days
    assert len(slots) == 160
    first_on = lambda d: min(s for s in slots if s.date() == d)  # noqa: E731
    assert first_on(date(2026, 10, 23)).hour == 8  # Friday before: 9:00 London = 08:00 UTC
    assert first_on(date(2026, 10, 26)).hour == 9  # Monday after:  9:00 London = 09:00 UTC


def test_range_backwards_is_empty():
    assert slots_between(date(2026, 10, 9), date(2026, 10, 5)) == []


@pytest.mark.parametrize(
    "moment, expected",
    [
        (datetime(2026, 10, 5, 8, 0), True),  # 09:00 London, opening
        (datetime(2026, 10, 5, 15, 30), True),  # 16:30 London, last slot
        (datetime(2026, 10, 5, 8, 17), False),  # not on the half hour
        (datetime(2026, 10, 5, 16, 0), False),  # 17:00 London, closed
        (datetime(2026, 10, 3, 9, 0), False),  # Saturday
        (datetime(2026, 10, 5, 3, 0), False),  # middle of the night
    ],
)
def test_is_slot_start(moment, expected):
    assert is_slot_start(moment) is expected


def test_is_slot_start_refuses_a_labelled_time():
    with pytest.raises(ValueError):
        is_slot_start(datetime(2026, 10, 5, 8, 0, tzinfo=UTC))
