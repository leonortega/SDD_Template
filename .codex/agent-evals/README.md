# Agent Evaluation

This directory contains the **Promptfoo**-based agent evaluation system for testing workflow routing decisions.

## Quick Start

```bash
# Run all evals via the repo CLI (fails loudly, exits non-zero on failure)
python -m tools.sdd_cli agent-eval run

# View results in browser
python -m tools.sdd_cli agent-eval view

# Direct promptfoo (alternative to the CLI runner)
npx promptfoo eval --no-cache
```

## Windows: npm cache EBUSY/EPERM workaround

On some Windows hosts, `npx promptfoo` fails to start because npm's cache
cleanup trips over a locked `onnxruntime-node` binary (EBUSY/EPERM). The
command exits 1 with no output. `python -m tools.sdd_cli agent-eval run`
detects this and **fails loudly** with a clear error instead of reporting a
misleading "0 tests passed".

Workarounds, in order of preference:

1. **Install promptfoo globally** so npx uses the cached binary, then retry:
   `npm install -g promptfoo`
2. **Clear the npm cache** and retry: `npm cache clean --force` (or delete
   `%LocalAppData%\npm-cache\_npx`).
3. **Use WSL / a Unix machine** where onnxruntime-node installs cleanly.

The eval is fully deterministic (no LLM), so you can also verify every case
without promptfoo by running the Python provider directly against the YAML
assertions (see `routing_provider.py` + `promptfooconfig.yaml`).

**Deterministic fallback recipe** (proven 46/46 on a Windows host):

1. `import routing_provider` from this directory.
2. Load `promptfooconfig.yaml` (pyyaml is available).
3. For each test case, call `routing_provider.call_api("", {}, {"vars": test["vars"]})`
   and read `{"output": "<json>"}`.
4. Evaluate the `is-json` + `javascript` assertions exactly with node:
   `new Function('output', 'return (' + assertion + ');')(output)`.
5. Persist to `.codex/agent-evals/results.local.json` (mode `post-prod-eval`, scope = release version).

Cleanup after a broken global promptfoo: `npm uninstall -g promptfoo` so a
broken install does not shadow real runs. Console gotcha on Windows cp1252
terminals: printing emoji from eval JSON crashes `print()` — prefix with
`PYTHONIOENCODING=utf-8`.

## Structure

| File                   | Purpose                                           |
| ---------------------- | ------------------------------------------------- |
| `promptfooconfig.yaml` | Test cases, providers, assertions                 |
| `routing_provider.py`  | Python custom provider implementing routing logic |
| `README.md`            | This file                                         |

## Test Cases

**46 test cases** covering the full delivery routing matrix including parallel delivery,
deployment lanes, explicit workflow-stage requests, state-driven resume, frontend
stack skill activation, and the PR Validation gate (CI-in-loop review blocking):

### Ticket Lifecycle (7 tests)

| #   | Scenario                         | Expected Route              |
| --- | -------------------------------- | --------------------------- |
| 1   | Todo ticket, no branch           | `dev-flow-start-ticket`     |
| 2   | In Progress, branch, no PR       | `dev-flow-implement-ticket` |
| 3   | Open PR exists                   | `dev-flow-implement-ticket` |
| 4   | PR merged to dev                 | `dev-ops-post-merge-deploy` |
| 5   | Ticket in QA                     | `configured QA gate`        |
| 6   | QA failed                        | `dev-flow-file-qa-bug`      |
| 7   | Done, QA passed, no PROD request | `blocked-no-prod`           |

### Edge Cases (4 tests)

| #   | Scenario         | Expected Route             |
| --- | ---------------- | -------------------------- |
| 8   | No product stack | `dev-flow-pipeline-status` |
| 9   | Ambiguous state  | `dev-flow-pipeline-status` |
| 10  | PROD incident    | `dev-ops-rollback-prod`    |
| 11  | PROD hotfix      | `dev-ops-hotfix-prod`      |

### Parallel Delivery (5 tests)

| #   | Scenario                                         | Expected Route              |
| --- | ------------------------------------------------ | --------------------------- |
| 12  | Parallel enabled, Todo, lane free                | `dev-flow-start-ticket`     |
| 13  | Parallel enabled, PR merged, lane owned by other | `blocked-lane-conflict`     |
| 14  | Parallel enabled, QA stage, lane owned by other  | `blocked-lane-conflict`     |
| 15  | Parallel enabled, max active tickets reached     | `blocked-max-active`        |
| 16  | Parallel enabled, worktree exists, reuse         | `dev-flow-implement-ticket` |

### Deployment Lane (5 tests)

| #   | Scenario                                        | Expected Route              |
| --- | ----------------------------------------------- | --------------------------- |
| 17  | QA passed, PROD explicitly requested            | `dev-ops-deploy-prod`       |
| 18  | PROD deploy blocked by lane ownership           | `blocked-lane-conflict`     |
| 19  | PR merged, missing Nexus artifact               | `blocked-missing-artifact`  |
| 20  | Release tag conflict                            | `blocked-tag-conflict`      |
| 21  | PR merged, lane acquired (serialized lane free) | `dev-ops-post-merge-deploy` |

### Infrastructure Validation (2 tests)

| #   | Scenario                                            | Expected Route             |
| --- | --------------------------------------------------- | -------------------------- |
| 22  | PROD deploy blocked by NodePort collision           | `blocked-infra-validation` |
| 23  | DEV deploy blocked by infrastructure collision      | `blocked-infra-validation` |

### Explicit Workflow-Stage Requests (11 tests)

| #   | Scenario                                            | Expected Route                     |
| --- | --------------------------------------------------- | ---------------------------------- |
| 24  | Explicit continue-implementation request            | `dev-flow-continue-implementation` |
| 25  | Explicit propose-change request                     | `dev-flow-propose-change`          |
| 26  | Explicit PR review request                          | `dev-flow-pr-review-agent`         |
| 27  | Explicit PR review feedback request                 | `dev-flow-pr-review-feedback-loop` |
| 28  | Explicit explore-change request                     | `dev-flow-explore-change`          |
| 29  | Explicit scaffold-project request                   | `dev-flow-scaffold-project`        |
| 30  | Explicit verify-change request                      | `dev-flow-verify-change`           |
| 31  | Explicit archive-change request                     | `dev-flow-archive-change`          |
| 32  | Explicit dashboard update request                   | `grafana-board-update`             |
| 33  | Explicit retrospective-audit request                | `dev-flow-retrospective-audit`     |
| 34  | Explicit docs-knowledge-maintenance request         | `docs-knowledge-maintenance`       |

### State-Driven Resume (1 test)

| #   | Scenario                                                  | Expected Route                     |
| --- | --------------------------------------------------------- | ---------------------------------- |
| 35  | In-progress + branch, auto-continue without named step    | `dev-flow-continue-implementation` |

### Regression (1 test)

| #   | Scenario                                 | Expected Route             |
| --- | ---------------------------------------- | -------------------------- |
| 36  | Product-free shell (original regression) | `dev-flow-pipeline-status` |

### Frontend Design Activation (3 tests)

Verifies stack-mapped skill activation during implementation: an implementation-stage
route on a frontend stack reports `activatedSkills` including `impeccable` (plus
`playwright`, `playwright-interactive`), mirroring the stack-mapping table in
`dev-flow-implement-ticket/SKILL.md`.

| #   | Scenario                                                              | Expected Route             | Activation                 |
| --- | --------------------------------------------------------------------- | -------------------------- | -------------------------- |
| 37  | Frontend (React + TS) implementation, needs UI design work            | `dev-flow-implement-ticket` | includes `impeccable`      |
| 38  | Backend-only (FastAPI) implementation, no frontend                    | `dev-flow-implement-ticket` | excludes `impeccable`      |
| 39  | Frontend stack, Todo ticket, no branch (not in implementation stage)  | `dev-flow-start-ticket`     | excludes `impeccable`      |

### PR Validation Gate (7 tests)

Verifies the CI-in-loop rule enforced in `dev-flow-pr-review-agent` /
`dev-flow-pr-review-feedback-loop`: a **red, pending, or unreadable PR Validation run
on the current head is a `BLOCKER` finding** (stable id `CI-001`) and **keeps the
`codex-reviewed` clean marker off** — the PR stays blocked on the CI gate until the
run is green. The route is unchanged (the review/fix loop still runs to fix the failing
steps); the blocking is asserted via the provider's `review` gate object:
`review.codexReviewed === false` with a `BLOCKER` finding in `review.findings`.

| #   | Scenario                                                              | Expected Route                     | Review gate                          |
| --- | --------------------------------------------------------------------- | ---------------------------------- | ------------------------------------ |
| 40  | Red run on open PR (state-driven loop)                                | `dev-flow-implement-ticket`        | `codexReviewed=false`, `BLOCKER`     |
| 41  | Green run on open PR                                                  | `dev-flow-implement-ticket`        | `codexReviewed=true`, no findings    |
| 42  | Pending run on open PR                                                | `dev-flow-implement-ticket`        | `codexReviewed=false`, `BLOCKER`     |
| 43  | Unknown/unreadable run on open PR                                     | `dev-flow-implement-ticket`        | `codexReviewed=false`, `BLOCKER`     |
| 44  | Explicit PR review request + red run                                  | `dev-flow-pr-review-agent`         | `codexReviewed=false`, `BLOCKER`     |
| 45  | Explicit PR review feedback request + red run                         | `dev-flow-pr-review-feedback-loop` | `codexReviewed=false`                |
| 46  | Merged PR with red run (gate not applicable)                          | `dev-ops-post-merge-deploy`        | `review === null`                    |

## Adding Test Cases

1. Add a new entry under `tests:` in `promptfooconfig.yaml`
2. Add the matching routing logic in `routing_provider.py` → `_evaluate_route()`
3. Add the expected route assertion using `javascript` type assertion
4. Run `python -m tools.sdd_cli agent-eval run` to verify

**Explicit workflow-stage requests:** to cover a routing-matrix route that is driven by
user intent rather than ticket state (e.g. `dev-flow-continue-implementation`,
`dev-flow-explore-change`, `grafana-board-update`), set `requestType: <kebab-case>` in
the test vars and add the matching entry to `EXPLICIT_REQUEST_ROUTES` in
`routing_provider.py`. Explicit requests are evaluated after incident/hotfix but before
the missing-stack fallback and ticket-state routing.

**State-driven resume:** for the auto-continue orchestrator without a `requestType`,
set `resumeRequested: true` with an in-progress ticket that has an existing branch. The
provider routes it to `dev-flow-continue-implementation` before merged-PR handling.

**Frontend stack activation:** the provider reports `activatedSkills` in its JSON output
for implementation-stage routes, mirroring the stack-mapping table in
`dev-flow-implement-ticket/SKILL.md`. A frontend stack (react, vue, svelte, angular,
next, nuxt, astro, frontend, typescript, javascript, web) activates `playwright`,
`playwright-interactive`, and `impeccable`; non-frontend stacks and non-implementation
routes activate none. Assert both `route` and `activatedSkills` in the test case.

**PR Validation gate:** to assert the CI-in-loop rule, set `prValidationStatus` in the
test vars (`green`, `red`, `pending`, or `unknown`; unset defaults to `unknown` —
fail-closed, matching the skill rule that an undetermined status keeps `codex-reviewed`
off; legacy tests that predate the gate assert only `route` and are unaffected) and
assert on the provider's `review` gate object, which is non-null only for an open PR
(exists, not merged):

- `review.codexReviewed === true` with empty `review.findings` only when the run is green.
- `review.codexReviewed === false` with a `BLOCKER` finding (`id: CI-001`, `source:
  pr-validation`) whenever the run is red, pending, or unknown.
- `review === null` once the PR is merged (the gate no longer applies).

Route is intentionally unaffected: the review/fix loop still runs to fix failing CI
steps, so the blocking is expressed through the review gate, not a dead-end blocked
route.
