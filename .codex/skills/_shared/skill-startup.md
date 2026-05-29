# Skill Startup

Use this startup sequence for non-OpenSpec, non-configure delivery skills before reading or mutating delivery state.

## Read Order

1. `.codex/memory/memory_summary.md`
2. `.codex/memory/MEMORY.md`
3. `.codex/skills/_shared/delivery-contract.md`
4. `docs/context-management.md`
5. Stage-specific docs named by the skill, such as `docs/architecture.md`, `docs/development.md`, or `docs/deployment.md`

Use memory only for recall and discovery. Verify task-critical facts against the current user request, Plane, OpenSpec, Gitea, Nexus, Azure, Git, current files, or live command output before acting.

## Common Rules

- Apply the authority order in `docs/context-management.md`.
- Apply stable markers, ticket context locks, rerun behavior, artifact lineage, release manifests, versioning, PR labels, and failure rules from `.codex/skills/_shared/delivery-contract.md`.
- Use `.codex/skills/_shared/scripts/delivery_tools.ps1` for deterministic mechanics when the skill names helper functions.
- Never print, commit, paste into tickets, or store real tokens, cookies, session values, Azure credentials, Nexus credentials, Gitea tokens, Plane tokens, secret-bearing URLs, or sensitive payloads.

## Memory Updates

At handoff, decide whether the run discovered reusable knowledge:

- Authoritative project or workflow context -> update `docs/`.
- Enforceable automation behavior -> update `.codex/skills/_shared/delivery-contract.md` plus affected skills and tests.
- Reusable but non-authoritative knowledge -> update `.codex/memory/` using `.codex/memory/retrieval-policy.md#update-process`.

Report any memory update in the final handoff. If no reusable knowledge was found, do not add memory noise.
