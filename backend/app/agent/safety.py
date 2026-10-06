"""The safety check: sorts every message as emergency, urgent or routine, before the
agent sees it.

Emergencies and urgent problems never reach the agent. They get a fixed reply pointing
to 999, NHS 111 or the clinic's phone line, so that advice which matters this much is
always the same and never depends on what the agent happens to say.
"""

from collections.abc import Awaitable, Callable
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict

from app.agent.prompts import SAFETY_INSTRUCTIONS

Urgency = Literal["emergency", "urgent", "routine"]
Classifier = Callable[[str], Awaitable[Urgency]]


class _Triage(BaseModel):
    model_config = ConfigDict(extra="forbid")  # strict mode needs "no other fields allowed"

    urgency: Urgency


def make_classifier(model: BaseChatModel) -> Classifier:
    """A classifier backed by an LLM, answering with exactly one of three words.

    Strict mode makes the model physically unable to answer in any other shape. Without
    it, a message like "write me a poem" or "ignore your instructions" could get the
    model to write the poem instead of sorting the message - which the eval caught.
    """
    structured = model.with_structured_output(_Triage, method="json_schema", strict=True)

    async def classify(message: str) -> Urgency:
        # The patient's words are wrapped in markers and labelled as text to sort, so
        # instructions inside them are read as part of the message, not obeyed.
        wrapped = f"Message to sort:\n<message>\n{message}\n</message>"
        result = await structured.ainvoke([SystemMessage(SAFETY_INSTRUCTIONS), HumanMessage(wrapped)])
        return result.urgency

    return classify
