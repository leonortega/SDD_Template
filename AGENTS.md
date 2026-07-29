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

Then read only the stage-specific docs, OpenSpec artifacts, skills, and workflow files needed for the task. Read local config only when the workflow needs those values, and never print secrets or credential-bearing values.

Prefer repository-specific skills and scripts over ad hoc process decisions.

<!-- CACHE BREAKPOINT: End Tier 1 - Stable session context. Dynamic per-turn data below. -->

## Mandatory Skill Declaration

Every agent **must** declare which skills it is activating for each step of the lab flow or any repo interaction. This includes both auto-activated skills and on-demand skills. The skills to list are determined by the **Mandatory Skill Catalog Review** process (see below).

**Format**: At the start of each response (after Caveman loading), include a `Skills used:` block. Reference each skill by its manifest category and name, and note whether it's active or skipped.

**Authority level**: 5 (same as Mandatory First Step, Mandatory MCP Routing).

**Examples**:

```markdown
Skills used: caveman (full), ponytail (full)

- caveman (auto, full): terse format
- ponytail (auto, full): code quality
- architecture/clean-architecture (manifest → architecture): dependency rule guidance for module boundaries
- test/e2e-testing-patterns (manifest → test): flaky test debugging
- deploy/release-it (manifest → deploy): circuit breaker pattern for retry logic
- security/owasp-security (skipped — no user input or auth in this scaffold)
- kubernetes/kubernetes-manifest-authoring (skipped — no K8s deployment in this ticket)
```

Failure to declare used skills violates repo convention. If a skill is auto-activated (caveman, ponytail), still declare it — do not assume it is implicit.

## Mandatory Skill Catalog Review

Before every task (read-only work excluded), every agent **must** consult the skill manifest at `.codex/skills/manifest.json` and determine which skills are relevant. This is a hard gate: no work begins until the catalog is reviewed and skills are declared.

**Authority level**: 5 (same as Mandatory First Step, Mandatory Skill Declaration, Mandatory MCP Routing).

### Review Process

1. **Read the manifest:** Open `.codex/skills/manifest.json` and inspect the `categories` section to find skill groups relevant to the current task.
2. **Assess relevance:** For each relevant category, review its skills and determine which rules, patterns, or constraints apply:
   - **Relevant** → Load the skill via `skill('<name>')` and apply its rules during the task.
   - **Irrelevant** → State the specific reason it does not apply (e.g., "C# coding standards — this is a TypeScript project", "View transitions — no route animations in scope").
3. **Declare with justification:** The `Skills used:` block (required by Mandatory Skill Declaration) must document the outcome of this review:
   - List every skill and whether it is active or skipped.
   - For skipped skills, include a brief rationale.
4. **Blockers:** If a required skill exists but cannot be loaded or applied (e.g., broken `SKILL.md`, conflicting instructions), stop and report the blocker. Apply Tool And Skill Blocker Consent from `delivery-contract-core.md`.

### Example Declaration

```markdown
Skills used: caveman (full), ponytail (full)

- caveman (auto, full): terse format
- ponytail (auto, full): code quality
- architecture/clean-architecture (manifest → architecture): dependency rule guidance for module boundaries
- test/e2e-testing-patterns (manifest → test): flaky test debugging
- deploy/release-it (manifest → deploy): circuit breaker pattern for retry logic
- security/owasp-security (skipped — no user input or auth in this scaffold)
- kubernetes/kubernetes-manifest-authoring (skipped — no K8s deployment in this ticket)
```

Omit this review only for purely read-only work (asking questions, exploring, reading files without changing them). Any mutation — including code changes, config edits, documentation updates, or PR reviews — triggers this gate.

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

### Skill Installation (Hybrid: npx skills + GitHub)

Skills are installed using a hybrid approach:
1. **Primary**: `npx skills add <owner/repo> --skill <name> --yes` (skills.sh registry)
2. **Fallback**: GitHub raw content copy from configured sources

The `install-skill` command tries npx first, and if that fails or npx is unavailable, falls back to fetching files directly from GitHub.

#### List available skills from GitHub sources

```bash
python -m tools.sdd_cli tool-installer list-skills
```

Reads configured sources from `.codex/skill-sources.json` (or `.codex/skill-sources.example.json`) and lists all discoverable skill directories from each GitHub repo.

#### Install a skill

```bash
# By source name (looks up repo + path from config):
python -m tools.sdd_cli tool-installer install-skill --source awesome-copilot --skill-name my-skill

# Direct (repo + path + name):
python -m tools.sdd_cli tool-installer install-skill --repo owner/repo --skill-path path/to/skill --skill-name my-skill
```

#### Preview without downloading

```bash
python -m tools.sdd_cli tool-installer list-skills --dry-run true
python -m tools.sdd_cli tool-installer install-skill --source awesome-copilot --skill-name my-skill --dry-run true
```

#### Default configured sources

The shipped `.codex/skill-sources.example.json` includes:

| Name | Repo | Description |
|------|------|-------------|
| `awesome-copilot` | `github/awesome-copilot` (skills/) | GitHub's awesome-copilot skills collection |
| `anthropics` | `anthropics/skills` (skills/) | Anthropic's skills collection |

Users can also install skills from any GitHub repo by passing `--repo`, `--skill-path`, and optionally `--token` for authenticated requests.

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

## Mandatory Pre-Action Routing Check

**Before every response that mutates state** (git, ticket provider, OpenSpec, comments, labels, API calls), every agent **must**:

1. **Resolve the stage** — Identify which workflow stage the user's request maps to.
2. **Check the routing table below** — Find the matching `User request / context` row.
3. **Load the skill** — Read the corresponding SKILL.md and follow its Workflow section step by step.
4. **If no match** — Stop and ask the user which workflow stage they want (e.g., "Start a ticket? Implement? Review? Deploy?").

**This is a hard gate (authority level 5).** Do not:
- Skip the routing check.
- Implement workflow steps from general knowledge alone.
- Rely on what a previous agent did — always re-check the table.
- Use any fallback mechanism instead of `time-telemetry-upsert`.

### ⚠️ Common Mistakes That Trigger This Gate

- User says "implement" → MUST load `dev-flow-implement-ticket` skill. Do NOT start coding without it.
- Step 15 in start-ticket says "use dev-flow-propose-change skill" → MUST load that skill and run its full artifact-generation workflow.
- Telemetry says "OpenProject time entries" → MUST call `time-telemetry-upsert` via POST /api/v3/time_entries. If the API fails, stop and report. There is no alternative path.

---

## Workflow Stage Routing

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
| CI deploy completed / post-deploy update | `grafana-board-update`             | `.codex/skills/grafana-board-update/SKILL.md`             |
| File and fix a QA bug                  | `dev-flow-file-qa-bug`             | `.codex/skills/dev-flow-file-qa-bug/SKILL.md`             |
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
