"""The tools the agent can call. Each is a thin wrapper around service code that already
exists and is tested - the rules live in the services, not here.

Two rules hold for every tool:

  Who the patient is comes from the login, passed in by our code through the run's
  config. It never comes from the model, so nobody can talk the agent into acting as
  someone else. (A guest's phone number does come from the chat - that is the proof of
  ownership the scheduling rules already check.)

  The model works in clinic time ("2026-10-07 14:30"). The tools convert to and from UTC,
  so the model never has to do timezone maths.

  Nothing is booked, cancelled or moved in one step. A prepare_ tool checks it and
  returns a summary to read back; confirm_action carries it out, and the code only lets
  it when the patient has replied to that summary (see pending_action at the bottom).

Tools return plain text written for the model. Expected problems ("that time was just
taken") come back as text the model can explain to the patient, not as crashes.
"""

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from app.core.config import settings
from app.db.session import SessionLocal
from app.features.auth.models import User
from app.features.clinic import service as clinic_service
from app.features.knowledge.service import (
    KnowledgeIndexOutdated,
    KnowledgeNotIngested,
    get_knowledge_base,
)
from app.features.scheduling import service as scheduling
from app.features.scheduling.models import Appointment

_CLINIC_TZ = ZoneInfo(settings.clinic_timezone)
_MAX_TIMES_SHOWN = 12


# --- Helpers ------------------------------------------------------------------------


def _user(config: RunnableConfig) -> User | None:
    return (config or {}).get("configurable", {}).get("user")


def _to_clinic_time(stored: datetime) -> datetime:
    return stored.replace(tzinfo=UTC).astimezone(_CLINIC_TZ)


def _show(stored: datetime) -> str:
    """A stored UTC time as the patient should see it, e.g. 'Wed 7 Oct 2026, 14:30'."""
    local = _to_clinic_time(stored)
    return f"{local:%a} {local.day} {local:%b %Y}, {local:%H:%M}"


def _parse_clinic_time(text: str) -> datetime:
    """'2026-10-07 14:30' in clinic time -> stored form (UTC, no label)."""
    local = datetime.strptime(text.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=_CLINIC_TZ)
    return local.astimezone(UTC).replace(tzinfo=None)


def _parse_day(text: str) -> date:
    return date.fromisoformat(text.strip())


async def _describe(appointments: list[Appointment]) -> str:
    async with SessionLocal() as session:
        services = {s.id: s.name for s in await clinic_service.get_services(session)}
        dentists = {d.id: d.name for d in await clinic_service.get_dentists(session)}
    return "\n".join(
        f"- Appointment #{a.id}: {services[a.service_id]} with {dentists[a.dentist_id]}, "
        f"{_show(a.start_time)} to {_to_clinic_time(a.end_time):%H:%M} ({a.status})"
        for a in appointments
    )


# --- Clinic documents --------------------------------------------------------------------


@tool
async def search_clinic_documents(question: str) -> str:
    """Search the clinic's own documents: policies, how treatments work, aftercare,
    emergencies, insurance, privacy, accessibility, parking and more. Use this for any
    question about the practice that the other tools don't cover. Ask in plain words."""
    knowledge = await asyncio.to_thread(get_knowledge_base)
    try:
        passages = await knowledge.search(question, limit=4)
    except (KnowledgeNotIngested, KnowledgeIndexOutdated):
        return "The clinic documents are unavailable right now. Do not guess - give the patient the clinic phone number."

    if not passages:
        return (
            "Nothing in the clinic documents matches this. Do not answer from general "
            "knowledge - say you don't know and give the clinic phone number."
        )
    return "\n\n".join(
        f"[From: {p.document}, page {', '.join(map(str, p.pages))}]\n{p.labelled_text}" for p in passages
    )


# --- Appointments -------------------------------------------------------------------


@tool
async def find_available_times(
    service_slug: str,
    first_day: str,
    last_day: str | None = None,
    dentist_slug: str | None = None,
    from_time: str | None = None,
) -> str:
    """Free appointment times for a treatment. Days are YYYY-MM-DD; leave last_day out to
    search one day, and dentist_slug out for any dentist. Searches at most 31 days.
    from_time ('HH:MM', clinic time) skips anything earlier in each day - use it when the
    patient asks for a particular time or part of the day, e.g. '15:00' or '12:00' for
    the afternoon. Only the first 12 matches are listed, so without it a late time may
    not appear even when it is free."""
    try:
        first = _parse_day(first_day)
        last = _parse_day(last_day) if last_day else first
        earliest = datetime.strptime(from_time.strip(), "%H:%M").time() if from_time else None
    except ValueError:
        return "Dates must look like 2026-10-07, and from_time like 15:00."

    try:
        async with SessionLocal() as session:
            slots = await scheduling.find_available_slots(session, service_slug, first, last, dentist_slug)
        async with SessionLocal() as session:
            names = {d.slug: d.name for d in await clinic_service.get_dentists(session)}
    except (clinic_service.NotFound, scheduling.SchedulingError) as exc:
        return f"Could not search: {exc}"

    if earliest:
        slots = [s for s in slots if _to_clinic_time(s.start_time).time() >= earliest]
    if not slots:
        return "No free times in that range. Try other days, times, or another dentist."
    shown = slots[:_MAX_TIMES_SHOWN]
    lines = [
        f"- {_show(s.start_time)} with {names[s.dentist_slug]} [dentist_slug: {s.dentist_slug}, "
        f"start_time: {_to_clinic_time(s.start_time):%Y-%m-%d %H:%M}]"
        for s in shown
    ]
    if len(slots) > len(shown):
        lines.append(f"(and {len(slots) - len(shown)} more - ask the patient to narrow it down)")
    return "\n".join(lines)


@tool(response_format="content_and_artifact")
async def prepare_booking(
    service_slug: str,
    dentist_slug: str,
    start_time: str,
    full_name: str,
    phone: str,
    email: str | None = None,
) -> tuple[str, dict | None]:
    """Check a booking and get the summary to read back to the patient. This does NOT
    book anything. start_time is clinic time, 'YYYY-MM-DD HH:MM', exactly as
    find_available_times gave it. Read the summary back, and only after the patient says
    yes in their next message, call confirm_action."""
    try:
        start = _parse_clinic_time(start_time)
    except ValueError:
        return "start_time must look like 2026-10-07 14:30.", None
    try:
        async with SessionLocal() as session:
            treatment, dentist = await scheduling.check_booking(session, service_slug, dentist_slug, start, phone)
    except scheduling.SlotTaken as exc:
        return f"Can't book this: {exc} Offer the patient other times from find_available_times.", None
    except (clinic_service.NotFound, scheduling.SchedulingError) as exc:
        return f"Can't book this: {exc}", None

    end = start + timedelta(minutes=treatment.duration_minutes)
    summary = (
        f"Ready to book - NOT booked yet:\n- {treatment.name} with {dentist.name}, {_show(start)} to "
        f"{_to_clinic_time(end):%H:%M}\n- For {full_name.strip()}, mobile {phone.strip()}"
        + (f", email {email.strip()}" if email else "")
        + "\nRead this back and ask the patient to confirm. Call confirm_action only after they say yes."
    )
    action = {"action": "book", "service_slug": service_slug, "dentist_slug": dentist_slug,
              "start_time": start.isoformat(), "full_name": full_name, "phone": phone, "email": email}
    return summary, action


@tool
async def find_my_appointments(phone: str | None = None, *, config: RunnableConfig) -> str:
    """The patient's upcoming appointments. Guests must give the phone number they booked
    with; logged-in patients need nothing."""
    user = _user(config)
    if user is None and not phone:
        return "Ask the patient for the mobile number they booked with."
    try:
        async with SessionLocal() as session:
            appointments = await scheduling.get_my_upcoming_appointments(session, user=user, phone=phone)
    except scheduling.SchedulingError as exc:
        return str(exc)
    if not appointments:
        return "No upcoming appointments found" + ("" if user else " for that phone number") + "."
    return await _describe(appointments)


@tool(response_format="content_and_artifact")
async def prepare_cancellation(
    appointment_id: int, phone: str | None = None, *, config: RunnableConfig
) -> tuple[str, dict | None]:
    """Check a cancellation and get the summary to read back. This does NOT cancel
    anything. Guests must give the phone number it was booked with. Only after the
    patient says yes in their next message, call confirm_action."""
    try:
        async with SessionLocal() as session:
            appointment = await scheduling.check_owned_appointment(session, appointment_id, _user(config), phone)
    except scheduling.SchedulingError as exc:
        return f"Can't cancel this: {exc}", None
    summary = (
        "Ready to cancel - NOT cancelled yet:\n" + await _describe([appointment])
        + "\nRead this back and ask the patient to confirm. Call confirm_action only after they say yes."
    )
    return summary, {"action": "cancel", "appointment_id": appointment_id, "phone": phone}


@tool(response_format="content_and_artifact")
async def prepare_reschedule(
    appointment_id: int,
    new_start_time: str,
    phone: str | None = None,
    new_dentist_slug: str | None = None,
    *,
    config: RunnableConfig,
) -> tuple[str, dict | None]:
    """Check a move to a new time from find_available_times (clinic time,
    'YYYY-MM-DD HH:MM'), optionally with another dentist, and get the summary to read
    back. This does NOT move anything. Only after the patient says yes in their next
    message, call confirm_action."""
    try:
        start = _parse_clinic_time(new_start_time)
    except ValueError:
        return "new_start_time must look like 2026-10-07 14:30.", None
    try:
        async with SessionLocal() as session:
            appointment = await scheduling.check_reschedule(session, appointment_id, start, _user(config), phone)
            if new_dentist_slug:
                await clinic_service.get_dentist(session, new_dentist_slug)
    except (clinic_service.NotFound, scheduling.SchedulingError) as exc:
        return f"Can't move this: {exc}", None

    summary = (
        "Ready to move - NOT moved yet:\n" + await _describe([appointment])
        + f"\n- New time: {_show(start)}" + (f", with {new_dentist_slug}" if new_dentist_slug else "")
        + "\nRead this back and ask the patient to confirm. Call confirm_action only after they say yes."
    )
    action = {"action": "reschedule", "appointment_id": appointment_id, "new_start_time": start.isoformat(),
              "phone": phone, "new_dentist_slug": new_dentist_slug}
    return summary, action


@tool(response_format="content_and_artifact")
async def confirm_action(
    state: Annotated[dict, InjectedState], config: RunnableConfig
) -> tuple[str, dict]:
    """Carry out the booking, cancellation or move you last prepared - only after the
    patient has said yes to its summary in their latest message. If they changed
    anything, prepare it again instead."""
    action, problem = pending_action(state["messages"])
    if action is None:
        return problem, {"handled": False}

    user, kind = _user(config), action["action"]
    try:
        async with SessionLocal() as session:
            if kind == "book":
                details = scheduling.PatientDetails(action["full_name"], action["phone"], action["email"])
                appointment = await scheduling.book_appointment(
                    session, action["service_slug"], action["dentist_slug"],
                    datetime.fromisoformat(action["start_time"]), details, user=user,
                )
                done = "Booked."
            elif kind == "cancel":
                appointment = await scheduling.cancel_appointment(
                    session, action["appointment_id"], user=user, phone=action["phone"]
                )
                done = "Cancelled."
            else:
                appointment = await scheduling.reschedule_appointment(
                    session, action["appointment_id"], datetime.fromisoformat(action["new_start_time"]),
                    user=user, phone=action["phone"], new_dentist_slug=action["new_dentist_slug"],
                )
                done = "Moved."
    except scheduling.SlotTaken as exc:
        # Taken by someone else between the summary and the "yes". Nothing changed.
        return f"Not done: {exc} Nothing was changed. Offer other times, and prepare again.", {"handled": True}
    except (clinic_service.NotFound, scheduling.SchedulingError) as exc:
        return f"Not done: {exc} Nothing was changed.", {"handled": True}
    return f"{done}\n" + await _describe([appointment]), {"handled": True}


# --- The rule that confirming needs a reply ----------------------------------------

PREPARE_TOOLS = {"prepare_booking", "prepare_cancellation", "prepare_reschedule"}


def pending_action(messages: list[BaseMessage]) -> tuple[dict | None, str]:
    """The prepared action that confirm_action may carry out - or None and the reason.

    This is what makes "confirm first" a rule in code rather than a request to the model.
    An action can only be carried out if the patient has sent exactly ONE message since
    it was prepared: their reply to the summary. So the agent can't prepare and act in
    the same turn, and can't act on an old summary after the patient has moved on.
    """
    patient_messages_since = 0
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            patient_messages_since += 1
        elif isinstance(message, ToolMessage) and message.name == "confirm_action":
            if (message.artifact or {}).get("handled"):
                return None, "That was already dealt with. Prepare it again if the patient wants something else."
        elif isinstance(message, ToolMessage) and message.name in PREPARE_TOOLS:
            if not message.artifact:
                return None, "The last thing prepared didn't pass its checks, so there's nothing to confirm."
            if patient_messages_since == 0:
                return None, "Not done: the patient hasn't replied to the summary yet. Read it back and wait for a yes."
            if patient_messages_since > 1:
                return None, "Not done: the patient has said more since this was prepared. Prepare it again and read it back."
            return message.artifact, ""
    return None, "Nothing has been prepared. Use prepare_booking, prepare_cancellation or prepare_reschedule first."


ALL_TOOLS = [
    search_clinic_documents,
    find_available_times,
    find_my_appointments,
    prepare_booking,
    prepare_cancellation,
    prepare_reschedule,
    confirm_action,
]
