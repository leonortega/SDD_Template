# Supporting And Operational Workflows

This document covers the **supporting and operational workflows** of the SDLC/DevOps
laboratory — the ones that run around, alongside, or instead of the linear
ticket → PROD flow. The linear flow (Stages 1–14) is documented in
[`implementation-deploy-flows.md`](implementation-deploy-flows.md).

Every workflow below is routed by `AGENTS.md` → Workflow Stage Routing and has its own
`.codex/skills/*/SKILL.md`. Follow the skill's Workflow section step by step; this
document is the readable map, not a replacement for the skill.

| Workflow | Skill | Read-only? | Mutates? | Typical trigger |
| -------- | ----- | ---------- | -------- | --------------- |
| Continue implementation | `dev-flow-continue-implementation` | Read-first | Yes (branch, OpenProject telemetry) | Resume an in-progress ticket |
| Explore / ask questions | `dev-flow-explore-change` | Yes | No | "Explore this change", planning, architecture discussion |
| Check pipeline status | `dev-flow-pipeline-status` | **Yes** | **No** | "What's the state?", ambiguous routing fallback |
| Scaffold project | `dev-flow-scaffold-project` | No | Yes (src/, tests/, Dockerfiles, CI) | After `set-project-stack` |
| Retrospective audit | `dev-flow-retrospective-audit` | Default read-only | Apply mode on request | Post-PROD, eval improvement, periodic review |
| Update docs / knowledge | `docs-knowledge-maintenance` | No | Yes (docs/, knowledge/) | Any durable learning discovered |
| Grafana board update | `grafana-board-update` | No | Yes (dashboard JSON, commit) | After each CI deploy completes |

Helper skills used **inside** the linear flow (not standalone routing stages):

- `dev-flow-apply-change` — executes OpenSpec tasks via the `/opsx:apply` pattern inside
  `dev-flow-implement-ticket`.
- `dev-flow-parallel-ticket-coordinator` — orchestrates multi-ticket parallel delivery
  (see `parallel-delivery.md` and Section 10 of `implementation-deploy-flows.md`).
- `tdd` — RED/GREEN discipline used inside implementation (see below).

---

## 1. Continue Implementation (`dev-flow-continue-implementation`)

**Purpose.** The deterministic resume router. When a ticket is already in progress
(branch exists, OpenProject in progress), this skill inspects durable state and routes
to the correct continuation stage instead of restarting the flow.

**Trigger.** Resume of an in-progress ticket; also the state-driven auto-continue route
used by the Promptfoo eval (`resumeRequested`).

**Workflow (read-first):**

1. **Pre-flight branch auto-checkout** — read `.codex/delivery-context.local.json` for
   the `branch` field; stash a dirty tree; switch to / fetch the target branch; pull
   `--ff-only` when an upstream exists. A corrupted or missing lock is reported, not
   fatal. A branch that exists nowhere routes to `dev-flow-pipeline-status`.
2. **State inspection** — resolve delivery risk from ticket, OpenSpec, PR/diff,
   artifact, and deployment evidence; read predecessor telemetry rows
   (`dev-flow-start-ticket`, `dev-flow-implement-ticket`, `dev-flow-pr-review-agent`,
   `dev-ops-post-merge-deploy`, `dev-ops-deploy-qa`, configured QA gate) and compare
   with durable checkpoints. Missing predecessor rows route back through that stage in
   idempotent verification mode.
3. **Routing** — delegate to the child stage that owns the next step (implementation,
   review, deploy, QA gate, PROD). Each child skill owns its own telemetry row; this
   router records a `dev-flow-continue-implementation` row only when it performs
   meaningful routing work, via `time-telemetry-upsert` (marker
   `IA generated workflow telemetry: {ticketKey}:dev-flow-continue-implementation`).
4. **Rerun policy** — idempotent; resume checkpoints (completed tasks, commits,
   existing PR, review markers, feedback tasks, labels) are detected and skipped.
5. **Output** — concise status, the route taken, files touched, validation run,
   blockers, next action.

**Failure rules.** Never append telemetry for a delegated child stage from this router
(double counting). Never route to the QA gate or later PR handoff when required
predecessor telemetry is missing — route through the predecessor idempotently first.

---

## 2. Explore / Ask Questions (`dev-flow-explore-change`)

**Purpose.** Curiosity-driven discovery: mapping existing architecture, brainstorming
approaches, comparing options, surfacing risks, and reframing problems. It produces
understanding, not mutations.

**Trigger.** "Explore this change", planning analysis inside
`dev-flow-start-ticket` Stage 8, architecture discussion, ad-hoc questions.

**Stance.**

- Curious, not prescriptive — questions emerge naturally.
- Open threads, not interrogations — surface directions, let the user follow.
- Visual — ASCII diagrams for state machines, data flows, comparisons.
- Adaptive, patient, grounded — explore the actual codebase, don't theorize.

**OpenSpec awareness.** When an OpenSpec change exists, read its `proposal.md`,
`specs/`, `design.md`, and `tasks.md` for context. When none exists, the discovery can
feed a future proposal. Prefer `grill-with-docs` when answers should become durable
context; use `grill-me` only for temporary alignment.

**Guardrails.** Read-only: no ticket, branch, OpenSpec, Git, or provider mutations.
When discovery ends, summarize what was figured out and the open questions.

---

## 3. Check Pipeline Status (`dev-flow-pipeline-status`)

**Purpose.** Read-only delivery visibility: current state, next recommended route,
open blockers, and configuration gaps. **It must not mutate ticket, repository,
review, artifact, deployment, observability, or local state.**

**Trigger.** "What's the status?", "is the pipeline blocked?", ambiguous routing
fallback when no deterministic route matches, missing-stack fallback
(`productStack == none`).

**Status sources.**

- Tickets by configured states (TO DO, In Progress, Developed, In testing, Tested,
  Closed) and generated markers (branch, PR, QA deployment, E2E QA, PROD, rollback,
  QA bug).
- Active `.codex/delivery-context.local.json` lock and any mismatch with discovered
  state.
- Open PRs / merged PRs, labels, review markers, CI status.
- Nexus artifacts and `release.json` for relevant commits.
- Git branches and SemVer tags; DEV/QA/PROD URLs and `/health`.
- Seq log search when relevant to PROD status.

**Output.** Concise sections: current state + next recommended skill, open blockers,
ticket/PR/artifact mapping, active lock and cross-ticket mismatches, deployed versions,
missing configuration. Ambiguous states list candidate routes and recommend the safest.

**Failure rules.** Record unconfigured/unreachable systems as unavailable instead of
failing the whole status. Do not update knowledge unless the user explicitly asks for a
workflow-memory correction.

---

## 4. Scaffold Project (`dev-flow-scaffold-project`)

**Purpose.** Generate the product scaffold for the **user-selected** stack. The
template repo is intentionally stack-agnostic: `set-project-stack` records the decision
in `.codex/project-profile.local.json` and returns `nextStage: dev-flow-scaffold-project`;
this skill resolves everything else as an AI (exact files depend on the stack).

**Hard rule: never assume a stack.** Read `stack.frontend`, `stack.backend`,
`stack.database` (and `stack.languages`, `stack.frameworks`, `stack.testFrameworks`)
from the local profile before generating anything. Unset/incomplete/ambiguous → ask the
user. If `metadataValidationStatus == "needs-user-validation"`, confirm first.

**Workflow.**

1. **Read the stack** — summarize it for the user (e.g. "Frontend: React +
   TypeScript · Backend: FastAPI · Database: PostgreSQL").
2. **Mandatory Skill Catalog Review** — activate skills per stack (clean-architecture,
   tdd, e2e-testing-patterns, configure-ci-workflows, dev-ops-configure-k8s, ponytail,
   ...), declare `Skills used:` with skip rationale.
3. **Resolve the scaffold per stack** — native tooling for the selected frontend /
   backend / database. Generate only what the stack needs; skip unselected domains.
4. **Generate build/deploy artifacts** — Dockerfiles per app role (multi-stage,
   `/health`, non-root), CI workflows, and K8s artifacts only where the deterministic
   `scaffold-k8s` output is insufficient (Dockerfile/nginx.conf/.dockerignore).
5. **Validate before handoff** — build succeeds, tests pass (unit + integration +
   architecture), Dockerfiles build, manifests dry-run. Document residual risk for
   gates that cannot run.
6. **Record and continue** — confirm generated files; optionally persist a non-obvious
   stack decision to `knowledge/`.

---

## 5. Retrospective Audit (`dev-flow-retrospective-audit`)

**Purpose.** The **single hub for Promptfoo-driven improvements** and delivery audits.
It runs the eval (`python -m tools.sdd_cli agent-eval run`), reads
`.codex/agent-evals/results.local.json`, classifies failures into findings
(`eval-regression`, `eval-coverage`), and recommends/edits
`routing_provider.py`, `promptfooconfig.yaml`, or delivery skills.

**Operating modes.** Default read-only unless the user asks to apply.

| Mode | Behavior |
| ---- | -------- |
| `Read-only audit` | Inspect evidence, report proposed improvements |
| `Proposal mode` | Draft exact changes without editing files |
| `Apply mode` | Edit after evidence is clear and user requested it |
| `post-prod-ticket-release` | Audit after `dev-ops-deploy-prod`; persists sanitized learning; auto-escalates to eval-driven improvement |
| `eval-driven-improvement` | Run eval first; sub-modes `probe` → `diagnose` → `propose` → `apply` |

`eval-driven-improvement` sub-modes: `probe` (health check), `diagnose` (understand
failures), `propose` (draft fixes), `apply` (apply fixes — requires user confirmation
unless auto-triggered from PROD deployment).

**Triggers.** Successful PROD deploy (auto `post-prod-ticket-release`), QA bug filed or
E2E QA fails, PR review misses a meaningful issue, workflow/gate tooling fails, blocked
deployment/rollback/hotfix, delivery-vs-configure skill disagreement, periodic manual
review (every 3–5 tickets), or explicit eval diagnosis requests.

**Apply gate.** Never silently rewrite workflow rules from one isolated failure. Apply
the Agent Self-Improvement Gate (`.codex/skills/_shared/delivery-contract.md`) before
changing skills, policy, templates, or gates.

---

## 6. Update Docs / Knowledge (`docs-knowledge-maintenance`)

**Purpose.** The mandatory gate for updating AI-updatable documentation (`docs/`) and
the knowledge base (`knowledge/`) after any workflow discovers durable context. It
starts with the deterministic `classify-knowledge` helper to pick candidate files, then
applies the classification table, standard template, conflict, and security rules.

**Read first.** `docs/README.md` (index + AI-updatable vs propose-only) and
`knowledge/README.md` (index, read/write policy, standard template).

**AI updatable (agents may edit):** `docs/architecture/system.md`,
`docs/architecture/deployment.md`, `docs/modules/*.md`, `docs/api/*.md`,
`docs/workflows/*.md`.

**Propose only / draft only (do not edit):** `docs/adr/` (human; AI may draft),
`docs/conventions/` (human; propose only).

**Knowledge classification.**

| Finding | Target |
| ------- | ------ |
| Known error with root cause | `knowledge/errors/<error>.md` |
| Validated reusable fix | `knowledge/fixes/<fix>.md` |
| Recommended pattern | `knowledge/patterns/<pattern>.md` |
| Practice to avoid | `knowledge/anti-patterns/<pattern>.md` |
| Diagnostic guide / checklist | `knowledge/troubleshooting/<topic>.md` |
| QA result / release lesson / workflow lesson | `knowledge/lessons-learned/<topic>.md` |
| Reusable prompt | `knowledge/prompts/<task>.md` |
| Architecture/implementation knowledge | `knowledge/architecture/` / `knowledge/implementation/` |
| Reference material | `knowledge/references/<topic>.md` |

**Standard template.** Every knowledge document uses `# Title` then
`## Summary`, `## Problem`, `## Context`, `## Root Cause`, `## Solution`,
`## Alternatives`, `## Limitations`, `## Examples`, `## Related Documents`,
`## Tags` (plus optional `Type`/`Status`/`Source`/`Last verified` metadata) so
agents can retrieve and reason consistently.

**Ownership.** Authoritative findings → `docs/`; enforceable automation →
`.codex/skills/_shared/delivery-contract.md` + affected skills and tests; reusable
non-authoritative knowledge → `knowledge/`. Record `Docs updated: <files>` in PR
bodies and OpenProject handoff comments.

---

## 7. Grafana Board Update (`grafana-board-update`)

**Purpose.** After a CI deploy completes, merge the live DEV/QA/PROD URLs into the
Grafana SDD Service Status dashboard (`http://localhost:3001`,
`uid: agentic-e2e-health-board`) so it reflects all deployed services. The CI pipeline
discovers URLs and uploads them to Nexus — this skill does the intelligent dashboard
editing (JSON + optional Grafana API push).

**Trigger.** Manually, after a CI deploy to any environment for the active ticket.

**Sources of truth.**

| Source | Contents |
| ------ | -------- |
| `infra/deployment/apps.json` | Apps with `appId`, `role`, `healthPath`, `deployOrder` |
| `infra/k8s/kind-config.yaml` | Host port ↔ nodePort `extraPortMappings` |
| `infra/monitoring/grafana/dashboards/health-board.json` | The dashboard JSON to edit |
| Nexus `app/latest/env-urls-{env}.json` | Live deployed URLs per environment |
| Grafana API `http://localhost:3001` | Push via `POST /api/dashboards/db` (`admin:admin`) |

**Decision framework.** First time (no dashboard) → create; new app added to `apps.json`
→ add; app removed → remove; URL changed (re-deploy) → update; environment section
missing → add.

**Constraints.** Version bump required for provisioned dashboards. Scope edits to the
deployed ticket's apps and environments. Commit and push the updated dashboard JSON.

---

## Helper Skills

### `dev-flow-apply-change` (OpenSpec task execution)

Not a standalone routing stage — it implements tasks from an OpenSpec change using the
`/opsx:apply` pattern inside `dev-flow-implement-ticket`. Selects the change (by name,
inferred from context, or via `openspec list --json` when ambiguous), then works
`tasks.md` items in vertical slices with RED/GREEN tests. Announced with
"Using change: `<name>`".

### `dev-flow-parallel-ticket-coordinator` (parallel delivery)

Orchestrates multiple configured tickets through role-specialized delivery agents: one
repository worktree and one local ticket lock per active ticket, deployment lanes
serialized through selected project-profile adapters. The coordinator owns preflight,
routing, runtime-state synthesis, lane ownership, and cross-ticket decisions; it does
not duplicate child workflows or implement ticket code. Full contract in
`parallel-delivery.md` and Section 10 of `implementation-deploy-flows.md`.

### `tdd` (test-driven development)

Behavior-over-implementation testing discipline used inside implementation: vertical
RED/GREEN cycles (one test → one implementation → repeat), three test levels (unit,
integration, architecture), acceptance-to-test mapping. Explicitly **avoids horizontal
slices** (all tests first, then all code). Tests verify behavior through public
interfaces, not internal structure. See `.codex/skills/tdd/SKILL.md`, `tests.md`,
`mocking.md`, and `_shared/pipeline-tdd-cycle.md`.

---

## 8. Setup Flow (`full-setup`)

The setup flow is the onboarding path, not a delivery routing stage — there is no
routing row for it. It runs the idempotent all-in-one command:

```bash
python -m tools.sdd_cli environment-lab setup-lab   # or: full-setup
```

Four stages in order, each with a pass/fail summary:

| Stage | What it does | Reuses |
| ----- | ------------ | ------ |
| 1. Prerequisites | Check Python 3.11+, Node.js, PowerShell policy, Docker Desktop | `prereqs.py` |
| 2. Lab Setup | Init local files, build Gitea images, compose up, health checks, provision users + board, install MCPs, push code, K8s + semgrep | `environment_lab.setup_lab` |
| 3. Tool Installation | Remaining MCP servers, quality tools, manifest validation | `tool_installer.py` |
| 4. Project Guidance | Inspect profile, detect stack, discover skills, print next steps | `guidance.py` |

Command reference: `environment-lab setup-lab` delegates to `full-setup`; the old
granular commands (`prereqs check`, `tool-installer install-*`, …) remain available.
The full architectural plan is in [`setup-flow-plan.md`](setup-flow-plan.md).

---

## 9. Eval Alignment (Promptfoo Coverage)

Every workflow in this document is exercised by the agent eval
(`.codex/agent-evals/promptfooconfig.yaml`, 39 cases). Coverage per workflow:

| Workflow | Eval coverage mechanism | Covered? |
| -------- | ----------------------- | -------- |
| `dev-flow-continue-implementation` | explicit `requestType: continue-implementation` + `resumeRequested` state case | ✅ |
| `dev-flow-explore-change` | explicit `requestType: explore-change` | ✅ |
| `dev-flow-pipeline-status` | fallback route (`no stack`, unknown state) | ✅ |
| `dev-flow-scaffold-project` | explicit `requestType: scaffold-project` | ✅ |
| `dev-flow-retrospective-audit` | explicit `requestType: retrospective-audit` | ✅ |
| `grafana-board-update` | explicit `requestType: dashboard-update` | ✅ |
| `dev-flow-parallel-ticket-coordinator` | parallel-delivery coverage group (5 cases, `blocked-*` + lane routes) | ✅ |
| `dev-flow-apply-change`, `tdd` | helper skills — exercised indirectly via implementation cases | ✅ |
| `docs-knowledge-maintenance` | explicit `requestType: docs-knowledge-maintenance` | ✅ |
| Frontend design (impeccable) | `activatedSkills` stack-mapping group (3 cases: frontend impl, backend-only, pre-impl) | ✅ |

**Resolved gaps.** `docs-knowledge-maintenance` previously had no entry in
`EXPLICIT_REQUEST_ROUTES` (`.codex/agent-evals/routing_provider.py`) and no state
route, so an explicit "update the docs" request fell through to
`dev-flow-pipeline-status`. It now has an explicit `requestType` mapping and a matching
Promptfoo test case. Frontend design skills are verified via `activatedSkills` on
implementation-stage routes (impeccable activated only for frontend stacks); all 39
eval cases pass against the provider.

---

## Coverage Map

| Routing row | Detailed in |
| ----------- | ----------- |
| `dev-flow-start-ticket` … `dev-ops-hotfix-prod` (Stages 1–14) | `implementation-deploy-flows.md` |
| `dev-flow-continue-implementation` | This document (§1) |
| `dev-flow-explore-change` | This document (§2) |
| `dev-flow-pipeline-status` | This document (§3) |
| `dev-flow-scaffold-project` | This document (§4) |
| `dev-flow-retrospective-audit` | This document (§5) |
| `docs-knowledge-maintenance` | This document (§6) |
| `grafana-board-update` | This document (§7) |
| `full-setup` (setup flow) | This document (§8) + `setup-flow-plan.md` |
| `dev-flow-parallel-ticket-coordinator` | `parallel-delivery.md` + helper skills above |
| `dev-flow-apply-change`, `tdd` | Helper skills above (used inside Stages 3–4) |
