## Requirements

### Requirement: Product data model
The system SHALL define a persisted Product record with Name, SKU, Status, Price, Category, and Last Updated fields in the data project that owns EF Core entities, DbContext, migrations, and database setup.

#### Scenario: Product schema is available
- **WHEN** the application database schema is created from migrations
- **THEN** the schema MUST include storage for each required Product field.

#### Scenario: Product last updated is maintained
- **WHEN** a product is created or updated
- **THEN** the system MUST store a Last Updated value representing the latest persisted change.

### Requirement: Product validation
The system SHALL validate Product create and update requests before saving them.

#### Scenario: Missing required product data
- **WHEN** a create or update request omits Name, SKU, Status, Price, or Category
- **THEN** the system MUST reject the request with validation errors and MUST NOT save the invalid record.

#### Scenario: Invalid product values
- **WHEN** a create or update request includes an invalid SKU, Status, or Price
- **THEN** the system MUST reject the request with validation errors and MUST NOT save the invalid record.

### Requirement: Product REST API
The system SHALL expose REST endpoints for listing, reading, creating, updating, and deleting Product records from the API project.

#### Scenario: Create product through API
- **WHEN** a caller submits a valid Product create request
- **THEN** the API MUST persist the Product and return the created record with its generated identifier and Last Updated value.

#### Scenario: Update product through API
- **WHEN** a caller submits a valid update for an existing Product
- **THEN** the API MUST persist the changed Product fields and return the updated record.

#### Scenario: Delete product through API
- **WHEN** a caller deletes an existing Product
- **THEN** subsequent API reads for that Product MUST report that the Product no longer exists.

#### Scenario: Read missing product through API
- **WHEN** a caller requests a Product identifier that does not exist
- **THEN** the API MUST return a not-found result without exposing stack traces or internal details.

### Requirement: Product CRUD page
The system SHALL provide a Blazor Products page for managing Product records.

#### Scenario: Navigate to Products page
- **WHEN** an authorized admin user uses the application navigation
- **THEN** the navigation MUST include a Products destination that opens the Products CRUD page.

#### Scenario: View product records
- **WHEN** a user opens the Products CRUD page
- **THEN** the page MUST show existing Product records with Name, SKU, Status, Price, Category, and Last Updated values or an empty state when no records exist.

#### Scenario: Create product through UI
- **WHEN** a user submits valid new Product details from the Products page
- **THEN** the UI MUST call the configured REST API and reflect the created Product in the list.

#### Scenario: Edit product through UI
- **WHEN** a user edits an existing Product and saves valid changes
- **THEN** the UI MUST call the configured REST API and reflect the saved Product fields after reload.

#### Scenario: Delete product through UI
- **WHEN** a user confirms deletion for an existing Product
- **THEN** the UI MUST call the configured REST API and remove the Product from the visible list.

### Requirement: Product page states
The Products page SHALL show explicit states for loading, empty results, successful operations, validation failures, and backend errors.

#### Scenario: Product list is loading
- **WHEN** the Products page is waiting for the list API response
- **THEN** the page MUST show a loading state.

#### Scenario: Product list is empty
- **WHEN** the list API returns no Product records
- **THEN** the page MUST show an empty state.

#### Scenario: Product operation succeeds
- **WHEN** create, update, or delete succeeds
- **THEN** the page MUST show a success state or message and refresh the list from the API-backed state.

#### Scenario: Product operation fails
- **WHEN** the API returns validation or server errors for a Product operation
- **THEN** the page MUST show clear errors without corrupting the current list state.

### Requirement: Product access restrictions
The system SHALL prevent users without proper permissions from accessing Products management behavior.

#### Scenario: Unauthorized page access
- **WHEN** a user without product-management permission requests the Products page
- **THEN** the system MUST deny access or render the configured unauthorized state.

#### Scenario: Unauthorized API access
- **WHEN** a caller without product-management permission sends a Product CRUD API request
- **THEN** the API MUST reject the request and MUST NOT expose or mutate Product records.
