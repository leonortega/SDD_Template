# ADR-0003: Shared Database Engine And Migration Jobs (Runtime-Agnostic)

## Status

Accepted (2026-08-12). Decision driven by the human owner across three review rounds; the
schema, CI, and manifest changes are now landed (2026-08-12). Drafted by the AI at the human
owner's request; the human owner retains final say.

Shipped-state note (implementation): `infra/deployment/apps.json` stays empty — registering
apps requires a product stack, and the template ships no stack-specific Dockerfiles
(authority-5 never-assume-stack gate). Per ADR-0005 the template ships **no reference apps at
all**: `apps/` is empty, `infra/k8s/shared/database/` remains the composed shared-engine
machinery in every env overlay, and `db-bootstrap` ships as a **scaffold template** under
`.template/scaffold/db-bootstrap/` that the scaffold materializes as `apps/db-bootstrap/` when
a consumer registers database-backed apps (`kind: job` for bootstrap/migration apps,
`kind: service` for the rest).

## Context

ADR-0002 established the `apps/<appId>/` + `packages/` layout for a portfolio of deployable
applications and removed `infra/k8s/base/`: cluster-level concerns stay in `infra/`, per-app
manifests live in each app's `deploy/`, and environment overlays compose them.

The repository is a product-free, stack-agnostic SDLC shell: no product code ships, the stack
lives in `.template/project-profile.local.json` (`stack.frontend` / `stack.backend` /
`stack.database`), and the AI scaffold (`dev-flow-scaffold-project`) generates per-stack
artifacts — never a fixed template list.

The portfolio (up to 12 deployable apps) needs shared persistence and schema migrations without
coupling the template to any one stack:

- Per-app database engines (one StatefulSet/PVC per app) are wasteful in a single-node kind lab
  and push a deployment-topology decision into the template shape.
- A single shared engine per environment namespace with per-app logical databases fits the lab
  and keeps persistence a project-level choice.
- Migration mechanics must not leak into CI: EF Core, Alembic, Flyway, golang-migrate, and knex
  all apply "whatever is in this folder" differently, and the template cannot assume one.
- Portfolio apps may legitimately use different runtimes (dotnet, node, python, go). The existing
  per-profile stack model records the primary domain choices; a per-app `runtime` field is the
  honest pivot for build/test/migration commands.

## Decision

1. **Shared engine per environment** — `infra/k8s/shared/database/` (not `base/`, which
   ADR-0002 deleted) holds `statefulset.yaml` + `pvc.yaml` + `service.yaml` (ClusterIP,
   e.g. `db.internal`, patched to NodePort per env via `ports.json` — see below) +
   `kustomization.yaml`. It is composed into every env overlay, so each
   namespace (`sdd-dev` / `sdd-qa` / `sdd-prod`) gets exactly one engine. Apps connect via
   `db.internal` plus their own logical database name (orders, storefront, ...). The engine
   itself is a project-wide choice from `project-profile.local.json → stack.database`, never a
   per-app field.
2. **Cluster-level manifests home** — `infra/k8s/shared/` is the corrected home for shared
   cluster resources (ADR-0002 decision 3); the deleted `infra/k8s/base/` stays deleted.
3. **`db-bootstrap` (kind: job)** — bootstrap-only Job that creates logical databases,
   roles, and extensions at engine level. It must be idempotent (re-runnable after a kind
   cluster recreation). Its image carries the engine client (`psql` / `sqlcmd`) — unavoidable
   and owned at project level, deliberately not tied to any app's runtime. Job, no Service, no
   ports.
4. **Per-app `migrations/` folder** — a runtime-agnostic slot for the app's own schema
   migrations; the migration tool is implied by the app's resolved stack (recorded via
   `runtime`). Each service app ships `deploy/migration-job.yaml`, which runs "whatever is in
   `migrations/`" through the app's own image entrypoint — CI knows only that the Job exists
   and how to wait for it, never the tool.
5. **`apps.json` gains `kind` + `runtime`** — `kind ∈ {service, job}` tells CI whether an app
   is wait-for-completion (Job) or rollout (Deployment); `runtime` records the resolved stack
   choice, filled at scaffold time. The shipped `apps.json` is empty (`"apps": []`); runtime is
   never pre-filled — honoring the authority-5 never-assume-stack gate. Schema: add `kind` (enum) and `runtime`
   (optional, `^[a-z][a-z0-9-]*$`); `role` stays a free string — `role: "job"` is already
   schema-valid because `apps.schema.json` defines no role enum. Job apps are excluded from
   `ports.json` (no ports). The shared database is the one infra service that IS registered:
   `roles.json` ships a `database` role (host base 5432, nodePort offset 700, TCP health
   check) and `ports.json` assigns per-env host/node ports (dev 5432/30700, qa 5433/31700,
   prod 5434/32700) with a `serviceName: db.internal` override so the overlay gate matches
   the rendered Service name. The health probe TCP-checks it so the Grafana Service Health
   panel shows the database row per environment.
6. **Overlay composition (corrected paths)** — from `infra/k8s/overlays/{env}/`:
   `../../shared/database` (2 levels up into `infra/k8s/`) and `../../../../apps/<appId>/deploy`
   (4 levels up to the repo root) per app; `service-patch.yaml` stays wired under `patches:`
   (`patches:` → `- path: service-patch.yaml`), not `resources:`. It now also carries the
   database NodePort per env.
7. **CI apply order (`package-deploy.yml`)** — `db-bootstrap` Job first, then
   `kubectl wait --for=condition=complete`, then per-app `migration-job.yaml`s (diff-scoped on
   PR-merge; every app on pinned dispatch), wait, then Deployments via rollout. A Job failure
   fails the deploy; rollouts never start before migrations complete. The PROD path (pinned
   `artifact_commit_sha`, no rebuild) skips diff-filtering and applies every app in the commit
   with the ordering intact.
8. **Stack-agnostic mechanics (Path A)** — `runtime` feeds the AI scaffold's per-app choices
   (base image, migration runner, test runner). No `.template/<runtime>/` skeleton directories:
   the AI-delegated scaffold stays the mechanism and `.template/` remains configuration-only.
9. **`packages/` grouped by runtime** — `packages/dotnet/`, `packages/node/`, ... created only
   when shared code exists for a runtime; build-time only, never deployed.

## Considered And Rejected

- **Per-app database engines** — resource-heavy for a single-node lab; deployment topology is a
  product decision, not template shape.
- **`.template/<runtime>/` skeleton libraries (Path B)** — a fixed template list; contradicts
  the AI-driven `dev-flow-scaffold-project` contract and `.template/`'s documented
  configuration-only role.
- **`migrationTool` field in `apps.json`** — dropped; the tool is implied by the resolved
  stack, keeping CI tool-agnostic.
- **Polyglot single apps** (e.g. Go service with a Python sidecar) — rejected for now: the
  manifest model assumes one Dockerfile → one image → one container per app. Multi-image
  deployments are a larger change and are documented, not folded in.

## Consequences

### Positive

- One engine per environment namespace; per-app logical databases scale the portfolio without
  12× StatefulSet/PVC pairs.
- Migrations decoupled from CI tooling — any runtime fits the same shape.
- `runtime` is the single stack pivot; everything else in the tree is runtime-identical.
- Cluster-level concerns stay in `infra/` (ADR-0002); job apps keep ports and the overlay gate
  unchanged.

### Required changes (pending — not yet landed)

- `infra/deployment/apps.schema.json` — add `kind` (enum `service`/`job`) and `runtime`
  (optional, pattern). `role: "job"` needs no change (no enum today).
- `validate-app-config` — logic unchanged, but a registered `db-bootstrap` app must have a
  `Dockerfile` at its `projectPath` like every registered app.
- `scaffold_k8s` — `kind` branch: job apps emit `job.yaml` (no Service, no ports); service apps
  unchanged.
- `.gitea/workflows/package-deploy.yml` — phased applies (bootstrap → migration-jobs →
  deployments), `wait --for=condition=complete`, Job-failure gating, dispatch-path ordering.
- `infra/k8s/shared/database/` — `kustomization.yaml` plus StatefulSet (with readiness/liveness
  probes, e.g. `pg_isready`), PVC, and the `db.internal` Service (ClusterIP base, upgraded to
  NodePort per env by the overlay service patches generated from `ports.json`). The overlay-compose
  guard (`test_k8s_validate`) requires every composed resource to resolve to a directory containing
  a `kustomization.yaml`.
- Environment overlays — add `shared/database` (and `db-bootstrap` + per-app migration jobs
  when apps are registered) to `resources:`.
- Operations notes — kind PVC data is lost on cluster recreation (consistent with the existing
  "kind cluster not persistent" limitation); `db-bootstrap` must be idempotent.
- Docs — `knowledge/references/project-map.md`, `docs/architecture/deployment.md`,
  cross-reference from ADR-0002.

### Deferred (explicit decision, not an omission)

- Runtime-aware tooling — `stack_tests.py` framework selection, `ensure-stack-toolchain`
  install set, `configure-ci-workflows` build/test steps, and the `environment_lab` semgrep
  mapping — stays profile-wide until the first app is registered with a non-empty `runtime`.
  Trigger to revisit: the first runtime-filled `apps.json` entry.

## Related Decisions

- ADR-0002 (product layout + deployment model) — this ADR extends it with the shared cluster
  resources home and the `kind` field.
- ADR-0001 (repository remains an SDLC shell) — the stack-agnostic guarantees this ADR
  preserves.
