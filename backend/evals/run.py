"""Runs the eval cases against the REAL agent: real Groq models, real embedding model,
real knowledge base. Only the database is a fresh copy, so test bookings never touch
clinic.db and every run starts from exactly the same state.

Run from the backend folder (stop the web server first - it holds the knowledge base):

    python -m evals.run                       all cases
    python -m evals.run --only appointments   one category
    python -m evals.run --case "full booking" one case (repeat --case for several)

Running some cases updates their rows in the existing report and keeps the rest, so
fixing one case doesn't mean paying for a full run again.

A full run uses roughly 120,000 of the 200,000 tokens Groq's free tier allows per day,
so run it when you've changed something, not on every save. It paces itself to stay
under the free tier's 8,000 tokens a minute, so a full run takes several minutes.

Results go to evals/results/latest.md (for the README) and latest.json (every reply).
"""

import os
import sys
import tempfile

# Must happen before anything from `app` is imported: point the app at a fresh database.
_DB = os.path.join(tempfile.gettempdir(), "dental_assistant_eval.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB}"

import argparse  # noqa: E402
import asyncio  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from collections import defaultdict  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

from langchain_core.callbacks import get_usage_metadata_callback  # noqa: E402
from langchain_core.messages import messages_from_dict  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.features.chat import service as chat  # noqa: E402
from app.features.chat.models import Conversation, Message  # noqa: E402
from app.features.knowledge.service import close_knowledge_base, get_knowledge_base  # noqa: E402
from app.features.scheduling.models import Appointment, AppointmentSlot, Patient  # noqa: E402
from evals.cases import CASES, Case  # noqa: E402
from evals.checks import UNIVERSAL, StepResult  # noqa: E402
from scripts.seed import seed  # noqa: E402

RESULTS = Path(__file__).parent / "results"
TOKENS_PER_MINUTE = 8_000
# Start a message only when the last minute used less than this, leaving room for the
# message itself (a busy one can use around 5,000 tokens).
_START_BELOW = 3_000


class Pacer:
    """Waits between messages so a run stays under Groq's tokens-per-minute limit."""

    def __init__(self):
        self.used: dict[str, list[tuple[float, int]]] = defaultdict(list)
        self.total = 0

    async def wait(self) -> None:
        while True:
            now = time.monotonic()
            busiest = max((sum(t for at, t in uses if now - at < 60) for uses in self.used.values()), default=0)
            if busiest < _START_BELOW:
                return
            await asyncio.sleep(2)

    def record(self, usage_by_model: dict) -> None:
        now = time.monotonic()
        for model, usage in usage_by_model.items():
            self.used[model].append((now, usage["total_tokens"]))
            self.total += usage["total_tokens"]


async def reset_diary() -> None:
    """Every case starts with no bookings, patients or conversations."""
    async with SessionLocal() as session:
        async with session.begin():
            for table in (Message, Conversation, AppointmentSlot, Appointment, Patient):
                await session.execute(delete(table))


async def tool_calls_since(conversation_id: str, position: int) -> list[str]:
    async with SessionLocal() as session:
        rows = await session.scalars(
            select(Message).where(Message.conversation_id == conversation_id, Message.position >= position)
        )
        messages = messages_from_dict([m.payload for m in rows])
    return [call["name"] for m in messages if m.type == "ai" for call in m.tool_calls]


async def message_count(conversation_id: str | None) -> int:
    if conversation_id is None:
        return 0
    async with SessionLocal() as session:
        return len((await session.scalars(select(Message).where(Message.conversation_id == conversation_id))).all())


async def run_case(case: Case, pacer: Pacer) -> dict:
    await reset_diary()
    if case.setup:
        await case.setup()

    conversation_id, patient_said, steps = None, [], []
    for number, step in enumerate(case.steps, start=1):
        await pacer.wait()
        before = await message_count(conversation_id)
        started = time.monotonic()
        with get_usage_metadata_callback() as usage:
            async with SessionLocal() as session:
                turn = await chat.send_message(session, step.say, None, conversation_id)
        pacer.record(usage.usage_metadata)
        conversation_id = turn.conversation_id
        patient_said.append(step.say)

        if turn.failure == "service":
            # The model service failed - usually Groq refusing because a limit was reached.
            # That says nothing about the agent's quality, so it isn't scored.
            steps.append({"step": number, "said": step.say, "reply": turn.reply, "failures": [],
                          "error": "the model service failed (usually Groq's rate limit) - see the log"})
            break
        if turn.failure:
            # The agent's own failure (stuck in a loop, or a blank answer) - that IS scored.
            steps.append({"step": number, "said": step.say, "reply": turn.reply,
                          "failures": [f"the agent gave up ({turn.failure.replace('_', ' ')})"]})
            break

        result = StepResult(
            reply=turn.reply,
            urgency=turn.urgency,
            tool_calls=await tool_calls_since(conversation_id, before),
            patient_said=list(patient_said),
        )
        failures = [reason for check in step.expect + UNIVERSAL if (reason := await check(result))]
        steps.append({
            "step": number, "said": step.say, "reply": turn.reply, "urgency": turn.urgency,
            "tools": result.tool_calls, "seconds": round(time.monotonic() - started, 1), "failures": failures,
        })
        if failures:
            break  # later steps depend on this one, so their results would mean nothing

    passed = not any(s["failures"] or s.get("error") for s in steps)
    return {"id": case.id, "category": case.category, "passed": passed, "steps": steps}


def status(result: dict) -> str:
    """'pass', 'fail', or 'error' when the case couldn't run."""
    if any(s.get("error") for s in result["steps"]):
        return "error"
    return "pass" if result["passed"] else "fail"


def merge_with_previous(results: list[dict]) -> list[dict]:
    """Put this run's results into the last report, replacing those cases' old rows."""
    previous_file = RESULTS / "latest.json"
    previous = json.loads(previous_file.read_text(encoding="utf-8")) if previous_file.exists() else []
    by_id = {r["id"]: r for r in previous} | {r["id"]: r for r in results}
    return [by_id[c.id] for c in CASES if c.id in by_id]


def write_report(results: list[dict], tokens: int, minutes: float) -> Path:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "latest.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    by_category = defaultdict(list)
    for r in results:
        by_category[r["category"]].append(status(r))
    scored = [r for r in results if status(r) != "error"]
    passed = sum(status(r) == "pass" for r in results)
    not_run = [r for r in results if status(r) == "error"]

    lines = [
        "# Eval results", "",
        f"Run on {datetime.now():%d %B %Y at %H:%M}. Agent model `{settings.llm_model}`, safety model "
        f"`{settings.safety_model}`, embeddings `{settings.embedding_model}`.", "",
        f"**{passed} of {len(scored)} cases passed.**"
        + (f" {len(not_run)} couldn't run and aren't counted." if not_run else "")
        + f" This run: {tokens:,} tokens, {minutes:.1f} minutes.", "",
        "| Category | Passed |", "|---|---|",
        *[
            f"| {cat} | {s.count('pass')} of {len(s) - s.count('error')}"
            + (f" ({s.count('error')} couldn't run)" if "error" in s else "") + " |"
            for cat, s in by_category.items()
        ],
    ]
    if not_run:
        lines += ["", "## Couldn't run", "",
                  "The model service refused these (usually Groq's rate limit), so they say nothing "
                  "about the agent. Run them again later with `--case`.", "",
                  *[f"- {r['id']}" for r in not_run]]
    failed = [r for r in results if status(r) == "fail"]
    if failed:
        lines += ["", "## Failures", ""]
        for r in failed:
            step = next(s for s in r["steps"] if s["failures"])
            lines += [
                f"**{r['id']}** (step {step['step']}): {'; '.join(step['failures'])}", "",
                f"> Patient: {step['said']}", ">",
                *[f"> {line}" if line else ">" for line in f"Assistant: {step['reply']}".splitlines()], "",
            ]
    path = RESULTS / "latest.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="run one category")
    parser.add_argument("--case", action="append", help="run one case, by id (repeat for several)")
    args = parser.parse_args()

    cases = [c for c in CASES if (not args.only or c.category == args.only) and (not args.case or c.id in args.case)]
    if not cases:
        sys.exit("No cases match.")

    try:
        await asyncio.to_thread(get_knowledge_base)  # load the model now, and fail early if the folder is busy
    except RuntimeError as exc:
        if "already accessed" in str(exc):
            sys.exit("The knowledge base folder is in use - stop the web server first.")
        raise

    await seed()  # fresh database with the clinic's services, dentists and FAQs
    pacer, results, started = Pacer(), [], time.monotonic()
    print(f"Running {len(cases)} cases against {settings.llm_model}...\n")
    for case in cases:
        try:
            result = await run_case(case, pacer)
        except Exception as exc:  # one broken case shouldn't stop the run
            result = {"id": case.id, "category": case.category, "passed": False,
                      "steps": [{"step": 0, "said": "", "reply": "", "failures": [f"crashed: {exc!r}"]}]}
        results.append(result)
        print(f"  {status(result).upper():5} {case.category:13} {case.id}")
        for step in result["steps"]:
            for problem in step["failures"] + ([step["error"]] if step.get("error") else []):
                print(f"          step {step['step']}: {problem}")

    def summary(rs):
        scored = [r for r in rs if status(r) != "error"]
        return f"{sum(status(r) == 'pass' for r in rs)} of {len(scored)} passed ({len(rs) - len(scored)} couldn't run)"

    ran = summary(results)
    if args.only or args.case:
        results = merge_with_previous(results)
    report = write_report(results, pacer.total, (time.monotonic() - started) / 60)
    print(f"\nThis run: {ran}, {pacer.total:,} tokens. Report now: {summary(results)}. {report}")
    close_knowledge_base()
    await engine.dispose()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(main())
