---
name: plane-start-ticket
description: Start Plane work items from chat by listing Todo tickets, preparing safe Git branches, generating OpenSpec-style planning notes, updating the Plane ticket description, and commenting with the branch. Use when the user asks to start the next Plane ticket, start a specific ticket such as E2EPROJECT-1, list Todo Plane tickets, prepare a ticket branch, or connect Plane ticket work to the local Git/OpenSpec workflow.
---

# Plane Start Ticket

## Overview

Use this skill for a chat-driven Plane workflow. The user should not need to run a command; Codex should call the configured Plane API and local Git commands from the conversation.

For setup details and branch pattern options, read `references/configuration.md` when configuration is missing or the user asks how to configure the tools.

## Configuration

Read `.codex/client-tools.local.json` as the primary configuration file. Fall back to `.codex/client-tools.example.json` only for defaults and setup guidance, then apply environment variable overrides only when present. Defaults are:

- Plane API base URL: `http://agentic.lvh.me:8080`
- Plane API token field: `plane.apiToken`
- Plane workspace slug: `e2etest`
- Plane project identifier: `E2EPROJECT`
- Todo state: `Todo`
- Base branch: `dev`
- Branch prefix: `feat`
- Branch pattern: `{prefix}/{ticketKeySlug}-{titleSlug}`
- Max branch length: `100`

Optional environment variables override local JSON config when present: `PLANE_BASE_URL`, `PLANE_API_TOKEN`, `PLANE_WORKSPACE_SLUG`, `PLANE_PROJECT_IDENTIFIER`, `PLANE_TODO_STATE`, `GIT_BASE_BRANCH`, `GIT_BRANCH_PREFIX`, `GIT_BRANCH_PATTERN`.

Never print, store, or write real tokens into repo files, branch names, ticket text, logs, or OpenSpec artifacts.

## Workflow

### No Ticket Specified

1. List Plane tickets in the configured Todo state using the Plane API with credentials from local JSON config or optional environment overrides.
2. Show ticket key, title, and state.
3. Ask the user to choose a ticket.
4. Do not mutate Git or Plane while only listing tickets.

### Ticket Specified

1. Fetch the Plane ticket by key or id.
2. Check `git status --porcelain`. If any output exists, stop and report changed files.
3. Switch to the configured base branch and run `git pull --ff-only`.
4. Create or reuse the configured branch name.
5. Analyze the ticket description in an OpenSpec explore style.
6. Update only the managed generated block in the Plane ticket description.
7. Add a Plane ticket comment with the branch name and base branch.

## Branch Naming

Build branch names from the configured pattern. Supported placeholders:

- `{prefix}`
- `{ticketKeySlug}`
- `{projectKeySlug}`
- `{titleSlug}`

Slug rules:

- Lowercase all text.
- Replace non-alphanumeric runs with `-`.
- Collapse repeated dashes.
- Trim leading and trailing dashes.
- Cap to configured max length.

Default example:

```text
feat/e2eproject-1-create-files-and-folders-for-a-site
```

## Generated Ticket Block

Use this exact generated section in the Plane ticket description:

```text
---

IA generated

<!-- ia-generated:start -->

Acceptance criteria:
- ...

Expected files/components affected:
- ...

Validation command or test expectation:
- ...

<!-- ia-generated:end -->
```

On rerun, replace only the content between `<!-- ia-generated:start -->` and `<!-- ia-generated:end -->`. Preserve all human-written text outside the markers exactly. If only one marker exists, stop and ask for manual cleanup.

Acceptance criteria must be concrete and testable. Reject and regenerate criteria containing generic wording such as `works correctly`, `as expected`, or `properly implemented`.

## Plane Access

Use the Plane API only. Never use Plane MCP, Docker containers, or direct database access for Plane.

Load credentials from `.codex/client-tools.local.json` or optional environment overrides only. Use `plane.apiToken` as the API key value and send it with the `X-API-Key` header. Avoid echoing request headers, tokens, or full credential-bearing URLs.

Use Plane's current `work-items` endpoints, not deprecated `issues` endpoints. Workspace slugs are case-sensitive in API paths; use the lowercase slug from the Plane URL. If only `projectIdentifier` is configured, resolve it through `GET /api/v1/workspaces/{workspace_slug}/projects/` and use the returned project UUID for project-scoped `work-items` calls.

## Failure Rules

- Dirty working tree: stop before branch creation or Plane mutation.
- Missing Plane API config: explain the missing setup and reference `references/configuration.md`.
- Invalid or empty title slug: fall back to a ticket-key-only branch segment.
- Existing branch: switch to it instead of creating a duplicate.
- Failed fast-forward pull: stop and report the branch issue.
- Malformed generated markers: stop before updating the ticket.
- Weak generated analysis: regenerate before updating Plane.
