#!/usr/bin/env python3
"""Microsoft Learn: Fabric docs, training and certification study guides, via Learn's public search and catalog APIs.

  learn.py search QUERY [--type docs|training|credential|any] [--limit N]
  learn.py page URL [--grep TERM] [--full]
  learn.py exam dp-600|dp-700 [--grep TERM]

search  Learn's own site search, kept to Fabric / Power BI docs (docs), training, or credentials.
        Output: {"results": [{title, url, updated, category, description, preview_in_title}]}
page    One Learn page: title, ms_date (author's review date), updated (last published), preview signals,
        and an excerpt (4000 chars), the paragraphs matching --grep (with their headings), or --full text.
        preview.title / preview.note are the page's own labels; preview.mentions are other sentences that
        say "preview" (often a sub-feature, so read them before labelling the whole feature).
exam    The exam's study guide (skills measured, upcoming changes) plus the Fabric learning paths from the
        Learn catalog, each with its last-modified date.
Exit 3 means Learn is unavailable: fall back to web search on learn.microsoft.com.
"""
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import cli  # noqa: E402
from lib.dates import iso_date  # noqa: E402
from lib.errors import SourceUnavailable  # noqa: E402
from lib.fetch import clean_url, get_json, http_get  # noqa: E402
from lib.text import clip, html_meta, html_to_text, select_text  # noqa: E402

SEARCH = "https://learn.microsoft.com/api/search"
CATALOG = "https://learn.microsoft.com/api/catalog/?locale=en-us&type=learningPaths"
STUDY_GUIDE = "https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/{}"
CATEGORY = {"docs": "Documentation", "training": "Training", "credential": "Credential"}
# Learn search is site-wide; keep results that are about Fabric or Power BI
FABRIC_URL = re.compile(r"learn\.microsoft\.com/[a-z-]+/(fabric|power-bi|rest/api/fabric|training|credentials)/", re.I)
FABRIC_WORD = re.compile(r"\b(fabric|power bi|onelake|lakehouse|direct lake|dp-600|dp-700)\b", re.I)
PREVIEW_NOTE = re.compile(r"(this feature is (currently )?in (public )?preview|feature is in preview|is currently in preview)", re.I)


FALLBACK = {"search": "web search on learn.microsoft.com", "page": "WebFetch the page",
            "exam": "web search for the exam's study guide on learn.microsoft.com"}
BOILERPLATE = re.compile(r"(?m)^\s*(Feedback|Summarize this article for me|In this article)\s*$")


def search(query, kind, limit):
    q = {"search": query, "locale": "en-us", "$top": "25"}
    if kind != "any":
        q["$filter"] = f"category eq '{CATEGORY[kind]}'"
    d = get_json(SEARCH + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote), ttl=6 * 3600)
    out = []
    for r in d.get("results", []):
        url = clean_url(r.get("url"))
        title = r.get("title") or ""
        if not (FABRIC_URL.search(url) and (kind == "docs" or FABRIC_WORD.search(title + " " + (r.get("description") or "")) or "/fabric/" in url)):
            continue
        out.append({
            "title": title,
            "url": url,
            "updated": iso_date(r.get("lastUpdatedDate")),
            "category": r.get("category"),
            "description": clip(re.sub(r"\s+", " ", r.get("description") or ""), 300),
            "preview_in_title": "preview" in title.lower(),
        })
        if len(out) >= limit:
            break
    return out


def article_text(page_html):
    """The article body: from the first <h1> to the feedback / footer area, minus page chrome."""
    start = page_html.find("<h1")
    ends = (page_html.find('id="ms--content-well-footer"', start), page_html.find('data-bi-name="feedback"', start),
            page_html.find("<footer", start))
    end = min([i for i in ends if i > 0] or [len(page_html)])
    text = BOILERPLATE.sub("", html_to_text(page_html[start:end] if start >= 0 else page_html))
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def page(url, grep=None, full=False):
    page_html = http_get(url, ttl=6 * 3600).decode("utf-8", "replace")
    title = (html_meta(page_html, "og:title") or "").strip()
    text = article_text(page_html)
    sentences = re.findall(r"[^.\n]*\bpreview\b[^.\n]*\.?", text, re.I)
    result = {
        "title": title,
        "url": clean_url(html_meta(page_html, "og:url") or url),
        "ms_date": iso_date(html_meta(page_html, "ms.date")),
        "updated": iso_date(html_meta(page_html, "updated_at")),
        "preview": {
            "title": "preview" in title.lower(),
            "note": bool(PREVIEW_NOTE.search(text)),
            "mentions": [clip(s.strip(), 200) for s in sentences if not PREVIEW_NOTE.search(s)][:8],
        },
    }
    key = "matches" if grep else "text" if full else "excerpt"
    result[key] = select_text(text, grep, full) or (f"no paragraph mentions '{grep}'" if grep else "")
    return result


def fabric_learning_paths():
    cat = get_json(CATALOG, ttl=24 * 3600)
    paths = [{
        "title": p.get("title"),
        "url": clean_url(p.get("url")),
        "updated": iso_date(p.get("last_modified")),
        "minutes": p.get("duration_in_minutes"),
        "levels": p.get("levels"),
    } for p in cat.get("learningPaths", [])
        if "fabric" in [x.lower() for x in p.get("products", [])] or "fabric" in (p.get("title") or "").lower()]
    return sorted(paths, key=lambda p: p["updated"] or "", reverse=True)


def cmd_search(a):
    cli.emit_results("learn", search(a.query, a.type, a.limit))


def cmd_page(a):
    if "learn.microsoft.com" not in a.url:
        raise SourceUnavailable("not a learn.microsoft.com URL")
    cli.emit(page(a.url, a.grep, a.full))


def cmd_exam(a):
    code = a.code.lower()
    if not re.fullmatch(r"[a-z]{2,3}-\d{3}", code):
        raise SourceUnavailable(f"not an exam code: {code}")
    cli.emit({"exam": code.upper(), "study_guide": page(STUDY_GUIDE.format(code), grep=a.grep),
              "fabric_learning_paths": fabric_learning_paths()})


def main():
    ap, sub = cli.parser(__doc__)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--type", choices=["docs", "training", "credential", "any"], default="docs")
    cli.add_limit(s, 8)
    p = sub.add_parser("page")
    p.add_argument("url")
    cli.add_text(p)
    e = sub.add_parser("exam")
    e.add_argument("code")
    e.add_argument("--grep")
    cli.run({"search": cmd_search, "page": cmd_page, "exam": cmd_exam}, ap.parse_args(), FALLBACK)


if __name__ == "__main__":
    main()
