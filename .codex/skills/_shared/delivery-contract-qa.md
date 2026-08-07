<!-- TIER 3: STAGE-SPECIFIC - QA stage (deploy to QA, E2E QA, QA bug) -->

# Delivery Contract — QA (deploy to QA, E2E QA, QA bug)

Stage-specific rules for QA evidence, trigger branch cleanup, and OpenSpec archive. Read in addition to
`delivery-contract-core.md`.

---

## QA Evidence Contract

E2E QA is an acceptance-evidence gate, not a screenshot, smoke, or page-load gate. The rule is: `QA Done = acceptance
criteria proven by executable assertions against the deployed QA artifact`.

Ticketed implementation is TDD-first. Implementation must map every acceptance criterion to committed automated
coverage. When browser-level proof is required, create or update the committed
Playwright/E2E test during implementation so QA can run it later.

When a deployed browser E2E fails, use Playwright MCP or the configured Browser/Playwright tool as the first diagnostic
source. Reproduce against the real QA URL, inspect console, network, websocket,
DOM, screenshots, and trace/video evidence, then classify as product defect, committed-test defect,
deployment/environment issue, or workflow gate gap. App code must remain product-only: do not add
JavaScript helpers, hidden hooks, test ids, bypass paths, timing shims, or Playwright-specific behavior whose only
purpose is making E2E pass.

Implementation owns acceptance test creation. `configured QA gate` owns deployed browser E2E execution, evidence, and QA
pass/fail classification only; it must not create, repair, commit, or stage
tests. After QA deployment, use the selected provider temporary QA trigger branch from the tested `dev` commit to run
the committed suite remotely against the deployed QA URLs and publish evidence.

Before `configured QA gate` may move a ticket to Done, it must:

- resolve the OpenProject/OpenSpec acceptance criteria and validation expectations for the ticket,
- map each criterion to at least one explicit test oracle or mark the criterion blocked,
- execute the relevant checks against the exact deployed QA artifact commit and tested QA URLs,
- record assertion evidence, not only navigation steps, screenshots, traces, logs, or HTTP 200 smoke checks,
- fail closed when any acceptance criterion lacks existing committed automated coverage,
- fail closed when any acceptance criterion lacks proof, when evidence targets the wrong artifact/environment, or when
evidence contradicts the pass result.

Ticket-scoped QA scenarios should use this taxonomy when relevant: navigation/rendering, user workflow, API/backend
effect, state verification, validation and boundaries, error handling, environment
correctness, evidence integrity.

QA outcomes:

- `PASS`: every required assertion passed and every acceptance criterion is proven.
- `PASS WITH GAPS`: usable but a non-blocking weakness remains; keep ticket out of Done until resolved.
- `FAIL`: required assertion failed, oracle missing, evidence contradictory, wrong environment tested, or product defect
found.

Only `PASS` can move OpenProject to Done.

## QA Evidence Trigger Branch Cleanup

Selected-provider QA trigger branches are temporary Gitea Actions triggers for evidence-only E2E QA. After the branch
run succeeds, Nexus evidence exists, the E2E QA OpenProject comment is verified,
the RC tag is created or verified, and the OpenProject work package is moved to Done, delete the remote trigger branch
from Gitea. Durable QA evidence belongs in Nexus, OpenProject comments, release
manifests, and tags, not in the trigger branch.

If evidence publication, OpenProject comment verification, RC tagging, or Done-state mutation is incomplete, keep the
branch until the blocking step is resolved.

## OpenSpec Completion Archive Gate

After E2E QA passes and the OpenProject work package is moved to Done, the linked active OpenSpec change must be
archived before the workflow is reported complete. If exactly one active OpenSpec
change clearly matches the ticket key, invoke `dev-flow-archive-change` and report the archive path.

Run OpenSpec automation with `OPENSPEC_TELEMETRY=0` in the process environment so `openspec list`, `openspec status`,
and archive preflights do not time out on telemetry startup or flush. Before
moving a ticket to review, implementation handoff must leave the active OpenSpec `tasks.md` with zero unchecked tasks.
Before reporting QA completion, `configured QA gate` must re-check `openspec list
--json` and the linked change status, then either archive the change or report `OpenSpec archive blocker: <reason>`.

If a ticket is already in Done or has QA evidence but lacks the canonical `IA generated E2E QA: {ticketKey}` marker,
treat the QA finalization as incomplete. Repair the canonical E2E QA marker,
workflow timing marker, and OpenSpec archive gate before reporting the ticket workflow complete.

`dev-flow-archive-change` must fail closed: incomplete artifacts, incomplete tasks, missing `tasks.md`, failed spec
sync, failed archive movement, or a still-active change after archive are blockers.

The archive step also runs the **Durable Learning Capture Gate** (`.codex/skills/_shared/delivery-contract-core.md`):
right after the change is archived, run `python -m tools.sdd_cli knowledge-search classify` with the change name + ticket
summary, the change's changed-file list, and the E2E QA outcome, then update only the candidate `docs/` / `knowledge/`
files via the `docs-knowledge-maintenance` skill and commit/push them. `NO_CHANGES` is a valid outcome — record
`Docs: no durable context changes` / `Knowledge updated: none` and continue. The archived specs under `openspec/specs/`
are the durable behavior record; do not duplicate spec content into `docs/` or `knowledge/`.

## E2E QA Workflow

This section defines the executable workflow for the E2E QA evidence gate. Run this **only after**: the QA deployment
is confirmed OK (deploy-qa validation passed), the ticket is in `In testing` (OpenProject ID 9), ticket comments are
posted, and the Grafana dashboard is updated. The suite runs against the **deployed QA URLs only — never DEV**.

### Prerequisites

Before starting, confirm:

- QA frontend returns HTTP 200 and renders the application
- QA backend `/health` returns HTTP 200 and `{"status":"ok"}`
- The commit SHA deployed to QA is resolved (from `IA generated QA deployment: {commitSha}`)
- The ticket key is resolved
- Playwright is installed: `npx playwright --version`
- Chrome/Chromium browser is installed: `npx playwright install chromium` (if missing)

### Step 1 — Resolve Acceptance Criteria

1. Fetch the linked ticket from OpenProject using the resolved ticket key
2. Expand the ticket's acceptance criteria, description, and OpenSpec change
3. Run `openspec list --json` to identify the active OpenSpec change matching the ticket key
4. Read the OpenSpec change's `tasks.md` to enumerate every acceptance criterion
5. Map each criterion to the committed Playwright test that covers it:
   - `e2e/login-flow.spec.ts` covers: landing page rendering, navigation, form validation, login success/failure,
   logout, authenticated redirects, forgot password flow
   - `e2e/responsive.spec.ts` covers: mobile/tablet/desktop viewport rendering, responsive layout, hamburger menu, KPI
   grid layout
6. If any criterion has no committed test coverage, mark it blocked and stop — do not proceed to testing

### Step 2 — Run Playwright E2E Tests Against QA

Run the full Playwright test suite targeting the deployed QA frontend:

```bash
BASE_URL="${QA_FRONTEND_URL}" npx playwright test --reporter=list,json
```

**How it works:** The `playwright.config.ts` (generated by the AI-driven `dev-flow-scaffold-project` skill after the
tech stack is defined — only for JS/TS web stacks; never a fixed template list)
reads the `BASE_URL` environment variable at the top of the config:

```ts
const baseURL = process.env.BASE_URL || 'http://localhost:4173';
```

When `BASE_URL` is set (e.g., `BASE_URL=http://localhost:8082`), the entire test suite runs against that deployed QA URL
instead of the default local Vite dev server. This is the only change needed —
no config file switching, no server restarts.

**Test behavior notes:**

- Tests that mock API routes via `page.route('**/api/auth/login', ...)` intercept at the browser level and work
unchanged against any target URL
- Tests that assert real page content (landing page, KPI values, footer text, responsive layouts) validate the deployed
app, not a local server
- When `BASE_URL` is set, the local Vite dev server is still started but unused — tests connect to the QA URL instead.
This is harmless.

Capture the output to a file for evidence:

```bash
BASE_URL="${QA_FRONTEND_URL}" npx playwright test --reporter=list,json > e2e-qa-output.json 2>&1
PLAYWRIGHT_EXIT_CODE=$?
```

### Step 3 — Classify Results

Read the test results and classify the outcome per the QA outcomes taxonomy:

| Condition | Outcome |
|---|---|
| All tests pass, every acceptance criterion proven | `PASS` |
| All tests pass, but non-blocking weakness remains (e.g., untestable criterion) | `PASS WITH GAPS` |
| Any test fails, oracle missing, evidence contradictory, or product defect found | `FAIL` |

**On `PASS`:**

1. Add a ticket comment with marker `IA generated E2E QA: {ticketKey}` including:
   - Commit SHA and QA URL tested
   - Test results: passed/failed/skipped counts
   - Pass verdict with acceptance criteria mapping summary
   - Screenshots of any failed tests (if any)
2. Move the ticket to the configured `Done` state (or `Tested` if `Done` is reserved for PROD)
3. Update Nexus `release-qa.json` with `e2eQaStatus: "passed"` and `versionStatus: "RC candidate"`
4. Optionally create an RC tag on the QA-approved commit: `git tag -a "v{MAJOR}.{MINOR}.{PATCH}-rc.{N}"`

**On `PASS WITH GAPS`:**

1. Add a ticket comment documenting which criteria are gapped and why
2. Keep the ticket out of `Done` state
3. Do not create an RC tag
4. Report the gaps for resolution before PROD

**On `FAIL`:**

1. Add a ticket comment with marker `IA generated E2E QA: {ticketKey}` including:
   - Failing test names and assertion details
   - Console errors, screenshots, or trace evidence
   - Classification: product defect, test defect, or environment issue
2. Move the ticket to `Test failed` (OpenProject ID 11) — the E2E-failed state that routes to the bug lifecycle (E2E
   ran with the ticket in `In testing` ID 9; FAIL advances it to `Test failed`)
3. Do not create an RC tag
4. Recommend fix and re-run: invoke `dev-flow-file-qa-bug`; after the fix is deployed to QA the parent returns to
   `In testing` (ID 9) and E2E re-runs against QA (never DEV)

### Step 4 — Archive OpenSpec Change

On `PASS` only, after moving the ticket to Done:

1. Set `OPENSPEC_TELEMETRY=0` in environment
2. Re-check `openspec list --json` to confirm the change is still active
3. Invoke `dev-flow-archive-change` with the ticket key
4. Confirm the change is archived (no longer active in `openspec list`)

If archiving fails, report `OpenSpec archive blocker: <reason>` and do not report workflow complete.

After the archive succeeds, run the Durable Learning Capture Gate as specified in the OpenSpec Completion Archive Gate
above (classify → update candidates via `docs-knowledge-maintenance` → commit/push → record the capture outcome in the
QA handoff).

### Step 5 — Clean Up QA Trigger Branch

On `PASS` only, after Nexus evidence exists, comment verified, and RC tag created:

1. Identify the temporary QA trigger branch (e.g., `qa-trigger/{ticketKey}-{commitSha}`)
2. Delete it from the remote: `git push origin --delete {triggerBranch}`
3. Confirm the branch no longer exists in Gitea

If any blocking step is incomplete (evidence publication, comment verification, RC tagging, Done mutation), keep the
branch until resolved.

### Stable Markers

- QA deployment: `IA generated QA deployment: {commitSha}`
- E2E QA result: `IA generated E2E QA: {ticketKey}` (canonical marker — single source of truth for the E2E QA gate)

### Failure Rules

- Do not run E2E tests against a broken or unverified QA deployment.
- Do not run E2E tests against DEV — the suite targets the deployed QA URLs only.
- Do not run E2E before the QA deployment is confirmed OK and the ticket is in `In testing` (ID 9).
- Do not accept PASS if any acceptance criterion lacks committed test coverage.
- Do not accept PASS if any test fails.
- Do not move the ticket to Done on `PASS WITH GAPS`.
- Do not create an RC tag on `FAIL` or `PASS WITH GAPS`.
- Do not skip OpenSpec archiving — report blocker if it fails.
- Do not leave QA trigger branches behind after E2E QA completes.

## Workflow Telemetry

The E2E QA gate is a telemetry stage: the QA agent must upsert its row before moving the ticket (shared pattern
`.codex/skills/_shared/pipeline-workflow-telemetry.md`):

```bash
python -m tools.sdd_cli dev-flow telemetry-upsert --ticket-key {ticketKey} \
  --workflow-stage qa-gate --agent-role e2eQa \
  --started-utc {startedUtc} --finished-utc {finishedUtc} --outcome {PASS|FAIL|PASS WITH GAPS}
```

Marker: `IA generated workflow telemetry: {ticketKey}:qa-gate`. If the upsert fails, report the blocker before
moving the ticket.
