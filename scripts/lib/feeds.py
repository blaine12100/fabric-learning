"""RSS 2.0 and Atom feeds, parsed into one entry shape:
{title, url, published (ISO date), author, html, categories}. Callers turn `html` into text as they need."""
import xml.etree.ElementTree as ET
from typing import Dict, List

from .dates import iso_date
from .errors import SourceUnavailable
from .fetch import http_get

ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"
FEED_ACCEPT = "application/rss+xml, application/atom+xml, application/xml;q=0.9"


def parse_feed(xml_bytes: bytes) -> List[Dict]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise SourceUnavailable(f"unexpected feed format: {e}")
    if root.tag == f"{ATOM}feed":
        return [_atom_entry(e) for e in root.findall(f"{ATOM}entry")]
    channel = root.find("channel")
    if channel is None:
        raise SourceUnavailable(f"not an RSS or Atom feed (root <{root.tag}>)")
    return [_rss_item(i) for i in channel.findall("item")]


def _rss_item(it) -> Dict:
    return {
        "title": (it.findtext("title") or "").strip(),
        "url": it.findtext("link") or "",
        "published": iso_date(it.findtext("pubDate")),
        "author": it.findtext(f"{DC}creator") or it.findtext("author"),
        "html": it.findtext("description") or "",
        "categories": [c.text for c in it.findall("category") if c.text],
    }


def _atom_entry(e) -> Dict:
    link = e.find(f"{ATOM}link")
    return {
        "title": (e.findtext(f"{ATOM}title") or "").strip(),
        "url": link.get("href") if link is not None else None,
        "published": iso_date(e.findtext(f"{ATOM}published") or e.findtext(f"{ATOM}updated")),
        "author": e.findtext(f"{ATOM}author/{ATOM}name"),
        "html": e.findtext(f"{ATOM}content") or e.findtext(f"{ATOM}summary") or "",
        "categories": [c.get("term") for c in e.findall(f"{ATOM}category") if c.get("term")],
    }


def fetch_feed(url: str, ttl: int = 1800, **http_kw) -> List[Dict]:
    """GET (cached) and parse a feed. Raises SourceUnavailable."""
    return parse_feed(http_get(url, ttl=ttl, accept=FEED_ACCEPT, **http_kw))
