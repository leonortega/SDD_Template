# Architecture Decision Records (ADR)

One architectural decision per file. Humans own ADRs; AI can draft proposals but must not finalize them without the
human owner.

## Index

| ADR                                                        | Decision                                   |
| ---------------------------------------------------------- | ------------------------------------------ |
| [ADR-0001](ADR-0001-repository-decisions.md)               | Repository remains an SDLC shell            |
| [ADR-0002](ADR-0002-product-layout-and-deployment.md)      | Product layout (`apps/` + `packages/`) and deployment model |
| [ADR-0003](ADR-0003-shared-database-and-migrations.md)     | Shared database engine + migration jobs (runtime-agnostic) |
| [ADR-0004](ADR-0004-config-driven-role-registry.md)        | Config-driven role registry (`infra/deployment/roles.json`) |
| [ADR-0005](ADR-0005-no-reference-apps.md)                  | No reference apps — `apps/` empty, shapes in `.template/scaffold/` |

## Template

```markdown
# ADR-NNNN: <Title>

## Status

Accepted | Proposed | Superseded

## Context

## Decision

## Consequences
```
