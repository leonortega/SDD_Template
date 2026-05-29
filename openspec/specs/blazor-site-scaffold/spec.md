# blazor-site-scaffold Specification

## Purpose
Defines the baseline Blazor site scaffold used by the delivery lab, including solution membership, project structure, .NET target, and command-line build expectations.

## Requirements
### Requirement: Blazor site solution
The repository SHALL include a .NET solution for the blank Blazor site.

#### Scenario: Build from solution
- **WHEN** a developer runs the documented solution-level build command
- **THEN** the Blazor site project MUST be included in the build.

### Requirement: Blazor project structure
The repository SHALL include a Blazor web project under the application source tree with conventional entry point, component, page, layout, and static asset folders.

#### Scenario: Inspect scaffolded files
- **WHEN** a developer inspects the application source tree
- **THEN** the project MUST contain standard Blazor files for startup, routing, a root app component, layout, at least one routable page, and static web assets.

### Requirement: .NET 10 target
The Blazor project SHALL target .NET 10.

#### Scenario: Inspect project target framework
- **WHEN** a developer opens the Blazor project file
- **THEN** the target framework MUST be set to a .NET 10 target framework moniker.

### Requirement: Blank site build validation
The blank Blazor site SHALL build successfully from the command line.

#### Scenario: Command-line build
- **WHEN** a developer runs `dotnet build` for the solution with a compatible .NET 10 SDK
- **THEN** the build MUST complete without restore or compile errors.
