"""Creates the Groq models and the shared agent.

This is the only file that knows the models come from Groq. Switching provider means
changing make_chat_model - the graph, tools and prompts don't change.
"""

from langchain_groq import ChatGroq

from app.agent.graph import build_agent_graph
from app.agent.safety import make_classifier
from app.agent.tools import ALL_TOOLS
from app.core.config import settings


class AgentNotConfigured(Exception):
    """The Groq API key is missing."""


def make_chat_model(model_name: str) -> ChatGroq:
    if not settings.groq_api_key:
        raise AgentNotConfigured("GROQ_API_KEY is not set in backend/.env, so the chat assistant can't run.")
    return ChatGroq(
        model=model_name,
        api_key=settings.groq_api_key,
        temperature=0,  # the same question should get the same kind of answer
        max_retries=2,
        timeout=30,
    )


_agent = None


def get_agent():
    """Built on first use, then reused. Raises AgentNotConfigured if the key is missing."""
    global _agent
    if _agent is None:
        _agent = build_agent_graph(
            chat_model=make_chat_model(settings.llm_model),
            classify=make_classifier(make_chat_model(settings.safety_model)),
            tools=ALL_TOOLS,
        )
    return _agent
