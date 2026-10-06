from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import AgentNotConfigured
from app.core.rate_limiting import chat_per_day, chat_per_minute
from app.db.session import get_session
from app.features.auth.dependencies import OptionalUser
from app.features.chat import service
from app.features.chat.schemas import ChatMessageOut, ChatReply, ChatRequest, ConversationOut

router = APIRouter(prefix="/chat", tags=["chat"])

_Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=ChatReply, dependencies=[Depends(chat_per_minute), Depends(chat_per_day)])
async def send(data: ChatRequest, session: _Session, user: OptionalUser):
    """Send a message to the assistant. Login is optional."""
    try:
        turn = await service.send_message(session, data.message, user, data.conversation_id)
    except service.ConversationNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except service.ConversationFull as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except service.ConversationBusy as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except AgentNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return ChatReply(conversation_id=turn.conversation_id, reply=turn.reply, urgency=turn.urgency)


@router.get("/{conversation_id}", response_model=ConversationOut)
async def read(conversation_id: str, session: _Session, user: OptionalUser):
    """A conversation as the patient sees it - their messages and the assistant's replies."""
    try:
        conversation, messages = await service.get_conversation(session, conversation_id, user)
    except service.ConversationNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        messages=[
            ChatMessageOut(
                role="patient" if m.role == "human" else "assistant",
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )
