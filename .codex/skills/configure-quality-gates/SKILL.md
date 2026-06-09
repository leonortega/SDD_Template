---
name: configure-quality-gates
description: Configure code quality and CI gates for this repo, including .NET 10 SDK expectations, coverage minimum percentage, Lefthook local hooks, Gitleaks, Trivy, optional Semgrep, Gitea PR validation, branch protection guidance, and quality gate templates. Use when Codex needs to set up lint, build, test, coverage, security verification, or PR validation workflows.
---

# Configure Quality Gates

## Overview

Configure local and CI quality gates used for ticket implementation validation and PR handoff.

## Shared Context

Read `.codex/skills/configure-dev-environment/references/quality-gates.md` before asking for values or applying changes.

Use the shared script at `.codex/skills/configure-dev-environment/scripts/configure_infra_tools.ps1`.

Keep this skill synchronized with `.codex/skills/_shared/delivery-contract.md` and the non-OpenSpec delivery-flow skills. When behavior differs, delivery-flow skills are authoritative.

Also apply `docs/context-management.md` when quality-gate findings should update durable docs or ticket handoff notes.

Safety:

- Keep Gitea PR validation as the authoritative gate.
- Keep local hooks lightweight.
- Do not write scanner, Gitea, Nexus, or Azure secrets into tracked files.

## Workflow

1. Run `AuditQualityGates`.
2. If templates are missing, ask before running `InitQualityGateTemplates`.
3. For every missing SDK/tool/scanner, provide install command, official URL, and post-install validation/configuration command before continuing.
4. Ensure `.codex/quality.local.json` exists from `.codex/quality.example.json`; default `coverage.minimumPercent` is `80`.
5. Use `SetQualityConfig` when the user wants a different coverage threshold; never write scanner, Gitea, Nexus, Azure, or Plane secrets there.
6. Verify the generated flow uses PR checks for restore, format, build, application tests only, coverage collection, coverage threshold enforcement, dependency audit, Gitleaks, and Trivy. CI restore, format, build, test, coverage, dependency-audit, and publish commands must target product/application projects, not SDD template, delivery-tool, workflow, agent, OpenSpec, infrastructure, or meta-test projects.
7. Run or recommend `BuildGiteaActionsImages` so Gitleaks, Trivy, Azure CLI, jq, zip, Node, and Playwright runtime dependencies are supplied by pinned local CI images instead of installed during every workflow run.
8. Run `ValidateGiteaActionsRunner` when Docker is available to catch missing local job images, missing shell tools, JavaScript action/node mismatches, and local Gitea checkout networking before a PR depends on CI.
9. Ask whether Semgrep should be enabled only after real app code exists or the user explicitly wants it.
10. Guide the user to configure Gitea branch protection and required status checks.

## Output

Report quality-gate templates, local config, missing tools, validation commands, CI status expectations, and ticket handoff risks without exposing secrets.

## Failure Rules

- Stop when required SDKs, scanners, or CI runner validation are missing and provide official install/setup guidance.
- Stop before weakening PR validation, coverage, secret scanning, dependency audit, or Trivy gates.
- Stop before writing scanner, Gitea, Nexus, Azure, or Plane secrets into tracked files.
