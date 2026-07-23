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

| Mode             | Docker Desktop K8s                                              | Image Pull     | Registry Needed   |
| ---------------- | --------------------------------------------------------------- | -------------- | ----------------- |
| Local dev        | `docker build -t frontend:latest`                               | `IfNotPresent` | No                |
| CI/Gitea Actions | Build + push to `host.docker.internal:5001/{appId}:{commitSha}` | `IfNotPresent` | Nexus Docker repo |

For local dev, images built with `docker build` are available to the K8s cluster without pushing to a registry (same daemon).

Environments use a **single envsubst manifest** (`infra/k8s/deploy.yaml`) with placeholders for `${ENV}`, `${REPLICAS}`, `${REGISTRY}`, and `${COMMIT_SHA}`:

```
text
infra/k8s/
├── deploy.yaml              # Single manifest: Namespace + Deployment + Service
│                             # Placeholders: ENV, REPLICAS, REGISTRY, COMMIT_SHA
└── ...
```

## Container Registry

CI builds push images to a **Nexus Docker repository** (not a raw repository — a Docker hosted repository). For local Docker Desktop K8s, you can skip the registry entirely since images are available from the shared daemon.

Nexus must have:

- A Docker hosted repository (e.g., `sdd-docker`) with `http` connector enabled (port `5001`)
- Anonymous pull access enabled (or credentials configured via Gitea secrets)

Image naming convention:

```
host.docker.internal:5001/{appId}:{commitSha}    # CI builds (pushed to registry)
{appId}:latest                                      # Local builds (shared daemon)
```

### Docker Desktop K8s Registry Mirror Workaround

Docker Desktop's built-in K8s has a `registry-mirror:1273` that intercepts ALL image pulls and returns HTTP 500 for custom registries. This causes `ErrImagePull` or rollout timeouts even when the registry is reachable from the CI container.

**Avoid this by using local-only image references in the K8s manifest:**

1. In the CI build step, tag the image locally with a bare name:

   ```bash
   docker build -t "ci-build:${COMMIT_SHA}" .
   docker tag "ci-build:${COMMIT_SHA}" "${app_id}:${COMMIT_SHA}"
   ```

2. In `deploy.yaml`, use the local-only reference with `IfNotPresent`:

   ```yaml
   image: sdd-test:${COMMIT_SHA}
   imagePullPolicy: IfNotPresent
   ```

3. Push to Nexus separately (for artifact storage), but the K8s manifest never references the registry hostname.

4. **K8s node communication via Docker Desktop VM:**
   - Image registry: `host.docker.internal:5001` (container → host-published port)
   - K8s API: `host.docker.internal:55353` (container → host-published port)
   - Both use host-published ports, not Docker Compose service names (job containers don't inherit Compose network when `container.volumes` is set)

## Prerequisites

Before running this skill:

1. **Project stack must be configured** — Run `configure-dev-environment` first. The skill reads `frontend`/`backend` from `project-profile.local.json`.
2. **Apps must be defined** — `infra/deployment/apps.json` must list every deployable app with `appId`, `projectPath`, `role`, `healthPath`.
3. **CI workflows must exist** — `.gitea/workflows/package-deploy.yml` must already exist (created by `configure-ci-workflows`).
4. **Nexus must be running** with Docker hosted repository configured (or available to create one).
5. **Docker Desktop K8s must be enabled** — Settings → Kubernetes → Enable Kubernetes in Docker Desktop. Verify with `kubectl cluster-info`.

## Configuration

The skill reads configuration from:

| Source                                                                         | What it provides                                    |
| ------------------------------------------------------------------------------ | --------------------------------------------------- |
| Merged project profile (`project-profile.json` + `project-profile.local.json`) | Stack technologies, Nexus provider config           |
| `infra/deployment/apps.json`                                                   | App topology (appId, role, projectPath, healthPath) |
| `client-tools.local.json → nexus`                                              | Nexus URL, credentials for Docker registry setup    |
| User input                                                                     | K8s cluster context, domain names per environment   |

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

### 3. Generate K8s Manifest

Create `infra/k8s/deploy.yaml` — a single envsubst-ready manifest:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: sdd-${ENV}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: { appId }
  namespace: sdd-${ENV}
spec:
  replicas: ${REPLICAS}
  selector:
    matchLabels:
      app: { appId }
  template:
    metadata:
      labels:
        app: { appId }
    spec:
      containers:
        - name: { appId }
          image: ${REGISTRY}/{appId}:${COMMIT_SHA}
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 80
          env:
            - name: ENVIRONMENT
              value: "${ENV}"
          livenessProbe:
            httpGet:
              path: { healthPath }
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: { healthPath }
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "256Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: { appId }
  namespace: sdd-${ENV}
spec:
  type: LoadBalancer
  selector:
    app: { appId }
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
```

Deploy with: `ENV=dev REPLICAS=1 REGISTRY=host.docker.internal:8083 COMMIT_SHA=latest envsubst < infra/k8s/deploy.yaml | kubectl apply -f -`

### 4. Skip Kustomize

No Kustomize overlays needed. The single `deploy.yaml` with envsubst replaces the base/overlay pattern entirely.

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
      "httpPort": 5001,
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

**Runner-to-K8s connectivity**: The Gitea Actions runner runs in a Docker container, while K8s runs on the host via Docker Desktop. The runner needs access to the host's Docker daemon. Ensure `infra/gitea/compose.yml` mounts the Docker socket:

```yaml
services:
  runner:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DOCKER_HOST=unix:///var/run/docker.sock
```

Without this mount, the CI workflow's `docker build` won't work — it'd target the runner's isolated environment instead of the host's Docker daemon.

**Replace the old deploy step** with:

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

    echo "${NEXUS_PASSWORD}" | docker login "${REGISTRY}" \
      -u "${NEXUS_USERNAME}" --password-stdin

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
    COMMIT_SHA: ${{ steps.checkout.outputs.COMMIT_SHA }}
    NEXUS_DOCKER_REGISTRY: ${{ secrets.NEXUS_DOCKER_REGISTRY }}
    ENV: ${{ steps.env.outputs.ENV }}
  shell: bash
  run: |
    set -euo pipefail
    REGISTRY="${NEXUS_DOCKER_REGISTRY:-host.docker.internal:8083}"
    REPLICAS=$(case "${ENV}" in dev) echo 1;; qa) echo 2;; prod) echo 3;; *) echo 1;; esac)

    export ENV REGISTRY COMMIT_SHA REPLICAS
    envsubst < infra/k8s/deploy.yaml | kubectl apply -f -

    kubectl -n "sdd-${ENV}" rollout status deployment/openproject --timeout=120s
```

### 7. Add Gitea Secrets For K8s Access

Ensure these secrets exist in Gitea:

| Secret           | Value                |
| ---------------- | -------------------- |
| `NEXUS_USERNAME` | Nexus admin username |
| `NEXUS_PASSWORD` | Nexus admin password |

Use the `sync-nexus-secrets` command for Nexus credentials:

```bash
python -m tools.sdd_cli environment-lab sync-nexus-secrets
```

### 8. Validate Deployment

Verify end-to-end:

1. **Docker build works**: `docker build -f frontend/Dockerfile frontend`
2. **Envsubst renders**: `ENV=dev REPLICAS=1 REGISTRY=host.docker.internal:8083 COMMIT_SHA=test envsubst < infra/k8s/deploy.yaml`
3. **Dry-run apply**: `ENV=dev REPLICAS=1 REGISTRY=host.docker.internal:8083 COMMIT_SHA=test envsubst < infra/k8s/deploy.yaml | kubectl apply --dry-run=client -f -`
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

- Dockerfiles created/updated (path per app)
- K8s manifest created (`infra/k8s/deploy.yaml` — envsubst: ENV, REPLICAS, REGISTRY, COMMIT_SHA)
- Nexus Docker repository configured (or already exists)
- CI workflow changes applied (diff summary)
- Gitea secrets required and current status
- Environment URLs discovered (via `setup-k8s-access`)
- Next steps for user: trigger first build

## Failure Rules

- **No apps in apps.json**: stop and ask the user to define apps first.
- **No project stack configured**: stop and ask the user to run `configure-dev-environment` first.
- **Nexus not reachable**: stop — cannot push images without a registry.
- **Nexus Docker repository creation fails**: stop — images need a Docker hosted repo, not a raw repo.
- **Docker not available locally**: stop — cannot build images without Docker.
- **Docker Desktop K8s not enabled**: stop and ask user to enable Kubernetes in Docker Desktop settings.
- **kubectl not available**: warn but don't stop — CI will use Docker Desktop's bundled kubectl.
- **Never overwrite existing Dockerfiles or K8s manifests without showing a dry-run diff first.**
- **Never hardcode secrets or tokens into manifest files.**

### Known Limitations

- **Single-app manifests**: The `scaffold-k8s` CLI generates K8s manifests for the first app in `apps.json` only. For multi-app projects, generate per-app manifests manually or extend the CLI.
- **`npm ci` requirement**: The generated Dockerfile uses `npm ci`, which requires a lockfile (`package-lock.json`). If the project uses `yarn` or lacks a lockfile, update the Dockerfile build step accordingly.
- **Docker Desktop single-node**: The built-in K8s is single-node — no pod anti-affinity, no multi-AZ, no load balancer. Fine for DEV/QA; PROD would need a proper cluster.
- **Runner mounts required**: The Gitea Actions runner container needs `/var/run/docker.sock` mounted to build images from CI.
