from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.init_db import create_tables
from app.db.session import engine
from app.features.knowledge.service import close_knowledge_base


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await create_tables(engine)  # runs on startup
    yield
    # Runs on shutdown.
    await engine.dispose()
    close_knowledge_base()  # frees the Qdrant folder for the ingest script


app = FastAPI(title=f"{settings.clinic_name} - AI Front Desk", lifespan=lifespan)

# Browsers block a page on one address from calling an API on another unless the API
# allows it. Only the listed websites are allowed. Logins travel in the Authorization
# header, not in cookies, so credentials (cookies) stay switched off.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
