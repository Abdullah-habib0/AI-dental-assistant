"""The agent: its tools, the safety routing, and the graph wiring.

No real LLM is called. A fake model replies from a script, so these tests check the
plumbing - which way a message goes, what tools return, that the login reaches the tools
- quickly and for free. How well the real model behaves is measured by the eval suite.
"""

import itertools
from datetime import datetime

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage

from app.agent import prompts, tools
from app.agent.graph import build_agent_graph, run_turn
from sqlalchemy import select

from app.db.session import SessionLocal
from app.features.auth.models import User
from app.features.clinic import service as clinic_service
from app.features.knowledge.service import Passage
from app.features.scheduling import service as scheduling
from app.features.scheduling.models import Appointment
from tests.conftest import clinic_time, next_monday

GUEST = {"configurable": {"user": None}}
ALI_PHONE = "07700 900123"


class FakeModel(GenericFakeChatModel):
    """Replies with the scripted messages, in order. Ignores the tools it's given."""

    def bind_tools(self, tools, **kwargs):
        return self


def scripted(*replies):
    return FakeModel(messages=iter(replies))


def calls(name, **args):
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call_{name}"}])


def graph_with(model, urgency="routine"):
    async def classify(_message):
        return urgency
    return build_agent_graph(model, classify, tools.ALL_TOOLS)


async def make_user() -> User:
    async with SessionLocal() as session:
        async with session.begin():
            user = User(email="ali@example.com", password_hash="x", full_name="Ali Khan")
            session.add(user)
    return user


def monday_at(hour, minute=0):
    return f"{next_monday().isoformat()} {hour:02d}:{minute:02d}"


async def book_directly(start: str, user=None, treatment="check-up-and-clean", dentist="mei-tanaka"):
    """Set up a booking without going through the agent. `start` is like monday_at(10)."""
    hour, minute = map(int, start.split()[1].split(":"))
    async with SessionLocal() as session:
        return await scheduling.book_appointment(
            session, treatment, dentist, clinic_time(next_monday(), hour, minute),
            scheduling.PatientDetails("Ali Khan", ALI_PHONE), user=user,
        )


async def appointment_count() -> int:
    async with SessionLocal() as session:
        return len((await session.scalars(select(Appointment).where(Appointment.status == "confirmed"))).all())


async def scheduling_appointment(appointment_id: int) -> Appointment:
    async with SessionLocal() as session:
        return await session.get(Appointment, appointment_id)


# --- The agent's instructions --------------------------------------------------------


async def test_instructions_carry_the_clinic_facts_from_the_database():
    async with SessionLocal() as session:
        services = await clinic_service.get_services(session)
        dentists = await clinic_service.get_dentists(session)
    text = prompts.agent_instructions(datetime(2026, 10, 5, 9, 30), services, dentists)

    assert "Teeth Whitening [slug: teeth-whitening]: £299.00, 60 minutes" in text
    assert "Dr Omar Haddad [slug: omar-haddad]" in text
    assert "Phone: +44 20 7946 0123" in text  # the real number, so the model never invents one
    assert "Open: Monday to Friday, 09:00 to 17:00" in text
    assert "Monday 05 October 2026" in text


async def test_a_price_change_reaches_the_agent_on_the_next_message():
    async with SessionLocal() as session:
        async with session.begin():
            whitening = await clinic_service.get_service(session, "teeth-whitening")
            whitening.price_cents = 25000

    seen = {}

    class Spy(FakeModel):
        async def _agenerate(self, messages, **kwargs):
            seen["instructions"] = messages[0].content
            return await super()._agenerate(messages, **kwargs)

    await run_turn(graph_with(Spy(messages=iter([AIMessage("ok")]))), [], "price?", user=None)
    assert "£250.00" in seen["instructions"]


# --- Tools --------------------------------------------------------------------------


async def test_find_available_times_shows_clinic_time_and_caps_the_list():
    out = await tools.find_available_times.ainvoke(
        {"service_slug": "check-up-and-clean", "first_day": next_monday().isoformat()}
    )
    assert f"start_time: {monday_at(9)}" in out  # 9:00 clinic time, whatever UTC says
    assert "(and 36 more" in out  # 48 free slots, 12 shown


async def test_find_available_times_can_start_from_a_given_time():
    """The eval caught this: asked for 15:00, the agent couldn't see it in a list that
    started at 9:00, and searched again and again until it hit the step limit."""
    out = await tools.find_available_times.ainvoke({
        "service_slug": "check-up-and-clean", "first_day": next_monday().isoformat(),
        "dentist_slug": "sarah-whitfield", "from_time": "15:00",
    })
    assert out.splitlines()[0].endswith(f"start_time: {monday_at(15)}]")
    assert monday_at(14, 30) not in out


async def test_find_available_times_explains_bad_input():
    out = await tools.find_available_times.ainvoke({"service_slug": "nope", "first_day": next_monday().isoformat()})
    assert out.startswith("Could not search")
    out = await tools.find_available_times.ainvoke({"service_slug": "teeth-whitening", "first_day": "next monday"})
    assert "2026-10-07" in out  # tells the model the format it should use


async def test_prepare_tools_change_nothing_and_summarise():
    whitening = {"service_slug": "teeth-whitening", "dentist_slug": "omar-haddad",
                 "full_name": "Ali Khan", "phone": ALI_PHONE}
    summary = await tools.prepare_booking.ainvoke({**whitening, "start_time": monday_at(13)}, config=GUEST)
    assert summary.startswith("Ready to book - NOT booked yet")
    assert "Teeth Whitening with Dr Omar Haddad" in summary and "13:00 to 14:00" in summary
    assert await appointment_count() == 0  # prepared, not booked

    appointment = await book_directly(monday_at(13), treatment="teeth-whitening", dentist="omar-haddad")
    cancel = await tools.prepare_cancellation.ainvoke({"appointment_id": appointment.id, "phone": ALI_PHONE}, config=GUEST)
    move = await tools.prepare_reschedule.ainvoke(
        {"appointment_id": appointment.id, "new_start_time": monday_at(15), "phone": ALI_PHONE}, config=GUEST
    )
    assert cancel.startswith("Ready to cancel - NOT cancelled yet") and move.startswith("Ready to move - NOT moved yet")
    assert (await scheduling_appointment(appointment.id)).status == "confirmed"  # still untouched


async def test_prepare_tools_refuse_what_would_fail():
    details = {"service_slug": "teeth-whitening", "dentist_slug": "omar-haddad",
               "full_name": "Ali Khan", "phone": ALI_PHONE}
    await book_directly(monday_at(13), treatment="teeth-whitening", dentist="omar-haddad")

    taken = await tools.prepare_booking.ainvoke({**details, "start_time": monday_at(13), "phone": "07700 111111"}, config=GUEST)
    assert taken.startswith("Can't book this:") and "other times" in taken
    odd = await tools.prepare_booking.ainvoke({**details, "start_time": monday_at(13, 17)}, config=GUEST)
    assert odd.startswith("Can't book this:")
    garbled = await tools.prepare_booking.ainvoke({**details, "start_time": "Monday at 1pm"}, config=GUEST)
    assert "must look like" in garbled
    bad_phone = await tools.prepare_booking.ainvoke({**details, "start_time": monday_at(9), "phone": "123"}, config=GUEST)
    assert bad_phone.startswith("Can't book this:")


async def test_find_my_appointments_as_guest_and_logged_in():
    user = await make_user()
    logged_in = {"configurable": {"user": user}}
    await book_directly(monday_at(10), user=user)

    assert "Ask the patient" in await tools.find_my_appointments.ainvoke({}, config=GUEST)
    # Logged in: found with no phone number at all.
    assert "Check-up & Clean" in await tools.find_my_appointments.ainvoke({}, config=logged_in)
    # A guest typing the same number does not see the account holder's booking.
    assert "No upcoming appointments" in await tools.find_my_appointments.ainvoke({"phone": ALI_PHONE}, config=GUEST)
    # Nor can they prepare to cancel it.
    cancel = await tools.prepare_cancellation.ainvoke({"appointment_id": 1, "phone": ALI_PHONE}, config=GUEST)
    assert cancel.startswith("Can't cancel this")


# --- Confirming is a rule in code: the patient must reply to the summary first -------


PREPARE_SARA = calls("prepare_booking", service_slug="check-up-and-clean", dentist_slug="mei-tanaka",
                     start_time=None, full_name="Sara Ahmed", phone="07700 900456")


def prepare_sara(hour=10):
    message = PREPARE_SARA.model_copy(deep=True)
    message.tool_calls[0]["args"]["start_time"] = monday_at(hour)
    return message


async def turn(history, says, *model_replies, user=None):
    result = await run_turn(graph_with(scripted(*model_replies)), history, says, user=user)
    return history + result.new_messages, result


def tool_said(result, name):
    return next(m.content for m in result.new_messages if isinstance(m, ToolMessage) and m.name == name)


async def test_preparing_and_confirming_in_the_same_turn_is_refused():
    """The exact mistake the eval caught: acting before the patient had said yes."""
    _, result = await turn([], "Book me in with Dr Tanaka at 10, I'm Sara, 07700 900456",
                           prepare_sara(), calls("confirm_action"), AIMessage("Done!"))
    assert "hasn't replied" in tool_said(result, "confirm_action")
    assert await appointment_count() == 0


async def test_confirming_after_the_patient_replies_books_it():
    history, _ = await turn([], "Book me in at 10", prepare_sara(), AIMessage("Shall I book this?"))
    _, result = await turn(history, "Yes please", calls("confirm_action"), AIMessage("Booked!"))
    assert tool_said(result, "confirm_action").startswith("Booked.")
    assert await appointment_count() == 1


async def test_an_old_summary_cant_be_confirmed_after_the_patient_moves_on():
    history, _ = await turn([], "Book me in at 10", prepare_sara(), AIMessage("Shall I book this?"))
    history, _ = await turn(history, "Actually, is there parking?", AIMessage("Yes, on the street."))
    _, result = await turn(history, "ok", calls("confirm_action"), AIMessage("Booked!"))
    assert "said more since" in tool_said(result, "confirm_action")
    assert await appointment_count() == 0


async def test_one_yes_confirms_only_once():
    history, _ = await turn([], "Book me in at 10", prepare_sara(), AIMessage("Shall I book this?"))
    _, result = await turn(history, "Yes", calls("confirm_action"), calls("confirm_action"), AIMessage("Booked!"))
    replies = [m.content for m in result.new_messages if isinstance(m, ToolMessage) and m.name == "confirm_action"]
    assert replies[0].startswith("Booked.") and "already dealt with" in replies[1]
    assert await appointment_count() == 1


async def test_nothing_to_confirm_when_nothing_was_prepared_or_it_failed():
    _, result = await turn([], "yes", calls("confirm_action"), AIMessage("Hmm."))
    assert "Nothing has been prepared" in tool_said(result, "confirm_action")

    await book_directly(monday_at(10))  # Mei's 10:00 is now taken, so the prepare fails
    history, _ = await turn([], "Book me in at 10", prepare_sara(), AIMessage("That time is taken."))
    _, result = await turn(history, "yes", calls("confirm_action"), AIMessage("Hmm."))
    assert "didn't pass its checks" in tool_said(result, "confirm_action")
    assert await appointment_count() == 1  # only the one booked directly


async def test_a_time_taken_between_summary_and_yes_changes_nothing():
    history, _ = await turn([], "Book me in at 10", prepare_sara(), AIMessage("Shall I book this?"))
    await book_directly(monday_at(10))  # someone else gets there first
    _, result = await turn(history, "Yes", calls("confirm_action"), AIMessage("Sorry."))
    assert "Nothing was changed" in tool_said(result, "confirm_action")
    assert await appointment_count() == 1


async def test_cancel_and_move_go_through_confirm_too():
    appointment = await book_directly(monday_at(10))
    history, _ = await turn([], "Move it to 15:00", calls(
        "prepare_reschedule", appointment_id=appointment.id, new_start_time=monday_at(15), phone=ALI_PHONE,
    ), AIMessage("Shall I move it?"))
    assert (await scheduling_appointment(appointment.id)).start_time == clinic_time(next_monday(), 10)

    history, _ = await turn(history, "Yes", calls("confirm_action"), AIMessage("Moved."))
    assert (await scheduling_appointment(appointment.id)).start_time == clinic_time(next_monday(), 15)

    history, _ = await turn(history, "Actually cancel it", calls(
        "prepare_cancellation", appointment_id=appointment.id, phone=ALI_PHONE,
    ), AIMessage("Cancel it?"))
    await turn(history, "Yes", calls("confirm_action"), AIMessage("Cancelled."))
    assert (await scheduling_appointment(appointment.id)).status == "cancelled"


async def test_search_formats_passages_with_their_source(monkeypatch):
    class FakeKnowledge:
        async def search(self, question, limit):
            return [Passage("Aftercare Instructions", "Dry socket after a tooth extraction",
                            "Signs of dry socket...", "04_aftercare_instructions.pdf", [3], 0.8)]

    monkeypatch.setattr(tools, "get_knowledge_base", lambda: FakeKnowledge())
    out = await tools.search_clinic_documents.ainvoke({"question": "dry socket"})
    assert out.startswith("[From: Aftercare Instructions, page 3]")
    assert "Aftercare Instructions > Dry socket after a tooth extraction" in out


async def test_search_with_no_match_tells_the_model_not_to_guess(monkeypatch):
    class EmptyKnowledge:
        async def search(self, question, limit):
            return []

    monkeypatch.setattr(tools, "get_knowledge_base", lambda: EmptyKnowledge())
    out = await tools.search_clinic_documents.ainvoke({"question": "Invisalign"})
    assert "Do not answer from general knowledge" in out


# --- The graph ----------------------------------------------------------------------


@pytest.mark.parametrize("urgency, expected", [
    ("emergency", prompts.emergency_reply()),
    ("urgent", prompts.urgent_reply()),
])
async def test_emergencies_get_the_fixed_reply_and_never_reach_the_agent(urgency, expected):
    model = scripted()  # an empty script: if the agent were called, the turn would fail
    turn = await run_turn(graph_with(model, urgency), [], "my face is swelling", user=None)
    assert turn.urgency == urgency
    assert turn.reply == expected


async def test_if_the_safety_check_fails_the_message_does_not_reach_the_agent():
    async def broken(_message):
        raise RuntimeError("safety model unavailable")

    graph = build_agent_graph(scripted(), broken, tools.ALL_TOOLS)
    turn = await run_turn(graph, [], "hello", user=None)
    assert turn.urgency == "unavailable"
    assert turn.reply == prompts.safety_unavailable_reply()
    assert turn.failure == "service"  # counted as the service's fault, not the agent's


async def test_routine_message_goes_through_a_tool_then_answers():
    model = scripted(
        calls("find_available_times", service_slug="teeth-whitening", first_day=next_monday().isoformat()),
        AIMessage("There are free times on Monday."),
    )
    turn = await run_turn(graph_with(model), [], "Any whitening on Monday?", user=None)

    assert turn.urgency == "routine"
    assert turn.reply == "There are free times on Monday."
    tool_output = next(m for m in turn.new_messages if isinstance(m, ToolMessage))
    assert f"start_time: {monday_at(9)}" in tool_output.content
    assert turn.new_messages[0].content == "Any whitening on Monday?"


async def test_the_login_reaches_the_tools_through_the_graph():
    user = await make_user()
    await book_directly(monday_at(10), user=user)
    model = scripted(calls("find_my_appointments"), AIMessage("You have one appointment."))
    turn = await run_turn(graph_with(model), [], "What appointments do I have?", user=user)

    tool_output = next(m for m in turn.new_messages if isinstance(m, ToolMessage))
    assert "Check-up & Clean with Dr Mei Tanaka" in tool_output.content


async def test_a_model_stuck_calling_tools_is_stopped():
    # A NEW message every round. Repeating one message object doesn't loop: the graph
    # sees the same message again, replaces it instead of adding it, and stops after one
    # round - which is how this test once passed without ever reaching the step limit.
    model = FakeModel(messages=(calls("find_my_appointments") for _ in itertools.count()))
    turn = await run_turn(graph_with(model), [], "hello", user=None)
    assert turn.reply == prompts.agent_failed_reply()
    assert turn.failure == "step_limit"  # the agent's own failure, so the eval scores it


async def test_an_empty_answer_is_replaced_with_an_apology():
    turn = await run_turn(graph_with(scripted(AIMessage(""))), [], "hello", user=None)
    assert turn.reply == prompts.agent_failed_reply()
    assert turn.failure == "empty"


async def test_a_normal_answer_has_no_failure():
    turn = await run_turn(graph_with(scripted(AIMessage("Hi!"))), [], "hello", user=None)
    assert turn.failure is None


async def test_history_is_kept_and_only_new_messages_are_returned():
    first = await run_turn(graph_with(scripted(AIMessage("Hi! How can I help?"))), [], "hello", user=None)
    second = await run_turn(graph_with(scripted(AIMessage("You said hello."))), first.new_messages, "what did I say?", user=None)
    assert [m.content for m in second.new_messages] == ["what did I say?", "You said hello."]
