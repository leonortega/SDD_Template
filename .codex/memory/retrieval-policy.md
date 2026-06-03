# Memory Retrieval And Write Policy

Use this policy whenever an agent reads from or writes to `.codex/memory/`.

## Purpose

The memory system exists to reduce repeated rediscovery across SDD/SDLC work. It should capture reusable knowledge about repository structure, workflow rules, repeated failure patterns, QA lessons, release behavior, and agent operating preferences.

It must not become an unchecked source of truth.

## Read Policy

Read memory when starting:

- ticket planning
- implementation
- PR review
- QA
- DEV/QA deployment
- PROD promotion
- rollback
- hotfix
- delivery retrospective
- workflow or skill maintenance

Use progressive disclosure:

1. Read `memory_summary.md`.
2. Use `MEMORY.md` to identify likely relevant memory files.
3. Open only the specific deeper files needed for the task.
4. Verify all task-critical facts against current repo files, Plane, OpenSpec, Gitea, Nexus, Azure, Git, or live command output.

## Operational Use Loop

Use memory as a practical loop during repository work:

1. Start: read `memory_summary.md`, then use `MEMORY.md` or the search helper to find relevant deeper entries.
2. Debug: when an error, blocker, failed command, deploy issue, PR feedback, QA failure, or configuration mismatch appears, search memory with the concrete symptom before inventing a fix.
3. Verify: treat memory as a lead, then confirm against current files and live state.
4. Finish: run the durable learning capture gate and report `Memory updated: <files>` or `Memory updated: none`.

Search helper:

```powershell
.\.codex\memory\search_memory.ps1 -ListTopics
.\.codex\memory\search_memory.ps1 -Query Api__BaseUrl
.\.codex\memory\search_memory.ps1 -Query Gitea,reviewer
```

Search terms should be concrete: command names, error fragments, config keys, service names, workflow stages, marker names, or tool names. Examples: `dotnet`, `pipefail`, `comment_html`, `Api__BaseUrl`, `collaborators`, `pwsh`, `coverage`, `autocrlf`.

## Write Policy

Agents may propose or write memory updates only when the information is reusable and source-backed.

Good memory candidates:

- repeated CI, QA, deploy, or review failures
- durable command or setup corrections
- module ownership or behavior discovered during implementation
- release, rollback, artifact, or QA lessons
- workflow decisions that are useful across tickets
- user preferences for this repository's agentic workflow

Poor memory candidates:

- one-off debugging traces
- unverified assumptions
- secrets or credentials
- temporary local machine state
- full logs
- speculative architecture ideas not accepted by the user
- stale ticket status that should be read from Plane or Gitea

## Update Process

Use this process when a run discovers reusable knowledge:

1. Classify the finding.
   - Authoritative architecture, setup, development, deployment, or context policy belongs in `docs/`.
   - Enforceable automation behavior belongs in `.codex/skills/_shared/delivery-contract.md` plus affected skills and tests.
   - Reusable but non-authoritative workflow knowledge belongs in `.codex/memory/`.
2. Verify the source.
   - Prefer current files, command output, Plane ticket data, Gitea PR data, Nexus manifests, Azure health checks, QA evidence, or explicit user instruction.
   - Do not store assumptions as facts.
3. Choose the target memory file.
   - Workflow or marker lesson -> `workflow-memory.md`.
   - Repo layout or source-of-truth lesson -> `project-map.md` or `module-map.md`.
   - Delivery decision -> `decisions.md`.
   - Repeated breakage or stop condition -> `failure-patterns.md`.
   - QA result pattern -> `qa-findings.md`.
   - Artifact, version, PROD, rollback, or hotfix lesson -> `release-lessons.md`.
4. Add or update an entry using the required entry shape below.
5. Update `MEMORY.md` when adding a new topic that future agents need to discover.
6. Update `memory_summary.md` only for high-signal context that should be read at the start of most runs.
7. If an older entry is contradicted, mark it `Superseded` and link or name the replacement entry.
8. Include memory changes in the final handoff summary.

Memory updates must be small, source-backed, and reviewable. Do not use memory as a scratchpad.

## Required Entry Shape

When adding durable memory, prefer this shape:

```markdown
### Short Title

- Type: Fact | Decision | Pattern | Preference | Deprecated | Risk
- Status: Active | Superseded | Needs Verification
- Source: file path, ticket, PR, commit, command, or conversation date
- Last verified: YYYY-MM-DD

Memory text.
```

## Staleness And Conflict Handling

- Treat memory as stale if current files or live tools disagree.
- Update memory when a verified contradiction is found.
- Mark old entries as `Superseded` instead of silently deleting useful history.
- Delete entries only when they are harmful, secret-bearing, or purely noise.
- Never let memory override the authority order in `docs/context-management.md`.

## Security

Do not store:

- API tokens
- passwords
- cookies
- secret-bearing URLs
- generated Plane secrets
- Azure credentials
- local service credentials
- contents of ignored `.local` config files
- private logs copied from local containers or databases

Store references to safe evidence locations instead of copying sensitive evidence into memory.
