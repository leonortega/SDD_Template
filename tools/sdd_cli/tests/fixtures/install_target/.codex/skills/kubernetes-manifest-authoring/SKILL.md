# Kubernetes And Docker Desktop — Manifest Authoring And Maintenance

Author Kubernetes manifests, convert Docker Compose to K8s resources, and maintain local cluster health.

## Scope

This skill covers K8s manifest authoring, Docker Compose to K8s conversion, troubleshooting local clusters, and WSL2/Rancher Desktop maintenance.

## Common K8s Manifest Patterns

### Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  labels:
    app: api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: app:latest
          ports:
            - containerPort: 8080
          resources:
            limits:
              cpu: 500m
              memory: 512Mi
            requests:
              cpu: 250m
              memory: 256Mi
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
```

### Service
```yaml
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 8080
  type: ClusterIP
```

### Ingress
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
spec:
  rules:
    - host: api.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 80
```

## Docker Compose → K8s Conversion

Use `kompose` to convert:

```bash
kompose convert -f infra/compose.yml -o infra/k8s/
```

Common conversion patterns:
- **Docker services** → K8s Deployments + Services
- **Volumes** → PersistentVolumeClaims
- **Networks** → (handled implicitly by K8s networking)
- **Environment variables** → ConfigMaps or Secrets
- **Ports** → Service port mappings

## Cluster Management Commands

```bash
# Check cluster status
kubectl cluster-info
kubectl get nodes
kubectl get pods --all-namespaces

# Deploy manifests
kubectl apply -f infra/k8s/

# Check deployment status
kubectl rollout status deployment/api
kubectl describe pod {pod-name}

# View logs
kubectl logs -f deployment/api

# Port forwarding (for local debugging)
kubectl port-forward service/api 8080:80

# Events
kubectl get events --sort-by='.lastTimestamp'
```

## K8s Tooling

| Tool | Purpose | Install |
|---|---|---|
| **kubectl** | Primary CLI | Native or `npx kubectl` |
| **helm** | Package manager | `choco install kubernetes-helm` |
| **kompose** | Compose → K8s | `choco install kompose` |
| **K9s** | TUI cluster manager | `choco install k9s` |

## WSL2 / Docker Desktop Maintenance

- **.vhdx compaction**: `wsl --shutdown`, then `diskpart` to compact ext4.vhdx
- **Port forwarding**: Use `netsh interface portproxy` for WSL2 → Windows
- **Hyper-V issues**: Check `services.msc` for Hyper-V services
- **Docker Desktop reset**: `Settings → Troubleshoot → Reset to factory defaults`
- **Kubeconfig location**: `%USERPROFILE%\.kube\config`
- **Context selection**: `kubectl config use-context docker-desktop`

## CI Pipeline Integration

When authoring K8s manifests for Gitea Actions CI, follow these patterns.

### Runner Configuration (infra/gitea/compose.yml)

The Gitea Actions runner must be configured with specific options for CI containers to work:

```yaml
container:
  network: agentic-e2e_nexus
  options: --user root --add-host host.docker.internal:host-gateway
  valid_volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - ${KUBE_SRC}:/home/runner/.kube/config:ro
```

**Key rules:**
- `labels: ["ubuntu-latest"]` must match the workflow's `runs-on: ubuntu-latest`
- Docker socket is mounted by `valid_volumes` — do NOT also add `--volume` in `options`
- Always run `docker compose` from the **root `infra/compose.yml`** (not from subdirectory) to use the correct network namespace

See `dev-ops-configure-k8s/SKILL.md` for complete runner configuration details.

### Workflow Container Options (package-deploy.yml)

The CI job container's `options` should only include `--user root` and `--add-host`:

```yaml
container:
  image: sdd-e2e-ci:local
  options: --user root --add-host host.docker.internal:host-gateway
  # NO --volume /var/run/docker.sock (handled by runner valid_volumes)
```

### Kustomize Overlays

When creating Kustomize overlays for CI deployment:

**🚫 NEVER use unresolvable placeholder variables in patches:**

```yaml
# ❌ WRONG: causes 'no resource matches strategic merge patch' error
patches:
  - path: config-patch.yaml
# config-patch.yaml contains:
# metadata:
#   name: ${COMPONENT_NAME}  ← kustomize treats this as literal string
```

```yaml
# ✅ CORRECT: remove patches that don't target real deployments
resources:
  - ../../base
images:
  - name: host.docker.internal:5001/frontend
    newTag: latest
```

Best practices:
- Every patch must target a `metadata.name` that **actually exists** in the base resources
- Kustomize does NOT support shell-style `${VARIABLE}` substitution — those are treated as literal strings
- If a patch is unused, remove it (don't leave orphaned files)
- The CI sets images via `kustomize edit set image`, which modifies the overlay's `images` field
- Verify overlays locally: `kustomize build .` or `kubectl kustomize .`

### CI Troubleshooting

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `Duplicate mount point: /var/run/docker.sock` | Socket mounted twice | Remove `--volume` from both runner `options` and workflow `container.options` |
| `permission denied while trying to connect to the docker API` | Container runs as non-root | Add `--user root` to `container.options` |
| `no resource matches strategic merge patch` | Kustomize patch references non-existent deployment name | Remove or fix the patch to target real deployment names |
| `tls: failed to verify certificate: ... not host.docker.internal` | kind TLS cert doesn't include `host.docker.internal` | Add `insecure-skip-tls-verify: true` to kubeconfig |
| Runner doesn't pick up jobs | Labels don't match `runs-on` | Set `labels: ["ubuntu-latest"]` in runner config |

## kind Cluster Setup (Alternative K8s)

When Docker Desktop K8s is not available, use **kind** (Kubernetes in Docker):

```bash
# Install
winget install Kubernetes.kind  # Windows
brew install kind               # macOS

# Create cluster
kind create cluster --name sdd-cluster

# Connect to project Docker networks (so CI containers can reach it)
docker network connect agentic-e2e_gitea sdd-cluster-control-plane
docker network connect agentic-e2e_nexus sdd-cluster-control-plane
```

For CI access, modify the kubeconfig:
- Change server address from `127.0.0.1:<port>` to `host.docker.internal:<port>`
- Add `insecure-skip-tls-verify: true` (TLS cert is for kind container name, not `host.docker.internal`)
- Set the modified kubeconfig as a Gitea `KUBECONFIG` secret

See `dev-ops-configure-k8s/SKILL.md` for the complete setup procedure.

## Docker Desktop for Windows Notes

- Docker uses named pipes (`npipe:////./pipe/dockerDesktopLinuxEngine`), not Unix sockets
- Use `//var/run/docker.sock` (double forward slash) for bind mounts in Docker Compose on Windows
- `host.docker.internal` resolves inside containers when `--add-host host.docker.internal:host-gateway` is set
- Run `docker compose` from the project root compose file (not subdirectories) to maintain correct network naming

## References

- K8s MCP: `kubernetes` server in `.vscode/mcp.json`
- Kubernetes MCP tools: pods, deployments, logs, helm, events
- Docker Desktop K8s: Enable in Docker Desktop Settings → Kubernetes
- CLI helpers: `python -m tools.sdd_cli environment-lab scaffold-k8s`
- K8s DevOps skill: `.codex/skills/dev-ops-configure-k8s/SKILL.md` (runner config, kind setup, troubleshooting)
