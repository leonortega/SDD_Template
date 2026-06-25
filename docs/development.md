# Development

This repository currently has no product implementation. It is ready for a new product stack to be introduced through the normal ticket and OpenSpec workflow.

## Current Project Shape

- Product source: not present yet.
- Product tests: not present yet.
- Delivery helpers: `tools/`.
- OpenSpec config: `openspec/config.yaml`.
- Repo-local Codex workflows: `.codex/skills/`.
- Platform infrastructure: `infra/`.

## Adding The Next Product

When the stack is chosen:

1. Add languages, frameworks, test frameworks, and stack-specific adapters to ignored `.codex/project-profile.local.json` while exploring the new project.
2. Add product source and test folders.
3. Add OpenSpec specs for product behavior.
4. Add deployment app targets and configuration mappings.
5. Replace placeholder Gitea workflows with stack-specific build, test, package, deployment, and QA jobs.
6. Add only the skills, MCPs, tools, and documentation needed for that chosen stack.

## Consumer Fixture Repositories

Use a separate repository to validate this tool as a real consumer would:

```bash
python -m tools.sdd_cli tool install --version v0.1.0 --target C:\path\to\consumer-repo
python -m tools.sdd_cli tool update --version v0.2.0 --target C:\path\to\consumer-repo
```

The consumer repo should not contain this tool's internal tests, memory, eval files, or experimental OpenSpec changes. Put product-specific source, tests, local profile overlays, secrets, and product OpenSpec changes in the consumer repo; the update command preserves them because they are not managed tool files.

## Development Rules

- Use the OpenProject/OpenSpec workflow for ticketed changes.
- Keep changes scoped to the active ticket or explicit user request.
- Use TDD for product behavior once a stack exists.
- Use Playwright for browser-visible flows when the future product has a UI.
- Keep docs, `.codex/project-profile.json`, and `.codex/project-profile.local.json` synchronized with stack and workflow changes.
- Do not add speculative stack guidance, dependencies, or CI jobs before the new product needs them.

## Quality Gates

Current placeholder workflows only protect the shell from obvious mistakes. Product-specific quality gates must be added with the next stack.

Expected future gate categories:

- build
- tests
- formatting or linting
- security scanning
- deployment/package verification
- browser or API QA when applicable

The exact commands belong to the future stack, not this empty shell.

## Context Findings

Every non-trivial repo change still needs a context findings review. Durable workflow findings belong in `docs/`, the shared delivery contract, affected skills, or `.codex/memory/` depending on authority.
