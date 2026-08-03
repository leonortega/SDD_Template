<!-- TIER 2: SEMI-STABLE - CI pipeline fixes, loaded at startup -->

# CI Pipeline Fixes

Durable lessons from CI pipeline debugging. Moved from `.codex/skills/dev-ops-configure-k8s/SKILL.md`; the skill now points here (single source of truth).

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
kind create cluster --name sdd-cluster --config infra/k8s/kind-config.yaml
```

Always use the project's `kind-config.yaml` to ensure `extraPortMappings` are applied. The config maps:

| Host Port | NodePort | Service |
|-----------|----------|--------|
| `8081` | `30080` | Frontend (DEV) |
| `5002` | `30500` | Backend (DEV) |
| `8082` | `30081` | Frontend (QA) |
| `5003` | `30501` | Backend (QA) |

**Note:** `5001` is reserved by Nexus Docker registry.

If the cluster already exists without the expected port mappings, you must recreate it:
```bash
kind delete cluster --name sdd-cluster
kind create cluster --name sdd-cluster --config infra/k8s/kind-config.yaml
```
This destroys all cluster state (including running deployments) — only do this when adding new port mappings.

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
  - name: host.docker.internal:5001/frontend
    newTag: latest
```

**Rules for kustomize overlays:**

- Patches must reference **actual** `metadata.name` values that exist in the base resources
- Placeholder variables like `${VARIABLE}` are NOT kustomize variables — they're treated as literal strings
- If an overlay needs to set environment variables, use a proper patch targeting the real deployment name (e.g., `name: frontend`)
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

> **Implemented in the lab CLI:** `tools/sdd_cli/environment_lab.py::_accept_nexus_eula()`
> now performs this two-step flow (with the legacy one-shot fallback for pre-3.92
> installs), wired into both `provision_nexus_repositories()` (setup-lab step 12)
> and the Nexus admin password bootstrap in `provision_lab_users()`. A failure is
> now surfaced as a warning finding instead of being swallowed as success.

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

### 9. KUBECONFIG Secret: CA Cert + insecure-skip-tls-verify Conflict

When configuring the `KUBECONFIG` Gitea secret for CI access to a kind cluster, **never include both `certificate-authority-data` and `insecure-skip-tls-verify: true`** in the kubeconfig — kubectl rejects this with:

```
error: specifying a root certificates file with the insecure flag is not allowed
```

#### Root Cause

The kind cluster's API server TLS certificate is issued for SANs including `localhost`, `kubernetes`, `sdd-cluster-control-plane`, etc. — but **not** `host.docker.internal`. When the CI runner container connects to `host.docker.internal:<port>`, the hostname doesn't match any SAN, so TLS verification fails.

Adding `insecure-skip-tls-verify: true` skips this hostname check. But if `certificate-authority-data` is also present, kubectl treats it as mutually exclusive and errors out.

#### Fix

When generating the kubeconfig for CI, **remove** `certificate-authority-data` entirely:

```python
import subprocess, yaml

result = subprocess.run(['kind', 'get', 'kubeconfig', '--name', 'sdd-cluster'], capture_output=True, text=True, check=True)
data = yaml.safe_load(result.stdout)

for cluster in data.get('clusters', []):
    cluster['cluster'].pop('certificate-authority-data', None)  # ⚠️ Remove CA cert
    cluster['cluster']['insecure-skip-tls-verify'] = True
    server = cluster['cluster'].get('server', '')
    cluster['cluster']['server'] = server.replace('127.0.0.1', 'host.docker.internal')

kubeconfig_yaml = yaml.dump(data, default_flow_style=False)
# Store kubeconfig_yaml as the raw KUBECONFIG secret value
```

**⚠️ Do NOT base64-encode the kubeconfig for the Gitea secret.** Gitea handles encoding internally. Set it via API as `{"data": "<raw-yaml>"}`.

### 10. Deployment Selector Immutability (commonLabels → labels Migration)

When a Deployment already exists in the cluster with a `spec.selector.matchLabels` that includes labels like `app.kubernetes.io/managed-by: sdd-cli` (from kustomize's deprecated `commonLabels`), and you change the kustomization to use the modern `labels` field instead, `kubectl apply` will fail with:

```
Deployment.apps "frontend" is invalid: spec.selector: Invalid value: {"matchLabels":{"app":"frontend"}}: field is immutable
```

#### Root Cause

- **`commonLabels`** (deprecated) adds labels to **both** `metadata.labels` and `spec.selector.matchLabels` — so the old deployment's selector includes `app.kubernetes.io/managed-by: sdd-cli`
- **`labels`** (modern) adds labels only to `metadata.labels` and `spec.template.metadata.labels` — **not** to `spec.selector.matchLabels`
- When `kubectl apply` tries to remove `app.kubernetes.io/managed-by` from the selector, Kubernetes rejects it because selectors are immutable

#### Fix

**In the CI workflow**, delete existing deployments before applying new manifests. Only deployments need deletion — Services have mutable selectors and can be updated in-place.

```yaml
# Add this step BEFORE kubectl apply in your CI workflow:
- name: Delete existing deployments for clean apply
  run: |
    python3 << PYEOF
    import json, subprocess
    with open('infra/deployment/apps.json') as f:
        apps = json.load(f).get('apps', [])
    for app in apps:
        app_id = app['appId']
        subprocess.run(['kubectl', '-n', 'sdd-dev', 'delete', 'deploy', app_id, '--ignore-not-found'], check=False)
    PYEOF
```

**Important:** Use an **unquoted** `PYEOF` heredoc delimiter (`<< PYEOF` not `<< 'PYEOF'`) so bash expands shell variables like `${APPS_JSON}` and `${NAMESPACE}` inside the Python script.

**⚠️ Only delete Deployments, not Services.** Service `spec.selector` IS mutable in Kubernetes, so services can be patched in-place. Deleting them would cause unnecessary traffic interruption.