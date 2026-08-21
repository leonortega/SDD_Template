# Port Allocation Mismatch with Role Registry

## Symptoms

CI validation fails with:

```
nodePort 30081 for dev/tkp-api is outside the 'api' dev nodePort range [30500, 31000)
```

## Root Cause

`ports.json` has hardcoded port values that don't match the role registry in `roles.json`. The role registry defines:

- `web`: `nodePortOffset: 80` → dev: 30080, qa: 31080, prod: 32080
- `api`: `nodePortOffset: 500` → dev: 30500, qa: 31500, prod: 32500
- `database`: `nodePortOffset: 700` → dev: 30700, qa: 31700, prod: 32700

## Fix

Align `ports.json` with the role registry:

| Role | Host Port (dev) | NodePort (dev) | Host Port (qa) | NodePort (qa) |
|---|---|---|---|---|
| web | 8081 | 30080 | 8082 | 31080 |
| api | 5002 | 30500 | 5003 | 31500 |
| database | 5432 | 30700 | 5433 | 31700 |

## Prevention

Generate `ports.json` from `roles.json` using `tools/sdd_cli/k8s_ports.py`:

```bash
python -m tools.sdd_cli k8s-ports write-artifacts
```

## Related

- PR #14 — port alignment fix
- `infra/deployment/ports.json` — canonical port map
- `infra/deployment/roles.json` — role registry
- `tools/sdd_cli/k8s_ports.py` — port generation
