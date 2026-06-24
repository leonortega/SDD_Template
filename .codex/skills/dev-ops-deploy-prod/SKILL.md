---
name: dev-ops-deploy-prod
description: Promote a QA-approved release artifact to production after configured ticket E2E QA approval. Use when Codex needs to verify one or more Done tickets included in a release, confirm the QA-approved artifact and checksum, ensure release/RC tag consistency, update the release branch, trigger production deployment, validate production page and health checks, verify configured observability when available, and comment the production result on every included ticket.
---

# Deploy To PROD

## Overview

Use this skill after `quality-test-e2e` has passed and moved each included ticket to `configured Done state`. `Done` means QA accepted and PROD eligible; PROD remains an explicit release event that may include one or more Done tickets. The release rule is:

```text
feature branch -> dev -> DEV -> QA -> E2E QA OK -> main -> PROD
```

PROD must reuse the QA-approved Nexus artifact. Never rebuild, republish, or rename the artifact during PROD promotion. For batch releases, promote the selected artifact commit once, then record the same PROD release result on every included ticket.

## Shared Context

Before production promotion, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/deployment.md` as the stage-specific doc. Load selected ticket, repository/review, artifact, deployment, and observability adapters. Use `.codex/skills/_shared/scripts/delivery_tools.ps1` helpers: `ValidateTicketLock` for `.codex/delivery-context.local.json`, `ValidateDeploymentLane`, `ArtifactPaths`, `ValidateReleaseManifest`, `UpdateReleaseManifest`, and `RenderTicketComment -Type ProdDeployment`.

For push-triggered production deployment from the release branch, the commit or merged PR title must start with the ticket key format configured in `.codex/project-profile.json` at `workflow.ticketKeyPattern`, and the change must touch configured application or test paths. Non-code changes outside those paths and non-ticket PRs must not deploy production.

## Configuration

Read `.codex/client-tools.local.json` first. Fall back to `.codex/client-tools.example.json` only for structure, then apply environment overrides when present.

Required values:

- `selected ticket adapter runtime values`, `configured Done state`
- `selected repository/review adapter runtime values`
- `nexus.baseUrl`, `nexus.username`, `nexus.password`, `nexus.repository`

Provider-supported environment variables may override local JSON when present. Repository/review overrides include `selected repository/review adapter overrides`.

## Workflow

Run preflight, main/tag promotion, PROD deployment, PROD verification, ticket-provider results, post-PROD retrospective, and release handoff steps in order. Do not continue to the next step until the prior validation evidence is present.

## Preflight

1. Resolve the primary ticket, included Done ticket list, PRs, QA-approved commit SHA, source RC version, and final release version from user input, ticket comments, repository PR metadata, tags, `app/qa-approved/latest.json`, or Nexus artifact paths. If `release.json.includedTickets` exists, treat it as the authoritative release membership list; otherwise default to the primary `ticketKey` for single-ticket compatibility.
2. Run `ValidateTicketLock` with the primary ticket, representative PR, QA-approved commit, source RC version when known, and final release version when known. If the result is invalid, stop before tag or `main` mutation. Do not reject a valid batch release only because additional included tickets differ from the active ticket lock.
3. Require SemVer tags:
   - source RC: `vMAJOR.MINOR.PATCH-rc.N`
   - final release: `vMAJOR.MINOR.PATCH`
4. Fetch every included ticket with expanded state/project data and verify each one is in `configured Done state`.
5. Read ticket comments for every included ticket and find `IA generated E2E QA: {ticketKey}` for the same commit/artifact or for a commit reachable from the promoted artifact commit.
6. Verify every included ticket's E2E QA comment includes pass result, PR URL, QA URL, Nexus artifact URL, QA evidence URL, and source RC version.
7. Verify Nexus contains the selected provider artifact set. selected deployment provider requires:
   - `app/{commitSha}/deployable-apps.json`
   - `app/{commitSha}/deployment-config.json`
   - one `app/{commitSha}/{artifactName}` per topology app
   - one `app/{commitSha}/{artifactName}.sha256` per topology app
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json`
   selected deployment provider requires:
   - `app/{commitSha}/container-images.json`
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release.json`
   - `app/{commitSha}/qa-observability.json` when observability is enabled
8. Download checksum metadata only as needed and verify `commit.sha` exactly matches the QA-approved commit.
9. Read `release.json` and verify it references the same commit SHA, checksum, primary ticket, QA evidence URL, and source RC version as the ticket provider E2E QA evidence. If `includedTickets` exists, every included ticket must have Done state, E2E QA PASS evidence, source RC lineage, and release membership proof. Treat a different `ticketKey` as blocking only when no `includedTickets` release membership proves the batch release.
10. Verify the source RC tag exists and points to the QA-approved commit.
11. Verify the final release tag does not already exist.
12. If `app/qa-approved/latest.json` is used to resolve the commit, verify its `artifactCommitSha`, `version`, `canonicalPath`, `releaseManifestPath`, `ticketKey`, and `includedTickets` match the selected release context before any `main` or tag mutation.

Stop if any QA gate, tag gate, artifact gate, or checksum gate fails.

## Main And Tag Promotion

1. Verify the QA-approved commit exists on `dev`.
2. Verify `main` can fast-forward to the QA-approved commit.
3. If `main` has diverged, stop and report the divergence. Do not create a merge commit unless the user explicitly changes the release policy.
4. Fast-forward `main` to the QA-approved commit.
5. Create the annotated final release tag only after fast-forward feasibility is confirmed and immediately before pushing.
6. Tag message must include primary ticket key, included ticket list, PR or release PR URL, source RC version, final version, QA evidence URL, Nexus artifact URL, checksum, and commit SHA.
7. Push `main` and the release tag only after every preflight check passes. If the push fails after creating the local tag and the tag was not created on the remote, delete the local tag before stopping so no orphaned local release tag remains.
8. If branch protection blocks the `main` push, delete any local-only final release tag, open a PR to `main` with the QA-approved commit and final version details, label/comment it as release-blocking, and stop before PROD deployment until that PR is merged. The user must rerun `dev-ops-deploy-prod` after the promotion PR merges. Do not deploy PROD from a commit that is not reachable from `main`.

## PROD Deployment

PROD deployment can be triggered in provider-specific ways:

- selected deployment provider: a push/merge to `main` deploys PROD only when the changed files include application/test/package source and the commit or merged PR title starts with the configured ticket key format from `.codex/project-profile.json`. It resolves the artifact from `app/qa-approved/latest.json`, requires the pointer commit to equal `GITHUB_SHA`, then validates `commit.sha`, `release.json`, and the source RC tag before downloading the canonical `app/{commitSha}` ZIPs.
- selected deployment provider: manual configured package/deploy workflow dispatch with `environment=prod` deploys the topology artifacts identified by `artifact_commit_sha`.
- selected deployment provider: manual configured selected-provider deploy workflow dispatch with `environment=prod` deploys the QA-approved image digest set from `app/{artifact_commit_sha}/container-images.json` into `sdd-prod`.

For selected-provider manual dispatch, trigger the production workflow declared by the selected deployment adapter with:

```text
environment=prod
artifact_commit_sha={qaApprovedCommit}
release_version={finalVersion}
source_rc_version={sourceRcVersion}
```

For selected-provider manual dispatch, trigger the deploy workflow declared by the selected deployment adapter. The workflow must validate `release.json`, verify the RC pointer when `source_rc_version` is supplied, download the approved artifact metadata, and deploy only immutable artifact references.

The PROD workflow must not run package, DEV, or QA jobs for a `main` push or `environment=prod` dispatch. Maintenance-only changes such as `.codex/**` or workflow-only edits must not deploy PROD. PROD must download the selected provider artifact set from Nexus, verify immutable artifact checksums or digests, deploy to PROD, then run:

- PROD page smoke check: HTTP 200, expected title/content, no selected deployment provider placeholder page.
- PROD health checks: every topology app health path returns HTTP 200 and JSON `status=ok`.

After dispatch, inspect the workflow run jobs and logs against the artifact-reuse contract. A successful PROD run must show that the workflow:

- used `environment=prod`,
- consumed `artifact_commit_sha={qaApprovedCommit}` for manual dispatch or resolved the same commit from `app/qa-approved/latest.json` for a `main` push,
- downloaded the provider artifact set from Nexus,
- verified every required checksum or digest reference,
- skipped rebuild/republish behavior,
- skipped DEV and QA deployment behavior,
- ran direct PROD page and `/health` checks.
- applied and verified the PROD configuration and monitoring evidence required by the selected deployment adapter.

Prefer named job checks such as `deploy-prod` when present, but do not rely only on job names. If the workflow rebuilds, republishes, downloads an artifact commit that does not match the approved commit, lacks a PROD deployment path, deploys DEV/QA during PROD promotion, or skips `/health`, treat it as blocking workflow drift.

## PROD Verification

After the workflow succeeds, run direct verification before commenting success:

1. Request the PROD web URL and assert HTTP 200 plus expected page title/content.
2. Request every topology app health path and assert HTTP 200 plus `status=ok`.
3. Verify the PROD workflow applied and verified the configuration, artifact metadata, and monitoring evidence required by the selected deployment adapter. Missing proof is blocking.
4. If Seq log validation is unavailable, classify monitoring as unavailable. Direct HTTP, deployment configuration, and `/health` checks remain authoritative for app success.
5. If direct page, deployment configuration, or `/health` checks fail, classify PROD verification as failed and do not claim success.
6. When PROD verification passes, use `UpdateReleaseManifest` to update `app/{commitSha}/release.json` with final release version, final tag, included tickets, PROD URL, PROD page status, PROD deployment configuration status, PROD `/health` status, workflow run URL, monitoring status, and PROD deployment timestamp. Validate and upload the updated manifest to Nexus.
7. Use `CreateArtifactPointer` to create the final release alias pointer, then upload `app/releases/{finalReleaseVersion}/artifact-pointer.json` and `app/releases/{finalReleaseVersion}/release.json`. The release alias must point back to canonical `app/{commitSha}/`; do not duplicate ZIP files into the version folder.

PROD success must never be based on screenshots alone.

## Ticket Provider Result

Before commenting, read existing comments for every included ticket when the API allows it. Use this stable marker:

```text
IA generated PROD deployment: {finalVersion}
```

Do not duplicate a PROD result comment with the same marker, commit, artifact, and PROD URL on an included ticket unless the user explicitly asks for a fresh run.

Keep the marker as the first line by itself. Use `RenderTicketComment -Type ProdDeployment` with the resolved release, reference, evidence, and production validation data to format the readable Markdown body.

Add or update the PROD result on every included ticket. The comment must include:

- primary ticket, included ticket list, and current state for the ticket being commented
- final release version and source RC version
- release lineage: `artifact commit -> source RC version -> final release version`
- final release tag URL or tag name and verified tag target commit
- PR URL or release PR URL
- commit SHA
- Nexus artifact URL and checksum
- Nexus release manifest URL
- QA evidence URL
- main ref update result
- workflow run URL
- PROD URL, page smoke status, and `/health` status
- Seq log search, or monitoring unavailable/configuration notes
- pass/fail result

Only write a success result after the workflow passed and direct PROD page plus `/health` verification passed. If app checks fail, write a failure comment on the primary ticket and stop. If only local monitoring is unavailable, deployment may still pass, but every included ticket comment must state monitoring verification was unavailable.

## Post-PROD Retrospective

After successful PROD result comments are recorded for every included ticket, automatically run `dev-flow-retrospective-audit` in read-only `post-prod-ticket-release` mode for the just-promoted release. Pass the primary ticket key, included ticket list, artifact commit, final release version, PROD URL, and Nexus release manifest path or URL as the audit scope.

This retrospective is a learning-evidence step, not a release gate. PROD success remains based on the artifact, workflow, direct PROD page, and `/health` validation above. If the retrospective cannot inspect optional evidence, report the evidence gap in the final handoff and keep the successful PROD result intact.

The retrospective must persist compact, sanitized learning evidence:

- append or update local audit result data in ignored `.codex/agent-evals/results.local.json`,
- add or reuse a compact ticket comment with marker `IA generated post-PROD retrospective: {finalVersion}`,
- include findings, recommended durable improvements, eval coverage gaps, residual evidence gaps, and follow-up ownership when applicable.

The retrospective must not mutate ticket status, deploy, promote, tag, rewrite branches, update release manifests, create tickets, schedule automations, or apply docs, contract, skill, eval, or memory changes unless the user separately asks for apply mode. Do not include secrets, raw tool payloads, full prompts, tokens, cookies, or credential-bearing URLs in the local result or ticket comment.

## Output

Report the final release version, included tickets, PROD URL, final tag, deployed artifact commit, validation results, ticket-provider PROD comment status for every included ticket, post-PROD retrospective result path and ticket provider marker status, and any handoff, audit, or monitoring gaps.

## Failure Rules

- Missing selected ticket adapter config: stop before ticket-provider reads or mutations.
- Any included ticket not in `configured Done state`: stop.
- Missing or stale E2E QA marker for any included ticket: stop.
- Ticket context lock mismatch: stop before tag, `main`, workflow, ticket provider, or release manifest mutation.
- Missing source RC tag or wrong tag target: stop.
- Existing final release tag: stop.
- Missing Nexus artifact/checksum/commit metadata: stop.
- Missing selected deployment-adapter PROD configuration verification: stop.
- Missing selected deployment-adapter immutable artifact metadata, RC pointer validation, or monitoring evidence when required: stop.
- Checksum, commit metadata, or included ticket membership mismatch: stop.
- Diverged `main`: stop.
- Local-only release tag after failed push: delete the local tag before stopping unless the tag already exists on the remote.
- Branch protection blocks `main`: open a release-blocking promotion PR and require rerunning this skill after merge.
- PROD workflow violates the artifact-reuse contract: route to `$configure-artifact-repository` or `$configure-dev-environment`, fix the workflow through PR, then rerun PROD dispatch only after the fix reaches `main`.
- Missing selected deployment-provider production configuration or repository workflow secrets: route to `$configure-cloud-environments` or `$configure-dev-environment`, configure the secrets from selected deployment provider deployment outputs without exposing secret values, then rerun PROD dispatch.
- PROD workflow failure: comment failure and stop.
- PROD page or `/health` failure: comment failure and stop.
- Seq unavailable: record as monitoring unavailable; do not fail the deployment when direct app checks pass.
- Secrets in logs or comments: redact or discard before reporting.
