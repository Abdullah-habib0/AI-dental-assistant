"""A search address for trying the knowledge base out, e.g. from the /docs page.

The AI agent doesn't use this - it calls the knowledge base directly.
"""

import asyncio

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.features.knowledge.service import (
    KnowledgeIndexOutdated,
    KnowledgeNotIngested,
    get_knowledge_base,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class PassageOut(BaseModel):
    document: str
    heading: str
    text: str
    source: str
    pages: list[int]
    score: float


@router.get("/search", response_model=list[PassageOut])
async def search(q: str = Query(min_length=1, max_length=1000), limit: int = Query(4, ge=1, le=10)):
    """Chunks that best match the question. An empty list means nothing was relevant enough."""
    # The first call loads the model, which takes several seconds of CPU work, so it runs
    # in a thread rather than holding up every other request.
    knowledge = await asyncio.to_thread(get_knowledge_base)
    try:
        return await knowledge.search(q, limit=limit)
    except (KnowledgeNotIngested, KnowledgeIndexOutdated) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
