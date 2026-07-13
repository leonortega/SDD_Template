# AGENTS.md

This repository is a product-free SDD/SDLC agentic shell. Use the workflow files and Codex skills as the source of truth before making changes.

## Start Here

Before implementing, reviewing, or deploying work, inspect the relevant local context for the current workflow stage:

- `README.md`
- `.codex/skills/_shared/skill-startup.md`
- `.codex/memory/memory_summary.md`
- `.codex/memory/MEMORY.md`
- `.codex/delivery-policy.json`

Then read only the stage-specific docs, OpenSpec artifacts, skills, provider adapters, and workflow files needed for the task. Read local config only when the workflow needs those values, and never print secrets or credential-bearing values.

Prefer repository-specific skills and scripts over ad hoc process decisions.

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

Apply Caveman full to all assistant chat prompts in this repository *after* claw compression. Use terse fragments for commentary, direct answers, status updates, debug findings, next steps, blockers, validation summaries, and final summaries. Write normal complete prose for authored artifacts.

Keep code blocks, commands, paths, API names, error messages, quoted text, and file content exact. Temporarily use normal prose for security warnings, irreversible actions, precise multi-step instructions, ambiguous order of operations, or clarification.

## Agent Guidance

When in doubt, first inspect the applicable skill under `.codex/skills/` and follow its workflow.

When a required repo skill, command, memory rule, definition, or configured tool/install path cannot be applied, stop the affected flow. Report the failed required item, why it is required, the current-flow fix, the viable alternative, and the alternative's risk or impact, then ask the user whether to fix the current flow or continue with the alternative.

Use `.codex/memory/` as a reviewable repository memory layer. Memory is guidance only and must be verified against the current user request, OpenProject, OpenSpec, shared delivery contract, canonical docs, current files, and live tool output before acting.

Before final handoff for any non-trivial repo work, perform a durable learning capture. Update `docs/`, `.codex/skills/_shared/delivery-contract.md` plus related skills/tests, or `.codex/memory/` according to `.codex/memory/retrieval-policy.md#update-process`, then report `Memory updated: <files>` or `Memory updated: none`.

## Mandatory MCP Routing

This repository has two MCP servers for content search — each with a strict domain. Every agent **must** follow `.codex/mcp-instructions.md` (the definitive MCP routing contract) when searching repository content:

| Content Type | MCP Server | Tool | Reason |
|---|---|---|---|
| Documentation (`.md`, `.mdx`, skills, adapters) | `monorepo-docs-search` | `search_documentation` | BM25 + FlashRank cross-encoder — token-efficient snippets |
| Source code (all other files) | `codebase-memory-mcp` | `search_graph`, `get_architecture`, `trace_path`, `get_code_snippet`, `query_graph` | BM25 ranking + structural boosting — definitions rank first |
| Source code (all other files) | `codebase-memory-mcp` | `search_code` | Grep + graph-enriched dedup — for raw regex/pattern matching |

This routing is mandatory (authority level 5 per `docs/context-management.md` — alongside `.codex/skills/_shared/delivery-contract.md`). Do not skip it. Do not use raw grep as the first approach. Do not cross-search domains between MCPs.

## Skill Activation Configuration
- All prompts must trigger skill evaluation by default
- Skills are applied in priority order: caveman > ponytail > others
- Caveman skill auto-activates with intensity: full (unless specified otherwise)
- Ponytail skill auto-activates on every prompt with intensity: full
- Other skills, MCP servers, and capabilities activate on demand when relevant to the task
