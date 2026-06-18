# Ticket Adapter: Plane

Use this adapter only when `.codex/project-profile.json` selects `providers.ticket.id = "plane"`.

## Runtime Configuration

- Read non-secret provider identity from `.codex/project-profile.json`.
- Read local endpoint, token, workspace, project, and state names from `.codex/client-tools.local.json`.
- Use `.codex/client-tools.example.json` only for placeholder shape.
- Never print tokens, cookies, session values, or secret-bearing URLs.

## Operations

- `list`: query work items by configured workspace, project, and state.
- `read`: fetch title, description, state, comments, and acceptance criteria.
- `enrich`: update only the managed generated block between `<!-- ia-generated:start -->` and `<!-- ia-generated:end -->`.
- `move-state`: move to the configured target state only after workflow gates pass.
- `comment`: write generated comments with the stable marker as the first line.
- `verify-marker`: re-read comments and verify the marker appears in stripped text before reporting success.

## Stable Markers

Use the marker names from `.codex/skills/_shared/delivery-contract.md`. Keep marker text searchable and provider-neutral except for API field names required by this adapter.

## Failure Rules

- Stop before mutation when Plane config is missing, the ticket is ambiguous, or the current state conflicts with the active delivery lock.
- Plane API comment mutations must send both rendered and stripped content fields expected by the Plane API.
- Do not read Plane data from containers, databases, or mounted volumes.
