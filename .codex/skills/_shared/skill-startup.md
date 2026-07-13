# Skill Startup

Use this startup sequence for non-OpenSpec, non-configure delivery skills before reading or mutating delivery state.

## Read Order

1. `.codex/skills/_shared/repo-startup.md` — always-active skill policy (caveman, ponytail)
2. `.codex/memory/memory_summary.md`
3. `.codex/memory/MEMORY.md`
4. `.codex/project-profile.json`
5. `.codex/project-profile.local.json` when present
6. `.codex/skills/_shared/provider-adapter-contract.md`
7. `.codex/skills/_shared/delivery-contract.md`
8. `.codex/delivery-policy.json`
9. `docs/context-management.md`
10. Stage-specific docs named by the skill, such as `docs/architecture.md`, `docs/development.md`, or `docs/deployment.md`

Use memory only for recall and discovery. Verify task-critical facts against the current user request, OpenProject, OpenSpec, Gitea, Nexus, Azure, Git, current files, or live command output before acting.

## Common Rules

- Apply the authority order in `docs/context-management.md`.
- Apply Tool And Skill Blocker Consent from `.codex/skills/_shared/delivery-contract.md`: if a required repo skill, command, memory rule, definition, or configured tool/install path cannot be applied, stop the affected flow, report the current-flow fix and viable alternative with risk, and ask the user before continuing through the alternative.
- Treat `.codex/project-profile.json` as the tracked non-secret declaration of common providers, workflow gates, environments, and adapter paths. Treat ignored `.codex/project-profile.local.json` as a local overlay for stack choices and project-specific adapter experiments.
- Load only the provider adapters selected by the merged project profile for the current stage. Keep provider-specific API calls, CLI commands, field names, versions, and images out of generic skill reasoning unless the selected adapter requires them.
- Use `python -m tools.sdd_cli memory search --query <symptom>` for symptom-driven memory lookup when a task mentions or reveals an error, blocker, failed command, deploy issue, PR feedback, QA failure, configuration mismatch, or local tooling problem.
- When searching the repository for symbols, references, definitions, cross-files, or structural context, prefer codegraph as the first source when the codegraph MCP/client tool is available.
 - When searching the repository for documentation, Codex skills, provider adapters, or model-integration notes, prefer the monorepo docs MCP (`monorepo-docs-search`) as the first source. See `.codex/mcp-instructions.md` for detailed guidance.
 - When a user request requires searching repository documentation, Codex skills, provider adapters, or model-integration notes, always use the monorepo docs MCP server `monorepo-docs-search` (invoke via tool `mcp_monorepo-mark_search_documentation`) as the first source. See `.codex/mcp-instructions.md` for detailed guidance. If the MCP tool is unavailable or returns no results, fall back to local `file_search`/`grep_search` after confirming with the user.
- Apply stable markers, ticket context locks, rerun behavior, artifact lineage, release manifests, versioning, PR labels, and failure rules from `.codex/skills/_shared/delivery-contract.md`.
- Apply the merged project profile for ticket key format and `.codex/delivery-policy.json` for `agentOptimization` defaults such as retry limits, prompt-cache ordering, telemetry output, and workflow eval paths when the platform exposes the needed data.
- Use `python -m tools.sdd_cli delivery <Mode>` for deterministic mechanics when the skill names helper functions.
- Never print, commit, paste into tickets, or store real tokens, cookies, session values, Azure credentials, Nexus credentials, Gitea tokens, OpenProject tokens, secret-bearing URLs, or sensitive payloads.

## Durable Learning Capture

At handoff for any non-trivial repo work, decide whether the run discovered reusable knowledge. This is not limited to QA or ticket delivery; it applies to any error, issue, blocker, configuration repair, local tooling fix, test harness fix, or debugging result that could help solve a similar situation later.

- Authoritative project or workflow context -> update `docs/`.
- Enforceable automation behavior -> update `.codex/skills/_shared/delivery-contract.md` plus affected skills and tests.
- Reusable but non-authoritative knowledge -> update `.codex/memory/` using `.codex/memory/retrieval-policy.md#update-process`.

Report the result in the final handoff as either `Memory updated: <files>` or `Memory updated: none`. If no reusable knowledge was found, do not add memory noise.
