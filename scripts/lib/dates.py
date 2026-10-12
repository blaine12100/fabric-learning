"""Dates: every source reports them differently. Normalise to ISO YYYY-MM-DD; compare as strings."""
import datetime as dt
import email.utils
import re
from typing import Optional

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_COMPACT = re.compile(r"^(\d{4})(\d{2})(\d{2})$")


def iso_date(value) -> Optional[str]:
    """ISO date from ISO 8601 ('2026-10-05T…'), RFC 822 ('Mon, 05 Oct 2026 …', RSS) or YYYYMMDD (yt-dlp).
    None if missing or unparseable."""
    if not value:
        return None
    s = str(value).strip()
    m = _ISO.match(s) or _COMPACT.match(s)
    if m:
        return "-".join(m.groups())
    try:
        return email.utils.parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return None


def in_window(published: Optional[str], since: Optional[str] = None, until: Optional[str] = None) -> bool:
    """True if published falls in [since, until]. Undated items are kept: the caller decides."""
    return published is None or ((not since or published >= since) and (not until or published <= until))


def today() -> str:
    return dt.date.today().isoformat()


def days_between(a: str, b: str) -> int:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days
