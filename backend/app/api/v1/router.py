from fastapi import APIRouter

from app.features.auth.routes import router as auth_router
from app.features.chat.routes import router as chat_router
from app.features.clinic.routes import router as clinic_router
from app.features.knowledge.routes import router as knowledge_router
from app.features.scheduling.routes import router as scheduling_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(chat_router)
api_router.include_router(clinic_router)
api_router.include_router(knowledge_router)
api_router.include_router(scheduling_router)
