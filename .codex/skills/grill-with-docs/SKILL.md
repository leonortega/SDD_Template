---
name: grill-with-docs
description: A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go.
disable-model-invocation: true
---

Run a `/grilling` session, using the `/domain-modeling` skill.

Repo-local adaptation: in this repository, keep the upstream questioning and domain-modeling stance, but write durable output to the existing SDD surfaces. Product or ticket clarity goes to the managed OpenProject block, planned behavior and design go to OpenSpec, durable repository or process knowledge goes to `docs/`, and reusable non-authoritative lessons go to `.codex/memory/`. Do not create `CONTEXT.md` or ADR files unless a separate explicit repo change adopts that model.
