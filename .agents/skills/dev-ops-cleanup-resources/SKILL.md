---
name: dev-ops-cleanup-resources
license: MIT
description: >-
  >- Remove temporary resources left behind after a ticket is closed: leftover Docker containers, images, and volumes
  created to test something, plus scratch/temp files from implementation and testing. Use after a ticket reaches the
  configured Done state (Closed) or when asked to clean up temporary test resources.
---

<!-- TIER 3: STAGE-SPECIFIC - Post-close temporary resource cleanup skill -->

# Clean Up Temporary Resources

## Overview

Use this skill after a ticket has been closed (`Closed`, OpenProject ID 12) — automatically as the closing step of the
E2E QA gate, or on explicit request. It removes temporary resources that were created only to test or verify something
during the ticket's lifecycle:

- **Docker leftovers** — stopped containers, dangling images, and volumes spun up to test a service, a database, a
  container image, or a one-off experiment. The healthy lab is never touched: compose-labeled services (Gitea,
  OpenProject, Nexus, monitoring, ...) and their volumes/images are protected.
- **Temp files** — scratch scripts (`.template/_tmp_*`), temp outputs (`*.tmp`, `tmp_*`, `*_scratch*`), and local
  test-run artifacts (`test-results/`, `playwright-report/`, `e2e-qa-output.json`) created during implementation and QA.

It never deletes tracked files, local configuration (`.template/*.local.json`, `infra/*/variables.env`, ...), the
delivery-context lock, or evidence already published to Nexus/OpenProject.

## Shared Context

Before running, follow `.agents/skills/_shared/skill-startup.md`, which reads `.template/project-profile.json`,
`.agents/skills/_shared/delivery-contract.md`, and `docs/conventions/context-management.md`. Confirm the resolved
ticket key and that the ticket is in the configured `Done` state (`Closed` by default — OpenProject ID 12). If the
ticket is not closed yet, do not run the cleanup unless the user explicitly asks.

## Workflow Telemetry

Apply the shared workflow telemetry pattern (`.agents/skills/_shared/pipeline-workflow-telemetry.md`) with:

- `{workflowStage}` = `dev-ops-cleanup-resources`
- `{agentRole}` = `cleanup`

Capture UTC start time after resolving the ticket key and before the first cleanup action. Create or update the
`dev-ops-cleanup-resources` entry via `time-telemetry-upsert` (payload in
`.agents/skills/openproject-sprint-backlog/references/openproject-api.md` → Operations → `time-telemetry-upsert`; shared
helpers in `.agents/skills/_shared/api-helpers.md` → OpenProject → Workflow time
telemetry). Use marker `IA generated workflow telemetry: {ticketKey}:dev-ops-cleanup-resources`. Resolve the activity via
`python -m tools.sdd_cli dev-flow resolve-openproject-activity --workflow-stage
dev-ops-cleanup-resources --input-json '{"timeTelemetry":{...}}'` and reverse-lookup the activity ID. Use `python -m
tools.sdd_cli dev-flow append-telemetry -TicketKey {ticketKey}` only as the JSONL fallback
when direct time telemetry is unavailable. Include `workflowStage`, `agentRole`, `startedUtc`, `finishedUtc`,
`retryCount`, and `outcome`.

## Workflow

1. Resolve the ticket key and confirm the ticket is in the configured `Done` state (`Closed` — ID 12 by default).
2. **Prune leftover Docker resources** — run the lab's scoped prune (non-fatal, idempotent, dry-run capable):

   ```bash
   python -m tools.sdd_cli environment-lab prune-docker-leftovers
   # Preview only: python -m tools.sdd_cli environment-lab prune-docker-leftovers --dry-run true
   ```

   Scope (the healthy lab is never touched):

   - containers: only STOPPED containers without a compose project label
   - images: only DANGLING (untagged `<none>`) images
   - volumes: only volumes without a compose project label

   A failed prune is reported as a non-blocking warning.

3. **Remove temporary files** created during the ticket. Inspect first, then delete (report each item):

   - scratch scripts under the config home: `.template/_tmp_*`
   - repo-root temp outputs (untracked only): `*.tmp`, `tmp_*`, `*_scratch*`
   - local test-run artifacts (gitignored outputs): `test-results/`, `playwright-report/`, `e2e-qa-output.json`
   - any other untracked scratch file the ticket's implementation or QA explicitly created (judgment call — report
     before deleting)

   Never delete tracked files, `.template/*.local.json`, `infra/*/variables.env` / `*.env`, the delivery-context lock
   (`.template/delivery-context.local.json`), or any evidence already published to Nexus/OpenProject.

4. **Report** what was pruned and removed, confirm lab services are untouched, and record the cleanup outcome.

## Output

Report the ticket key, what Docker resources were pruned (or `nothing to remove`), which temp files were deleted (or
`none`), confirmation that lab services (compose-labeled) and local config were untouched, and any non-blocking
warnings.

## Failure Rules

- Do not run cleanup while the ticket is not in `Closed` (unless the user explicitly asks).
- Do not prune compose-labeled lab resources, tagged lab images (`sdd-*:local`), or compose-owned volumes.
- Do not delete tracked files, local configuration, the delivery-context lock, or published evidence.
- A failed Docker prune is a warning, never a blocker.
- Idempotent: re-running reports `nothing to remove` when the ticket left no leftovers.
