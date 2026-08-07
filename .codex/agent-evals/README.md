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

**60 test cases** covering the full delivery routing matrix including parallel delivery,
deployment lanes, explicit workflow-stage requests, state-driven resume, the QA
user-approval gate, frontend stack skill activation, the PR Validation gate
(CI-in-loop review blocking), the ticket refinement gate (always ask the user
for extra info before writing the IA block, linear and parallel context), and the
Durable Learning Capture Gate (archive / hotfix / retrospective must run the
classifier and update only the classifier-selected candidates):

### Ticket Lifecycle (9 tests — rows 6–8 are cross-listed in the QA User-Approval Gate section below; 7 are lifecycle-unique)

| #   | Scenario                         | Expected Route                  |
| --- | -------------------------------- | ------------------------------- |
| 1   | Todo ticket, no branch           | `dev-flow-start-ticket`         |
| 2   | In Progress, branch, no PR       | `dev-flow-implement-ticket`     |
| 3   | Open PR exists                   | `dev-flow-implement-ticket`     |
| 4   | PR merged to dev                 | `dev-ops-post-merge-deploy`     |
| 5   | Ticket in QA                     | `configured QA gate`            |
| 6   | QA pending user approval         | `dev-ops-deploy-qa-approval-gate` |
| 7   | QA user-approved                 | `dev-ops-deploy-qa`             |
| 8   | QA failed                        | `dev-flow-file-qa-bug`          |
| 9   | Done, QA passed, no PROD request | `blocked-no-prod`               |

### QA User-Approval Gate (3 tests — rows 6–8, two cross-listed from Ticket Lifecycle)

Verifies the human-in-the-loop gate enforced in `dev-ops-deploy-qa`: QA is **not
auto-promoted** after DEV. The agent verifies DEV is healthy, then **asks the user
for approval** before dispatching the QA deployment. The provider models this with
the `qaApproved` var: pending approval routes to
`dev-ops-deploy-qa-approval-gate` (agent stops and asks — never auto-approves); an
explicit approval (or an explicit `deploy-qa` request, which wins via the
workflow-stage routing matrix) routes to `dev-ops-deploy-qa` (the dispatch proceeds).

| #   | Scenario                          | Expected Route                  |
| --- | --------------------------------- | ------------------------------- |
| 6   | QA pending, no user approval      | `dev-ops-deploy-qa-approval-gate` |
| 7   | QA pending, user approved         | `dev-ops-deploy-qa`             |
| 8   | Explicit `deploy-qa` request      | `dev-ops-deploy-qa`             |

### Edge Cases (4 tests)

| #   | Scenario         | Expected Route             |
| --- | ---------------- | -------------------------- |
| 10  | No product stack | `dev-flow-pipeline-status` |
| 11  | Ambiguous state  | `dev-flow-pipeline-status` |
| 12  | PROD incident    | `dev-ops-rollback-prod`    |
| 13  | PROD hotfix      | `dev-ops-hotfix-prod`      |

### Parallel Delivery (5 tests)

| #   | Scenario                                         | Expected Route              |
| --- | ------------------------------------------------ | --------------------------- |
| 14  | Parallel context (multi-ticket), Todo, lane free                | `dev-flow-start-ticket`     |
| 15  | Parallel context (multi-ticket), PR merged, lane owned by other | `blocked-lane-conflict`     |
| 16  | Parallel context (multi-ticket), QA stage, lane owned by other  | `blocked-lane-conflict`     |
| 17  | Parallel context (multi-ticket), max active tickets reached     | `blocked-max-active`        |
| 18  | Parallel context (multi-ticket), worktree exists, reuse         | `dev-flow-implement-ticket` |

### Deployment Lane (5 tests)

| #   | Scenario                                        | Expected Route              |
| --- | ----------------------------------------------- | --------------------------- |
| 19  | QA passed, PROD explicitly requested            | `dev-ops-deploy-prod`       |
| 20  | PROD deploy blocked by lane ownership           | `blocked-lane-conflict`     |
| 21  | PR merged, missing Nexus artifact               | `blocked-missing-artifact`  |
| 22  | Release tag conflict                            | `blocked-tag-conflict`      |
| 23  | PR merged, lane acquired (serialized lane free) | `dev-ops-post-merge-deploy` |

### Infrastructure Validation (2 tests)

| #   | Scenario                                            | Expected Route             |
| --- | --------------------------------------------------- | -------------------------- |
| 24  | PROD deploy blocked by NodePort collision           | `blocked-infra-validation` |
| 25  | DEV deploy blocked by infrastructure collision      | `blocked-infra-validation` |

### Explicit Workflow-Stage Requests (12 tests)

| #   | Scenario                                            | Expected Route                     |
| --- | --------------------------------------------------- | ---------------------------------- |
| 26  | Explicit continue-implementation request            | `dev-flow-continue-implementation` |
| 27  | Explicit propose-change request                     | `dev-flow-propose-change`          |
| 28  | Explicit PR review request                          | `dev-flow-pr-review-agent`         |
| 29  | Explicit PR review feedback request                 | `dev-flow-pr-review-feedback-loop` |
| 30  | Explicit explore-change request                     | `dev-flow-explore-change`          |
| 31  | Explicit scaffold-project request                   | `dev-flow-scaffold-project`        |
| 32  | Explicit verify-change request                      | `dev-flow-verify-change`           |
| 33  | Explicit archive-change request                     | `dev-flow-archive-change`          |
| 34  | Explicit dashboard update request                   | `grafana-board-update`             |
| 35  | Explicit retrospective-audit request                | `dev-flow-retrospective-audit`     |
| 36  | Explicit docs-knowledge-maintenance request         | `docs-knowledge-maintenance`       |
| 37  | Explicit multi-ticket request (implement 2 tickets) | `dev-flow-parallel-ticket-coordinator` |

### State-Driven Resume (1 test)

| #   | Scenario                                                  | Expected Route                     |
| --- | --------------------------------------------------------- | ---------------------------------- |
| 38  | In-progress + branch, auto-continue without named step    | `dev-flow-continue-implementation` |

### Regression (1 test)

| #   | Scenario                                 | Expected Route             |
| --- | ---------------------------------------- | -------------------------- |
| 39  | Product-free shell (original regression) | `dev-flow-pipeline-status` |

### Frontend Design Activation (3 tests)

Verifies stack-mapped skill activation during implementation: an implementation-stage
route on a frontend stack reports `activatedSkills` including `impeccable` (plus
`playwright`, `playwright-interactive`), mirroring the stack-mapping table in
`dev-flow-implement-ticket/SKILL.md`.

| #   | Scenario                                                              | Expected Route             | Activation                 |
| --- | --------------------------------------------------------------------- | -------------------------- | -------------------------- |
| 40  | Frontend (React + TS) implementation, needs UI design work            | `dev-flow-implement-ticket` | includes `impeccable`      |
| 41  | Backend-only (FastAPI) implementation, no frontend                    | `dev-flow-implement-ticket` | excludes `impeccable`      |
| 42  | Frontend stack, Todo ticket, no branch (not in implementation stage)  | `dev-flow-start-ticket`     | excludes `impeccable`      |

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
| 43  | Red run on open PR (state-driven loop)                                | `dev-flow-implement-ticket`        | `codexReviewed=false`, `BLOCKER`     |
| 44  | Green run on open PR                                                  | `dev-flow-implement-ticket`        | `codexReviewed=true`, no findings    |
| 45  | Pending run on open PR                                                | `dev-flow-implement-ticket`        | `codexReviewed=false`, `BLOCKER`     |
| 46  | Unknown/unreadable run on open PR                                     | `dev-flow-implement-ticket`        | `codexReviewed=false`, `BLOCKER`     |
| 47  | Explicit PR review request + red run                                  | `dev-flow-pr-review-agent`         | `codexReviewed=false`, `BLOCKER`     |
| 48  | Explicit PR review feedback request + red run                         | `dev-flow-pr-review-feedback-loop` | `codexReviewed=false`                |
| 49  | Merged PR with red run (gate not applicable)                          | `dev-ops-post-merge-deploy`        | `review === null`                    |

### Ticket Refinement Gate (5 tests)

Models `dev-flow-start-ticket` step 7: refinement runs **at least 1**
`grill-with-docs` cycle (at most 4) and **ALWAYS asks the user for extra info** —
even when the ticket seems complete — before the curated IA block is written.
The route is unchanged (still `dev-flow-start-ticket`); the always-ask invariant
is asserted via the provider's `refinement` gate object:
`refinement.userAsked === false` with `refinement.blocked === true` until the
user has been asked, `userAsked === true` with `blocked === false` once answered,
and `refinement === null` outside the start-ticket stage.

Rows 53-54 add the parallel-coordinator mirror
(`dev-flow-parallel-ticket-coordinator` Section 2 step 5): the coordinator must
verify `refinementUserAsked` per Todo ticket — reported by the `ticketStarter`
child agent (`refinementUserAsked: yes/no`) — before each ticket routes onward.
The provider applies the same `refinement` gate to a parallel Todo route
(`parallelEnabled: true` + `dev-flow-start-ticket`).

| #   | Scenario                                                             | Expected Route             | Refinement gate                      |
| --- | -------------------------------------------------------------------- | -------------------------- | ------------------------------------ |
| 50  | Todo refinement, user not asked yet                                  | `dev-flow-start-ticket`    | `userAsked=false`, `blocked=true`    |
| 51  | Todo refinement, user answered the clarifying questions              | `dev-flow-start-ticket`    | `userAsked=true`, `blocked=false`    |
| 52  | Implementation in progress (gate not applicable)                     | `dev-flow-implement-ticket` | `refinement === null`               |
| 53  | Parallel (multi-ticket) Todo, user not asked yet                     | `dev-flow-start-ticket`    | `userAsked=false`, `blocked=true`    |
| 54  | Parallel (multi-ticket) Todo, user answered                          | `dev-flow-start-ticket`    | `userAsked=true`, `blocked=false`    |

### Durable Learning Capture Gate (5 tests)

Models the Durable Learning Capture Gate wired into `dev-flow-archive-change`,
`dev-ops-hotfix-prod`, and `dev-flow-retrospective-audit`: after the stage
completes, the agent runs the classifier (`knowledge-search classify`), updates
**only** the classifier-selected candidate `docs/` / `knowledge/` files via
`docs-knowledge-maintenance`, and records the canonical markers. A missing capture
step is a blocker in those skills, so the `capture` gate object is asserted on the
completion-stage routes (and is `null` elsewhere, mirroring the review/refinement
gates). The retrospective is mode-aware: `captureMode: apply` updates the
candidate files; read-only / proposal / automatic `post-prod-ticket-release`
modes are **advisory only** (`capture.applied === false`, candidates reported as
recommendations, nothing written).

| #   | Scenario                                                                  | Expected Route                 | Capture gate                            |
| --- | ------------------------------------------------------------------------- | ------------------------------ | --------------------------------------- |
| 55  | Archive route runs the capture gate                                        | `dev-flow-archive-change`      | `applied=true`, `classifierRun=true`    |
| 56  | Hotfix route runs the capture gate                                         | `dev-ops-hotfix-prod`          | `applied=true`, `classifierRun=true`    |
| 57  | Retrospective in apply mode runs the capture gate                          | `dev-flow-retrospective-audit` | `applied=true`, `classifierRun=true`    |
| 58  | Retrospective in read-only mode is advisory only                           | `dev-flow-retrospective-audit` | `applied=false`, `scope=advisory-only` |
| 59  | Capture gate not applicable outside archive/hotfix/retrospective routes    | `dev-flow-implement-ticket`    | `capture === null`                      |

> Note: table row numbers trail the YAML file order by one (a pre-existing numbering drift — the
> table ends at row 59 while `promptfooconfig.yaml` holds 60 cases). Use the YAML `tests:` list as
> the authoritative order; row numbers here are labels only.

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

**Durable Learning Capture Gate:** to assert the capture step from the archive /
hotfix / retrospective skills, assert on the provider's `capture` gate object,
which is non-null only on the `dev-flow-archive-change`, `dev-ops-hotfix-prod`, and
`dev-flow-retrospective-audit` routes:

- `capture.applicable === true`, `capture.classifierRun === true`, and
  `capture.applied === true` (with `scope === 'classifier-selected-candidates'`)
  on those routes — the classifier must run and only the selected candidates are
  updated.
- `capture.applied === false` with `scope === 'advisory-only'` when the
  retrospective runs in read-only / proposal / automatic `post-prod-ticket-release`
  mode (set `captureMode: read-only` in the vars; default is `apply`).
- `capture === null` on any other route (gate not applicable).

**Ticket refinement gate:** to assert the always-ask rule from
`dev-flow-start-ticket` step 7, set `refinementUserAsked` in the test vars
(`true` = the user already answered the grill-with-docs clarifying questions;
`false`/unset = not asked yet) and assert on the provider's `refinement` gate
object, which is non-null only on the `dev-flow-start-ticket` route:

- `refinement.userAsked === false` with `refinement.blocked === true` (and a
  `blocker` message) until the user has been asked.
- `refinement.userAsked === true` with `refinement.blocked === false` once the
  user answered.
- `refinement === null` on any other route (gate not applicable).

Route is intentionally unaffected: refinement still runs in `dev-flow-start-ticket`;
the gate only blocks writing the curated IA block until the user has been asked.
