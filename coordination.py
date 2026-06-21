"""Explainable, energy-aware friend meeting coordination.

The scores use observable calendar signals only. They never claim to infer a
person's mood or health from an event title.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Iterable

from models import CalendarEvent, TaskType, UserProfile
from scheduler import combine, is_free


DEMANDING_TYPES = {
    TaskType.CLASS,
    TaskType.STUDY,
    TaskType.APPOINTMENT,
}


@dataclass
class MeetingConstraints:
    friend_name: str | None = None
    duration_minutes: int = 60
    preferred_period: str | None = None
    avoid_after_demanding: bool = False


@dataclass
class MeetingCandidate:
    start: datetime
    end: datetime
    score: int
    reasons: list[str] = field(default_factory=list)
    tradeoffs: list[str] = field(default_factory=list)


def parse_meeting_request(text: str, friend_names: Iterable[str]) -> MeetingConstraints:
    """Extract the small set of constraints the visual demo supports."""
    lowered = text.lower()
    friend = next((name for name in friend_names if name.lower() in lowered), None)

    duration = 60
    duration_match = re.search(r"\b(30|45|60|90|120)\s*(?:minutes?|mins?)\b", lowered)
    if duration_match:
        duration = int(duration_match.group(1))
    elif "half an hour" in lowered:
        duration = 30
    elif "an hour and a half" in lowered or "90 min" in lowered:
        duration = 90
    elif "an hour" in lowered:
        duration = 60

    preferred_period = next(
        (period for period in ("morning", "afternoon", "evening") if period in lowered),
        None,
    )
    avoid_after_demanding = any(
        phrase in lowered
        for phrase in (
            "not right after",
            "avoid right after",
            "not after class",
            "not after work",
            "avoid packed",
            "when we have energy",
        )
    )
    return MeetingConstraints(
        friend_name=friend,
        duration_minutes=duration,
        preferred_period=preferred_period,
        avoid_after_demanding=avoid_after_demanding,
    )


def _day_events(events: list[CalendarEvent], day: date) -> list[CalendarEvent]:
    return sorted((event for event in events if event.start.date() == day), key=lambda e: e.start)


def _minutes(events: list[CalendarEvent]) -> int:
    return int(sum((event.end - event.start).total_seconds() for event in events) // 60)


def _is_demanding(event: CalendarEvent) -> bool:
    duration = (event.end - event.start).total_seconds() / 60
    return event.task_type in DEMANDING_TYPES or duration >= 120


def _evaluate_person(
    label: str,
    events: list[CalendarEvent],
    start: datetime,
    end: datetime,
    avoid_after_demanding: bool,
) -> tuple[int, list[str], list[str]]:
    day_events = _day_events(events, start.date())
    daily_minutes = _minutes(day_events)
    before = [event for event in day_events if event.end <= start]
    after = [event for event in day_events if event.start >= end]
    previous = before[-1] if before else None
    following = after[0] if after else None

    score = 0
    reasons: list[str] = []
    tradeoffs: list[str] = []

    if daily_minutes <= 180:
        score += 18
        reasons.append(f"{label} has a relatively light day before adding this meetup")
    elif daily_minutes >= 420:
        score -= 28
        tradeoffs.append(f"{label} already has about {daily_minutes // 60} scheduled hours that day")

    if previous:
        gap = int((start - previous.end).total_seconds() // 60)
        if gap >= 60:
            score += 16
            reasons.append(f"{label} gets a {gap}-minute reset beforehand")
        elif gap < 30:
            penalty = 28 if avoid_after_demanding and _is_demanding(previous) else 14
            score -= penalty
            tradeoffs.append(f"{label} has only {gap} minutes after {previous.title}")
    else:
        score += 8
        reasons.append(f"{label} has no earlier calendar block that day")

    if following:
        gap = int((following.start - end).total_seconds() // 60)
        if gap >= 45:
            score += 10
        elif gap < 20:
            score -= 15
            tradeoffs.append(f"{label} has only {gap} minutes before {following.title}")
    else:
        score += 6

    return score, reasons, tradeoffs


def rank_friend_meeting_slots(
    user_events: list[CalendarEvent],
    friend_events: list[CalendarEvent],
    profile: UserProfile,
    start_day: date,
    end_day: date,
    constraints: MeetingConstraints,
    limit: int = 3,
    step_minutes: int = 30,
) -> list[MeetingCandidate]:
    """Rank shared openings and provide an auditable explanation for each."""
    candidates: list[MeetingCandidate] = []
    day = start_day
    duration = timedelta(minutes=constraints.duration_minutes)

    while day <= end_day:
        slot_start = combine(day, profile.day_start)
        day_end = combine(day, profile.day_end)
        while slot_start + duration <= day_end:
            slot_end = slot_start + duration
            if is_free(user_events, slot_start, slot_end) and is_free(
                friend_events, slot_start, slot_end
            ):
                score = 50
                reasons: list[str] = ["The time is open on both calendars"]
                tradeoffs: list[str] = []

                for label, events in (
                    ("Your schedule", user_events),
                    ("Your friend's schedule", friend_events),
                ):
                    person_score, person_reasons, person_tradeoffs = _evaluate_person(
                        label,
                        events,
                        slot_start,
                        slot_end,
                        constraints.avoid_after_demanding,
                    )
                    score += person_score
                    reasons.extend(person_reasons)
                    tradeoffs.extend(person_tradeoffs)

                hour = slot_start.hour
                period_matches = {
                    "morning": 8 <= hour < 12,
                    "afternoon": 12 <= hour < 17,
                    "evening": 17 <= hour < 21,
                }
                if constraints.preferred_period:
                    if period_matches[constraints.preferred_period]:
                        score += 20
                        reasons.append(f"It matches the requested {constraints.preferred_period}")
                    else:
                        score -= 8
                if hour < 8 or hour >= 21:
                    score -= 25
                    tradeoffs.append("The time falls near the edge of the day")

                candidates.append(
                    MeetingCandidate(
                        start=slot_start,
                        end=slot_end,
                        score=score,
                        reasons=reasons[:4],
                        tradeoffs=tradeoffs[:3],
                    )
                )
            slot_start += timedelta(minutes=step_minutes)
        day += timedelta(days=1)

    candidates.sort(key=lambda candidate: (-candidate.score, candidate.start))
    return candidates[:limit]
