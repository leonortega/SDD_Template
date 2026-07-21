---
name: dev-ops-configure-k8s
description: Scaffold and configure Kubernetes deployment for all apps in the project. K8s is the single deployment target — no adapter pattern, no alternate providers.
---

<!-- TIER 3: STAGE-SPECIFIC - K8s deployment configuration skill -->

# Configure K8s Deployment

## Overview

Kubernetes is the **only** deployment target for this project. No adapter pattern, no alternate providers, no docker-compose deployment. Every deployable app gets:
- A production-grade `Dockerfile`
- K8s manifests (Deployment + Service) per environment, using LoadBalancer for local access
- CI workflow that builds Docker images, pushes to Nexus, deploys to K8s, and publishes environment URLs
- Grafana health monitoring pointing to deployed K8s services

## Docker Desktop K8s

The cluster runs on **Docker Desktop's built-in Kubernetes** — a single-node cluster sharing the same Docker daemon. This simplifies local development:

- **Enable K8s in Docker Desktop**: Settings → Kubernetes → Enable Kubernetes → Apply & Restart
- **Images are shared**: Images built with `docker build` are available to the K8s cluster without pushing to a registry (same daemon). Use `imagePullPolicy: IfNotPresent`.
- **kubectl included**: Docker Desktop bundles `kubectl`. Verify: `kubectl cluster-info`
- **host.docker.internal works**: Pods can reach host services (Nexus at `host.docker.internal:8088`, Gitea at `host.docker.internal:3000`) naturally.


### Image Strategy

Two modes — local dev (no registry push) and CI (registry push):

| Mode | Docker Desktop K8s | Image Pull | Registry Needed |
|------|-------------------|------------|----------------|
| Local dev | `docker build -t frontend:latest` | `IfNotPresent` | No |
| CI/Gitea Actions | Build + push to `host.docker.internal:8083/{appId}:{commitSha}` | `IfNotPresent` | Nexus Docker repo |

For local dev, the overlay's `newTag` field is set to `latest` so manually built images are picked up automatically.

Environments use **Kustomize overlays** with a shared base plus environment-specific patches:

```
infra/k8s/
├── base/                  # Shared manifests
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── namespace.yaml
├── overlays/
│   ├── dev/               # DEV environment
│   │   ├── kustomization.yaml
│   │   └── config-patch.yaml
│   ├── qa/                # QA environment
│   │   ├── kustomization.yaml
│   │   └── config-patch.yaml
│   └── prod/              # PROD environment
│       ├── kustomization.yaml
│       └── config-patch.yaml
└── Dockerfile             # Per-app Dockerfile (generated per app)
```

## Container Registry

CI builds push images to a **Nexus Docker repository** (not a raw repository — a Docker hosted repository). For local Docker Desktop K8s, you can skip the registry entirely since images are available from the shared daemon.

Nexus must have:
- A Docker hosted repository (e.g., `sdd-docker`) with `http` connector enabled (default port `8083`)
- Anonymous pull access enabled (or credentials configured via Gitea secrets)

Image naming convention:
```
host.docker.internal:8083/{appId}:{commitSha}    # CI builds (pushed to registry)
{appId}:latest                                      # Local builds (shared daemon)
```

## Prerequisites

Before running this skill:

1. **Project stack must be configured** — Run `configure-dev-environment` first. The skill reads `frontend`/`backend` from `project-profile.local.json`.
2. **Apps must be defined** — `infra/deployment/apps.json` must list every deployable app with `appId`, `projectPath`, `role`, `healthPath`.
3. **CI workflows must exist** — `.gitea/workflows/package-deploy.yml` must already exist (created by `configure-ci-workflows`).
4. **Nexus must be running** with Docker hosted repository configured (or available to create one).
5. **Docker Desktop K8s must be enabled** — Settings → Kubernetes → Enable Kubernetes in Docker Desktop. Verify with `kubectl cluster-info`.


## Configuration

The skill reads configuration from:

| Source | What it provides |
|--------|-----------------|
| Merged project profile (`project-profile.json` + `project-profile.local.json`) | Stack technologies, Nexus provider config |
| `infra/deployment/apps.json` | App topology (appId, role, projectPath, healthPath) |
| `client-tools.local.json → nexus` | Nexus URL, credentials for Docker registry setup |
| User input | K8s cluster context, domain names per environment |

## Shared Context

Before running, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/deployment.md` as the stage-specific doc.

## Workflow

### 1. Read Project Stack And App Topology

Read the merged project profile and `infra/deployment/apps.json` to determine:

- Which apps exist and their roles (`web`, `api`, `admin`)
- Build output directories (`dist/` for React, etc.)
- Health check paths

### 2. Generate Dockerfile Per App

For each app in `apps.json`, generate a `Dockerfile` at the app's project root (e.g., `frontend/Dockerfile`).

**For web apps (React/Vue/Angular):**

```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost/health || exit 1
CMD ["nginx", "-g", "daemon off;"]
```

Also generate `nginx.conf` for web apps:

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }
    location /health {
        return 200 '{"status":"ok"}';
        add_header Content-Type application/json;
    }
}
```

**For API apps (Node/FastAPI/Django/.NET):**

Generate appropriate multi-stage Dockerfile based on the backend stack.

### 3. Generate K8s Base Manifests

Create `infra/k8s/base/` with shared manifests:

**`namespace.yaml`** — One namespace per environment pattern:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: sdd-{environment}
```

**`deployment.yaml`** — Parameterized Deployment:
- `name: {appId}`
- `replicas: 1` (DEV), `2` (QA), `3` (PROD) — configurable via patches
- `image: host.docker.internal:8083/{appId}:{commitSha}` (placeholder)
- `imagePullPolicy: IfNotPresent` (all environments — shares Docker daemon)
- `livenessProbe` + `readinessProbe` pointing to `{healthPath}`
- Resource limits/requests (defaults set in base, overridden per environment)

**`service.yaml`** — LoadBalancer Service:
- `type: LoadBalancer` — Docker Desktop assigns a localhost port automatically
- `port: 80`
- `targetPort: 80` (or app-specific port)

**`kustomization.yaml`** — Base kustomization listing all resources:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - deployment.yaml
  - service.yaml
commonLabels:
  app.kubernetes.io/managed-by: sdd-cli
```

### 4. Generate K8s Environment Overlays

For each environment (dev, qa, prod), create `infra/k8s/overlays/{env}/`:

**`kustomization.yaml`** — Environment-specific overlay:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: sdd-{env}
resources:
  - ../../base
patches:
  - path: config-patch.yaml
images:
  - name: host.docker.internal:8083/{appId}
    newTag: latest
```

**`config-patch.yaml`** — Environment-specific config (replicas, resources, env vars):
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {appId}
spec:
  replicas: 1  # dev=1, qa=2, prod=3
  template:
    spec:
      containers:
        - name: {appId}
          env:
            - name: ENVIRONMENT
              value: {env}
```

### 5. Configure Nexus Docker Registry

Nexus must have a Docker hosted repository for image storage:

```bash
# Create Docker hosted repository in Nexus
curl --user "${NEXUS_ADMIN:?}:${NEXUS_PASS:?}" -X POST \  # gitleaks:allow
  http://localhost:8088/service/rest/v1/repositories/docker/hosted \
  -H "Content-Type: application/json" \
  -d '{
    "name": "sdd-docker",
    "online": true,
    "storage": {
      "blobStoreName": "default",
      "strictContentTypeValidation": true,
      "writePolicy": "ALLOW_ONCE"
    },
    "docker": {
      "httpPort": 8083,
      "forceBasicAuth": true
    }
  }'
```

Use the `scaffold-k8s` CLI command for this:
```bash
python -m tools.sdd_cli environment-lab scaffold-k8s --values-json '{
  "apps": ["frontend"],
  "domain": "sdd.local",
  "nexus-docker-port": 8083
}'
```

### 6. Update CI Workflow For Container Build + Deploy

Modify `.gitea/workflows/package-deploy.yml`:

**Runner-to-K8s connectivity**: The Gitea Actions runner runs in a Docker container, while K8s runs on the host via Docker Desktop. The runner needs access to the host's Docker daemon and kubeconfig. Ensure `infra/gitea/compose.yml` mounts the Docker socket and kubeconfig into the runner container:

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

Without these mounts, the CI workflow's `docker build` and `kubectl apply` won't work — they'd target the runner's isolated environment instead of the host's Docker daemon and K8s cluster.

**Replace the old deploy step** (which ran `node server.mjs` inline) with:

```yaml
      - name: Build and push Docker image
        env:
          NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
          NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
        shell: bash
        run: |
          set -euo pipefail
          COMMIT_SHA=$(git rev-parse HEAD)
          REGISTRY="host.docker.internal:8083"
          
          # Login to Nexus Docker registry
          echo "${NEXUS_PASSWORD}" | docker login "${REGISTRY}" \
            -u "${NEXUS_USERNAME}" --password-stdin
          
          # Build and push each app
          for app_dir in frontend; do
            app_id=$(basename "${app_dir}")
            IMAGE="${REGISTRY}/${app_id}:${COMMIT_SHA}"
            docker build -t "${IMAGE}" -f "${app_dir}/Dockerfile" "${app_dir}"
            docker push "${IMAGE}"
            docker tag "${IMAGE}" "${REGISTRY}/${app_id}:latest"
            docker push "${REGISTRY}/${app_id}:latest"
          done

      - name: Deploy to K8s
        env:
          KUBECONFIG: ${{ secrets.KUBECONFIG }}
        shell: bash
        run: |
          set -euo pipefail
          ENV="dev"
          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            ENV="${{ github.event.inputs.environment }}"
          fi
          
          # Set image tag
          COMMIT_SHA=$(git rev-parse HEAD)
          REGISTRY="host.docker.internal:8083"
          
          cd infra/k8s/overlays/${ENV}
          kustomize edit set image "${REGISTRY}/frontend:${COMMIT_SHA}"
          kustomize build . | kubectl apply -f -
          
          # Wait for rollout
          for app_id in frontend; do
            kubectl -n "sdd-${ENV}" rollout status deployment "${app_id}" --timeout=120s
          done
          
          # Health check
          NAMESPACE="sdd-${ENV}"
          for app_id in frontend; do
            HEALTH_PATH=$(python3 -c "
          import json
          with open('infra/deployment/apps.json') as f:
              apps = json.load(f).get('apps', [])
          for a in apps:
              if a['appId'] == '${app_id}':
                  print(a.get('healthPath', '/health'))
          " 2>/dev/null || echo "/health")
            
            POD=$(kubectl -n "${NAMESPACE}" get pod -l app="${app_id}" -o jsonpath='{.items[0].metadata.name}')
            kubectl -n "${NAMESPACE}" exec "${POD}" -- sh -c \
              "wget -qO- http://localhost${HEALTH_PATH}" | grep '"status":"ok"'
            echo "${app_id} health check PASSED"
          done
```

### 7. Add Gitea Secrets For K8s Access

Ensure these secrets exist in Gitea:

| Secret | Value |
|--------|-------|
| `NEXUS_USERNAME` | Nexus admin username |
| `NEXUS_PASSWORD` | Nexus admin password |
| `KUBECONFIG` | Base64-encoded kubeconfig for the target cluster |

Use the `sync-nexus-secrets` command for Nexus credentials:
```bash
python -m tools.sdd_cli environment-lab sync-nexus-secrets
```

For `KUBECONFIG`, encode and add manually via Gitea UI or API:
```bash
cat ~/.kube/config | base64 -w0
# Then add as KUBECONFIG secret in Gitea repository settings
```

### 8. Validate Deployment

Verify end-to-end:

1. **Docker build works**: `docker build -f frontend/Dockerfile frontend`
2. **Kustomize builds**: `kustomize build infra/k8s/overlays/dev/`
3. **Dry-run apply**: `kustomize build infra/k8s/overlays/dev/ | kubectl apply --dry-run=client -f -`
4. **Trigger CI**: Push to `dev` branch and verify the workflow succeeds

## CLI Commands

Three CLI commands automate the K8s setup process:

### scaffold-k8s

Scaffold Dockerfiles, K8s manifests, and environment overlays:

```bash
python -m tools.sdd_cli environment-lab scaffold-k8s
```

This reads `infra/deployment/apps.json` to determine which apps to scaffold. Validates Docker Desktop K8s as a prerequisite before writing any files.

Dry-run mode:
```bash
python -m tools.sdd_cli environment-lab scaffold-k8s --dry-run true
```

### validate-docker-desktop-k8s

Check that Docker Desktop K8s is enabled and accessible:

```bash
python -m tools.sdd_cli environment-lab validate-docker-desktop-k8s
```

Checks:
- `kubectl` is available
- K8s API server is reachable
- Context is Docker Desktop

### setup-k8s-access

Discover deployed service URLs and suggest port-forward commands:

```bash
python -m tools.sdd_cli environment-lab setup-k8s-access
```

For each app and environment:
- Discovers the LoadBalancer `nodePort` if the service is already deployed
- Shows the direct URL: `http://localhost:{nodePort}/health`
- If not deployed, suggests the `kubectl port-forward` command

## Output

Report:
- Dockerfiles created/updated (path per app)    - K8s base manifests created (`infra/k8s/base/` — no Ingress, uses LoadBalancer for local access)
- K8s environment overlays created (`infra/k8s/overlays/{dev,qa,prod}/`)
- Nexus Docker repository configured (or already exists)
- CI workflow changes applied (diff summary)
- Gitea secrets required and current status
- Environment URLs discovered (via `setup-k8s-access`)
- Next steps for user: add `KUBECONFIG` secret, trigger first build

## Failure Rules

- **No apps in apps.json**: stop and ask the user to define apps first.
- **No project stack configured**: stop and ask the user to run `configure-dev-environment` first.
- **Nexus not reachable**: stop — cannot push images without a registry.
- **Nexus Docker repository creation fails**: stop — images need a Docker hosted repo, not a raw repo.
- **Docker not available locally**: stop — cannot build images without Docker.
- **Docker Desktop K8s not enabled**: stop and ask user to enable Kubernetes in Docker Desktop settings.
- **kubectl not available**: warn but don't stop — CI will use its own kubeconfig or Docker Desktop's bundled kubectl.
- **Kustomize not available**: install via `kubectl kustomize` or standalone binary.
- **Never overwrite existing Dockerfiles or K8s manifests without showing a dry-run diff first.**
- **Never hardcode secrets or tokens into manifest files.**
- **Never store kubeconfig in tracked files — use Gitea secrets.**

### Known Limitations

- **Single-app manifests**: The `scaffold-k8s` CLI generates K8s manifests for the first app in `apps.json` only. For multi-app projects, generate per-app manifests manually or extend the CLI.
- **`npm ci` requirement**: The generated Dockerfile uses `npm ci`, which requires a lockfile (`package-lock.json`). If the project uses `yarn` or lacks a lockfile, update the Dockerfile build step accordingly.
- **Docker Desktop single-node**: The built-in K8s is single-node — no pod anti-affinity, no multi-AZ, no load balancer. Fine for DEV/QA; PROD would need a proper cluster.
- **Runner mounts required**: The Gitea Actions runner container needs `/var/run/docker.sock` and `~/.kube/config` mounted to build images and deploy to Docker Desktop K8s from CI.
