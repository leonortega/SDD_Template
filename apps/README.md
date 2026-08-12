# apps/ — Product applications (generated, not shipped)

This directory is **empty in the template** by design (ADR-0005): the template ships
no product code and no example apps. Every app under `apps/<appId>/` is generated at
stack-selection time by the AI-driven scaffold (`dev-flow-scaffold-project` +
`scaffold-k8s`) from:

- the selected stack in `.template/project-profile.local.json` (`stack.frontend` /
  `stack.backend` / `stack.database`),
- the port roles in `infra/deployment/roles.json`,
- the starting shapes in `.template/scaffold/`.

Once apps exist, register them in `infra/deployment/apps.json` (schema:
`apps.schema.json`), allocate ports via `assign-app-ports`, and the env overlays
compose each app's `deploy/` automatically. See
`docs/architecture/deployment.md` and `docs/adr/ADR-0005-no-reference-apps.md`.
