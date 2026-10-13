---
name: fabric-learn
description: >-
  Researches and teaches any Microsoft Fabric topic from cited sources (Fabric and Power BI blogs, Microsoft
  Learn docs, DP-600/DP-700 training, Reddit, the Fabric Community forum and Ideas, YouTube transcripts, GitHub
  and fabricstack.dev) and explains it at the user's level using their learner profile. Use this whenever the
  user wants to understand a Fabric concept, item, feature, admin setting or capacity behaviour; asks how to do
  something or how others did it; is stuck on a Fabric error or unexpected behaviour (throttling, failing
  refreshes, slow queries, Spark timeouts); wants to design an architecture; compares options such as Lakehouse
  vs Warehouse; asks whether a tool or repo exists for a Fabric task; or is studying for DP-600/DP-700. Applies
  even when they don't say Fabric but mean Power BI semantic models, OneLake, Direct Lake or semantic link. Not
  for news digests (fabric-catchup) and never acts on a Fabric tenant; learning only. Not Daniel Miessler's
  fabric CLI or Azure Service Fabric.
---

# Fabric learn

## Purpose

- Answer one Fabric question well:
  - Researched across official and community sources.
  - Every claim traceable to a link.
  - Pitched at the user's level.
- Fabric is new and changes fast. Features get renamed, move from preview to GA, and older answers go stale. A confident wrong answer does real damage, so:
  - **Traceability beats completeness.** A shorter answer where every claim is cited beats a longer one padded with unsourced detail.
  - Saying "I couldn't find a source for X" is a valid, useful answer.
- This plugin is **for learning only**:
  - It explains, with sources.
  - It never connects to, creates, changes or queries anything in the user's Fabric tenant, and never offers to.

## Ground rules

- **Read the shared sourcing rules first:** `<skill-base-dir>/../../references/sourcing-rules.md` ([sourcing-rules.md](../../references/sourcing-rules.md)).
  - They define the citation rules, sources, findings contract, authority, engagement, release status, verification, citation format and privacy.
  - They apply in full to this skill.
- **On top of the shared rules,** this skill adds:
  - **Date everything time-sensitive.** Write "as of <month year>" for release status, limits and pricing.
  - **Freshness** follows this skill's [freshness rules](#freshness-rules), which depend on the release status of the item.

## Flow

### 1. Load the learner profile

- Run `python3 <skill-base-dir>/../../scripts/profile.py show`.
  - `<skill-base-dir>` is the "Base directory for this skill" path shown when this skill loads.
- **Profile exists:** use it in steps 3, 6 and 7:
  - `preferences.depth` sets the default depth.
  - `background_fields`, `background_platforms` and `background_stack` say which analogies to use.
  - `known_topics` says what to skip or compress.
  - `interests` say which related topics to suggest.
- **No profile:**
  - Hand off to `fabric-onboard` in its "sent here by another skill" mode. The user can skip it.
  - Then come back to the original question.
  - If they skip, continue with `depth: "examples"` and make no assumptions about background.
- **Invalid profile** (`show` exits 2, e.g. after a hand edit):
  - Don't send the user to onboarding, and never write over it.
  - Continue unpersonalised.
  - Say in one line that `fabric-progress` can fix it.
- Also check whether this topic, or one close to it, was covered before (see [Learning log](#learning-log)):
  - Run `profile.py log --topic "<term>"` (case-insensitive substring match) for the main topic **and** for 1–2 key terms, e.g. "capacity" and "OneLake" for "how do workspaces, capacities and OneLake relate".
  - In the same conversation, an earlier answer counts too.
  - If a related session exists, build on it ("Following on from your session on copying data across capacities…") instead of saying the topic is new.

### 2. Classify the question

- Pick the **one** type that best fits. It decides which sources lead, whether to clarify, and the answer layout.
- If a question spans two types (e.g. "what are Ontologies and how do I set one up"), pick the main one and use the other's layout for one section.

| Type | Example | Lead sources | Answer layout |
|---|---|---|---|
| **Concept** | "What are Ontologies in Fabric?" | Learn docs → Learn training → Fabric blog → YouTube → Reddit | [Concept](#concept) |
| **How-to** | "How do I migrate workspaces across capacities?" | Learn docs → Learn training → Reddit + Community forum → GitHub | [How-to](#how-to) |
| **Scenario design** | "Design a near-real-time IoT pipeline on Fabric" | Learn docs (architecture) → Learn training → community blogs → GitHub → YouTube | [Scenario design](#scenario-design) |
| **Admin / setting** | "What does the 'Users can create Fabric items' tenant setting do?" | Learn docs → Fabric blog → Reddit + Community forum | [Admin / setting](#admin--setting) |
| **Comparison** | "Lakehouse vs Warehouse for a SQL-heavy team?" | Learn docs → Learn training → Reddit → community blogs | [Comparison](#comparison) |
| **Problem solving** | "Our F64 keeps throttling every morning, what can we do?" · "My Dataflow Gen2 refresh fails with a gateway error" | Reddit + Community forum → Learn docs (troubleshooting, known issues) → fabricstack → GitHub (incl. issues) → Fabric blog | [Problem solving](#problem-solving) |
| **Tool discovery** | "Is there a tool for monitoring capacity usage?" | fabricstack → GitHub → Reddit → Fabric blog | [Tool discovery](#tool-discovery) |

- **Problem solving vs How-to:**
  - **How-to:** the user wants to *do* something ("how do I set up X").
  - **Problem solving:** something is broken, blocked, slow or behaving unexpectedly, or the user faces a concrete situation that needs a solution.
  - When unsure, pick Problem solving if the user mentions an error, a symptom or "it's not working".
- **Why Reddit and the Community forum lead for problem solving:**
  - Most real fixes and workarounds are posted there first, by people who hit the same error. Microsoft staff and Super Users often answer on both.
  - The forum also marks **accepted solutions**, a strong signal that a fix actually worked (see the shared [source notes](../../references/sourcing-rules.md#notes-per-source)).
  - Always dispatch both for problem solving.
- **Problem solving stays a learning exercise.** The answer explains **why** it happens and **what the options are**, so the user understands the fix and can apply it themselves. This plugin never runs diagnostics or changes anything in the tenant.
- For a feature that's new or recently changed, add the **Fabric blog** near the front, whatever the type. Announcements often appear on the blog before the docs are complete.

### 3. Decide whether to clarify

- **Default: don't ask.** Most questions can be answered directly, and extra questions slow the user down.
- **Ask only when the answer would materially differ** between plausible readings, for example:
  - **Scenario design:** almost always ask. Constraints change the design (data volume, latency needs, team skills, existing platform).
  - **How-to:** ask when the procedure forks, e.g. same vs different region, or Fabric vs Power BI Premium capacity.
  - **Comparison:** ask when the user's criteria aren't stated (cost, performance, skills, governance).
  - **Problem solving:** usually ask, because the same symptom can have different causes:
    - Which workload or item is affected.
    - The error message or symptom, if not given. Invite the user to paste the error text, after removing workspace names, IDs, URLs and personal details.
    - When it started, and what changed around then.
    - Offer "Not sure" for each.
  - **Concept / Admin / Tool discovery:** rarely ask. If a tool question hides a how-to fork (e.g. same vs different region), the How-to rule applies.
- **How to ask:**
  - One `AskUserQuestion` call with 1–3 focused questions, each with 2–4 options.
  - Always include a "Not sure — cover the common cases" option, so the user is never blocked.
  - Pre-fill from the profile where you can and say so, e.g. "Your profile says you come from Databricks; I'll compare against that unless you want otherwise".
  - If `AskUserQuestion` isn't available, ask the same questions as numbered options in plain text.
- **Known topic check:**
  - **The question's main topic is itself in `known_topics`:** don't re-teach the basics. Offer a branch instead. A workload-level entry (e.g. "Data engineering") never triggers this branch for a specific topic inside it; it only raises the starting depth.
    - "What's changed since you learned it"
    - "A specific aspect"
    - "Full refresher anyway"
    - "None, just answer the question as asked" (always offered, so the user is never stuck)
  - **Topic is in the learning log:** mention when it was covered, e.g. "We covered Direct Lake on 3 Sep", and build on it rather than repeating it.

### 4. Plan the research

- Write a short research brief before dispatching. It keeps every source searching for the same thing:
  - **Topic** and the user's question in one sentence.
  - **Search terms:** per the shared [search hygiene](../../references/sourcing-rules.md#2-search-hygiene) rules, including confirmed former names. Fabric renames things, and older posts use the old names.
  - **Time window:** set it by the release status of the item or feature in question, using the [freshness rules](#freshness-rules). If the status isn't known yet, use the preview window until research confirms it.
    - Tool discovery: any age, ranked by recent activity.
    - Problem solving: favour the newest material. A fix from 18 months ago may no longer apply, and a recent known issue may explain the symptom.
  - **For problem solving, also search:**
    - The **exact error text**, quoted, with IDs and names stripped.
    - The **symptom in plain words**, e.g. "capacity throttling mornings".
  - **Which sources to use and in what priority**, from the type table.
- Skip sources that clearly won't help, to save time and tokens. For example, YouTube rarely helps for a single tenant setting.

### 5. Research the sources

- Run the research as the shared [Running the research](../../references/sourcing-rules.md#running-the-research) section describes:
  - **One `gather.py` call** for all script sources, including `learn.py` for Learn docs and training.
  - **One message** of parallel web searches and fetches, only for sources without a script and for a script's named fallback.
  - Subagents only where that section's decision table says. Most questions need none. Typical exceptions: a comparison or scenario with independent parts, or several long videos or threads to read in full.
  - Sources, scripts and the **findings contract** are defined in the [shared sourcing rules](../../references/sourcing-rules.md#3-sources).
- **What each source should look for, for this skill:**

| Source | Focus for learning |
|---|---|
| **learn-docs** | The concept, how-to or settings pages for the topic, plus troubleshooting and known-issues pages for problem solving |
| **learn-training** | DP-600 / DP-700 modules and exercises that teach the topic, and whether the topic appears in a skills-measured list |
| **fabric-blog** | Announcement and deep-dive posts for the topic, especially if it's new or recently changed |
| **reddit** / **community-forum** | Explanations, experiences, gotchas, and (for problem solving) fixes and accepted solutions |
| **youtube** | Explainers, demos and session recordings, with timestamps for the relevant moments |
| **fabricstack** | **Problem solving and Tool discovery only:** catalogue tools that address the problem (`fabricstack.py search`) |
| **github** | Tools and libraries for the task (`github.py search`), issues describing the problem and its workarounds (`github.py issues`), and samples. Check each candidate with `github.py repo` before citing it |
| **web** | Practitioner blog write-ups and lessons learned on the topic |
| **fabric-ideas** | Only when the capability looks unsupported: the matching idea, its votes and its status |

- **fabric-ideas** is used only when the honest answer is "Fabric can't do this today" (see the How-to and Problem solving layouts). It shows whether people have asked for it and how Microsoft has responded.

- **fabricstack is for Problem solving and Tool discovery only.** Its catalogue is organised around solving problems, not explaining concepts.

### 6. Verify and reconcile

- Apply the shared [verification rules](../../references/sourcing-rules.md#8-verification).
- **Spot-check 2–3 claims:** the ones the answer stands or falls on, e.g. the core definition or the key migration step.
- **Rank** findings:
  - Authority comes first: `official` > `expert` > `community`.
  - Within the same authority, use engagement relative to that platform.
  - Then recency.
- **Flag staleness** using the [freshness rules](#freshness-rules). Mark a finding outdated if a newer source contradicts it.
- **Thin evidence:** if a key part of the question has no sourced answer, say so, and suggest where the user could ask, e.g. r/MicrosoftFabric or the Fabric Community forum.

### 7. Write the answer

- Answer in the **terminal**. Write a Markdown file only if the user asks (see [Saving](#saving)).
- Pitch by `preferences.depth`. The user can override it per question ("give me the deep version"):
  - **summary:** the layout's first section plus 3–5 bullets, a one-line cited "Learn next" (when a source links one), then sources. If the question has several parts (e.g. "how does it work, and is it GA?"), give each part one short block.
  - **examples:** the full layout, with one concrete example or snippet where it helps.
  - **deep:**
    - The full layout plus internals, edge cases, limits and code.
    - All code comes from or is adapted from a cited source. Say which.
- **Translate using the background fields:**
  - **From another data platform:** map the Fabric concept onto that platform's equivalent, and cite the Fabric side.
  - **From software engineering:**
    - Lean on Git, CI/CD, APIs and typed code.
    - Explain data-modelling and Spark concepts rather than assuming them.
    - For .NET / JVM users, point out when a Fabric task is Python- or SQL-first.
  - **From a business or non-technical background:** first principles, no unnecessary jargon.
  - The analogy is framing and needs no citation. The Fabric facts inside it still do.
- **Skip or compress** anything in `known_topics`. A one-line reminder is fine.
- **Citation check before showing anything.** Pipe the draft through `python3 <skill-base-dir>/../../scripts/check_citations.py < draft.md`. For each sentence it flags, do one of three things:
  - **Cite it.** A `[n]` covers its own sentence and the one just before it, when both come from that source. Nothing after the last `[n]` in a bullet is covered.
  - **Make it plainly framing.** For example, "Why it matters to you" lines may only combine the user's profile with the item's already-cited facts, so end them with that item's `[n]`.
  - **Cut it.**

  **Show exactly the draft that passed.** Any sentence added or reworded afterwards (an intro, a summary, a closing line) must go through the check again. Re-run until it reports `ok`, or only deliberate framing remains. The script can't judge truth; it makes sure nothing unsupported slips through unnoticed.


#### Freshness rules

- Freshness depends on the **release status of the item or feature** the finding is about, not on its general area:

| Status of the item / feature | Finding counts as fresh if published within | Older than that |
|---|---|---|
| **GA** | 12 months | Keep it, but label it "may be outdated (<month year>)" |
| **Preview** | 6 months | Keep it, but label it "may be outdated (<month year>) — preview features change quickly" |
| **Status unknown** | 6 months (treat as preview) | As for preview |
| **No Preview label on its learn-docs page** | 12 months (counts as GA) | As for GA. Cite the page; a docs page without a Preview label is the evidence (`learn.py page`: `preview.title` and `preview.note` both false) |
| **Deprecated / retired** | always flagged | Say so prominently and point to the replacement if a source names one |

- Long-standing core features (Spark, Lakehouse, Direct Lake, workspaces…) rarely carry a "GA" label. Don't leave them as "status unknown" when their learn-docs page shows no Preview label.
- Take the status from the most authoritative, most recent source, usually learn-docs or the blog. Statuses change, and a feature that was in preview in an old post may be GA now.
- Freshness applies **per finding**. One answer can mix a fresh GA doc with a stale preview-era Reddit thread.
- Stale findings aren't hidden. They're labelled, ranked below fresh ones, and never used as the only support for a claim about current behaviour.

#### Citations

- Use the shared [citation format](../../references/sourcing-rules.md#9-citation-format): numbered inline markers, and a **Sources** list at the end of every answer.

#### Layouts by type

##### Concept
- **In short:** 2–3 lines, framed for the user's background.
- **How it works:** components and how they fit together.
- **Where it fits:** when to use it, when not to, and what it replaces or sits next to.
- **Status & limits:** preview or GA, known limitations, region or SKU requirements (as of the source date).
- **What practitioners say:** community experience, gotchas, adoption.
- **Learn next:** 1–3 related topics that a **cited source** links to this one, e.g. the docs page's "Next steps" section, the next module in a training path, or a link in the body that the page presents as a prerequisite or related topic. Cite the link. If the user's `interests` include one, put it first. If no source links any related topic, leave this section out rather than inventing one.

##### How-to
- **Short answer:** is it possible, and what's the main route.
- **Options:** each with steps, prerequisites and caveats:
  - The official route.
  - Community tools or scripts.
  - Manual workarounds people report.
- **Gotchas people hit:** from Reddit, the Community forum, GitHub issues and blogs.
- **Before you start:** permissions, capacity or SKU needs, and anything irreversible.
- **If it isn't possible today:**
  - Say so plainly, with the source that shows it.
  - Give the closest workaround.
  - Link any matching Fabric Idea with its votes and status, so the user can vote for it.

##### Scenario design
- **Assumptions:** the constraints from step 3 (or "common case").
- **Options:** 1–3 candidate architectures, each with:
  - Components.
  - Data flow (a small ASCII diagram is fine).
  - Trade-offs.
  - Rough cost and skills implications, only where sourced.
- **Reference implementations:** repos, samples and talks that do something similar.
- **Open questions:** decisions the user still has to make.

##### Admin / setting
- **What it controls.**
- **Scope:** tenant, capacity, domain or workspace.
- **Default, and who can change it.**
- **Impact of turning it on or off,** including security or cost implications.
- **What admins report:** from Reddit and the Community forum, with dates. Note Microsoft employee or Super User answers.

##### Comparison
- **Verdict for this user:** 2–3 lines, conditional on their criteria.
- **Comparison table:** one row per criterion, with a citation in each Fabric cell that states a fact.
  - When one column is the user's **own background platform** (e.g. Databricks), its cells are framing drawn from what the user knows. Mark that column header "(your background, not researched)" and don't cite it, unless you did research it.
- **When each wins:** short bullets.
- **Migration or interoperability notes,** if relevant.

##### Problem solving
- **What's likely going on:**
  - The most likely causes, ranked, each cited.
  - Say plainly if the evidence doesn't single one out.
- **Why it happens:** the underlying Fabric behaviour (e.g. how capacity smoothing and throttling work). This is the learning core: understanding the cause lets the user handle the next variation themselves.
- **How to confirm which cause it is:** what the user can check themselves, e.g. which monitoring view or log to look at and what to look for. Describe the steps; don't run anything.
- **Options to fix or work around:**
  - **Official fix or guidance:** docs, and the Fabric known-issues list (now at support.fabric.microsoft.com; the old learn.microsoft.com known-issues URLs redirect there).
  - **Community tools that solve or monitor it:** from fabricstack and GitHub, with ★, last commit, maintainer and "not supported by Microsoft".
  - **Fixes and workarounds people report:**
    - From Reddit, the Community forum, GitHub issues and blogs, with dates.
    - Put forum threads with an accepted solution and highly upvoted Reddit fixes first.
    - Note when a Microsoft employee or Super User confirmed the fix.
  - For each option: effort, prerequisites (permissions, SKU) and risks.
- **Known issue?** If a known-issues page or a recent thread matches the symptom, say so up front, with its date and status (open / fixed).
- **Prevent it next time:** 1–3 practices, cited.
- **If the root cause is a missing capability:** link any matching Fabric Idea with its votes and status.
- **Learn next:** the concept behind the problem, as a related topic, cited from the source that explains it.

##### Tool discovery
- Ranked list. For each tool:
  - What it does.
  - Official or community, and maintainer.
  - ★ stars, last commit, licence.
  - Install effort.
  - Caveats, e.g. abandoned, preview APIs only, or needs admin rights.
- **Official alternative,** if one exists.
- Say clearly that community tools aren't supported by Microsoft.
- **Learn next** (optional): the concept the tools rely on, if a cited source links it. This keeps `related_topics` useful for `fabric-progress`.

### 8. Offer next steps

- End with **one** `AskUserQuestion` (single-select, 2–4 options) built from what's useful now. Pick from:
  - **Go deeper:** the same topic at the next depth level.
  - **More examples / code:** if depth is below `deep`.
  - **Related topic:** name one specific topic, preferring the user's `interests`.
  - **Mark as learned:** adds the topic to `known_topics`.
  - **Save as Markdown.**
  - **Practise it:** point to the relevant Microsoft Learn training module or exercise, if one was found during research.
- Always include **"None for now"** as one of the options.
- Skip this step when the user is clearly done or moving on.

## Learning log

- After answering, append one entry, **even with no profile or an invalid one** (the log doesn't depend on the profile). It records **what was covered, not what the user knows**:

```bash
python3 <skill-base-dir>/../../scripts/profile.py append < entry.json
```

```json
{
  "skill": "fabric-learn",
  "topic": "Fabric IQ Ontologies",
  "question": "What are Ontologies in Fabric?",
  "type": "concept",
  "depth": "examples",
  "status": "preview",
  "sources": ["https://learn.microsoft.com/...", "https://reddit.com/..."],
  "related_topics": [ { "topic": "Fabric data agents", "url": "https://learn.microsoft.com/..." } ]
}
```

- The full schema is in the shared [data model](../../references/data-model.md#log-entries).
- `status`: the cited release status of the main topic (`preview` · `ga` · `deprecated` · `retired` · `planned` · `unknown`). `fabric-progress` uses it to decide when a known topic needs a refresh.
- `related_topics`: exactly the topics in the answer's cited "Learn next" section, each with the URL that links it. `fabric-progress` recommends next steps only from these, so it never has to invent how topics relate. The helper rejects entries without a URL.

- **Only the user decides what they know.**
  - Add a topic to `known_topics` only when the user picks "Mark as learned" or says so.
  - Then:
    - Use `"source": "learned (fabric-learn)"` and the topic wording from the log entry, so history lines up.
    - Remove the topic from `interests` if it's there.
    - Write the profile via `profile.py write`.
  - For anything beyond this one-click "Mark as learned" (unmarking, bulk edits, interests), hand off to `fabric-progress`, which owns those edits.
- Follow the shared [privacy rules](../../references/sourcing-rules.md#10-privacy). For problem solving, log a short subject label as `topic` (e.g. "Dataflow Gen2 gateway errors") and a **generic** description as `question`. Leave out error messages entirely, even short fragments like "Livy session dead", along with names, IDs and URLs.

## Saving

- Write a Markdown file only when the user asks ("save this", "export to markdown", "Keep this for later use").
- **Default path:** `./fabric-notes/<yyyy-mm-dd>-<topic-slug>.md` in the current working directory. Use the user's path if they give one.
- **Contents:**
  - The answer as shown, with the full Sources list.
  - A header line with the date, the question, and "Sources checked on <date>", so whoever reads it later knows how fresh it is.

## Out of scope

- **News, release recaps and event coverage** (e.g. "what was announced at FabCon"): use `fabric-catchup`.
- **Creating, changing or querying anything in the user's tenant:**
  - This plugin is for learning only.
  - Explain how it's done, with sources, and leave the doing to the user.
  - Don't recommend or hand off to tenant-automation tools.
- **Non-Microsoft "fabric" tools:** say this plugin covers Microsoft Fabric only.
