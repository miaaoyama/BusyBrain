"""Real venue lookup for friend meetups, powered by Browserbase.

Hybrid strategy:
  1. search.web() finds candidate venues for the activity/location.
  2. fetch_api.create() tries the cheap, fast path first for each candidate.
  3. If fetch's result looks like a bot-checkpoint/JS-required page, escalate
     to a real Stagehand browser session for that one candidate, which can
     render JavaScript and get past simple bot walls.

This satisfies the Browserbase hackathon requirement via search + fetch +
Stagehand (three of the five listed primitives), and the fallback gives a
genuine reliability story: try cheap, escalate only when needed.

Requires BROWSERBASE_API_KEY in the environment (.env). Stagehand sessions
route model calls through Browserbase's Model Gateway using that same key —
no separate OpenAI/Anthropic key needed (if your installed SDK version
requires model_api_key explicitly, see the note in fetch_venue_snippet_via_stagehand).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional

from browserbase import Browserbase

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class VenueResult:
    name: str
    url: str
    snippet: str  # short excerpt from the fetched/rendered page
    source: str = "fetch"  # "fetch", "stagehand", or "search-only" — for transparency in the UI/demo


def _client() -> Browserbase:
    api_key = os.getenv("BROWSERBASE_API_KEY", "")
    if not api_key:
        raise RuntimeError("BROWSERBASE_API_KEY is missing. Add it to .env.")
    return Browserbase(api_key=api_key)


def search_venues(query: str, num_results: int = 5) -> List[dict]:
    """Real web search for candidate venues. Returns raw result dicts
    (title, url) — callers should fetch a candidate's page for more detail
    before presenting it, since search results alone don't include hours.
    """
    bb = _client()
    response = bb.search.web(query=query, num_results=num_results)
    return [{"title": r.title, "url": r.url} for r in response.results]


def fetch_venue_snippet(url: str, max_chars: int = 600) -> str:
    """Fetches a venue's page and returns a short markdown snippet.

    Some sites (heavy JS apps, aggressive bot detection) return blank or
    checkpoint/CAPTCHA content via simple fetch — this is a known fetch vs.
    full-browser tradeoff, not a bug. Detect that case and return "" so
    callers can escalate to Stagehand or fall back to search-result info.
    """
    bb = _client()
    result = bb.fetch_api.create(url=url, format="markdown")
    content = getattr(result, "content", None) or getattr(result, "text", "") or ""
    content = re.sub(r"\s+", " ", content).strip()

    if not content or _looks_blocked(content):
        return ""

    return content[:max_chars]


def fetch_venue_snippet_via_stagehand(url: str, max_chars: int = 600) -> str:
    """Escalation path: spins up a real Browserbase browser session via
    Stagehand and extracts page content with JS fully rendered. Slower and
    costs session time, so only call this after fetch_api has been tried
    and looked blocked.

    Stagehand should route model calls through Browserbase's Model Gateway
    using just BROWSERBASE_API_KEY. If your installed stagehand-py version
    raises a "model_api_key is required" error despite that, set
    MODEL_API_KEY in .env to any supported provider key (OpenAI/Anthropic/
    Gemini) as a workaround — this is a known SDK quirk, not a sign Model
    Gateway isn't working.
    """
    from stagehand import Stagehand

    api_key = os.getenv("BROWSERBASE_API_KEY", "")
    if not api_key:
        raise RuntimeError("BROWSERBASE_API_KEY is missing. Add it to .env.")

    model_api_key = os.getenv("MODEL_API_KEY")  # optional fallback, see docstring

    client_kwargs = {"browserbase_api_key": api_key}
    if model_api_key:
        client_kwargs["model_api_key"] = model_api_key

    client = Stagehand(**client_kwargs)
    session = client.sessions.start(model_name="anthropic/claude-sonnet-4-6")
    session_id = session.data.session_id
    try:
        client.sessions.navigate(id=session_id, url=url)
        result = client.sessions.extract(
            id=session_id,
            instruction="Extract the venue's name, address, and hours of operation if visible on the page.",
        )
        content = str(getattr(result, "data", result))
        content = re.sub(r"\s+", " ", content).strip()
        return content[:max_chars]
    finally:
        client.sessions.end(id=session_id)


def _looks_blocked(content: str) -> bool:
    """Heuristic check for bot-checkpoint / JS-required / WAF-blocked pages
    that fetch couldn't actually read past. Not exhaustive — new sites will
    surface new phrasing over time — but covers the common patterns seen
    from Vercel, Cloudflare, and JS-required interstitials."""
    lowered = content.lower()
    blocked_markers = (
        "verifying your browser",
        "security checkpoint",
        "enable js",
        "enable javascript",
        "disable any ad blocker",
        "checking your browser",
        "are you a robot",
        "captcha",
        "you have been blocked",
        "cloudflare ray id",
        "security service",
        "please enable cookies",
        "access denied",
        "attention required",
        "please verify you are a human",
        "unusual traffic",
    )
    return any(marker in lowered for marker in blocked_markers)


def find_venue_for_meetup(
    activity_query: str,
    location_hint: Optional[str] = None,
    num_candidates: int = 3,
    use_stagehand_fallback: bool = True,
) -> Optional[VenueResult]:
    """Searches for a real venue matching the activity/location, fetching
    candidates in order. If the cheap fetch path is blocked on every
    candidate and use_stagehand_fallback is True, escalates to a real
    Stagehand browser session on the top candidate before giving up.

    Returns None only if search itself finds nothing.
    """
    query = activity_query if not location_hint else f"{activity_query} near {location_hint}"
    candidates = search_venues(query, num_results=num_candidates)
    if not candidates:
        return None

    for candidate in candidates:
        try:
            snippet = fetch_venue_snippet(candidate["url"])
        except Exception:
            snippet = ""
        if snippet:
            return VenueResult(name=candidate["title"], url=candidate["url"], snippet=snippet, source="fetch")

    # Every candidate was blocked via fetch — escalate to Stagehand on the
    # top candidate only, since a full browser session costs real time.
    if use_stagehand_fallback:
        top = candidates[0]
        try:
            snippet = fetch_venue_snippet_via_stagehand(top["url"])
            if snippet:
                return VenueResult(name=top["title"], url=top["url"], snippet=snippet, source="stagehand")
        except Exception:
            pass  # Stagehand itself failed — fall through to name-only result below

    # Everything failed — still return the top search result so the feature
    # degrades gracefully instead of failing the whole meetup flow.
    top = candidates[0]
    return VenueResult(name=top["title"], url=top["url"], snippet="", source="search-only")


if __name__ == "__main__":
    # Quick manual smoke test: python3 venue_lookup.py
    result = find_venue_for_meetup("quiet coffee shop for studying", "UCI Irvine")
    if result:
        print(f"Found ({result.source}): {result.name}\n{result.url}\n{result.snippet}")
    else:
        print("No venue found.")