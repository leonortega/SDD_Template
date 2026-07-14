<!-- TIER 2: SEMI-STABLE - Delivery contract index, loaded every stage -->
# Delivery Contract Index

This file is the entry point for delivery contract rules. For all rules, read the appropriate stage-specific file below.

The delivery contract is the agent-enforced operational layer. The docs (`docs/context-management.md` etc.) are the human-readable context layer. If docs and contract conflict, the contract wins for automation behavior until docs are corrected.

## Always-Read (every delivery stage)

→ `delivery-contract-core.md` — Blocker consent, skill sync rule, context findings, learning capture gate, self-improvement gate, risk-adaptive depth, stable markers, comment format, reusable tools, failure policy, anti-duplication, grill modes

For tiered context assembly rules (prompt ordering, cache breakpoints, tier definitions), see **`docs/context-management.md` → §Prompt Cache Hygiene & Tiered Context Assembly** — the single authoritative source. The tier configuration is defined in `.codex/delivery-policy.json` → `agentOptimization.contextTiers`.

## Stage-Specific Contracts (read the one matching your stage)

| Stage | File | Content |
|-------|------|---------|
| Ticket start, implement, propose, explore | `delivery-contract-ticket.md` | States/flow, refinement gate, workload forecast, commit strategy, installed skill index, context lock |
| PR review, feedback loop | `delivery-contract-review.md` | Ponytail review, adversarial review, PR handoff, labels, review feedback |
| QA deploy, E2E QA, QA bug | `delivery-contract-qa.md` | QA evidence contract, trigger branch cleanup, OpenSpec archive gate |
| Post-merge deploy, CI, PROD deploy | `delivery-contract-deploy.md` | Local/CI quality split, Nexus artifacts, deployment config drift, release manifest, version rules |
| Parallel multi-ticket coordination | `delivery-contract-parallel.md` | Parallel delivery, worktree management, lane ownership |

## Cross-References

- Generic delivery skills: provider-neutral, read project profile + provider-adapter-contract.md
- Startup sequence: `.codex/skills/_shared/skill-startup.md`
- Durable context policy: `docs/context-management.md`
- API helper patterns: `.codex/skills/_shared/api-helpers.md`