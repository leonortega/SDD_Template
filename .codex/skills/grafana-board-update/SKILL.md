---
name: grafana-board-update
license: MIT
description: >-
  >- After a CI deploy completes, intelligently update the Grafana SDD Service Status dashboard with live URLs, new
  apps, and multi-environment support. Use when a deploy finishes and you need to refresh the Grafana dashboard — either
  from scratch or by merging changes into the existing JSON. Handles app additions, environment sections (DEV/QA/PROD),
  stale entry cleanup, and Grafana API push.
---

<!-- TIER 3: STAGE-SPECIFIC - Grafana dashboard update after deploy -->

# Grafana Dashboard Update

## Overview

**Trigger:** Run this skill **manually** after a CI deploy completes. The CI pipeline discovers URLs and uploads them to
Nexus — the agent handles the **intelligent** work of reading those URLs,
deciding what to add/remove, modifying the Grafana dashboard JSON, and optionally pushing to Grafana via API.

After a CI deploy to any environment (DEV, QA, or PROD), the Grafana SDD Service Status dashboard at
`http://localhost:3001` should reflect the current state of all deployed services.

## Shared Context

Read these docs for background:

- `.codex/skills/_shared/delivery-contract.md` → deploy stage contract, handoff markers
- `docs/conventions/context-management.md` → durable context rules
- `docs/architecture/deployment.md` → Grafana provisioning, dashboard architecture
- `.codex/skills/grafana-observability/SKILL.md` → Grafana patterns
- `knowledge/README.md` → past issues / gotchas

Run this skill after a deploy completes for the active ticket; scope dashboard edits to the deployed ticket's apps and
environments.

## Sources Of Truth

| Source | What it contains | How to read |
|---|---|---|
| `infra/deployment/apps.json` | All known apps with `appId`, `role`, `healthPath`, `deployOrder` | Direct file read |
| `infra/k8s/kind-config.yaml` | Host port ↔ nodePort mappings (`extraPortMappings`) | Direct file read |
| `infra/monitoring/grafana/dashboards/health-board.json` | The current dashboard JSON | Direct file read — this is what you will edit |
| Nexus `app/latest/env-urls-{env}.json` | Live deployed URLs per environment | Fetch via `curl -u admin:admin123 http://host.docker.internal:8088/repository/sdd-artifacts/app/latest/env-urls-dev.json` |
| Grafana API `http://localhost:3001` | Push dashboard updates | `POST /api/dashboards/db` with auth `admin:admin` |

## Environment To Nexus URL Mapping

| Environment | Nexus artifact path |
|---|---|
| DEV | `http://host.docker.internal:8088/repository/sdd-artifacts/app/latest/env-urls-dev.json` |
| QA | `http://host.docker.internal:8088/repository/sdd-artifacts/app/latest/env-urls-qa.json` |
| PROD | `http://host.docker.internal:8088/repository/sdd-artifacts/app/latest/env-urls-prod.json` |

Nexus auth: `admin / admin123` (unless overridden in secrets).

## Dashboard Architecture

The dashboard (`uid: agentic-e2e-health-board`) has these panels:

| Panel ID | Title | Type | Purpose |
|---|---|---|---|
| `10` | (empty — header) | `text` (markdown) | Title banner with cluster info, env, deploy SHA |
| `1` | 🟢 Service Health | `table` (Infinity datasource) | Live per-service status table fed by the health probe |
| `6` | 🔧 Infrastructure Access | `text` (markdown) | Static table with Grafana/Gitea/Nexus/Dozzle links |

## Decision Framework

When updating the dashboard, use this decision order:

### 1. First time? No dashboard exists

If `health-board.json` is missing (`infra/monitoring/grafana/dashboards/health-board.json`), **create it from scratch**
using the template structure below. Generate all panels with whatever apps and
environments are currently deployed.

### 2. New app added to apps.json

If `infra/deployment/apps.json` has a new app that doesn't appear in the dashboard:

- Add it to the **Service Health** table (panel 1) — the health-probe payload drives the rows
- Assign an emoji from the role mapping below
- Calculate proper `gridPos.y` to fit the new row
- When the table grows significantly (>8 rows), consider splitting DEV/QA/PROD into separate sections within the same
panel, or reorganize with section headers

### 3. App removed from apps.json

If an app exists in the dashboard but is no longer in `apps.json`:

- **Remove** it from Service Health
- **Check** if the app was decommissioned vs just not deployed this run

### 4. URL changed (re-deploy)

If the same app gets new URLs after a re-deploy:

- Update the **Service Health** row with the new URL

### 5. Environment section needs adding

When a new environment deploys for the first time (e.g., QA after DEV):

- The **Service Health** panel should get new rows prefixed with the environment badge (🔷 DEV, 🟢 QA, 🔴 PROD)
- Consider whether to add environment sub-sections within existing panels or create separate panels

## Emoji & Role Mapping

| Role | Emoji | Display Suffix |
|---|---|---|
| `web` | 🖥️ | React / Web |
| `api` | 🔄 | API |
| `worker` | ⚙️ | Worker |
| `database` | 🗄️ | Database |
| `queue` | 📨 | Queue |
| `cache` | ⚡ | Cache |
| (unknown) | 📦 | (as-is) |

## Environment Badge Mapping

| Environment | Badge Emoji |
|---|---|
| DEV | 🔷 |
| QA | 🟢 |
| PROD | 🔴 |

## Critical Rules

### Rule 1: Version must increase

Grafana provisioning **only overwrites a dashboard when the `version` field is higher** than what's stored in the DB.
When editing `health-board.json`:

- Read the current `version` value (e.g. `27`)
- Set it to `int(time.time())` (epoch seconds) — this guarantees a higher value
- Never set version lower than the current value

### Rule 2: Infinity datasource — no `color` in mappings

The Infinity datasource plugin (`yesoreyeram-infinity-datasource`) crashes with:

```text
TypeError: Cannot read properties of undefined (reading 'Not deployed')
```

when value mappings contain a `"color"` property. **Never include `"color"` inside mapping objects.** Use text-only:

```json
// ❌ BAD — crashes Infinity
"mappings": [{"type": "value", "value": "Active", "text": "✅ Active", "color": "green"}]

// ✅ GOOD — works fine
"mappings": [{"type": "value", "value": "Active", "text": "✅ Active"}]
```

### Rule 3: Infinity datasource — use `source: "inline"` for tables

The Infinity datasource **crashes** when `source: "url"` is used with `parser: "backend"` and `format: "table"`. Always
use `source: "inline"` for table panels:

```json
// ✅ Correct approach for inline table panels
"source": "inline",
"data": "{\"data\":[...]}",
"format": "table",
"parser": "backend"
```

### Rule 4: Keep `uid` stable

The dashboard UID is `agentic-e2e-health-board`. Never change it. The `overwrite: true` flag on API push ensures updates
work.

### Rule 5: gridPos arithmetic

The dashboard uses a 24-column grid (`schemaVersion: 39`):

- `w: 24` — Full width
- `h: N` — Height in grid rows (~30px per row)
- `y` values must not overlap — calculate sequentially. **Pack tightly.** When creating from scratch, use:
  - Panel 0 (header): `y=0`, `h=4`
  - Panel 1 (health): `y = panel0.y + panel0.h`, `h = max(4, num_rows + 2)`
  - Panel 2 (infra): `y = panel1.y + panel1.h`, `h = 6`

### Rule 6: Use kind-config for host port mapping

The kind cluster maps nodePorts to host ports via `extraPortMappings` in `infra/k8s/kind-config.yaml`:

```yaml
extraPortMappings:
  - containerPort: 30080  # ← this is the K8s nodePort
    hostPort: 8081        # ← this is the actual localhost URL
```

When building the dashboard, resolve:

- `hostUrl` = `http://localhost:<hostPort>` (e.g. `http://localhost:8081`) — **use this as the clickable URL**. From the
Windows host the nodePort itself is NOT reachable at `localhost:{nodePort}` —
kind's `extraPortMappings` expose services only at the host ports.
- `nodePort` = the K8s Service nodePort (e.g. `30080`) — display it as info only; it is NOT a host URL. The
health-probe determines status from the **external URL users navigate**
(`host.docker.internal:<hostPort>`), not from the internal nodePort.

For infrastructure services (Grafana, Gitea, Nexus) that run via Docker Compose (not K8s), use their Docker host ports
directly.

## Workflow

### Step 1: Gather deploy state

1. Read `infra/deployment/apps.json` — collect `appId`, `role`, `healthPath` for every app
2. Read `infra/k8s/kind-config.yaml` — build the `{nodePort: hostPort}` mapping
3. Fetch environment URLs from Nexus for **all** environments that have been deployed. Try each:

   ```bash
   curl -s -u 'admin:admin123' \
     'http://host.docker.internal:8088/repository/sdd-artifacts/app/latest/env-urls-dev.json'
   ```

   - DEV: `env-urls-dev.json` (always try first)
   - QA: `env-urls-qa.json` (try — may not exist yet)
   - PROD: `env-urls-prod.json` (try — may not exist yet)
   - If Nexus is unreachable, use what's available locally
4. Read the current `infra/monitoring/grafana/dashboards/health-board.json` — understand what's already there

### Step 2: Decide what to change

Based on the Decision Framework above, determine:

- Does a dashboard exist? (Yes → update, No → create)
- Are there new apps? (add them)
- Are there removed apps? (remove them)
- Did URLs change? (update them)
- Are there new environments? (add sections)

### Step 3: Modify the dashboard JSON

Edit `infra/monitoring/grafana/dashboards/health-board.json`:

1. **Bump version**: Set `"version": <int(time.time())>`
2. **Update header panel** (id: 10): Add deploy SHA and environment info to the markdown content
3. **Update Service Health panel** (id: 1): The live table is fed by the health probe
   (`http://health-probe:8090/health` via the Infinity datasource). Columns map directly from the probe JSON
   (`env/service/status/http/directUrl/healthPath/nodePort`) — verify the probe payload reflects the deployed
   apps/environments instead of hand-editing rows.
4. **Update Infrastructure Access panel** (id: 6): Keep mostly static, update environment name in the footer
5. **Recalculate all `gridPos.y` values** so panels don't overlap (header → health → infra)
6. **Update `time.from` and `time.to`**: Keep at `"now-1h"` / `"now"`

### Step 4: Validate the JSON

Before saving or pushing:

1. Run `python3 -m json.tool infra/monitoring/grafana/dashboards/health-board.json` to validate JSON syntax
2. Check that all panel `id` values are unique (10, 1, 6)
3. Check that no two panels occupy overlapping `gridPos` rectangles
4. Check that Infinity inline `data` strings are valid JSON (use a Python json.loads check on the inline data)
5. Check that no Infinity mapping contains a `"color"` property

### Step 5: Push to Grafana API (optional, for immediate effect)

**⚠️ Provisioned dashboard limitation:** The `health-board.json` is provisioned from disk via
`infra/monitoring/grafana/provisioning/dashboards/dashboards.yml`. Grafana **rejects API writes** to
provisioned dashboards with status `"Cannot save provisioned dashboard"`.

You have two options:

**Option A — File only (safe, always works):** Just save the updated JSON. Grafana provisioning picks it up on next
restart — the `version` bump ensures the new file overwrites the old DB entry.

**Option B — Try API (may fail for provisioned dashboards):** If Grafana is configured with `editable: true` and the
dashboard is NOT provisioned, the API push will work for immediate effect:

```bash
DASHBOARD_JSON=$(cat infra/monitoring/grafana/dashboards/health-board.json)
PAYLOAD=$(python3 -c "
import json
dashboard = json.load(open('infra/monitoring/grafana/dashboards/health-board.json'))
payload = {'dashboard': dashboard, 'overwrite': True, 'message': 'CI post-deploy update'}
print(json.dumps(payload))
")
curl -s -X POST 'http://admin:admin@localhost:3001/api/dashboards/db' \
  -H 'Content-Type: application/json' \
  -d "$PAYLOAD" | python3 -m json.tool
```

Expected response on success:

```json
{
  "status": "success",
  "uid": "agentic-e2e-health-board",
  "url": "/d/agentic-e2e-health-board/sdd-service-status",
  "version": 28
}
```

If the API returns `"Cannot save provisioned dashboard"`, the file-based change is sufficient. Verify the updated JSON
is committed and pushed.

If Grafana rejects with a version error, increase the version field and retry.

```bash
DASHBOARD_JSON=$(cat infra/monitoring/grafana/dashboards/health-board.json)
PAYLOAD=$(python3 -c "
import json
dashboard = json.load(open('infra/monitoring/grafana/dashboards/health-board.json'))
payload = {'dashboard': dashboard, 'overwrite': True, 'message': 'CI post-deploy update'}
print(json.dumps(payload))
")
curl -s -X POST 'http://admin:admin@localhost:3001/api/dashboards/db' \
  -H 'Content-Type: application/json' \
  -d "$PAYLOAD" | python3 -m json.tool
```

Expected response:

```json
{
  "status": "success",
  "uid": "agentic-e2e-health-board",
  "url": "/d/agentic-e2e-health-board/sdd-service-status",
  "version": 28
}
```

If Grafana rejects with a version error, increase the version field and retry.

### Step 6: Verify in browser

Open `http://localhost:3001` and navigate to the SDD Service Status dashboard. Verify:

- All deployed apps appear with correct URLs
- New apps are present, removed apps are gone
- Status icons are correct (UP/DOWN based on URL presence)
- Tables load without JS console errors (no Infinity datasource crashes)

### Step 7: Commit changes (if JSON was modified)

If you modified `health-board.json`:

```bash
git add infra/monitoring/grafana/dashboards/health-board.json
git commit -m "chore: update Grafana dashboard after {env} deploy"
git push
```

## Dashboard JSON Template Structure

Use this as a reference when creating from scratch. All panels must be present.

```json
{
  "title": "🚀 SDD Service Status",
  "uid": "agentic-e2e-health-board",
  "version": <int(time.time())>,
  "schemaVersion": 39,
  "timezone": "browser",
  "editable": true,
  "refresh": "30s",
  "graphTooltip": 1,
  "tags": ["agentic-e2e", "health", "urls", "infrastructure", "env-{env}"],
  "timepicker": {
    "refresh_intervals": ["10s", "30s", "1m", "5m", "15m", "30m", "1h"],
    "time_options": ["5m", "15m", "1h", "6h", "12h", "24h", "2d", "7d", "30d"]
  },
  "panels": [
    // Panel 10: Header (markdown, full width)
    // Panel 1: Service Health (table, Infinity datasource, full width)
    // Panel 6: Infrastructure Access (markdown, full width)
  ],
  "links": [
    { "title": "Grafana Docs", "type": "link", "url": "http://localhost:3001/help", "targetBlank": true },
    { "title": "Gitea", "type": "link", "url": "http://localhost:3000", "targetBlank": true },
    { "title": "Nexus", "type": "link", "url": "http://localhost:8088", "targetBlank": true }
  ],
  "time": { "from": "now-1h", "to": "now" }
}
```

## Dashboard JSON Template — Panel Details

### Panel 10: Header (id: 10)

```json
{
  "id": 10,
  "type": "text",
  "title": "",
  "gridPos": { "h": 4, "w": 24, "x": 0, "y": 0 },
  "options": {
    "content": "# 🚀 SDD Service Status Dashboard\n\n**Cluster:** `sdd-cluster` · **Refresh:** `30s` · **Grafana:** http://localhost:3001 · _Click a Direct URL to open the service._",
    "mode": "markdown"
  }
}
```

### Panel 1: Service Health (id: 1)

A live `table` panel backed by the Infinity datasource, fed by the health probe
(`http://health-probe:8090/health`). Columns map directly from the probe JSON payload:

`Environment` · `Service` · `Status` · `HTTP` · `Direct URL` · `Health Endpoint` · `K8s NodePort`

Status value mappings (as shipped in `health-board.json`):

- `UP` (green) — probe reports the service reachable
- `Not deployed` (gray) — service expected but endpoint unreachable
- `DOWN` (red) — probe cannot reach the endpoint

The probe payload is the source of truth; do not hand-maintain rows here.

### Panel 6: Infrastructure Access (id: 6)

Static markdown table with all infrastructure services. Update the environment name in the footer message.

## Common Failure Modes

| Symptom | Likely Cause | Fix |
|---|---|---|
| Dashboard shows old URLs | ci deployed but dashboard not updated yet | Run this skill → the deploy has new URLs in Nexus |
| Panel shows `Cannot read properties of undefined` | Infinity crash from `color` in mappings | Remove all `"color"` properties from mappings |
| Dashboard not updating after JSON edit | Version number not incremented | Set version to `int(time.time())` |
| `412 Precondition Failed` on API push | Version lower than stored version | Increase version and retry |
| Grafana returns 404 for dashboard | Dashboard never created | Create from scratch using the template |
| New app not showing | Not in `apps.json` yet | Add to `apps.json` first, then run this skill |
| Nexus URL fetch fails | Nexus credentials missing or service not running | Try `admin:admin123`, check Docker Compose |

## Output

Report the dashboard JSON changes (version bump, panels added/removed/updated),
the JSON validation results, the Grafana API push outcome (or the
provisioned-file fallback), and the handoff status for the deploy ticket.

## Failure Rules

- Stop if `apps.json` cannot be read — the dashboard must match app topology.
- Stop if the edited JSON fails validation or violates the Infinity rules.
- Stop if the dashboard `uid` would change or `version` would decrease.
- Never push via API to provisioned dashboards and claim success; fall back to the file change.
