## Why

Plane ticket `E2EPROJECT-3` reports that the first client created from the website CRUD page is not saved on the first attempt because the flow performs the Select Client GET behavior instead of the Create Client POST behavior. This breaks the empty-client onboarding path and forces users to submit a second time before the client exists.

## What Changes

- Fix the client CRUD page so the first client creation submits the create/save operation on the first attempt.
- Preserve the existing Select Client flow for choosing an existing client.
- Preserve subsequent client creation behavior after at least one client exists.
- Add automated coverage for the zero-clients creation path.

Non-goals:

- No data model changes.
- No new client fields or validation rules beyond the existing create form behavior.
- No deployment workflow or infrastructure changes.

## Capabilities

### New Capabilities

- `client-crud-first-create`: Covers creating the first client from the website CRUD page when no clients exist yet.

### Modified Capabilities

- None.

## Impact

- Blazor client CRUD page components and form/event handlers under `src/SDDTemplate.Site`.
- Client persistence/API interaction used by the CRUD page when saving a new client.
- Site test coverage under `tests/SDDTemplate.Site.Tests`.
