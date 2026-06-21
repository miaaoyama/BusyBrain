"""Workload and social-context specialist uAgent."""

from datetime import date, timedelta

from uagents import Agent, Context, Protocol
from uagents.registration import AlmanacApiRegistrationPolicy

from agent_config import ORCHESTRATOR_ADDRESS, WELLNESS_SEED
from agent_messages import PlanningRequest, SpecialistResponse
from agent_utils import ask_asi
from agents import CalendarOrchestrator
from coordination import parse_meeting_request
from sample_data import build_friend_schedules, build_sample_inputs


agent = Agent(
    name="BusyBrainWorkloadContext",
    seed=WELLNESS_SEED,
    port=8004,
    mailbox=True,
    readme_path="README.md",
    description="Explains calendar pressure and fair, energy-aware social timing.",
    registration_policy=AlmanacApiRegistrationPolicy(),
    publish_agent_details=True,
)
protocol = Protocol(name="BusyBrainWellnessProtocol", version="1.0.0")


@protocol.on_message(PlanningRequest, replies=SpecialistResponse)
async def plan_wellness(ctx: Context, sender: str, msg: PlanningRequest):
    if sender != ORCHESTRATOR_ADDRESS:
        ctx.logger.warning("Rejected planning request from unknown sender %s", sender)
        return

    ctx.logger.info("Received request %s from BusyBrain", msg.request_id)
    try:
        friend_schedules = build_friend_schedules()
        constraints = parse_meeting_request(msg.user_text, friend_schedules)
        if constraints.friend_name:
            profile, classes, fixed_events, tasks, week_start = build_sample_inputs()
            planner = CalendarOrchestrator()
            user_plan = planner.build_week_plan(
                profile, classes, fixed_events, tasks, week_start
            )
            candidates = planner.social_agent.rank_friend_meetings(
                friend_a_events=user_plan.events,
                friend_b_events=friend_schedules[constraints.friend_name],
                profile=profile,
                start_day=date.today(),
                end_day=date.today() + timedelta(days=6),
                constraints=constraints,
                limit=3,
            )
            if not candidates:
                result = (
                    f"No shared {constraints.duration_minutes}-minute opening was found "
                    f"with {constraints.friend_name} in the next seven days."
                )
            else:
                options = []
                for index, candidate in enumerate(candidates, 1):
                    why = "; ".join(candidate.reasons)
                    tradeoffs = "; ".join(candidate.tradeoffs) or "none identified"
                    options.append(
                        f"Option {index}: {candidate.start.strftime('%A %b %d, %I:%M %p')}–"
                        f"{candidate.end.strftime('%I:%M %p')} (fit {candidate.score}). "
                        f"Why: {why}. Tradeoffs: {tradeoffs}."
                    )
                result = (
                    f"I compared the seeded calendars for the student and "
                    f"{constraints.friend_name} using observable load and transition "
                    "signals. " + "\n".join(options)
                )
        else:
            result = await ask_asi(
                """You are BusyBrain's Workload and Social Context specialist.
Analyze only defensible calendar signals: scheduled hours, back-to-back blocks,
event duration, travel, time since the last break, transition gaps, and late
finishes. When the request involves friends, compare the stated calendars and
recommend fair meeting windows with a concise 'why this time' rationale. Never
claim to infer mood, disability, or health from a calendar. Add only essential
meals or recovery buffers and return concise advice for an orchestrator.""",
                msg.user_text,
            )
    except Exception as exc:
        ctx.logger.exception("Wellness planning failed")
        result = f"Wellness specialist could not complete the request: {exc}"

    await ctx.send(
        sender,
        SpecialistResponse(
            request_id=msg.request_id, specialist="wellness", result=result
        ),
    )
    ctx.logger.info("Returned wellness plan for request %s", msg.request_id)


agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
