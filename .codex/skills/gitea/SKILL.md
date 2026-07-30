---
name: gitea
description: "Operate a Gitea instance via its REST API at /api/v1/... with curl. FORCED ROUTING — use this skill for any repository whose git remote host is not github.com: derive the candidate HTTPS base URL from the remote host, probe /api/v1/version, then call the REST endpoints directly."
---

# Gitea (REST API)

Operate Gitea by sending HTTP requests to `$GITEA_URL/api/v1/...` authenticated
by `$GITEA_TOKEN`. This skill does NOT depend on any MCP server — every
operation is a direct `curl` call.

Keep this entry file small. Load only the reference pack the current turn needs.

## Always-On Rules

0. **Forced forge routing.** Before any forge work, run `git remote get-url origin` and parse the host. If the host is `github.com`, this skill does not apply — use `gh`, including for internal GitHub organizations. For any other host, treat it as a Gitea candidate: derive `https://<host>` as the probe base URL, run `curl -fsS --max-time 5 "https://<host>/api/v1/version"`, and use this skill only if HTTP 200 returns JSON with a `version` field. If the probe fails or times out, ask the user; do not guess another forge.
1. **Resolve `$GITEA_URL` + `$GITEA_TOKEN` from named env pairs, not from the user.** Each instance is exported as `GITEA_<ALIAS>_URL` + `GITEA_<ALIAS>_TOKEN` (e.g. `GITEA_ORGA_URL` + `GITEA_ORGA_TOKEN`). Call `gitea_auto` (defined in [setup.md](references/setup.md#instance-selection-multi-gitea)) to auto-pick the pair whose URL host matches the current repo's `origin`; falls back to the unaliased `GITEA_URL`/`GITEA_TOKEN`, then to gitea-mcp legacy `GITEA_HOST`/`GITEA_ACCESS_TOKEN`, then asks the user. `$GITEA_URL` is always the base URL **without** the `/api` suffix.
2. Send `Authorization: token $GITEA_TOKEN` on every request. Never put the token in the query string (`?token=`) — it would be logged.
3. Prefer `curl -s` piped to `jq` so results are easy to inspect. Always include `-o /dev/null -w '%{http_code}\n'` (or `--fail-with-body`) when verifying success on write/delete calls — Gitea returns success bodies on 2xx and a `{ "message": "...", "url": "..." }` error envelope on 4xx/5xx.
4. **Respect destructiveness.** Any `DELETE` against `/branches`, `/contents`, `/releases`, `/tags`, labels, milestones, packages, secrets, variables, or wiki pages is **irreversible**. State exactly what will be removed and confirm with the user unless explicitly authorized.
5. **Pagination**: most list endpoints take `?page=N&limit=M` (default `page=1`, `limit=30`, server max usually 50). A few older endpoints accept `per_page=` as an alias. Loop pages until the response is empty or `Link: rel="next"` is absent.
6. `PUT /repos/{owner}/{repo}/contents/{path}` (create/update file): `content` must be **base64-encoded**. Omit `sha` to create; pass the current file `sha` to update.
7. Endpoint responses are the resource directly — Gitea does **not** wrap them in `{ success, data }`. Errors come back with HTTP 4xx/5xx plus `{ "message": "...", "url": "..." }`.

## Core Workflow

### Environment

Credentials live in **named pairs** — `GITEA_<ALIAS>_URL` + `GITEA_<ALIAS>_TOKEN` — one pair per Gitea instance. `gitea_auto` matches the current repo's `origin` host to one of the URLs and loads that pair into `$GITEA_URL` + `$GITEA_TOKEN`. Full discovery order and inline helper code: [setup.md](references/setup.md#instance-selection-multi-gitea).

```bash
# Example user-side ~/.bashrc:
#   export GITEA_ORGA_URL=https://git.orga.com    GITEA_ORGA_TOKEN=...
#   export GITEA_ORGB_URL=https://git.orgb.local  GITEA_ORGB_TOKEN=...
#   export GITEA_URL=https://gitea.com            GITEA_TOKEN=...

# Per-session bootstrap (define the helpers from setup.md or source them):
gitea_list_aliases() { env | grep -oE '^GITEA_[A-Z0-9][A-Z0-9_]*_URL=' | sed -E 's/^GITEA_(.+)_URL=$/\1/' | sort -u; }
gitea_use() { local a="$1" u="GITEA_${1}_URL" t="GITEA_${1}_TOKEN" f="GITEA_${1}_TOKEN_FILE"
  [ -n "${!u:-}" ] || { echo "no $u" >&2; return 1; }
  if   [ -n "${!t:-}" ];                   then GITEA_TOKEN="${!t}"
  elif [ -n "${!f:-}" ] && [ -r "${!f}" ]; then GITEA_TOKEN="$(cat "${!f}")"
  else echo "no $t or ${t}_FILE" >&2; return 1; fi
  GITEA_URL="${!u}"; export GITEA_URL GITEA_TOKEN; }
gitea_auto() { local src o h a u uh
  if [ -n "${GITEA_URL:-}" ]; then src="$GITEA_URL"
  else o=$(git remote get-url origin 2>/dev/null) || o=""; src="$o"; fi
  case "$src" in
    git@*:*)        h="${src#git@}";   h="${h%%:*}";;
    ssh://*)        h="${src#ssh://}"; h="${h#*@}"; h="${h%%/*}"; h="${h%%:*}";;
    http*://*)      h="${src#http*://}"; h="${h%%/*}"; h="${h%%:*}";;
  esac
  if [ -n "${h:-}" ]; then
    for a in $(gitea_list_aliases); do
      u="GITEA_${a}_URL"; uh="${!u#http*://}"; uh="${uh%%/*}"; uh="${uh%%:*}"
      [ "$h" = "$uh" ] && { gitea_use "$a"; return 0; }
    done
  fi
  [ -n "${GITEA_URL:-}" ] && [ -n "${GITEA_TOKEN:-}" ] && { export GITEA_URL GITEA_TOKEN; return 0; }
  [ -n "${GITEA_HOST:-}" ] && [ -n "${GITEA_ACCESS_TOKEN:-}" ] && {
    GITEA_URL="$GITEA_HOST"; GITEA_TOKEN="$GITEA_ACCESS_TOKEN"; export GITEA_URL GITEA_TOKEN; return 0; }
  return 1; }

gitea_auto || { echo "no Gitea credentials (set GITEA_<ALIAS>_URL + GITEA_<ALIAS>_TOKEN, or GITEA_URL + GITEA_TOKEN)" >&2; return 1; }

AUTH=(-H "Authorization: token $GITEA_TOKEN")
JSON=(-H 'Content-Type: application/json')
```

Two usage patterns:

- **Inside a repo**, no env set: `gitea_auto` parses `origin` and finds the alias whose `GITEA_<ALIAS>_URL` host matches.
- **Outside a repo, or targeting a different instance**: `export GITEA_URL=https://git.aaa.com` first, then `gitea_auto` will match `git.aaa.com` against the configured aliases and pull the right token. No need to remember which alias corresponds to which host.

Hard override: `gitea_use ORGA` activates the `ORGA` pair regardless of URL.

### `gitea` helper

After resolving env, source the `gitea` wrapper from
[setup.md](references/setup.md#gitea-helper-function). Every `api-*.md`
example assumes it is in scope:

```bash
gitea GET    /version                                          # health
gitea GET    /user                                             # token identity
gitea GET   '/repos/foo/bar/issues?state=closed&limit=50'      # list with query
gitea POST   /repos/foo/bar/issues   -d '{"title":"x"}'        # write
gitea DELETE /repos/foo/bar/releases/42                        # destructive
```

The helper auto-injects `$GITEA_URL/api/v1`, the auth header, and
`Content-Type: application/json`; surfaces HTTP 4xx/5xx with the
`{message, url}` envelope on stderr and returns 1; pretty-prints success
bodies via `jq`.

### Single issue create + comment (canonical write flow)

```bash
ISSUE=$(gitea POST /repos/{owner}/{repo}/issues \
          -d '{"title":"fix auth bug","body":"Steps to reproduce..."}') || return 1
NUM=$(echo "$ISSUE" | jq -r '.number')

gitea POST "/repos/{owner}/{repo}/issues/$NUM/comments" \
  -d '{"body":"PR will land tomorrow"}'
```

## Reference Packs

Load only the pack that covers the task at hand. Each pack lists every
endpoint with method, path, key params, and a curl example.

- `references/setup.md`
  Env vars, auth, /api/v1/version probe, PAT scopes, pagination, error envelope, common gotchas.
- `references/api-repo.md` — **~23 operations**
  Repos & forks, branches, tags, commits, repo tree, file contents (read / create / update / delete), releases.
- `references/api-issues-prs.md` — **issue + PR endpoints**
  `list/get/create/update issues`, comments, labels-on-issue; PR `list/get/diff/files/status/reviews/create/update/close/merge/update-branch/add-reviewers`; review submit/dismiss.
- `references/api-project.md` — **labels, milestones, time tracking, wiki**
  Repo & org labels (CRUD), milestones (CRUD), stopwatches + tracked time entries, wiki pages + revisions.
- `references/api-discovery.md` — **users, orgs, search, notifications, version**
  `/user`, `/user/orgs`, `/users/search`, `/orgs/{org}/teams/search`, `/repos/search`, `/repos/issues/search`, notifications list/get/mark-read, `/version`.
- `references/api-cicd.md` — **actions & packages**
  Workflows + runs + jobs + logs, dispatch/cancel/rerun runs, repo/org Actions secrets + variables CRUD, packages list/versions/get/delete.

## Quick Routing

- Connection refused, 401, 403, missing token, PAT scopes: `references/setup.md`.
- Clone / fork / create repo, read or commit a file, branch / tag, release: `references/api-repo.md`.
- File issues, comment, manage PRs, request/submit reviews, merge: `references/api-issues-prs.md`.
- Labels, milestones, time tracking, wiki pages: `references/api-project.md`.
- "Who am I", search repos/users/issues, org list, notifications: `references/api-discovery.md`.
- CI runs/workflows, secrets/variables, packages: `references/api-cicd.md`.

## When to Use Another Forge

- `git remote get-url origin` host is `github.com` -> use `gh` instead; this skill does not apply.
- `/api/v1/version` probe fails -> the host is probably not a Gitea instance. Ask the user; do not guess another forge.
