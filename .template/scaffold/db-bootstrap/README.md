# db-bootstrap (kind: job) — starting template

Engine-level bootstrap Job (ADR-0003): creates logical databases, roles, and
extensions on the shared engine — nothing else. It deliberately knows **no app
schema**; per-app schema migrations live in each app's `migrations/` folder and
run via that app's `deploy/migration-job.yaml`.

This is a **scaffold template** (ADR-0005), not a shipped app: when a consumer
registers database-backed apps, the scaffold materializes it as
`apps/db-bootstrap/` and rewrites the engine-client image + `src/bootstrap.sh`
for the engine chosen in `project-profile.local.json → stack.database`
(shipped shape: Postgres).

## Rules

- **Idempotent** — must be re-runnable after a kind cluster recreation
  (`IF NOT EXISTS` semantics; the engine's PVC dies with the cluster).
- **Job, no Service, no ports** — registered `kind: job` (plus `role: job`);
  it never appears in `ports.json`, so the overlay gate, health probe, and URL
  discovery are untouched by it.
- **Engine-client image** — the Dockerfile ships the engine client (`psql`),
  not an app runtime.

## CI behavior

`package-deploy.yml` treats `kind: job` apps as wait-for-completion phases:
`kubectl wait --for=condition=complete` before any Deployment rollout starts.

See `docs/adr/ADR-0003-shared-database-and-migrations.md`.
