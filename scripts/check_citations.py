#!/usr/bin/env python3
"""Lint a drafted answer or digest for sentences that state something without a [n] citation.

  check_citations.py < draft.md

Prints JSON: {"uncited": [{"line": N, "text": "..."}], "unused_sources": [n...], "missing_sources": [n...], "ok": bool}

Heuristic: a sentence needs a citation unless it is
  - a heading, a table header/separator, or inside the Sources list or a code block,
  - a question to the user or a suggested prompt (ends with "?", or is in quotes),
  - explicitly marked framing: starts with "Framing:" / "Analogy:" or contains "(no source)" / "unverified",
  - a short label line (< 5 words, or up to 6 words with no closing punctuation, or ending in ":"),
    or a bold-only heading, e.g. "Also new", "**Options**", "Tools & packages",
  - the assistant describing its own process ("I'll check…", "Let me…", "Here's…"),
  - about the user, from their profile ("You already know…", "Coming from Databricks…"),
  - an italic-only metadata line ("*Date: … · Sources checked …*").
A citation covers its own sentence and the one just before it on the same line ("Claim. Detail [1].").
Anything further back, or after the last citation on a line, is flagged.
It can't judge truth. It only makes every unsupported sentence visible, so each one is either cited,
marked as framing, or dropped before the answer is shown.
"""
import json
import re
import sys

CITE = re.compile(r"\[\d+[a-z]?(?:\s*,\s*\d+[a-z]?)*\]")  # [1], [1a], and [1, 3] (the contract is [1][3])
EXEMPT_START = ("framing:", "analogy:", "note:", "tip:", "sources", "not covered", "+", "—", "say ", "ask ",
                # coverage notes and advice to the user, not claims about Fabric
                "thin evidence", "gaps:", "coverage:", "no 🔥", "watch for", "check ", "verify ", "try ", "remember ")
EXEMPT_ANY = ("(no source)", "unverified", "i couldn't find a source", "couldn't find a source",
              "rate-limited", "was unavailable", "not read directly")


ABBREV = re.compile(r"\b(e\.g|i\.e|etc|vs|approx|incl|cf)\.$", re.I)


def sentences(line):
    raw = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])", line)
    parts = []
    for p in raw:  # re-join splits that happened after abbreviations like "e.g."
        if parts and ABBREV.search(parts[-1]):
            parts[-1] += " " + p
        else:
            parts.append(p)
    return [p.strip() for p in parts if p.strip()]


def main():
    text = sys.stdin.read()
    uncited, cited_nums, in_code, in_sources = [], set(), False, False
    listed = set()
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line:
            continue
        if re.match(r"^#*\s*\**\s*sources\s*:?\s*\**\s*:?\s*$", line, re.I):  # Sources, ## Sources:, **Sources:**
            in_sources = True
            continue
        if in_sources and line.startswith("#"):
            in_sources = False  # a heading after the list starts normal text again
        if in_sources:
            m = re.match(r"^[-*]?\s*\[?(\d+[a-z]?)[\].)]", line)  # [1] …, 1. …, - [1] …
            if m:
                listed.add(m.group(1))
            continue
        if re.match(r"^\|?\s*:?-{3,}", line):
            uncited = [u for u in uncited if u["line"] != n - 1]  # the row above was a table header
            continue
        if line.startswith("#"):
            continue
        # bold-only heading lines and digest header lines are labels, not claims
        # italic-only (*…*, no other asterisks) or bold-only lines; a "* " bullet is neither
        if re.match(r"^\*[^*\s][^*]*\*$", line) or re.match(r"^\*\*[^*]+\*\*:?$", line) or re.match(r"^(fabric catch-up|window|scope)\b", line, re.I):
            continue
        for c in CITE.findall(line):
            cited_nums.update(x.strip() for x in c.strip("[]").split(","))
        body = re.sub(r"^[\s>*\-•\d.)|]+", "", line).strip()
        sents = sentences(body)
        for i, s in enumerate(sents):
            low = s.lower().strip("*_ ")
            # a sentence is covered by its own citation or by one on the very next sentence of the same line
            nxt = sents[i + 1] if i + 1 < len(sents) else ""
            if CITE.search(s) or CITE.search(nxt) or len(s.split()) < 5:
                continue
            # titles and section labels: no sentence punctuation and short, or decorated headers
            if (not re.search(r"[.!?]$", s) and (len(s.split()) <= 6 or s.endswith(":"))) or s[:1] in "★↻☐✔◐":
                continue
            if s.endswith("?") or (s[:1] in "\"'“" and s.rstrip()[-1:] in "\"'”"):
                continue
            if low.startswith(EXEMPT_START) or any(x in low for x in EXEMPT_ANY):
                continue
            # the assistant talking about its own process ("I'll check…", "Let me…") isn't a claim about Fabric
            if re.match(r"^(i|i'll|i've|i'm|i'd|let me|quick check|before i|here's|here is|tell me|you already|you know|coming from|since you|from your profile|if you run|next, i could)\b", low):
                continue
            uncited.append({"line": n, "text": s[:200]})
    out = {
        "uncited": uncited,
        # with no Sources list at all, every cited number is missing
        "missing_sources": sorted(cited_nums - listed),
        "unused_sources": sorted(listed - cited_nums),
        "ok": not uncited and not (cited_nums - listed),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
