"""Calendar and logistics specialist uAgent."""

from uagents import Agent, Context, Protocol
from uagents.registration import AlmanacApiRegistrationPolicy

from agent_config import CALENDAR_SEED, ORCHESTRATOR_ADDRESS
from agent_messages import PlanningRequest, SpecialistResponse
from agent_utils import ask_asi


agent = Agent(
    name="BusyBrainCalendarPlanner",
    seed=CALENDAR_SEED,
    port=8003,
    mailbox=True,
    readme_path="README.md",
    description="Finds realistic calendar slots and protects travel and transition time.",
    registration_policy=AlmanacApiRegistrationPolicy(),
    publish_agent_details=True,
)
protocol = Protocol(name="BusyBrainCalendarProtocol", version="1.0.0")


@protocol.on_message(PlanningRequest, replies=SpecialistResponse)
async def plan_calendar(ctx: Context, sender: str, msg: PlanningRequest):
    if sender != ORCHESTRATOR_ADDRESS:
        ctx.logger.warning("Rejected planning request from unknown sender %s", sender)
        return

    ctx.logger.info("Received request %s from BusyBrain", msg.request_id)
    try:
        result = await ask_asi(
            """You are BusyBrain's Calendar and Logistics specialist. Identify
fixed commitments, due dates, time windows, locations, travel, preparation, and
transition buffers. Find conflicts and propose a chronological schedule. Do not
double-book or invent exact times the user did not provide; clearly label
assumptions. Return concise recommendations for an orchestrator.""",
            msg.user_text,
        )
    except Exception as exc:
        ctx.logger.exception("Calendar planning failed")
        result = f"Calendar specialist could not complete the request: {exc}"

    await ctx.send(
        sender,
        SpecialistResponse(
            request_id=msg.request_id, specialist="calendar", result=result
        ),
    )
    ctx.logger.info("Returned calendar plan for request %s", msg.request_id)


agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
