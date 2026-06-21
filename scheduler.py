from __future__ import annotations
from datetime import datetime, date, time, timedelta
from typing import List, Optional
from models import CalendarEvent, EnergyLevel, EnergyWindow, UserProfile


def combine(day: date, t: time) -> datetime:
    return datetime.combine(day, t)


def minutes_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def energy_score(level: EnergyLevel) -> int:
    return {EnergyLevel.LOW: 1, EnergyLevel.MEDIUM: 2, EnergyLevel.HIGH: 3}[level]


def window_score(slot_start: datetime, slot_end: datetime, profile: UserProfile, needed: EnergyLevel) -> int:
    score = 0
    needed_score = energy_score(needed)
    for window in profile.energy_windows:
        ws = combine(slot_start.date(), window.start)
        we = combine(slot_start.date(), window.end)
        if slot_start >= ws and slot_end <= we:
            score += energy_score(window.energy) * 10
            if energy_score(window.energy) >= needed_score:
                score += 50
    return score


def is_free(existing: List[CalendarEvent], start: datetime, end: datetime) -> bool:
    return all(not event.overlaps(start, end) for event in existing)


def find_best_slot(
    existing: List[CalendarEvent],
    profile: UserProfile,
    duration_minutes: int,
    start_day: date,
    end_day: date,
    energy_needed: EnergyLevel = EnergyLevel.MEDIUM,
    step_minutes: int = 15,
) -> Optional[tuple[datetime, datetime]]:
    candidates: list[tuple[int, datetime, datetime]] = []
    current_day = start_day
    while current_day <= end_day:
        day_start = combine(current_day, profile.day_start)
        day_end = combine(current_day, profile.day_end)
        slot_start = day_start
        while slot_start + timedelta(minutes=duration_minutes) <= day_end:
            slot_end = slot_start + timedelta(minutes=duration_minutes)
            if is_free(existing, slot_start, slot_end):
                score = window_score(slot_start, slot_end, profile, energy_needed)
                # Prefer not too late, and prefer earlier deadlines.
                if slot_start.hour >= 20:
                    score -= 10
                candidates.append((score, slot_start, slot_end))
            slot_start += timedelta(minutes=step_minutes)
        current_day += timedelta(days=1)
    if not candidates:
        return None
    candidates.sort(key=lambda c: (-c[0], c[1]))
    return candidates[0][1], candidates[0][2]


def split_hours_into_focus_blocks(total_hours: float, focus_minutes: int) -> List[int]:
    total_minutes = int(total_hours * 60)
    blocks = []
    while total_minutes > 0:
        block = min(focus_minutes, total_minutes)
        blocks.append(block)
        total_minutes -= block
    return blocks


def add_drive_buffers(event: CalendarEvent, profile: UserProfile) -> list[CalendarEvent]:
    if not event.location:
        return []
    buffer = timedelta(minutes=profile.drive_buffer_minutes)
    return [
        CalendarEvent(
            title=f"Drive to {event.title}",
            start=event.start - buffer,
            end=event.start,
            task_type=event.task_type,
            location=event.location,
            notes="Automatically added travel buffer.",
            flexible=False,
        ),
        CalendarEvent(
            title=f"Drive back from {event.title}",
            start=event.end,
            end=event.end + buffer,
            task_type=event.task_type,
            location=event.location,
            notes="Automatically added travel buffer.",
            flexible=False,
        ),
    ]
