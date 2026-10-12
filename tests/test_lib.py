"""Offline tests for the shared library and the citation checker. Run: python3 -m unittest discover tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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
        with tempfile.TemporaryDirectory() as d:
            os.environ["FABRIC_LEARNING_CACHE"] = d
            c = DiskCache("t")
            self.assertIsNone(c.get("k", 60))
            c.put("k", b"v")
            self.assertEqual(c.get("k", 60), b"v")
            self.assertIsNone(c.get("k", 0))  # ttl 0 = no cache


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


if __name__ == "__main__":
    unittest.main()
