## 1. Persistence

- [x] 1.1 Select the database provider based on existing repo configuration or the smallest local-friendly EF Core option.
- [x] 1.2 Add the Client entity with Name, LastName, Address, BornDate, City, Country, and ZipCode fields.
- [x] 1.3 Add the application DbContext and register it in the app startup configuration.
- [x] 1.4 Create the initial migration for Client storage.

## 2. API And Validation

- [x] 2.1 Add create and update request DTOs with validation rules for required fields and field formats.
- [x] 2.2 Add REST endpoints for listing, reading, creating, updating, and deleting Client records.
- [x] 2.3 Return appropriate success, validation, not-found, and delete responses from the Client API.

## 3. CRUD UI

- [x] 3.1 Add a Blazor Client CRUD page that lists existing records and handles the empty state.
- [x] 3.2 Add create and edit form behavior that submits through the Client API and displays validation errors.
- [x] 3.3 Add delete behavior that removes a Client through the API and refreshes the visible list.
- [x] 3.4 Add navigation to the Client CRUD view if the existing layout supports navigation links.

## 4. Tests And Gates

- [x] 4.1 Add persistence and migration-related tests for Client storage.
- [x] 4.2 Add API tests for successful create, read, update, delete, and not-found behavior.
- [x] 4.3 Add validation tests for missing required fields and invalid field formats.
- [x] 4.4 Add UI/page rendering tests for the Client CRUD route and visible empty/list states where supported.
- [x] 4.5 Run the configured build, test, coverage, formatting, and security gates before PR handoff.
- [x] 4.6 Fix Gitea Actions PR-validation blockers found during handoff rerun.

## PR Review Feedback

- [x] RF-1 Source: human review `robert` review id 5 on head `a25a8a8b90e71e687ae8fa008f41d813725a9a3b`; severity: BLOCKER; requested change: separate the Client REST API from the Blazor site and move database entities, DbContext, migrations, and setup into a separate data project for Azure web/API deployment alignment.
