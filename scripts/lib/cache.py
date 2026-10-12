"""Namespaced on-disk cache. Keys are hashed, so any string (a URL, a command line) works as a key."""
import hashlib
import time
from pathlib import Path
from typing import Optional

from .config import cache_root


class DiskCache:
    def __init__(self, namespace: str):
        self.namespace = namespace

    def _path(self, key: str) -> Path:
        return cache_root() / self.namespace / hashlib.sha256(key.encode()).hexdigest()

    def get(self, key: str, ttl: int) -> Optional[bytes]:
        """Cached bytes if younger than ttl seconds, else None. ttl=0 disables the cache."""
        p = self._path(key)
        if ttl and p.exists() and time.time() - p.stat().st_mtime < ttl:
            return p.read_bytes()
        return None

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
