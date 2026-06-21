from sample_data import build_sample_inputs
from agents import CalendarOrchestrator


def print_plan(result):
    current_day = None
    for event in result.events:
        if event.start.date() != current_day:
            current_day = event.start.date()
            print(f"\n=== {current_day.strftime('%A, %b %d')} ===")
        print(
            f"{event.start.strftime('%I:%M %p')} - {event.end.strftime('%I:%M %p')} | "
            f"{event.title} [{event.task_type.value}]"
        )
        if event.notes:
            print(f"   → {event.notes}")

    if result.messages:
        print("\nMessages:")
        for msg in result.messages:
            print(f"- {msg}")

    if result.unscheduled:
        print("\nNeeds manual review:")
        for item in result.unscheduled:
            print(f"- {item}")


def main():
    print("Busy Brain")
    profile, classes, fixed_events, tasks, week_start = build_sample_inputs()
    orchestrator = CalendarOrchestrator()
    result = orchestrator.build_week_plan(profile, classes, fixed_events, tasks, week_start)
    print_plan(result)

    friend_result = orchestrator.social_agent.find_friend_meeting(
        friend_a_events=result.events,
        friend_b_events=[],
        profile=profile,
        start_day=week_start,
        end_day=week_start.replace(day=week_start.day) if False else week_start,
        duration_minutes=90,
    )
    if friend_result.events:
        print("\nSuggested friend meeting:")
        print_plan(friend_result)


if __name__ == "__main__":
    main()
