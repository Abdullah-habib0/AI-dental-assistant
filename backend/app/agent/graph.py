"""The agent, as a LangGraph graph:

    START -> safety_check -- routine ----------> agent <--> tools
                         |
                         +-- emergency/urgent -> escalate      (both end the turn)

Every message goes through safety_check first. Routine ones go to the agent, which can
call tools as many times as it needs (up to a limit) before answering. Emergencies and
urgent problems go to escalate, which gives a fixed reply and never reaches the agent.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent import prompts
from app.agent.safety import Classifier
from app.core.config import settings
from app.db.session import SessionLocal
from app.features.auth.models import User
from app.features.clinic import service as clinic_service

logger = logging.getLogger(__name__)
_CLINIC_TZ = ZoneInfo(settings.clinic_timezone)


class AgentState(MessagesState):
    urgency: str


@dataclass
class TurnResult:
    reply: str
    new_messages: list[BaseMessage]  # the patient's message, then everything the agent added
    urgency: str  # "routine", "urgent", "emergency", or "unavailable" if the check failed
    # None when the agent answered. Otherwise why it didn't, so problems outside the agent
    # (the model service down or rate-limited) can be told apart from the agent's own
    # (stuck calling tools, or answering with nothing):
    #   "service"     the model service failed - the safety check or the agent couldn't run
    #   "step_limit"  the agent kept calling tools until it hit the limit
    #   "empty"       the agent's answer was blank
    failure: str | None = None


def _tool_failed(error: Exception) -> str:
    logger.exception("Agent tool failed", exc_info=error)
    return "That tool failed unexpectedly. Apologise, and give the patient the clinic phone number."


def build_agent_graph(chat_model: BaseChatModel, classify: Classifier, tools: list[BaseTool]):
    tool_model = chat_model.bind_tools(tools)

    async def safety_check(state: AgentState) -> dict:
        try:
            urgency = await classify(state["messages"][-1].content)
        except Exception:
            # Fail closed: an unchecked message doesn't go to the agent.
            logger.exception("Safety check failed")
            urgency = "unavailable"
        return {"urgency": urgency}

    def after_safety_check(state: AgentState) -> str:
        return "agent" if state["urgency"] == "routine" else "escalate"

    def escalate(state: AgentState) -> dict:
        reply = {
            "emergency": prompts.emergency_reply,
            "urgent": prompts.urgent_reply,
        }.get(state["urgency"], prompts.safety_unavailable_reply)()
        return {"messages": [AIMessage(reply)]}

    async def agent(state: AgentState, config: RunnableConfig) -> dict:
        now = datetime.now(UTC).astimezone(_CLINIC_TZ)
        # Read fresh every time, so a price changed in the database is used straight away.
        async with SessionLocal() as session:
            services = await clinic_service.get_services(session)
            dentists = await clinic_service.get_dentists(session)
        instructions = SystemMessage(prompts.agent_instructions(now, services, dentists))
        response = await tool_model.ainvoke([instructions, *state["messages"]], config)
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("safety_check", safety_check)
    graph.add_node("escalate", escalate)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=_tool_failed))

    graph.add_edge(START, "safety_check")
    graph.add_conditional_edges("safety_check", after_safety_check, ["agent", "escalate"])
    graph.add_conditional_edges("agent", tools_condition)  # tool calls -> "tools", otherwise END
    graph.add_edge("tools", "agent")
    graph.add_edge("escalate", END)
    return graph.compile()


async def run_turn(graph, history: list[BaseMessage], message: str, user: User | None) -> TurnResult:
    """Answer one patient message, given the conversation so far.

    `user` is the logged-in user, or None for a guest. It reaches the tools through the
    run's config - the model never sees it and can't change it.
    """
    patient_message = HumanMessage(message)
    config = {
        "configurable": {"user": user},
        # Each tool use is two steps (agent, then tools). The limit stops a confused model
        # from calling tools in a loop forever.
        "recursion_limit": settings.agent_max_steps * 2 + 3,
    }
    try:
        result = await graph.ainvoke({"messages": [*history, patient_message]}, config)
    except GraphRecursionError:
        logger.warning("Agent hit the step limit")
        return _failed(patient_message, "routine", "step_limit")
    except Exception:
        # The LLM service being down or rate-limited shouldn't crash the chat.
        logger.exception("Agent run failed")
        return _failed(patient_message, "routine", "service")

    urgency = result.get("urgency", "routine")
    new_messages = result["messages"][len(history):]
    if urgency == "unavailable":
        # The safety check couldn't run; escalate already gave the safe fallback reply.
        return TurnResult(new_messages[-1].content, new_messages, urgency, failure="service")

    reply = new_messages[-1].content if isinstance(new_messages[-1], AIMessage) else ""
    if not reply.strip():
        return _failed(patient_message, urgency, "empty")
    return TurnResult(reply, new_messages, urgency)


def _failed(patient_message: HumanMessage, urgency: str, failure: str) -> TurnResult:
    reply = AIMessage(prompts.agent_failed_reply())
    return TurnResult(reply.content, [patient_message, reply], urgency, failure=failure)
