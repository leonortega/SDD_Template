---
name: configure-quality-gates
description: Configure code quality and CI gates for this repo, including .NET 10 SDK expectations, Lefthook local hooks, Gitleaks, Trivy, optional Semgrep, Gitea PR validation, branch protection guidance, and quality gate templates. Use when Codex needs to set up lint, build, test, security verification, or PR validation workflows.
---

# Configure Quality Gates

Read `.codex/skills/configure-dev-environment/references/quality-gates.md` before asking for values or applying changes.

Use the shared script at `.codex/skills/configure-dev-environment/scripts/configure_infra_tools.ps1`.

Safety:

- Keep Gitea PR validation as the authoritative gate.
- Keep local hooks lightweight.
- Do not write scanner, Gitea, Nexus, or Azure secrets into tracked files.

Workflow:

1. Run `AuditQualityGates`.
2. If templates are missing, ask before running `InitQualityGateTemplates`.
3. For every missing SDK/tool/scanner, provide install command, official URL, and post-install validation/configuration command before continuing.
4. Verify the generated flow uses PR checks for restore, format, build, tests, coverage, dependency audit, Gitleaks, and Trivy.
5. Ask whether Semgrep should be enabled only after real app code exists or the user explicitly wants it.
6. Guide the user to configure Gitea branch protection and required status checks.
