---
name: dev-flow-retrospective-audit
description: Inspect delivery runs and Promptfoo eval results, convert repeated misses and eval regressions into durable workflow improvements. Use as the Promptfoo-driven improvement hub: run the eval, read results, classify failures, recommend or apply routing fixes, test updates, and eval-coverage additions.
---

<!-- TIER 3: STAGE-SPECIFIC - Retrospective audit skill — Promptfoo-driven improvement hub -->

# Delivery Retrospective Audit

## Overview

This skill is the **single hub for Promptfoo-driven improvements**. The old eval system (`workflow-cases.json`) is gone — Promptfoo is the only eval mechanism. This skill:

- **Runs** `npx promptfoo eval` as part of its workflow
- **Reads** eval results from `.codex/agent-evals/results.local.json`
- **Classifies** failures into findings (eval-regression, eval-coverage)
- **Recommends** improvements: fix routing logic, update test expectations, add new test cases
- **Applies** changes in apply mode (edits `routing_provider.py`, `promptfooconfig.yaml`, or delivery skills)

It does not deliver tickets, deploy releases, or promote environments. It audits evidence and improves the workflow.

## Shared Context

Follow `.codex/skills/_shared/skill-startup.md` with `docs/architecture.md`, `docs/development.md`, and `docs/deployment.md` as stage-specific docs. Treat the delivery contract as the policy baseline and apply its Skill Synchronization Rule before changing any delivery or configure skill.

## Operating Modes

Default to read-only mode unless the user explicitly asks to apply changes.

- **`Read-only audit`**: inspect evidence and report proposed improvements.
- **`Proposal mode`**: draft exact skill/config/test changes without editing files.
- **`Apply mode`**: edit skills, scripts, templates, or tests after evidence is clear and the user requested implementation.
- **`post-prod-ticket-release`**: read-only audit mode invoked after successful `dev-ops-deploy-prod` for the just-promoted release; persist sanitized learning evidence. Receives eval results from the Post-PROD Eval step as evidence — include the eval summary (total, passed, failed) in the findings. If eval failures exist, `dev-ops-deploy-prod` automatically escalates into the full `eval-driven-improvement` cycle after this mode completes (see Triggers below).
- **`eval-driven-improvement`**: **Run Promptfoo eval directly** as the first step. Read results, classify failures as `eval-regression` or `eval-coverage` findings, and recommend concrete improvements. Supports read-only, proposal, and apply sub-modes. When triggered automatically from `dev-ops-deploy-prod`, the sub-modes run sequentially (probe → diagnose → propose → apply) without manual intervention, limited to eval infrastructure files.

### Eval-Driven Improvement Modes

Within `eval-driven-improvement`. Choose the sub-mode based on what you want to do:

| Sub-mode   | Use When                                                                      | Behavior                                                                                                                                                                                                                                                                     |
| ---------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `probe`    | Quick health check — eval is working? All tests pass?                         | Run eval, show results, no recommendations                                                                                                                                                                                                                                   |
| `diagnose` | Eval results show failures and you need to understand why                     | Run eval, read results, classify failures, report findings                                                                                                                                                                                                                   |
| `propose`  | Findings are clear and you want to draft specific fixes without applying them | Run eval, classify, draft specific changes to config/provider/skills                                                                                                                                                                                                         |
| `apply`    | Findings are clear and fix should be applied                                  | Run eval, classify, **apply** fixes. Requires user confirmation per the Agent Self-Improvement Gate **unless** triggered automatically from `dev-ops-deploy-prod`'s auto-escalation flow, where the gate is satisfied by the high-severity context of a PROD eval regression |

**Decision rule for sub-mode selection:**

1. No eval run exists yet → start with `probe`
2. Failures detected → escalate to `diagnose`
3. Root cause understood → escalate to `propose` (or directly to `apply` if user already confirmed)

Never silently rewrite workflow rules from one isolated failure. Apply the Agent Self-Improvement Gate in `.codex/skills/_shared/delivery-contract.md` before changing skills, workflow policy, configure templates, or quality gates from retrospective evidence.

This skill is safe to run as a manual quality lane through prompts such as:

- `Audit recent delivery workflow`
- `Run Promptfoo eval and diagnose failures`
- `Find eval coverage gaps`
- `Run agent self-improvement audit`

## Triggers

Run this audit after or between delivery work when one of these conditions occurs:

- `dev-ops-deploy-prod` records a successful PROD deployment and invokes `post-prod-ticket-release` for the promoted release, then **auto-escalates** into `eval-driven-improvement` (probe → diagnose → propose → apply) when eval failures are detected,
- a QA bug is filed or E2E QA fails,
- `dev-flow-pr-review-agent` misses a meaningful issue,
- repository workflow, local quality gates, or runner tooling fail in a way that blocks handoff,
- deployment, release manifest, rollback, or hotfix flow is blocked,
- a delivery skill and configure skill appear to disagree,
- the operator asks for a periodic manual review after several completed tickets, such as every 3 to 5 tickets,
- the operator asks to **diagnose Promptfoo eval failures** or **improve eval coverage**.

## Evidence Sources

Inspect the smallest useful set first, then expand as needed:

### Eval-Specific Evidence (always read in `eval-driven-improvement` mode)

- `.codex/agent-evals/promptfooconfig.yaml` — Promptfoo test cases, expected routes, assertions
- `.codex/agent-evals/routing_provider.py` — Python routing logic that runs during eval
- `.codex/agent-evals/results.local.json` — persisted eval results (pass/fail per test, failure details, timestamps)
- `.codex/delivery-policy.json` → `agentOptimization.workflowEvals` — eval configuration (test count, CI path, block flag)
- `.gitea/workflows/agent-eval.yml` — CI eval workflow triggering
- CI eval run output logs and artifacts — when diagnosing a CI-reported eval failure

### General Evidence (read for all audit types)

- `.codex/skills/_shared/delivery-contract.md`
- `.codex/memory/MEMORY.md` and relevant `.codex/memory/*.md` files
- `docs/context-management.md`
- `docs/architecture.md`
- `docs/development.md`
- `docs/deployment.md`
- `.codex/skills/dev-flow-continue-implementation/SKILL.md`
- `.codex/skills/dev-flow-implement-ticket/SKILL.md`
- `.codex/skills/dev-flow-pr-review-agent/SKILL.md`
- `.codex/skills/dev-flow-verify-change/SKILL.md`
- `.codex/skills/configure-dev-environment/SKILL.md`
- `.codex/skills/configure-*` docs, references, scripts, templates, and tests when setup or generated behavior is implicated
- `.codex/delivery-context.local.json` when present, without printing secrets
- ignored `.codex/agent-telemetry.local.jsonl` when present, without printing prompts or sensitive payloads
- prior ticket comments with marker `IA generated post-PROD retrospective: {finalVersion}` when auditing PROD release learning evidence
- recent Git commits, branches, tags, PR labels, PR review comments, CI results, OpenSpec verification output, ticket comments, QA bug tickets, Nexus release manifests, and deployment evidence when available

## Workflow

### 0. Run Promptfoo Eval (eval-driven-improvement mode only)

When operating in `eval-driven-improvement` mode, run the eval as the first workflow step:

```bash
npx promptfoo eval --config .codex/agent-evals/promptfooconfig.yaml --no-cache
```

Or use the CLI runner:

```bash
python -m tools.sdd_cli agent-eval run
```

Read the output and persist key results to `.codex/agent-evals/results.local.json`:

```json
{
  "schemaVersion": 1,
  "lastRun": "2026-01-01T00:00:00Z",
  "mode": "eval-driven-improvement",
  "scope": "all",
  "totalTests": 22,
  "passed": 20,
  "failed": 2,
  "failures": [
    {
      "testId": 13,
      "description": "Parallel enabled, PR merged, lane owned by other, blocked",
      "expectedRoute": "blocked-lane-conflict",
      "actualRoute": "dev-ops-post-merge-deploy",
      "assertionPassed": false
    }
  ],
  "findings": []
}
```

**Persistence rules:**

- If no previous `results.local.json` exists → create it
- If a previous run exists with a **different** scope or timestamp → append as a new entry (keep history)
- If a previous run exists with the **same** scope → overwrite it (replace with latest results)

If the eval cannot run (missing `npx`, missing Python deps), report the blocker and stop.

### 1. Define The Audit Scope

Resolve what the user wants audited:

- one ticket or PR,
- one failed run,
- the latest delivery attempt,
- a class of failures such as QA bugs, review misses, CI failures, or deployment blockers,
- **eval regression**: Promptfoo test cases that recently failed,
- **eval coverage gap**: a routing scenario with no corresponding test case,
- the skill workflow itself,
- a post-PROD ticket release, using the primary ticket key, included ticket list, artifact commit, final release version, PROD URL, and release manifest supplied by `dev-ops-deploy-prod`.

If the scope is ambiguous and local evidence clearly identifies a current locked ticket or PR, use that as the scope and say so. If several scopes are plausible, run a read-only summary instead of guessing.

For `eval-driven-improvement`, the scope defaults to "all Promptfoo eval results" unless the user names specific test cases or failure patterns.

### 2. Reconstruct The Delivery Timeline (general audits only)

Build a concise timeline from durable checkpoints:

- ticket status and generated comments,
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

- **`eval-regression`**: a Promptfoo test case that **was passing and is now failing**. Indicates a routing logic change or delivery contract drift. Route to: diagnose routing provider, update test expectations, or flag unintentional contract drift.
- **`eval-coverage`**: a repeated delivery miss lacks a Promptfoo eval test case that would catch route selection, tool selection, argument precision, mutation gates, stop conditions, or handoff gaps. Route to: add a new test case to `promptfooconfig.yaml`.
- `implementation`: code, tests, OpenSpec tasks, or local validation missed something.
- `review`: `dev-flow-pr-review-agent` criteria, scope, labels, or marker behavior missed something.
- `quality-gate`: CI, coverage, secret scanning, dependency audit, or workflow checks missed something.
- `configuration`: generated templates, local config guidance, runner setup, or setup audit drifted from delivery requirements.
- `deployment`: artifact, release manifest, health contract, promotion, tag, or rollback rules missed something.
- `skill-drift`: delivery skills and configure skills disagree with `_shared/delivery-contract.md`.
- `observability`: evidence, logs, comments, or status reporting were insufficient to diagnose a run.
- `agency-risk`: an agent had too much write authority, used the wrong tool boundary, attempted unsafe mutation, or acted without sufficient confirmation.
- `model-optimization`: model choice, reasoning effort, prompt-cache hygiene, tool-call count, retries, latency, or token use produced avoidable cost or delay.
- `risk-depth`: delivery risk classification, compact path selection, workload forecast, adversarial review trigger, or installed-skill index behavior was missing, stale, too heavy for low-risk work, or too light for high-risk work.

For each finding, include the evidence, why it matters, and the durable improvement that would prevent recurrence.

Use `templates/audit-checklist.md` as the default report skeleton when producing a read-only audit or proposal.

### 4. Decide Whether To Improve

Apply one of these outcomes:

| Outcome                        | When To Use                                                                 | What To Do                                  |
| ------------------------------ | --------------------------------------------------------------------------- | ------------------------------------------- |
| `No change`                    | One-off, already covered, not actionable                                    | —                                           |
| `Fix routing provider`         | `eval-regression` caused by bug in `_evaluate_route()`                      | Edit `routing_provider.py` to fix logic     |
| `Update test expectation`      | `eval-regression` caused by intentional routing change                      | Edit `promptfooconfig.yaml` assertion       |
| `Promptfoo eval` (add test)    | `eval-coverage`: missing test for a known scenario                          | Add new test case in `promptfooconfig.yaml` |
| `Promptfoo eval` (modify test) | `eval-coverage`: existing test doesn't capture the right behavior           | Refine test vars or assertions              |
| `Skill instruction update`     | Skill needs clearer routing, classification, validation, or handoff rules   | Edit the relevant `SKILL.md`                |
| `Shared contract update`       | Multiple skills need a new common rule                                      | Edit `_shared/delivery-contract-core.md`    |
| `Configure sync update`        | Setup docs, templates, audit scripts, or tests must match delivery behavior | Edit `configure-*` skill                    |
| `Regression test`              | A script/template/check should enforce the rule                             | Add test                                    |
| `Quality gate update`          | CI or local validation should catch the issue                               | Update CI workflow                          |
| `Docs update`                  | Durable knowledge → promote to `docs/`                                      | Edit relevant `docs/*.md`                   |
| `Memory update`                | Reusable non-authoritative → store in `.codex/memory/`                      | Edit memory file                            |
| `Follow-up ticket`             | Change is product work, infra work, or too large                            | Create ticket                               |

For `eval-regression` findings, diagnose the root cause before choosing an outcome:

1. Check if the delivery contract has changed (e.g., new routing rules in `delivery-contract.md`)
2. Check if `routing_provider.py` was modified (git diff)
3. Check if `promptfooconfig.yaml` tests are stale (expectations don't match current routing)

**Heuristic: routing bug vs intentional change**

- If `routing_provider.py` was recently modified AND the change contradicts the delivery contract → **bug in routing provider** → outcome: `Fix routing provider`
- If `routing_provider.py` was recently modified AND the change matches the delivery contract → **test expectations are stale** → outcome: `Update test expectation`
- If `promptfooconfig.yaml` was not modified and `routing_provider.py` was not modified → **delivery contract drift** → outcome: `Shared contract update` or `Fix routing provider`

For `eval-coverage` findings, add the smallest test case that covers the repeated miss.

For `risk-depth` findings, prefer deterministic helpers or Promptfoo eval test cases over more prose.

Prefer tests or deterministic validation for enforceable rules. Prefer skill text only for judgment-heavy process rules.

For automatic `post-prod-ticket-release`, recommendation outcomes are advisory only. Repeated or high-severity findings may recommend docs, delivery contract, skill, configure, test, memory, or Promptfoo eval test case updates, but they must not be applied during the automatic audit.

For `eval-driven-improvement` in `apply` sub-mode, outcomes may be applied **only after**:

1. The Agent Self-Improvement Gate is satisfied (repeated pattern, high-severity, or contract conflict)
2. User confirms the proposed change
3. A new eval run confirms the fix passes all test cases

**Exception:** When triggered automatically from `dev-ops-deploy-prod`'s auto-escalation flow, requirement 2 (user confirmation) is bypassed because:

- A PROD eval regression is inherently high-severity (satisfies the Agent Self-Improvement Gate)
- Only eval infrastructure files (`routing_provider.py`, `promptfooconfig.yaml`) are modified
- Each fix is verified by re-running the eval before proceeding
- Any fix that causes other test failures is reverted — no unsafe change is committed

Before choosing any outcome other than `No change`, confirm the Agent Self-Improvement Gate in `.codex/skills/_shared/delivery-contract.md` is satisfied.

### 5. Apply Promptfoo Improvements

This step is **only executed in `eval-driven-improvement apply` sub-mode**, after:

1. The Agent Self-Improvement Gate is satisfied (repeated pattern, high-severity, or contract conflict)
2. User confirmed the proposed change from Step 4 (or triggered automatically from `dev-ops-deploy-prod`'s auto-escalation flow)

For each failing test case or coverage gap, apply the specific fix based on the outcome chosen in Step 4:

#### 5a. Fix Routing Provider (`eval-regression` — bug in routing logic)

When the routing logic in `routing_provider.py` has a bug:

1. Read the failing test case from `promptfooconfig.yaml` — understand which scenario is broken.
2. Trace through `_evaluate_route()` in `routing_provider.py` with the test's input variables.
3. Identify the incorrect condition or return path.
4. Fix the logic: correct the condition, add a missing check, or fix the return value.
5. Run the full eval suite: `npx promptfoo eval --config .codex/agent-evals/promptfooconfig.yaml --no-cache`.
6. If all tests pass, commit the fix. If not, iterate until all pass.

**Example:** If test 13 expects `blocked-lane-conflict` but returns `dev-ops-post-merge-deploy`, trace the `lane_owner` check in `_evaluate_route()` to find why the lane conflict isn't being detected.

#### 5b. Update Test Expectation (`eval-regression` — intentional routing change)

When the routing logic intentionally changed and the test needs updating:

1. Read the failing test case from `promptfooconfig.yaml` — note the expected route in the `javascript` assertion.
2. Determine the correct expected route from the current delivery contract and routing provider logic.
3. Update the expected route string inside the `javascript` assertion in `promptfooconfig.yaml`. For example, change `'dev-ops-post-merge-deploy'` to `'dev-ops-deploy-canary'`.
4. Run the full eval suite to confirm all tests pass with the updated expectation.
5. Commit the change.

**Example:** If a new route `dev-ops-deploy-canary` replaced `dev-ops-post-merge-deploy` for canary deployments, update the assertion from `'dev-ops-post-merge-deploy'` to `'dev-ops-deploy-canary'`.

#### 5c. Add New Test Case (`eval-coverage` — missing scenario)

When a routing scenario has no corresponding test:

1. Identify the missing scenario (e.g., "QA expired evidence routes to re-deploy").
2. Pick the right variables for the test case:
   - `scenario`: human-readable description
   - `ticketState`, `branchExists`, `prExists`, `prMerged`, `qaEvidence`: the state that triggers this route
   - `productStack`: `"selected"` or `"none"`
   - Any extra vars needed (`parallelEnabled`, `laneOwner`, `incident`, `hotfix`, etc.)
3. Add the expected route assertion:
   ```yaml
   - type: javascript
     value: "JSON.parse(output).route === 'dev-flow-expected-route'"
   ```
4. Run the full eval suite to confirm the new test passes AND all existing tests still pass.
5. Commit the change.

#### 5d. Apply Safely (all changes)

Regardless of the fix type, apply these safety rules:

1. Keep edits scoped to the improvement — fix one test case at a time.
2. Update `_shared/delivery-contract.md` first if the rule change is cross-cutting.
3. Update the matching durable docs if the finding is reusable project knowledge.
4. Run `npx promptfoo eval --no-cache` after EVERY change to confirm no regressions.
5. Do not change OpenSpec-specific skills unless the improvement explicitly affects OpenSpec behavior.
6. Commit and push after all eval tests pass.

### 6. Persist Eval-Driven Evidence

For `eval-driven-improvement`, persist the eval results and findings:

1. Write or update `.codex/agent-evals/results.local.json` with:
   - schema version and timestamp,
   - mode (`eval-driven-improvement`),
   - ticket key or scope identifier,
   - total tests, passed, failed counts,
   - per-failure details (test id, description, expected vs actual route),
   - finding summaries and recommendation outcomes,
   - `appliedChanges: false` or `appliedChanges: true` with file list.

2. For `post-prod-ticket-release`, write only compact, sanitized evidence:
   - Include schema version, timestamp, mode, ticket key, artifact commit, final release version, PROD URL host or safe URL, release manifest path or URL, inspected evidence categories, finding summaries, recommendation outcomes, eval coverage gaps, residual evidence gaps, and `appliedChanges: false`.

3. Do not store secrets, tokens, cookies, credential-bearing URLs, raw prompts, raw tool payloads, large logs, private request/response bodies, or unredacted local config values.

4. For ticket-scoped findings, add or reuse a compact ticket comment with marker:

   ```text
   IA generated post-PROD retrospective: {finalVersion}
   ```

   or for eval-specific findings:

   ```text
   IA generated eval improvement: {scopeIdentifier}
   ```

   Keep the marker as the first line by itself. Summarize audit scope, eval results, findings, recommendations, file changes (if any), and residual gaps.

## Output

For read-only audits (including `eval-driven-improvement probe/diagnose`), report:

- audit scope,
- evidence inspected,
- eval run summary (total, passed, failed) when applicable,
- timeline summary (general audits only),
- findings grouped by layer,
- recommended durable improvements,
- risks or evidence gaps,
- local result path and ticket provider marker status when applicable.

For applied improvements (including `eval-driven-improvement apply`), report:

- files changed,
- improvement rationale,
- synchronization work performed,
- eval pass/fail after changes,
- validation commands and results,
- remaining gaps or follow-up tickets.

Keep recommendations concrete. Avoid vague statements like "improve tests" unless paired with the exact missing test or gate.

## Failure Rules

- If `npx promptfoo eval` cannot run (missing tool, missing deps), report the blocker and stop for `eval-driven-improvement` mode. For other modes, eval is optional.
- If secrets or credential-bearing URLs are encountered, redact them and continue only with non-secret evidence.
- If delivery state is ambiguous, produce a read-only status/audit summary and do not mutate files.
- If evidence conflicts with the delivery contract, treat the contract as authoritative unless the user explicitly asks to revise the contract.
- If a proposed improvement would change deployment, QA, PROD, rollback, artifact, or ticket-state behavior, update configure docs/templates/audits/tests in the same change or report why synchronization is blocked.
- If validation cannot be run, state the reason and residual risk.
