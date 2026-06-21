"""ASI:One-facing BusyBrain orchestrator uAgent."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from uagents import Agent, Context, Protocol
from uagents.registration import AlmanacApiRegistrationPolicy
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from agent_config import ORCHESTRATOR_SEED, SPECIALIST_ADDRESSES
from agent_messages import PlanningRequest, SpecialistResponse
from agent_utils import ask_asi


agent = Agent(
    name="BusyBrain",
    seed=ORCHESTRATOR_SEED,
    port=8001,
    mailbox=True,
    readme_path="README.md",
    description="Coordinates specialist agents into humane, ADHD-friendly plans.",
    registration_policy=AlmanacApiRegistrationPolicy(),
    publish_agent_details=True,
)
chat_protocol = Protocol(spec=chat_protocol_spec)
planning_protocol = Protocol(name="BusyBrainOrchestrationProtocol", version="1.0.0")

# Pending requests are intentionally in-memory: each ASI:One chat turn is a short
# orchestration session. Persistent storage is a future production enhancement.
pending: dict[str, dict] = {}


def text_from(message: ChatMessage) -> str:
    return " ".join(
        item.text.strip()
        for item in message.content
        if isinstance(item, TextContent) and item.text.strip()
    )


def chat_reply(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=text),
            EndSessionContent(type="end-session"),
        ],
    )


@chat_protocol.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id
        ),
    )

    user_text = text_from(msg)
    if not user_text:
        await ctx.send(sender, chat_reply("Tell me what your week needs to hold."))
        return

    request_id = str(uuid4())
    pending[request_id] = {"sender": sender, "text": user_text, "responses": {}}
    request = PlanningRequest(request_id=request_id, user_text=user_text)

    ctx.logger.info("Dispatching request %s to 3 specialists", request_id)
    for address in SPECIALIST_ADDRESSES.values():
        await ctx.send(address, request)


@planning_protocol.on_message(SpecialistResponse)
async def handle_specialist_response(
    ctx: Context, sender: str, msg: SpecialistResponse
):
    expected_sender = SPECIALIST_ADDRESSES.get(msg.specialist)
    if expected_sender != sender:
        ctx.logger.warning("Ignored unverified %s response from %s", msg.specialist, sender)
        return

    state = pending.get(msg.request_id)
    if state is None:
        ctx.logger.warning("Received response for unknown request %s", msg.request_id)
        return

    state["responses"][msg.specialist] = msg.result
    ctx.logger.info(
        "Request %s has %s/3 specialist responses",
        msg.request_id,
        len(state["responses"]),
    )
    if len(state["responses"]) < len(SPECIALIST_ADDRESSES):
        return

    evidence = "\n\n".join(
        f"[{('WORKLOAD & SOCIAL' if name == 'wellness' else name.upper())} SPECIALIST]\n{state['responses'][name]}"
        for name in ("study", "calendar", "wellness")
    )
    try:
        final = await ask_asi(
            """You are BusyBrain, an ADHD-friendly planning orchestrator. Merge
the three verified specialist reports into one practical answer. Resolve
conflicts, prioritize must-do items, and give a chronological plan when dates
or times are available. Include invisible work such as setup, travel, meals,
breaks, and recovery without making the plan overwhelming. Clearly identify
assumptions and ask at most one essential follow-up question. Briefly state
which specialists contributed. Never diagnose medical conditions.""",
            f"USER REQUEST:\n{state['text']}\n\nSPECIALIST REPORTS:\n{evidence}",
            max_tokens=1400,
        )
    except Exception:
        ctx.logger.exception("Final synthesis failed")
        final = "I gathered the specialist plans but could not synthesize them:\n\n" + evidence

    await ctx.send(state["sender"], chat_reply(final))
    pending.pop(msg.request_id, None)


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


agent.include(chat_protocol, publish_manifest=True)
agent.include(planning_protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
