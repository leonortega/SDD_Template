<!-- TIER 2: SEMI-STABLE - Core delivery rules, loaded every stage, changes rarely -->

# Delivery Contract — Core (always-read)

Use this reference before reading stage-specific contracts. Skill-local instructions may add stricter checks, but must not weaken these rules.

Generic delivery skills must remain provider-neutral. Read `.codex/project-profile.json` plus ignored `.codex/project-profile.local.json` when present for the merged selected providers, stack, ticket key pattern, branch policy, environments, quality gates, and adapter paths. Then read `.codex/skills/_shared/provider-adapter-contract.md` and only the selected adapter files needed for the current stage. Concrete provider details belong in `.codex/providers/`, `.codex/client-tools.local.json`, executable workflow files, infrastructure files, or stack-specific skills.

For common delivery-skill startup, memory read behavior, and memory update classification, read `.codex/skills/_shared/skill-startup.md` which defines the tiered read order with cache breakpoints.

For durable context policy, read `docs/context-management.md`. The docs are the human-readable context layer; this delivery contract is the agent-enforced operational layer. If the docs and this contract conflict, the delivery contract wins for automation behavior until the docs are corrected.

---

## Tool And Skill Blocker Consent

When an agent cannot apply a required repository skill, command, memory rule, definition, or configured tool/install path, it must stop the affected workflow step instead of silently falling back to an alternative. This applies to repo-local skills, selected provider adapters, shared helper scripts, configured quality gates, memory update rules, project-guidance acquisition, and platform-supported installers.

IDE-owned and global skill roots are read-only for this repository. Do not edit, patch, or install into those roots for repo-specific behavior. Restore-only cleanup is allowed when an earlier run changed an IDE-owned skill; after restoration, put all repo-specific skill acquisition behavior in `.codex/skills/project-guidance-acquire` and repo-owned configure scripts.

The blocker response must include:

- failed required item
- why it is required
- current-flow fix
- alternative path
- risk/impact of alternative
- explicit user choice required before continuing

The agent may continue unrelated read-only investigation, but must not mutate repository files, OpenProject, Git, Gitea, Nexus, tags, releases, or local workflow state through the alternative until the user chooses that path or fixes the current flow.

## Skill Synchronization Rule

When changing any non-OpenSpec delivery skill or any `configure-*` skill, check for policy drift across related skills before finishing.

Source-of-truth order:

1. `_shared/delivery-contract-core.md` + stage-specific contracts
2. `.codex/project-profile.json`, optional `.codex/project-profile.local.json`, and selected `.codex/providers/*.md` adapter files
3. `docs/context-management.md`, `docs/architecture.md`, `docs/development.md`, `docs/deployment.md`
4. Non-OpenSpec delivery-flow skills
5. Configure skills and generated templates

If configure skills differ from delivery-flow skills, update configure docs, templates, audits, and tests to match the delivery-flow rule. Before finishing any change to a non-OpenSpec delivery skill, identify whether the change affects repo setup, generated files, workflow YAML, secrets, ignored local files, OpenProject/Gitea labels, ticket gates, artifact paths, release manifests, QA/PROD promotion, rollback, or audit/repair behavior. If it does, update the matching `configure-*` skill docs, references, templates, scripts, and tests. If not, state no configure sync was required.

## Context Findings

Implementation and retrospective work must preserve durable context discovered during delivery. Apply the Context Findings classification from `docs/context-management.md`.

Implementation PR bodies and OpenProject handoff comments must include `Context findings: added/updated/none`, `Docs updated: <files>` or `Docs: no durable context changes`, `Memory updated: <files>` or `Memory updated: none`, and `Assumptions recorded: <short list or none>`.

## Durable Learning Capture Gate

Before final handoff for any non-trivial repository work, classify whether the run discovered reusable knowledge using `.codex/memory/retrieval-policy.md#update-process`. This applies to implementation, review feedback, DEV/QA deployment, E2E QA, PROD deployment, rollback, hotfix, retrospective workflow maintenance, local tooling fixes, configuration repairs, debugging, and any prompt where an error, issue, blocker, or fix was diagnosed.

This gate is mandatory even when no memory update is needed. The final handoff must include one of:

- `Memory updated: <files>` when reusable non-authoritative knowledge was added or updated.
- `Memory updated: none` when the run produced no reusable memory candidates.

Do not treat OpenProject comments, PR comments, QA evidence, logs, or chat summaries as a substitute for this gate. When the agent itself hits a failed command, hook rejection, configuration mismatch, missing local tool, wrong tool boundary, or other repeatable workflow mistake while doing the task, treat it as a durable learning candidate by default. Search memory with the concrete symptom, apply the immediate fix, and update memory, docs, skills, or tests unless the issue is already covered or clearly one-off.

## Agent Self-Improvement Gate

Agent self-improvement is a controlled quality lane, not an automatic permission to rewrite workflow behavior. Use `dev-flow-retrospective-audit` for prompts such as `Audit recent delivery workflow`, `Audit failed QA/review/CI run`, or `Run agent self-improvement audit`. The audit is read-only by default.

Before changing any skill, workflow policy, configure template, or quality gate from retrospective evidence, at least one gate must be met:

- repeated pattern across multiple delivery runs,
- high-severity failure that could recur or affect QA, PROD, artifacts, secrets, or user-visible behavior,
- direct conflict with this delivery contract,
- missing deterministic check for an already-required workflow rule.

When a retrospective changes delivery behavior, update this contract first when the rule is cross-cutting, then synchronize affected delivery skills, configure skills, durable docs, templates, and regression tests under the Skill Synchronization Rule.

## Risk-Adaptive Workflow Depth

Strict delivery gates remain mandatory. Risk-adaptive depth changes how much planning, review, and context loading is required, not whether gates can be skipped.

Classify delivery risk as:

- `low`: localized docs, text, or clearly bounded low-impact changes with no deployable, API, data, auth, secret, workflow, or release-surface impact.
- `standard`: normal feature, bug, test, or workflow work that crosses implementation and validation but does not touch high-risk surfaces.
- `high`: work touching auth, authorization, persistence, migrations, deployment workflows, secrets, public APIs, `/health`, release manifests, rollback/hotfix, or large diffs.

Use `python -m tools.sdd_cli dev-flow` deterministic helpers when available. Low-risk work may use compact planning and review summaries, but must still preserve ticket context, branch/PR handoff, validation evidence, docs/memory classification, and configured quality gates. High-risk work requires full workload forecast handling, adversarial review, deployment topology checks when applicable, and explicit evidence in PR and OpenProject handoff comments.

## Anti-Duplication And Skill Size

Do not create parallel catalogs, planning artifacts, review workflows, or quality-command lists when an existing repo-owned surface already exists. Put cross-cutting automation rules in this contract first, explain human intent in `docs/`, and keep stage skills focused on activation, hard rules, decision gates, execution steps, and output contracts. Move long examples, API endpoint details, and edge-case prose to local `references/` files or deterministic scripts when practical.

## Grill Planning Modes

Use grill-style questioning as a planning stance inside the existing delivery workflow, not as a separate installed skill dependency or parallel planning system.

- `grill-with-docs` is the preferred style when the discussion should produce durable knowledge. Use it for domain terms, business rules, acceptance criteria, design choices, or future-reader rationale.
- `grill-me` is the lightweight style for temporary alignment only.

Map resolved durable knowledge into the existing context surfaces:

- product or ticket clarity → the managed OpenProject generated block,
- planned behavior or design → OpenSpec artifacts,
- durable repository or process knowledge → `docs/`,
- reusable non-authoritative lessons → `.codex/memory/`.

Do not create a standalone `CONTEXT.md`, ADR convention, global grill skill install, or upstream-default grill artifact path unless a separate explicit change adopts that model.

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
- OpenProject generated description block: `<!-- ia-generated:start -->` through `<!-- ia-generated:end -->`

Before adding generated comments or moving states, read existing comments when the API allows it and treat matching markers as already completed.

## OpenProject Comment Format

Generated OpenProject comments must keep the stable marker as the first line by itself, followed by a blank line and a human-readable Markdown summary. Use this structure:

1. `**Status:** PASS|FAIL|BLOCKED - one-sentence outcome`
2. `**Context:**` compact bullets for ticket, state, version, commit, PR, artifact, and workflow run.
3. `**Validation:**` grouped bullets or a small Markdown table for environment checks, test totals, and monitoring checks.
4. `**Evidence:**` durable links to Nexus manifests, evidence ZIPs, screenshots, logs, or local fallback paths.
5. `**Notes:**` only when defects, blockers, assumptions, or tooling issues matter.

Prefer Markdown links for long URLs, short commit display text such as `8acc4d4` with the full SHA recorded in a field when needed, and grouped sections over long flat lists. Keep automation-critical values present and searchable; do not hide the stable marker, commit SHA, ticket key, release version, artifact URL, or evidence URL inside prose only.

## Reusable Delivery Tools

Use `python -m tools.sdd_cli dev-flow <subcommand>` for deterministic delivery mechanics instead of duplicating script logic in skills:

- `artifact-paths`, `check-git-ignored`, `next-rc-version`, `extract-ticket-key`, `validate-release-manifest`, `create-artifact-pointer`, `validate-ticket-lock`, `validate-deployment-lane`, `validate-parallel-dry-run`, `ticket-readiness`, `delivery-risk`, `parse-workload-forecast`, `detect-adversarial-trigger`, `resolve-openproject-activity`, `render-openproject-comment`, `read-openproject-telemetry`, `init-telemetry`, `append-telemetry`, `read-telemetry`, `render-ticket-comment`, `update-release-manifest`, `ReadProjectProfile`, `ReadDeliveryPolicy`, `ReadCoverageThreshold`, `ReadCoberturaLineRate`

See the full contract in `delivery-contract-deploy.md` for Nexus/release-specific helpers. Skills remain responsible for API calls, user-facing decisions, blocker classification, and whether a mutation is allowed.

## Rerun And Failure Policy

Reruns must continue from the latest completed marker, branch, PR, artifact, tag, or manifest checkpoint.

Stop instead of guessing when:

- the ticket, PR, commit, artifact, or target state is ambiguous,
- Nexus is unavailable for promotion,
- PR labels still indicate blocking review/test work,
- QA evidence cannot be safely stored or published,
- release manifest fields conflict with OpenProject comments or tags,
- `main` diverges from the intended QA-approved commit.

Rollback does not rewrite `main`. After rollback, require a hotfix PR, revert PR, or explicit temporary divergence note with owner and expected resolution.
