"""Database queries for the clinic feature. Queries only - nothing here ever saves."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.clinic.models import Dentist, Faq, Service


async def list_services(session: AsyncSession) -> list[Service]:
    result = await session.scalars(select(Service).order_by(Service.name))
    return list(result)


async def get_service_by_slug(session: AsyncSession, slug: str) -> Service | None:
    return await session.scalar(select(Service).where(Service.slug == slug))


async def list_dentists(session: AsyncSession) -> list[Dentist]:
    result = await session.scalars(select(Dentist).order_by(Dentist.name))
    return list(result)


async def get_dentist_by_slug(session: AsyncSession, slug: str) -> Dentist | None:
    return await session.scalar(select(Dentist).where(Dentist.slug == slug))


async def list_faqs(session: AsyncSession) -> list[Faq]:
    result = await session.scalars(select(Faq).order_by(Faq.category, Faq.id))
    return list(result)
