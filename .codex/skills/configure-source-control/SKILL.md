---
name: configure-source-control
description: Configure Gitea repository and PR automation for this repo, including Gitea API access, repository owner/name, PR reviewers, minimum approvals, review labels, and Gitea live validation. Use when Codex needs to set up PR creation/review automation, .codex/client-tools.local.json Gitea settings, reviewers, minimum approvals, or labels.
---

# Configure Gitea Source Control

## Overview

Configure Gitea repository and PR automation used for ticket review, minimum approvals, validation labels, and handoff.

## Shared Context

Read `.codex/skills/configure-dev-environment/references/gitea-pr.md` before asking for values or applying changes.

Use the shared command `python -m tools.sdd_cli configure`.

Apply `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` before changing review, label, ticket, or handoff behavior.

Safety:

- Do not print Gitea API tokens.
- Do not retrieve tokens from Docker containers, mounted volumes, databases, or logs.
- Do not create labels or mutate the repository during configuration unless explicitly requested.

## Workflow

1. Run `Audit`.
2. Infer owner/repo from `git remote get-url origin` when possible.
3. Ask only for missing or placeholder Gitea/PR values.
4. Apply confirmed `.codex/client-tools.local.json` values with `SetClientTools`, including `pr.minimumApprovals.dev` and `pr.minimumApprovals.main`.
5. Apply live Gitea branch protection approval counts with `SetGiteaBranchProtection` when Gitea is running and the user asked to configure Gitea.
6. Validate token, repo, collaborators, branch protection approval minimum, and labels only when Gitea is running.

## Output

Report inferred repo values, missing user-supplied values, validation status, PR approval minimum status, PR label status, and ticket handoff impact without exposing tokens.

## Failure Rules

- Stop when Gitea token, owner/repo, reviewer, approval minimum, or label values are missing.
- Stop before mutating labels or repository settings without explicit user approval.
- Stop before using unvalidated PR automation for ticket delivery.
