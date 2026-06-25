---
name: dev-flow-start-ticket
description: Start configured work items from chat by listing Todo tickets, preparing safe repository branches, pushing new branches, generating OpenSpec-style planning notes, updating the ticket description, and commenting with the branch through selected project-profile adapters. Use when the user asks to start the next ticket, start a specific ticket key, list Todo tickets, prepare a ticket branch, or connect ticket work to the local repository/OpenSpec workflow.
---

# Start Ticket

## Overview

Use this skill for a chat-driven ticket workflow. The user should not need to run a command; Codex should call the selected ticket adapter and local Git commands from the conversation.

For setup details and branch pattern options, read `references/configuration.md` when configuration is missing or the user asks how to configure the tools. Before making ticket-provider calls, read `.codex/project-profile.json` and the selected ticket adapter path; read provider-specific references only when that adapter requires them.

## Shared Context

Before mutating ticket or repository state, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/architecture.md` as the stage-specific doc. Load selected ticket and repository adapters before any mutation.

This skill owns initial creation of ignored `.codex/delivery-context.local.json` for automatic delivery. OpenProject time entries are the primary telemetry store; ignored `.codex/agent-telemetry.local.jsonl` is fallback only. Never commit local workflow files.

## Workflow Telemetry

Capture UTC start time before the first ticket-specific mutation. When OpenProject time-entry telemetry is available, create or update the `dev-flow-start-ticket` time entry with marker `IA generated workflow telemetry: {ticketKey}:dev-flow-start-ticket`. If direct time telemetry is unavailable, initialize fallback `.codex/agent-telemetry.local.jsonl` and append a row with `python -m tools.sdd_cli delivery -Mode AppendWorkflowTelemetry -TicketKey {ticketKey}`. On resume or idempotent reuse, append or update another row for the same stage; workflow timing rendering collapses repeated stage rows into earliest start and latest finish. Include `workflowStage=dev-flow-start-ticket`, `agentRole=ticketStarter`, `startedUtc`, `finishedUtc`, `retryCount`, and `outcome`. If a blocker happens before a ticket key is selected, report that no telemetry row was possible.

## Configuration

Read `.codex/project-profile.json` first for the selected ticket provider, ticket key pattern, branch policy, and adapter path. Read `.codex/client-tools.local.json` only for selected adapter runtime values. Fall back to `.codex/client-tools.common.json` only for defaults and setup guidance, then apply provider-supported environment variable overrides only when present. Defaults are:

- Todo state: `Todo`
- In-progress state: `In Progress`
- Base branch, branch prefix, branch pattern, ticket key pattern, and maximum branch length from `.codex/project-profile.json` or the selected repository adapter.

Before any mutating step, validate that the selected ticket adapter has the runtime values it requires, that the configured base branch exists, and that the branch pattern includes `{ticketKeySlug}`.

## Stack Context Preflight

Before starting the first ticket, and before mutating any Todo ticket when stack context has not been verified, confirm the project tool set and tech stack are configured. This prevents the first OpenSpec proposal and generated ticket block from being created with generic or stale assumptions.

Required stack context:

- `docs/architecture.md`, `docs/development.md`, and `docs/deployment.md` contain `Technology Stack And Tool Set`.
- `openspec/config.yaml` contains `context:` and `rules:` with the current stack and artifact guidance.
- `.codex/tool-recommendations.common.json` exists as the tracked placeholder-safe shape/template.
- Ignored `.codex/tool-recommendations.local.json` is used only after project guidance discovery confirms local recommendations and `usedInSteps`.

Run the read-only recommendation audit before Git, ticket provider, or OpenSpec mutation when any of these files are missing, appear unconfigured, or this is the first ticket start in a fresh repository:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode AuditRecommendedTools
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode DiscoverProjectGuidance
```

If the audit reports any `stack-context.*` warning, if `DiscoverProjectGuidance` reports missing suggested skills or guidance that the operator has not reviewed, or if the required files are missing or placeholder-only, stop before branch creation, OpenProject description updates, comments, state changes, ticket-lock writes, or OpenSpec proposal creation. Route to `$configure-dev-environment` plus `project-guidance-discover` to define the stack/tooling docs, complete `openspec/config.yaml`, research extra useful guidance from detected project signals, confirm or dismiss suggestions, and update the local recommendation catalog first.

## Workflow

### No Ticket Specified

1. List tickets in the configured Todo state using the selected ticket adapter with credentials from local JSON config or optional environment overrides.
2. Show ticket key, title, and state.
3. Ask the user to choose a ticket, even if there is exactly one Todo ticket.
4. Do not mutate Git or ticket provider while only listing tickets.

### Ticket Specified

1. Fetch the ticket by key or id.
2. Run the Ticket Refinement Gate from the shared delivery contract before mutating Git, ticket status, the ticket lock, or OpenSpec:
   - Prefer repo-local readiness helpers when available.
   - `ready`: continue.
   - `refinable`: use grill-style refinement before writing the managed ticket provider block. Prefer `grill-with-docs` style when answers create durable product, domain, acceptance, or rationale knowledge; use `grill-me` style only for temporary alignment. Generate Scrum-ready planning details with a problem or opportunity, user story, concrete acceptance criteria, scope or affected areas, dependencies or assumptions, validation expectations, risks, and definition of done in the managed ticket provider block, then continue.
   - `blocked`: stop before branch creation, ticket status updates, comments, ticket-lock writes, or OpenSpec proposal creation. Report the missing product or technical intent.
3. Run the Stack Context Preflight. If stack/tooling docs, OpenSpec config, local project guidance catalog, or project guidance discovery review are missing or drifted, stop and route to `configure-dev-environment` and `project-guidance-discover` before mutating Git, ticket provider, or OpenSpec.
4. Check `git status --porcelain`. If any output exists, stop and report changed files.
5. Prepare workflow telemetry for the selected ticket. Prefer OpenProject time entries with the configured `openProject.timeTelemetry` activity. Initialize and clear `.codex/agent-telemetry.local.jsonl` with `python -m tools.sdd_cli delivery -Mode InitializeWorkflowTelemetry -TicketKey {ticketKey}` only when the OpenProject time-entry path is unavailable. Do not initialize telemetry when only listing Todo tickets.
6. Switch to the configured base branch and run `git pull --ff-only`.
7. Create or reuse the configured branch name.
8. Pre-scan branch conflicts before creating or switching branches:
   - `git show-ref --verify refs/heads/{branchName}` for a local branch.
   - `git ls-remote --heads origin {branchName}` for a remote branch.
   If both exist and point to different commits, stop and report the conflict. If the remote branch exists and the local branch is missing, create the local branch from the remote only when it descends from the configured base branch.
9. Push the branch to repository/review provider with upstream tracking using `git push -u origin {branchName}`. If the upstream branch already exists and points to the same commit, treat it as complete; if the push is rejected or would require a non-fast-forward update, stop and report the branch issue.
10. Analyze the ticket description in an OpenSpec explore style unless OpenSpec is explicitly skipped by policy below.
11. Update only the managed generated block in the ticket description.
12. Add a ticket comment with the branch name, base branch, pushed repository branch, and OpenSpec decision, unless a generated comment for the same branch already exists.
13. Create or update `.codex/delivery-context.local.json` with `ticketKey`, `branch`, `openspecChange` when applicable, and any known PR/artifact/version fields. If an existing lock names a different ticket, fetch the locked ticket through the OpenProject API when OpenProject is selected, otherwise through the selected ticket adapter, and compare its status with the configured `openProject.doneStatus` or default `Done`. If the locked ticket is `Done`, call `EnsureDeliveryContext` with `replaceExisting=true` for the new selected ticket. If the locked ticket is active, missing, ambiguous, or cannot be verified, stop and report the stale-lock blocker. Do not delete the lock merely because the old ticket is QA Done or ready for PROD; replacement is lazy on the next ticket start.
14. Move the ticket to the configured in-progress status, unless it is already there.
15. Create an OpenSpec proposal using the `dev-flow-propose-change` skill (`/opsx:propose`) with a change name matching the branch name as closely as OpenSpec allows, unless OpenSpec is explicitly skipped.

For step 15, if the branch name contains `/`, convert it to a filesystem-safe kebab-case OpenSpec change id by replacing `/` with `-`. Example: branch `feat/e2eproject-1-create-files-and-folders-for-a-site` becomes OpenSpec change `feat-e2eproject-1-create-files-and-folders-for-a-site`. Use the ticket title and generated planning block as proposal input.

Only move the ticket to the in-progress status after branch creation, repository/review provider push, generated description update, and branch comment all succeed or are confirmed idempotently already complete. Only create the OpenSpec proposal after the ticket is in the in-progress status.

## OpenSpec Decision

Default to creating an OpenSpec proposal for feature, bug, and hotfix tickets. Skip OpenSpec only when one of these is true:

- the ticket contains an explicit `no-openspec` marker,
- the ticket is clearly labeled or titled as `chore` or `ops-only`,
- the user explicitly requests no OpenSpec in the current chat.

When OpenSpec is skipped, write `OpenSpec: skipped ({reason})` in the generated ticket block and branch comment. Do not invoke `dev-flow-propose-change`.

## Branch Naming

Build branch names from the configured pattern. Supported placeholders:

- `{prefix}`
- `{ticketKeySlug}`
- `{projectKeySlug}`
- `{titleSlug}`

Slug rules:

- Lowercase all text.
- Replace `/` and non-alphanumeric runs with `-`.
- Collapse repeated dashes.
- Trim leading and trailing dashes.
- Cap to configured max length.

Default example:

```text
feat/e2eproject-1-create-files-and-folders-for-a-site
```

## Generated Ticket Block

The managed generated block is the durable destination for grill-style product and ticket clarity. Do not add a separate `CONTEXT.md`, ADR, or upstream-default grill skill artifact while starting a ticket.

Use this exact generated section in the ticket description:

```text
---

IA generated

<!-- ia-generated:start -->

Problem / opportunity:
...

User story:
- As a ...
- I want ...
- So that ...

Acceptance criteria:
- ...

Scope / affected areas:
- ...

Dependencies / assumptions:
- ...

Validation expectations:
- ...

Risks:
- ...

Definition of done:
- ...

<!-- ia-generated:end -->
```

On rerun, replace only the content between `<!-- ia-generated:start -->` and `<!-- ia-generated:end -->`. Preserve all human-written text outside the markers exactly. If only one marker exists, stop and ask for manual cleanup.

Acceptance criteria must be concrete and testable. Reject and regenerate criteria containing generic wording such as `works correctly`, `as expected`, or `properly implemented`.

Concrete examples:

- `GET /health returns HTTP 200 with JSON field status equal to ok.`
- `Submitting an empty contact form shows required-field validation without creating a record.`
- `The home page renders the configured site title on desktop and mobile widths.`
- `Unauthorized API requests return HTTP 401 and do not expose stack traces or secrets.`

## Ticket Provider Access

Use OpenProject API v3 `work_packages` endpoints when the selected ticket adapter is OpenProject.

Use the selected ticket adapter only. Never use MCPs, Docker containers, or direct database access for ticket delivery unless the selected adapter explicitly requires it.

Load credentials from `.codex/client-tools.local.json` or optional environment overrides only. Avoid echoing request headers, tokens, or full credential-bearing URLs.

Use provider-neutral operations from `.codex/skills/_shared/provider-adapter-contract.md`: `list`, `read`, `enrich`, `move-state`, `comment`, and `verify-marker`. The selected ticket adapter translates those operations to concrete endpoints, payload fields, lock/version mechanics, and state names.
Fetch the current `lockVersion` before OpenProject description or status updates.

To move a ticket to the in-progress status, resolve the configured target state through the selected ticket adapter. Do not guess a state id or provider-specific lock/version value.

Use `IA generated branch: {branchName}` as the stable branch comment marker. If existing comments contain the same marker, do not add another branch comment.

## Output

Report the selected ticket, branch, OpenSpec change or explicit no-OpenSpec rationale, ticket lock path, telemetry initialization, validation performed, ticket comment marker, and handoff to `dev-flow-implement-ticket`.

## Failure Rules

- Dirty working tree: stop before branch creation or ticket-provider mutation.
- Missing selected ticket adapter config: explain the missing setup and reference `references/configuration.md`.
- Invalid or empty title slug: fall back to a ticket-key-only branch segment.
- Existing branch: switch to it instead of creating a duplicate.
- Failed fast-forward pull: stop and report the branch issue.
- Local/remote branch conflict: stop before ticket-provider mutation and report both refs.
- Failed repository branch push: stop before ticket-provider mutation and report the push failure.
- Malformed generated markers: stop before updating the ticket.
- Weak generated analysis: regenerate before updating ticket provider.
- Blocked ticket readiness: stop before branch, ticket status, delivery lock, or OpenSpec mutation and report missing intent.
- Missing in-progress state: stop after the branch/comment steps and report that the configured state was not found; do not guess another state.
- Existing OpenSpec change with the derived name: follow `dev-flow-propose-change` guidance for existing changes instead of overwriting.
- Existing branch comment or target state: treat as already complete and continue.
