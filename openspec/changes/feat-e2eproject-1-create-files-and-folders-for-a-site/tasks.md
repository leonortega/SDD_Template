## 1. Project Scaffold

- [x] 1.1 Create a .NET solution for the Blazor site.
- [x] 1.2 Create a Blazor web project under `src/` targeting .NET 10.
- [x] 1.3 Add the Blazor project to the solution.

## 2. Blank Site Structure

- [x] 2.1 Ensure the project contains standard startup, routing, root component, layout, page, and static asset files.
- [x] 2.2 Keep the initial UI blank/minimal without adding domain-specific features.
- [x] 2.3 Update documentation only if needed to identify the build command.

## 3. Validation

- [x] 3.1 Run the solution-level `dotnet build` command with a compatible .NET 10 SDK.
- [x] 3.2 Confirm the build completes without restore or compile errors.
- [x] 3.3 Add scaffold tests so Gitea PR validation can produce coverage for the new solution.
- [x] 3.4 Add repository NuGet source configuration so restore is not blocked by machine-level package sources.
- [x] 3.5 Align generated template code with repository style checks that run during build.
- [x] 3.6 Update PR validation to use a .NET 10 SDK image that the local Gitea runner can pull successfully.
- [x] 3.7 Replace JavaScript-based PR validation actions with shell steps compatible with the .NET SDK container.
- [x] 3.8 Map local Gitea hostnames to the Docker host during containerized shell checkout.
- [x] 3.9 Pin Gitleaks installation to the Linux release archive instead of the removed install script.
