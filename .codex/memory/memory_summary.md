# Memory Summary

This repository is a product-free SDD/SDLC delivery shell. The previous sample application and old stack guidance were removed. `.codex/project-profile.json` is the tracked common provider/workflow declaration; ignored `.codex/project-profile.local.json` is the local stack overlay and currently has no product stack selected.

Memory is guidance only. It must never override the latest user request, active ticket, active OpenSpec change, the merged project profile, the shared delivery contract, canonical docs, current files, durable evidence, or live tool output.

## High-Signal Operating Context

- Repository root: `C:\Endava\EndevLocal\Personal\SDD_template`.
- Product source: not present.
- Product tests: not present.
- Delivery helpers: `tools/sdd_cli`.
- Durable docs: `docs/context-management.md`, `docs/architecture.md`, `docs/development.md`, and `docs/deployment.md`.
- Agent skills: `.codex/skills/`.
- Shared delivery contract: `.codex/skills/_shared/delivery-contract.md`.
- Project profile: `.codex/project-profile.json` plus optional `.codex/project-profile.local.json`.
- Provider adapters: `.codex/providers/`.
- OpenSpec config: `openspec/config.yaml`.

## Core Workflow

```text
Configured Todo ticket
  -> OpenSpec planning
  -> implementation once a product stack exists
  -> configured review
  -> artifact/deployment/QA gates once app targets exist
  -> explicit production promotion
```

## Memory Use

- Read memory at the start of planning, implementation, review, QA, deployment, rollback, hotfix, and retrospective work.
- Use `MEMORY.md` as the index into deeper memory files.
- Write memory only for reusable, source-backed knowledge.
- Keep secrets, tokens, local credentials, and ignored local runtime state out of memory.
