---
name: dev-flow-implement-ticket
license: MIT
description: >-
  >- Implement an already-started configured ticket through OpenSpec tasks, project-profile quality gates,
  repository/review adapter handoff, review-agent fixes, and ticket adapter review-state update. Use when a ticket
  already has an implementation branch and OpenSpec change, or when Codex is asked to continue, finish, validate, or
  hand off ticket implementation work.
---

<!-- TIER 3: STAGE-SPECIFIC - Ticket implementation skill -->

# Implement Ticket

## Overview

Use this skill after `dev-flow-start-ticket` has created or reused the implementation branch, moved the ticket to
progress, and created the OpenSpec change. This skill owns implementation through PR
handoff. It does not select Todo tickets, create initial branches, or archive OpenSpec changes.

## Shared Context

Before implementation, handoff, or review work, follow `.agents/skills/_shared/skill-startup.md` with
`docs/conventions/development.md` as the stage-specific doc. Read `.template/project-profile.json`,
then load the selected ticket, repository/review, stack, and E2E adapters only when the current step needs them.

## Workflow Telemetry

See `.agents/skills/_shared/pipeline-workflow-telemetry.md` for the common workflow telemetry pattern. Use:

- `{workflowStage}` = `dev-flow-implement-ticket`
- `{agentRole}` = `implementation`

This stage writes its **own** completion row before handoff (mandatory):

```bash
python -m tools.sdd_cli dev-flow telemetry-upsert --ticket-key {ticketKey} \
  --workflow-stage dev-flow-implement-ticket --agent-role implementation \
  --started-utc {startedUtc} --finished-utc {finishedUtc} --outcome {outcome}
```

The marker `IA generated workflow telemetry: {ticketKey}:dev-flow-implement-ticket` is written automatically. The
prerequisite check in the Workflow section below still verifies the `dev-flow-start-ticket` row exists before starting.

## Configuration

Read `.template/project-profile.json` first for stack, provider, branch, ticket-key, and quality-gate policy. Read
`.template/client-tools.local.json` only for selected adapter runtime values. Fall back to
`.template/client-tools.example.json` only for defaults and setup guidance.

Read coverage config from `.template/quality.local.json` when present. If it is missing, invalid, or missing
`coverage.minimumPercent`, use `80` and report the configuration gap. The safe tracked
template is `.template/quality.example.json`.

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
2. Read `.template/delivery-context.local.json` when present and verify the resolved ticket, current branch, OpenSpec
change, existing PR, and any artifact commit match the locked `ticketKey`. If they
resolve to another ticket, stop and report the mismatch.
3. Stop if the branch or OpenSpec change is missing; tell the user to run the `dev-flow-start-ticket` flow first.
4. Check `git status --porcelain`. If unrelated changes exist, stop before implementation and list the changed files.

**Pre-Flight Gate: Verify OpenSpec and time entries exist.** Before any analysis or implementation work, verify the
following. If any check fails, stop and route back to `dev-flow-start-ticket`:

- **OpenSpec artifacts are complete:**

  Check that the required artifact files exist:

  - `openspec/changes/<change-name>/tasks.md`
  - `openspec/changes/<change-name>/design.md`
  - `openspec/changes/<change-name>/proposal.md`
  - `openspec/changes/<change-name>/specs/`

  If any are missing, stop and report: "OpenSpec change `<change-name>` is incomplete. Run the full propose flow first."

- **Work package has estimatedTime set:**

  ```bash
  curl -s -H "Authorization: Bearer <token>" "<openproject-url>/api/v3/work_packages/<id>" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('estimatedTime'))"
  ```

  If `estimatedTime` is null or empty, stop and report: "Work package has no estimated time. Complete step 17 of
  dev-flow-start-ticket first."

  - **Time entry exists for dev-flow-start-ticket:**

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

       Replace `<wpId>` with the work package ID and `<token>` with the API token from `.template/client-tools.local.json`.
       If no time entries exist, log one via `time-telemetry-upsert` (see Workflow Telemetry section) before proceeding.
       If logging fails, stop and report: "Cannot start implementation without time
       entries for dev-flow-start-ticket."

    **This is a hard gate (authority level 5).** Do not skip these checks even on resume. A previous agent may have
    skipped them.

   a. **Read stack configuration:**

- Stack lives **only** in `.template/project-profile.local.json` (the ignored local overlay). Read
`.template/project-profile.local.json` → `stack` section for frontend/backend/database values. If it does
not exist, stack is empty.
- Read `.template/project-profile.json` for **non-stack** config: providers, workflow, quality gates, adapters.
- Use the merged result from `load_project_profile()` (in `_shared.py`) when available, which overlays local.json on top
of profile.json.
- Read `.template/tool-recommendations.local.json` → `detectedTags`, `researchTopics`, `accepted` recommendations.

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
   | **Any task (generic)**                | **Scan all `.agents/skills/` directories.** Every installed skill must be assessed for relevance, not just stack-mapped ones. See sub-step f below. |

   c. **Load and declare each skill:**

- Try loading each identified `SKILL.md` via the `skill` tool first. If the `skill` tool reports "no skills available"
or is unavailable, read the SKILL.md file directly from
`.agents/skills/<name>/SKILL.md` and apply its rules manually.
- Declare all active skills at the start of every response body:

     ```markdown
     Skills used: caveman (auto, full), ponytail (auto, full),
     tdd (on-demand), playwright (on-demand),
     <tech-stack-skills> (on-demand)
     ```

- If a skill recommendation is listed in `accepted` but not yet installed in `.agents/skills/`, report it as a gap and
route to `project-guidance-acquire`. If the stack is empty (`applies: false` for
all domains) but the ticket implies a product, suggest running `python -m tools.sdd_cli guidance discover` to
auto-detect the stack from repo signals, or configure via `set-project-stack`.

   d. **Apply architecture patterns based on stack:**

- **React frontend:** Component-per-file, custom hooks for logic, service modules for API calls, TypeScript types in a
`types/` directory.
- **ASP.NET backend:** Controller → Service → Repository layering with dependency injection.
- **Python backend:** Route → Service → Repository or similar separation of concerns.
- **Clean Architecture:** Separate domain, application, infrastructure, and presentation layers — but only add layers
the implementation actually needs (ponytail principle: no speculative
abstractions).

   e. **Stop and report when:**

- Required skills are missing from `.agents/skills/` — route to `project-guidance-acquire`.
- Stack implies a framework but relevant test frameworks are not configured in the recommendations.

   f. **Scan all installed skills for relevance:** Beyond the stack-mapped skills above, enumerate every skill directory
   under `.agents/skills/` that has a `SKILL.md` and assess it:

- Read the skill's `SKILL.md` (or `metadata.json` → `description` when available) to determine what domain, language, or
pattern it covers.
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

- If assessing a skill's applicability requires understanding its full rules, load it via `skill('<name>')` (or read its
`SKILL.md` directly) before deciding.
- **Failure to scan:** If a skill is installed in `.agents/skills/` but the agent does not list it in the declaration, it
is a process violation (authority level 5). The implementation must stop and
the agent must redo the scan.

1. Detect resume checkpoints before doing new work:
   - completed and pending OpenSpec tasks,
   - existing implementation commits on the branch,
   - upstream branch and push status,
   - existing open PR for the branch,
   - latest review-agent marker and stable AI finding ids for the current head SHA,
   - existing OpenSpec `## PR Review Feedback` tasks,
   - human-authored top-level PR comments and inline code review comments,
   - latest ticket provider `IA generated PR feedback detected: {headSha}:{feedbackBatchId}` markers,
   - latest ticket provider `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}` markers,
   - current `agent-reviewed`, `needs-tests`, and `needs-changes` labels,
   - latest repository workflow status.
     Continue from the latest completed checkpoint instead of restarting earlier steps.
2. Confirm the OpenSpec change is active via the opsx flow: run `openspec status --change "<change>" --json` and check
   that `tasks.md` exists (or `openspec/changes/<change>/tasks.md` on disk).
3. Load context files for implementation by reading the change artifacts directly:
   - `openspec/changes/<change>/proposal.md` — what & why
   - `openspec/changes/<change>/specs/*.md` — behavior specs
   - `openspec/changes/<change>/design.md` — how
   - `openspec/changes/<change>/tasks.md` — implementation steps
4. Run the opsx apply flow — delegate to `openspec-apply-change` (`.agents/skills/openspec-apply-change/SKILL.md`):
   `openspec status --change "<change>" --json` for the task list, then implement incomplete tasks one by one using TDD
cycles per the apply skill's repo TDD rules.
5. Classify delivery risk from ticket text, OpenSpec artifacts, changed/planned paths, and estimated changed lines using
the shared delivery contract. Prefer repo-local helpers when available. Record
`low`, `standard`, or `high` in the PR body and ticket handoff.

### 2. Discover Quality Gates

Inspect configured quality surfaces. Do not invent validation commands.

- `.template/quality.local.json`, falling back to coverage threshold `80`
- `.template/quality.example.json`, for the tracked default
- configured PR validation workflow files
- configured workflow documentation
- `lefthook.yml`

Treat repository workflow PR validation as the authoritative quality gate. Treat local hooks as automatic protections
that run through normal Git operations.

**❌ HARD GATE (authority level 5): Coverage must be verified locally before PR creation.** The coverage threshold from
`.template/quality.local.json` (`coverage.minimumPercent`, default `80`) is a hard
gate — implementation cannot proceed to PR handoff unless coverage meets or exceeds the threshold.

**❌ HARD GATE (authority level 5): Lefthook pre-push stack tests must pass before pushing.** The `lefthook.yml`
`pre-push` hook runs `python -m tools.sdd_cli stack-tests`, which runs the product test
suite — unit, integration, and architecture levels per `.agents/skills/_shared/test-requirements.md` — driven by
`stack.testFrameworks` from `.template/project-profile.local.json`. This gate runs on the
dev machine (stack runtimes live locally; the CI image stays lean) and applies on every `git push`:

- **Stack configured:** the hook installs dependencies, runs the test command for each mapped framework (pytest for
Python, vitest/jest for JS/TS, `dotnet test` for .NET — pytest is Python-only and
never used for .NET), then runs the **coverage gate** with the configurable threshold `coverage.minimumPercent` from
`.template/quality.local.json` (fallback `.template/quality.example.json`, default `80`).
A failing test or coverage-below-threshold step fails the push. A framework with tests but no mapped coverage command
reports a gap step (non-blocking) — CI remains the authoritative coverage gate for
that framework.
  - **Stack-native coverage:** the coverage gate runs each framework's native coverage command with the configured
  threshold — e.g. .NET stacks run `dotnet test /p:CollectCoverage=true /p:Threshold={n}`, which requires
  `coverlet.msbuild` referenced in the test project. Without it, `dotnet test`
  silently ignores those properties and exits 0 — a false pass. `dev-flow-scaffold-project` must add the framework's
  coverage tool (e.g. `coverlet.msbuild` for .NET) to test projects; verify it is present before relying on the
  coverage gate.
- **No stack configured (template state):** the hook skips cleanly and exits 0 — no tests to run.
- **Never bypass with `--no-verify`** unless the user explicitly requests it in the current chat. If a push is blocked
by failing stack tests, fix the tests before pushing (same treatment as the
coverage gate). The CI image intentionally does not contain stack runtimes, so this local hook is the only product-test
gate — CI covers scans only.

Discover a local coverage command:

1. Prefer the command used by configured PR validation workflow files.
2. Then prefer commands documented in configured workflow documentation, `lefthook.yml`, project README files, or
package/build manifests.
3. If exactly one stack-native coverage command is obvious, use it as a local fallback only when no repo-specific
command overrides it.
4. If no unambiguous local coverage command exists, report that CI remains the only coverage source.

**If a local coverage command exists:** Run it before PR creation. If coverage is below `coverage.minimumPercent`, stop
— do not create the PR. Add or update OpenSpec tasks for missing coverage, write
the missing tests, and re-run coverage until the threshold is met.

**If no local coverage command exists:** The PR validation workflow is the coverage gate. Report the coverage gap in the
PR body and ticket handoff. If the PR validation workflow fails on coverage,
treat it as an implementation failure per Section 5.

When repository workflow runner, workflow container, or security tool compatibility is part of the configured gate, use
the existing infra validation path instead of inventing ad hoc checks:

```bash
python -m tools.sdd_cli dev-flow audit-skill-contracts
the selected runner validation helper from `configure-dev-environment`
```

Use the selected runner validation helper whenever repository workflow fails before repository validation commands run,
or logs show image pull failures, missing runtime tools, checkout networking
failures, missing scanners, missing shell tools, or job-container tool incompatibility.

### 2.5 Knowledge Consult

Before starting the TDD cycle, consult the knowledge base for known errors, patterns, anti-patterns, and lessons
relevant to the change's area:

```bash
python -m tools.sdd_cli knowledge-search search --query <feature or module terms>
python -m tools.sdd_cli knowledge-search search --list-topics
```

Fold relevant entries into the implementation approach and risk analysis. Record `Knowledge consulted: <files>` or
`Knowledge consulted: none` in the PR body and ticket handoff comment. If the consult
surfaces a reusable lesson the change depends on, capture it via `knowledge/README.md` and the
`docs-knowledge-maintenance` skill during the Context Findings Review.

### 3. Implement — Tests First, Then Code

**❌ HARD GATE (authority level 5): Test folder structure must exist.** Before writing ANY test or product code, verify that all 4 test folders exist:

```
apps/<appId>/test/unit/
apps/<appId>/test/integration/
apps/<appId>/test/e2e/
apps/<appId>/test/architecture/
```

If ANY folder is missing, **stop** and create them. Tests in `src/` (co-located) are a process violation — the `test/` directory is the ONLY allowed location. See `.agents/skills/_shared/test-requirements.md` §HARD GATE: Test Folder Structure.

**❌ HARD GATE (authority level 5): TDD test-first is mandatory.** Before writing ANY product code, all acceptance
criteria must have tests written and confirmed RED (failing). This gate is non-negotiable.

**❌ HARD GATE (authority level 5): AC source is the IA curated block, NOT the original ticket description.**
The IA curated block (from enrich steps 10-12 in `dev-flow-start-ticket`) is the **only** source of truth for
acceptance criteria. The original ticket description is raw input — the IA refinement process transforms it into
curated, testable ACs. Read the IA curated block from the ticket description (look for the section starting with
`## IA Curated` or the structured AC list added by the start-ticket enrichment). If the IA curated block is missing,
stop and route back to `dev-flow-start-ticket` to complete enrichment first.

**Do NOT derive tests from:**
- The original ticket description (before IA refinement)
- OpenSpec proposal.md (it describes what/why, not testable ACs)
- OpenSpec design.md (it describes how, not testable ACs)
- Assumed behavior not explicitly listed in the IA curated block

**Enforcement sequence:**
1. **Read the IA curated block** from the ticket description — extract every acceptance criterion.
2. Build the **acceptance-to-test map**: map each IA curated AC to specific tests. Every AC must have at least one
corresponding test. If an AC cannot be tested, flag it and ask the user.
3. Write ALL tests first (unit + integration + architecture per `.agents/skills/_shared/test-requirements.md`).
4. Run the test suite — confirm ALL new tests are RED (failing because no product code exists yet).
5. **Only after RED is confirmed**, proceed to write product code.
6. Each implementation cycle follows RED → GREEN → REFACTOR per `.agents/skills/_shared/pipeline-tdd-cycle.md`.
7. **After each GREEN cycle, check off the corresponding task** in `openspec/changes/<change>/tasks.md` —
change `- [ ]` to `- [x]` for the task just completed. Do NOT batch check-offs. Do NOT move to the next task
until the current task is checked off. This is a hard gate: unchecked tasks at PR handoff are a process violation.

**If product code is written before tests are confirmed RED:**
- Stop immediately.
- Record the process violation.
- Delete or revert the premature product code.
- Write the missing tests.
- Confirm RED.
- Then continue from GREEN.

This is the same rule from `.agents/skills/_shared/pipeline-tdd-cycle.md` Phase A, enforced as a hard gate here.
Do not treat it as advisory. Do not skip it on resume. A previous agent may have skipped it.

See `.agents/skills/_shared/pipeline-tdd-cycle.md` for the common TDD test-first pattern. The following are
feature-flow-specific additions:

- **AC source:** the **IA curated block** in the ticket description (from enrich steps 10-12 in
`dev-flow-start-ticket`). This is the ONLY valid source for acceptance criteria and test derivation.
The original ticket description, OpenSpec proposal, and design doc are context — not test sources.
- **Task source:** `openspec/changes/<change>/tasks.md`
- **Before coding, activate skills from step 5a-f scan.** The declared skills in the `Skills used:` block are NOT
decorative — they must be actively applied during every TDD cycle.
- **Before any service interaction, check MCP routing** per `.agents/mcp-instructions.md`: service MCPs (gitea,
openproject, grafana, kubernetes). Repository content search uses built-in file/search
tools.
- **Create the per-app folder structure** (`apps/<appId>/src/` and `apps/<appId>/test/`, ADR-0002 layout) before
writing any product code. There is no root `src/`/`test/` pair — each deployable app owns its source, tests,
`deploy/` manifests, and `Dockerfile` under `apps/<appId>/`. Always **ask the user** to confirm the
scaffold structure before creating files.
- **Declare skills at start of every response** body via a `Skills used:` block (see Section 1 for format).
- **Mark task complete** only after its tests pass and acceptance-to-test map entries are verified.
- **Keep OpenSpec specs, design notes, and tasks aligned** with the latest implementation.
- **Do not automatically stash** normal ticket progress. Use stash only for unrelated local or user changes.

### 4. Quality And Coverage Completion

**❌ HARD GATE (authority level 5): Coverage must meet `coverage.minimumPercent` before PR handoff.**

Implementation is not complete until:

- all OpenSpec tasks are complete,
- OpenSpec verification has no critical issues,
- configured local hooks or quality tools pass when they run — including the `lefthook.yml` `pre-push` stack-tests hook
(`python -m tools.sdd_cli stack-tests`, unit/integration/architecture levels)
when a stack is configured,
- repository PR validation passes,
- **coverage meets `coverage.minimumPercent`** — verified locally when a command is available, or via CI as the
authoritative gate.

Before PR and ticket provider review handoff, re-read the active OpenSpec `tasks.md` and stop if any `- [ ]` task
remains, including final quality, Context Findings, PR review feedback, validation, or
handoff tasks. Mark a task complete only when the matching evidence is present in the PR body, ticket handoff comment,
validation output, docs/context review result, or knowledge status.

For web/API application work, preserve the delivery health contract required by deployment promotion:

- The app must expose `/health` with HTTP 200 and JSON `status=ok`.
- The endpoint must not expose secrets, connection strings, tokens, host internals, or detailed exception data.
- Add or preserve focused tests for `/health` when application startup, routing, middleware, hosting, or
deployment-facing behavior changes.
- Treat removal or breakage of `/health` as an implementation failure because DEV, QA, and PROD promotion gates depend
on it.
- Never define a client-side (SPA) route at `/health` — the web server owns that path for the probe
  (`location = /health`), so a SPA route there works in local dev but silently breaks in the deployed (nginx)
  topology. Put any user-facing health/status page on a non-probe path (e.g. `/status`).

Run Deployment Topology Review through the selected deployment configure skill when changes touch deployable project
files, deployment manifests, provider-specific deployment infrastructure, or
configured package/deploy workflows. Verify deployment manifests, provider infrastructure settings, workflow artifacts,
and per-app DEV/QA/PROD secret documentation stay aligned. Handoff comments must
include `Deployment topology: updated`, `Deployment topology: verified`, or `Deployment topology: no deployable app
changes`.

**❌ HARD RULE**: If coverage is below `coverage.minimumPercent`, stop — do not proceed to PR creation, PR review, or
ticket handoff. Add or update OpenSpec tasks for missing test coverage, write the
missing unit or integration tests, and re-run coverage until the threshold is met. Never lower the threshold just to
pass a ticket. This is a process violation (authority level 5).

### 5. Validation Failure Classification

When local hooks, configured quality tools, OpenSpec verification, PR review, or repository workflow fail:

1. Classify the failure before editing files.
2. Treat app, code, spec, formatting, build, test, coverage, staged-secret, or PR review feedback against changed
behavior as implementation failures. Fix them in the current ticket, add or update
OpenSpec tasks before or alongside the fix, update specs/design when behavior changes, and add or update tests for
regressions, edge cases, and coverage gaps.
3. Treat runner, workflow-container, Docker image pull, missing runtime tools, local repository hostname, scanner
installation, missing shell tool, or stale tool-install URL failures as infra/tooling
failures. Route through `configure-dev-environment`, `configure-ci-runner`, or `configure-quality-gates`; run configured
quality-gate and runner validation helpers when applicable.
4. If an infra/tooling failure blocks the authoritative PR gate, fix repo-owned workflow/config issues in the branch or
route external setup issues to the infra skill, then keep the ticket open until
repository PR validation passes. Record the fix separately from feature implementation work.
5. Full local `gitleaks detect --source . --redact --no-git` findings in ignored local secret files are local setup
notes, not implementation defects. Staged `gitleaks protect --staged --redact` and
CI secret scans remain authoritative for tracked changes.
6. Treat flaky or intermittent failures separately when the same command or CI job passes and fails without code
changes. Rerun once. If the rerun passes, record a flaky-test note and continue only
when the authoritative gate is passing. If it fails again, classify as implementation or infra based on the failure
evidence.
7. Maintain a running list grouped as feature fixes, quality/test fixes, flaky/intermittent notes, infra validation
fixes, and remaining non-blocking infra notes.

### 6. Verify OpenSpec

Run `dev-flow-verify-change` before PR handoff. Fix critical issues. Convert required follow-up into OpenSpec tasks and
keep artifacts current with the final code state.

### 7. Commit Checkpoints And Push

Use one PR with multiple commits as the default ticket shape. Chained PRs apply only when the Review Workload Forecast,
OpenSpec artifacts, or user direction records that split.

**⚠️ Lefthook stash-conflict recovery:** when a commit fails with `Unable to restore
previously hidden unstaged changes` (lefthook stashes unstaged changes, runs `trunk fmt`,
then fails to restore the stash because a file was both staged and unstaged), the working tree may have been silently
**reverted to HEAD** for all modified tracked files. Do NOT follow the suggested
`git add -A && git commit` — it would commit the reverted (HEAD) versions. Instead:

1. Run `git diff HEAD --stat` and grep for key markers the change should contain (e.g. an endpoint or component name)
before committing anything.
2. Recover lost work from the dangling stash object: `git fsck --no-reflogs | grep commit`, then `git show <sha>:<path>`
to identify content and `git checkout <sha> -- <paths>` to restore it.
3. Verify the **committed tree**, not just the working tree: after commit, `git show HEAD:<file>` and confirm the
expected markers are present (a clean tree can still be missing the change).
4. Commit in narrow slices with explicit paths (never blind `git add -A`) when hooks reformat files; keep OpenSpec-only
commits separate from code commits; stage a file BEFORE a hook that reformats it
so the restore patch has nothing to conflict with.

At each workflow-step checkpoint with tracked changes:

1. Finish the step changes.
2. Review `git status` and the relevant diff.
3. Run the smallest relevant validation for that step, or document why validation is deferred to CI.
4. Run Context Findings Review before staging docs, knowledge, or workflow-policy changes.
5. Stage only files related to that completed step.
6. Commit with a message that satisfies the configured commit hook and starts with the ticket or OpenSpec id. For
   non-ticket repo changes (infra/Dockerfile/tooling fixes without an OpenProject ticket), use the `[SDD]` prefix the
   commit-msg hook accepts — observed: the gate rejects unprefixed messages, so `[SDD] <summary>` is the canonical
   shape for unticketed changes.
7. Let hooks run naturally. Do not bypass hooks unless the user explicitly requests that in the current chat.

**⚠️ Hook realities (observed in parallel delivery):**

- **`pre-commit trunk-fmt` reformats AFTER the commit lands.** The commit succeeds but leaves reformatted files dirty;
  this is expected, not a failure. Re-check `git status` after every commit, and make a small separate
  "formatting pass" commit (same ticket prefix) so the tree is clean before push. Some files may show `M` with an
  empty diff (stat-cache/CRLF noise) — refresh the index (`git add` those paths or `git update-index --refresh`)
  before treating them as real changes.
- **Long hooks can kill the commit mid-run.** `trunk-check`/`gitleaks` can exceed a 2-minute tool timeout: the commit
  aborts but leaves files staged. Before retrying, check `git status` (files staged, no new commit) and retry with a
  longer timeout — do NOT assume the commit landed, and do NOT blind `git add -A` (see stash-conflict recovery
  above).
- **Budget hook time per commit** (trunk runs ~70s–4min); prefer fewer, larger checkpoint commits over many small ones.

Create checkpoint commits for OpenSpec refinement, implementation, tests or reusable QA coverage, docs/context/knowledge
updates, review-feedback fixes, and ticket-scoped tooling/config fixes when
those steps change tracked files. Skip empty commits. Do not intentionally leave broken intermediate commits; if two
steps must stay together to keep the repository valid, combine them and report that
reason in the handoff. Push the branch after the planned commit set is ready, and push again after each later
feedback-fix commit.

Do not automatically stash normal ticket progress. Use stash only for unrelated local or user changes that block the
current step, and document the stash in the handoff when it affects delivery flow.

**⚠️ Windows agent tool-execution rule:** complex bash quoting (nested quotes/escapes in
one-line `python -c "..."` or curl commands reading `client-tools.local.json`) can
break JSON parsing of the agent tool call on Windows. For non-trivial shell logic, write a temp Python script under
`.template/` (e.g. `.template/_tmp_<purpose>.py`), run it, and delete it after — keep
one-liners simple. Prefix console-printing commands with `PYTHONIOENCODING=utf-8` on Windows to avoid cp1252
`UnicodeEncodeError` on emoji/non-ASCII output.

When the user explicitly forbids PowerShell, never use a PowerShell-defaulting execution path (e.g.
a `shell_command` tool) — use file-based edits (apply_patch or the repo's native edit tools) and a
neutral shell or Node `child_process.execFile` for validation commands.

### Context Findings Review

Before committing, apply the Context Findings classification from `docs/conventions/context-management.md` and the
knowledge update process from `knowledge/README.md`. If the finding changes
enforceable automation behavior, update `.agents/skills/_shared/delivery-contract.md` plus related skills and tests.

If implementation discovers durable authoritative knowledge, update the matching doc in the same PR. If it discovers
reusable non-authoritative knowledge, update `knowledge/`. If no durable knowledge
was discovered, record `Docs: no durable context changes` in the PR body and ticket handoff comment.

### 8. Coverage Verification Before PR

**❌ HARD GATE (authority level 5): Verify coverage before creating or reusing a PR.** Before any PR creation or reuse:

1. Check if a local coverage command was discovered in Section 2.
2. If yes — run it. If coverage is below `coverage.minimumPercent`, **stop**. Do not create/reuse the PR. Add OpenSpec
tasks for missing tests, write them, re-run coverage, and confirm the threshold
is met.
3. If no local command exists — report the coverage gap in the PR body. The CI workflow is the coverage gate; monitor it
after PR creation.
4. Log the coverage result (percentage, command used, pass/fail) in the handoff output.

### 9. Full CI Validation Loop Before PR

**❌ HARD GATE (authority level 5): Run the full CI quality suite via the `sdd-e2e-ci:local` Docker image and fix all
errors before creating the PR.** Do not create or reuse a PR until the local CI
loop produces zero errors.

**Why this exists:** External CI feedback is slow and clutters the PR with fixup commits. Running the full check suite
inside the CI container image locally ensures the PR is clean on first push, with
the same tools and environment as the real CI pipeline.

**Prerequisites:** Docker must be running locally. The `sdd-e2e-ci:local` image must exist (built via `python -m
tools.sdd_cli environment-lab build-gitea-images` or the CI workflow build step).

**Steps:**

1. **Read the CI workflow file** (`.gitea/workflows/pr-validation.yml`). The `container.image` field shows which image
to use — currently `sdd-e2e-ci:local`. Extract the `run:` commands from each CI
step.

2. **If the `sdd-e2e-ci:local` image is not present locally**, build it:

   ```bash
   python -m tools.sdd_cli environment-lab build-gitea-images
   ```

   If the build fails (Docker not available, missing Dockerfile, or network issue), skip to the fallback at the end of
   this section.

3. **Run each CI check individually** inside the container for clear pass/fail per check. Mount the current project as a
volume:

   ```bash
   docker run --rm -v "$(pwd):/workspace" -w /workspace sdd-e2e-ci:local bash -c '<command>'
   ```

   Run these checks (extracted from the CI workflow):
   - **JSON validation:** `python3 -m json.tool` against every `.json` file
   - **Secret scan:** `gitleaks detect --source . --redact --no-git`
   - **SAST scan:** `semgrep scan --config p/typescript --config p/javascript --config p/python --config p/csharp
   --error --verbose .`
   - **SCA scan:** `trivy fs --format table --exit-code 1 --no-progress .`
   - **IaC scan:** `checkov -d . --compact --soft-fail --config-file .checkov.yml`

4. **Run stack-native checks** (build, test, coverage, lint). These may run inside the container if the image contains
the stack's tools (Node.js, dotnet, Python with pytest, etc.), or directly on the
host if the image lacks them:
   - **Inside container:** If the container has the stack's runtime, use the same `docker run` pattern: `docker run --rm
   -v "$(pwd):/workspace" -w /workspace sdd-e2e-ci:local bash -c 'npm run build &&
   npm test'`
   - **On host:** If the container lacks the stack's tools, run directly on the host: `npm run build && npm test` (or
   `dotnet build && dotnet test`, `pytest --cov`, etc.)
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

**❌ HARD RULE**: If any quality check fails inside the container, do NOT create the PR. Fix, commit, re-run, loop until
zero errors. This is a process violation (authority level 5).

### 9.5 Prune Implemented Scaffold Shapes

Once the implemented app is registered in `infra/deployment/apps.json` and all checks pass, remove the
scaffold shape whose kind the real app now replaces — the real app is the reference (ADR-0005 lifecycle).

Run the deterministic prune step:

```bash
python -m tools.sdd_cli environment-lab prune-scaffold
```

It removes, per registered app kind:

- a registered `kind: service` app → deletes `.template/scaffold/apps/service/`
- a registered `kind: job` app → deletes `.template/scaffold/apps/job/`
- a registered `db-bootstrap` app → deletes `.template/scaffold/db-bootstrap/`

Dry-run first with `--dry-run true` and confirm the plan with the user. Include the removal in the PR so the
template never carries starter shapes alongside real implementations. If no shape is redundant yet (e.g. an
app was implemented without being registered), the step reports `prune.none` and continues — it is never a
blocker, only a cleanup.### 10–12. PR Lifecycle (Shared)

**Follow the 7-step shared PR lifecycle** in `.agents/skills/_shared/pipeline-pr-lifecycle.md` exactly. Do NOT
re-implement, duplicate, or redefine its steps. The shared lifecycle owns:

- Step 1: Create/reuse PR + ticket comment + state move
- Step 2: Request human reviewers (hard gate — immediate)
- Step 3: AI review via `dev-flow-pr-review-agent`
- Step 4: Feedback loop via `dev-flow-pr-review-feedback-loop`
- Step 5: CI validation (pr-validation.yml)
- Step 6: Re-verify reviewers (hard gate)
- Step 7: Human merge + post-merge handoff

This skill adds only **ticket-specific PR body content** and **ticket-specific handoff comment content**.

**Ticket-specific PR body additions** (beyond the shared lifecycle's standard body):
- acceptance-to-test map for every acceptance criterion
- TDD RED/GREEN evidence for tests added or updated
- `Knowledge updated: <files>` or `Knowledge updated: none`
- Deployment topology: updated/verified/no deployable app changes

**Ticket-specific handoff comment** — follow `.agents/skills/_shared/pipeline-ticket-comment.md`:
- Marker: `IA generated handoff: {ticketKey}`
- Severity: `blocking`
- Include: PR link, acceptance-to-test map, TDD RED/GREEN evidence, coverage result, quality gate result,
  feature/quality/infra fixes, tests, Context findings, Docs, Knowledge, Delivery risk, Deployment topology.
- Do not move the ticket to Done.

## Output

Report the ticket, branch, OpenSpec change, PR URL, commits pushed, validation and coverage results, PR review feedback
batches handled, Context Findings Review result, ticket handoff state, and any
remaining blockers or risks.

## Archive And QA Policy

- Do not archive OpenSpec changes in this skill.
- Archive only after PR merge in a separate post-merge flow.
- QA findings after merge must create a new related ticket provider bug ticket linked to the parent ticket.
- The bug ticket gets its own branch, OpenSpec change if needed, implementation, PR, and review flow.

## Failure Rules

- Missing branch or OpenSpec change: stop and route to `dev-flow-start-ticket`.
- **Reviewers not requested on PR (authority level 5):** Stop after PR creation. Run `python -m tools.sdd_cli
gitea request-reviewers --pr {prNumber}` before proceeding to AI review or handoff. A PR without reviewers
is incomplete — the shared PR lifecycle Step 2 is a hard gate, not optional.
- **Missing IA curated block in ticket description (authority level 5):** Stop before any implementation or test
writing. The IA curated block (from enrich steps 10-12) is the mandatory AC source. Route back to
dev-flow-start-ticket to complete ticket enrichment. Do not guess or infer ACs from the raw ticket description.
- Dirty worktree with unrelated changes: stop before implementation.
- Missing or placeholder API token: stop before ticket provider or repository/review provider mutations.
- Invalid coverage config: use `80`, report the issue, and do not lower the gate.
- Lefthook pre-push stack tests fail or an unmapped framework is configured: stop before pushing — fix the tests or
framework mapping and re-run `python -m tools.sdd_cli stack-tests` until it passes.
Do not bypass the hook with `--no-verify` unless the user explicitly requests it. When no stack is configured the hook
skips cleanly (expected template state).
- **Coverage below threshold: HARD STOP (authority level 5).** Do not create the PR, do not move the ticket to review,
do not hand off until coverage meets `coverage.minimumPercent`. Add or update
OpenSpec tasks for missing tests, write them, re-run coverage, and confirm the threshold is met before proceeding. If no
local coverage command exists and CI is the only gate, report the gap and
proceed — but if CI fails on coverage, stop and fix before re-triggering CI.
- Missing local coverage command: report the gap; do not invent a command when CI is the only configured coverage
source.
- Missing acceptance-to-test map or committed automated coverage for any acceptance criterion: stop before product-code
handoff or PR review handoff and add the missing tests.
- **TDD test-first violated (authority level 5):** Product code changed before ALL acceptance tests were written and
confirmed RED. Stop immediately. Revert premature product code. Write all missing tests. Confirm RED.
Then continue from GREEN. This is a hard gate — no exceptions, no resume shortcuts. Record the violation in the PR
body and ticket handoff.
- Missing Review Workload Forecast: update OpenSpec tasks before implementation, or stop if the forecast cannot be
derived safely.- **Unchecked OpenSpec tasks at PR handoff (authority level 5):** Stop before moving the ticket to review. Every
task must be checked off (`- [x]`) as it is implemented — not batched at the end. If any `- [ ]` remains, the
implementation is incomplete. Complete the task evidence or report the blocker.
- Oversized/high workload without split or `size:exception`: stop before implementation and request or record the
required decision.
- Flaky test or CI failure: rerun once before classifying; do not edit product code solely for an unconfirmed
intermittent failure.
- Repository workflow infra/tooling failure: route through `configure-dev-environment`, `configure-ci-runner`, or
`configure-quality-gates`; run configured runner validation when runner/container
compatibility is implicated; do not classify it as a product implementation defect.
- Ignored local secret findings from full local scans: report as local setup notes unless the same secret is staged,
tracked, or reported by CI.
- Existing PR: reuse it instead of creating a duplicate.
- Existing review-agent comment for same head SHA: reuse it instead of posting a duplicate; post a new review marker
only after the head SHA changes.
- Actionable AI or human PR feedback: invoke `dev-flow-pr-review-feedback-loop` to create OpenSpec `## PR Review
Feedback` tasks, post ticket provider feedback batch comments, apply fixes, validate,
commit, push, and rerun AI review before handoff.
- Ambiguous or conflicting human PR feedback: stop before changing code, request clarification in the PR when possible,
and record the blocker in ticket provider.
- Late human PR feedback after ticket is in `Developed` (OpenProject ID 8): process it on manual resume and keep the
ticket in `Developed` while fixes are applied.
- Stale PR labels: `agent-reviewed` is the clean marker — present only when the current-head AI review has ZERO findings
of any severity AND the current-head PR Validation run is green; remove it
whenever actionable findings exist or the run is red/pending, and rely on the re-review to reapply it when clean. Remove
`needs-tests` after required tests are added and passing; remove
`needs-changes` after requested fixes are in place, OpenSpec PR review feedback tasks are complete, and the current-head
review has no findings of any severity.
- Review loop exceeds 3 cycles with remaining blockers: stop and escalate with a concise conflict/stale-feedback
summary.
- Missing ticket provider `Developed` state (ID 8): stop after PR/review work and report the missing state. The correct
OpenProject statuses are defined in `delivery-contract-ticket.md`.
