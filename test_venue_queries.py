"""Run several different venue queries through find_venue_for_meetup to see
overall hit rate across the fetch -> stagehand -> search-only fallback chain.
    python3 test_venue_queries.py
"""

from venue_lookup import find_venue_for_meetup

queries = [
    ("quiet coffee shop for studying", "UCI Irvine"),
    ("library study room", "Irvine CA"),
    ("casual lunch spot", "Saddleback College Mission Viejo"),
    ("walk and smoothie place", "Irvine CA"),
    ("museum or bookstore", "Irvine CA"),
]

for activity, location in queries:
    print(f"\n=== {activity} near {location} ===")
    try:
        result = find_venue_for_meetup(activity, location)
        if result:
            print(f"[{result.source}] {result.name}")
            print(f"  {result.url}")
            print(f"  {result.snippet[:150]}")
        else:
            print("  No result.")
    except Exception as e:
        print(f"  ERROR: {e}")