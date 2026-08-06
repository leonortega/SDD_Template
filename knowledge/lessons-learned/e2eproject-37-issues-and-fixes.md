<!-- TIER 2: SEMI-STABLE - E2EPROJECT-37 issue/fix catalog, loaded at startup -->

# E2EPROJECT-37 Issues And Fixes

Complete catalog of every issue and its fix encountered while delivering
E2EPROJECT-37 (landing page) through the release pipeline
(dev → DEV+QA → main v0.1.0 → PROD), including the PR-validation loop and
monitoring fixes. Issues already captured elsewhere are indexed here with a
pointer; new lessons carry full detail.

## Issue Catalog

| ID  | Area       | Issue                                                        | Fix                                                                                            | Captured                |
| --- | ---------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- | ----------------------- |
| 01  | CI gate    | PR Validation fails: `FAIL: codex-reviewed label not found`  | Run AI review (post `<!-- codex-review-agent:{sha} -->` comment), apply label, re-run workflow | §13 below               |
| 02  | CI SAST    | Semgrep flags vendored content (AI-001)                      | Add `.semgrepignore` vendor exclusion                                                          | ci-pipeline-fixes §11   |
| 03  | CI SCA     | Trivy `--skip-db-update` on first run                        | Drop flag until DB pre-cached                                                                  | ci-pipeline-fixes §11a  |
| 04  | CI SCA     | React Router CVEs in package-lock                            | Upgrade react-router-dom 6.30.4 → react-router 8.3.0 + React 19                                | ci-pipeline-fixes §11b  |
| 05  | CI deploy  | 4-layer deploy failure chain                                 | gitignore → heredoc → python -c → runtime, fix in order                                        | ci-pipeline-fixes §12   |
| 06  | Monitoring | Grafana shows QA `Not deployed` though healthy               | Update probe/kind-config/allowedHosts to real nodePorts                                        | §A below                |
| 07  | Monitoring | kind hostPorts not bound on running cluster                  | Reach nodePorts via kind network DNS, not host ports                                           | §A below                |
| 08  | Monitoring | nginx e2e proxy 502 (stale hardcoded IP)                     | Proxy to stable DNS name, not container IP                                                     | §A below                |
| 09  | Monitoring | Infinity panel crash rules                                   | `source: "inline"`, no `color` in mappings                                                     | §A below                |
| 10  | OpenSpec   | `openspec archive` skips main-spec sync                      | Create main specs from deltas, canonical format                                                | §B below                |
| 11  | Ticket     | OpenProject has no "Done" status                             | Terminal state is `Closed` (id 12)                                                             | §B below                |
| 12  | Git        | `git push --delete` hangs on Windows; merged branches linger | Delete branches via Gitea API                                                                  | §C below                |
| 13  | Tooling    | cp1252 console crashes on emoji output                       | `PYTHONIOENCODING=utf-8`                                                                       | §C below                |
| 14  | Tooling    | Complex bash quoting breaks agent tool calls                 | Write temp Python script files and run them                                                    | §C below                |
| 15  | Tooling    | Windows promptfoo @libsql blocker                            | Deterministic Python+node eval fallback                                                        | eval-tooling-windows.md |
| 16  | Tooling    | npm global native-module install fails on Windows (esbuild)  | Do not rely on global promptfoo; uninstall broken install                                      | eval-tooling-windows.md |
| 17  | Deploy     | Env-specific deploy dispatch                                 | `workflow_dispatch` with `environment=prod`; push to dev auto-promotes DEV+QA                  | §B below                |

## A. Monitoring: Grafana Service Status Dashboard

### A1. Stale "Not deployed" after per-env nodePort change

**Symptom:** After the per-env NodePort fix moved QA to nodePorts 31080/31500
and PROD to 32080/32500, the SDD Service Status dashboard reported QA as
`Not deployed` even though QA was deployed and healthy.

**Root cause:** Three sources still referenced the old base ports:
`infra/monitoring/health_probe.py`, `infra/k8s/kind-config.yaml`
(extraPortMappings), and the Infinity datasource `allowedHosts`
(`infra/monitoring/grafana/provisioning/datasources/infinity-health.yml`).

**Fix:** Point the probe at `sdd-cluster-control-plane:<nodePort>` directly on
the kind Docker network (independent of host extraPortMappings), correct the
per-env nodePorts in all three files, then restart the probe and Grafana
containers. Verified end-to-end through Grafana's `/api/ds/query`.

### A2. kind extraPortMappings only apply at cluster creation

**Symptom:** `localhost:8082` / `localhost:8083` (new hostPorts for QA/PROD)
fail with connection refused, while the nodePorts work from inside the kind
network.

**Root cause:** `kind-config.yaml` extraPortMappings are read only when the
cluster is created. A running cluster does not rebind host ports after config
edits.

**Fix:** For host access, proxy through the cluster node DNS name
(`sdd-cluster-control-plane:<nodePort>` — verified 200 via the health probe
container) or run an nginx proxy container on the `kind` network.

### A3. nginx proxy 502 — stale hardcoded upstream IP

**Symptom:** `qa-fe-proxy` (nginx on host port 31080) returned 502 on every
path even though the probe reported QA UP.

**Root cause:** The proxy's `proxy_pass` hardcoded a container IP
(`http://172.22.0.3:31080`) that changed after container/network restarts.

**Fix:** Rewrite `proxy_pass` to the stable DNS name
(`http://sdd-cluster-control-plane:31080`), `docker cp` the config in, and
`nginx -s reload`. Never hardcode container IPs in proxy upstreams.

### A4. Infinity datasource crash rules

- **`source: "url"` + `parser: "backend"` + `format: "table"` crashes** the
  panel. Use `source: "inline"` with `data: '{"data":[...]}'`.
- **`"color"` inside mapping objects crashes Infinity**
  (`Cannot read properties of undefined`). Keep mappings text-only.
- **Provisioned dashboards reject API writes**
  (`Cannot save provisioned dashboard`). Edit the file
  (`infra/monitoring/grafana/dashboards/health-board.json`), bump `version` to
  `int(time.time())`, and restart Grafana — provisioning overwrites the DB
  entry on the version bump.

## B. Workflow: OpenSpec, OpenProject, Deploy Dispatch

### B1. `openspec archive` skips main-spec sync

**Symptom:** `openspec archive <change>` reported `specsUpdated: false` and
`openspec/specs/` stayed empty.

**Root cause:** The CLI archives the change but does not synthesize main specs
when none exist.

**Fix:** Create `openspec/specs/{capability}/spec.md` from the archived delta
specs, strip the delta-only `status: proposed` frontmatter line, and use the
canonical spec structure (`## Purpose`, `### Requirement:` headings,
`#### Scenario:` blocks). Validate with `openspec validate --specs`; wrap
lines to the markdownlint limit so trunk `--ci` passes.

### B2. OpenProject "Done" = status 12 `Closed`

OpenProject has no literal "Done" status in this project. The terminal
completed state is `Closed` (id 12); QA state is `In testing` (id 9), and the
post-QA state is `Tested` (id 10). Move the work package via PATCH with the
current `lockVersion`.

### B3. Environment-specific deploy dispatch

- **Push to `dev`:** `package-deploy` auto-deploys DEV **and** promotes to QA
  in one run.
- **`workflow_dispatch`** with input `environment=prod` (ref `main`) deploys
  PROD only. Dispatch:
  `POST /repos/{owner}/{repo}/actions/workflows/package-deploy.yml/dispatches`
  with `{"ref": "main", "inputs": {"environment": "prod"}}` → HTTP 204.
- Release lineage: `v0.1.0-rc.1` (RC tag on the QA-approved commit) →
  `v0.1.0` (final annotated tag on the same commit) → main → PROD.

## C. Windows / Agent Tooling Gotchas

### C1. `git push --delete <branch>` hangs on Windows

**Symptom:** `git push gitea --delete <branch>` hangs indefinitely (credential
prompt), blocking branch cleanup.

**Fix:** Delete via the Gitea API instead (URL-encode the branch name):

```bash
curl -X DELETE -H "Authorization: token <token>" \
  "http://localhost:3000/api/v1/repos/<owner>/<repo>/branches/<branch>"
```

### C2. cp1252 console UnicodeEncodeError

**Symptom:** Python `print()` of eval/dashboard JSON containing emoji crashes
with `UnicodeEncodeError: 'charmap' codec can't encode character`.

**Fix:** Prefix the command with `PYTHONIOENCODING=utf-8`.

### C3. Complex bash quoting breaks agent tool calls

**Symptom:** Nested quotes/escapes in one-line shell commands fail JSON
parsing of the tool call (common with Python one-liners reading
client-tools.local.json).

**Fix:** Write the logic to a temp file under `.codex/` and run
`python .codex/_tmp_*.py`; delete the file after. Keep one-liners simple.

### C4. Gitea label payload needs label ids

Labels are set via `POST /issues/{n}/labels` with `{"labels": [<label_id>]}`
(object format, resolved from `GET /labels`), not bare label names.

### C5. Merged PRs leave remote branches

Gitea does not auto-delete PR source branches. After merge, delete the branch
locally and via the API (C1), then `git fetch gitea --prune`.

## Already-Captured Issues (pointers)

- **Trivy DB + React Router SCA chain** — `knowledge/lessons-learned/
ci-pipeline-fixes.md` §11 (Semgrep vendor → Trivy first-run → npm SCA).
- **Deploy failure chain** — `knowledge/lessons-learned/ci-pipeline-fixes.md`
  §12 (gitignore → bash heredoc → python -c → runtime, runs #14–#20).
- **Windows promptfoo @libsql blocker + deterministic fallback** —
  `knowledge/lessons-learned/eval-tooling-windows.md` (verified 46/46 for the
  v0.1.0 post-PROD eval).
