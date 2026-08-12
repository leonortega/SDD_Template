# ADR-0004: Config-Driven Role Registry (web/api Decoupled From Python)

## Status

Accepted (2026-08-12). Decision driven by the human owner (Option A in the review: keep the example appIds,
decouple the role vocabulary). Drafted by the AI at the human owner's request; the human owner retains final say.

## Context

The template's port-allocation scheme (blocks of 10 per role, per env) keyed off a hardcoded role vocabulary in
Python: `ROLE_HOST_BASES = {"web": 8081, "api": 5002}` and `ROLE_NODE_OFFSETS = {"web": 80, "api": 500}` in
`tools/sdd_cli/k8s_ports.py`, plus role-based container-port and host-port fallbacks in `k8s_lab.py`
(`_port_map = {"web": 80, "api": 5000}`, the `role == "api"` PORT-env check, and the `web→808x / api→500x`
`setup_k8s_access` guesses).

This is template-hostile for two reasons:

- A consumer with an async worker, a cron scheduler, or a websocket service has no clean slot — `assign-app-ports`
  only knows `web`/`api`, and `role` is required on every app.
- Extending the vocabulary means editing Python constants and their tests, not configuration — the wrong boundary
  for a product-free template whose whole point is per-consumer shaping.

The example **appIds** (`web-storefront`, `api-orders`) were never the problem — every tool is keyed by `appId`
from `apps.json`/`ports.json`. ADR-0005 subsequently removed them entirely: the template ships no reference apps
and no per-app port entries.

## Decision

Move the role vocabulary and its port ranges into a config file, **`infra/deployment/roles.json`** (schema:
`roles.schema.json`), and make the tooling read it:

- Each role declares `hostPortBase` (host-port block 0 start), `nodePortOffset` (added to `env_code*1000`),
  `containerPort` (scaffold fallback), `portEnv` (emit the stack-independent `PORT` env in scaffolded
  Deployments), and `healthCheck` (`http` vs `tcp` — the health probe uses it). The shipped file defines `web`,
  `api`, and `database` (the shared engine, ADR-0003) with the exact ranges the hardcoded constants had plus the
  database role's own block.
- `k8s_ports.py` gains `load_roles(root)`: the shipped file is the source of truth; a **missing** file falls back
  to `_DEFAULT_ROLES` (mirrors the shipped file — used by unit fixtures and bare checkouts), and a
  **present-but-invalid** file raises `ValueError` so a config typo never silently re-defaults. `role_host_base`,
  `env_node_base`, `load_ports`, and `assign_app_ports` accept the registry; `assign-app-ports` resolves consumer
  roles when invoked with a repo root.
- `k8s_lab.py` derives its role→container-port fallback and `portEnv` set from the registry; `setup_k8s_access`
  derives its host-port fallback guesses from each role's `hostPortBase` (dev/qa/prod consume consecutive slots).
- `validate-app-config` validates `roles.json` against `roles.schema.json` so a consumer's custom-role edit fails
  the gate, not a later deploy.
- The `assign-app-ports` CLI error lists the known roles from the registry, not a static `web, api` string.

Deliberately **not** changed:

- `role` stays **required** in `apps.schema.json` and `ports.schema.json`. JSON Schema `default` is not applied by
  the loaders, so making it optional would need loader changes for no template benefit; ports.json entries always
  state the role that drives their ranges.
- The legacy appId→role fallbacks (`_LEGACY_APP_ID_ROLES`, the `kind_config_yaml` role-label map) were **removed**
  with ADR-0005 — no reference apps ship, and `ports.schema.json` requires an explicit `role` on every entry, so
  the fallbacks are dead code.
- `health_probe.py` stays as-is: its hardcoded maps are appId→label/port (cosmetic, self-contained fallback), not
  role vocabulary.
- Runtime-aware gates (`stack_tests.py` / `ensure-stack-toolchain` / `configure-ci-workflows`) stay profile-wide —
  same deferral already recorded in ADR-0003; revisit when the first app registers a non-empty `runtime`.

## Consequences

- Consumers add roles (`worker`, `scheduler`, ...) by editing `infra/deployment/roles.json` — no Python changes,
  and `assign-app-ports` allocates from their ranges automatically.
- The shipped numbers are unchanged: web still allocates from 8081/offset 80, api from 5002/offset 500 — generated
  artifacts and the drift guard (`test_committed_artifacts_match_generator`) stay byte-identical.
- A new drift guard (`test_shipped_roles_json_matches_defaults`) pins the committed `roles.json` to the Python
  fallback registry, so the two cannot diverge silently.
- With ADR-0005, `ports.json` ships without per-app entries (empty `appPorts` + empty env blocks) and
  `kind-config.yaml` carries no extraPortMappings until a consumer registers apps.
- `load_roles` makes malformed `roles.json` a hard error in every port path — config mistakes surface at the gate
  and CLI, not as silent fallbacks.
