# Decision Memory

## Use File-Backed Memory, Not Opaque Agent Memory

- Type: Decision
- Status: Active
- Source: current conversation, `.codex/memory/`
- Last verified: 2026-05-29

This repository should use a tracked, reviewable, file-backed memory system under `.codex/memory/`. Memory entries should be source-backed and should support the existing SDD/SDLC workflow rather than replacing OpenProject, OpenSpec, docs, delivery contracts, or live tool state.

## Memory Is Subordinate To Existing Context Authority

- Type: Decision
- Status: Active
- Source: current conversation, `docs/context-management.md`
- Last verified: 2026-05-29

Memory is a retrieval aid. It does not alter the authority order in `docs/context-management.md`. Current user request, active ticket, active OpenSpec change, delivery contract, canonical docs, current files, and live tools remain authoritative.

## Root Agent Entry Point

- Type: Decision
- Status: Active
- Source: current conversation, `AGENTS.md`
- Last verified: 2026-05-29

The repository now has a root `AGENTS.md` to give coding agents an immediate entry point. It points agents toward `.codex/skills/`, OpenSpec, quality configuration, delivery policy, source-control expectations, and secret-handling rules.

## Production Promotion Is Explicit

- Type: Decision
- Status: Active
- Source: `README.md`, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Passing QA does not automatically promote to PROD. PROD promotion requires explicit user request or the defined PROD-only workflow trigger.

## Build Once, Promote The Same Artifact

- Type: Decision
- Status: Active
- Source: `README.md`, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Nexus stores the immutable artifact promoted across DEV, QA, PROD, and rollback. Do not rebuild between environments and do not deploy from local files.

## Context As SDLC Asset

- Type: Decision
- Status: Active
- Source: `docs/context-management.md`
- Last verified: 2026-05-29

Durable project knowledge belongs in tracked documentation and workflow contracts, not only in chat history, temporary notes, PR comments, or OpenProject comments. Memory extends this approach but does not replace canonical docs.

## Shared Startup For Delivery Skills

- Type: Decision
- Status: Active
- Source: `.codex/skills/_shared/skill-startup.md`, current conversation
- Last verified: 2026-05-29

Non-OpenSpec, non-configure delivery skills should use `.codex/skills/_shared/skill-startup.md` for common startup behavior: memory summary/index reads, delivery contract reads, context authority, secret handling, and memory update classification. Individual skills should keep only their stage-specific docs, helper functions, mutation gates, and stop rules.

## Explicit Consent Before Alternative Flow

- Type: Decision
- Status: Active
- Source: current conversation, `AGENTS.md`, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-06-18

When a required repo skill, command, memory rule, definition, or configured tool/install path cannot be applied, agents must stop the affected flow instead of silently using an alternative. The agent must report the blocker, current-flow fix, viable alternative, and risk or impact, then ask the user whether to fix the current flow or continue with the alternative.

## OpenProject Replaces Plane

- Type: Decision
- Status: Active
- Source: current conversation, `.codex/project-profile.json`, `.codex/providers/ticket.openproject.md`
- Last verified: 2026-06-24

OpenProject is the configured ticket provider. Future delivery uses OpenProject work packages, API v3 bearer-token authentication, and the `openProject` local config section. Existing archived OpenSpec text remains historical and is not migrated.

## Repo-Local Skill Installation Preference

- Type: Preference
- Status: Active
- Source: user instruction in chat, 2026-06-25
- Last verified: 2026-06-25

When adding external skills for this repository, install them as repo-local skills under `.codex/skills/` and catalog them in `.codex/skills/README.md`. Do not install them globally under `$CODEX_HOME/skills`; if a skill installer defaults to global installation, pass an explicit repo-local destination.
