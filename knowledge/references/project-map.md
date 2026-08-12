<!-- TIER 2: SEMI-STABLE - Project map, loaded at startup -->

# Project Map

Current repository shape:

```text
docs/
openspec/
infra/
.gitea/
.agents/          # skills, agent-evals, mcp-instructions, ponytail config
.template/        # configuration only (delivery policy, project profile, quality)
tools/sdd_cli/
apps/             # deployable applications (ADR-0002) — created by scaffold after stack selection
packages/         # shared libraries consumed by apps (ADR-0002)
artifacts/        # ignored
```

`.template/` is the config home (delivery policy, project profile, quality, client tools);
its name is deliberately product-agnostic — it is not tied to any AI product or agent runtime.
`codex`-specific paths remain only for Codex CLI conventions inside vendor skills
(e.g. impeccable `.codex/hooks.json`, playwright `$HOME/.codex`).

Product code layout (ADR-0002 — see `docs/adr/ADR-0002-product-layout-and-deployment.md`):

```text
apps/<app>/       # one self-contained folder per deployable app
  src/            # application source
  test/           # unit/, integration/, e2e/, architecture/
  deploy/         # per-app K8s manifests (Deployment, Service), composed into env overlays
  Dockerfile
  app.json
packages/<pkg>/   # shared libraries (auth, UI kit, API client, domain)
```

There is deliberately **no root `src/` / `test/` pair** — a single root pair only suits one deployable unit, and this
shell targets a portfolio of deployable apps. `apps/` and `packages/` are created by the project scaffold
(`dev-flow-scaffold-project`, one example app) after the user selects a product stack; `.template/` stays the
configuration-only home, and `infra/` holds cluster-level concerns. Tests live per app under
`apps/<app>/test/{unit,integration,e2e,architecture}/` — never a single shared `test/` directory.
