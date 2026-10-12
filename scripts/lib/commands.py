"""Run external CLIs (gh, yt-dlp) with an on-disk cache and one retry on rate limits.
Raises CommandError instead of exiting, so it is safe inside worker threads."""
import json
import shutil
import subprocess
import time
from typing import List, Optional  # noqa: F401

from .cache import DiskCache
from .errors import CommandError


def run_cached(argv: List[str], ttl: int = 3600, timeout: int = 180,
               retry_markers=("rate limit", "abuse"), retry_wait: int = 20, ok_empty: bool = False) -> Optional[str]:
    """stdout of argv, cached by the full command line. If stderr contains a retry marker, wait and retry once.
    ok_empty=True returns None on failure instead of raising (for optional look-ups such as a README)."""
    exe = argv[0]
    if not (shutil.which(exe) or "/" in exe or "\\" in exe):
        raise CommandError(f"{exe} CLI not installed")
    name = exe.replace("\\", "/").rsplit("/", 1)[-1]
    cache = DiskCache(name.split(".")[0])  # cache namespace per tool: gh, yt-dlp
    key = json.dumps(argv[1:])
    cached = cache.get(key, ttl)
    if cached is not None:
        return cached.decode()
    err = ""
    for attempt in range(2):
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            err = f"timed out after {timeout}s"
            break
        if r.returncode == 0:
            if ttl:
                cache.put(key, r.stdout.encode())
            return r.stdout
        err = r.stderr.strip()
        if attempt == 0 and any(m in err.lower() for m in retry_markers):
            time.sleep(retry_wait)
            continue
        break
    if ok_empty:
        return None
    raise CommandError(f"{name} failed: {err[-300:]}")
