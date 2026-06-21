import unittest
from datetime import date, datetime, time

from coordination import MeetingConstraints, parse_meeting_request, rank_friend_meeting_slots
from models import CalendarEvent, EnergyLevel, EnergyWindow, FocusProfile, TaskType, UserProfile


DAY = date(2026, 6, 22)


def event(title, start_hour, end_hour, task_type=TaskType.CLASS):
    return CalendarEvent(
        title=title,
        start=datetime.combine(DAY, time(start_hour)),
        end=datetime.combine(DAY, time(end_hour)),
        task_type=task_type,
    )


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.profile = UserProfile(
            name="Student",
            focus_profile=FocusProfile("balanced"),
            energy_windows=[EnergyWindow(time(8), time(12), EnergyLevel.HIGH)],
            day_start=time(8),
            day_end=time(20),
        )

    def test_natural_language_constraints(self):
        result = parse_meeting_request(
            "Find 45 minutes with Maya in the afternoon, not right after class",
            ["Maya", "Sam"],
        )
        self.assertEqual(result.friend_name, "Maya")
        self.assertEqual(result.duration_minutes, 45)
        self.assertEqual(result.preferred_period, "afternoon")
        self.assertTrue(result.avoid_after_demanding)

    def test_packed_transition_is_ranked_below_recovery_gap(self):
        user_events = [event("Long class", 8, 12)]
        friend_events = [event("Lab", 15, 17)]
        candidates = rank_friend_meeting_slots(
            user_events,
            friend_events,
            self.profile,
            DAY,
            DAY,
            MeetingConstraints(duration_minutes=60, avoid_after_demanding=True),
            limit=20,
            step_minutes=30,
        )
        immediate = next(candidate for candidate in candidates if candidate.start.time() == time(12))
        recovered = next(candidate for candidate in candidates if candidate.start.time() == time(13))
        self.assertGreater(recovered.score, immediate.score)
        self.assertTrue(any("only 0 minutes" in item for item in immediate.tradeoffs))

    def test_candidates_never_overlap_either_calendar(self):
        user_events = [event("Class", 9, 11)]
        friend_events = [event("Work", 13, 16, TaskType.PERSONAL)]
        candidates = rank_friend_meeting_slots(
            user_events,
            friend_events,
            self.profile,
            DAY,
            DAY,
            MeetingConstraints(duration_minutes=60),
            limit=50,
        )
        for candidate in candidates:
            for busy in user_events + friend_events:
                self.assertFalse(busy.overlaps(candidate.start, candidate.end))


if __name__ == "__main__":
    unittest.main()
