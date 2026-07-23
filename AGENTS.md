<!-- TIER 1: STABLE PREFIX - Repo identity, mandatory rules, session-cached -->

# AGENTS.md

This repository is a product-free SDD/SDLC agentic shell. Use the workflow files and Codex skills as the source of truth before making changes.

## Mandatory First Step

Before any tool call or file edit, every agent **must**:

1. Call `skill('caveman')` and apply its full mode (terse fragments for commentary, status, blockers, summaries; normal prose only for authored artifacts).
2. Read the **Start Here** section below and the files it lists.

Failure to load Caveman first violates repo convention (authority level 5 per `docs/context-management.md`). If the skill tool reports "no skills available", report this as a setup gap and apply these rules manually: use terse fragments for commentary, status updates, blockers, summaries, and final handoff. Use normal prose only for authored artifacts (code blocks, documentation, config files).

## Start Here

After the mandatory first step, inspect the relevant local context for the current workflow stage. **Assemble context in tier order** (see `.codex/delivery-policy.json` → `agentOptimization.contextTiers`):

1. **TIER 1 — Stable prefix** (cache once per session): `AGENTS.md`, `.codex/skills/_shared/repo-startup.md`, `.codex/delivery-policy.json`, `.codex/mcp-instructions.md`
2. **TIER 2 — Semi-stable** (cache once per session): `.codex/skills/_shared/delivery-contract.md`, `.codex/skills/_shared/delivery-contract-core.md`, `.codex/skills/_shared/skill-startup.md`
3. **TIER 3 — Stage-specific** (cache per stage): relevant `delivery-contract-{stage}.md`, `api-helpers.md`
4. **TIER 4 — Dynamic** (never cached): user message, conversation history, tool outputs, live state

Always read in order:

- `README.md`
- `.codex/skills/_shared/skill-startup.md`
- `.codex/memory/memory_summary.md`
- `.codex/memory/MEMORY.md`
- `.codex/delivery-policy.json`

Then read only the stage-specific docs, OpenSpec artifacts, skills, provider adapters, and workflow files needed for the task. Read local config only when the workflow needs those values, and never print secrets or credential-bearing values.

Prefer repository-specific skills and scripts over ad hoc process decisions.

<!-- CACHE BREAKPOINT: End Tier 1 - Stable session context. Dynamic per-turn data below. -->

## Mandatory Skill Declaration

Every agent **must** declare which skills it is activating for each step of the lab flow or any repo interaction. This includes both auto-activated skills and on-demand skills.

**Format**: At the start of each response (after Caveman loading), include a `Skills used:` block listing every activated skill with its intensity/purpose.

**Authority level**: 5 (same as Mandatory First Step, Mandatory MCP Routing).

**Examples**:

```markdown
Skills used: caveman (full), ponytail (full), security-best-practices (on-demand)

- caveman: terse response format
- ponytail: code quality review
- security-best-practices: validating auth implementation
```

Failure to declare used skills violates repo convention. If a skill is auto-activated (caveman, ponytail), still declare it — do not assume it is implicit.

## Mandatory Pre-Implementation Skill Review

Before any code change — whether implementing a ticket, fixing a bug, or adding a feature — every agent **must** review all installed skills for relevance. This is a hard gate: no code is edited until the review is complete.

**Authority level**: 5 (same as Mandatory First Step, Mandatory Skill Declaration, Mandatory MCP Routing).

### Review Process

1. **List installed skills:** Read the `.codex/skills/` directory and enumerate every installed skill (each subdirectory containing a `SKILL.md`).
2. **Assess relevance:** For each skill, determine whether its rules, patterns, or constraints apply to the current task:
   - **Relevant** → Load the skill via `skill('<name>')` and apply its rules during implementation.
   - **Irrelevant** → State the specific reason it does not apply (e.g., "C# coding standards — this is a TypeScript project", "View transitions — no route animations in this ticket's scope").
3. **Declare with justification:** The `Skills used:` block (required by Mandatory Skill Declaration) must document the outcome of this review:
   - List every installed skill and whether it is active or skipped.
   - For skipped skills, include a brief rationale.
4. **Blockers:** If a required skill exists in `.codex/skills/` but cannot be loaded or applied (e.g., broken `SKILL.md`, conflicting instructions), stop and report the blocker before editing code. Apply Tool And Skill Blocker Consent from `delivery-contract-core.md`.

### Example Declaration

```markdown
Skills used:

- caveman (auto, full): terse format
- ponytail (auto, full): code quality
- vercel-react-best-practices (on-demand): React performance patterns for component optimization
- clean-code (on-demand): naming, function size, error handling
- solid-principles (on-demand): component interface design
- modern-csharp-coding-standards (skipped — C# only, not a C# project)
- vercel-react-view-transitions (skipped — no route animations in scope)
- clean-architecture (skipped — overkill for a 6-component SPA landing page)
```

Omit this review only when the agent is performing purely read-only work (asking questions, exploring, reading files). Any mutation — including config changes, documentation edits, or code changes — triggers this gate.

## Environment Setup

To configure the local development and delivery environment, run the idempotent all-in-one command:

```bash
python -m tools.sdd_cli environment-lab setup-lab
```

This initialises local files, builds Gitea Actions images, starts Docker Compose services (Gitea, OpenProject, Nexus, Monitoring), and validates observability and CI runner prerequisites. Use `--dry-run true` to preview without making changes.

For step-by-step control, run individual subcommands:

```bash
python -m tools.sdd_cli environment-lab init-local-files
python -m tools.sdd_cli environment-lab compose-up
python -m tools.sdd_cli environment-lab build-gitea-images
python -m tools.sdd_cli environment-lab set-project-stack --values-json '{"frontend": "react", "backend": "fastapi", "database": "postgresql"}'
```

See `.codex/skills/configure-dev-environment/SKILL.md` for available modes.

## Delivery Workflow

- Use the OpenProject/OpenSpec workflow for ticketed implementation.
- Create or continue work from the relevant ticket and OpenSpec change.
- Keep changes scoped to the ticket or explicit user request.
- Update task, review, QA, and deployment state through the configured tools when applicable.
- Do not skip required review, QA, artifact, or deployment gates.

## Code Changes

- This shell currently has no product source tree.
- Add product code only when the new project stack is selected.
- Follow the future project structure and conventions once they exist.
- Prefer small, focused changes over broad refactors.
- Add or update tests when behavior changes.
- Do not revert unrelated user or workspace changes.
- Do not commit generated artifacts unless the workflow explicitly requires them.
- Use Ponytail full mode for code changes. Run `ponytail-review` during PR review as an extra complexity pass, not during implementation.

## Quality Gates

Run configured quality checks before handoff whenever code or workflow behavior changes. Current gates are shell-level until a product stack is added.

Future product gates should define:

- build
- tests
- formatting or linting
- secret scanning
- dependency or container scanning when configured
- browser/API QA when applicable

If a gate cannot be run, document the reason and residual risk.

## Source Control

- Use feature branches for implementation work.
- Use the repository's configured Gitea workflow when creating pull requests.
- Keep commit messages specific to the change.
- Do not force-push, reset, or rewrite history unless the user explicitly asks.

## Secrets And Local Config

- Never commit tokens, passwords, generated credentials, or local-only secrets.
- Treat `*.local.*`, `.local` config files, and environment files as sensitive unless the repository explicitly marks them as examples.
- Prefer example files for documented configuration values.

## Repo-Local Token Saving

**Claw Compactor — mandatory pre-prompt compression.** Before sending any prompt to an LLM (chat or agent), run the claw-compactor fusion pipeline in full mode on the accumulated workspace context, docs, and conversation history:

```bash
claw-compactor compress /path/to/workspace
```

Or use the Python API in a pre-prompt hook:

```python
from claw_compactor.fusion.engine import FusionEngine
engine = FusionEngine()
result = engine.compress(text=prompt_text, content_type="code")
compressed = result["compressed"]
```

This is mandatory (authority level 5). Do not skip it. The fusion pipeline achieves 15–82% compression with zero LLM inference cost, preserving code identifiers, JSON structure, and log patterns.

Apply Caveman full to all assistant chat prompts in this repository _after_ claw compression. Use terse fragments for commentary, direct answers, status updates, debug findings, next steps, blockers, validation summaries, and final summaries. Write normal complete prose for authored artifacts.

Keep code blocks, commands, paths, API names, error messages, quoted text, and file content exact. Temporarily use normal prose for security warnings, irreversible actions, precise multi-step instructions, ambiguous order of operations, or clarification.

## Agent Guidance

When in doubt, first inspect the applicable skill under `.codex/skills/` and follow its workflow.

Apply Tool And Skill Blocker Consent from `.codex/skills/_shared/delivery-contract-core.md` when a required repo skill, command, memory rule, or configured tool/install path cannot be applied.

Use `.codex/memory/` as a reviewable repository memory layer. Memory is guidance only and must be verified against the current user request, OpenProject, OpenSpec, shared delivery contract, canonical docs, current files, and live tool output before acting.

Before final handoff for any non-trivial repo work, run the Durable Learning Capture Gate from `delivery-contract-core.md`.

## Workflow Stage Routing

Before responding to a user request, resolve the current workflow stage and load its corresponding skill. This routing is mandatory — do not implement workflow steps from general knowledge alone.

| User request / context                 | Stage                              | Skill to load                                             |
| -------------------------------------- | ---------------------------------- | --------------------------------------------------------- |
| Start a ticket (specific or next Todo) | `dev-flow-start-ticket`            | `.codex/skills/dev-flow-start-ticket/SKILL.md`            |
| Create / propose an OpenSpec change    | `dev-flow-propose-change`          | `.codex/skills/dev-flow-propose-change/SKILL.md`          |
| Implement a ticket / change            | `dev-flow-implement-ticket`        | `.codex/skills/dev-flow-implement-ticket/SKILL.md`        |
| Continue implementation                | `dev-flow-continue-implementation` | `.codex/skills/dev-flow-continue-implementation/SKILL.md` |
| Review a pull request                  | `dev-flow-pr-review-agent`         | `.codex/skills/dev-flow-pr-review-agent/SKILL.md`         |
| Address PR review feedback             | `dev-flow-pr-review-feedback-loop` | `.codex/skills/dev-flow-pr-review-feedback-loop/SKILL.md` |
| Verify an OpenSpec change              | `dev-flow-verify-change`           | `.codex/skills/dev-flow-verify-change/SKILL.md`           |
| Archive an OpenSpec change             | `dev-flow-archive-change`          | `.codex/skills/dev-flow-archive-change/SKILL.md`          |
| Deploy to QA                           | `dev-ops-deploy-qa`                | `.codex/skills/dev-ops-deploy-qa/SKILL.md`                |
| Deploy to production                   | `dev-ops-deploy-prod`              | `.codex/skills/dev-ops-deploy-prod/SKILL.md`              |
| Rollback production                    | `dev-ops-rollback-prod`            | `.codex/skills/dev-ops-rollback-prod/SKILL.md`            |
| Hotfix production                      | `dev-ops-hotfix-prod`              | `.codex/skills/dev-ops-hotfix-prod/SKILL.md`              |
| Post-merge deploy                      | `dev-ops-post-merge-deploy`        | `.codex/skills/dev-ops-post-merge-deploy/SKILL.md`        |
| File a QA bug                          | `dev-flow-file-qa-bug`             | `.codex/skills/dev-flow-file-qa-bug/SKILL.md`             |
| Check pipeline status                  | `dev-flow-pipeline-status`         | `.codex/skills/dev-flow-pipeline-status/SKILL.md`         |
| Run retrospective audit                | `dev-flow-retrospective-audit`     | `.codex/skills/dev-flow-retrospective-audit/SKILL.md`     |
| Explore a change / ask questions       | `dev-flow-explore-change`          | `.codex/skills/dev-flow-explore-change/SKILL.md`          |

After loading the skill, follow its Workflow section step by step. Do not skip steps. Do not improvise. If a step requires an API call, comment, label, or state change that the skill defines, execute it — do not treat it as optional.

## Mandatory MCP Routing

This repository has two MCP servers for content search — each with a strict domain. Every agent **must** follow `.codex/mcp-instructions.md` (the definitive MCP routing contract) when searching repository content:

| Content Type                                    | MCP Server             | Tool                                                                                | Reason                                                       |
| ----------------------------------------------- | ---------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| Documentation (`.md`, `.mdx`, skills, adapters) | `monorepo-docs-search` | `search_documentation`                                                              | BM25 + FlashRank cross-encoder — token-efficient snippets    |
| Source code (all other files)                   | `codebase-memory-mcp`  | `search_graph`, `get_architecture`, `trace_path`, `get_code_snippet`, `query_graph` | BM25 ranking + structural boosting — definitions rank first  |
| Source code (all other files)                   | `codebase-memory-mcp`  | `search_code`                                                                       | Grep + graph-enriched dedup — for raw regex/pattern matching |

This routing is mandatory (authority level 5 per `docs/context-management.md` — alongside `.codex/skills/_shared/delivery-contract.md`). Do not skip it. Do not use raw grep as the first approach. Do not cross-search domains between MCPs.

## Skill Activation Configuration

- All prompts must trigger skill evaluation by default
- Skills are applied in priority order: caveman > ponytail > others
- Caveman skill auto-activates with intensity: full (unless specified otherwise)
- Ponytail skill auto-activates on every prompt with intensity: full
- Other skills, MCP servers, and capabilities activate per the **Mandatory Pre-Implementation Skill Review** scan results — the scan determines which skills are relevant; activation triggers per-task when implementation begins
- The scan is a **code-change gate**, not a conversation-start gate — purely read-only work (asking questions, exploring, reading files) does not require the scan
