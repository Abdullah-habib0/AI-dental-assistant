"""Database queries for chat. Queries only - nothing here commits."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.chat.models import Conversation, Message


async def get_conversation(session: AsyncSession, conversation_id: str) -> Conversation | None:
    return await session.get(Conversation, conversation_id)


def add_conversation(session: AsyncSession, conversation: Conversation) -> None:
    session.add(conversation)


async def get_messages(session: AsyncSession, conversation_id: str) -> list[Message]:
    result = await session.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.position)
    )
    return list(result)


async def count_patient_messages(session: AsyncSession, conversation_id: str) -> int:
    return await session.scalar(
        select(func.count()).where(Message.conversation_id == conversation_id, Message.role == "human")
    )


def add_messages(session: AsyncSession, messages: list[Message]) -> None:
    session.add_all(messages)
