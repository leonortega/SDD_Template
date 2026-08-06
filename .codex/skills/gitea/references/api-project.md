# Gitea REST API — Labels, milestones, time tracking, wiki

All examples use the `gitea` helper from [setup.md](setup.md#gitea-helper-function). Annotation column: `R` / `W` / `D`.

## Endpoint reference

| Verb | Path | Operation | A |
|---|---|---|---|
| GET | `/repos/{owner}/{repo}/labels` | List repo labels | R |
| GET | `/repos/{owner}/{repo}/labels/{id}` | Get repo label | R |
| POST | `/repos/{owner}/{repo}/labels` | Create repo label | W |
| PATCH | `/repos/{owner}/{repo}/labels/{id}` | Edit repo label | W |
| DELETE | `/repos/{owner}/{repo}/labels/{id}` | Delete repo label | **D** |
| GET | `/orgs/{org}/labels` | List org labels | R |
| GET | `/orgs/{org}/labels/{id}` | Get org label | R |
| POST | `/orgs/{org}/labels` | Create org label | W |
| PATCH | `/orgs/{org}/labels/{id}` | Edit org label | W |
| DELETE | `/orgs/{org}/labels/{id}` | Delete org label | **D** |
| GET | `/repos/{owner}/{repo}/milestones` | List milestones | R |
| GET | `/repos/{owner}/{repo}/milestones/{id}` | Get milestone | R |
| POST | `/repos/{owner}/{repo}/milestones` | Create milestone | W |
| PATCH | `/repos/{owner}/{repo}/milestones/{id}` | Edit milestone | W |
| DELETE | `/repos/{owner}/{repo}/milestones/{id}` | Delete milestone | **D** |
| GET | `/repos/{owner}/{repo}/issues/{idx}/times` | List issue times | R |
| GET | `/repos/{owner}/{repo}/times` | List repo times | R |
| POST | `/repos/{owner}/{repo}/issues/{idx}/times` | Add time entry | W |
| DELETE | `/repos/{owner}/{repo}/issues/{idx}/times/{id}` | Delete time entry | **D** |
| DELETE | `/repos/{owner}/{repo}/issues/{idx}/times` | Reset issue time | **D** |
| GET | `/user/times` | My tracked times | R |
| GET | `/user/stopwatches` | My stopwatches | R |
| POST | `/repos/{owner}/{repo}/issues/{idx}/stopwatch/start` | Start stopwatch | W |
| POST | `/repos/{owner}/{repo}/issues/{idx}/stopwatch/stop` | Stop stopwatch | W |
| DELETE | `/repos/{owner}/{repo}/issues/{idx}/stopwatch/delete` | Discard stopwatch | **D** |
| GET | `/repos/{owner}/{repo}/wiki/pages` | List wiki pages | R |
| GET | `/repos/{owner}/{repo}/wiki/page/{name}` | Get wiki page | R |
| GET | `/repos/{owner}/{repo}/wiki/revisions/{name}` | Page revisions | R |
| POST | `/repos/{owner}/{repo}/wiki/new` | Create wiki page | W |
| PATCH | `/repos/{owner}/{repo}/wiki/page/{name}` | Edit wiki page | W |
| DELETE | `/repos/{owner}/{repo}/wiki/page/{name}` | Delete wiki page | **D** |

## Table of Contents

- [Repo labels](#repo-labels)
- [Org labels](#org-labels)
- [Milestones](#milestones)
- [Time tracking](#time-tracking)
- [Wiki](#wiki)

## Repo labels

### List · `GET /repos/{owner}/{repo}/labels?page=1&limit=30` · read-only

### Get one · `GET /repos/{owner}/{repo}/labels/{id}` · read-only

### Create · `POST /repos/{owner}/{repo}/labels` · write

```bash
gitea POST /repos/{owner}/{repo}/labels -d '{"name":"bug","color":"#ee0701","description":"Something is broken"}'
```

Body: `name` (req), `color` (req, `#RRGGBB`), `description` (opt), `is_archived` (opt, repo-only).

### Edit · `PATCH /repos/{owner}/{repo}/labels/{id}` · write

Body fields (any subset): `name`, `color`, `description`, `is_archived`.

### Delete · `DELETE /repos/{owner}/{repo}/labels/{id}` · **DESTRUCTIVE**

## Org labels

### List · `GET /orgs/{org}/labels?page=1&limit=30` · read-only

### Get one · `GET /orgs/{org}/labels/{id}` · read-only

### Create · `POST /orgs/{org}/labels` · write

Same body as repo labels plus `exclusive` (boolean, org-only — only one label of an exclusive group may be applied at
once).

### Edit · `PATCH /orgs/{org}/labels/{id}` · write

### Delete · `DELETE /orgs/{org}/labels/{id}` · **DESTRUCTIVE**

## Milestones

### List · `GET /repos/{owner}/{repo}/milestones?state=open|closed|all&name=&page=1&limit=30` · read-only

### Get one · `GET /repos/{owner}/{repo}/milestones/{id}` · read-only

### Create · `POST /repos/{owner}/{repo}/milestones` · write

```bash
gitea POST /repos/{owner}/{repo}/milestones \
  -d '{"title":"v1.0","description":"first stable","due_on":"2026-03-01T00:00:00Z","state":"open"}'
```

Body: `title` (req), `description`, `due_on` (ISO 8601), `state` (`open|closed`, default `open`).

### Edit · `PATCH /repos/{owner}/{repo}/milestones/{id}` · write

Body fields (any subset): `title`, `description`, `due_on`, `state`.

### Delete · `DELETE /repos/{owner}/{repo}/milestones/{id}` · **DESTRUCTIVE**

## Time tracking

Some endpoints require the repo to have time tracking enabled (`has_issues` + repo setting "Enable Timetracker").

### List tracked time for an issue · `GET /repos/{owner}/{repo}/issues/{idx}/times` · read-only

### List tracked time for a repo · `GET /repos/{owner}/{repo}/times?page=1&limit=30` · read-only

### Add time to an issue · `POST /repos/{owner}/{repo}/issues/{idx}/times` · write

```bash
gitea POST "/repos/{owner}/{repo}/issues/$IDX/times" \
  -d '{"time":3600,"created":"2025-01-15T10:30:00Z","user_name":"alice"}'
```

Body: `time` (req — seconds), `created` (opt — ISO 8601, default now), `user_name` (opt — admin only).

### Delete a time entry · `DELETE /repos/{owner}/{repo}/issues/{idx}/times/{id}` · **DESTRUCTIVE**

### Reset all time on an issue · `DELETE /repos/{owner}/{repo}/issues/{idx}/times` · **DESTRUCTIVE**

### My tracked times · `GET /user/times?page=1&limit=30` · read-only

### My stopwatches · `GET /user/stopwatches` · read-only

### Start stopwatch · `POST /repos/{owner}/{repo}/issues/{idx}/stopwatch/start` · write

### Stop stopwatch (creates a time entry) · `POST /repos/{owner}/{repo}/issues/{idx}/stopwatch/stop` · write

### Delete stopwatch (without saving) · `DELETE /repos/{owner}/{repo}/issues/{idx}/stopwatch/delete` · **DESTRUCTIVE**

## Wiki

Repos must have `has_wiki: true`.

### List pages · `GET /repos/{owner}/{repo}/wiki/pages?page=1&limit=30` · read-only

### Get page · `GET /repos/{owner}/{repo}/wiki/page/{pageName}` · read-only

Returns `{ title, content_base64, commit_count, sidebar, footer, ... }`. Decode `content_base64` with `base64 -d`.

### Get page revisions · `GET /repos/{owner}/{repo}/wiki/revisions/{pageName}?page=1&limit=30` · read-only

### Create page · `POST /repos/{owner}/{repo}/wiki/new` · write

```bash
CONTENT_B64=$(printf '## Hello\n' | base64 -w0)
gitea POST /repos/{owner}/{repo}/wiki/new -d "$(jq -n --arg c "$CONTENT_B64" \
  '{title:"Hello",content_base64:$c,message:"docs: add hello page"}')"
```

Body: `title` (req), `content_base64` (req — base64), `message` (commit message, opt).

### Edit page · `PATCH /repos/{owner}/{repo}/wiki/page/{pageName}` · write

Body: `title`, `content_base64`, `message` (any subset).

### Delete page · `DELETE /repos/{owner}/{repo}/wiki/page/{pageName}` · **DESTRUCTIVE**
