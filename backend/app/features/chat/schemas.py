from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    # Leave out to start a new conversation; send back the id you were given to continue.
    conversation_id: str | None = Field(default=None, max_length=32)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message can't be empty.")
        return value.strip()


class ChatReply(BaseModel):
    conversation_id: str
    reply: str
    # "routine", or "urgent" / "emergency" when the safety check stepped in, so the
    # website can show those replies differently. "unavailable" if the check failed.
    urgency: str


class ChatMessageOut(BaseModel):
    role: Literal["patient", "assistant"]
    content: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def label_as_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC)


class ConversationOut(BaseModel):
    id: str
    title: str
    messages: list[ChatMessageOut]
