<!-- TIER 3: STAGE-SPECIFIC - PR review + reviewer request pattern, shared across all flow skills -->

# Pipeline — Review Handoff

## Usage

Use this pattern after a PR is created. It defines the order: **AI review first, then human reviewers**. Replace the placeholders:

- `{prNumber}` — the PR number
- `{owner}` — repository owner
- `{repo}` — repository name
- `{giteaBaseUrl}` — Gitea base URL

## Pattern

### Step 1 — Run AI Review

Invoke the `dev-flow-pr-review-agent` skill against the PR. This reviews the diffs, posts findings as PR comments, and applies labels (`codex-reviewed`, `needs-changes`, `needs-tests`).

The AI review runs first so issues are caught and fixes are applied before human reviewers are requested.

### Step 2 — Request Human Reviewers (Hard Gate)

**❌ HARD GATE (authority level 5):** Human reviewers MUST be requested after the AI review completes. Do not skip this step.

1. **Resolve the reviewer list:**
   - If `pr.reviewers` is `"all"`, list repository collaborators via:
     ```text
     GET {giteaBaseUrl}/api/v1/repos/{owner}/{repo}/collaborators
     ```
     Normalize the response: Gitea may return either an array or a single object. Use `login` first, then `username`. Exclude the PR author and the authenticated automation user.
   - If `pr.reviewers` is an array, use that list after trimming empty values.

2. **Call `request-reviewers`** on the PR:
   ```text
   POST {giteaBaseUrl}/api/v1/repos/{owner}/{repo}/pulls/{prNumber}/requested_reviewers
   ```
   Payload:
   ```json
   {
     "reviewers": ["username1", "username2"]
   }
   ```

3. **Verify reviewers are present** — re-fetch the PR and inspect `requested_reviewers`. If not present, retry the request once.

4. **If reviewer assignment fails** after retry, log the blocking issue. Document the reviewer gap in the PR body, ticket handoff comment, and final summary. Do not hand off without at least documenting the gap.

### Why This Order?

The AI review runs first — it catches issues, applies feedback fixes, and ensures the PR is clean before human reviewers are requested. Requesting human reviewers too early (during PR creation) wastes reviewer time on issues the AI would have caught and fixed.

## Related Files

- For API endpoint details: `.codex/skills/_shared/api-helpers.md` → Gitea → Request reviewers
- For provider-specific API: `.codex/skills/dev-flow-pr-review-agent/references/gitea-review-api.md` → `request-reviewers` Operation Details
