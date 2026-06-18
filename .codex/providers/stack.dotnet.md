# Stack Adapter: .NET

Use this adapter only when `.codex/project-profile.json` lists the .NET stack.

## Sources Of Truth

- Project files define target frameworks and package references.
- Workflow files define CI commands and job images.
- `infra/deployment/apps.json` defines deployable project topology.
- `.codex/project-profile.json` declares stack identity for skill routing only.

## Local Gates

- Restore, format, build, test, coverage, and dependency audit commands are defined by the current workflow and quality gate configuration.
- Use framework-specific skills only when their trigger matches the work, such as ASP.NET Core or Web API changes.

## Failure Rules

- Do not hard-code SDK or package versions in generic delivery skills.
- Do not invent architecture changes outside the active ticket scope.
- Keep framework guidance in stack-specific skills or this adapter, not in generic workflow skills.
