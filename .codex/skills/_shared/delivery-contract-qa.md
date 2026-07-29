<!-- TIER 3: STAGE-SPECIFIC - QA stage (deploy to QA, E2E QA, QA bug) -->

# Delivery Contract — QA (deploy to QA, E2E QA, QA bug)

Stage-specific rules for QA evidence, trigger branch cleanup, and OpenSpec archive. Read in addition to `delivery-contract-core.md`.

---

## QA Evidence Contract

E2E QA is an acceptance-evidence gate, not a screenshot, smoke, or page-load gate. The rule is: `QA Done = acceptance criteria proven by executable assertions against the deployed QA artifact`.

Ticketed implementation is TDD-first. Implementation must map every acceptance criterion to committed automated coverage. When browser-level proof is required, create or update the committed Playwright/E2E test during implementation so QA can run it later.

When a deployed browser E2E fails, use Playwright MCP or the configured Browser/Playwright tool as the first diagnostic source. Reproduce against the real QA URL, inspect console, network, websocket, DOM, screenshots, and trace/video evidence, then classify as product defect, committed-test defect, deployment/environment issue, or workflow gate gap. App code must remain product-only: do not add JavaScript helpers, hidden hooks, test ids, bypass paths, timing shims, or Playwright-specific behavior whose only purpose is making E2E pass.

Implementation owns acceptance test creation. `configured QA gate` owns deployed browser E2E execution, evidence, and QA pass/fail classification only; it must not create, repair, commit, or stage tests. After QA deployment, use the selected provider temporary QA trigger branch from the tested `dev` commit to run the committed suite remotely against the deployed QA URLs and publish evidence.

Before `configured QA gate` may move a ticket to Done, it must:

- resolve the OpenProject/OpenSpec acceptance criteria and validation expectations for the ticket,
- map each criterion to at least one explicit test oracle or mark the criterion blocked,
- execute the relevant checks against the exact deployed QA artifact commit and tested QA URLs,
- record assertion evidence, not only navigation steps, screenshots, traces, logs, or HTTP 200 smoke checks,
- fail closed when any acceptance criterion lacks existing committed automated coverage,
- fail closed when any acceptance criterion lacks proof, when evidence targets the wrong artifact/environment, or when evidence contradicts the pass result.

Ticket-scoped QA scenarios should use this taxonomy when relevant: navigation/rendering, user workflow, API/backend effect, state verification, validation and boundaries, error handling, environment correctness, evidence integrity.

QA outcomes:

- `PASS`: every required assertion passed and every acceptance criterion is proven.
- `PASS WITH GAPS`: usable but a non-blocking weakness remains; keep ticket out of Done until resolved.
- `FAIL`: required assertion failed, oracle missing, evidence contradictory, wrong environment tested, or product defect found.

Only `PASS` can move OpenProject to Done.

## QA Evidence Trigger Branch Cleanup

Selected-provider QA trigger branches are temporary Gitea Actions triggers for evidence-only E2E QA. After the branch run succeeds, Nexus evidence exists, the E2E QA OpenProject comment is verified, the RC tag is created or verified, and the OpenProject work package is moved to Done, delete the remote trigger branch from Gitea. Durable QA evidence belongs in Nexus, OpenProject comments, release manifests, and tags, not in the trigger branch.

If evidence publication, OpenProject comment verification, RC tagging, or Done-state mutation is incomplete, keep the branch until the blocking step is resolved.

## OpenSpec Completion Archive Gate

After E2E QA passes and the OpenProject work package is moved to Done, the linked active OpenSpec change must be archived before the workflow is reported complete. If exactly one active OpenSpec change clearly matches the ticket key, invoke `dev-flow-archive-change` and report the archive path.

Run OpenSpec automation with `OPENSPEC_TELEMETRY=0` in the process environment so `openspec list`, `openspec status`, and archive preflights do not time out on telemetry startup or flush. Before moving a ticket to review, implementation handoff must leave the active OpenSpec `tasks.md` with zero unchecked tasks. Before reporting QA completion, `configured QA gate` must re-check `openspec list --json` and the linked change status, then either archive the change or report `OpenSpec archive blocker: <reason>`.

If a ticket is already in Done or has QA evidence but lacks the canonical `IA generated E2E QA: {ticketKey}` marker, treat the QA finalization as incomplete. Repair the canonical E2E QA marker, workflow timing marker, and OpenSpec archive gate before reporting the ticket workflow complete.

`dev-flow-archive-change` must fail closed: incomplete artifacts, incomplete tasks, missing `tasks.md`, failed spec sync, failed archive movement, or a still-active change after archive are blockers.
