#!/usr/bin/env python3
"""Microsoft Fabric Community site via its public RSS endpoints: the Fabric Updates blog,
forum Q&A and Fabric Ideas. (blog.fabric.microsoft.com redirects here; the site's HTML pages
block automated fetching, but RSS is open and carries full post text.)

  community.py blog   [--product fabric|powerbi|any] [--query Q] [--since D] [--until D] [--limit N] [--full] [--grep T]
  community.py search QUERY [--board any|blog|ideas|forum] [--sort relevance|date] [--since D] [--limit N] [--full]
  community.py ideas  QUERY [--since D] [--limit N]

Output: JSON {"results": [{title, url, board, published, author, text}]}. text is an excerpt
(4000 chars) unless --full. Long posts (monthly feature summaries run to 100k+ chars): use
--grep TERM to return only the paragraphs that mention TERM, or --full to read everything. Exit 3 means the source is unavailable: fall back to web search.
RSS returns at most ~20 results per query; narrow the query rather than paging.
Ideas results carry no vote counts or status: get those from a web search snippet.
"""
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import cli  # noqa: E402
from lib.dates import in_window  # noqa: E402
from lib.feeds import fetch_feed  # noqa: E402
from lib.text import html_to_text, select_text  # noqa: E402

FALLBACK = "web search with site:community.fabric.microsoft.com"
BASE = "https://community.fabric.microsoft.com/t5/s/rss"
BOARD_FEED = f"{BASE}/board?board.id=fbc_fabricupdatesblogs"
BOARDS = {"blog": "blog-board:fbc_fabricupdatesblogs", "ideas": "idea-board:fbc_ideas"}
NOT_FORUM = ("Fabric-Updates-Blog", "Power-BI-Updates-Blog", "Fabric-Ideas")
PRODUCT_BOARDS = {"powerbi": ("Power-BI-Updates-Blog",), "any": ("Power-BI-Updates-Blog", "Fabric-Updates-Blog")}


def search_url(q, board=None, newest=False):
    params = {"q": q}
    if board in BOARDS:
        params["location"] = BOARDS[board]
    if newest:
        params["sort_by"] = "-topicPostDate"
    return f"{BASE}/search?{urllib.parse.urlencode(params)}"


def to_result(entry, grep, full):
    """Feed entry -> community result. The board is the path segment after /t5/."""
    url = entry["url"]
    return {
        "title": entry["title"],
        "url": url,
        "board": url.split("/t5/")[1].split("/")[0] if "/t5/" in url else "",
        "published": entry["published"],
        "author": entry["author"],
        "text": select_text(html_to_text(entry["html"]), grep, full),
    }


def fetch(urls, a):
    """Fetch and merge several feeds, keeping the first copy of each URL."""
    seen, out = set(), []
    for url in urls:
        for e in fetch_feed(url, ttl=1800):
            if e["url"] not in seen:
                seen.add(e["url"])
                out.append(to_result(e, a.grep, a.full))
    return out


def dedupe_reposts(results):
    """The same post submitted twice (double-click on "Post") gets two ids; keep the first."""
    seen, out = set(), []
    for r in results:
        key = (r["board"], r["title"].lower(), r["published"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def finish(a, source, results, query_url, keep_board=None):
    if keep_board:
        results = [r for r in results if keep_board(r["board"])]
    if a.grep:
        results = [r for r in results if r["text"]]
    fetched = dedupe_reposts(results)
    results = [r for r in fetched if in_window(r["published"], a.since, a.until)]
    meta = {"query_url": query_url}
    if len(results) < len(fetched):
        meta["outside_window"] = len(fetched) - len(results)
        if not results:
            # RSS can't page, so an older window is often out of reach; say so rather than return a silent zero
            meta["note"] = ("All results fell outside the window: RSS only reaches the ~20 newest or most relevant "
                            "posts. For older windows, use a web search with site:community.fabric.microsoft.com "
                            "plus the key words and the month.")
    cli.emit_results(source, results, limit=a.limit, **meta)


def cmd_blog(a):
    if a.product != "fabric":
        # The Power BI Updates blog has no working board feed (and its board id isn't guessable), so merge a
        # few searches and keep only posts from the right blog board.
        q = a.query or "Power BI"
        urls = [search_url(q), search_url(q, newest=True), search_url(f"{q} feature summary", newest=True),
                search_url(f"{q} updates blog")]
        results = sorted(fetch(urls, a), key=lambda r: r["published"] or "", reverse=True)
        finish(a, "fabric-blog", results, urls[-1], keep_board=lambda b: b in PRODUCT_BOARDS[a.product])
        return
    # without a query: the board feed, newest first; with one, relevance finds exact titles
    url = search_url(a.query, "blog") if a.query else BOARD_FEED
    finish(a, "fabric-blog", fetch([url], a), url)


def cmd_search(a):
    url = search_url(a.query, a.board, newest=a.sort == "date")
    finish(a, "community", fetch([url], a), url, keep_board=(lambda b: b not in NOT_FORUM) if a.board == "forum" else None)


def cmd_ideas(a):
    url = search_url(a.query, "ideas", newest=True)
    finish(a, "fabric-ideas", fetch([url], a), url)


def main():
    ap, sub = cli.parser(__doc__)
    b = sub.add_parser("blog")
    b.add_argument("--query")
    b.add_argument("--product", choices=["fabric", "powerbi", "any"], default="fabric")
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--board", choices=["any", "blog", "ideas", "forum"], default="any")
    s.add_argument("--sort", choices=["relevance", "date"], default="relevance")
    i = sub.add_parser("ideas")
    i.add_argument("query")
    for p in (b, s, i):
        cli.add_window(p)
        cli.add_limit(p, 20)
        cli.add_text(p)
    cli.run({"blog": cmd_blog, "search": cmd_search, "ideas": cmd_ideas}, ap.parse_args(), FALLBACK)


if __name__ == "__main__":
    main()
