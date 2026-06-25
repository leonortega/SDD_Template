---
name: project-guidance-discover
description: Discover project-relevant guidance from the current repository. Use when Codex needs to scan tech stack, tools, environments, QA/test setup, security gates, code standards, architecture, web UI, REST/API needs, MCP/plugin/tool/reference/IDE-extension needs, or "config infra" guidance findings; research extra useful skills, MCPs, plugins, tools, references, practices, standards, and Codex-applicable IDE helpers from detected project signals; show suggested missing guidance with guarded install metadata; and prepare confirmed items for local acquisition or mapping.
---

# Project Guidance Discover

## Overview

Use this skill before acquiring project expert skills, MCPs, plugins, tools, IDE extensions, or persisting project guidance. Discovery is read-only until the user confirms the final list.

Use it for first-ticket setup, base-code setup, `config infra`, or any handoff where missing framework, tool, QA, security, architecture, code-standard, documentation, MCP, plugin, or general engineering guidance could make the next ticket less reliable.

## Shared Context

Read `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` before using discovery to affect delivery behavior. Treat docs, OpenSpec context, current files, and validation output as stronger than memory or assumptions.

## Workflow

1. Scan the repository for technology, tool, environment, QA, security, code-standard, architecture, web UI, REST/API, deploy, observability, and rollback signals.
2. Build research topics from detected signals. Do not rely on a fixed catalog alone.
3. Search multiple source families for each topic, in priority order:
   - Repository-local workflow skills, scripts, templates, and docs that are already tracked in this project.
   - OpenAI skill catalogs and docs.
   - Official repository or tool docs for the technology, framework, product, or plugin.
   - Technology-owner skill repositories or docs for the selected stack, E2E tool, repository/review provider, artifact provider, deployment provider, observability tools, container tools, or security standards.
   - `skills.sh`, `skills`, marketplace pages, or command examples when they identify a repository, ref, skill name, and likely `SKILL.md` path.
   - Well-used public skills or references only when no official or technology-owner source exists; label them as community-maintained.
4. Check whether each candidate skill already exists at `.codex/skills/{skill-name}/SKILL.md`.
5. Research extra useful skills, MCPs, plugins, tools, references, practices, standards, and Codex-applicable IDE helpers for the detected topics before presenting the result. Do not make the user name the extra tools first.
6. Show suggested missing skills and guidance with source, `sourceKind`, target, detected need, validation command, install metadata, and whether the item is a `skill`, `mcp`, `plugin`, `tool`, `reference`, `practice`, `standard`, or `ide-extension`.
   - For repeated tools used by CI/QA/security gates, include `installPreference: docker-preferred` and `dockerAlternative` metadata when an official/vendor or repo-owned pinned image exists.
   - Do not mark MCPs, IDE plugins, Docker itself, secret-interactive tools, or tools without verified images as Docker-preferred.
7. Ask the user only to confirm, dismiss, or add omissions after Codex has already done the extra research. Make the action clear: a confirmation means Codex will record the accepted guidance and immediately run `project-guidance-acquire` plus any supported guarded installer/configuration path. Do not ask a second "install?" question.
8. If the user adds omissions, research and validate those sources with the same multi-source, official-first policy.
9. Produce the final confirmed list for `project-guidance-acquire`. Do not copy, install, or configure anything from this skill.
10. After confirmation, persist the catalog-shaped local discovery state to `.codex/tool-recommendations.local.json` when requested. The local file keeps source, target, validation, accepted/dismissed state, detected tags, research topics, and recommendation entries with optional `usedInSteps`.

## Deterministic Script

Use the configure router when deterministic scanning is needed:

```bash
python -m tools.sdd_cli configure DiscoverProjectGuidance
```

To update the local project reference after the user confirms discovery, pass `persistLocal=true`:

```bash
python -m tools.sdd_cli configure DiscoverProjectGuidance --values-json-file .codex/guidance-discovery-values.local.json
```

The report must include:

- `detectedTags`
- `researchTopics`
- `existingSkills`
- `suggestedMissingSkills`
- `suggestedGuidance`
- `userAddedRequestedGuidance`
- `finalConfirmedGuidance`
- `sourceKind`
- `discoverySourcePriority`
- `localRecommendationsPath`

Use `AuditRecommendedTools` when the user also needs MCP, plugin, and non-skill recommendation findings.

The local file is intentionally ignored and shaped like `.codex/tool-recommendations.common.json`, but it is project-specific runtime state. `project-guidance-mapper` updates `usedInSteps` on recommendations after a step uses, confirms, or infers a guidance mapping.

## Output

Return a user-facing handoff with detected tags, research topics, existing skills, suggested missing skills, suggested non-skill guidance, user-added requested guidance, final confirmed guidance, validation commands, and the next action.

## User Handoff

Present suggestions before acquisition. Use a compact message like:

```text
I found these missing project guidance items:
- stack expert skill: detected selected stack; source <url>; target .codex/skills/<skill>/SKILL.md
- configured E2E tool reference: detected browser QA; source <url>; type reference

Confirm these to record and install/configure what is supported now, dismiss any you do not want, or name anything I missed.
```

If the user confirms the researched list, immediately record accepted ids, persist the local catalog, pass the final list to `project-guidance-acquire`, and install/configure supported MCP/plugin/tool/IDE items through platform-supported tools. If the user adds omissions, append researched and validated entries, show the updated final list, then use the same confirm-means-record-and-install flow.

## Safety

- Do not install, copy, or configure skills, MCPs, plugins, tools, or IDE extensions.
- Treat installer commands from `skills.sh`, `skills`, marketplace pages, or README examples as discovery metadata only. Extract the repository, ref, skill name, and likely `SKILL.md` path; do not execute the command.
- Confirm every skill source resolves to a readable repository `SKILL.md` before adding it to the final confirmed acquisition list.
- Treat command installers as metadata only unless `project-guidance-acquire` later has explicit user confirmation and a supported guarded install path.
- Prefer pinned Docker alternatives over package-manager installs for recurring tools when the metadata proves the tool can run from the mounted workspace/cache without host secrets or interactive auth.
- Do not read or print secrets.
- Do not recommend MCP-based ticket delivery unless the selected ticket adapter explicitly requires it; repo-local skills must use the configured ticket adapter.
- Record accepted or dismissed recommendation ids only with `SetRecommendedTools` after explicit user confirmation.
- Do not commit `.codex/tool-recommendations.local.json`; it is local project state.
- Do not list OpenSpec or configure skills as installable skill recommendations in the local or example catalog.

## Failure Rules

- Stop when the detected project stack conflicts with docs/OpenSpec context; route to `configure-dev-environment`.
- Stop when a source cannot be verified from an official, technology-owner, or clearly labeled community source.
- Stop when the user has not confirmed or dismissed the researched guidance list.
- Stop before any acquisition operation; copying and guarded install planning belong to `project-guidance-acquire`.
- When required discovery, verification, memory, or configured acquisition guidance cannot be applied, do not silently substitute another source family or installer path. Report the failed requirement, current-flow fix, viable alternative, and risk, then ask the user whether to fix the current flow or continue with the alternative.
