# Deployment

Deployment is ticket-gated and artifact-based. The workflow promotes one immutable Nexus artifact through DEV, QA, PROD, and rollback paths without rebuilding between environments.

## Flow

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

Push-triggered deployment is allowed only for ticket-named application changes. The ticket key pattern is configured in `.codex/delivery-policy.json`. `[SDD]`, OpenSpec-only, chore, and ops-only maintenance commits do not deploy environments automatically.

## Artifacts

Nexus stores artifacts by commit SHA:

```text
app/{commitSha}/app.zip
app/{commitSha}/app.zip.sha256
app/{commitSha}/commit.sha
app/{commitSha}/release.json
```

`commit.sha` must match the artifact commit. `app.zip.sha256` must verify before deployment. `release.json` records ticket, artifact, environment, QA, version, PROD, and rollback lineage.

## Environments

DEV and QA deploy from `dev` and must use the same Nexus ZIP artifact for the same commit SHA. Both environments must pass page and `/health` smoke checks.

PROD deploys only a QA-approved existing Nexus artifact. PROD does not rebuild. Promotion requires a final version, source RC version, verified artifact commit, and successful PROD page and `/health` checks.

## QA Evidence And Versions

E2E QA evidence is stored under ignored local paths:

```text
artifacts/qa/{ticketKey}/{runId}/
```

The preferred durable publication target is Nexus at:

```text
qa/{ticketKey}/{runId}/qa-evidence.zip
```

RC tags identify QA-approved artifacts. Final tags identify production releases. Release lineage should remain traceable as:

```text
artifact commit -> source RC version -> final release version
```

## Rollback And Hotfix

Rollback deploys a previously verified Nexus artifact and does not rewrite `main`. After rollback, the expected follow-up is a hotfix PR, revert PR, or explicit temporary divergence note with owner and resolution plan.
