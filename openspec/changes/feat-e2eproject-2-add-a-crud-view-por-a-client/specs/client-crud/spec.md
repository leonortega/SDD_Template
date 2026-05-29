## ADDED Requirements

### Requirement: Client data model
The system SHALL define a persisted Client record with Name, Last Name, Address, Born date, City, Country, and ZIP code fields.

#### Scenario: Client schema is available
- **WHEN** the application database schema is created from migrations
- **THEN** the schema MUST include storage for each required Client field.

### Requirement: Client validation
The system SHALL validate Client create and update requests before saving them.

#### Scenario: Missing required client data
- **WHEN** a create or update request omits a required Client field
- **THEN** the system MUST reject the request with validation errors and MUST NOT save the invalid record.

#### Scenario: Invalid client field format
- **WHEN** a create or update request includes an invalid Born date or ZIP code value
- **THEN** the system MUST reject the request with validation errors and MUST NOT save the invalid record.

### Requirement: Client REST API
The system SHALL expose REST endpoints for listing, reading, creating, updating, and deleting Client records.

#### Scenario: Create client through API
- **WHEN** a caller submits a valid Client create request
- **THEN** the API MUST persist the Client and return the created record.

#### Scenario: Update client through API
- **WHEN** a caller submits a valid update for an existing Client
- **THEN** the API MUST persist the changed Client fields and return the updated record.

#### Scenario: Delete client through API
- **WHEN** a caller deletes an existing Client
- **THEN** subsequent API reads for that Client MUST report that the Client no longer exists.

### Requirement: Client CRUD view
The system SHALL provide a Blazor CRUD view for managing Client records.

#### Scenario: View client records
- **WHEN** a user opens the Client CRUD view
- **THEN** the page MUST show existing Client records or an empty state when no records exist.

#### Scenario: Manage client records
- **WHEN** a user creates, edits, or deletes a Client through the CRUD view
- **THEN** the UI MUST call the REST API and reflect the resulting Client list state.
