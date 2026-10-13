#!/usr/bin/env python3
"""Local state for the fabric-learning plugin: learner profile + learning log.

Data lives in $FABRIC_LEARNING_HOME, or ~/.claude/fabric-learning by default:
  profile.json        learner profile (validated on every write)
  learning-log.jsonl  one JSON object per line: fabric-learn sessions and fabric-catchup digests
  cache/              temporary files (catch-up checkpoints, HTTP cache)

Commands (all output JSON / JSONL on stdout, errors on stderr):
  show [--raw]                 print profile; exit 1 if none, exit 2 if invalid (--raw prints the stored
                               JSON even when invalid, so a single field can be repaired)
  exit codes: 0 OK, 1 no profile, 2 invalid input or state, 4 unexpected error (not "no profile")
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
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b")  # alphabetic TLD: pkg@0.9.1 is a version pin
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:$|T)")
SCOPES = ("since-last-time", "period", "event", "topic-news")
GENERAL_SCOPES = ("since-last-time", "period")
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
    if path.is_dir():
        raise ValidationError(f"{path} is a directory; give a file path")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_text(path: Path) -> str:
    """UTF-8, tolerating the BOM that Windows editors add. Undecodable bytes are a validation problem."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        raise ValidationError(f"{path.name} is not UTF-8 text ({e}); re-save it as UTF-8")


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


def read_log():
    """Return (entries, malformed_lines). Each entry gets a private _line index.
    Malformed lines (unparseable, or missing fields the readers rely on) are skipped here but kept verbatim
    by write_log, so history that can't be read is never dropped."""
    entries, malformed = [], []
    p = log_path()
    if not p.exists():
        return entries, malformed
    # split on \n only: str.splitlines() also splits on U+2028/U+2029/NEL, which can sit raw inside a JSON string
    for i, line in enumerate(read_text(p).split("\n")):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
            if not isinstance(e, dict):
                raise ValueError
            check_shape(e)
        except (ValueError, ValidationError):
            malformed.append(line)
            continue
        e["_line"] = i
        entries.append(e)
    return entries, malformed


def write_log(entries, malformed):
    lines = [json.dumps({k: v for k, v in e.items() if k != "_line"}, ensure_ascii=False) for e in entries]
    lines += malformed  # never drop history we couldn't read
    atomic_write(log_path(), "\n".join(lines) + ("\n" if lines else ""))


# ---------- validation ----------

def is_date(s) -> bool:
    """YYYY-MM-DD, optionally followed by a time ('2026-10-13T08:00:00Z'). Same result on every Python version."""
    if not isinstance(s, str) or not DATE_RE.match(s):
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
    if type(p.get("schema_version")) is not int or p["schema_version"] != SCHEMA_VERSION:
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


def _nonempty_str(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _date_range(v) -> bool:
    return isinstance(v, dict) and is_date(v.get("from")) and is_date(v.get("to")) and v["from"][:10] <= v["to"][:10]


def check_shape(e: dict) -> None:
    """The fields every reader (summary, catchup-state, forget, export) relies on. Also run on each log line."""
    skill = e.get("skill")
    if skill not in SKILLS:
        raise ValidationError(f"skill: must be one of {sorted(SKILLS)}")
    if "ts" in e and not is_date(e["ts"]):
        raise ValidationError("ts: must be an ISO timestamp")
    for key in ("label", "type", "coverage"):
        if key in e and e[key] is not None and not isinstance(e[key], str):
            raise ValidationError(f"{key}: must be a string")
    if skill == "fabric-learn":
        if not _nonempty_str(e.get("topic")):
            raise ValidationError("topic: required for fabric-learn entries")
        if "sources" in e and (not isinstance(e["sources"], list) or not all(isinstance(x, str) for x in e["sources"])):
            raise ValidationError("sources: must be a list of URL strings")
        rel = e.get("related_topics", [])
        if not isinstance(rel, list) or not all(isinstance(r, dict) and _nonempty_str(r.get("topic"))
                                                and _nonempty_str(r.get("url")) for r in rel):
            raise ValidationError("related_topics: must be a list of {topic, url}, each linked from a cited source")
    else:
        if not _date_range(e.get("window")):
            raise ValidationError("window: required for fabric-catchup entries, as {from, to} dates with from <= to")
        if e.get("uncovered") is not None and not _date_range(e["uncovered"]):
            raise ValidationError("uncovered: must be {from, to} dates with from <= to, or omitted")
        items = e.get("items", [])
        if not isinstance(items, list) or not all(isinstance(i, dict) and _nonempty_str(i.get("title"))
                                                  and _nonempty_str(i.get("url")) for i in items):
            raise ValidationError("items: must be a list of {title, url, status}")


def validate_entry(e: dict) -> dict:
    """Everything check_shape checks, plus the rules for new entries (enums, scope, no personal data)."""
    check_shape(e)
    if e["skill"] == "fabric-learn":
        if e.get("status", "unknown") not in ("preview", "ga", "deprecated", "retired", "planned", "unknown"):
            raise ValidationError("status: must be preview, ga, deprecated, retired, planned or unknown")
    elif e.get("scope") not in SCOPES:
        # without a scope, catchup-state can't tell whether this catch-up moves "since last time"
        raise ValidationError(f"scope: required for fabric-catchup entries, one of {', '.join(SCOPES)}")
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
        prof = json.loads(read_text(p))
        if not isinstance(prof, dict):
            raise ValidationError("profile.json must contain a JSON object")
        return validate_profile(prof), None
    except json.JSONDecodeError as e:
        return None, f"profile.json is not valid JSON: {e}"
    except ValidationError as e:
        return None, str(e)


def topic_match(text, t, contains=False) -> bool:
    """Whole-topic match ignoring case/spacing/punctuation; with contains=True, the topic's words anywhere in text."""
    if not contains:
        return norm(t) == norm(text)
    # whole words only, so "AI" doesn't match "domains" or "maintenance"
    return bool(re.search(rf"\b{re.escape(norm(t))}\b", norm(text)))


def entry_matches_topic(e, t, contains=True) -> bool:
    if e.get("skill") == "fabric-learn":
        return topic_match(e.get("topic", ""), t, contains)
    return any(topic_match(i.get("title", ""), t, contains) for i in e.get("items", []))


def d(s):
    return dt.date.fromisoformat(s[:10])


def is_general(e) -> bool:
    """An unfiltered catch-up: the only kind that moves "since last time" or fills an open gap."""
    return e.get("scope") in GENERAL_SCOPES and not e.get("topic")


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
            print(profile_path().read_text(encoding="utf-8-sig", errors="replace"))
        return 2
    if prof is None:
        print("no profile", file=sys.stderr)
        return 1
    print(json.dumps(prof, indent=2, ensure_ascii=False))
    return 0


def cmd_write(args):
    p = read_stdin_json()
    old, existing_err = load_profile()
    if existing_err and not args.replace_invalid:
        raise ValidationError(f"existing profile is invalid ({existing_err}); fix that field, "
                              "or pass --replace-invalid after the user confirms replacing it")
    p.setdefault("schema_version", SCHEMA_VERSION)
    p.setdefault("onboarding_skipped", False)
    for key in ("workloads", "background_fields", "background_platforms", "background_stack",
                "interest_areas", "known_topics", "interests"):
        p.setdefault(key, [])
    if p.get("preferences") is None:
        p["preferences"] = {}
    if not isinstance(p["preferences"], dict):
        raise ValidationError("preferences: must be an object, e.g. {\"depth\": \"examples\"}")
    p["preferences"].setdefault("depth", "examples")
    p["created_at"] = (old or {}).get("created_at") or p.get("created_at") or now_iso()
    p["updated_at"] = now_iso()
    validate_profile(p)
    atomic_write(profile_path(), json.dumps(p, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"written": str(profile_path())}))
    return 0


def cmd_append(args):
    e = read_stdin_json()
    # The helper owns timestamps: a model-written ts is a guess. --keep-ts is for imports/tests only.
    if not (args.keep_ts and e.get("ts")):
        e["ts"] = now_iso()
    validate_entry(e)
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
    entries, malformed = read_log()
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
        # only a general catch-up fills a gap; an event or topic digest covers a slice of the news
        later = [(d(c["window"]["from"]), d(c["window"]["to"])) for c in catch[i + 1:] if is_general(c)]
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
            "first_ts": catch[0].get("ts") if catch else None,
            "last": {"ts": last.get("ts"), "label": last.get("label"), "window": last.get("window")} if last else None,
            "items_shown": sum(len(e.get("items", [])) for e in catch),
            "open_gaps": gaps,
            "items_matching_interests": matching,
        },
        "log_issues": {"malformed_lines": len(malformed)},
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
    general = [e for e in catch if is_general(e)]
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
    entries, malformed = read_log()
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
        write_log(keep, malformed)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cell(v) -> str:
    """Text safe inside a Markdown table cell."""
    return str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")


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
            what = f"{e.get('topic')} ({e.get('type') or ''})"
            srcs = " ".join(f"[{i + 1}]({u})" for i, u in enumerate(e.get("sources", [])))
        else:
            what = f"Catch-up: {e.get('label') or ''} ({e['window']['from']} – {e['window']['to']})"
            srcs = " ".join(f"[{cell(i['title']).replace(']', ')')}]({i['url']})" for i in e.get("items", []))
        lines.append(f"| {e.get('ts', '')[:10]} | {e.get('skill')} | {cell(what)} | {cell(srcs)} |")
    return "\n".join(lines) + "\n"


def cmd_export(args):
    prof, err = load_profile()
    entries, malformed = read_log()
    clean = [{k: v for k, v in e.items() if k != "_line"} for e in entries]
    if args.format == "json":
        doc = {"profile": prof, "log": clean}
        if err:  # an export taken before a delete must not lose an invalid (e.g. hand-edited) profile
            doc.update(profile_error=err, profile_raw=profile_path().read_text(encoding="utf-8-sig", errors="replace"))
        if malformed:
            doc["log_unreadable_lines"] = malformed
        text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    else:
        text = to_markdown(build_summary(), clean, prof)
        if err:
            text += f"\n## Profile could not be read\n\n{err}. Raw file: {profile_path()}\n"
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


def date_arg(s: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""):
        raise argparse.ArgumentTypeError(f"expected a date YYYY-MM-DD, got {s!r}")
    try:
        dt.date.fromisoformat(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))
    return s


def main():
    for stream in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252; profile text can be any language
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
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
    lg.add_argument("--since", type=date_arg)
    lg.add_argument("--last", action="store_true")
    fg = sub.add_parser("forget")
    fg.add_argument("--topic")
    fg.add_argument("--before", type=date_arg)
    fg.add_argument("--contains", action="store_true", help="match the topic's words anywhere, not the whole topic")
    fg.add_argument("--dry-run", action="store_true")
    ex = sub.add_parser("export")
    ex.add_argument("--format", choices=["md", "json"], default="md")
    ex.add_argument("--out", required=True)
    rs = sub.add_parser("reset")
    rs.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    handlers = {"show": cmd_show, "write": cmd_write, "append": cmd_append, "log": cmd_log,
                "summary": cmd_summary, "forget": cmd_forget, "export": cmd_export,
                "reset": cmd_reset, "paths": cmd_paths, "catchup-state": cmd_catchup_state}
    try:
        return handlers[args.cmd](args)
    except ValidationError as e:
        print(f"invalid: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # never exit 1 by accident: the skills read 1 as "no profile" and start onboarding
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
