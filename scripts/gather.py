#!/usr/bin/env python3
"""Run several source-script calls concurrently in one go.

Claude Code (and Copilot) run Bash tool calls one after another, so calling five source scripts separately
costs five round-trips in sequence. gather.py takes a plan, runs every call in parallel threads,
and returns all results in one JSON document.

  gather.py < plan.json
  plan.json: [{"id": "blog", "script": "community.py", "args": ["blog", "--since", "2026-09-01"]}, ...]

Allowed scripts: the source scripts registered in lib.SOURCES.
Output: {"<id>": {"ok": true, "result": {...}} | {"ok": false, "error": "...", "fallback": "..."}}
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lib import SOURCES  # noqa: E402

ALLOWED = set(SOURCES)


# children print UTF-8 whatever the platform's default encoding (cp1252 on Windows)
CHILD_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def run(step):
    sid, script = step["id"], step.get("script")
    if script not in ALLOWED:
        return sid, {"ok": False, "error": f"script not allowed: {script}"}
    args = step.get("args", [])
    if not isinstance(args, list):
        return sid, {"ok": False, "error": "args must be a list of strings"}
    try:
        r = subprocess.run([sys.executable, str(HERE / script), *map(str, args)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=CHILD_ENV, timeout=300)
    except subprocess.TimeoutExpired:
        return sid, {"ok": False, "error": "timed out after 300s", "fallback": "web search"}
    try:
        out = json.loads(r.stdout)
        if not isinstance(out, dict):
            raise ValueError
    except ValueError:
        return sid, {"ok": False, "error": (r.stderr or r.stdout).strip()[-400:] or f"exit {r.returncode}"}
    if r.returncode == 0:
        return sid, {"ok": True, "result": out}
    return sid, {"ok": False, "error": out.get("error"), "fallback": out.get("fallback")}


def main():
    try:
        plan = json.loads(sys.stdin.read())
    except ValueError as e:
        print(json.dumps({"error": f"plan is not valid JSON: {e}"}))
        return 2
    if not isinstance(plan, list) or not plan or not all(isinstance(s, dict) for s in plan):
        print(json.dumps({"error": "plan must be a non-empty JSON list of step objects"}))
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
