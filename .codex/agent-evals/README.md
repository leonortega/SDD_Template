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

## Structure

| File                   | Purpose                                           |
| ---------------------- | ------------------------------------------------- |
| `promptfooconfig.yaml` | Test cases, providers, assertions                 |
| `routing_provider.py`  | Python custom provider implementing routing logic |
| `README.md`            | This file                                         |

## Test Cases

**36 test cases** covering the full delivery routing matrix including parallel delivery,
deployment lanes, explicit workflow-stage requests, and state-driven resume:

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
