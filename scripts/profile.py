#!/usr/bin/env python3
"""Local state for the fabric-learning plugin: learner profile + learning log.

Data lives in $FABRIC_LEARNING_HOME, or ~/.claude/fabric-learning by default:
  profile.json        learner profile (validated on every write)
  learning-log.jsonl  one JSON object per line: fabric-learn sessions and fabric-catchup digests
  cache/              temporary files (catch-up checkpoints, HTTP cache)

Commands (all output JSON / JSONL on stdout, errors on stderr):
  show [--raw]                 print profile; exit 1 if none, exit 2 if invalid (--raw prints the stored
                               JSON even when invalid, so a single field can be repaired)
  write [--replace-invalid] < profile.json
                               validate and write the profile atomically; refuses to overwrite
                               an existing invalid profile unless --replace-invalid
  append [--keep-ts] < entry.json
                               validate and append one log entry; the helper stamps ts
  log [--skill S] [--topic T] [--since DATE] [--last]
  summary                      aggregate view used by fabric-progress
  catchup-state                where "since last time" starts + every item URL already shown
  forget (--topic T [--contains] | --before DATE) [--dry-run]
  export --format md|json --out PATH
  reset [--dry-run]
  paths
Standard library only.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.config import data_dir  # noqa: E402

SCHEMA_VERSION = 1
SKILLS = {"fabric-learn", "fabric-catchup"}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
GUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")


class ValidationError(Exception):
    pass


# ---------- paths and IO ----------

def profile_path() -> Path:
    return data_dir() / "profile.json"


def log_path() -> Path:
    return data_dir() / "learning-log.jsonl"


def cache_dir() -> Path:
    return data_dir() / "cache"


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today() -> str:
    return dt.date.today().isoformat()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def read_stdin_json():
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValidationError("expected a JSON object on stdin, got nothing")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValidationError(f"stdin is not valid JSON: {e}")
    if not isinstance(obj, dict):
        raise ValidationError("expected a JSON object on stdin")
    return obj


_MALFORMED = []  # raw lines that couldn't be parsed; preserved verbatim on rewrite


def read_log():
    """Return (entries, malformed_count). Each entry gets a private _line index."""
    entries, bad = [], 0
    _MALFORMED.clear()
    p = log_path()
    if not p.exists():
        return entries, bad
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
            if not isinstance(e, dict):
                raise ValueError
            e["_line"] = i
            entries.append(e)
        except ValueError:
            bad += 1
            _MALFORMED.append(line)
    return entries, bad


def write_log(entries):
    lines = [json.dumps({k: v for k, v in e.items() if k != "_line"}, ensure_ascii=False) for e in entries]
    lines += _MALFORMED  # never drop history we couldn't read
    atomic_write(log_path(), "\n".join(lines) + ("\n" if lines else ""))


# ---------- validation ----------

def is_date(s) -> bool:
    if not isinstance(s, str):
        return False
    try:
        dt.date.fromisoformat(s[:10])
        return True
    except ValueError:
        return False


def check_pii(obj, where="") -> None:
    """Reject emails and GUIDs (tenant/workspace IDs) anywhere in the data. URLs in sources are allowed GUIDs."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            check_pii(v, f"{where}.{k}" if where else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_pii(v, f"{where}[{i}]")
    elif isinstance(obj, str):
        is_url = obj.startswith("http://") or obj.startswith("https://")
        if EMAIL_RE.search(obj) and not is_url:
            raise ValidationError(f"{where}: looks like an email address; personal data must not be stored")
        if GUID_RE.search(obj) and not is_url:
            raise ValidationError(f"{where}: looks like a tenant/workspace ID (GUID); identifiers must not be stored")


def _str_list(p, key):
    v = p.get(key, [])
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ValidationError(f"{key}: must be a list of strings")


def _topic_list(p, key):
    v = p.get(key, [])
    if not isinstance(v, list):
        raise ValidationError(f"{key}: must be a list")
    seen = set()
    for i, t in enumerate(v):
        if not isinstance(t, dict):
            raise ValidationError(f"{key}[{i}]: must be an object with topic, source, added_at")
        if not isinstance(t.get("topic"), str) or not t["topic"].strip():
            raise ValidationError(f"{key}[{i}].topic: must be a non-empty string")
        if not isinstance(t.get("source"), str) or not t["source"].strip():
            raise ValidationError(f"{key}[{i}].source: must be a non-empty string")
        if not is_date(t.get("added_at")):
            raise ValidationError(f"{key}[{i}].added_at: must be a date YYYY-MM-DD")
        n = norm(t["topic"])
        if n in seen:
            raise ValidationError(f"{key}[{i}].topic: duplicate of an earlier entry ('{t['topic']}')")
        seen.add(n)


def validate_profile(p: dict) -> dict:
    if p.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError(f"schema_version: must be {SCHEMA_VERSION}")
    if not isinstance(p.get("onboarding_skipped", False), bool):
        raise ValidationError("onboarding_skipped: must be true or false")
    for key in ("role", "experience"):
        if key in p and p[key] is not None and not isinstance(p[key], str):
            raise ValidationError(f"{key}: must be a string")
    for key in ("workloads", "background_fields", "background_platforms", "background_stack", "interest_areas"):
        _str_list(p, key)
    prefs = p.get("preferences", {})
    if not isinstance(prefs, dict) or not isinstance(prefs.get("depth", "examples"), str):
        raise ValidationError("preferences.depth: must be a string")
    _topic_list(p, "known_topics")
    _topic_list(p, "interests")
    known = {norm(t["topic"]) for t in p.get("known_topics", [])}
    for t in p.get("interests", []):
        if norm(t["topic"]) in known:
            raise ValidationError(f"interests: '{t['topic']}' is also in known_topics; a topic can only be in one list")
    for key in ("created_at", "updated_at"):
        if key in p and not is_date(p[key]):
            raise ValidationError(f"{key}: must be an ISO timestamp")
    check_pii(p)
    return p


def validate_entry(e: dict) -> dict:
    skill = e.get("skill")
    if skill not in SKILLS:
        raise ValidationError(f"skill: must be one of {sorted(SKILLS)}")
    if "ts" in e and not is_date(e["ts"]):
        raise ValidationError("ts: must be an ISO timestamp")
    if skill == "fabric-learn":
        if not isinstance(e.get("topic"), str) or not e["topic"].strip():
            raise ValidationError("topic: required for fabric-learn entries")
        if "sources" in e and (not isinstance(e["sources"], list) or not all(isinstance(x, str) for x in e["sources"])):
            raise ValidationError("sources: must be a list of URL strings")
        rel = e.get("related_topics", [])
        if not isinstance(rel, list) or not all(isinstance(r, dict) and r.get("topic") and r.get("url") for r in rel):
            raise ValidationError("related_topics: must be a list of {topic, url}, each linked from a cited source")
        if e.get("status", "unknown") not in ("preview", "ga", "deprecated", "retired", "planned", "unknown"):
            raise ValidationError("status: must be preview, ga, deprecated, retired, planned or unknown")
    else:
        w = e.get("window")
        if not isinstance(w, dict) or not is_date(w.get("from")) or not is_date(w.get("to")):
            raise ValidationError("window: required for fabric-catchup entries, as {from, to} dates")
        if "uncovered" in e and e["uncovered"] is not None:
            u = e["uncovered"]
            if not isinstance(u, dict) or not is_date(u.get("from")) or not is_date(u.get("to")):
                raise ValidationError("uncovered: must be {from, to} dates or omitted")
        items = e.get("items", [])
        if not isinstance(items, list) or not all(isinstance(i, dict) and i.get("title") and i.get("url") for i in items):
            raise ValidationError("items: must be a list of {title, url, status}")
    check_pii(e)
    return e


# ---------- helpers ----------

def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def load_profile():
    """Return (profile or None, error or None)."""
    p = profile_path()
    if not p.exists():
        return None, None
    try:
        prof = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(prof, dict):
            raise ValidationError("profile.json must contain a JSON object")
        return validate_profile(prof), None
    except json.JSONDecodeError as e:
        return None, f"profile.json is not valid JSON: {e}"
    except ValidationError as e:
        return None, str(e)


def topic_match(text, t, contains=False) -> bool:
    """Whole-topic match ignoring case/spacing/punctuation; substring match only if contains=True."""
    return (norm(t) in norm(text)) if contains else norm(t) == norm(text)


def entry_matches_topic(e, t, contains=True) -> bool:
    if e.get("skill") == "fabric-learn":
        return topic_match(e.get("topic", ""), t, contains)
    return any(topic_match(i.get("title", ""), t, contains) for i in e.get("items", []))


def d(s):
    return dt.date.fromisoformat(s[:10])


def subtract_intervals(gap, covers):
    """Remove covered date ranges from a gap. All are (date, date) inclusive."""
    parts = [gap]
    for c0, c1 in covers:
        nxt = []
        for p0, p1 in parts:
            if c1 < p0 or c0 > p1:
                nxt.append((p0, p1))
                continue
            if c0 > p0:
                nxt.append((p0, c0 - dt.timedelta(days=1)))
            if c1 < p1:
                nxt.append((c1 + dt.timedelta(days=1), p1))
        parts = nxt
    return parts


# ---------- commands ----------

def cmd_show(args):
    prof, err = load_profile()
    if err:
        print(err, file=sys.stderr)
        if getattr(args, "raw", False):
            print(profile_path().read_text(encoding="utf-8"))
        return 2
    if prof is None:
        print("no profile", file=sys.stderr)
        return 1
    print(json.dumps(prof, indent=2, ensure_ascii=False))
    return 0


def cmd_write(args):
    p = read_stdin_json()
    _, existing_err = load_profile()
    if existing_err and not args.replace_invalid:
        raise ValidationError(f"existing profile is invalid ({existing_err}); fix that field, "
                              "or pass --replace-invalid after the user confirms replacing it")
    p.setdefault("schema_version", SCHEMA_VERSION)
    p.setdefault("onboarding_skipped", False)
    for key in ("workloads", "background_fields", "background_platforms", "background_stack",
                "interest_areas", "known_topics", "interests"):
        p.setdefault(key, [])
    p.setdefault("preferences", {}).setdefault("depth", "examples")
    old, _ = load_profile()
    p["created_at"] = (old or {}).get("created_at") or p.get("created_at") or now_iso()
    p["updated_at"] = now_iso()
    validate_profile(p)
    atomic_write(profile_path(), json.dumps(p, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"written": str(profile_path())}))
    return 0


def cmd_append(args):
    e = validate_entry(read_stdin_json())
    # The helper owns timestamps: a model-written ts is a guess. --keep-ts is for imports/tests only.
    if not (args.keep_ts and e.get("ts")):
        e["ts"] = now_iso()
    log_path().parent.mkdir(parents=True, exist_ok=True)
    with open(log_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(json.dumps({"appended": str(log_path())}))
    return 0


def filtered(args):
    entries, _ = read_log()
    out = []
    for e in entries:
        if args.skill and e.get("skill") != args.skill:
            continue
        if args.since and (not is_date(e.get("ts")) or e["ts"][:10] < args.since):
            continue
        if getattr(args, "topic", None) and not entry_matches_topic(e, args.topic, contains=True):
            continue
        out.append(e)
    return out


def cmd_log(args):
    out = filtered(args)
    if args.last:
        out = out[-1:]
    for e in out:
        print(json.dumps({k: v for k, v in e.items() if k != "_line"}, ensure_ascii=False))
    return 0


def build_summary():
    prof, err = load_profile()
    entries, bad = read_log()
    learn = [e for e in entries if e.get("skill") == "fabric-learn"]
    catch = [e for e in entries if e.get("skill") == "fabric-catchup"]

    by_topic = {}
    for e in learn:
        n = norm(e.get("topic", ""))
        g = by_topic.setdefault(n, {"topic": e["topic"], "sessions": 0, "related_topics": []})
        g.update(topic=e["topic"], last_ts=e.get("ts"), type=e.get("type"), status=e.get("status"))
        for r in e.get("related_topics", []):
            r = r if isinstance(r, dict) else {"topic": r, "url": None}
            if all(norm(x["topic"]) != norm(r["topic"]) for x in g["related_topics"]):
                g["related_topics"].append(r)
        g["sessions"] += 1

    raw = prof or {}
    known = [dict(t, last_status=by_topic.get(norm(t["topic"]), {}).get("status"),
                  last_covered=by_topic.get(norm(t["topic"]), {}).get("last_ts"))
             for t in raw.get("known_topics", [])]
    known_n = {norm(t["topic"]) for t in known}
    interests = [dict(t, covered=norm(t["topic"]) in by_topic) for t in raw.get("interests", [])]
    covered_not_known = sorted((g for n, g in by_topic.items() if n not in known_n),
                               key=lambda g: g.get("last_ts") or "", reverse=True)
    # Related topics from ANY session (cited links), minus what's already known or covered.
    related, seen_rel = [], set()
    for n, g in by_topic.items():
        for r in g["related_topics"]:
            rn = norm(r["topic"])
            if rn in known_n or rn in by_topic or rn in seen_rel:
                continue
            seen_rel.add(rn)
            related.append({"topic": r["topic"], "url": r.get("url"), "from_topic": g["topic"], "from_ts": g.get("last_ts")})

    gaps = []
    for i, e in enumerate(catch):
        u = e.get("uncovered")
        if not u:
            continue
        later = [(d(c["window"]["from"]), d(c["window"]["to"])) for c in catch[i + 1:]]
        for g0, g1 in subtract_intervals((d(u["from"]), d(u["to"])), later):
            gaps.append({"from": g0.isoformat(), "to": g1.isoformat()})

    last = catch[-1] if catch else None
    interest_n = [norm(t["topic"]) for t in raw.get("interests", [])]
    matching = []
    for e in catch:
        for it in e.get("items", []):
            title_n = norm(it.get("title", ""))
            hits = [t["topic"] for t, n in zip(raw.get("interests", []), interest_n)
                    if re.search(rf"\b{re.escape(n)}\b", title_n)]
            if hits:
                matching.append({"title": it["title"], "url": it["url"], "status": it.get("status"),
                                 "shown_on": (e.get("ts") or "")[:10], "interests": hits})
    return {
        "paths": {"dir": str(data_dir()), "profile": str(profile_path()), "log": str(log_path())},
        "profile": {
            # valid is null when there is no profile, so "missing" is never mistaken for "invalid"
            "exists": profile_path().exists(),
            "valid": None if not profile_path().exists() else err is None, "error": err,
            "onboarding_skipped": raw.get("onboarding_skipped", False),
            "created_at": raw.get("created_at"), "updated_at": raw.get("updated_at"),
            "role": raw.get("role"), "experience": raw.get("experience"),
            "workloads": raw.get("workloads", []), "background_fields": raw.get("background_fields", []),
            "background_platforms": raw.get("background_platforms", []),
            "background_stack": raw.get("background_stack", []),
            "depth": raw.get("preferences", {}).get("depth"), "interest_areas": raw.get("interest_areas", []),
        },
        "known_topics": known,
        "interests": interests,
        "covered_not_known": covered_not_known,
        "related_suggestions": related,
        "learn": {"sessions": len(learn), "first_ts": learn[0].get("ts") if learn else None,
                  "last_ts": learn[-1].get("ts") if learn else None},
        "catchup": {
            "count": len(catch),
            "last": {"ts": last.get("ts"), "label": last.get("label"), "window": last.get("window")} if last else None,
            "items_shown": sum(len(e.get("items", [])) for e in catch),
            "open_gaps": gaps,
            "items_matching_interests": matching,
        },
        "log_issues": {"malformed_lines": bad},
    }


def cmd_summary(_):
    print(json.dumps(build_summary(), indent=2, ensure_ascii=False))
    return 0


def cmd_catchup_state(_):
    entries, _ = read_log()
    catch = [e for e in entries if e.get("skill") == "fabric-catchup"]
    # Key by URL + title: one monthly feature summary (one URL) anchors many separate items.
    shown = {}
    for e in catch:
        for it in e.get("items", []):
            shown[f"{it['url']} | {norm(it.get('title', ''))}"] = {
                "url": it["url"], "title": it.get("title"), "status": it.get("status"),
                "shown_on": (e.get("ts") or "")[:10]}
    # Only unfiltered catch-ups move "since last time": an event or topic-news digest covers a slice of the
    # news, so starting the next general catch-up after it would skip everything else.
    general = [e for e in catch if e.get("scope") in ("since-last-time", "period") and not e.get("topic")]
    starts = [e["window"]["to"] for e in general]
    print(json.dumps({
        "catchups": len(catch),
        "since_last_time_from": max(starts) if starts else None,
        "last": {k: catch[-1].get(k) for k in ("ts", "label", "scope", "window", "coverage")} if catch else None,
        "shown": shown,
    }, indent=2, ensure_ascii=False))
    return 0


def cmd_forget(args):
    if not args.topic and not args.before:
        raise ValidationError("forget needs --topic or --before")
    entries, _ = read_log()
    keep, removed_entries, removed_items = [], [], []
    for e in entries:
        if args.before and is_date(e.get("ts")) and e["ts"][:10] < args.before:
            removed_entries.append(e)
            continue
        if args.topic and e.get("skill") == "fabric-learn" and entry_matches_topic(e, args.topic, args.contains):
            removed_entries.append(e)
            continue
        if args.topic and e.get("skill") == "fabric-catchup":
            # Remove only the matching items; keep the entry so catch-up windows stay intact.
            hit = [i for i in e.get("items", []) if topic_match(i.get("title", ""), args.topic, args.contains)]
            if hit:
                removed_items.extend({"title": i["title"], "catchup_ts": e.get("ts")} for i in hit)
                e = dict(e, items=[i for i in e["items"] if i not in hit])
        keep.append(e)
    report = {
        "dry_run": args.dry_run,
        "entries_removed": len(removed_entries),
        "catchup_entries_removed": sum(1 for e in removed_entries if e.get("skill") == "fabric-catchup"),
        "date_range": [min((e.get("ts", "") for e in removed_entries), default=None),
                       max((e.get("ts", "") for e in removed_entries), default=None)],
        "learn_topics": sorted({e["topic"] for e in removed_entries if e.get("skill") == "fabric-learn"}),
        "catchup_items_removed": removed_items,
    }
    if not args.dry_run:
        write_log(keep)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def to_markdown(s, entries, prof):
    lines = [f"# Fabric learning progress — exported {today()}", ""]
    p = s["profile"]
    if prof:
        lines += ["## Profile", "",
                  f"- Role: {p['role'] or '—'} · Experience: {p['experience'] or '—'} · Depth: {p['depth']}",
                  f"- Workloads: {', '.join(p['workloads']) or '—'}",
                  f"- Coming from: {', '.join(p['background_fields'] + p['background_platforms'] + p['background_stack']) or '—'}",
                  ""]
    lines += ["## Known topics", ""] + [f"- {t['topic']} — {t['source']} · {t['added_at']}" for t in s["known_topics"]] + [""]
    lines += ["## Want to learn", ""] + [f"- {t['topic']} — added {t['added_at']}" for t in s["interests"]] + [""]
    lines += ["## History", "", "| Date | Skill | What | Sources |", "|---|---|---|---|"]
    for e in entries:
        if e.get("skill") == "fabric-learn":
            what = f"{e.get('topic')} ({e.get('type', '')})"
            srcs = " ".join(f"[{i + 1}]({u})" for i, u in enumerate(e.get("sources", [])))
        else:
            what = f"Catch-up: {e.get('label', '')} ({e['window']['from']} – {e['window']['to']})"
            srcs = " ".join(f"[{i['title']}]({i['url']})" for i in e.get("items", []))
        lines.append(f"| {e.get('ts', '')[:10]} | {e.get('skill')} | {what} | {srcs} |")
    return "\n".join(lines) + "\n"


def cmd_export(args):
    prof, _ = load_profile()
    entries, _ = read_log()
    clean = [{k: v for k, v in e.items() if k != "_line"} for e in entries]
    if args.format == "json":
        text = json.dumps({"profile": prof, "log": clean}, indent=2, ensure_ascii=False) + "\n"
    else:
        text = to_markdown(build_summary(), clean, prof)
    out = Path(args.out).expanduser()
    atomic_write(out, text)
    print(json.dumps({"exported": str(out.resolve()), "entries": len(clean)}))
    return 0


def cmd_reset(args):
    targets = [p for p in (profile_path(), log_path(), cache_dir()) if p.exists()]
    if not args.dry_run:
        for p in targets:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    print(json.dumps({"dry_run": args.dry_run, "removed": [str(p) for p in targets]}, indent=2))
    return 0


def cmd_paths(_):
    print(json.dumps({"dir": str(data_dir()), "profile": str(profile_path()),
                      "log": str(log_path()), "cache": str(cache_dir())}, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("summary", "paths", "catchup-state"):
        sub.add_parser(name)
    ap_ = sub.add_parser("append")
    ap_.add_argument("--keep-ts", action="store_true", help="keep the entry's own ts (imports/tests only)")
    sh = sub.add_parser("show")
    sh.add_argument("--raw", action="store_true")
    wr = sub.add_parser("write")
    wr.add_argument("--replace-invalid", action="store_true")
    lg = sub.add_parser("log")
    lg.add_argument("--skill", choices=sorted(SKILLS))
    lg.add_argument("--topic")
    lg.add_argument("--since")
    lg.add_argument("--last", action="store_true")
    fg = sub.add_parser("forget")
    fg.add_argument("--topic")
    fg.add_argument("--before")
    fg.add_argument("--contains", action="store_true", help="substring match instead of whole topic")
    fg.add_argument("--dry-run", action="store_true")
    ex = sub.add_parser("export")
    ex.add_argument("--format", choices=["md", "json"], default="md")
    ex.add_argument("--out", required=True)
    rs = sub.add_parser("reset")
    rs.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if getattr(args, "skill", None) is None and args.cmd == "log":
        args.skill = None
    handlers = {"show": cmd_show, "write": cmd_write, "append": cmd_append, "log": cmd_log,
                "summary": cmd_summary, "forget": cmd_forget, "export": cmd_export,
                "reset": cmd_reset, "paths": cmd_paths, "catchup-state": cmd_catchup_state}
    try:
        return handlers[args.cmd](args)
    except ValidationError as e:
        print(f"invalid: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
