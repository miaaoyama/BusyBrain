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


class FlowTaskOut(BaseModel):
    """A task with its real energy-match status, for Today's Flow."""
    title: str
    time_range: str
    start_hour: float  # decimal hour, e.g. 8.5 for 8:30am — used to place on the chart
    type: str
    focus_label: str  # "Heavy focus" / "Medium focus" / "Light focus", derived from task_type
    match_status: str  # "peak_match" | "energy_dip" | "steady"
    note: str


class FlowCurvePoint(BaseModel):
    hour: float
    energy_percent: int


class DayFlowOut(BaseModel):
    dow: str
    dom: str
    title: str
    current_energy_percent: int
    current_energy_label: str
    peak_window_label: str  # e.g. "Morning energy" — which window we're in/near now
    events_count: int
    tasks_fighting_energy: int
    curve: List[FlowCurvePoint]
    tasks: List[FlowTaskOut]


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


# Energy levels map to a percentage band for the gauge/chart. These are
# fixed reference points, not a measured biometric value — the UI is
# explicit that this is a schedule-derived estimate, not a claim about how
# the person actually feels (see the wellness agent's "never infer mood"
# principle, applied here too).
_ENERGY_LEVEL_PERCENT = {
    EnergyLevel.HIGH: 85,
    EnergyLevel.MEDIUM: 55,
    EnergyLevel.LOW: 25,
}

# What energy level each task type implicitly needs, for match scoring.
# Mirrors the energy_needed values already used when these tasks were
# scheduled in agents.py, so "peak match" reflects the same logic that
# placed the task, not a separate guess.
_TASK_TYPE_ENERGY_NEED = {
    TaskType.STUDY: EnergyLevel.HIGH,
    TaskType.CLASS: EnergyLevel.MEDIUM,
    TaskType.APPOINTMENT: EnergyLevel.MEDIUM,
    TaskType.WORKOUT: EnergyLevel.MEDIUM,
    TaskType.MEAL: EnergyLevel.LOW,
    TaskType.SOCIAL: EnergyLevel.MEDIUM,
    TaskType.PERSONAL: EnergyLevel.LOW,
}

_FOCUS_LABEL = {
    EnergyLevel.HIGH: "Heavy focus",
    EnergyLevel.MEDIUM: "Medium focus",
    EnergyLevel.LOW: "Light focus",
}


def _energy_percent_at(hour: float, profile: UserProfile) -> int:
    """Real lookup against the profile's actual energy windows — not a
    fabricated curve. Hours outside any defined window get a low baseline,
    since no stated high/medium window applies there."""
    for window in profile.energy_windows:
        start_hour = window.start.hour + window.start.minute / 60
        end_hour = window.end.hour + window.end.minute / 60
        if start_hour <= hour < end_hour:
            return _ENERGY_LEVEL_PERCENT[window.energy]
    return 15  # outside any defined window — treated as a low-energy baseline


def _build_energy_curve(profile: UserProfile, step_minutes: int = 30) -> List[FlowCurvePoint]:
    points: List[FlowCurvePoint] = []
    hour = 7.0
    while hour <= 21.0:
        points.append(FlowCurvePoint(hour=hour, energy_percent=_energy_percent_at(hour, profile)))
        hour += step_minutes / 60
    return points


def _match_status(event_start_hour: float, task_type, profile: UserProfile) -> str:
    needed = _TASK_TYPE_ENERGY_NEED.get(task_type, EnergyLevel.MEDIUM)
    actual_percent = _energy_percent_at(event_start_hour, profile)
    needed_percent = _ENERGY_LEVEL_PERCENT[needed]
    if actual_percent >= needed_percent:
        return "peak_match"
    if actual_percent <= needed_percent - 30:
        return "energy_dip"
    return "steady"


@app.get("/today-flow", response_model=DayFlowOut)
def today_flow(day_offset: int = 0):
    """Real energy-aware view of a single day: current energy %, an hourly
    curve from the profile's actual energy windows, and each task's match
    status computed against what that task type needs versus the energy
    level at its scheduled time. day_offset selects which day of the
    current week to show (0 = first day of week, matching /schedule)."""
    _, classes, fixed_events, tasks, week_start = build_sample_inputs()
    profile = _build_profile()
    all_classes = classes + session_classes

    plan = orchestrator.build_week_plan(profile, all_classes, fixed_events, tasks, week_start)

    day = week_start + timedelta(days=day_offset)
    day_events = sorted(
        (e for e in plan.events if e.start.date() == day),
        key=lambda e: e.start,
    )

    now = datetime.now()
    current_hour = now.hour + now.minute / 60 if now.date() == day else 9.0
    current_percent = _energy_percent_at(current_hour, profile)
    current_level = next(
        (level for level, pct in _ENERGY_LEVEL_PERCENT.items() if pct == current_percent),
        EnergyLevel.LOW,
    )

    # Label the nearest/current window by time-of-day name, for display
    # (e.g. "Morning energy") rather than just showing a raw enum value.
    window_label = "Resting"
    for window in profile.energy_windows:
        start_hour = window.start.hour + window.start.minute / 60
        end_hour = window.end.hour + window.end.minute / 60
        if start_hour <= current_hour < end_hour:
            period = "Morning" if start_hour < 12 else ("Afternoon" if start_hour < 17 else "Evening")
            window_label = f"{period} energy"
            break

    flow_tasks: List[FlowTaskOut] = []
    fighting_count = 0
    for e in day_events:
        start_hour = e.start.hour + e.start.minute / 60
        status = _match_status(start_hour, e.task_type, profile)
        if status == "energy_dip":
            fighting_count += 1
        needed = _TASK_TYPE_ENERGY_NEED.get(e.task_type, EnergyLevel.MEDIUM)
        flow_tasks.append(FlowTaskOut(
            title=e.title,
            time_range=f"{e.start.strftime('%I:%M %p').lstrip('0')} \u2013 {e.end.strftime('%I:%M %p').lstrip('0')}",
            start_hour=start_hour,
            type=_TASK_TYPE_LABEL.get(e.task_type, "personal"),
            focus_label=_FOCUS_LABEL[needed],
            match_status=status,
            note=e.notes,
        ))

    return DayFlowOut(
        dow=day.strftime("%a").upper(),
        dom=day.strftime("%d"),
        title=day.strftime("%A, %B %d"),
        current_energy_percent=current_percent,
        current_energy_label="Time for a gentle reset" if current_percent < 40 else "Feeling steady",
        peak_window_label=window_label,
        events_count=len(day_events),
        tasks_fighting_energy=fighting_count,
        curve=_build_energy_curve(profile),
        tasks=flow_tasks,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
