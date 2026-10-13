---
name: fabric-catchup
description: >-
  Builds a cited, personalised digest of what's new across the whole Microsoft Fabric ecosystem: official
  announcements, releases and preview-to-GA changes, new and updated community tools and packages (GitHub,
  fabricstack.dev, e.g. semantic-link-labs releases), popular community discussions, long-requested Fabric Ideas
  and videos. Use this whenever the user wants to catch up or keep up: what's new in Fabric, catch me up, what
  did I miss since last time or over the summer, what happened in September, what was announced at FabCon or
  Ignite, any new community tools, anything new in Power BI or Real-Time Intelligence lately, or asks about
  recent releases, feature summaries or an event, even without saying digest. Remembers what it already showed
  and picks up where the last catch-up ended. Not for explaining one topic in depth (fabric-learn) and never
  acts on a Fabric tenant; learning only. Not Daniel Miessler's fabric CLI or Azure Service Fabric.
---

# Fabric catch-up

## Purpose

- Help the user keep up with the **whole Microsoft Fabric ecosystem**, official and community, without reading everything themselves.
  - A big event like FabCon produces dozens of blog posts, hundreds of Reddit comments, hours of video, and new tools on GitHub. No one can follow all of it.
- Cover three groups of updates:
  - **Official:** what Microsoft announced, released or changed.
  - **Tools & packages:** new releases of existing libraries and tools, and newly launched community tools, found by **open discovery** rather than a fixed list, so tools the user has never heard of can surface.
  - **Community:** what practitioners are saying, building and running into, on Reddit, YouTube, blogs and the Community forum. Fabric Ideas shows which changes the community has been **asking for**.
  - A digest built only from blog posts misses half of what a Fabric practitioner needs to know.
- This skill:
  - Gathers what changed.
  - Merges duplicates across sources into single items.
  - Ranks the items by relevance to **this** user.
  - Cites every one.
- A digest is for **scanning**. Each item is short, and the user can ask `fabric-learn` to go deep on any of them.
- This plugin is **for learning only**. It never connects to, creates, changes or queries anything in the user's Fabric tenant, and never offers to.

## Ground rules

- **Read the shared sourcing rules first:** `<skill-base-dir>/../../references/sourcing-rules.md` ([sourcing-rules.md](../../references/sourcing-rules.md)).
  - They define the citation rules, sources, findings contract, authority, engagement, release status, verification, citation format and privacy.
  - They apply in full to this skill.
- **On top of the shared rules,** this skill adds:
  - **Who can confirm what:**
    - **A Fabric feature** is "announced" or "released" only if an official source says so: the Fabric blog, Learn docs, the Fabric roadmap, or Microsoft's own event pages and sessions.
      - Community posts about unannounced features are labelled **"unconfirmed — community report"**. Never present them as released.
    - **A tool or package release** is confirmed by its own repo: the GitHub release, changelog or commit.
  - **Date every item** with the date of its source.
  - **Freshness:** items must fall inside the scope's window (step 2). Within a window, a status can change (e.g. preview in week 1, GA in week 3), so report the **latest** status and mention the change.

## Flow

### 1. Load the profile and catch-up history

- Run `python3 <skill-base-dir>/../../scripts/profile.py show`.
  - `<skill-base-dir>` is the "Base directory for this skill" path shown when this skill loads.
- **No profile:**
  - Hand off to `fabric-onboard` in its "sent here by another skill" mode. The user can skip it.
  - If they skip, build an unpersonalised digest: same layout, but no "For you" section, everything ranked by significance.
- **Invalid profile** (`show` exits 2, e.g. after a hand edit):
  - Don't send the user to onboarding, and never write over it.
  - Build the unpersonalised digest.
  - Say in one line that `fabric-progress` can fix it.
- Run `profile.py catchup-state` to get:
  - `since_last_time_from`: where "since last time" starts: the latest window end among **general** catch-ups (`since-last-time` and `period`, with no topic filter). Event digests and any topic-filtered digest cover only a slice of the news, so they don't move it.
  - `shown`: **every** item URL shown in any previous catch-up, with its status then, so nothing repeats (see [Catch-up log](#catch-up-log)).

### 2. Work out the scope

- Pick the **one** time scope that fits. A topic filter is a separate decision (see [Topic filter](#topic-filter) below):

| Scope | Example | Window |
|---|---|---|
| **Since last time** | "catch me up", "what's new?" | `since_last_time_from` → today, however long ago |
| **Period** | "what happened in September?", "this week in Fabric" | the stated period |
| **Event** | "FabCon Barcelona updates", "Fabric at Ignite" | event start − 1 day → event end + 30 days (or today, if sooner) |
| **Topic news** | "anything new in Real-Time Intelligence lately?" | last 90 days unless stated |

- **All scopes use all three source groups.** Official sources and tools lead for Period and Event:

| Group | Sources | What they add |
|---|---|---|
| **Official** | fabric-blog, learn-docs | *What changed*: announcements, releases, status changes, roadmap |
| **Tools & packages** | github, fabricstack | New releases of existing tools and libraries, and newly launched community tools |
| **Community** | reddit, youtube, community-forum, web | *How people react and use it*, plus community practices and tools the official channels never mention |
| **Demand** | fabric-ideas | *How long people wanted it*: links released features to the feature requests behind them. See [Demand signals](#demand-signals) |

- <a id="topic-filter"></a>**Topic filter.** Whenever the user names a workload, item or feature (Lakehouse, Power BI, Real-Time Intelligence, Direct Lake…), set it as the topic filter, whatever the time scope. Research and show only that topic, and log it (see [Catch-up log](#catch-up-log)). "Catch me up" or "what's new in Fabric?" has no topic filter.
- **Scopes can combine with a topic:**
  - Event + topic: "what's new for Power BI since FabCon": the event's end is the window start, filtered to Power BI.
  - Period + topic: "what changed for lakehouses in September?": Period scope, window 1–30 Sep, filtered to Lakehouse.
  - A topic with no time ("anything new in Real-Time Intelligence lately?") is Topic news scope, last 90 days.
- **Event scope: confirm the event first.**
  - Find the event's official name and dates from a source: Microsoft's event page or a Fabric blog post. Use these for the window, and cite them in the digest header.
  - If the name is ambiguous (e.g. "FabCon" with several editions), pick the most recent past edition and say so in the header.
  - If the event hasn't happened yet, say so. Offer the pre-event announcements instead, or suggest coming back afterwards.
- **Why the event window starts one day early:**
  - Major announcements land on the first keynote day.
  - One day before catches posts published on the eve, plus timezone differences: a post dated the evening before in US time can be launch day in Europe.
  - Pre-event "what to expect" posts are mostly speculation, so they're out of scope.
- **Why the event window runs 30 days after:**
  - Session recordings, deep-dive posts, community recaps and tool releases timed to the event keep arriving for weeks.
  - Features announced at the event often reach preview or GA within that month.
- **"Since last time" bounds:**
  - **No previous catch-up:** use the last 14 days and say so.
  - **"Last N days"** means today − (N − 1) through today, inclusive. If a big event starts just before that window, mention it in the header ("FabCon ran 28 Sep – 1 Oct, just before this window").
  - **Previous catch-up exists:** start the window at `since_last_time_from`, however long ago. The user should be able to come back after any gap and pick up where they left off.
  - **Window longer than 30 days:** ask how to cover it (step 3).

### 3. Decide whether to clarify

- **Default: don't ask.** State the scope and window in the digest header instead, e.g. "Since your last catch-up on 24 Sep".
- **Topic news handed off from a refresh check** (window = since the topic was learned): use **Highlights** without asking. The user already chose to catch up on that one topic.
  - In a catch-up on a single known topic, use one list ("What changed in <topic>"), not "For you" plus "Changes to things you know".
- **Ask when the window is longer than 30 days**, e.g. the last catch-up was four months ago:
  - One `AskUserQuestion`. Header "Catch-up". Question: "Your last catch-up was on <date>, <N> days ago. How should I cover it?"
  - Options:
    - **"Highlights across features & tools":** the most important official changes, tool releases and community picks across the whole period, in one digest.
    - **"Month by month":** the full period, broken down by month.
    - **"Just the last 30 days":** a normal catch-up for the most recent 30 days. The tool's "Other" box lets the user type a different number of days.
  - In the question text, mention that the first two take longer for long gaps.
  - **Whatever they choose, log the catch-up up to today.** The next "since last time" starts from now, not from the old date.
  - If the user picked "Just the last 30 days" (or N days), log `window` as the range actually covered (today − 29 … today) and `uncovered` as the skipped range, so a later request can still reach it.
- **A skipped period handed over from `fabric-progress`:** use Period scope for exactly that range. If it's longer than 30 days, ask the same question, worded for the period ("The period you skipped, 1 Aug – 10 Sep, is 41 days. How should I cover it?").
- **Ask when the request is too vague to scope**, e.g. "what's going on with Fabric?" with no catch-up history and no stated interests. Options:
  - "Last 2 weeks"
  - "Last month"
  - "A specific event"
  - "A specific area"
- If `AskUserQuestion` isn't available, ask the same as numbered options in plain text.

### Long windows

- **Applies when** the user chose "Highlights" or "Month by month" for a window longer than 30 days.
- **Slice the window by calendar month** and research each slice separately, using `fabric-researcher` subagents: one per month, at most 2 at a time, in waves. Follow the shared [subagent rules](../../references/sourcing-rules.md#running-the-research). If subagents are unavailable or fail, research the remaining slices one after another in the main conversation, still checkpointing each.
  - Each slice gets all three source groups, with the month as its window.
  - The blog's monthly feature-summary post for that month is the official backbone of the slice. The blog feed only holds the latest ~20 posts, so for older months **search for it**: `community.py blog --query "<Month YYYY> Feature Summary" --since <month start> --until <month end + 15 days> --grep <term>` (and `--product powerbi` for Power BI).
  - **Which month owns what:** a feature summary belongs to the month in its title, even though it's published early the next month. An event belongs to the month it starts.
  - **Reddit for older months:** RSS listings only reach recent posts, so use `reddit.py search "<key words>" --sort top --time year` and keep the posts dated inside the slice.
  - Slicing keeps each research task small enough to be thorough, instead of skimming months at once.
- **Checkpoint each slice to disk** as it finishes:
  - Path: `<data dir>/cache/catchup-<from>-<to>/<yyyy-mm>.json`, where `<data dir>` comes from `profile.py paths` (normally `~/.claude/fabric-learning`). Each file holds the slice's findings in the shared findings contract.
  - If the run is interrupted, the next catch-up with the same window reuses finished slices instead of re-fetching them.
  - Delete the cache folder once the digest is shown and logged.
- **Merge and rank across all slices** (step 6), so an item that started in month 1 and went GA in month 3 becomes **one** item with its latest status.
- **Layout by choice:**
  - **Highlights:** the normal layout over the whole window, with caps raised by half (e.g. 8 → 12). No per-month breakdown.
  - **Month by month:**
    - "For you" and "Changes to things you know" cover the whole window, at normal caps.
    - Then one block per month, most recent first, each with that month's "Also new", "Tools & packages" and "Community picks" as one-liners.

### 4. Plan the research

- Write a short brief before dispatching, so every source works to the same window and focus:
  - **Scope**, **window** (exact dates) and **topic filter**, if any.
  - **Event name variants**, if event scope, e.g. "FabCon Europe 2026", "FabCon Barcelona", "#FabCon". Hashtags help for YouTube.
  - **The user's focus:** `workloads`, `interest_areas` and `interests` from the profile. These guide **ranking**, not what's searched. Something big outside the user's areas still belongs in the digest.
- Skip sources that won't help. For example, learn-training rarely has news, so don't dispatch it unless the scope is about certifications.

### 5. Research the sources

- Run the research as the shared [Running the research](../../references/sourcing-rules.md#running-the-research) section describes:
  - **One `gather.py` call** for all script sources, including `learn.py` for Learn docs and training.
  - **One message** of parallel web searches and fetches, only for sources without a script and for a script's named fallback.
  - Subagents only where that section says.
  - Sources, scripts and the **findings contract** are defined in the [shared sourcing rules](../../references/sourcing-rules.md#3-sources).
- **What each source should look for within the window:**

| Source | Focus for catch-up |
|---|---|
| **fabric-blog** | All posts in the window, especially monthly feature summaries and event round-ups (`community.py blog`). For Power BI scopes, also the Power BI Updates blog (`community.py blog --product powerbi`). Feature summaries are huge: read them with `--grep <term>` or `--full`, not the default excerpt |
| **learn-docs** | The Fabric "what's new" page; the roadmap / release plan for **planned** items; commits to MicrosoftDocs/fabric-docs that add pages for new features |
| **github** | See [Tools & packages discovery](#tools--packages-discovery) below |
| **fabricstack** | Tools **added** to the catalogue in the window (the catalogue records an `added` date) |
| **fabric-ideas** | Ideas whose status changed in the window (especially to Planned or Completed), and ideas matching features released in the window, with vote counts and age. Ideas come from `community.py ideas`; vote counts and status come from web search snippets (see the shared source notes) |
| **reddit** | r/MicrosoftFabric top and new posts: announcement threads, first impressions, problems with new releases, tools people share |
| **youtube** | Videos published in the window: Microsoft channels, event sessions, community recaps and demos. Transcripts for the top videos |
| **community-forum** | Highly kudoed threads in the window, and announcements mirrored on the forum |
| **web** | Community blog recaps, newsletters, conference write-ups |

#### Demand signals

- Two signals show **how much a change matters to people**. They add weight to items found elsewhere and never create items on their own:
  - **Long-awaited** (from fabric-ideas):
    - Tag an item **"long-awaited"** only when a source **states** it: a Fabric Idea whose vote count and status are visible (in a search snippet), or an official post that names the request.
    - Cite that source.
    - Vote counts aren't in the Ideas RSS feed and rarely appear in snippets. Expect this tag to be rare, and never infer it.
    - Ideas newly marked **Planned** in the window can go in "Also new" as **Planned (Fabric Ideas)**, clearly labelled as not released, but only when the status is visible in a source.
  - **🔥 Widely discussed** (from reddit, community-forum, youtube):
    - The items with the most discussion in the window, measured within each platform (see the shared [engagement rules](../../references/sourcing-rules.md#6-engagement)), get this tag.
    - Cite the discussion.
- **Never let engagement decide what's left out.** It can lift an item up. It can't push a lower-engagement item, especially a new tool, out of the digest (see [protecting new launches](#protecting-new-launches)).

#### Tools & packages discovery

- **Never track a fixed list of repos.** The value is in surfacing what the user doesn't know about yet. Well-known tools (semantic-link-labs, skills-for-fabric, FUAM, fabric-cicd…) are found the same way as everything else.
- **Run `github.py discover --since <from> --until <to>`.** It covers the first two directions below in one call and returns the two lanes already ranked.
- **Find candidates from several directions:**
  - **Updated repos:** search GitHub for repos about Microsoft Fabric **pushed during the window**, sorted by stars. Search on "Microsoft Fabric", related terms (OneLake, Fabric lakehouse, semantic link, Fabric capacity…) and the `microsoft-fabric` topic.
  - **New repos:** the same searches, restricted to repos **created during the window**.
  - **Mentioned repos:** every GitHub URL that turns up in other sources' findings in the window, e.g. a tool shared on Reddit, written up on a blog or shown in a session.
  - **fabricstack:** tools added in the window, then followed to their repos.
- **Decide what counts as an update:**
  - **Releases or tags** published in the window: report what changed, from the release notes.
  - **No releases:** include only if a changelog file changed in the window, or another source mentioned the change. Commits alone are noise.
  - **New repos:** include if notable for their age (stars, activity, a clear README) or mentioned by another source.
- **Rank in two separate lanes,** never against each other:
  - **New launches** (repos created, or first released, in the window): rank by early signals (stars per day since creation, a clear README, mentions in other sources), then by relevance to the user.
  - **Updates** to existing tools: rank by engagement (see the shared [engagement rules](../../references/sourcing-rules.md#6-engagement)), then by relevance to the user.
- **Label** each tool with its authority as the shared rules define it: official, "Microsoft org, unsupported", or "community, not supported by Microsoft".

### 6. Merge, verify and rank

- **Merge findings into items.** Many findings describe the same change: a blog post, a Reddit thread, two community blog posts and a video about one feature.
  - Group them into **one item**.
  - The official finding (or, for a tool, its repo release) is the item's anchor. Other findings become its **reactions**.
  - An item with no official or repo anchor is either a **community item** (a discussion, a practice) or an **unconfirmed report**.
- **Verify** per the shared [verification rules](../../references/sourcing-rules.md#8-verification). **Spot-check the top 3–5 items** by fetching their anchor URLs: these are the items the user is most likely to act on or repeat to colleagues.
- **Drop already-seen items.**
  - Remove items already in `catchup-state.shown`, which is keyed by **URL + normalised title**. One monthly feature summary (one URL) anchors many separate items, so match on both.
  - **Exception:** an item whose **status changed** since it was shown (e.g. preview → GA). Keep it, marked "update".
- **Rank by relevance to this user, then significance:**
  1. **For you:**
     - Matches the user's `interests`, `workloads` or `interest_areas`.
     - Changes something in their `known_topics`. These matter most: something they know has changed.
  2. **Significance:**
     - GA > preview > planned.
     - Breaking changes and deprecations rank high whatever their area.
  3. **Community signal:**
     - Engagement relative to the platform.
     - "🔥 widely discussed" and "long-awaited" tags (see [Demand signals](#demand-signals)).
- **Protecting new launches:**
  - Community tools launched in the window have **reserved places** in "Tools & packages", under a "New launches" sub-heading. Established tools with more stars or more discussion can't take those places.
  - At least **2 places** (3 at `deep`) go to new launches whenever there are that many. Unused places go back to updates.
  - New launches are never dropped for low engagement alone. A week-old tool with 15★ that solves a real problem belongs in the digest.
- **Cap the digest** so it stays scannable. Defaults by profile depth:

| `preferences.depth` | "For you" items | "Also new" one-liners | Tools & packages | Community picks |
|---|---|---|---|---|
| summary | up to 5 | up to 8 | up to 5 | up to 3 |
| examples | up to 8 | up to 12 | up to 8 | up to 5 |
| deep | up to 10 | up to 20 | up to 12 | up to 5 |

- A tool release that matches the user's interests or workloads can go into "For you" instead of "Tools & packages".
- **Each item appears once.** If it qualifies for both "For you" and "Changes to things you know", put it in "Changes to things you know".
- Mention how many more items were found, so the user can ask for them ("+14 more, say 'show everything'").

### 7. Write the digest

- Output to the **terminal**. Write a Markdown file only if the user asks (see [Saving](#saving)).
- **Layout:**

```
Fabric catch-up — <scope>[, <topic>], <date range>
<one line: what the window covered, e.g. "FabCon Europe 2026, Barcelona, 28 Sep – 1 Oct [1]">

★ For you
  1. <Item title> — GA · 30 Sep · 🔥 widely discussed · long-awaited [2]
     <1–2 lines: what changed>
     Why it matters to you: <1 line tied to their profile>
     Community: <1 line, e.g. "Top r/MicrosoftFabric thread (140↑) is mostly about licensing questions" [3]>
  2. …

↻ Changes to things you know
  - <Known topic>: <what changed> — Preview → GA · 3 Oct [4]

Also new
  - <One-liner> — Preview · 29 Sep [5]

Tools & packages
  New launches
  - <New tool> — <what it does, from its README> · ★ 15 · created 2 Oct · community, not supported by Microsoft [6]
  Updates
  - <Tool> <version> — <headline changes, from the release notes> · <date> · <authority label> [7]

Community picks
  - <Reddit discussion / blog / forum thread> — <why it's worth a look> [8]

Worth watching
  - <Video title> — <channel> · 12k views · <what's covered> [9] (jump to 14:05)

Unconfirmed
  - <Community report> — unconfirmed — community report [10]

Not covered: <sources that failed or returned nothing, if it leaves a gap>

Sources
[1] …
```

- **Leave out empty sections.** A quiet week might be only "For you" and "Tools & packages".
- **Tags** ("🔥 widely discussed", "long-awaited") always cite their evidence: the discussion, or the Fabric Idea with its votes.
- **Community source unavailable** (e.g. Reddit rate-limited): add one line under "Not covered", e.g. "Reddit was unavailable, so community reaction is thin." Don't silently drop the community view.
- **Depth:** `summary` drops the "Community:" lines; `deep` adds 1–2 more lines per "For you" item (prerequisites, regions, SKUs, as sourced).
- **"Why it matters to you"** comes from the profile, e.g. "You work in RTI" or "You come from Databricks — this is Fabric's take on X". It's framing and needs no citation. Facts inside it still do.
- **Citations** follow the shared [citation format](../../references/sourcing-rules.md#9-citation-format).
- **Citation check before showing anything.** Pipe the draft through `python3 <skill-base-dir>/../../scripts/check_citations.py < draft.md`. For each sentence it flags, do one of three things:
  - **Cite it.** A `[n]` covers its own sentence and the one just before it, when both come from that source. Nothing after the last `[n]` in a bullet is covered.
  - **Make it plainly framing.** For example, "Why it matters to you" lines may only combine the user's profile with the item's already-cited facts, so end them with that item's `[n]`.
  - **Cut it.**

  **Show exactly the draft that passed.** Any sentence added or reworded afterwards (an intro, a summary, a closing line) must go through the check again. Re-run until it reports `ok`, or only deliberate framing remains. The script can't judge truth; it makes sure nothing unsupported slips through unnoticed.


### 8. Offer next steps

- End with **one** `AskUserQuestion` (single-select, 2–4 options) chosen from:
  - **Explain one item in depth:** name the top "For you" item. Hands off to `fabric-learn` with that item's sources as a starting point.
  - **Add to my interests:** for an item outside the user's current interests but related to them.
  - **Show everything:** if items were cut by the cap.
  - **Save as Markdown.**
- Always include **"None for now"** as one of the options.
- Skip this step if the user is clearly done.

## Catch-up log

- After showing the digest, append one entry to the learning log. This is what makes "since last time" and de-duplication work. Log it **even with no profile or an invalid one**: the log doesn't depend on the profile.

```bash
python3 <skill-base-dir>/../../scripts/profile.py append < entry.json
```

```json
{
  "skill": "fabric-catchup",
  "scope": "since-last-time",
  "topic": null,
  "label": "Since 12 Jun",
  "window": { "from": "2026-06-12", "to": "2026-10-10" },
  "coverage": "last-30-days",
  "uncovered": { "from": "2026-06-12", "to": "2026-09-09" },
  "items": [
    { "title": "Fabric IQ in Microsoft Copilot", "url": "https://…", "status": "ga" }
  ]
}
```

- `scope`: `since-last-time` · `period` · `event` · `topic-news`.
- `topic`: **required whenever the digest was filtered to a topic, whatever the scope**, e.g. `"scope": "period", "topic": "Lakehouse"` for "what changed for lakehouses in September?". `null` only for an unfiltered digest. A topic digest logged with `topic: null` counts as a general catch-up, so the next "catch me up" would skip all the other news in that window.
- `coverage`: `full` · `highlights` · `month-by-month` · `last-<n>-days`.
- `uncovered`: only when the user chose a shorter range than the gap. It lets a later request ("show me what I missed in the summer") pick it up.
- Log **only the items shown**, not everything found. Items cut by the cap can still appear next time.
- Store each item's status, so the next catch-up can spot a status change and resurface it.
- **Being shown an item doesn't mean the user knows it.**
  - Never add digest items to `known_topics`.
  - Add to `interests` only when the user picks "Add to my interests" or asks. Use `"source": "catch-up"` and today's date, and show the before → after before writing.

## Saving

- Write a Markdown file only when the user asks.
- **Default path:** `./fabric-notes/<yyyy-mm-dd>-catchup-<scope-slug>.md`, e.g. `2026-10-10-catchup-fabcon-europe-2026.md`. Use the user's path if they give one.
- Include the full digest, the Sources list, and a header line with the scope, the window and "Sources checked on <date>".

## Out of scope

- **Deep explanation of a single topic:** hand off to `fabric-learn`.
- **Anything in the user's tenant:** this plugin is for learning only.
- **Non-Microsoft "fabric" tools:** say this plugin covers Microsoft Fabric only.
