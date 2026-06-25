# Quality Gates Configuration

Owns:

- `.codex/delivery-policy.json`
- `.editorconfig`
- `.codex/quality.common.json`
- `.codex/quality.local.json`
- `lefthook.yml`
- `.gitea/workflows/pr-validation.yml`
- `.gitea/workflows/README.md`

## Strategy

- Current PR validation is shell-level because no product stack exists.
- Local hooks run staged secret scanning and commit-message validation.
- Product-specific build, test, coverage, formatting, dependency, package, deploy, and QA gates must be added with the future stack.
- Do not write scanner, Gitea, Nexus, or environment secrets into tracked files.
- Keep future workflow images pinned and locally buildable when the stack introduces them.

## Local Hooks

Use Lefthook by default:

- `pre-commit`: `gitleaks protect --staged --redact`.
- `commit-msg`: require a ticket, OpenSpec id, or `[SDD]` direct maintenance prefix.

## PR Validation

The current placeholder workflow validates JSON files and runs a full Gitleaks scan. Replace it with stack-specific gates when product source and tests are added.

Expected future gate categories:

- restore or dependency install
- formatting or linting
- build
- tests
- coverage when configured
- dependency/security scan
- package verification

## Branch Protection

Ask the user to configure Gitea branch protection:

- Block direct pushes to `dev` and `main`.
- Require pull requests into `dev`.
- Require the configured PR validation workflow to pass.
- Require review approval(s) or the configured review label.
- Block merge while `needs-changes` is present.

## Deployment Gating

Push-triggered deployments should stay disabled until a product app target exists. Once a stack is added, deployment workflows must be ticket-gated by `.codex/project-profile.json` `workflow.ticketKeyPattern` and changed deploy-trigger paths.
