---
name: dev-ops-post-merge-deploy
license: MIT
description: >-
  >- Coordinate the post-merge transition from a merged pull request into QA deployment by validating review labels,
  resolving the merge commit, waiting for artifact metadata, and delegating promotion to dev-ops-deploy-qa through
  selected project-profile adapters. Use after a PR merges or when Codex is asked to trigger or continue QA deployment
  for merged work.
---

<!-- TIER 3: STAGE-SPECIFIC - Post-merge deployment skill -->

# Post Merge Deploy

## Overview

Use this skill after a PR has merged to `dev`. It is an orchestration bridge: validate the merged PR is eligible,
trigger the CI build (which deploys to **DEV only** — QA is deployed separately after the user approves, via
`dev-ops-deploy-qa`), wait for the immutable artifacts, then invoke `dev-ops-deploy-qa` for DEV verification, user
approval, and QA dispatch.

Do not perform DEV/QA validation inside this skill. `dev-ops-deploy-qa` owns environment checks and ticket updates.

## Shared Context

Before running, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`,
`.codex/skills/_shared/delivery-contract.md`, and `docs/conventions/context-management.md`,
with `docs/architecture/deployment.md` as the stage-specific doc. Load selected repository/review, artifact, deployment,
and ticket adapters. Use `python -m tools.sdd_cli dev-flow` helpers:
`ValidateTicketLock` for `.codex/delivery-context.local.json`, `ValidateDeploymentLane`, and `ArtifactPaths`.

## Workflow Telemetry

Apply the shared workflow telemetry pattern (`.codex/skills/_shared/pipeline-workflow-telemetry.md`) with:

- `{workflowStage}` = `dev-ops-post-merge-deploy`
- `{agentRole}` = `deployment`

Capture UTC start time after resolving the ticket key and before post-merge validation or artifact waiting. Create or
update the `dev-ops-post-merge-deploy` entry via `time-telemetry-upsert` (payload
in `.codex/skills/openproject-sprint-backlog/references/openproject-api.md` → Operations → `time-telemetry-upsert`;
shared helpers in `.codex/skills/_shared/api-helpers.md` → OpenProject → Workflow
time telemetry). Use marker `IA generated workflow telemetry: {ticketKey}:dev-ops-post-merge-deploy`. Resolve the
activity via `python -m tools.sdd_cli dev-flow resolve-openproject-activity
--workflow-stage dev-ops-post-merge-deploy --input-json '{"timeTelemetry":{...}}'` and reverse-lookup the activity ID.
Use `python -m tools.sdd_cli dev-flow append-telemetry -TicketKey {ticketKey}`
only as the JSONL fallback when direct time telemetry is unavailable. On resume, append or update another row for the
same stage; timing rendering collapses repeated stage rows into earliest start and
latest finish. Include `workflowStage`, `agentRole`, `startedUtc`, `finishedUtc`, `retryCount`, and `outcome`. Do not
duplicate the `dev-ops-deploy-qa` row; `dev-ops-deploy-qa` records its own stage
when invoked.

## Configuration

Read `.codex/client-tools.local.json` first. Required values are ticket provider, repository/review provider, and Nexus
settings used by `dev-ops-deploy-qa`.

Also requires Gitea API token with `write:repository` scope to trigger the `package-deploy` workflow after merge. The
token and Gitea connection values (`baseUrl`, `owner`, `repo`) must be available
via `gitea.*` keys in client-tools config.

## Workflow

1. Resolve the PR from user input, current branch, ticket comments, commit messages, or ticket key.
2. Verify the PR is merged and its target branch is `dev`.

3. **Delete the source branch** (local and remote) — it is no longer needed after merge. First extract the PR number and
source branch from the resolved PR metadata:

   ```bash
   # PR_NUMBER must be set from the resolved PR in step 1
   # Fetch PR metadata to get source branch name
   PR_JSON=$(curl -s -H "Authorization: token ${GITEA_API_TOKEN}" \
     "${GITEA_BASE_URL}/api/v1/repos/${GITEA_OWNER}/${GITEA_REPO}/pulls/${PR_NUMBER}")
   BRANCH=$(echo "$PR_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('head',{}).get('ref',''))")

   if [ -n "$BRANCH" ]; then
     # ⚠️ Delete the REMOTE branch via the Gitea API, NOT `git push --delete`:
     # `git push --delete` hangs indefinitely on Windows (credential prompt),
     # blocking branch cleanup. URL-encode the branch name for the API path.
     ENC_BRANCH=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$BRANCH")
     curl -s -o /dev/null -w "DELETE branch HTTP:%{http_code}\n" \
       -X DELETE -H "Authorization: token ${GITEA_API_TOKEN}" \
       "${GITEA_BASE_URL}/api/v1/repos/${GITEA_OWNER}/${GITEA_REPO}/branches/${ENC_BRANCH}" || \
       echo "Remote branch '$BRANCH' already deleted or not found"
     # Delete local branch if it exists
     git branch -d "$BRANCH" 2>/dev/null || \
       echo "Local branch '$BRANCH' not found or not fully merged"
     # Prune stale remote refs (Gitea does not auto-delete PR source branches)
     git fetch --prune 2>/dev/null || true
     echo "Branch '$BRANCH' cleaned up after merge"
   else
     echo "Could not resolve source branch name from PR metadata — skipping branch deletion"
   fi
   ```

   **Note:** The PR number must be stored as `PR_NUMBER` from the resolved PR object before this command runs. This is
   best-effort cleanup — if the branch cannot be deleted (already deleted,
   protected, or name not resolvable), log it as a non-blocking note and continue. Always use the **Gitea API** (`DELETE
   /api/v1/repos/{owner}/{repo}/branches/{branch}`) for remote branch deletion —
   `git push --delete` hangs on Windows.

4. Verify the PR does not currently have configured `pr.labels.needsChanges` or `pr.labels.needsTests`.
5. Resolve the merge commit SHA from repository/review provider metadata.
6. Resolve the ticket key from the PR title/body, branch name, commit messages, or ticket comments.
7. Run `ValidateTicketLock` with the resolved ticket key, PR number, branch, and merge/artifact commit when known. If
the result is invalid, stop before triggering the build.

   **❌ HARD GATE (authority level 5):** The ticket MUST be in `Developed` (OpenProject ID 8) before triggering the CI
   build — `dev-ops-deploy-qa` enforces the same gate before any QA activity. If the
   ticket is in an earlier state (e.g., `In progress` ID 7), transition it to `Developed` first; stop if the
   transition fails.

   **DEV health gate:** the dispatched pipeline verifies every app's `/health` on the external DEV host URLs right after
   the DEV rollout and exits when DEV is unhealthy. Waiting for the DEV Nexus artifacts therefore
   implies the DEV gate passed. QA is deployed later, only after the user approves (`dev-ops-deploy-qa`).

8. **Trigger the CI build** by dispatching the `package-deploy` Gitea Actions workflow on the `dev` branch. The CI
pipeline deploys to **DEV only**; QA is not auto-promoted in this run.

   Derive the connection values from `.codex/client-tools.local.json`:
   - `GITEA_BASE_URL` from `gitea.baseUrl`
   - `GITEA_OWNER` from `gitea.owner`
   - `GITEA_REPO` from `gitea.repo`
   - `GITEA_API_TOKEN` from `gitea.apiToken`

   Then dispatch and capture the HTTP response code:

   ```bash
   RESP=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
     -H "Authorization: token ${GITEA_API_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"ref":"dev"}' \
     "${GITEA_BASE_URL}/api/v1/repos/${GITEA_OWNER}/${GITEA_REPO}/actions/workflows/package-deploy.yml/dispatches")
   ```

   Interpret the response:
   - HTTP `204`: Workflow dispatched successfully. Proceed to step 9 (artifact polling).
   - Any other status or connection error: stop and report the error. Do not proceed to artifact polling.

9. Poll for the Nexus artifact files for the merge commit. The CI pipeline deploys DEV only in this run, so wait for
the DEV artifacts:
   - `app/{commitSha}/deployable-apps.json`
   - one `app/{commitSha}/{artifactName}` per topology app
   - one `app/{commitSha}/{artifactName}.sha256` per topology app
   - `app/{commitSha}/commit.sha`
   - `app/{commitSha}/release-dev.json` (DEV deployment metadata)
   - `app/{commitSha}/env-urls-dev.json` (DEV URLs)
   QA artifacts (`release-qa.json`, `env-urls-qa.json`) do not exist yet — they are produced by the user-approved QA
   dispatch in `dev-ops-deploy-qa`.
     Also require any additional deployment metadata declared by the selected deployment adapter:
   - `app/{commitSha}/container-images.json`
   - `app/{commitSha}/monitoring-summary-dev.json` when DEV deployment already completed
10. Use bounded waiting: check immediately, then retry with backoff for up to 10 minutes unless the user asked for a
shorter wait.
11. Verify `commit.sha` matches the merge commit before delegating.
12. If `release-dev.json` exists, verify `ticketKey` matches the locked/resolved ticket key.
13. Invoke `dev-ops-deploy-qa` with the resolved PR, ticket key, and merge commit. Since the CI pipeline already
deployed both DEV and QA, `dev-ops-deploy-qa` runs in verification mode: validate QA
health, update the ticket, and call E2E QA gate. If QA verification is already complete, invoke `dev-ops-deploy-qa` in
idempotent verification mode so that stage records its own telemetry row without
duplicating ticket comments or state changes.

## Idempotency

- If the QA deployment marker `IA generated QA deployment: {commitSha}` already exists and the ticket is in QA, append
`dev-ops-post-merge-deploy` telemetry, invoke `dev-ops-deploy-qa` idempotently,
and report that QA promotion is already complete.
- If the artifact exists (both `release-dev.json` and `release-qa.json`), skip waiting and delegate immediately.
- If labels were stale but have since been removed, continue.

## Output

Report the PR, merge commit, workflow dispatch status, artifact availability, validation status, deployment-lane result,
invoked child skill, and handoff to QA or the blocker found.

## Failure Rules

- Unmerged PR: stop and report the PR state.
- PR target is not `dev`: stop and report the mismatch.
- Stale `needs-changes` or `needs-tests` labels: stop before artifact promotion.
- **Workflow dispatch error**: if the `package-deploy` workflow dispatch returns non-`204` or a connection error, stop
and report the error. Do not proceed without a successful build trigger.
- Nexus artifact missing after the wait window: stop and report provider-specific artifact paths checked.
- Nexus unavailable: stop; do not use a degraded artifact source.
- Commit metadata mismatch: stop and report the expected and actual commit SHA.
