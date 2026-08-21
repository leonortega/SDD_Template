# Kustomize Image Override Pattern

## Pattern

When using `kustomize edit set image` to override container images, the command requires `OLD=NEW` format:

```bash
# WRONG — adds a new image entry but doesn't override existing ones
kustomize edit set image host.docker.internal:5001/tkp-web:abc123

# CORRECT — maps from base image name to new image
kustomize edit set image tkp-web:latest=host.docker.internal:5001/tkp-web:abc123
```

## Why

Kustomize's `images` transformer matches by image name. Without the `OLD=` prefix, the command adds a new entry with no matching base image, so the override never applies.

## Base Image Names

The base deployment manifests use `image: <app-id>:latest`. The kustomize command must reference this exact name:

```yaml
# base/shared/tkp-web/deployment.yaml
image: tkp-web:latest
```

```bash
# Override for CI deploy
kustomize edit set image tkp-web:latest=host.docker.internal:5001/tkp-web:${COMMIT_SHA}
```

## CI Integration

In `.gitea/workflows/package-deploy.yml`:

```python
image = f'{registry}/{app_id}:{commit_sha}'
subprocess.run(['kustomize', 'edit', 'set', 'image', f'{app_id}:latest={image}'], check=True)
```

## Related

- PR #15 — fix for kustomize image override
- `.gitea/workflows/package-deploy.yml` — CI deploy step
