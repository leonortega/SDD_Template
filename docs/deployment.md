# Deployment

## Technology Stack And Tool Set

Kubernetes is the **only** deployment target for this project. The cluster runs on **Docker Desktop's built-in Kubernetes** (single-node, same Docker daemon as the host).

| Layer              | Status                 | Detail                                                                   |
| ------------------ | ---------------------- | ------------------------------------------------------------------------ |
| Deployment target  | Docker Desktop K8s     | Single-node Kubernetes on Docker Desktop                                 |
| Container registry | Nexus (:8083)          | Docker hosted repository for CI-built images                             |
| Artifact storage   | Nexus (:8088)          | Raw hosted repository for build artifacts and manifests                  |
| Environments       | dev, qa, prod          | Three K8s namespaces (sdd-dev, sdd-qa, sdd-prod) with Kustomize overlays |
| CI/CD              | Gitea Actions          | PR validation + package-deploy workflows                                 |
| Observability      | Grafana + Seq + Dozzle | Health dashboards, log search, container monitoring                      |

No app target is currently deployable. Product apps will be added through `infra/deployment/apps.json` when the product stack is defined.

## Architecture Overview

```
text
┌──────────────────────────────────────────────────────────┐
│  Docker Desktop Host                                     │
│                                                          │
│  ┌─ Docker Desktop K8s ───────────────────────────────┐  │
│  │  Namespace: sdd-dev                                 │  │
│  │  ┌──────────────┐    ┌──────────────┐              │  │
│  │  │ Deployment:   │    │ Service:     │              │  │
│  │  │ frontend      │───▶│ frontend     │── LoadBalancer│  │
│  │  │ (nginx:80)    │    │ type:        │── localhost:3xxxx│  │
│  │  └──────────────┘    └──────────────┘              │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ Docker Compose ───────────────────────────────────┐  │
│  │  Gitea :3000 │ Nexus :8088 │ Grafana :3001         │  │
│  │  Nexus Docker Registry :8083                        │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Key Components

| Component                    | Host                   | Port   | Purpose                                    |
| ---------------------------- | ---------------------- | ------ | ------------------------------------------ |
| K8s Cluster (Docker Desktop) | `localhost`            | -      | Runs app Deployments + Services            |
| Nexus Artifacts              | `host.docker.internal` | `8088` | Stores build artifacts + env URL manifests |
| Nexus Docker Registry        | `host.docker.internal` | `8083` | Stores container images (CI pushes here)   |
| Gitea                        | `host.docker.internal` | `3000` | Source control + CI runner                 |
| Grafana                      | `localhost`            | `3001` | Health monitoring dashboards               |

## Environment Model

Three environments, each a separate K8s namespace:

| Environment | Namespace  | Replicas | Trigger                           |
| ----------- | ---------- | -------- | --------------------------------- |
| **dev**     | `sdd-dev`  | 1        | Push to `dev` branch              |
| **qa**      | `sdd-qa`   | 2        | `workflow_dispatch` with env=qa   |
| **prod**    | `sdd-prod` | 3        | `workflow_dispatch` with env=prod |

Each environment uses a **Kustomize overlay** that inherits from a shared base:

```
infra/k8s/
├── base/                        # Shared manifests
│   ├── kustomization.yaml
│   ├── deployment.yaml          # Deployment with ContainerPort 80
│   ├── service.yaml             # LoadBalancer type
│   └── namespace.yaml           # sdd-{ENV}
├── overlays/
│   ├── dev/
│   │   ├── kustomization.yaml   # images.newTag: latest
│   │   └── config-patch.yaml    # replicas: 1
│   ├── qa/
│   │   ├── kustomization.yaml
│   │   └── config-patch.yaml    # replicas: 2
│   └── prod/
│       ├── kustomization.yaml
│       └── config-patch.yaml    # replicas: 3
└── Dockerfile                   # Per-app multi-stage build
```

### Service Type: LoadBalancer

Services use `type: LoadBalancer`. On Docker Desktop K8s, this assigns a **nodePort** in the `30000-32767` range that is immediately accessible at `localhost:{nodePort}`.

**No Ingress controller is needed** — the LoadBalancer exposes each service directly on localhost.

## CLI Commands

Three `environment-lab` commands manage the K8s deployment setup:

### scaffold-k8s

Generate Dockerfiles, K8s manifests, and environment overlays. Reads `infra/deployment/apps.json` to determine which apps to scaffold. Validates Docker Desktop K8s as a prerequisite.

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
- `infra/k8s/base/` — namespace, deployment, service, kustomization
- `infra/k8s/overlays/{dev,qa,prod}/` — env-specific patches

### validate-docker-desktop-k8s

Check that Docker Desktop K8s is enabled and reachable:

```bash
python -m tools.sdd_cli environment-lab validate-docker-desktop-k8s
```

Validates:

- `kubectl` CLI is available
- K8s API server responds
- Current context is Docker Desktop

### setup-k8s-access

Discover deployed service URLs and suggest port-forward commands:

```bash
python -m tools.sdd_cli environment-lab setup-k8s-access
```

For each app and environment, it either:

- **Discovers** the LoadBalancer nodePort and shows the direct URL
- **Suggests** a `kubectl port-forward` command if not yet deployed

## CI Pipeline

The CI workflow (`.gitea/workflows/package-deploy.yml`) runs on push to `dev` or `workflow_dispatch`:

```
Checkout → Determine Env → Build Docker Images → Deploy to K8s → Discover URLs → Upload to Nexus
```

### Step Details

**1. Checkout** — Clones the commit using Gitea API token for auth.

**2. Determine Environment** — `dev` on push, or user-selected env on workflow_dispatch.

**3. Build and Push Docker Images** — For each app in `apps.json`:

- Logs into Nexus Docker registry (`host.docker.internal:8083`)
- Runs `docker build` using the app's `Dockerfile`
- Pushes `{appId}:{commitSha}` and `{appId}:latest` tags

**4. Deploy to K8s** — For the target environment:

- Reads `apps.json` to get app list
- Runs `kustomize edit set image` to set the commit SHA tag
- Runs `kustomize build . | kubectl apply -f -`
- Waits for rollout of each deployment

**5. Discover Environment URLs** — Single Python script:

- Calls `kubectl get svc -o jsonpath='{.spec.ports[0].nodePort}'` for each app
- Writes `app/{commitSha}/env-urls.json` with discovered URLs

**6. Upload to Nexus** — Uploads artifacts including:

- `app/{commitSha}/env-urls.json`
- `app/latest/env-urls-{env}.json` (latest pointer, overwritten each deploy)

### Runner Requirements

The Gitea Actions runner container needs access to the host's Docker daemon and kubeconfig. Ensure `infra/gitea/compose.yml` mounts these:

```yaml
services:
  runner:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ~/.kube/config:/home/runner/.kube/config:ro
    environment:
      - KUBECONFIG=/home/runner/.kube/config
      - DOCKER_HOST=unix:///var/run/docker.sock
```

## Prerequisites

Before any deployment:

1. **Docker Desktop K8s enabled** — Settings → Kubernetes → Enable Kubernetes → Apply & Restart
2. **Apps defined** — `infra/deployment/apps.json` must list every deployable app
3. **K8s manifests scaffolded** — Run `scaffold-k8s` to generate Dockerfiles + manifests
4. **Nexus Docker registry configured** — Docker hosted repository on port `8083` (created by `setup-lab`)
5. **Gitea secrets** — `NEXUS_USERNAME`, `NEXUS_PASSWORD`, `KUBECONFIG` (base64 of `~/.kube/config`)
6. **Runner mounts** — Docker socket and kubeconfig mounted into the runner container

### Image Strategy

| Mode      | Build Command                               | Registry             | Image Tag             |
| --------- | ------------------------------------------- | -------------------- | --------------------- |
| Local dev | `docker build -t frontend:latest frontend/` | None (shared daemon) | `frontend:latest`     |
| CI build  | `docker build` + `docker push`              | Nexus :8083          | `{appId}:{commitSha}` |

## Accessing Deployed Apps

### Via LoadBalancer (direct)

After the CI pipeline deploys, each service gets a nodePort. Discover it:

```bash
python -m tools.sdd_cli environment-lab setup-k8s-access
```

Output:

```
DEV frontend accessible at: http://localhost:32768/health
DEV openproject accessible at: http://localhost:32769/health
```

### Via Port-Forward (manual)

If the service isn't deployed yet, the CLI suggests the command:

```bash
kubectl port-forward -n sdd-dev svc/frontend 8081:80
# Then visit http://localhost:8081
```

## Grafana Monitoring

Grafana runs at `http://localhost:3001` (provisioned via Docker Compose).

- **Datasource**: Infinity datasource (`infinity-health`) allows `http://localhost:*` and `http://host.docker.internal:*`
- **Health alerts**: Currently disabled (empty `rules: []`). After deployment, discover URLs via `setup-k8s-access` and add alert rules using the template in `infra/monitoring/grafana/provisioning/alerting/health-alerts.yml`
- **Environment URLs**: CI publishes `app/latest/env-urls-{env}.json` to Nexus, which can be queried via the infinity datasource

## Adding a New App

1. Add an entry to `infra/deployment/apps.json` with `appId`, `projectPath`, `role`, `healthPath`
2. Run `scaffold-k8s` to generate the Dockerfile and K8s manifests
3. Build locally: `docker build -f {projectPath}/Dockerfile {projectPath}`
4. Commit and push — the CI pipeline will build and deploy automatically

## Known Limitations

- **Single-node K8s**: Docker Desktop's built-in K8s is single-node — no pod anti-affinity, no multi-AZ. Fine for DEV/QA; PROD would need a proper cluster.
- **Dynamic nodePorts**: LoadBalancer ports change on service recreation. Run `setup-k8s-access` after each deploy to discover current URLs.
- **Runner mounts**: The Gitea Actions runner needs host Docker socket and kubeconfig mounted.
- **Single-app manifests**: `scaffold-k8s` generates manifests for the first app in `apps.json` only. Extend manually for multi-app.
- **`npm ci` assumption**: Generated Dockerfiles use `npm ci` which requires a lockfile.
