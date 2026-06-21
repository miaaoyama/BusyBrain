from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import List
from models import (
    CalendarEvent,
    ClassPlan,
    EnergyLevel,
    PlanResult,
    TaskRequest,
    TaskType,
    UserProfile,
)
from scheduler import add_drive_buffers, find_best_slot, is_free, split_hours_into_focus_blocks
from coordination import MeetingCandidate, MeetingConstraints, rank_friend_meeting_slots


class StudyPlannerAgent:
    """Adds invisible study work around class schedules."""

    def plan_class_study(self, class_plan: ClassPlan, profile: UserProfile, existing: List[CalendarEvent]) -> PlanResult:
        result = PlanResult()
        if not class_plan.meetings:
            result.unscheduled.append(f"No meetings found for {class_plan.class_name}.")
            return result

        start_day = min(m.start.date() for m in class_plan.meetings)
        end_day = start_day + timedelta(days=6)
        blocks = split_hours_into_focus_blocks(class_plan.weekly_study_hours, profile.focus_profile.focus_minutes)

        scheduled_today = {}
        for i, focus_minutes in enumerate(blocks, 1):
            duration = focus_minutes + profile.focus_profile.break_minutes
            slot = find_best_slot(
                existing + result.events,
                profile,
                duration,
                start_day,
                end_day,
                energy_needed=EnergyLevel.HIGH,
            )
            if not slot:
                result.unscheduled.append(f"Study block {i} for {class_plan.class_name}")
                continue
            start, end, reason = slot
            count = scheduled_today.get(start.date(), 0)
            if count >= profile.focus_profile.max_blocks_per_day:
                result.unscheduled.append(f"Daily focus limit reached for one {class_plan.class_name} block.")
                continue
            scheduled_today[start.date()] = count + 1
            result.events.append(CalendarEvent(
                title=f"Study: {class_plan.class_name} ({focus_minutes} min focus + break)",
                start=start,
                end=end,
                task_type=TaskType.STUDY,
                notes=f"Why this time: {reason}.",
                flexible=True,
            ))
        result.messages.append(f"Added study blocks for {class_plan.class_name} using {profile.focus_profile.focus_minutes}/{profile.focus_profile.break_minutes} focus rhythm.")
        return result


class TravelAgent:
    """Adds driving time for appointments/classes with locations."""

    def add_travel(self, events: List[CalendarEvent], profile: UserProfile) -> List[CalendarEvent]:
        travel_events = []
        for event in events:
            if event.location and event.task_type in {TaskType.APPOINTMENT, TaskType.CLASS, TaskType.SOCIAL}:
                travel_events.extend(add_drive_buffers(event, profile))
        return travel_events


class WellnessAgent:
    """Adds meals, recipes, workouts, and emotional support nudges."""

    recipe_ideas = [
        "rice bowl with eggs, avocado, and cucumber",
        "chicken wrap with hummus and greens",
        "salmon or tofu bowl with microwave rice",
        "pasta with tomato sauce and protein",
    ]

    messages = [
        "You do not have to finish everything at once. Start tiny.",
        "Your brain is not lazy. It is overloaded. One step is enough.",
        "Pause, drink water, unclench your shoulders, and restart gently.",
        "Done imperfectly still counts.",
    ]

    def plan_daily_support(self, day: date, profile: UserProfile, existing: List[CalendarEvent]) -> PlanResult:
        result = PlanResult()
        workout_minutes = profile.preferred_workout_minutes
        slot = find_best_slot(existing, profile, workout_minutes, day, day, EnergyLevel.MEDIUM)
        if slot:
            start, end, reason = slot
            result.events.append(CalendarEvent(
                title="Workout / movement reset",
                start=start,
                end=end,
                task_type=TaskType.WORKOUT,
                notes=f"Why this time: {reason}. Keep it easy if energy is low.",
                flexible=True,
            ))

        meal_slot = find_best_slot(existing + result.events, profile, 15, day, day, EnergyLevel.LOW)
        if meal_slot:
            meal_start, meal_end, meal_reason = meal_slot
            recipe = self.recipe_ideas[day.toordinal() % len(self.recipe_ideas)]
            result.events.append(CalendarEvent(
                title="Meal idea reminder",
                start=meal_start,
                end=meal_end,
                task_type=TaskType.MEAL,
                notes=f"Quick idea: {recipe}. Why this time: {meal_reason}.",
                flexible=True,
            ))

        for hour in [10, 14, 18]:
            start = datetime.combine(day, datetime.min.time()).replace(hour=hour)
            end = start + timedelta(minutes=5)
            if is_free(existing + result.events, start, end):
                result.events.append(CalendarEvent(
                    title="Gentle check-in",
                    start=start,
                    end=end,
                    task_type=TaskType.PERSONAL,
                    notes=self.messages[(day.toordinal() + hour) % len(self.messages)],
                    flexible=True,
                ))
        return result


class TaskAgent:
    """Schedules normal tasks by due date and estimated effort."""

    def plan_task(self, task: TaskRequest, profile: UserProfile, existing: List[CalendarEvent]) -> PlanResult:
        result = PlanResult()
        end_day = task.due.date() if task.due else date.today() + timedelta(days=7)
        blocks = split_hours_into_focus_blocks(task.estimated_hours, profile.focus_profile.focus_minutes)
        for i, focus_minutes in enumerate(blocks, 1):
            duration = focus_minutes + profile.focus_profile.break_minutes
            slot = find_best_slot(existing + result.events, profile, duration, date.today(), end_day, task.energy_needed)
            if not slot:
                result.unscheduled.append(f"{task.title} block {i}")
                continue
            start, end, reason = slot
            result.events.append(CalendarEvent(
                title=f"Task: {task.title}",
                start=start,
                end=end,
                task_type=task.task_type,
                location=task.location,
                notes=f"Auto-split from estimated {task.estimated_hours} hours. Why this time: {reason}.",
                flexible=True,
            ))
        return result


class SocialAgent:
    """Ranks shared time using observable load and transition signals."""

    ideas = [
        "quiet coffee shop for body-doubling",
        "library study room",
        "walk + smoothie",
        "museum or bookstore reset",
        "low-pressure lunch spot",
    ]

    def rank_friend_meetings(
        self,
        friend_a_events: List[CalendarEvent],
        friend_b_events: List[CalendarEvent],
        profile: UserProfile,
        start_day: date,
        end_day: date,
        constraints: MeetingConstraints,
        limit: int = 3,
    ) -> list[MeetingCandidate]:
        return rank_friend_meeting_slots(
            user_events=friend_a_events,
            friend_events=friend_b_events,
            profile=profile,
            start_day=start_day,
            end_day=end_day,
            constraints=constraints,
            limit=limit,
        )

    def find_friend_meeting(
        self,
        friend_a_events: List[CalendarEvent],
        friend_b_events: List[CalendarEvent],
        profile: UserProfile,
        start_day: date,
        end_day: date,
        duration_minutes: int = 90,
    ) -> PlanResult:
        result = PlanResult()
        candidates = self.rank_friend_meetings(
            friend_a_events,
            friend_b_events,
            profile,
            start_day,
            end_day,
            MeetingConstraints(duration_minutes=duration_minutes),
            limit=1,
        )
        if not candidates:
            result.unscheduled.append("Friend meeting")
            return result
        candidate = candidates[0]
        idea = self.ideas[start_day.toordinal() % len(self.ideas)]
        result.events.append(CalendarEvent(
            title=f"Friend meet-up: {idea}",
            start=candidate.start,
            end=candidate.end,
            task_type=TaskType.SOCIAL,
            notes="Why this time: " + "; ".join(candidate.reasons),
            flexible=True,
        ))
        result.messages.append(
            f"Meeting fit score {candidate.score}. " + "; ".join(candidate.reasons)
        )
        return result


class CalendarOrchestrator:
    """Coordinates all internal planning modules into one calendar plan."""

    def __init__(self) -> None:
        self.study_agent = StudyPlannerAgent()
        self.travel_agent = TravelAgent()
        self.wellness_agent = WellnessAgent()
        self.task_agent = TaskAgent()
        self.social_agent = SocialAgent()

    def build_week_plan(
        self,
        profile: UserProfile,
        classes: List[ClassPlan],
        fixed_events: List[CalendarEvent],
        tasks: List[TaskRequest],
        week_start: date,
    ) -> PlanResult:
        result = PlanResult(events=list(fixed_events))
        result.events.extend(self.travel_agent.add_travel(fixed_events, profile))

        for class_plan in classes:
            study_plan = self.study_agent.plan_class_study(class_plan, profile, result.events)
            result.events.extend(study_plan.events)
            result.messages.extend(study_plan.messages)
            result.unscheduled.extend(study_plan.unscheduled)

        for task in tasks:
            task_plan = self.task_agent.plan_task(task, profile, result.events)
            result.events.extend(task_plan.events)
            result.unscheduled.extend(task_plan.unscheduled)

        for offset in range(7):
            day = week_start + timedelta(days=offset)
            wellness = self.wellness_agent.plan_daily_support(day, profile, result.events)
            result.events.extend(wellness.events)

        result.events.sort(key=lambda e: e.start)
        return result
