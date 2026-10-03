"""What goes in and out of the scheduling API.

Times are where most bugs would come from, so there are two rules:

  Coming in   A time must say which timezone it is in, e.g. "2026-10-05T13:00:00+01:00"
              or "2026-10-05T12:00:00Z". A bare "13:00" is refused - we can't guess
              whether the person meant London time or UTC. It is then turned into UTC
              with no label, like everything else inside the app.

  Going out   Every time is sent as UTC with the label on ("...Z"), so the website
              can't mistake it for local time. The website converts it for display.
"""

from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, EmailStr, Field, field_validator


def _to_stored_utc(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


def _label_as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC)


# --- Coming in ----------------------------------------------------------------------


class BookingRequest(BaseModel):
    service_slug: str
    dentist_slug: str
    start_time: AwareDatetime
    full_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=1, max_length=30)
    email: EmailStr | None = None

    store_as_utc = field_validator("start_time")(_to_stored_utc)


class GuestPhone(BaseModel):
    """How a guest proves an appointment is theirs. Ignored when logged in.

    Sent in the body rather than the web address, so phone numbers don't end up in
    server logs and browser history.
    """

    phone: str | None = Field(default=None, max_length=30)


class RescheduleRequest(GuestPhone):
    new_start_time: AwareDatetime
    new_dentist_slug: str | None = None

    store_as_utc = field_validator("new_start_time")(_to_stored_utc)


# --- Going out ----------------------------------------------------------------------


class FreeSlotOut(BaseModel):
    dentist_slug: str
    start_time: datetime
    end_time: datetime

    send_as_utc = field_validator("start_time", "end_time")(_label_as_utc)


class AppointmentOut(BaseModel):
    id: int
    service_slug: str
    service_name: str
    dentist_slug: str
    dentist_name: str
    start_time: datetime
    end_time: datetime
    status: str

    send_as_utc = field_validator("start_time", "end_time")(_label_as_utc)
