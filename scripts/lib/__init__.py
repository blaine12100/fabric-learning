"""Shared building blocks for the fabric-learning source scripts. Standard library only (Python 3.9+).

Layers, lowest first:
  config    where data and cache live (env overrides)
  cache     namespaced on-disk cache with a TTL
  fetch     cached GET with retries, JSON fetch, cross-process rate limiting
  commands  cached subprocess runner for CLIs (gh, yt-dlp)
  dates     parse any date format the sources use into ISO; window filtering
  text      HTML to text, clipping, --grep / --full selection
  feeds     RSS 2.0 and Atom parsing into one entry shape
  cli       JSON output, exit codes, shared arguments, and the error-to-fallback runner

A source script is an adapter: it builds URLs or commands for its source, maps responses onto
result dicts, and hands them to `cli.emit_results`. To add a source, see the README's "Adding a source".
"""

# Scripts gather.py may run. A new source script must be added here.
SOURCES = ("community.py", "learn.py", "reddit.py", "fabricstack.py", "youtube.py", "github.py")
