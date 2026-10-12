# Data model (shared)

- The one definition of the plugin's local state, and of the helper that reads and writes it. All four skills follow it.
- The helper is `scripts/profile.py` (standard library only). It validates everything it writes, so a skill can't write a malformed record.

## Where the data lives

```
~/.claude/fabric-learning/        (or $FABRIC_LEARNING_HOME if set)
├── profile.json                  learner profile
├── learning-log.jsonl            one JSON object per line: learn sessions and catch-ups
└── cache/                        temporary: catch-up checkpoints, HTTP cache for the source scripts
```

- Outside the plugin folder, so it survives plugin updates and reinstalls.
- **No PII.** The helper rejects email addresses and GUIDs (tenant and workspace IDs) anywhere outside URLs.

## Ownership

| Data | Written by | Notes |
|---|---|---|
| Questionnaire and preference fields (role, experience, workloads, background, depth, interest areas) | `fabric-onboard` | |
| `known_topics`, `interests` | `fabric-progress` | Two shortcuts: `fabric-learn`'s one-click "Mark as learned", and `fabric-catchup`'s "Add to my interests". Onboarding's first run seeds both lists. |
| Log entries | `fabric-learn`, `fabric-catchup` | Append-only. Only `fabric-progress` deletes entries, on request. |

- **Edit pattern:** `show` → change the field → `write`. Never write `summary` output back: it contains derived fields.

## Helper commands

```bash
# `profile.py` = python3 <skill-base-dir>/../../scripts/profile.py
# Write the full path in every command: a shell variable holding the command breaks in zsh.
# If `python3` is not found (common on Windows), use `python` or `py -3`.
profile.py show [--raw]              # profile JSON. Exit 1: no profile. Exit 2: invalid (error on stderr; --raw also prints the stored JSON so one field can be fixed)
profile.py write [--replace-invalid] < profile.json   # validate + atomic write; refuses to overwrite an invalid profile unless --replace-invalid
profile.py append < entry.json       # validate + append one log entry; the helper stamps `ts` (omit it)
profile.py log [--skill S] [--topic T] [--since YYYY-MM-DD] [--last]   # query entries (JSONL). --topic: case-insensitive substring match on learn topics and catch-up item titles
profile.py summary                   # aggregate view (below)
profile.py catchup-state             # where "since last time" starts + every item already shown (below)
profile.py forget (--topic T [--contains] | --before YYYY-MM-DD) [--dry-run]
profile.py export --format md|json --out PATH
profile.py reset [--dry-run]         # delete profile, log and cache
profile.py paths
```

- **Exit codes for every command:** 0 OK, 1 nothing there (no profile), 2 invalid input or state (message on stderr names the field).
- **Profile states every skill must handle:**
  - **Exit 1 (no profile):** offer `fabric-onboard`.
  - **Exit 2 (invalid profile, e.g. hand-edited):**
    - Don't onboard over it, and don't write over it.
    - Continue unpersonalised.
    - Tell the user in one line that `fabric-progress` can fix it.
- `forget --topic` matches **whole topics** (ignoring case, spacing and punctuation). `--contains` switches to substring matching, so offer it only after showing a dry run.
  - Learn entries that match are deleted.
  - In catch-up entries, only the matching **items** are removed. The entry and its window stay, so "since last time" keeps working.
  - `forget --before` deletes whole entries, catch-ups included.
- Rewriting the log never drops lines it can't parse.

## profile.json

```json
{
  "schema_version": 1,
  "created_at": "2026-10-08T19:30:00Z",
  "updated_at": "2026-10-08T19:30:00Z",
  "onboarding_skipped": false,
  "role": "Data engineer",
  "experience": "regular",
  "workloads": ["data-engineering", "rti"],
  "background_fields": ["data", "software"],
  "background_platforms": ["Databricks"],
  "background_stack": ["python"],
  "preferences": { "depth": "examples" },
  "interest_areas": ["features", "community-tools"],
  "known_topics": [ { "topic": "Lakehouse", "source": "self-reported", "added_at": "2026-10-08" } ],
  "interests":    [ { "topic": "Fabric IQ Ontologies", "source": "self-reported", "added_at": "2026-10-08" } ]
}
```

- Only `schema_version` is required. `write` fills missing fields with empty defaults, and `preferences.depth` with `examples`.
- **Omit `created_at` / `updated_at`.** The helper stamps them and keeps the original `created_at`.
- Workload-level known topics use fixed labels: Data engineering · Warehousing & SQL · Power BI & semantic models · Real-Time Intelligence · AI & agents. A workload entry doesn't make the topics inside it known.
- A topic can't be in both `known_topics` and `interests`, and can't appear twice in either.
- `known_topics[].source`: `self-reported` · `self-reported (workload)` · `learned (fabric-learn)`.
- `interests[].source`: `self-reported` · `catch-up`.
- Value mappings for questionnaire fields are defined in `fabric-onboard`. "Other" answers are stored as typed.

## Log entries

**fabric-learn:**

```json
{
  "ts": "2026-10-10T18:05:00Z",
  "skill": "fabric-learn",
  "topic": "Fabric IQ Ontologies",
  "question": "What are Ontologies in Fabric?",
  "type": "concept",
  "depth": "examples",
  "status": "preview",
  "sources": ["https://learn.microsoft.com/…"],
  "related_topics": [ { "topic": "Fabric data agents", "url": "https://learn.microsoft.com/…" } ]
}
```

- `type`: `concept` · `how-to` · `scenario-design` · `admin-setting` · `comparison` · `problem-solving` · `tool-discovery`.
- `status`: the cited release status of the main topic: `preview` · `ga` · `deprecated` · `retired` · `planned` · `unknown`.
- `related_topics`:
  - Only topics a **cited source** links to this one, e.g. a docs "Next steps" section or the next module in a training path.
  - `url` is the URL of that cited source: the page that links the related topic. The helper rejects entries without one.
- For problem solving:
  - `topic` is a **short subject label** (2–5 words), e.g. "Spark notebook timeouts", so it can be found and forgotten by name.
  - `question` is a **generic** description, e.g. "Spark notebook times out on a large left join".
  - Never the pasted error text.

**fabric-catchup:**

```json
{
  "ts": "2026-10-10T18:30:00Z",
  "skill": "fabric-catchup",
  "scope": "since-last-time",
  "label": "Since 12 Jun",
  "window": { "from": "2026-06-12", "to": "2026-10-10" },
  "coverage": "last-30-days",
  "uncovered": { "from": "2026-06-12", "to": "2026-09-09" },
  "items": [ { "title": "Fabric IQ in Microsoft Copilot", "url": "https://…", "status": "ga" } ]
}
```

- `scope`: `since-last-time` · `period` · `event` · `topic-news`.
- `topic`: the topic filter for `topic-news` (or a filtered period), otherwise `null`.
- `coverage`: `full` · `highlights` · `month-by-month` · `last-<n>-days`.
- `uncovered`: only when the user chose a shorter range than the gap.
- `items`: only the items **shown**, each with its status at the time (`n/a` for tools, packages and community picks).

## `summary` output

```json
{
  "paths": { "dir": "…", "profile": "…", "log": "…" },
  "profile": { "exists": true, "valid": true, "error": null, "onboarding_skipped": false,
               "created_at": "…", "updated_at": "…", "role": "…", "experience": "…",
               "workloads": [], "background_fields": [], "background_platforms": [], "background_stack": [],
               "depth": "examples", "interest_areas": [] },
  "known_topics": [ { "topic": "…", "source": "…", "added_at": "…", "last_status": "ga", "last_covered": "…" } ],
  "interests":    [ { "topic": "…", "source": "…", "added_at": "…", "covered": false } ],
  "covered_not_known": [ { "topic": "…", "last_ts": "…", "type": "concept", "sessions": 2, "status": "preview",
                           "related_topics": [ { "topic": "…", "url": "…" } ] } ],
  "related_suggestions": [ { "topic": "…", "url": "…", "from_topic": "…", "from_ts": "…" } ],
  "learn":   { "sessions": 0, "first_ts": null, "last_ts": null },
  "catchup": { "count": 0, "last": { "ts": "…", "label": "…", "window": {} }, "items_shown": 0,
               "open_gaps": [ { "from": "…", "to": "…" } ],
               "items_matching_interests": [ { "title": "…", "url": "…", "status": "…", "shown_on": "…", "interests": ["…"] } ] },
  "log_issues": { "malformed_lines": 0 }
}
```

- Topics are matched ignoring case, spacing and punctuation.
- `last_status` / `last_covered`: from the most recent learn entry for that topic, or `null`.
- `profile.valid`: `true` / `false`, or `null` when there's no profile, so "missing" is never mistaken for "invalid".
- `related_suggestions`: related topics from **every** learn session (each with its cited URL), minus anything already known or covered.
- `open_gaps`: skipped catch-up periods minus every later catch-up's window. They close by themselves once covered.
- `items_matching_interests`: logged catch-up items whose title contains an interest as a whole phrase.

## `catchup-state` output

```json
{
  "catchups": 3,
  "since_last_time_from": "2026-10-10",
  "last": { "ts": "…", "label": "…", "scope": "…", "window": {}, "coverage": "…" },
  "shown": { "https://… | fabric iq in microsoft copilot": { "url": "https://…", "title": "Fabric IQ in Microsoft Copilot", "status": "preview", "shown_on": "2026-09-24" } }
}
```

- `since_last_time_from`: the latest `window.to` among **general** catch-ups (`since-last-time`, and `period` without a topic). Event and topic-news digests don't move it, because they only cover a slice of the news.
- `shown`: every item shown in any catch-up, keyed `"<url> | <normalised title>"` (one feature-summary URL anchors many items), with its status then. Used for de-duplication and spotting status changes.
