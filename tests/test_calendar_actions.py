import tempfile
import unittest
from pathlib import Path

from calendar_actions import confirm_option, google_calendar_template_url, parse_option_selection
from agent_messages import MeetingOption, SpecialistResponse
from uagents.storage import KeyValueStore


OPTION = {
    "option_id": 2,
    "title": "Meet with Maya",
    "start_iso": "2026-06-22T13:00:00",
    "end_iso": "2026-06-22T13:45:00",
    "score": 142,
    "reasons": ["Both calendars are open", "There is recovery time beforehand"],
    "tradeoffs": [],
}


class CalendarActionTests(unittest.TestCase):
    def test_uagents_protocol_schema_is_serializable(self):
        option = MeetingOption(
            option_id=1,
            title="Meet with Maya",
            start_iso="2026-06-22T13:00:00",
            end_iso="2026-06-22T13:45:00",
            score=100,
        )
        response = SpecialistResponse(
            request_id="request-1",
            specialist="wellness",
            result="ok",
            meeting_options=[option],
        )
        schema = response.schema_json()
        self.assertIn("meeting_options", schema)

    def test_selection_parser(self):
        self.assertEqual(parse_option_selection("choose option 2"), 2)
        self.assertEqual(parse_option_selection("Please book #1"), 1)
        self.assertIsNone(parse_option_selection("show me more times"))

    def test_google_calendar_handoff_contains_event(self):
        url = google_calendar_template_url(OPTION)
        self.assertIn("calendar.google.com/calendar/render", url)
        self.assertIn("Meet+with+Maya", url)
        self.assertIn("20260622T130000%2F20260622T134500", url)

    def test_confirmation_is_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            store = KeyValueStore(Path(directory) / "actions.json")
            receipt = confirm_option(store, "user-agent", OPTION)
            self.assertEqual(receipt["status"], "confirmed")
            saved = store.get("confirmed_events:user-agent")
            self.assertEqual(saved[0]["title"], "Meet with Maya")


if __name__ == "__main__":
    unittest.main()
