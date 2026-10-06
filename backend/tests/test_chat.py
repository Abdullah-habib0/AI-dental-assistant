"""Chat: conversations are kept, private, capped, and the agent can still book mid-chat.

The agent's model is a fake (see test_agent.py), so no LLM is called.
"""

import asyncio

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from sqlalchemy import select

from app.agent import prompts, tools
from app.agent.graph import build_agent_graph
from app.agent.llm import AgentNotConfigured
from app.db.session import SessionLocal
from app.features.chat import service
from app.features.chat.models import Message
from app.features.scheduling.models import Appointment
from tests.conftest import next_monday
from tests.test_agent import calls, scripted

CHAT = "/api/v1/chat"


class EchoHistory(BaseChatModel):
    """Replies with every patient message it was given, so a test can see the history."""

    delay: float = 0.0

    @property
    def _llm_type(self) -> str:
        return "echo-history"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        said = " | ".join(m.content for m in messages if m.type == "human")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(said))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        await asyncio.sleep(self.delay)
        return self._generate(messages)


def use_agent(monkeypatch, model, urgency="routine"):
    async def classify(_message):
        return urgency
    graph = build_agent_graph(model, classify, tools.ALL_TOOLS)
    monkeypatch.setattr(service, "get_agent", lambda: graph)


async def register(client, email):
    r = await client.post("/api/v1/auth/register",
                          json={"email": email, "password": "correcthorse", "full_name": "Ali"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- Conversations ------------------------------------------------------------------


async def test_first_message_starts_a_conversation(client, monkeypatch):
    use_agent(monkeypatch, EchoHistory())
    r = await client.post(CHAT, json={"message": "  Hello there  "})
    assert r.status_code == 200
    body = r.json()
    assert len(body["conversation_id"]) == 32  # long and random, not 1, 2, 3
    assert body["reply"] == "Hello there"
    assert body["urgency"] == "routine"


async def test_the_agent_sees_the_earlier_messages(client, monkeypatch):
    use_agent(monkeypatch, EchoHistory())
    first = (await client.post(CHAT, json={"message": "first"})).json()
    second = (await client.post(CHAT, json={"message": "second", "conversation_id": first["conversation_id"]})).json()
    assert second["reply"] == "first | second"
    assert second["conversation_id"] == first["conversation_id"]


async def test_reading_a_conversation_shows_only_what_a_person_would_see(client, monkeypatch):
    use_agent(monkeypatch, scripted(
        calls("find_available_times", service_slug="teeth-whitening", first_day=next_monday().isoformat()),
        AIMessage("Monday has free times."),
    ))
    started = (await client.post(CHAT, json={"message": "Any whitening on Monday?"})).json()

    r = await client.get(f"{CHAT}/{started['conversation_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Any whitening on Monday?"
    assert [(m["role"], m["content"]) for m in body["messages"]] == [
        ("patient", "Any whitening on Monday?"),
        ("assistant", "Monday has free times."),
    ]
    # ...while the tool call and its result are still saved, for the agent's next turn.
    async with SessionLocal() as session:
        roles = [m.role for m in await session.scalars(select(Message).order_by(Message.position))]
    assert roles == ["human", "ai", "tool", "ai"]


async def test_unknown_conversation_is_404(client, monkeypatch):
    use_agent(monkeypatch, EchoHistory())
    assert (await client.get(f"{CHAT}/{'0' * 32}")).status_code == 404
    r = await client.post(CHAT, json={"message": "hi", "conversation_id": "0" * 32})
    assert r.status_code == 404


async def test_a_logged_in_conversation_is_private_to_that_account(client, monkeypatch):
    use_agent(monkeypatch, EchoHistory())
    ali = await register(client, "ali@example.com")
    sara = await register(client, "sara@example.com")
    conversation_id = (await client.post(CHAT, json={"message": "my secret"}, headers=ali)).json()["conversation_id"]

    assert (await client.get(f"{CHAT}/{conversation_id}", headers=ali)).status_code == 200
    assert (await client.get(f"{CHAT}/{conversation_id}", headers=sara)).status_code == 404
    assert (await client.get(f"{CHAT}/{conversation_id}")).status_code == 404  # guest
    r = await client.post(CHAT, json={"message": "hi", "conversation_id": conversation_id}, headers=sara)
    assert r.status_code == 404


# --- Safety, limits and failures ----------------------------------------------------


async def test_safety_replies_are_saved_and_marked(client, monkeypatch):
    use_agent(monkeypatch, scripted(), urgency="emergency")
    body = (await client.post(CHAT, json={"message": "I can't breathe properly, my face is swollen"})).json()
    assert body["urgency"] == "emergency"
    assert body["reply"] == prompts.emergency_reply()

    async with SessionLocal() as session:
        reply = await session.scalar(select(Message).where(Message.role == "ai"))
    assert reply.urgency == "emergency"  # findable later, for review


async def test_a_conversation_is_capped(client, monkeypatch):
    use_agent(monkeypatch, EchoHistory())
    monkeypatch.setattr(service, "MAX_PATIENT_MESSAGES", 2)
    conversation_id = (await client.post(CHAT, json={"message": "one"})).json()["conversation_id"]
    await client.post(CHAT, json={"message": "two", "conversation_id": conversation_id})
    r = await client.post(CHAT, json={"message": "three", "conversation_id": conversation_id})
    assert r.status_code == 429


@pytest.mark.parametrize("message", ["", "   ", "x" * 2001])
async def test_empty_or_huge_messages_are_refused(client, message):
    assert (await client.post(CHAT, json={"message": message})).status_code == 422


async def test_missing_groq_key_is_a_clear_503(client, monkeypatch):
    def not_configured():
        raise AgentNotConfigured("GROQ_API_KEY is not set")
    monkeypatch.setattr(service, "get_agent", not_configured)
    r = await client.post(CHAT, json={"message": "hi"})
    assert r.status_code == 503
    assert "GROQ_API_KEY" in r.json()["detail"]


async def test_two_messages_at_once_cannot_jumble_the_history(client, monkeypatch):
    use_agent(monkeypatch, EchoHistory(delay=0.3))
    conversation_id = (await client.post(CHAT, json={"message": "start"})).json()["conversation_id"]

    a, b = await asyncio.gather(
        client.post(CHAT, json={"message": "A", "conversation_id": conversation_id}),
        client.post(CHAT, json={"message": "B", "conversation_id": conversation_id}),
    )
    assert sorted([a.status_code, b.status_code]) == [200, 409]

    async with SessionLocal() as session:
        positions = [m.position for m in await session.scalars(select(Message).order_by(Message.position))]
    assert positions == list(range(len(positions)))  # no gaps, no doubles


# --- The database stays unlocked while the agent thinks ------------------------------


async def test_the_agent_can_book_in_the_middle_of_a_chat(client, monkeypatch):
    """If chat held the database lock while the agent ran, this booking would wait for it
    and fail. It must go through.

    Also checks the two-step booking works across real saved conversation history: the
    prepared summary is saved in one message, loaded back, and confirmed in the next.
    """
    start_time = f"{next_monday().isoformat()} 10:00"
    use_agent(monkeypatch, scripted(
        calls("prepare_booking", service_slug="check-up-and-clean", dentist_slug="omar-haddad",
              start_time=start_time, full_name="Ali Khan", phone="07700 900123"),
        AIMessage("Shall I book a check-up with Dr Omar Haddad at 10:00?"),
    ))
    first = (await client.post(CHAT, json={"message": "Book me a check-up at 10"})).json()

    use_agent(monkeypatch, scripted(calls("confirm_action"), AIMessage("You're booked in.")))
    r = await client.post(CHAT, json={"message": "Yes please", "conversation_id": first["conversation_id"]})
    assert r.json()["reply"] == "You're booked in."

    async with SessionLocal() as session:
        assert await session.scalar(select(Appointment)) is not None


# --- History trimming ---------------------------------------------------------------


def test_trimmed_history_starts_at_a_patient_message():
    history = [
        HumanMessage("1"), AIMessage("", tool_calls=[{"name": "find_my_appointments", "args": {}, "id": "a"}]),
        ToolMessage("prices", tool_call_id="a"), AIMessage("answer"),
        HumanMessage("2"), AIMessage("reply"),
    ]
    assert service.recent(history, 10) == history
    # A cut of 4 would start at the tool result - so it moves forward to "2".
    assert [m.content for m in service.recent(history, 4)] == ["2", "reply"]


def test_old_tool_results_are_dropped_in_pairs():
    def turn(n):
        return [
            HumanMessage(f"q{n}"),
            AIMessage("", tool_calls=[{"name": "find_my_appointments", "args": {}, "id": f"t{n}"}]),
            ToolMessage(f"result{n}", tool_call_id=f"t{n}"),
            AIMessage(f"a{n}"),
        ]

    history = turn(1) + turn(2) + turn(3)
    kept = service.without_old_tool_results(history, keep_turns=2)

    # Turn 1 keeps only its text; turns 2 and 3 keep their tool calls and results.
    assert [m.content for m in kept] == ["q1", "a1", "q2", "", "result2", "a2", "q3", "", "result3", "a3"]
    # Every tool result still has the call that asked for it, and vice versa.
    call_ids = {c["id"] for m in kept if isinstance(m, AIMessage) for c in m.tool_calls}
    result_ids = {m.tool_call_id for m in kept if isinstance(m, ToolMessage)}
    assert call_ids == result_ids == {"t2", "t3"}
