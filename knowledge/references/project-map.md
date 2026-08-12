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
artifacts/        # ignored
```

`.template/` is the config home (delivery policy, project profile, quality, client tools);
its name is deliberately product-agnostic — it is not tied to any AI product or agent runtime.
`codex`-specific paths remain only for Codex CLI conventions inside vendor skills
(e.g. impeccable `.codex/hooks.json`, playwright `$HOME/.codex`).

Absent by design:

```text
src/
test/
```

Add product source, tests, stack guidance, app targets, and quality gates in a future ticket after the new product stack
is selected.
