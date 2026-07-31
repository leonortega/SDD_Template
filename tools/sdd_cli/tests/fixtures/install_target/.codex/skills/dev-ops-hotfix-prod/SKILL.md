---
name: dev-ops-hotfix-prod
license: MIT
description: Run an expedited but gated production hotfix workflow for urgent targeted code fixes, including incident/hotfix ticket creation, branch and PR handling, review, immutable artifact deployment, QA evidence, and explicit production promotion through selected project-profile adapters. Use when rollback is insufficient and a production regression needs a small code fix.
---

<!-- TIER 3: STAGE-SPECIFIC - PROD hotfix skill -->

# Hotfix PROD

## Overview

Use this skill when PROD needs a targeted code fix rather than a rollback. It is expedited in scope, not in quality gates: review, tests, immutable artifacts, QA evidence, and explicit PROD promotion still apply.

Prefer `dev-ops-rollback-prod` when restoring a known-good artifact is enough.

## Shared Context

Before starting, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/development.md` and `docs/deployment.md` as stage-specific docs. Load selected ticket, repository/review, artifact, deployment, observability, stack, and E2E adapters for the current step.

## Configuration

Read `.codex/project-profile.json` first. Read `.codex/client-tools.local.json` only for selected adapter runtime values used by the normal delivery skills.

## Workflow

1. Confirm the incident or regression, affected PROD version, user impact, and why rollback is not sufficient.
2. Read `.codex/delivery-context.local.json` when present. If it points to an unrelated active feature ticket, stop and ask the user to confirm replacing the lock with the incident/hotfix ticket before mutation.
3. Create or reuse a ticket provider incident/hotfix ticket with marker `IA generated PROD hotfix: {incidentOrTicketKey}`.
4. Branch from `main` unless the user explicitly supplies a release branch policy.
5. Use `dev-flow-start-ticket` for branch/comment setup, ticket lock creation, and OpenSpec creation unless the ticket is explicitly `no-openspec` or ops-only.

6. **⚠️ MANDATORY: Implement Fix With Tests** — delegate to `dev-flow-implement-ticket` for the code fix, tests, PR, review-agent loop, and handoff. The TDD test-first pattern is defined in `.codex/skills/_shared/pipeline-tdd-cycle.md`. Key hotfix-specific details:

   - **AC source:** the incident/hotfix ticket description (set in step 3).
   - **Task source:** the OpenSpec `tasks.md` for any tasks created in step 5.
   - **Tests are non-negotiable even for hotfixes.** The mandatory test requirement (unit + integration + architecture, RED before fix code) applies equally to hotfixes. An expedited schedule is not an excuse to skip tests.
   - **Quality gates are the same as the feature flow** and are enforced by `dev-flow-implement-ticket` during implementation:
     - **Lefthook pre-push stack tests + coverage (`python -m tools.sdd_cli stack-tests`)** must pass before pushing — unit, integration, and architecture tests per `.codex/skills/_shared/test-requirements.md` (driven by `stack.testFrameworks`) plus the **coverage gate** with the configurable threshold `coverage.minimumPercent` (default `80`). No stack: clean skip. Do not bypass the hook with `--no-verify` unless the user explicitly requests it.
     - **Coverage gate:** coverage must meet `coverage.minimumPercent` (default `80`) before PR creation. Below threshold: HARD STOP (authority level 5) — add/update tests and re-run until met.
     - **Full local CI loop:** run the checks in `.gitea/workflows/pr-validation.yml` (via `sdd-e2e-ci:local` when Docker is available) and fix all errors before creating the PR.
   - **Expect the PR body** (created by `dev-flow-implement-ticket`) to include the acceptance-to-test map and TDD RED/GREEN evidence.
7. After merge, use `dev-ops-post-merge-deploy` and the configured QA gate for artifact promotion and QA evidence.
8. Invoke `dev-ops-deploy-prod` only when the user explicitly asks for PROD promotion after QA passes.
9. Comment the incident ticket with release lineage, evidence, and any temporary divergence from normal cadence.

## Scope Rules

- Keep hotfixes narrowly scoped to the production defect.
- Do not bundle unrelated cleanup or feature work.
- **Tests are non-negotiable even for hotfixes.** The mandatory test requirement (unit + integration + architecture, RED before fix code) applies equally to hotfixes. An expedited schedule is not an excuse to skip tests.
- If the fix grows beyond a targeted change, stop and route to the normal `dev-flow-continue-implementation` flow.

## Output

Report the incident or hotfix ticket, branch, PR, **acceptance-to-test map** (ACs → unit/integration/architecture tests with RED/GREEN evidence), validation performed, artifact/QA/PROD status when reached, and the next handoff or blocker.

## Failure Rules

- Missing incident context: stop and ask for the production symptom and impact.
- Rollback is clearly safer and sufficient: recommend `dev-ops-rollback-prod` first.
- Tests, review, artifact, QA, or PROD checks fail: stop at the same gate as the normal delivery flow.
- Lefthook pre-push stack tests fail or an unmapped framework is configured: stop before pushing — fix the tests or framework mapping and re-run `python -m tools.sdd_cli stack-tests` until it passes. Do not bypass the hook with `--no-verify` unless the user explicitly requests it. When no stack is configured the hook skips cleanly (expected template state).
- Coverage below `coverage.minimumPercent` (default `80`): HARD STOP (authority level 5) before PR creation — add or update tests and re-run coverage until the threshold is met.
- Branch protection or release workflow drift: route through the same repair path as `dev-ops-deploy-prod`.
