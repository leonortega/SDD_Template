# AI SDLC + DevOps Laboratory

This repository is a laboratory for testing an AI-assisted SDLC and DevOps flow using local and free software where possible. It is meant to prove the workflow end to end: ticket intake, specification, implementation flow, review, artifact handling, deployment, QA evidence, release promotion, rollback, and operational learning.

This repository is not a production-ready product template yet. It is not a product application either. The current goal is to keep a reusable lab where a separate test project can exercise the full delivery flow and help improve the tool before it becomes something ready for real product adoption.

## What This Lab Gives You

- A repeatable SDLC workflow driven by tickets, OpenSpec changes, and Codex skills.
- A local DevOps platform shape built around free/open-source tools for source control, CI, artifacts, deployment, and observability.
- Provider adapters for OpenProject, Gitea, Nexus, Docker Desktop, and observability tools.
- Versioned install and update commands so a separate test repository can consume lab releases.
- Guardrails for quality gates, secret safety, PR review, QA evidence, release lineage, and rollback.

## How The Flow Works

The intended delivery flow is:

```text
Idea or ticket
  -> OpenProject work item
  -> OpenSpec proposal, design, specs, and tasks
  -> feature branch from dev
  -> implementation with focused tests
  -> pull request in Gitea
  -> CI and review gates
  -> immutable artifact in Nexus
  -> DEV and QA deployment
  -> executable QA evidence
  -> merge/release approval
  -> explicit PROD promotion
  -> rollback or hotfix when needed
```

The tool is intentionally conservative:

- Sample project source code is added only after the project stack is selected.
- Generated runtime evidence stays out of Git.
- Secrets and local machine settings stay in ignored local files.
- Production promotion is explicit; QA success alone does not automatically release to PROD.
- Artifacts are built once and promoted through environments instead of rebuilt per environment.

## Repository Shape

```text
.codex/             AI workflow skills, provider adapters, policies, and profile files
.gitea/             Gitea Actions workflow templates
docs/               Architecture, development, deployment, and context guidance
infra/              Local platform templates and deployment topology
openspec/           OpenSpec configuration and future change specs
tools/              Helper CLI used by the workflow
artifacts/          Ignored runtime/evidence output
```

The product folders are intentionally absent:

```text
src/
tests/
```

Create them only in a separate test project repository or after a sample project stack is chosen.

## Install In A Test Repository

From this lab repository, install the latest final release into a separate test repository:

```bash
python -m tools.sdd_cli template-installer install --target C:\path\to\test-repo
```

Install a specific pinned version:

```bash
python -m tools.sdd_cli template-installer install --version v0.1.0 --target C:\path\to\test-repo
```

Update an installed test repository:

```bash
python -m tools.sdd_cli template-installer update --version v0.2.0 --target C:\path\to\test-repo
```

If `--version` is omitted, the installer uses the latest final Git tag matching `vMAJOR.MINOR.PATCH`. Release candidates such as `v0.1.7-rc.2` are ignored by that default.

The install writes:

```text
.codex/sdd-tool-version.json
```

That manifest records the installed version, source repo, source commit, checksum, managed files, preserved local files, and local Git bootstrap status. If the target is not already a Git repository, install initializes it locally on `dev` without adding a remote. Gitea remote mapping is configured later during Gitea setup.

The installer also seeds the required `.codex/memory/MEMORY.md`, `.codex/memory/memory_summary.md`, and `.codex/memory/retrieval-policy.md` files so startup guidance works before any product memory exists. Future updates replace only managed tool files. Test-project files such as `.codex/project-profile.local.json`, local memory files, secrets, product source, tests, and product OpenSpec changes are preserved.

## Tools Used

- Codex skills: AI workflow instructions for planning, implementation, review, QA, deployment, rollback, and retrospective work.
- OpenSpec: structured proposal, design, spec, and task workflow for product changes.
- OpenProject: ticket and work package workflow.
- Gitea: repository hosting, pull requests, review, and Actions workflows.
- Nexus: immutable artifact storage and release lineage.
- Docker Desktop: local container runtime for the lab stack.
- Seq: application log search and inspection.
- Grafana: dashboards, health checks, and alert visibility.
- Dozzle: container log visibility.
- Playwright: browser-level QA and UI validation when a future product has a UI.
- Python `tools.sdd_cli`: deterministic helper CLI for install/update, infrastructure commands, delivery checks, manifest handling, and workflow rendering.

## Use It In Chat

Most work is started by asking your AI coding agent to run one workflow stage. Use short, explicit prompts and keep one ticket or release goal active at a time.

Follow this normal lab delivery sequence:

```text
1. Configure this repository for my sample project stack and local delivery tools.
2. Create or refine an OpenProject ticket for this project idea: <idea>.
3. Propose an OpenSpec change for ticket <ticket-key>.
4. Start implementation for ticket <ticket-key>.
5. Continue implementation for ticket <ticket-key>.
6. Verify the OpenSpec change for ticket <ticket-key>.
7. Create a pull request for ticket <ticket-key>.
8. Run PR review for ticket <ticket-key>.
9. Address PR review feedback for ticket <ticket-key>.
10. Continue after merge and deploy ticket <ticket-key> to QA.
11. Run the configured QA gate for ticket <ticket-key>.
12. Promote the QA-approved release to PROD.
13. Check pipeline status for ticket <ticket-key>.
```

Use these operational prompts when needed:

```text
Rollback PROD to the previous verified release.
Run an urgent PROD hotfix for <incident or ticket>.
Show pipeline status for <ticket-key>.
Audit recent delivery workflow and capture improvements.
Archive the completed OpenSpec change for <ticket-key>.
```

For a fresh test project, a typical chat flow is:

```text
Install this SDLC tool into C:\path\to\test-repo.
Configure the test repo for <stack>, <deployment target>, and <quality gates>.
Create the first project ticket for: <feature idea>.
Propose the OpenSpec change for that ticket.
Start implementation.
```

## Common Commands

Start local delivery infrastructure:

```bash
python -m tools.sdd_cli environment-lab compose-up
```

Stop local delivery infrastructure:

```bash
python -m tools.sdd_cli environment-lab compose-down
```

In an installed test repository, run smoke checks for the installed helper CLI:

```bash
python -m tools.sdd_cli environment-lab audit
python -m tools.sdd_cli guidance discover
```

In this lab repository only, run helper tests when test dependencies are available:

```bash
python -m pytest tools/sdd_cli/tests
```

If `pytest` is not installed, run the lab repository's stdlib test suite:

```bash
python -m unittest tools.sdd_cli.tests.test_cli
```

## Documentation

- [Architecture](docs/architecture.md): repository topology, sources of truth, and install boundary.
- [Development](docs/development.md): how to add a sample project stack and use a test fixture repository.
- [Deployment](docs/deployment.md): deployment shell and app target wiring.
- [Context Management](docs/context-management.md): authority order, freshness checks, and handoff rules.
- [Parallel Delivery](docs/parallel-delivery.md): optional multi-ticket coordination.
- [Delivery Contract](.codex/skills/_shared/delivery-contract.md): agent-enforced delivery policy.

## Current Status

This project is a product-free SDLC and DevOps laboratory. It is ready to be versioned and installed into a separate test repository so the full workflow can be exercised with a real sample project. It should not be presented as a finished production template yet.

## Thanks

This tool uses and integrates ideas, workflows, or runtime support from the following external projects and platforms:

- [OpenAI Codex](https://developers.openai.com/codex/) for AI-assisted repository work.
- [OpenAI Codex Agent Skills](https://developers.openai.com/codex/skills) for the skill-based workflow model.
- [OpenAI Skills repository](https://github.com/openai/skills) for reusable external skill patterns.
- [OpenAI Playwright skill](https://github.com/openai/skills/tree/main/skills/.curated/playwright) and [OpenAI Playwright Interactive skill](https://github.com/openai/skills/tree/main/skills/.curated/playwright-interactive) for browser automation workflow guidance.
- [OpenAI Security Best Practices skill](https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices) for secure-by-default review guidance.
- [Caveman skill](https://github.com/JuliusBrussee/caveman/tree/main/plugins/caveman/skills/caveman) for terse, token-saving assistant communication.
- [Domain Modeling skill](https://github.com/mattpocock/skills/tree/main/skills/engineering/domain-modeling) for domain language and modeling guidance.
- [Grill Me skill](https://github.com/mattpocock/skills/tree/main/skills/productivity/grill-me), [Grill With Docs skill](https://github.com/mattpocock/skills/tree/main/skills/engineering/grill-with-docs), and [Grilling skill](https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling) for planning and design interrogation.
- [TDD skill](https://github.com/mattpocock/skills/tree/main/skills/engineering/tdd) for test-driven implementation guidance.
- [Ponytail skills](https://github.com/DietrichGebert/ponytail/tree/main/skills) for minimal-solution implementation and complexity review guidance.
- [OpenSpec](https://openspec.dev/) for structured software change specifications.
- [OpenProject](https://www.openproject.org/) for project and ticket management.
- [Gitea](https://about.gitea.com/) and [Gitea Actions](https://docs.gitea.com/usage/actions/overview) for Git hosting, pull requests, review, and CI automation.
- [Sonatype Nexus Repository](https://www.sonatype.com/products/sonatype-nexus-repository) for artifact storage and promotion.
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) and [Kubernetes](https://kubernetes.io/) for local deployment workflows.
- [Grafana](https://grafana.com/), [Seq](https://datalust.co/seq), and [Dozzle](https://dozzle.dev/) for observability workflows.
- [Playwright](https://playwright.dev/) for browser automation and QA validation.
- [Python](https://www.python.org/) and the Python standard library for the local helper CLI.
