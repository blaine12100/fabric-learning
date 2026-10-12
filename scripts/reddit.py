#!/usr/bin/env python3
"""Reddit via public RSS (the JSON API blocks unauthenticated requests).

  reddit.py search QUERY [--sub MicrosoftFabric] [--sort relevance|top|new] [--time week|month|year|all] [--limit N]
  reddit.py top  [--sub MicrosoftFabric] [--time day|week|month|year] [--limit N]
  reddit.py new  [--sub MicrosoftFabric] [--limit N]
  reddit.py thread URL [--limit N]       # the post plus its top-level comments

Output: JSON {"results": [{title, url, author, published, text, ...}]}. RSS carries no upvote counts;
`thread` returns `comments` (count of comments in the feed) as the engagement signal.
Reddit rate-limits RSS: the script caches for 3 hours, spaces requests >= 3 s apart across processes, and backs off on HTTP 429.
Exit 3 means Reddit is unavailable: fall back to web search with site:reddit.com/r/MicrosoftFabric.
"""
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import cli  # noqa: E402
from lib.feeds import fetch_feed  # noqa: E402
from lib.fetch import RateLimiter  # noqa: E402
from lib.text import clip, html_to_text  # noqa: E402

FALLBACK = "web search with site:reddit.com/r/MicrosoftFabric"
# Reddit rate-limits unauthenticated RSS hard: >= 3 s between requests across all processes, 3-hour cache.
LIMITER = RateLimiter("reddit", 3)


def entries(url):
    return [{
        "title": e["title"],
        "url": e["url"],
        "author": (e["author"] or "").replace("/u/", ""),
        "published": e["published"],
        "text": clip(html_to_text(e["html"]), 1500),
    } for e in fetch_feed(url, ttl=3 * 3600, retries=3, limiter=LIMITER)]


def feed_url(a):
    if a.cmd == "search":
        q = urllib.parse.urlencode({"q": a.query, "restrict_sr": "on", "sort": a.sort, "t": a.time})
        return f"https://www.reddit.com/r/{a.sub}/search.rss?{q}"
    if a.cmd == "top":
        return f"https://www.reddit.com/r/{a.sub}/top/.rss?t={a.time}"
    if a.cmd == "new":
        return f"https://www.reddit.com/r/{a.sub}/new/.rss"
    return a.url.split("?")[0].rstrip("/") + "/.rss"


def cmd_listing(a):
    url = feed_url(a)
    cli.emit_results("reddit", entries(url), limit=a.limit, query_url=url)


def cmd_thread(a):
    res = entries(feed_url(a))
    post, comments = (res[0] if res else None), res[1:]
    cli.emit({"source": "reddit", "post": post, "comments": len(comments), "top_comments": comments[: a.limit]})


def main():
    ap, sub = cli.parser(__doc__)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--sort", choices=["relevance", "top", "new"], default="relevance")
    s.add_argument("--time", choices=["week", "month", "year", "all"], default="year")
    t = sub.add_parser("top")
    t.add_argument("--time", choices=["day", "week", "month", "year"], default="week")
    n = sub.add_parser("new")
    th = sub.add_parser("thread")
    th.add_argument("url")
    for p in (s, t, n):
        p.add_argument("--sub", default="MicrosoftFabric")
    for p in (s, t, n, th):
        cli.add_limit(p, 15)
    cli.run({"search": cmd_listing, "top": cmd_listing, "new": cmd_listing, "thread": cmd_thread},
            ap.parse_args(), FALLBACK)


if __name__ == "__main__":
    main()
