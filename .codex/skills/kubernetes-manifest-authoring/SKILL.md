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

## References

- K8s MCP: `kubernetes` server in `.vscode/mcp.json`
- Kubernetes MCP tools: pods, deployments, logs, helm, events
- Docker Desktop K8s: Enable in Docker Desktop Settings → Kubernetes
- CLI helpers: `python -m tools.sdd_cli environment-lab scaffold-k8s`
