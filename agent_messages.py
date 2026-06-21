"""Typed messages exchanged by the BusyBrain uAgents."""

from uagents import Model


class PlanningRequest(Model):
    request_id: str
    user_text: str


class SpecialistResponse(Model):
    request_id: str
    specialist: str
    result: str

