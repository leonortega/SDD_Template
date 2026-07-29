# Nexus Repository Management

Manage Sonatype Nexus Repository — hosted, proxy, and group repos, cleanup policies, and artifact promotion pipelines.

## Scope

This skill covers Nexus repository configuration, artifact publishing, promotion, and REST API scripting.

## Repository Types

| Type | Purpose | Example |
|---|---|---|
| **Hosted** | Store your own built artifacts | `sdd-artifacts` (raw), `nuget-hosted`, `npm-hosted` |
| **Proxy** | Cache external dependencies | `nuget.org-proxy`, `npmjs-proxy`, `pypi-proxy` |
| **Group** | Combine multiple repos under one URL | `nuget-group` → `nuget-hosted` + `nuget.org-proxy` |

## Artifact Promotion Pipeline

```
dev (hosted, writable)
  → staging (hosted, QA-verified)
    → release (hosted, immutable)
```

Promotion uses Nexus REST API to copy/move components between repositories. Use the `promote-alias` operation for pointer-based promotion without moving canonical artifacts.

## Cleanup Policies

- **Snapshot cleanup**: Delete snapshots older than 30 days, keep last 5
- **Staging cleanup**: Delete staging artifacts after 14 days or when superseded
- **Release retention**: Immutable, never auto-delete

## CLI Helpers

```bash
# Validate release manifest
python -m tools.sdd_cli dev-flow validate-release-manifest \
  --manifest-path artifacts/release.json

# Generate next RC version
python -m tools.sdd_cli dev-flow next-rc-version \
  --current-version 1.2.3
```

## REST API Scripting

Common Nexus REST API v1 operations:

```bash
# List components in a repository
curl -u admin:{password} \
  "{nexusUrl}/service/rest/v1/components?repository={repo}"

# Upload a component (raw)
curl -u admin:{password} \
  -F "raw.directory={path}" \
  -F "raw.asset1=@{file}" \
  -F "raw.asset1.filename={filename}" \
  "{nexusUrl}/service/rest/v1/components?repository={repo}"

# Delete a component
curl -X DELETE -u admin:{password} \
  "{nexusUrl}/service/rest/v1/components/{id}"
```

## References

- Nexus provider adapter: `.codex/providers/artifact.nexus.md`
- Nexus base URL: `http://localhost:8088`
- Default credentials: admin / (set in local config)
