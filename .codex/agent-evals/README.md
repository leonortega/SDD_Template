# Agent Evaluation

This directory contains the **Promptfoo**-based agent evaluation system for testing workflow routing decisions.

## Quick Start

```bash
# Run all evals
npx promptfoo eval --no-cache

# View results in browser
npx promptfoo view
```

## Structure

| File                   | Purpose                                           |
| ---------------------- | ------------------------------------------------- |
| `promptfooconfig.yaml` | Test cases, providers, assertions                 |
| `routing_provider.py`  | Python custom provider implementing routing logic |
| `README.md`            | This file                                         |

## Test Cases

**22 test cases** covering the full delivery routing matrix including parallel delivery and deployment lanes:

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

### Regression (1 test)

| #   | Scenario                                 | Expected Route             |
| --- | ---------------------------------------- | -------------------------- |
| 22  | Product-free shell (original regression) | `dev-flow-pipeline-status` |

## CI Integration

The Gitea workflow `.gitea/workflows/agent-eval.yml` runs evals automatically on PRs to `dev`.

## Adding Test Cases

1. Add a new entry under `tests:` in `promptfooconfig.yaml`
2. Add the matching routing logic in `routing_provider.py` → `_evaluate_route()`
3. Add the expected route assertion using `javascript` type assertion
4. Run `npx promptfoo eval --no-cache` to verify
