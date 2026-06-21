import base64
import html
import importlib
import math
from datetime import date, datetime, timedelta

import streamlit as st

import sample_data
from agents import CalendarOrchestrator
from models import CalendarEvent, EnergyLevel, EnergyWindow, TaskType
from scheduler import find_best_slot


st.set_page_config(page_title="Busy Brain", page_icon="🧠", layout="wide")

# Streamlit may retain an older module during development hot reloads.
sample_data = importlib.reload(sample_data)
build_sample_inputs = sample_data.build_sample_inputs
build_friend_schedules = sample_data.build_friend_schedules


def data_uri(path: str, mime: str) -> str:
    with open(path, "rb") as file:
        return f"data:{mime};base64,{base64.b64encode(file.read()).decode()}"


CAT_BG = data_uri("images/cat-bg.jpg", "image/jpeg")
CAT_CIRCLE = data_uri("images/cat-circle.png", "image/png")
CAT_PLUS = data_uri("images/cat-plus-launcher-reference.png", "image/png")

COLORS = {
    "class": "#a78bfa",
    "study": "#60a5fa",
    "appointment": "#fb7185",
    "workout": "#34d399",
    "meal": "#fbbf24",
    "social": "#818cf8",
    "personal": "#818cf8",
    "travel": "#94a3b8",
}
TYPE_LABELS = {
    "class": "Class",
    "study": "Study",
    "appointment": "Appointment",
    "workout": "Workout",
    "meal": "Meal",
    "social": "Social",
    "personal": "Personal",
    "travel": "Travel",
}
LOADS = {
    "class": (2, "Medium focus"),
    "study": (3, "Heavy focus"),
    "appointment": (2, "Medium focus"),
    "workout": (2, "Medium focus"),
    "meal": (1, "Light focus"),
    "social": (1, "Light focus"),
    "personal": (1, "Light focus"),
    "travel": (1, "Light focus"),
}


def init_state() -> None:
    defaults = {
        "view": "Today's flow",
        "selected_day": date.today(),
        "energy_peak": "Morning",
        "class_name": "Computer Science",
        "weekly_study_hours": 10,
        "saved_meetings": [],
        "saved_tasks": [],
        "added_classes": [],
        "friend_results": [],
        "chosen_meeting": None,
        "invite_ready": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def energy_at(minute: float, peak: str | None = None) -> float:
    peak = peak or st.session_state.energy_peak

    def gaussian(center: float, width: float) -> float:
        return math.exp(-((minute - center) ** 2) / (2 * width**2))

    value = 0.2
    if peak == "Morning":
        value += 0.62 * gaussian(600, 115) + 0.30 * gaussian(980, 135)
    elif peak == "Afternoon":
        value += 0.64 * gaussian(860, 150) + 0.22 * gaussian(600, 100)
    else:
        value += 0.58 * gaussian(1160, 140) + 0.30 * gaussian(620, 120)
    value -= 0.20 * gaussian(790, 55)
    return max(0.08, min(1.0, value))


def curve_paths(width: int, top: int, baseline: int, peak: str | None = None):
    points = []
    for minute in range(420, 1261, 12):
        x = ((minute - 420) / 840) * width
        y = baseline - energy_at(minute, peak) * (baseline - top)
        points.append((x, y))
    line = " ".join(
        f"{'M' if index == 0 else 'L'}{x:.1f} {y:.1f}"
        for index, (x, y) in enumerate(points)
    )
    return line, f"{line} L{width} {baseline} L0 {baseline} Z"


def task_kind(event: CalendarEvent) -> str:
    if event.title.startswith("Drive"):
        return "travel"
    return event.task_type.value if hasattr(event.task_type, "value") else str(event.task_type)


def match_for(event: CalendarEvent):
    minute = (event.start.hour * 60 + event.start.minute + event.end.hour * 60 + event.end.minute) / 2
    level = energy_at(minute)
    load = LOADS.get(task_kind(event), (1, "Light focus"))[0]
    if load >= 3 and level < 0.5:
        return "⚠", "Energy dip", "#b4791a", "#fff3dc", "low"
    if load >= 2 and level < 0.38:
        return "⚠", "Low energy", "#b4791a", "#fff3dc", "low"
    if level >= 0.6:
        return "✓", "Peak match", "#1f9d6b", "#e6f7ef", "good"
    return "~", "Steady", "#6d56e8", "#efecfb", "ok"


def build_plan():
    profile, classes, fixed_events, tasks, week_start = build_sample_inputs()
    classes[0].class_name = st.session_state.class_name
    classes[0].weekly_study_hours = st.session_state.weekly_study_hours
    for meeting in classes[0].meetings:
        meeting.title = f"{st.session_state.class_name} Class"

    if st.session_state.energy_peak == "Afternoon":
        profile.energy_windows = [
            EnergyWindow(datetime.min.replace(hour=9).time(), datetime.min.replace(hour=11).time(), EnergyLevel.MEDIUM),
            EnergyWindow(datetime.min.replace(hour=13).time(), datetime.min.replace(hour=17).time(), EnergyLevel.HIGH),
        ]
    elif st.session_state.energy_peak == "Evening":
        profile.energy_windows = [
            EnergyWindow(datetime.min.replace(hour=10).time(), datetime.min.replace(hour=13).time(), EnergyLevel.MEDIUM),
            EnergyWindow(datetime.min.replace(hour=17).time(), datetime.min.replace(hour=21).time(), EnergyLevel.HIGH),
        ]

    result = CalendarOrchestrator().build_week_plan(profile, classes, fixed_events, tasks, week_start)
    result.events.extend(
        meeting for meeting in st.session_state.saved_meetings if hasattr(meeting, "start")
    )
    result.events.sort(key=lambda event: event.start)
    return profile, result, week_start


init_state()

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800;900&display=swap');
* {{ box-sizing:border-box; }}
html, body, [class*="css"] {{ font-family:'Nunito',system-ui,sans-serif; }}
.stApp {{ background:#f4f2fb; color:#2d2b52; }}
[data-testid="stHeader"], [data-testid="stToolbar"] {{ background:transparent; }}
[data-testid="stSidebar"] {{ width:264px !important; background:#fcfbff; border-right:1px solid #ece7f5; }}
[data-testid="stSidebar"] > div:first-child {{ width:264px !important; padding:16px 16px 20px; }}
[data-testid="stSidebar"] .stRadio > label {{ font-size:10.5px; font-weight:800; letter-spacing:.8px; text-transform:uppercase; color:#aaa6c4; }}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] {{ gap:3px; }}
[data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] {{ padding:9px 11px; border-radius:10px; font-size:14px; font-weight:700; color:#5a5775; }}
[data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:has(input:checked) {{ background:#ede9fe; color:#6d56e8; }}
[data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] > div:first-child {{ display:none; }}
.main .stRadio [role="radiogroup"] {{ gap:8px; flex-wrap:wrap; }}
.main .stRadio label[data-baseweb="radio"] {{ min-width:70px; justify-content:center; border:1px solid #ece8f7; border-radius:13px; padding:10px 12px; background:#fff; color:#5a5775; font-weight:800; }}
.main .stRadio label[data-baseweb="radio"]:has(input:checked) {{ background:linear-gradient(135deg,#8b7cf6,#7c6cf0); color:#fff; border-color:transparent; box-shadow:0 4px 12px rgba(124,108,240,.3); }}
.main .stRadio label[data-baseweb="radio"] > div:first-child {{ display:none; }}
.main .block-container {{ max-width:840px; padding:38px 40px 80px; }}
h1,h2,h3 {{ color:#2d2b52; letter-spacing:-.5px; }}
h1 {{ font-size:29px !important; font-weight:900 !important; }}
h2 {{ font-size:19px !important; font-weight:900 !important; }}
p {{ line-height:1.5; }}
.bb-brand {{ position:relative; height:96px; border-radius:14px; overflow:hidden; background:url('{CAT_BG}') center 56%/cover; box-shadow:0 6px 18px rgba(120,100,200,.18); margin-bottom:14px; }}
.bb-brand:after {{ content:''; position:absolute; inset:0; background:linear-gradient(180deg,rgba(45,43,82,.5),transparent 40%,transparent 58%,rgba(45,43,82,.62)); }}
.bb-brand-title,.bb-brand-copy {{ position:absolute; left:0; right:0; text-align:center; color:#fff; z-index:1; text-shadow:0 1px 4px rgba(45,43,82,.55); }}
.bb-brand-title {{ top:8px; font-size:19px; font-weight:900; }}
.bb-brand-copy {{ bottom:8px; font-size:11px; font-weight:600; }}
.bb-energy-now {{ padding:14px 15px; background:linear-gradient(135deg,#f3efff,#eef0ff); border:1px solid #e6e0f8; border-radius:14px; margin-bottom:13px; }}
.bb-eyebrow {{ font-size:10.5px; font-weight:800; letter-spacing:.65px; text-transform:uppercase; color:#9b8df0; }}
.bb-energy-row {{ display:flex; justify-content:space-between; align-items:center; }}
.bb-energy-pct {{ font-size:15px; font-weight:900; color:#6d56e8; }}
.bb-bar {{ height:8px; border-radius:99px; background:#e3ddf6; margin:9px 0 8px; overflow:hidden; }}
.bb-advice {{ display:flex; gap:6px; align-items:center; font-size:12px; font-weight:700; color:#5a5775; }}
.bb-dot {{ width:7px; height:7px; border-radius:50%; }}
.bb-legend {{ margin-top:20px; padding:15px 16px; background:#fff; border:1px solid #ece8f7; border-radius:14px; display:grid; grid-template-columns:1fr 1fr; gap:8px 10px; }}
.bb-legend-title {{ grid-column:1/-1; font-size:10.5px; font-weight:800; text-transform:uppercase; letter-spacing:.7px; color:#aaa6c4; }}
.bb-legend-item {{ display:flex; align-items:center; gap:7px; font-size:12px; color:#5a5775; font-weight:600; }}
.bb-square {{ width:9px; height:9px; border-radius:3px; }}
.bb-subtitle {{ color:#75718f; font-size:15px; margin-top:-10px; margin-bottom:24px; }}
.bb-panel {{ background:#fff; border:1px solid #ece8f7; border-radius:16px; padding:24px; box-shadow:0 1px 3px rgba(80,70,140,.05); }}
.bb-ribbon {{ position:relative; height:240px; margin-top:6px; }}
.bb-ribbon svg {{ display:block; width:100%; height:240px; }}
.bb-axis {{ display:flex; justify-content:space-between; color:#b0acc6; font-size:11px; font-weight:700; }}
.bb-event {{ display:flex; align-items:stretch; background:#fff; border:1px solid #ece8f7; border-radius:14px; overflow:hidden; margin-top:10px; box-shadow:0 1px 2px rgba(80,70,140,.04); }}
.bb-event-time {{ width:92px; flex:none; padding:14px 0 14px 16px; display:flex; justify-content:center; flex-direction:column; }}
.bb-event-time strong {{ font-size:13px; }} .bb-event-time span {{ font-size:11px; color:#aaa6c4; }}
.bb-event-body {{ flex:1; min-width:0; padding:13px 14px; display:flex; align-items:center; gap:12px; }}
.bb-event-title {{ font-size:15px; font-weight:800; }}
.bb-event-meta {{ color:#9a96b8; font-size:12px; font-weight:600; margin-top:2px; }}
.bb-chip {{ margin-left:auto; white-space:nowrap; display:flex; gap:5px; align-items:center; font-size:11.5px; font-weight:800; padding:5px 10px; border-radius:99px; }}
.bb-result {{ background:#fff; border:1px solid #ece8f7; border-radius:14px; padding:20px 22px 10px; margin-top:14px; }}
.bb-result-title {{ font-size:16.5px; font-weight:900; }}
.bb-check {{ color:#1f9d6b; font-size:13px; margin-top:7px; }}
.bb-chosen {{ background:#e6f7ef; border:1px solid #bfe9d5; color:#1f9d6b; border-radius:12px; padding:13px 18px; font-size:14.5px; font-weight:800; margin-top:20px; }}
.bb-cat-launcher {{ width:96px; height:96px; border-radius:50%; overflow:hidden; border:3px solid #fff; box-shadow:0 8px 22px rgba(124,108,240,.32); margin:18px auto 5px; background:url('{CAT_PLUS}') center/cover; }}
.stButton > button {{ border:none; border-radius:10px; padding:.64rem 1rem; font-weight:800; color:#fff; background:linear-gradient(135deg,#8b7cf6,#7c6cf0); box-shadow:0 3px 10px rgba(124,108,240,.22); }}
.stButton > button:hover {{ color:#fff; border:none; transform:translateY(-1px); }}
.stTextInput input,.stTextArea textarea,[data-baseweb="select"] > div,.stDateInput input {{ border-color:#e7e2f3 !important; border-radius:10px !important; background:#faf8ff !important; }}
[data-testid="stForm"] {{ border:0; padding:0; }}
[data-testid="stImage"] img {{ border-radius:50%; }}
@media(max-width:760px) {{ [data-testid="stSidebar"] {{ width:235px !important; }} .main .block-container {{ padding:28px 20px 60px; }} .bb-chip {{ display:none; }} }}
</style>
""",
    unsafe_allow_html=True,
)

now = datetime.now()
now_minute = now.hour * 60 + now.minute
now_energy = energy_at(now_minute)
now_pct = round(now_energy * 100)
now_advice = "Great for deep work" if now_energy >= 0.6 else "Good for lighter tasks" if now_energy >= 0.4 else "Time for a gentle reset"
now_color = "#22b07d" if now_energy >= 0.6 else "#7c6cf0" if now_energy >= 0.4 else "#f5a524"

with st.sidebar:
    st.markdown(
        """<div class="bb-brand"><div class="bb-brand-title">Busy Brain</div><div class="bb-brand-copy">Plan with your energy, not against it</div></div>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""<div class="bb-energy-now"><div class="bb-energy-row"><span class="bb-eyebrow">Energy right now</span><span class="bb-energy-pct">{now_pct}%</span></div><div class="bb-bar"><div style="height:100%;width:{now_pct}%;background:linear-gradient(90deg,#a78bfa,#7c6cf0);border-radius:99px"></div></div><div class="bb-advice"><span class="bb-dot" style="background:{now_color}"></span>{now_advice}</div></div>""",
        unsafe_allow_html=True,
    )
    st.radio(
        "Menu",
        ["Today's flow", "Find a time", "Classes & energy"],
        key="view",
    )
    legend_html = "".join(
        f'<div class="bb-legend-item"><span class="bb-square" style="background:{color}"></span>{label}</div>'
        for label, color in [
            ("Classes", COLORS["class"]), ("Study", COLORS["study"]),
            ("Appointments", COLORS["appointment"]), ("Workout", COLORS["workout"]),
            ("Meals", COLORS["meal"]), ("Personal", COLORS["personal"]),
        ]
    )
    st.markdown(f'<div class="bb-legend"><div class="bb-legend-title">Task colors</div>{legend_html}</div>', unsafe_allow_html=True)


profile, plan, week_start = build_plan()


def render_schedule() -> None:
    title_col, button_col = st.columns([5, 1.2])
    with title_col:
        st.title("Today's flow")
        st.markdown('<div class="bb-subtitle">Your tasks, mapped onto the energy you’ll actually have.</div>', unsafe_allow_html=True)
    with button_col:
        st.write("")
        if st.button("↻ Re-plan", use_container_width=True):
            st.rerun()

    days = [week_start + timedelta(days=offset) for offset in range(7)]
    labels = {day.strftime("%a · %d"): day for day in days}
    current_label = next((label for label, day in labels.items() if day == st.session_state.selected_day), list(labels)[0])
    selected_label = st.radio("Week", list(labels), index=list(labels).index(current_label), horizontal=True, label_visibility="collapsed")
    selected_day = labels[selected_label]
    st.session_state.selected_day = selected_day
    events = [event for event in plan.events if event.start.date() == selected_day]

    line, area = curve_paths(1000, 30, 200)
    dots = []
    low_count = 0
    for event in events:
        middle = (event.start.hour * 60 + event.start.minute + event.end.hour * 60 + event.end.minute) / 2
        left = ((middle - 420) / 840) * 100
        top = 200 - energy_at(middle) * 170
        kind = task_kind(event)
        if match_for(event)[4] == "low":
            low_count += 1
        dots.append(f'<span title="{html.escape(event.title)}" style="position:absolute;left:{left:.2f}%;top:{top:.1f}px;width:13px;height:13px;border-radius:50%;background:{COLORS.get(kind, COLORS["personal"])};border:2.5px solid #fff;transform:translate(-50%,-50%);box-shadow:0 1px 5px rgba(80,70,140,.3);z-index:3"></span>')
    verdict = "nicely in flow" if low_count == 0 else f"{low_count} task{'s' if low_count != 1 else ''} fighting your energy"
    st.markdown(
        f"""<div class="bb-panel"><div style="display:flex;justify-content:space-between;align-items:center"><div><div style="font-size:16px;font-weight:900">{selected_day.strftime('%A, %B %d')}</div><div style="font-size:12.5px;color:#9a96b8;font-weight:700">{len(events)} events · {verdict}</div></div><div style="font-size:11.5px;font-weight:800;color:#7c6cf0;background:#f1ecfe;padding:6px 11px;border-radius:99px">〰 {st.session_state.energy_peak} energy</div></div><div class="bb-ribbon"><svg viewBox="0 0 1000 240" preserveAspectRatio="none"><defs><linearGradient id="bbfill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c4b5fd" stop-opacity=".55"/><stop offset="1" stop-color="#ede9fe" stop-opacity=".05"/></linearGradient></defs><line x1="0" y1="200" x2="1000" y2="200" stroke="#ece7f6"/><path d="{area}" fill="url(#bbfill)"/><path d="{line}" fill="none" stroke="#8b7cf6" stroke-width="2.5" vector-effect="non-scaling-stroke"/>
        {''.join(dots)}</svg></div><div class="bb-axis"><span>7 AM</span><span>10 AM</span><span>1 PM</span><span>4 PM</span><span>7 PM</span><span>9 PM</span></div></div>""",
        unsafe_allow_html=True,
    )
    if not events:
        st.info("A clear day. Your brain gets some breathing room.")
    for event in events:
        kind = task_kind(event)
        icon, label, color, background, _ = match_for(event)
        _, load_label = LOADS.get(kind, (1, "Light focus"))
        st.markdown(
            f"""<div class="bb-event"><div class="bb-event-time"><strong>{event.start.strftime('%-I:%M %p')}</strong><span>to {event.end.strftime('%-I:%M %p')}</span></div><div style="width:4px;background:{COLORS.get(kind, COLORS['personal'])}"></div><div class="bb-event-body"><div><div class="bb-event-title">{html.escape(event.title)}</div><div class="bb-event-meta">{TYPE_LABELS.get(kind, kind.title())} · {load_label}</div></div><div class="bb-chip" style="color:{color};background:{background}">{icon} {label}</div></div></div>""",
            unsafe_allow_html=True,
        )


def find_ranked_slots(friend, start_day, search_days, duration):
    friend_schedules = build_friend_schedules()
    existing = list(plan.events) + [meeting for meeting in st.session_state.saved_meetings if hasattr(meeting, "start")]
    end_day = start_day + timedelta(days=search_days - 1)
    if start_day <= now.date() <= end_day and now.time() > profile.day_start:
        existing.append(CalendarEvent("Time already passed", datetime.combine(now.date(), profile.day_start), now, TaskType.PERSONAL))
    blockers = []
    slots = []
    for index in range(3):
        slot = find_best_slot(existing + friend_schedules[friend] + blockers, profile, duration, start_day, end_day, EnergyLevel.MEDIUM)
        if not slot:
            break
        slot_start, slot_end = slot[0], slot[1]
        reason = slot[2] if len(slot) > 2 else "A comfortable energy match for you"
        slots.append((slot_start, slot_end, reason))
        blockers.append(CalendarEvent(f"Candidate {index}", slot_start, slot_end, TaskType.PERSONAL))
    return slots


def render_find_time() -> None:
    st.title("Find a time to meet")
    st.markdown('<div class="bb-subtitle">We rank shared openings by where they land on <em>your</em> energy—not just what’s free.</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.text_area("Ask in your own words", placeholder="Find me 60 minutes with Maya this week, not right after class.", height=82)
        left, right = st.columns(2)
        with left:
            friend = st.selectbox("Which friend?", list(build_friend_schedules()))
        with right:
            start_day = st.date_input("Start looking from", value=max(date.today(), week_start))
        days_col, duration_col = st.columns(2)
        with days_col:
            search_days = st.slider("Search the next … days", 1, 14, 5)
        with duration_col:
            duration = st.slider("How long (minutes)", 15, 120, 60, 15)
        if st.button("Find our best time", use_container_width=True):
            st.session_state.friend_results = [
                (friend, start, end, reason)
                for start, end, reason in find_ranked_slots(friend, start_day, search_days, duration)
            ]
            st.session_state.chosen_meeting = None

    if st.session_state.friend_results:
        st.subheader("Best shared windows")
        st.caption("Each window is ranked against your energy curve for that day.")
        for index, result in enumerate(st.session_state.friend_results):
            result_friend, start, end = result[:3]
            reason = result[3] if len(result) > 3 else "A comfortable energy match for you"
            energy = energy_at((start.hour * 60 + start.minute + end.hour * 60 + end.minute) / 2)
            energy_label = "Rides your peak" if energy >= 0.6 else "Steady energy" if energy >= 0.42 else "Lower-energy slot"
            st.markdown(
                f"""<div class="bb-result"><div style="display:flex;justify-content:space-between;gap:12px"><div class="bb-result-title">{start.strftime('%a, %b %d · %-I:%M')}–{end.strftime('%-I:%M %p')}</div><div class="bb-chip" style="color:#6d56e8;background:#efecfb">{energy_label}</div></div><div class="bb-check">✓ Open on both calendars</div><div class="bb-check">✓ {html.escape(reason).capitalize()}</div></div>""",
                unsafe_allow_html=True,
            )
            if st.button("Choose this time", key=f"choose-slot-{index}", use_container_width=True):
                meeting = CalendarEvent(
                    f"Meet with {result_friend}", start, end, TaskType.SOCIAL,
                    notes=f"Best shared free time found automatically for you and {result_friend}.",
                    flexible=True,
                )
                st.session_state.chosen_meeting = meeting
                if not any(hasattr(saved, "start") and saved.start == start and saved.title == meeting.title for saved in st.session_state.saved_meetings):
                    st.session_state.saved_meetings.append(meeting)
                st.rerun()

    chosen = st.session_state.chosen_meeting
    if chosen:
        st.markdown(f'<div class="bb-chosen">✓ Chosen · {chosen.start.strftime("%A, %b %d · %-I:%M %p")}</div>', unsafe_allow_html=True)
        st.markdown('<div class="bb-panel" style="margin-top:14px"><div class="bb-eyebrow" style="color:#aaa6c4">Suggested spot</div><div style="font-size:16px;font-weight:900;margin-top:6px">Riverside Café</div><div style="font-size:13.5px;color:#75718f;margin-top:5px">A calm, low-stimulation pick with soft lighting, quiet corners, and an easy route from campus.</div></div>', unsafe_allow_html=True)
        with st.expander("🎥 Create a video invite", expanded=True):
            st.write("Hand off a personalized invitation clip to Pika using the chosen time and place.")
            permission = st.checkbox("I have permission to use this person’s photo for the invitation.")
            if st.button("Prepare personalized invite", disabled=not permission):
                st.session_state.invite_ready = True
                st.success("Invite ready — handed to Pika ✨")
        st.markdown(f'<div class="bb-cat-launcher"></div><div style="text-align:center;font-weight:900;color:#6d56e8">Generate schedule</div>', unsafe_allow_html=True)
        if st.button("Open today’s flow", use_container_width=True):
            st.session_state.view = "Today's flow"
            st.rerun()


def render_classes() -> None:
    st.title("Classes & energy")
    st.markdown('<div class="bb-subtitle">Tell Busy Brain how you work. This shapes the energy curve everything else is planned around.</div>', unsafe_allow_html=True)
    with st.container(border=True):
        name_col, hours_col = st.columns(2)
        with name_col:
            class_name = st.text_input("Class name", value=st.session_state.class_name, placeholder="e.g. Organic Chemistry")
        with hours_col:
            study_hours = st.number_input("Weekly study hours", 1, 40, st.session_state.weekly_study_hours)
        energy_peak = st.radio("When’s your energy highest?", ["Morning", "Afternoon", "Evening"], index=["Morning", "Afternoon", "Evening"].index(st.session_state.energy_peak), horizontal=True)
        preview_line, preview_area = curve_paths(1000, 12, 108, energy_peak)
        st.markdown(
            f"""<div style="background:#faf8ff;border:1px solid #f0ecf8;border-radius:12px;padding:14px 16px;margin-top:12px"><div class="bb-eyebrow" style="color:#aaa6c4">Your predicted energy</div><svg viewBox="0 0 1000 120" preserveAspectRatio="none" width="100%" height="90"><defs><linearGradient id="bbprev" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c4b5fd" stop-opacity=".5"/><stop offset="1" stop-color="#ede9fe" stop-opacity=".05"/></linearGradient></defs><path d="{preview_area}" fill="url(#bbprev)"/><path d="{preview_line}" fill="none" stroke="#8b7cf6" stroke-width="2.5" vector-effect="non-scaling-stroke"/></svg><div class="bb-axis"><span>7 AM</span><span>1 PM</span><span>9 PM</span></div></div>""",
            unsafe_allow_html=True,
        )
        if st.button("Add class & plan study time", use_container_width=True):
            st.session_state.class_name = class_name or "Untitled class"
            st.session_state.weekly_study_hours = study_hours
            st.session_state.energy_peak = energy_peak
            st.session_state.added_classes.append({"name": st.session_state.class_name, "hours": study_hours, "peak": energy_peak})
            st.success("Class added and study time re-planned ✨")
    if st.session_state.added_classes:
        st.subheader("Your classes")
        for index, item in enumerate(st.session_state.added_classes):
            label_col, remove_col = st.columns([8, 1])
            with label_col:
                st.markdown(f'<div class="bb-panel" style="padding:14px 16px"><strong>{html.escape(item["name"])}</strong><div style="font-size:12.5px;color:#8a86a8">{item["hours"]}h/week · planned for your {item["peak"].lower()} peak</div></div>', unsafe_allow_html=True)
            with remove_col:
                if st.button("×", key=f"remove-class-{index}"):
                    st.session_state.added_classes.pop(index)
                    st.rerun()


if st.session_state.view == "Today's flow":
    render_schedule()
elif st.session_state.view == "Find a time":
    render_find_time()
else:
    render_classes()
