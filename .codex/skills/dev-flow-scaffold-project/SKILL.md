---
name: dev-flow-scaffold-project
license: MIT
description: Generate the implementation scaffold for the selected tech stack using AI, not a fixed template list. Reads frontend/backend/database from project-profile.local.json, runs the Mandatory Skill Catalog Review to activate the relevant skills (architecture, TDD, CI, k8s), and generates build manifests, test setup, Dockerfiles, CI workflows, and k8s artifacts for the actual stack. Use automatically after set-project-stack (scaffoldRequired/nextStage), or when the user asks to scaffold the project.
---

<!-- TIER 3: STAGE-SPECIFIC - AI-driven project scaffold after stack selection -->

# AI-Driven Project Scaffold

## Overview

The template repo is **intentionally stack-agnostic** — it ships no `package.json`,
no `playwright.config.ts`, no `src/` or `tests/` folders, and no Dockerfiles. The
stack is defined by the user via `set-project-stack` and recorded in
`.codex/project-profile.local.json` (`stack.frontend`, `stack.backend`,
`stack.database`).

`set-project-stack` only creates the deterministic skeleton (`src/` + `tests/`)
and then marks `scaffoldRequired: true` with `nextStage: dev-flow-scaffold-project`.
**This skill resolves everything else as an AI** — the exact files depend on the
chosen stack, so they can never come from a fixed list of combinations.

> **Rule: never assume a stack.** Read the actual `stack.frontend` /
> `stack.backend` / `stack.database` values before generating anything. If the
> stack is unset, incomplete, or ambiguous, ask the user — do not guess.

## Shared Context

Run inside the active ticket's delivery context. Read
`.codex/skills/_shared/delivery-contract.md` and
`docs/conventions/context-management.md` before scaffolding, and keep the
generated scaffold scoped to the ticket's acceptance criteria. The stack must
come from the user's explicit decision in `.codex/project-profile.local.json` —
never inferred from existing files.

## When To Use

- Automatically: right after `set-project-stack` (the CLI returns
  `nextStage: dev-flow-scaffold-project`).
- On request: "scaffold the project", "generate the project files", "create the
  initial structure for the stack".

## Workflow

Follow these steps in order. Do not skip steps.

### 1. Read the stack

Read `.codex/project-profile.local.json` and extract `stack.frontend`,
`stack.backend`, `stack.database` (each is `{applies: bool, value: str}`).
Also read `stack.languages`, `stack.frameworks`, `stack.testFrameworks` when
present. Summarize the stack for the user, e.g.:
"Frontend: React + TypeScript · Backend: FastAPI · Database: PostgreSQL".

If `metadataValidationStatus == "needs-user-validation"`, confirm the stack
with the user before scaffolding.

### 2. Mandatory Skill Catalog Review

Consult `.codex/skills/manifest.json` (per AGENTS.md) and activate the skills
relevant to the selected stack. Typical activations:

- Architecture: `clean-architecture`, `clean-code`, `domain-modeling`,
  `architecture-patterns` — structure of `src/` per stack
- Testing: `tdd`, `e2e-testing-patterns`, `webapp-testing` —
  unit/integration/architecture test setup
- CI: `configure-ci-workflows` — build/test/package workflows for the stack
- Deployment: `dev-ops-configure-k8s`, `kubernetes-manifest-authoring` —
  Dockerfiles + k8s artifacts for the stack's runtimes
- Quality: `ponytail` (auto), `design-pattern-review` as applicable

Declare the activated skills in a `Skills used:` block. State why a skill was
skipped when it does not apply (e.g., "C# coding standards — this is a
TypeScript project").

### 3. Resolve the scaffold per stack (AI decision)

For each domain, decide what the stack's **native tooling and conventions**
require, then generate the files. Examples, never exhaustive:

- **Frontend JS/TS** (react, vue, angular, svelte, next, nuxt, ...): folder
  layout under `src/`, `package.json` (dev/build/test/e2e scripts), test
  framework config (vitest/jest), E2E tool (playwright/cypress), `e2e/`
  folder, `playwright.config.ts`/`cypress.config.ts` (BASE_URL-aware for QA).
- **Frontend .NET** (blazor, asp.net razor, mvc): solution + project layout
  under `src/`, `*.csproj`, test project(s), `dotnet test` wiring.
- **Backend** (fastapi/django/flask, node/express, spring, rails, go, ...):
  app entry point, dependency manifest (`requirements.txt`, `package.json`,
  `pom.xml`, `Gemfile`, `go.mod`, ...), settings/env handling, `/health`
  endpoint (k8s probes use it), test framework per stack.
- **Database** (postgres, mysql, sqlite, mongodb, redis, ...): connection
  config, migration tooling, dev seed/scripts.

Generate only what the stack needs. Do not generate files for a stack that was
not selected (`applies: false`).

### 4. Generate build/deploy artifacts

- **Dockerfiles** per app role (web + api) matching the stack's runtime:
  multi-stage builds, correct base images, healthchecks (`/health`), non-root
  user when practical. See `dev-ops-configure-k8s` / `kubernetes-manifest-authoring`.
- **CI workflows** for the stack's build/test commands via
  `configure-ci-workflows`.
- **K8s manifests** only if missing (`scaffold-k8s` already generates the
  deterministic Deployment/Service/Kustomize from `apps.json`; the AI supplies
  the stack-specific Dockerfiles/nginx.conf/.dockerignore).

### 5. Scaffold quality requirements (proven by E2EPROJECT-37)

Apply these hard-won requirements to **every** generated scaffold. They are
non-negotiable — each one prevented a real failure in a consumer delivery:

1. **Runtime write-access (non-root container):** if the app writes to its
   workdir on boot (SQLite `Data Source=todos.db`, file caches, uploads), the
   Dockerfile must `RUN chown -R <uid>:<gid> /app` **before** the `USER <non-root>`
   line — otherwise the container CrashLoopBackOffs with
   `unable to open database file`. Verify with `docker run` + curl a DB-backed
   endpoint **before** merging (catches the crash loop in seconds without a
   cluster round-trip).
2. **Source-tree hygiene vs. `.gitignore`:** never let a generic `**/data/`
   rule swallow a source `Data/` layer. On Windows (`core.ignorecase`) the rule
   matches `Data/` case-insensitively and silently drops the file from CI
   checkouts → `CS0234: 'Data' does not exist`. Add negations
   (`!src/<app>/Data/`, `!src/<app>/Data/**`) and verify with
   `git check-ignore <file>` + `git ls-files`. A green local build is **not**
   proof the CI build will work.
3. **Dependency versions must be current enough for SCA:** default frontend
   scaffolds to **React ≥ 19.2.7 + react-router 8** (`react-router-dom` was
   merged into `react-router` in v8; the v6/7 line still ships MEDIUM/HIGH
   advisories like GHSA-qwww-vcr4-c8h2). If the generated lockfile triggers
   Trivy findings, upgrade rather than suppress.
4. **Python-in-CI column-0 rule:** any `python3 -c "..."` or heredoc body
   embedded in a workflow `run: |` block must start at **column 0** of the
   generated script (YAML keeps its indentation offset; Python and `<< EOF`
   terminators reject it). Validate extracted scripts with `bash -n` and
   `python -m py_compile`.

### 6. Validate before handoff

Run the stack's local quality gates on the scaffold:

1. Build succeeds (`npm run build` / `dotnet build` / `mvn compile` / `go build` / ...).
2. Tests pass (unit + integration + at least one architecture test).
3. Dockerfiles build (`docker build`) when Docker is available, then `docker run`
   and curl the health/DB endpoints (requirement 1 above).
4. Manifests are valid (`kubectl apply --dry-run=client` / `kustomize build`).
5. SCA is clean (`trivy fs` / `npm audit`) or upgrades are documented.

Fix failures before reporting done. If a gate cannot run, document the reason
and residual risk.

### 7. Record and continue

- Confirm the generated files list to the user.
- Optionally record a durable knowledge note in `knowledge/` when a
  non-obvious stack decision was made.
- The next flow stage continues normally (no manual next-step question — the
  process is deterministic).

## Deliverables Checklist

- [ ] `src/` structure per architecture skill for the stack
- [ ] `tests/` with unit + integration (+ architecture) test setup per TDD skill
- [ ] Build manifest(s) for the stack's native tooling
- [ ] Test config + runner wiring
- [ ] Dockerfile(s) per app role (or documented skip)
- [ ] CI workflow(s) using the stack's commands
- [ ] k8s stack-specific artifacts (nginx.conf/.dockerignore) where applicable
- [ ] All local quality gates green (or documented residual risk)

## Output

Report the generated file list, the validation results of each local quality
gate (build, tests, Dockerfiles, k8s manifests), any residual risk for gates
that could not run, and the handoff point to the next delivery stage.

## Failure Rules

- Stop if the stack is unset, incomplete, or ambiguous — ask the user, do not guess.
- Stop if a local quality gate fails; fix before reporting done.
- Stop if the generated scaffold contradicts the selected stack or ticket scope.
