"""BusyBrain Streamlit product demo.

The interface mirrors the soft, focused design prototype while keeping the real
deterministic scheduling and coordination logic behind every interaction.
"""

from __future__ import annotations

import base64
import html
import importlib
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

import sample_data
from agents import CalendarOrchestrator
from coordination import MeetingConstraints, parse_meeting_request
from models import CalendarEvent, TaskType


sample_data = importlib.reload(sample_data)
build_friend_schedules = sample_data.build_friend_schedules
build_sample_inputs = sample_data.build_sample_inputs

ROOT = Path(__file__).parent
st.set_page_config(page_title="Busy Brain", page_icon="🐈‍⬛", layout="wide")


def image_data(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{encoded}"


ocean_background = image_data(ROOT / "images" / "jellycat.jpg")
cat_mark = image_data(ROOT / "images" / "busy-brain-logo.jpg")


def initialize_state() -> None:
    defaults = {
        "class_name": "Computer Science",
        "weekly_study_hours": 10,
        "saved_meetings": [],
        "meeting_candidates": [],
        "selected_meeting": None,
        "generated_plan": None,
        "added_classes": [],
        "pika_invite_prompt": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_state()

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800&display=swap');

:root {{
  --ink:#2d2b52; --muted:#75718f; --purple:#8b7cf6;
  --line:#ece8f7; --panel:rgba(255,255,255,.93);
}}
html, body, [class*="css"] {{ font-family:'Nunito',system-ui,sans-serif; }}
.stApp {{
  color:var(--ink);
  background:linear-gradient(rgba(245,243,251,.72),rgba(244,241,252,.82)),
             url('{ocean_background}') center/cover fixed;
}}
header[data-testid="stHeader"] {{ background:transparent; }}
.main .block-container {{ max-width:830px; padding:3rem 2.2rem 6rem; }}
h1,h2,h3,p {{ color:var(--ink); }}
h1 {{ letter-spacing:-.035em; font-weight:800 !important; }}

[data-testid="stSidebar"] {{
  width:264px !important; min-width:264px !important;
  background:linear-gradient(rgba(255,255,255,.72),rgba(255,255,255,.88)),
             url('{ocean_background}') center/cover;
  border-right:1px solid #e7e0f2;
}}
[data-testid="stSidebar"] > div:first-child {{ padding:1rem .75rem; }}
.brand-card {{
  height:124px; border-radius:17px; overflow:hidden; position:relative;
  background:url('{cat_mark}') center 46%/cover;
  box-shadow:0 5px 18px rgba(90,76,165,.24); margin:0 .2rem .5rem;
}}
.brand-card:after {{ content:''; position:absolute; inset:0;
  background:linear-gradient(180deg,rgba(45,43,82,.52),transparent 52%); }}
.brand-title {{ position:absolute; z-index:2; top:10px; width:100%; text-align:center;
  color:white; font-size:1.28rem; font-weight:800; text-shadow:0 1px 7px #2d2b52; }}
.brand-subtitle {{ text-align:center; color:#5f5b7c; font-size:.76rem;
  font-weight:700; margin:.6rem 0 1rem; }}

[data-testid="stSidebar"] [role="radiogroup"] {{
  background:rgba(255,255,255,.58); border:1px solid rgba(255,255,255,.8);
  border-radius:15px; padding:.42rem; gap:.2rem;
  box-shadow:0 2px 9px rgba(90,76,165,.10);
}}
[data-testid="stSidebar"] [role="radiogroup"] label {{
  padding:.55rem .62rem; border-radius:11px; font-weight:700;
}}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
  background:#ede9fe; color:#6d56e8;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] > label {{ display:none; }}
.legend {{ margin-top:2rem; padding:.8rem .85rem; background:rgba(255,255,255,.62);
  border:1px solid rgba(255,255,255,.8); border-radius:15px; }}
.legend-title {{ color:#9a96b8; font-size:.69rem; text-transform:uppercase;
  letter-spacing:.08em; font-weight:800; margin-bottom:.55rem; }}
.legend-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:.42rem .7rem; }}
.legend-item {{ color:#5a5775; font-size:.76rem; white-space:nowrap; }}
.dot {{ width:10px; height:10px; display:inline-block; border-radius:50%; margin-right:6px; }}

.page-kicker {{ color:var(--muted); font-size:.95rem; line-height:1.5; margin:-.55rem 0 1.7rem; }}
.surface {{ background:var(--panel); border:1px solid var(--line); border-radius:19px;
  padding:1.55rem; box-shadow:0 2px 8px rgba(80,70,140,.06); margin-bottom:1.25rem; }}
.section-copy {{ color:#85819d; font-size:.86rem; margin-top:-.55rem; margin-bottom:1rem; }}
.candidate-card,.event-card {{ background:var(--panel); border:1px solid var(--line);
  border-radius:16px; padding:1.18rem 1.3rem; box-shadow:0 2px 8px rgba(80,70,140,.055);
  margin:.8rem 0 .45rem; }}
.candidate-top {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; }}
.candidate-time {{ font-size:1.03rem; font-weight:800; }}
.score-pill {{ color:#6d56e8; background:#ede9fe; border-radius:999px; padding:.28rem .68rem;
  font-size:.76rem; font-weight:800; white-space:nowrap; }}
.reason {{ color:#5a5775; font-size:.84rem; margin:.38rem 0; }}
.check {{ color:#21a16f; font-weight:800; margin-right:.45rem; }}
.tradeoff {{ color:#9b6b27; font-size:.8rem; margin-top:.45rem; }}
.chosen-card {{ background:#e3f9f0; border:1px solid #bdecd6; border-radius:14px;
  padding:.82rem 1rem; color:#1f8d64; font-weight:800; margin:1rem 0; }}
.calendar-card {{ display:flex; gap:.9rem; align-items:center; }}
.calendar-avatar {{ width:58px; height:58px; flex:none; border-radius:50%;
  background:url('{cat_mark}') center/cover; border:2px solid #ede9fe; }}
.eyebrow {{ color:#9a96b8; text-transform:uppercase; letter-spacing:.07em; font-size:.68rem; font-weight:800; }}
.event-card {{ display:grid; grid-template-columns:5px 1fr; gap:.85rem; }}
.event-bar {{ border-radius:8px; }}
.event-head {{ display:flex; justify-content:space-between; gap:1rem; align-items:center; }}
.event-title {{ font-weight:800; font-size:.98rem; }}
.event-type {{ border-radius:999px; padding:.2rem .55rem; font-size:.68rem; font-weight:800; }}
.event-time {{ color:#6b6889; font-size:.82rem; font-weight:700; margin-top:.25rem; }}
.event-note {{ color:#8a86a8; font-size:.79rem; margin-top:.3rem; }}

.stButton > button, [data-testid="stFormSubmitButton"] button {{
  background:linear-gradient(135deg,#9d8df8,#8b7cf6); color:white; border:0;
  border-radius:13px; font-weight:800; min-height:2.8rem;
  box-shadow:0 4px 14px rgba(139,124,246,.28);
}}
.stButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {{
  color:white; background:linear-gradient(135deg,#8b7cf6,#7a68ef); border:0;
}}
[data-baseweb="input"] > div,[data-baseweb="textarea"] > div,
[data-baseweb="select"] > div {{ border-radius:12px !important; border-color:#e4e0f2 !important; background:#fbfaff; }}
[data-testid="stForm"] {{ background:var(--panel); border:1px solid var(--line);
  border-radius:19px; padding:1.45rem; box-shadow:0 2px 8px rgba(80,70,140,.06); }}
[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap:.35rem; overflow-x:auto; }}
[data-testid="stTabs"] button[role="tab"] {{ border-radius:12px; background:white; border:1px solid var(--line); padding:.55rem .8rem; }}
[data-testid="stTabs"] button[aria-selected="true"] {{ background:#8b7cf6; color:white; }}
@media (max-width:720px) {{
  [data-testid="stSidebar"] {{ width:240px !important; min-width:240px !important; }}
  .main .block-container {{ padding:2rem 1rem 5rem; }}
  .candidate-top,.event-head {{ align-items:flex-start; flex-direction:column; gap:.35rem; }}
}}
</style>
""",
    unsafe_allow_html=True,
)


LEGEND = [
    ("Classes", "#a78bfa"), ("Study", "#60a5fa"),
    ("Appointments", "#fb7185"), ("Workout", "#34d399"),
    ("Meals", "#fbbf24"), ("Personal", "#818cf8"),
    ("Travel", "#94a3b8"),
]

with st.sidebar:
    st.markdown(
        '<div class="brand-card"><div class="brand-title">Busy Brain</div></div>'
        '<div class="brand-subtitle">Gentle planning for busy brains</div>',
        unsafe_allow_html=True,
    )
    view = st.radio(
        "Navigation",
        ["🔎  Find a time", "🗓️  My Schedule", "📚  Classes & Energy"],
        label_visibility="collapsed",
    )
    legend = "".join(
        f'<div class="legend-item"><span class="dot" style="background:{color}"></span>{label}</div>'
        for label, color in LEGEND
    )
    st.markdown(
        f'<div class="legend"><div class="legend-title">Task colors</div>'
        f'<div class="legend-grid">{legend}</div></div>',
        unsafe_allow_html=True,
    )


def build_plan():
    profile, classes, fixed_events, tasks, week_start = build_sample_inputs()
    classes[0].name = st.session_state.class_name
    classes[0].weekly_study_hours = st.session_state.weekly_study_hours
    for meeting in classes[0].meetings:
        meeting.title = f"{st.session_state.class_name} Class"
    for event in fixed_events:
        if event.title == "CS Class":
            event.title = f"{st.session_state.class_name} Class"
    result = CalendarOrchestrator().build_week_plan(
        profile=profile,
        classes=classes,
        fixed_events=fixed_events,
        tasks=tasks,
        week_start=week_start,
    )
    result.events.extend(st.session_state.saved_meetings)
    result.events.sort(key=lambda event: event.start)
    st.session_state.generated_plan = result
    return result


def show_find_time() -> None:
    st.title("Find a time to meet")
    st.markdown(
        '<div class="page-kicker">Energy-aware scheduling — ranked by real availability '
        'and calendar load, not guessed moods.</div>', unsafe_allow_html=True,
    )

    friend_schedules = build_friend_schedules()
    with st.form("friend_meeting_form"):
        meeting_request = st.text_area(
            "Ask in your own words",
            value="Find me 60 minutes with Maya this week, not right after class.",
        )
        left, right = st.columns(2)
        friend_name = left.selectbox("Which friend?", list(friend_schedules))
        search_start = right.date_input("Start looking from")
        left, right = st.columns(2)
        search_days = left.slider("Search the next", 1, 14, 5, format="%d days")
        meeting_minutes = right.select_slider(
            "How long", [30, 45, 60, 90, 120], value=60,
            format_func=lambda minutes: f"{minutes} min",
        )
        meeting_place = st.text_input("Place (optional)", placeholder="Library café, video call…")
        submitted = st.form_submit_button("Find our best time", use_container_width=True)

    if submitted:
        parsed = parse_meeting_request(meeting_request, friend_schedules)
        friend_name = parsed.friend_name or friend_name
        parsed.duration_minutes = parsed.duration_minutes or meeting_minutes
        profile, classes, fixed_events, tasks, week_start = build_sample_inputs()
        current_plan = CalendarOrchestrator().build_week_plan(
            profile=profile, classes=classes, fixed_events=fixed_events,
            tasks=tasks, week_start=week_start,
        )
        now = datetime.now()
        search_end = search_start + timedelta(days=search_days - 1)
        if search_start <= now.date() <= search_end and now.time() > profile.day_start:
            current_plan.events.append(CalendarEvent(
                "Time already passed", datetime.combine(now.date(), profile.day_start),
                now, TaskType.PERSONAL,
            ))
        candidates = CalendarOrchestrator().social_agent.rank_friend_meetings(
            friend_a_events=current_plan.events + st.session_state.saved_meetings,
            friend_b_events=friend_schedules[friend_name],
            profile=profile,
            start_day=search_start,
            end_day=search_end,
            constraints=MeetingConstraints(
                friend_name=friend_name,
                duration_minutes=parsed.duration_minutes,
                preferred_period=parsed.preferred_period,
                avoid_after_demanding=parsed.avoid_after_demanding,
            ),
            limit=3,
        )
        st.session_state.meeting_candidates = candidates
        st.session_state.meeting_friend = friend_name
        st.session_state.meeting_place = meeting_place
        st.session_state.selected_meeting = None
        if not candidates:
            st.warning("No shared opening was found. Try a shorter meeting or wider search.")

    if st.session_state.meeting_candidates:
        st.subheader("Best shared windows")
        st.markdown(
            '<div class="section-copy">Ranked by availability, calendar load, and transition time.</div>',
            unsafe_allow_html=True,
        )
        for index, candidate in enumerate(st.session_state.meeting_candidates):
            reasons = "".join(
                f'<div class="reason"><span class="check">✓</span>{html.escape(reason)}</div>'
                for reason in candidate.reasons
            )
            tradeoffs = "".join(
                f'<div class="tradeoff">△ {html.escape(item)}</div>'
                for item in candidate.tradeoffs
            )
            st.markdown(
                f'<div class="candidate-card"><div class="candidate-top">'
                f'<div class="candidate-time">{candidate.start.strftime("%A, %b %d · %I:%M %p")}–'
                f'{candidate.end.strftime("%I:%M %p")}</div>'
                f'<div class="score-pill">Fit {candidate.score}</div></div>'
                f'<div style="margin-top:.8rem;font-weight:800">Why this time?</div>{reasons}{tradeoffs}</div>',
                unsafe_allow_html=True,
            )
            if st.button("Choose this time", key=f"choose_{index}", use_container_width=True):
                meeting = CalendarEvent(
                    title=f"Meet with {st.session_state.meeting_friend}",
                    start=candidate.start, end=candidate.end,
                    task_type=TaskType.SOCIAL,
                    location=st.session_state.meeting_place or None,
                    notes="Why this time: " + "; ".join(candidate.reasons),
                    flexible=True,
                )
                st.session_state.saved_meetings.append(meeting)
                st.session_state.selected_meeting = meeting
                st.session_state.meeting_candidates = []
                st.rerun()

    meeting = st.session_state.selected_meeting
    if meeting:
        when = (
            f"{meeting.start.strftime('%A, %b %d at %I:%M %p')}–"
            f"{meeting.end.strftime('%I:%M %p')}"
        )
        st.markdown(f'<div class="chosen-card">✓ Chosen: {when} ✨</div>', unsafe_allow_html=True)
        with st.expander("🎬 Create a video invite", expanded=True):
            st.caption("Prepare a personalized Pika handoff using the chosen time and place.")
            consent = st.checkbox("I have permission to use this person's photo for the invitation.")
            if st.button("Prepare personalized invite", disabled=not consent, use_container_width=True):
                friend = st.session_state.meeting_friend
                st.session_state.pika_invite_prompt = (
                    f"Create a playful 8-second vertical meetup invitation for {friend}. "
                    f"On-screen text: '{meeting.start.strftime('%A at %I:%M %p')} — our calm window'. "
                    "Warm Y2K pastel style, gentle calendar motifs, upbeat motion, preserve the "
                    "consented person's facial identity, no additional people."
                )
            if st.session_state.pika_invite_prompt:
                st.code(st.session_state.pika_invite_prompt)
        st.markdown(
            f'<div class="surface calendar-card"><div class="calendar-avatar"></div><div>'
            f'<div class="eyebrow">Scheduled friend time</div><div style="font-size:1.05rem;font-weight:800">'
            f'{html.escape(meeting.title)}</div><div style="color:#6b6889;font-size:.84rem;font-weight:700">'
            f'{when}</div></div></div>', unsafe_allow_html=True,
        )
        if st.button("✨ Generate Schedule", use_container_width=True):
            build_plan()
            st.info("Schedule generated. Open **My Schedule** in the sidebar.")


TYPE_STYLE = {
    "class": ("#a78bfa", "#f1ecfe"), "study": ("#60a5fa", "#e7f0ff"),
    "appointment": ("#fb7185", "#ffe9ee"), "workout": ("#34d399", "#e3f9f0"),
    "meal": ("#fbbf24", "#fff4dc"), "personal": ("#818cf8", "#eceefe"),
    "social": ("#818cf8", "#eceefe"), "travel": ("#94a3b8", "#eef1f5"),
}


def event_html(event: CalendarEvent) -> str:
    event_type = event.task_type.value if hasattr(event.task_type, "value") else str(event.task_type)
    if "Drive" in event.title:
        event_type = "travel"
    color, tint = TYPE_STYLE.get(event_type, TYPE_STYLE["personal"])
    note = html.escape(event.notes) if event.notes else "A protected block in your plan."
    return (
        f'<div class="event-card"><div class="event-bar" style="background:{color}"></div><div>'
        f'<div class="event-head"><div class="event-title">{html.escape(event.title)}</div>'
        f'<div class="event-type" style="color:{color};background:{tint}">{html.escape(event_type)}</div></div>'
        f'<div class="event-time">{event.start.strftime("%I:%M %p")} – {event.end.strftime("%I:%M %p")}</div>'
        f'<div class="event-note">{note}</div></div></div>'
    )


def show_schedule() -> None:
    left, right = st.columns([3, 1])
    left.title("My schedule")
    left.markdown(
        '<div class="page-kicker">You don\'t have to do it all today — just what matters most.</div>',
        unsafe_allow_html=True,
    )
    if right.button("✨ Regenerate", use_container_width=True) or st.session_state.generated_plan is None:
        build_plan()
    result = st.session_state.generated_plan
    days = {}
    for event in result.events:
        days.setdefault(event.start.date(), []).append(event)
    dates = sorted(days)
    tabs = st.tabs([day.strftime("%a · %d") for day in dates])
    for tab, day in zip(tabs, dates):
        with tab:
            st.subheader(day.strftime("%A, %B %d"))
            for event in sorted(days[day], key=lambda item: item.start):
                st.markdown(event_html(event), unsafe_allow_html=True)
    if result.messages:
        with st.expander("Planner notes"):
            for message in result.messages:
                st.write("•", message)


def show_classes() -> None:
    st.title("Classes & energy")
    st.markdown(
        '<div class="page-kicker">Tell Busy Brain how you work. We’ll plan study blocks '
        'around your real energy.</div>', unsafe_allow_html=True,
    )
    with st.form("class_form", clear_on_submit=False):
        left, right = st.columns(2)
        class_name = left.text_input("Class name", value=st.session_state.class_name)
        hours = right.number_input("Weekly study hours", 1, 40, st.session_state.weekly_study_hours)
        st.markdown("**Focus rhythm**")
        rhythm = st.radio("Focus rhythm", ["30/10", "40/10", "60/10"], horizontal=True, label_visibility="collapsed")
        st.markdown("**When is your energy highest?**")
        energy = st.radio(
            "Energy", ["🌅 Morning", "☀️ Afternoon", "🌙 Evening"],
            horizontal=True, label_visibility="collapsed",
        )
        add_class = st.form_submit_button("✨ Add class & plan study time", use_container_width=True)
    if add_class:
        st.session_state.class_name = class_name.strip() or "Untitled class"
        st.session_state.weekly_study_hours = hours
        detail = f"{hours}h/week · {rhythm} rhythm · {energy.split()[-1].lower()} energy"
        st.session_state.added_classes.append((st.session_state.class_name, detail))
        st.session_state.generated_plan = None
        st.success("Class added to your planning profile.")
    if st.session_state.added_classes:
        st.subheader("Your classes")
        for name, detail in st.session_state.added_classes:
            st.markdown(
                f'<div class="surface" style="padding:1rem"><div style="font-weight:800">'
                f'🟣 {html.escape(name)}</div><div class="event-note">{html.escape(detail)}</div></div>',
                unsafe_allow_html=True,
            )


if view.startswith("🔎"):
    show_find_time()
elif view.startswith("🗓️"):
    show_schedule()
else:
    show_classes()
