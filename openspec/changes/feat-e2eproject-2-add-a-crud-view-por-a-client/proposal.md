## Why

The application needs a way to manage client records through both the UI and a REST API. This ticket establishes the client data model, persistence, validation, and CRUD workflow needed for users to create and maintain client information.

## What Changes

- Add a persisted Client entity with Name, Last Name, Address, Born date, City, Country, and ZIP code fields.
- Add database migration support for the client storage schema.
- Add REST API endpoints for client list, detail, create, update, and delete operations.
- Add validation for client creation and update requests.
- Add a Blazor CRUD view for managing client records.
- Add tests covering persistence, API behavior, validation, and UI availability.

## Capabilities

### New Capabilities
- `client-crud`: Client record persistence, REST CRUD operations, validation, and UI management.

### Modified Capabilities

## Impact

- `src/SDDTemplate.Site` data model, persistence setup, API routing, UI pages/components, and navigation.
- `tests/SDDTemplate.Site.Tests` coverage for client API, validation, persistence, and CRUD page rendering.
- Project dependencies may expand to include Entity Framework Core packages and database provider support if not already present.
