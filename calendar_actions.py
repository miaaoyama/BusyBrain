"""Executable calendar actions used directly from an ASI:One conversation."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlencode


def parse_option_selection(text: str) -> int | None:
    match = re.search(
        r"\b(?:choose|select|pick|confirm|book|schedule|option)\s*(?:option\s*)?#?([1-3])\b",
        text.lower(),
    )
    return int(match.group(1)) if match else None


def google_calendar_template_url(option: dict) -> str:
    start = datetime.fromisoformat(option["start_iso"])
    end = datetime.fromisoformat(option["end_iso"])
    date_format = "%Y%m%dT%H%M%S"
    details = "Scheduled by BusyBrain. Why this time: " + "; ".join(
        option.get("reasons", [])
    )
    query = urlencode(
        {
            "action": "TEMPLATE",
            "text": option["title"],
            "dates": f"{start.strftime(date_format)}/{end.strftime(date_format)}",
            "details": details,
        }
    )
    return f"https://calendar.google.com/calendar/render?{query}"


def confirm_option(storage, sender: str, option: dict) -> dict:
    """Persist an auditable action receipt in the uAgent's durable storage."""
    receipt = {
        **option,
        "action_id": f"busybrain-{int(datetime.now(tz=timezone.utc).timestamp())}",
        "confirmed_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": "confirmed",
        "google_calendar_url": google_calendar_template_url(option),
    }
    key = f"confirmed_events:{sender}"
    events = storage.get(key) or []
    events.append(receipt)
    storage.set(key, events[-20:])
    return receipt
