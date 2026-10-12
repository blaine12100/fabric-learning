"""Where the plugin keeps data and cache."""
import os
from pathlib import Path

USER_AGENT = "fabric-learning-plugin/0.1 (learning tool; respects rate limits)"


def data_dir() -> Path:
    """Profile and learning log. FABRIC_LEARNING_HOME overrides ~/.claude/fabric-learning."""
    env = os.environ.get("FABRIC_LEARNING_HOME")
    return Path(env).expanduser() if env else Path.home() / ".claude" / "fabric-learning"


def cache_root() -> Path:
    """HTTP / CLI cache and the yt-dlp environment. FABRIC_LEARNING_CACHE overrides (e.g. to share across test runs)."""
    env = os.environ.get("FABRIC_LEARNING_CACHE")
    return Path(env).expanduser() if env else data_dir() / "cache"
