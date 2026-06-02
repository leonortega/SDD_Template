# Release Lessons Memory

## Artifact Identity

- Type: Fact
- Status: Active
- Source: `.codex/skills/_shared/delivery-contract.md`
- Last verified: 2026-05-29

Artifact identity is the commit SHA.

```text
app/{commitSha}/deployable-apps.json
app/{commitSha}/{artifactName}
app/{commitSha}/{artifactName}.sha256
app/{commitSha}/commit.sha
app/{commitSha}/release.json
```

`commit.sha` must exactly match the artifact commit. Each `{artifactName}.sha256` must verify its ZIP before deployment.

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

## Topology Changes Must Reach Live App Settings

- Type: Pattern
- Status: Active
- Source: current conversation, `infra/deployment/apps.json`, `infra/azure/main.bicep`, E2EPROJECT-2 QA evidence
- Last verified: 2026-06-02

When deployable app topology or `appsettings*.json` mappings change, it is not enough for the tracked manifest, Bicep, and workflow to be correct. The live DEV/QA/PROD App Service settings must also be deployed or repaired so non-secret inferred mappings such as web `Api__BaseUrl`, API `Cors__AllowedOrigins__0`, and API `ConnectionStrings__ClientsDb` are present. If QA shows the API works directly but the site cannot call it, compare the rendered site configuration and live Azure app settings against the topology manifest before treating the issue as product code.

