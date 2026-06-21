"""Typed messages exchanged by the BusyBrain uAgents."""

from uagents import Model
from pydantic.v1 import Field


class PlanningRequest(Model):
    request_id: str
    user_text: str


class MeetingOption(Model):
    option_id: int
    title: str
    start_iso: str
    end_iso: str
    score: int
    reasons: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)


class SpecialistResponse(Model):
    request_id: str
    specialist: str
    result: str
    meeting_options: list[MeetingOption] = Field(default_factory=list)
