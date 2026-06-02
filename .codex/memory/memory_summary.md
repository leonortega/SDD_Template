# Memory Summary

This repository is an agentic SDD/SDLC delivery lab for moving Plane tickets through OpenSpec planning, implementation, Gitea review, Nexus artifact promotion, Azure DEV/QA/PROD deployment, E2E QA, explicit PROD promotion, rollback, and hotfix workflows.

Memory is guidance only. It must never override the latest user request, active Plane ticket, active OpenSpec change, `.codex/skills/_shared/delivery-contract.md`, canonical docs, current code, tests, workflow files, or live tool output.

## High-Signal Operating Context

- Repository root: `C:\Endava\EndevLocal\Personal\SDD_template`.
- Solution: `SDDTemplate.slnx`.
- App: `src/SDDTemplate.Site`.
- Tests: `tests/SDDTemplate.Site.Tests`.
- Delivery helpers: `tools/SDDTemplate.DeliveryTools`.
- Durable docs: `docs/context-management.md`, `docs/architecture.md`, `docs/development.md`, and `docs/deployment.md`.
- Agent skills: `.codex/skills/`.
- Shared delivery contract: `.codex/skills/_shared/delivery-contract.md`.
- OpenSpec changes: `openspec/changes`.
- Ticket key pattern: `E2EPROJECT-[0-9]+`.
- Coverage threshold: `80%`.

## Core Workflow

```text
Plane Todo
  -> branch + OpenSpec proposal
  -> implementation + tests
  -> Gitea PR
  -> PR validation + Codex review agent
  -> merge to dev
  -> Nexus package + Azure DEV + Azure QA
  -> E2E QA evidence
  -> Plane Done
  -> explicit PROD promotion to main/PROD
  -> rollback or hotfix when needed
```

## Common Commands

```powershell
dotnet build .\SDDTemplate.slnx
dotnet test .\SDDTemplate.slnx
dotnet format --verify-no-changes
.\infra\up.ps1
.\infra\down.ps1
```

## Memory Use

- Read memory at the start of planning, implementation, review, QA, deployment, rollback, hotfix, and retrospective work.
- Use `MEMORY.md` as the index into deeper memory files.
- Use `.codex/memory/search_memory.ps1 -Query <symptom>` when debugging concrete errors, blockers, failed commands, deployment issues, PR feedback, QA failures, configuration mismatches, or local tooling problems.
- Write memory only for reusable, source-backed knowledge.
- Follow `retrieval-policy.md#update-process` when updating memory.
- Prefer updating canonical docs when the finding is authoritative workflow or architecture context.
- Keep secrets, tokens, local credentials, and ignored local runtime state out of memory.
- Before final handoff for any non-trivial repository work, report `Memory updated: <files>` or `Memory updated: none` after classifying reusable errors, blockers, fixes, configuration repairs, tooling corrections, and debugging results.
- Recent cross-thread lessons include worktree local-config sync, Gitea reviewer collaborator requirements, Plane comment payload fields, Gitea Actions shell/runtime assumptions, PR feedback batching, and live Azure app-to-app settings for topology deployments.
