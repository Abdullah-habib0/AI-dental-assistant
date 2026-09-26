from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.clinic import service
from app.features.clinic.schemas import (
    ClinicInfo,
    DentistOut,
    FaqOut,
    ServiceDetail,
    ServiceSummary,
)

router = APIRouter(tags=["clinic"])


@router.get("/services", response_model=list[ServiceSummary])
async def list_services(session: AsyncSession = Depends(get_session)):
    return await service.get_services(session)


@router.get("/services/{slug}", response_model=ServiceDetail)
async def get_service(slug: str, session: AsyncSession = Depends(get_session)):
    try:
        return await service.get_service(session, slug)
    except service.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/dentists", response_model=list[DentistOut])
async def list_dentists(session: AsyncSession = Depends(get_session)):
    return await service.get_dentists(session)


@router.get("/dentists/{slug}", response_model=DentistOut)
async def get_dentist(slug: str, session: AsyncSession = Depends(get_session)):
    try:
        return await service.get_dentist(session, slug)
    except service.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/faqs", response_model=list[FaqOut])
async def list_faqs(session: AsyncSession = Depends(get_session)):
    return await service.get_faqs(session)


@router.get("/clinic", response_model=ClinicInfo)
async def get_clinic():
    return service.get_clinic_info()
