<!-- TIER 1: STABLE PREFIX - Mandatory MCP routing contract, authority level 5 -->

# MCP Routing Instructions — Mandatory

This file defines the **mandatory** MCP server routing for all agent prompts. Every agent **must** follow this routing whenever the task requires interacting with lab services.

## Service MCP Servers

The lab infrastructure provides dedicated MCP servers for each service. Route to the correct MCP based on the target service:

| Service | MCP Server | Domain | Tools |
|---|---|---|---|
| **Gitea** | `gitea` | Repos, issues, PRs, Actions, wiki | `list_my_repos`, `list_pull_requests`, `issue_read`, `issue_write`, `pull_request_write`, `actions_run_read`, `get_file_contents`, `get_dir_contents` |
| **OpenProject** | `openproject` | Work packages, projects, time entries | work-package CRUD, project listing, time-entry management via APIv3 |
| **Grafana** | `grafana` | Dashboards, datasources, alerts, incidents, OnCall | dashboard search/CRUD, Prometheus/Loki queries, alert management, incident search |
| **Kubernetes** | `kubernetes` | K8s cluster resources, Helm, pods | `pods_list`, `pods_get`, `pods_log`, `pods_exec`, `helm_list`, `helm_install`, `events_list`, `nodes_top` |

**When to use each:**

- **Gitea MCP** — any task involving Gitea: creating repos, managing issues/PRs, reading files, triggering Actions, managing wiki
- **OpenProject MCP** — any task involving tickets/work packages: reading, creating, updating work packages, managing projects, time tracking
- **Grafana MCP** — any task involving dashboards, metrics queries (Prometheus), log queries (Loki), alert rules, incidents, or OnCall schedules
- **Kubernetes MCP** — any task involving cluster management: pods, deployments, services, Helm charts, logs, events

**Note on availability:**
- Gitea MCP uses the official Docker image `docker.gitea.com/gitea-mcp-server`
- OpenProject MCP uses the community `openproject-mcp` package (read/write)
  - Cross-ref API adapter at `.codex/skills/openproject-sprint-backlog/references/openproject-api.md` for direct REST API calls
- Grafana MCP uses the official `grafana/mcp-grafana` via `uvx`
- Kubernetes MCP uses the official `containers/kubernetes-mcp-server` via `npx`
- **Seq and Dozzle** have no dedicated MCP servers. Use the Repo / monitoring skills for those.
- **Nexus** has no official MCP. Use the Nexus skill + provider adapter instead.

See `.vscode/mcp.json` for exact configuration.

## Repository Content Search

Repository content search (documentation, source code, skills) uses the agent's **built-in file/search tools** — there are no dedicated content-search MCP servers in this repository. Use standard grep, file reads, and search tools directly.

## Authority

This routing contract sits at authority level 5 in `docs/context-management.md` — alongside `.codex/skills/_shared/delivery-contract.md` — and overrides ad hoc service-interaction decisions.
