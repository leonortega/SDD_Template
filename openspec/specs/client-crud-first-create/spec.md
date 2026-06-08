# client-crud-first-create Specification

## Purpose

Ensure the client CRUD page saves the first client on the first submit when the list starts empty, while preserving existing selection and later create flows.

## Requirements

### Requirement: First Client Creation Uses Create Flow

The client CRUD page SHALL persist the first client on the first form submit when the client list is initially empty.

#### Scenario: First client is saved from empty state

- **WHEN** a user opens the client CRUD page with no existing clients and submits valid new-client details
- **THEN** the system persists the client through the create/save operation and displays the created client without requiring a second submit

#### Scenario: First create does not trigger select flow

- **WHEN** a user submits valid new-client details while no existing clients are available to select
- **THEN** the system does not use the Select Client load path as a substitute for saving the client

### Requirement: Existing Client Workflows Remain Available

The client CRUD page SHALL preserve existing client selection and subsequent client creation behavior after at least one client exists.

#### Scenario: Subsequent client is saved

- **WHEN** a user submits valid new-client details after another client already exists
- **THEN** the system persists the new client on the first submit

#### Scenario: Existing client can still be selected

- **WHEN** a user selects an existing client from the client list
- **THEN** the system loads that client into the edit flow without creating a duplicate client
