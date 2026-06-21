import streamlit as st
import importlib
import sample_data
from agents import CalendarOrchestrator
from models import CalendarEvent, TaskType
import base64
from datetime import datetime, timedelta
from coordination import MeetingConstraints, parse_meeting_request

# Streamlit can retain an older imported module during a development hot reload.
# Reloading keeps helper additions in sync without requiring a server restart.
sample_data = importlib.reload(sample_data)
build_friend_schedules = sample_data.build_friend_schedules
build_sample_inputs = sample_data.build_sample_inputs

st.set_page_config(page_title="Busy Brain", page_icon="🧠", layout="wide")


def get_base64(path):
    with open(path, "rb") as img:
        return base64.b64encode(img.read()).decode()


sidebar_image = get_base64("images/jellycat.jpg")
launcher_image = get_base64("images/cat-plus-launcher.png")

st.markdown(
    f"""
<style>
.stApp {{
    background:
        radial-gradient(circle at top left, rgba(255,255,255,0.75), transparent 35%),
        linear-gradient(135deg, #dfeeff 0%, #f7e8ff 45%, #ffeef5 100%);
    color: #1f2450;
}}

.main .block-container {{
    padding-top: 2rem;
}}

h1, h2, h3 {{
    color: #2b245f;
}}

[data-testid="stSidebar"] {{
    background-image: url("data:image/jpg;base64,{sidebar_image}");
    background-size: cover;
    background-position: center center;
    background-repeat: no-repeat;
    border-left: 1px solid rgba(160,130,255,0.25);
    left: auto;
    right: 0;
}}

[data-testid="stSidebar"] > div {{
    background: transparent;
    min-height: 100vh;
}}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] > h1,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] > h2,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] > h3,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
    text-shadow: 0 1px 8px rgba(255,255,255,0.95);
}}

[data-testid="stSidebar"] [data-testid="stPopover"] button {{
    width: 104px;
    height: 104px;
    min-height: 104px;
    padding: 0;
    border: 3px solid rgba(255,255,255,0.9) !important;
    border-radius: 50% !important;
    background-color: transparent !important;
    background-image: url("data:image/png;base64,{launcher_image}") !important;
    background-size: cover !important;
    background-position: center !important;
    background-repeat: no-repeat !important;
    box-shadow: 0 10px 24px rgba(76, 29, 149, 0.32);
    transition: transform 160ms ease, box-shadow 160ms ease;
}}

[data-testid="stSidebar"] [data-testid="stPopover"] button:hover {{
    border-color: white;
    transform: scale(1.06);
    box-shadow: 0 14px 30px rgba(76, 29, 149, 0.4);
}}

[data-testid="stSidebar"] [data-testid="stPopover"] button p {{
    font-size: 0 !important;
    color: transparent !important;
}}

[data-testid="stPopoverBody"] .stButton > button {{
    width: 52px;
    height: 52px;
    min-height: 52px;
    padding: 0;
    border-radius: 50%;
    font-size: 1.25rem;
}}

[data-testid="stPopoverBody"] [data-testid="stCaptionContainer"] {{
    text-align: center;
    line-height: 1.15;
}}

.stButton > button {{
    background: linear-gradient(135deg, #8b5cf6, #a78bfa);
    color: white;
    border: none;
    border-radius: 16px;
    padding: 0.7rem 1.4rem;
    font-weight: 700;
    box-shadow: 0 8px 18px rgba(139,92,246,0.25);
}}

.stButton > button:hover {{
    background: linear-gradient(135deg, #7c3aed, #9333ea);
    color: white;
}}

input, textarea {{
    border-radius: 14px !important;
}}

.event-card {{
    padding: 16px;
    border-radius: 18px;
    margin-bottom: 14px;
    box-shadow: 0 8px 25px rgba(123, 92, 246, 0.12);
    border: 1px solid rgba(255,255,255,0.7);
}}

.class-card {{
    background: #ead7ff;
    border-left: 7px solid #a78bfa;
}}

.study-card {{
    background: #dbeafe;
    border-left: 7px solid #60a5fa;
}}

.appointment-card {{
    background: #ffe4e6;
    border-left: 7px solid #fb7185;
}}

.workout-card {{
    background: #dcfce7;
    border-left: 7px solid #86efac;
}}

.meal-card {{
    background: #ffedd5;
    border-left: 7px solid #fdba74;
}}

.personal-card {{
    background: #f3e8ff;
    border-left: 7px solid #c084fc;
}}

.travel-card {{
    background: #f1f5f9;
    border-left: 7px solid #94a3b8;
}}

.hero-card {{
    background: rgba(255,255,255,0.72);
    padding: 24px;
    border-radius: 26px;
    margin-bottom: 22px;
    box-shadow: 0 12px 35px rgba(123, 92, 246, 0.12);
    border: 1px solid rgba(255,255,255,0.7);
}}

.candidate-card {{
    background: rgba(255,255,255,0.82);
    padding: 16px;
    border-radius: 18px;
    margin: 12px 0;
    border: 1px solid rgba(139,92,246,0.22);
    box-shadow: 0 8px 22px rgba(76,29,149,0.10);
}}

.score-pill {{
    display: inline-block;
    background: #ede9fe;
    color: #5b21b6;
    border-radius: 999px;
    padding: 4px 10px;
    font-weight: 700;
}}

.legend-dot {{
    height: 14px;
    width: 14px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
}}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero-card">
    <h1>🧠 Busy Brain</h1>
    <h3>The calendar that schedules the invisible work too 💜</h3>
    <p>You do not have to do it all today. Just what matters most.</p>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("🧠 Busy Brain")
    st.caption("Cute, gentle planning for busy brains.")

    if "sidebar_action" not in st.session_state:
        st.session_state.sidebar_action = None
    if "class_name" not in st.session_state:
        st.session_state.class_name = "Computer Science"
    if "weekly_study_hours" not in st.session_state:
        st.session_state.weekly_study_hours = 10
    if "saved_meetings" not in st.session_state:
        st.session_state.saved_meetings = []
    if "saved_tasks" not in st.session_state:
        st.session_state.saved_tasks = []
    if "meeting_candidates" not in st.session_state:
        st.session_state.meeting_candidates = []
    if "selected_meeting" not in st.session_state:
        st.session_state.selected_meeting = None

    with st.popover("🐱"):
        st.caption("What would you like to add?")
        class_col, meeting_col, task_col = st.columns(3)
        with class_col:
            if st.button("🎓", help="Add class"):
                st.session_state.sidebar_action = "class"
            st.caption("Add class")
        with meeting_col:
            if st.button("☕", help="Create meeting with friend"):
                st.session_state.sidebar_action = "meeting"
            st.caption("Meet friend")
        with task_col:
            if st.button("✓", help="Add task"):
                st.session_state.sidebar_action = "task"
            st.caption("Add task")

    class_name = st.session_state.class_name
    weekly_study_hours = st.session_state.weekly_study_hours
    focus_rhythm = "40/10"
    energy = "Morning"

    if st.session_state.sidebar_action == "class":
        st.header("Add a Class")
        class_name = st.text_input("Class name", key="class_name")
        weekly_study_hours = st.number_input(
            "Weekly study hours",
            min_value=1,
            max_value=40,
            key="weekly_study_hours",
        )
        focus_rhythm = st.radio(
            "Focus rhythm",
            ["30/10", "40/10", "60/10"],
            horizontal=True,
        )
        energy = st.radio(
            "Highest energy",
            ["Morning", "Afternoon", "Evening"],
        )

    elif st.session_state.sidebar_action == "meeting":
        st.header("Energy-aware meetup")
        friend_schedules = build_friend_schedules()
        with st.form("friend_meeting_form"):
            meeting_request = st.text_area(
                "Ask naturally",
                value="Find me 60 minutes with Maya this week, not right after class.",
                help="BusyBrain extracts the friend, duration, preferred time, and recovery constraints.",
            )
            friend_name = st.selectbox("Which friend?", list(friend_schedules))
            search_start = st.date_input("Look for time starting")
            search_days = st.slider("Search the next … days", 1, 7, 5)
            meeting_minutes = st.select_slider(
                "How long?", [30, 45, 60, 90, 120], value=60,
                format_func=lambda minutes: f"{minutes} minutes",
            )
            meeting_place = st.text_input("Place (optional)")
            find_meeting = st.form_submit_button("Find our best time", use_container_width=True)

        if find_meeting:
            parsed = parse_meeting_request(meeting_request, friend_schedules)
            friend_name = parsed.friend_name or friend_name
            parsed.duration_minutes = parsed.duration_minutes or meeting_minutes
            profile, classes, fixed_events, tasks, week_start = build_sample_inputs()
            planner = CalendarOrchestrator()
            current_plan = planner.build_week_plan(
                profile=profile,
                classes=classes,
                fixed_events=fixed_events,
                tasks=tasks,
                week_start=week_start,
            )
            now = datetime.now()
            search_end = search_start + timedelta(days=search_days - 1)
            if search_start <= now.date() <= search_end and now.time() > profile.day_start:
                current_plan.events.append(
                    CalendarEvent(
                        "Time already passed",
                        datetime.combine(now.date(), profile.day_start),
                        now,
                        TaskType.PERSONAL,
                    )
                )
            existing_meetings = [
                event for event in st.session_state.saved_meetings
                if hasattr(event, "start")
            ]
            candidates = planner.social_agent.rank_friend_meetings(
                friend_a_events=current_plan.events + existing_meetings,
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
            if candidates:
                st.session_state.meeting_candidates = candidates
                st.session_state.meeting_friend = friend_name
                st.session_state.meeting_place = meeting_place
                st.session_state.meeting_request = meeting_request
            else:
                st.warning(
                    f"No shared {parsed.duration_minutes}-minute opening in those {search_days} days. "
                    "Try a shorter meeting or a wider search."
                )

        if st.session_state.meeting_candidates:
            st.subheader("Best shared windows")
            st.caption("Ranked using availability, calendar load, and transition time—not guessed emotions.")
            for index, candidate in enumerate(st.session_state.meeting_candidates):
                reasons = "<br>".join(f"✓ {reason}" for reason in candidate.reasons)
                tradeoffs = "<br>".join(f"△ {item}" for item in candidate.tradeoffs)
                st.markdown(
                    f"""
                    <div class="candidate-card">
                      <span class="score-pill">Fit score {candidate.score}</span>
                      <h3>{candidate.start.strftime('%A, %b %d · %I:%M %p')}–{candidate.end.strftime('%I:%M %p')}</h3>
                      <b>Why this time?</b><br>{reasons}
                      {f'<br><b>Tradeoffs</b><br>{tradeoffs}' if tradeoffs else ''}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Choose this time", key=f"choose_meeting_{index}", use_container_width=True):
                    meeting = CalendarEvent(
                        title=f"Meet with {st.session_state.meeting_friend}",
                        start=candidate.start,
                        end=candidate.end,
                        task_type=TaskType.SOCIAL,
                        location=st.session_state.meeting_place or None,
                        notes="Why this time: " + "; ".join(candidate.reasons),
                        flexible=True,
                    )
                    st.session_state.saved_meetings.append(meeting)
                    st.session_state.selected_meeting = meeting
                    st.session_state.meeting_candidates = []
                    st.rerun()

        if st.session_state.selected_meeting:
            meeting = st.session_state.selected_meeting
            st.success(
                f"Chosen: {meeting.start.strftime('%A, %b %d at %I:%M %p')}–"
                f"{meeting.end.strftime('%I:%M %p')} ✨"
            )
            with st.expander("🎬 Pika invite handoff"):
                consent = st.checkbox(
                    "I have permission to use the person's photo for this invitation."
                )
                if st.button("Prepare personalized invite", disabled=not consent):
                    friend = st.session_state.meeting_friend
                    invite_prompt = (
                        f"Create a playful 8-second vertical meetup invitation for {friend}. "
                        f"On-screen text: '{meeting.start.strftime('%A at %I:%M %p')} — our calm window'. "
                        "Warm Y2K pastel style, gentle calendar motifs, upbeat motion, preserve the "
                        "consented person's facial identity, no additional people."
                    )
                    st.session_state.pika_invite_prompt = invite_prompt
                if st.session_state.get("pika_invite_prompt"):
                    st.code(st.session_state.pika_invite_prompt)
                    st.caption("Ready to send to the hackathon Pika MCP with the consented reference photo.")

        if st.session_state.saved_meetings:
            st.caption("Scheduled friend time")
            for meeting in st.session_state.saved_meetings[-3:]:
                if hasattr(meeting, "start"):
                    st.markdown(
                        f"**{meeting.title}**  \n"
                        f"{meeting.start.strftime('%a, %b %d · %I:%M %p')}"
                    )

    elif st.session_state.sidebar_action == "task":
        st.header("Add a Task")
        with st.form("task_form", clear_on_submit=True):
            task_name = st.text_input("What needs doing?")
            task_date = st.date_input("Due date")
            task_priority = st.select_slider(
                "Priority", ["Low", "Medium", "High"], value="Medium"
            )
            if st.form_submit_button("Add task", use_container_width=True):
                st.session_state.saved_tasks.append(
                    (task_name or "Untitled task", task_date, task_priority)
                )
                st.success("Task added ✨")

    generate = st.button("✨ Generate Schedule")

    st.markdown("---")
    st.subheader("Task Color Legend")
    st.markdown('<span class="legend-dot" style="background:#a78bfa;"></span> Classes', unsafe_allow_html=True)
    st.markdown('<span class="legend-dot" style="background:#60a5fa;"></span> Study', unsafe_allow_html=True)
    st.markdown('<span class="legend-dot" style="background:#fb7185;"></span> Appointments', unsafe_allow_html=True)
    st.markdown('<span class="legend-dot" style="background:#86efac;"></span> Workout', unsafe_allow_html=True)
    st.markdown('<span class="legend-dot" style="background:#fdba74;"></span> Meals', unsafe_allow_html=True)
    st.markdown('<span class="legend-dot" style="background:#c084fc;"></span> Personal', unsafe_allow_html=True)
    st.markdown('<span class="legend-dot" style="background:#94a3b8;"></span> Travel', unsafe_allow_html=True)


def get_card_class(event):
    event_type = event.task_type.value if hasattr(event.task_type, "value") else str(event.task_type)

    if "Drive" in event.title:
        return "travel-card"
    if event_type == "class":
        return "class-card"
    if event_type == "study":
        return "study-card"
    if event_type == "appointment":
        return "appointment-card"
    if event_type == "workout":
        return "workout-card"
    if event_type == "meal":
        return "meal-card"
    if event_type == "personal":
        return "personal-card"

    return "personal-card"


if generate:
    profile, classes, fixed_events, tasks, week_start = build_sample_inputs()

    classes[0].name = class_name
    classes[0].weekly_study_hours = weekly_study_hours

    if hasattr(classes[0], "class_name"):
        classes[0].class_name = class_name

    for meeting in classes[0].meetings:
        meeting.title = f"{class_name} Class"

    for event in fixed_events:
        if event.title == "CS Class":
            event.title = f"{class_name} Class"

    orchestrator = CalendarOrchestrator()
    result = orchestrator.build_week_plan(
        profile=profile,
        classes=classes,
        fixed_events=fixed_events,
        tasks=tasks,
        week_start=week_start,
    )
    result.events.extend(
        event for event in st.session_state.saved_meetings
        if hasattr(event, "start")
    )
    result.events.sort(key=lambda event: event.start)

    for event in result.events:
        if "Computer Science" in event.title:
            event.title = event.title.replace("Computer Science", class_name)

    st.success("Schedule generated! ✨")

    days = {}
    for event in result.events:
        date_key = event.start.date()
        days.setdefault(date_key, []).append(event)

    sorted_dates = sorted(days.keys())
    tabs = st.tabs([day.strftime("%A, %b %d") for day in sorted_dates])

    for tab, date_key in zip(tabs, sorted_dates):
        with tab:
            st.subheader(date_key.strftime("%A, %B %d"))

            for event in sorted(days[date_key], key=lambda e: e.start):
                card_class = get_card_class(event)
                event_type = event.task_type.value if hasattr(event.task_type, "value") else str(event.task_type)

                location_html = f"<p><b>Location:</b> {event.location}</p>" if event.location else ""
                notes_html = f"<p><i>{event.notes}</i></p>" if event.notes else ""

                st.markdown(
                    f"""
                    <div class="event-card {card_class}">
                        <h3>{event.title}</h3>
                        <p><b>Time:</b> {event.start.strftime('%I:%M %p')} - {event.end.strftime('%I:%M %p')}</p>
                        <p><b>Type:</b> {event_type}</p>
                        {location_html}
                        {notes_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    if result.messages:
        st.markdown('<div class="hero-card"><h2>⭐ Planner Messages</h2>', unsafe_allow_html=True)

        for message in result.messages:
            st.write("•", message)

        st.markdown("</div>", unsafe_allow_html=True)

    if result.unscheduled:
        st.header("Needs Manual Review")
        for item in result.unscheduled:
            st.warning(item)

else:
    st.info("Click **Generate Schedule** to test Busy Brain.")
