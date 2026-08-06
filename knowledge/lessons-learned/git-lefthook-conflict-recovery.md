# Git + Lefthook Conflict: Silent Revert of Unstaged Changes (E2EPROJECT-39)

## What happened

During the E2EPROJECT-39 flow, a `git commit` failed at the lefthook `trunk-fmt`
pre-commit stage:

```text
error: patch failed: openspec/.../tasks.md:27
error: .../tasks.md: patch does not apply
Unable to restore previously hidden unstaged changes.
Stage all changes with `git add -A` and try again.
```

The failure mode: lefthook stashes unstaged changes, runs `trunk fmt` on staged
files (which reformatted `tasks.md`), then restores the stash. Because trunk-fmt
modified a file that was BOTH staged and unstaged (a prior fmt pass had left a
working-tree edit), the restore patch conflicted and lefthook left the working
tree **reverted to HEAD** for all modified tracked files.

The follow-up `git add -A && git commit` then silently committed the REVERTED
(HEAD) versions of those files: `Program.cs` without `MapQuoteEndpoints`,
`LandingPage.tsx` without the quote CTA, the old `smoke.spec.ts`. Nothing was
flagged as missing because the tree was clean and the commit succeeded.

**Detection:** the pre-push `stack-tests` gate failed with `404 NotFound` on
`/api/quotes` — the endpoint existed in the working tree when tests ran
locally, but the committed tree did not map it.

**Recovery:** the lost changes were found in a dangling git object created by
lefthook's stash (`git fsck --no-reflogs`). Recovered with
`git checkout <dangling-sha> -- <paths>`.

## Rules

1. After ANY lefthook "unable to restore" failure, do NOT `git add -A` and
   re-commit blindly. The working tree may have been reverted. Verify the
   index/HEAD diff matches intent first (`git diff HEAD --stat`, and grep for
   key markers such as `MapQuoteEndpoints`).
2. Commit in narrow slices (explicit paths, not `-A`) when hooks reformat
   files. Keep OpenSpec-only commits separate from code commits.
3. Verify the committed tree, not just the working tree: after commit, run
   `git show HEAD:<file>` and check the expected markers are present.
4. When a hook re-formats a file, stage it BEFORE committing so the restore
   patch has nothing to conflict with. If trunk fmt keeps touching a file
   across commits, commit the fmt pass separately.
5. Recovery tools: `git stash list`, `git fsck --no-reflogs | grep commit`,
   then `git show <sha>:<path>` to identify the lost content and
   `git checkout <sha> -- <paths>` to restore it.

## Status

Recovered in full; no changes lost permanently. Lesson captured 2026-08-05
(E2EPROJECT-39, PR #16).
