# Artifact Provider Adapter Example

This adapter is a provider-neutral scaffold. Replace this file with a selected provider adapter for a concrete project, or copy it to a provider-specific adapter path and fill in project-specific behavior.

## Operations

- `publish`: store immutable build output.
- `retrieve`: download an existing artifact.
- `verify`: check checksum and manifest integrity.
- `promote-alias`: move an environment or release alias to an existing artifact.
- `publish-evidence`: store QA or release evidence.

## Configuration Boundary

- Keep credentials, tokens, endpoint secrets, and local-only values in ignored local config.
- Keep exact executable commands, image tags, SDK versions, and provider field names in provider-specific adapters or executable workflow files.
- Generic delivery skills call the operation names; this adapter translates them to the selected provider.
