#!/usr/bin/env python3
"""fabricstack.dev: community catalogue of Microsoft Fabric tools (CC BY 4.0), via its public JSON API.

  fabricstack.py search QUERY [--limit N]     # keyword match on title, description, tags, category
  fabricstack.py added --since YYYY-MM-DD     # tools added to the catalogue since a date
  fabricstack.py categories

Output: JSON {"results": [{title, description, url, category, tags, maintainer, author, status, added, listing}]}.
The listing proves a tool exists; cite what it does from the tool's own repo/docs.
Exit 3 means the site is unavailable: rely on GitHub search instead.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import cli  # noqa: E402
from lib.errors import SourceUnavailable  # noqa: E402
from lib.fetch import get_json  # noqa: E402

API = "https://fabricstack.dev/api/tools.json"
FALLBACK = "GitHub search"


def load():
    data = get_json(API, ttl=6 * 3600)
    tools = data.get("tools") if isinstance(data, dict) else data
    if not isinstance(tools, list):
        raise SourceUnavailable("unexpected API format")
    return [{
        "title": t.get("title") or t.get("name"),
        "description": t.get("description"),
        "url": t.get("url"),
        "category": t.get("category"),
        "tags": t.get("tags", []),
        "maintainer": t.get("maintainer"),
        "author": t.get("author"),
        "language": t.get("language"),
        "status": t.get("status"),
        "added": t.get("added"),
        "listing": t.get("href"),
    } for t in tools]


def score(t, words):
    hay = " ".join(str(x) for x in (t["title"], t["description"], t["category"], " ".join(t["tags"] or []))).lower()
    return sum(2 if w in (t["title"] or "").lower() else 1 for w in words if re.search(rf"\b{re.escape(w)}", hay))


def cmd_search(a):
    tools = load()
    words = [w for w in re.findall(r"[a-z0-9]+", a.query.lower()) if len(w) > 2]
    ranked = sorted(((score(t, words), t) for t in tools), key=lambda x: -x[0])
    cli.emit_results("fabricstack", [t for sc, t in ranked if sc > 0], limit=a.limit, catalogue_size=len(tools))


def cmd_added(a):
    res = sorted((t for t in load() if (t["added"] or "") >= a.since), key=lambda t: t["added"], reverse=True)
    cli.emit_results("fabricstack", res)


def cmd_categories(a):
    tools = load()
    cli.emit({"source": "fabricstack", "count": len(tools), "categories": sorted({t["category"] for t in tools if t["category"]})})


def main():
    ap, sub = cli.parser(__doc__)
    s = sub.add_parser("search")
    s.add_argument("query")
    cli.add_limit(s, 10)
    ad = sub.add_parser("added")
    cli.add_window(ad, since_required=True, until=False)
    sub.add_parser("categories")
    cli.run({"search": cmd_search, "added": cmd_added, "categories": cmd_categories}, ap.parse_args(), FALLBACK)


if __name__ == "__main__":
    main()
