"""Shared configuration for the BusyBrain uAgent network."""

from __future__ import annotations

import os

from uagents.crypto import Identity

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # Environment exports still work when python-dotenv is not installed yet.
    pass

ASI1_API_KEY = os.getenv("ASI1_API_KEY", "")

def required_seed(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is missing. Copy .env.example to .env and set it.")
    return value


ORCHESTRATOR_SEED = required_seed("BUSY_BRAIN_ORCHESTRATOR_SEED")
STUDY_SEED = required_seed("BUSY_BRAIN_STUDY_SEED")
CALENDAR_SEED = required_seed("BUSY_BRAIN_CALENDAR_SEED")
WELLNESS_SEED = required_seed("BUSY_BRAIN_WELLNESS_SEED")


def address_for(seed: str) -> str:
    return Identity.from_seed(seed, 0).address


ORCHESTRATOR_ADDRESS = address_for(ORCHESTRATOR_SEED)
STUDY_ADDRESS = address_for(STUDY_SEED)
CALENDAR_ADDRESS = address_for(CALENDAR_SEED)
WELLNESS_ADDRESS = address_for(WELLNESS_SEED)

SPECIALIST_ADDRESSES = {
    "study": STUDY_ADDRESS,
    "calendar": CALENDAR_ADDRESS,
    "wellness": WELLNESS_ADDRESS,
}
