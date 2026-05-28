---
name: hotfix-prod
description: Run an expedited but gated production hotfix workflow for urgent targeted code fixes, including Plane incident/hotfix ticket creation, branch and PR handling, review, immutable artifact deployment, QA evidence, and explicit PROD promotion. Use when rollback is insufficient and a production regression needs a small code fix.
---

# Hotfix PROD

## Overview

Use this skill when PROD needs a targeted code fix rather than a rollback. It is expedited in scope, not in quality gates: review, tests, immutable artifacts, QA evidence, and explicit PROD promotion still apply.

Prefer `rollback-prod` when restoring a known-good artifact is enough.

Before starting, read `.codex/skills/_shared/delivery-contract.md` and preserve its artifact, QA, PROD, and rollback invariants.

## Configuration

Read `.codex/client-tools.local.json` first. Required values are Plane, Git, Gitea, Nexus, and deployment settings used by the normal delivery skills.

Never print or write real tokens, passwords, cookies, Azure credentials, or Nexus credentials.

## Workflow

1. Confirm the incident or regression, affected PROD version, user impact, and why rollback is not sufficient.
2. Create or reuse a Plane incident/hotfix ticket with marker `IA generated PROD hotfix: {incidentOrTicketKey}`.
3. Branch from `main` unless the user explicitly supplies a release branch policy.
4. Use `plane-start-ticket` for branch/comment setup and OpenSpec creation unless the ticket is explicitly `no-openspec` or ops-only.
5. Use `implement-ticket` for the code fix, tests, PR, review-agent loop, and handoff.
6. After merge, use `post-merge-deploy` and `test-e2e` for artifact promotion and QA evidence.
7. Invoke `deploy-to-prod` only when the user explicitly asks for PROD promotion after QA passes.
8. Comment the incident ticket with release lineage, evidence, and any temporary divergence from normal cadence.

## Scope Rules

- Keep hotfixes narrowly scoped to the production defect.
- Do not bundle unrelated cleanup or feature work.
- If the fix grows beyond a targeted change, stop and route to the normal `automatic-implement-ticket` flow.

## Failure Rules

- Missing incident context: stop and ask for the production symptom and impact.
- Rollback is clearly safer and sufficient: recommend `rollback-prod` first.
- Tests, review, artifact, QA, or PROD checks fail: stop at the same gate as the normal delivery flow.
- Branch protection or release workflow drift: route through the same repair path as `deploy-to-prod`.
