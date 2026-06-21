from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Optional, List


class EnergyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskType(str, Enum):
    CLASS = "class"
    STUDY = "study"
    APPOINTMENT = "appointment"
    WORKOUT = "workout"
    MEAL = "meal"
    SOCIAL = "social"
    PERSONAL = "personal"


@dataclass
class FocusProfile:
    name: str
    focus_minutes: int = 40
    break_minutes: int = 10
    max_blocks_per_day: int = 4

    @property
    def block_total_minutes(self) -> int:
        return self.focus_minutes + self.break_minutes


@dataclass
class EnergyWindow:
    start: time
    end: time
    energy: EnergyLevel


@dataclass
class UserProfile:
    name: str
    focus_profile: FocusProfile
    energy_windows: List[EnergyWindow]
    preferred_workout_minutes: int = 30
    drive_buffer_minutes: int = 20
    day_start: time = time(7, 0)
    day_end: time = time(22, 0)


@dataclass
class CalendarEvent:
    title: str
    start: datetime
    end: datetime
    task_type: TaskType
    location: Optional[str] = None
    notes: str = ""
    flexible: bool = False

    def overlaps(self, other_start: datetime, other_end: datetime) -> bool:
        return self.start < other_end and other_start < self.end


@dataclass
class ClassPlan:
    class_name: str
    meetings: List[CalendarEvent]
    weekly_study_hours: float = 10.0


@dataclass
class TaskRequest:
    title: str
    due: Optional[datetime]
    estimated_hours: float
    task_type: TaskType = TaskType.PERSONAL
    location: Optional[str] = None
    energy_needed: EnergyLevel = EnergyLevel.MEDIUM


@dataclass
class PlanResult:
    events: List[CalendarEvent] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    unscheduled: List[str] = field(default_factory=list)
