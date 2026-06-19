# Delivery Workflow Contract

Use this reference before running non-config delivery skills. Skill-local instructions may add stricter checks, but must not weaken this contract.

Generic delivery skills must remain provider-neutral. Read `.codex/project-profile.json` for the selected providers, stack, ticket key pattern, branch policy, environments, quality gates, and adapter paths. Then read `.codex/skills/_shared/provider-adapter-contract.md` and only the selected adapter files needed for the current stage. Concrete provider details belong in `.codex/providers/`, `.codex/client-tools.local.json`, executable workflow files, infrastructure files, or stack-specific skills.

For repeated provider endpoint patterns, read the selected adapter file and `.codex/skills/_shared/api-helpers.md` when the current adapter needs HTTP API mechanics.

For common delivery-skill startup, memory read behavior, and memory update classification, read `.codex/skills/_shared/skill-startup.md`.

For durable context policy, read `docs/context-management.md`. The docs are the human-readable context layer; this delivery contract is the agent-enforced operational layer. If the docs and this contract conflict, the delivery contract wins for automation behavior until the docs are corrected.

## Tool And Skill Blocker Consent

When an agent cannot apply a required repository skill, command, memory rule, definition, or configured tool/install path, it must stop the affected workflow step instead of silently falling back to an alternative. This applies to repo-local skills, selected provider adapters, shared helper scripts, configured quality gates, memory update rules, project-guidance acquisition, and platform-supported installers.

The blocker response must include:

- failed required item
- why it is required
- current-flow fix
- alternative path
- risk/impact of alternative
- explicit user choice required before continuing

The agent may continue unrelated read-only investigation, but must not mutate repository files, Plane, Git, Gitea, Nexus, Azure, tags, releases, or local workflow state through the alternative until the user chooses that path or fixes the current flow.

## Skill Synchronization Rule

When changing any non-OpenSpec delivery skill or any `configure-*` skill, check for policy drift across related skills before finishing.

Source-of-truth order:

1. `_shared/delivery-contract.md`
2. `.codex/project-profile.json` and selected `.codex/providers/*.md` adapter files for project-specific provider and stack selection
3. `docs/context-management.md`, `docs/architecture.md`, `docs/development.md`, and `docs/deployment.md` for durable human-readable context
4. Non-OpenSpec delivery-flow skills: `dev-flow-parallel-ticket-coordinator`, `dev-flow-continue-implementation`, `dev-flow-start-ticket`, `dev-flow-implement-ticket`, `dev-flow-pr-review-feedback-loop`, `dev-flow-pr-review-agent`, `dev-ops-post-merge-deploy`, `dev-ops-deploy-qa`, `quality-test-e2e`, `dev-ops-deploy-prod`, `dev-ops-rollback-prod`, `dev-flow-file-qa-bug`, `dev-flow-pipeline-status`, and `dev-ops-hotfix-prod`
5. Configure skills and generated templates: `configure-dev-environment`, `configure-artifact-repository`, `configure-quality-gates`, and related `configure-*` skills

If configure skills differ from delivery-flow skills, update configure docs, templates, audits, and tests to match the delivery-flow rule. Do not update OpenSpec-specific skills unless the requested change explicitly affects OpenSpec behavior.

Before finishing any change to a non-OpenSpec delivery skill, run this completion gate:

- Identify whether the skill change affects repo setup, generated files, workflow YAML, secrets, ignored local files, Plane/Gitea labels, ticket gates, artifact paths, release manifests, QA/PROD promotion, rollback, or audit/repair behavior.
- If it does, update the matching `configure-*` skill docs, references, templates, scripts, and tests in the same change.
- If it does not, state in the final response that the configure skills were checked and no configure sync was required.
- Add or update regression tests for the sync point when the behavior is enforceable from files.

## Context Findings

Implementation and retrospective work must preserve durable context discovered during delivery. Apply the Context Findings classification from `docs/context-management.md`.

Implementation PR bodies and Plane handoff comments must include `Context findings: added/updated/none`, `Docs updated: <files>` or `Docs: no durable context changes`, `Memory updated: <files>` or `Memory updated: none`, and `Assumptions recorded: <short list or none>`.

## Durable Learning Capture Gate

Before final handoff for any non-trivial repository work, classify whether the run discovered reusable knowledge using `.codex/memory/retrieval-policy.md#update-process`. This applies to implementation, review feedback, DEV/QA deployment, E2E QA, PROD deployment, rollback, hotfix, retrospective workflow maintenance, local tooling fixes, configuration repairs, debugging, and any prompt where an error, issue, blocker, or fix was diagnosed.

This gate is mandatory even when no memory update is needed. The final handoff must include one of:

- `Memory updated: <files>` when reusable non-authoritative knowledge was added or updated.
- `Memory updated: none` when the run produced no reusable memory candidates.

Do not treat Plane comments, PR comments, QA evidence, logs, or chat summaries as a substitute for this gate. If a run fixes or diagnoses a blocker that could recur across tickets, first decide whether it belongs in canonical docs, this delivery contract plus related skills/tests, or `.codex/memory/`, then update the selected durable surface before reporting completion.

When the agent itself hits a failed command, hook rejection, configuration mismatch, missing local tool, wrong tool boundary, or other repeatable workflow mistake while doing the task, treat it as a durable learning candidate by default. Search memory with the concrete symptom, apply the immediate fix, and update memory, docs, skills, or tests unless the issue is already covered or clearly one-off. Do not report `Memory updated: none` for a newly diagnosed repeatable agent/tooling failure.

## Agent Self-Improvement Gate

Agent self-improvement is a controlled quality lane, not an automatic permission to rewrite workflow behavior.

Use `dev-flow-retrospective-audit` for prompts such as `Audit recent delivery workflow`, `Audit failed QA/review/CI run`, or `Run agent self-improvement audit`. The audit is read-only by default and must not mutate Plane state, deploy, promote, tag, create scheduled automations, or rewrite active ticket context unless the user explicitly requests that separate action.

Before changing any skill, workflow policy, configure template, or quality gate from retrospective evidence, at least one gate must be met:

- repeated pattern across multiple delivery runs,
- high-severity failure that could recur or affect QA, PROD, artifacts, secrets, or user-visible behavior,
- direct conflict with this delivery contract,
- missing deterministic check for an already-required workflow rule.

When a retrospective changes delivery behavior, update this contract first when the rule is cross-cutting, then synchronize affected delivery skills, configure skills, durable docs, templates, and regression tests under the Skill Synchronization Rule.

## States And Flow

Default Plane states:

- Todo: work is not started.
- In Progress: branch and implementation are active.
- In Review: PR exists and awaits review/merge.
- QA: artifact is deployed to QA and awaits E2E validation.
- Done: E2E QA passed with acceptance criteria proven by executable assertions against the deployed QA artifact, and the ticket is closed as QA accepted and eligible for a later explicit PROD release.

Delivery flow:

```text
Plane Todo -> branch/OpenSpec -> implementation -> PR review -> dev -> DEV/QA -> E2E QA -> main -> PROD -> rollback/hotfix when needed
```

Before starting the first ticket, and before any Todo ticket is moved into implementation when stack context is missing, verify that the project tool set and tech stack are defined in `.codex/project-profile.json`, that every selected adapter path exists, and that docs/OpenSpec context points to the profile instead of duplicating canonical provider facts. The ticket-start path must run or inspect the configured guidance audit and stop before repository, ticket, or OpenSpec mutation when the audit reports `stack-context.*` drift or missing profile/adapter files. Route the operator to `configure-dev-environment` to define the project profile and recommendation catalog first. When project guidance coverage is missing, use `project-guidance-discover` to research extra useful skills, MCPs, plugins, tools, references, practices, standards, and Codex-applicable IDE helpers, show suggested guidance, and ask only for confirmation, dismissals, or omissions. A confirmation must record accepted ids, persist the local catalog, run `project-guidance-acquire`, and install/configure supported confirmed items without a second install prompt. `project-guidance-acquire` may auto-copy safe repo-local, non-secret skills; global, IDE, secret-bearing, privileged, MCP/plugin, or reboot-required installs require explicit confirmation, and the confirmed discovery list satisfies that requirement for listed non-secret items unless the installer introduces new scope, secrets, or different items. Restart and reboot requirements must be aggregated and reported once after all feasible acquisition steps finish; do not reboot automatically. Ignored `.codex/tool-recommendations.local.json` may preserve catalog-shaped discovery state and recommendation-level `usedInSteps` for `project-guidance-mapper`, but it must never override the active ticket, this delivery contract, validation gates, or current repo files.

For recurring tools used by CI, QA, security, or delivery gates, project guidance must prefer a verified pinned Docker image over repeated package-manager installation when the tool can run with mounted workspace/cache and no host-only interactive auth. Record this with `installPreference: docker-preferred` and `dockerAlternative` metadata. Keep host install plans for Docker itself, MCPs, IDE plugins, secret-bearing tools, interactive-auth tools, and tools without official/vendor or repo-owned pinned images.

PROD promotion is explicit and release-centric. Do not promote to PROD only because QA passed unless the user asks for PROD promotion or a ticket-named `src/**` or `tests/**` merge to `main` triggers the PROD-only workflow. A PROD release may include one or more Done tickets; the release promotes one QA-approved artifact commit once, then records the PROD result on every included ticket without changing Plane state.

Push-triggered environment deployment is allowed only for ticket-named work that changes configured application or test paths. The ticket key pattern is configured in `.codex/project-profile.json` at `workflow.ticketKeyPattern`. The commit message must start with the configured ticket key format, or be a repository-adapter merge commit whose PR title starts with that ticket key format. Non-code changes outside configured deploy-trigger paths do not run automatic CI/deployment work.

Before committing, classify the change as ticketed work, an OpenSpec maintenance change, or direct SDD repository maintenance. Ticketed work uses the configured ticket prefix such as `E2EPROJECT-123: ...`; OpenSpec maintenance uses the OpenSpec id prefix; direct SDD maintenance must use `[SDD]`, for example `[SDD] Improve project guidance acquisition flow`. Do this before invoking `git commit` so the `require-ticket` hook does not fail on a preventable prefix issue.

## QA Evidence Contract

E2E QA is an acceptance-evidence gate, not a screenshot, smoke, or page-load gate. The rule is: `QA Done = acceptance criteria proven by executable assertions against the deployed QA artifact`.

When a deployed browser E2E fails, use Playwright MCP or the configured Browser/Playwright tool as the first diagnostic source before changing source code. Reproduce the failing user flow against the real QA URL, inspect console, network, websocket, DOM readiness, screenshots, and trace/video evidence, then classify the failure as product defect, E2E harness issue, deployment/environment issue, or workflow gate gap. App code must remain product-only: do not add JavaScript helpers, hidden hooks, test ids, bypass paths, timing shims, or Playwright-specific behavior whose only purpose is making E2E pass. If the classification is an E2E harness issue, change only the E2E tests, evidence capture, or workflow. If it is a product defect, implement the smallest product-valid fix and keep the E2E proof external to product code.

Implementation records browser E2E expectations, acceptance oracles, and lower-level regression coverage, but does not create Playwright E2E tests by default. `quality-test-e2e` owns deployed browser E2E creation, repair, execution, evidence, and QA pass/fail classification; it creates or updates reusable E2E tests when QA proof requires them and existing committed coverage is insufficient. After QA deployment, use a temporary `qa/{ticketKey}` branch from the tested `dev` commit to run the committed suite remotely against the deployed QA URLs and publish evidence. Gitea Actions `e2e-qa` is the normal QA execution path. Local E2E QA is forbidden unless a deployment-related blocker prevents the normal Gitea `e2e-qa` path from running or completing and `agentOptimization.maxToolRetries` deploy-fix attempts from `.codex/delivery-policy.json` have failed. In this repo that limit is currently `2`. Product E2E test failures are QA failures, not a reason to switch to local fallback. Any local fallback must run `npm run test:docker` under `tests/SDDTemplate.E2ETests`, target deployed QA URLs through `E2E_SITE_URL` and `E2E_API_URL`, never target localhost, and record the deploy blocker, both failed fix attempts, local command, tested URLs, and evidence before Plane can move to Done. During QA execution, keep one-off exploratory scripts, probes, screenshots, traces, logs, and reports under ignored `artifacts/qa/**`; do not commit them as regression tests unless the configured QA workflow rule explicitly allows it or a follow-up implementation workflow intentionally promotes them. Implementation may add E2E only when the user, Plane ticket, or OpenSpec artifacts explicitly make implementation-owned E2E part of the PR scope.

Before `quality-test-e2e` may move a ticket to Done, it must:

- resolve the Plane/OpenSpec acceptance criteria and validation expectations for the ticket,
- map each criterion to at least one explicit test oracle or mark the criterion blocked,
- execute the relevant checks against the exact deployed QA artifact commit and tested QA URLs,
- record assertion evidence, not only navigation steps, screenshots, traces, logs, or HTTP 200 smoke checks,
- fail closed when any acceptance criterion lacks proof, when evidence targets the wrong artifact/environment, or when evidence contradicts the pass result.

Ticket-scoped QA scenarios should use this reusable taxonomy when relevant:

- Navigation/rendering: page, route, component, and state render correctly.
- User workflow: the intended user action can be completed end to end.
- API/backend effect: changed behavior reaches the deployed backend when the feature depends on data, services, persistence, jobs, or integrations.
- State verification: created, changed, removed, or computed state is observable from an independent source, not only the initiating UI.
- Validation and boundaries: changed business rules include valid, invalid, and boundary inputs.
- Error handling: expected failures show correct UI/API errors and do not corrupt state.
- Environment correctness: browser and API calls target the configured QA service URLs, not localhost, mocks, stale DEV endpoints, or accidental same-origin fallbacks.
- Evidence integrity: screenshots, traces, logs, API summaries, and reports are checked for blank captures, console errors, failed network calls, wrong environment, stale data, or other contradictions.

QA outcomes are:

- `PASS`: every required ticket-scoped assertion passed and every acceptance criterion is proven.
- `PASS WITH GAPS`: the deployed artifact appears usable but a non-blocking evidence weakness, warning, or assumption remains; record the gap and keep the ticket out of Done until the gap is resolved or explicitly accepted as non-blocking in the ticket.
- `FAIL`: a required assertion failed, a required oracle is missing, evidence is contradictory, the wrong artifact/environment was tested, or a product defect was found.

Only `PASS` can move Plane to Done. `PASS WITH GAPS` and `FAIL` must leave the ticket in QA unless a separate explicit user decision changes the ticket's acceptance expectations.

## Risk-Adaptive Workflow Depth

Strict delivery gates remain mandatory. Risk-adaptive depth changes how much planning, review, and context loading is required, not whether Plane, OpenSpec, PR validation, QA, artifact promotion, PROD, rollback, or secret-safety gates can be skipped.

Classify delivery risk as:

- `low`: localized docs, text, or clearly bounded low-impact changes with no deployable, API, data, auth, secret, workflow, or release-surface impact.
- `standard`: normal feature, bug, test, or workflow work that crosses implementation and validation but does not touch high-risk surfaces.
- `high`: work touching auth, authorization, persistence, migrations, deployment workflows, secrets, public APIs, `/health`, release manifests, Nexus/Azure/Gitea Actions, rollback/hotfix, or large diffs.

Use `.codex/skills/_shared/scripts/delivery_tools.ps1` or `tools/SDDTemplate.DeliveryTools` deterministic helpers when available. Low-risk work may use compact planning and review summaries, but must still preserve ticket context, branch/PR handoff, validation evidence, docs/memory classification, and configured quality gates. High-risk work requires full workload forecast handling, adversarial review, deployment topology checks when applicable, and explicit evidence in PR and Plane handoff comments.

## Ponytail Implementation And Review

When adding or changing project code, implementation agents must apply `ponytail full`: use the smallest working change, prefer standard library and native framework features, avoid speculative abstractions or dependencies, and keep tests focused on changed behavior.

`ponytail-review` runs during PR review as an additive complexity pass. It complements normal correctness, test, security, compatibility, and adversarial review; it does not replace the review-agent pass, configured human reviewers, PR validation, or any label rule.

Actionable `ponytail-review` findings are AI review findings and feed the same `dev-flow-pr-review-feedback-loop` as other current-head AI findings.

## Ticket Refinement Gate

Before `dev-flow-start-ticket` mutates Git, Plane state, the delivery lock, or OpenSpec, classify the ticket as:

- `ready`: includes a user-visible goal, concrete acceptance criteria, and validation expectations.
- `refinable`: intent is clear enough to proceed after adding Scrum-ready planning details to the managed Plane block: problem or opportunity, user story, concrete acceptance criteria, scope or affected areas, dependencies or assumptions, validation expectations, risks, and definition of done.
- `blocked`: product or technical intent is too vague to safely generate acceptance criteria.

For `refinable`, update only the generated Plane block and continue. For `blocked`, stop before branch, Plane state, delivery lock, or OpenSpec mutation and report the missing intent. Do not create a second planning artifact for refinement; Plane managed block plus OpenSpec remain the planning surfaces.

## Review Workload Forecast

OpenSpec `tasks.md` for ticketed implementation must include a compact `Review Workload Forecast` near the top:

```text
Estimated changed lines: <rough range or number>
400-line budget risk: Low|Medium|High
Chained PRs recommended: Yes|No
Decision needed before apply: Yes|No
Delivery strategy: ask-on-risk|auto-chain|single-pr|exception-ok
Suggested work units: <single PR or PR 1 -> PR 2 -> PR 3>
```

If the forecast says `400-line budget risk: High`, `Chained PRs recommended: Yes`, or `Decision needed before apply: Yes`, implementation must not start until the prompt, Plane/OpenSpec artifacts, or user decision records one of:

- split/chained work-unit plan,
- `size:exception`,
- `exception-ok`.

Work units must be deliverable behavior slices. Keep code, tests, and docs for the same behavior together; do not split PRs only by file type.

## Ticket Commit Strategy

Default ticket implementation uses one PR with multiple ticket-prefixed commits. Chained PRs remain reserved for oversized or high-risk work when the Review Workload Forecast, OpenSpec artifacts, or explicit user direction records that split.

Commit after each completed workflow step when the step produced tracked changes, then start the next step from a clean working tree. Stable commit checkpoints include:

- OpenSpec task, spec, or design refinement.
- Implementation changes.
- Tests or reusable QA regression coverage.
- Documentation, context, memory, or workflow policy updates.
- PR review feedback fixes.
- Tooling or configuration fixes scoped to the active ticket.

For each commit checkpoint:

1. Finish the step changes.
2. Review `git status` and the relevant diff.
3. Run the smallest relevant validation for that step, or record why validation is deferred to CI.
4. Stage only files related to that step.
5. Commit with a message that starts with the Plane ticket key or OpenSpec id.
6. Continue the next workflow step only after the working tree is clean or remaining changes are intentionally unrelated and documented.

Do not create empty commits. Do not intentionally leave broken intermediate commits; when two workflow steps must be committed together to keep the repository valid, combine them and record that reason in the handoff. Do not automatically stash normal ticket progress. Use stash only for unrelated local or user changes that block the current step, and never stash as a substitute for committing completed ticket work.

## Adversarial Review

`dev-flow-pr-review-agent` must run an adversarial pass when requested explicitly or when risk is `high`, including auth, authorization, persistence, migrations, deployment workflows, secrets, public APIs, `/health`, release manifests, rollback/hotfix, or large diffs. The pass reads Plane/OpenSpec acceptance criteria first, then tries to disprove implementation compliance through negative paths, idempotency, security, data-loss, deployment, and missing-test scenarios.

Adversarial review output must include one verdict:

- `PASS`: no blockers or meaningful gaps.
- `PASS WITH GAPS`: no blockers, but warnings or tracked gaps remain.
- `FAIL`: blocker, missing proof for required behavior, or high-risk unresolved issue.

Adversarial findings feed the same `dev-flow-pr-review-feedback-loop` as normal AI review findings. Do not create a separate review workflow.

## PR Reviewer Handoff

Ticket implementation handoff must request the configured human reviewers before moving the Plane ticket to review. When `pr.reviewers` is `"all"`, resolve reviewers from current Gitea collaborators and exclude the PR author plus the authenticated automation user. Gitea collaborator responses must be normalized before filtering: treat both a JSON array and a single collaborator object as a candidate list, and resolve each username from `login` first, then `username`. If reviewers are resolved but the PR create response does not show them as requested, call the Gitea requested-reviewers endpoint and re-fetch the PR to verify the requested reviewer list.

Do not treat the Codex review-agent comment, `codex-reviewed` label, or passing PR validation as a substitute for human reviewer assignment. If no eligible reviewers can be resolved, or Gitea rejects reviewer assignment, keep the PR open but document the reviewer gap in the PR body, Plane handoff comment, and final summary.

## QA Evidence Trigger Branch Cleanup

`qa/{ticketKey}` branches are temporary Gitea Actions triggers for evidence-only E2E QA. After the branch run succeeds, Nexus evidence exists for the tested artifact, the E2E QA Plane comment is verified, the RC tag is created or verified, and the Plane ticket is moved to Done, delete the remote `qa/{ticketKey}` branch from Gitea. Durable QA evidence belongs in Nexus, Plane comments, release manifests, and tags, not in the trigger branch.

If evidence publication, Plane comment verification, RC tagging, or Done-state mutation is incomplete, keep the branch until the blocking step is resolved or the branch is intentionally rerun.

## Local And CI Quality Split

Local validation is for fast feedback and test authoring. Agents should run targeted builds, tests, and cheap checks that correspond to the touched behavior and risk, then hand off the full required gate to Gitea PR validation. Do not require a full local duplicate of restore, format, release build, coverage, dependency audit, full secret scan, and filesystem scanner before opening or updating a PR unless the ticket or risk explicitly requires it.

Gitea PR validation is authoritative for restore, formatting verification, release build, tests with coverage, coverage threshold, dependency vulnerability audit, full secret scanning, and filesystem scanning in a clean pinned runner. Merge and deployment jobs should focus on immutable artifact packaging, deployment configuration verification, and environment smoke checks; they should not rerun the same unit test suite unless package or artifact inputs changed outside the already-validated PR path.

`config infra` owns building and validating repo-owned Gitea Actions job images. Workflows should consume pinned local images for common CI tools instead of installing Gitleaks, Trivy, Azure CLI, jq, zip, Node, or Playwright browser dependencies during every run. Job containers remain disposable; do not switch normal ticket CI to host-mode runner execution to preserve tool persistence.

## OpenSpec Completion Archive Gate

After E2E QA passes and the Plane ticket is moved to Done, the linked active OpenSpec change must be archived before the workflow is reported complete. If exactly one active OpenSpec change clearly matches the ticket key, invoke `dev-flow-archive-change` and report the archive path. Do not leave a completed linked OpenSpec change active merely because Plane, Nexus, and tags are complete.

Run OpenSpec automation with `OPENSPEC_TELEMETRY=0` in the process environment so `openspec list`, `openspec status`, and archive preflights do not time out on telemetry startup or flush. Before moving a ticket to review, implementation handoff must leave the active OpenSpec `tasks.md` with zero unchecked tasks. Before reporting QA completion, `quality-test-e2e` must re-check `openspec list --json` and the linked change status, then either archive the change or report `OpenSpec archive blocker: <reason>`.

If a ticket is already in Done or has QA evidence but lacks the canonical `IA generated E2E QA: {ticketKey}` marker, treat the QA finalization as incomplete, not as an idempotent success. Repair the canonical E2E QA marker, workflow timing marker, and OpenSpec archive gate before reporting the ticket workflow complete.

`dev-flow-archive-change` must fail closed: incomplete artifacts, incomplete tasks, missing `tasks.md`, failed spec sync, failed archive movement, or a still-active change after archive are blockers. Do not allow confirmation prompts to override incomplete work. If no matching active change can be resolved, multiple active changes match, artifact or task completion is incomplete, spec sync fails, or archive movement fails, report the archive blocker explicitly in Plane or the final handoff and leave the ticket result intact.

## Installed Skill Runtime Index

Project guidance remains the broad catalog for skills, tools, references, practices, standards, MCPs, and plugins. The installed-skill runtime index is only a derived cache of actual `.codex/skills/*/SKILL.md` files and exact paths for delegation.

Rules:

- The index must be ignored local state and secret-free.
- Cache by schema version plus skill path, mtime, and size so unchanged skills are cheap to reuse.
- `SKILL.md` remains the source of truth; the index does not summarize, rewrite, acquire, accept, dismiss, or replace project guidance.
- Coordinator skills may use the index to pass exact skill paths to child agents, while `project-guidance-*` continues to own broad guidance discovery, acquisition, and mapping.

## Anti-Duplication And Skill Size

Do not create parallel catalogs, planning artifacts, review workflows, or quality-command lists when an existing repo-owned surface already exists. Put cross-cutting automation rules in this contract first, explain human intent in `docs/`, and keep stage skills focused on activation, hard rules, decision gates, execution steps, and output contracts. Move long examples, API endpoint details, and edge-case prose to local `references/` files or deterministic scripts when practical.

## Ticket Context Lock

Normal automatic delivery must stay locked to one Plane ticket. Use ignored `.codex/delivery-context.local.json` as the local active delivery context lock. Never commit it. Do not delete the lock merely because E2E QA moved a ticket to `Done`; the lock can still carry QA-approved artifact, RC, and release context needed for explicit PROD promotion.

Parallel delivery keeps the same lock shape, but scopes it to the ticket worktree. Each active ticket worktree must contain its own `.codex/delivery-context.local.json`, and role agents must run only from the worktree assigned to that ticket. Do not share one checkout, one lock file, or one active implementation branch across multiple active tickets.

Baseline shape:

```json
{
  "ticketKey": "E2EPROJECT-123",
  "branch": "feat/e2eproject-123-example",
  "openspecChange": "feat-e2eproject-123-example",
  "prNumber": 12,
  "artifactCommitSha": "abc123",
  "sourceRcVersion": "v1.2.3-rc.1",
  "finalReleaseVersion": "v1.2.3"
}
```

Rules:

- `dev-flow-continue-implementation` resolves or creates the lock before delegating. If no ticket is selected, it must ask or route to `dev-flow-pipeline-status` instead of guessing.
- `dev-flow-parallel-ticket-coordinator` creates or reuses one Git worktree per active ticket, records that assignment in ignored `.codex/parallel-delivery.local.json`, and delegates child skills only inside the assigned worktree.
- `dev-flow-start-ticket` creates or updates the lock after the selected ticket, branch, and OpenSpec decision are known. If an existing lock names a different ticket, fetch the locked ticket from Plane and compare it with the configured Done state. If the locked ticket is `Done`, replace the lock for the new selected ticket. If the locked ticket is active, missing, ambiguous, or cannot be verified, stop before branch, Plane, or OpenSpec mutation and report the lock blocker. This is lazy cleanup on next ticket start, not immediate deletion after QA Done.
- Child skills must verify their resolved ticket, branch, PR, artifact `release.json.planeTicketKey`, QA evidence path, RC tag, and PROD release lineage match the locked `ticketKey` before mutating or promoting. For PROD batch releases, `includedTickets` is authoritative when present: do not block only because the promoted commit includes multiple ticket keys, but stop when any explicitly included ticket lacks Done state, E2E QA PASS evidence, source RC lineage, or release membership proof.
- If the lock exists and a child skill resolves a different ticket key, stop and report the mismatch. Do not deploy, test, move state, tag, or comment the other ticket.
- If the lock is stale outside the `dev-flow-start-ticket` terminal-ticket replacement path, or all durable checkpoints clearly identify one different active ticket, stop and ask the user to clear or replace the lock; do not silently rewrite it.
- `dev-flow-pipeline-status` may read and report the lock plus mismatches. `dev-ops-rollback-prod` may operate by incident/release target, but must report when it differs from the active lock and require explicit user confirmation before mutation.

## Parallel Delivery

Parallel delivery uses role-specialized agents and Git worktrees to let multiple tickets progress through planning, implementation, PR validation, and review at the same time. The default local runtime state file is ignored `.codex/parallel-delivery.local.json`; never commit it or print secret-derived values copied into a worktree.

Baseline shape:

```json
{
  "maxActiveTickets": 2,
  "deploymentLanePolicy": "serialized",
  "agentModelPolicy": {
    "pipelineStatus": {
      "model": "gpt-5.4-mini",
      "reasoningEffort": "low"
    },
    "implementation": {
      "model": "gpt-5.3-codex",
      "reasoningEffort": "medium"
    },
    "deployToProd": {
      "model": "gpt-5.4",
      "reasoningEffort": "high"
    }
  },
  "deploymentLaneOwner": {
    "ticketKey": "E2EPROJECT-123",
    "stage": "dev-ops-deploy-qa"
  },
  "tickets": [
    {
      "ticketKey": "E2EPROJECT-123",
      "branch": "feat/e2eproject-123-example",
      "worktreePath": "../ticket-worktrees/e2eproject-123",
      "stage": "dev-flow-implement-ticket",
      "prNumber": 12
    }
  ]
}
```

Rules:

- `parallelDelivery.maxActiveTickets` limits active ticket worktrees. If the limit is reached, report the active tickets and do not start another one.
- `parallelDelivery.worktreeRoot` is the only supported isolation model for parallel implementation. Fresh clones and shared-checkout parallelism are unsupported.
- `parallelDelivery.agentModelPolicy` maps each delivery role to a model and reasoning effort. `model: inherit` means omit the model override and use the parent Codex run's model.
- Each active ticket owns exactly one worktree and one implementation branch. Reuse matching worktrees; stop if a ticket, branch, or worktree mapping conflicts with durable Plane/Gitea/Git checkpoints.
- Copy ignored local config needed by child skills into each worktree without printing tokens, passwords, cookies, or credential-bearing URLs. The default allowlist is `.codex/client-tools.local.json`, `.codex/quality.local.json`, and `.codex/tool-recommendations.local.json` when present; do not copy `.codex/parallel-delivery.local.json`, `.codex/delivery-context.local.json`, `.codex/azure-login.local.json`, or app `*.local.json` files by default. Keep tracked templates placeholder-safe.
- Before Git, Plane, or Gitea mutation for new or reused parallel work, run `ValidateParallelDeliveryDryRun` with planned tickets, lane state, enabled state, and required local runtime files. The operator-facing question is: `Can I safely start these 2 tickets in parallel?`
- Implementation and review stages may run concurrently across tickets.
- DEV, QA, E2E QA, PROD, rollback, and hotfix promotion share deployment lanes and release tags. With `deploymentLanePolicy` set to `serialized`, only the recorded lane owner may run `dev-ops-post-merge-deploy`, `dev-ops-deploy-qa`, `quality-test-e2e`, or `dev-ops-deploy-prod`; other agents must wait or report the owner.
- PROD promotion remains explicit. Parallel delivery must not promote to PROD only because QA passed.
- After QA evidence is recorded and the Plane ticket is moved to Done, the coordinator checkout owns ticket worktree teardown. Verify the worktree is clean, verify its branch is merged into the configured base branch, run `git worktree remove <worktreePath>` and `git worktree prune`, then remove that ticket from `.codex/parallel-delivery.local.json`. Child role agents must not delete their own assigned worktree.

Role contracts:

- `coordinator`: owns preflight, routing, runtime-state synthesis, lane ownership, and all cross-ticket decisions.
- `ticketStarter`: prepares ticket branch, worktree, Plane/OpenSpec setup, and ticket lock only.
- `implementation`: edits and tests one assigned ticket worktree only.
- `prReview`: performs focused review, labels, and comments without taking unrelated implementation work.
- `deployment`: handles post-merge DEV/QA promotion only when the serialized deployment lane is free or owned by the ticket.
- `qa`: validates QA and records evidence only with lane ownership.
- `prodHotfix`: handles PROD, rollback, and hotfix only after explicit user intent and lane validation.

Every child agent must return concise status, files touched, validation run, blockers, and next action. Never let two agents mutate the same Plane ticket. Never parallelize DEV, QA, E2E QA, PROD, rollback, or hotfix promotion.

## Stable Markers

Use these exact markers for idempotency:

- Branch start: `IA generated branch: {branchName}`
- QA deployment: `IA generated QA deployment: {commitSha}`
- E2E QA: `IA generated E2E QA: {ticketKey}`
- QA bug: `IA generated QA bug: {parentTicketKey}`
- PROD deployment: `IA generated PROD deployment: {finalVersion}`
- Post-PROD retrospective: `IA generated post-PROD retrospective: {finalVersion}`
- PROD rollback: `IA generated PROD rollback: {rollbackVersionOrCommit}`
- PROD rollback incident: `IA generated PROD rollback incident: {rollbackVersionOrCommit}`
- PROD hotfix: `IA generated PROD hotfix: {incidentOrTicketKey}`
- Workflow timing: `IA generated workflow timing: {ticketKey}`
- PR review agent: `<!-- codex-review-agent:{headSha} -->`
- PR review feedback detected: `IA generated PR feedback detected: {headSha}:{feedbackBatchId}`
- PR review feedback fixes: `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}`
- Plane generated description block: `<!-- ia-generated:start -->` through `<!-- ia-generated:end -->`

Before adding generated comments or moving states, read existing comments when the API allows it and treat matching markers as already completed.

After a successful PROD deployment marker is recorded on every included ticket, `dev-ops-deploy-prod` runs a read-only `dev-flow-retrospective-audit` with `post-prod-ticket-release` scope for the just-promoted release. This audit stores sanitized learning evidence in ignored `.codex/agent-evals/results.local.json` and records the post-PROD retrospective marker on Plane. It is not a release gate and must not mutate Plane state, deploy, promote, tag, rewrite branches, update release manifests, create tickets, or apply docs, contract, skill, eval, test, or memory changes without a separate user request.

## Plane Comment Format

Generated Plane comments must keep the stable marker as the first line by itself, followed by a blank line and a human-readable Markdown summary.

When creating or repairing Plane work-item comments through the API, send both `comment_html` and `comment_stripped`; do not send Gitea-style `comment` or `body` fields. Plane can accept those fields while rendering a blank `<p></p>` comment. After posting or patching a generated marker, read the comment back and verify `comment_stripped` starts with the stable marker before reporting the Plane comment as added.

Use this structure unless a workflow-specific skill requires more detail:

1. `**Status:** PASS|FAIL|BLOCKED - one-sentence outcome`
2. `**Context:**` compact bullets for ticket, state, version, commit, PR, artifact, and workflow run.
3. `**Validation:**` grouped bullets or a small Markdown table for environment checks, test totals, and monitoring checks.
4. `**Evidence:**` durable links to Nexus manifests, evidence ZIPs, screenshots, logs, or local fallback paths.
5. `**Notes:**` only when defects, blockers, assumptions, or tooling issues matter.

Prefer Markdown links for long URLs, short commit display text such as ``8acc4d4`` with the full SHA recorded in a field when needed, and grouped sections over long flat `Label: value` lists. Keep automation-critical values present and searchable; do not hide the stable marker, commit SHA, ticket key, release version, artifact URL, or evidence URL inside prose only.

Workflow timing comments use marker `IA generated workflow timing: {ticketKey}` and a compact Markdown table with stage, outcome, duration, started UTC, and finished UTC. At the beginning of a selected ticket, `dev-flow-start-ticket` must create or clear ignored `.codex/agent-telemetry.local.jsonl` with `InitializeWorkflowTelemetry`. Each non-OpenSpec delivery stage must capture UTC start and finish times and append one row for its own stage with `AppendWorkflowTelemetry` on every run, resume, `PASS`, `BLOCKED`, `FAIL`, or idempotent `SKIP`; this includes `dev-flow-start-ticket`, `dev-flow-implement-ticket`, `dev-flow-pr-review-feedback-loop`, `dev-flow-pr-review-agent`, `dev-ops-post-merge-deploy`, `dev-ops-deploy-qa`, and `quality-test-e2e`. `dev-flow-continue-implementation` may append only its own routing row when it performs meaningful routing work, but it must not duplicate child stage rows. `ReadWorkflowTelemetry` must collapse repeated rows for the same ticket and stage into one rendered stage row: earliest `startedUtc`, latest `finishedUtc`, elapsed time as latest finish minus earliest start, latest outcome, and summed retry count. The timing table must list the standard stages even when a stage did not run or did not apply to the ticket; missing stages use outcome `NOT RUN / N/A`, duration `no time`, and `-` for start and finish. Before routing forward, required predecessor telemetry must exist for `dev-flow-start-ticket`, `dev-flow-implement-ticket`, `dev-flow-pr-review-agent`, `dev-ops-post-merge-deploy`, `dev-ops-deploy-qa`, and `quality-test-e2e`; `dev-flow-pr-review-feedback-loop` is required only when unresolved PR feedback exists or feedback markers/tasks show it ran. If durable evidence says a predecessor stage completed but its telemetry row is missing, route through that stage in idempotent verification mode so it appends its own row without duplicating Plane comments or state changes. After the E2E QA Plane comment is verified and before final QA handoff, `quality-test-e2e` must read rows for the active ticket with `ReadWorkflowTelemetry`, render the Plane timing comment with `RenderPlaneComment -Type WorkflowTiming`, then create or patch the timing marker comment. Raw telemetry stays in the ignored JSONL file; Plane timing comments must not include token counts, raw logs, full prompts, credential-bearing URLs, secrets, noisy tool details, Gitea Actions job duration, or Plane marker-derived timing. If telemetry cannot be written or read, report the workflow timing comment as blocked. On rerun, update or reuse the existing workflow timing marker comment for the same ticket instead of creating duplicates. Send both `comment_html` and `comment_stripped`, and verify `comment_stripped` starts with the marker after posting or patching.

## Reusable Delivery Tools

Use `.codex/skills/_shared/scripts/delivery_tools.ps1` for deterministic delivery mechanics instead of duplicating script logic in skills:

- `ArtifactPaths`: derive Nexus artifact paths for `app/{commitSha}`.
- `CheckGitIgnored`: verify evidence or local runtime paths are ignored before writing generated files.
- `NextRcVersion`: derive the next RC version from existing Git tags.
- `ReadProjectProfile`: read `.codex/project-profile.json` and return configured workflow values such as the ticket key pattern.
- `ReadDeliveryPolicy`: compatibility wrapper that reads `.codex/project-profile.json` first, then legacy `.codex/delivery-policy.json` when the profile is absent.
- `ExtractTicketKey`: extract ticket keys from ticket-prefixed commits or Gitea merge commit titles.
- `ReadCoverageThreshold`: read the configured coverage minimum with the repo default fallback.
- `ReadCoberturaLineRate`: read Cobertura coverage percent from XML without shell text parsing.
- `ValidateReleaseManifest`: validate required `release.json` fields and version formats.
- `CreateArtifactPointer`: write human-readable Nexus alias pointer JSON for QA-approved, RC, and final release metadata folders.
- `ValidateTicketLock`: compare resolved ticket, branch, PR, artifact commit, RC, or final version against `.codex/delivery-context.local.json`.
- `ValidateDeploymentLane`: enforce serialized deployment ownership from `.codex/parallel-delivery.local.json`.
- `ValidateParallelDeliveryDryRun`: validate enabled state, planned ticket/worktree/branch uniqueness, serialized lane ownership, supported lane policy, and required ignored local runtime files without mutating Git, Plane, Gitea, Nexus, or Azure.
- `ClassifyTicketReadiness`: classify Plane ticket text as `ready`, `refinable`, or `blocked`.
- `ClassifyDeliveryRisk`: classify planned or changed work as `low`, `standard`, or `high`.
- `ParseWorkloadForecast`: parse required `Review Workload Forecast` guard lines from OpenSpec tasks.
- `DetectAdversarialReviewTrigger`: determine whether PR review needs adversarial mode.
- `WriteInstalledSkillIndex`: write or reuse the ignored installed-skill runtime index and cache.
- `InitializeWorkflowTelemetry`, `AppendWorkflowTelemetry`, and `ReadWorkflowTelemetry`: create or clear the per-ticket ignored telemetry JSONL file, append stage timing rows, and prepare timing data for Plane comments.
- `RenderPlaneComment`: render standard Markdown Plane comments for QA deployment, E2E QA, PROD deployment, and workflow timing.
- `UpdateReleaseManifest`: merge stage-specific fields into `release.json` while preserving existing metadata, then validate the result.

Skills remain responsible for API calls, user-facing decisions, blocker classification, and whether a mutation is allowed. The script is the reusable preflight/render/update helper.

## PR Labels And Review Severity

Default labels:

- Reviewed: `codex-reviewed`
- Missing tests: `needs-tests`
- Blocking changes: `needs-changes`

Review findings must use:

- `BLOCKER`: must be fixed before handoff/promotion.
- `WARNING`: meaningful non-blocking risk.
- `SUGGESTION`: optional improvement.

Severity describes risk and PR label behavior. In this repository, every AI review finding is still tracked as required PR review feedback before human-review handoff, including `WARNING` and `SUGGESTION`.

## PR Review Feedback

PR review has two reconnectable loops:

1. AI review runs immediately after PR creation. The PR is not ready for human review until the current head has a review-agent comment, AI findings have been converted into OpenSpec feedback tasks, all feedback tasks are complete, relevant validation has passed, and current-head `needs-tests` / `needs-changes` labels are clean.
2. Human review happens later. The automatic workflow reconnects only when the operator manually resumes the ticket, such as `automatically continue this ticket` or `continue E2EPROJECT-123`. Plane remains `In Review` while human feedback fixes are applied unless the workflow stops on an ambiguous or conflicting blocker.

Feedback batches are identified by source ids, not only by head SHA. Compute `feedbackBatchId` as a deterministic short id from the sorted source ids in the batch, such as AI finding ids, Gitea top-level comment ids, and inline review comment ids. This allows late human comments on the same `headSha` to create a new batch instead of being skipped by an earlier fix marker.

`dev-flow-pr-review-feedback-loop` is the repo-owned skill that applies this rule. Keep this local delivery behavior in repo-owned dev-flow skills.

When actionable AI or human feedback is found:

- Add or update a `## PR Review Feedback` section in the active OpenSpec `tasks.md`.
- Add one task for each feedback item. Each task must record source type, source id or link, head SHA, severity, and the requested code, test, documentation, or workflow change.
- Add a Plane ticket comment with marker `IA generated PR feedback detected: {headSha}:{feedbackBatchId}` before applying fixes. The comment must list source ids or links, classifications, and OpenSpec feedback task ids.
- Apply the requested code, test, documentation, or workflow change when it is clear and scoped to the ticket.
- Update OpenSpec specs or design artifacts when the feedback changes required behavior.
- Run the relevant quality checks for the changed files.
- Commit and push the fix to the existing PR branch.
- Mark the OpenSpec feedback tasks complete only after the code and validation are complete.
- Add a Plane ticket comment with marker `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}` as the first line by itself, followed by a blank line and a reviewer-facing Markdown summary. The body must be human-readable, not only automation evidence, and must include `**Status:** READY FOR REVIEW | BLOCKED | PARTIAL - short outcome`, `**Reviewer feedback addressed:**` with source ids or links plus a short human summary of each comment, `**How IA resolved it:**` with concrete changes in reviewer language, `**Changed:**` with commit SHA, PR link, and completed OpenSpec feedback tasks, `**Validation:**` with checks run and results, `**Reviewer readiness:**` with what the reviewer should re-check and remaining blockers or `None`, and `**Skipped comments:**` only when non-actionable, stale, duplicate, generated, ambiguous, or conflicting comments were skipped.
- Rerun the AI review loop on the new head before returning to human review.

AI review findings must have stable finding ids in the PR review comment so `dev-flow-pr-review-feedback-loop` can convert them into deterministic feedback tasks and batch ids. Human-authored Gitea PR feedback includes top-level PR comments and inline code review comments, plus review-thread replies supported by the configured Gitea version.

Do not treat generated agent comments, duplicate comments already addressed by a newer head SHA or completed feedback batch, resolved/outdated inline comments, or purely informational comments as required code changes. Record skipped human comments in the Plane detection or fix comment. If human feedback is ambiguous or conflicts with the ticket, OpenSpec, security policy, or another human comment, stop before guessing and report the blocker in the PR and Plane ticket.

Before PR handoff, merge, or QA promotion, stop when any current PR feedback batch is unresolved, any OpenSpec `## PR Review Feedback` task is incomplete, or the merged PR still has `needs-tests` or `needs-changes`.

## Nexus Artifacts

Nexus is mandatory for DEV, QA, PROD, and rollback promotion. Do not rebuild between environments and do not deploy from local files.

Artifact identity is the commit SHA:

```text
app/{commitSha}/deployable-apps.json
app/{commitSha}/{artifactName}
app/{commitSha}/{artifactName}.sha256
app/{commitSha}/commit.sha
app/{commitSha}/release.json
```

`deployable-apps.json` is the packaged copy of `infra/deployment/apps.json` sorted for deployment. `commit.sha` must exactly match the artifact commit. Every `{artifactName}.sha256` listed by the topology must verify before deployment.

Human-readable Nexus version folders are aliases only. Do not move or rename canonical ZIP artifacts out of `app/{commitSha}/`. QA approval may publish `app/qa-approved/latest.json`, `app/rc/{sourceRcVersion}/artifact-pointer.json`, and `app/rc/{sourceRcVersion}/release.json`; PROD success may publish `app/releases/{finalReleaseVersion}/artifact-pointer.json` and `app/releases/{finalReleaseVersion}/release.json`. PROD push resolution must read `app/qa-approved/latest.json` and validate it against `commit.sha`, `release.json`, and the source RC tag before deploying.

## Deployment Configuration Drift

Every deployable app configuration key must be discovered, mapped, applied, and verified before DEV, QA, or PROD deployment can be reported as successful.

Rules:

- `configure-cloud-environments` owns `infra/deployment/configuration.json`, the tracked placeholder-safe mapping from flattened `appsettings*.json` keys to deploy-time App Service settings.
- The package workflow must build `deployment-config.json` from `infra/deployment/apps.json`, `infra/deployment/configuration.json`, and each deployable project `appsettings*.json`, then publish it next to `deployable-apps.json` in Nexus.
- Deployment jobs must apply and verify `deployment-config.json` for every target environment before claiming deployment success. Verification must check required keys exist, non-secret values match expected resolved values, and secret-backed keys exist without printing secret values.
- Multi-app web/API smoke checks must also prove browser-facing configuration, not only health endpoints: web app checks must verify the rendered clients page contains the expected API base URL, and API app checks must verify CORS preflight allows the matching web origin.
- Interactive configure or planning runs should infer known safe values from topology and environment metadata. When a required value cannot be inferred, ask the developer in chat for the mapping choice or tell them exactly where to create the needed secret or find the value. Never ask for raw secret values in chat.
- Non-interactive CI and deploy automation must fail closed when a required key is unmapped, marked `manualRequired`, missing from the live App Service settings, or mismatched.
- Removed keys are reported as drift. Automatic deletion from live App Service settings requires a separate explicit action because operational settings may still be in use.

## Release Manifest

Validate `release.json` against `.codex/skills/_shared/release.schema.json` when reading or writing it. Preserve existing fields when adding stage-specific data.

Required baseline fields:

- `schemaVersion`
- `commitSha`
- `checksum`
- `artifactUrl`
- `planeTicketKey`
- Optional `includedTickets` records the Done tickets included in a PROD release. `planeTicketKey` remains the primary or representative ticket for backward compatibility; when `includedTickets` exists, PROD skills must use it as the release membership list.
- `versionStatus`

Stage-specific fields are added by the responsible skill:

- DEV/QA deployment: DEV/QA URLs, statuses, health checks, PR URL, workflow URL.
- E2E QA: source RC version, QA evidence URL, QA result, tested URLs, QA timestamp.
- PROD: final release version, final tag, PROD URL, PROD statuses, monitoring status, PROD timestamp.
- Rollback: rollback timestamp, rollback workflow URL, rollback source/current version relationship.

## Version Rules

- Source RC format: `vMAJOR.MINOR.PATCH-rc.N`
- Final release format: `vMAJOR.MINOR.PATCH`
- RC tags must be annotated and point to the tested artifact commit.
- Final tags must be annotated and point to the QA-approved artifact commit.
- If no RC is supplied, derive the next RC from existing tags only when unambiguous.

## Rerun And Failure Policy

Reruns must continue from the latest completed marker, branch, PR, artifact, tag, or manifest checkpoint.

Stop instead of guessing when:

- the ticket, PR, commit, artifact, or target state is ambiguous,
- Nexus is unavailable for promotion,
- PR labels still indicate blocking review/test work,
- QA evidence cannot be safely stored or published,
- release manifest fields conflict with Plane comments or tags,
- `main` diverges from the intended QA-approved commit.

Rollback does not rewrite `main`. After rollback, require a hotfix PR, revert PR, or explicit temporary divergence note with owner and expected resolution.
