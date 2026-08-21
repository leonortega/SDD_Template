# Anti-Pattern: Incomplete Environment Overlay

## Description

Creating a K8s overlay for an environment (QA, PROD) that only includes shared infrastructure (database) but not application resources (Deployments, Services, Secrets).

## Example

```yaml
# WRONG — only database, no apps
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: sdd-qa
resources:
  - ../../shared/database
patches:
  - path: service-patch.yaml
```

## Correct Approach

Include all application resources:

```yaml
# CORRECT — database + apps
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: sdd-qa
resources:
  - ../../shared/database
  - ../../shared/tkp-web
  - ../../shared/tkp-api
patches:
  - path: service-patch.yaml
```

## Why

- Deploying only the database leaves apps undeployed
- The CI deploy gate detects "no deployable changes" and skips
- Manual intervention required to fix

## Prevention

When creating a new environment overlay, copy from the DEV overlay and adjust namespace/ports.

## Related

- PR #23 — QA overlay fix
- `infra/k8s/overlays/qa/kustomization.yaml`
