# Repository And Review Provider Adapter Example

This adapter is a provider-neutral scaffold. Replace this file with a selected provider adapter for a concrete project, or copy it to a provider-specific adapter path and fill in project-specific behavior.

## Operations

- `branch`: create or inspect a branch.
- `push`: publish branch changes.
- `pull-request`: create or update a review request.
- `status`: read validation state.
- `label`: add or remove review labels.
- `comment`: add review evidence.
- `request-reviewers`: request human review.

## Configuration Boundary

- Keep credentials, tokens, endpoint secrets, and local-only values in ignored local config.
- Keep exact executable commands, image tags, SDK versions, and provider field names in provider-specific adapters or executable workflow files.
- Generic delivery skills call the operation names; this adapter translates them to the selected provider.
