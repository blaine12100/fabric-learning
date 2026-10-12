"""Exceptions shared by every layer. Each one means "this source can't answer right now"."""


class SourceUnavailable(Exception):
    """The source could not be reached or answered in an unexpected format (blocked, rate-limited, down).
    The script exits 3 and names a fallback, usually a web search."""


class CommandError(SourceUnavailable):
    """An external CLI (gh, yt-dlp) is missing or failed."""
