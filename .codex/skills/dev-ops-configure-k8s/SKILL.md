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

This section documents critical fixes discovered during CI pipeline debugging that must be applied to any new project. These issues caused repeated CI failures and took significant debugging to resolve.

### 1. Runner Container Configuration (`infra/gitea/compose.yml`)

The Gitea Actions runner config is written via heredoc in the compose file. The following settings are **required**:

```yaml
runner:
  image: gitea/runner:1.0.0
  # ...
  extra_hosts:
    - "host.docker.internal:host-gateway"   # Required for DNS resolution from runner
  volumes:
    - runner-data:/data
    - //var/run/docker.sock:/var/run/docker.sock  # Mount Docker socket (use // on Windows)
  # Config written via heredoc to /tmp/config.yml:
  command:
    - sh
    - -c
    - |
      cat > /tmp/config.yml << YAMLEOF
      log:
        level: info
      runner:
        capacity: 1
        env_file: .env
        timeout: 3h
        fetch_interval: 2s
        labels: ["ubuntu-latest"]          # ⚠️ REQUIRED: must match workflow's runs-on
      cache:
        enabled: true
      container:
        network: agentic-e2e_nexus       # Network for CI job containers
        options: --user root --add-host host.docker.internal:host-gateway
        workdir_parent: /workspace
        valid_volumes:                      # ⚠️ Auto-mounted to each CI container
          - /var/run/docker.sock:/var/run/docker.sock
          - ${KUBE_SRC}:/home/runner/.kube/config:ro
        force_pull: false
        force_rebuild: false
        bind_workdir: false
      YAMLEOF
      export CONFIG_FILE=/tmp/config.yml
      exec run.sh
```

**Critical rules:**

| Setting | Value | Why |
|---------|-------|-----|
| `labels` | `["ubuntu-latest"]` | Must match `runs-on: ubuntu-latest` in workflow YAML — without this, the runner never picks up CI jobs |
| `options` | `--user root --add-host host.docker.internal:host-gateway` | `--user root` fixes `permission denied` on Docker socket; `--add-host` enables `host.docker.internal` DNS resolution for CI containers |
| `valid_volumes` | Includes `/var/run/docker.sock:/var/run/docker.sock` | Auto-mounts the Docker socket to every CI job container. **Do NOT also add `--volume` in `options`** — that creates a duplicate mount |
| `network` | Project network (e.g., `agentic-e2e_nexus`) | Ensures CI containers are on the correct network for registry and service discovery |

**⚠️ Common Mistake — Duplicate Docker socket mount:**

```yaml
# ❌ WRONG: --volume in options creates a mount that duplicates valid_volumes
options: --volume /var/run/docker.sock:/var/run/docker.sock --user root

# Result: Duplicate mount point error → container creation fails
```

```yaml
# ✅ CORRECT: valid_volumes handles the socket mount; options only has user + DNS
options: --user root --add-host host.docker.internal:host-gateway
valid_volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

**⚠️ Docker Compose directory matters:**

Always run `docker compose` from the **project root compose file** (`infra/compose.yml`), NOT from individual service compose files (`infra/gitea/compose.yml`). The project root compose file sets the project name (`name: agentic-e2e`) which prefixes all networks. Running from the wrong directory creates containers on the wrong Docker network, causing hostname resolution failures.

```bash
# ✅ CORRECT — from the main compose file
cd /repo/infra && docker compose up -d --no-deps runner

# ❌ WRONG — creates runner on wrong network
cd /repo/infra/gitea && docker compose up -d --no-deps runner
```

### 2. CI Workflow Container Options (`.gitea/workflows/package-deploy.yml`)

The CI job container also needs specific options, but **without** the Docker socket volume mount (it's already handled by `valid_volumes`):

```yaml
jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    container:
      image: sdd-e2e-ci:local
      # ✅ CORRECT: only --user root and --add-host
      # 🚫 NO --volume here (handled by runner's valid_volumes)
      options: --user root --add-host host.docker.internal:host-gateway
```

**What each option does:**

- **`--user root`** — The CI image (`sdd-e2e-ci:local`) runs as `appuser` by default. Without root, it gets `permission denied` when accessing the Docker socket.
- **`--add-host host.docker.internal:host-gateway`** — Enables `host.docker.internal` DNS resolution inside the CI container. Required for reaching the Gitea API, Nexus registry, and kind K8s API server.
- **NO `--volume`** — The Docker socket is already auto-mounted by the runner's `valid_volumes`. Adding it again causes `Duplicate mount point` error.

### 3. kind Cluster Setup (Alternative to Docker Desktop K8s)

When Docker Desktop K8s is unavailable or you want a lightweight local cluster, use **kind** (Kubernetes in Docker).

#### Install kind

```bash
# On Windows with winget:
winget install Kubernetes.kind

# On macOS/Linux:
brew install kind
# or
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.32.0/kind-$(uname)-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/
```

#### Create a cluster

```bash
kind create cluster --name sdd-cluster
```

#### Configure kubeconfig for CI access

The kind API server is exposed on `127.0.0.1:<random-port>`. From inside Docker containers (where CI runs), `127.0.0.1` isn't accessible. You need to:

1. Get the external kubeconfig
2. Change the server address from `127.0.0.1:<port>` to `host.docker.internal:<port>`
3. Add `insecure-skip-tls-verify: true` (the TLS certificate is for `sdd-cluster-control-plane`, not `host.docker.internal`)
4. Connect the kind control-plane to the project's Docker networks
5. Set the modified kubeconfig as a Gitea secret

```bash
KIND=/path/to/kind.exe  # On Windows, find it in winget packages dir
CLUSTER_NAME=sdd-cluster

# Get the port from kubeconfig
KUBECONFIG_PORT=$($KIND get kubeconfig --name $CLUSTER_NAME | grep server | grep -oP ':\K\d+')

# Get and modify kubeconfig, then save to file
$KIND get kubeconfig --name $CLUSTER_NAME | \
  sed "s|server: https://127.0.0.1:$KUBECONFIG_PORT|server: https://host.docker.internal:$KUBECONFIG_PORT|" > kubeconfig-ci.yaml

# Add insecure-skip-tls-verify using Python (since CA cert won't match host.docker.internal)
python3 -c "
with open('kubeconfig-ci.yaml', 'r') as f:
    content = f.read()
content = content.replace('certificate-authority-data:', 'insecure-skip-tls-verify: true')
# Remove the multi-line CA data after the replacement
import re
content = re.sub(r'insecure-skip-tls-verify: true[^s]*?(?=\n    server:)', 'insecure-skip-tls-verify: true', content, flags=re.DOTALL)
with open('kubeconfig-ci.yaml', 'w') as f:
    f.write(content)
"

# Connect kind control-plane to project networks (so CI containers can reach it via Docker DNS)
docker network connect agentic-e2e_gitea ${CLUSTER_NAME}-control-plane
docker network connect agentic-e2e_nexus ${CLUSTER_NAME}-control-plane

# Set as Gitea secret
python3 -c "
import base64, json, urllib.request
with open('kubeconfig-ci.yaml', 'r') as f:
    kubeconfig_data = f.read()
url = 'http://localhost:3000/api/v1/repos/admin/sdd-test/actions/secrets/KUBECONFIG'
payload = json.dumps({'data': kubeconfig_data}).encode()
req = urllib.request.Request(url, data=payload, method='PUT')
creds = base64.b64encode(b'admin:admin123').decode()
req.add_header('Authorization', f'Basic {creds}')
req.add_header('Content-Type', 'application/json')
urllib.request.urlopen(req)
print('KUBECONFIG secret set successfully')
"

# Clean up temp file
rm kubeconfig-ci.yaml
```

### 4. Gitea Actions Secrets via API

Set repository secrets programmatically:

```bash
# API: PUT /api/v1/repos/{owner}/{repo}/actions/secrets/{secretname}
# Body: {"data": "<raw-value>"}
# Gitea handles base64 encoding internally — do NOT pre-encode

curl -u 'admin:admin123' -X PUT \
  'http://localhost:3000/api/v1/repos/admin/sdd-test/actions/secrets/KUBECONFIG' \
  -H 'Content-Type: application/json' \
  -d "{\"data\": \"$(cat kubeconfig.yaml | tr '\n' '\\n')\"}"
```

Required secrets for CI:

| Secret | Description |
|--------|-------------|
| `KUBECONFIG` | Raw kubeconfig YAML (not base64) — set via API as `{"data": "<raw-yaml>"}` |
| `NEXUS_USERNAME` | Nexus admin username |
| `NEXUS_PASSWORD` | Nexus admin password |
| `NEXUS_URL` | Nexus URL (e.g., `http://host.docker.internal:8088`) |
| `NEXUS_REPOSITORY` | Nexus artifact repository name (e.g., `sdd-artifacts`) |

### 5. Kustomize Best Practices

**🚫 NEVER use unresolvable placeholder variables in overlay patches:**

```yaml
# ❌ WRONG: kustomize can't resolve ${COMPONENT_NAME} — causes build failure
patches:
  - path: config-patch.yaml  # contains ${COMPONENT_NAME} and ${REPLICAS}
```

```yaml
# ✅ CORRECT: use real deployment names or remove the patch if unused
resources:
  - ../../base
images:
  - name: host.docker.internal:8083/openproject
    newTag: latest
```

**Rules for kustomize overlays:**

- Patches must reference **actual** `metadata.name` values that exist in the base resources
- Placeholder variables like `${VARIABLE}` are NOT kustomize variables — they're treated as literal strings
- If an overlay needs to set environment variables, use a proper patch targeting the real deployment name (e.g., `name: openproject`)
- Unused placeholder patches that don't match any resource cause `no resource matches strategic merge patch` error in kustomize v5+
- Remove orphaned patch files when they're no longer referenced

### 6. Docker Desktop for Windows Considerations

| Aspect | Details |
|--------|---------|
| **Docker socket path** | On Windows, Docker Desktop uses a **named pipe** (`npipe:////./pipe/dockerDesktopLinuxEngine`), not a Unix socket. The `//var/run/docker.sock` syntax in Docker Compose mounts the socket via the FUSE layer. |
| **`host.docker.internal`** | Works when `--add-host host.docker.internal:host-gateway` is set on the container. Resolves to the Windows host from inside Docker containers. |
| **`kind` on Windows** | kind creates clusters as Docker containers. The API server is exposed on `127.0.0.1:<port>`. CI containers need `host.docker.internal:<port>` with `insecure-skip-tls-verify: true`. |
| **Git Bash path issues** | `/tmp` in Git Bash maps to a Windows temp directory. Python and Docker may see different paths. Always use absolute project paths (e.g., `/c/LeonRepository/SDD_Test/`) to avoid confusion. |
| **Docker Compose network naming** | When `infra/compose.yml` has `name: agentic-e2e`, all networks are prefixed with `agentic-e2e_`. Running compose from subdirectories creates networks with different names (e.g., `gitea_gitea` vs `agentic-e2e_gitea`). |

### 7. Troubleshooting CI Pipeline

| Error | Cause | Fix |
|-------|-------|-----|
| `Duplicate mount point: /var/run/docker.sock` | Docker socket mounted twice — once from runner's `valid_volumes`, once from `--volume` in `container.options` | Remove `--volume` from both runner `options` and workflow `container.options`; only use `valid_volumes` |
| `permission denied while trying to connect to the docker API` | CI container runs as `appuser` instead of root | Add `--user root` to `container.options` in workflow YAML |
| `daemon Docker Engine socket not found` | Docker socket not mounted (on Windows, the bind mount path may be wrong) | Use `//var/run/docker.sock:/var/run/docker.sock` (double slash on Windows) in the compose file |
| `no resource matches strategic merge patch Deployment.v1.apps/${COMPONENT_NAME}` | Kustomize overlay has a patch targeting a non-existent deployment | Remove placeholder patches with `${VARIABLE}` names, or update them to target real deployment names |
| `tls: failed to verify certificate: ... not host.docker.internal` | kind TLS cert doesn't include `host.docker.internal` in SAN | Add `insecure-skip-tls-verify: true` to the kubeconfig cluster entry |
| `couldn't get version/kind; json parse error` | Secret was stored base64-encoded via Gitea API but shouldn't have been | Set secrets via API with raw value (Gitea handles encoding internally); don't pre-encode |
| `no kind clusters found` | kind cluster doesn't exist or was deleted by Docker restart | Re-run `kind create cluster --name sdd-cluster` and re-set the kubeconfig secret |
| Runner never picks up CI jobs | Runner labels don't match workflow's `runs-on` | Set `labels: ["ubuntu-latest"]` in runner config |
| `lookup host.docker.internal: no such host` from host | `host.docker.internal` only resolves inside Docker containers | Use `kubectl` directly from host (not from inside a container) for local testing; inside CI, it works with `--add-host` |
| `Error: Process completed with exit code 1` on build step | Generic failure — check the error log at `/tmp/kustomize-err.log` | Run `kustomize build . 2>&1` locally to see the actual error |

### 8. Nexus EULA Acceptance and Password Handling

Nexus 3.x on first boot generates a **random admin password** and blocks all API calls until the **EULA is accepted**. Both issues cause silent CI failures:

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| CI upload step returns **HTTP 401 Unauthorized** | Gitea secret `NEXUS_PASSWORD` is the hardcoded `admin123` but Nexus generated a random password | Read actual password from container: `docker exec agentic-nexus cat /nexus-data/admin.password` |
| CI upload step returns **HTTP 403 Forbidden** | EULA not accepted — Nexus blocks uploads on fresh install | Accept EULA via two-step API flow |
| Nexus API returns empty or 500 on all calls | Wrong EULA endpoint used — old `/editions/eula/accept` doesn't exist in Nexus 3.92+ | Use correct two-step flow below |

#### Fix 1: Read the Actual Admin Password

Nexus stores the generated admin password at `/nexus-data/admin.password` inside the container. **Never hardcode `admin123`** — always read it dynamically:

```python
import subprocess

def _get_nexus_admin_password() -> str:
    """Read Nexus admin password from container, fall back to admin123."""
    try:
        r = subprocess.run(
            # ⚠️ Use // prefix on Windows to prevent Git Bash path translation
            ["docker", "exec", "agentic-nexus", "cat", "//nexus-data/admin.password"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return "admin123"
```

**Why `//nexus-data` instead of `/nexus-data`:** On Windows with Git Bash, the path `/nexus-data/admin.password` gets translated to a Windows absolute path like `C:/Users/.../nexus-data/admin.password` (because `/nexus-data` is treated as an MSYS path). Using `//` at the start disables MSYS path conversion, keeping it as a Linux absolute path inside the container.

This function is used by both:
- `provision_nexus_repositories()` — to create the `sdd-artifacts` repository
- `provision_gitea_secrets()` — to set the `NEXUS_PASSWORD` Gitea secret

#### Fix 2: Accept the EULA via Two-Step API

The Nexus 3.92+ EULA API requires a **two-step** flow — GET first, then POST back with `accepted: true`. The old single-endpoint (`/editions/eula/accept`) was removed.

```bash
# Step 1: GET the current EULA status with disclaimer text
EULA_JSON=$(curl -s -u 'admin:ACTUAL_PASSWORD' \
  'http://localhost:8088/service/rest/v1/system/eula' \
  -H 'Accept: application/json')

# Step 2: POST it back with accepted: true
curl -X POST -u 'admin:ACTUAL_PASSWORD' \
  'http://localhost:8088/service/rest/v1/system/eula' \
  -H 'Content-Type: application/json' \
  -d "$EULA_JSON" \
  # ^^^ Sends the EXACT disclaimer text back (including smart quotes)
```

The critical detail: the disclaimer text contains **smart quotes** (Unicode `'` U+2018 and `'` U+2019). You must send the **exact text** that Nexus returned — any modification to the disclaimer (like replacing smart quotes with regular ASCII quotes) will cause `Invalid EULA disclaimer` error.

In Python, use `urllib.request` (no extra dependencies — it's part of the standard library) to perform the same two-step flow:

```python
import json, urllib.request, base64

def _accept_nexus_eula() -> bool:
    """Accept Nexus EULA via two-step API. Returns True on success."""
    passwd = _get_nexus_admin_password()
    auth_data = base64.b64encode(f"admin:{passwd}".encode()).decode()
    base = "http://localhost:8088"

    def _api(method, path, body=None):
        req = urllib.request.Request(f"{base}{path}", data=body, method=method)
        req.add_header("Authorization", f"Basic {auth_data}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    # Step 1: GET the EULA
    status, data = _api("GET", "/service/rest/v1/system/eula")
    if status != 200:
        return False

    eula = json.loads(data)
    if eula.get("accepted"):
        return True  # Already accepted

    # Step 2: POST back with accepted=true (preserving exact disclaimer text)
    eula["accepted"] = True
    status, _ = _api("POST", "/service/rest/v1/system/eula", body=json.dumps(eula).encode())
    return status in (200, 204)
```

#### When Do These Issues Occur?

- **New Nexus installation** (first `setup-lab` run on a fresh environment)
- **After Docker volume wipe** (`nexus-data` volume is deleted, Nexus resets)
- **When using `provision_gitea_secrets` standalone** without first running `provision_nexus_repositories` (secrets get hardcoded `admin123`)

#### Prevention

The `provision_nexus_repositories` and `provision_gitea_secrets` functions in `environment_lab.py` now handle both issues automatically.

#### Manual Fix for Existing Broken Install

If CI is already failing with 401/403 on the upload step:

```bash
# 1. Get the actual password
NEXUS_PASS=$(docker exec agentic-nexus cat //nexus-data/admin.password)

# 2. Accept the EULA
EULA=$(curl -s -u "admin:$NEXUS_PASS" 'http://localhost:8088/service/rest/v1/system/eula' -H 'Accept: application/json')
curl -s -X POST -u "admin:$NEXUS_PASS" 'http://localhost:8088/service/rest/v1/system/eula' -H 'Content-Type: application/json' -d "$EULA"

# 3. Update Gitea secrets with actual password
curl -s -u 'admin:admin123' -X PUT \
  'http://localhost:3000/api/v1/repos/admin/sdd-test/actions/secrets/NEXUS_PASSWORD' \
  -H 'Content-Type: application/json' \
  -d "{\"data\": \"$NEXUS_PASS\"}"
```
