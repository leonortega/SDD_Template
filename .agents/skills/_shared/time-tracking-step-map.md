<!-- TIER 3: STAGE-SPECIFIC - Step-to-message mapping for OpenProject time tracking -->

# Time Tracking Step Map

Every delivery step MUST call `time-telemetry-upsert` after completion to record
time spent on the ticket in OpenProject. This reference maps each workflow step
to its OpenProject activity, comment message template, and duration variable.

## Usage

After finishing each step, run:

```bash
python -m tools.sdd_cli dev-flow telemetry-upsert \
  --ticket-key {ticketKey} --workflow-stage {workflowStage} \
  --agent-role {agentRole} --started-utc {startedUtc} \
  --finished-utc {finishedUtc} --outcome {outcome}
```

The `{duration}` is computed as `finishedUtc - startedUtc` and encoded as
ISO-8601 (e.g. `PT1H30M` for 1.5 hours). The CLI script derives it
automatically from the timestamps.

## Step Map

| # | Workflow Stage (workflowStage) | Agent Role (agentRole) | Activity | Comment Message Template | Duration Variable |
|---|-------------------------------|----------------------|----------|-------------------------|-------------------|
| 1 | `dev-flow-start-ticket` | `startTicket` | Specification (2) | `IA generated workflow telemetry: {ticketKey}:dev-flow-start-ticket — Ticket started and branch prepared` | `{duration}` = `finishedUtc − startedUtc` |
| 2 | `dev-flow-propose-change` | `proposeChange` | Specification (2) | `IA generated workflow telemetry: {ticketKey}:dev-flow-propose-change — OpenSpec proposal created` | `{duration}` = `finishedUtc − startedUtc` |
| 3 | `dev-flow-implement-ticket` | `implementation` | Development (3) | `IA generated workflow telemetry: {ticketKey}:dev-flow-implement-ticket — Code implementation complete` | `{duration}` = `finishedUtc − startedUtc` |
| 4 | `dev-flow-pr-review-agent` | `prReview` | Development (3) | `IA generated workflow telemetry: {ticketKey}:dev-flow-pr-review-agent — PR reviewed` | `{duration}` = `finishedUtc − startedUtc` |
| 5 | `dev-flow-pr-review-feedback-loop` | `reviewFeedback` | Development (3) | `IA generated workflow telemetry: {ticketKey}:dev-flow-pr-review-feedback-loop — Review feedback addressed` | `{duration}` = `finishedUtc − startedUtc` |
| 6 | `dev-flow-verify-change` | `verify` | Testing (4) | `IA generated workflow telemetry: {ticketKey}:dev-flow-verify-change — Change verified against spec` | `{duration}` = `finishedUtc − startedUtc` |
| 7 | `dev-flow-archive-change` | `archive` | Management (1) | `IA generated workflow telemetry: {ticketKey}:dev-flow-archive-change — Change archived` | `{duration}` = `finishedUtc − startedUtc` |
| 8 | `dev-flow-file-qa-bug` | `fileBug` | Testing (4) | `IA generated workflow telemetry: {ticketKey}:dev-flow-file-qa-bug — QA bug filed` | `{duration}` = `finishedUtc − startedUtc` |
| 9 | `dev-flow-continue-implementation` | `continueImpl` | Development (3) | `IA generated workflow telemetry: {ticketKey}:dev-flow-continue-implementation — Implementation continued` | `{duration}` = `finishedUtc − startedUtc` |
| 10 | `dev-ops-post-merge-deploy` | `postMergeDeploy` | Development (3) | `IA generated workflow telemetry: {ticketKey}:dev-ops-post-merge-deploy — Post-merge deploy complete` | `{duration}` = `finishedUtc − startedUtc` |
| 11 | `dev-ops-deploy-qa` | `deployQA` | Development (3) | `IA generated workflow telemetry: {ticketKey}:dev-ops-deploy-qa — QA deployment complete` | `{duration}` = `finishedUtc − startedUtc` |
| 12 | `dev-ops-deploy-prod` | `deployProd` | Development (3) | `IA generated workflow telemetry: {ticketKey}:dev-ops-deploy-prod — Production deployment complete` | `{duration}` = `finishedUtc − startedUtc` |
| 13 | `dev-ops-rollback-prod` | `rollbackProd` | Support (5) | `IA generated workflow telemetry: {ticketKey}:dev-ops-rollback-prod — Production rollback complete` | `{duration}` = `finishedUtc − startedUtc` |
| 14 | `dev-ops-hotfix-prod` | `hotfixProd` | Support (5) | `IA generated workflow telemetry: {ticketKey}:dev-ops-hotfix-prod — Production hotfix applied` | `{duration}` = `finishedUtc − startedUtc` |
| 15 | `qa-gate` | `qaGate` | Testing (4) | `IA generated workflow telemetry: {ticketKey}:qa-gate — QA gate evaluated` | `{duration}` = `finishedUtc − startedUtc` |

## Activity ID Reference

| Activity Name | ID | Used By Steps |
|--------------|-----|---------------|
| Management | 1 | archive |
| Specification | 2 | startTicket, proposeChange |
| Development | 3 | implementation, prReview, reviewFeedback, continueImpl, postMergeDeploy, deployQA, deployProd |
| Testing | 4 | verify, fileBug, qaGate |
| Support | 5 | rollbackProd, hotfixProd |
| Other | 6 | (unused by default) |

## Duration Encoding

The `{duration}` variable is an ISO-8601 duration computed from timestamps:

- Whole hours: `PT{n}H` (e.g. 3 hours → `PT3H`)
- Hours and minutes: `PT{n}H{n}M` (e.g. 1h 30m → `PT1H30M`)
- Minutes only: `PT{n}M` (e.g. 45 minutes → `PT45M`)

The CLI script (`telemetry-upsert`) computes this automatically from
`--started-utc` and `--finished-utc`. Never compute duration manually.

## Constraint

**Every delivery step MUST call `time-telemetry-upsert` before handoff.** If the
call fails, stop and report — do not skip time tracking. The only exception is
read-only operations (listing, exploring, questioning) that do not mutate ticket
state.
