## Context

The repository already contains a Clients CRUD vertical slice with EF Core storage, ASP.NET Core API endpoints, a Blazor page, and tests. E2EPROJECT-7 should introduce Products as a similar user-visible management capability while keeping code changes proportional and easy to review.

Products must include name, SKU, status, price, category, and last updated date. The ticket also calls out permissions, but the current app may not yet have a full authentication or authorization model. Implementation should preserve the intended access boundary in code and tests where the app supports it, and record any platform gap explicitly if auth infrastructure is absent.

## Goals / Non-Goals

**Goals:**

- Add product storage, API, UI, validation, and tests using existing project patterns.
- Keep the CRUD behavior API-backed and independently verifiable in tests.
- Represent loading, empty, success, validation-error, backend-error, and confirmation states in the UI.
- Preserve the ticket's access-control requirement without inventing broad authentication architecture outside the ticket scope.

**Non-Goals:**

- Do not redesign the shared layout or global visual system beyond the Products navigation/page needs.
- Do not add external product catalog integrations, inventory workflows, image upload, bulk import/export, or pricing engines.
- Do not introduce a large authorization framework unless existing project conventions already support it or implementation cannot satisfy the ticket safely without it.

## Decisions

- Follow the existing Clients vertical-slice pattern for Products.
  - Rationale: The repo already has a working data/API/UI/test shape for CRUD behavior, so product code should be familiar and reviewable.
  - Alternative considered: Introduce a generic CRUD framework. Rejected because this ticket only needs one new entity and generic abstractions would add review risk.
- Store Products in the data project with EF Core migrations.
  - Rationale: Product records are first-class persisted data and need independent API/UI verification.
  - Alternative considered: In-memory or UI-only product state. Rejected because the ticket requires centralized system management and API-backed CRUD actions.
- Treat SKU as a unique product identifier when practical.
  - Rationale: SKU is a key product management field and duplicate SKUs create ambiguous management behavior.
  - Alternative considered: Allow duplicate SKUs. Rejected unless current data conventions make uniqueness impractical.
- Use explicit UI state flags and API responses rather than assuming happy-path rendering.
  - Rationale: The acceptance criteria require loading, empty, success, and error states.
  - Alternative considered: Only test submit/list paths. Rejected because it would leave required UI states unproven.

## Risks / Trade-offs

- Access-control infrastructure may be incomplete -> Implement the strongest boundary supported by current app conventions and document any remaining authorization gap in the PR and Plane handoff.
- Product CRUD touches data, API, UI, and tests -> Keep implementation in a single vertical slice and avoid unrelated refactors.
- EF migration can create review noise -> Keep migration limited to Product storage and verify it with focused migration/schema tests.
- Browser-visible CRUD may be flaky if tests depend on shared data -> Prefer isolated test data and independent API/state verification.

## Migration Plan

Add an EF Core migration for Products and ensure startup/database setup applies it in the same manner as existing Client storage. Rollback is the normal PR rollback before merge; after deployment, rollback should use the repository's artifact rollback flow rather than manual database edits.

## Open Questions

- Confirm whether existing app auth conventions can distinguish admin users from unauthorized users, or whether the ticket should encode a placeholder/policy boundary until auth exists.
