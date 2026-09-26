"""The rules for the clinic feature.

Both the website routes and the AI agent's tools call these functions. Neither of them
talks to the database directly, so the rules only ever exist in one place.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.clinic import repository
from app.features.clinic.models import Dentist, Faq, Service
from app.features.clinic.schemas import ClinicInfo


class NotFound(Exception):
    """Something was asked for that does not exist.

    This is a plain error, not a web error, because the AI agent calls these functions
    too and it has no idea what a 404 is. routes.py turns it into a 404 for the website.
    """


async def get_services(session: AsyncSession) -> list[Service]:
    return await repository.list_services(session)


async def get_service(session: AsyncSession, slug: str) -> Service:
    service = await repository.get_service_by_slug(session, slug)
    if service is None:
        raise NotFound(f"No service called '{slug}'.")
    return service


async def get_dentists(session: AsyncSession) -> list[Dentist]:
    return await repository.list_dentists(session)


async def get_dentist(session: AsyncSession, slug: str) -> Dentist:
    dentist = await repository.get_dentist_by_slug(session, slug)
    if dentist is None:
        raise NotFound(f"No dentist called '{slug}'.")
    return dentist


async def get_faqs(session: AsyncSession) -> list[Faq]:
    return await repository.list_faqs(session)


def get_clinic_info() -> ClinicInfo:
    """Read from settings, not the database - there is only ever one clinic."""
    return ClinicInfo(
        name=settings.clinic_name,
        phone=settings.clinic_phone,
        email=settings.clinic_email,
        address=settings.clinic_address,
        timezone=settings.clinic_timezone,
        opening_hour=settings.opening_hour,
        closing_hour=settings.closing_hour,
        open_weekdays=list(settings.open_weekdays),
    )
