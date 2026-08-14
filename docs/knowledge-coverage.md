# Knowledge Base → Template Coverage Matrix

Maps every `knowledge/` file to its template home (`.agents/skills/`, `tools/sdd_cli/`,
`.gitea/workflows/`, or `infra/`) so a lesson's enforcement point is discoverable in one place.

- **Audited:** 2026-08-06 (conversation-wide audit of `knowledge/` vs the template); 2026-08-07
  added the `knowledge/errors/` scaffold stub; 2026-08-14 removed the 2 archive lesson
  files after their fixes were applied inline (see the Removed table below).
- **Last restructure:** 2026-08-06 — the 7 implemented lesson files were deleted; their rules now
  live inline in skills, scripts, and workflows (see the Removed table below).
- **Scope:** the 14 `.md` files remaining under `knowledge/`. (The 2026-08-11 SDD_Test knowledge port
  was fully applied as real template fixes and cleaned — see the note below. The 2026-08-14
  TICKET-38/39/41 port was likewise applied as template fixes and its 2 files removed.)
- **Rule:** a lesson is *covered* when the template enforces it via a skill, script, workflow, or
  tracked config — not when it exists only as prose in `knowledge/`. Informational/reference docs
  (`✅ Reference`) map to their documentation home (`AGENTS.md`, `docs/`) and are intentionally not
  enforced.

## Summary

| Metric                                   | Count |
| ---------------------------------------- | ----- |
| Total knowledge files                    | 14    |
| Files with enforceable lessons           | 0     |
| Informational / index / placeholder      | 5     |
| Category scaffolds (empty templates)     | 9     |
| Removed 2026-08-06 (implemented inline)  | 7     |
| Removed 2026-08-14 (implemented inline)  | 2     |

All enforceable lessons have been moved out of `knowledge/` into the template — the folder now holds
only the index, category scaffolds, and reference/placeholder files.

**2026-08-11 SDD_Test knowledge port — applied and cleaned.** Ten consumer-delivery knowledge
files were ported; their fixes were applied as real template changes where applicable and the files
were deleted: agent-eval encoding/v3-envelope fix (`agent_eval.py` + tests), checkout-sync rule
(`dev-ops-deploy-qa`), OpenProject `lockVersion` (`api-helpers.md`), Nexus fail-closed manifest check +
localhost retag (`package-deploy.yml`), SPA `/health` rule (`dev-flow-implement-ticket`), archive
mechanics (`dev-flow-archive-change`), git-push credential recipe (`configure-dev-environment`),
dispatch discipline (`dev-ops-deploy-prod`), and the shared-index union rule
(`docs-knowledge-maintenance`).

**2026-08-14 TICKET-38/39/41 port — applied and cleaned.** The two archive/QA-lesson files
(`fixes/archive-e2eproject-openspec-changes.md`, `lessons-learned/archive-e2eproject-openspec-changes.md`)
were removed after their fixes were applied as template changes: non-interactive `openspec archive
--yes` and `npx trunk fmt` on synced specs (`dev-flow-archive-change`), and the oracle-regex
must-match-actual-format rule (`e2e-testing-patterns`). See the Removed table below.

## Current Matrix (14 files)

| Knowledge file | Template home (skill / script / workflow) | Coverage | Notes |
| -------------- | ----------------------------------------- | -------- | ----- |
| `knowledge/README.md` | `tools/sdd_cli/knowledge_search.py` (search + classify) via `tools/sdd_cli/cli.py`, tested in `tests/` | ✅ Native | Index + read/write policy. The `knowledge-search` commands it documents are implemented and tested. |
| `knowledge/anti-patterns/README.md` | — | ⬜ Scaffold | Category template only — no lessons yet. |
| `knowledge/errors/README.md` | — | ⬜ Scaffold | Category template only — the classifier may create `knowledge/errors/<error>.md` entries. |
| `knowledge/architecture/README.md` | — | ⬜ Scaffold | Category template only. |
| `knowledge/fixes/README.md` | — | ⬜ Scaffold | Category template only. |
| `knowledge/implementation/README.md` | — | ⬜ Scaffold | Category template only. |
| `knowledge/lessons-learned/README.md` | self-referential catalog | ✅ Index | Lists the retained lesson docs; points to `docs/knowledge-coverage.md` for the moved lessons. |
| `knowledge/lessons-learned/qa-findings.md` | — | ⬜ Placeholder | "No current QA findings" — reserved for future QA evidence. |
| `knowledge/lessons-learned/workflow-memory.md` | `AGENTS.md` + `docs/workflows/*` | ✅ Reference | Informational — records the configured delivery workflow; not an enforceable lesson. |
| `knowledge/patterns/README.md` | — | ⬜ Scaffold | Category template only. |
| `knowledge/prompts/README.md` | — | ⬜ Scaffold | Category template only. |
| `knowledge/references/README.md` | — | ⬜ Scaffold | Category template only. |
| `knowledge/references/project-map.md` | `docs/` + `AGENTS.md` | ✅ Reference | Reference — documents repository shape and absent-by-design folders. |
| `knowledge/troubleshooting/README.md` | — | ⬜ Scaffold | Category template only. |

## Removed 2026-08-06 — Implemented Inline In The Template

These 7 files were deleted after their lessons were verified as enforced. Each row records where the
lesson now lives.

| Removed file | Lesson now enforced by |
| ------------ | ---------------------- |
| `errors/installed-readme-excluded-tests.md` | `.agents/skills/docs-knowledge-maintenance/SKILL.md` (inline rule: installed validation must use CLI smoke checks, e.g. `environment-lab health-check`, never `python -m unittest tools.sdd_cli.tests.test_cli`) |
| `errors/no-powershell-alternate-execution.md` | `.agents/skills/dev-flow-implement-ticket/SKILL.md` §7 "Windows agent tool-execution rule" (PowerShell-default discipline) |
| `errors/openproject-container-secret-key-base.md` | `infra/openproject/compose.yml` (`SECRET_KEY_BASE: ${OPENPROJECT_SECRET_KEY_BASE:?...}`) + `ensure_openproject_env()` in `environment_lab.py` |
| `errors/template-config-infra-native-modes.md` | `test_all_configure_modes_have_native_dispatch` in `tools/sdd_cli/tests/test_cli.py` + `init_local_files()` knowledge seeding |
| `errors/tool-update-runtime-db-directories.md` | `tools/sdd_cli/sdd-tool-data.json` (excludes `pgdata`, `data`, `logs`) + `walk_sdd_source_files()` in `tools/sdd_cli/_shared.py` |
| `lessons-learned/ci-pipeline-fixes.md` | `.agents/skills/dev-ops-configure-k8s/SKILL.md` "Lessons Learned: CI Pipeline Fixes" (14 inline rules), `.agents/skills/configure-ci-workflows/SKILL.md`, `.gitea/workflows/package-deploy.yml`, `.gitea/workflows/pr-validation.yml`, `infra/gitea/compose.yml`, `.gitignore`, `environment_lab.py`, `k8s_lab.py`, `dev-flow-scaffold-project` |
| `lessons-learned/release-lessons.md` | `.agents/skills/dev-ops-deploy-prod/SKILL.md` "Branch-Protected `main` (Release-Branch PR Flow)" (inline) |

## Removed 2026-08-14 — Implemented Inline In The Template

These 2 files were deleted after their lessons were verified as enforced. Each row records where the
lesson now lives.

| Removed file | Lesson now enforced by |
| ------------ | ---------------------- |
| `fixes/archive-e2eproject-openspec-changes.md` | `.agents/skills/dev-flow-archive-change/SKILL.md` (non-interactive `OPENSPEC_TELEMETRY=0 openspec archive <name> --yes` + `npx trunk fmt` on newly synced specs before the archive commit) |
| `lessons-learned/archive-e2eproject-openspec-changes.md` | `.agents/skills/e2e-testing-patterns/SKILL.md` (oracle regex must match the actual generated reference format — base36 alphanumeric, e.g. `/Q-\d{4}-[A-Z0-9]{6,}\d{6}/`); protected-dev archive-PR routing enforced by the pre-receive branch-protection hook |

### ci-pipeline-fixes.md — Per-Section Mapping (historical record)

| § | Lesson | Where the rule now lives | Status |
| - | ------ | ------------------------ | ------ |
| 1 | Runner container config (`labels`, `options`, `valid_volumes`, `network`) | `infra/gitea/compose.yml`; inline rule 1 in `dev-ops-configure-k8s` | ✅ |
| 2 | CI workflow container options (`--user root`, no duplicate `--volume`) | `.gitea/workflows/package-deploy.yml`; inline rule 2 | ✅ |
| 3 | kind cluster setup + fixed per-env port mappings | `infra/k8s/kind-config.yaml`; `k8s_ports.py` (canonical `ports.json`); inline rule 4 | ✅ |
| 4 | Gitea Actions secrets via API (raw value, no base64) | `provision_gitea_secrets()` in `environment_lab.py`; inline rule 6 | ✅ |
| 5 | Kustomize best practices (no `${VAR}` placeholder patches) | `configure-ci-workflows`; inline rule 7 | ✅ |
| 6 | Docker Desktop for Windows considerations | `configure-dev-environment`; inline rule 8 | ✅ |
| 7 | CI troubleshooting table | Compact symptom→fix table in `dev-ops-configure-k8s` (inline) | ✅ |
| 8 | Nexus EULA two-step flow + dynamic admin password | `_accept_nexus_eula()` + `_get_nexus_admin_password()` in `environment_lab.py`; inline rule 9 | ✅ |
| 9 | KUBECONFIG CA-cert vs `insecure-skip-tls-verify` conflict | `setup_k8s_access()` in `k8s_lab.py` (YAML parse, drop CA data); inline rule 5 | ✅ |
| 10 | Deployment selector immutability — delete Deployments before apply | `.gitea/workflows/package-deploy.yml` delete step + `configure-ci-workflows`; inline rule 10 | ✅ |
| 11a | Trivy `--skip-db-update` on first run | `.gitea/workflows/pr-validation.yml` (flag dropped) + `configure-ci-workflows`; inline rule 14 | ✅ |
| 11b | React Router SCA upgrade chain | Coordinated upgrade recipe in `configure-ci-workflows` §5 (inline) | ✅ |
| 12a | `.gitignore` case-insensitive match silently drops source | `.gitignore` negations (`!apps/**/Data/` + `/**`); inline rule 12 | ✅ |
| 12b | YAML block-scalar indent breaks heredoc terminators (column-0) | `configure-ci-workflows`; inline rule 11 | ✅ |
| 12c | `python3 -c` bodies must start at column 0 | `configure-ci-workflows`; inline rule 11 | ✅ |
| 12d | Non-root container can't write root-owned workdir | `dev-flow-scaffold-project` §Dockerfile (`RUN chown -R <uid>:<gid> /app` before `USER`); inline rule 13 | ✅ |
| 12e | NodePorts are cluster-scoped — per-env overlays + `protocol: TCP` gotcha | NodePort-uniqueness gate in `package-deploy.yml` + `configure-ci-workflows`; inline rule 4 | ✅ |
| 12f | Process notes (protected branches, never copy CI logs, validation order) | `dev-ops-deploy-prod` + `lefthook.yml` gitleaks gate | ✅ |
| 13 | `agent-reviewed` label loop (CI-in-loop review) | `dev-flow-pr-review-agent` + label gate in `.gitea/workflows/pr-validation.yml` | ✅ |
| 14 | kind API port is random — never hardcode 6443 | `setup_k8s_access()` derives the port from the live cluster; inline rule 5 | ✅ |

## Gaps Fixed On 2026-08-06 (before removal)

1. **Phantom CLI command in a knowledge doc** — `installed-readme-excluded-tests.md` recommended
   `python -m tools.sdd_cli environment-lab audit`, but `audit` is not a registered `environment-lab`
   mode. Corrected to the real installed smoke check `environment-lab health-check`, and the rule was
   inlined into `docs-knowledge-maintenance`.
2. **No-PowerShell discipline not in any skill** — baked into the "Windows agent tool-execution rule"
   in `dev-flow-implement-ticket` §7.

## Keeping This Matrix Current

- Re-verify the mapping whenever `knowledge/` entries or template skills/scripts/workflows change.
- `python -m tools.sdd_cli knowledge-search search --list-topics` lists the discoverable topics;
  every listed topic should resolve to a template home above.
- New consumer-project lessons should be folded into the template (skill/script/workflow) first, per
  `knowledge/README.md` Update Process; this matrix is the ledger of that rule.
