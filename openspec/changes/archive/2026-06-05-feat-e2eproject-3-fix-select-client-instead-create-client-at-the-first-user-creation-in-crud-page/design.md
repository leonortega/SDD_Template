## Context

Plane ticket `E2EPROJECT-3` targets the client CRUD page. The current page is implemented in `src/SDDTemplate.Site/Components/Pages/Clients.razor`, with API behavior covered in `tests/SDDTemplate.Site.Tests/ClientApiTests.cs`, page shell coverage in `tests/SDDTemplate.Site.Tests/ClientCrudPageTests.cs`, and deployed browser CRUD coverage in `tests/SDDTemplate.E2ETests/tests/client-crud.spec.ts`.

The reported failure is specific to the empty-client state: the first create attempt triggers the select/load path instead of the create/save path, so no client is persisted until a second submit. The fix should keep the API contract unchanged and correct the page event flow.

## Goals / Non-Goals

**Goals:**

- Ensure the first client created from an empty list uses the create/save path and persists on the first submit.
- Keep selecting an existing client separate from submitting a new client.
- Keep existing subsequent create, update, and delete behavior intact.
- Add focused automated coverage for the zero-clients creation path.

**Non-Goals:**

- No database schema, migration, or DTO changes.
- No API route changes unless implementation proves the page cannot call the existing API correctly.
- No new CRUD fields, validation rules, or visual redesign.

## Decisions

- Keep the fix in the client CRUD page event flow unless investigation finds a lower-level client service bug.
  - Rationale: API tests already cover `POST /api/clients`, and the failure is described as the website selecting instead of creating.
  - Alternative considered: change API create/list behavior. Rejected because the API create contract is already explicit and changing it would widen the ticket.
- Add a test that starts from an empty client store and verifies the first submit persists a client.
  - Rationale: the bug only appears when no clients exist, so generic CRUD shell tests are not enough.
  - Alternative considered: rely only on existing deployed Playwright CRUD. Rejected because ticket implementation needs fast local regression coverage before PR handoff.
- Preserve existing selectors and page structure where practical.
  - Rationale: deployed E2E tests already depend on the CRUD page surface; avoiding unnecessary markup churn reduces review and QA risk.

## Risks / Trade-offs

- Empty-state behavior can be missed if tests seed clients before the create action. Mitigation: create a zero-clients test case that explicitly verifies the first submit.
- Submit and select controls may share data attributes or event handlers. Mitigation: separate create/update form submission from row selection logic and assert POST behavior for a new client.
- A page-only fix could still leave deployed E2E coverage blind to the exact first-client case. Mitigation: prefer adding or adjusting browser-visible E2E coverage if the existing test cannot express the empty-state scenario.

## Migration Plan

No migration is required. The change is deployed as a normal application code/test update through the existing PR, artifact, DEV/QA, and E2E QA workflow. Rollback uses the standard previous Nexus artifact if a regression appears after deployment.

## Open Questions

- None for ticket start. Implementation should confirm whether the first-client regression is reproduced in local tests before applying the fix.
