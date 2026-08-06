---
name: docs-knowledge-maintenance
description: >-
  Update AI-updatable documentation (docs/) and knowledge base entries (knowledge/) using the standard template and
  classification rules.
---

# Docs & Knowledge Maintenance

Use this skill whenever a workflow discovers durable context that should be captured in `docs/` or
`knowledge/`, or when the user asks to update documentation or the knowledge base.

## Overview

This skill is the mandatory gate for updating AI-updatable documentation (`docs/`) and the knowledge
base (`knowledge/`) after any workflow discovers durable context. It always starts with the
deterministic `classify-knowledge` helper (Workflow step 1) to pick the candidate files, then applies
the classification table, standard template, conflict, and security rules below. The classifier decides
**which** files may need updating; this skill decides **what content** to write.

## Shared Context

Follow `.codex/skills/_shared/skill-startup.md` for the tiered read order. This skill owns updates to
`docs/` and `knowledge/`; authoritative findings belong in `docs/`, enforceable automation belongs in
`.codex/skills/_shared/delivery-contract.md` plus affected skills and tests, and reusable
non-authoritative knowledge belongs in `knowledge/`. For the authority order and context layers, read
`docs/conventions/context-management.md`.

## Purpose

The repository keeps two context layers:

- `docs/` — documentation for humans and maintainers (architecture, ADRs, modules, APIs, workflows,
    conventions). Only files marked **AI updatable** may be edited directly by agents.
- `knowledge/` — operational knowledge that agents actively consult while implementing, debugging,
    reviewing, and fixing code. Agents may add and update entries freely, following the standard
    template.

## Read First

- `docs/README.md` — document index and which docs are AI updatable vs. propose-only
- `knowledge/README.md` — knowledge base index, read/write policy, and standard template

## AI Updatable Docs

From `docs/README.md`, the following may be edited directly by agents:

- `docs/architecture/system.md` (Human + AI)
- `docs/architecture/deployment.md` (Human + AI)
- `docs/modules/*.md` (AI)
- `docs/api/*.md` (AI)
- `docs/workflows/*.md` (AI)

Docs marked **Propose only** or **Draft only** must NOT be edited directly:

- `docs/adr/` (Human; AI may draft)
- `docs/conventions/` (Human; propose only)

If a finding is enforceable automation behavior, update `.codex/skills/_shared/delivery-contract.md`
plus affected skills and tests instead of these docs.

**README validation commands for installed targets** must be installed CLI smoke checks (e.g.
`python -m tools.sdd_cli environment-lab health-check`) — never `python -m unittest
tools.sdd_cli.tests.test_cli`, because the installer excludes `tools/sdd_cli/tests` from installed
consumer repositories.

## Knowledge Classification

When the run discovers reusable non-authoritative knowledge, classify it into `knowledge/`:

| Finding                                                           | Target                                                     |
| ----------------------------------------------------------------- | ---------------------------------------------------------- |
| Known error with root cause                                       | `knowledge/errors/<error>.md`                              |
| Validated reusable fix                                            | `knowledge/fixes/<fix>.md`                                 |
| Recommended pattern                                               | `knowledge/patterns/<pattern>.md`                          |
| Practice to avoid                                                 | `knowledge/anti-patterns/<pattern>.md`                     |
| Diagnostic guide / checklist                                      | `knowledge/troubleshooting/<topic>.md`                     |
| QA result, release lesson, or workflow lesson                     | `knowledge/lessons-learned/<topic>.md`                     |
| Reusable prompt for a common agent task                           | `knowledge/prompts/<task>.md`                              |
| Architecture or implementation knowledge consulted while coding   | `knowledge/architecture/` or `knowledge/implementation/`   |
| Reference material (project maps, module maps)                    | `knowledge/references/<topic>.md`                          |

## Standard Template

Every knowledge document must use the same template so agents can retrieve and reason over the content consistently:

```markdown
# Title

## Summary

## Problem

## Context

## Root Cause

## Solution

## Alternatives

## Limitations

## Examples

## Related Documents

## Tags
```

Include metadata where useful:

```markdown
- Type: Fact | Decision | Pattern | Preference | Deprecated | Risk
- Status: Active | Superseded | Needs Verification
- Source: <file, ticket, PR, commit, command, or date>
- Last verified: YYYY-MM-DD
```

## Workflow

1. **Run the deterministic classifier (MANDATORY first step)** — before classifying or writing
   anything, run the classifier now (or reuse its output from the pre-flight gate or the Durable
   Learning Capture Gate if already run):

   ```bash
   python -m tools.sdd_cli knowledge-search classify --task "<task summary>" --changed-files "<comma-separated changed paths>" --test-results "<test outcome>"
   ```

   It maps the task summary, changed files, and test results to the exact candidate `knowledge/` or
   `docs/` file paths (or `NO_CHANGES`). Update only those candidate files. If the classifier returns
   `NO_CHANGES`, stop and record `Knowledge updated: none` / `Docs: no durable context changes` — do
   not invent files to update.
2. **Classify the finding** — start from the classifier's candidate list and confirm or refine the
   category: authoritative → `docs/` or delivery contract; enforceable automation →
   `.codex/skills/_shared/delivery-contract.md` plus affected skills and tests; reusable
   non-authoritative → `knowledge/`.
3. **Verify the source** — current files, command output, OpenProject, Gitea, Nexus, health checks,
   QA evidence, or explicit user instruction. Do not store assumptions as facts.
4. **Choose the target file** using the tables above.
5. **Apply the standard template** and keep entries small, source-backed, and reviewable.
6. **Handle conflicts** — if an older entry is contradicted, mark it `Superseded` and link the
   replacement. Delete entries only when harmful, secret-bearing, or purely noise.
7. **Never store secrets** — no API tokens, passwords, cookies, secret-bearing URLs, credentials, or private log
contents.
8. **Record the change** in the final handoff:
   - `Docs updated: <files>` or `Docs: no durable context changes`
   - `Knowledge updated: <files>` or `Knowledge updated: none`
   - `Knowledge consulted: <files>` or `Knowledge consulted: none` when a consult ran before acting

## Output

Report the updated candidate files exactly as the classifier selected them: `Docs updated: <files>` /
`Docs: no durable context changes`, `Knowledge updated: <files>` / `Knowledge updated: none`, and
`Knowledge consulted: <files>` / `Knowledge consulted: none` when a pre-action consult ran. If the
classifier returned `NO_CHANGES`, report its `decision: NO_CHANGES` output as the validation evidence
instead of an empty update list.

## Failure Rules

- If `knowledge-search classify` fails or returns an error, stop the update step and report the
  blocker — do not hand-pick target files without the deterministic candidate list.
- If the classifier returns `NO_CHANGES`, do not force an update; record the `none` markers.
- If a candidate file does not exist yet, create it with the standard template; never append to a
  `README.md` index instead of its category file.
- Never store secrets (see step 7) — a secret-bearing entry must be removed or replaced with a
  reference to a safe evidence location.
- If an older entry contradicts a new finding, mark it `Superseded` and link the replacement; never silently delete
history.

## Search First

Before adding a knowledge entry, search the existing knowledge base to avoid duplication:

```bash
python -m tools.sdd_cli knowledge-search search --query <symptom>
python -m tools.sdd_cli knowledge-search search --list-topics
```

If an entry already covers the topic, update it instead of creating a duplicate.
