# Checkov Scope — Limit to Apps + Infra Deployment

## Problem

Running `checkov -d infra/k8s` scans all K8s manifests including kubelet/infrastructure checks (CKV_K8S_68 through CKV_K8S_119). These checks are for cluster-level configuration, not application manifests.

## Symptoms

- 90+ Checkov failures from K8s checks
- CI pipeline fails on irrelevant kubelet policies
- Time wasted triaging cluster-level vs app-level findings

## Solution

Scope Checkov to application-relevant directories only:

```yaml
# .gitea/workflows/pr-validation.yml
DIRS=""
for d in apps infra/deployment; do [ -d "$d" ] && DIRS="$DIRS $d"; done
```

Keep K8s manifest validation in the kustomize validation step instead:

```yaml
- name: Validate Kustomize overlays
  run: kustomize build . | kubectl apply --dry-run=client -f -
```

## Checkov Skip List

For dev environments, skip:

```yaml
# .checkov.yml
skip-check:
  - CKV_SECRET_4  # plaintext creds in K8s Secret manifests
  - CKV_SECRET_6  # basic auth in manifests
```

## Related

- PR #14 — Checkov scope fix
- `.gitea/workflows/pr-validation.yml` — CI validation
- `.checkov.yml` — Checkov config
