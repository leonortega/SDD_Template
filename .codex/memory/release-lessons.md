# Release Lessons Memory

## Artifact Identity

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Artifact identity is the commit SHA.

```text
app/{commitSha}/app.zip
app/{commitSha}/app.zip.sha256
app/{commitSha}/commit.sha
app/{commitSha}/release.json
```

`commit.sha` must exactly match the artifact commit. `app.zip.sha256` must verify the ZIP before deployment.

## Release Manifest

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Required baseline `release.json` fields:

- `schemaVersion`
- `commitSha`
- `checksum`
- `artifactUrl`
- `planeTicketKey`
- `versionStatus`

Preserve existing manifest fields when adding stage-specific data.

## Version Formats

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

- Source RC format: `vMAJOR.MINOR.PATCH-rc.N`
- Final release format: `vMAJOR.MINOR.PATCH`
- RC tags must be annotated and point to the tested artifact commit.
- Final tags must be annotated and point to the QA-approved artifact commit.

## PROD Promotion

- Type: Fact
- Status: Active
- Source: `README.md`, `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

PROD promotion is explicit and artifact-based. Do not promote to PROD only because QA passed.

## Rollback

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Rollback restores PROD to a previously verified Nexus artifact. Rollback does not rewrite `main`. After rollback, require a hotfix PR, revert PR, or explicit temporary divergence note with owner and expected resolution.

## Hotfix

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`, `.codex/skills/hotfix-prod/`
- Last verified: 2026-05-29

Production hotfixes should remain expedited but gated. They still require ticket/incident context, branch and PR handling, review, immutable artifact deployment, QA evidence, and explicit PROD promotion.

