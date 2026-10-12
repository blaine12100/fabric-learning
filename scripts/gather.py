#!/usr/bin/env python3
"""Run several source-script calls concurrently in one go.

Claude Code runs Bash tool calls one after another, so calling five source scripts separately
costs five round-trips in sequence. gather.py takes a plan, runs every call in parallel threads,
and returns all results in one JSON document.

  gather.py < plan.json
  plan.json: [{"id": "blog", "script": "community.py", "args": ["blog", "--since", "2026-09-01"]}, ...]

Allowed scripts: the source scripts registered in lib.SOURCES.
Output: {"<id>": {"ok": true, "result": {...}} | {"ok": false, "error": "...", "fallback": "..."}}
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lib import SOURCES  # noqa: E402

ALLOWED = set(SOURCES)


def run(step):
    sid, script = step.get("id"), step.get("script")
    if script not in ALLOWED:
        return sid, {"ok": False, "error": f"script not allowed: {script}"}
    args = [str(a) for a in step.get("args", [])]
    try:
        r = subprocess.run([sys.executable, str(HERE / script), *args], capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return sid, {"ok": False, "error": "timed out after 300s", "fallback": "web search"}
    try:
        out = json.loads(r.stdout)
    except ValueError:
        return sid, {"ok": False, "error": (r.stderr or r.stdout).strip()[-400:] or f"exit {r.returncode}"}
    if r.returncode == 0:
        return sid, {"ok": True, "result": out}
    return sid, {"ok": False, "error": out.get("error"), "fallback": out.get("fallback")}


def main():
    plan = json.load(sys.stdin)
    if not isinstance(plan, list) or not plan:
        print(json.dumps({"error": "plan must be a non-empty JSON list"}))
        return 2
    ids = [s.get("id") for s in plan]
    if None in ids or len(set(ids)) != len(ids):
        print(json.dumps({"error": "every step needs a unique id"}))
        return 2
    with ThreadPoolExecutor(max_workers=min(8, len(plan))) as ex:
        results = dict(ex.map(run, plan))
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
