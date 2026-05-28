---
name: automatic-implement-ticket
description: Orchestrate the full Plane ticket delivery lifecycle by inspecting current Plane, Git, Gitea, Nexus, OpenSpec, QA, tag, and PROD state, then delegating to the correct focused skill. Use when Codex is asked to automatically continue, resume, implement, deploy, QA, or hand off a ticket without the user knowing the current workflow step.
---

# Automatic Implement Ticket

## Overview

Use this master skill as the default high-level entry point for normal ticket delivery. It does not duplicate child skill workflows. It inspects state, chooses the next valid milestone, invokes the focused child skill, and reports the exact blocker when automation cannot continue.

PROD promotion remains explicit. Do not invoke `deploy-to-prod` only because QA passed unless the user explicitly asks to promote to PROD.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` only for structure and defaults. Read `.codex/quality.local.json` when coverage context is needed.

Never print, commit, paste into tickets, or write real Plane, Gitea, Nexus, Azure, cookie, or session secrets.

## State Inspection

Before delegating, inspect as much context as is safely available:

- Plane ticket key, state, generated markers, linked parent/bug tickets, and deployment/QA/PROD comments.
- Current Git branch, branch naming, local dirty state, remote branch, active OpenSpec change, and relevant tags.
- Gitea PR status, target branch, merge status, head/merge commit, review markers, and `needs-tests` / `needs-changes` labels.
- Nexus artifact files under `app/{commitSha}/`: `app.zip`, `app.zip.sha256`, `commit.sha`, and `release.json`.
- QA evidence marker `IA generated E2E QA: {ticketKey}` and source RC tag.
- PROD marker `IA generated PROD deployment: {finalVersion}` and latest release manifest.

If the state is ambiguous, invoke `pipeline-status` or produce a read-only status summary instead of guessing.

## Routing

- Ticket in Todo with no branch: invoke `plane-start-ticket`.
- Ticket in In Progress with active branch/OpenSpec but no PR: invoke `implement-ticket`.
- Open PR exists: invoke or resume `implement-ticket` review/fix loop.
- PR merged to `dev` and artifact is not yet promoted to QA: invoke `post-merge-deploy`.
- Ticket in QA: invoke `test-e2e`.
- QA failed with product defect: invoke `file-qa-bug`.
- Ticket in Done with QA-approved RC but no PROD release: stop unless the user explicitly requested PROD; if requested, invoke `deploy-to-prod`.
- PROD incident or regression: invoke `rollback-prod` when restore is needed, or `hotfix-prod` when a targeted code fix is needed.
- User asks where the work stands, or routing has multiple plausible targets: invoke `pipeline-status`.

## Rerun Policy

Treat existing generated comments, branches, PRs, artifacts, QA evidence, and tags as checkpoints. Continue from the latest completed checkpoint instead of restarting earlier steps.

When a child skill stops on a blocker, preserve its blocker classification and do not route around it. Examples:

- Missing Nexus artifact blocks deployment promotion.
- Stale `needs-changes` or `needs-tests` labels block QA promotion.
- Missing RC tag blocks PROD promotion.
- QA product defect routes to `file-qa-bug`, not direct code edits inside QA.

## Output

Summarize:

- ticket and current state,
- resolved route,
- child skill invoked or blocker found,
- checkpoint evidence used,
- next required user or system action when blocked.
