---
name: pipeline-status
description: Produce a read-only operator dashboard for Plane tickets, Gitea PRs, Nexus artifacts, QA evidence, tags, DEV/QA/PROD release state, and blockers. Use when the user asks where a ticket or release stands, what is deployed, what is blocked, or which workflow step should run next.
---

# Pipeline Status

## Overview

Use this skill for read-only delivery visibility. It must not mutate Plane, Git, Gitea, Nexus, Azure, or local repo files.

Read `.codex/skills/_shared/delivery-contract.md` before reporting so state names, markers, artifact paths, and version terms match the rest of the delivery workflow.

## Configuration

Read `.codex/client-tools.local.json` first. Use available Plane, Gitea, Nexus, and monitoring settings. If a system is unconfigured or unreachable, record it as unavailable instead of failing the whole status.

Never print real tokens, credentials, cookies, or private payloads.

## Status Sources

Collect what is relevant to the request:

- Plane tickets by configured states: Todo, In Progress, In Review, QA, Done.
- Current ticket generated markers: branch, PR, QA deployment, E2E QA, PROD deployment, rollback, QA bug.
- Gitea open PRs, merged PRs, target branches, labels, latest review markers, and CI status when available.
- Nexus artifacts and `release.json` for relevant commits.
- Git branches and SemVer tags.
- DEV/QA/PROD URLs and `/health` status when available.
- Prometheus/Grafana availability when relevant to PROD status.

## Output

Report concise sections:

- Current state and next recommended skill.
- Open blockers.
- Ticket/PR/artifact mapping.
- Deployed versions for DEV, QA, and PROD when known.
- Missing configuration or unavailable external systems.

If the next step is ambiguous, list the candidate routes and recommend the safest one.

## Failure Rules

- Do not mutate state.
- If credentials are missing, report which integration cannot be inspected.
- If Nexus or Gitea is unavailable, continue with Plane/Git information when possible.
- If multiple tickets or PRs match, report all candidates and do not choose one unless the user provided a unique key.
