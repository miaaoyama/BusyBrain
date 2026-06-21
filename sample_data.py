from datetime import date, datetime, time, timedelta
from models import (
    CalendarEvent,
    ClassPlan,
    EnergyLevel,
    EnergyWindow,
    FocusProfile,
    TaskRequest,
    TaskType,
    UserProfile,
)


def build_sample_inputs():
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    profile = UserProfile(
        name="Student",
        focus_profile=FocusProfile(name="ADHD balanced", focus_minutes=40, break_minutes=10, max_blocks_per_day=4),
        energy_windows=[
            EnergyWindow(time(8, 30), time(11, 30), EnergyLevel.HIGH),
            EnergyWindow(time(13, 00), time(16, 00), EnergyLevel.MEDIUM),
            EnergyWindow(time(19, 00), time(21, 00), EnergyLevel.LOW),
        ],
        preferred_workout_minutes=25,
        drive_buffer_minutes=25,
    )

    cs_meetings = [
        CalendarEvent("CS Class", datetime.combine(week_start + timedelta(days=0), time(10, 0)), datetime.combine(week_start + timedelta(days=0), time(11, 30)), TaskType.CLASS, location="Campus"),
        CalendarEvent("CS Class", datetime.combine(week_start + timedelta(days=2), time(10, 0)), datetime.combine(week_start + timedelta(days=2), time(11, 30)), TaskType.CLASS, location="Campus"),
    ]

    design_meetings = [
        CalendarEvent("Design Studio", datetime.combine(week_start + timedelta(days=1), time(13, 0)), datetime.combine(week_start + timedelta(days=1), time(15, 30)), TaskType.CLASS, location="Campus"),
        CalendarEvent("Design Studio", datetime.combine(week_start + timedelta(days=3), time(13, 0)), datetime.combine(week_start + timedelta(days=3), time(15, 30)), TaskType.CLASS, location="Campus"),
    ]

    classes = [
        ClassPlan("Computer Science", cs_meetings, weekly_study_hours=10),
        ClassPlan("Design Studio", design_meetings, weekly_study_hours=6),
    ]

    fixed_events = cs_meetings + design_meetings + [
        CalendarEvent("Therapy appointment", datetime.combine(week_start + timedelta(days=4), time(12, 0)), datetime.combine(week_start + timedelta(days=4), time(13, 0)), TaskType.APPOINTMENT, location="Clinic"),
        CalendarEvent("Work shift", datetime.combine(week_start + timedelta(days=4), time(15, 0)), datetime.combine(week_start + timedelta(days=4), time(19, 0)), TaskType.PERSONAL),
    ]

    tasks = [
        TaskRequest("Finish project README", datetime.combine(week_start + timedelta(days=5), time(23, 59)), estimated_hours=3, task_type=TaskType.STUDY, energy_needed=EnergyLevel.MEDIUM),
        TaskRequest("Submit scholarship form", datetime.combine(week_start + timedelta(days=3), time(23, 59)), estimated_hours=1.5, task_type=TaskType.PERSONAL, energy_needed=EnergyLevel.HIGH),
    ]

    return profile, classes, fixed_events, tasks, week_start


def build_friend_schedules():
    """Sample connected-calendar availability for the friend picker."""
    today = date.today()

    def busy(name, day_offset, start, end):
        day = today + timedelta(days=day_offset)
        return CalendarEvent(
            f"{name} busy",
            datetime.combine(day, start),
            datetime.combine(day, end),
            TaskType.PERSONAL,
        )

    return {
        "Maya": [
            busy("Maya", 0, time(9, 0), time(14, 0)),
            busy("Maya", 1, time(12, 0), time(17, 0)),
            busy("Maya", 2, time(9, 0), time(12, 0)),
            busy("Maya", 4, time(14, 0), time(20, 0)),
        ],
        "Jordan": [
            busy("Jordan", 0, time(13, 0), time(18, 0)),
            busy("Jordan", 2, time(8, 0), time(15, 0)),
            busy("Jordan", 3, time(10, 0), time(16, 0)),
            busy("Jordan", 5, time(11, 0), time(15, 0)),
        ],
        "Sam": [
            busy("Sam", 1, time(8, 0), time(13, 0)),
            busy("Sam", 2, time(16, 0), time(21, 0)),
            busy("Sam", 3, time(8, 0), time(12, 0)),
            busy("Sam", 4, time(9, 0), time(17, 0)),
        ],
    }
