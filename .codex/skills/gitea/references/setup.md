# Gitea REST API — setup, auth, probing, pagination, errors

This skill calls the Gitea REST API directly with `curl`. There is **no MCP
server dependency**. Each operation is documented in the `api-*.md` reference
packs as `METHOD /api/v1/...` with a curl example.

## Table of Contents

- [Environment](#environment)
- [Instance selection (multi-Gitea)](#instance-selection-multi-gitea)
- [`gitea` helper function](#gitea-helper-function)
- [Authentication](#authentication)
- [Probing the instance](#probing-the-instance)
- [Personal access token (PAT) scopes](#personal-access-token-pat-scopes)
- [Response shapes](#response-shapes)
- [Pagination](#pagination)
- [Common gotchas](#common-gotchas)
- [TLS, proxies, and self-signed certs](#tls-proxies-and-self-signed-certs)

## Environment

Two values must end up in scope before any call: `$GITEA_URL` (base URL **without** the `/api` suffix, e.g. `https://git.example.com`) and `$GITEA_TOKEN` (PAT for that URL). The skill discovers them from the environment using **named pairs**, then constructs every endpoint as `$GITEA_URL/api/v1/...`.

```bash
# Single instance:
export GITEA_URL=https://git.example.com
export GITEA_TOKEN="$(pass show gitea/example)"

# Multiple instances (named pairs — see next section):
export GITEA_ORGA_URL=https://git.orga.com     GITEA_ORGA_TOKEN="..."
export GITEA_ORGB_URL=https://git.orgb.local   GITEA_ORGB_TOKEN="..."

# Activate (auto-pick by current repo's origin, else fall back to GITEA_URL/GITEA_TOKEN):
gitea_auto || { echo "no Gitea credentials in env" >&2; return 1; }

AUTH=(-H "Authorization: token $GITEA_TOKEN")
JSON=(-H 'Content-Type: application/json')
```

## Instance selection (multi-Gitea)

A single shell often needs credentials for several Gitea instances (one per org, one per environment, etc.). The skill models this as **named pairs**: each instance gets an alias `<X>`, exported as `GITEA_<X>_URL` + `GITEA_<X>_TOKEN`. At call time, the right pair is loaded into `$GITEA_URL` + `$GITEA_TOKEN`.

### Convention

The env-var template is **`GITEA_<ALIAS>_URL`** + **`GITEA_<ALIAS>_TOKEN`**. `<ALIAS>` is user-chosen (uppercase letters, digits, underscores; non-empty). The URL and TOKEN of one instance must share the exact same `<ALIAS>`. `GITEA_URL` + `GITEA_TOKEN` (no alias segment) is the single-instance fallback used when no named pair matches.

```bash
export GITEA_ORGA_URL=https://git.orga.com
export GITEA_ORGA_TOKEN="$(pass show gitea/orga)"
export GITEA_ORGB_URL=https://git.orgb.local:3000
export GITEA_ORGB_TOKEN_FILE=/run/secrets/gitea-orgb-token

export GITEA_URL=https://gitea.com
export GITEA_TOKEN="$(pass show gitea/public)"
```

- Discovery regex: `^GITEA_[A-Z0-9][A-Z0-9_]*_URL=` — the captured middle group is the alias.
- `_TOKEN_FILE` is accepted for any alias when `_TOKEN` is not exported directly.

### Selection helpers

Drop these into the shell once (also inlined in SKILL.md's `Environment` block):

```bash
# Print all aliases that have a GITEA_<ALIAS>_URL set, one per line.
gitea_list_aliases() {
  env | grep -oE '^GITEA_[A-Z0-9][A-Z0-9_]*_URL=' \
      | sed -E 's/^GITEA_(.+)_URL=$/\1/' | sort -u
}

# Activate a named alias: load its URL + token into GITEA_URL/GITEA_TOKEN.
gitea_use() {
  local a="$1" u="GITEA_${1}_URL" t="GITEA_${1}_TOKEN" f="GITEA_${1}_TOKEN_FILE"
  [ -n "${!u:-}" ] || { echo "no $u in env" >&2; return 1; }
  if   [ -n "${!t:-}" ];                              then GITEA_TOKEN="${!t}"
  elif [ -n "${!f:-}" ] && [ -r "${!f}" ];            then GITEA_TOKEN="$(cat "${!f}")"
  else echo "no $t or ${t}_FILE in env" >&2; return 1
  fi
  GITEA_URL="${!u}"
  export GITEA_URL GITEA_TOKEN
}

# Resolve a Gitea instance by matching a URL host against the configured aliases.
# Source URL priority: explicit $GITEA_URL > current repo's `git remote origin`.
# Lookup: scan GITEA_<ALIAS>_URL pairs for a host match, then load that alias's token.
# Fallbacks: unaliased GITEA_URL/GITEA_TOKEN -> legacy GITEA_HOST/GITEA_ACCESS_TOKEN.
gitea_auto() {
  local src o h a u uh
  if [ -n "${GITEA_URL:-}" ]; then
    src="$GITEA_URL"                                  # explicit target wins
  else
    o=$(git remote get-url origin 2>/dev/null) || o=""
    src="$o"                                          # else fall back to repo origin
  fi
  case "$src" in
    git@*:*)        h="${src#git@}";   h="${h%%:*}";;
    ssh://*)        h="${src#ssh://}"; h="${h#*@}"; h="${h%%/*}"; h="${h%%:*}";;
    http*://*)      h="${src#http*://}"; h="${h%%/*}"; h="${h%%:*}";;
    *)              h="";;
  esac
  # 1. Match host against any configured alias
  if [ -n "$h" ]; then
    for a in $(gitea_list_aliases); do
      u="GITEA_${a}_URL"; uh="${!u#http*://}"; uh="${uh%%/*}"; uh="${uh%%:*}"
      if [ "$h" = "$uh" ]; then gitea_use "$a"; return 0; fi
    done
  fi
  # 2. Unaliased default pair (only valid if BOTH URL and TOKEN are set)
  if [ -n "${GITEA_URL:-}" ] && [ -n "${GITEA_TOKEN:-}" ]; then
    export GITEA_URL GITEA_TOKEN; return 0
  fi
  # 3. gitea-mcp legacy pair
  if [ -n "${GITEA_HOST:-}" ] && [ -n "${GITEA_ACCESS_TOKEN:-}" ]; then
    GITEA_URL="$GITEA_HOST"; GITEA_TOKEN="$GITEA_ACCESS_TOKEN"
    export GITEA_URL GITEA_TOKEN; return 0
  fi
  return 1
}
```

### Selection order (resolved by `gitea_auto`)

`gitea_auto` first determines a **source URL** to match against, then scans the named pairs by **host**:

| Step | What happens | Example |
|---|---|---|
| 0 | Source URL = explicit `$GITEA_URL` if set, else `git remote get-url origin`. | `GITEA_URL=https://git.aaa.com` -> source = `git.aaa.com`. |
| 1 | **Match host against every configured `GITEA_<ALIAS>_URL`.** First match wins; `gitea_use ALIAS` loads its URL + token. | `GITEA_ORGA_URL=https://git.aaa.com` -> alias `ORGA` matches -> `GITEA_TOKEN` set from `GITEA_ORGA_TOKEN`. |
| 2 | No host match? Use **unaliased default**: `GITEA_URL` + `GITEA_TOKEN` (both must be set explicitly by the user). | Single-instance shell with `GITEA_URL=...` + `GITEA_TOKEN=...`. |
| 3 | Still nothing? Use **gitea-mcp legacy** pair: `GITEA_HOST` + `GITEA_ACCESS_TOKEN`. | Migrating from an older gitea-mcp config without renaming env vars. |
| 4 | Nothing found -> ask the user; recommend they add a named pair so future sessions auto-resolve. | — |

Two ways to use it:

1. **No explicit URL — auto from repo origin.** Common case inside a checked-out repo. `gitea_auto` parses the remote URL and finds the matching alias.
2. **Explicit URL, lookup token.** User sets `GITEA_URL=https://git.aaa.com` and calls `gitea_auto`; the matching `GITEA_<ALIAS>_URL` is found by host comparison and its `_TOKEN` is loaded. No need to remember which alias maps to which host.

Manual override at any time: `gitea_use ORGA` (sets the active pair without auto-detect).

### Verifying resolution

After `gitea_auto`, confirm before any write — never echo the full token:

```bash
echo "host:  $(printf '%s' "$GITEA_URL" | sed -E 's#^https?://##; s#/.*##')"
echo "token: $(printf '%s' "$GITEA_TOKEN" | head -c 6)... ($(printf '%s' "$GITEA_TOKEN" | wc -c) chars)"
gitea GET /user | jq '{login, full_name}'
```

## `gitea` helper function

The `api-*.md` reference packs use a one-line `gitea` wrapper instead of repeating the full curl invocation. Define it once per shell:

```bash
gitea() {
  local method="$1" path="$2"; shift 2
  local url="${GITEA_URL}/api/v1${path}"
  local tmp; tmp=$(mktemp)
  local http
  http=$(curl -sS -o "$tmp" -w '%{http_code}' \
    -H "Authorization: token $GITEA_TOKEN" \
    -H 'Content-Type: application/json' \
    -X "$method" "$@" "$url")
  if [ "$http" -ge 400 ]; then
    >&2 echo "HTTP $http for $method $path"
    >&2 jq . "$tmp" 2>/dev/null || >&2 cat "$tmp"
    rm -f "$tmp"; return 1
  fi
  [ -s "$tmp" ] && { jq . "$tmp" 2>/dev/null || cat "$tmp"; }
  rm -f "$tmp"
}
```

### Usage

```bash
gitea GET    /repos/foo/bar/issues
gitea GET   '/repos/foo/bar/issues?state=closed&page=2&limit=50'
gitea POST   /repos/foo/bar/issues   -d '{"title":"x","body":"y"}'
gitea PATCH  /repos/foo/bar/issues/3 -d '{"state":"closed"}'
gitea DELETE /repos/foo/bar/releases/42
```

### Properties

- Method and path are positional; everything after is passed through to curl unchanged (`-d`, `-F`, `--data-binary`, extra `-H`, `--cacert`, etc.).
- The helper always sends `Content-Type: application/json`. For multipart uploads, use raw `curl` with `-F` so curl can generate the multipart boundary.
- Success bodies are pretty-printed via `jq`; empty 204 bodies are silently fine.
- HTTP 4xx/5xx: the function writes `HTTP <code> for <method> <path>` + the `{message, url}` envelope to **stderr** and returns 1. Combine with `||` for failure handling, or capture stdout for the success payload.
- Body capture for multi-step flows:
  ```bash
  ISSUE=$(gitea POST /repos/foo/bar/issues -d '{"title":"new"}') || return 1
  NUM=$(echo "$ISSUE" | jq -r '.number')
  ```
- For **raw bodies** (downloading job logs, PR diffs, file content), use `--output -` and skip jq:
  ```bash
  gitea GET /repos/foo/bar/pulls/3.diff --output - 2>/dev/null > pr.diff
  # or skip the helper entirely; raw text isn't valid JSON.
  curl -sS "${AUTH[@]}" "$GITEA_URL/api/v1/repos/foo/bar/pulls/3.diff" > pr.diff
  ```

When an example in the `api-*.md` packs uses `gitea ...`, it assumes this function and the resolved env are already in scope. Examples that drop to raw `curl` are doing so deliberately (multipart upload, base64-heavy payloads, HTTP-status capture, raw text response).

## Authentication

Send the token as a header on every request:

```bash
curl -s -H "Authorization: token $GITEA_TOKEN" "$GITEA_URL/api/v1/user" | jq
```

Accepted equivalents:

| Form | Example | Notes |
|---|---|---|
| `token <PAT>` (preferred) | `-H "Authorization: token abc..."` | Recommended; works on all Gitea versions. |
| `Bearer <PAT>` | `-H "Authorization: Bearer abc..."` | Works on recent Gitea; identical effect. |
| HTTP Basic with PAT as password | `-u "<username>:<PAT>"` | Works but unusual; reserve for tools that only speak Basic. |
| `?token=<PAT>` query param | `?token=abc...` | **Avoid.** Tokens leak into access logs and shell history. |

Never echo `$GITEA_TOKEN` to stdout. Mask in any logging.

## Probing the instance

Confirm an unknown non-`github.com` host is actually Gitea before driving any
operation. For git remotes, discard SSH ports and construct the probe URL as
`https://<host>/api/v1/version`; a custom web port cannot be inferred from an
SSH remote and must be known separately.

```bash
curl -fsS --max-time 5 "$GITEA_URL/api/v1/version" | jq
# -> { "version": "1.23.x" } on success
```

If the call returns non-2xx, times out, or returns JSON without a `version` field, the host is **not** a Gitea instance — stop and ask the user. Do not silently fall back to another forge.

After a successful probe, confirm the token resolves to the expected user:

```bash
curl -s "${AUTH[@]}" "$GITEA_URL/api/v1/user" | jq '{login, full_name, email}'
```

If this returns `401 Unauthorized`, the token is wrong/expired. If it returns `403 Forbidden` on subsequent writes, the token lacks the required scope (see below).

## Personal access token (PAT) scopes

Gitea PAT scopes are coarse. The most commonly needed:

| Scope | Covers |
|---|---|
| `read:user` | `/user`, `/users/{u}` |
| `read:repository` | Repo read, file read, branches/tags list, releases list |
| `write:repository` | Create/fork repo, push files, branches, tags, releases |
| `read:issue` | Issues read |
| `write:issue` | Create/update issues, comments, labels-on-issue, milestones-on-issue |
| `read:organization` | Org info, teams, org repos |
| `write:organization` | Create org labels, milestones, secrets/variables, team membership |
| `read:notification` | Notification list/thread |
| `write:notification` | Mark notifications read |
| `read:package` / `write:package` | Package registry read / delete |
| `read:admin` / `write:admin` | Site-admin only operations |

A scope/permission error from Gitea surfaces as `403` with `{"message":"...","url":"..."}`. **Report it; the fix is a wider-scoped token, not a retry.**

## Response shapes

Gitea returns the resource directly — there is **no** `{success, data}` wrapper.

- **Success (2xx)**: the resource JSON (or empty body for 204 No Content).
- **Failure (4xx/5xx)**: `{ "message": "...", "url": "..." }` plus the HTTP status. Some 422 responses also include `errors: [...]`.

When verifying a write, capture the HTTP status:

```bash
HTTP=$(curl -s -o /tmp/body.json -w '%{http_code}' "${AUTH[@]}" "${JSON[@]}" -X POST \
  -d '{...}' "$GITEA_URL/api/v1/...")
if [ "$HTTP" -ge 400 ]; then
  jq < /tmp/body.json   # show the {message, url} envelope
  exit 1
fi
jq < /tmp/body.json
```

Or use `--fail-with-body` so curl exits non-zero on 4xx/5xx but still prints the body.

## Pagination

Standard list endpoints accept:

| Param | Default | Notes |
|---|---|---|
| `page` | `1` | 1-indexed |
| `limit` | `30` (usually) | Capped server-side (commonly 50). A few older endpoints accept `per_page` as alias. |

To enumerate fully:

```bash
PAGE=1
while :; do
  RESP=$(curl -s "${AUTH[@]}" "$GITEA_URL/api/v1/repos/{owner}/{repo}/issues?state=all&page=$PAGE&limit=50")
  COUNT=$(echo "$RESP" | jq 'length')
  [ "$COUNT" -eq 0 ] && break
  echo "$RESP" | jq -c '.[]'
  PAGE=$((PAGE + 1))
done
```

Alternative: check the `Link` response header for `rel="next"`:

```bash
curl -s -I "${AUTH[@]}" "$GITEA_URL/api/v1/repos/{owner}/{repo}/issues?page=1&limit=50" | grep -i '^link:'
```

If absent, you are on the last page.

## Common gotchas

- **`/api` vs root.** `$GITEA_URL` is the bare host (`https://git.example.com`). Endpoints are `/api/v1/...`. Concatenating `https://git.example.com/api/api/v1/...` produces 404.
- **File contents are base64.** `PUT /repos/.../contents/{path}` requires `content` base64-encoded. Read-back via `GET` also returns `content` base64-encoded; decode with `jq -r .content | base64 -d`.
- **Create vs update file.** `PUT /repos/.../contents/{path}` creates when `sha` is omitted, updates when the current file `sha` is passed. Wrong `sha` -> 409 Conflict.
- **Branch name in URL** must be URL-encoded when it contains `/` (e.g. `feature%2Fnewui`).
- **Soft delete.** `DELETE /repos/{owner}/{repo}` moves the repo to trash for some configurations. Confirm with the user; recovery is admin-only.
- **Empty arrays vs missing.** Gitea returns `[]` for empty list endpoints (not 404). 404 means the resource path itself is wrong.
- **Time formats.** Date filters (`since`, `before`, `due_on`, `deadline`) use ISO 8601 with timezone, e.g. `2025-01-15T10:30:00Z`.
- **Issue numbers vs IDs.** Use the per-repo `number` (visible in the URL) for `/issues/{idx}` paths. Internal `id` is global and only relevant for cross-repo APIs.
- **Pull request endpoints reuse issue paths for comments.** Comments on a PR are posted via `/issues/{idx}/comments`, not `/pulls/{idx}/comments` (which is for review comments).

## TLS, proxies, and self-signed certs

For self-signed or internal CA hosts, the recommended approach is to install the CA into the system trust store. As a curl-local override:

```bash
curl --cacert /path/to/internal-ca.pem "${AUTH[@]}" "$GITEA_URL/api/v1/version"
```

Only as a last resort, `curl -k` (insecure, skip verification) — record why in any committed config.

Behind a corporate proxy, set `HTTPS_PROXY` / `NO_PROXY` in the shell environment; curl honors both.
