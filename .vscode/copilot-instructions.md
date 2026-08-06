# SDD Template Copilot Instructions

## Skill-First Workflow

**Always read the repository skills before acting independently:**

1. When asked to implement a feature, configure tooling, deploy, or document patterns:
   - Check `.codex/skills/` first to see if a skill already covers this area
   - Check `.codex/skills/_shared/delivery-contract.md` for the authoritative policy
   - Check referenced documents in the skill (`docs/`, `.codex/quality.local.json`, etc.)

2. **Source-of-truth hierarchy** (from delivery-contract.md):
   - `.codex/skills/_shared/delivery-contract.md`
   - `docs/conventions/context-management.md`, `docs/architecture/system.md`, `docs/conventions/development.md`,
     `docs/architecture/deployment.md`
   - Non-OpenSpec delivery-flow skills
   - Configure skills and generated templates

3. **For knowledge decisions**, use `knowledge/README.md#update-process`:
   - Authoritative rules → update `docs/` or skills, not knowledge
   - Repeated failures → `knowledge/errors/<error>.md` only if not already in skills
   - Reusable non-authoritative context → knowledge files
   - If instructions exist, do not duplicate in knowledge

4. **Example workflow**:
   - User asks: "Add formatting validation to pre-commit"
   - Action: Check `configure-dev-environment` skill → read `quality-gates.md` → see lefthook rules already documented →
     add to lefthook.yml per skill guidance, not independently
   - Result: Follow skill, don't add custom instruction to knowledge

5. **When skills have gaps**: Document the gap in the final handoff (e.g., "Skill quality-gates.md does not cover X;
   added knowledge entry with ...") so the skill can be updated later.
6. **When skills have gaps**: Document the gap in the final handoff (e.g., "Skill quality-gates.md does not cover X;
added knowledge entry with ...") so the skill can be updated later.

This ensures consistency, prevents duplicate documentation, and keeps you aligned with the repository's established
patterns.

## Overview

This is an agentic SDD/SDLC delivery lab. Work is driven from OpenProject work packages through OpenSpec planning,
implementation, review, artifact promotion, deployment, QA, and production handoff. All delivery workflows, domain
knowledge, and learnings are captured in `.codex/` without duplication.

**Reference live `.codex/` files directly—do not copy or recreate them.**

## Reference Architecture

### High-Level Workflow

```text
text
OpenProject Ticket (Todo)
  → Branch + OpenSpec Proposal
  → Implementation + Tests + Gitea PR
  → Codex PR Review
  → Merge to dev
  → Nexus Artifact Package
  → Azure DEV + QA Deployment
  → E2E QA Validation
  → OpenProject Ticket (Done)
  → Explicit PROD Promotion
  → Rollback / Hotfix (if needed)
```

### Key Repository Locations

- **Skills**: `.codex/skills/` — delivery workflow skills for every SDLC stage
- **Infrastructure**: `infra/` — Docker Compose services, K8s manifests, deployment configs
- **Documentation**: `docs/` — architecture (system, deployment), conventions (development, context-management), ADRs,
  modules, workflows
- **Knowledge**: `knowledge/` — errors, fixes, patterns, troubleshooting, lessons-learned, prompts (AI-updatable)
- **Delivery CLI**: `tools/sdd_cli/` — Python CLI helpers for environment lab, dev flow, tooling

## Critical `.codex/` Resources

### 1. **Skills** (`.codex/skills/`)

Domain-specific workflows for each delivery stage. Load these based on task type:

#### Ticket Implementation

- [`dev-flow-continue-implementation`](.codex/skills/dev-flow-continue-implementation/) – Main entry point; inspects
  state, routes to next workflow
- [`dev-flow-implement-ticket`](.codex/skills/dev-flow-implement-ticket/) – Core ticket implementation workflow
- [`dev-flow-start-ticket`](.codex/skills/dev-flow-start-ticket/) – Initialize new ticket from OpenProject

#### OpenSpec Planning & Changes

- [`dev-flow-explore-change`](.codex/skills/dev-flow-explore-change/) – Explore change requirements
- [`dev-flow-propose-change`](.codex/skills/dev-flow-propose-change/) – Create OpenSpec change proposal
- [`dev-flow-implement-ticket`](.codex/skills/dev-flow-implement-ticket/) – Implement proposed change
- [`dev-flow-verify-change`](.codex/skills/dev-flow-verify-change/) – Verify implementation matches spec
- [`dev-flow-archive-change`](.codex/skills/dev-flow-archive-change/) – Archive completed change

#### Deployment & Release

- [`dev-ops-deploy-prod`](.codex/skills/dev-ops-deploy-prod/) – Promote to production
- [`dev-ops-post-merge-deploy`](.codex/skills/dev-ops-post-merge-deploy/) – Deploy after merge
- [`dev-ops-hotfix-prod`](.codex/skills/dev-ops-hotfix-prod/) – Emergency hotfix workflow
- [`dev-ops-rollback-prod`](.codex/skills/dev-ops-rollback-prod/) – Rollback production

#### Infrastructure & Configuration

- [`configure-dev-environment`](.codex/skills/configure-dev-environment/) – Setup local environment
- [`configure-ci-workflows`](.codex/skills/configure-ci-workflows/) – CI workflow configuration

#### Quality & Review

- [`dev-flow-file-qa-bug`](.codex/skills/dev-flow-file-qa-bug/) – Log QA failures
- [`dev-flow-pr-review-agent`](.codex/skills/dev-flow-pr-review-agent/) – Automated PR review
- [`dev-flow-pr-review-feedback-loop`](.codex/skills/dev-flow-pr-review-feedback-loop/) – Handle PR feedback
- [`e2e-testing-patterns`](.codex/skills/e2e-testing-patterns/) – Run E2E tests

#### Development Guidance

- [`project-guidance-acquire`](.codex/skills/project-guidance-acquire/) – Get project insights
- [`project-guidance-discover`](.codex/skills/project-guidance-discover/) – Explore patterns
- [`security-best-practices`](.codex/skills/security-best-practices/) – Security patterns

#### Shared Resources

- [`_shared/delivery-contract.md`](.codex/skills/_shared/delivery-contract.md) – Core delivery contract

**How to use**: When starting work, check if a matching skill exists. If yes, load it directly. Skill files are
      live—Copilot reads them without duplication.

### 2. **Knowledge** (`knowledge/`)

Operational knowledge that agents consult while implementing, debugging, reviewing, and fixing code. Consulted
automatically at session start.

| Path                                     | Purpose                                      |
| ---------------------------------------- | -------------------------------------------- |
| [`knowledge/README.md`](knowledge/README.md) | Index, read/write policy, standard template |
| [`knowledge/errors/`](knowledge/errors/) | Known errors: symptoms, root causes, fixes   |
| [`knowledge/fixes/`](knowledge/fixes/)   | Reusable validated fixes                     |
| [`knowledge/patterns/`](knowledge/patterns/) | Recommended implementation patterns       |
| [`knowledge/anti-patterns/`](knowledge/anti-patterns/) | Practices to avoid            |
| [`knowledge/troubleshooting/`](knowledge/troubleshooting/) | Diagnostic guides          |
| [`knowledge/lessons-learned/`](knowledge/lessons-learned/) | QA, release, workflow lessons |
| [`knowledge/references/`](knowledge/references/) | Project maps, module maps                |

**How to use**: Start each session by reading `knowledge/README.md`. For detailed context, check the relevant category
      folder. Update knowledge following `knowledge/README.md#update-process` after significant events (blockers, fixes,
      deployment issues, QA findings).

### 3. **Policy & Configuration** (`.codex/`)

| File                                                        | Purpose                                          |
| ----------------------------------------------------------- | ------------------------------------------------ |
| [`delivery-policy.json`](.codex/delivery-policy.json)       | Ticket key pattern, agent constraints, telemetry |
| [`quality.local.json`](.codex/quality.local.json)           | Build, test, coverage, lint gates (do not edit)  |
| [`client-tools.local.json`](.codex/client-tools.local.json) | Local tooling config (do not edit)               |

**How to use**: Read at session start to understand constraints. Do not edit `.local.json` files—these are local only.

## Workflow Entry Points

### Continuing a Ticket

```text
"automatically continue this ticket"
→ .codex/skills/dev-flow-continue-implementation
→ Inspects OpenProject, Git, Gitea, Nexus, OpenSpec, QA state
→ Routes to next focused skill
```

### Starting Fresh

Choose based on task:

- **New Ticket**: `"create ticket E2EPROJECT-123 for [feature]"` → `dev-flow-start-ticket`
- **OpenSpec Planning**: `"propose change for [feature]"` → `dev-flow-propose-change`
- **Implementation**: `"implement ticket E2EPROJECT-123"` → `dev-flow-implement-ticket`
- **PR Review**: `"review PR #42"` → `dev-flow-pr-review-agent`
- **Deployment**: `"deploy to QA"` → `dev-ops-post-merge-deploy` or `"promote to PROD"` → `dev-ops-deploy-prod`
- **QA**: `"run E2E tests"` → `e2e-testing-patterns`
- **Hotfix**: `"create hotfix for issue [X]"` → `dev-ops-hotfix-prod`

## How Copilot Discovers & Uses Resources

### Pattern 1: Reference by File Path

In chat, you can directly reference files:

```text
@.codex/skills/dev-flow-implement-ticket/SKILL.md
@knowledge/README.md
@.codex/delivery-policy.json
```

Copilot loads the file into context without copying.

### Pattern 2: Mention Ticket or Feature

```text
"continue E2EPROJECT-42"
"implement user authentication"
"fix failing E2E test"
```

Copilot automatically discovers the matching skill based on task context.

### Pattern 3: Explicit Workflow Request

```text
"follow the OpenSpec workflow for this change"
"run the deployment checklist"
"perform QA validation"
```

### Pattern 4: Skill Mode Activation

When a conversation requires multiple steps, Copilot may activate a skill-driven mode that:

1. Loads the skill from `.codex/skills/`
2. Checks knowledge for relevant context
3. Follows the workflow sequentially
4. Updates knowledge after significant steps

### Copilot Chat Model Configuration

Copilot chat sessions can use the repository's OpenRouter runtime configuration from `.codex/client-tools.local.json`:

- `openRouter.baseUrl`
- `openRouter.apiKey`
- `openRouter.defaultChatModel`
- `openRouter.modelMapping.chat`
  When present, `defaultChatModel` is the fallback for chat interactions and `modelMapping.chat` can override chat
  behavior for Copilot-driven repo workflows.

## Key Constraints & Policies

- **Ticket Key Pattern**: `E2EPROJECT-[0-9]+` (from `delivery-policy.json`)
- **Coverage Threshold**: 80% (from knowledge base)
- **No Duplication**: All `.codex/` files are live references, not copies
- **Knowledge is Guidance**: Never override active OpenProject work package, OpenSpec, user request, or live tool output
- **Quality Gates**: Run all gates before handoff (build, test, coverage, lint)
- **Checkpoint-Based**: Reruns continue from existing state (branches, PRs, artifacts, QA evidence)

## Common Commands

```powershell
# Environment Lab
python -m tools.sdd_cli environment-lab health-check     # Check all lab services
python -m tools.sdd_cli environment-lab compose-up        # Start Docker Compose services
python -m tools.sdd_cli environment-lab setup-lab         # Full idempotent lab setup

# Delivery CLI
python -m tools.sdd_cli dev-flow validate-commit-message "E2EPROJECT-123: message"
python -m tools.sdd_cli dev-flow create-release-manifest --version v1.0.30

# Tests
python -m pytest tools/sdd_cli/tests/ -q                   # Run CLI tests

# New stack: add product-specific build/test commands here
```text

## Quality Gates Checklist (Shell Level)

Before handoff for any repo change:

1. ✅ **Tests**: `python -m pytest tools/sdd_cli/tests/ -q` passes
2. ✅ **JSON validity**: All `.json` files are valid JSON
3. ✅ **Security**: No secrets or credentials in code
4. ✅ **Consistency**: Changes follow the delivery contract and skills

**Product gates** (add when a stack is selected): build, unit tests, coverage, formatting, linting, package verification.

See `.codex/quality.local.json` for the authoritative gate configuration when populated.

## Session Protocol

1. **Start**: Load `knowledge/README.md`
2. **Discover**: Identify matching skill from `.codex/skills/`
3. **Execute**: Follow skill workflow, referencing docs & knowledge
4. **Validate**: Run quality gates
5. **Update**: Capture learnings in knowledge following `knowledge/README.md#update-process`
6. **Handoff**: Confirm state change in OpenProject, Gitea, or deployment system

## When to Consult `.codex/` Resources

| Situation             | Consult                                                    |
| --------------------- | ---------------------------------------------------------- |
| Starting new task     | `knowledge/README.md` + matching skill                     |
| Unclear next step     | `dev-flow-continue-implementation` or `knowledge/lessons-learned/` |
| Build/test failure    | `knowledge/errors/` + `quality.local.json`                 |
| Deployment issue      | `deploy-*.md` skills + `knowledge/lessons-learned/`        |
| Architecture question | `knowledge/references/` + `docs/architecture/system.md`    |
| Setup needed          | `configure-*.md` skills                                    |
| QA failure            | `knowledge/lessons-learned/` + `dev-flow-file-qa-bug` skill |
| Production problem    | `dev-ops-rollback-prod` or `dev-ops-hotfix-prod` skills    |

## Summary

- ✅ All domain knowledge is in `.codex/skills/` — skills are **live references**
- ✅ Learnings are in `knowledge/` — knowledge is **automatically consulted**
- ✅ Policy & gates are in `.codex/` JSON files — no duplication needed
- ✅ Start with `knowledge/README.md` each session
- ✅ Use `@knowledge/` and `@.codex/` references to load files on demand
- ✅ Never copy or recreate `.codex/` or `knowledge/` content — reference it directly
- ✅ Update knowledge after significant work (use `knowledge/README.md` as guide)

For detailed delivery workflow, start with
[`.codex/skills/_shared/delivery-contract.md`](.codex/skills/_shared/delivery-contract.md).
