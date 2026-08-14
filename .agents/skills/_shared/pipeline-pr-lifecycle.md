<!-- TIER 3: STAGE-SPECIFIC - Shared PR lifecycle, single source of truth for the PR loop -->

# Pipeline — PR Lifecycle (7 steps)

## Usage

Use this pattern for **every** pull request, regardless of which flow created it
(feature ticket, bug fix, hotfix, release). The sequence is always the same;
only the PR body and handoff context differ. The **PROD release PR variant**
(Step 1 only) is described at the end.

Replace the placeholders:

- `{prNumber}` — the PR number
- `{ticketKey}` — the ticket key (or incident/hotfix key)
- `{headSha}` — the current PR head commit SHA
- `{baseBranch}` — the target branch (normally `dev`; `main` for PROD release PRs)

## The 7 Steps

```text
1. Create / reuse the PR (PR body + ticket comment + state move)
2. Request human reviewers (immediately at creation — HARD GATE)
3. Run the AI review (dev-flow-pr-review-agent → findings + labels)
4. PR review feedback loop (dev-flow-pr-review-feedback-loop → OpenSpec tasks, fixes, re-review)
5. CI validation check and fix (pr-validation.yml green on the current head)
6. Re-verify human reviewers after the AI review (idempotent — HARD GATE)
7. Merge (human) + post-merge handoff (approval is the automated agent-reviewed gate; merges are human-only — HARD GATE)
```

### Step 1 — Create / Reuse The PR

Reuse an existing open PR for the branch when present; otherwise create a PR
targeting the configured base branch (`{baseBranch}`, normally `dev`).

The PR body must include (flow-specific items filled by the caller):

- ticket id (or incident/hotfix key)
- OpenSpec change id (when present)
- implementation / fix summary
- acceptance-to-test map for every acceptance criterion (when applicable)
- TDD RED/GREEN evidence for tests added or updated
- tests added or updated
- E2E expectations for QA when browser acceptance is relevant, or
  `E2E expectations for QA: none`
- coverage threshold used and **coverage result: `<percentage>%` (`<pass|fail>`)**
- configured quality gates expected to run
- feature / quality / infra validation fixes applied
- Context findings: added/updated/none
- Docs updated: <files> or Docs: no durable context changes
- `Knowledge updated: <files>` or `Knowledge updated: none`
- Delivery risk: low/standard/high
- Review workload forecast: low/medium/high (and split/exception decision when applicable)
- **Reviewers requested: <usernames>**
- Assumptions recorded: <short list or none>
- remaining non-blocking infra notes and known non-blocking product risks or gaps

**Immediately after creation or reuse**, add a ticket comment and move the
ticket to the configured review state:

- Marker: `IA generated PR: {prUrl}`
- Body: `**Branch:** {branchName}`, `**OpenSpec change:** {openspecChangeName}`
  (when present), `**Reviewers requested:** {reviewers}`
- Move the ticket to the configured developed/review state (e.g. OpenProject
  `Developed`, ID 8) if it is not already there. If the state move or comment
  fails, log it as a non-blocking note and continue — the handoff step retries.

### Step 2 — Request Human Reviewers (At Creation — HARD GATE)

**❌ HARD GATE (authority level 5):** Human reviewers MUST be requested
immediately after the PR is created or reused — do NOT defer until after the
AI review. Human review runs in parallel with the AI review, and a PR that
pauses or stops mid-loop must still have reviewers assigned.

Run the reviewer automation (deterministic resolve + request + verify + retry):

```bash
python -m tools.sdd_cli gitea request-reviewers --pr {prNumber}
```

The command reads `.template/client-tools.local.json`
(`gitea.baseUrl/apiToken/owner/repo`), resolves the reviewer list
(`gitea.reviewers` → `pr.reviewers`; `"all"` expands to repo collaborators;
fallback to provisioned `gitea.provisioning.users`), excludes the PR author,
POSTs `requested_reviewers`, verifies the reviewers are present, and retries
once. Exit code 0 = verified; 1 = failed. Use `--dry-run true` first to
preview the resolved list without calling the API (note: `pr.reviewers =
"all"` cannot be previewed in dry-run — the collaborator fetch is an API call).

Failure handling:

- **Unprovisioned lab config** (placeholder `apiToken`/`owner`/`repo`):
  **BLOCKER (authority level 5)** — stop and run the environment provisioning
  (`setup-lab`) before handoff.
- **Any other failure** (no eligible reviewers, Gitea rejects the request):
  log the issue, document the reviewer gap in the PR body and the handoff
  comment, and report it in the final summary — never hand off without at
  least documenting the gap.

See `.agents/skills/_shared/pipeline-review-handoff.md` for the full reviewer
pattern (API details, manual fallback, collaborator normalization).

### Step 3 — Run The AI Review

Load and follow the `dev-flow-pr-review-agent` skill against the PR. It:

1. Resolves the PR and fetches metadata, head SHA, diff, existing comments,
   and the latest PR Validation run for the current head.
2. Reviews the code with severity labels `BLOCKER` / `WARNING` / `SUGGESTION`
   and stable finding ids (e.g. `AI-001`), runs the mandatory PR Validation
   gate check, the `ponytail-review` complexity pass, and adversarial review
   when risk is high.
3. Posts one top-level PR comment with marker
   `<!-- agent-review:{headSha} -->`.
4. Applies labels: `agent-reviewed` ONLY when the current head has ZERO
   findings of any severity AND its PR Validation run is green; otherwise
   `needs-tests` (missing/failing tests) and/or `needs-changes` (actionable
   findings) keep the `agent-reviewed` clean marker off.

**❌ HARD GATE (authority level 5):** **Never use human users to approve a PR**
— the automated approval is the `agent-reviewed` label (zero findings + green
PR Validation). Never submit an approval review or merge a pull request on
behalf of any user — provisioned lab accounts included. Merges remain
human-only.

### Step 4 — PR Review Feedback Loop

Load and follow the `dev-flow-pr-review-feedback-loop` skill. It:

1. Reuses or reruns the AI review on the current head.
2. Reads all feedback sources: AI findings, human top-level + inline PR
   comments, existing OpenSpec `## PR Review Feedback` tasks, ticket markers,
   and the latest PR Validation run (every failing CI step is a first-class
   feedback source).
3. Classifies each item (actionable / non-actionable / stale /
   ambiguous-conflicting) and computes a deterministic `feedbackBatchId`.
4. Adds one OpenSpec `## PR Review Feedback` task per actionable item.
5. Adds a ticket comment with marker
   `IA generated PR feedback detected: {headSha}:{feedbackBatchId}`.
6. REMOVES the `agent-reviewed` label while any actionable feedback exists or
   the CI run is red/pending, then applies the requested fixes, validates,
   commits (ticket-prefixed), and pushes.
7. Adds a ticket comment with marker
   `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}`.
8. Reruns the AI review on the new head; `agent-reviewed` is applied only
   when the new head has ZERO findings AND its PR Validation run is green.

The loop is done only when:

- the current-head AI review has been run or reused,
- all OpenSpec `## PR Review Feedback` tasks are complete,
- all feedback batches have fix markers,
- validation for feedback fixes has passed,
- `needs-tests` / `needs-changes` are no longer valid for the current head.

### Step 5 — CI Validation Check And Fix

> **CI is a continuous gate, not a sequential step.** It runs automatically on
every push and is checked across Steps 3–5: the AI review (Step 3) performs the
mandatory PR Validation gate check before finalizing findings, the feedback
loop (Step 4) ingests failing steps as first-class feedback sources, and this
step closes the loop by fixing and re-checking until green.

The authoritative PR Validation workflow is `.gitea/workflows/pr-validation.yml`
(gitleaks detect, semgrep, trivy, checkov, JSON validation, kustomize overlay
validation, and the `agent-reviewed` label gate). For every head:

1. Read the latest PR Validation run for the current head SHA.
2. A red, pending, or unreadable run keeps `agent-reviewed` off — the PR
   stays red on the CI gate until the run completes green.
3. Every failing step becomes a `BLOCKER` finding with a stable finding id;
   quote the step name and exact error so the feedback loop can fix it.
4. Fix, push, and re-check until the run is green on the current head.

### Step 6 — Re-Verify Human Reviewers (After AI Review — HARD GATE)

**❌ HARD GATE (authority level 5):** After the AI review (and any feedback
fixes) complete, re-run the reviewer automation — the command is idempotent
(reviewers already requested are verified, missing ones are re-requested). Do
not skip this step.

```bash
python -m tools.sdd_cli gitea request-reviewers --pr {prNumber}
```

Apply the same failure handling as Step 2. Keep `Reviewers requested:
<usernames>` in the PR body accurate if the resolved list changed.

### Step 7 — Merge (Human) + Post-Merge Handoff

**❌ HARD GATE (authority level 5):** **Never use human users to approve a PR**
— the automated approval is `agent-reviewed` + green PR Validation (applied via
the `gitea labels` CLI, never by requesting a human approval). Merges are
human-only: the agent never merges — it reports the PR as ready (approved by
the automated gate) and stops.

Before handoff for merge, confirm:

- `agent-reviewed` is present AND `needs-tests` / `needs-changes` are absent
  on the current head,
- the current-head PR Validation run is green,
- the ticket is in the developed/review state,
- the PR comment and handoff ticket comment exist (marker
  `IA generated handoff: {ticketKey}`).

After the human merges, the caller's post-merge flow continues
(e.g. `dev-ops-post-merge-deploy` → QA). Do not archive OpenSpec changes
here — archiving happens in the post-merge flow.

---

## PROD Release PR Variant (Step 1 only)

A release-blocking PR (`release/vX.Y.Z → main`) promotes an already
QA-approved, code-reviewed artifact. The full review/feedback loop does not
apply — **only Step 1** (plus the human merge from Step 7; the approval is the
`agent-reviewed` label, automated):

1. Open the PR `release/vX.Y.Z → main` with the release body.
2. Apply the `agent-reviewed` label directly (the artifact is already clean —
   this is the caller's responsibility, not the review agent's). If the
   repository requires reviewers on the PR and reviewers are configured, run
   the Step 2 command — the caller may skip the parallel review loop.
3. The `agent-reviewed` label is the approval — no human approval step
   (branch-protection approval requirements, if configured, are enforced by
   Gitea, never requested or orchestrated by the agent). The human merges.

No AI review, feedback loop, or CI fix loop runs for this PR — the artifact
was already verified in the QA flow.

---

## Related Files

- `.agents/skills/_shared/pipeline-review-handoff.md` — detailed reviewer
  request pattern (Step 2 / Step 6 mechanics)
- `.agents/skills/dev-flow-pr-review-agent/SKILL.md` — the AI review (Step 3)
- `.agents/skills/dev-flow-pr-review-feedback-loop/SKILL.md` — the feedback
  loop (Step 4)
- `.gitea/workflows/pr-validation.yml` — the CI gate (Step 5)
- `.agents/skills/_shared/pipeline-ticket-comment.md` — ticket comment
  verification pattern (Step 1 / Step 7)
- `.agents/skills/_shared/delivery-contract-review.md` — review-stage rules
