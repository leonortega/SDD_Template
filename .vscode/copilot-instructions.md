# SDD Template Copilot Instructions

## Skill-First Workflow

**Always read the repository skills before acting independently:**

1. When asked to implement a feature, configure tooling, deploy, or document patterns:
   - Check `.codex/skills/` first to see if a skill already covers this area
   - Check `.codex/skills/_shared/delivery-contract.md` for the authoritative policy
   - Check referenced documents in the skill (`docs/`, `.codex/quality.local.json`, etc.)
   
2. **Source-of-truth hierarchy** (from delivery-contract.md):
   - `.codex/skills/_shared/delivery-contract.md`
   - `docs/context-management.md`, `docs/architecture.md`, `docs/development.md`, `docs/deployment.md`
   - Non-OpenSpec delivery-flow skills
   - Configure skills and generated templates

3. **For memory decisions**, use `.codex/memory/retrieval-policy.md#update-process`:
   - Authoritative rules → update `docs/` or skills, not memory
   - Repeated failures → `failure-patterns.md` only if not already in skills
   - Reusable non-authoritative context → memory files
   - If instructions exist, do not duplicate in memory

4. **Example workflow**:
   - User asks: "Add formatting validation to pre-commit"
   - Action: Check `configure-dev-environment` skill → read `quality-gates.md` → see lefthook rules already documented → add to lefthook.yml per skill guidance, not independently
   - Result: Follow skill, don't add custom instruction to memory

5. **When skills have gaps**: Document the gap in the final handoff (e.g., "Skill quality-gates.md does not cover X; added memory entry with ...") so the skill can be updated later.

This ensures consistency, prevents duplicate documentation, and keeps you aligned with the repository's established patterns.

## Overview

This is an agentic SDD/SDLC delivery lab. Work is driven from Plane tickets through OpenSpec planning, implementation, review, artifact promotion, deployment, QA, and production handoff. All delivery workflows, domain knowledge, and learnings are captured in `.codex/` without duplication.

**Reference live `.codex/` files directly—do not copy or recreate them.**

## Reference Architecture

### High-Level Workflow
```
Plane Ticket (Todo)
  → Branch + OpenSpec Proposal
  → Implementation + Tests + Gitea PR
  → Codex PR Review
  → Merge to dev
  → Nexus Artifact Package
  → Azure DEV + QA Deployment
  → E2E QA Validation
  → Plane Ticket (Done)
  → Explicit PROD Promotion
  → Rollback / Hotfix (if needed)
```

### Key Repository Locations
- **Solution**: `SDDTemplate.slnx`
- **App**: `src/SDDTemplate.Site` (Blazor + ASP.NET Core)
- **API**: `src/SDDTemplate.Api` (ASP.NET Core)
- **Tests**: `tests/SDDTemplate.Site.Tests`, `tests/SDDTemplate.E2ETests`
- **Infrastructure**: `infra/` (Docker Compose + Azure)
- **Documentation**: `docs/` (architecture, development, deployment, context-management)

## Critical `.codex/` Resources

### 1. **Skills** (`.codex/skills/`)

Domain-specific workflows for each delivery stage. Load these based on task type:

#### Ticket Implementation
- [`automatic-implement-ticket`](.codex/skills/automatic-implement-ticket/) – Main entry point; inspects state, routes to next workflow
- [`implement-ticket`](.codex/skills/implement-ticket/) – Core ticket implementation workflow
- [`plane-start-ticket`](.codex/skills/plane-start-ticket/) – Initialize new ticket from Plane

#### OpenSpec Planning & Changes
- [`openspec-explore`](.codex/skills/openspec-explore/) – Explore change requirements
- [`openspec-propose`](.codex/skills/openspec-propose/) – Create OpenSpec change proposal
- [`openspec-implement-change`](.codex/skills/openspec-implement-change/) – Implement proposed change
- [`openspec-verify-change`](.codex/skills/openspec-verify-change/) – Verify implementation matches spec
- [`openspec-archive-change`](.codex/skills/openspec-archive-change/) – Archive completed change

#### Deployment & Release
- [`deploy-to-prod`](.codex/skills/deploy-to-prod/) – Promote to production
- [`post-merge-deploy`](.codex/skills/post-merge-deploy/) – Deploy after merge
- [`hotfix-prod`](.codex/skills/hotfix-prod/) – Emergency hotfix workflow
- [`rollback-prod`](.codex/skills/rollback-prod/) – Rollback production

#### Infrastructure & Configuration
- [`configure-dev-environment`](.codex/skills/configure-dev-environment/) – Setup local environment
- [`configure-azure-environments`](.codex/skills/configure-azure-environments/) – Configure DEV/QA/PROD
- [`configure-plane-workflow`](.codex/skills/configure-plane-workflow/) – Setup Plane
- [`configure-gitea-source-control`](.codex/skills/configure-gitea-source-control/) – Setup Git
- [`configure-infra-tools`](.codex/skills/configure-infra-tools/) – Docker Compose, Nexus, etc.
- [`configure-observability`](.codex/skills/configure-observability/) – Monitoring & logging

#### Quality & Review
- [`file-qa-bug`](.codex/skills/file-qa-bug/) – Log QA failures
- [`gitea-pr-review-agent`](.codex/skills/gitea-pr-review-agent/) – Automated PR review
- [`pr-review-feedback-loop`](.codex/skills/pr-review-feedback-loop/) – Handle PR feedback
- [`test-e2e`](.codex/skills/test-e2e/) – Run E2E tests
- [`test-analysis-extensions`](.codex/skills/test-analysis-extensions/) – Analyze test results

#### Development Guidance
- [`project-guidance-acquire`](.codex/skills/project-guidance-acquire/) – Get project insights
- [`project-guidance-discover`](.codex/skills/project-guidance-discover/) – Explore patterns
- [`project-guidance-mapper`](.codex/skills/project-guidance-mapper/) – Map architecture
- [`security-best-practices`](.codex/skills/security-best-practices/) – Security patterns

#### Shared Resources
- [`_shared/delivery-contract.md`](.codex/skills/_shared/delivery-contract.md) – Core delivery contract

**How to use**: When starting work, check if a matching skill exists. If yes, load it directly. Skill files are live—Copilot reads them without duplication.

### 2. **Memory** (`.codex/memory/`)

Persistent learning and context. Consulted automatically at session start.

| File | Purpose |
|------|---------|
| [`memory_summary.md`](.codex/memory/memory_summary.md) | Quick reference: workflow, commands, context |
| [`MEMORY.md`](.codex/memory/MEMORY.md) | Index into all memory files |
| [`module-map.md`](.codex/memory/module-map.md) | ASP.NET Core module layout |
| [`project-map.md`](.codex/memory/project-map.md) | High-level project structure |
| [`workflow-memory.md`](.codex/memory/workflow-memory.md) | Workflow checkpoints & learnings |
| [`failure-patterns.md`](.codex/memory/failure-patterns.md) | Known issues & solutions |
| [`decisions.md`](.codex/memory/decisions.md) | Architecture decisions |
| [`qa-findings.md`](.codex/memory/qa-findings.md) | QA test results & patterns |
| [`release-lessons.md`](.codex/memory/release-lessons.md) | Deployment & release learnings |
| [`retrieval-policy.md`](.codex/memory/retrieval-policy.md) | How to update memory |

**How to use**: Start each session by reading `.codex/memory/memory_summary.md`. For detailed context, check the relevant memory file. Update memory following `.codex/memory/retrieval-policy.md` after significant events (blockers, fixes, deployment issues, QA findings).

### 3. **Policy & Configuration** (`.codex/`)

| File | Purpose |
|------|---------|
| [`delivery-policy.json`](.codex/delivery-policy.json) | Ticket key pattern, agent constraints, telemetry |
| [`quality.local.json`](.codex/quality.local.json) | Build, test, coverage, lint gates (do not edit) |
| [`client-tools.local.json`](.codex/client-tools.local.json) | Local tooling config (do not edit) |

**How to use**: Read at session start to understand constraints. Do not edit `.local.json` files—these are local only.

## Workflow Entry Points

### Continuing a Ticket
```
"automatically continue this ticket"
→ .codex/skills/automatic-implement-ticket
→ Inspects Plane, Git, Gitea, Nexus, OpenSpec, QA state
→ Routes to next focused skill
```

### Starting Fresh
Choose based on task:
- **New Ticket**: `"create ticket E2EPROJECT-123 for [feature]"` → `plane-start-ticket`
- **OpenSpec Planning**: `"propose change for [feature]"` → `openspec-propose`
- **Implementation**: `"implement ticket E2EPROJECT-123"` → `implement-ticket`
- **PR Review**: `"review PR #42"` → `gitea-pr-review-agent`
- **Deployment**: `"deploy to QA"` → `post-merge-deploy` or `"promote to PROD"` → `deploy-to-prod`
- **QA**: `"run E2E tests"` → `test-e2e`
- **Hotfix**: `"create hotfix for issue [X]"` → `hotfix-prod`

## How Copilot Discovers & Uses Resources

### Pattern 1: Reference by File Path
In chat, you can directly reference files:
```
@.codex/skills/implement-ticket/SKILL.md
@.codex/memory/memory_summary.md
@.codex/delivery-policy.json
```
Copilot loads the file into context without copying.

### Pattern 2: Mention Ticket or Feature
```
"continue E2EPROJECT-42"
"implement user authentication"
"fix failing E2E test"
```
Copilot automatically discovers the matching skill based on task context.

### Pattern 3: Explicit Workflow Request
```
"follow the OpenSpec workflow for this change"
"run the deployment checklist"
"perform QA validation"
```

### Pattern 4: Skill Mode Activation
When a conversation requires multiple steps, Copilot may activate a skill-driven mode that:
1. Loads the skill from `.codex/skills/`
2. Checks memory for relevant context
3. Follows the workflow sequentially
4. Updates memory after significant steps

## Key Constraints & Policies

- **Ticket Key Pattern**: `E2EPROJECT-[0-9]+` (from `delivery-policy.json`)
- **Coverage Threshold**: 80% (from memory)
- **No Duplication**: All `.codex/` files are live references, not copies
- **Memory is Guidance**: Never override active Plane ticket, OpenSpec, user request, or live tool output
- **Quality Gates**: Run all gates before handoff (build, test, coverage, lint)
- **Checkpoint-Based**: Reruns continue from existing state (branches, PRs, artifacts, QA evidence)

## Common Commands

```powershell
# Build & Test
dotnet build .\SDDTemplate.slnx
dotnet test .\SDDTemplate.slnx
dotnet format --verify-no-changes

# Infrastructure
.\infra\up.ps1              # Start local Docker Compose
.\infra\down.ps1            # Stop local Docker Compose

# Memory Search (when needed)
.\.codex\memory\search_memory.ps1 -Query "deployment issue"
```

## Quality Gates Checklist

Before handoff for any code change:
1. ✅ **Build**: `dotnet build` passes
2. ✅ **Tests**: `dotnet test` passes with ≥80% coverage
3. ✅ **Format**: `dotnet format --verify-no-changes` passes
4. ✅ **Lint**: No warnings (checked via build)
5. ✅ **Security**: No secrets or credentials in code
6. ✅ **Artifacts**: Pushed to Nexus (if deployment)

See `.codex/quality.local.json` for the authoritative gate configuration.

## Session Protocol

1. **Start**: Load `.codex/memory/memory_summary.md`
2. **Discover**: Identify matching skill from `.codex/skills/`
3. **Execute**: Follow skill workflow, referencing docs & memory
4. **Validate**: Run quality gates
5. **Update**: Capture learnings in memory following `.codex/memory/retrieval-policy.md`
6. **Handoff**: Confirm state change in Plane, Gitea, or deployment system

## When to Consult `.codex/` Resources

| Situation | Consult |
|-----------|---------|
| Starting new task | `memory_summary.md` + matching skill |
| Unclear next step | `automatic-implement-ticket` or `workflow-memory.md` |
| Build/test failure | `failure-patterns.md` + `quality.local.json` |
| Deployment issue | `deploy-*.md` skills + `release-lessons.md` |
| Architecture question | `project-map.md` + `docs/architecture.md` |
| Setup needed | `configure-*.md` skills |
| QA failure | `qa-findings.md` + `file-qa-bug` skill |
| Production problem | `rollback-prod` or `hotfix-prod` skills |

## Summary

- ✅ All domain knowledge is in `.codex/skills/` — skills are **live references**
- ✅ Learnings are in `.codex/memory/` — memory is **automatically consulted**
- ✅ Policy & gates are in `.codex/` JSON files — no duplication needed
- ✅ Start with `.codex/memory/memory_summary.md` each session
- ✅ Use `@.codex/` references to load files on demand
- ✅ Never copy or recreate `.codex/` content — reference it directly
- ✅ Update memory after significant work (use `retrieval-policy.md` as guide)

For detailed delivery workflow, start with [`.codex/skills/_shared/delivery-contract.md`](.codex/skills/_shared/delivery-contract.md).
