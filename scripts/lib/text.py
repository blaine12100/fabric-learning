"""Text helpers: HTML to plain text, clipping, and the --grep / --full / excerpt choice."""
import html
import re
from html.parser import HTMLParser

EXCERPT = 4000  # default excerpt length for long posts and pages


class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "pre", "section"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(s: str) -> str:
    p = _Text()
    p.feed(html.unescape(s or "") if "&lt;" in (s or "") else (s or ""))
    text = "".join(p.out)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " …"


def grep_paragraphs(text: str, term: str) -> str:
    """Paragraphs mentioning term, each with the nearest heading-like line above it (status labels such as
    'Generally available' or '(Preview)' usually live in the heading)."""
    t = term.lower()
    lines = [p.strip() for p in text.split("\n") if p.strip()]
    out = []
    for i, p in enumerate(lines):
        if t not in p.lower():
            continue
        head = next((lines[j] for j in range(i - 1, max(i - 4, -1), -1) if len(lines[j]) < 120), None)
        out.append(f"{head}\n{p}" if head and head not in out and t not in head.lower() else p)
    return "\n\n".join(out)


def select_text(text: str, grep=None, full: bool = False, limit: int = EXCERPT) -> str:
    """What a long-text source returns: matching paragraphs (--grep), everything (--full) or an excerpt."""
    if grep:
        return grep_paragraphs(text, grep)
    return text if full else clip(text, limit)


def html_meta(page_html: str, name: str):
    """Content of <meta name|property="name" content="...">, or None."""
    m = re.search(rf'<meta\s+(?:name|property)="{re.escape(name)}"\s+content="([^"]*)"', page_html)
    return m.group(1) if m else None
