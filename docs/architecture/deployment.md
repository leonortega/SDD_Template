# Deployment

## Technology Stack And Tool Set

Kubernetes is the **only** deployment target for this project. The cluster runs on **kind** (Kubernetes in Docker) by
default, with Docker Desktop's built-in K8s as a fallback.

| Layer              | Status                 | Detail                                                                   |
| ------------------ | ---------------------- | ------------------------------------------------------------------------ |
| Deployment target  | kind cluster           | Single-node K8s cluster (`sdd-cluster`) via kind (installed by `setup-lab`) |
| Container registry  | Nexus (:5001)          | Docker hosted repository for CI-built images                             |
| Artifact storage   | Nexus (:8088)          | Raw hosted repository for build artifacts and manifests                  |
| Environments       | dev, qa, prod          | Three K8s namespaces (sdd-dev, sdd-qa, sdd-prod) with Kustomize overlays |
| CI/CD              | Gitea Actions          | PR validation + package-deploy workflows                                 |
| Observability      | Grafana + Seq + Dozzle | Health dashboards, log search, container monitoring                      |

No app target is currently deployable. Product apps will be added through `infra/deployment/apps.json` when the product
stack is defined.

## Architecture Overview

```text
text
┌──────────────────────────────────────────────────────────┐
│  Docker Desktop Host                                     │
│                                                          │
│  ┌─ kind cluster ─────────────────────────────────────┐  │
│  │  Namespace: sdd-dev                                 │  │
│  │  ┌──────────────┐    ┌──────────────┐              │  │
│  │  │ Deployment:   │    │ Service:     │              │  │
│  │  │ frontend      │───▶│ frontend     │── NodePort   │  │
│  │  │ (nginx:80)    │    │ type:        │── localhost:8081│  │
│  │  └──────────────┘    └──────────────┘              │  │
│  │                                                    │  │
│  │  Connected to: agentic-e2e_gitea,                   │  │
│  │  agentic-e2e_nexus networks (for CI access)         │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ Docker Compose ───────────────────────────────────┐  │
│  │  Gitea :3000 │ Nexus :8088 │ Grafana :3001         │  │
│  │  Nexus Docker Registry :5001                        │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Key Components

| Component                    | Host                   | Port   | Purpose                                    |
| ---------------------------- | ---------------------- | ------ | ------------------------------------------ |
| K8s Cluster (kind)            | `localhost` / `host.docker.internal` | 64366 | Runs app Deployments + Services (kind cluster `sdd-cluster`) |
| Nexus Artifacts              | `host.docker.internal` | `8088` | Stores build artifacts + env URL manifests |
| Nexus Docker Registry        | `host.docker.internal` | `5001` | Stores container images (CI pushes here)   |
| Gitea                        | `host.docker.internal` | `3000` | Source control + CI runner                 |
| Gitea MCP (shared HTTP)      | `localhost`            | `8123` | Single gitea-mcp server for all MCP clients (`/mcp`) |
| Grafana                      | `localhost`            | `3001` | Health monitoring dashboards               |

## Environment Model

Three environments, each a separate K8s namespace:

| Environment | Namespace  | Replicas | Trigger                           |
| ----------- | ---------- | -------- | --------------------------------- |
| **dev**     | `sdd-dev`  | 1        | PR merged into `dev` branch       |
| **qa**      | `sdd-qa`   | 2        | `workflow_dispatch` with env=qa   |
| **prod**    | `sdd-prod` | 3        | `workflow_dispatch` with env=prod |

Each environment uses a **Kustomize overlay** that inherits from a shared base:

```text
infra/k8s/
├── base/                        # Shared manifests
│   ├── kustomization.yaml
│   ├── deployment.yaml          # Deployment with ContainerPort 80
│   └── service.yaml             # NodePort type
├── overlays/
│   ├── dev/
│   │   ├── kustomization.yaml   # images.newTag: latest
│   │   └── service-patch.yaml   # dev nodePorts (30080/30500)
│   ├── qa/
│   │   ├── kustomization.yaml
│   │   └── service-patch.yaml   # QA nodePorts (31080/31500)
│   ├── prod/
│   │   ├── kustomization.yaml
│   │   └── service-patch.yaml   # PROD nodePorts (32080/32500)
│   │   └── kustomization.yaml
│   └── prod/
│       └── kustomization.yaml
└── Dockerfile                   # Per-app multi-stage build
```

**Note:** The base `namespace.yaml` and overlay `config-patch.yaml` files were removed to fix a Kustomize build failure
(unresolved `${COMPONENT_NAME}` placeholders blocked `kustomize build`). Namespaces are created by the CI workflow via
`kubectl create namespace`, and image tags are set by `kustomize edit set image`. If you need per-overlay environment
variables, add patches targeting actual deployment names (not placeholder variables).

### Service Type: NodePort

Services use `type: NodePort` with **fixed per-environment nodePorts** defined in `infra/k8s/kind-config.yaml`
(canonical source: `infra/deployment/ports.json`). The nodePort itself is only reachable **inside the cluster network**
(e.g. from the health-probe on `agentic-e2e_monitoring`) — from the Windows host it is NOT accessible at
`localhost:{nodePort}`. Kind's `extraPortMappings` expose the services at the **host ports** listed in the tables below
(`localhost:{hostPort}`).

**No Ingress controller is needed** — each service is reachable directly via its host-mapped port.

## CLI Commands

Three `environment-lab` commands manage the K8s deployment setup:

### scaffold-k8s

Generate Dockerfiles, K8s manifests, and environment overlays. Reads `infra/deployment/apps.json` to determine which
apps to scaffold. Validates Docker Desktop K8s as a prerequisite.

```bash
# Dry-run (preview what would be created)
python -m tools.sdd_cli environment-lab scaffold-k8s --dry-run true

# Real run (creates Dockerfiles, manifests, overlays)
python -m tools.sdd_cli environment-lab scaffold-k8s
```

Generates per app:

- `frontend/Dockerfile` — multi-stage (node build → nginx serve)
- `frontend/.dockerignore` — excludes node_modules, .git, .env
- `frontend/nginx.conf` — SPA routing + /health endpoint
- `infra/k8s/deploy.yaml` — single envsubst manifest (Namespace, Deployment, Service)

**Note:** The CI workflow uses a Kustomize overlay structure (`infra/k8s/base/` + `infra/k8s/overlays/`) instead of the
envsubst manifest. The Kustomize overlays must be created/updated separately from `scaffold-k8s`. See the
`dev-ops-configure-k8s` skill for overlay setup guidance.

### setup-kind-cluster

Creates a kind cluster with extraPortMappings for direct host access (no kubectl port-forward).
Run automatically by `setup-lab`, or manually:

```bash
python -m tools.sdd_cli environment-lab setup-kind-cluster
```

**Idempotent** — skips creation if `sdd-cluster` already exists.

Uses `infra/k8s/kind-config.yaml` which defines fixed port mappings:

| Host Port | Service         | NodePort |
| --------- | --------------- | -------- |
| `8081`    | frontend (DEV)  | `30080`  |
| `5002`    | backend (DEV)   | `30500`  |
| `8082`    | frontend (QA)   | `31080`  |
| `5003`    | backend (QA)    | `31500`  |
| `8083`    | frontend (PROD) | `32080`  |
| `5004`    | backend (PROD)  | `32500`  |

This replaces the old Docker Desktop K8s requirement. Steps:

1. **Installs kind** — via winget (Windows), brew (macOS), or direct download (Linux)
2. **Creates `sdd-cluster`** — with extraPortMappings from `infra/k8s/kind-config.yaml`
3. **Saves CI kubeconfig** — to `infra/k8s/kind-kubeconfig-ci.yaml` (replaces `127.0.0.1` → `host.docker.internal`, sets
`insecure-skip-tls-verify: true`)
4. **Exports host kubeconfig** — merges into `~/.kube/config`
5. **Connects to Docker networks** — attaches `sdd-cluster-control-plane` to `agentic-e2e_gitea` and `agentic-e2e_nexus`
for CI access

### validate-docker-desktop-k8s

Check that K8s cluster (Docker Desktop or kind) is reachable:

```bash
python -m tools.sdd_cli environment-lab validate-docker-desktop-k8s
```

Validates:

- `kubectl` CLI is available
- K8s API server responds
- Current context (Docker Desktop, kind, or sdd-cluster)

### setup-k8s-access

Discover deployed service URLs and suggest port-forward commands:

```bash
python -m tools.sdd_cli environment-lab setup-k8s-access
```

For each app and environment, it either:

- **Discovers** the deployed Service's nodePort and shows the direct URL via the kind host port
- **Suggests** a `kubectl port-forward` command if not yet deployed

## CI Pipeline

The CI workflow (`.gitea/workflows/package-deploy.yml`) runs when a pull request targeting `dev` is **merged** (closed+
merged event) or on explicit `workflow_dispatch`:

```text
Checkout → Determine Env → Check Changed Paths (src/test) → Build Docker Images → Deploy to K8s → Discover URLs → Upload to Nexus
```

### Step Details

**1. Checkout** — Clones the commit using Gitea API token for auth.

**2. Determine Environment** — `dev` on a PR merge, or user-selected env on workflow_dispatch.

**2a. Check for Deployable Changes** — deploys in **any** environment run only when the change set touches a `src/`,
`test/`, or `tests/` folder at any depth (e.g. `src/...`, `frontend/src/...`, `backend/tests/...`). For a PR merge the
change set is the diff between the PR base and the merge commit; for `workflow_dispatch` it is the dispatched commit's
first-parent diff. Docs, infra, and workflow-only changes skip the entire deploy pipeline (the run stays green with the
deploy steps skipped).

**3. Build and Push Docker Images** — For each app in `apps.json` (**skipped for PROD** — PROD reuses the QA-approved
images pushed by the DEV/QA pipeline for the pinned artifact commit):

- Probes `http://host.docker.internal:5001/v2/` — if the registry is unreachable, the push is **skipped**
- Logs into Nexus Docker registry (`host.docker.internal:5001`) — plain-HTTP push requires `host.docker.internal:5001`
in Docker Desktop **insecure registries**
- Runs `docker build` using the app's `Dockerfile`
- Pushes `{appId}:{commitSha}` and `{appId}:latest` tags (only when login succeeded)
- **Loads images into the kind cluster** via `kind load docker-image` — this is the actual path used to get images to
the cluster (kind's containerd is separate from host Docker; without this the pods hit `ImagePullBackOff`)
- Prunes old local/kind images (keeps newest commit tags per app) so the runner's image store does not grow unbounded

**4. Deploy to K8s** — For the target environment:

- Reads `apps.json` to get app list
- Runs `kustomize edit set image` to set the commit SHA tag
- Runs `kustomize build . | kubectl apply -f -` (per-env overlays patch unique cluster-scoped nodePorts)
- Waits for rollout of each deployment

**5. Discover Environment URLs** — Single Python script:

- Calls `kubectl get svc -o jsonpath='{.spec.ports[0].nodePort}'` for each app
- Writes `app/{commitSha}/env-urls.json` with discovered URLs

**6. Upload to Nexus** — Uploads artifacts including:

- `app/{commitSha}/env-urls.json`
- `app/latest/env-urls-{env}.json` (latest pointer, overwritten each deploy)

### PROD Deployment Path

`workflow_dispatch environment=prod` takes a different path than DEV/QA (single workflow, conditional steps):

- **No build/republish** — the `Build and push Docker images` step is skipped; PROD reuses the QA-approved images
  pushed by the DEV/QA pipeline for the pinned commit.
- **Artifact pinning** — the dispatch input `artifact_commit_sha` (the QA-approved commit) selects the commit to
  deploy; it defaults to the dispatched ref's head commit.
- **Verification gate** — before deploying, the workflow downloads `app/{commitSha}/container-images.json` from
  Nexus, checks its `commitSha` matches, and confirms every image tag exists in the registry.
- **Health gate** — after deploy, every app's `/health` is checked through the PROD host ports
  (`host.docker.internal:{hostPort}`) and must return `status=ok`, or the run fails.
- **Release metadata** — optional `release_version` / `source_rc_version` dispatch inputs are recorded in
  `app/{commitSha}/release-prod.json`.

DEV and QA share the same pipeline (same build, per-env overlay deploy, auto-promote to QA); their `/health`
validation is performed by the agent after the run (`dev-ops-deploy-qa`).

### Runner Requirements

The Gitea Actions runner container needs specific configuration to work with CI. The config is written via heredoc in
`infra/gitea/compose.yml`:

```yaml
services:
  runner:
    image: gitea/runner:1.0.0
    container_name: agentic-gitea-runner
    depends_on:
      - gitea
    env_file:
      - ./runner.env
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - runner-data:/data
      - //var/run/docker.sock:/var/run/docker.sock  # Note: // prefix on Windows
    # Config is written via heredoc command:
    command:
      - sh
      - -c
      - |
        cat > /tmp/config.yml << YAMLEOF
        runner:
          labels: ["ubuntu-latest"]   # ⚠️ Must match workflow's runs-on
        container:
          network: agentic-e2e_nexus
          options: --user root --add-host host.docker.internal:host-gateway
          valid_volumes:
            - /var/run/docker.sock:/var/run/docker.sock  # Auto-mounted to CI containers
            - ${KUBE_SRC}:/home/runner/.kube/config:ro
        YAMLEOF
        export CONFIG_FILE=/tmp/config.yml
        exec run.sh
```

> **Note:** In `infra/gitea/compose.yml` the kubeconfig line is emitted **only when a
> kubeconfig source path is found** (`KUBE_SRC` non-blank). On machines without a host
> kubeconfig, `WIN_USER`, `first_user`, and `KUBE_SRC` are blank, the volume entry is
> omitted (a blank `${KUBE_SRC}` would render a malformed `- :/...` line), and the lab
> still works — runner jobs simply run without K8s volume access.

**Critical rules:**

1. **`labels: ["ubuntu-latest"]`** — Required for runner to match workflow's `runs-on: ubuntu-latest`
2. **Docker socket mount** — Mounted via `valid_volumes` (auto-mounts to CI containers). Do **NOT** add `--volume
/var/run/docker.sock` in `options` — that creates a duplicate mount causing `Duplicate mount point` error
3. **`options: --user root --add-host host.docker.internal:host-gateway`** — `--user root` fixes `permission denied` on
Docker socket; `--add-host` enables `host.docker.internal` DNS resolution
4. **Compose directory matters** — Always run `docker compose up -d --no-deps runner` from the **project root**
(`infra/compose.yml`), not from `infra/gitea/compose.yml`. The root compose sets the project name which prefixes all
networks; running from the wrong directory creates the runner on a different Docker network, causing DNS resolution
failures.

### CI Job Container Options

The CI workflow (`.gitea/workflows/package-deploy.yml`) also specifies options for the CI job container:

```yaml
container:
  image: sdd-e2e-ci:local
  options: --user root --add-host host.docker.internal:host-gateway
  # NO --volume /var/run/docker.sock:/var/run/docker.sock
  # (socket is auto-mounted by runner's valid_volumes)
```

### Gitea Secrets for CI

Required secrets set via API:

```bash
# API: PUT /api/v1/repos/{owner}/{repo}/actions/secrets/{secretname}
# Body: {"data": "<raw-value>"}
# Gitea handles base64 encoding internally — do NOT pre-encode

curl -u 'admin:admin123' -X PUT \
  'http://localhost:3000/api/v1/repos/admin/sdd-test/actions/secrets/KUBECONFIG' \
  -H 'Content-Type: application/json' \
  -d '{"data": "<raw-kubeconfig-yaml>"}'
```

| Secret | Description |
|--------|-------------|
| `KUBECONFIG` | Raw kubeconfig YAML for K8s cluster access (set via API) |
| `NEXUS_USERNAME` | Nexus admin username |
| `NEXUS_PASSWORD` | Nexus admin password |

## Prerequisites

Before any deployment:

1. **kind cluster** — Run `setup-lab` (step 16) or `python -m tools.sdd_cli environment-lab setup-kind-cluster` to
create `sdd-cluster`
2. **Apps defined** — `infra/deployment/apps.json` must list every deployable app
3. **K8s manifests scaffolded** — Run `scaffold-k8s` to generate Dockerfiles + manifests
4. **Nexus Docker registry configured** — Docker hosted repository (`docker-hosted`) on port `5001`. `setup-lab`
provisions it idempotently via the Nexus REST API (with `docker.httpPort: 5001` and `forceBasicAuth: true`; an existing
repo's connector port + Basic auth are reconciled). Anonymous access is disabled, so registry calls require the `admin`
credentials (`NEXUS_USERNAME`/`NEXUS_PASSWORD`)
5. **Gitea secrets** — `NEXUS_USERNAME`, `NEXUS_PASSWORD`, `KUBECONFIG` (provisioned automatically by `setup-lab`)
6. **Runner mounts** — Docker socket and kubeconfig mounted into the runner container

### Image Strategy

| Mode      | Build Command                               | Registry             | Image Tag             |
| --------- | ------------------------------------------- | -------------------- | --------------------- |
| Local dev | `docker build -t frontend:latest frontend/` | None (shared daemon) | `frontend:latest`     |
| CI build  | `docker build` + `docker push`              | Nexus :5001          | `{appId}:{commitSha}` |

## Accessing Deployed Apps

### Via kind extraPortMappings (direct — no port-forward needed)

The kind cluster is created with `infra/k8s/kind-config.yaml` which defines fixed
port mappings from the Windows host directly into the kind node container:

| Host Port | Service         | NodePort |
| --------- | --------------- | -------- |
| `8081`    | frontend (DEV)  | `30080`  |
| `5002`    | backend (DEV)   | `30500`  |
| `8082`    | frontend (QA)   | `31080`  |
| `5003`    | backend (QA)    | `31500`  |
| `8083`    | frontend (PROD) | `32080`  |
| `5004`    | backend (PROD)  | `32500`  |

After the CI pipeline deploys, you can access apps **directly at localhost**
without any `kubectl port-forward`:

```bash
# Frontend
curl http://localhost:8081/health
# Open in browser: http://localhost:8081

# Backend API
curl http://localhost:5002/health
```

To discover all deployed URLs:

```bash
python -m tools.sdd_cli environment-lab setup-k8s-access
```

Output:

```text
DEV frontend accessible at: http://localhost:8081/health (kind nodePort 30080 mapped to host:8081)
DEV backend accessible at: http://localhost:5002/health (kind nodePort 30500 mapped to host:5002)
QA frontend accessible at: http://localhost:8082/health (kind nodePort 31080 mapped to host:8082)
QA backend accessible at: http://localhost:5003/health (kind nodePort 31500 mapped to host:5003)
PROD frontend accessible at: http://localhost:8083/health (kind nodePort 32080 mapped to host:8083)
PROD backend accessible at: http://localhost:5004/health (kind nodePort 32500 mapped to host:5004)
```

## Grafana Monitoring

Grafana runs at `http://localhost:3001` (provisioned via Docker Compose).

### Managing the Monitoring Stack (Project `agentic-e2e`)

The monitoring stack (Grafana, health-probe, Seq, Dozzle) is defined in
`infra/monitoring/compose.yml` and included by the root compose file
`infra/compose.yml`, whose project name is **`agentic-e2e`**. **Always manage
the stack through the root file — never run `docker compose up` standalone
from `infra/monitoring/`.**

```bash

# Correct — canonical stack (project agentic-e2e, network agentic-e2e_monitoring)
docker compose --env-file infra/openproject/variables.env \
  --env-file infra/monitoring/variables.env \
  -f infra/compose.yml --project-directory infra up -d health-probe

# Wrong — spawns a stray `monitoring` project on a separate `monitoring_monitoring` network
cd infra/monitoring && docker compose up -d health-probe

```

**Why it matters (incident-driven):** running the compose file standalone
creates a second compose project (`monitoring`) with its own network. The
`health-probe` container then lands on `monitoring_monitoring` instead of
the canonical `agentic-e2e_monitoring`, so Grafana can no longer resolve
`health-probe:8090` (the Service Health panel shows "No data"/400) and the
probe can no longer reach the kind control-plane node
(`sdd-cluster-control-plane`).

Two things make this durable (see the comments in `infra/monitoring/compose.yml`):

1. The `monitoring` network is pinned to `agentic-e2e_monitoring`, so the
   probe joins the canonical network even when the file is read standalone —
   but the compose **project** must still be `agentic-e2e` so all containers
   are lifecycle-managed by the one canonical stack. `docker compose ls`
   should show a single `agentic-e2e` project; a second `monitoring`
   project indicates a stray standalone run.
1. The `health-probe` service has `restart: unless-stopped` plus a
   healthcheck (`GET /health` via stdlib urllib, no curl in the alpine
   image). A silent process exit is auto-restarted; a hung-but-alive probe
   shows `unhealthy` in `docker ps`/`docker inspect` instead of dying
   silently. (Docker has no native restart-on-unhealthy, and the `kill -9 1`
   self-terminate trick is ineffective on Docker Desktop/WSL2 — the
   healthcheck is observability, the restart policy covers exits.)

The health-probe is the data source for the Service Health panel: it polls
each environment's NodePort from inside the cluster network and serves the
JSON Grafana consumes.

### Dashboard Provisioning

Dashboards are **provisioned from disk** — Grafana watches the `infra/monitoring/grafana/dashboards/` directory and
auto-loads any JSON file dropped there:

```bash
# Architecture
infra/monitoring/grafana/
├── compose.yml                    # Grafana service definition
├── variables.env                  # Grafana env vars
├── variables.env.example          # Template
├── provisioning/
│   ├── dashboards/dashboards.yml  # Dashboard provider config
│   ├── datasources/
│   │   └── infinity-health.yml    # Infinity datasource for health checks
│   └── alerting/
│       └── health-alerts.yml      # Alert rules (disabled by default)
└── dashboards/
    └── health-board.json          # 🚀 SDD Service Status dashboard
```

**Critical rule — version bump on every change:** Grafana provisioning only overwrites a dashboard when the file version
is **higher** than the DB version. If you edit `health-board.json`, always increment the `"version": N` field.
Otherwise, changes won't take effect after restart.

### Grafana Dashboard Best Practices

Based on the official Grafana skills (`dashboarding`, `grafana-oss`, `grafana-dashboards`):

1. **Add `description` fields** to every panel — this shows as a tooltip on the panel title's ℹ️ icon. Use it to explain
what the panel shows.
2. **Set `graphTooltip: 1`** — enables shared crosshair tooltip across all panels.
3. **Configure `timepicker`** — set `refresh_intervals` and `time_options` for better UX.
4. **Set column widths** on table panels via `fieldConfig.overrides` → `custom.width`.
5. **Use `sortBy`** on tables for consistent row ordering.
6. **Add dashboard-level `links`** — creates a navigation dropdown in the top-left corner.
7. **Use meaningful panel titles** — prefixed with emojis for quick visual scanning.

### Infinity Datasource — Known Issues

The Infinity datasource plugin (`yesoreyeram-infinity-datasource`) is used for health check panels. It has two known
frontend bugs that cause JS console errors:

#### Issue 1: `TypeError: Cannot read properties of undefined (reading 'method')`

**Cause:** Using `source: "url"` with `parser: "backend"` + `format: "table"` on simple JSON responses like
`{"status":"ok"}`. The Infinity plugin tries to parse the single-object response as an array and crashes.

**Fix:** Don't use stat or table panels with `source: "url"`. Instead:

- Use **text (markdown) panels** to display health status manually.
- Use **`source: "inline"`** for table panels that need dynamic data (the inline parser doesn't trigger this bug).

#### Issue 2: `TypeError: Cannot read properties of undefined (reading 'Not deployed')`

**Cause:** Value mappings on Infinity-driven table columns with `"color": "green"` or `"color": "text"` properties
inside the mapping object. The Infinity frontend code crashes when processing inline color values.

**Fix:** Remove the `"color"` property from inside mapping objects. Use text-only transformations:

```json
// ❌ BAD — crashes Infinity
"mappings": [{
  "type": "value",
  "value": "Active",
  "text": "✅ Active",
  "color": "green"    // <-- crashes Infinity
}]

// ✅ GOOD — works fine
"mappings": [{
  "type": "value",
  "value": "Active",
  "text": "✅ Active"   // no color property
}]
```

#### What works reliably with Infinity

| Source type | Parser | Panel types | Status |
|---|---|---|---|
| **`inline`** | `backend` | `table` | ✅ Works perfectly |
| **`inline`** | `backend` | `stat` | ✅ Works perfectly |
| **`url`** | `backend` | `table` | ❌ JS crash (#1) |
| **`url`** | `backend` | `stat` | ❌ JS crash (#1) |
| **`url`** | `default` | `stat` | ❌ JS crash (#1) |
| — (no datasource) | — | **`text`** (markdown) | ✅ Always works |

### Dashboard JSON Layout Reference

This project uses `schemaVersion: 39` which uses a **24-column grid** (`w: 24` = full width). Key `gridPos` properties:

- `w: 24` — Full width
- `w: 12` — Half width (side-by-side panels)
- `w: 8` — One-third width
- `h: N` — Height in grid rows (~30px per row at 100% zoom)

On a 1080p monitor at 100% zoom, ~22 grid rows are visible without scrolling. For a "one-glance" dashboard, keep total
height ≤ 22 rows.

#### Grafana Sidebar Width

The Grafana left navigation sidebar takes ~250px when expanded (showing text labels). This can make panels appear to
occupy only half the screen. **Fix:** Collapse the sidebar by clicking the ☰ hamburger icon at the top-left. The sidebar
state is saved per-user in browser local storage.

### Health Alerts

Alert rules are currently **disabled** (empty `rules: []` in `health-alerts.yml`). To enable:

1. Deploy apps to K8s via the CI pipeline
2. Discover nodePorts: `python -m tools.sdd_cli environment-lab setup-k8s-access`
3. Copy the template blocks from `health-alerts.yml` into the `rules` array
4. Update `NODE_PORT` placeholders with actual ports
5. Restart Grafana: `docker restart agentic-grafana`

### Environment URLs

CI publishes `app/latest/env-urls-{env}.json` to Nexus after each deploy. The Grafana health dashboard can reference
these via the Infinity datasource (using `source: "inline"` to avoid the URL bug).

## Adding a New App

1. Add an entry to `infra/deployment/apps.json` with `appId`, `projectPath`, `role`, `healthPath`
2. Run `scaffold-k8s` to generate the Dockerfile and K8s manifests
3. Build locally: `docker build -f {projectPath}/Dockerfile {projectPath}`
4. Open a PR to `dev` and merge it — the CI pipeline builds and deploys automatically on the PR merge (direct pushes
to `dev` never deploy).

## Known Limitations

- **Single-node K8s**: kind creates a single-node cluster — no pod anti-affinity, no multi-AZ. Fine for DEV/QA; PROD
would need a proper cluster.
- **kind cluster not persistent**: If Docker is restarted, the kind cluster goes away. Re-run `setup-kind-cluster` to
recreate it.
- **Fixed nodePorts**: NodePorts are fixed per environment (canonical in `infra/deployment/ports.json`); host access
goes through kind `extraPortMappings`. Run `setup-k8s-access` after each deploy to confirm URLs.
- **Runner mounts**: The Gitea Actions runner needs host Docker socket and kubeconfig mounted.
- **Single-app manifests**: `scaffold-k8s` generates manifests for the first app in `apps.json` only. Extend manually
for multi-app.
- **AI-driven Dockerfiles**: `scaffold-k8s` no longer generates stack-specific Dockerfiles/nginx — those are delegated
to the `dev-flow-scaffold-project` skill, which resolves what to generate from the selected stack (never a fixed
template list). `scaffold-k8s` only emits deterministic Kustomize manifests.
