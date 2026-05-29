---
name: delivery-retrospective-audit
description: Inspect completed, failed, or blocked Plane/Gitea/OpenSpec delivery runs and convert repeated audit evidence into durable workflow improvements. Use when Codex is asked to audit the delivery flow, perform a retrospective, identify self-improvements, reduce recurring review/QA/CI failures, improve skills from past delivery evidence, or propose/apply updates to delivery skills, configure skills, templates, tests, quality gates, or shared workflow policy.
---

# Delivery Retrospective Audit

## Overview

Use this skill after or between delivery runs to find repeated process misses and turn them into controlled improvements. This skill does not deliver tickets, deploy releases, or promote environments; it audits evidence and improves the workflow only when the evidence supports it.

## Shared Context

Follow `.codex/skills/_shared/skill-startup.md` with `docs/architecture.md`, `docs/development.md`, and `docs/deployment.md` as stage-specific docs. Treat the delivery contract as the policy baseline and apply its Skill Synchronization Rule before changing any delivery or configure skill.

## Operating Modes

Default to read-only mode unless the user explicitly asks to apply changes.

- `Read-only audit`: inspect evidence and report proposed improvements.
- `Proposal mode`: draft exact skill/config/test changes without editing files.
- `Apply mode`: edit skills, scripts, templates, or tests after evidence is clear and the user requested implementation.

Never silently rewrite workflow rules from one isolated failure. Apply the Agent Self-Improvement Gate in `.codex/skills/_shared/delivery-contract.md` before changing skills, workflow policy, configure templates, or quality gates from retrospective evidence.

This skill is safe to run as a manual quality lane through prompts such as:

- `Audit recent delivery workflow`
- `Audit failed QA/review/CI run`
- `Run agent self-improvement audit`

Do not create recurring automations, scheduled jobs, Plane tickets, deployment actions, tags, or ticket-state mutations from this skill unless the user explicitly requests that separate action.

## Triggers

Run this audit after or between delivery work when one of these conditions occurs:

- a QA bug is filed or E2E QA fails,
- `gitea-pr-review-agent` misses a meaningful issue,
- Gitea Actions, local quality gates, or runner tooling fail in a way that blocks handoff,
- deployment, release manifest, rollback, or hotfix flow is blocked,
- a delivery skill and configure skill appear to disagree,
- the operator asks for a periodic manual review after several completed tickets, such as every 3 to 5 tickets.

If operators want scheduled audits, create a follow-up ticket that defines cadence, ownership, output destination, and allowed mutations.

## Evidence Sources

Inspect the smallest useful set first, then expand as needed:

- `.codex/skills/_shared/delivery-contract.md`
- `.codex/memory/MEMORY.md` and relevant `.codex/memory/*.md` files
- `docs/context-management.md`
- `docs/architecture.md`
- `docs/development.md`
- `docs/deployment.md`
- `.codex/skills/automatic-implement-ticket/SKILL.md`
- `.codex/skills/implement-ticket/SKILL.md`
- `.codex/skills/gitea-pr-review-agent/SKILL.md`
- `.codex/skills/openspec-verify-change/SKILL.md`
- `.codex/skills/configure-dev-environment/SKILL.md`
- `.codex/skills/configure-*` docs, references, scripts, templates, and tests when setup or generated behavior is implicated
- `.codex/delivery-context.local.json` when present, without printing secrets
- recent Git commits, branches, tags, PR labels, PR review comments, CI results, OpenSpec verification output, Plane comments, QA bug tickets, Nexus release manifests, and deployment evidence when available

## Workflow

### 1. Define The Audit Scope

Resolve what the user wants audited:

- one ticket or PR,
- one failed run,
- the latest delivery attempt,
- a class of failures such as QA bugs, review misses, CI failures, or deployment blockers,
- the skill workflow itself.

If the scope is ambiguous and local evidence clearly identifies a current locked ticket or PR, use that as the scope and say so. If several scopes are plausible, run a read-only summary instead of guessing.

### 2. Reconstruct The Delivery Timeline

Build a concise timeline from durable checkpoints:

- Plane state and generated comments,
- active or historical ticket context lock,
- branch and OpenSpec change,
- PR number, head SHA, labels, review-agent markers, and comments,
- CI or local quality gate result,
- Nexus artifact and release manifest state,
- DEV/QA/PROD deployment evidence,
- QA bug or rollback/hotfix evidence.

Use existing stable markers from the delivery contract for idempotency.

### 3. Classify Findings

Group findings by the workflow layer that should improve:

- `implementation`: code, tests, OpenSpec tasks, or local validation missed something.
- `review`: `gitea-pr-review-agent` criteria, scope, labels, or marker behavior missed something.
- `quality-gate`: CI, coverage, secret scanning, dependency audit, or workflow checks missed something.
- `configuration`: generated templates, local config guidance, runner setup, or setup audit drifted from delivery requirements.
- `deployment`: artifact, release manifest, health contract, promotion, tag, or rollback rules missed something.
- `skill-drift`: delivery skills and configure skills disagree with `_shared/delivery-contract.md`.
- `observability`: evidence, logs, comments, or status reporting were insufficient to diagnose a run.
- `agency-risk`: an agent had too much write authority, used the wrong tool boundary, attempted unsafe mutation, or acted without sufficient confirmation.

For each finding, include the evidence, why it matters, and the durable improvement that would prevent recurrence.

Use `templates/audit-checklist.md` as the default report skeleton when producing a read-only audit or proposal.

### 4. Decide Whether To Improve

Apply one of these outcomes:

- `No change`: the issue was one-off, already covered, or not actionable.
- `Skill instruction update`: a skill needs clearer routing, classification, validation, or handoff rules.
- `Shared contract update`: multiple skills need a new common rule.
- `Configure sync update`: setup docs, templates, audit scripts, or tests must match delivery behavior.
- `Regression test`: a script/template/check should enforce the rule.
- `Quality gate update`: CI or local validation should catch the issue.
- `Docs update`: durable findings should be promoted to `docs/architecture.md`, `docs/development.md`, `docs/deployment.md`, or `docs/context-management.md`.
- `Memory update`: reusable but non-authoritative findings should be added to `.codex/memory/` through the memory update process.
- `Follow-up ticket`: the change is product work, infra work, or too large for the current retrospective.

Prefer tests or deterministic validation for enforceable rules. Prefer skill text only for judgment-heavy process rules.

Before choosing any outcome other than `No change`, confirm the Agent Self-Improvement Gate in `.codex/skills/_shared/delivery-contract.md` is satisfied.

Use the Context Findings classification from `docs/context-management.md` and `.codex/memory/retrieval-policy.md` to decide whether a durable finding belongs in `docs/`, `.codex/skills/_shared/delivery-contract.md` plus related skills and tests, or `.codex/memory/`.

### 5. Apply Changes Safely

When applying changes:

1. Keep edits scoped to the improvement.
2. Update `_shared/delivery-contract.md` first when the rule is cross-cutting.
3. Update the matching durable docs when the finding is reusable project knowledge.
4. Update `.codex/memory/` when the finding is reusable but non-authoritative.
5. Update affected delivery-flow skills.
6. Update configure skills, generated templates, audits, and tests when the Skill Synchronization Rule requires it.
7. Add or update regression tests when the behavior can be enforced from files.
8. Run the narrowest relevant validation command, such as skill validation, script tests, or existing repo tests.

Do not change OpenSpec-specific skills unless the requested improvement explicitly affects OpenSpec behavior.

## Output

For read-only audits, report:

- audit scope,
- evidence inspected,
- timeline summary,
- findings grouped by layer,
- recommended durable improvements,
- risks or evidence gaps.

For applied improvements, report:

- files changed,
- improvement rationale,
- synchronization work performed,
- validation commands and results,
- remaining gaps or follow-up tickets.

Keep recommendations concrete. Avoid vague statements like "improve tests" unless paired with the exact missing test or gate.

## Failure Rules

- If secrets or credential-bearing URLs are encountered, redact them and continue only with non-secret evidence.
- If delivery state is ambiguous, produce a read-only status/audit summary and do not mutate files.
- If evidence conflicts with the delivery contract, treat the contract as authoritative unless the user explicitly asks to revise the contract.
- If a proposed improvement would change deployment, QA, PROD, rollback, artifact, or ticket-state behavior, update configure docs/templates/audits/tests in the same change or report why synchronization is blocked.
- If validation cannot be run, state the reason and residual risk.
