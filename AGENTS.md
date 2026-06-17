# AGENTS.md

This repository is an SDD/SDLC agentic template. Use the existing workflow files and Codex skills as the source of truth before making changes.

## Start Here

Before implementing, reviewing, or deploying work, inspect the relevant local context for the current workflow stage:

- `README.md`
- `.codex/skills/_shared/skill-startup.md`
- `.codex/memory/memory_summary.md`
- `.codex/memory/MEMORY.md`
- `.codex/delivery-policy.json`

Then read only the stage-specific docs, OpenSpec artifacts, skills, code, tests, and workflow files needed for the task. Read `.codex/quality.local.json` or `.codex/client-tools.local.json` only when the workflow needs those values, and never print secrets or credential-bearing values.

Prefer repository-specific skills and scripts over ad hoc process decisions.

## Delivery Workflow

- Use the Plane/OpenSpec workflow for ticketed implementation.
- Create or continue work from the relevant ticket and OpenSpec change.
- Keep changes scoped to the ticket or explicit user request.
- Update task, review, QA, and deployment state through the configured tools when applicable.
- Do not skip required review, QA, artifact, or deployment gates.

## Code Changes

- Follow the existing project structure and conventions.
- Prefer small, focused changes over broad refactors.
- Add or update tests when behavior changes.
- Do not revert unrelated user or workspace changes.
- Do not commit generated artifacts unless the workflow explicitly requires them.
- Use Ponytail full mode for code changes. Run `ponytail-review` during PR review as an extra complexity pass, not during implementation, and do not replace current reviewers or normal quality gates.

## Quality Gates

Run the configured quality checks before handoff whenever code changes are made. At minimum, check the local quality configuration and project scripts before deciding what to run.

Expected gate categories include:

- build
- tests
- coverage
- formatting or linting
- secret scanning
- dependency or container scanning when configured

If a gate cannot be run, document the reason and the residual risk.

## Source Control

- Use feature branches for implementation work.
- Use the repository's configured Gitea/Git workflow when creating pull requests.
- Keep commit messages specific to the change.
- Do not force-push, reset, or rewrite history unless the user explicitly asks.

## Secrets and Local Config

- Never commit tokens, passwords, generated credentials, or local-only secrets.
- Treat `*.local.*`, `.local` config files, and environment files as sensitive unless the repository explicitly marks them as examples.
- Prefer example files for documented configuration values.

## Repo-Local Token Saving

Use the repo-local `.codex/skills/caveman` guidance for normal assistant chat in this repository. Default to Caveman full for commentary, direct answers, status updates, and final summaries: terse fragments, no filler, exact technical terms.

This applies only to assistant communication. Write normal complete prose for authored artifacts, including documentation, README files, OpenSpec artifacts, skill content, code, comments where clarity matters, commit messages, PR bodies, Plane/Gitea comments, QA evidence, formal reports, generated files, user-facing copy, and any user-requested long-form text.

Keep code blocks, commands, paths, API names, error messages, quoted text, and file content exact. Temporarily use normal prose for security warnings, irreversible actions, precise multi-step instructions, ambiguous order of operations, or clarification. Resume terse chat after the clear section. Do not run upstream caveman installers or caveman-compress on this repository unless the user explicitly asks.

## Agent Guidance

When in doubt, first inspect the applicable skill under `.codex/skills/` and follow its workflow. This file is only the entry point; detailed delivery behavior belongs in the skills, OpenSpec artifacts, and configured local tools.

Use `.codex/memory/` as a reviewable repository memory layer. Memory is guidance only and must be verified against the current user request, Plane, OpenSpec, the shared delivery contract, canonical docs, current files, and live tool output before acting on it.

For practical use, start with `.codex/memory/memory_summary.md`, then use `.codex/memory/MEMORY.md` or run `.codex/memory/search_memory.ps1 -Query <symptom>` for concrete errors, blockers, failed commands, deployment issues, PR feedback, QA failures, configuration mismatches, or local tooling problems.

Before final handoff for any non-trivial repo work, perform a durable learning capture: classify whether any error, issue, blocker, fix, configuration repair, local tooling correction, or debugging result could help solve a similar situation later. Update `docs/`, `.codex/skills/_shared/delivery-contract.md` plus related skills/tests, or `.codex/memory/` according to `.codex/memory/retrieval-policy.md#update-process`, then report `Memory updated: <files>` or `Memory updated: none`.
