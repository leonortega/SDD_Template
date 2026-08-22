# K8s Manifest Filter — Match by App Label

## Problem

The CI deploy workflow filters kustomize output to only apply resources for affected apps. The filter matched by resource `name` only, which dropped Secrets and ConfigMaps that belong to an app but have a different name.

Example: `tkp-api-secrets` (Secret) belongs to app `tkp-api`, but the name doesn't match.

## Symptoms

- Pod `CreateContainerConfigError` — Secret not found
- `kubectl get secrets -n sdd-dev` returns empty

## Fix

Add app-label matching to the manifest filter in `.gitea/workflows/package-deploy.yml`:

```python
elif name in affected:
    kept_deployments.append(doc)
else:
    # Check if the resource belongs to an affected app via
    # the app: label (e.g. Secrets named tkp-api-secrets
    # where the affected app is tkp-api).
    app_label = re.search(r"^  app:\s*(\S+)", doc, flags=re.M)
    if app_label and app_label.group(1) in affected:
        kept_deployments.append(doc)
    else:
        skipped.append(name)
```

## Resource Naming Convention

Resources belonging to an app should have `app: <app-id>` label:

```yaml
metadata:
  name: tkp-api-secrets
  labels:
    app: tkp-api
```

## Related

- PR #16 — fix for manifest filter
- `.gitea/workflows/package-deploy.yml` — deploy filter logic
