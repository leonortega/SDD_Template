<!-- TIER 2: SEMI-STABLE - Pre-flight gate loaded before any mutation, referenced by skill-startup.md and
delivery-contract-core.md -->

# Pre-Flight: Skills, Knowledge & MCP Gate

**This is a mandatory pre-flight gate (authority level 5).** Before any mutation — before editing files, making API
calls, committing, pushing, or changing ticket state — every agent **must** check
which skills and knowledge apply to the current task, consult the knowledge base when it maps to a knowledge category,
and activate the relevant MCPs.

Failure to run this gate before a mutation is a process violation.

---

## 1. Check Manifest For Relevant Skills

Open `.codex/skills/manifest.json` and read the `categories` section. Identify which categories match the current task:

| If your task is...                     | Check these manifest categories           |
| -------------------------------------- | ----------------------------------------- |
| Ticket start, propose, explore         | `ticket`, `plan`, `guidance`              |
| Implementation, coding                 | `implement`, `architecture`, `quality`, `security`, `test` |
| PR review, feedback                    | `review`, `quality`                       |
| QA, deploy, release                    | `qa`, `deploy`, `monitor`                 |
| Configuration, setup                   | `config`, `guidance`                      |
| Infrastructure, K8s, monitoring        | `kubernetes`, `observability`, `nexus`, `gitea`, `openproject` |
| Any code change                        | `architecture`, `quality`, `security`, `test` (always) |

For each matching category, read its `skills` array. For every skill listed, check if `SKILL.md` exists in
`.codex/skills/<path>/`:

```bash
test -f ".codex/skills/<skill-path>" && echo "EXISTS" || echo "NOT_FOUND"
```

**If the skill exists:** load it via `skill('<name>')` (preferred) or read its `SKILL.md` directly. Apply its rules
during the task.

**If the skill is missing** but listed in `manifest.json`: report it as a setup gap. Route to `project-guidance-acquire`
if the skill is needed for the current task.

**If the skill exists but is not relevant** to the current task: declare it as `skipped` with a brief rationale in the
`Skills used:` block.

## 2. Consult The Knowledge Base

The repository knowledge base (`knowledge/`) holds errors, fixes, patterns, anti-patterns, troubleshooting guides, and
lessons learned. Consult it before acting so reusable guidance informs the task
instead of being rediscovered.

Run the deterministic search helper with concrete symptom or topic terms (error text, config keys, tool names, workflow
stages, ticket subjects):

```bash
python -m tools.sdd_cli knowledge-search search --query <symptom-or-topic>
python -m tools.sdd_cli knowledge-search search --list-topics
```

Consult knowledge when the task involves:

- a ticket subject, feature area, error symptom, or blocker mentioned in the conversation
- implementation, review, QA, deploy, rollback, hotfix, or retrospective work
- a failed command, hook rejection, or configuration mismatch

If a relevant entry exists, apply it and cite it in the handoff (`Knowledge consulted: <file>`). The search is fast and
read-only; do not skip it when the task maps to a knowledge category.

## 3. Check MCPs For The Current Domain

Read `.codex/mcp-instructions.md` for the mandatory MCP routing contract. Identify which MCP servers are relevant to the
current task:

| Domain                          | MCP Server              | Tools                                  |
| ------------------------------- | ----------------------- | -------------------------------------- |
| Gitea (repos, PRs, issues)      | `gitea`                 | list/read/write operations             |
| OpenProject (tickets)           | `openproject`           | work-package CRUD                      |
| Grafana (dashboards, alerts)    | `grafana`               | dashboard search, PromQL queries       |
| Kubernetes (cluster, pods)      | `kubernetes`            | pods list, helm, events                |

**For each relevant MCP:**

- Verify the MCP is configured in `.vscode/mcp.json`.
- If the MCP is available and relevant, use its tools for the task — do not use raw grep or manual curl as the first
approach.
- If the MCP is unavailable, fall back to the appropriate tool (search_files for code, curl for APIs) and report the gap
in the handoff.
- Repository content search (docs/code/skills) uses the agent's built-in file/search tools — no dedicated content-search
MCP exists.

## 4. Load And Activate

Before any mutation, you MUST have all of the following clear in your working context:

1. **Which skills apply** — from manifest.json category matching + installed SKILL.md check
2. **Which MCPs to use** — from mcp-instructions.md domain matching
3. **Which skills are skipped and why** — documented with rationale

**Activation during the task:**

- For **skills**: apply their rules/patterns/constraints during the relevant phase (RED/GREEN/REFACTOR for
implementation, review criteria for PR review, security checks for config changes, etc.)
- For **MCPs**: route service interactions through them (gitea, openproject, grafana, kubernetes); repository content
search uses built-in tools

## 5. Declare

At the start of every response body, include a `Skills used:` block that shows:

- Which skills are **active** and how they were applied (e.g., "clean-code — applied: extracted helper function")
- Which skills are **skipped** and why (e.g., "playwright — skipped: no UI in this task")
- Which MCPs were **used** for this step (e.g., "MCPs used: gitea for PR operations")

```markdown
Skills used:
- caveman (auto, full)
- ponytail (auto, full)
- clean-code (on-demand) — applied: meaningful names, small functions
- security-best-practices (on-demand) — applied: input validation
- solid (skipped — single-file change, no interface design)
- MCPs used: gitea for PR status
```

## When To Run This Gate

| Scenario                                   | Run gate? |
| ------------------------------------------ | --------- |
| Read-only investigation (no mutations)     | Optional  |
| Before first edit in any skill workflow    | **MANDATORY** |
| Before proposing OpenSpec changes          | **MANDATORY** |
| Before API calls to Gitea/OpenProject/Nexus | **MANDATORY** |
| Before commit or push                      | **MANDATORY** |
| Before PR creation or review               | **MANDATORY** |
| Before implementation, review, QA, deploy, rollback, or hotfix | **MANDATORY** — consult knowledge first |
| Before deployment or release               | **MANDATORY** |
| Before configuration changes               | **MANDATORY** |
| Resume from checkpoint (skills already declared) | Skip if skills context is still valid |

## Integration With Existing Workflows

This gate runs **after** context reading (Tiers 1-3 in skill-startup.md) but **before** any mutation. It feeds into:

- `dev-flow-implement-ticket` §1 step 5 (Skill Pre-Analysis) — this gate replaces the manual scan with a structured
check
- `dev-flow-apply-change` Skill Pre-Analysis section — same structured check
- `dev-flow-pr-review-agent` — checks review skills + Gitea MCP before posting review
- `dev-ops-*` skills — checks deploy/monitor skills + Kubernetes MCP before deployment
- `dev-flow-start-ticket` Stack Context Preflight and `dev-flow-pr-review-agent` — consult the knowledge base before
proposing or reviewing

The `Skills used:` declaration in every response body satisfies the declaration requirement from AGENTS.md Mandatory
Skill Declaration.
