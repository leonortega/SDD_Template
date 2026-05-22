## Why

The repository needs an initial application surface so the local delivery lab can build, validate, and later deploy a real site artifact. Creating a blank Blazor site establishes the baseline project structure for future feature tickets.

## What Changes

- Add a new blank Blazor web application targeting .NET 10.
- Add a solution and conventional source folder layout for the site.
- Include standard Blazor entry points, routing, layout, page, and static asset structure.
- Ensure the scaffolded site can be built from the command line.

## Capabilities

### New Capabilities

- `blazor-site-scaffold`: Defines the baseline Blazor site structure and build expectation.

### Modified Capabilities

- None.

## Impact

- Adds a .NET solution and Blazor project under the application source tree.
- Introduces .NET 10 SDK build requirements for local development and CI.
- Establishes the initial site artifact that later delivery pipeline work can build, package, and deploy.
