<!-- TIER 2: SEMI-STABLE - Release lessons, loaded at startup -->

# Release Lessons

## PROD promotion requires a release branch PR because `main` is branch-protected (v0.2.0)

During the v0.2.0 PROD promotion (`dev-ops-deploy-prod`, E2EPROJECT-38/39):

- `main` has **push disabled** and requires **1 approval** (same protection as `dev`). Direct `git push` to `main` is
  rejected, so the skill's fast-forward path cannot be used as-is.
- The release rule in the deploy skills is `... E2E QA OK -> main -> PROD`. In this lab the working pattern (matching
  the earlier v0.1.0 release, PR #11) is:
  1. Create `release/vX.Y.Z` from the QA-approved commit (the artifact commit, **do not rebuild**).
  2. Create the **final annotated tag** (`vX.Y.Z`) on that commit.
  3. Open a **release-blocking PR** `release/vX.Y.Z -> main`, label `codex-reviewed`, get 1 approval from a user other
     than the PR author (self-approval is rejected), and merge.
  4. Then dispatch `package-deploy` with `workflow_dispatch` inputs `environment=prod` on the release branch (so the
     workflow checks out exactly the QA-approved commit).
- Pitfalls hit:
  - `main` diverges from `dev` after a release-branch merge (the merge commit is only on `main`). This is expected;
    it does not block the next promotion — a fresh release branch from the new QA-approved dev commit works.
  - The workflow's dispatch only accepts `environment` (dev|qa|prod) and deploys **only** that target on dispatch.
  - Final version must not already exist as a tag; the skill blocks reusing an existing final tag.

Result: PROD deployed from commit `cfc2e82` (run #56 success), endpoints verified (tracking + quote live).
