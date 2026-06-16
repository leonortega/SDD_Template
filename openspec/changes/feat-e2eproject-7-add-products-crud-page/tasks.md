## Review Workload Forecast

Estimated changed lines: 700-1200
400-line budget risk: High
Chained PRs recommended: Yes
Decision needed before apply: Yes
Delivery strategy: ask-on-risk
Suggested work units: PR 1 data/API Product CRUD and tests -> PR 2 Blazor Products page and browser-visible tests -> PR 3 access-control hardening and QA refinements if auth scope exceeds current patterns

## 1. Planning And Scope Control

- [x] 1.1 Confirm whether implementation should proceed as a chained PR plan or as a size exception for one PR.
- [x] 1.2 Inspect current Client data/API/UI/tests and identify reusable patterns without introducing generic CRUD abstractions.
- [x] 1.3 Confirm current authentication and authorization capabilities before implementing Products access restrictions.

## 2. Data And API

- [x] 2.1 Add Product entity, DbContext mapping, and migration for Name, SKU, Status, Price, Category, and Last Updated.
- [x] 2.2 Add Product DTOs and CRUD endpoints for list, read, create, update, and delete.
- [x] 2.3 Add Product validation for required fields, invalid SKU/status/price values, missing records, and duplicate SKU if supported.
- [ ] 2.4 Add or preserve Products API access-control behavior according to current app conventions.

## 3. Blazor UI

- [ ] 3.1 Add Products navigation and routable Products page.
- [ ] 3.2 Add Product list rendering with Name, SKU, Status, Price, Category, and Last Updated values.
- [ ] 3.3 Add Product create and edit form behavior with required-field validation errors.
- [ ] 3.4 Add delete confirmation behavior and post-delete list refresh.
- [ ] 3.5 Add loading, empty, success, validation-error, and backend-error UI states.

## 4. Tests And QA Evidence

- [x] 4.1 Add migration/schema tests for Product storage.
- [x] 4.2 Add API tests for Product list, read, create, update, delete, validation, and not-found behavior.
- [ ] 4.3 Add Blazor page tests for navigation, list, create, edit, delete, validation, and state rendering.
- [ ] 4.4 Add or update reusable E2E QA coverage for deployed Products CRUD acceptance criteria where practical.

## 5. Quality Gates And Handoff

- [x] 5.1 Run focused build/test validation while implementing, then run configured quality gates before PR handoff.
- [x] 5.2 Run ponytail full mode simplification review on the current diff and apply actionable recommendations.
- [x] 5.3 Perform context findings review and update docs or memory only if durable reusable knowledge is discovered.
- [ ] 5.4 Prepare PR and Plane handoff with validation, docs/context findings, memory result, assumptions, and any chained-PR decision.
