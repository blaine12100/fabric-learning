#!/usr/bin/env python3
"""YouTube search and transcripts via yt-dlp. On first use, yt-dlp is installed into a private
virtual environment in the plugin's data directory (no system-wide install).

  youtube.py search QUERY [--limit N] [--recent] [--since YYYY-MM-DD]
  youtube.py transcript URL_OR_ID [--lang en] [--chunk 30]
  youtube.py setup                      # install / update yt-dlp

search -> {"results": [{title, url, channel, published, views, duration}]}
transcript -> {"video": {...}, "segments": [{start, seconds, url, text}]}; each segment URL jumps to that moment.
Exit 3 means YouTube or yt-dlp is unavailable: fall back to web search with site:youtube.com.
"""
import json
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import cli, tools  # noqa: E402
from lib.commands import run_cached  # noqa: E402
from lib.dates import days_between, in_window, iso_date, today  # noqa: E402
from lib.errors import CommandError  # noqa: E402
from lib.fetch import get_json  # noqa: E402

FALLBACK = "web search with site:youtube.com"


def run_json(args, ttl=3600):
    """yt-dlp -J, cached like every other source call. Raises CommandError."""
    out = run_cached([tools.ensure("yt-dlp"), "--no-warnings", "-J", *args], ttl=ttl, timeout=180)
    try:
        return json.loads(out)
    except ValueError:
        raise CommandError("yt-dlp returned no JSON (blocked, or the video is unavailable)")


def mmss(sec):
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def video_info(vid):
    try:
        return run_json([f"https://www.youtube.com/watch?v={vid}", "--skip-download"], ttl=24 * 3600)
    except CommandError:  # one bad video shouldn't sink the search
        return None


def to_result(e):
    return {"title": e.get("title"), "url": f"https://www.youtube.com/watch?v={e.get('id')}",
            "channel": e.get("channel") or e.get("uploader"), "published": iso_date(e.get("upload_date")),
            "views": e.get("view_count"), "likes": e.get("like_count"), "duration": e.get("duration_string")}


def cmd_search(a):
    q = a.query if "fabric" in a.query.lower() else f"Microsoft Fabric {a.query}"
    if a.recent or a.since:
        # YouTube no longer honours "sort by upload date" (sp=CAI%3D) for searches, so use its upload-date
        # *filter* instead (videos only): the smallest of this week / month / year that covers --since.
        # The flat listing has no dates, so fetch details per video in parallel and filter on the real date.
        days = days_between(a.since, today()) if a.since else 7
        sp = "EgQIAxAB" if days <= 7 else "EgQIBBAB" if days <= 31 else "EgQIBRAB"
        url = f"https://www.youtube.com/results?{urllib.parse.urlencode({'search_query': q, 'sp': sp})}"
        flat = run_json([url, "--flat-playlist", "--playlist-end", str(a.limit * 2)])
        ids = [e.get("id") for e in (flat.get("entries") or []) if e and e.get("id") and len(e["id"]) == 11][: a.limit * 2]
        with ThreadPoolExecutor(4) as ex:
            infos = [i for i in ex.map(video_info, ids) if i]
    else:
        data = run_json([f"ytsearch{a.limit}:{q}", "--skip-download", "--ignore-errors"])
        infos = [e for e in (data.get("entries") or []) if e]
    res = [to_result(e) for e in infos]
    if a.since:
        res = [r for r in res if in_window(r["published"], a.since)]
    if a.recent or a.since:
        res.sort(key=lambda r: r["published"] or "", reverse=True)
    cli.emit_results("youtube", res, limit=a.limit, query=q, sorted="newest" if (a.recent or a.since) else "relevance")


def cmd_transcript(a):
    url = a.video if a.video.startswith("http") else f"https://www.youtube.com/watch?v={a.video}"
    info = run_json([url, "--skip-download"])
    tracks = None
    for kind in ("subtitles", "automatic_captions"):
        langs = info.get(kind) or {}
        for lang in [a.lang, f"{a.lang}-orig", f"{a.lang}-US", f"{a.lang}-GB"] + sorted(langs):
            if lang in langs and lang.split("-")[0] == a.lang:
                tracks = langs[lang]
                break
        if tracks:
            break
    if not tracks:
        cli.fail(f"no {a.lang} transcript for {url}", "use the video description, or skip this video")
    j3 = next((t for t in tracks if t.get("ext") == "json3"), None)
    if not j3:
        cli.fail("no json3 transcript track", "skip this video")
    events = get_json(j3["url"], ttl=24 * 3600).get("events", [])
    segs, cur, start = [], [], None
    for ev in events:
        text = "".join(s.get("utf8", "") for s in ev.get("segs") or []).replace("\n", " ").strip()
        if not text:
            continue
        t = ev.get("tStartMs", 0) / 1000
        if start is None:
            start = t
        cur.append(text)
        if t - start >= a.chunk:
            segs.append((start, " ".join(cur)))
            cur, start = [], None
    if cur:
        segs.append((start or 0, " ".join(cur)))
    vid = info.get("id")
    cli.emit({
        "source": "youtube",
        "video": {"title": info.get("title"), "url": url, "channel": info.get("channel"),
                  "published": iso_date(info.get("upload_date")), "views": info.get("view_count"),
                  "likes": info.get("like_count"), "duration": info.get("duration_string")},
        "segments": [{"start": mmss(s), "seconds": int(s),
                      "url": f"https://www.youtube.com/watch?v={vid}&t={int(s)}", "text": txt}
                     for s, txt in segs],
    })


def cmd_setup(a):
    cli.emit({"yt-dlp": tools.install("yt-dlp")})


def main():
    ap, sub = cli.parser(__doc__)
    s = sub.add_parser("search")
    s.add_argument("query")
    cli.add_limit(s, 8)
    s.add_argument("--recent", action="store_true", help="newest first")
    cli.add_window(s, until=False)
    t = sub.add_parser("transcript")
    t.add_argument("video")
    t.add_argument("--lang", default="en")
    t.add_argument("--chunk", type=int, default=30, help="seconds per segment")
    sub.add_parser("setup")
    cli.run({"search": cmd_search, "transcript": cmd_transcript, "setup": cmd_setup}, ap.parse_args(), FALLBACK)


if __name__ == "__main__":
    main()
