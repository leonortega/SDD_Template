<!-- TIER 3: STAGE-SPECIFIC - Deploy stage (post-merge, CI, QA deploy, PROD deploy) -->

# Delivery Contract — Deploy (post-merge, CI, QA deploy, PROD deploy)

Stage-specific rules for CI quality split, Nexus artifacts, deployment configuration, release manifest, and versioning. Read in addition to `delivery-contract-core.md`.

---

## Local And CI Quality Split

Local validation is for fast feedback and test authoring. Agents should run targeted builds, tests, and cheap checks that correspond to the touched behavior and risk, then hand off the full required gate to Gitea PR validation. Do not require a full local duplicate of restore, format, release build, coverage, dependency audit, full secret scan, and filesystem scanner before opening or updating a PR unless the ticket or risk explicitly requires it.

Gitea PR validation is authoritative for restore, formatting verification, release build, tests with coverage, coverage threshold, dependency vulnerability audit, full secret scanning, and filesystem scanning in a clean pinned runner. Merge and deployment jobs should focus on immutable artifact packaging, deployment configuration verification, and environment smoke checks; they should not rerun the same unit test suite unless package or artifact inputs changed outside the already-validated PR path.

`config infra` owns building and validating repo-owned Gitea Actions job images. Workflows should consume pinned local images for common CI tools instead of installing tools during every run.

## Nexus Artifacts

Nexus is mandatory for DEV, QA, PROD, and rollback promotion. Do not rebuild between environments and do not deploy from local files.

Artifact identity is the commit SHA:

```
text
app/{commitSha}/deployable-apps.json
app/{commitSha}/{artifactName}
app/{commitSha}/{artifactName}.sha256
app/{commitSha}/commit.sha
app/{commitSha}/release.json
app/{commitSha}/container-images.json
app/{commitSha}/monitoring-summary-{environment}.json
app/{commitSha}/qa-observability.json
```

`deployable-apps.json` is the packaged copy of `infra/deployment/apps.json` sorted for deployment. `commit.sha` must exactly match the artifact commit. Every `{artifactName}.sha256` listed by the topology must verify before ZIP deployment.

Human-readable Nexus version folders are aliases only. Do not move or rename canonical ZIP artifacts out of `app/{commitSha}/`. QA approval may publish `app/qa-approved/latest.json`, `app/rc/{sourceRcVersion}/artifact-pointer.json`, and `app/rc/{sourceRcVersion}/release.json`; PROD success may publish `app/releases/{finalReleaseVersion}/artifact-pointer.json` and `app/releases/{finalReleaseVersion}/release.json`.

## Deployment Configuration Drift

Every deployable app configuration key must be discovered, mapped, applied, and verified before DEV, QA, or PROD deployment can be reported as successful.

Rules:

- `configure-cloud-environments` owns `infra/deployment/configuration.json`, the tracked placeholder-safe mapping from flattened `appsettings*.json` keys to deploy-time settings.
- The package workflow must build `deployment-config.json` and publish it next to `deployable-apps.json` in Nexus.
- Deployment jobs must apply and verify `deployment-config.json` for every target environment before claiming success.
- Non-interactive CI and deploy automation must fail closed when a required key is unmapped, marked `manualRequired`, missing from live settings, or mismatched.

## Release Manifest

Validate `release.json` against `.codex/skills/_shared/release.schema.json` when reading or writing it. Preserve existing fields when adding stage-specific data.

Required baseline fields:

- `schemaVersion`, `commitSha`, `checksum`, `artifactUrl`, `ticketKey`, `versionStatus`
- Optional `includedTickets` records the Done tickets included in a PROD release.

Stage-specific fields:

- DEV/QA deployment: DEV/QA URLs, statuses, health checks, PR URL, workflow URL.
- E2E QA: source RC version, QA evidence URL, QA result, tested URLs, QA timestamp.
- PROD: final release version, final tag, PROD URL, PROD statuses, monitoring status, PROD timestamp.
- Rollback: rollback timestamp, rollback workflow URL, rollback source/current version relationship.

## Version Rules

- Source RC format: `vMAJOR.MINOR.PATCH-rc.N`
- Final release format: `vMAJOR.MINOR.PATCH`
- RC tags must be annotated and point to the tested artifact commit.
- Final tags must be annotated and point to the QA-approved artifact commit.
- If no RC is supplied, derive the next RC from existing tags only when unambiguous.
