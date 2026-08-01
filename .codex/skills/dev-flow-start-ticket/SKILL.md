---
name: dev-flow-start-ticket
license: MIT
description: Start configured work items from chat by listing Specified tickets (feature starting point), preparing safe repository branches, pushing new branches, generating OpenSpec-style planning notes, updating the ticket description, and commenting with the branch through selected project-profile adapters. Bug tickets (status: New) are automatically re-routed to the dedicated bug fix lifecycle (dev-flow-file-qa-bug). Use when the user asks to start the next feature ticket, start a specific ticket key, list Specified tickets, prepare a ticket branch, or connect ticket work to the local repository/OpenSpec workflow.
---

<!-- TIER 3: STAGE-SPECIFIC - Ticket start workflow skill -->

# Start Ticket

## Overview

Use this skill for a chat-driven ticket workflow. The user should not need to run a command; Codex should call the selected ticket adapter and local Git commands from the conversation.

### Bug Routing

When the user asks to start a ticket or a ticket is fetched that is a **bug** (status is `New`, ID 1), this skill **does not** continue with the normal feature flow. Instead, it routes to `dev-flow-file-qa-bug` which handles the full bug fix lifecycle:

```text
E2E QA fails → File bug → Move to Specified → Update parent OpenSpec → Commit → Move to In progress → Branch → PR → Merge & deploy to QA → Close bug → Return to parent QA
```

**How routing works:**
1. The ticket is fetched and its status is checked
2. If status is `New` (ID 1) → route to `dev-flow-file-qa-bug`
3. After the bug flow completes, the parent ticket continues its normal QA flow
4. If status is `Specified` or any other state → continue with the normal feature flow below

For setup details and branch pattern options, read `references/configuration.md` when configuration is missing or the user asks how to configure the tools. Before making ticket-provider calls, read `.codex/project-profile.json` and the selected ticket adapter path; read provider-specific references only when that adapter requires them.

## Shared Context

Before mutating ticket or repository state, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/delivery-contract.md`, and `docs/conventions/context-management.md`, with `docs/architecture/system.md` as the stage-specific doc. Load selected ticket and repository adapters before any mutation.

This skill owns initial creation of ignored `.codex/delivery-context.local.json` for automatic delivery. OpenProject time entries are the only telemetry store. Never commit local workflow files.

## Workflow Telemetry

### ⚠️ HARD GATE: Time entries are mandatory

OpenProject time entries are the PRIMARY telemetry store. You MUST:

1. **Capture UTC start time** before the first ticket-specific mutation.
2. **Create the time entry** via `time-telemetry-upsert` (POST `/api/v3/time_entries`). See `.codex/skills/openproject-sprint-backlog/references/openproject-api.md` → Operations → `time-telemetry-upsert` for the exact API payload with `spentOn`, `hours`, `comment`, `_links.user`, `_links.entity`, `_links.project`, and `_links.activity`.
3. **Use marker** `IA generated workflow telemetry: {ticketKey}:dev-flow-start-ticket`.
4. **Resolve activity** by running:
   ```bash
   python -m tools.sdd_cli dev-flow resolve-openproject-activity --workflow-stage dev-flow-start-ticket --input-json '{"timeTelemetry":{...}}'
   ```
   Then reverse-lookup the activity ID from the resolved name against the mapping in the adapter doc.

**Do NOT skip this step.** If `time-telemetry-upsert` fails (returns a 4xx or 5xx error), stop and report the failure. Do not use any fallback mechanism.

For shared API helpers including time-entry POST payload format and activity reverse-lookup, see `.codex/skills/_shared/api-helpers.md` → OpenProject → Workflow time telemetry.

## Configuration

Read `.codex/project-profile.json` first for the selected ticket provider, ticket key pattern, branch policy, and adapter path. Read `.codex/client-tools.local.json` only for selected adapter runtime values. Fall back to `.codex/client-tools.example.json` only for defaults and setup guidance, then apply provider-supported environment variable overrides only when present. Defaults are:

- Feature starting state: `Specified` (feature tickets start here — see `delivery-contract-ticket.md`)
- In-progress state: `In progress` (lowercase p — matches OpenProject status ID 7)
- Base branch, branch prefix, branch pattern, ticket key pattern, and maximum branch length from `.codex/project-profile.json` or the selected repository adapter.

Before any mutating step, validate that the selected ticket adapter has the runtime values it requires, that the configured base branch exists, and that the branch pattern includes `{ticketKeySlug}`.

## Stack Context Preflight

Before starting the first ticket, and before mutating any feature ticket when stack context has not been verified, confirm the project tool set and tech stack are configured. This prevents the first OpenSpec proposal and generated ticket block from being created with generic or stale assumptions.

Required stack context:

- `docs/architecture/system.md`, `docs/conventions/development.md`, and `docs/architecture/deployment.md` contain `Technology Stack And Tool Set`.
- `openspec/config.yaml` contains `context:` and `rules:` with the current stack and artifact guidance.
- Ignored `.codex/tool-recommendations.local.json` is used only after project guidance discovery confirms local recommendations and `usedInSteps`.

Run the read-only recommendation audit before Git, ticket provider, or OpenSpec mutation when any of these files are missing, appear unconfigured, or this is the first ticket start in a fresh repository:

```bash
python -m tools.sdd_cli guidance discover
```

If the audit reports any `stack-context.*` warning, if `DiscoverProjectGuidance` reports missing suggested skills or guidance that the operator has not reviewed, or if the required files are missing or placeholder-only, stop before branch creation, OpenProject description updates, comments, state changes, ticket-lock writes, or OpenSpec proposal creation. Route to `$configure-dev-environment` plus `project-guidance-discover` to define the stack/tooling docs, complete `openspec/config.yaml`, research extra useful guidance from detected project signals, confirm or dismiss suggestions, and update the local recommendation catalog first.

After the user confirms or dismisses suggestions, persist the state with:

```bash
python -m tools.sdd_cli guidance set-recommended-tools --accepted '["id1","id2"]' --dismissed '["id3"]'
```

Before creating the OpenSpec proposal (step 16), verify that the `openspec` CLI is available and initialize the project:    ```bash
    which openspec || where openspec || echo "openspec CLI not found — install via: npm install -g @fission-ai/openspec@latest"
    openspec init --tools codex
    openspec update
    ```

    If the CLI is missing, attempt auto-installation: `npm install -g @fission-ai/openspec@latest`, then run `openspec init --tools codex && openspec update`.

### Knowledge Consult

Before creating the OpenSpec proposal (step 16) and before mutating ticket or repository state, consult the knowledge base for known errors, patterns, and lessons related to the ticket topic:

```bash
python -m tools.sdd_cli knowledge-search search --query <ticket topic terms>
python -m tools.sdd_cli knowledge-search search --list-topics
```

Fold relevant entries into the proposal context and risk analysis. Record `Knowledge consulted: <files>` in the handoff.

## Workflow

### No Ticket Specified

1. List tickets in the feature starting state (`Specified`) using the selected ticket adapter with credentials from local JSON config or optional environment overrides.
2. Show ticket key, title, and state.
3. Ask the user to choose a ticket, even if there is exactly one ticket.
4. Do not mutate Git or ticket provider while only listing tickets.

### Ticket Specified

1. Fetch the ticket by key or id.

2. **Check if the ticket is a bug.** If the ticket's status is `New` (ID 1, the bug starting state — see `delivery-contract-ticket.md`), route to the dedicated bug fix lifecycle:
   - Load `dev-flow-file-qa-bug` and follow its full Workflow section
   - This skill does NOT create a branch, OpenSpec proposal, or feature-scoped planning for bugs
   - After the bug flow completes (Phase 7: Close Bug & Return To Parent QA), the parent ticket `{parentTicketKey}` resumes its QA flow
   - **Do not continue** with the normal feature steps below — the bug flow handles everything

3. Run the Ticket Refinement Gate from the shared delivery contract before mutating Git, ticket status, the ticket lock, or OpenSpec:
   - Prefer repo-local readiness helpers when available.
   - `ready`: continue.
   - `refinable`: use grill-style refinement before writing the managed ticket provider block. Prefer `grill-with-docs` style when answers create durable product, domain, acceptance, or rationale knowledge; use `grill-me` style only for temporary alignment. Generate Scrum-ready planning details with a problem or opportunity, user story, concrete acceptance criteria, scope or affected areas, dependencies or assumptions, validation expectations, risks, and definition of done in the managed ticket provider block, then continue.
   - `blocked`: stop before branch creation, ticket status updates, comments, ticket-lock writes, or OpenSpec proposal creation. Report the missing product or technical intent.

4. Run the Stack Context Preflight. If stack/tooling docs, OpenSpec config, local project guidance catalog, or project guidance discovery review are missing or drifted, stop and route to `configure-dev-environment` and `project-guidance-discover` before mutating Git, ticket provider, or OpenSpec.

4.5. **Initialize trunk.io after tech stack is confirmed.** The lefthook pre-commit hook runs `npx trunk fmt` and `npx trunk check --all --ci --no-fix` on every commit. If trunk hasn't been initialized, these hooks fail and block the first commit. After the tech stack is confirmed, initialize trunk:

    ```bash
    # Initialize trunk if not already done
    if [ ! -f .trunk/trunk.yaml ]; then
      echo "Initializing trunk.io..."
      npx trunk init 2>&1 || echo "trunk init skipped — will auto-init on first trunk fmt run"
    fi
    ```

    Verify trunk is initialized by checking `.trunk/trunk.yaml` exists after the command. If trunk is not available (`npx trunk` not found), report it as a non-blocking warning: "Trunk.io not initialized — first commit may fail if trunk-fmt or trunk-check hooks run." The user can fix it later with `npx trunk init`.

5. Check `git status --porcelain`. If any output exists, stop and report changed files.

6. Log a time entry for the selected ticket via `time-telemetry-upsert` (POST `/api/v3/time_entries`). See Workflow Telemetry section above for the exact payload format. Do not initialize telemetry when only listing tickets.

7. Switch to the configured base branch and run `git pull --ff-only`.

8. Create or reuse the configured branch name.

9. Derive the repository remote name from `git remote` output (e.g., `origin` or `gitea`). Pre-scan branch conflicts before creating or switching branches:
   - `git show-ref --verify refs/heads/{branchName}` for a local branch.
   - `git ls-remote --heads {remoteName} {branchName}` for a remote branch.
     If both exist and point to different commits, stop and report the conflict. If the remote branch exists and the local branch is missing, create the local branch from the remote only when it descends from the configured base branch.

10. Push the branch to repository/review provider with upstream tracking using `git push -u {remoteName} {branchName}` (where `{remoteName}` is the detected remote from step 9). If the upstream branch already exists and points to the same commit, treat it as complete; if the push is rejected or would require a non-fast-forward update, stop and report the branch issue.

11. **Feed human ticket text to dev-flow-explore-change skill.** Load `.codex/skills/dev-flow-explore-change/SKILL.md`. Feed it the human-authored ticket description (fetched in step 1). It produces an exploratory analysis with structure, gaps, risks, and insights.

12. **Run iterative grill-with-docs cycles on the human ticket text (up to 4 cycles).**

    a. **Cycle 1:** grill-with-docs interviews the user on unclear aspects, generating questions about gaps, ambiguities, and missing context.
    b. **IA answers each question** with the best possible answer based on available context.
    c. **Cycle 2-4:** Repeat — each cycle, grill-with-docs generates new questions based on the previous answers. The IA answers again.
    d. **Stop when** either 4 cycles are reached or grill-with-docs has no more questions.
    e. **Combine all grilled answers** from every cycle into one consolidated grill-with-docs output (refined/clarified requirements with domain knowledge).

    Uses `/grilling` + `/domain-modeling` under the hood. Output: a single comprehensive refined-requirements document built from all cycles.

13. **Curate both outputs into one agile-format IA block.** Take output from step 11 (dev-flow-explore-change analysis) + output from step 12 (grill-with-docs refined requirements). The IA curates, merges, and improves both into a single cohesive agile-format block with all sections below. **Critically, extract every "will not implement" decision from grill-with-docs cycles and consolidate them into the "Out of scope" section** — do not leave these decisions scattered in different comments or omitted entirely.

    Full agile-format sections:
    - Problem / opportunity
    - User story (As a... I want... So that...)
    - Concrete acceptance criteria
    - Scope / affected areas
    - **Out of scope** — every decision from grill cycles that will NOT be implemented in this ticket (e.g. "Registration: out of scope for MVP", "Analytics: not included", "Rate limiting: deferred to future ticket"). This prevents scattered comments and makes scope boundaries explicit.
    - Dependencies / assumptions
    - Validation expectations
    - Risks
    - Definition of done

    Then **PATCH** the ticket description with the enrich pattern:
    - **Fetch** current description + `lockVersion` via the ticket adapter.
    - **Append** the curated IA block (separator `---` + `IA generated` header + markers) AFTER the original human-authored description.
    - Preserve all text outside `<!-- ia-generated:start -->` and `<!-- ia-generated:end -->` markers exactly.
    - On subsequent runs, replace only the content between the markers.
    - Include current `lockVersion` in the PATCH payload.

14. Add a ticket comment with the branch name, base branch, pushed repository branch, and OpenSpec decision, unless a generated comment for the same branch already exists.

14. Create or update `.codex/delivery-context.local.json` with `ticketKey`, `branch`, `openspecChange` when applicable, and any known PR/artifact/version fields. If an existing lock names a different ticket, fetch the locked ticket through the OpenProject API when OpenProject is selected, otherwise through the selected ticket adapter, and compare its status with the configured `openProject.doneStatus` or default `Done`. If the locked ticket is `Done`, call `EnsureDeliveryContext` with `replaceExisting=true` for the new selected ticket. If the locked ticket is active, missing, ambiguous, or cannot be verified, stop and report the stale-lock blocker. Do not delete the lock merely because the old ticket is QA Done or ready for PROD; replacement is lazy on the next ticket start.

15. Move the ticket to the configured in-progress status, unless it is already there.

16. **Run the OpenSpec propose flow.** Load the `dev-flow-propose-change` skill and follow its Workflow section to propose the change and generate all planning artifacts in one flow:

    a. **Scaffold the change** if not already created:
       ```bash
       openspec new change "<change-name>"
       ```
       Use the branch name converted to kebab-case: replace `/` with `-`. Example: branch `feat/e2eproject-1-files` becomes `feat-e2eproject-1-files`.

    b. **Generate all planning artifacts in one propose flow.** Use the ticket context, project context from `openspec/config.yaml`, and the `spec-driven` schema rules to create ALL artifacts:
       - `proposal.md` — what & why
       - `specs/**/*.md` — behavior specs
       - `design.md` — how
       - `tasks.md` — implementation steps with Review Workload Forecast

       Apply the OpenSpec `/opsx:propose` pattern: the AI reads the schema context and rules from `openspec/config.yaml`, reads the ticket description and generated planning block as input, and creates all artifacts in dependency order in a single coherent pass. Do NOT iterate manually with `openspec instructions` — the AI generates each artifact based on the schema template and project context.

    c. **Verify all artifacts were created:**
       ```bash
       openspec status --change "<change-name>"
       ```
       Confirm that `proposal.md`, `design.md`, `specs/`, and `tasks.md` all show as complete (`[x]`).

17. **Parse workload forecast and set estimated time on the work package:**

    a. **Parse the forecast:**
       ```bash
       python -m tools.sdd_cli dev-flow parse-workload-forecast --tasks-path openspec/changes/<change-name>/tasks.md --openspec-change <change-name>
       ```
       Extract `estimatedTotalHours` from the result.

    b. **Set estimatedTime on the work package** via the ticket adapter's `set-estimated-time` operation (see `.codex/skills/openproject-sprint-backlog/references/openproject-api.md` → Operations → `set-estimated-time`). Convert hours to ISO-8601 duration (e.g. `5` → `PT5H`, `2.5` → `PT2H30M`). Fetch current `lockVersion` first.

    c. **Log a time entry for the start-ticket stage** via `time-telemetry-upsert` if not already logged (see Workflow Telemetry section above).

Only move the ticket to the in-progress status after branch creation, repository/review provider push, generated description update (steps 11-13), and branch comment (step 14) all succeed or are confirmed idempotently already complete. Only create the OpenSpec proposal (step 16) after the ticket is in the in-progress status.

## OpenSpec Decision

Default to creating an OpenSpec proposal for feature and hotfix tickets. Bug OpenSpec handling is delegated to `dev-flow-file-qa-bug` (Phase 3: Update Parent OpenSpec With Bug Tasks) — bugs append tasks to the **parent's** existing OpenSpec change and do NOT create a new one.

Skip OpenSpec only when one of these is true:

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

### ⚠️ CRITICAL: Append — Never Replace

The IA generated block MUST be APPENDED after the original human-written description, never replacing it. The PATCH payload sent to the ticket provider MUST contain the FULL description (original human text + separator + IA generated block).

### On First Creation (no markers exist yet)

When this is the first time writing to the ticket description:

1. **Fetch** the current description from the ticket provider (this is the human-authored original).
2. **Append** the separator, `IA generated` header, markers, and generated content AFTER the original text.
3. **PATCH** with the full reconstructed description:

```text
[Human-authored original description — preserved exactly as-is]

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

### On Subsequent Updates (markers exist)

On rerun:

1. **Fetch** the current description from the ticket provider.
2. **Keep everything before** `<!-- ia-generated:start -->` unchanged (this includes the original human text).
3. **Replace only** the content between `<!-- ia-generated:start -->` and `<!-- ia-generated:end -->`.
4. **PATCH** with the full description, preserving the human-authored portion outside the markers.

If only one marker exists (`<!-- ia-generated:start -->` without a matching `<!-- ia-generated:end -->`, or vice versa), stop and ask for manual cleanup.

### Generated Block Format Reference

This is the block that gets appended after the original human text (shown here in isolation):

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

### Acceptance Criteria Quality

Acceptance criteria must be concrete and testable. Reject and regenerate criteria containing generic wording such as `works correctly`, `as expected`, or `properly implemented`. Every acceptance criterion will drive a vertical TDD cycle during implementation: one behavior-focused test through a public interface, RED confirmation, minimal code, GREEN confirmation. Criteria must be verifiable through committed automated test coverage — not manual checks deferred to QA.

Concrete examples:

- `GET /health returns HTTP 200 with JSON field status equal to ok.`
- `Submitting an empty contact form shows required-field validation without creating a record.`
- `The home page renders the configured site title on desktop and mobile widths.`
- `Unauthorized API requests return HTTP 401 and do not expose stack traces or secrets.`

## Ticket Provider Access

Use OpenProject API v3 `work_packages` endpoints when the selected ticket adapter is OpenProject.

Use the selected ticket adapter only. Never use MCPs, Docker containers, or direct database access for ticket delivery unless the selected adapter explicitly requires it.

Load credentials from `.codex/client-tools.local.json` or optional environment overrides only. Avoid echoing request headers, tokens, or full credential-bearing URLs.

Use provider-neutral operations (`list`, `read`, `enrich`, `move-state`, `comment`, and `verify-marker`). The selected ticket adapter translates those operations to concrete endpoints, payload fields, lock/version mechanics, and state names.
Fetch the current `lockVersion` before OpenProject description or status updates.

To move a ticket to the in-progress status, resolve the configured target state through the selected ticket adapter. Do not guess a state id or provider-specific lock/version value.

Use `IA generated branch: {branchName}` as the stable branch comment marker. If existing comments contain the same marker, do not add another branch comment.

## Output

Report the selected ticket, branch, OpenSpec change or explicit no-OpenSpec rationale, ticket lock path, telemetry initialization, validation performed, ticket comment marker, and handoff to `dev-flow-implement-ticket`.

If the ticket was a bug (status: New) and was re-routed to `dev-flow-file-qa-bug`, report the bug ticket, parent ticket, and the full bug flow output (see `dev-flow-file-qa-bug` → Output section).

## Failure Rules

- Bug routing failure: if the ticket is a bug (status: New) but `dev-flow-file-qa-bug` cannot be loaded or followed, stop and report the routing failure — do not apply the feature flow to a bug.
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
