# Implementation And Deployment Flows

This document describes the **complete implementation flow and deployment flow** of this
SDLC/DevOps laboratory, exactly as they are implemented by the workflow skills, shared
delivery contracts, CI workflows, and the Promptfoo agent eval system.

It has two purposes:

1. **User knowledge** — a single readable map of how a ticket moves from idea to
   production, including every stage, gate, marker, and handoff.
2. **Promptfoo improvement input** — the routing matrix, stage transitions, gates,
   blockers, and stable markers are the exact inputs the agent eval
   (`.codex/agent-evals/`) reasons about. The final section shows how this document
   maps to `promptfooconfig.yaml` and `routing_provider.py` so the next eval
   improvement step can extend test coverage from a single source of truth.

Source of truth for every rule below:

- `.codex/skills/_shared/delivery-contract.md` (index) and `delivery-contract-{core,ticket,review,qa,deploy,parallel,format}.md`
- `.codex/skills/dev-flow-*` and `.codex/skills/dev-ops-*` workflow skills
- `AGENTS.md` → Workflow Stage Routing table
- `.codex/agent-evals/promptfooconfig.yaml`, `.codex/agent-evals/routing_provider.py`
- `docs/architecture/system.md`, `docs/conventions/development.md`, `docs/architecture/deployment.md`, `docs/conventions/context-management.md`, `docs/workflows/parallel-delivery.md`

---

## 1. End-To-End Delivery Flow

```text
Idea or ticket
  -> OpenProject work item (Specified / New for bugs)
  -> OpenSpec proposal, design, specs, and tasks
  -> feature branch from dev
  -> implementation with focused tests (TDD, three test levels)
  -> pull request in Gitea
  -> AI review -> feedback fixes -> human reviewers
  -> merge to dev
  -> CI builds immutable artifact, deploys to DEV, auto-promotes to QA
  -> E2E QA evidence gate (acceptance criteria proven by executable assertions)
  -> release manifest + optional RC tag
  -> explicit PROD promotion (main fast-forward + final release tag)
  -> post-PROD eval + retrospective
  -> rollback / hotfix when needed
```

The release rule is:

```text
feature branch -> dev -> DEV + QA (auto) -> E2E QA OK -> main -> PROD
```

Key principles:

- **Artifacts are immutable.** Identity is the commit SHA. Nothing is rebuilt between
  environments — DEV, QA, PROD, and rollback all reuse `app/{commitSha}/` artifacts
  from Nexus.
- **PROD promotion is explicit.** QA passing alone never releases to PROD; the user or
  a ticket-named `src/**` / `tests/**` merge to `main` must trigger it.
- **QA is evidence, not smoke.** `QA Done = acceptance criteria proven by executable
  assertions against the deployed QA artifact`.
- **Deterministic next step.** Every stage has exactly one next skill defined by the
  routing table; agents inform the user of the next step and pause only when a mutation
  is required.

---

## 2. Workflow Stage Routing Matrix

This matrix (from `AGENTS.md`) is the core routing contract — **and the core subject of
the Promptfoo agent eval**. Given a user request and live state, the agent loads the
matching skill and follows its Workflow section step by step.

| User request / context | Stage | Skill |
| ---------------------- | ----- | ----- |
| Start a ticket (specific or next Todo) | `dev-flow-start-ticket` | `.codex/skills/dev-flow-start-ticket/SKILL.md` |
| Create / propose an OpenSpec change | `dev-flow-propose-change` | `.codex/skills/dev-flow-propose-change/SKILL.md` |
| Implement a ticket / change | `dev-flow-implement-ticket` | `.codex/skills/dev-flow-implement-ticket/SKILL.md` |
| Continue implementation | `dev-flow-continue-implementation` | `.codex/skills/dev-flow-continue-implementation/SKILL.md` |
| Review a pull request | `dev-flow-pr-review-agent` | `.codex/skills/dev-flow-pr-review-agent/SKILL.md` |
| Address PR review feedback | `dev-flow-pr-review-feedback-loop` | `.codex/skills/dev-flow-pr-review-feedback-loop/SKILL.md` |
| Verify an OpenSpec change | `dev-flow-verify-change` | `.codex/skills/dev-flow-verify-change/SKILL.md` |
| Archive an OpenSpec change | `dev-flow-archive-change` | `.codex/skills/dev-flow-archive-change/SKILL.md` |
| Deploy to QA | `dev-ops-deploy-qa` | `.codex/skills/dev-ops-deploy-qa/SKILL.md` |
| Deploy to production | `dev-ops-deploy-prod` | `.codex/skills/dev-ops-deploy-prod/SKILL.md` |
| Rollback production | `dev-ops-rollback-prod` | `.codex/skills/dev-ops-rollback-prod/SKILL.md` |
| Hotfix production | `dev-ops-hotfix-prod` | `.codex/skills/dev-ops-hotfix-prod/SKILL.md` |
| Post-merge deploy | `dev-ops-post-merge-deploy` | `.codex/skills/dev-ops-post-merge-deploy/SKILL.md` |
| CI deploy completed / post-deploy update | `grafana-board-update` | `.codex/skills/grafana-board-update/SKILL.md` |
| File and fix a QA bug | `dev-flow-file-qa-bug` | `.codex/skills/dev-flow-file-qa-bug/SKILL.md` |
| Check pipeline status | `dev-flow-pipeline-status` | `.codex/skills/dev-flow-pipeline-status/SKILL.md` |
| Run retrospective audit | `dev-flow-retrospective-audit` | `.codex/skills/dev-flow-retrospective-audit/SKILL.md` |
| Explore a change / ask questions | `dev-flow-explore-change` | `.codex/skills/dev-flow-explore-change/SKILL.md` |
| Scaffold project after stack selection | `dev-flow-scaffold-project` | `.codex/skills/dev-flow-scaffold-project/SKILL.md` |
| Update AI-updatable docs / knowledge | `docs-knowledge-maintenance` | `.codex/skills/docs-knowledge-maintenance/SKILL.md` |

Routing decisions use the following state inputs (the same variables the Promptfoo eval
passes to `routing_provider.py`):

- `ticketState` — `todo`, `in progress`, `qa`, `done`, or unknown
- `branchExists`, `prExists`, `prMerged` — Git/Gitea state
- `qaEvidence` — `deployed`, `passed`, `failed`, or empty
- `productStack` — `selected` or `none`
- `incident`, `hotfix` — PROD override signals
- `parallelEnabled`, `maxActiveReached`, `laneOwner`, `worktreeExists` — parallel delivery state
- `prodRequested` — explicit PROD promotion intent
- `nexusArtifactExists`, `releaseTagConflict`, `infraValidationFailed` — deployment gates

Decision priority (mirrors `_evaluate_route()`):

1. `infraValidationFailed` → `blocked-infra-validation`
2. `incident` → `dev-ops-rollback-prod`; `hotfix` → `dev-ops-hotfix-prod`
3. `productStack == none` → `dev-flow-pipeline-status`
4. parallel `maxActiveReached` → `blocked-max-active`
5. ticket-state routing (see below)
6. unknown/ambiguous state → `dev-flow-pipeline-status`

Blocked outcomes the eval recognizes: `blocked-no-prod`, `blocked-lane-conflict`,
`blocked-max-active`, `blocked-missing-artifact`, `blocked-tag-conflict`,
`blocked-infra-validation`.

---

## 3. Implementation Flow (Feature Tickets)

### Stage 1 — Start Ticket (`dev-flow-start-ticket`)

Trigger: user asks to start the next feature ticket, start a specific ticket key, or list
Specified tickets. Bug tickets (status `New`, ID 1) are re-routed to
`dev-flow-file-qa-bug` and never follow the feature flow.

1. **List / select ticket.** List tickets in the feature starting state (`Specified`);
   the user chooses even if only one ticket exists.
2. **Ticket Refinement Gate** — classify the ticket before mutating anything:
   - `ready` — user-visible goal, concrete acceptance criteria, validation expectations.
   - `refinable` — add Scrum-ready planning to the managed ticket block, then continue.
   - `blocked` — stop before any branch/status/OpenSpec mutation; report missing intent.
3. **Stack Context Preflight** — verify `docs/architecture|development|deployment.md`
   stack sections, `openspec/config.yaml` context/rules, and local recommendations
   exist; otherwise route to `configure-dev-environment` + `project-guidance-discover`.
4. **Trunk init** — initialize trunk.io so the lefthook pre-commit hooks pass on the
   first commit.
5. **Clean working tree check** — stop on unrelated changes.
6. **Workflow telemetry (hard gate)** — capture UTC start, create the OpenProject time
   entry via `time-telemetry-upsert` (POST `/api/v3/time_entries`), marker
   `IA generated workflow telemetry: {ticketKey}:dev-flow-start-ticket`. No fallback:
   if the API fails, stop and report.
7. **Branch** — pull base branch (`git pull --ff-only`), create/reuse the configured
   branch name (e.g. `feat/e2eproject-1-create-files-and-folders-for-a-site`), pre-scan
   local/remote conflicts, push with upstream.
8. **Planning analysis** — feed the human ticket text to `dev-flow-explore-change`, then run up
   to 4 iterative `grill-with-docs` cycles; consolidate into one refined-requirements
   document.
9. **Curated ticket block** — merge both outputs into one agile-format IA block
   (problem/opportunity, user story, concrete acceptance criteria, scope, **out of
   scope**, dependencies/assumptions, validation expectations, risks, definition of
   done) and PATCH the ticket description using the enrich pattern — **append after the
   human text, never replace**; markers `<!-- ia-generated:start -->` /
   `<!-- ia-generated:end -->`.
10. **Branch comment** — marker `IA generated branch: {branchName}` (skip if present).
11. **Ticket context lock** — create/update ignored `.codex/delivery-context.local.json`
    with `ticketKey`, `branch`, `openspecChange`, PR/artifact fields. Never commit it.
12. **Move ticket to `In progress`** (OpenProject ID 7).
13. **OpenSpec propose flow** — delegate to `dev-flow-propose-change` (Stage 2).
14. **Workload forecast** — parse the Review Workload Forecast from `tasks.md`, set
    `estimatedTime` on the work package (ISO-8601 duration).

### Stage 2 — Propose OpenSpec Change (`dev-flow-propose-change`)

Creates the change and generates all planning artifacts in one flow:

```bash
openspec new change "<change-name>"        # kebab-case, e.g. feat-e2eproject-1-files
```

- `proposal.md` — problem/opportunity, user story, scope, acceptance criteria, out of
  scope, risks.
- `specs/**/*.md` — behavior specs, one per capability, with concrete scenarios.
- `design.md` — architecture decisions, component structure, alternatives.
- `tasks.md` — implementation tasks with checkboxes, grouped by concern, including the
  **Review Workload Forecast** (estimated lines, estimated hours, 400-line budget risk,
  chained-PR recommendation, delivery strategy).

Verify: `openspec status --change "<name>"` — all artifacts must show complete.
If the forecast reports `400-line budget risk: High`, `Chained PRs recommended: Yes`, or
`Decision needed before apply: Yes`, implementation must not start until a split /
`size:exception` / `exception-ok` decision is recorded.

### Stage 3 — Implement Ticket (`dev-flow-implement-ticket`)

Pre-flight gate (authority level 5, enforced even on resume):

- OpenSpec artifacts complete (`tasks.md`, `design.md`, `proposal.md`, `specs/`).
- `estimatedTime` set on the work package.
- A `dev-flow-start-ticket` time entry exists.

Workflow:

1. **Resolve context** — verify ticket, branch, OpenSpec change, and PR against the
   ticket lock; stop on mismatch. Detect resume checkpoints (completed tasks, commits,
   existing PR, review markers, feedback tasks, labels) and continue from the latest.
2. **Skill scan** — map the declared stack to applicable skills, then scan **every**
   installed `.codex/skills/*/SKILL.md`; declare each active/skipped skill with
   rationale in a `Skills used:` block. Missing a declaration is a process violation.
3. **TDD implementation** — follow `/opsx:apply` over `tasks.md` with vertical TDD
   cycles (see `.codex/skills/_shared/pipeline-tdd-cycle.md`):
   - Write all tests first (RED) — no product code before tests.
   - Three test levels: **unit** (per component, `test/unit/`), **integration** (per
     endpoint/feature, `test/integration/`), **architecture** (single project-wide file,
     `test/architecture/`).
   - Build the acceptance-to-test map from the IA curated ticket block + `tasks.md`.
   - GREEN with minimal code (`ponytail full`), REFACTOR while GREEN.
4. **Quality gates** (details in Section 7):
   - Coverage ≥ `coverage.minimumPercent` (default **80**) — HARD GATE before PR.
   - Lefthook pre-push `python -m tools.sdd_cli stack-tests` (unit + integration +
     architecture + coverage) — HARD GATE on every push.
   - Full local CI loop inside `sdd-e2e-ci:local` (JSON validation, gitleaks, semgrep,
     trivy, checkov + stack-native build/test) — zero errors before PR.
   - `/health` contract for web/API apps (HTTP 200, JSON `status=ok`, no secrets).
5. **Verify OpenSpec** — run `dev-flow-verify-change` (Stage 4) before PR handoff.
6. **Commit checkpoints** — commit after each completed step with ticket-key-prefixed
   messages; keep the working tree clean between steps.
7. **Create / reuse the PR** to the base branch, then **immediately** add ticket comment
   `IA generated PR: {prUrl}` and move the ticket to `Developed` (ID 8). PR body must
   include ticket id, OpenSpec change id, implementation summary, acceptance-to-test
   map, TDD RED/GREEN evidence, coverage result, quality gates, risk classification,
   context/docs/knowledge classification, and reviewer list (pending).
8. **Review and fix loop** — delegate to `dev-flow-pr-review-feedback-loop` (Stage 6).
9. **Request human reviewers** only after the AI review completes.
10. **Handoff** — verify ticket state `Developed`, retry missing PR comment.

### Stage 4 — Verify OpenSpec Change (`dev-flow-verify-change`)

Validates the implementation against the change artifacts across three dimensions:

- **Completeness** — all tasks checked, all requirements implemented.
- **Correctness** — requirement-to-implementation mapping, scenario coverage.
- **Coherence** — design adherence, code pattern consistency.

Issues are classified CRITICAL (fix before archive), WARNING (should fix), and
SUGGESTION (nice to fix). Critical issues block PR handoff and archive.

### Stage 5 — PR Review Agent (`dev-flow-pr-review-agent`)

Reviews one explicit PR (invoked after PR creation or on resume; marker
`<!-- codex-review-agent:{headSha} -->` prevents duplicate reviews for the same head):

1. **Resolve the PR** — verify PR/branch/head against the ticket lock.
2. **Review the code** — finding priority: bugs/regressions, missing edge tests,
   security/credential/data-loss, API/schema/migration/compatibility, maintainability.
   Severities: `BLOCKER` (must fix), `WARNING` (meaningful risk), `SUGGESTION`
   (optional). Every AI finding is tracked as required review feedback before human
   handoff. Large diffs (≥500 changed lines) use structured risk-based review;
   high-risk surfaces (auth, persistence, migrations, deployment workflows, secrets,
   public APIs, `/health`) are always fully inspected.
3. **Adversarial review** — required when explicitly requested or risk is high; ends
   with verdict `PASS`, `PASS WITH GAPS`, or `FAIL`.
4. **Ponytail complexity pass** — separate simplification findings (unnecessary code,
   hand-rolled stdlib behavior, speculative abstractions).
5. **Post the review** — one top-level comment with stable finding ids (`AI-001`…),
   test gaps, review mode, adversarial verdict, sources consulted.
6. **Labels** — `codex-reviewed` (#5319e7), `needs-tests` (#fbca04), `needs-changes`
   (#d73a4a); create missing labels, apply/remove based on current head findings.
   `codex-reviewed` is the CLEAN marker: applied only when the head has zero findings
   of any severity (no BLOCKER/WARNING/SUGGESTION, no test gaps) AND its PR Validation
   run is green, and REMOVED whenever any finding exists or the run is red/pending —
   so the CI gate stays red until the review loop is clean.
7. **PR Validation gate check (mandatory)** — read the latest Gitea Actions
   `pr-validation` run for the current head before finalizing the review. Every
   failing step is a `BLOCKER` finding quoting the step name and exact error; a red,
   pending, or unreadable run also keeps `codex-reviewed` off.

### Stage 6 — PR Review Feedback Loop (`dev-flow-pr-review-feedback-loop`)

Reconnectable loop with two phases: AI review (immediate, after every pushed fix) and
human review (on manual resume).

1. Resolve ticket, branch, PR, head SHA, workflow status, labels.
2. Invoke/reuse `dev-flow-pr-review-agent` for the current head.
3. Collect feedback sources: AI findings, human top-level comments, human inline review
   comments, OpenSpec `## PR Review Feedback` tasks, ticket markers, and the latest
   PR Validation run — every failing step is a first-class feedback source.
4. Classify each item: `actionable`, `non-actionable`, `stale`, or
   `ambiguous/conflicting`.
5. Compute `feedbackBatchId` deterministically from sorted source ids.
6. Add one OpenSpec `## PR Review Feedback` task per feedback item (source type, id,
   head SHA, severity, requested change).
7. Add ticket comment marker `IA generated PR feedback detected: {headSha}:{feedbackBatchId}`.
8. Ensure the `codex-reviewed` label is removed while actionable feedback exists or the
   current-head PR Validation run is red/pending (CI stays red until the loop is clean),
   then apply fixes, run relevant validation, mark tasks complete only after code +
   validation.
9. Commit with ticket key, push, add marker
   `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}` (human-readable body:
   status, reviewer feedback addressed, how IA resolved it, changed, validation,
   reviewer readiness, skipped comments).
10. Rerun the AI review loop on the new head and re-check its PR Validation run (must
    have completed, not running/pending); the re-review reapplies `codex-reviewed` only
    when the new head has zero findings of any severity AND its PR Validation run is
    green.

Ticket stays in `Developed` (ID 8) during late feedback fixes. Handoff to merge is
blocked while any feedback batch is unresolved, `codex-reviewed` is absent (current-head
review not clean or PR Validation run not green), or `needs-tests`/`needs-changes` is
valid on the current head. At most one `codex-reviewed` label live means the loop
finished clean.

---

## 4. Deployment Flow

### Stage 7 — Post-Merge Deploy (`dev-ops-post-merge-deploy`)

Orchestration bridge after a PR merges to `dev`. It validates, triggers CI, waits for
artifacts, then delegates to `dev-ops-deploy-qa`.

1. Resolve the PR; verify it is **merged** and targets **dev** (else stop).
2. Delete the source branch (local + remote) — best-effort cleanup.
3. Verify no `needs-changes` / `needs-tests` labels (else stop).
4. Resolve merge commit SHA; resolve ticket key; `ValidateTicketLock` (else stop).
5. **Trigger the CI pipeline** — dispatch `package-deploy` Gitea Actions workflow on
   `dev` (HTTP `204` = success). The pipeline deploys to **DEV and auto-promotes to QA**
   in the same run.
6. **Wait for Nexus artifacts** (bounded, up to 10 minutes, backoff): per app
   `app/{commitSha}/{artifactName}` + `.sha256`, `deployable-apps.json`, `commit.sha`,
   `release-dev.json`, `release-qa.json`, `env-urls-dev.json`, `env-urls-qa.json`,
   `container-images.json`, plus monitoring summaries when observability is enabled.
7. Verify `commit.sha` matches the merge commit; verify `release-dev.json.ticketKey`
   matches the locked ticket.
8. Invoke `dev-ops-deploy-qa` (verification mode when artifacts already exist).

### Stage 8 — Deploy To QA (`dev-ops-deploy-qa`)

Because CI auto-promotes DEV → QA, this skill validates and updates the ticket rather
than dispatching a separate QA deployment.

Preflight:

- PR merged to `dev`; no `needs-changes`/`needs-tests`.
- Ticket lock valid; Nexus reachable; all required artifact files present;
  `commit.sha` matches the resolved SHA; `release-dev.json`/`release-qa.json`
  `ticketKey` matches the locked ticket.

DEV + QA validation:

- DEV URL from `app/latest/env-urls-dev.json` — `curl --fail` + `/health` (HTTP 200,
  JSON `status=ok`).
- QA deployed the **same artifact set** (no rebuild); QA URL + `/health` validated.
- Deployment configuration applied and verified for both environments.
- On failure: add failure comment, do not move the ticket.

Release manifest + ticket:

- `UpdateReleaseManifest` → `app/{commitSha}/release-qa.json` (commit SHA, checksum,
  artifact URL, PR URL, ticket key, DEV/QA URLs + statuses, per-app health, workflow
  run URL, `versionStatus=unversioned QA candidate` unless an RC tag exists).
- Move ticket to `In testing` (ID 9).
- Comment marker `IA generated QA deployment: {commitSha}` (skip if present).

Then, automatically:

- **Grafana dashboard update** (`grafana-board-update`) — merge live DEV/QA URLs into
  `infra/monitoring/grafana/dashboards/health-board.json` (version bump required for
  provisioned dashboards), commit and push.
- **E2E QA evidence gate** (Stage 9) — mandatory; the pipeline must not proceed to PROD
  without it.

### Stage 9 — E2E QA Evidence Gate (`delivery-contract-qa.md`)

The acceptance-evidence gate. `QA Done = acceptance criteria proven by executable
assertions against the deployed QA artifact`.

1. **Resolve acceptance criteria** — fetch the ticket, expand ACs + OpenSpec change,
   enumerate every criterion from `tasks.md`, map each to committed Playwright test
   coverage. Missing coverage → mark blocked and stop.
2. **Run the committed suite against QA**:

   ```bash
   BASE_URL="${QA_FRONTEND_URL}" npx playwright test --reporter=list,json
   ```

   (`BASE_URL` is the only switch; `playwright.config.ts` defaults to the local dev
   server when unset.)
3. **Classify** the outcome:
   - `PASS` — every required assertion passed, every AC proven.
   - `PASS WITH GAPS` — usable but a non-blocking weakness remains; ticket stays out of
     Done.
   - `FAIL` — required assertion failed, oracle missing, evidence contradictory, wrong
     environment, or product defect.
4. **On PASS**: ticket comment marker `IA generated E2E QA: {ticketKey}` (commit SHA,
   QA URL, pass/fail counts, AC mapping summary); move ticket to Done (or `Tested` if
   Done is reserved for PROD); update `release-qa.json` with `e2eQaStatus: "passed"` and
   `versionStatus: "RC candidate"`; optionally create the annotated RC tag
   `vMAJOR.MINOR.PATCH-rc.N` on the tested commit; archive the OpenSpec change (Stage 10
   below); delete the temporary QA trigger branch.
5. **On FAIL**: ticket comment with failing tests + classification (product defect /
   test defect / environment issue); leave ticket in QA; no RC tag; route to
   `dev-flow-file-qa-bug` (Stage 11).

### Stage 10 — Archive OpenSpec Change (`dev-flow-archive-change`)

Runs automatically after E2E QA passes and the ticket is Done. Fails closed when:

- artifacts are missing (`proposal.md`, `specs/`, `design.md`, `tasks.md`),
- any `tasks.md` task is incomplete,
- delta-spec sync fails or is required but not applied,
- the change directory still exists after the move.

On success the change moves to `openspec/changes/archive/YYYY-MM-DD-<name>/` and specs
are synced to `openspec/specs/`.

### Stage 11 — File And Fix QA Bug (`dev-flow-file-qa-bug`)

Full bug fix lifecycle when E2E QA fails:

```text
E2E QA fails -> File bug -> Move to Specified -> Update parent OpenSpec -> Commit
  -> Move to In progress -> Branch -> PR -> Merge & deploy to QA -> Close bug
  -> Return to parent QA
```

1. **File bug with evidence** — child ticket of the parent, marker
   `IA generated QA bug: {parentTicketKey}`; parent stays in its current state.
2. **Move bug to `Specified`** — add fix plan to the bug description (root cause, fix
   approach, ACs, affected files, validation, effort); marker
   `IA generated bug specification: {bugKey}`.
3. **Update parent OpenSpec** — **append** bug-fix tasks to the parent's `tasks.md` as a
   new `## Bug Fix: {bugKey}` section (bugs never create a new OpenSpec change).
4. **Fix branch** — commit OpenSpec changes on `dev` first, then
   `fix/{bugKeySlug}-{short-description}`; marker `IA generated bug branch: ...`.
5. **Implement with tests** — same TDD + quality gates as the feature flow
   (RED before fix code; tests non-negotiable).
6. **PR** — `{bugKey}: {short description} (parent: {parentTicketKey})`; marker
   `IA generated bug PR: {prUrl}` (blocking); AI review + reviewers.
7. **Merge & deploy** — after merge, `dev-ops-post-merge-deploy` +
   `dev-ops-deploy-qa`; verify `IA generated QA deployment: {mergeCommitSha}`.
8. **Close bug** — mark bug tasks done in parent `tasks.md`, delete fix branch, comment
   `IA generated bug closed: {bugKey}`, move bug to `Closed` (ID 12), switch the ticket
   lock back to the parent.
9. **Return to parent QA** — move parent from `Test failed` (ID 11) back to
   `In testing` (ID 9) and re-run the E2E QA evidence gate.

Non-code defects (data/environment/requirements only): no OpenSpec change, no branch;
comment on the bug and report the non-code owner.

### Stage 12 — Deploy To PROD (`dev-ops-deploy-prod`)

Explicit, release-centric promotion of the **QA-approved artifact**. Can include one or
more QA-approved (Done) tickets as a batch release.

Preflight (stop on any failure):

1. Resolve primary ticket, included Done tickets, QA-approved commit SHA, source RC
   version (`vMAJOR.MINOR.PATCH-rc.N`), final version (`vMAJOR.MINOR.PATCH`).
   `release.json.includedTickets` is the authoritative release membership.
2. `ValidateTicketLock` — do not reject a valid batch release because extra included
   tickets differ from the active lock.
3. Every included ticket must be in the configured Done state.
4. **E2E QA gate** — every included ticket must have a passing
   `IA generated E2E QA: {ticketKey}` comment with PASS result, PR URL, QA URL, Nexus
   artifact URL, QA evidence URL, and source RC version. Missing → stop and run the E2E
   QA evidence contract first.
5. Nexus artifact set present (per-app artifacts + `.sha256`, `deployable-apps.json`,
   `deployment-config.json`, `commit.sha`, `release-dev.json`, `release-qa.json`,
   `container-images.json`, monitoring evidence); `commit.sha` exactly matches the
   QA-approved commit.
6. `release-qa.json` matches the ticket E2E QA evidence (commit, checksum, ticket key,
   QA evidence URL, source RC).
7. Source RC tag exists and points to the QA-approved commit; final release tag does
   **not** exist yet.

Main + tag promotion:

1. Verify the QA-approved commit exists on `dev`.
2. Verify `main` can fast-forward to it; if diverged, **stop** (no merge commit unless
   the user changes release policy).
3. Fast-forward `main`; create the annotated final release tag (message: ticket keys,
   PR URL, source RC, final version, QA evidence, Nexus artifact, checksum, commit SHA).
4. Push `main` + tag only after all preflight checks pass. Branch protection fallback:
   delete the local tag, open a release-blocking promotion PR to `main`, stop until it
   merges; PROD is never deployed from a commit not reachable from `main`.

PROD deployment (artifact-reuse contract — no rebuild, no DEV/QA jobs):

```text
environment=prod
artifact_commit_sha={qaApprovedCommit}
release_version={finalVersion}
source_rc_version={sourceRcVersion}
```

PROD verification (direct, before commenting success):

- PROD page HTTP 200 + expected title/content (never screenshots alone).
- Every topology app `/health` HTTP 200 + `status=ok`.
- Deployment configuration and monitoring evidence applied/verified.

Release manifest + pointers:

- `UpdateReleaseManifest` → `app/{commitSha}/release-prod.json` (final version, final
  tag, included tickets, PROD URL/status, health, workflow URL, monitoring, timestamp).
- `CreateArtifactPointer` → `app/releases/{finalReleaseVersion}/artifact-pointer.json`
  and `release.json` (aliases point back to canonical `app/{commitSha}/`).

Ticket results: comment marker `IA generated PROD deployment: {finalVersion}` on **every
included ticket** (lineage: artifact commit → source RC → final release; PR URL, commit,
artifact, checksum, manifests, QA evidence, main ref result, workflow URL, PROD
URL/health, pass/fail). Failure comments on PROD check failure and stop.

Post-PROD eval (advisory, not a gate):

```bash
python -m tools.sdd_cli agent-eval run
```

(Direct fallback when the CLI runner is unavailable:
`npx promptfoo eval --config .codex/agent-evals/promptfooconfig.yaml --no-cache`.)

Persist results to `.codex/agent-evals/results.local.json` with mode `post-prod-eval`,
scope = final release version.

Post-PROD retrospective (`dev-flow-retrospective-audit` in `post-prod-ticket-release`
mode): persists sanitized learning evidence (marker
`IA generated post-PROD retrospective: {finalVersion}`), includes the eval summary
(total/passed/failed). If eval failures exist, **auto-escalates** into
`eval-driven-improvement` (probe → diagnose → propose → apply), limited to eval
infrastructure files (`routing_provider.py`, `promptfooconfig.yaml`), verifying after
each fix and reverting any fix that breaks other tests.

### Stage 13 — Rollback PROD (`dev-ops-rollback-prod`)

Rollback is a deployment operation, not a rebuild:

1. Resolve current PROD release (latest PROD comment / release manifest).
2. If no target supplied: list known-good candidates (PROD comments, Git tags, Nexus
   `release.json`) newest-first, mark current PROD, ask the user to choose.
3. Validate target artifact set + checksums + `commit.sha`; verify `release.json` marks
   the target QA-approved and previously PROD-deployed (or user-approved).
4. Redeploy the existing artifact (same dispatch inputs with the rollback commit) —
   **never rebuild**; verify page + all `/health`.
5. Comments: `IA generated PROD rollback: {rollbackVersionOrCommit}` +
   `IA generated PROD rollback incident: {rollbackVersionOrCommit}` (who/what requested,
   why, timeline, evidence, follow-up).
6. Document Git state — `main` is **not** automatically reverted; require a hotfix PR,
   a revert PR, or an accepted temporary divergence note with owner and resolution.

### Stage 14 — Hotfix PROD (`dev-ops-hotfix-prod`)

Expedited in scope only — quality gates are identical to the feature flow:

1. Confirm incident/regression, affected version, impact, and why rollback is not
   sufficient.
2. Create/reuse incident ticket with marker `IA generated PROD hotfix: {incidentOrTicketKey}`.
3. Branch from `main`; use `dev-flow-start-ticket` for branch/lock/OpenSpec setup.
4. **Implement fix with tests** via `dev-flow-implement-ticket` — tests are
   non-negotiable; coverage ≥ 80; lefthook pre-push stack tests must pass; full local CI
   loop before PR.
5. After merge: `dev-ops-post-merge-deploy` + QA gate, then PROD **only when the user
   explicitly asks** after QA passes.
6. Comment the incident ticket with release lineage and any cadence divergence.

---

## 5. Supporting And Operational Workflows

Stages 1–14 above are the **linear ticket → PROD flow**. The routing table also routes
to supporting workflows that run around, alongside, or instead of that line:

| Workflow | Skill | When it runs | Documented in |
| -------- | ----- | ------------ | ------------- |
| Continue implementation | `dev-flow-continue-implementation` | Resume an in-progress ticket | [`supporting-workflows.md`](supporting-workflows.md) |
| Explore / ask questions | `dev-flow-explore-change` | Planning, discovery, architecture discussions | [`supporting-workflows.md`](supporting-workflows.md) |
| Check pipeline status | `dev-flow-pipeline-status` | Read-only delivery visibility | [`supporting-workflows.md`](supporting-workflows.md) |
| Scaffold project | `dev-flow-scaffold-project` | After `set-project-stack` | [`supporting-workflows.md`](supporting-workflows.md) |
| Retrospective audit | `dev-flow-retrospective-audit` | Post-PROD, eval improvement, periodic | [`supporting-workflows.md`](supporting-workflows.md) |
| Update docs / knowledge | `docs-knowledge-maintenance` | Any durable learning | [`supporting-workflows.md`](supporting-workflows.md) |
| Grafana board update | `grafana-board-update` | After each CI deploy | [`supporting-workflows.md`](supporting-workflows.md) |

Helper skills used **inside** the linear flow (not standalone stages): `dev-flow-apply-change`
(OpenSpec `/opsx:apply` task execution), `dev-flow-parallel-ticket-coordinator` (parallel
worktree delivery, Section 10 below), and `tdd` (RED/GREEN discipline inside implementation).

---

## 6. Ticket States (OpenProject Status Mapping)

| External label | OpenProject status | ID | Meaning |
| -------------- | ------------------ | -- | ------- |
| New | New | 1 | Bug starting point (filed from E2E QA failure) |
| (refining) | In specification | 2 | Ticket being refined with acceptance criteria |
| TO DO | Specified | 3 | Feature starting point — ACs defined |
| (confirmed) | Confirmed | 4 | Bug reproduced and confirmed |
| (queue) | To be scheduled | 5 | Queued for a future sprint |
| (sprint) | Scheduled | 6 | Assigned to a sprint |
| In progress | In progress | 7 | Implementation active on the branch |
| IN REVIEW | Developed | 8 | Code complete, PR exists for review |
| IN QA | In testing | 9 | Artifact deployed to QA, awaiting E2E validation |
| Tested | Tested | 10 | E2E QA passed, ACs proven |
| (failed) | Test failed | 11 | E2E QA failed — routes to bug lifecycle |
| Closed | Closed | 12 | Done (closed) |
| (paused) | On hold | 13 | Work paused |
| Rejected | Rejected | 14 | Declined (closed) |

Standard flow: `Specified → In progress → Developed → In testing → Tested → Closed`.
Bug flow: `New → Specified → In progress → Developed → In testing → Tested → Closed`.
Bug revert: `Test failed → (child bug) → New → … → Closed → parent back to In testing`.

---

## 7. Quality Gates

| Gate | Where | Rule |
| ---- | ----- | ---- |
| Coverage | local + CI | `coverage.minimumPercent` from `.codex/quality.local.json`, default **80** — HARD GATE before PR creation/review/handoff; never lower the threshold |
| Pre-push stack tests | lefthook | `python -m tools.sdd_cli stack-tests` — unit + integration + architecture per `stack.testFrameworks` + coverage gate; clean skip with no stack; never bypass with `--no-verify` |
| Pre-commit | lefthook | `gitleaks protect --staged --redact`, `npx trunk fmt` |
| Commit message | lefthook | `python -m tools.sdd_cli dev-flow validate-commit-message`, gitleaks detect, trunk check |
| Local CI loop | `sdd-e2e-ci:local` | JSON validation, `gitleaks detect`, `semgrep scan`, `trivy fs`, `checkov` + stack-native build/test/lint — zero errors before PR |
| PR validation | Gitea CI (`pr-validation.yml`) | Authoritative for restore/format/release build/tests/coverage/SCA/secret scan/fs scan in a clean pinned runner |
| `/health` contract | app | HTTP 200 + JSON `status=ok`, no secrets; DEV/QA/PROD promotion depends on it |
| Tests | all implementation | Three levels (unit per component, integration per endpoint, architecture project-wide), TDD RED before code |

Local vs CI split: local validation is fast feedback on touched behavior; Gitea PR
validation is the authoritative full gate. The CI image intentionally has no stack
runtimes — the lefthook pre-push hook runs product tests on the dev machine.

### 7.1 Local PR Validation Loop (reproduce CI in `sdd-e2e-ci:local`)

**Purpose.** PR Validation (`pr-validation.yml`) often fails in CI for reasons that are
cheap to catch locally. This process runs the **exact same gates, in the exact same
order, inside the same `sdd-e2e-ci:local` image** the CI job uses, so errors are fixed
before push and the PR passes on the first CI run.

**Prerequisites.**

1. Docker is running (`docker version` answers).
2. The CI image exists — build it if missing:

   ```bash
   python -m tools.sdd_cli environment-lab build-gitea-images
   docker images sdd-e2e-ci:local
   ```

**Run the loop.** Mount the repository read-write into the container and execute each
gate with the identical command from `pr-validation.yml`. The `.semgrep-rules.json`
content equals the workflow's fallback rule set, so the hardcoded `--config` list below
is the faithful equivalent:

```bash
REPO="$(pwd)"
run_gate() { # usage: run_gate "<shell command>"
  echo "=== RUN: $*"
  # set -euo pipefail mirrors the CI step shells (abort on first failure,
  # e.g. an invalid *.json mid-pipeline must not be masked by a later valid file)
  docker run --rm -v "$REPO":/workspace -w /workspace sdd-e2e-ci:local bash -lc "set -euo pipefail; $*"
  rc=$?
  echo "=== EXIT: $rc"
  [ $rc -ne 0 ] && { echo "GATE FAILED: $*"; exit $rc; }
}

# 1. JSON validation (every *.json must parse)
#   single-quoted so $file is expanded inside the container, not by the outer shell
run_gate 'find . -path "./.git" -prune -o -name "*.json" -print | while IFS= read -r file; do python3 -m json.tool "$file" >/dev/null; done'
# 2. Secret scan (Gitleaks)
run_gate "gitleaks detect --source . --redact --no-git"
# 3. SAST scan (Semgrep) — rules equal to .semgrep-rules.json
run_gate "semgrep scan --config p/typescript --config p/javascript --config p/python --config p/csharp --error --verbose ."
# 4. SCA scan (Trivy) — uses the DB pre-cached in the image
run_gate "trivy fs --format table --exit-code 1 --no-progress --skip-db-update ."
# 5. IaC scan (Checkov) — blocking, config-file skip list applies
run_gate "checkov -d . --compact --config-file .checkov.yml"
# 6. Repo tooling tests
run_gate "python3 -m pytest tools/sdd_cli/tests/ -q"

echo "ALL GATES PASSED"
```

**Gate-by-gate pass criteria (mirrors `pr-validation.yml`).**

| # | Gate | Passes when | Common local failures to fix before push |
|---| ---- | ----------- | ----------------------------------------- |
| 1 | JSON validation | every `*.json` parses via `python3 -m json.tool` | inline `//` comments, trailing commas, encoding issues |
| 2 | Gitleaks | exit 0 — no leaked secrets in the working tree | real tokens in tracked files, test fixtures with fake secrets (add to `.gitleaksignore` only for intentional templates) |
| 3 | Semgrep | exit 0 with `--error` — no findings at the selected rule level | code matching `p/typescript` / `p/javascript` / `p/python` / `p/csharp` rules |
| 4 | Trivy | exit 0 — no vulnerabilities at default severity | vulnerable lockfiles/dependency manifests; DB must be pre-cached in the image (`--skip-db-update`) |
| 5 | Checkov | exit 0 — IaC checks pass (**blocking** since `--soft-fail` was removed) | unskipped `CKV_K8S_*` / `CKV_SECRET_*` findings; extend `.checkov.yml` `skip-check` only for intentional template values |
| 6 | Repo tooling tests | `pytest tools/sdd_cli/tests/` all green | broken tests, fixture drift, import errors |

**Definition of done.** All six gates exit 0 inside `sdd-e2e-ci:local` **before** opening
or updating the PR. If any gate fails, fix the code/config, re-run the loop from the
start (gates are order-independent but are run in CI order), and only push when the loop
prints `ALL GATES PASSED`.

**What is NOT covered locally (CI-only):** the `codex-reviewed` label gate (requires the
PR + Gitea API — the label is present only when the current-head AI review found zero
findings AND the current-head PR Validation run is green, so CI stays red until the
review loop is clean) and checkout networking. The review loop re-checks the run on
every new head and feeds failing steps back as `BLOCKER` findings. Everything else is
byte-for-byte the same command as the CI job, so a green local loop is strong evidence
the PR Validation run will pass.

---

## 8. Stable Markers (Idempotency Contract)

Markers are exact strings; matching markers mean the step is already complete.

| Group | Marker |
| ----- | ------ |
| General | `IA generated branch: {branchName}` |
| | `IA generated PR: {prUrl}` |
| | `IA generated handoff: {ticketKey}` |
| | `IA generated workflow timing: {ticketKey}` |
| | ticket block: `<!-- ia-generated:start -->` … `<!-- ia-generated:end -->` |
| | telemetry: `IA generated workflow telemetry: {ticketKey}:{workflowStage}` |
| Review | `<!-- codex-review-agent:{headSha} -->` |
| | `IA generated PR feedback detected: {headSha}:{feedbackBatchId}` |
| | `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}` |
| QA / E2E | `IA generated QA deployment: {commitSha}` |
| | `IA generated E2E QA: {ticketKey}` (canonical E2E QA marker) |
| Bug | `IA generated QA bug: {parentTicketKey}` |
| | `IA generated bug specification: {bugKey}` |
| | `IA generated bug branch: fix/{bugKeySlug}-{short-description}` |
| | `IA generated bug PR: {prUrl}` |
| | `IA generated bug closed: {bugKey}` |
| PROD | `IA generated PROD deployment: {finalVersion}` |
| | `IA generated post-PROD retrospective: {finalVersion}` |
| | `IA generated PROD rollback: {rollbackVersionOrCommit}` |
| | `IA generated PROD rollback incident: {rollbackVersionOrCommit}` |
| | `IA generated PROD hotfix: {incidentOrTicketKey}` |
| | `IA generated eval improvement: {scopeIdentifier}` |

OpenProject comment format: marker as the first line by itself, then a blank line and a
Markdown body with `**Status:**`, `**Context:**`, `**Validation:**`, `**Evidence:**`,
`**Notes:**` sections.

---

## 9. Environment Model And Artifacts

Three K8s environments (kind cluster `sdd-cluster` unless Docker Desktop K8s is used):

| Environment | Namespace | Replicas | Trigger |
| ----------- | --------- | -------- | ------- |
| dev | `sdd-dev` | 1 | Push to `dev` branch |
| qa | `sdd-qa` | 2 | CI auto-promote after DEV in the same `package-deploy` run |
| prod | `sdd-prod` | 3 | Explicit PROD deployment of the QA-approved artifact |

Nexus artifact layout (identity = commit SHA; human-readable version folders are aliases
only):

```text
app/{commitSha}/deployable-apps.json
app/{commitSha}/{artifactName}           + .sha256 per topology app
app/{commitSha}/commit.sha
app/{commitSha}/release.json
app/{commitSha}/release-dev.json         # DEV deployment metadata
app/{commitSha}/release-qa.json          # QA deployment + E2E QA status
app/{commitSha}/release-prod.json        # PROD deployment metadata
app/{commitSha}/container-images.json
app/{commitSha}/env-urls-{env}.json      # discovered URLs per environment
app/{commitSha}/monitoring-summary-{env}.json, qa-observability.json
app/qa-approved/latest.json              # QA approval pointer
app/rc/{sourceRcVersion}/artifact-pointer.json + release.json
app/releases/{finalReleaseVersion}/artifact-pointer.json + release.json
```

Version rules: source RC `vMAJOR.MINOR.PATCH-rc.N`, final release `vMAJOR.MINOR.PATCH`;
both tags annotated and pointing at the tested/approved artifact commit.

CI pipeline (`package-deploy.yml`):
`Checkout → Determine Env → Build + Push images to Nexus registry → Deploy to K8s
(kustomize edit set image + apply) → Discover URLs → Upload env-urls + manifests to
Nexus`.

---

## 10. Parallel Delivery (Optional Mode)

When `parallelDelivery.enabled=true` (default false), multiple tickets progress through
planning, implementation, and review in isolated Git worktrees; DEV/QA/E2E/PROD/rollback/
hotfix promotion is **serialized** through a deployment lane.

- `maxActiveTickets` (default 2) limits active worktrees.
- Each active ticket owns exactly one worktree and one implementation branch.
- Only the recorded `deploymentLaneOwner` may run post-merge deploy, QA deploy, QA gate,
  or PROD deploy — others route to `blocked-lane-conflict`.
- Role contracts: coordinator, ticketStarter, implementation, prReview, deployment, qa,
  prodHotfix.
- Before Git/OpenProject/Gitea mutation:
  `python -m tools.sdd_cli dev-flow validate-parallel-dry-run`.

---

## 11. Mapping To The Promptfoo Agent Eval

The Promptfoo eval (run via `python -m tools.sdd_cli agent-eval run`; direct fallback
`npx promptfoo eval --config .codex/agent-evals/promptfooconfig.yaml --no-cache`)
verifies that the routing logic in `routing_provider.py` matches the delivery contract.
This document is the human-readable spec of that contract; the eval encodes it as test
cases.

**Test case anatomy** (46 cases today): each case provides `scenario`, `ticketState`,
`branchExists`, `prExists`, `prMerged`, `qaEvidence`, `productStack` plus optional
`incident`, `hotfix`, `parallelEnabled`, `maxActiveReached`, `laneOwner`,
`prodRequested`, `nexusArtifactExists`, `releaseTagConflict`, `worktreeExists`,
`infraValidationFailed`, `requestType`, `resumeRequested`, `prValidationStatus`, then
asserts `JSON.parse(output).route === '<expected>'` (skill-activation and CI-gate cases
also assert `activatedSkills` / the `review` gate).

**Coverage groups today:** ticket lifecycle (7), edge cases (4), parallel delivery (5),
deployment lane (5), infrastructure validation (2), explicit workflow-stage requests (11),
state-driven resume (1), regression (1), PR validation gate (7).

**How to use this document for the next improvement step:**

1. **Extend the routing matrix** (Section 2) — any new user prompt / stage / route
   added there should get a corresponding eval test case. Every routing-matrix route now
   has its own coverage: explicit `requestType` cases cover `dev-flow-propose-change`,
   `dev-flow-pr-review-agent`, `dev-flow-pr-review-feedback-loop`,
   `dev-flow-continue-implementation`, `dev-flow-explore-change`,
   `dev-flow-scaffold-project`, `dev-flow-verify-change`, `dev-flow-archive-change`,
   `grafana-board-update`, `dev-flow-retrospective-audit`, and
   `docs-knowledge-maintenance`; `resumeRequested` covers
   the state-driven auto-continue variant. The PR validation gate group (7 cases)
   asserts the CI-in-loop rule via the `review` gate: a red/pending/unknown run is a
   `BLOCKER` finding with `codexReviewed=false` (no dead-end blocked route — the
   review/fix loop still runs to fix failing steps). Future additions should also
   consider marker-driven idempotency decisions (Section 8) and state-driven variants
   of other stages.
2. **Check the decision priority** (Section 2) against `_evaluate_route()` — the eval
   should catch ordering regressions (e.g. incident/hotfix overriding ticket state).
3. **Blocked outcomes** (Section 2) are the eval's expected `blocked-*` routes — any new
   blocker added to the contracts should be added to the eval's blocked set and the
   provider's guard clauses, in the same priority order the provider checks them
   (infrastructure validation first, then incident/hotfix, then capacity, then state).
4. **Stage transitions** (Sections 3-4) define the state inputs — when a stage adds a
   new state-dependent decision (e.g. a new gate between QA and Done), add the matching
   vars + test case.
5. **Stable markers** (Section 8) are not directly tested today; eval cases could be
   extended to assert marker-driven idempotency decisions (e.g. existing QA deployment
   marker ⇒ verification mode, not redeploy).

The eval is advisory after PROD (post-PROD eval) and becomes an enforced improvement
cycle through `dev-flow-retrospective-audit` → `eval-driven-improvement` when regressions
or coverage gaps are found.

Routing logic note: explicit `requestType` requests are checked after incident/hotfix
but before the missing-stack fallback and ticket-state routing, because the latest
explicit user request is the highest authority in the routing hierarchy
(`docs/conventions/context-management.md` → Authority Order). State-driven resume
(`resumeRequested` on an in-progress ticket with an existing branch) routes to
`dev-flow-continue-implementation` inside the in-progress branch, before merged-PR
handling.
