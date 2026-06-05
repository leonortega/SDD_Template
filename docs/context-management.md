# Context Management Fundamentals

This repository treats context as an SDLC asset. Durable project knowledge belongs in tracked documentation and workflow contracts, not only in chat history, temporary notes, PR comments, or Plane comments.

`.codex/memory/` provides a reviewable repository memory layer for reusable workflow knowledge, repeated failure patterns, module landmarks, and release or QA lessons. Memory is a retrieval aid only; it must be verified against the authority order below before it drives an action.

For practical lookup, use `.codex/memory/search_memory.ps1 -Query <symptom>` with concrete error text, config keys, tool names, workflow stages, or marker names. Memory search should accelerate diagnosis, not replace freshness checks against current files and live systems.

## Authority Order

When sources disagree, use this order until the conflict is resolved:

1. Latest explicit user request in the current conversation.
2. Active Plane ticket state, description, acceptance criteria, and generated markers.
3. Active OpenSpec proposal, design, specs, and tasks.
4. `.codex/skills/_shared/delivery-contract.md` for agent-enforced delivery behavior.
5. Canonical docs in `docs/`.
6. Current code, tests, workflow files, and configuration templates.
7. Historical Plane comments, PR comments, QA evidence, release manifests, and tags.
8. `.codex/memory/` entries.
9. Agent assumptions.

Assumptions must never override a concrete source. If an assumption is required to continue, record it in the handoff summary.

## Context Bundles

Load only the context needed for the workflow stage.

- Ticket start: Plane ticket, current Plane state, base branch, branch policy, OpenSpec decision rules, and existing generated markers.
- Implementation: ticket lock, Plane ticket, OpenSpec apply context files, relevant code, relevant tests, quality gates, and local docs for architecture/development/deployment constraints.
- PR review: PR diff, ticket, OpenSpec artifacts, relevant tests, CI status, review labels, and current head SHA.
- QA and deploy: ticket lock, merged PR, artifact commit, Nexus paths, `release.json`, workflow run, DEV/QA URLs, health checks, and QA evidence rules.
- PROD: QA-approved artifact, source RC tag, final version, `main` target commit, release manifest, PROD health checks, and monitoring status.
- Rollback or hotfix: incident/ticket context, current PROD release, known-good artifact, rollback lineage, active ticket lock mismatch, and follow-up ownership.

## Freshness Checks

Before mutating Plane, Git, Gitea, Nexus, Azure, tags, or release manifests, refresh the relevant state:

- Plane state, ticket description, and generated comments.
- Current Git branch, dirty state, remote branch, and tags.
- Gitea PR status, labels, reviews, head SHA, merge commit, and CI status.
- Nexus artifact files under `app/{commitSha}/`, including `release.json`.
- DEV, QA, and PROD health evidence when deployment state matters.
- QA evidence, RC tags, final tags, and rollback lineage before promotion or rollback.

Use durable checkpoints for reruns. Do not restart a completed stage when the matching marker, branch, PR, artifact, tag, evidence bundle, or manifest entry already proves it completed.

## Conflict Rules

Stop instead of guessing when a resolved ticket, branch, PR, artifact commit, source RC version, final release version, QA evidence path, or deployment lane owner does not match the active context lock or durable checkpoints.

If docs conflict with `.codex/skills/_shared/delivery-contract.md`, the delivery contract wins for automation behavior until the docs are corrected.

## Handoff Compression

Every implementation, review, QA, deployment, PROD, rollback, or hotfix handoff must preserve:

- goal and current workflow stage
- Plane ticket and state
- branch and OpenSpec change
- PR number or URL
- commit SHA and artifact path when available
- tests and validation commands run
- QA evidence, RC version, final version, or rollback target when relevant
- blockers, risks, and assumptions
- context findings and docs updated
- memory updated or explicitly not updated when the workflow performs a memory update review
- next required action

## Prompt Cache Hygiene

Long-running agent workflows should keep stable context before volatile runtime context so repeated calls can reuse cacheable prompt prefixes. Put repository policy, delivery contract excerpts, skill instructions, schemas, and stable examples before ticket-specific Plane comments, PR diffs, tool results, timestamps, logs, and health-check output.

Dynamic values belong near the end of the working context:

- current user request
- active ticket state and generated comments
- Git branch, dirty state, commit SHA, PR state, labels, and CI status
- Nexus manifests, Azure health checks, QA evidence, and monitoring output
- tool errors, retries, and latest observations

Do not insert timestamps, random IDs, raw tool dumps, or refreshed status summaries into otherwise stable context blocks. If a run records model telemetry, write it to ignored local output such as `.codex/agent-telemetry.local.jsonl` and summarize only useful optimization findings in handoff text. Automatic ticket delivery may also maintain a concise generated Plane timing comment for the active ticket, but only with per-stage outcome, duration, and UTC start/finish values; raw logs, token counts, prompts, and sensitive values stay out of Plane.

## Risk-Adaptive Context Loading

Strict gates do not require every run to load every long instruction body. Agents should classify delivery risk as `low`, `standard`, or `high` using the shared delivery contract and deterministic helpers when available.

- `low` risk: use compact planning/review summaries and load only the relevant docs, skills, and files.
- `standard` risk: use the normal stage context bundle.
- `high` risk: load full acceptance/spec context, affected deployment/security/release guidance, and adversarial review evidence.

Project guidance remains the broad catalog for skills, tools, references, practices, standards, MCPs, and plugins. The installed-skill runtime index is only an ignored cache of exact installed `SKILL.md` paths used to avoid repeated scans and pass precise skill paths during delegation.

Avoid duplicate context systems. Ticket refinement belongs in the managed Plane block; implementation planning belongs in OpenSpec; recurring workflow learning belongs in `delivery-retrospective-audit`, docs, the shared contract, or `.codex/memory/` according to the existing authority order.

## Agent Telemetry

When the platform exposes usage data, delivery agents should record non-secret optimization telemetry for retrospective analysis:

- workflow stage and agent role
- model and reasoning effort
- input, output, reasoning, and cached token counts when available
- tool-call count, retry count, elapsed time, and outcome
- blocker category when the run stops

Telemetry is evidence for model routing, prompt-cache hygiene, tool-description changes, and eval coverage. It is not an authority source and must not contain secrets, full prompts, raw credentials, private payloads, or large tool results.

## Context Findings

During implementation and retrospective work, update durable docs when new reusable knowledge is discovered:

- architecture/topology/source-of-truth finding -> `docs/architecture.md`
- local setup, commands, repo conventions, testing, or quality gates -> `docs/development.md`
- artifact, deployment, QA, release, rollback, or monitoring finding -> `docs/deployment.md`
- agent context loading, freshness, authority, handoff, or conflict rule -> `docs/context-management.md`
- enforceable automation behavior -> `.codex/skills/_shared/delivery-contract.md` plus affected skills and tests
- reusable but non-authoritative workflow memory -> `.codex/memory/`

When updating memory, follow `.codex/memory/retrieval-policy.md`. Memory updates must be source-backed, small, and reviewable. If a finding is authoritative or enforceable, update the appropriate docs or delivery contract before adding any memory note.

Temporary debugging details, one-off failures, and local machine quirks should stay in run evidence or handoff notes unless they reveal a durable rule.
