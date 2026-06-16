## Why

Plane ticket E2EPROJECT-7 requests a centralized Products management experience for admin users. The current application has a Clients CRUD pattern, but no product management capability for creating, viewing, updating, and deleting product records.

## What Changes

- Add a Products CRUD page reachable from application navigation for authorized admin users.
- Add product persistence and REST API behavior for list, detail, create, update, and delete operations.
- Add product validation for required fields and invalid values before data is saved.
- Add UI states for loading, empty, success, validation errors, backend errors, and delete confirmation.
- Add automated tests covering product CRUD, validation, persistence, and access control expectations.

## Capabilities

### New Capabilities

- `product-crud`: Defines the persisted Product data model, validation, REST API, Blazor management page, UI states, and access restrictions for product records.

### Modified Capabilities

- None.

## Impact

- `src/SDDTemplate.Data`: Product entity, DbContext mapping, migration, and database setup updates.
- `src/SDDTemplate.Api`: Product DTOs, CRUD endpoints, validation, and access control behavior.
- `src/SDDTemplate.Site`: Products navigation, page, form/list/detail/edit/delete flows, API calls, and UI state rendering.
- `tests/SDDTemplate.Site.Tests` and any E2E coverage added during implementation: product API, migration, page, validation, and authorization tests.
