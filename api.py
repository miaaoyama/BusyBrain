"""FastAPI layer over BusyBrain's real planning logic.

This is the bridge between the UI (plain HTML/JS) and the actual agent code
in agents.py / scheduler.py / models.py. No fake data lives here — every
response is computed by the same CalendarOrchestrator and SocialAgent used
by the uAgents network, just called directly instead of over a chat message.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents import CalendarOrchestrator, SocialAgent
from coordination import MeetingConstraints
from models import ClassPlan, EnergyLevel, FocusProfile, EnergyWindow, UserProfile, TaskType
from sample_data import build_friend_schedules, build_sample_inputs

app = FastAPI(title="BusyBrain API")

# Loosened for hackathon demo purposes only — tighten before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = CalendarOrchestrator()

# In-memory store for classes added via the "Classes & Energy" tab during this
# demo session. Resets on server restart — fine for a hackathon, would need a
# real datastore for production.
session_classes: List[ClassPlan] = []

# The most recently submitted focus rhythm / energy preference. models.py's
# FocusProfile and energy windows are per-profile, not per-class, so the most
# honest behavior for this demo is: the latest "Add a class" submission updates
# the active session profile, rather than being silently ignored.
session_focus_minutes: Optional[int] = None
session_energy_label: Optional[str] = None


# ---------------------------------------------------------------------------
# Request / response shapes. These mirror exactly what the frontend expects,
# so the HTML/JS layer doesn't need to do any reshaping of the response.
# ---------------------------------------------------------------------------

class FindMeetingRequest(BaseModel):
    friend: str
    start_date: str  # "YYYY-MM-DD"
    days: int = 5
    duration_minutes: int = 60
    place: Optional[str] = None


class MeetingResultOut(BaseModel):
    when: str
    score: int
    reasons: List[str]
    start_iso: str
    end_iso: str


class AddClassRequest(BaseModel):
    class_name: str
    weekly_study_hours: float = 1.0
    focus_minutes: int = 30
    energy_label: str = "Morning"


class TaskOut(BaseModel):
    title: str
    time: str
    type: str
    note: str


class DayOut(BaseModel):
    dow: str
    dom: str
    title: str
    tasks: List[TaskOut]


_ENERGY_LABEL_TO_LEVEL = {
    "Morning": EnergyLevel.HIGH,
    "Afternoon": EnergyLevel.MEDIUM,
    "Evening": EnergyLevel.LOW,
}

_TASK_TYPE_LABEL = {
    TaskType.CLASS: "class",
    TaskType.STUDY: "study",
    TaskType.APPOINTMENT: "appointment",
    TaskType.WORKOUT: "workout",
    TaskType.MEAL: "meal",
    TaskType.SOCIAL: "personal",
    TaskType.PERSONAL: "personal",
}


def _build_profile() -> UserProfile:
    """Builds the demo profile, applying any focus/energy preference submitted
    this session via the Classes & Energy form. Falls back to the sample
    profile's defaults if nothing has been submitted yet."""
    profile, _, _, _, _ = build_sample_inputs()

    if session_focus_minutes is not None:
        profile.focus_profile = FocusProfile(
            name=profile.focus_profile.name,
            focus_minutes=session_focus_minutes,
            break_minutes=profile.focus_profile.break_minutes,
            max_blocks_per_day=profile.focus_profile.max_blocks_per_day,
        )

    if session_energy_label is not None:
        target_level = _ENERGY_LABEL_TO_LEVEL.get(session_energy_label)
        if target_level is not None:
            # Re-tag the energy window that currently has the highest energy
            # so it matches the user's stated peak period, rather than
            # silently keeping "Morning" as HIGH regardless of their choice.
            adjusted_windows = []
            for window in profile.energy_windows:
                period = _window_period(window.start)
                if period == session_energy_label.lower():
                    adjusted_windows.append(EnergyWindow(window.start, window.end, EnergyLevel.HIGH))
                elif window.energy == EnergyLevel.HIGH:
                    # Demote the previous HIGH window so there's exactly one
                    # peak window, matching what the user just told us.
                    adjusted_windows.append(EnergyWindow(window.start, window.end, EnergyLevel.MEDIUM))
                else:
                    adjusted_windows.append(window)
            profile.energy_windows = adjusted_windows

    return profile


def _window_period(start_time: time) -> str:
    if start_time.hour < 12:
        return "morning"
    if start_time.hour < 17:
        return "afternoon"
    return "evening"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/find-meeting", response_model=List[MeetingResultOut])
def find_meeting(req: FindMeetingRequest):
    """Real friend-meeting ranking, using SocialAgent + sample calendars."""
    profile, classes, fixed_events, tasks, week_start = build_sample_inputs()
    plan = orchestrator.build_week_plan(profile, classes, fixed_events, tasks, week_start)

    friend_schedules = build_friend_schedules()
    friend_events = friend_schedules.get(req.friend, [])

    start_day = date.fromisoformat(req.start_date)
    end_day = start_day + timedelta(days=req.days)

    social = SocialAgent()
    candidates = social.rank_friend_meetings(
        friend_a_events=plan.events,
        friend_b_events=friend_events,
        profile=profile,
        start_day=start_day,
        end_day=end_day,
        constraints=MeetingConstraints(duration_minutes=req.duration_minutes),
        limit=3,
    )

    return [
        MeetingResultOut(
            when=f"{c.start.strftime('%a, %b %d')} \u00b7 {c.start.strftime('%I:%M %p').lstrip('0')}\u2013{c.end.strftime('%I:%M %p').lstrip('0')}",
            score=c.score,
            reasons=c.reasons,
            start_iso=c.start.isoformat(),
            end_iso=c.end.isoformat(),
        )
        for c in candidates
    ]


class VenueSuggestionRequest(BaseModel):
    activity_hint: Optional[str] = None
    place: Optional[str] = None


class VenueSuggestionOut(BaseModel):
    name: str
    url: Optional[str] = None
    snippet: str
    source: str


@app.post("/venue-suggestion", response_model=VenueSuggestionOut)
def venue_suggestion(req: VenueSuggestionRequest):
    """Real Browserbase-powered venue lookup, called once the user has
    chosen a specific meeting time. Kept separate from /find-meeting so a
    slow venue lookup doesn't delay showing the ranked time options.

    Degrades gracefully (returns source="unavailable") instead of a 500 if
    BROWSERBASE_API_KEY is missing or the lookup fails for any reason —
    the venue suggestion is a nice-to-have layered on top of the real
    scheduling logic, not something that should break the demo if it fails.
    """
    activity = req.activity_hint or "casual meetup spot"
    try:
        from venue_lookup import find_venue_for_meetup
        venue = find_venue_for_meetup(activity, req.place)
    except Exception as exc:
        return VenueSuggestionOut(name="Venue lookup unavailable", url=None, snippet=str(exc), source="unavailable")

    if not venue:
        return VenueSuggestionOut(name="No venue found", url=None, snippet="", source="none")
    return VenueSuggestionOut(name=venue.name, url=venue.url, snippet=venue.snippet, source=venue.source)


@app.post("/classes")
def add_class(req: AddClassRequest):
    """Adds a class for this session, to be included in the next schedule generation.

    Also updates the session's active focus rhythm and energy preference —
    see _build_profile for why this is profile-wide rather than per-class.
    """
    global session_focus_minutes, session_energy_label
    session_focus_minutes = req.focus_minutes
    session_energy_label = req.energy_label

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    # A representative weekly meeting placeholder so the study planner has an
    # anchor date range; real meeting times would come from a calendar import.
    placeholder_meeting_start = datetime.combine(week_start, time(10, 0))
    from models import CalendarEvent
    meetings = [
        CalendarEvent(
            title=req.class_name,
            start=placeholder_meeting_start,
            end=placeholder_meeting_start + timedelta(hours=1, minutes=30),
            task_type=TaskType.CLASS,
            location="Campus",
        )
    ]
    session_classes.append(
        ClassPlan(class_name=req.class_name, meetings=meetings, weekly_study_hours=req.weekly_study_hours)
    )
    return {"added": req.class_name, "total_classes": len(session_classes)}


@app.get("/schedule", response_model=List[DayOut])
def generate_schedule():
    """Real week plan from CalendarOrchestrator, including any session-added
    classes and the most recently submitted focus/energy preference."""
    _, classes, fixed_events, tasks, week_start = build_sample_inputs()
    profile = _build_profile()
    all_classes = classes + session_classes

    plan = orchestrator.build_week_plan(profile, all_classes, fixed_events, tasks, week_start)

    days: List[DayOut] = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        day_events = [e for e in plan.events if e.start.date() == day]
        day_events.sort(key=lambda e: e.start)
        days.append(DayOut(
            dow=day.strftime("%a"),
            dom=day.strftime("%b %d"),
            title=day.strftime("%A, %B %d"),
            tasks=[
                TaskOut(
                    title=e.title,
                    time=f"{e.start.strftime('%I:%M %p').lstrip('0')} \u2013 {e.end.strftime('%I:%M %p').lstrip('0')}",
                    type=_TASK_TYPE_LABEL.get(e.task_type, "personal"),
                    note=e.notes,
                )
                for e in day_events
            ],
        ))
    return days


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)