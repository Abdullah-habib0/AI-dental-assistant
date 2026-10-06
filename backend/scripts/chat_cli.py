"""Talk to the agent in the terminal, as a guest.

Run it from the backend folder:   python -m scripts.chat_cli
Type 'quit' to stop. Stop the web server first - both need the knowledge base folder.

Bookings made here are real: they go into clinic.db like any other.
"""

import asyncio

from app.agent.graph import run_turn
from app.agent.llm import AgentNotConfigured, get_agent
from app.db.session import engine
from app.features.knowledge.service import close_knowledge_base


async def main() -> None:
    try:
        agent = get_agent()
    except AgentNotConfigured as exc:
        raise SystemExit(str(exc)) from exc

    history = []
    print("Bright Smile Dental assistant. Type 'quit' to stop.\n")
    try:
        while True:
            message = (await asyncio.to_thread(input, "You: ")).strip()
            if message.lower() in {"quit", "exit"}:
                break
            if not message:
                continue
            turn = await run_turn(agent, history, message, user=None)
            history.extend(turn.new_messages)
            tag = "" if turn.urgency == "routine" else f"  [safety check: {turn.urgency}]"
            print(f"\nAssistant:{tag}\n{turn.reply}\n")
    finally:
        close_knowledge_base()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
