# Workflows

End-to-end business and technical workflows. The authoritative routing contract is
`AGENTS.md` → Workflow Stage Routing; these documents are the readable maps of each
flow, in the same order the skills execute them.

## Document Index

| File                                            | Purpose                                                                        | Typical author | AI updatable |
| ----------------------------------------------- | ------------------------------------------------------------------------------ | -------------- | ------------ |
| `implementation-deploy-flows.md`                | Linear ticket → PROD flow: Stages 1–14, routing matrix, gates, markers, env     | AI             | Yes          |
| `supporting-workflows.md`                       | Supporting/operational workflows (resume, explore, status, scaffold, retro, docs, Grafana) | AI       | Yes          |
| `parallel-delivery.md`                          | Optional multi-ticket coordination (worktrees + deployment lane)               | AI             | Yes          |
| `setup-flow-plan.md`                            | Architectural plan for the `full-setup` flow (summarized in `supporting-workflows.md` §8) | AI    | Yes          |

## Coverage Map

Every row in the `AGENTS.md` routing table is documented in exactly one place:

| Routing row | Where documented |
| ----------- | ---------------- |
| `dev-flow-start-ticket` (Stage 1) | `implementation-deploy-flows.md` §3 |
| `dev-flow-propose-change` (Stage 2) | `implementation-deploy-flows.md` §3 |
| `dev-flow-implement-ticket` (Stage 3) | `implementation-deploy-flows.md` §3 |
| `dev-flow-verify-change` (Stage 4) | `implementation-deploy-flows.md` §3 |
| `dev-flow-pr-review-agent` (Stage 5) | `implementation-deploy-flows.md` §3 |
| `dev-flow-pr-review-feedback-loop` (Stage 6) | `implementation-deploy-flows.md` §3 |
| `dev-ops-post-merge-deploy` (Stage 7) | `implementation-deploy-flows.md` §4 |
| `dev-ops-deploy-qa` (Stage 8) | `implementation-deploy-flows.md` §4 |
| E2E QA evidence gate (Stage 9, contract gate `delivery-contract-qa.md`) | `implementation-deploy-flows.md` §4 |
| `dev-flow-archive-change` (Stage 10) | `implementation-deploy-flows.md` §4 |
| `dev-flow-file-qa-bug` (Stage 11) | `implementation-deploy-flows.md` §4 |
| `dev-ops-deploy-prod` (Stage 12) | `implementation-deploy-flows.md` §4 |
| `dev-ops-rollback-prod` (Stage 13) | `implementation-deploy-flows.md` §4 |
| `dev-ops-hotfix-prod` (Stage 14) | `implementation-deploy-flows.md` §4 |
| `dev-flow-continue-implementation` | `supporting-workflows.md` §1 |
| `dev-flow-explore-change` | `supporting-workflows.md` §2 |
| `dev-flow-pipeline-status` | `supporting-workflows.md` §3 |
| `dev-flow-scaffold-project` | `supporting-workflows.md` §4 |
| `dev-flow-retrospective-audit` | `supporting-workflows.md` §5 |
| `docs-knowledge-maintenance` | `supporting-workflows.md` §6 |
| `grafana-board-update` | `supporting-workflows.md` §7 |
| `dev-flow-parallel-ticket-coordinator` (helper) | `parallel-delivery.md` + `supporting-workflows.md` |
| `dev-flow-apply-change`, `tdd` (helpers) | `supporting-workflows.md` (Helper Skills) |
| `full-setup` / `setup-lab` (setup flow) | `supporting-workflows.md` §8 + `setup-flow-plan.md` |

## How To Read

1. Start at the **routing matrix** in `implementation-deploy-flows.md` §2 — it maps a
   user request to the skill to load.
2. For the **linear flow** (ticket → PROD), read `implementation-deploy-flows.md`
   Stages 1–14 with its gates and markers sections.
3. For **everything around the line** (resume, status, scaffold, audits, docs,
   dashboards), read `supporting-workflows.md`.
4. For **multi-ticket delivery**, read `parallel-delivery.md`.
5. For the **setup flow** (`full-setup`), read `supporting-workflows.md` §8, with the full architectural plan in
`setup-flow-plan.md`.

## Eval Alignment

All 20 routing rows now have eval coverage: the Promptfoo eval
(`.codex/agent-evals/promptfooconfig.yaml`, 39 cases) exercises every explicit
`requestType` route plus the state-driven variants. See the Eval Alignment section
(§9) in `supporting-workflows.md` for the per-workflow coverage table.
