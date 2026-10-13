#!/usr/bin/env python3
"""GitHub discovery for the Microsoft Fabric ecosystem, via the `gh` CLI. Open discovery: no fixed repo list.

  github.py discover --since YYYY-MM-DD [--until YYYY-MM-DD] [--extra "term" ...] [--limit N]
      Two lanes for a time window:
        new_launches: repos CREATED in the window, ranked by stars per day of age
        updates:      established repos with a RELEASE published in the window, ranked by stars
  github.py search QUERY [--limit N]          repos matching a task (tool discovery), ranked by stars and recency
  github.py repo OWNER/NAME                   one repo: stars, last push, licence, latest release, README excerpt
  github.py issues QUERY [--limit N]          issues mentioning a problem in Fabric repos (workarounds)

Output: JSON. Exit 3 means gh is missing or GitHub is unavailable: fall back to web search with site:github.com.
"""
import base64
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import cli  # noqa: E402
from lib.commands import run_cached  # noqa: E402
from lib.errors import CommandError  # noqa: E402
from lib.dates import days_between, in_window, iso_date, today  # noqa: E402
from lib.text import clip  # noqa: E402

FALLBACK = "web search with site:github.com"
TERMS = ['"Microsoft Fabric"', "topic:microsoft-fabric", "OneLake", '"Fabric lakehouse"',
         '"semantic link" fabric', '"Fabric capacity"', '"fabric notebook"']
FIELDS = "fullName,url,description,stargazersCount,createdAt,pushedAt,license,isArchived"


def gh(args, ok_empty=False, ttl=3600):
    """gh with the shared command cache; one 20 s back-off on GitHub's secondary rate limit.
    Raises CommandError (never exits), so it is safe inside threads."""
    return run_cached(["gh", *args], ttl=ttl, timeout=120, ok_empty=ok_empty)


def search_repos(query, extra, limit, sort="stars"):
    out = gh(["search", "repos", query, *extra, "--sort", sort, "--limit", str(limit), "--json", FIELDS])
    return json.loads(out or "[]")


def slim(r):
    return {"repo": r["fullName"], "url": r["url"], "description": r.get("description"),
            "stars": r.get("stargazersCount"), "created": iso_date(r.get("createdAt")),
            "last_push": iso_date(r.get("pushedAt")),
            "license": (r.get("license") or {}).get("key") if r.get("license") else None,
            "microsoft_org": r["fullName"].lower().split("/")[0] in ("microsoft", "microsoftdocs", "azure", "azure-samples")}


def search_terms(terms, extra, failed):
    """search_repos for each term; one failing term (e.g. a secondary rate limit) is noted, not fatal.
    Raises only if every term fails, so the caller falls back as a whole."""
    def one(t):
        try:
            return search_repos(t, extra, 30)
        except CommandError as e:
            failed.append({"term": t, "error": str(e)[-200:]})
            return []
    with ThreadPoolExecutor(3) as ex:
        batches = list(ex.map(one, terms))
    if terms and len(failed) == len(terms):
        raise CommandError(failed[0]["error"])
    return batches


def releases_in_window(repo, since, until):
    out = gh(["api", f"repos/{repo}/releases?per_page=10"], ok_empty=True)
    rel = []
    for r in json.loads(out or "[]"):
        pub = iso_date(r.get("published_at"))
        if pub and in_window(pub, since, until) and not r.get("draft"):
            rel.append({"tag": r.get("tag_name"), "name": r.get("name"), "published": pub,
                        "url": r.get("html_url"), "notes": clip(r.get("body") or "", 1200)})
    return rel


def cmd_discover(a):
    until = a.until or today()
    terms = TERMS + list(a.extra or [])
    # Search API allows ~30 requests/minute; keep concurrency low and lean on the cache.
    failed = []
    created = search_terms(terms, [f"--created={a.since}..{until}"], failed)
    pushed = search_terms(terms, [f"--updated={a.since}..{until}"], failed)
    seen, new = set(), []
    for r in (x for batch in created for x in batch):
        if r["fullName"] in seen or r.get("isArchived") or not is_ms_fabric(r):
            continue
        seen.add(r["fullName"])
        s = slim(r)
        age = max(days_between(s["created"], until), 1)
        s["stars_per_day"] = round((s["stars"] or 0) / age, 2)
        new.append(s)
    new.sort(key=lambda s: (-s["stars_per_day"], -(s["stars"] or 0)))
    established = []
    for r in (x for batch in pushed for x in batch):
        if r["fullName"] in seen or r.get("isArchived") or not is_ms_fabric(r):
            continue
        seen.add(r["fullName"])
        established.append(slim(r))
    established.sort(key=lambda s: -(s["stars"] or 0))
    established = established[: a.check]
    with ThreadPoolExecutor(4) as ex:
        rels = list(ex.map(lambda s: releases_in_window(s["repo"], a.since, until), established))
    updates = [dict(s, releases=r) for s, r in zip(established, rels) if r]
    cli.emit({"source": "github", "window": {"from": a.since, "to": until}, "search_terms": terms,
              **({"failed_searches": failed} if failed else {}),
          "new_launches": new[: a.limit], "updates": updates[: a.limit],
          "note": "Repos pushed in the window without a release are omitted (commits alone are noise). "
                  "Check GitHub URLs mentioned by other sources separately with `repo`."})


STOP = {"the", "and", "for", "with", "how", "can", "does", "tool", "tools", "fabric", "microsoft", "across",
        "between", "from", "into", "that", "this", "any", "there", "allows", "users", "user", "my", "a", "to", "of"}
# Other projects called "fabric" that pollute results.
NOT_MS_FABRIC = ("service fabric", "service-fabric", "servicefabric", "hyperledger", "fabric.js", "fabricjs",
                 "fabricmc", "fabric mod", "minecraft", "fabric loader", "danielmiessler", "fabric patterns")
MS_FABRIC_SIGNALS = ("microsoft fabric", "ms fabric", "onelake", "power bi", "powerbi", "lakehouse", "semantic model",
                     "semantic link", "sempy", "fabric capacity", "fabric workspace", "fabric notebook",
                     "fabric warehouse", "data factory", "fabric api", "fabric rest", "fabric cli", "fuam", "eventhouse",
                     "real-time intelligence", "direct lake", "fabric admin", "fabric tenant")


def is_ms_fabric(r):
    text = f"{r['fullName']} {r.get('description') or ''}".lower().replace("_", " ")
    if any(x in text for x in NOT_MS_FABRIC):
        return False
    owner = r["fullName"].split("/")[0].lower()
    return any(x in text for x in MS_FABRIC_SIGNALS) or (owner in ("microsoft", "microsoftdocs") and "fabric" in text)


def cmd_search(a):
    terms = [w for w in re.findall(r"[a-z0-9-]+", a.query.lower()) if len(w) > 2 and w not in STOP][:5]
    queries = [f"{t} fabric in:name,description" for t in terms] + [f"{' '.join(terms[:2])} topic:microsoft-fabric"]
    with ThreadPoolExecutor(3) as ex:
        batches = list(ex.map(lambda q: search_repos(q, [], 30), queries))
    seen, res = set(), []
    for r in (x for b in batches for x in b):
        if r["fullName"] in seen or r.get("isArchived") or not is_ms_fabric(r):
            continue
        seen.add(r["fullName"])
        s = slim(r)
        text = f"{r['fullName']} {r.get('description') or ''}".lower()
        s["terms_matched"] = [t for t in terms if t[:6] in text]  # crude stem: migrate~migration
        res.append(s)
    res.sort(key=lambda s: (-len(s["terms_matched"]), -(s["stars"] or 0)))
    cli.emit_results("github", res, limit=a.limit, query=a.query, terms=terms,
                     note= "Filtered to Microsoft Fabric repos (Service Fabric, Hyperledger etc. removed). "
                  "Ranked by how many query terms the name/description match, then stars. Verify with `repo` before citing.")


def cmd_repo(a):
    # `gh repo view` names fields differently from `gh search repos`; map them onto the search shape.
    info = json.loads(gh(["repo", "view", a.repo, "--json",
                          "nameWithOwner,url,description,stargazerCount,createdAt,pushedAt,licenseInfo,isArchived,latestRelease"]))
    info["fullName"] = info.pop("nameWithOwner")
    info["stargazersCount"] = info.pop("stargazerCount")
    info["license"] = info.pop("licenseInfo")
    s = slim(info)
    lr = info.get("latestRelease") or {}
    s["latest_release"] = {"tag": lr.get("tagName"), "published": iso_date(lr.get("publishedAt"))} if lr else None
    readme = gh(["api", f"repos/{a.repo}/readme"], ok_empty=True)
    if readme:
        try:
            s["readme_excerpt"] = clip(base64.b64decode(json.loads(readme)["content"]).decode("utf-8", "replace"), 2500)
        except (KeyError, ValueError):
            pass
    cli.emit({"source": "github", "repo": s})


def cmd_issues(a):
    out = gh(["search", "issues", f'{a.query} "fabric"', "--limit", str(a.limit), "--sort", "updated",
              "--json", "title,url,repository,state,updatedAt,commentsCount"])
    res = [{"title": i["title"], "url": i["url"], "repo": i["repository"]["nameWithOwner"], "state": i["state"],
            "updated": iso_date(i["updatedAt"]), "comments": i["commentsCount"]} for i in json.loads(out or "[]")]
    cli.emit_results("github", res, query=a.query)


def main():
    ap, sub = cli.parser(__doc__)
    d = sub.add_parser("discover")
    cli.add_window(d, since_required=True)
    d.add_argument("--extra", action="append")
    cli.add_limit(d, 12)
    d.add_argument("--check", type=int, default=40, help="established repos to check for releases")
    s = sub.add_parser("search")
    s.add_argument("query")
    cli.add_limit(s, 10)
    r = sub.add_parser("repo")
    r.add_argument("repo")
    i = sub.add_parser("issues")
    i.add_argument("query")
    cli.add_limit(i, 10)
    cli.run({"discover": cmd_discover, "search": cmd_search, "repo": cmd_repo, "issues": cmd_issues},
            ap.parse_args(), FALLBACK)


if __name__ == "__main__":
    main()
