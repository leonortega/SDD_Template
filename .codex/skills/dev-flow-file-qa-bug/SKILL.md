---
name: dev-flow-file-qa-bug
description: Create a linked bug through the selected ticket adapter from failed QA evidence, preserve failure context, and start a focused fix workflow when code changes are required. Use when quality-test-e2e finds a product defect, QA fails after deployment, or Codex needs to create a follow-up bug ticket from QA evidence.
---

# File QA Bug

## Overview

Use this skill when QA finds a product defect after a ticket has reached QA. The original ticket stays in QA unless the user explicitly changes workflow policy. Create a linked bug with evidence, then start the normal fix workflow only when the defect requires code work.

## Shared Context

Before filing or linking tickets, follow `.codex/skills/_shared/skill-startup.md`, which reads `.codex/project-profile.json`, `.codex/skills/_shared/provider-adapter-contract.md`, `.codex/skills/_shared/delivery-contract.md`, and `docs/context-management.md`, with `docs/development.md` and `docs/deployment.md` as stage-specific docs. Load selected ticket, repository, artifact, deployment, and E2E adapters as needed.

## Configuration

Read `.codex/project-profile.json` first. Read `.codex/client-tools.local.json` only for selected adapter runtime values when a ticket mutation or fix branch is needed.

## Workflow

1. Resolve the parent Plane ticket, failed QA run, tested commit, artifact, QA URL, and evidence path or URL.
2. Read `.codex/delivery-context.local.json` when present and verify the parent ticket, tested commit, artifact `release.json.planeTicketKey`, and evidence path match the locked `ticketKey`. If they do not, stop before filing a bug against the wrong parent.
3. Confirm the failure is a product defect, not tooling, missing credentials, missing test data, unreachable infrastructure, or evidence upload failure.
4. Create or reuse a linked Plane bug ticket with:
   - parent ticket key,
   - tested commit and artifact,
   - QA environment and URLs,
   - failed scenario and expected/actual behavior,
   - evidence link or local fallback path,
   - severity and user impact,
   - marker `IA generated QA bug: {parentTicketKey}`.
5. Comment on the parent ticket with the bug link and leave the parent in QA.
6. If code work is required, invoke `dev-flow-start-ticket` for the bug ticket. The new bug ticket becomes the active lock only after the parent link is recorded.
7. If the defect is only data, environment, or unclear requirements, stop after filing the bug and report the non-code owner.

## OpenSpec Policy

Default to OpenSpec for product bugs and hotfixes. Skip OpenSpec only when the bug is explicitly marked `no-openspec`, `ops-only`, or the user explicitly requests no OpenSpec.

## Output

Report the parent ticket, QA validation failure, bug ticket link, evidence path or URL, whether a fix workflow was started, and the handoff owner for non-code defects.

## Failure Rules

- Missing parent ticket or QA evidence: stop and ask for the missing identifier.
- Ticket context lock mismatch: stop before filing or linking a bug.
- Unsafe evidence contains secrets: redact or discard unsafe evidence before commenting.
- Existing linked bug with the same marker and tested commit: reuse it instead of creating a duplicate.
- Plane mutation fails: do not create branches or OpenSpec changes until the bug relationship is recorded.
