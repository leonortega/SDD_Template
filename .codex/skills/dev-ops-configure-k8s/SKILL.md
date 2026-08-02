---
name: dev-ops-configure-k8s
license: MIT
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

## Docker Desktop K8s (deprecated)

> **Preferred approach**: Use `kind` instead. The `setup-lab` CLI now installs kind and creates a cluster automatically. Docker Desktop K8s is preserved as a fallback for environments where kind cannot be installed.

The cluster runs on **Docker Desktop's built-in Kubernetes** — a single-node cluster sharing the same Docker daemon. This simplifies local development:

- **Enable K8s in Docker Desktop**: Settings → Kubernetes → Enable Kubernetes → Apply & Restart
- **Images are shared**: Images built with `docker build` are available to the K8s cluster without pushing to a registry (same daemon). Use `imagePullPolicy: IfNotPresent`.
- **kubectl included**: Docker Desktop bundles `kubectl`. Verify: `kubectl cluster-info`
- **host.docker.internal works**: Pods can reach host services (Nexus at `host.docker.internal:8088`, Gitea at `host.docker.internal:3000`) naturally.

### Image Strategy

Two modes — local dev (no registry push) and CI (registry push + kind load):

| Mode             | Cluster Provider                                          | Image Delivery                                    | Registry Needed   |
| ---------------- | --------------------------------------------------------- | ------------------------------------------------- | ----------------- |
| Local dev        | kind or Docker Desktop K8s                                | `docker build -t frontend:latest` + `kind load docker-image` | No |
| CI/Gitea Actions | kind (preferred) or Docker Desktop K8s                    | Build + push to `host.docker.internal:5001/{appId}:{commitSha}` + `kind load docker-image` | Nexus Docker repo |

**Why `kind load docker-image` is required:** kind runs each cluster node as a Docker container with its own containerd instance. Images on the host Docker daemon are NOT visible to kind's nodes. After building an image via `docker build`, you must explicitly load it into kind:

```bash
docker build -t host.docker.internal:5001/frontend:latest .
kind load docker-image --name sdd-cluster host.docker.internal:5001/frontend:latest
```

The CI workflow does this automatically after each `docker build` step.

Environments use a **Kustomize overlay structure** with per-app manifests in `infra/k8s/base/` and environment-specific image tags in `infra/k8s/overlays/{env}/`:

```
text
infra/k8s/
├── base/
│   ├── kustomization.yaml              # References all apps from apps.json
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml
│   ├── backend-deployment.yaml
│   └── backend-service.yaml
├── overlays/
│   ├── dev/kustomization.yaml          # namespace: sdd-dev, image tags
│   ├── qa/kustomization.yaml
│   └── prod/kustomization.yaml
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
5. **K8s cluster must be available** — Run `python -m tools.sdd_cli environment-lab setup-kind-cluster` to create a kind cluster, or enable Kubernetes in Docker Desktop. Verify with `kubectl cluster-info`.

## Configuration

The skill reads configuration from:

| Source                                                                         | What it provides                                    |
| ------------------------------------------------------------------------------ | --------------------------------------------------- |
| Merged project profile (`project-profile.json` + `project-profile.local.json`) | Stack technologies, Nexus provider config           |
| `infra/deployment/apps.json`                                                   | App topology (appId, role, projectPath, healthPath) |
| `client-tools.local.json → nexus`                                              | Nexus URL, credentials for Docker registry setup    |
| User input                                                                     | K8s cluster context, domain names per environment   |

## Shared Context

Before running, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/delivery-contract.md`, and `docs/conventions/context-management.md`, with `docs/architecture/deployment.md` as the stage-specific doc. Confirm the active ticket and the deployment lane before changing manifests.

## Workflow

### 1. Read Project Stack And App Topology

Read the merged project profile and `infra/deployment/apps.json` to determine:

- Which apps exist and their roles (`web`, `api`, `admin`)
- Build output directories (`dist/` for React, etc.)
- Health check paths

### 2. Generate Dockerfile Per App

For each app in `apps.json`, generate a `Dockerfile` at the app's project root (e.g., `frontend/Dockerfile`).

**AI-driven (no fixed template list):** Dockerfile/nginx.conf/.dockerignore generation is delegated to the `dev-flow-scaffold-project` skill, which reads `project-profile.local.json → stack.frontend` and resolves the correct Dockerfile for the actual stack. Use the JS/TS multi-stage node→nginx template below when the frontend is JS/TS (React/Vue/Angular/Svelte), a .NET `dotnet publish` Dockerfile for ASP.NET/Blazor, and the equivalent template for any other runtime — never assume a stack.

**For JS/TS web apps (React/Vue/Angular):**

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

**⚠️ Critical — add runtime DNS resolver for backend upstream.**

Without the resolver and variable `proxy_pass`, nginx resolves the backend hostname **at config load time**. If the backend service DNS entry hasn't propagated yet (e.g. first deploy to a new namespace), nginx fails to start — causing **CrashLoopBackOff**. Always include:

- `resolver kube-dns.kube-system.svc.cluster.local valid=10s;` in the `server` block
- `set $backend_upstream http://backend:5000;` and `proxy_pass $backend_upstream;` — using a variable forces nginx to resolve the hostname at runtime via the resolver, not at startup

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Resolver for dynamic DNS resolution of upstream services.
    # Prevents CrashLoopBackOff when the backend service DNS entry
    # hasn't propagated yet at pod startup time.
    resolver kube-dns.kube-system.svc.cluster.local valid=10s;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Use a variable in proxy_pass so nginx resolves the backend
    # hostname at runtime (via the resolver) instead of at startup.
    # Without this, nginx fails to start if 'backend' isn't resolvable
    # immediately (e.g. on first deploy to a new namespace).
    location /api/ {
        set $backend_upstream http://backend:5000;
        proxy_pass $backend_upstream;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /health {
        return 200 '{"status":"ok"}';
        add_header Content-Type application/json;
    }
}
```

**For API apps (Node/FastAPI/Django/.NET):**

Generate an appropriate multi-stage Dockerfile based on the backend stack — read the confirmed backend value from `project-profile.local.json → stack.backend` and pick the matching runtime template (`dotnet publish` for .NET, `pip install + uvicorn` for FastAPI/Django, `npm ci + node` for Node/Express, `go build` for Go). This is the responsibility of the `dev-flow-scaffold-project` skill (AI-driven, no fixed template list). `scaffold-k8s` sets the `PORT` env var for `role == "api"` apps; the Dockerfile decides how to consume it (e.g., `ASPNETCORE_URLS` for .NET). Never assume a stack: if the backend is unknown, ask the user rather than guessing.

### 3. Generate Kustomize Manifests

Run `scaffold-k8s` to generate a complete Kustomize structure matching every app in `apps.json`:

```bash
python -m tools.sdd_cli environment-lab scaffold-k8s
```

This creates:

```
infra/k8s/
├── base/
│   ├── kustomization.yaml          # References all app manifests
│   ├── {appId}-deployment.yaml     # Per app (port 80 for web, 5000 for api)
│   ├── {appId}-service.yaml        # LoadBalancer per app
├── overlays/
│   ├── dev/
│   │   └── kustomization.yaml      # namespace: sdd-dev, image tags
│   ├── qa/
│   │   └── kustomization.yaml
│   └── prod/
│       └── kustomization.yaml
```

**Key design decisions:**

- **Ports by role**: `web` apps use port 80 (nginx), `api` apps use port 5000
- **Health probes always point to `/health`**: Web apps get `/health` via generated `nginx.conf`. API apps must implement a GET `/health` endpoint in their code. This prevents rollout failures where probes point to non-existent endpoints.
- **Image references**: Base manifests use `image: host.docker.internal:5001/{appId}` without tags — overlays set the actual tag via `newTag`
- **API env vars**: `ASPNETCORE_URLS=http://+:5000` is set for `api`-role apps

**⚠️ QA Overlay: Dedicated NodePorts via Service Patch**

The base K8s services use `type: LoadBalancer`, which assigns random high NodePorts. For the QA overlay, you **must** create a `service-patch.yaml` to assign dedicated NodePorts so host port mappings work reliably without port conflicts between DEV and QA:

```yaml
# infra/k8s/overlays/qa/service-patch.yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend
spec:
  ports:
    - protocol: TCP
      port: 80
      targetPort: 80
      nodePort: 30081          # QA frontend NodePort
---
apiVersion: v1
kind: Service
metadata:
  name: backend
spec:
  ports:
    - protocol: TCP
      port: 5000
      targetPort: 5000
      nodePort: 30501          # QA backend NodePort
```

Then reference it in the QA overlay's `kustomization.yaml`:
```yaml
patches:
  - path: service-patch.yaml
```

The kind cluster's `extraPortMappings` in `infra/k8s/kind-config.yaml` maps these NodePorts to host ports:
- **30081 → 8082** (QA frontend)
- **30501 → 5003** (QA backend)

See the kind-config section below for the full mapping.

**⚠️ Critical: K8s manifests must match apps.json**

The `scaffold-k8s` command generates one Deployment + Service per app in `apps.json`. If you add or remove apps, re-run `scaffold-k8s` to keep manifests in sync. The CI workflow reads `apps.json` and uses `kustomize edit set image` to tag each app's image — if a manifest is missing for an app, the image tag is silently ignored and the app won't be deployed.

**Example generated deployment (web app):**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
        - name: frontend
          image: host.docker.internal:5001/frontend
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 80
          livenessProbe:
            httpGet:
              path: /health
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
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
```

### 4. Deploy Via Kustomize

Deploy using kustomize overlays (the CI workflow does this automatically):

```bash
cd infra/k8s/overlays/dev
kustomize build . | kubectl apply -f -
kubectl -n sdd-dev rollout status deployment/frontend --timeout=120s
```

**How the CI workflow sets image tags:**

The CI workflow reads `apps.json` and runs `kustomize edit set image ${registry}/${appId}:${commitSha}` for each app. This updates the overlay's `images` entries with the actual commit SHA, then `kustomize build` produces manifests with the correct image tags.

```bash
# Example: what the CI does per app
kustomize edit set image host.docker.internal:5001/frontend:abc123def
kustomize build . | kubectl apply -f -
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
      "httpPort": 5001,
      "forceBasicAuth": true
    }
  }'
```

Use the `provision-nexus-docker-registry` CLI command for this (called automatically by `setup-lab`).

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

The CI workflow (`.gitea/workflows/package-deploy.yml`) handles build + deploy using the current approach:

1. **Build and push**: Reads `apps.json`, builds each app with `docker build`, pushes to registry, then loads images into kind via `kind load docker-image --name sdd-cluster`
2. **Deploy**: Uses `kustomize edit set image` to tag each app with the commit SHA, then `kustomize build . | kubectl apply -f -`
3. **Rollout**: Waits for each deployment to become ready with `kubectl rollout status`

See the actual `.gitea/workflows/package-deploy.yml` for the full implementation.

**Key patterns in the CI workflow:**

- `kind load docker-image` is called after each image build — kind's containerd is separate from the host Docker daemon, so images must be explicitly loaded
- `kustomize edit set image` updates the overlay's image entries; the base kustomization references all apps from `apps.json`
- The CI container runs with `--user root` and `--add-host host.docker.internal:host-gateway` for Docker socket access and hostname resolution

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
2. **Kustomize build works**: `cd infra/k8s/overlays/dev && kustomize build . | kubectl apply --dry-run=client -f -`
3. **kind image loaded**: Ensure images are loaded into kind via `kind load docker-image --name sdd-cluster host.docker.internal:5001/frontend:latest`
4. **Trigger CI**: Push to `dev` branch and verify the workflow succeeds

## CLI Commands

Three CLI commands automate the K8s setup process:

### scaffold-k8s

Scaffold Dockerfiles, per-app Kustomize base manifests, and environment overlays.

This is the primary command for generating K8s deployment resources. It reads `infra/deployment/apps.json` and creates:

```
infra/k8s/
├── base/
│   ├── kustomization.yaml          # References all apps
│   ├── {appId}-deployment.yaml     # One per app (port by role)
│   ├── {appId}-service.yaml        # One per app (LoadBalancer)
├── overlays/
│   ├── dev/kustomization.yaml      # namespace: sdd-dev, image tags
│   ├── qa/kustomization.yaml
│   └── prod/kustomization.yaml
```

**⚠️ Always use `/health` as the health probe path.** The scaffold sets `/health` for all apps. Web apps get nginx.conf with a `/health` endpoint. API apps must implement GET `/health` in their code. This prevents rollout failures.

```bash
# Dry-run (preview what would be created)
python -m tools.sdd_cli environment-lab scaffold-k8s --dry-run true

# Real run (creates/updates manifests)
python -m tools.sdd_cli environment-lab scaffold-k8s
```

Validates that `kubectl` is available (via kind or Docker Desktop) before writing files.

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
- nginx.conf created (with /health endpoint for web apps)
- K8s base manifests created (`infra/k8s/base/{appId}-deployment.yaml` and `{appId}-service.yaml` per app)
- K8s overlays created (`infra/k8s/overlays/{env}/kustomization.yaml` for dev, qa, prod)
- Nexus Docker repository configured (or already exists)
- CI workflow changes applied (diff summary)
- Gitea secrets required and current status
- Environment URLs discovered (via `setup-k8s-access`)
- validation results of each deployment check (docker build, kustomize dry-run, rollout)
- handoff point: trigger the first CI build for the active ticket
- Next steps for user: trigger first build

## Failure Rules

- **No apps in apps.json**: stop and ask the user to define apps first.
- **No project stack configured**: stop and ask the user to run `configure-dev-environment` first.
- **Nexus not reachable**: stop — cannot push images without a registry.
- **Nexus Docker repository creation fails**: stop — images need a Docker hosted repo, not a raw repo.
- **Docker not available locally**: stop — cannot build images without Docker.
- **kind cluster not running**: stop and ask user to run `setup-kind-cluster` or enable Kubernetes in Docker Desktop.
- **kubectl not available**: stop — cannot scaffold K8s manifests without kubectl.
- **Never overwrite existing Dockerfiles or K8s manifests without showing a dry-run diff first.**
- **Never hardcode secrets or tokens into manifest files.**

## Lessons Learned: CI Pipeline Fixes

Durable CI-pipeline fixes (runner container config, workflow container options, kind cluster setup, Gitea secrets API, Kustomize best practices, Windows considerations, troubleshooting, Nexus EULA, KUBECONFIG secret handling, selector immutability) live in **`knowledge/lessons-learned/ci-pipeline-fixes.md`** — the single source of truth. Load that file and apply the relevant lessons before scaffolding or deploying; never duplicate the full lesson bodies inline here.
