---
name: dev-flow-pipeline-status
description: Produce a read-only operator dashboard for configured tickets, pull requests, selected-provider artifacts, QA evidence, tags, environments, release state, and blockers through selected project-profile adapters. Use when the user asks where a ticket or release stands, what is deployed, what is blocked, or which workflow step should run next.
---

<!-- TIER 3: STAGE-SPECIFIC - Pipeline visibility skill -->

# Pipeline Status

## Overview

Use this skill for read-only delivery visibility. It must not mutate ticket, repository, review, artifact, deployment, observability, or local repo state.

## Shared Context

Before reporting, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/architecture.md` as the stage-specific doc. Load only adapters needed for read-only status. This remains a read-only skill; do not update memory unless the user explicitly asks for a workflow-memory correction.

## Configuration

Read `.codex/project-profile.json` first. Use available selected adapter runtime settings from `.codex/client-tools.local.json`. If a system is unconfigured or unreachable, record it as unavailable instead of failing the whole status.

## Workflow

Collect read-only status sources, compare them against the ticket context lock, report validation gaps, and recommend the next handoff route without mutating ticket provider, Git, repository/review provider, Nexus, selected deployment provider, tags, or release manifests.

## Status Sources

Collect what is relevant to the request:

- tickets by configured states: Todo, In Progress, In Review, QA, Done.
- Current ticket generated markers: branch, PR, QA deployment, E2E QA, PROD deployment, rollback, QA bug.
- Active `.codex/delivery-context.local.json` lock, including ticket key, branch, PR, artifact commit, RC/final versions, and any mismatch with discovered state.
- repository/review provider open PRs, merged PRs, target branches, labels, latest review markers, and CI status when available.
- Nexus artifacts and `release.json` for relevant commits.
- Git branches and SemVer tags.
- DEV/QA/PROD URLs and `/health` status when available.
- Seq log search availability when relevant to PROD status.

## Output

Report concise sections:

- Current state and next recommended skill.
- Open blockers.
- Ticket/PR/artifact mapping.
- Active ticket lock and cross-ticket mismatches.
- Deployed versions for DEV, QA, and PROD when known.
- Missing configuration or unavailable external systems.

If the next step is ambiguous, list the candidate routes and recommend the safest one.

## Failure Rules

- Do not mutate state.
- If credentials are missing, report which integration cannot be inspected.
- If Nexus or repository/review provider is unavailable, continue with ticket provider/Git information when possible.
- If multiple tickets or PRs match, report all candidates and do not choose one unless the user provided a unique key.
