"""HTTP: cached GET with retries, JSON fetch, and a cross-process rate limiter."""
import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    import fcntl  # POSIX only; on Windows the limiter just doesn't coordinate across processes
except ImportError:
    fcntl = None

from .cache import DiskCache
from .config import USER_AGENT, cache_root
from .errors import SourceUnavailable

_cache = DiskCache("http")
RETRY_STATUS = (429, 500, 502, 503, 504)


def http_get(url: str, ttl: int = 3600, retries: int = 4, accept: str = "*/*", limiter=None) -> bytes:
    """GET with an on-disk cache (ttl seconds) and exponential backoff on 429/5xx.
    `limiter` (a RateLimiter) spaces out requests that miss the cache. Raises SourceUnavailable."""
    cached = _cache.get(url, ttl)
    if cached is not None:
        return cached
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    delay = 2
    for attempt in range(retries + 1):
        try:
            if limiter:
                with limiter:
                    body = _read(req)
            else:
                body = _read(req)
            if ttl:
                _cache.put(url, body)
            return body
        except urllib.error.HTTPError as e:
            if e.code in RETRY_STATUS and attempt < retries:
                time.sleep(min(_retry_after(e.headers.get("Retry-After"), delay), 30))
                delay *= 2
                continue
            raise SourceUnavailable(f"HTTP {e.code} for {url}")
        # URLError and timeouts are OSErrors (socket.timeout on 3.9); dropped connections raise HTTPException
        except (OSError, http.client.HTTPException) as e:
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise SourceUnavailable(f"{e} for {url}")
    raise SourceUnavailable(f"gave up on {url}")


def _retry_after(value, default: int) -> int:
    """Retry-After is either seconds or an HTTP date; anything unreadable falls back to our own backoff."""
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def _read(req) -> bytes:
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def get_json(url: str, ttl: int = 3600, **kw):
    """GET and parse JSON. Raises SourceUnavailable on network errors or a non-JSON reply."""
    try:
        return json.loads(http_get(url, ttl=ttl, accept="application/json", **kw))
    except ValueError as e:
        raise SourceUnavailable(f"not JSON from {url}: {e}")


class RateLimiter:
    """Keeps requests to one host at least `interval` seconds apart, across processes
    (gather.py runs several scripts at once). Use as a context manager around the request."""

    def __init__(self, name: str, interval: float):
        self.lock_path = cache_root() / f"{name}.lock"
        self.interval = interval
        self._f = None

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.lock_path, "a+")
        if fcntl:
            fcntl.flock(self._f, fcntl.LOCK_EX)
        self._f.seek(0)
        wait = self.interval - (time.time() - float(self._f.read() or 0))
        if wait > 0:
            time.sleep(wait)
        return self

    def __exit__(self, *exc):
        self._f.seek(0)
        self._f.truncate()
        self._f.write(str(time.time()))
        self._f.close()  # closing releases the flock
        return False


def clean_url(url: str) -> str:
    """Drop the query string (tracking such as ?WT.mc_id=...) so URLs de-duplicate and cite cleanly."""
    p = urllib.parse.urlsplit(url or "")
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "", p.fragment))
