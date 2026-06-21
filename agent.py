"""ASI:One-facing BusyBrain orchestrator uAgent."""

from __future__ import annotations

import time
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
from calendar_actions import confirm_option, parse_option_selection


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
REQUEST_TIMEOUT_SECONDS = 45


def choices_key(sender: str) -> str:
    return f"pending_meeting_choices:{sender}"


def text_from(message: ChatMessage) -> str:
    return " ".join(
        item.text.strip()
        for item in message.content
        if isinstance(item, TextContent) and item.text.strip()
    )


def chat_reply(text: str, end_session: bool = True) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=content,
    )


async def handle_selection(ctx: Context, sender: str, user_text: str) -> bool:
    selected = parse_option_selection(user_text)
    if selected is None:
        return False

    choices = ctx.storage.get(choices_key(sender)) or []
    option = next(
        (choice for choice in choices if choice.get("option_id") == selected), None
    )
    if option is None:
        await ctx.send(
            sender,
            chat_reply(
                "I don't have that option available. Ask me to find meetup times first, "
                "then reply with ‘choose option 1’, ‘choose option 2’, or ‘choose option 3’."
            ),
        )
        return True

    receipt = confirm_option(ctx.storage, sender, option)
    ctx.storage.set(choices_key(sender), [])
    start = datetime.fromisoformat(receipt["start_iso"])
    end = datetime.fromisoformat(receipt["end_iso"])
    await ctx.send(
        sender,
        chat_reply(
            f"✅ Confirmed {receipt['title']} for "
            f"{start.strftime('%A, %B %d at %I:%M %p')}–{end.strftime('%I:%M %p')}.\n\n"
            f"Action receipt: `{receipt['action_id']}`\n\n"
            f"[Add this confirmed event to Google Calendar]({receipt['google_calendar_url']})"
        ),
    )
    ctx.logger.info("Confirmed calendar action %s", receipt["action_id"])
    return True


async def finalize_request(ctx: Context, request_id: str, timed_out: bool = False):
    state = pending.pop(request_id, None)
    if state is None:
        return

    responses = state["responses"]
    if not responses:
        await ctx.send(
            state["sender"],
            chat_reply(
                "I couldn't reach the planning specialists in time. Your request was "
                "not lost—please try again after checking that their mailboxes are online."
            ),
        )
        return

    ordered_names = [name for name in ("study", "calendar", "wellness") if name in responses]
    evidence = "\n\n".join(
        f"[{('WORKLOAD & SOCIAL' if name == 'wellness' else name.upper())} SPECIALIST]\n"
        f"{responses[name]['result']}"
        for name in ordered_names
    )
    missing = [name for name in SPECIALIST_ADDRESSES if name not in responses]
    warning = ""
    if timed_out and missing:
        warning = f"\n\n⚠️ Partial result: {', '.join(missing)} did not respond before the timeout."

    try:
        final = await ask_asi(
            """You are BusyBrain, an ADHD-friendly planning orchestrator. Merge
the verified specialist reports into one practical answer. Resolve conflicts,
prioritize must-do items, and give a chronological plan when dates or times are
available. Never alter or invent meeting-option dates supplied by a specialist.
Clearly identify assumptions and briefly state which specialists contributed.
Never diagnose medical conditions.""",
            f"USER REQUEST:\n{state['text']}\n\nSPECIALIST REPORTS:\n{evidence}",
            max_tokens=1200,
        )
    except Exception:
        ctx.logger.exception("Final synthesis failed")
        final = "I gathered these verified specialist results:\n\n" + evidence

    options = state.get("meeting_options", [])
    if options:
        ctx.storage.set(choices_key(state["sender"]), options)
        option_text = []
        for option in options:
            start = datetime.fromisoformat(option["start_iso"])
            end = datetime.fromisoformat(option["end_iso"])
            option_text.append(
                f"**Option {option['option_id']} — fit {option['score']}**: "
                f"{start.strftime('%A, %b %d at %I:%M %p')}–{end.strftime('%I:%M %p')}\n"
                f"Why: {'; '.join(option['reasons'])}"
            )
        final += (
            "\n\n### Executable meetup options\n\n"
            + "\n\n".join(option_text)
            + "\n\nReply **choose option 1**, **choose option 2**, or **choose option 3**. "
            "I will confirm it and create the Google Calendar action."
        )

    await ctx.send(
        state["sender"],
        chat_reply(final + warning, end_session=not bool(options)),
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

    if await handle_selection(ctx, sender, user_text):
        return

    request_id = str(uuid4())
    pending[request_id] = {
        "sender": sender,
        "text": user_text,
        "responses": {},
        "meeting_options": [],
        "created_at": time.monotonic(),
    }
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

    state["responses"][msg.specialist] = {
        "result": msg.result,
        "meeting_options": [option.dict() for option in msg.meeting_options],
    }
    if msg.meeting_options:
        state["meeting_options"] = [option.dict() for option in msg.meeting_options]
    ctx.logger.info(
        "Request %s has %s/3 specialist responses",
        msg.request_id,
        len(state["responses"]),
    )
    if len(state["responses"]) < len(SPECIALIST_ADDRESSES):
        return
    await finalize_request(ctx, msg.request_id)


@agent.on_interval(period=5.0)
async def recover_timed_out_requests(ctx: Context):
    expired = [
        request_id
        for request_id, state in pending.items()
        if time.monotonic() - state["created_at"] >= REQUEST_TIMEOUT_SECONDS
    ]
    for request_id in expired:
        ctx.logger.warning("Finalizing timed-out request %s with partial results", request_id)
        await finalize_request(ctx, request_id, timed_out=True)


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


agent.include(chat_protocol, publish_manifest=True)
agent.include(planning_protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
