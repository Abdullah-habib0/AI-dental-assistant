"""Web addresses for scheduling.

Login is optional everywhere. Logged in: your account decides which appointments are
yours. Guest: the phone number you booked with does.

Cancel and reschedule are POST, not DELETE/PATCH, because a guest has to send their
phone number in the body, and DELETE requests with a body are poorly supported.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.auth.dependencies import OptionalUser
from app.features.clinic import service as clinic_service
from app.features.scheduling import service
from app.features.scheduling.models import Appointment
from app.features.scheduling.schemas import (
    AppointmentOut,
    BookingRequest,
    FreeSlotOut,
    GuestPhone,
    RescheduleRequest,
)

router = APIRouter(tags=["scheduling"])

_Session = Annotated[AsyncSession, Depends(get_session)]

# What each kind of failure means to the website. Order matters: the specific errors
# are checked before SchedulingError, which they are all kinds of.
_ERROR_STATUS = [
    (clinic_service.NotFound, status.HTTP_404_NOT_FOUND),
    (service.AppointmentNotFound, status.HTTP_404_NOT_FOUND),
    (service.SlotTaken, status.HTTP_409_CONFLICT),
    (service.SchedulingError, status.HTTP_400_BAD_REQUEST),
]
_HANDLED = (clinic_service.NotFound, service.SchedulingError)


def _http_error(exc: Exception) -> HTTPException:
    code = next(code for kind, code in _ERROR_STATUS if isinstance(exc, kind))
    return HTTPException(status_code=code, detail=str(exc))


async def _describe(session: AsyncSession, appointments: list[Appointment]) -> list[AppointmentOut]:
    """Swap the ids for slugs and names, which is what the website can actually use."""
    services = {s.id: s for s in await clinic_service.get_services(session)}
    dentists = {d.id: d for d in await clinic_service.get_dentists(session)}
    return [
        AppointmentOut(
            id=a.id,
            service_slug=services[a.service_id].slug,
            service_name=services[a.service_id].name,
            dentist_slug=dentists[a.dentist_id].slug,
            dentist_name=dentists[a.dentist_id].name,
            start_time=a.start_time,
            end_time=a.end_time,
            status=a.status,
        )
        for a in appointments
    ]


@router.get("/availability", response_model=list[FreeSlotOut])
async def availability(
    session: _Session,
    service_slug: str,
    first_day: date,
    last_day: date | None = None,
    dentist_slug: str | None = None,
):
    """Free times for a treatment. Leave last_day out for one day; dentist_slug for anyone."""
    try:
        return await service.find_available_slots(
            session, service_slug, first_day, last_day or first_day, dentist_slug
        )
    except _HANDLED as exc:
        raise _http_error(exc) from exc


@router.post("/appointments", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def book(data: BookingRequest, session: _Session, user: OptionalUser):
    try:
        appointment = await service.book_appointment(
            session,
            data.service_slug,
            data.dentist_slug,
            data.start_time,
            service.PatientDetails(data.full_name, data.phone, data.email),
            user=user,
        )
    except _HANDLED as exc:
        raise _http_error(exc) from exc
    return (await _describe(session, [appointment]))[0]


@router.post("/appointments/mine", response_model=list[AppointmentOut])
async def my_appointments(data: GuestPhone, session: _Session, user: OptionalUser):
    """Your upcoming appointments. POST so a guest's phone number stays out of the URL."""
    if user is None and not data.phone:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Log in, or give the phone number you booked with.")
    try:
        appointments = await service.get_my_upcoming_appointments(session, user=user, phone=data.phone)
    except _HANDLED as exc:
        raise _http_error(exc) from exc
    return await _describe(session, appointments)


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
async def cancel(appointment_id: int, data: GuestPhone, session: _Session, user: OptionalUser):
    try:
        appointment = await service.cancel_appointment(
            session, appointment_id, user=user, phone=data.phone
        )
    except _HANDLED as exc:
        raise _http_error(exc) from exc
    return (await _describe(session, [appointment]))[0]


@router.post("/appointments/{appointment_id}/reschedule", response_model=AppointmentOut)
async def reschedule(
    appointment_id: int, data: RescheduleRequest, session: _Session, user: OptionalUser
):
    try:
        appointment = await service.reschedule_appointment(
            session,
            appointment_id,
            data.new_start_time,
            user=user,
            phone=data.phone,
            new_dentist_slug=data.new_dentist_slug,
        )
    except _HANDLED as exc:
        raise _http_error(exc) from exc
    return (await _describe(session, [appointment]))[0]
