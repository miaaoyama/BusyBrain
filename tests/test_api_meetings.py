from datetime import date, datetime, time, timedelta

import api


def setup_function():
    api.session_meetings.clear()


def teardown_function():
    api.session_meetings.clear()


def test_saved_meeting_appears_in_today_flow_and_is_idempotent():
    today = date.today()
    start = datetime.combine(today, time(17, 0))
    end = start + timedelta(hours=1)
    request = api.SaveMeetingRequest(
        friend="Maya",
        start_iso=start.isoformat(),
        end_iso=end.isoformat(),
        venue="Quiet cafe",
    )

    first = api.save_meeting(request)
    second = api.save_meeting(request)

    assert first.saved is True
    assert second.saved is False
    assert len(api.session_meetings) == 1

    flow = api.today_flow(day_offset=today.weekday())
    meeting = next(task for task in flow.tasks if task.title == "Meet with Maya")
    assert meeting.type == "personal"
    assert meeting.time_range == "5:00 PM – 6:00 PM"


def test_today_flow_accepts_dates_beyond_the_current_week():
    future = date.today() + timedelta(days=35)
    offset = (future - (date.today() - timedelta(days=date.today().weekday()))).days

    flow = api.today_flow(day_offset=offset)

    assert flow.title == future.strftime("%A, %B %d")
    assert flow.tasks  # recurring planning/support tasks exist beyond week one


def test_saved_future_meeting_appears_in_its_schedule_week():
    current_monday = date.today() - timedelta(days=date.today().weekday())
    meeting_day = current_monday + timedelta(weeks=3, days=2)
    start = datetime.combine(meeting_day, time(15, 0))
    api.save_meeting(api.SaveMeetingRequest(
        friend="Jordan",
        start_iso=start.isoformat(),
        end_iso=(start + timedelta(minutes=45)).isoformat(),
    ))

    week = api.generate_schedule(week_offset=3)

    wednesday = week[2]
    assert any(task.title == "Meet with Jordan" for task in wednesday.tasks)
