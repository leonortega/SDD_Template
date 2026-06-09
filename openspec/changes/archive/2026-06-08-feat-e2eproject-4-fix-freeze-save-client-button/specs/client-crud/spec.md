## ADDED Requirements

### Requirement: Client create works after routed navigation
The system SHALL allow a user to create a Client from the Clients CRUD view on the first save attempt after navigating to the view from another application page.

#### Scenario: Save client after main-page navigation
- **WHEN** a user opens the main page, navigates to the Clients CRUD view through application navigation, completes all required Client fields, and clicks `Save Client` once
- **THEN** the UI MUST submit the create request and reflect the created Client without requiring a browser refresh.

#### Scenario: Invalid client after main-page navigation
- **WHEN** a user opens the main page, navigates to the Clients CRUD view through application navigation, leaves required Client fields missing or invalid, and clicks `Save Client`
- **THEN** the UI MUST show validation errors and MUST NOT create a Client record.
