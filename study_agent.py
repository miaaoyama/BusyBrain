"""Study specialist uAgent."""

from uagents import Agent, Context, Protocol
from uagents.registration import AlmanacApiRegistrationPolicy

from agent_config import ORCHESTRATOR_ADDRESS, STUDY_SEED
from agent_messages import PlanningRequest, SpecialistResponse
from agent_utils import ask_asi


agent = Agent(
    name="BusyBrainStudyPlanner",
    seed=STUDY_SEED,
    port=8002,
    mailbox=True,
    readme_path="README.md",
    description="Builds ADHD-friendly study blocks from workload and energy needs.",
    registration_policy=AlmanacApiRegistrationPolicy(),
    publish_agent_details=True,
)
protocol = Protocol(name="BusyBrainStudyProtocol", version="1.0.0")


@protocol.on_message(PlanningRequest, replies=SpecialistResponse)
async def plan_study(ctx: Context, sender: str, msg: PlanningRequest):
    if sender != ORCHESTRATOR_ADDRESS:
        ctx.logger.warning("Rejected planning request from unknown sender %s", sender)
        return

    ctx.logger.info("Received request %s from BusyBrain", msg.request_id)
    try:
        result = await ask_asi(
            """You are BusyBrain's Study Planner specialist. Extract schoolwork,
deadlines, difficulty, and available time from the request. Propose realistic
30/10, 40/10, or 60/10 focus blocks. Limit daily overload, include breaks, and
flag missing information. Return concise recommendations for another agent to
merge into a final plan. Never diagnose a medical condition.""",
            msg.user_text,
        )
    except Exception as exc:
        ctx.logger.exception("Study planning failed")
        result = f"Study specialist could not complete the request: {exc}"

    await ctx.send(
        sender,
        SpecialistResponse(
            request_id=msg.request_id, specialist="study", result=result
        ),
    )
    ctx.logger.info("Returned study plan for request %s", msg.request_id)


agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
