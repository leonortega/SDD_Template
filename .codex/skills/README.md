# Skill Catalog

This catalog is the tracked source of truth for repo-local skill ownership, categories, and naming.

## Convention

- **Repo-owned** skills are authored and maintained in this repository. They may have `<!-- TIER N -->` markers for prompt-cache optimization.
- **External** skills are copied from upstream sources and must remain unmodified (no tier markers, no repo-specific additions) to stay in sync with the upstream. Only `.codex/skills/_shared/` delivery contracts and repo-owned skills get tier markers.

Product-stack skills should be added only after the next product stack is selected. The current shell keeps generic delivery flow, configuration, review, Playwright, and TDD skills.

---

## Repo-Owned Skills

Skills authored and maintained in this repository. These may include `<!-- TIER N -->` markers for tiered context optimization.

| Skill                                  | Category      | Tier   | Original name                               |
| -------------------------------------- | ------------- | ------ | ------------------------------------------- |
| `project-guidance-acquire`             | Agent utility | Tier 3 | No rename                                   |
| `project-guidance-discover`            | Agent utility | Tier 3 | No rename                                   |
| `project-guidance-mapper`              | Agent utility | Tier 3 | No rename                                   |
| `configure-dev-environment`            | Configure     | Tier 3 | No rename                                   |
| `dev-flow-apply-change`                | Dev flow      | Tier 3 | Renamed from `openspec-apply-change`        |
| `dev-flow-archive-change`              | Dev flow      | Tier 3 | Renamed from `openspec-archive-change`      |
| `dev-flow-continue-implementation`     | Dev flow      | Tier 3 | Renamed from `automatic-implement-ticket`   |
| `dev-flow-explore-change`              | Dev flow      | Tier 3 | Renamed from `openspec-explore`             |
| `dev-flow-file-qa-bug`                 | Dev flow      | Tier 3 | Renamed from `file-qa-bug`                  |
| `dev-flow-implement-change`            | Dev flow      | Tier 3 | Renamed from `openspec-implement-change`    |
| `dev-flow-implement-ticket`            | Dev flow      | Tier 3 | Renamed from `implement-ticket`             |
| `dev-flow-parallel-ticket-coordinator` | Dev flow      | Tier 3 | Renamed from `parallel-ticket-coordinator`  |
| `dev-flow-pipeline-status`             | Dev flow      | Tier 3 | Renamed from `pipeline-status`              |
| `dev-flow-pr-review-agent`             | Dev flow      | Tier 3 | Renamed from `gitea-pr-review-agent`        |
| `dev-flow-pr-review-feedback-loop`     | Dev flow      | Tier 3 | Renamed from `pr-review-feedback-loop`      |
| `dev-flow-propose-change`              | Dev flow      | Tier 3 | Renamed from `openspec-propose`             |
| `dev-flow-retrospective-audit`         | Dev flow      | Tier 3 | Renamed from `delivery-retrospective-audit` |
| `dev-flow-start-ticket`                | Dev flow      | Tier 3 | Configured ticket-provider start workflow   |
| `dev-flow-verify-change`               | Dev flow      | Tier 3 | Renamed from `openspec-verify-change`       |
| `dev-ops-deploy-prod`                  | DevOps        | Tier 3 | Renamed from `deploy-to-prod`               |
| `dev-ops-deploy-qa`                    | DevOps        | Tier 3 | Renamed from `deploy-to-qa`                 |
| `dev-ops-hotfix-prod`                  | DevOps        | Tier 3 | Renamed from `hotfix-prod`                  |
| `dev-ops-post-merge-deploy`            | DevOps        | Tier 3 | Renamed from `post-merge-deploy`            |
| `dev-ops-rollback-prod`                | DevOps        | Tier 3 | Renamed from `rollback-prod`                |

## External Skills

Copied from upstream sources. **Do not modify** these files — no tier markers, no repo-specific additions. Keep as-is to stay in sync with upstream.

| Skill                     | Category          | Source                                                                             |
| ------------------------- | ----------------- | ---------------------------------------------------------------------------------- |
| `caveman`                 | Agent utility     | https://github.com/JuliusBrussee/caveman/tree/main/plugins/caveman/skills/caveman  |
| `ponytail`                | Agent utility     | https://github.com/DietrichGebert/ponytail/tree/main/skills/ponytail               |
| `ponytail-audit`          | Agent utility     | https://github.com/DietrichGebert/ponytail/tree/main/skills/ponytail-audit         |
| `ponytail-debt`           | Agent utility     | https://github.com/DietrichGebert/ponytail/tree/main/skills/ponytail-debt          |
| `ponytail-help`           | Agent utility     | https://github.com/DietrichGebert/ponytail/tree/main/skills/ponytail-help          |
| `ponytail-review`         | Agent utility     | https://github.com/DietrichGebert/ponytail/tree/main/skills/ponytail-review        |
| `domain-modeling`         | External guidance | https://github.com/mattpocock/skills/tree/main/skills/engineering/domain-modeling  |
| `grill-me`                | External guidance | https://github.com/mattpocock/skills/tree/main/skills/productivity/grill-me        |
| `grill-with-docs`         | External guidance | https://github.com/mattpocock/skills/tree/main/skills/engineering/grill-with-docs  |
| `grilling`                | External guidance | https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling        |
| `playwright`              | External guidance | https://github.com/openai/skills/tree/main/skills/.curated/playwright              |
| `playwright-interactive`  | External guidance | https://github.com/openai/skills/tree/main/skills/.curated/playwright-interactive  |
| `security-best-practices` | External guidance | https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices |
| `tdd`                     | External guidance | https://github.com/mattpocock/skills/tree/main/skills/engineering/tdd              |

## Removed Skills (not present in repo)

The following skills were previously listed but no longer have SKILL.md files in this repository. They are listed here for historical reference only:

| Skill                           | Category        | Notes                                                  |
| ------------------------------- | --------------- | ------------------------------------------------------ |
| `configure-artifact-repository` | Configure       | Removed, consolidated into `configure-dev-environment` |
| `configure-ci-runner`           | Configure       | Removed, consolidated into `configure-dev-environment` |
| `configure-cloud-environments`  | Configure       | Removed, consolidated into `configure-dev-environment` |
| `configure-infra-tools`         | Configure alias | Removed, consolidated into `configure-dev-environment` |
| `configure-observability`       | Configure       | Removed, consolidated into `configure-dev-environment` |
| `configure-quality-gates`       | Configure       | Removed, consolidated into `configure-dev-environment` |
| `configure-source-control`      | Configure       | Removed, consolidated into `configure-dev-environment` |
| `configure-ticket-workflow`     | Configure       | Removed, consolidated into `configure-dev-environment` |

## Tiered Context Markers

Repo-owned skills may have `<!-- TIER N: NAME -->` markers at the top of their files to indicate prompt-cache tier membership:

- **Tier 1 — Stable Prefix**: Session-cached, never changes per turn (e.g., `AGENTS.md`, `repo-startup.md`)
- **Tier 2 — Semi-Stable**: Session-cached, changes rarely (e.g., `delivery-contract-core.md`, memory files)
- **Tier 3 — Stage-Specific**: Cached per workflow stage (e.g., `delivery-contract-ticket.md`, repo-owned skill files)
- **Tier 4 — Dynamic**: Never cached (user messages, tool outputs, live state)

See `docs/context-management.md` → §Prompt Cache Hygiene & Tiered Context Assembly for the full documentation.
