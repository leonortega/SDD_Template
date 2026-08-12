# Gitea REST API — Repositories, files, branches, tags, commits, releases

All examples use the `gitea` helper from [setup.md](setup.md#gitea-helper-function) (auto-injects URL + auth + JSON
header + jq + 4xx handling). Annotation column: `R` = read-only, `W` = write, `D` = **DESTRUCTIVE** (confirm with the
user first).

## Endpoint reference

| Verb | Path | Operation | A |
|---|---|---|---|
| POST | `/user/repos` | Create personal repo | W |
| POST | `/orgs/{org}/repos` | Create org repo | W |
| POST | `/repos/{owner}/{repo}/forks` | Fork repo | W |
| GET | `/user/repos` | List my repos | R |
| GET | `/orgs/{org}/repos` | List org repos | R |
| GET | `/repos/{owner}/{repo}` | Get repo | R |
| PATCH | `/repos/{owner}/{repo}` | Edit repo | W |
| DELETE | `/repos/{owner}/{repo}` | Delete repo | **D** |
| GET | `/repos/{owner}/{repo}/branches` | List branches | R |
| GET | `/repos/{owner}/{repo}/branches/{branch}` | Get branch | R |
| POST | `/repos/{owner}/{repo}/branches` | Create branch | W |
| DELETE | `/repos/{owner}/{repo}/branches/{branch}` | Delete branch | **D** |
| GET | `/repos/{owner}/{repo}/tags` | List tags | R |
| GET | `/repos/{owner}/{repo}/tags/{tag}` | Get tag | R |
| POST | `/repos/{owner}/{repo}/tags` | Create tag | W |
| DELETE | `/repos/{owner}/{repo}/tags/{tag}` | Delete tag | **D** |
| GET | `/repos/{owner}/{repo}/commits` | List commits | R |
| GET | `/repos/{owner}/{repo}/git/commits/{sha}` | Get commit | R |
| GET | `/repos/{owner}/{repo}/git/trees/{tree_sha}` | Get repo tree | R |
| GET | `/repos/{owner}/{repo}/contents/{path}` | Get file or dir | R |
| PUT | `/repos/{owner}/{repo}/contents/{path}` | Create / update file | W |
| DELETE | `/repos/{owner}/{repo}/contents/{path}` | Delete file | **D** |
| GET | `/repos/{owner}/{repo}/releases` | List releases | R |
| GET | `/repos/{owner}/{repo}/releases/{id}` | Get release | R |
| GET | `/repos/{owner}/{repo}/releases/latest` | Latest release | R |
| POST | `/repos/{owner}/{repo}/releases` | Create release | W |
| PATCH | `/repos/{owner}/{repo}/releases/{id}` | Edit release | W |
| DELETE | `/repos/{owner}/{repo}/releases/{id}` | Delete release | **D** |
| GET | `/repos/{owner}/{repo}/releases/{id}/assets` | List release assets | R |
| POST | `/repos/{owner}/{repo}/releases/{id}/assets` | Upload release asset | W |
| DELETE | `/repos/{owner}/{repo}/releases/{id}/assets/{aid}` | Delete release asset | **D** |

## Table of Contents

- [Repos & forks](#repos--forks)
- [Branches](#branches)
- [Tags](#tags)
- [Commits & tree](#commits--tree)
- [File contents](#file-contents)
- [Releases](#releases)

## Repos & forks

### Create personal repo · `POST /user/repos` · write

```bash
gitea POST /user/repos -d '{"name":"my-repo","description":"...","private":false,"auto_init":true,"default_branch":"main"}'
```

Body fields: `name` (req), `description`, `private`, `auto_init`, `template`, `gitignores`, `license`, `readme`,
`default_branch`, `issue_labels`, `trust_model` (`default|collaborator|committer|collaboratorcommitter`),
`object_format_name` (`sha1|sha256`).

### Create org repo · `POST /orgs/{org}/repos` · write

Same body as personal; the URL determines ownership.

```bash
gitea POST /orgs/my-org/repos -d '{"name":"svc-x","auto_init":true}'
```

### Fork repo · `POST /repos/{owner}/{repo}/forks` · write

```bash
gitea POST /repos/{owner}/{repo}/forks -d '{"organization":"my-org","name":"my-fork"}'
```

Body (all optional): `organization` (target org; omit = personal), `name`.

### List my repos · `GET /user/repos?page=1&limit=30` · read-only

```bash
gitea GET '/user/repos?limit=50'
```

### List org repos · `GET /orgs/{org}/repos?page=1&limit=30` · read-only

### Get repo · `GET /repos/{owner}/{repo}` · read-only

### Edit repo · `PATCH /repos/{owner}/{repo}` · write

```bash
gitea PATCH /repos/{owner}/{repo} -d '{"description":"new","default_branch":"main"}'
```

Body fields (any subset): `name`, `description`, `website`, `private`, `default_branch`, `has_issues`,
`has_pull_requests`, `has_wiki`, `archived`, `allow_merge_commits`, `allow_rebase`, `allow_squash_merge`,
`internal_tracker`, etc.

### Delete repo · `DELETE /repos/{owner}/{repo}` · **DESTRUCTIVE**

```bash
gitea DELETE /repos/{owner}/{repo}   # 204 on success; helper returns 0
```

## Branches

### List branches · `GET /repos/{owner}/{repo}/branches?page=1&limit=30` · read-only

### Get branch · `GET /repos/{owner}/{repo}/branches/{branch}` · read-only

URL-encode `branch` if it contains `/` (e.g. `feature%2Fnewui`).

### Create branch · `POST /repos/{owner}/{repo}/branches` · write

```bash
gitea POST /repos/{owner}/{repo}/branches -d '{"new_branch_name":"feature/x","old_branch_name":"main"}'
```

Body: `new_branch_name` (req), `old_branch_name` (opt, defaults to repo default branch).

### Delete branch · `DELETE /repos/{owner}/{repo}/branches/{branch}` · **DESTRUCTIVE**

```bash
gitea DELETE /repos/{owner}/{repo}/branches/feature%2Fx   # URL-encode '/'
```

## Tags

### List tags · `GET /repos/{owner}/{repo}/tags?page=1&limit=20` · read-only

### Get tag · `GET /repos/{owner}/{repo}/tags/{tag}` · read-only

### Create tag · `POST /repos/{owner}/{repo}/tags` · write

```bash
gitea POST /repos/{owner}/{repo}/tags -d '{"tag_name":"v1.0.0","target":"main","message":"Release 1.0"}'
```

Body: `tag_name` (req), `target` (commit-ish, opt), `message` (annotated tag message, opt).

### Delete tag · `DELETE /repos/{owner}/{repo}/tags/{tag}` · **DESTRUCTIVE**

```bash
gitea DELETE /repos/{owner}/{repo}/tags/v1.0.0
```

## Commits & tree

### List commits · `GET /repos/{owner}/{repo}/commits?sha=&path=&page=1&limit=30` · read-only

Query: `sha` (starting commit/branch), `path` (only commits touching this path).

### Get commit · `GET /repos/{owner}/{repo}/git/commits/{sha}` · read-only

### Get repo tree · `GET /repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=false&page=1&per_page=30` · read-only

`tree_sha` may be a tree SHA, branch, or tag. Set `recursive=true` to walk the whole tree.

## File contents

Read-back and writes both use the same path; the verb distinguishes them.

### Get file content · `GET /repos/{owner}/{repo}/contents/{path}?ref={branch|tag|sha}` · read-only

Returns `{ name, path, sha, size, type, content (base64), encoding, ... }`. Decode:

```bash
gitea GET '/repos/{owner}/{repo}/contents/README.md?ref=main' | jq -r '.content' | base64 -d
```

### Get directory contents · `GET /repos/{owner}/{repo}/contents/{path}?ref=...` · read-only

When `path` is a directory, Gitea returns an array of entries instead of a single file object.

### Create or update file · `PUT /repos/{owner}/{repo}/contents/{path}` · write

```bash
CONTENT_B64=$(base64 -w0 < ./local.txt)
gitea PUT /repos/{owner}/{repo}/contents/README.md -d "$(jq -n \
  --arg c "$CONTENT_B64" \
  '{message:"docs: update readme", branch:"main", content:$c, sha:"<current-sha-or-omit>"}')"
```

Body: `message` (req, commit message), `content` (req, **base64-encoded**), `branch` (target branch — required if not
repo default), `new_branch` (create branch for this change), `sha` (current file SHA — **omit to create**, **set to
update**), `author` / `committer` (`{name,email}` objects, opt).

Conflict (wrong `sha`) returns 409. Wrong base64 returns 422. Use `jq -n --arg` to safely embed multi-line /
special-char content.

### Delete file · `DELETE /repos/{owner}/{repo}/contents/{path}` · **DESTRUCTIVE**

```bash
gitea DELETE /repos/{owner}/{repo}/contents/old-doc.md \
  -d '{"message":"chore: remove stale doc","branch":"main","sha":"<current-file-sha>"}'
```

Body: `message` (req), `branch` (req), `sha` (req — current file SHA), `new_branch` (opt), `author` / `committer` (opt).

## Releases

### List releases · `GET /repos/{owner}/{repo}/releases?page=1&limit=20&draft=&pre-release=` · read-only

### Get release by ID · `GET /repos/{owner}/{repo}/releases/{id}` · read-only

### Get latest release · `GET /repos/{owner}/{repo}/releases/latest` · read-only

### Create release · `POST /repos/{owner}/{repo}/releases` · write

```bash
gitea POST /repos/{owner}/{repo}/releases \
  -d '{"tag_name":"v1.0.0","target_commitish":"main","name":"v1.0.0","body":"Notes...","draft":false,"prerelease":false}'
```

Body: `tag_name` (req), `target_commitish` (branch or commit, req when tag does not exist), `name` (display title),
`body`, `draft`, `prerelease`.

### Edit release · `PATCH /repos/{owner}/{repo}/releases/{id}` · write

Body fields: `tag_name`, `target_commitish`, `name`, `body`, `draft`, `prerelease` — any subset.

### Delete release · `DELETE /repos/{owner}/{repo}/releases/{id}` · **DESTRUCTIVE**

### Release attachments

- **List**: `gitea GET /repos/{owner}/{repo}/releases/{id}/assets`
- **Upload** (multipart — use raw `curl` so it can set the multipart boundary):

  ```bash
  curl -sS "${AUTH[@]}" \
    "$GITEA_URL/api/v1/repos/{owner}/{repo}/releases/{id}/assets?name=app.tar.gz" \
    -F 'attachment=@./app.tar.gz'
  ```

- **Delete**: `gitea DELETE /repos/{owner}/{repo}/releases/{id}/assets/{aid}` · **DESTRUCTIVE**
