## Review Workload Forecast

Estimated changed lines: 80-180
400-line budget risk: Low
Chained PRs recommended: No
Decision needed before apply: No
Delivery strategy: single-pr
Suggested work units: Single PR with client CRUD fix, regression tests, and context review

## 1. Reproduce And Locate

- [x] 1.1 Inspect `src/SDDTemplate.Site/Components/Pages/Clients.razor` to confirm how empty-list rendering, form submit, edit selection, and client reload interact.
- [x] 1.2 Add or adjust a regression test that starts with zero clients and proves the first valid create submit persists a client on the first attempt.
- [x] 1.3 Confirm whether the failure is page event flow, API base URL/configuration, or test-environment behavior before changing production code.

## 2. Implement Client CRUD Fix

- [x] 2.1 Update the client CRUD page so an empty `client-id` always uses the create/save path and never falls through to Select Client behavior.
- [x] 2.2 Preserve edit/select behavior for existing clients and delete behavior for listed clients.
- [x] 2.3 Keep the existing client API contract unchanged unless the reproduction proves the API layer is the defect source.

## 3. Validate Behavior

- [x] 3.1 Verify first-client creation from empty state saves and displays the client without a second submit.
- [x] 3.2 Verify subsequent client creation still saves on first submit.
- [x] 3.3 Verify selecting an existing client loads it for editing without creating a duplicate.
- [x] 3.4 Run `dotnet test .\SDDTemplate.slnx`.

## 4. Handoff Review

- [x] 4.1 Run the configured quality gates required by `.codex/quality.local.json` when available.
- [x] 4.2 Perform Context Findings Review and update docs only if durable project context changed.
- [x] 4.3 Record `Docs: no durable context changes` if no docs updates are needed.
- [ ] 4.4 Prepare PR and Plane handoff with validation evidence, assumptions, docs status, and memory status.
