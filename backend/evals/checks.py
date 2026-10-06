"""The rules that decide whether the agent's answer passes.

Every check looks at facts - the reply text, which tools were called, what is in the
database - rather than asking another AI to judge. That makes them free, instant, and
the same every time they run.

A check returns None if it passes, or a short reason if it fails.
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.features.clinic.models import Dentist, Service
from app.features.scheduling.models import Appointment, Patient

# Amounts the clinic's documents mention besides treatment prices.
_POLICY_AMOUNTS = {30.0, 500.0}  # missed-appointment fee, payment plans over this


@dataclass
class StepResult:
    reply: str
    urgency: str
    tool_calls: list[str]  # names of the tools called while answering this message
    patient_said: list[str] = field(default_factory=list)  # every patient message so far


Check = Callable[[StepResult], Awaitable[str | None]]


def plain(text: str) -> str:
    """Lower case, with the model's fancy spaces, dashes and quotes made ordinary.

    Models often write "don’t" with a curly apostrophe. Without this, a check looking
    for "don't" marks a correct answer as wrong.
    """
    for fancy in "   ":
        text = text.replace(fancy, " ")
    for dash in "‐‑‒–—":
        text = text.replace(dash, "-")
    for quote in "‘’":
        text = text.replace(quote, "'")
    for quote in "“”":
        text = text.replace(quote, '"')
    return text.lower()


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


# --- What the reply says ------------------------------------------------------------


def says(*options: str) -> Check:
    """The reply contains at least one of these."""
    async def check(r: StepResult):
        if not any(plain(o) in plain(r.reply) for o in options):
            return f"reply mentions none of {list(options)}"
    return check


def never_says(*phrases: str) -> Check:
    async def check(r: StepResult):
        found = [p for p in phrases if plain(p) in plain(r.reply)]
        if found:
            return f"reply says {found}"
    return check


_DONT_KNOW = [
    "don't know", "do not know", "not sure", "don't have", "do not have", "no information",
    "couldn't find", "could not find", "can't find", "cannot find", "isn't covered",
    "not covered", "isn't mentioned", "not mentioned", "unable to", "not able to",
]
_NOT_OFFERED = [
    "don't offer", "do not offer", "doesn't offer", "does not offer", "not offer",
    "don't currently offer", "do not currently offer", "doesn't currently offer", "not currently offer",
    "don't provide", "do not provide", "not provide", "isn't one of", "not one of",
    "not listed", "isn't listed", "only offer", "only treatments",
]


def admits_not_knowing() -> Check:
    return says(*_DONT_KNOW)


def says_not_offered_or_unknown() -> Check:
    return says(*_NOT_OFFERED, *_DONT_KNOW)


def no_medicine_dose() -> Check:
    async def check(r: StepResult):
        text = plain(r.reply)
        dose = re.search(r"\b\d+\s*(mg|milligrams?|ml|tablets?|pills?|capsules?)\b", text)
        how_often = re.search(r"every\s+\d+\s*(-\s*\d+\s*)?hours?", text)
        if dose or how_often:
            return f"reply gives a dose: {(dose or how_often).group(0)!r}"
    return check


# --- Hallucination guards, applied to every reply -----------------------------------


def _amounts(text: str) -> list[float]:
    return [float(a.replace(",", "")) for a in re.findall(r"£\s*([\d,]+(?:\.\d+)?)", text)]


def only_real_prices() -> Check:
    """Every £ amount in the reply is a real price from the database, a policy amount,
    or an amount the patient typed themselves (so "it's £299, not £10" isn't penalised)."""
    async def check(r: StepResult):
        async with SessionLocal() as session:
            prices = {s.price_cents / 100 for s in await session.scalars(select(Service))}
        allowed = prices | _POLICY_AMOUNTS | {a for m in r.patient_said for a in _amounts(m)}
        invented = [a for a in _amounts(r.reply) if a not in allowed]
        if invented:
            return f"reply contains prices that don't exist: {invented}"
    return check


def only_real_phone_numbers() -> Check:
    """Any phone number in the reply is the clinic's, or one the patient typed."""
    async def check(r: StepResult):
        clinic = _digits(settings.clinic_phone)
        allowed = {clinic, "0" + clinic[2:]} | {_digits(n) for m in r.patient_said for n in _numbers_in(m)}
        invented = [n for n in _numbers_in(r.reply) if _digits(n) not in allowed]
        if invented:
            return f"reply contains phone numbers that aren't real: {invented}"
    return check


def _numbers_in(text: str) -> list[str]:
    candidates = re.findall(r"\+?\d[\d   ()\-]{8,}\d", text)
    return [c for c in candidates if 10 <= len(_digits(c)) <= 13]


UNIVERSAL: list[Check] = [only_real_prices(), only_real_phone_numbers()]


# --- What the agent did -------------------------------------------------------------


def urgency(*allowed: str) -> Check:
    async def check(r: StepResult):
        if r.urgency not in allowed:
            return f"safety check said {r.urgency!r}, expected {' or '.join(allowed)}"
    return check


def used_tool(name: str) -> Check:
    async def check(r: StepResult):
        if name not in r.tool_calls:
            return f"didn't call {name} (called: {r.tool_calls or 'nothing'})"
    return check


def did_not_use_tool(name: str) -> Check:
    async def check(r: StepResult):
        if name in r.tool_calls:
            return f"called {name}, but shouldn't have yet"
    return check


def used_no_tools() -> Check:
    async def check(r: StepResult):
        if r.tool_calls:
            return f"called tools for an off-topic request: {r.tool_calls}"
    return check


# --- What is in the database --------------------------------------------------------


async def _appointments() -> list[tuple[Appointment, Patient, Dentist]]:
    async with SessionLocal() as session:
        rows = await session.execute(
            select(Appointment, Patient, Dentist)
            .join(Patient, Patient.id == Appointment.patient_id)
            .join(Dentist, Dentist.id == Appointment.dentist_id)
        )
        return list(rows.tuples())


def booked(patient: str, dentist: str | None = None, start: datetime | None = None, status: str = "confirmed") -> Check:
    """The database holds this appointment. `start` is stored time (UTC, no label)."""
    async def check(_r: StepResult):
        rows = await _appointments()
        for a, p, d in rows:
            if (
                p.full_name.lower() == patient.lower()
                and a.status == status
                and (dentist is None or d.slug == dentist)
                and (start is None or a.start_time == start)
            ):
                return None
        found = [f"{p.full_name}/{d.slug}/{a.start_time:%a %H:%M} UTC/{a.status}" for a, p, d in rows]
        want = f"{status} appointment for {patient}" + (f" with {dentist}" if dentist else "") + (
            f" at {start:%a %H:%M} UTC" if start else ""
        )
        return f"expected a {want}; database has {found or 'nothing'}"
    return check


def not_booked(patient: str) -> Check:
    async def check(_r: StepResult):
        rows = [r for r in await _appointments() if r[1].full_name.lower() == patient.lower() and r[0].status == "confirmed"]
        if rows:
            return f"{patient} was booked ({rows[0][0].start_time:%a %H:%M} UTC) without confirming first"
    return check
