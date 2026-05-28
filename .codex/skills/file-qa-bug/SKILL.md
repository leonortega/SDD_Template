---
name: file-qa-bug
description: Create a linked Plane bug from failed QA evidence, preserve failure context, and start a focused fix workflow when code changes are required. Use when test-e2e finds a product defect, QA fails after deployment, or Codex needs to create a follow-up bug ticket from QA evidence.
---

# File QA Bug

## Overview

Use this skill when QA finds a product defect after a ticket has reached QA. The original ticket stays in QA unless the user explicitly changes workflow policy. Create a linked bug with evidence, then start the normal fix workflow only when the defect requires code work.

Before filing or linking tickets, read `.codex/skills/_shared/delivery-contract.md` for stable markers, rerun behavior, and QA defect ownership rules.

## Configuration

Read `.codex/client-tools.local.json` first. Required values are Plane settings and Git settings when a fix branch is needed.

Never print or store real tokens, cookies, credentials, or sensitive QA payloads.

## Workflow

1. Resolve the parent Plane ticket, failed QA run, tested commit, artifact, QA URL, and evidence path or URL.
2. Confirm the failure is a product defect, not tooling, missing credentials, missing test data, unreachable infrastructure, or evidence upload failure.
3. Create or reuse a linked Plane bug ticket with:
   - parent ticket key,
   - tested commit and artifact,
   - QA environment and URLs,
   - failed scenario and expected/actual behavior,
   - evidence link or local fallback path,
   - severity and user impact,
   - marker `IA generated QA bug: {parentTicketKey}`.
4. Comment on the parent ticket with the bug link and leave the parent in QA.
5. If code work is required, invoke `plane-start-ticket` for the bug ticket.
6. If the defect is only data, environment, or unclear requirements, stop after filing the bug and report the non-code owner.

## OpenSpec Policy

Default to OpenSpec for product bugs and hotfixes. Skip OpenSpec only when the bug is explicitly marked `no-openspec`, `ops-only`, or the user explicitly requests no OpenSpec.

## Failure Rules

- Missing parent ticket or QA evidence: stop and ask for the missing identifier.
- Unsafe evidence contains secrets: redact or discard unsafe evidence before commenting.
- Existing linked bug with the same marker and tested commit: reuse it instead of creating a duplicate.
- Plane mutation fails: do not create branches or OpenSpec changes until the bug relationship is recorded.
