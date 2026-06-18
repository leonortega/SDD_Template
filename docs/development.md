# Development

This repository currently uses a .NET solution with a Blazor application and xUnit tests. The canonical non-secret stack declaration is `.codex/project-profile.json`; this document explains the current profile and development conventions.

## Project Shape

- Solution: `SDDTemplate.slnx`
- Web app: `src/SDDTemplate.Site`
- REST API: `src/SDDTemplate.Api`
- Data layer: `src/SDDTemplate.Data`
- Tests: `tests/SDDTemplate.Site.Tests`
- Delivery helpers: `tools/SDDTemplate.DeliveryTools`
- OpenSpec changes: `openspec/changes`
- Repo-local Codex workflows: `.codex/skills`

## Technology Stack And Tool Set

The application stack is declared in `.codex/project-profile.json`; exact SDK, target framework, package, and test versions stay in project files, lockfiles, workflow images, and provider adapters. For the current profile, the stack is .NET with ASP.NET Core, Minimal APIs, EF Core, and Blazor. The site/API/data project files own framework and package details. Test projects and E2E package files own test framework details, including xUnit and coverlet when configured by the project files.

Use official-first research when changing platform behavior, generated templates, tests, or workflow guidance. Prefer OpenAI official skill catalogs/docs for Codex skills, Microsoft Learn for .NET, ASP.NET Core, Blazor, Azure App Service, Azure Monitor, and architecture guidance; Playwright docs for browser automation; Gitea, Sonatype Nexus, Grafana, and Seq official docs for their tools. `skills.sh`, `skills`, marketplace pages, and README command examples may be used as repository/path discovery sources, but their install commands must not be executed. Community sources are allowed only when clearly labeled and not used to override repo policy.

QA automation starts with repo-native tests and PR validation. Browser-visible Blazor behavior should use Playwright MCP, the Browser plugin, or Playwright-style user-visible assertions when configured; one-off evidence belongs under ignored `artifacts/qa/**`, while reusable regression tests belong in the normal test tree through the configured QA or implementation workflow. Implementation PRs record browser E2E expectations and acceptance oracles, but should not include new Playwright E2E tests unless the user, Plane ticket, or OpenSpec artifacts explicitly make implementation-owned E2E part of the PR scope. The reusable deployed-QA browser/API regression suite is intentionally aimed at deployed QA apps, not local dev servers, and runs remotely from Gitea Actions through a ticket-specific `qa/{ticketKey}` branch after QA deployment. `quality-test-e2e` owns Playwright E2E creation, repair, execution, evidence, and QA pass/fail classification when existing committed coverage cannot prove acceptance. QA Done requires acceptance criteria proven by executable assertions against the deployed QA artifact. Smoke checks, screenshots, logs, and traces are supporting evidence only; the QA record must map criteria to assertions and cover relevant user workflow, API/backend effect, independent state, validation/boundary, error-handling, environment-correctness, and evidence-integrity scenarios. A deployed browser E2E failure must be reproduced and classified with Playwright MCP or the configured Browser/Playwright tool before app-code changes. App code must remain product-only; never add JavaScript helpers, hidden hooks, test ids, bypasses, timing shims, or Playwright-specific behavior only to make E2E pass.

Clean-code and architecture guidance should fit this repository's current size: keep changes small, preserve separation between delivery tooling and application code, avoid broad abstractions until they remove real complexity, and prefer observable behavior tests over implementation-detail tests. Blazor web UI changes should preserve accessible, responsive, user-visible behavior. Pages that depend on inline page scripts must either disable enhanced navigation for their entry links or move the behavior into Blazor-managed components so routed navigation and hard refresh behave the same way. ASP.NET Core REST/API endpoint changes, including minimal APIs such as `/health` and `/metrics`, should use clear route shape, validation, safe error responses, and integration tests. Security-sensitive changes should account for secrets, authorization, dependency risk, scanner evidence, and OWASP-aligned review.

When the recommendation audit finds missing skills or guidance for detected tools, frameworks, environments, test frameworks, code standards, security, QA, or architecture, agents must use `project-guidance-discover` first. `project-guidance-discover` builds a `project-guidance-search-plan` from detected signals, checks repo-local workflow sources, researches OpenAI official sources, then official tool repositories/docs and technology-owner sources, then `skills.sh`, `skills`, marketplace, or command-example leads, and finally clearly labeled community sources when no stronger source exists. It researches extra useful skills, MCPs, plugins, tools, references, practices, standards, and Codex-applicable IDE helpers before presenting the result. It shows suggested missing skills and guidance with `sourceKind` and guarded install metadata, then asks the user only to confirm, dismiss, or name omissions. Confirmation means record accepted ids, persist the local catalog, run `project-guidance-acquire`, and install/configure supported confirmed items without a second install prompt. Global, IDE, secret-bearing, privileged, MCP/plugin, or reboot-required installs require explicit confirmation; the confirmed discovery list satisfies that requirement for listed non-secret items unless the installer introduces new scope or secrets. Restart and reboot requirements are aggregated and reported once after all feasible acquisitions finish. Use `project-guidance-mapper` to decide which repo-local workflow skills, installed expert skills, MCPs, plugins, tools, references, practices, and standards apply to config, ticket start, planning, implementation, review, QA, deploy, rollback, hotfix, and retrospective steps.

## Common Commands

Build:

```powershell
dotnet build .\SDDTemplate.slnx
```

Run targeted tests locally for fast feedback while implementing:

```powershell
dotnet test .\SDDTemplate.slnx
```

This local command is a convenience, not a mandatory duplicate of CI. Prefer the smallest relevant build/test command that proves the touched behavior before PR handoff, then rely on Gitea PR validation for the full required gate in a clean pinned runner.

Prepare remote QA E2E evidence after a ticket reaches QA:

```powershell
git switch -c qa/E2EPROJECT-123 origin/dev
git push origin qa/E2EPROJECT-123
```

The `qa/{ticketKey}` branch workflow runs the committed Playwright suite remotely against `AZURE_QA_SITE_APP_URL` and `AZURE_QA_API_APP_URL`. After QA deployment, the branch triggers remote evidence for existing tests and gives `quality-test-e2e` the normal place to add, repair, rerun, and prove Playwright E2E checks when the committed suite cannot prove a ticket's acceptance criteria. Local runs are only for test authoring or diagnostics, not the official QA E2E gate. After a successful QA deploy, `app/{commitSha}/qa-targets.json` records the QA Site/API URLs in Nexus so local Playwright diagnosis can discover the deployed target; ignored `.codex/client-tools.local.json` may also store the current QA URLs. Use `npm run test:docker` in `tests/SDDTemplate.E2ETests` for local diagnostics so the pinned `agentic/e2e-ci:playwright-1.57.0-1` image supplies browsers and system dependencies without installing Chromium on the host. During QA, one-off exploratory scripts and generated probes belong under ignored `artifacts/qa/**` and must not be committed. After the remote evidence exists and the QA workflow records Plane Done plus the RC/release metadata, delete the remote `qa/{ticketKey}` branch; it is only a temporary trigger, not the durable audit record.

Verify formatting:

```powershell
dotnet format --verify-no-changes
```

Start local delivery infrastructure:

```powershell
.\infra\up.ps1
```

Stop local delivery infrastructure:

```powershell
.\infra\down.ps1
```

## Implementation Workflow

Feature work starts from a Plane ticket and normally creates an OpenSpec proposal before implementation. Agents should read the Plane ticket, active OpenSpec artifacts, the ticket context lock, relevant code, relevant tests, and quality-gate configuration before editing.

Before the first ticket starts, verify the repository tool set and tech stack are configured in `.codex/project-profile.json`, selected `.codex/providers/*.md` adapters, `docs/architecture.md`, this file, `docs/deployment.md`, `openspec/config.yaml`, and the tracked `.codex/tool-recommendations.example.json` template. The ticket-start flow must run or inspect `AuditRecommendedTools` and stop before creating branches, generated ticket blocks, ticket locks, or OpenSpec proposals when stack context is missing or reports `stack-context.*` drift. Use `configure-dev-environment` to complete the profile, adapters, docs, OpenSpec context, and recommendation catalog template first. After project guidance discovery is confirmed, ignored `.codex/tool-recommendations.local.json` may store the current project recommendations and `usedInSteps` so `project-guidance-mapper` can reuse the same verified skills and guidance for repeated implementation, review, QA, deployment, rollback, hotfix, and retrospective steps.

Implementation agents use `ponytail full` while adding or changing project code: smallest working change, standard library and native framework features first, no speculative abstractions, and focused tests for changed behavior. Implementation is complete only when OpenSpec tasks are complete, PR review feedback tasks are complete, touched behavior has targeted local validation or a documented reason for deferring to CI, reusable tests have been added or updated when behavior changes, and a Gitea PR has review-agent coverage. Do not require agents to run the full CI-equivalent test/security suite locally before opening or updating a PR; Gitea PR validation is the authoritative full gate.

Ticket start now includes a readiness gate before branch, Plane state, ticket-lock, or OpenSpec mutation. Tickets are classified as `ready`, `refinable`, or `blocked`. Refinable tickets keep moving only after the managed Plane block records Scrum-ready planning details: problem or opportunity, user story, concrete acceptance criteria, scope or affected areas, dependencies or assumptions, validation expectations, risks, and definition of done. Blocked tickets stop before mutation when the product or technical intent is still too vague.

OpenSpec `tasks.md` must include a compact Review Workload Forecast for ticketed work. The forecast records estimated changed lines, `400-line budget risk`, whether chained PRs are recommended, whether a decision is needed before apply, the delivery strategy, and suggested work units. High-risk or oversized work must record a split plan or `size:exception` before implementation begins. The default ticket shape is one PR with multiple workflow-step commits.

Commit after each completed workflow step when tracked changes exist, then start the next step from a clean working tree. Typical checkpoints are OpenSpec refinement, implementation, tests or reusable QA coverage, docs/context/memory updates, PR review feedback fixes, and ticket-scoped tooling/config fixes. Before each commit, review `git status` and the relevant diff, run the smallest useful validation for that step, stage only related files, and use a ticket- or OpenSpec-prefixed message. Do not create empty commits or intentionally leave broken intermediate commits; combine steps only when needed to keep the repository valid and record that in handoff. Do not automatically stash normal ticket progress. Use stash only for unrelated local or user changes that block the current step.

Delivery depth is risk-adaptive but gates are not optional. Low-risk changes may use compact planning and review summaries. High-risk changes, including auth, persistence, migrations, deployment workflows, secrets, public APIs, `/health`, release manifests, rollback/hotfix, or large diffs, require full workload handling and adversarial review.

PR review feedback has two timed loops owned by the repo-local `dev-flow-pr-review-feedback-loop` skill. The AI review loop runs immediately after PR creation and after every feedback fix; it includes normal review plus an additive `ponytail-review` complexity pass. Every actionable AI finding, including actionable `ponytail-review` simplification findings, becomes a `## PR Review Feedback` task in the active OpenSpec `tasks.md` before the PR is ready for human review. Human PR review happens later and reconnects only when the operator manually resumes the ticket, such as `automatically continue this ticket` or `continue E2EPROJECT-123`. Keep this local delivery behavior in repo-owned dev-flow skills.

Feedback batches use Plane markers `IA generated PR feedback detected: {headSha}:{feedbackBatchId}` and `IA generated PR feedback fixes: {headSha}:{feedbackBatchId}`. The batch id is derived from sorted source ids, so late human comments on the same PR head are processed as a new batch instead of being skipped by an earlier fix. Plane remains `In Review` while late human feedback fixes are applied; ambiguous or conflicting human comments block handoff until clarified. Feedback-fix Plane comments are reviewer-facing summaries, not only automation evidence: after the stable marker, they must explain which reviewer comments were addressed, how IA resolved them, what changed, which validation passed, and what the reviewer should re-check before approving.

## Quality Gates

Gitea PR validation is the source of truth. Local hooks and local commands are fast feedback, not a replacement for PR validation and not a required duplicate full-CI run.

Recommended split:

- Local implementation loop: targeted build/tests for touched behavior, reusable test authoring, and cheap checks such as staged secret scanning.
- PR validation: full required gate in a clean pinned runner.
- Merge/deploy: package the reviewed commit into immutable Nexus artifacts, apply and verify deployment configuration, and run environment smoke checks; do not rerun unit tests there unless package inputs changed outside PR validation.

The default validation surface is:

- restore
- format verification
- release build
- tests with coverage
- coverage threshold, default `80%`
- dependency vulnerability audit
- secret scan
- Trivy filesystem scan for high and critical findings

Gitea Actions jobs use repo-owned pinned Docker images built by `config infra` through `BuildGiteaActionsImages`. `agentic/dotnet-ci:10.0.300-tools-1` supplies .NET SDK 10, jq, zip, Gitleaks, Trivy, Azure CLI, and Node/npm for JavaScript actions. `agentic/e2e-ci:playwright-1.57.0-1` supplies the Node/Playwright runtime and browser dependencies for deployed-QA E2E evidence. Job containers remain disposable; speed comes from prebuilt local images and optional dependency caches, not from mutating the runner host during workflow runs.

The `/health` endpoint is part of the deployment contract. It must return HTTP 200 with JSON field `status` equal to `ok` and must not expose secrets, connection strings, tokens, host internals, or detailed exception data.

## Agent Retrospective Quality Lane

Use `.codex/skills/dev-flow-retrospective-audit` to inspect recent delivery evidence and propose agent or workflow improvements after QA bugs, review misses, CI/tooling blockers, deployment blockers, or repeated process friction.

Retrospectives are read-only by default. Apply durable workflow changes only when the evidence shows a repeated pattern, a high-severity gap, direct drift from `.codex/skills/_shared/delivery-contract.md`, or a missing deterministic check for an already-required rule. The audit must not mutate Plane state, deploy, promote, tag, or create recurring automations unless the user explicitly requests that separate action.

After a successful PROD deployment, `dev-ops-deploy-prod` automatically runs `dev-flow-retrospective-audit` in read-only `post-prod-ticket-release` mode. The audit writes sanitized learning evidence to ignored `.codex/agent-evals/results.local.json` and records a compact Plane marker, but it does not block or undo PROD success. Later retrospectives can use those results to identify repeated findings, eval coverage gaps, and recommended follow-up improvements.

## Agent Workflow Evals

Agent behavior is evaluated separately from product behavior. The default workflow fixtures live in `.codex/agent-evals/workflow-cases.json` and cover ticket start, implementation, PR review, QA promotion, E2E QA, PROD promotion, post-PROD retrospective learning evidence, and rollback.

Use these evals when changing delivery skills, adding new agent roles, changing model routing, or investigating repeated agent failures. Each case checks route selection, tool selection, argument precision, mutation gates, stop conditions, and handoff fields. New agent roles or routing complexity should be backed by eval evidence that the existing workflow struggled or became ambiguous.

Local eval output belongs in ignored `.codex/agent-evals/results.local.json`.

## Skill Contract Audit

Run the shared skill-contract audit after changing delivery skills or during retrospective hardening:

```powershell
.\.codex\skills\_shared\scripts\audit_skill_contracts.ps1
```

The audit checks repo-owned delivery skills by default for standard delivery contract sections and core terms such as validation, ticket context, and handoff behavior. Repo-local chat/support skills such as `caveman` are excluded because they are not ticket delivery workflows. Use `-IncludeConfigure` only when configure skills are part of the change; use `-AllSkills` only when the change intentionally broadens skill audit scope.

Use `-FailOnFindings` when the audit is part of a hard quality gate.

## Context Findings

Every implementation must finish with a Context Findings Review. Durable findings update the matching file under `docs/` in the same PR. If there are no durable findings, the PR body and Plane handoff comment must state `Docs: no durable context changes`.
