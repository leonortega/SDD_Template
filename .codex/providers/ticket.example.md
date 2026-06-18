# Ticket Provider Adapter Example

This adapter is a provider-neutral scaffold. Replace this file with a selected provider adapter for a concrete project, or copy it to a provider-specific adapter path and fill in project-specific behavior.

## Operations

- `list`: list candidate work items.
- `read`: read one work item and acceptance criteria.
- `enrich`: update planning or delivery metadata.
- `move-state`: transition workflow state.
- `comment`: add durable workflow evidence.
- `verify-marker`: confirm a generated marker exists.

## Configuration Boundary

- Keep credentials, tokens, endpoint secrets, and local-only values in ignored local config.
- Keep exact executable commands, image tags, SDK versions, and provider field names in provider-specific adapters or executable workflow files.
- Generic delivery skills call the operation names; this adapter translates them to the selected provider.
