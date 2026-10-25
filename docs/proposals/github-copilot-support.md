# Plan: GitHub Copilot support for fabric-learning

> **Status: implemented (2026-10-25).** Copilot CLI 1.0.103 passed the pre-written acceptance suite (20 of 21; the one failure is a test flaw that fed tool logs to the citation checker, and the answer text itself passes). VS Code was tested by hand. Remaining: Claude Code regression run, and the `fabric-researcher` worker script-access issue seen in VS Code (mitigated in sourcing-rules.md, not root-caused).

## Step 0 findings (Copilot CLI 1.0.97, tested 2026-10-13)

Tested with a local marketplace install (`copilot plugin marketplace add <clone>` then `copilot plugin install fabric-learning@fabric-learning`) in an isolated `COPILOT_HOME`.

| Check | Result |
|---|---|
| Plugin install from `.claude-plugin/` | Works as-is. "Installed 4 skills." Local marketplaces are loaded live, not copied. |
| Skills | All 4 listed and attributed to the plugin. `fabric-learn` auto-loaded from a Fabric question without being named. |
| `agents/fabric-researcher.md` | Loads as `fabric-learning:fabric-researcher` and can be dispatched via `task`. **No rename to `.agent.md` needed.** Step 1's rename is unnecessary. |
| `model: sonnet` / `maxTurns` | Didn't block loading. Whether they take effect wasn't checked. |
| `<skill-base-dir>` | Resolved correctly to `<plugin>/skills/<skill>`, so `../../scripts/...` paths work. |
| `ask_user` | Present in interactive sessions. It's disabled in `-p` (non-interactive) mode. |
| **Web search** | **No web search tool.** Only `web_fetch` is available, and it needs URL approval. |
| VS Code | Not tested yet. |

**Open decisions before resuming:**

1. **Web search gap.** The scripts (Learn, Reddit, GitHub, YouTube, forum, blogs) still work. The `web` source (community blogs) and every script's "fall back to web search" path don't. Options:
   - degrade gracefully: skip the lane and report it as a gap (no new code)
   - add a keyless search script (fragile, and may conflict with the site's terms)
   - document a web-search MCP server that users add with their own API key
2. **VS Code check.** Agent plugins can't be driven from a CLI session, so someone needs to test them by hand with `chat.pluginLocations`.

## Context

fabric-learning is packaged as a Claude Code plugin (`.claude-plugin/`, `skills/`, `agents/`, `scripts/`). Fabric users mostly work in M365 Copilot or GitHub Copilot, so the goal is to reach them there too.

**Research findings (task 1):**

| Target | Can it take this plugin? | Why |
|---|---|---|
| **GitHub Copilot CLI** | **Yes, almost as-is** | Reads `.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json`. Default component dirs are `skills/` and `agents/`. Accepts Claude tool names (`Bash`, `Read`, `Write`, `WebSearch`, `WebFetch`) as aliases in agent `tools:`. Install: `copilot plugin marketplace add blaine12100/fabric-learning` then `copilot plugin install fabric-learning@fabric-learning`. |
| **VS Code (Copilot agent plugins)** | **Yes** | Lists "Claude: `.claude-plugin/plugin.json`" as a supported format. Installs from marketplaces, Git URLs or a local path (`chat.pluginLocations`), and also picks up plugins already installed by Copilot CLI. |
| **M365 Copilot** | **No (skipped)** | Skills exist only in declarative agents, which are a Frontier preview. The script sandbox has no network access and no package installs, so `gather.py` and friends can't run. There's no persistent storage for the profile, and SKILL.md is capped at 20k chars (fabric-learn and fabric-catchup are ~26k). Revisit if the sandbox gains network access. |

**Decisions made with you:** Copilot CLI + VS Code only. No M365. Codex is out of scope (not built yet). Keep the data dir at `~/.claude/fabric-learning` so Claude and Copilot share one profile.

**What's left to do:** most of the work is making the skill text client-neutral where it names Claude-only tools. Then fix the one agent-file incompatibility (if it turns out to be one), and document installation.

## Step 0: Spike to confirm the unknowns (no repo changes)

Install Copilot CLI (`npm install -g @github/copilot`), add this repo as a local marketplace (`copilot plugin marketplace add ./`), install the plugin, and check:

1. `/skills list` shows all 4 skills, and `/skills info` attributes them to fabric-learning.
2. Whether `agents/fabric-researcher.md` loads. The plugin reference says agent dirs contain `.agent.md` files, while the custom-agents reference accepts `.md` or `.agent.md`.
3. Whether `model: sonnet` and `maxTurns: 20` in the agent frontmatter are ignored, warned about, or rejected.
4. How each skill's directory reaches the model, so `<skill-base-dir>/../../scripts/...` resolves (Claude passes "Base directory for this skill").
5. Exact slash-command form for plugin skills in Copilot CLI (`/fabric-onboard` vs `/fabric-learning:fabric-onboard`).
6. Repeat 1–5 in VS Code via `chat.pluginLocations` pointing at the local clone.

The results decide which of steps 1–2 below are needed. I'll report them back before editing.

## Step 1: Agent file compatibility (only if step 0 shows a problem)

- If `.md` isn't picked up: rename [agents/fabric-researcher.md](../../agents/fabric-researcher.md) to `agents/fabric-researcher.agent.md`. Claude Code takes the agent name from the frontmatter `name`, so it keeps working. I'll check that in Claude Code too.
- If `model: sonnet` breaks Copilot: drop the field and note it in the README (Claude would then use the session model for research workers). The alternative is a separate Copilot copy, which I'd avoid because it duplicates the file.
- Leave `tools: Bash, Read, Write, WebSearch, WebFetch` as is. All of them are documented aliases.

## Step 2: Make skill text client-neutral

The same pattern applies everywhere: wherever a Claude tool name is an instruction, name the capability and give both clients' tool names. The existing "if unavailable, fall back" wording is already there in most places, so these are small edits.

| Where | Today | Change |
|---|---|---|
| `AskUserQuestion` (onboard ×3, learn ×3, catchup ×3, progress ×6) | "Use the `AskUserQuestion` tool when available" + plain-text fallback | "the ask-the-user tool (`AskUserQuestion` in Claude Code, `ask_user` in Copilot)". Keep the plain-text fallback. Round-per-call wording stays, plus a note that Copilot may ask one question per call. |
| `<skill-base-dir>` (all 4 skills, `references/*.md`) | Assumes Claude provides it | One line near the top of each skill: "`<skill-base-dir>` = the directory containing this SKILL.md." Wording depends on the step 0 finding. |
| `WebSearch` / `WebFetch` ([references/sourcing-rules.md:127](../../references/sourcing-rules.md#L127), [scripts/learn.py:40](../../scripts/learn.py#L40) fallback text) | Claude names | "web search / web fetch tools" with both clients' names |
| Subagent dispatch ([references/sourcing-rules.md:129-154](../../references/sourcing-rules.md#L129-L154), catchup:127, learn:135) | "spawn `fabric-researcher` subagents" | Add: in Copilot this is the `task` tool with the `fabric-researcher` custom agent. The existing "if subagents are unavailable, research inline" fallback already covers VS Code if agents don't load. |
| "Claude Code" mention ([references/sourcing-rules.md](../../references/sourcing-rules.md)) | Claude-specific | Generalise, or keep it where it's a citation (the Anthropic multi-agent cost link stays). |

Skill `description` frontmatter stays unchanged (within Copilot's 1024-char limit, to be checked in step 0).

## Step 3: Manifests

- Keep `.claude-plugin/` as the single source. Copilot CLI and VS Code both read it, so I won't add a second `plugin.json`, to avoid drift.
- [.claude-plugin/marketplace.json](../../.claude-plugin/marketplace.json): change "An unofficial Claude Code plugin…" to client-neutral wording ("An unofficial agent plugin for Claude Code and GitHub Copilot…").
- Add `"copilot"` / `"github-copilot"` to `keywords` in [.claude-plugin/plugin.json](../../.claude-plugin/plugin.json).

## Step 4: README

- Add a badge for GitHub Copilot next to the Claude Code one.
- Intro: "a Claude Code plugin" → "a plugin for Claude Code and GitHub Copilot".
- **Install** section: three tabs/subsections, Claude Code (existing), **Copilot CLI** (`copilot plugin marketplace add …` / `copilot plugin install …`, then restart the session), **VS Code** (Extensions view `@agentPlugins`, or "Chat: Install Plugin From Source" with the repo URL, or `chat.plugins.marketplaces`). Each includes a local-clone variant.
- Requirements: list Copilot CLI / VS Code with agent plugins enabled (`chat.plugins.enabled`).
- Slash-command column in "The four skills": show per-client forms from step 0.
- Short "Why not M365 Copilot?" note (sandbox has no network, no storage, Frontier-only).
- Data location note: both clients share `~/.claude/fabric-learning` (or `$FABRIC_LEARNING_HOME`).

## Files touched

- [agents/fabric-researcher.md](../../agents/fabric-researcher.md) (possibly renamed, frontmatter)
- [skills/fabric-onboard/SKILL.md](../../skills/fabric-onboard/SKILL.md), [skills/fabric-learn/SKILL.md](../../skills/fabric-learn/SKILL.md), [skills/fabric-catchup/SKILL.md](../../skills/fabric-catchup/SKILL.md), [skills/fabric-progress/SKILL.md](../../skills/fabric-progress/SKILL.md)
- [references/sourcing-rules.md](../../references/sourcing-rules.md), [references/data-model.md](../../references/data-model.md)
- [scripts/learn.py](../../scripts/learn.py) (fallback hint text only)
- [.claude-plugin/marketplace.json](../../.claude-plugin/marketplace.json), [.claude-plugin/plugin.json](../../.claude-plugin/plugin.json)
- [README.md](../../README.md)

No changes to the Python logic, data model or data directory.

## Verification

1. `python3 -m unittest discover tests` passes (script text change only).
2. **Copilot CLI**: from a local marketplace install, run the four smoke prompts from the README's "first five minutes":
   - "Set up my Microsoft Fabric learning profile": questions are asked via `ask_user` or plain text, and the profile is written to `~/.claude/fabric-learning`.
   - "How does Direct Lake fall back to DirectQuery…": scripts run, the answer has `[n]` citations, and `check_citations.py` runs.
   - "Catch me up on Fabric over the last 3 months": `fabric-researcher` is dispatched via `task` (max 2), or falls back inline.
   - "What should I learn next?": reads the log written above.
3. **VS Code**: same four prompts with the plugin loaded via `chat.pluginLocations`.
4. **Claude Code regression**: reinstall from the local marketplace and run the same four prompts. Confirm `AskUserQuestion` rounds, subagent dispatch and slash commands are unchanged.
5. Fresh-clone install test of the published repo in Copilot CLI (`copilot plugin marketplace add blaine12100/fabric-learning`) after pushing.

## Sources

- Copilot CLI plugin reference: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference
- Copilot CLI marketplace: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-marketplace
- Copilot CLI skills: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-skills
- Custom agents config (tool aliases): https://docs.github.com/en/copilot/reference/custom-agents-configuration
- VS Code agent plugins: https://code.visualstudio.com/docs/agent-customization/agent-plugins
- VS Code agent skills: https://code.visualstudio.com/docs/agent-customization/agent-skills
- M365 declarative agent skills (preview): https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/declarative-agent-skills
