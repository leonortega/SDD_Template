# Deployment Adapter: Rancher Desktop Kubernetes

Use this adapter when a local laboratory run selects Rancher Desktop as the deployment provider. It is an additional local deployment provider and does not replace the default Azure App Service adapter in `.codex/project-profile.json`.

## Runtime Configuration

- Use Rancher Desktop's built-in Kubernetes context named `rancher-desktop`.
- Read local cluster access from the user's kubeconfig for manual runs or from a secret such as `RANCHER_KUBECONFIG_B64` for Gitea Actions.
- Read Nexus Docker registry endpoint and credentials from Gitea Actions secrets or ignored `.codex/client-tools.local.json`.
- Keep runtime images in a Nexus Docker hosted repository and keep release metadata plus QA evidence in the existing Nexus raw repository.
- Never store kubeconfig contents, Nexus credentials, certificates, or registry passwords in tracked files.

## Operations

- `deploy-artifact`: deploy the selected container image digest set from `app/{commitSha}/container-images.json` to a target namespace.
- `apply-config`: apply namespace-specific ConfigMaps, Secrets, PVCs, Services, Deployments, and Ingress resources.
- `verify-config`: verify the namespace, image digests, image pull secret, and environment settings before reporting deployment success.
- `health`: verify each app `/health` endpoint through the local ingress URL.
- `observe`: capture sanitized Kubernetes pod logs, post them to local Seq when enabled, verify Prometheus/Grafana health target coverage, and publish monitoring evidence to Nexus raw.
- `record`: update release metadata and ticket comments through the selected artifact and ticket adapters.

## Environment Mapping

- DEV namespace: `sdd-dev`.
- QA namespace: `sdd-qa`.
- PROD namespace: `sdd-prod`.
- Default local hosts:
  - DEV site/API: `site.dev.sdd.localhost`, `api.dev.sdd.localhost`.
  - QA site/API: `site.qa.sdd.localhost`, `api.qa.sdd.localhost`.
  - PROD site/API: `site.prod.sdd.localhost`, `api.prod.sdd.localhost`.

## Failure Rules

- Stop when `kubectl config current-context` is not `rancher-desktop`.
- Stop when the Nexus Docker registry is not reachable by both the Gitea runner and Rancher Desktop Kubernetes.
- Stop when deployment would use a mutable tag without an immutable digest.
- Do not rebuild between DEV, QA, PROD, or rollback. Promote the exact image digest references from `container-images.json`.
- Do not publish unsanitized pod logs to Nexus, Plane, or PR comments. Store only sanitized log snippets and summary JSON.
- Do not treat Rancher Desktop as an Azure emulator; it is a local Kubernetes deployment provider.
