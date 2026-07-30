# Gitea REST API — Users, orgs, search, notifications, version

All examples use the `gitea` helper from [setup.md](setup.md#gitea-helper-function). Annotation column: `R` / `W`.

## Endpoint reference

| Verb | Path | Operation | A |
|---|---|---|---|
| GET | `/version` | Server version (Gitea-detection probe) | R |
| GET | `/settings/api` | Server API settings | R |
| GET | `/user` | Current user (token identity) | R |
| GET | `/user/orgs` | My orgs | R |
| GET | `/user/emails` | My emails | R |
| GET | `/user/followers` | My followers | R |
| GET | `/user/following` | Who I follow | R |
| GET | `/user/starred` | My starred repos | R |
| GET | `/user/subscriptions` | My watched repos | R |
| GET | `/users/{username}` | Get user | R |
| GET | `/users/{username}/orgs` | User's orgs | R |
| GET | `/users/{username}/repos` | User's repos | R |
| GET | `/orgs/{org}` | Get org | R |
| GET | `/orgs/{org}/members` | Org members | R |
| GET | `/orgs/{org}/teams` | Org teams | R |
| GET | `/users/search` | Search users | R |
| GET | `/repos/search` | Search repos | R |
| GET | `/orgs/{org}/teams/search` | Search org teams | R |
| GET | `/repos/issues/search` | Search issues + PRs across repos | R |
| GET | `/notifications` | List notifications | R |
| GET | `/repos/{owner}/{repo}/notifications` | Repo notifications | R |
| GET | `/notifications/threads/{id}` | Get thread | R |
| GET | `/notifications/new` | Unread count | R |
| PUT | `/notifications` | Mark all read | W |
| PUT | `/repos/{owner}/{repo}/notifications` | Mark repo read | W |
| PATCH | `/notifications/threads/{id}` | Mark thread | W |

## Table of Contents

- [Server identity](#server-identity)
- [Current user](#current-user)
- [User & org lookup](#user--org-lookup)
- [Search](#search)
- [Notifications](#notifications)

## Server identity

### Get version · `GET /version` · read-only (no auth required)

```bash
gitea GET /version
# or, for the probe before auth is set up:
curl -fsS "$GITEA_URL/api/v1/version" | jq
# { "version": "1.23.x" }
```

Use this as the Gitea-detection probe before any other operation.

### Server settings (admin) · `GET /settings/api` · read-only

Pagination/limit defaults exposed by the server: useful when scripting bulk pulls.

## Current user

### Get me · `GET /user` · read-only

```bash
gitea GET /user | jq '{login, full_name, email, is_admin}'
```

A 401 here means the token is wrong/expired.

### My orgs · `GET /user/orgs?page=1&limit=30` · read-only

### My emails · `GET /user/emails` · read-only

### My followers · `GET /user/followers?page=1&limit=30` · read-only

### My following · `GET /user/following?page=1&limit=30` · read-only

### My starred repos · `GET /user/starred?page=1&limit=30` · read-only

### My subscriptions (watched repos) · `GET /user/subscriptions?page=1&limit=30` · read-only

## User & org lookup

### Get user · `GET /users/{username}` · read-only

### List user's orgs · `GET /users/{username}/orgs?page=1&limit=30` · read-only

### List user's repos · `GET /users/{username}/repos?page=1&limit=30` · read-only

### Get org · `GET /orgs/{org}` · read-only

### List org members · `GET /orgs/{org}/members?page=1&limit=30` · read-only

### List org teams · `GET /orgs/{org}/teams?page=1&limit=30` · read-only

## Search

### Search users · `GET /users/search?q={query}&page=1&limit=30` · read-only

```bash
gitea GET '/users/search?q=alice&limit=30' | jq '.data[].login'
```

(Response shape: `{ data: [...], ok: true }` — search endpoints use this minimal envelope.)

### Search repos · `GET /repos/search?q={query}&...` · read-only

Query: `q`, `topic` (`true` = `q` matches topics only), `includeDesc` (search descriptions too), `uid` (limit to a user/org ID), `priority_owner_id`, `team_id`, `starredBy`, `private`, `is_private`, `template`, `archived`, `mode` (`fork|source|mirror|collaborative`), `exclusive`, `sort` (`alpha|created|updated|size|id`), `order` (`asc|desc`), `page`, `limit`.

```bash
gitea GET '/repos/search?q=auth&limit=10' | jq '.data[].full_name'
```

### Search org teams · `GET /orgs/{org}/teams/search?q={query}&include_desc=&page=1&limit=30` · read-only

### Search issues + PRs across repos · `GET /repos/issues/search` · read-only

Query: `q` (text), `state` (`open|closed|all`), `type` (`issues|pulls`), `labels` (comma-separated names), `milestones`, `owner`, `team`, `since` / `before` (ISO 8601), `created_by`, `assigned_by`, `mentioned_by`, `priority_repo_id`, `page`, `limit`.

```bash
gitea GET '/repos/issues/search?q=memory+leak&type=issues&state=open&limit=30' | jq '.[].title'
```

## Notifications

### List notifications · `GET /notifications` · read-only

Query: `all` (`true` = include read), `status-types` (comma list: `unread|read|pinned`), `subject-type` (comma list: `Issue|Pull|Commit|Repository`), `since`, `before`, `page`, `limit`.

### List repo-scoped notifications · `GET /repos/{owner}/{repo}/notifications` · read-only

Same query params as above.

### Get thread · `GET /notifications/threads/{id}` · read-only

### Mark all as read · `PUT /notifications?last_read_at=&to-status=read|pinned|unread` · write

Query: `last_read_at` (ISO 8601, default now), `to-status` (target state, default `read`).

### Mark repo-scoped as read · `PUT /repos/{owner}/{repo}/notifications?last_read_at=&to-status=read` · write

### Mark one thread · `PATCH /notifications/threads/{id}?to-status=read|pinned|unread` · write

### Check unread count · `GET /notifications/new` · read-only

Returns `{ "new": N }`.
