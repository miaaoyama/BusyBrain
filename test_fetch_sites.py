"""Quick test: does Browserbase's fetch_api get blocked on multiple sites,
or was the earlier result (corner.inc) a one-off? Run this directly:
    python3 test_fetch_sites.py
"""

import os
import re
from dotenv import load_dotenv
load_dotenv()

from browserbase import Browserbase

bb = Browserbase(api_key=os.getenv("BROWSERBASE_API_KEY"))

test_urls = [
    "https://www.starbucks.com/store-locator/store/1234",  # may 404, that's fine — testing block behavior
    "https://en.wikipedia.org/wiki/Coffeehouse",
    "https://www.yelp.com/biz/moongoat-coffee-irvine",
    "https://www.google.com/maps/search/coffee+shop+irvine",
    "https://www.peets.com/pages/store/u-c-irvine",
]

for url in test_urls:
    print(f"\n=== {url} ===")
    try:
        result = bb.fetch_api.create(url=url, format="markdown")
        content = getattr(result, "content", None) or getattr(result, "text", "") or str(result)
        content = re.sub(r"\s+", " ", content).strip()
        print(content[:300])
    except Exception as e:
        print(f"ERROR: {e}")
