# Documentation

This folder is documentation for humans and maintainers: how the project is built. Operational knowledge that
agents consult while implementing, debugging, reviewing, and fixing code lives in the top-level
`knowledge/` folder instead.

## Document Index

| Path                                        | Purpose                                                                                                                   | Typical author       | AI updatable |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | -------------------- | ------------ |
| [Architecture](architecture/system.md)      | Overall architecture, layers, responsibilities                                                                            | Human + AI           | Yes          |
| [Deployment](architecture/deployment.md)    | Deployment topology, environments, CI/CD, observability                                                                   | Human + AI           | Yes          |
| [ADR](adr/README.md)                        | One architectural decision per file                                                                                       | Human (AI can draft) | Draft only   |
| [Modules](modules/README.md)                | Responsibilities, public APIs, dependencies of each module                                                                | AI                   | Yes          |
| [API](api/README.md)                        | API contracts and examples                                                                                                | AI                   | Yes          |
| [Workflows](workflows/README.md)            | End-to-end business or technical workflows (linear ticket→PROD flow, supporting workflows, parallel delivery, setup flow) | AI                   | Yes          |
| [Knowledge coverage](knowledge-coverage.md) | Maps every `knowledge/` file to its template home (skill, script, workflow)                                               | AI                   | Yes          |
| [Conventions](conventions/README.md)        | Coding, testing, git, and agent conventions                                                                               | Human                | Propose only |

## AI Updatable Docs

Docs marked **AI updatable** may be edited by agents during implementation, review, QA, deployment, and
retrospective work. Use the `docs-knowledge-maintenance` skill to update them, and record
`Docs updated: <files>` in PR bodies and OpenProject handoff comments.

Docs marked **Propose only** or **Draft only** must not be edited directly by agents; propose changes
to the human owner instead. If a finding is enforceable automation behavior, update
`.codex/skills/_shared/delivery-contract.md` plus affected skills and tests instead of these docs.
