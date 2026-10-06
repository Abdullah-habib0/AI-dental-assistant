from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    # A long random string, not 1, 2, 3... Guests have no login, so knowing a
    # conversation's id is what lets them come back to it. A counting number could be
    # guessed, and anyone could read anyone else's chat.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # Empty for guests. When set, only that user can open the conversation.
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class Message(Base):
    """Every message in a conversation, including the agent's tool calls and their
    results, so the next turn sees exactly what the agent saw."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('human', 'ai', 'tool')", name="role_is_valid"),
        # Two replies being saved into the same conversation at once can't both take
        # the same place - the second one is refused instead of jumbling the history.
        UniqueConstraint("conversation_id", "position", name="one_message_per_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # 0, 1, 2... in order
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # what a person would read
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)  # the full message, for the agent
    # Set on the assistant's reply when the safety check didn't say "routine", so urgent
    # and emergency conversations can be found and reviewed later.
    urgency: Mapped[str | None] = mapped_column(String(12), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
