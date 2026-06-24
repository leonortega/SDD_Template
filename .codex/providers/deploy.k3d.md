# Deployment Adapter: k3d Kubernetes

Use this adapter when `.codex/project-profile.json` selects `providers.deployment.id = "k3d"`. It is the default deployment provider for this local Kubernetes lab.

## Runtime Configuration

- Use cluster `sdd-template` and Kubernetes context `k3d-sdd-template`.
- During explicit `config infra`, use `EnsureK3dCluster` to create or start the k3d cluster through the host `k3d` CLI, expose the Kubernetes API on `127.0.0.1:6550`, switch kubeconfig to `k3d-sdd-template`, and wait for at least one Ready node. Plain `Audit` only reports missing or unhealthy k3d cluster state.
- During explicit `config infra`, use `EnsureK3dHeadlamp` to install Headlamp through the official Helm chart and expose it at `http://127.0.0.1:4466`. Create the login token with `kubectl create token headlamp --namespace headlamp | Set-Clipboard`; never print or store the token in tracked files.
- During explicit `config infra`, use `EnsureK3dPortForwards` after Kubernetes is ready to start stable localhost browser mappings for deployed services: DEV site/API on `127.0.0.1:18081`/`18082`, QA site/API on `127.0.0.1:18083`/`18084`, and PROD site/API on `127.0.0.1:18085`/`18086`. Plain `Audit` only reports missing mappings.
- Read local cluster access from the user's kubeconfig for manual runs or from a secret such as `K3D_KUBECONFIG_B64` for Gitea Actions.
- Read Nexus Docker registry endpoint and credentials from Gitea Actions secrets or ignored `.codex/client-tools.local.json`.
- Keep runtime images in a Nexus Docker hosted repository and keep release metadata plus QA evidence in the existing Nexus raw repository.
- Never store kubeconfig contents, Nexus credentials, certificates, or registry passwords in tracked files.

## Operations

- `deploy-artifact`: deploy the selected container image digest set from `app/{commitSha}/container-images.json` to a target namespace.
- `apply-config`: apply namespace-specific ConfigMaps, Secrets, PVCs, Services, Deployments, and Ingress resources.
- `verify-config`: verify the namespace, image digests, image pull secret, and environment settings before reporting deployment success.
- `health`: verify each app `/health` endpoint through direct HTTP checks against the deployed site/API URLs.
- `observe`: verify Grafana Infinity health datasource/dashboard coverage and publish direct health-check monitoring evidence to Nexus raw.
- `record`: update release metadata and ticket comments through the selected artifact and ticket adapters.

## Environment Mapping

- DEV namespace: `sdd-dev`.
- QA namespace: `sdd-qa`.
- PROD namespace: `sdd-prod`.
- Default local hosts:
  - DEV site/API: `site.dev.sdd.localhost`, `api.dev.sdd.localhost`.
  - QA site/API: `site.qa.sdd.localhost`, `api.qa.sdd.localhost`.
  - PROD site/API: `site.prod.sdd.localhost`, `api.prod.sdd.localhost`.
- Windows browser fallback URLs created by `EnsureK3dPortForwards`:
  - DEV site/API: `http://127.0.0.1:18081`, `http://127.0.0.1:18082`.
  - QA site/API: `http://127.0.0.1:18083`, `http://127.0.0.1:18084`.
  - PROD site/API: `http://127.0.0.1:18085`, `http://127.0.0.1:18086`.

## Failure Rules

- Stop when `kubectl config current-context` is not `k3d-sdd-template`.
- Stop when the k3d cluster `sdd-template` is missing, unreachable, or has no Ready nodes after `EnsureK3dCluster`.
- Stop when the Nexus Docker registry is not reachable by both the Gitea runner and k3d Kubernetes.
- Stop when deployment would use a mutable tag without an immutable digest.
- Do not rebuild between DEV, QA, PROD, or rollback. Promote the exact image digest references from `container-images.json`.
- Do not publish pod logs to Nexus, Plane, or PR comments for the local k3d health evidence path. Store summary JSON only.
- Do not treat k3d as an Azure emulator; it is a local Kubernetes deployment provider.
