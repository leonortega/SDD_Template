# E2EPROJECT-38/39 Issues And Fixes

Complete catalog of every issue and its fix encountered while delivering
E2EPROJECT-38 (Real-Time Shipment Tracking Portal) and E2EPROJECT-39 (Dynamic
Quote Request & Freight Calculator) end-to-end — implementation, AI review,
QA, PROD promotion, and post-release ops. Use this to improve the template:
every row below maps to a durable fix, knowledge entry, script change, or
skill improvement that a fresh consumer project should inherit.

## Issue Catalog

|  ID  | Area       | Issue                                                                                        | Fix                                                                                                                                       | Knowledge / artifact                          |
|  --- | ---------- | ------------------------------------------------------------------                           | ----------------------------------------------------------------------------------------------------                                      | --------------------------------------        |
|  01  | AI review  | Tracking endpoint echoed malformed IDs (trust boundary)                                      | Server-side guard: reject id > 64 chars or non-`[A-Za-z0-9-]` before echoing                                                              | code pattern, not yet a skill                 |
|  02  | AI review  | Re-entering the SAME tracking id after an error did nothing                                  | `setSearchParams` with identical `q` is a no-op → add `retryKey` state bumped on same-id submit                                           | React `useSearchParams` pitfall               |
|  03  | AI review  | Hero search input/URL query sync gaps                                                        | Sync input state with `?q=`; added tests                                                                                                  | code pattern                                  |
|  04  | Quality    | Unformatted files fail trunk gate                                                            | Run `trunk fmt` per file before commit                                                                                                    | workflow memory                               |
|  05  | Git hooks  | lefthook stash conflict silently reverted unstaged changes                                   | Recovery via dangling git object; rules: no blind `git add -A`, narrow commits, verify `git show HEAD:`                                   | `git-lefthook-conflict-recovery.md`           |
|  06  | Detection  | Lost wiring only caught at pre-push `stack-tests` (404 /api/quotes)                          | Gate caught it; verify committed tree not just working tree                                                                               | same file above                               |
|  07  | A11y       | Modal: no focus trap / focus restore / scroll lock; Escape submits mid-flight                | Focus trap + restore + scroll lock + Escape guard during submit (+tests)                                                                  | code pattern — consider a11y skill            |
|  08  | Release    | PROD promotion blocked: `main` branch-protected (push disabled, 1 approval)                  | Release-branch PR flow: `release/vX.Y.Z` → final tag → PR `release/.. -> main` (approver ≠ author) → `workflow_dispatch environment=prod` | `release-lessons.md`                          |
|  09  | Monitoring | Health-probe landed on wrong Docker network (standalone compose run) → Grafana "No data"/400 | Pin `monitoring` network to `agentic-e2e_monitoring`; manage stack only via root `infra/compose.yml`                                      | deployment.md §Managing the Monitoring Stack  |
|  10  | Monitoring | Silent health-probe exit not detected                                                        | `restart: unless-stopped` + healthcheck (stdlib urllib, no curl in alpine)                                                                | compose.yml comments + deployment.md          |
|  11  | Ports      | nodePort drift/collision; hardcoded ports in 3 places; NodePorts cluster-scoped              | Canonical `infra/deployment/ports.json` + `tools/sdd_cli/k8s_ports.py`; CI drift validation; per-env patches                              | ports.json, k8s_ports.py, package-deploy.yml  |
|  12  | Docs       | Stale port tables (QA nodePorts wrong, PROD row missing); "LoadBalancer" text wrong          | 6-row tables; "Service Type: NodePort" explanation (host ports vs nodePorts)                                                              | deployment.md                                 |
|  13  | Nexus      | Docker registry pushes 401 / repo missing (Bearer-token flow rejected by daemon)             | `docker-hosted` repo with `forceBasicAuth: true`, port 5001, idempotent GET/PUT reconcile                                                 | `environment_lab.py`                          |
|  14  | Disk       | Local + kind image accumulation per deploy                                                   | CI prune steps: keep newest N commit tags per app; kind prune keeps current build (guarded)                                               | package-deploy.yml                            |
|  15  | Grafana    | Dashboard stale after PROD deploy                                                            | Environment Matrix panel with PROD Active; version-bump on every dashboard edit                                                           | health-board.json + deployment.md             |

## Durable Rules For New Projects

1. **Never `git add -A && git commit` blindly after a lefthook "unable to
   restore" failure** — the working tree may have been reverted to HEAD. Check
   `git diff HEAD --stat` and key markers first (see lefthook knowledge file).
2. **Commit in narrow slices** (explicit paths) when hooks reformat files;
   keep OpenSpec-only commits separate from code commits; stage before a hook
   that reformats.
3. **Trust boundaries first:** reject malformed input server-side before
   echoing anything back to the caller.
4. **`setSearchParams` with the same value is a no-op** — use a retry key when
   the same query must re-trigger an effect.
5. **Modal a11y checklist:** focus trap, focus restore, scroll lock, Escape
   guard during in-flight submit.
6. **`main` may be branch-protected** — PROD promotion needs the release-branch
   PR flow, not a direct fast-forward.
7. **Manage the monitoring stack only via the root compose file** (project
   `agentic-e2e`); pin the `monitoring` network to `agentic-e2e_monitoring`.
8. **One canonical port source** (`ports.json`) with CI drift validation;
   NodePorts are cluster-scoped — never reuse across environments.
9. **Nexus Docker registry needs `forceBasicAuth: true`** on port 5001 or
   `docker login`/push 401s.
10. **Image pruning is a deploy hygiene step** — local daemon and kind
    containerd both accumulate commit-tag images.

## Status

All issues fixed and verified in the SDD_Test consumer project (PRs #15–#28 +
docker-hosted/pruning port). This catalog is the template-side record so future
scaffolded projects inherit the fixes (scripts, workflows, compose, docs, and
knowledge files listed above are part of the template).
