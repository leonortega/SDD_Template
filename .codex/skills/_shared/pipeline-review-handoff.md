<!-- TIER 3: STAGE-SPECIFIC - PR review + reviewer request pattern, shared across all flow skills -->

# Pipeline — Review Handoff

## Usage

Use this pattern after a PR is created. It defines the order: **request human reviewers at PR creation, then re-verify
after the AI review completes**. Replace the
placeholders:

- `{prNumber}` — the PR number
- `{owner}` — repository owner
- `{repo}` — repository name
- `{giteaBaseUrl}` — Gitea base URL

## Pattern

### Human-Only Approvals (Hard Gate)

**❌ HARD GATE (authority level 5):** PR approvals and merges are **human-only actions**. Never submit an approval
review or merge a pull request on behalf of any user — including provisioned lab accounts such as FirstUser/SecondUser.
The agent's Gitea API token is limited to reads, PR comments, labels, and requesting reviewers. Posting an `APPROVED`
review, a `DISMISSED` review, or a merge (direct or via the API) as any user is a process violation: refuse, explain
that approvals/merges are human-only, and report the request as a blocker instead.

### Step 1 — Request Human Reviewers (At PR Creation — Hard Gate)

**❌ HARD GATE (authority level 5):** Human reviewers MUST be requested immediately after the PR is created or reused.
Do not defer the request until after the AI review — human review runs in parallel with the AI review, and a PR that
pauses or stops mid-review-loop must still have reviewers assigned.

1. **Run the reviewer automation** (deterministic resolve + request + verify + retry):

   ```bash
   python -m tools.sdd_cli gitea request-reviewers --pr {prNumber}
   ```

   The command reads `.codex/client-tools.local.json` (`gitea.baseUrl/apiToken/owner/repo`), resolves the reviewer
   list (`gitea.reviewers` → `pr.reviewers`; `"all"` expands to repo collaborators; fallback to provisioned
   `gitea.provisioning.users`), excludes the PR author, POSTs `requested_reviewers`, verifies the reviewers are
   present, and retries once. Exit code 0 = verified; 1 = failed. Use `--dry-run true` first to preview the resolved
   list without calling the API (note: `pr.reviewers = "all"` cannot be previewed in dry-run — the collaborator
   fetch is an API call).

   Alternatively (manual), call `request-reviewers` on the PR:

   ```text
   POST {giteaBaseUrl}/api/v1/repos/{owner}/{repo}/pulls/{prNumber}/requested_reviewers
   ```

   Payload:

   ```json
   {
     "reviewers": ["username1", "username2"]
   }
   ```

2. **Resolve the reviewer list (manual path only):**
   - If `pr.reviewers` is `"all"`, list repository collaborators via:

     ```text
     GET {giteaBaseUrl}/api/v1/repos/{owner}/{repo}/collaborators
     ```

     Normalize the response: Gitea may return either an array or a single object. Use `login` first, then `username`.
     Exclude the PR author and the authenticated automation user.
   - If `pr.reviewers` is an array, use that list after trimming empty values.

3. **Verify reviewers are present** — the CLI verifies automatically; for manual calls, re-fetch the PR and inspect
`requested_reviewers`. If not present, retry the request once.

4. **If reviewer assignment fails** after retry, log the blocking issue. Document the reviewer gap in the PR body,
ticket handoff comment, and final summary. Do not hand off without at least
documenting the gap.

5. **Unprovisioned lab config is a BLOCKER (authority level 5):** if the command fails because `apiToken`/`owner`/`repo`
are missing or placeholders in `client-tools.local.json`, stop and run the environment provisioning (`setup-lab`)
before handoff. Do not hand off a PR with no reviewers requested.

### Step 2 — Run AI Review, Then Re-Verify (Hard Gate)

Invoke the `dev-flow-pr-review-agent` skill against the PR. This reviews the diffs, posts findings as PR comments, and
applies labels (`codex-reviewed`, `needs-changes`, `needs-tests`).

**❌ HARD GATE (authority level 5):** After the AI review completes, re-run the reviewer automation to confirm the
reviewers are still present — the command is idempotent (reviewers already requested are verified; missing ones are
re-requested):

```bash
python -m tools.sdd_cli gitea request-reviewers --pr {prNumber}
```

If the re-verify fails, apply the same failure handling as Step 1 items 4-5.

### Why This Order?

Reviewers are requested at PR creation so human review starts immediately and runs in parallel with the AI review — a
PR that pauses or stops mid-review-loop still has reviewers assigned. The post-AI-review re-verify (idempotent)
confirms the reviewers are still present after feedback fixes are pushed, so the merge gate is never silently missing
a reviewer.

## Related Files

- For API endpoint details: `.codex/skills/_shared/api-helpers.md` → Gitea → Request reviewers
- For provider-specific API: `.codex/skills/dev-flow-pr-review-agent/references/gitea-review-api.md` →
`request-reviewers` Operation Details
