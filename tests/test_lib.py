"""Offline tests for the shared library and the citation checker. Run: python3 -m unittest discover tests"""
import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.cache import DiskCache  # noqa: E402
from lib.dates import in_window, iso_date  # noqa: E402
from lib.errors import SourceUnavailable  # noqa: E402
from lib.feeds import parse_feed  # noqa: E402
from lib.fetch import clean_url  # noqa: E402
from lib.text import grep_paragraphs, html_meta, html_to_text, select_text  # noqa: E402

RSS = b"""<?xml version="1.0"?><rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
<item><title> Fabric September 2026 Feature Summary </title>
<link>https://community.fabric.microsoft.com/t5/Fabric-Updates-Blog/x/ba-p/1</link>
<pubDate>Mon, 05 Oct 2026 10:00:00 GMT</pubDate><dc:creator>alice</dc:creator>
<description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;</description></item></channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Direct Lake question</title><link href="https://www.reddit.com/r/MicrosoftFabric/comments/abc/"/>
<published>2026-09-30T08:00:00+00:00</published><author><name>/u/bob</name></author>
<content type="html">&lt;p&gt;Body&lt;/p&gt;</content></entry></feed>"""


class Feeds(unittest.TestCase):
    def test_rss(self):
        [e] = parse_feed(RSS)
        self.assertEqual(e["title"], "Fabric September 2026 Feature Summary")
        self.assertEqual(e["published"], "2026-10-05")
        self.assertEqual(e["author"], "alice")
        self.assertEqual(html_to_text(e["html"]), "Hello world")

    def test_atom(self):
        [e] = parse_feed(ATOM)
        self.assertEqual(e["url"], "https://www.reddit.com/r/MicrosoftFabric/comments/abc/")
        self.assertEqual(e["published"], "2026-09-30")
        self.assertEqual(e["author"], "/u/bob")

    def test_not_a_feed(self):
        with self.assertRaises(SourceUnavailable):
            parse_feed(b"<html><body>blocked</body></html>")
        with self.assertRaises(SourceUnavailable):
            parse_feed(b"not xml")


class Dates(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(iso_date("2026-10-05T10:00:00Z"), "2026-10-05")
        self.assertEqual(iso_date("20261005"), "2026-10-05")
        self.assertEqual(iso_date("Mon, 05 Oct 2026 10:00:00 GMT"), "2026-10-05")
        self.assertIsNone(iso_date(""))
        self.assertIsNone(iso_date("soon"))

    def test_window(self):
        self.assertTrue(in_window("2026-10-05", "2026-10-01", "2026-10-31"))
        self.assertTrue(in_window("2026-10-01", "2026-10-01", "2026-10-01"))  # inclusive
        self.assertFalse(in_window("2026-09-30", "2026-10-01"))
        self.assertTrue(in_window(None, "2026-10-01"))  # undated kept


class Text(unittest.TestCase):
    DOC = "Data Engineering\nRuntime 2.0 is now generally available.\nOther\nUnrelated paragraph."

    def test_grep_includes_heading(self):
        self.assertEqual(grep_paragraphs(self.DOC, "runtime"), "Data Engineering\nRuntime 2.0 is now generally available.")

    def test_select(self):
        self.assertEqual(select_text("x " * 10, limit=5), "x x …")
        self.assertEqual(select_text(self.DOC, full=True), self.DOC)

    def test_meta_and_url(self):
        self.assertEqual(html_meta('<meta name="ms.date" content="2026-09-02" />', "ms.date"), "2026-09-02")
        self.assertEqual(clean_url("https://learn.microsoft.com/a/b/?WT.mc_id=api"), "https://learn.microsoft.com/a/b/")


class Cache(unittest.TestCase):
    def test_roundtrip_and_ttl(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"FABRIC_LEARNING_CACHE": d}):
            c = DiskCache("t")
            self.assertIsNone(c.get("k", 60))
            c.put("k", b"v")
            self.assertEqual(c.get("k", 60), b"v")
            self.assertIsNone(c.get("k", 0))  # ttl 0 = no cache
            self.assertIsNone(DiskCache("other").get("k", 60))  # namespaces don't leak into each other


class Citations(unittest.TestCase):
    def check(self, text):
        r = subprocess.run([sys.executable, str(SCRIPTS / "check_citations.py")], input=text, capture_output=True, text=True)
        return json.loads(r.stdout)

    def test_covered_by_next_sentence(self):
        out = self.check("Direct Lake reads Delta tables from OneLake. It avoids import refreshes [1].\n\nSources\n[1] x\n")
        self.assertTrue(out["ok"], out)

    def test_trailing_speculation_flagged(self):
        out = self.check("Direct Lake reads Delta tables [1]. This will probably cause many support tickets.\n\nSources\n[1] x\n")
        self.assertEqual(len(out["uncited"]), 1)

    def test_missing_source(self):
        out = self.check("Direct Lake reads Delta tables from OneLake [2].\n\nSources\n[1] x\n")
        self.assertEqual(out["missing_sources"], ["2"])

    def test_citations_without_any_sources_list_fail(self):
        out = self.check("Direct Lake reads Delta tables from OneLake directly [1].\n")
        self.assertFalse(out["ok"])
        self.assertEqual(out["missing_sources"], ["1"])

    def test_comma_separated_citation(self):
        out = self.check("Lakehouses store tables in Delta format [1, 2].\n\nSources\n[1] x\n[2] y\n")
        self.assertTrue(out["ok"], out)

    def test_adjacent_citations_and_letter_suffix(self):
        out = self.check("Shortcuts reference external data without copying it [1][2b].\n\nSources\n[1] x\n[2b] y\n")
        self.assertTrue(out["ok"], out)

    def test_uncited_bullet_claim_flagged(self):
        out = self.check("- Lakehouses store all tables in Delta Parquet format by default.\n\nSources\n[1] x\n")
        self.assertEqual(len(out["uncited"]), 1)
        self.assertEqual(out["unused_sources"], ["1"])

    def test_code_headings_questions_and_framing_are_exempt(self):
        draft = ("## How Direct Lake works\n"
                 "```\nspark.read.table('sales').write.mode('overwrite').saveAsTable('gold')\n```\n"
                 "Do you want me to compare it with Import mode?\n"
                 "Framing: think of it as Import mode without the refresh step.\n"
                 "It reads Delta tables from OneLake, e.g. tables written by Spark [1].\n\nSources\n[1] x\n")
        out = self.check(draft)
        self.assertTrue(out["ok"], out)

    def test_citation_covers_only_the_sentence_before_it(self):
        out = self.check("Claim one is long enough here. Claim two is also long enough. Claim three [1].\n\nSources\n[1] x\n")
        self.assertEqual([u["text"] for u in out["uncited"]], ["Claim one is long enough here."])


class Gather(unittest.TestCase):
    def gather(self, plan):
        r = subprocess.run([sys.executable, str(SCRIPTS / "gather.py")], input=json.dumps(plan),
                           capture_output=True, text=True, timeout=60)
        return r.returncode, json.loads(r.stdout)

    def test_rejects_scripts_outside_the_allowlist(self):
        code, out = self.gather([{"id": "x", "script": "profile.py", "args": ["delete"]},
                                 {"id": "y", "script": "../../evil.py"}])
        self.assertEqual(code, 0)
        self.assertFalse(out["x"]["ok"])
        self.assertIn("not allowed", out["x"]["error"])
        self.assertFalse(out["y"]["ok"])

    def test_plan_validation(self):
        self.assertEqual(self.gather([])[0], 2)
        self.assertEqual(self.gather({"id": "x"})[0], 2)
        self.assertEqual(self.gather([{"id": "a", "script": "learn.py"}, {"id": "a", "script": "learn.py"}])[0], 2)
        self.assertEqual(self.gather([{"script": "learn.py"}])[0], 2)

    def test_bad_arguments_become_a_failed_step_not_a_crash(self):
        code, out = self.gather([{"id": "bad", "script": "github.py", "args": ["no-such-command"]}])
        self.assertEqual(code, 0)
        self.assertFalse(out["bad"]["ok"])
        self.assertTrue(out["bad"]["error"])


class CliContract(unittest.TestCase):
    def run_cli(self, fallback, cmd="search"):
        from lib import cli

        def boom(_):
            raise SourceUnavailable("HTTP 503")
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit) as ex:
            cli.run({"search": boom, "page": boom}, argparse.Namespace(cmd=cmd), fallback)
        return ex.exception.code, json.loads(buf.getvalue())

    def test_source_unavailable_is_exit_3_with_fallback(self):
        code, out = self.run_cli("web search with site:github.com")
        self.assertEqual(code, 3)
        self.assertEqual(out, {"error": "HTTP 503", "fallback": "web search with site:github.com"})

    def test_per_command_fallback(self):
        self.assertEqual(self.run_cli({"search": "s", "page": "p"}, cmd="page")[1]["fallback"], "p")
        self.assertEqual(self.run_cli({"search": "s"}, cmd="page")[1]["fallback"], "web search")


class Community(unittest.TestCase):
    def finish(self, results, since=None, until=None, limit=20):
        import community
        a = argparse.Namespace(since=since, until=until, grep=None, limit=limit)
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit):
            community.finish(a, "community", results, "https://example/rss")
        return json.loads(buf.getvalue())

    @staticmethod
    def post(title, published, board="Fabric-platform"):
        return {"title": title, "url": f"https://x/t5/{board}/{title}", "board": board, "published": published, "text": "t"}

    def test_window_and_duplicate_reposts(self):
        out = self.finish([self.post("A", "2026-09-10"), self.post("a", "2026-09-10"),  # double-posted
                           self.post("B", "2026-10-02"), self.post("C", None)], "2026-09-01", "2026-09-30")
        self.assertEqual([r["title"] for r in out["results"]], ["A", "C"])  # undated is kept for the caller
        self.assertEqual(out["outside_window"], 1)
        self.assertNotIn("note", out)

    def test_everything_outside_window_explains_itself(self):
        out = self.finish([self.post("B", "2026-10-02")], "2026-09-01", "2026-09-30")
        self.assertEqual(out["count"], 0)
        self.assertIn("web search", out["note"])

    def test_no_window_no_note(self):
        out = self.finish([self.post("B", "2026-10-02")])
        self.assertNotIn("outside_window", out)


class GithubFilter(unittest.TestCase):
    def test_microsoft_fabric_vs_other_fabrics(self):
        from github import is_ms_fabric

        def repo(name, desc=""):
            return {"fullName": name, "description": desc}
        self.assertTrue(is_ms_fabric(repo("alice/fuam-tools", "Monitoring for Microsoft Fabric capacities")))
        self.assertTrue(is_ms_fabric(repo("bob/x", "Load data into a OneLake lakehouse")))
        self.assertTrue(is_ms_fabric(repo("microsoft/fabric-samples", "")))
        self.assertFalse(is_ms_fabric(repo("azure/service-fabric-cli", "Service Fabric cluster tool for Microsoft Fabric fans")))
        self.assertFalse(is_ms_fabric(repo("danielmiessler/fabric", "AI patterns")))
        self.assertFalse(is_ms_fabric(repo("someone/fabric-mod", "Minecraft fabric mod with a lakehouse")))
        self.assertFalse(is_ms_fabric(repo("someone/fabric", "A Python deployment tool")))


class MoreParsing(unittest.TestCase):
    def test_dates_edge_cases(self):
        self.assertEqual(iso_date("2026-09-30T23:30:00-05:00"), "2026-09-30")  # the source's own calendar day
        self.assertEqual(iso_date("Tue, 30 Sep 2026 23:30:00 -0500"), "2026-09-30")
        self.assertIsNone(iso_date("Tue, 99 Foo 2026"))
        self.assertIsNone(iso_date(None))
        self.assertTrue(in_window("2026-09-15", until="2026-09-30"))
        self.assertFalse(in_window("2026-10-01", until="2026-09-30"))

    def test_html_to_text(self):
        self.assertEqual(html_to_text("<p>A</p><script>var x=1</script><style>p{}</style><p>B &amp; C</p>"), "A\nB & C")
        self.assertEqual(html_to_text("&lt;p&gt;escaped&lt;/p&gt;"), "escaped")
        self.assertEqual(html_to_text(None), "")

    def test_clip_keeps_words_whole(self):
        from lib.text import clip
        self.assertEqual(clip("alpha beta gamma", 8), "alpha …")
        self.assertEqual(clip("short", 10), "short")

    def test_feed_entries_missing_fields(self):
        [rss] = parse_feed(b"<rss><channel><item><title>T</title></item></channel></rss>")
        self.assertEqual((rss["url"], rss["published"], rss["html"]), ("", None, ""))
        [atom] = parse_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title>'
                            b'<updated>2026-09-01T00:00:00Z</updated></entry></feed>')
        self.assertIsNone(atom["url"])
        self.assertEqual(atom["published"], "2026-09-01")  # falls back to <updated>

    def test_retry_after_header_forms(self):
        from lib.fetch import _retry_after
        self.assertEqual(_retry_after("7", 2), 7)
        self.assertEqual(_retry_after("Wed, 21 Oct 2026 07:28:00 GMT", 2), 2)  # HTTP-date form: don't crash
        self.assertEqual(_retry_after(None, 4), 4)
        self.assertEqual(_retry_after("-5", 4), 0)

    def test_grep_without_match_is_empty(self):
        self.assertEqual(grep_paragraphs("Nothing relevant here.", "lakehouse"), "")


class CitationGaps(Citations):
    """Claims the checker used to let through, and valid drafts it used to fail."""

    def test_short_unpunctuated_claim_flagged(self):
        out = self.check("- Direct Lake is now generally available in all regions\n\nSources\n[1] x\n")
        self.assertEqual(len(out["uncited"]), 1)

    def test_about_is_not_an_exemption(self):
        out = self.check("About 40 percent of an F64 capacity is reserved for background jobs.\n\nSources\n[1] x\n")
        self.assertEqual(len(out["uncited"]), 1)

    def test_bullet_ending_in_bold_is_not_italic_metadata(self):
        out = self.check("* Direct Lake now supports composite models in **GA**\n\nSources\n[1] x\n")
        self.assertEqual(len(out["uncited"]), 1)

    def test_bold_sources_header_and_numbered_list(self):
        out = self.check("Lakehouse schemas are generally available now [1].\n\n**Sources:**\n1. [Blog](https://x)\n")
        self.assertTrue(out["ok"], out)

    def test_text_after_sources_heading_is_checked(self):
        out = self.check("Schemas are generally available now [1].\n\nSources\n[1] x\n\n## Next steps\n"
                         "OneLake security is rolling out to every region this month.\n")
        self.assertEqual(len(out["uncited"]), 1)

    def test_digest_labels_stay_exempt(self):
        draft = ("Tools & packages\n  New launches\nWhy it matters to you:\n*Date: 13 Oct · Sources checked today*\n"
                 "Lakehouse schemas are GA [1].\n\nSources\n[1] x\n")
        self.assertTrue(self.check(draft)["ok"])


class Profile(unittest.TestCase):
    """profile.py end to end, in a throwaway data directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = {**os.environ, "FABRIC_LEARNING_HOME": self.tmp.name}

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, stdin=None, env=None):
        r = subprocess.run([sys.executable, str(SCRIPTS / "profile.py"), *args], input=stdin, capture_output=True,
                           text=True, encoding="utf-8", env=env or self.env, timeout=60)
        return r.returncode, r.stdout, r.stderr

    def write(self, profile, *flags):
        return self.cli("write", *flags, stdin=json.dumps(profile))

    def append(self, entry, keep_ts=True):
        return self.cli("append", *(["--keep-ts"] if keep_ts else []), stdin=json.dumps(entry))

    def summary(self):
        code, out, err = self.cli("summary")
        self.assertEqual(code, 0, err)
        return json.loads(out)

    @staticmethod
    def learn(topic, ts="2026-09-01T10:00:00Z", **kw):
        return {"skill": "fabric-learn", "ts": ts, "topic": topic, "type": "concept", "status": "ga", **kw}

    @staticmethod
    def catchup(frm, to, scope="since-last-time", ts=None, items=(), **kw):
        return {"skill": "fabric-catchup", "ts": ts or f"{to}T12:00:00Z", "scope": scope, "label": "x",
                "window": {"from": frm, "to": to}, "items": list(items), **kw}

    # --- profile states ---

    def test_no_profile_is_exit_1_and_valid_null(self):
        self.assertEqual(self.cli("show")[0], 1)
        self.assertIsNone(self.summary()["profile"]["valid"])

    def test_write_fills_defaults_and_keeps_created_at(self):
        code, _, err = self.write({"role": "Data engineer"})
        self.assertEqual(code, 0, err)
        first = json.loads(self.cli("show")[1])
        self.assertEqual(first["preferences"], {"depth": "examples"})
        self.write(dict(first, role="Analytics / BI developer"))
        second = json.loads(self.cli("show")[1])
        self.assertEqual(second["created_at"], first["created_at"])
        self.assertEqual(second["role"], "Analytics / BI developer")

    def test_write_rejects_bad_shapes_with_exit_2(self):
        for bad in ({"preferences": "deep"}, {"schema_version": True}, {"workloads": "Spark"},
                    {"known_topics": [{"topic": "Spark", "source": "user"}]},  # no added_at
                    {"interests": [{"topic": "x", "source": "u", "added_at": "2026-10-01garbage"}]}):
            code, _, err = self.write(bad)
            self.assertEqual(code, 2, (bad, err))
        self.assertEqual(self.write({"preferences": None})[0], 0)  # null means "use the default"

    def test_known_and_interest_overlap_rejected(self):
        t = {"topic": "Direct Lake", "source": "user", "added_at": "2026-10-01"}
        self.assertEqual(self.write({"known_topics": [t], "interests": [dict(t, topic="direct-lake")]})[0], 2)

    def test_pii_rules(self):
        topic = {"source": "user", "added_at": "2026-10-01"}
        self.assertEqual(self.write({"known_topics": [dict(topic, topic="mail alice@contoso.com")]})[0], 2)
        self.assertEqual(self.write({"known_topics": [dict(topic, topic="ws 0f8fad5b-d9cb-469f-a165-70867728950e")]})[0], 2)
        self.assertEqual(self.write({"known_topics": [dict(topic, topic="semantic-link-labs@0.9.1")]})[0], 0)  # version pin

    def test_invalid_profile_is_protected(self):
        (self.home / "profile.json").write_text('{"schema_version": 1, "role": 5}', encoding="utf-8")
        code, out, err = self.cli("show", "--raw")
        self.assertEqual(code, 2)
        self.assertIn('"role": 5', out)
        self.assertEqual(self.write({"role": "x"})[0], 2)  # won't overwrite without --replace-invalid
        self.assertEqual(self.write({"role": "x"}, "--replace-invalid")[0], 0)

    def test_bom_and_non_utf8_profiles(self):
        good = {"schema_version": 1, "role": "Data engineer"}
        (self.home / "profile.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(good).encode())  # Notepad BOM
        self.assertEqual(self.cli("show")[0], 0)
        (self.home / "profile.json").write_bytes('{"schema_version": 1, "role": "Ingénieur"}'.encode("latin-1"))
        code, _, err = self.cli("show")
        self.assertEqual(code, 2, err)  # invalid, never "no profile"

    def test_non_ascii_output_on_a_cp1252_pipe(self):
        self.write({"role": "数据工程师 🚀"})
        code, out, err = self.cli("show", env=dict(self.env, PYTHONIOENCODING="cp1252"))
        self.assertEqual(code, 0, err)
        self.assertIn("数据工程师", out)

    # --- learning log ---

    def test_append_stamps_ts_unless_keep_ts(self):
        self.append(self.learn("Direct Lake", ts="1999-01-01"), keep_ts=False)
        [e] = [json.loads(x) for x in self.cli("log")[1].splitlines()]
        self.assertNotEqual(e["ts"][:4], "1999")
        self.assertEqual(self.append(self.learn("Spark", ts="not a date"), keep_ts=False)[0], 0)  # replaced anyway

    def test_append_rejects_entries_readers_would_crash_on(self):
        for bad in (self.learn("x", related_topics=[{"topic": 5, "url": "https://x"}]),
                    self.learn("", ), self.learn("x", status="beta"),
                    self.catchup("2026-09-01", "2026-09-30", items=[{"title": 123, "url": "https://x"}]),
                    self.catchup("2026-09-30", "2026-09-01"),  # reversed window
                    dict(self.catchup("2026-09-01", "2026-09-30"), scope=None)):
            self.assertEqual(self.append(bad)[0], 2, bad)

    def test_unicode_line_separators_survive(self):
        self.append(self.learn("Direct Lake", question="copied from a page\u0085here"))
        self.append(self.learn("Spark"))
        lines = lambda: [x for x in self.cli("log")[1].split("\n") if x]  # noqa: E731 (splitlines() would split U+2028)
        self.assertEqual(len(lines()), 2)
        self.assertEqual(self.summary()["log_issues"]["malformed_lines"], 0)
        self.cli("forget", "--topic", "Spark")
        [e] = [json.loads(x) for x in lines()]
        self.assertEqual(e["question"], "copied from a page\u0085here")

    def test_malformed_lines_are_skipped_but_kept(self):
        self.append(self.learn("Direct Lake"))
        with open(self.home / "learning-log.jsonl", "a", encoding="utf-8") as f:
            f.write("not json\n")
            f.write(json.dumps({"skill": "fabric-catchup", "ts": "2026-09-02"}) + "\n")  # hand-edited, no window
        s = self.summary()
        self.assertEqual(s["log_issues"]["malformed_lines"], 2)
        self.assertEqual(self.cli("catchup-state")[0], 0)
        self.cli("forget", "--topic", "Direct Lake")
        self.assertEqual(self.summary()["log_issues"]["malformed_lines"], 2)  # still there after a rewrite

    def test_forget_matching(self):
        self.append(self.learn("AI"))
        self.append(self.learn("Fabric domains"))
        self.append(self.learn("Spark maintenance jobs"))
        self.append(self.learn("AI functions in notebooks"))
        out = json.loads(self.cli("forget", "--topic", "ai", "--contains", "--dry-run")[1])
        self.assertEqual(out["learn_topics"], ["AI", "AI functions in notebooks"])
        out = json.loads(self.cli("forget", "--topic", "AI", "--dry-run")[1])
        self.assertEqual(out["learn_topics"], ["AI"])
        self.assertEqual(len(self.cli("log")[1].splitlines()), 4)  # dry run removed nothing

    def test_date_arguments_are_validated(self):
        self.append(self.learn("Direct Lake"))
        code, _, err = self.cli("forget", "--before", "Oct 1", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("YYYY-MM-DD", err)
        self.assertEqual(self.cli("log", "--since", "last week")[0], 2)
        out = json.loads(self.cli("forget", "--before", "2026-09-02", "--dry-run")[1])
        self.assertEqual(out["entries_removed"], 1)

    def test_forget_topic_in_catchup_keeps_the_window(self):
        items = [{"title": "Lakehouse schemas GA", "url": "https://a", "status": "ga"},
                 {"title": "Eventhouse update", "url": "https://b", "status": "ga"}]
        self.append(self.catchup("2026-09-01", "2026-09-30", items=items))
        self.cli("forget", "--topic", "lakehouse", "--contains")
        state = json.loads(self.cli("catchup-state")[1])
        self.assertEqual(state["since_last_time_from"], "2026-09-30")
        self.assertEqual([v["title"] for v in state["shown"].values()], ["Eventhouse update"])

    # --- catch-up state and gaps ---

    def test_since_last_time_ignores_event_and_topic_digests(self):
        self.append(self.catchup("2026-09-01", "2026-09-15"))
        self.append(self.catchup("2026-09-28", "2026-10-01", scope="event"))
        self.append(self.catchup("2026-09-01", "2026-10-10", scope="period", topic="Eventhouse"))
        self.assertEqual(json.loads(self.cli("catchup-state")[1])["since_last_time_from"], "2026-09-15")

    def test_open_gaps_closed_only_by_general_catchups(self):
        self.append(self.catchup("2026-06-12", "2026-10-10", uncovered={"from": "2026-06-12", "to": "2026-09-09"}))
        self.append(self.catchup("2026-06-01", "2026-10-12", scope="topic-news", topic="Eventhouse"))
        self.assertEqual(self.summary()["catchup"]["open_gaps"], [{"from": "2026-06-12", "to": "2026-09-09"}])
        self.append(self.catchup("2026-07-01", "2026-07-31", scope="period"))
        self.assertEqual(self.summary()["catchup"]["open_gaps"],
                         [{"from": "2026-06-12", "to": "2026-06-30"}, {"from": "2026-08-01", "to": "2026-09-09"}])

    def test_summary_tandem_view(self):
        self.write({"known_topics": [{"topic": "Direct Lake", "source": "user", "added_at": "2026-08-01"}],
                    "interests": [{"topic": "Eventhouse", "source": "user", "added_at": "2026-08-01"}]})
        self.append(self.learn("Direct Lake", status="preview"))
        self.append(self.learn("OneLake shortcuts", related_topics=[{"topic": "OneLake security", "url": "https://l"}]))
        self.append(self.catchup("2026-09-01", "2026-09-30", ts="2026-10-01T09:00:00Z",
                                 items=[{"title": "Eventhouse endpoint GA", "url": "https://e", "status": "ga"}]))
        s = self.summary()
        self.assertEqual(s["known_topics"][0]["last_status"], "preview")
        self.assertEqual([g["topic"] for g in s["covered_not_known"]], ["OneLake shortcuts"])
        self.assertEqual([r["topic"] for r in s["related_suggestions"]], ["OneLake security"])
        self.assertEqual(s["catchup"]["items_matching_interests"][0]["interests"], ["Eventhouse"])
        self.assertEqual(s["catchup"]["first_ts"], "2026-10-01T09:00:00Z")

    # --- export / reset ---

    def test_export_keeps_an_invalid_profile_and_escapes_tables(self):
        (self.home / "profile.json").write_text('{"schema_version": 1, "role": 5, "known_topics": []}', encoding="utf-8")
        self.append(self.catchup("2026-09-01", "2026-09-30", items=[{"title": "Direct Lake | now GA", "url": "https://x"}]))
        out_json, out_md = self.home / "e.json", self.home / "e.md"
        self.assertEqual(self.cli("export", "--format", "json", "--out", str(out_json))[0], 0)
        doc = json.loads(out_json.read_text(encoding="utf-8"))
        self.assertIn('"role": 5', doc["profile_raw"])
        self.cli("export", "--format", "md", "--out", str(out_md))
        row = [x for x in out_md.read_text(encoding="utf-8").splitlines() if "fabric-catchup" in x][0]
        self.assertEqual(row.count(" | "), 3)  # four cells; the | in the title is escaped

    def test_export_to_a_directory_fails_cleanly(self):
        code, _, err = self.cli("export", "--format", "json", "--out", self.tmp.name)
        self.assertEqual(code, 2, err)
        self.assertEqual(list(self.home.parent.glob(f"{self.home.name}*.tmp")), [])

    def test_reset(self):
        self.write({"role": "x"})
        self.append(self.learn("Spark"))
        self.assertEqual(len(json.loads(self.cli("reset", "--dry-run")[1])["removed"]), 2)
        self.assertTrue((self.home / "profile.json").exists())
        self.cli("reset")
        self.assertEqual(self.cli("show")[0], 1)


class SourceRobustness(unittest.TestCase):
    def test_dropped_connection_is_source_unavailable(self):
        from lib import fetch
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"FABRIC_LEARNING_CACHE": d}), \
                mock.patch.object(fetch, "_read", side_effect=__import__("http.client").client.RemoteDisconnected("x")), \
                mock.patch.object(fetch.time, "sleep"):
            with self.assertRaises(SourceUnavailable):
                fetch.http_get("https://example.invalid/feed", retries=1)

    def test_github_discover_survives_one_failed_term(self):
        import github
        from lib.errors import CommandError

        def fake(q, extra, limit, sort="stars"):
            if "OneLake" in q:
                raise CommandError("gh failed: secondary rate limit")
            return []
        failed = []
        with mock.patch.object(github, "search_repos", side_effect=fake):
            self.assertEqual(github.search_terms(["OneLake", "lakehouse"], [], failed), [[], []])
            self.assertEqual([f["term"] for f in failed], ["OneLake"])
            with self.assertRaises(CommandError):
                github.search_terms(["OneLake"], [], [])

    def test_forum_board_excludes_both_update_blogs(self):
        import community
        self.assertIn("Power-BI-Updates-Blog", community.NOT_FORUM)


if __name__ == "__main__":
    unittest.main()
