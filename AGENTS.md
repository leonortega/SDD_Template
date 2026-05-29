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

## Agent Guidance

When in doubt, first inspect the applicable skill under `.codex/skills/` and follow its workflow. This file is only the entry point; detailed delivery behavior belongs in the skills, OpenSpec artifacts, and configured local tools.

Use `.codex/memory/` as a reviewable repository memory layer. Memory is guidance only and must be verified against the current user request, Plane, OpenSpec, the shared delivery contract, canonical docs, current files, and live tool output before acting on it.
