from fastapi import APIRouter

from app.features.clinic.routes import router as clinic_router

api_router = APIRouter()
api_router.include_router(clinic_router)
