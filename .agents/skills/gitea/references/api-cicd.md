# Gitea REST API — Actions (CI) & packages

All examples use the `gitea` helper from [setup.md](setup.md#gitea-helper-function). Annotation column: `R` / `W` / `D`.

> Gitea Actions endpoints mirror GitHub Actions paths where possible, so most
> patterns transfer 1:1. Secrets are write-only — Gitea never returns secret
> values after upsert.

## Endpoint reference

| Verb | Path | Operation | A |
|---|---|---|---|
| GET | `/repos/{owner}/{repo}/actions/workflows` | List workflows | R |
| GET | `/repos/{owner}/{repo}/actions/workflows/{wf}` | Get workflow | R |
| POST | `/repos/{owner}/{repo}/actions/workflows/{wf}/dispatches` | Dispatch workflow | W |
| GET | `/repos/{owner}/{repo}/actions/runs` | List runs | R |
| GET | `/repos/{owner}/{repo}/actions/runs/{run_id}` | Get run | R |
| POST | `/repos/{owner}/{repo}/actions/runs/{run_id}/cancel` | Cancel run | W |
| POST | `/repos/{owner}/{repo}/actions/runs/{run_id}/rerun` | Rerun run | W |
| DELETE | `/repos/{owner}/{repo}/actions/runs/{run_id}` | Delete run | **D** |
| GET | `/repos/{owner}/{repo}/actions/runs/{run_id}/jobs` | List run jobs | R |
| GET | `/repos/{owner}/{repo}/actions/jobs` | List all repo jobs | R |
| GET | `/repos/{owner}/{repo}/actions/jobs/{job_id}` | Get job | R |
| GET | `/repos/{owner}/{repo}/actions/jobs/{job_id}/logs` | Download job logs (raw) | R |
| GET | `/repos/{owner}/{repo}/actions/secrets` | List repo secrets (names only) | R |
| PUT | `/repos/{owner}/{repo}/actions/secrets/{name}` | Upsert repo secret | **D** |
| DELETE | `/repos/{owner}/{repo}/actions/secrets/{name}` | Delete repo secret | **D** |
| GET | `/repos/{owner}/{repo}/actions/variables` | List repo variables | R |
| GET | `/repos/{owner}/{repo}/actions/variables/{name}` | Get repo variable | R |
| POST | `/repos/{owner}/{repo}/actions/variables/{name}` | Create repo variable | W |
| PUT | `/repos/{owner}/{repo}/actions/variables/{name}` | Update repo variable | W |
| DELETE | `/repos/{owner}/{repo}/actions/variables/{name}` | Delete repo variable | **D** |
| GET | `/orgs/{org}/actions/secrets` | List org secrets | R |
| PUT | `/orgs/{org}/actions/secrets/{name}` | Upsert org secret | **D** |
| DELETE | `/orgs/{org}/actions/secrets/{name}` | Delete org secret | **D** |
| GET | `/orgs/{org}/actions/variables` | List org variables | R |
| GET | `/orgs/{org}/actions/variables/{name}` | Get org variable | R |
| POST | `/orgs/{org}/actions/variables/{name}` | Create org variable | W |
| PUT | `/orgs/{org}/actions/variables/{name}` | Update org variable | W |
| DELETE | `/orgs/{org}/actions/variables/{name}` | Delete org variable | **D** |
| GET | `/packages/{owner}` | List packages owner-wide | R |
| GET | `/packages/{owner}/{type}/{name}` | List versions | R |
| GET | `/packages/{owner}/{type}/{name}/{version}` | Get version | R |
| GET | `/packages/{owner}/{type}/{name}/{version}/files` | List package files | R |
| DELETE | `/packages/{owner}/{type}/{name}/{version}` | Delete version | **D** |

## Table of Contents

- [Workflows](#workflows)
- [Workflow runs](#workflow-runs)
- [Jobs & logs](#jobs--logs)
- [Repo Actions secrets](#repo-actions-secrets)
- [Repo Actions variables](#repo-actions-variables)
- [Org Actions secrets](#org-actions-secrets)
- [Org Actions variables](#org-actions-variables)
- [Packages](#packages)

## Workflows

### List workflows · `GET /repos/{owner}/{repo}/actions/workflows?page=1&limit=30` · read-only

### Get workflow · `GET /repos/{owner}/{repo}/actions/workflows/{workflow_id}` · read-only

`workflow_id` may be the numeric ID or the workflow filename (e.g. `ci.yml`).

### Dispatch workflow · `POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches` · write

```bash
gitea POST /repos/{owner}/{repo}/actions/workflows/ci.yml/dispatches \
  -d '{"ref":"main","inputs":{"environment":"staging"}}'
# 204 on success (empty body)
```

Body: `ref` (req — branch or tag), `inputs` (opt — object matching `workflow_dispatch.inputs`).

## Workflow runs

### List runs · `GET /repos/{owner}/{repo}/actions/runs` · read-only

Query: `actor`, `branch`, `event`, `status` (`queued|in_progress|completed|failure|success|cancelled|skipped`),
`workflow_id`, `head_sha`, `page`, `limit`.

### Get run · `GET /repos/{owner}/{repo}/actions/runs/{run_id}` · read-only

### Cancel run · `POST /repos/{owner}/{repo}/actions/runs/{run_id}/cancel` · write

```bash
gitea POST "/repos/{owner}/{repo}/actions/runs/$RUN_ID/cancel"
# 202 on success (empty body)
```

### Rerun run · `POST /repos/{owner}/{repo}/actions/runs/{run_id}/rerun` · write

### Delete run · `DELETE /repos/{owner}/{repo}/actions/runs/{run_id}` · **DESTRUCTIVE**

## Jobs & logs

### List jobs for a run · `GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs?page=1&limit=30` · read-only

### List all jobs in repo · `GET /repos/{owner}/{repo}/actions/jobs?status=&page=1&limit=30` · read-only

### Get job · `GET /repos/{owner}/{repo}/actions/jobs/{job_id}` · read-only

### Download job logs · `GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs` · read-only

Returns **plain text**, not JSON — drop to raw curl (the `gitea` helper would try to `jq` the body):

```bash
# Stream to file
curl -sS "${AUTH[@]}" "$GITEA_URL/api/v1/repos/{owner}/{repo}/actions/jobs/$JOB_ID/logs" \
  -o ./job-$JOB_ID.log

# Tail preview (server has no native tail param)
curl -sS "${AUTH[@]}" "$GITEA_URL/api/v1/repos/{owner}/{repo}/actions/jobs/$JOB_ID/logs" | tail -n 200
```

## Repo Actions secrets

### List secrets · `GET /repos/{owner}/{repo}/actions/secrets?page=1&limit=30` · read-only

Returns names only — secret values are never returned.

### Upsert secret · `PUT /repos/{owner}/{repo}/actions/secrets/{secretname}` · **DESTRUCTIVE** (overwrites)

```bash
gitea PUT /repos/{owner}/{repo}/actions/secrets/MY_SECRET -d '{"data":"super-secret-value"}'
# 201 on create, 204 on update (empty body)
```

Body: `data` (req — secret value in plaintext; Gitea encrypts server-side).

### Delete secret · `DELETE /repos/{owner}/{repo}/actions/secrets/{secretname}` · **DESTRUCTIVE**

## Repo Actions variables

### List variables · `GET /repos/{owner}/{repo}/actions/variables?page=1&limit=30` · read-only

### Get variable · `GET /repos/{owner}/{repo}/actions/variables/{name}` · read-only

### Create variable · `POST /repos/{owner}/{repo}/actions/variables/{name}` · write

Body: `{"value":"...","description":"..."}`. 409 if it already exists; use update instead.

### Update variable · `PUT /repos/{owner}/{repo}/actions/variables/{name}` · write

Body: `{"value":"...","description":"..."}`.

### Delete variable · `DELETE /repos/{owner}/{repo}/actions/variables/{name}` · **DESTRUCTIVE**

## Org Actions secrets

### List · `GET /orgs/{org}/actions/secrets?page=1&limit=30` · read-only

### Upsert · `PUT /orgs/{org}/actions/secrets/{secretname}` · **DESTRUCTIVE**

Body: `{"data":"...","visibility":"all|private|selected","selected_repository_ids":[...]}`.

### Delete · `DELETE /orgs/{org}/actions/secrets/{secretname}` · **DESTRUCTIVE**

## Org Actions variables

### List · `GET /orgs/{org}/actions/variables?page=1&limit=30` · read-only

### Get · `GET /orgs/{org}/actions/variables/{name}` · read-only

### Create · `POST /orgs/{org}/actions/variables/{name}` · write

### Update · `PUT /orgs/{org}/actions/variables/{name}` · write

### Delete · `DELETE /orgs/{org}/actions/variables/{name}` · **DESTRUCTIVE**

## Packages

`{type}` is one of `container | npm | maven | pypi | cargo | generic | composer | conan | conda | helm | nuget |
rubygems | debian | rpm | alpine | swift | vagrant | chef`.

### List packages (owner-wide) · `GET /packages/{owner}?page=1&limit=30&type=&q=` · read-only

Query: `type` (filter by package type), `q` (search).

### List versions · `GET /packages/{owner}/{type}/{name}?page=1&limit=30` · read-only

`name` may contain `/`; URL-encode it (`%2F`).

### Get one version · `GET /packages/{owner}/{type}/{name}/{version}` · read-only

### List package files · `GET /packages/{owner}/{type}/{name}/{version}/files` · read-only

### Delete package version · `DELETE /packages/{owner}/{type}/{name}/{version}` · **DESTRUCTIVE**

```bash
NAME_ENC=$(jq -rn --arg n '@myorg/lib' '$n | @uri')
gitea DELETE "/packages/{owner}/npm/$NAME_ENC/1.2.3"
# 204 on success (empty body)
```
