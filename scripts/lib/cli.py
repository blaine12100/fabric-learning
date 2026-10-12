"""The command-line contract every source script follows.

  stdout: one JSON document.   exit 0: OK.   exit 3: source unavailable, JSON names the fallback.
"""
import argparse
import json
import sys

from .errors import SourceUnavailable


def emit(obj, code: int = 0):
    print(json.dumps(obj, indent=2, ensure_ascii=False))
    sys.exit(code)


def fail(msg: str, fallback: str):
    """Exit 3 = source unavailable; the caller should use the fallback (usually web search)."""
    emit({"error": msg, "fallback": fallback}, 3)


def emit_results(source: str, results, limit=None, **meta):
    """The standard result envelope: {"source", ...meta, "count", "results"}."""
    results = list(results)[:limit] if limit else list(results)
    emit({"source": source, **meta, "count": len(results), "results": results})


def parser(doc: str):
    """ArgumentParser with subcommands, showing the script's docstring as help."""
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    return ap, ap.add_subparsers(dest="cmd", required=True)


def add_window(p, since_required: bool = False, until: bool = True):
    p.add_argument("--since", required=since_required, help="YYYY-MM-DD, inclusive")
    if until:
        p.add_argument("--until", help="YYYY-MM-DD, inclusive")


def add_text(p):
    g = p.add_mutually_exclusive_group()
    g.add_argument("--full", action="store_true", help="return the whole text")
    g.add_argument("--grep", help="return only paragraphs mentioning this term")


def add_limit(p, default: int):
    p.add_argument("--limit", type=int, default=default)


def run(commands: dict, args, fallback):
    """Dispatch args.cmd to its handler. Any SourceUnavailable (network, feed format, CLI) becomes exit 3.
    fallback: one string, or {command: string} when commands fall back differently."""
    try:
        commands[args.cmd](args)
    except SourceUnavailable as e:
        fail(str(e), fallback.get(args.cmd, "web search") if isinstance(fallback, dict) else fallback)
