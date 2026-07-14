---
name: dev-ops-hotfix-prod
description: Run an expedited but gated production hotfix workflow for urgent targeted code fixes, including incident/hotfix ticket creation, branch and PR handling, review, immutable artifact deployment, QA evidence, and explicit production promotion through selected project-profile adapters. Use when rollback is insufficient and a production regression needs a small code fix.
---

<!-- TIER 3: STAGE-SPECIFIC - PROD hotfix skill -->

# Hotfix PROD

## Overview

Use this skill when PROD needs a targeted code fix rather than a rollback. It is expedited in scope, not in quality gates: review, tests, immutable artifacts, QA evidence, and explicit PROD promotion still apply.

Prefer `dev-ops-rollback-prod` when restoring a known-good artifact is enough.

## Shared Context

Before starting, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/development.md` and `docs/deployment.md` as stage-specific docs. Load selected ticket, repository/review, artifact, deployment, observability, stack, and E2E adapters for the current step.

## Configuration

Read `.codex/project-profile.json` first. Read `.codex/client-tools.local.json` only for selected adapter runtime values used by the normal delivery skills.

## Workflow

1. Confirm the incident or regression, affected PROD version, user impact, and why rollback is not sufficient.
2. Read `.codex/delivery-context.local.json` when present. If it points to an unrelated active feature ticket, stop and ask the user to confirm replacing the lock with the incident/hotfix ticket before mutation.
3. Create or reuse a ticket provider incident/hotfix ticket with marker `IA generated PROD hotfix: {incidentOrTicketKey}`.
4. Branch from `main` unless the user explicitly supplies a release branch policy.
5. Use `dev-flow-start-ticket` for branch/comment setup, ticket lock creation, and OpenSpec creation unless the ticket is explicitly `no-openspec` or ops-only.
6. Use `dev-flow-implement-ticket` for the code fix, tests, PR, review-agent loop, and handoff.
7. After merge, use `dev-ops-post-merge-deploy` and the configured QA gate for artifact promotion and QA evidence.
8. Invoke `dev-ops-deploy-prod` only when the user explicitly asks for PROD promotion after QA passes.
9. Comment the incident ticket with release lineage, evidence, and any temporary divergence from normal cadence.

## Scope Rules

- Keep hotfixes narrowly scoped to the production defect.
- Do not bundle unrelated cleanup or feature work.
- If the fix grows beyond a targeted change, stop and route to the normal `dev-flow-continue-implementation` flow.

## Output

Report the incident or hotfix ticket, branch, PR, validation performed, artifact/QA/PROD status when reached, and the next handoff or blocker.

## Failure Rules

- Missing incident context: stop and ask for the production symptom and impact.
- Rollback is clearly safer and sufficient: recommend `dev-ops-rollback-prod` first.
- Tests, review, artifact, QA, or PROD checks fail: stop at the same gate as the normal delivery flow.
- Branch protection or release workflow drift: route through the same repair path as `dev-ops-deploy-prod`.
