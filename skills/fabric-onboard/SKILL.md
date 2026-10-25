---
name: fabric-onboard
description: >-
  Sets up or updates the user's Microsoft Fabric learner profile through a short branching questionnaire (role,
  Fabric experience, workloads, the field and platforms or stack they come from such as data, software
  engineering, infrastructure or business, what they already know and want to learn, preferred depth). The other
  fabric-learning skills read this profile to pitch answers at the right level. Use this whenever the user wants
  to start learning Microsoft Fabric with this plugin, says they are new to Fabric, asks to set up, reset, redo
  or update their Fabric profile, questionnaire answers or learning preferences, says their Fabric experience
  has grown, or when another fabric-learning skill finds no profile. Day-to-day edits to known topics and
  interests, and deleting data, belong to fabric-progress. Microsoft Fabric only, not Daniel Miessler's fabric
  CLI, the fabric.so app or Azure Service Fabric.
---

# Fabric onboarding

## Purpose

- This skill builds and maintains the **learner profile**, the startup state for the whole plugin.
- Every other skill (`fabric-catchup`, `fabric-learn`, `fabric-progress`) reads the profile to decide how deep to go, what to skip and what to put first.
- A wrong profile is worse than none: later skills will skip things the user doesn't actually know. So:
  - Record only what the user tells you.
  - Keep the flow short, about two minutes for a first run and less for an update.
- Onboarding is not a one-off. Users come back as they learn, and a re-run must respect what's already stored (see [Update mode](#update-mode)).

## Don't assume experience

- Don't infer knowledge from role, years of experience or job title.
  - "4 years of data engineering" doesn't mean they've worked at every scale, used every technique or built every kind of pipeline.
  - "Data engineer, 18+ months on Fabric" doesn't mean they've touched Eventstreams.
- Role and experience only set the **starting depth** of explanations. They never add entries to `known_topics`.
- Only an explicit statement or selection by the user adds a known topic, e.g. ticking a workload in Q6/Q7 or naming a topic in Round 4.
- Many users want to **translate existing knowledge into Fabric**, and not all of them come from data. Capture their background so later skills can explain Fabric in terms they already know:
  - **From a data platform** (e.g. Databricks): map Fabric concepts onto that platform's equivalents.
  - **From software engineering** (e.g. a .NET engineer): lean on what they know (source control, CI/CD, APIs, typed code), and don't assume data-modelling or Spark knowledge.
  - **From business or non-technical roles:** explain from first principles and avoid jargon.

## Where the profile lives

```
~/.claude/fabric-learning/      (or $FABRIC_LEARNING_HOME if set)
├── profile.json        # questionnaire & preference fields owned here; known_topics/interests edits owned by fabric-progress
└── learning-log.jsonl  # append-only record of what was covered; written by fabric-learn / fabric-catchup
```

- Treat these two files as the user's database of their progress in Fabric.
- They live outside the plugin directory so they survive plugin updates and reinstalls.
- Every read and write goes through the shared helper, so all skills use one validated schema:

```bash
python3 <skill-base-dir>/../../scripts/profile.py show              # prints profile JSON; exit 1 if none, exit 2 if invalid
python3 <skill-base-dir>/../../scripts/profile.py write  < new.json  # validates, stamps updated_at, writes atomically
```

- `<skill-base-dir>` is the directory that contains this SKILL.md (Claude Code shows it as "Base directory for this skill"; in GitHub Copilot, use the directory this skill was loaded from).
- **No PII, ever.** No names, email addresses, employers, tenant or workspace IDs, or credentials. The skill needs none of these to work, and this rule is never relaxed. See [Privacy](#privacy).

## Flow

### 1. Check for an existing profile

- Run `profile.py show`, then pick the matching case:
  - **No profile** (exit 1): go to [step 2, first-run questionnaire](#2-first-run-questionnaire).
  - **Placeholder profile** (`onboarding_skipped: true`, left when the user skipped setup earlier): there's nothing to keep, so go straight to the first-run questionnaire. No keep/update/start-over question and no export offer. The learning log is untouched, and any known topics or interests in the placeholder are carried over.
  - **Invalid profile** (exit 2, e.g. after a hand edit):
    - Never run the first-run questionnaire over it. That would erase the user's history.
    - Show the error and hand off to `fabric-progress` to fix the named field.
    - Use `write --replace-invalid` only if the user explicitly chooses to replace the profile.
    - Once it's fixed, offer [Update mode](#update-mode) for any questionnaire fields still missing. Don't invent answers for them.
  - **Profile exists, user invoked this skill directly:**
    - Summarise the profile in 3–5 lines: role, experience, workloads, top interests, number of known topics.
    - Ask whether to **keep it**, **update parts of it** ([Update mode](#update-mode)) or **start over**.
    - Never overwrite silently. The profile may hold months of learning history, and losing it is unacceptable.
    - For "start over":
      - Show what will be cleared, e.g. "12 known topics and 5 interests will be cleared. Your learning history stays."
      - Offer to export first (via `fabric-progress`).
      - Then confirm once more.
      - The learning log is never deleted by this skill.
    - If the user wants their data **deleted** rather than the questionnaire redone, hand off to `fabric-progress`, which owns data deletion.
  - **Another skill sent the user here because no profile exists:**
    - Say so in one line, e.g. "Before I dig into that: a short setup so I can pitch this at your level. You can skip it."
    - If they skip:
      - Write a minimal profile with `"onboarding_skipped": true` and default preferences (`depth: "examples"`).
      - Return to the original request. Don't hold their question hostage.
  - **Another skill sent the user here to update the profile:**
    - Summarise the current profile first.
    - Run [Update mode](#update-mode).
    - Return to the original request.

### 2. First-run questionnaire

- **Use what the user already said.** If their message already answers a question (e.g. "I'm a C# developer" answers Field and Stack), don't ask it again. Preselect the answer, and list it in the confirmation summary so they can correct it. Skip a round if all its questions are already answered.

- Use the ask-the-user tool when available (`AskUserQuestion` in Claude Code, `ask_user` in GitHub Copilot):
  - It's quicker than typing.
  - It limits answers to values the other skills understand.
- If it's unavailable (another client), ask the same questions as numbered options in plain text. Apply the same skip rules.
- The tool adds an "Other" free-text choice to every question. Store whatever the user writes there **verbatim** in the matching field. Don't force it into one of the options.

- The questionnaire has the same shape for everyone:

| Round | Theme | Asked to | Format |
|---|---|---|---|
| 1 | Who you are | everyone | picker, 3 questions |
| 2 | Your background & Fabric use | only the questions that apply; skip the round if none do | picker, 0–4 questions |
| 3 | How you want to learn | everyone | picker, 2 questions |
| 4 | Known topics & goals | everyone (optional answer) | plain text |

- Each round is one ask-the-user call, so its questions appear as tabs of a single step. If the client takes one question per call, ask them one after another.
- Round 2's questions depend on Round 1 answers. That's why they're a separate round: one call can't branch on its own answers.

**Round 1: who you are** (always, 3 questions)

| # | Header | Question | Options | Multi |
|---|---|---|---|---|
| 1 | Role | Which role do you work in, or are you moving into, with Fabric? | Data engineer · Analytics / BI developer · Platform admin or architect · Data scientist / AI engineer | no |
| 2 | Experience | How much have you used Microsoft Fabric? | Not yet · Getting started (< 6 months) · Regular user (6–18 months) · Experienced (18+ months, production workloads) | no |
| 3 | Field | Which field(s) are you coming from? Pick all that apply. | Data & analytics · Software engineering (e.g. .NET, Java, web) · Cloud, infrastructure or DevOps · Business or non-technical (analyst, PM, domain expert) | yes |

- Roles outside the four options (pre-sales, consultant, project manager…) go in "Other" and are stored verbatim. Pick the nearest depth and analogies from Q3, not from the role.
- Q1 asks about the **target** role on purpose. A .NET engineer learning Fabric to become a data engineer picks "Data engineer". Their current field is captured by Q3.
- Q3 matters as much as the role. Someone from software engineering already knows Git, CI/CD, APIs and testing, but may not know dimensional modelling or Spark. Later skills use the field to:
  - Explain Fabric in terms the user already knows.
  - Skip the basics the user's field has already covered.
  - Avoid assuming data knowledge the user doesn't have.

**Round 2: your background & Fabric use** (conditional, 0–4 questions)

- Include each question only when its condition holds.
- If no question applies (e.g. a business user with no Fabric experience), skip the round and go to Round 3.

| # | Header | Question | Options | Multi | Asked when |
|---|---|---|---|---|---|
| 4 | Data tools | Which data platforms have you used? Pick all that apply. | Power BI · Azure Synapse / Data Factory · Databricks · Other cloud data platforms (Snowflake, BigQuery, Redshift…) | yes | Q3 includes Data & analytics |
| 5 | Stack | Which languages or stacks do you work in? Pick all that apply. | .NET / C# · Java / JVM · Python · JavaScript / TypeScript | yes | Q3 includes Software engineering |
| 6 | Data & BI | Which of these Fabric areas do you work in or already feel comfortable with? Pick all that apply. | Data engineering (Lakehouse, Spark, notebooks, pipelines) · Warehousing & SQL · Power BI & semantic models · None of these | yes | experience ≠ Not yet |
| 7 | RTI & AI | And which of these? Pick all that apply. | Real-Time Intelligence (Eventstreams, Eventhouse, KQL) · AI & agents (data agents, Fabric IQ, Ontologies) · Neither yet | yes | experience ≠ Not yet |

- **Q6–Q7, Fabric workloads:**
  - Skip both when experience is "Not yet". Someone who hasn't used Fabric can't say which workloads they use, and names like Eventhouse or Ontology mean nothing to them yet. Set `workloads` to `[]`.
  - They're split into two questions because the tool allows at most four options per question.
  - Both are **multi-select**: the user can tick any number on each.
  - Ticking a workload means "I work in this or I'm already comfortable with it". It feeds both `workloads` and `known_topics` (see [step 3](#3-build-and-write-the-profile)).
- **"Other" in Q3:**
  - Store the text in `background_fields`.
  - Ask no follow-up for it. The free text in Round 4 lets the user add detail.

**Round 3: how you want to learn** (always, 2 questions)

| # | Header | Question | Options | Multi |
|---|---|---|---|---|
| 8 | Depth | How should I pitch explanations by default? | Quick summaries · Explanations with examples · Deep dives with code & architecture | no |
| 9 | Interests | What do you most want to keep up with? Pick all that apply. | New features & announcements · Community tools & open source · Real-world practices & lessons learned · Admin, governance & capacity | yes |

**Round 4: known topics & goals** (plain text, optional, one message):

- Ask:
  > Last one, optional: is there anything specific you **already know well** (so I don't re-explain it) or **want to learn next**? For example: "comfortable with Lakehouse and Direct Lake; want to learn Ontologies and capacity management".
- Split the answer into short topic strings for `known_topics` and `interests`.
- If they skip, leave both lists empty.

### 3. Build and write the profile

- Build the profile from the answers using the schema and mappings below.
- **Omit `created_at` and `updated_at`.** The helper sets both, and keeps the original `created_at` on later writes.
- Pipe the JSON to `profile.py write`.
- If validation fails, fix the field it names and retry. Don't hand-write the file to get around the validator.

```json
{
  "schema_version": 1,
  "onboarding_skipped": false,
  "role": "Data engineer",
  "experience": "regular",
  "workloads": ["data-engineering", "power-bi", "rti"],
  "background_fields": ["data", "software"],
  "background_platforms": ["Azure Synapse / Data Factory", "Power BI"],
  "background_stack": ["dotnet", "python"],
  "preferences": { "depth": "examples" },
  "interest_areas": ["features", "community-tools"],
  "known_topics": [
    { "topic": "Lakehouse", "source": "self-reported", "added_at": "2026-10-08" }
  ],
  "interests": [
    { "topic": "Fabric IQ Ontologies", "source": "self-reported", "added_at": "2026-10-08" }
  ]
}
```

- Value mappings:
  - `experience`: `none` · `starting` · `regular` · `experienced`
  - `workloads`: `data-engineering` · `warehousing` · `power-bi` · `rti` · `ai-agents`. "None of these" or "Neither yet" adds nothing.
  - `background_fields`: `data` · `software` · `cloud-infra` · `business`
  - `background_platforms`: the Q4 option labels as shown. `[]` if Q4 wasn't asked.
  - `background_stack`: `dotnet` · `jvm` · `python` · `javascript`. `[]` if Q5 wasn't asked.
  - `preferences.depth`: `summary` · `examples` · `deep`
  - `interest_areas`: `features` · `community-tools` · `practices` · `admin`
  - "Other" answers: the user's text, as-is.
- `known_topics` entries come only from what the user states or selects, never from role or experience:
  - Each workload ticked in Q6/Q7 adds one entry with `"source": "self-reported (workload)"` and **exactly** this `topic` label, so every skill matches it the same way:

    | Workload | `topic` label |
    |---|---|
    | `data-engineering` | Data engineering |
    | `warehousing` | Warehousing & SQL |
    | `power-bi` | Power BI & semantic models |
    | `rti` | Real-Time Intelligence |
    | `ai-agents` | AI & agents |

  - Free-text items from Round 4 add entries with `"source": "self-reported"`.
  - Knowledge from **another platform** keeps its provenance in the topic, e.g. "Spark (from Databricks)" or "Delta Lake (from Databricks)". It tells later skills what to build on, without claiming the user knows Fabric's version of it.
  - A workload entry means comfort with the **workload as a whole**, not every feature in it. Later skills can still explain specific features inside it (e.g. Eventstream schema sets within RTI), just at a higher starting depth.

### 4. Confirm and hand off

- Show a compact summary (5–6 lines max) and the file path, so the user knows they can read or edit it themselves.
- Then:
  - **If another skill sent the user here:** go straight back to their original question. No suggestions.
  - **Otherwise:** suggest **two or three next prompts** that fit the profile. For example, an analyst interested in features might get:
    - "What's new in Power BI and semantic models this month?"
    - "Explain Direct Lake like I know Import mode well"
- Suggestions are prompts to try, not claims. Don't state facts about Fabric features, dates or releases here. This skill has fetched no sources, and every factual statement this plugin makes needs a citation.

## Update mode

Use this when a profile exists and the user wants to change it. Typical reasons:
- They have more Fabric experience now.
- They've moved into new workloads.
- Their interests have shifted.

- **Don't re-run Round 1 from scratch.** Role and background rarely change, and re-asking everything feels pointless.
- Ask which sections to update (one `AskUserQuestion`, multi-select), showing each section's current value in its option description:

| Option | Re-asks |
|---|---|
| Experience & workloads | Q2, then Q6–Q7 if experience ≠ Not yet |
| Depth & interests | Q8, Q9 |
| What I know / want to learn | Round 4 free text, **merged** into existing lists |
| Role & background | Q1, Q3, then Q4 / Q5 if their conditions hold |

- **Use what the user already said.** If their message states a new value (e.g. "I'm experienced now and work with RTI daily"), don't ask that question again. Take the value, preselect it in the section picker, and show it in the before → after for confirmation. Ask only what's still unknown, in as few calls as the conditions allow.
- Re-ask only the chosen sections. Keep every other field exactly as it is.
- **Merge, never replace,** `known_topics` and `interests`:
  - Add new entries.
  - Remove an entry only when the user asks to.
  - **One exception:** a topic can't be in both lists. If a newly ticked workload (or a newly known topic) is already in `interests`, **move** it to `known_topics` and show the move in the before → after, e.g. "Real-Time Intelligence: want to learn → known (workload)".
- Group the re-asked questions the same way as the first run:
  - Unconditional ones in one call.
  - Conditional follow-ups (Q4–Q7) in the next call.
- If experience moves from "Not yet" to any other level, ask Q6–Q7 now. The user can answer them meaningfully for the first time.
- If a newly added field unlocks Q4 or Q5 (e.g. they add Software engineering), ask that follow-up too.
- When re-asking Q6–Q7, pre-describe the workloads already in the profile (e.g. "currently selected") so the user only ticks additions.
  - Newly ticked workloads are merged into `workloads` and `known_topics`.
  - Unticked ones are removed from `workloads` only, and only if the user confirms. Leave `known_topics` alone: knowing a workload doesn't stop being true when you stop using it.
- Keep `created_at`. The helper updates `updated_at`.
- Before writing, show a short before → after for each changed field.

**Single-field changes** don't need the questionnaire at all:
- **Preference or questionnaire fields** (e.g. "switch me to deep dives", "I'm a data engineer now"): read the profile, change that one field, show before → after, and write it back.
- **Known topics and interests** (e.g. "I've now learned Eventstreams", "add Dataflows Gen2 to what I want to learn"): hand off to `fabric-progress`, which owns those edits and keeps them consistent with the learning log.
- Don't promote topics to `known_topics` just because they came up in conversation. That's always the user's decision.

## Privacy

- The profile stays on the user's machine and is never sent anywhere.
- It holds no names, email addresses, employers, tenant or workspace IDs, or credentials.
- If the user volunteers any of these during onboarding:
  - Leave them out of the profile.
  - Remind them briefly not to share credentials or personal details in their answers.
