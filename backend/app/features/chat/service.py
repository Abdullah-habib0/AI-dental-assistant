"""Chat: keep conversations, and pass each new message to the agent.

One message is handled in three steps:

  1. Load    - check the conversation is yours, read its history. Short transaction.
  2. Think   - the agent answers. NO transaction is open during this step.
  3. Save    - store the patient's message and everything the agent added. Short
               transaction.

Step 2 must run with the database unlocked. The agent's tools book and cancel
appointments, and each of those takes the database's write lock. If chat held a
transaction across the agent's few seconds of thinking, every booking would wait for it
and then fail.
"""

import uuid
from dataclasses import dataclass

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
    messages_from_dict,
    messages_to_dict,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import run_turn
from app.agent.llm import get_agent
from app.features.auth.models import User
from app.features.chat import repository
from app.features.chat.models import Conversation, Message

# A cap per conversation, so one chat left running can't use up the free LLM allowance.
MAX_PATIENT_MESSAGES = 50
# How much history the agent is given. Older messages are left out to keep each request
# small and fast; the full conversation is still saved.
HISTORY_LIMIT = 40
# Tool results (lists of free times, document passages) are large, and Groq's free tier
# allows only 8,000 tokens a minute. Only the last few turns' tool results are sent;
# older turns are sent as just the conversation text. Two turns covers "here are the
# times" -> "2pm please" -> "yes, book it".
TOOL_RESULT_TURNS = 2

_ROLES = {"human": "human", "ai": "ai", "tool": "tool"}


class ConversationNotFound(Exception):
    """No such conversation - or it belongs to someone else. Deliberately one error for
    both, so nobody can find out which conversation ids exist."""


class ConversationFull(Exception):
    pass


class ConversationBusy(Exception):
    """Another message in this conversation was answered at the same moment."""


@dataclass
class ChatTurn:
    conversation_id: str
    reply: str
    urgency: str
    failure: str | None = None  # why the agent couldn't answer, if it couldn't (see TurnResult)


async def send_message(
    session: AsyncSession, message: str, user: User | None, conversation_id: str | None = None
) -> ChatTurn:
    # 1. Load. Nothing is created yet: if the agent fails to start, no empty
    #    conversation is left behind.
    async with session.begin():
        if conversation_id is None:
            conversation, stored = None, []
        else:
            conversation = await _get_owned(session, conversation_id, user)
            if await repository.count_patient_messages(session, conversation_id) >= MAX_PATIENT_MESSAGES:
                raise ConversationFull("This conversation is full. Please start a new one.")
            stored = await repository.get_messages(session, conversation_id)

    # 2. Think. The database is unlocked here.
    agent = get_agent()
    history = messages_from_dict([m.payload for m in stored])
    turn = await run_turn(agent, for_agent(history), message, user)

    # 3. Save.
    try:
        async with session.begin():
            if conversation is None:
                conversation = Conversation(
                    id=uuid.uuid4().hex,
                    user_id=user.id if user else None,
                    title=_title_from(message),
                )
                repository.add_conversation(session, conversation)
            repository.add_messages(session, _to_rows(conversation.id, len(stored), turn.new_messages, turn.urgency))
    except IntegrityError as exc:
        raise ConversationBusy("Still answering your previous message - please wait a moment.") from exc

    return ChatTurn(conversation.id, turn.reply, turn.urgency, turn.failure)


async def get_conversation(
    session: AsyncSession, conversation_id: str, user: User | None
) -> tuple[Conversation, list[Message]]:
    """The conversation and the messages a person would see (no tool calls)."""
    async with session.begin():
        conversation = await _get_owned(session, conversation_id, user)
        messages = await repository.get_messages(session, conversation_id)
    visible = [m for m in messages if m.role in ("human", "ai") and m.content.strip()]
    return conversation, visible


def for_agent(history: list[BaseMessage]) -> list[BaseMessage]:
    """The part of the history worth sending to the agent: recent, and without old tool results."""
    return without_old_tool_results(recent(history, HISTORY_LIMIT), TOOL_RESULT_TURNS)


def without_old_tool_results(history: list[BaseMessage], keep_turns: int) -> list[BaseMessage]:
    """Drop tool calls and their results from all but the last `keep_turns` turns.

    A tool call and its result are always dropped together - the LLM service rejects a
    result whose call is missing, and a call whose result is missing.
    """
    starts = [i for i, m in enumerate(history) if isinstance(m, HumanMessage)]
    if len(starts) <= keep_turns:
        return history
    cut = starts[-keep_turns] if keep_turns else len(history)
    older = [
        m for m in history[:cut]
        if not isinstance(m, ToolMessage) and not (isinstance(m, AIMessage) and m.tool_calls)
    ]
    return older + history[cut:]


def recent(history: list[BaseMessage], limit: int) -> list[BaseMessage]:
    """The last part of the history, starting at one of the patient's messages.

    Cutting anywhere else could split a tool call from its result, and the LLM service
    rejects a conversation where a tool result appears without the call that asked for it.
    """
    if len(history) <= limit:
        return history
    tail = history[-limit:]
    for index, message in enumerate(tail):
        if isinstance(message, HumanMessage):
            return tail[index:]
    return []


async def _get_owned(session: AsyncSession, conversation_id: str, user: User | None) -> Conversation:
    conversation = await repository.get_conversation(session, conversation_id)
    if conversation is None:
        raise ConversationNotFound("Conversation not found.")
    # A conversation started while logged in is private to that account. A guest
    # conversation can be opened by whoever holds its id.
    if conversation.user_id is not None and (user is None or user.id != conversation.user_id):
        raise ConversationNotFound("Conversation not found.")
    return conversation


def _title_from(message: str) -> str:
    title = " ".join(message.split())
    return title if len(title) <= 80 else title[:77].rstrip() + "..."


def _to_rows(conversation_id: str, start: int, messages: list[BaseMessage], urgency: str) -> list[Message]:
    rows = []
    for offset, (message, payload) in enumerate(zip(messages, messages_to_dict(messages))):
        is_reply = isinstance(message, AIMessage) and offset == len(messages) - 1
        rows.append(
            Message(
                conversation_id=conversation_id,
                position=start + offset,
                role=_ROLES[message.type],
                content=message.content if isinstance(message.content, str) else "",
                payload=payload,
                urgency=urgency if is_reply and urgency != "routine" else None,
            )
        )
    return rows
