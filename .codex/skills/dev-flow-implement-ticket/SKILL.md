---
name: dev-flow-implement-ticket
license: MIT
description: Implement an already-started configured ticket through OpenSpec tasks, project-profile quality gates, repository/review adapter handoff, review-agent fixes, and ticket adapter review-state update. Use when a ticket already has an implementation branch and OpenSpec change, or when Codex is asked to continue, finish, validate, or hand off ticket implementation work.
---

<!-- TIER 3: STAGE-SPECIFIC - Ticket implementation skill -->

# Implement Ticket

## Overview

Use this skill after `dev-flow-start-ticket` has created or reused the implementation branch, moved the ticket to progress, and created the OpenSpec change. This skill owns implementation through PR handoff. It does not select Todo tickets, create initial branches, or archive OpenSpec changes.

## Shared Context

Before implementation, handoff, or review work, follow `.codex/skills/_shared/skill-startup.md` with `docs/conventions/development.md` as the stage-specific doc. Read `.codex/project-profile.json`, then load the selected ticket, repository/review, stack, and E2E adapters only when the current step needs them.

## Workflow Telemetry

See `.codex/skills/_shared/pipeline-workflow-telemetry.md` for the common workflow telemetry pattern. Use:

- `{workflowStage}` = `dev-flow-implement-ticket`
- `{agentRole}` = `implementation`

## Configuration

Read `.codex/project-profile.json` first for stack, provider, branch, ticket-key, and quality-gate policy. Read `.codex/client-tools.local.json` only for selected adapter runtime values. Fall back to `.codex/client-tools.common.json` only for defaults and setup guidance.

Read coverage config from `.codex/quality.local.json` when present. If it is missing, invalid, or missing `coverage.minimumPercent`, use `80` and report the configuration gap. The safe tracked template is `.codex/quality.example.json`.

Required/defaulted values:

- `selected ticket adapter runtime values`
- `configured developed state`: target state after PR creation. Default: `Developed` (OpenProject ID 8).
- `git.baseBranch`
- `selected repository/review adapter runtime values`
- `pr.reviewers`
- `pr.labels.reviewed`, `pr.labels.needsTests`, `pr.labels.needsChanges`
- `coverage.minimumPercent`, default `80`

## Workflow

### 1. Resolve Context

1. Identify the ticket, current branch, and OpenSpec change from user input, branch name, or existing OpenSpec changes.
2. Read `.codex/delivery-context.local.json` when present and verify the resolved ticket, current branch, OpenSpec change, existing PR, and any artifact commit match the locked `ticketKey`. If they resolve to another ticket, stop and report the mismatch.
3. Stop if the branch or OpenSpec change is missing; tell the user to run the `dev-flow-start-ticket` flow first.
4. Check `git status --porcelain`. If unrelated changes exist, stop before implementation and list the changed files.

4.5. **Pre-Flight Gate: Verify OpenSpec and time entries exist.** Before any analysis or implementation work, verify the following. If any check fails, stop and route back to `dev-flow-start-ticket`:

    a. **OpenSpec artifacts are complete:**
       Check that the required artifact files exist:
       - `openspec/changes/<change-name>/tasks.md`
       - `openspec/changes/<change-name>/design.md`
       - `openspec/changes/<change-name>/proposal.md`
       - `openspec/changes/<change-name>/specs/`
       If any are missing, stop and report: "OpenSpec change `<change-name>` is incomplete. Run the full propose flow first."

    b. **Work package has estimatedTime set:**
       ```bash
       curl -s -H "Authorization: Bearer <token>" "<openproject-url>/api/v3/work_packages/<id>" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('estimatedTime'))"
       ```
       If `estimatedTime` is null or empty, stop and report: "Work package has no estimated time. Complete step 17 of dev-flow-start-ticket first."

    c. **Time entry exists for dev-flow-start-ticket:**
       ```bash
       python -c "
import json, urllib.request
filters = json.dumps([{'work_package': {'operator': '=', 'values': ['<wpId>']}}])
url = f'<openproject-url>/api/v3/time_entries?filters={{\"filters\": {filters}}}'
# Use urllib with auth header
req = urllib.request.Request(url)
req.add_header('Authorization', 'Bearer <token>')
resp = urllib.request.urlopen(req)
d = json.loads(resp.read())
print(len(d.get('_embedded', {}).get('elements', [])))
"
       ```
       Replace `<wpId>` with the work package ID and `<token>` with the API token from `.codex/client-tools.local.json`.
       If no time entries exist, log one via `time-telemetry-upsert` (see Workflow Telemetry section) before proceeding. If logging fails, stop and report: "Cannot start implementation without time entries for dev-flow-start-ticket."

    **This is a hard gate (authority level 5).** Do not skip these checks even on resume. A previous agent may have skipped them.

   a. **Read stack configuration:**
   - Stack lives **only** in `.codex/project-profile.local.json` (the ignored local overlay). Read `.codex/project-profile.local.json` → `stack` section for frontend/backend/database values. If it does not exist, stack is empty.
   - Read `.codex/project-profile.json` for **non-stack** config: providers, workflow, quality gates, adapters.
   - Use the merged result from `load_project_profile()` (in `_shared.py`) when available, which overlays local.json on top of profile.json.
   - Read `.codex/tool-recommendations.local.json` → `detectedTags`, `researchTopics`, `accepted` recommendations.

   b. **Map stack to applicable skills:**

   | Detected / Declared Technology        | Skills to Activate                                                                                                                                 |
   | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
   | **React** + TypeScript                | React component patterns, TypeScript typing, `@testing-library/react` for component tests, Vite for build, `impeccable` (design system, tokens, UI craft) |
   | **TypeScript** (any)                  | TypeScript `tsconfig.json` configuration, type-safe patterns                                                                                       |
   | **C# / ASP.NET Core**                 | Controller-service-repository layers, Entity Framework guidance                                                                                    |
   | **Python / FastAPI / Flask / Django** | FastAPI/Flask/Django patterns, pytest for testing                                                                                                  |
   | **SQLite / PostgreSQL / MongoDB**     | ORM/schema guidance, migration patterns                                                                                                            |
   | **Any web frontend**                  | `playwright` (E2E browser tests), `playwright-interactive` (debugging), `impeccable` (frontend design: UI polish, audit, critique, a11y, responsive)  |
   | **Any implementation**                | `tdd` (test-first cycles), `ponytail` (minimal code, standard library), `security-best-practices`, `clean-architecture` (Dependency Rule, layer separation), `clean-code` (naming, function size, error handling), `solid` (SOLID principles)                                                  |
   | **Gitea** (repo/review provider)      | `dev-flow-pr-review-agent` (PR review automation)                                                                                                  |
   | **Any task (generic)**                | **Scan all `.codex/skills/` directories.** Every installed skill must be assessed for relevance, not just stack-mapped ones. See sub-step f below. |

   c. **Load and declare each skill:**
   - Try loading each identified `SKILL.md` via the `skill` tool first. If the `skill` tool reports "no skills available" or is unavailable, read the SKILL.md file directly from `.codex/skills/<name>/SKILL.md` and apply its rules manually.
   - Declare all active skills at the start of every response body:
     ```markdown
     Skills used: caveman (auto, full), ponytail (auto, full),
     tdd (on-demand), playwright (on-demand),
     <tech-stack-skills> (on-demand)
     ```
   - If a skill recommendation is listed in `accepted` but not yet installed in `.codex/skills/`, report it as a gap and route to `project-guidance-acquire`. If the stack is empty (`applies: false` for all domains) but the ticket implies a product, suggest running `python -m tools.sdd_cli guidance discover` to auto-detect the stack from repo signals, or configure via `set-project-stack`.

   d. **Apply architecture patterns based on stack:**
   - **React frontend:** Component-per-file, custom hooks for logic, service modules for API calls, TypeScript types in a `types/` directory.
   - **ASP.NET backend:** Controller → Service → Repository layering with dependency injection.
   - **Python backend:** Route → Service → Repository or similar separation of concerns.
   - **Clean Architecture:** Separate domain, application, infrastructure, and presentation layers — but only add layers the implementation actually needs (ponytail principle: no speculative abstractions).

   e. **Stop and report when:**
   - Required skills are missing from `.codex/skills/` — route to `project-guidance-acquire`.
   - Stack implies a framework but relevant test frameworks are not configured in the recommendations.

   f. **Scan all installed skills for relevance:** Beyond the stack-mapped skills above, enumerate every skill directory under `.codex/skills/` that has a `SKILL.md` and assess it:

   - Read the skill's `SKILL.md` (or `metadata.json` → `description` when available) to determine what domain, language, or pattern it covers.
   - Classify each skill:
     - **active** — its rules, patterns, or constraints apply to the current implementation task.
     - **skipped** — it does not apply (document the specific reason).
   - Include all skills — both active and skipped — in the `Skills used:` declaration block.
   - **Skipped skills must include a rationale.** A bare list of skipped names is insufficient. Examples:

     ```markdown
     Skills used:

     - caveman (auto, full)
     - ponytail (auto, full)
     - vercel-react-best-practices (on-demand): React performance patterns
     - clean-code (on-demand): naming, function size, error handling
     - solid-principles (on-demand): component interface design
     - modern-csharp-coding-standards (skipped — C# only, not a C# project)
     - vercel-react-view-transitions (skipped — no route animations in scope)
     - clean-architecture (skipped — overkill for a 6-component SPA landing page)
     ```

   - If assessing a skill's applicability requires understanding its full rules, load it via `skill('<name>')` (or read its `SKILL.md` directly) before deciding.
   - **Failure to scan:** If a skill is installed in `.codex/skills/` but the agent does not list it in the declaration, it is a process violation (authority level 5). The implementation must stop and the agent must redo the scan.

6. Detect resume checkpoints before doing new work:
   - completed and pending OpenSpec tasks,
   - existing implementation commits on the branch,
   - upstream branch and push status,
   - existing open PR for the branch,
   - latest review-agent marker and stable AI finding ids for the current head SHA,
   - existing OpenSpec `## PR Review Feedback` tasks,
   - human-authored top-level PR comments and inline code review comments,
   - latest ticket provider `IA generated PR feedback detected: {headSha}:{feedbackBatchId}` markers,
   - latest ticket provider `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}` markers,
   - current `needs-tests` and `needs-changes` labels,
   - latest repository workflow status.
     Continue from the latest completed checkpoint instead of restarting earlier steps.
7. Confirm the OpenSpec change is active by checking that `openspec/changes/<change>/tasks.md` exists.
8. Load context files for implementation by reading the change artifacts directly:
   - `openspec/changes/<change>/proposal.md` — what & why
   - `openspec/changes/<change>/specs/*.md` — behavior specs
   - `openspec/changes/<change>/design.md` — how
   - `openspec/changes/<change>/tasks.md` — implementation steps
9. Follow the `/opsx:apply` pattern: read `tasks.md`, identify incomplete tasks, and implement them one by one using TDD cycles.
10. Classify delivery risk from ticket text, OpenSpec artifacts, changed/planned paths, and estimated changed lines using the shared delivery contract. Prefer repo-local helpers when available. Record `low`, `standard`, or `high` in the PR body and ticket handoff.

### 2. Discover Quality Gates

Inspect configured quality surfaces. Do not invent validation commands.

- `.codex/quality.local.json`, falling back to coverage threshold `80`
- `.codex/quality.common.json`, for the tracked default
- configured PR validation workflow files
- configured workflow documentation
- `lefthook.yml`

Treat repository workflow PR validation as the authoritative quality gate. Treat local hooks as automatic protections that run through normal Git operations.

**❌ HARD GATE (authority level 5): Coverage must be verified locally before PR creation.** The coverage threshold from `.codex/quality.local.json` (`coverage.minimumPercent`, default `80`) is a hard gate — implementation cannot proceed to PR handoff unless coverage meets or exceeds the threshold.

**❌ HARD GATE (authority level 5): Lefthook pre-push stack tests must pass before pushing.** The `lefthook.yml` `pre-push` hook runs `python -m tools.sdd_cli stack-tests`, which runs the product test suite — unit, integration, and architecture levels per `.codex/skills/_shared/test-requirements.md` — driven by `stack.testFrameworks` from `.codex/project-profile.local.json`. This gate runs on the dev machine (stack runtimes live locally; the CI image stays lean) and applies on every `git push`:

- **Stack configured:** the hook installs dependencies, runs the test command for each mapped framework (pytest for Python, vitest/jest for JS/TS, `dotnet test` for .NET — pytest is Python-only and never used for .NET), then runs the **coverage gate** with the configurable threshold `coverage.minimumPercent` from `.codex/quality.local.json` (fallback `.codex/quality.example.json`, default `80`). A failing test or coverage-below-threshold step fails the push. A framework with tests but no mapped coverage command reports a gap step (non-blocking) — CI remains the authoritative coverage gate for that framework.
  - **.NET stacks:** the coverage gate runs `dotnet test /p:CollectCoverage=true /p:Threshold={n}` and therefore requires `coverlet.msbuild` referenced in the test project. Without it, `dotnet test` silently ignores those properties and exits 0 — a false pass. `dev-flow-scaffold-project` must add `coverlet.msbuild` to .NET test projects; verify it is present before relying on the .NET coverage gate.
- **No stack configured (template state):** the hook skips cleanly and exits 0 — no tests to run.
- **Never bypass with `--no-verify`** unless the user explicitly requests it in the current chat. If a push is blocked by failing stack tests, fix the tests before pushing (same treatment as the coverage gate). The CI image intentionally does not contain stack runtimes, so this local hook is the only product-test gate — CI covers repo tooling tests and scans only.

Discover a local coverage command:

1. Prefer the command used by configured PR validation workflow files.
2. Then prefer commands documented in configured workflow documentation, `lefthook.yml`, project README files, or package/build manifests.
3. If exactly one stack-native coverage command is obvious, use it as a local fallback only when no repo-specific command overrides it.
4. If no unambiguous local coverage command exists, report that CI remains the only coverage source.

**If a local coverage command exists:** Run it before PR creation. If coverage is below `coverage.minimumPercent`, stop — do not create the PR. Add or update OpenSpec tasks for missing coverage, write the missing tests, and re-run coverage until the threshold is met.

**If no local coverage command exists:** The PR validation workflow is the coverage gate. Report the coverage gap in the PR body and ticket handoff. If the PR validation workflow fails on coverage, treat it as an implementation failure per Section 5.

When repository workflow runner, workflow container, or security tool compatibility is part of the configured gate, use the existing infra validation path instead of inventing ad hoc checks:

```bash
python -m tools.sdd_cli dev-flow audit-skill-contracts
the selected runner validation helper from `configure-dev-environment`
```

Use the selected runner validation helper whenever repository workflow fails before repository validation commands run, or logs show image pull failures, missing runtime tools, checkout networking failures, missing scanners, missing shell tools, or job-container tool incompatibility.

### 2.5 Knowledge Consult

Before starting the TDD cycle, consult the knowledge base for known errors, patterns, anti-patterns, and lessons relevant to the change's area:

```bash
python -m tools.sdd_cli knowledge-search search --query <feature or module terms>
python -m tools.sdd_cli knowledge-search search --list-topics
```

Fold relevant entries into the implementation approach and risk analysis. Record `Knowledge consulted: <files>` or `Knowledge consulted: none` in the PR body and ticket handoff comment. If the consult surfaces a reusable lesson the change depends on, capture it via `knowledge/README.md` and the `docs-knowledge-maintenance` skill during the Context Findings Review.

### 3. Implement — Tests First, Then Code

See `.codex/skills/_shared/pipeline-tdd-cycle.md` for the common TDD test-first pattern. The following are feature-flow-specific additions:

- **AC source:** the **IA curated block** in the ticket description (from enrich steps 10-12 in `dev-flow-start-ticket`). This contains the acceptance criteria, scope, out of scope, dependencies, and risks. The **IA curated block is the source of truth** for what to build.
- **Task source:** `openspec/changes/<change>/tasks.md`
- **Before coding, activate skills from step 5a-f scan.** The declared skills in the `Skills used:` block are NOT decorative — they must be actively applied during every TDD cycle.
- **Before any service interaction, check MCP routing** per `.codex/mcp-instructions.md`: service MCPs (gitea, openproject, grafana, kubernetes). Repository content search uses built-in file/search tools.
- **Create `src/` and `test/` folder structure** before writing any product code. Always **ask the user** to confirm the scaffold structure before creating files.
- **Declare skills at start of every response** body via a `Skills used:` block (see Section 1 for format).
- **Mark task complete** only after its tests pass and acceptance-to-test map entries are verified.
- **Keep OpenSpec specs, design notes, and tasks aligned** with the latest implementation.
- **Do not automatically stash** normal ticket progress. Use stash only for unrelated local or user changes.

### 4. Quality And Coverage Completion

**❌ HARD GATE (authority level 5): Coverage must meet `coverage.minimumPercent` before PR handoff.**

Implementation is not complete until:

- all OpenSpec tasks are complete,
- OpenSpec verification has no critical issues,
- configured local hooks or quality tools pass when they run — including the `lefthook.yml` `pre-push` stack-tests hook (`python -m tools.sdd_cli stack-tests`, unit/integration/architecture levels) when a stack is configured,
- repository PR validation passes,
- **coverage meets `coverage.minimumPercent`** — verified locally when a command is available, or via CI as the authoritative gate.

Before PR and ticket provider review handoff, re-read the active OpenSpec `tasks.md` and stop if any `- [ ]` task remains, including final quality, Context Findings, PR review feedback, validation, or handoff tasks. Mark a task complete only when the matching evidence is present in the PR body, ticket handoff comment, validation output, docs/context review result, or knowledge status.

For web/API application work, preserve the delivery health contract required by deployment promotion:

- The app must expose `/health` with HTTP 200 and JSON `status=ok`.
- The endpoint must not expose secrets, connection strings, tokens, host internals, or detailed exception data.
- Add or preserve focused tests for `/health` when application startup, routing, middleware, hosting, or deployment-facing behavior changes.
- Treat removal or breakage of `/health` as an implementation failure because DEV, QA, and PROD promotion gates depend on it.

Run Deployment Topology Review through the selected deployment configure skill when changes touch deployable project files, deployment manifests, provider-specific deployment infrastructure, or configured package/deploy workflows. Verify deployment manifests, provider infrastructure settings, workflow artifacts, and per-app DEV/QA/PROD secret documentation stay aligned. Handoff comments must include `Deployment topology: updated`, `Deployment topology: verified`, or `Deployment topology: no deployable app changes`.

**❌ HARD RULE**: If coverage is below `coverage.minimumPercent`, stop — do not proceed to PR creation, PR review, or ticket handoff. Add or update OpenSpec tasks for missing test coverage, write the missing unit or integration tests, and re-run coverage until the threshold is met. Never lower the threshold just to pass a ticket. This is a process violation (authority level 5).

### 5. Validation Failure Classification

When local hooks, configured quality tools, OpenSpec verification, PR review, or repository workflow fail:

1. Classify the failure before editing files.
2. Treat app, code, spec, formatting, build, test, coverage, staged-secret, or PR review feedback against changed behavior as implementation failures. Fix them in the current ticket, add or update OpenSpec tasks before or alongside the fix, update specs/design when behavior changes, and add or update tests for regressions, edge cases, and coverage gaps.
3. Treat runner, workflow-container, Docker image pull, missing runtime tools, local repository hostname, scanner installation, missing shell tool, or stale tool-install URL failures as infra/tooling failures. Route through `configure-dev-environment`, `configure-ci-runner`, or `configure-quality-gates`; run configured quality-gate and runner validation helpers when applicable.
4. If an infra/tooling failure blocks the authoritative PR gate, fix repo-owned workflow/config issues in the branch or route external setup issues to the infra skill, then keep the ticket open until repository PR validation passes. Record the fix separately from feature implementation work.
5. Full local `gitleaks detect --source . --redact --no-git` findings in ignored local secret files are local setup notes, not implementation defects. Staged `gitleaks protect --staged --redact` and CI secret scans remain authoritative for tracked changes.
6. Treat flaky or intermittent failures separately when the same command or CI job passes and fails without code changes. Rerun once. If the rerun passes, record a flaky-test note and continue only when the authoritative gate is passing. If it fails again, classify as implementation or infra based on the failure evidence.
7. Maintain a running list grouped as feature fixes, quality/test fixes, flaky/intermittent notes, infra validation fixes, and remaining non-blocking infra notes.

### 6. Verify OpenSpec

Run `dev-flow-verify-change` before PR handoff. Fix critical issues. Convert required follow-up into OpenSpec tasks and keep artifacts current with the final code state.

### 7. Commit Checkpoints And Push

Use one PR with multiple commits as the default ticket shape. Chained PRs apply only when the Review Workload Forecast, OpenSpec artifacts, or user direction records that split.

At each workflow-step checkpoint with tracked changes:

1. Finish the step changes.
2. Review `git status` and the relevant diff.
3. Run the smallest relevant validation for that step, or document why validation is deferred to CI.
4. Run Context Findings Review before staging docs, knowledge, or workflow-policy changes.
5. Stage only files related to that completed step.
6. Commit with a message that satisfies the configured commit hook and starts with the ticket or OpenSpec id.
7. Let hooks run naturally. Do not bypass hooks unless the user explicitly requests that in the current chat.

Create checkpoint commits for OpenSpec refinement, implementation, tests or reusable QA coverage, docs/context/knowledge updates, review-feedback fixes, and ticket-scoped tooling/config fixes when those steps change tracked files. Skip empty commits. Do not intentionally leave broken intermediate commits; if two steps must stay together to keep the repository valid, combine them and report that reason in the handoff. Push the branch after the planned commit set is ready, and push again after each later feedback-fix commit.

Do not automatically stash normal ticket progress. Use stash only for unrelated local or user changes that block the current step, and document the stash in the handoff when it affects delivery flow.

### Context Findings Review

Before committing, apply the Context Findings classification from `docs/conventions/context-management.md` and the knowledge update process from `knowledge/README.md`. If the finding changes enforceable automation behavior, update `.codex/skills/_shared/delivery-contract.md` plus related skills and tests.

If implementation discovers durable authoritative knowledge, update the matching doc in the same PR. If it discovers reusable non-authoritative knowledge, update `knowledge/`. If no durable knowledge was discovered, record `Docs: no durable context changes` in the PR body and ticket handoff comment.

### 8. Coverage Verification Before PR

**❌ HARD GATE (authority level 5): Verify coverage before creating or reusing a PR.** Before any PR creation or reuse:

1. Check if a local coverage command was discovered in Section 2.
2. If yes — run it. If coverage is below `coverage.minimumPercent`, **stop**. Do not create/reuse the PR. Add OpenSpec tasks for missing tests, write them, re-run coverage, and confirm the threshold is met.
3. If no local command exists — report the coverage gap in the PR body. The CI workflow is the coverage gate; monitor it after PR creation.
4. Log the coverage result (percentage, command used, pass/fail) in the handoff output.

### 9. Full CI Validation Loop Before PR

**❌ HARD GATE (authority level 5): Run the full CI quality suite via the `sdd-e2e-ci:local` Docker image and fix all errors before creating the PR.** Do not create or reuse a PR until the local CI loop produces zero errors.

**Why this exists:** External CI feedback is slow and clutters the PR with fixup commits. Running the full check suite inside the CI container image locally ensures the PR is clean on first push, with the same tools and environment as the real CI pipeline.

**Prerequisites:** Docker must be running locally. The `sdd-e2e-ci:local` image must exist (built via `python -m tools.sdd_cli environment-lab build-gitea-images` or the CI workflow build step).

**Steps:**

1. **Read the CI workflow file** (`.gitea/workflows/pr-validation.yml`). The `container.image` field shows which image to use — currently `sdd-e2e-ci:local`. Extract the `run:` commands from each CI step.

2. **If the `sdd-e2e-ci:local` image is not present locally**, build it:
   ```bash
   python -m tools.sdd_cli environment-lab build-gitea-images
   ```
   If the build fails (Docker not available, missing Dockerfile, or network issue), skip to the fallback at the end of this section.

3. **Run each CI check individually** inside the container for clear pass/fail per check. Mount the current project as a volume:
   ```bash
   docker run --rm -v "$(pwd):/workspace" -w /workspace sdd-e2e-ci:local bash -c '<command>'
   ```
   Run these checks (extracted from the CI workflow):
   - **JSON validation:** `python3 -m json.tool` against every `.json` file
   - **Secret scan:** `gitleaks detect --source . --redact --no-git`
   - **SAST scan:** `semgrep scan --config p/typescript --config p/javascript --config p/python --config p/csharp --error --verbose .`
   - **SCA scan:** `trivy fs --format table --exit-code 1 --no-progress .`
   - **IaC scan:** `checkov -d . --compact --soft-fail --config-file .checkov.yml`

4. **Run stack-native checks** (build, test, coverage, lint). These may run inside the container if the image contains the stack's tools (Node.js, dotnet, Python with pytest, etc.), or directly on the host if the image lacks them:
   - **Inside container:** If the container has the stack's runtime, use the same `docker run` pattern: `docker run --rm -v "$(pwd):/workspace" -w /workspace sdd-e2e-ci:local bash -c 'npm run build && npm test'`
   - **On host:** If the container lacks the stack's tools, run directly on the host: `npm run build && npm test` (or `dotnet build && dotnet test`, `pytest --cov`, etc.)
   - Coverage must meet `coverage.minimumPercent` per Section 8

5. **Check results.** If any command fails or reports issues:
   - Fix the errors (code, config, tests, formatting)
   - Commit the fixes:
     ```bash
     git add -A
     git commit -m "{ticketKey}: fix quality check findings"
     ```
   - Re-run the failed check(s) from steps 3-4
   - **Loop until ALL checks pass with zero errors**

6. **Document the loop.** In the PR body, record:
   - The Docker image used (`sdd-e2e-ci:local`)
   - Which checks ran inside the container vs on the host
   - Number of fix cycles completed
   - Final pass/fail status per check

7. **Only after zero errors**, proceed to PR creation.

**Fallback — if Docker is not available or the `sdd-e2e-ci:local` image cannot be built:**
- Run stack-native checks (build, test, coverage, lint) directly on the host
- Document the gap in the PR body: which CI checks could not run locally and why
- The CI workflow remains the authoritative gate; monitor it after PR creation per Section 11's failure rules

**❌ HARD RULE**: If any quality check fails inside the container, do NOT create the PR. Fix, commit, re-run, loop until zero errors. This is a process violation (authority level 5).

### 10. Create Or Reuse The repository PR

Reuse an existing open PR for the branch when present. Otherwise create a PR targeting the configured base branch.

Resolve configured human reviewers for the PR body and ticket comment, but **do NOT call `request-reviewers` yet**. The actual reviewer request is deferred to Section 11.5, after the AI review completes. When `pr.reviewers` is `"all"`, list current repository collaborators and exclude the PR author plus the authenticated automation user. Normalize the collaborator response before filtering (the selected repository adapter may return either an array or a single object). Use each collaborator's `login` value, falling back to `username`, and discard empty or duplicate names. When `pr.reviewers` is an array, use the configured usernames after trimming empty values.

Store the resolved reviewer list for Section 11.5. Include `Reviewers requested: <usernames>` in the PR body and ticket comment, but defer the actual API call.

**Immediately after PR creation or reuse, add a comment on the ticket and move it to the configured review state.** Do NOT defer this to Section 12 — the ticket must reflect the PR even if the review loop pauses or encounters issues:

- **Add a ticket comment** with:
  ```text
  IA generated PR: {prUrl}
  
  **Branch:** {branchName}
  **OpenSpec change:** {openspecChangeName}
  **Reviewers (pending — will be assigned after AI review):** {reviewers}
  ```

- **Move the ticket to** `Developed` (OpenProject ID 8) — the configured `configured developed state`. If the ticket is already in this state (from a previous resume), skip the state transition but still add the comment.

  Use the selected ticket adapter's `move-state` and `comment` operations. For OpenProject, see `.codex/skills/_shared/api-helpers.md` → OpenProject → Patch description or status (for move-state) and → OpenProject → Create generated comments (for adding the comment via `POST ... /activities` with `{"comment": {"raw": "..."}}`).

  **If the move-state or comment API call fails**, log the error as a non-blocking note and continue. The Section 12 handoff will retry both the state move and the comment.

The PR body must include:

- ticket id
- OpenSpec change id
- implementation summary
- acceptance-to-test map for every acceptance criterion
- TDD RED/GREEN evidence for tests added or updated
- tests added or updated
- E2E expectations for QA when browser acceptance is relevant, or `E2E expectations for QA: none`
- coverage threshold used
- **coverage result: `<percentage>%` (`<pass|fail>`)**
- configured quality gates expected to run
- feature fixes applied
- quality/test fixes applied
- infra validation fixes applied
- Context findings: added/updated/none
- Docs updated: <files> or Docs: no durable context changes
- `Knowledge updated: <files>` or `Knowledge updated: none`
- Delivery risk: low/standard/high
- Review workload forecast: low/medium/high and split/exception decision when applicable
- Reviewers (pending — will be assigned after AI review in Section 11.5): <usernames>
- Assumptions recorded: <short list or none>
- remaining non-blocking infra notes
- known non-blocking product risks or gaps

### 11. Review And Fix Loop

Invoke the repo-owned `dev-flow-pr-review-feedback-loop` skill after PR creation and on every open-PR resume. That skill owns AI review findings, late human PR comments, feedback batch ids, ticket provider detection/fix comments, and OpenSpec `## PR Review Feedback` tasks.

After `dev-flow-pr-review-feedback-loop` returns, continue only when:

- current-head AI review has been run or reused,
- all OpenSpec `## PR Review Feedback` tasks are complete,
- all current feedback batches have `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}` markers,
- validation for feedback fixes has passed,
- `pr.labels.needsTests` and `pr.labels.needsChanges` are no longer valid for the current head.

Keep the ticket in `Developed` (OpenProject ID 8) while late human feedback fixes are applied. If `dev-flow-pr-review-feedback-loop` reports ambiguous or conflicting human feedback, stop and preserve its blocker classification.

### 11.5 Request Human Reviewers (After AI Review)

See `.codex/skills/_shared/pipeline-review-handoff.md` for the common AI review → human reviewers pattern.

### 12. Ticket Provider Handoff

The ticket was already moved to `Developed` (OpenProject ID 8) in Section 10 (immediately after PR creation). Verify the current state and comment and retry if either failed:

1. **Check current ticket state** via the ticket provider API. If it is already `Developed` (ID 8), skip the state transition. This is expected on normal flow.

2. **If the ticket is still in a pre-developed state** (e.g., `In progress`, ID 7), the Section 10 move failed — retry now: move the ticket to `Developed` (OpenProject ID 8).

3. **Verify the Section 10 PR comment was created and retry if missing.** See `.codex/skills/_shared/pipeline-ticket-comment.md` for the common comment verification pattern. Use:
   - Marker: `IA generated PR: {prUrl}`
   - Comment body: `**Branch:** {branchName}\n**OpenSpec change:** {openspecChangeName}\n**Reviewers (pending — will be assigned after AI review):** {reviewers}`
   - Severity: `blocking` (stop if comment cannot be created)

4. **Add the comprehensive handoff comment** (this supplements the Section 10 PR comment with full detail). Follow the same pattern from `.codex/skills/_shared/pipeline-ticket-comment.md`. Use:
   - Marker: `IA generated handoff: {ticketKey}`
   - Severity: `blocking`

   The handoff comment must include:
   - IA generated handoff marker: `IA generated handoff: {ticketKey}`
   - PR link
   - acceptance-to-test map for every acceptance criterion
   - TDD RED/GREEN evidence for tests added or updated
   - coverage threshold used
   - **coverage result: `<percentage>%` (`<pass|fail>`)**
   - quality gate result
   - feature fixes applied
   - quality/test fixes applied
   - infra validation fixes applied
   - improvements applied
   - tests added or updated
   - E2E expectations for QA when browser acceptance is relevant, or `E2E expectations for QA: none`
   - Context findings: added/updated/none
   - Docs updated: <files> or Docs: no durable context changes
   - `Knowledge updated: <files>` or `Knowledge updated: none`
   - Delivery risk: low/standard/high
   - Review workload forecast: low/medium/high and split/exception decision when applicable
   - Assumptions recorded: <short list or none>
   - remaining non-blocking infra notes
   - remaining non-blocking risks or gaps
   - Deployment topology: updated/verified/no deployable app changes

Do not move the ticket to Done.

## Output

Report the ticket, branch, OpenSpec change, PR URL, commits pushed, validation and coverage results, PR review feedback batches handled, Context Findings Review result, ticket handoff state, and any remaining blockers or risks.

## Archive And QA Policy

- Do not archive OpenSpec changes in this skill.
- Archive only after PR merge in a separate post-merge flow.
- QA findings after merge must create a new related ticket provider bug ticket linked to the parent ticket.
- The bug ticket gets its own branch, OpenSpec change if needed, implementation, PR, and review flow.

## Failure Rules

- Missing branch or OpenSpec change: stop and route to `dev-flow-start-ticket`.
- Dirty worktree with unrelated changes: stop before implementation.
- Missing or placeholder API token: stop before ticket provider or repository/review provider mutations.
- Invalid coverage config: use `80`, report the issue, and do not lower the gate.
- Lefthook pre-push stack tests fail or an unmapped framework is configured: stop before pushing — fix the tests or framework mapping and re-run `python -m tools.sdd_cli stack-tests` until it passes. Do not bypass the hook with `--no-verify` unless the user explicitly requests it. When no stack is configured the hook skips cleanly (expected template state).
- **Coverage below threshold: HARD STOP (authority level 5).** Do not create the PR, do not move the ticket to review, do not hand off until coverage meets `coverage.minimumPercent`. Add or update OpenSpec tasks for missing tests, write them, re-run coverage, and confirm the threshold is met before proceeding. If no local coverage command exists and CI is the only gate, report the gap and proceed — but if CI fails on coverage, stop and fix before re-triggering CI.
- Missing local coverage command: report the gap; do not invent a command when CI is the only configured coverage source.
- Missing acceptance-to-test map or committed automated coverage for any acceptance criterion: stop before product-code handoff or PR review handoff and add the missing tests.
- Product code changed before the first relevant failing test: stop, record the process gap, add the missing behavior test, confirm it fails against the pre-fix behavior when still feasible, then continue from GREEN.
- Missing Review Workload Forecast: update OpenSpec tasks before implementation, or stop if the forecast cannot be derived safely.
- Unchecked OpenSpec tasks at PR handoff: stop before moving the ticket to review; complete the task evidence or report the blocker.
- Oversized/high workload without split or `size:exception`: stop before implementation and request or record the required decision.
- Flaky test or CI failure: rerun once before classifying; do not edit product code solely for an unconfirmed intermittent failure.
- Repository workflow infra/tooling failure: route through `configure-dev-environment`, `configure-ci-runner`, or `configure-quality-gates`; run configured runner validation when runner/container compatibility is implicated; do not classify it as a product implementation defect.
- Ignored local secret findings from full local scans: report as local setup notes unless the same secret is staged, tracked, or reported by CI.
- Existing PR: reuse it instead of creating a duplicate.
- Existing review-agent comment for same head SHA: reuse it instead of posting a duplicate; post a new review marker only after the head SHA changes.
- Actionable AI or human PR feedback: invoke `dev-flow-pr-review-feedback-loop` to create OpenSpec `## PR Review Feedback` tasks, post ticket provider feedback batch comments, apply fixes, validate, commit, push, and rerun AI review before handoff.
- Ambiguous or conflicting human PR feedback: stop before changing code, request clarification in the PR when possible, and record the blocker in ticket provider.
- Late human PR feedback after ticket is in `Developed` (OpenProject ID 8): process it on manual resume and keep the ticket in `Developed` while fixes are applied.
- Stale PR labels: remove `needs-tests` after required tests are added and passing; remove `needs-changes` after requested fixes are in place, OpenSpec PR review feedback tasks are complete, and the current-head review has no blocking findings.
- Review loop exceeds 3 cycles with remaining blockers: stop and escalate with a concise conflict/stale-feedback summary.
- Missing ticket provider `Developed` state (ID 8): stop after PR/review work and report the missing state. The correct OpenProject statuses are defined in `delivery-contract-ticket.md`.
