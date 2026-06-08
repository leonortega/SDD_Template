## Context

`E2EPROJECT-4` targets a routed-navigation-only defect in the Clients CRUD page. The user can complete all required client fields after navigating from the main page to Clients, but the first `Save Client` click does nothing until the browser is refreshed with F5. The same view works after a hard refresh, which points to a Blazor component lifecycle, form state, validation, or event binding difference rather than a backend contract problem.

## Goals / Non-Goals

**Goals:**

- Make the first `Save Client` click after in-app navigation submit the completed form.
- Preserve existing Client CRUD API behavior, validation behavior, and hard-refresh behavior.
- Add regression coverage that reproduces the routed navigation path.

**Non-Goals:**

- Change Client entity fields, migrations, or REST API contracts.
- Redesign the Clients page or unrelated CRUD workflows.
- Change deployment, artifact, or environment topology.

## Decisions

- Disable enhanced navigation for the primary Clients navigation link while the page depends on an inline script for form behavior.
  - Rationale: The hard-refresh path works because the inline script executes on document load; enhanced routed navigation can replace page content without re-running that script, leaving the first save path unbound.
  - Alternative considered: Rebuild the form submission path from scratch. Rejected because it would be disproportionate until the lifecycle/event root cause is verified.

- Cover the regression at the UI/component workflow level where possible, with lower-level tests only when they make the root cause observable.
  - Rationale: The defect is user-visible and path-dependent: main page navigation to Clients followed by first save.
  - Alternative considered: Only test service/API create behavior. Rejected because API success after refresh would not prove the routed first-click path.

- Keep existing validation semantics intact.
  - Rationale: The ticket asks for a frozen save button fix, not changed validation rules.
  - Alternative considered: Relax validation to force submission. Rejected because it could allow invalid client data.

## Risks / Trade-offs

- Routed-navigation behavior is not reproduced by current tests -> add a targeted regression test before or with the fix.
- The first click may fail because async initialization is incomplete -> ensure form actions wait for required page state without swallowing the submit event.
- The page may issue duplicate saves if the fix retries blindly -> assert the first valid save submits once and reflects the updated list.
- Browser-only behavior may be hard to prove with unit tests -> use the strongest available repo-native or browser automation test and document any remaining QA evidence need.

## Migration Plan

No data migration is expected. The change should deploy as a normal application artifact through the existing DEV, QA, E2E QA, and explicit PROD promotion workflow. Rollback uses the prior Nexus artifact if QA or production validation fails.

## Open Questions

- Which exact component boundary drops the first click: route initialization, form model initialization, validation context, event callback binding, API client readiness, or JavaScript/runtime interop?
