# Proposed features

Ideas that have been researched or planned but aren't scheduled yet. Each links to its full proposal where one exists.

| Feature | Status | Summary | Proposal |
|---|---|---|---|
| GitHub Copilot support (CLI + VS Code) | On hold. Planned, step 0 spike done | The plugin already installs in Copilot CLI from `.claude-plugin/` with no changes. The remaining work: make the skill text client-neutral, handle the missing web search tool, add install docs, and test in VS Code. | [github-copilot-support.md](proposals/github-copilot-support.md) |
| Microsoft 365 Copilot support | Not viable today | M365 skills only run in declarative agents (Frontier preview). The script sandbox has no network access or persistent storage, and SKILL.md is capped at 20k characters. Revisit if that changes. | See the M365 row in [github-copilot-support.md](proposals/github-copilot-support.md#context) |
| Codex support | Idea | Package the skills for OpenAI Codex. Not researched yet. | — |
