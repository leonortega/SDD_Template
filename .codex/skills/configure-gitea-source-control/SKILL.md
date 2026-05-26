---
name: configure-gitea-source-control
description: Configure Gitea repository and PR automation for this repo, including Gitea API access, repository owner/name, PR reviewers, review labels, and Gitea live validation. Use when Codex needs to set up PR creation/review automation, .codex/client-tools.local.json Gitea settings, reviewers, or labels.
---

# Configure Gitea Source Control

Read `.codex/skills/configure-dev-environment/references/gitea-pr.md` before asking for values or applying changes.

Use the shared script at `.codex/skills/configure-dev-environment/scripts/configure_infra_tools.ps1`.

Safety:

- Do not print Gitea API tokens.
- Do not retrieve tokens from Docker containers, mounted volumes, databases, or logs.
- Do not create labels or mutate the repository during configuration unless explicitly requested.

Workflow:

1. Run `Audit`.
2. Infer owner/repo from `git remote get-url origin` when possible.
3. Ask only for missing or placeholder Gitea/PR values.
4. Apply confirmed `.codex/client-tools.local.json` values with `SetClientTools`.
5. Validate token, repo, collaborators, and labels only when Gitea is running.
