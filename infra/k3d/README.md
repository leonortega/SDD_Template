# k3d Local Deployment

This folder contains the local Kubernetes deployment surface for the k3d laboratory lane.

The local lane keeps Azure support separate and uses:

```text
Gitea Actions -> Nexus Docker hosted -> k3d Kubernetes
Nexus raw hosted -> release manifests, pointers, QA evidence
```

## Required Local Setup

1. Run `config infra` to create or start the selected k3d lane, or create it manually with `k3d cluster create sdd-template --api-port 127.0.0.1:6550`. Then confirm:

   ```powershell
   kubectl config current-context
   kubectl get nodes
   ```

   The current context must be `k3d-sdd-template`.
   At least one node must be `Ready`. The configure `Audit` reports missing or unhealthy k3d cluster state but does not create the cluster; explicit `config infra` runs `EnsureK3dCluster` before the read-only audit.

   `config infra` also runs `EnsureK3dHeadlamp` to install the Headlamp Kubernetes UI into the `headlamp` namespace and expose it at:

   ```text
   http://127.0.0.1:4466
   ```

   Copy a fresh login token to the Windows clipboard, then paste it into Headlamp:

   ```powershell
   kubectl create token headlamp --namespace headlamp | Set-Clipboard
   ```

   `config infra` also runs `EnsureK3dPortForwards` for deployed services. This starts stable localhost browser mappings when Windows cannot resolve the `*.sdd.localhost` ingress hosts:

   ```text
   DEV site/API  -> http://127.0.0.1:18081 / http://127.0.0.1:18082
   QA site/API   -> http://127.0.0.1:18083 / http://127.0.0.1:18084
   PROD site/API -> http://127.0.0.1:18085 / http://127.0.0.1:18086
   ```

2. In Nexus, create a Docker hosted repository and expose its HTTP connector on the port mapped in `infra/nexus/compose.yml`, default `5001`.

3. Configure the Gitea Actions secrets:

   ```text
   NEXUS_DOCKER_REGISTRY
   NEXUS_DOCKER_USERNAME
   NEXUS_DOCKER_PASSWORD
   K3D_KUBECONFIG_B64
   K3D_DEV_SITE_URL
   K3D_DEV_API_URL
   K3D_QA_SITE_URL
   K3D_QA_API_URL
   K3D_PROD_SITE_URL
   K3D_PROD_API_URL
   SEQ_URL
   K3D_APP_SEQ_URL
   ```

   Keep the existing raw Nexus secrets unchanged. When values are consumed by Gitea Action containers or Kubernetes app pods, use the `host.docker.internal` port-forward URLs, for example `http://host.docker.internal:18083` for QA site, `http://host.docker.internal:18084` for QA API, and `http://host.docker.internal:5341` for Seq.

4. Configure the k3d cluster so k3s/containerd can pull from the Nexus Docker registry. For HTTP local-lab registries, use a k3d registry config with an allowed insecure registry or use a trusted local TLS certificate.

## Deployment Model

- Namespaces: `sdd-dev`, `sdd-qa`, `sdd-prod`.
- Runtime images: `sddtemplate/site` and `sddtemplate/api`.
- Deployment identity: image digests from `app/{commitSha}/container-images.json`.
- API data: a namespace-local PVC mounted at `/home/data`.
- Site-to-API calls: site pods use the namespace-local API service URL `http://api:8080`.
- Observability metadata: pods carry app, namespace, environment, commit SHA, and image digest labels/annotations plus matching non-secret environment variables. Pods also send live Serilog events to Seq through `K3D_APP_SEQ_URL`, default `http://host.docker.internal:5341`.

Run the script directly only after setting digest-pinned image references:

```powershell
bash infra/k3d/deploy-local-lab.sh --environment dev --namespace sdd-dev --site-image "<site@sha256...>" --api-image "<api@sha256...>" --commit-sha "<commitSha>"
```

## Observability Evidence

Site/API pods send live Serilog events to local Seq after deployment. Deployment workflows use direct site/API `/health` checks for evidence and write `monitoring-summary.json`.

Tracked defaults live in `infra/monitoring/variables.env.example`; real local values stay in ignored env files or Gitea Actions secrets.

Raw Nexus stores the local monitoring evidence next to the artifact commit:

```text
app/{commitSha}/monitoring-summary.json
app/{commitSha}/qa-observability.json
```
