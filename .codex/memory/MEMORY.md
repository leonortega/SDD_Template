# Repository Memory Index

This file indexes durable, source-backed memory for the SDD/SDLC agentic delivery repository.

Memory is not an authority source. Use it to find relevant context quickly, then verify against current repo files and live tools.

## Authority Reminder

When sources disagree, follow the authority order in `docs/context-management.md`. Do not duplicate that list here; this memory index is intentionally subordinate to current user intent, Plane, OpenSpec, the shared delivery contract, canonical docs, current files, durable evidence, and only then memory.

## Memory Files

- `memory_summary.md`: compact high-signal startup context for agents.
- `retrieval-policy.md`: rules for reading, writing, reviewing, and pruning memory.
- `project-map.md`: current repository shape and source-of-truth map.
- `workflow-memory.md`: delivery workflow, state transitions, gates, and stable markers.
- `decisions.md`: durable decisions known from current repository docs and this thread.
- `failure-patterns.md`: recurring failure classes and required responses.
- `qa-findings.md`: QA and deployment validation memory.
- `release-lessons.md`: artifact, versioning, promotion, rollback, and hotfix memory.
- `module-map.md`: code and workflow module landmarks.

## Memory Update Process

When a run discovers reusable knowledge, first classify whether it belongs in canonical docs, the shared delivery contract, or memory:

- Authoritative project or workflow context -> `docs/`.
- Enforceable automation behavior -> `.codex/skills/_shared/delivery-contract.md` plus affected skills and tests.
- Reusable but non-authoritative knowledge -> `.codex/memory/`.

Then follow `retrieval-policy.md#update-process`. Memory updates must include a source, status, and last verified date. Update `MEMORY.md` only when adding a discoverable new topic, and update `memory_summary.md` only for high-signal startup context.

## Current Confirmed Memories

### SDD/SDLC Delivery Model

- This repository is a local agent-driven software delivery lab.
- Plane is the source of ticket state, generated workflow markers, and delivery comments.
- OpenSpec records planned behavior before implementation.
- Gitea handles PR review and validation.
- Nexus stores immutable build artifacts.
- Azure hosts DEV, QA, and PROD application runtimes.
- PROD promotion is explicit and artifact-based.

Sources: `README.md`, `docs/architecture.md`, `.codex/skills/_shared/delivery-contract.md`.

### Context Management

- Context is treated as an SDLC asset.
- Durable project knowledge belongs in tracked docs and workflow contracts, not only chat, temporary notes, PR comments, or Plane comments.
- Every implementation must run a Context Findings Review.
- Durable findings update the matching `docs/` file in the same PR.
- If no durable context changed, the PR body and Plane handoff comment must state `Docs: no durable context changes`.

Sources: `README.md`, `docs/context-management.md`, `docs/development.md`.

### Agent Entry Points

- `automatic-implement-ticket` is the high-level workflow router for continuing, resuming, implementing, deploying, QA, or handoff work.
- `configure-dev-environment` is the setup router for Plane, Gitea, runner, quality gates, Nexus, Azure, and observability.
- `pipeline-status` is the read-only status dashboard.
- `parallel-ticket-coordinator` coordinates multiple Plane tickets with one worktree and one local context lock per active ticket.

Sources: `README.md`, `.codex/skills/`.

### Local Configuration And Secrets

- Local credentials and generated secrets belong only in ignored local files.
- Tracked example files must remain placeholder-safe.
- The workflow must not read secrets from Docker containers, mounted volumes, databases, logs, or committed files.

Sources: `README.md`, `.codex/skills/_shared/delivery-contract.md`.

### Memory System Addition

- `AGENTS.md` was added as a root-level entry point for future coding agents.
- `.codex/memory/` was added to provide a file-backed Memory & Knowledge Systems layer.
- The memory layer is intentionally subordinate to the existing context-management authority order.

Sources: current conversation, `AGENTS.md`, `.codex/memory/`.
