---
name: fabric-progress
description: >-
  Shows and manages the user's Microsoft Fabric learning progress (what they've covered, what they know, what
  they want to learn, their catch-up history) and recommends what to learn next from their own history. Owns
  day-to-day edits to known topics and interests, and the user's fabric-learning data. Use this whenever the
  user asks what have I learned, show my Fabric progress, what should I learn next, mark Eventstreams as
  learned, I don't really know Direct Lake after all, add or remove a topic from my learning list, which of my
  topics might be out of date, export my learning history, where is my data, or wants to delete, erase or wipe
  their fabric-learning data. Redoing the setup questions is fabric-onboard; research is fabric-learn; news is
  fabric-catchup. Never acts on a Fabric tenant; learning only. Not Daniel Miessler's fabric CLI or Azure
  Service Fabric.
---

# Fabric progress

## Purpose

- Give the user a clear view of their Fabric learning journey, and let them steer it:
  - **Where am I?** What they've covered, what they know, what's still on their list.
  - **What next?** Recommendations drawn from their own profile and history.
  - **Keep it accurate.** Mark topics known or not, and edit interests. This skill **owns** these edits.
  - **Own the data.** See where it lives, export it, delete it.
- It works only on the **local state** written by the other skills. It doesn't search or teach:
  - Explaining a topic, or questions like "what should I study for DP-700" → `fabric-learn`.
  - What's new, including skipped catch-up periods → `fabric-catchup`.
  - Re-answering the setup questionnaire → `fabric-onboard`.
- It can't see progress anywhere else, e.g. Microsoft Learn training progress. Say so if asked.
- This plugin is **for learning only**. It never connects to anything in the user's Fabric tenant.

## Ground rules

- **No new Fabric facts.** This skill has no sources to cite.
  - Recommendations name **topics**, never claims. "Learn about Eventstreams next" is fine. "Eventstreams now supports X" is not.
  - It may repeat a **logged** item, with the URL cited at the time and its date, worded as history:
    - "From your 24 Sep catch-up: Fabric IQ in Copilot — GA as of then [link]; may have changed since."
  - Relationships between topics come only from `related_topics` in learn log entries, which came from cited research. Never from general knowledge.
- **Only the user decides what they know.**
  - Never add to or remove from `known_topics` without the user asking and confirming.
  - Coverage in the log is **not** knowledge. Work out what's known only from `known_topics`.
- **Every profile edit is shown as before → after and confirmed** before writing. That includes additions.
- **Never lose history silently.** Deletions say exactly what will be removed and what side effects follow, and need explicit confirmation.
- **Topics are matched carefully:**
  - Treat strings that differ only in case, spacing or punctuation as the same topic (e.g. "Direct Lake" / "direct-lake").
  - Anything else that might be the same, e.g. "Direct Lake" vs "Direct Lake mode", or a possible rename: **ask** the user. Never merge because you assume a rename. That would be an uncited fact.
- **Privacy:** the data is local. Never send it anywhere or use it in searches. Topics the user types are stored as typed, so apply the no-PII rule: leave out employer names, people's names, tenant or workspace names.
- If `AskUserQuestion` isn't available, ask the same options as a numbered list in plain text.

## Data

- The profile, log entries, helper commands and the `summary` output are defined in the shared [data model](../../references/data-model.md). Read it before editing anything.

```bash
# `profile.py` = python3 <skill-base-dir>/../../scripts/profile.py
# Write the full path in every command: a shell variable holding the command breaks in zsh.
profile.py summary                    # start here: aggregate view of profile + log
profile.py show / write             # edit pattern: show → change the field → write
profile.py log [--skill S] [--topic T] [--since D] [--last]
profile.py forget (--topic T [--contains] | --before D) [--dry-run]
profile.py export --format md|json --out PATH
profile.py reset [--dry-run]
```

- `<skill-base-dir>` is the "Base directory for this skill" path shown when this skill loads.
- **Never print the raw log.** Use `summary`, plus filtered `log` queries for detail. Logs grow large.
- **Never write `summary` output back.** It contains derived fields (`last_status`, `covered`…). Edit with `show` → change → `write`.

## Flow

### 1. Load state

- Run `profile.py summary` and pick the matching case:
  - **No profile and no log:** say there's nothing to show yet, in one line, and offer `fabric-onboard`. Stop.
  - **Profile invalid** (`profile.valid: false`, e.g. hand-edited):
    - Show the validator's error in one line.
    - **Never** `write` over it wholesale.
    - **To fix one field:** run `profile.py show --raw` to get the stored JSON, correct only the named field, show the before → after, and write it with `write --replace-invalid` after the user confirms.
    - Offer to fix only the field it names, with a before → after.
    - Until it's fixed, show only the log-based sections (covered topics, catch-ups), and make no edits.
    - If the user chooses to replace the profile instead, use `write --replace-invalid`, after confirming.
  - **Profile has `onboarding_skipped: true`:** leave out the profile lines in the Overview, and suggest onboarding once.
  - **Log only, no profile:** work from the log, and suggest onboarding once.
  - **`log_issues.malformed_lines` > 0:** mention it in one line (e.g. "2 log lines couldn't be read and were skipped"). Don't try to repair them.

### 2. Work out what the user wants

| Mode | Example requests | Go to |
|---|---|---|
| **Overview** | "show my progress", "what have I learned?" | [Overview](#overview) |
| **What next** | "what should I learn next?" | [What next](#what-next) |
| **Update knowledge** | "mark Eventstreams as learned", "I don't actually know Direct Lake" | [Update knowledge](#update-knowledge) |
| **Manage interests** | "add Dataflows Gen2 to my list", "drop Copilot from my interests" | [Manage interests](#manage-interests) |
| **Refresh check** | "which of my topics might be out of date?" | [Refresh check](#refresh-check) |
| **Export** | "export my learning history" | [Export](#export) |
| **Data** | "where is my data?", "forget everything about Copilot", "delete all my data" | [Data management](#data-management) |

- **Vague request** ("fabric progress"): show the Overview. Its closing picker covers the other modes.
- **Hand off instead when:**
  - The request names a topic to *learn about* ("what should I learn next about RTI?") → `fabric-learn`.
  - It's about what's new or a skipped period ("what did I miss in the summer?") → `fabric-catchup`.
- **"What have I learned about <topic>?"** Answer from the log (dates, question types, sources), then offer a recap via `fabric-learn`.

### Overview

- One screen. Leave out empty sections:

```
Your Fabric learning — since <the earliest of profile.created_at, learn.first_ts and the first catch-up's ts>

Profile      <role> · <experience> · <workloads> · depth: <depth>
Coming from  <background fields / platforms / stack>

✔ Known topics (<n>)
  <topic> — self-reported · <date>
  <topic> — self-reported (workload) · <date>
  <topic> — learned via fabric-learn · <date>

◐ Covered, not yet marked as known (<n>)
  <topic> — <type> · <sessions> session(s) · last <date>

☐ Want to learn (<n>)
  <interest> — added <date> · <covered / not covered yet>

↻ Catch-ups
  Last: <date> (<label>) · <count> catch-ups · <items_shown> items shown
  Skipped and still open: <from> – <to>

Activity     <sessions> learn sessions · <count> catch-ups · last active <date>
```

- **"Covered, not yet marked as known"** is the most useful list: things the user has studied but hasn't claimed. It comes straight from `covered_not_known`.
- Show the 8 most recent entries per list, plus "+N more".
- Then go to [Next steps](#next-steps).

### What next

- Recommend **3–5 topics**, each with a one-line reason taken from the user's own data:

| Signal | Example |
|---|---|
| An interest not yet covered | "Fabric IQ Ontologies — on your list since 8 Oct" |
| Covered but not marked known | "Review Direct Lake — covered 3 Sep, not marked as known" |
| `related_suggestions` (cited links from past sessions, not yet covered or known) | "Eventhouse — linked from your 12 Sep Eventstreams session [link]" |
| `catchup.items_matching_interests`, not yet studied | "From your 24 Sep catch-up: <item> [link]" |
| `interest_areas` includes `community-tools` and a past catch-up showed new tools (`profile.py log --skill fabric-catchup`) | "Try <tool> from your 3 Oct catch-up [link]" |
| An open catch-up gap | "You skipped 12 Jun – 9 Sep" |

- At most two recommendations from the same signal, so there's variety.
- Then one `AskUserQuestion` (single-select): up to 3 of the recommendations, plus "None for now".
  - A topic → hand off to `fabric-learn` with that topic.
  - A gap → hand off to `fabric-catchup` for that period.

### Update knowledge

- **Mark as known:**
  - Match the topic against `interests` and `covered_not_known` (see the matching rules). Use the existing wording, so history lines up.
  - `source`:
    - `"learned (fabric-learn)"` if a learn session covered it.
    - Otherwise `"self-reported"`.
  - Remove it from `interests` if it's there.
- **Unmark** ("I don't actually know X"):
  - Remove it from `known_topics`, and offer to add it to `interests`.
  - Leave the log alone: it records what was covered, which is still true.
  - If the entry is `self-reported (workload)`, say that `workloads` is unchanged and can be updated via `fabric-onboard`.
- **Several topics at once:** one before → after for all of them, one confirmation.
- **Write** with `show` → change → `write`.
- **Choosing from a list** (e.g. "mark some of my covered topics as known"):
  - One `AskUserQuestion`, multi-select, with the 4 most recent candidates. The user can type others in "Other".
  - Never pre-select anything.

### Manage interests

- **Add:**
  - Append with `"source": "self-reported"` and today's date, after showing before → after.
  - If the topic is already in `known_topics`, ask whether to move it back to interests (relearn) or keep it as known.
- **Remove:** show before → after, and remove on confirmation.

### Refresh check

- Known topics can go stale as Fabric changes. **Workload-level entries** (`self-reported (workload)`) are too broad to refresh, so skip them. Using `fabric-learn`'s freshness windows, flag a known topic when:
  - `last_status` is `preview`, `planned` or `unknown`, and its latest date (`last_covered`, else `added_at`) is **more than 6 months ago**; or
  - `last_status` is `ga` or `null`, and its latest date is **more than 12 months ago**; or
  - `last_status` is `deprecated` or `retired`, whatever the age.
- A **workload-level** known topic (e.g. "Data engineering") doesn't make the topics inside it known. When recommending something inside a known workload, frame it as "go deeper in <workload>".
- List the flagged topics with their dates and the reason, e.g. "preview when you studied it, 8 months ago". Then offer one picker with at most 4 options: "Catch up on <topic>" for the top 2 flagged topics, "Full refresher on <top topic>", and "None for now":
  - **"Catch up on <topic> since <date>"** → `fabric-catchup`, Topic news scope, window starting at that date.
  - **"Full refresher on <topic>"** → `fabric-learn`.
- Never say something **has** changed. This skill hasn't checked. Say "may have changed since".

### Export

- Only when asked.
- Run `profile.py export --format md --out <path>` (or `json` if asked).
  - **Default path:** `./fabric-notes/<yyyy-mm-dd>-fabric-progress.md`. Use the user's path if they give one.
- Tell the user the path. Don't print the export in the terminal.

### Data management

- **Where is my data?** Show the paths from `summary`, and mention the user can open and read the files.
- **Forget part of the history** ("forget everything about Copilot", "delete history before June"):
  - Run `profile.py forget … --dry-run` and show what would be removed: learn entries, catch-up items, date range.
    - `--topic` matches whole topics. If it finds nothing, or the user clearly means a broader match, offer `--contains` and dry-run again.
    - With `--topic`, catch-up entries keep their windows. Only the matching items go.
    - **If a learn entry being deleted is the only record behind a known topic's status,** warn that the refresh check will stop flagging that topic. Suggest running the refresh check first.
  - **With `--before`, whole catch-up entries go too.** Warn: "Your next catch-up may repeat items from that period, and 'since last time' may start earlier."
  - Confirm with one `AskUserQuestion`: "Delete <n> entries" / "Cancel".
  - Run it without `--dry-run` and report what was removed.
  - Then ask separately whether to also remove matching `known_topics` / `interests`. Those are different things from the history.
    - Use the same matching as the forget call (whole topic, or `--contains` if that was used).
    - List the matching entries, and confirm before removing any.
- **Delete all my data** (reset):
  - Run `profile.py reset --dry-run` and show what would be deleted: the profile, the whole log and the cache folder inside the data directory. A cache relocated with `FABRIC_LEARNING_CACHE` is left alone.
  - Say it can't be undone, and that saved notes in `./fabric-notes/` aren't touched.
  - One `AskUserQuestion`: "Export first, then delete" / "Delete without export" / "Cancel".
  - After deleting, offer `fabric-onboard`.
- **Redo the questionnaire** without deleting history → `fabric-onboard`.

### Next steps

- After the Overview, and after any edit, end with **one** `AskUserQuestion` (single-select, 2–4 options) chosen from:
  - **What should I learn next?** → [What next](#what-next)
  - **Mark covered topics as known:** if `covered_not_known` isn't empty.
  - **Refresh check:** if any known topic would be flagged.
  - **Catch up on what I skipped:** if `open_gaps` isn't empty.
- Always include **"None for now"** as one of the options.
- Skip it if the user is clearly done.

## Out of scope

- **Explaining or researching topics:** `fabric-learn`.
- **What's new:** `fabric-catchup`.
- **Re-running the questionnaire:** `fabric-onboard`.
- **Progress on other platforms** (e.g. Microsoft Learn training): not visible to this plugin.
- **Anything in the user's tenant:** this plugin is for learning only.
