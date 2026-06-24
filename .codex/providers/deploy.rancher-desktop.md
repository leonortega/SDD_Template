# Deployment Adapter: Rancher Desktop Kubernetes

Use this adapter when `.codex/project-profile.json` selects `providers.deployment.id = "rancher-desktop"`. It is the default deployment provider for this local Kubernetes lab.

## Runtime Configuration

- Use the Kubernetes context `rancher-desktop`.
- During explicit `config infra`, use `EnsureRancherDesktopCluster` to switch kubeconfig to `rancher-desktop` and wait for at least one Ready node. Rancher Desktop owns cluster creation and startup through its application settings. Plain `Audit` only reports missing or unhealthy Rancher Desktop Kubernetes state.
- During explicit `config infra`, use `EnsureRancherDesktopHeadlamp` to install Headlamp through the official Helm chart and expose it at `http://127.0.0.1:4466`. Create the login token with `kubectl create token headlamp --namespace headlamp | Set-Clipboard`; never print or store the token in tracked files.
- During explicit `config infra`, use `EnsureRancherDesktopPortForwards` after Kubernetes is ready to start stable localhost browser mappings for deployed services: DEV site/API on `127.0.0.1:18081`/`18082`, QA site/API on `127.0.0.1:18083`/`18084`, and PROD site/API on `127.0.0.1:18085`/`18086`. Plain `Audit` only reports missing mappings.
- Read local cluster access from the user's kubeconfig for manual runs or from a secret such as `RANCHER_KUBECONFIG_B64` for Gitea Actions.
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
- Windows browser fallback URLs created by `EnsureRancherDesktopPortForwards`:
  - DEV site/API: `http://127.0.0.1:18081`, `http://127.0.0.1:18082`.
  - QA site/API: `http://127.0.0.1:18083`, `http://127.0.0.1:18084`.
  - PROD site/API: `http://127.0.0.1:18085`, `http://127.0.0.1:18086`.

## Failure Rules

- Stop when `kubectl config current-context` is not `rancher-desktop`.
- Stop when the `rancher-desktop` context is missing, unreachable, or has no Ready nodes after `EnsureRancherDesktopCluster`.
- Stop when the Nexus Docker registry is not reachable by both the Gitea runner and Rancher Desktop Kubernetes.
- Stop when deployment would use a mutable tag without an immutable digest.
- Do not rebuild between DEV, QA, PROD, or rollback. Promote the exact image digest references from `container-images.json`.
- Do not publish pod logs to Nexus, OpenProject, or PR comments for the local Rancher Desktop health evidence path. Store summary JSON only.
- Do not treat Rancher Desktop as an Azure emulator; it is a local Kubernetes deployment provider.

