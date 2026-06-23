# Rancher Desktop Local Deployment

This folder contains the local Kubernetes deployment surface for the Rancher Desktop laboratory lane.

The local lane keeps Azure support separate and uses:

```text
Gitea Actions -> Nexus Docker hosted -> Rancher Desktop Kubernetes
Nexus raw hosted -> release manifests, pointers, QA evidence
```

## Required Local Setup

1. Run `config infra` to enable Rancher Desktop Kubernetes for the selected Rancher lane, or enable it manually in Rancher Desktop Settings -> Kubernetes. Then confirm:

   ```powershell
   kubectl config current-context
   kubectl get nodes
   ```

   The current context must be `rancher-desktop`.
   At least one node must be `Ready`. The configure `Audit` reports disabled or unhealthy Kubernetes but does not change Rancher Desktop settings; explicit `config infra` runs `EnsureRancherKubernetes` before the read-only audit.

   `config infra` also runs `EnsureHeadlamp` to install the Headlamp Kubernetes UI into the `headlamp` namespace and expose it at:

   ```text
   http://127.0.0.1:4466
   ```

   Copy a fresh login token to the Windows clipboard, then paste it into Headlamp:

   ```powershell
   kubectl create token headlamp --namespace headlamp | Set-Clipboard
   ```

   `config infra` also runs `EnsureRancherPortForwards` for deployed services. This starts stable localhost browser mappings when Windows cannot resolve the `*.sdd.localhost` ingress hosts:

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
   RANCHER_KUBECONFIG_B64
   RANCHER_DEV_SITE_URL
   RANCHER_DEV_API_URL
   RANCHER_QA_SITE_URL
   RANCHER_QA_API_URL
   RANCHER_PROD_SITE_URL
   RANCHER_PROD_API_URL
   SEQ_URL
   RANCHER_APP_SEQ_URL
   PROMETHEUS_URL
   RANCHER_OBSERVABILITY_ENABLED
   ```

   Keep the existing raw Nexus secrets unchanged. When values are consumed by Gitea Action containers or Kubernetes app pods, use the `host.docker.internal` port-forward URLs, for example `http://host.docker.internal:18083` for QA site, `http://host.docker.internal:18084` for QA API, `http://host.docker.internal:5341` for Seq, and `http://host.docker.internal:9091` for Prometheus.

4. Configure Rancher Desktop so Kubernetes can pull from the Nexus Docker registry. For HTTP local-lab registries, configure Rancher Desktop/containerd with an allowed insecure registry or use a trusted local TLS certificate.

## Deployment Model

- Namespaces: `sdd-dev`, `sdd-qa`, `sdd-prod`.
- Runtime images: `sddtemplate/site` and `sddtemplate/api`.
- Deployment identity: image digests from `app/{commitSha}/container-images.json`.
- API data: a namespace-local PVC mounted at `/home/data`.
- Site-to-API calls: site pods use the namespace-local API service URL `http://api:8080`.
- Observability metadata: pods carry app, namespace, environment, commit SHA, and image digest labels/annotations plus matching non-secret environment variables. Pods also send live Serilog events to Seq through `RANCHER_APP_SEQ_URL`, default `http://host.docker.internal:5341`.

Run the script directly only after setting digest-pinned image references:

```powershell
bash infra/rancher/deploy-local-lab.sh --environment dev --namespace sdd-dev --site-image "<site@sha256...>" --api-image "<api@sha256...>" --commit-sha "<commitSha>"
```

## Observability Evidence

Site/API pods send live Serilog events to local Seq after deployment. Use `capture-observability.sh` after a namespace deployment for evidence snapshots. It verifies site/API `/health`, collects recent pod logs, redacts common secret patterns, posts the sanitized events to Seq through `/ingest/clef`, and writes `monitoring-summary.json`.

```powershell
bash infra/rancher/capture-observability.sh --environment qa --namespace sdd-qa --commit-sha "<commitSha>" --site-image "<site@sha256...>" --api-image "<api@sha256...>" --site-url "http://site.qa.sdd.localhost" --api-url "http://api.qa.sdd.localhost"
```

Tracked defaults live in `infra/monitoring/variables.env.example`; real local values stay in ignored env files or Gitea Actions secrets.

Raw Nexus stores the local monitoring evidence next to the artifact commit:

```text
app/{commitSha}/monitoring-summary.json
app/{commitSha}/qa-observability.json
app/{commitSha}/{environment}-site-pod.sanitized.log
app/{commitSha}/{environment}-api-pod.sanitized.log
```
