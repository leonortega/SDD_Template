---
name: plane-start-ticket
description: Start Plane work items from chat by listing Todo tickets, preparing safe Git branches, pushing new branches to Gitea, generating OpenSpec-style planning notes, updating the Plane ticket description, and commenting with the branch. Use when the user asks to start the next Plane ticket, start a specific ticket such as E2EPROJECT-1, list Todo Plane tickets, prepare a ticket branch, or connect Plane ticket work to the local Git/OpenSpec workflow.
---

# Plane Start Ticket

## Overview

Use this skill for a chat-driven Plane workflow. The user should not need to run a command; Codex should call the configured Plane API and local Git commands from the conversation.

For setup details and branch pattern options, read `references/configuration.md` when configuration is missing or the user asks how to configure the tools. Before making Plane API calls, read `references/plane-api.md`.

## Shared Context

Before mutating Plane or Git, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md`, with `docs/architecture.md` as the stage-specific doc.

This skill owns initial creation of ignored `.codex/delivery-context.local.json` and ignored `.codex/agent-telemetry.local.jsonl` for automatic delivery. Never commit those files.

## Workflow Telemetry

Capture UTC start time before the first ticket-specific mutation. After telemetry is initialized, append one `plane-start-ticket` row with `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode AppendWorkflowTelemetry -TicketKey {ticketKey}` when ticket start succeeds, blocks, fails, or is skipped idempotently. Include `workflowStage=plane-start-ticket`, `agentRole=ticketStarter`, `startedUtc`, `finishedUtc`, `retryCount`, and `outcome`. If a blocker happens before telemetry initialization or before a ticket key is selected, report that no telemetry row was possible.

## Configuration

Read `.codex/client-tools.local.json` as the primary configuration file. Fall back to `.codex/client-tools.example.json` only for defaults and setup guidance, then apply environment variable overrides only when present. Defaults are:

- Plane API base URL: `http://agentic.lvh.me:8080`
- Plane API token field: `plane.apiToken`
- Plane workspace slug: `e2etest`
- Plane project identifier: `E2EPROJECT`
- Todo state: `Todo`
- In-progress state: `In Progress`
- Base branch: `dev`
- Branch prefix: `feat`
- Branch pattern: `{prefix}/{ticketKeySlug}-{titleSlug}`
- Max branch length: `100`

Optional environment variables override local JSON config when present: `PLANE_BASE_URL`, `PLANE_API_TOKEN`, `PLANE_WORKSPACE_SLUG`, `PLANE_PROJECT_IDENTIFIER`, `PLANE_TODO_STATE`, `PLANE_IN_PROGRESS_STATE`, `GIT_BASE_BRANCH`, `GIT_BRANCH_PREFIX`, `GIT_BRANCH_PATTERN`.

Before any mutating step, validate that `baseUrl`, `apiToken`, lowercase `workspaceSlug`, `projectIdentifier`, `baseBranch`, and `branchPattern` are present. The `branchPattern` must include `{ticketKeySlug}`.

## Stack Context Preflight

Before starting the first ticket, and before mutating any Todo ticket when stack context has not been verified, confirm the project tool set and tech stack are configured. This prevents the first OpenSpec proposal and generated ticket block from being created with generic or stale assumptions.

Required stack context:

- `docs/architecture.md`, `docs/development.md`, and `docs/deployment.md` contain `Technology Stack And Tool Set`.
- `openspec/config.yaml` contains `context:` and `rules:` with the current stack and artifact guidance.
- `.codex/tool-recommendations.example.json` exists as the tracked placeholder-safe shape/template.
- Ignored `.codex/tool-recommendations.local.json` is used only after project guidance discovery confirms local recommendations and `usedInSteps`.

Run the read-only recommendation audit before Git, Plane, or OpenSpec mutation when any of these files are missing, appear unconfigured, or this is the first ticket start in a fresh repository:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode AuditRecommendedTools
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode DiscoverProjectGuidance
```

If the audit reports any `stack-context.*` warning, if `DiscoverProjectGuidance` reports missing suggested skills or guidance that the operator has not reviewed, or if the required files are missing or placeholder-only, stop before branch creation, Plane description updates, comments, state changes, ticket-lock writes, or OpenSpec proposal creation. Route to `$configure-dev-environment` plus `project-guidance-discover` to define the stack/tooling docs, complete `openspec/config.yaml`, research extra useful guidance from detected project signals, confirm or dismiss suggestions, and update the local recommendation catalog first.

## Workflow

### No Ticket Specified

1. List Plane tickets in the configured Todo state using the Plane API with credentials from local JSON config or optional environment overrides.
2. Show ticket key, title, and state.
3. Ask the user to choose a ticket, even if there is exactly one Todo ticket.
4. Do not mutate Git or Plane while only listing tickets.

### Ticket Specified

1. Fetch the Plane ticket by key or id.
2. Run the Ticket Refinement Gate from the shared delivery contract before mutating Git, Plane state, the ticket lock, or OpenSpec:
   - Prefer `tools/SDDTemplate.DeliveryTools ClassifyTicketReadiness` when available.
   - `ready`: continue.
   - `enrichable`: generate concrete acceptance criteria, expected files/components affected, validation expectations, risks, and definition of done in the managed Plane block, then continue.
   - `blocked`: stop before branch creation, Plane state updates, comments, ticket-lock writes, or OpenSpec proposal creation. Report the missing product or technical intent.
3. Run the Stack Context Preflight. If stack/tooling docs, OpenSpec config, local project guidance catalog, or project guidance discovery review are missing or drifted, stop and route to `configure-dev-environment` and `project-guidance-discover` before mutating Git, Plane, or OpenSpec.
4. Check `git status --porcelain`. If any output exists, stop and report changed files.
5. Initialize and clear `.codex/agent-telemetry.local.jsonl` for the selected ticket with `.codex/skills/_shared/scripts/delivery_tools.ps1 -Mode InitializeWorkflowTelemetry -TicketKey {ticketKey}`. Do not initialize telemetry when only listing Todo tickets.
6. Switch to the configured base branch and run `git pull --ff-only`.
7. Create or reuse the configured branch name.
8. Pre-scan branch conflicts before creating or switching branches:
   - `git show-ref --verify refs/heads/{branchName}` for a local branch.
   - `git ls-remote --heads origin {branchName}` for a remote branch.
   If both exist and point to different commits, stop and report the conflict. If the remote branch exists and the local branch is missing, create the local branch from the remote only when it descends from the configured base branch.
9. Push the branch to Gitea with upstream tracking using `git push -u origin {branchName}`. If the upstream branch already exists and points to the same commit, treat it as complete; if the push is rejected or would require a non-fast-forward update, stop and report the branch issue.
10. Analyze the ticket description in an OpenSpec explore style unless OpenSpec is explicitly skipped by policy below.
11. Update only the managed generated block in the Plane ticket description.
12. If the fetched Plane ticket has empty or null `point`, infer and patch `point` from the generated analysis using the rubric below. If `point` or `estimate_point` already has a value, preserve it exactly and do not overwrite a human estimate.
13. Add a Plane ticket comment with the branch name, base branch, pushed Gitea branch, and OpenSpec decision, unless a generated comment for the same branch already exists.
14. Create or update `.codex/delivery-context.local.json` with `ticketKey`, `branch`, `openspecChange` when applicable, and any known PR/artifact/version fields. If an existing lock names a different ticket, fetch the locked ticket through the Plane API and compare its state with configured `plane.doneState` or default `Done`. If the locked ticket is `Done`, call `EnsureDeliveryContext` with `replaceExisting=true` for the new selected ticket. If the locked ticket is active, missing, ambiguous, or cannot be verified, stop and report the stale-lock blocker. Do not delete the lock merely because the old ticket is QA Done or ready for PROD; replacement is lazy on the next ticket start.
15. Move the Plane ticket to the configured in-progress state, unless it is already there.
16. Create an OpenSpec proposal using the `openspec-propose` skill (`/opsx:propose`) with a change name matching the branch name as closely as OpenSpec allows, unless OpenSpec is explicitly skipped.

For step 16, if the branch name contains `/`, convert it to a filesystem-safe kebab-case OpenSpec change id by replacing `/` with `-`. Example: branch `feat/e2eproject-1-create-files-and-folders-for-a-site` becomes OpenSpec change `feat-e2eproject-1-create-files-and-folders-for-a-site`. Use the Plane ticket title and generated planning block as proposal input.

Only move the ticket to the in-progress state after branch creation, Gitea push, generated description update, and branch comment all succeed or are confirmed idempotently already complete. Only create the OpenSpec proposal after the ticket is in the in-progress state.

## OpenSpec Decision

Default to creating an OpenSpec proposal for feature, bug, and hotfix tickets. Skip OpenSpec only when one of these is true:

- the ticket contains an explicit `no-openspec` marker,
- the ticket is clearly labeled or titled as `chore` or `ops-only`,
- the user explicitly requests no OpenSpec in the current chat.

When OpenSpec is skipped, write `OpenSpec: skipped ({reason})` in the generated ticket block and branch comment. Do not invoke `openspec-propose`.

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

Use this exact generated section in the Plane ticket description:

```text
---

IA generated

<!-- ia-generated:start -->

Acceptance criteria:
- ...

Expected files/components affected:
- ...

Validation command or test expectation:
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

## Estimate Points

After the generated ticket block is complete, set Plane `point` only when the current ticket `point` and `estimate_point` fields are null or empty. Never overwrite a non-empty estimate because it may be a human planning value.

Use this rubric:

- `0`: explicitly no-op, research-only, or investigation ticket with no expected code/config/doc change.
- `1`: trivial text/config-only change.
- `2`: small localized code or doc change.
- `3`: normal single-feature implementation with tests.
- `5`: multi-area implementation, API/data/UI interaction, or deployment-sensitive change.
- `7`: large or high-risk work requiring broad coordination.

Patch the work item with only the resolved `point` value and any other fields required by Plane for a valid partial update. Current Plane work-item responses may include `estimate_point`, but the accepted mutable field for this workflow is `point`. If Plane rejects the estimate patch after the generated description update succeeds, report the estimate update as blocked and continue only when no later workflow rule requires the estimate field.

## Plane Access

Use the Plane API only. Never use Plane MCP, Docker containers, or direct database access for Plane.

Load credentials from `.codex/client-tools.local.json` or optional environment overrides only. Use `plane.apiToken` as the API key value and send it with the `X-API-Key` header. Avoid echoing request headers, tokens, or full credential-bearing URLs.

Use Plane's current `work-items` endpoints, not deprecated `issues` endpoints. Workspace slugs are case-sensitive in API paths; use the lowercase slug from the Plane URL. If only `projectIdentifier` is configured, resolve it through `GET /api/v1/workspaces/{workspace_slug}/projects/` and use the returned project UUID for project-scoped `work-items` calls.

To move a ticket to the in-progress state, resolve the project states through the Plane API, find the state whose name equals configured `plane.inProgressState`, and update the work item's state by id. Do not guess a state id.

Use `IA generated branch: {branchName}` as the stable branch comment marker. If existing comments contain the same marker, do not add another branch comment.

## Output

Report the selected ticket, branch, OpenSpec change or explicit no-OpenSpec rationale, ticket lock path, telemetry initialization, validation performed, Plane comment marker, and handoff to `implement-ticket`.

## Failure Rules

- Dirty working tree: stop before branch creation or Plane mutation.
- Missing Plane API config: explain the missing setup and reference `references/configuration.md`.
- Invalid or empty title slug: fall back to a ticket-key-only branch segment.
- Existing branch: switch to it instead of creating a duplicate.
- Failed fast-forward pull: stop and report the branch issue.
- Local/remote branch conflict: stop before Plane mutation and report both refs.
- Failed Gitea branch push: stop before Plane mutation and report the push failure.
- Malformed generated markers: stop before updating the ticket.
- Weak generated analysis: regenerate before updating Plane.
- Blocked ticket readiness: stop before branch, Plane state, delivery lock, or OpenSpec mutation and report missing intent.
- Missing in-progress state: stop after the branch/comment steps and report that the configured state was not found; do not guess another state.
- Existing OpenSpec change with the derived name: follow `openspec-propose` guidance for existing changes instead of overwriting.
- Existing branch comment or target state: treat as already complete and continue.
