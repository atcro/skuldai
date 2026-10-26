"""G08 smoke test: one real Tavily search call, evidence to stdout.

DOC-VERIFIED SDK pattern (runbook G08, tavily-python). Run inside WSL2 with
TAVILY_API_KEY set in the environment or in a git-ignored .env file.
Redirect stdout into evidence/G08/ after confirming no secret is printed.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from dotenv import load_dotenv
from tavily import TavilyClient


def main() -> int:
    load_dotenv()
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        print("TAVILY_API_KEY not set; refusing to pretend a call happened.", file=sys.stderr)
        return 2

    query = "Franka Emika Panda robot arm payload specification official documentation"
    client = TavilyClient(api_key=api_key)
    started = dt.datetime.now(dt.UTC).isoformat()
    result = client.search(query, search_depth="basic", max_results=3)
    finished = dt.datetime.now(dt.UTC).isoformat()

    hits = result.get("results") or []
    if not hits:
        print("Tavily returned no usable results.", file=sys.stderr)
        return 1

    evidence = {
        "gate": "G08",
        "kind": "tavily_search_smoke",
        "started_utc": started,
        "finished_utc": finished,
        "query": query,
        "result_count": len(hits),
        "results": [{"title": h.get("title"), "url": h.get("url")} for h in hits],
    }
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
