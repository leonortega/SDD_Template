<!-- TIER 2: SEMI-STABLE - Core startup sequence, loaded every stage, changes rarely -->

# Skill Startup

Use this startup sequence for non-OpenSpec, non-configure delivery skills before reading or mutating delivery state.

## Read Order With Tier Markers

Load context in this order to maximize prompt caching. The tier markers indicate cache breakpoints.

### Tier 1 — Stable Prefix (cache once per session)

`.codex/skills/_shared/repo-startup.md` — always-active skill policy (caveman, ponytail)

> `<!-- CACHE BREAKPOINT: Tier 1 / Tier 2 boundary -->`

### Tier 2 — Semi-Stable (cache once per session)

1. `.codex/memory/memory_summary.md`
2. `.codex/memory/MEMORY.md`
3. `.codex/project-profile.json`
4. `.codex/project-profile.local.json` when present
5. `.codex/skills/_shared/provider-adapter-contract.md`
6. `.codex/skills/_shared/delivery-contract-core.md` — always-read core rules

> `<!-- CACHE BREAKPOINT: Tier 2 / Tier 3 boundary -->`

### Tier 3 — Stage-Specific (cache per stage)

7. `.codex/skills/_shared/delivery-contract-{ticket,review,qa,deploy,parallel}.md` — stage-specific contract
8. `.codex/delivery-policy.json` — optimization config, loaded here so Tier 1-2 stay fully stable
9. `docs/context-management.md` — context management fundamentals
10. Stage-specific docs named by the skill, such as `docs/architecture.md`, `docs/development.md`, or `docs/deployment.md`
11. `.codex/skills/_shared/api-helpers.md` when API calls are needed

> `<!-- CACHE BREAKPOINT: End cached context. Dynamic data below. -->`

### Tier 4 — Dynamic (never cached)

- Current user request / conversation
- Active ticket state and generated comments
- Git branch, dirty state, commit SHA
- PR state, labels, head SHA, CI status
- Nexus manifests, QA evidence, monitoring output
- Tool results, errors, retries, file contents

---

Use memory only for recall and discovery. Verify task-critical facts against the current user request, OpenProject, OpenSpec, Gitea, Nexus, Git, current files, or live command output before acting.

## Common Rules

- Apply the authority order in `docs/context-management.md`.
- Apply Tool And Skill Blocker Consent from `.codex/skills/_shared/delivery-contract.md`: if a required repo skill, command, memory rule, definition, or configured tool/install path cannot be applied, stop the affected flow, report the current-flow fix and viable alternative with risk, and ask the user before continuing through the alternative.
- Treat `.codex/project-profile.json` as the tracked non-secret declaration of common providers, workflow gates, environments, and adapter paths. Treat ignored `.codex/project-profile.local.json` as a local overlay for stack choices and project-specific adapter experiments.
- Load only the provider adapters selected by the merged project profile for the current stage. Keep provider-specific API calls, CLI commands, field names, versions, and images out of generic skill reasoning unless the selected adapter requires them.
- Use `python -m tools.sdd_cli memory-search search --query <symptom>` for symptom-driven memory lookup when a task mentions or reveals an error, blocker, failed command, deploy issue, PR feedback, QA failure, configuration mismatch, or local tooling problem.
- Follow the mandatory MCP routing contract in `.codex/mcp-instructions.md`. Docs/markdown → `monorepo-docs-search`, source code → `codebase-memory-mcp`. Do not use raw grep as the first approach.
- Apply stable markers, ticket context locks, rerun behavior, artifact lineage, release manifests, versioning, PR labels, and failure rules from `.codex/skills/_shared/delivery-contract.md`.
- Apply the merged project profile for ticket key format and `.codex/delivery-policy.json` for `agentOptimization` defaults such as retry limits, prompt-cache ordering, telemetry output, and Promptfoo eval paths when the platform exposes the needed data.
- Use `python -m tools.sdd_cli dev-flow <subcommand>` for deterministic mechanics when the skill names helper functions.
- Never print, commit, paste into tickets, or store real tokens, cookies, session values, Azure credentials, Nexus credentials, Gitea tokens, OpenProject tokens, secret-bearing URLs, or sensitive payloads.

## Durable Learning Capture

At handoff for any non-trivial repo work, classify whether the run discovered reusable knowledge. See `.codex/skills/_shared/delivery-contract-core.md` §Durable Learning Capture Gate for the full rule, handoff format (`Memory updated: <files>`), and mandatory gate requirements.
