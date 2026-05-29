## Context

The current application is a .NET 10 Blazor site with minimal health and metrics endpoints and no existing persistence layer. The ticket asks for client data storage, migrations, REST access, validation, and a CRUD view for client records.

## Goals / Non-Goals

**Goals:**
- Introduce client persistence with a migration-managed schema.
- Expose REST endpoints for client CRUD operations.
- Validate client create and update input before persistence.
- Provide a Blazor page for listing, creating, editing, and deleting clients.
- Cover the new behavior with automated tests.

**Non-Goals:**
- Authentication, authorization, or role-specific client access.
- Bulk import/export, search, sorting, or pagination beyond what is needed for a usable initial CRUD view.
- Production database provisioning outside the application migration and configuration shape.

## Decisions

- Use Entity Framework Core for persistence and migrations because the ticket explicitly requires database elements using migrations and the app is a .NET application. Alternative: hand-written SQL scripts, which would add more custom deployment mechanics and less testable application integration.
- Keep Client as an application-owned model with explicit request DTOs for create/update operations. This keeps validation and API contracts separate from persistence details. Alternative: bind API requests directly to the entity, which would make accidental persistence-field exposure more likely.
- Implement REST endpoints under a client-specific route group such as `/api/clients`. Minimal APIs fit the current `Program.cs` style and avoid introducing controller structure before the app needs it.
- Use Blazor components/pages for the CRUD view and call the REST API through a typed client or local service abstraction. This keeps the UI aligned with the user-facing API contract while still allowing tests to exercise API behavior independently.
- Use required string/date validation for the requested client fields and normalize field names in code to conventional C# names, including `LastName`, `BornDate`, and `ZipCode`.

## Risks / Trade-offs

- [Risk] The desired database provider is not specified. -> Mitigation: choose the repo's established provider if one exists during implementation; otherwise use a local-friendly EF Core provider and document the choice.
- [Risk] The ticket does not define exact field lengths or date constraints. -> Mitigation: set conservative validation rules during implementation and cover them in tests.
- [Risk] UI and API behavior can drift if duplicated validation logic grows. -> Mitigation: centralize request validation and reuse DTO contracts where practical.

## Migration Plan

1. Add the EF Core model, DbContext, provider configuration, and initial client migration.
2. Add REST endpoints and validation for client CRUD operations.
3. Add the Blazor CRUD page and navigation.
4. Add tests for schema/persistence, API success and failure paths, and UI page availability.
5. Run the configured build, test, coverage, and formatting gates before PR handoff.

Rollback for this development change is to revert the branch before merge. After deployment, rollback follows the repository artifact promotion and rollback workflow.

## Open Questions

- The ticket does not specify the database provider. Implementation should follow existing repo configuration if present, otherwise choose the smallest provider that satisfies local and deployed environments.
- The ticket title says "por a client"; this proposal treats it as "for a client" while preserving the ticket key and title in workflow markers.
