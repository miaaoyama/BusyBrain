"""End-to-end Chat Protocol client for the live BusyBrain agent network."""

import os
from datetime import datetime, timezone
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

from agent_config import ORCHESTRATOR_ADDRESS


PROMPT = os.getenv(
    "BUSY_BRAIN_TEST_PROMPT",
    "I have class Monday and Wednesday 10-11:30 and a six-hour project due "
    "Saturday. My best focus is in the morning. Make a realistic plan with "
    "meals, breaks, and recovery.",
)

client = Agent(
    name="BusyBrainSmokeTest",
    seed="busy-brain-local-smoke-test-client-2026",
    port=8005,
    endpoint=["http://127.0.0.1:8005/submit"],
    registration_policy=AlmanacApiRegistrationPolicy(),
    publish_agent_details=False,
)
protocol = Protocol(spec=chat_protocol_spec)


@client.on_event("startup")
async def send_test(ctx: Context):
    ctx.logger.info("Sending end-to-end test to %s", ORCHESTRATOR_ADDRESS)
    await ctx.send(
        ORCHESTRATOR_ADDRESS,
        ChatMessage(
            timestamp=datetime.now(tz=timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=PROMPT)],
        ),
    )


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info("Orchestrator acknowledged the test request")


@protocol.on_message(ChatMessage)
async def handle_reply(ctx: Context, sender: str, msg: ChatMessage):
    for item in msg.content:
        if isinstance(item, TextContent):
            print("\n=== BUSYBRAIN END-TO-END RESPONSE ===\n")
            print(item.text)
            print("\n=== TEST PASSED ===\n")

    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(tz=timezone.utc), acknowledged_msg_id=msg.msg_id
        ),
    )


client.include(protocol, publish_manifest=False)

if __name__ == "__main__":
    client.run()

