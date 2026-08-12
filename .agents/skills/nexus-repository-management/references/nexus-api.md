# Artifact Adapter: Nexus

Use this adapter only when `.template/project-profile.json` selects `providers.artifact.id = "nexus"`.

## Runtime Configuration

- Read non-secret artifact policy from `.template/project-profile.json`.
- Read local endpoint, repository, username, and password/token from `.template/client-tools.local.json`.
- Keep artifact identity and manifest schema in `.agents/skills/_shared/delivery-contract.md` and
`.agents/skills/_shared/release.schema.json`.

## Operations

- `publish`: upload build outputs, checksums, topology metadata, and `release.json` under `app/{commitSha}/`.
- `retrieve`: download existing artifacts and manifests by commit SHA.
- `verify`: compare checksums and validate `release.json`.
- `promote-alias`: publish human-readable pointer aliases without moving canonical artifacts.
- `publish-evidence`: upload QA evidence bundles when configured.

## Failure Rules

- Build once and promote the same artifact across environments.
- Do not rebuild between DEV, QA, PROD, or rollback.
- Do not rename or duplicate canonical ZIP artifacts to represent release versions.
- Stop when the artifact commit, checksum, manifest, or ticket lineage conflicts with the delivery lock.
