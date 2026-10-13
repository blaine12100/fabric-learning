# Sourcing rules (shared)

- Shared by every fabric-learning skill that researches sources (`fabric-learn`, `fabric-catchup`) and by the source research agents.
- Read this file in full before dispatching any research.
- Each skill adds its own rules on top, e.g. freshness in `fabric-learn` and time windows in `fabric-catchup`. Where a skill is stricter, the skill wins.

## Contents
- [1. Citation rules](#1-citation-rules)
- [2. Search hygiene](#2-search-hygiene)
- [3. Sources](#3-sources) (incl. [Running the research](#running-the-research))
- [4. Findings contract](#4-findings-contract)
- [5. Authority](#5-authority)
- [6. Engagement](#6-engagement)
- [7. Release status](#7-release-status)
- [8. Verification](#8-verification)
- [9. Citation format](#9-citation-format)
- [10. Privacy](#10-privacy)

## 1. Citation rules

- **Every factual statement shown to the user needs a citation.**
  - A factual statement is anything about what Fabric does, how a feature behaves, limits, pricing, licensing, release status, dates, what a tool does, or what people have done or reported.
  - Fabric is new and changes fast. An uncited statement may be outdated or wrong, and the user has no way to check it.
- **The model's own knowledge is for structure only:**
  - Ordering, grouping, analogies to the user's background, and deciding what to ask.
  - Never use it as a source of Fabric facts or of what's new. It may be outdated, and "new" is exactly what it can't know.
- **No source, no statement.** Either leave it out or mark it plainly: "unverified — I couldn't find a source".
- **Fetch summaries aren't sources.** A web-fetch summary can paraphrase wrongly (e.g. calling a community library "officially supported"). Base every claim on the page's own words. That's what `quote` is for. Support status comes from the repo README or Microsoft docs, never from a summary.
- **Cite what you actually read.** A blog saying "the docs say X" is a citation to the blog. Cite the docs only if you've seen the docs page.
- **Every factual sentence is cited.** A `[n]` covers its own sentence and the one just before it ("Claim. Detail [1]."), when both come from that source. Anything further back, or after the last `[n]` in a bullet, is uncited. `scripts/check_citations.py` lists every uncited sentence in a draft, and both research skills run it before showing an answer.
- **Attribute community statements to their source.** Write "people on r/MicrosoftFabric report…", "a Microsoft employee answered on the Community forum…". Never state them as plain fact.

## 2. Search hygiene

- Always write **"Microsoft Fabric"** in searches, not just "Fabric". Otherwise results get polluted by Daniel Miessler's `fabric` CLI and the fabric.so app.
- Include **former names** of a feature only when a source confirms the rename, e.g. an official page that says "formerly called…".
- **Strip identifiers** from anything the user pasted (workspace names, IDs, URLs, emails) before using it as a search term.

## 3. Sources

- Each skill decides **which** sources to use and in what order. This section defines **what each source is** and **how it's accessed**.

| Source | What it is | Access | Default authority |
|---|---|---|---|
| **fabric-blog** | The official Microsoft Fabric Updates blog: announcements, monthly feature summaries, event round-ups. blog.fabric.microsoft.com now redirects to the Community site's "Fabric Updates Blog" board, so cite the community.fabric.microsoft.com URL | `scripts/community.py blog` (RSS, full post text) | official |
| **learn-docs** | Microsoft Learn Fabric docs (learn.microsoft.com/fabric), incl. "what's new", troubleshooting and the Fabric roadmap / release plan; the known-issues list now lives at support.fabric.microsoft.com (old Learn URLs redirect there); plus the source repo MicrosoftDocs/fabric-docs, whose commit history shows when a page changed | `scripts/learn.py search` / `page` (Learn's public search API and the page itself: dates and Preview labels); `gh` for fabric-docs commits; web search for the roadmap and known issues | official |
| **learn-training** | Microsoft Learn training for the Fabric certifications: learning paths, modules and exam study guides for **DP-600** (Fabric Analytics Engineer) and **DP-700** (Fabric Data Engineer) | `scripts/learn.py search --type training` and `learn.py exam dp-600` (study guide + Learn catalog of Fabric learning paths) | official |
| **reddit** | r/MicrosoftFabric, plus r/PowerBI and r/dataengineering when relevant | `scripts/reddit.py` (public RSS) | community; expert with flair (see [Authority](#5-authority)) |
| **community-forum** | The Q&A forums and community blogs of the Microsoft Fabric Community site (community.fabric.microsoft.com): threads, accepted solutions, replies from Microsoft employees and Super Users, and community posts about new features | `scripts/community.py search` (RSS, full text) | community; expert with badge |
| **fabric-ideas** | Fabric Ideas, the feature-request board of the Microsoft Fabric Community site (community.fabric.microsoft.com/t5/Fabric-Ideas/…, also reached via ideas.fabric.microsoft.com): ideas with vote counts and a status such as New, Needs Votes, Under Review, Planned, Completed, Declined | `scripts/community.py ideas` (RSS) for the ideas; web search for vote counts and status (see notes) | community (the idea); the **status** is set by Microsoft |
| **youtube** | Fabric videos and their transcripts: Microsoft channels, event sessions, community creators | `scripts/youtube.py` (`yt-dlp`, installed on first use into a private environment) | depends on channel |
| **fabricstack** | fabricstack.dev, a community catalogue of Fabric tools organised by the problem they solve, with category, tags, maintainer, status and date added | `scripts/fabricstack.py` (public JSON API) | community |
| **github** | Community and Microsoft repos for Fabric: tools, libraries, samples, releases and issues. **Open discovery, no fixed repo list** | `scripts/github.py` (`search`, `discover`, `repo`, `issues`, via `gh`) | depends on repo (see [Authority](#5-authority)) |
| **web** | Community blogs, newsletters, conference write-ups | web search + fetch | community; expert for recognised experts with evidence |

### Notes per source
- **Direct access first, web search second.** Every source with a script is reached through it: the scripts return dates, engagement and status labels that search snippets lose. Web search is for:
  - the fallback a script names when it exits 3,
  - sources without a script (community blogs, the roadmap, known issues, Microsoft Q&A),
  - finding things the source's own search misses (try one web search when a script returns nothing relevant).
- **learn access:** `learn.py search` keeps results to Fabric and Power BI docs (or training / credentials with `--type`). `learn.py page URL` gives `ms_date` (last reviewed), `updated` (last published) and `preview`: `title` / `note` mean the page itself is labelled Preview; `mentions` are other sentences that say "preview", usually a sub-feature. Use `--grep TERM` for the paragraphs you need.

- **The three official sources differ:**
  - **learn-docs** is the reference for **current** behaviour, limits and settings. Prefer it when official sources disagree on a current fact.
  - **fabric-blog** is **first to announce**. Use it for what's new and for features the docs don't cover yet.
  - **learn-training:**
    - Gives structured, step-by-step explanations and exercises. These are often the clearest way to teach, and sometimes answer the user's question directly.
    - It can lag behind the product. Check its claims about current behaviour against learn-docs or the blog.
    - If a topic appears in an exam's skills-measured list, say so.
- **fabricstack:**
  - The catalogue proves a tool **exists**. What the tool **does** is cited from the tool's own repo or docs.
  - It's small and curated, so **always follow up with a GitHub search**.
  - If the site is down or its format changes, skip it and rely on GitHub.
- **github: discover, don't track.**
  - Never limit research to a fixed list of repos. The point is to surface tools the user hasn't heard of.
  - Find repos by searching for "Microsoft Fabric" and related terms (e.g. OneLake, Fabric lakehouse, semantic link, Fabric capacity), and the `microsoft-fabric` topic.
  - Also check **every GitHub URL mentioned by other sources** (a tool shared on Reddit, shown in a video or written up on a blog).
  - Judge repos by stars, recent activity, releases and README quality, **relative to their age**: a two-week-old repo with 80★ is notable.
  - **Releases:** report what changed from the release notes or changelog, not just the version number.
- **Community site access (fabric-blog, community-forum, fabric-ideas):**
  - The site's web pages block automated fetching (HTTP 403, checked 2026-10-10), but its **RSS endpoints are open and carry full post text**. `scripts/community.py` uses them.
  - RSS search returns at most ~20 results and ANDs the words. Use **2–4 key words**, not a sentence, and run 2–3 variants rather than one long query.
  - RSS can't page, so forum and Ideas posts from an **older window** (more than a few weeks back) are often out of reach. When a windowed call returns `outside_window` with no results, follow its `note`: a web search with the key words and the month.
  - `community.py` returns a 4,000-character excerpt per post by default. **Monthly feature summaries and event round-ups are 20k–300k characters**, so for those use `--grep <term>` (only the paragraphs mentioning the term) or `--full`. Always read the anchor post in full, or grepped, before citing a specific fact from it.
  - The **Power BI Updates blog** is a separate board. Use `community.py blog --product powerbi` (or `any`).
  - **Dates of re-hosted posts:** older blog posts migrated to the Community site can carry the migration date as their RSS date. If the post body or title shows an earlier date (e.g. "May 2024 Feature Summary"), use that date for freshness and note "re-hosted".
  - RSS has no kudos, accepted-solution flags, vote counts or idea status. When those matter, get them from a web search snippet (`site:community.fabric.microsoft.com`) and quote the snippet.
  - Don't try to get around the block on web pages (other user agents, proxies, caches).
- **Microsoft Q&A** (learn.microsoft.com/answers) is a Microsoft-run Q&A site. Treat it like community-forum: `community`, or `expert` when the answerer shows a Microsoft employee, moderator or MVP badge. Reach it through web search.
- **community-forum:** RSS doesn't show replies or accepted-solution flags. Rank a thread "accepted solution" only when a search snippet or the thread text shows it.
- **community-forum:** an **accepted solution** shows the fix worked for the person who asked. It doesn't show the fix is current or applies to everyone.
- **fabric-ideas: what users are asking for.**
  - An idea shows **demand**, not a feature. Never present an idea as something Fabric does or will do.
  - Its **status** is set by Microsoft, so it carries more weight: "Planned" means Microsoft intends to do it, and "Completed" means Microsoft marked it delivered.
  - Still confirm a "Completed" feature from fabric-blog or learn-docs before calling it released.
  - **Use it for:**
    - **Long-awaited features:** a newly shipped feature that matches a highly voted idea. The vote count and the idea's age show how long people waited.
    - **"Can Fabric do X?" when the answer is no:** an idea for X shows whether it's been requested and how Microsoft has responded. Point the user to it so they can vote.
- **reddit access:**
  - Reddit's JSON API blocks unauthenticated requests. Its RSS feeds work but are rate-limited; `scripts/reddit.py` caches for 3 hours and backs off on HTTP 429.
  - RSS gives titles, text, authors, dates and comment threads, but **no upvote counts**. Use comment count as the engagement signal. When search results show scores, use those.
  - If the script is rate-limited out, fall back to web search. Put "reddit r/MicrosoftFabric" plus 2–4 key words in the **query text**, not in a domain filter (domain filters on reddit.com can be rejected). Try two phrasings.
  - If that finds nothing too, say so in the output ("community reaction unavailable") rather than leaving the gap silent.
- **Source scripts:**
  - Commands show `python3`. If it isn't found (common on Windows), use `python` or `py -3` instead, for every script.
  - All scripts print JSON. **Exit 3** means the source is unavailable, and the output names the fallback (usually a `site:` web search). Use it and carry on.
  - Run them through `scripts/gather.py` (see [Running the research](#running-the-research)), not one by one.
- **Unavailable source:** (Reddit is the usual one; its RSS is rate-limited, and `reddit.py` paces itself to one request every 3 s)
  - If a source fails (site down, rate-limited, tool missing), carry on with the others.
  - Report it in the output only if it leaves a real gap, e.g. "Reddit was unavailable, so community reaction is thin".

### Running the research

- **Bash calls run one at a time in Claude Code; web searches and fetches issued in the same message run in parallel.** So:
  - **Script sources** (community, learn, reddit, fabricstack, youtube, github): one `gather.py` call with a plan covering all of them. They run concurrently, and one call returns everything.

    ```bash
    python3 <skill-base-dir>/../../scripts/gather.py <<'EOF'
    [{"id": "blog",   "script": "community.py", "args": ["blog", "--query", "ontology", "--grep", "ontology"]},
     {"id": "docs",   "script": "learn.py",     "args": ["search", "fabric iq ontology"]},
     {"id": "forum",  "script": "community.py", "args": ["search", "ontology binding", "--board", "forum"]},
     {"id": "reddit", "script": "reddit.py",    "args": ["search", "fabric ontology"]},
     {"id": "yt",     "script": "youtube.py",   "args": ["search", "Fabric IQ ontology", "--limit", "5"]},
     {"id": "gh",     "script": "github.py",    "args": ["search", "ontology"]}]
    EOF
    ```

  - **Web sources** (web, roadmap, known issues, snippet look-ups, script fallbacks): put all the `WebSearch` / `WebFetch` calls in **one message**, so they run in parallel.
  - Do both in the same message where possible.
- **Subagents: decide automatically.** The user never has to ask, and shouldn't have to think about it. Subagents cost a lot (a multi-agent run uses roughly 15× the tokens of a chat: [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)) and they count against the user's session limits, so the default is **none**.
- **Hard limit: 0 to 2 subagents running at any moment.** Never more than 2 in one message, whatever the table says. More work waits for the next wave, or is done inline.

| Situation | What to do |
|---|---|
| Concept, admin setting, how-to, tool lookup, or any question answerable from ≤ 10 tool calls | **Inline.** One `gather.py` call, plus one message of parallel web calls |
| Problem solving while still clarifying with the user | **Inline.** Subagents can't ask questions |
| 3 or more **long documents** must be read in full (videos over 20 min, feature summaries, long threads), and their raw text isn't needed in the answer | Spawn **1 subagent per 1–3 documents**, max 2 |
| Comparison or scenario design with **2 or more independent parts**, each needing ~5 or more tool calls | Spawn **1 subagent per part**, max 2. A third part is researched inline |
| Catch-up over more than 30 days, where the user chose Highlights or Month by month | Spawn **1 subagent per month**, max 2 at a time. More months go in waves |
| Anything that writes the profile or log, asks the user, or verifies the final answer | **Never delegate.** The lead does it |

- **How to spawn:**
  - Use the plugin's `fabric-researcher` agent if it's available: restricted tools, a cheaper model, a 20-turn cap. Otherwise use a general-purpose agent with the same brief.
  - Foreground or background both work. If a subagent runs in the background, research another slice inline meanwhile (that counts towards the 2), and **don't show the answer until every slice is back**.
  - Don't tell the user about tool mechanics (monitors, notifications, background tasks). Progress lines name the content only, e.g. "Still reading September…".
  - Issue all of one wave's subagents in a **single message**, so they run in parallel.
  - Tell the user in one line, e.g. "Reading 3 session recordings in parallel…".
  - One level deep only: subagents never spawn subagents.
- **Briefing a subagent** (each item matters; vague briefs make subagents duplicate work):
  - **Objective:** one sentence, plus the exact window.
  - **Sources and scripts** to use, and which to skip.
  - **Output:** findings-contract JSON only.
  - **Boundaries:** don't write the answer, don't touch the profile or log, ≤ 15 tool calls.
  - **The plugin root path** and any env prefix.
- **When a subagent fails** (rate or session limit, timeout): don't relaunch in parallel. Finish that slice inline, or report it as a gap. A partial answer that says what's missing beats a failed run.
- **The lead always:**
  - Merges and ranks the findings.
  - Spot-checks the claims that matter.
  - Runs `check_citations.py`.
  - Writes the log.

## 4. Findings contract

- Every source returns a list of findings in this shape. The skill discards anything that doesn't conform.

```json
{
  "claim": "One factual statement, as narrow as the quote supports",
  "url": "https://…",
  "title": "Page / post / video / repo title",
  "source": "fabric-blog | learn-docs | learn-training | reddit | community-forum | fabric-ideas | youtube | fabricstack | github | web",
  "authority": "official | expert | community",
  "authority_evidence": "Why this authority, e.g. 'learn.microsoft.com page', 'Reddit Microsoft Employee flair', 'YouTube channel: Microsoft Fabric (official)'",
  "published": "YYYY-MM-DD",
  "engagement": { },
  "status": "preview | ga | deprecated | retired | planned | unknown",
  "quote": "Short verbatim excerpt that supports the claim (≤ 40 words)",
  "timestamp": "mm:ss"
}
```

- Field rules:
  - **Required:** `claim`, `url`, `source`, `authority`, `published`, `quote`.
  - `published`:
    - The date the content was published or last updated (for docs, the "updated" date).
    - Use `"unknown"` only if the page shows no date. Treat undated findings as weaker.
  - `engagement`: see [Engagement](#6-engagement). Empty for official sources.
  - `status`: the release status the source states for the feature the claim is about; `unknown` if it states none.
  - `timestamp`: YouTube only. The point in the video where the claim is made.
  - **One claim per finding.** Split a source that supports several claims into several findings with the same URL.

## 5. Authority

- `official`:
  - fabric-blog, learn-docs and learn-training.
  - Microsoft event sessions on Microsoft channels.
  - Repos for products Microsoft documents on Learn as supported, e.g. the Fabric CLI.
- `expert`:
  - A person with **visible evidence** of their role, e.g.:
    - Reddit "Microsoft Employee" flair.
    - Forum "Microsoft Employee" or "Super User" badge.
    - A YouTube channel or blog About page showing a Microsoft or MVP role.
    - A blog's About page showing MVP status.
  - **Repos under a Microsoft GitHub org that aren't a documented product**, e.g. accelerators and samples published by a Microsoft team. Label these **"Microsoft org, unsupported"** in the output, especially if the README says they're not officially supported.
- `community`: everyone and everything else.
- **Evidence is required.** Record it in `authority_evidence`. No evidence means `community`, however well known the name seems.

## 6. Engagement

- Use each platform's own signals:

| Source | `engagement` fields |
|---|---|
| reddit | `comments` (RSS has no scores); `upvotes` only when a search result shows them |
| community-forum | `kudos`, `replies`, `accepted_solution` (true/false) |
| youtube | `views`, `likes` |
| github | `stars`, `last_commit`, `open_issues`, `latest_release` |
| fabric-ideas | `votes`, `idea_status` (as shown, e.g. Planned, Completed), `posted` (the idea's date, to show how long it has been open) |
| fabricstack, web | whatever the page shows, or `{}` |

- **Compare engagement within a platform, never across platforms.**
  - r/MicrosoftFabric is small: a thread with 40 comments, or 40 upvotes where shown, is a strong signal.
  - A two-week-old repo with 80★ beats a three-year-old repo with 200★ for "new and notable".
- Engagement shows **interest, not correctness.** A popular answer can still be wrong or outdated. Authority and recency still apply.
- **Engagement must never bury new things.** A tool launched last week can't compete on stars, reactions or views with an established one. Judge new items against their age, and give them their own place in the output (each skill says how) rather than ranking them against established items.

## 7. Release status

- Every feature mentioned to the user gets a status label: **Preview**, **GA**, **Deprecated**, **Retired**, **Planned** (roadmap or "coming soon", not yet released, with the timeframe as stated), or **Status not confirmed**.
  - Announced but not yet shipped ("GA coming in November") is **Planned**, whatever the heading says.
  - Tools, packages and community picks have no release status: log them as `n/a`.
- Take the status from the **most authoritative, most recent** source. Statuses change: a feature in preview in an old post may be GA now.
- If the status changed within the material researched, report the latest status and mention the change, e.g. "Preview (Jun) → GA (Sep)".

## 8. Verification

- **Drop** findings without a `url` or a `quote`.
- **The quote must support the claim.** If the claim says more than the quote, cut the claim back to what the quote says, or drop it.
- **Spot-check what matters most.** Fetch the URL yourself for the few claims the output depends on most (each skill says how many) and confirm the page says it. Research can mis-summarise.
- **Surface conflicts, don't resolve them silently.**
  - When sources disagree, especially community vs official, show both with dates and say which is newer.
  - Docs sometimes lag behind reality; Reddit posts sometimes go stale.
- **Thin evidence is reported, not papered over.** Say what couldn't be sourced.

## 9. Citation format

- Cite inline with numbered markers: `… binds entity types to OneLake data [1][3].`
- End every output with a **Sources** list: title — source · authority · engagement · date, then the URL on the next line.

```
Sources
[1] Ontology overview — Microsoft Learn · official · updated Jun 2026
    https://learn.microsoft.com/...
[2] Get started with Fabric IQ — Microsoft Learn training (DP-600 path) · official · updated May 2026
    https://learn.microsoft.com/training/...
[3] "We moved 40 workspaces between F64s – lessons" — r/MicrosoftFabric · community · 23 comments · Mar 2026
    https://reddit.com/r/MicrosoftFabric/...
[4] "Dataflow Gen2 refresh fails: gateway timeout" — Fabric Community forum · expert (Super User), accepted solution · 14 kudos · Aug 2026
    https://community.fabric.microsoft.com/...
[5] <tool name> — GitHub · Microsoft org, unsupported · ★ 412 · last commit Sep 2026
    https://github.com/...
[6] "Fabric IQ deep dive" — YouTube · expert (Microsoft PM) · 18k views · Jul 2026 · at 12:34
    https://youtube.com/watch?v=...&t=754
[7] "Allow X in Y" — Fabric Ideas · Planned · 1,240 votes · open since Mar 2024
    https://community.fabric.microsoft.com/t5/Fabric-Ideas/...
```

- YouTube links include `&t=<seconds>`, so the user lands on the relevant moment.
- Community tools are always marked "not supported by Microsoft".

## 10. Privacy

- Research never needs the user's identity or tenant details. Don't put them in searches or logs.
- Never log pasted error text, workspace names, IDs, URLs from the user's environment, or credentials.
- Logs record **generic** descriptions of what was covered.
