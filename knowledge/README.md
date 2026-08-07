<!-- TIER 2: SEMI-STABLE - Knowledge base index and policy, loaded at startup of every stage -->

# Knowledge Base

This repository keeps three context layers:

- `docs/` — documentation for humans and maintainers (architecture, ADRs, modules, APIs, workflows, conventions).
- `knowledge/` — operational knowledge that agents actively consult while implementing, debugging, reviewing, and fixing
code.
- `openspec/specs/` — archived OpenSpec behavior specs (created when a change is archived; delta specs are synced to
`openspec/specs/<capability>/spec.md`). Agents consult these as an additional knowledge source for durable behavior
standards, alongside `docs/` and `knowledge/`. The folder is optional — it does not exist until the first change is
archived, and `knowledge-search` skips it silently until then.

This file is the index, the read/write policy, and the standard template for the knowledge base. Use it at the start of
planning, implementation, review, QA, deployment, rollback, hotfix, and retrospective work.

Knowledge is guidance only. It must never override the latest user request, the active ticket, the active OpenSpec
change, the merged project profile, the shared delivery contract, canonical docs, current files, durable evidence, or
live tool output.

## Categories

| Path                                   | Purpose                                                                       | Typical author |
| -------------------------------------- | ----------------------------------------------------------------------------- | -------------- |
| `knowledge/errors/`                    | Known errors: symptoms, root causes, validated fixes                          | AI             |
| `knowledge/fixes/`                     | Reusable fixes that have been validated                                       | AI             |
| `knowledge/patterns/`                  | Recommended implementation patterns                                          | AI             |
| `knowledge/anti-patterns/`             | Practices to avoid                                                           | AI             |
| `knowledge/troubleshooting/`           | Diagnostic guides and checklists                                              | AI             |
| `knowledge/lessons-learned/`           | Knowledge gained from completed work (QA findings, release lessons, workflows)| AI             |
| `knowledge/prompts/`                   | Reusable prompts for common agent tasks                                      | AI             |
| `knowledge/architecture/`              | Architecture knowledge agents consult while coding                           | AI             |
| `knowledge/implementation/`            | Implementation knowledge agents consult while coding                         | AI             |
| `knowledge/references/`                | Reference material such as project maps and module maps                      | Human + AI     |

## Read Policy

Read the knowledge base when starting:

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

1. Read this file (`knowledge/README.md`).
2. Open only the category folders relevant to the task.
3. Verify all task-critical facts against current repo files, OpenProject, OpenSpec, Gitea, Nexus, Git, or live command
output.

## Search

Use the deterministic search helper with concrete symptom terms (error text, config keys, tool names, workflow stages,
marker names):

```bash
python -m tools.sdd_cli knowledge-search search --list-topics
python -m tools.sdd_cli knowledge-search search --query Api__BaseUrl
python -m tools.sdd_cli knowledge-search search --query Gitea,reviewer
```

Search covers all three Markdown KB layers — `knowledge/`, `docs/`, and `openspec/specs/` (docs/ and specs/ only when
they exist); results carry a `root` field so callers can tell operational knowledge, human docs, and archived behavior
specs apart.

Search accelerates diagnosis; it does not replace freshness checks against current files and live systems.

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

Use one file per topic (e.g. `knowledge/errors/playwright-timeout.md`). Keep entries small, source-backed, and
reviewable.

## Write Policy

Agents may propose or write knowledge updates only when the information is reusable and source-backed.

Good candidates:

- repeated CI, QA, deploy, or review failures
- agent-caused workflow mistakes that are likely to recur (hook rejections, wrong commit prefixes, wrong tool
boundaries, skipped preflight steps)
- durable command or setup corrections
- module ownership or behavior discovered during implementation
- release, rollback, artifact, or QA lessons
- workflow decisions useful across tickets
- user preferences for this repository's agentic workflow

Poor candidates:

- one-off debugging traces
- unverified assumptions
- secrets or credentials
- temporary local machine state
- full logs
- speculative architecture ideas not accepted by the user
- stale ticket status that should be read from OpenProject or Gitea

## Update Process

Run the deterministic classifier first to pick the candidate file paths:

```bash
python -m tools.sdd_cli knowledge-search classify --task "<task summary>" --changed-files "<comma-separated changed paths>" --test-results "<test outcome>"
```

It maps the task summary, changed files, and test results to the exact candidate `knowledge/`, `docs/`, or
`openspec/specs/` file paths (or `NO_CHANGES`). Then update only those candidate files.

1. Classify the finding.
   - Archived-spec edits (`openspec/specs/`) map to the spec file itself — the spec is the durable behavior record, so
   no new `knowledge/` entry is minted for a spec-only change.
   - Authoritative architecture, setup, development, deployment, or context policy belongs in `docs/` (use the
   `docs-knowledge-maintenance` skill for AI-updatable docs).
   - Enforceable automation behavior belongs in `.codex/skills/_shared/delivery-contract.md` plus affected skills and
   tests.
   - Reusable but non-authoritative workflow knowledge belongs in `knowledge/`.
2. Verify the source against current files, command output, OpenProject, Gitea, Nexus, health checks, QA evidence, or
explicit user instruction. Do not store assumptions as facts.
3. Choose the target file:
   - Known error with root cause -> `knowledge/errors/<error>.md`
   - Validated reusable fix -> `knowledge/fixes/<fix>.md`
   - Recommended pattern -> `knowledge/patterns/<pattern>.md`
   - Practice to avoid -> `knowledge/anti-patterns/<pattern>.md`
   - Diagnostic guide -> `knowledge/troubleshooting/<topic>.md`
   - QA result, release lesson, or workflow lesson -> `knowledge/lessons-learned/<topic>.md`
   - Reusable prompt -> `knowledge/prompts/<task>.md`
   - Reference material -> `knowledge/references/<topic>.md`
4. Use the standard template above. Include metadata where useful: `- Type: Fact | Decision | Pattern | Preference |
Deprecated | Risk`, `- Status: Active | Superseded | Needs Verification`, `- Source: <file, ticket, PR, commit, command,
or date>`, `- Last verified: YYYY-MM-DD`.
5. If an older entry is contradicted, mark it `Superseded` and link the replacement entry.
6. Keep entries small and reviewable. Do not use the knowledge base as a scratchpad.

## Staleness And Conflict Handling

- Treat knowledge as stale if current files or live tools disagree.
- Update knowledge when a verified contradiction is found.
- Mark old entries as `Superseded` instead of silently deleting useful history.
- Delete entries only when they are harmful, secret-bearing, or purely noise.
- Never let knowledge override the authority order in `docs/conventions/context-management.md`.

## Security

Do not store:

- API tokens
- passwords
- cookies
- secret-bearing URLs
- generated OpenProject secrets
- Azure credentials
- local service credentials
- contents of ignored `.local` config files
- private logs copied from local containers or databases

Store references to safe evidence locations instead of copying sensitive evidence into knowledge.
