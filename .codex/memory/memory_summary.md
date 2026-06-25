# Memory Summary

This repository is an agentic SDD/SDLC delivery lab. `.codex/project-profile.json` is the canonical non-secret stack/provider declaration, and `.codex/providers/` holds selected provider adapter behavior. The current profile moves tickets through OpenSpec planning, implementation, review, artifact promotion, deployment, E2E QA, explicit PROD promotion, rollback, and hotfix workflows.

Memory is guidance only. It must never override the latest user request, active ticket, active OpenSpec change, `.codex/project-profile.json`, `.codex/skills/_shared/delivery-contract.md`, canonical docs, current code, tests, workflow files, or live tool output.

## High-Signal Operating Context

- Repository root: `C:\Endava\EndevLocal\Personal\SDD_template`.
- Solution: `SDDTemplate.slnx`.
- App: `src/SDDTemplate.Site`.
- Tests: `tests/SDDTemplate.Site.Tests`.
- Delivery helpers: `tools/sdd_cli`.
- Durable docs: `docs/context-management.md`, `docs/architecture.md`, `docs/development.md`, and `docs/deployment.md`.
- Agent skills: `.codex/skills/`.
- Shared delivery contract: `.codex/skills/_shared/delivery-contract.md`.
- Project profile: `.codex/project-profile.json`.
- Provider adapters: `.codex/providers/`.
- OpenSpec changes: `openspec/changes`.
- Ticket key pattern: read from `.codex/project-profile.json`.
- Coverage threshold: `80%`.

## Core Workflow

```text
Configured Todo ticket
  -> branch + OpenSpec proposal
  -> implementation + tests
  -> configured review PR
  -> PR validation + Codex review agent
  -> merge to dev
  -> configured artifact package + DEV + QA
  -> E2E QA evidence
  -> configured ticket Done
  -> explicit PROD promotion to main/PROD
  -> rollback or hotfix when needed
```

## Common Commands

```bash
python -m tools.sdd_cli infra up
python -m tools.sdd_cli infra down
dotnet build ./SDDTemplate.slnx
dotnet test ./SDDTemplate.slnx
```

## Memory Use

- Read memory at the start of planning, implementation, review, QA, deployment, rollback, hotfix, and retrospective work.
- Use `MEMORY.md` as the index into deeper memory files.
- Use `python -m tools.sdd_cli memory search --query <symptom>` when debugging concrete errors, blockers, failed commands, deployment issues, PR feedback, QA failures, configuration mismatches, or local tooling problems.
- Write memory only for reusable, source-backed knowledge.
- Follow `retrieval-policy.md#update-process` when updating memory.
- Treat agent-caused or tool-discovered failures as memory candidates by default; if a command fails, a hook rejects an action, or a local tool/config mismatch is diagnosed, search memory with the symptom and persist a small update unless already covered or clearly one-off.
- Prefer updating canonical docs when the finding is authoritative workflow or architecture context.
- Keep secrets, tokens, local credentials, and ignored local runtime state out of memory.
- Before final handoff for any non-trivial repository work, report `Memory updated: <files>` or `Memory updated: none` after classifying reusable errors, blockers, fixes, configuration repairs, tooling corrections, and debugging results.
- Recent cross-thread lessons include worktree local-config sync, Gitea reviewer collaborator requirements, OpenProject comment payload fields, Gitea Actions shell/runtime assumptions, PR feedback batching, and live Azure app-to-app settings for topology deployments.
