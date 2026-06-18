---
name: quality-frontend-testing-debugging
description: Use when testing, debugging, or making targeted improvements to rendered frontend apps: local dev servers, UI regressions, interaction bugs, console errors, responsive layout, and visual QA. Prefer the Browser plugin when available; otherwise use Playwright and record the fallback reason.
---

# Frontend Testing Debugging

## Overview

Use this skill for ticket-scoped website QA or targeted frontend debugging. The `quality-test-e2e` skill should prefer this skill for Blazor UI changes when rendered behavior, responsive layout, browser console health, screenshots, or user interactions need validation.

When invoked as part of delivery QA, follow `.codex/skills/_shared/skill-startup.md` and keep browser evidence under the QA evidence rules owned by `quality-test-e2e`.

## Shared Context

When this skill is used for ticket delivery, follow `.codex/skills/_shared/delivery-contract.md` and `docs/context-management.md` through the caller skill. Preserve validation evidence and handoff details in the owning ticket workflow.

## Workflow

Use the Browser path first, then apply the QA quality bar, collect evidence, and return a concise validation handoff to the calling skill.

## Browser Path

Prefer the Codex Browser plugin when it is available in the current session:

1. Open or reuse the target tab.
2. Navigate to the DEV, QA, local, or ticket-specific URL under test.
3. Verify page title, URL, meaningful DOM content, and absence of framework error overlays.
4. Inspect console errors and warnings; classify relevant app errors as QA failures unless explained.
5. Exercise the target user flow with stable visible locators or accessible names.
6. Capture screenshot evidence for the relevant state and one mobile viewport when layout is in scope.

If the Browser plugin is unavailable, use the repository's configured Playwright workflow. If no Playwright workflow exists, use a temporary Playwright script outside the repo for screenshots, console capture, and interaction proof. Do not commit temporary screenshots, traces, generated reports, or one-off scripts.

## QA Quality Bar

- Define the flow under test as `entry route -> user action/state -> expected rendered result`.
- Assert observable behavior, not just navigation success.
- Check blank-page risk, layout overlap, clipped text, missing assets, broken links, stale loading states, and console errors.
- Use screenshots as evidence only after validating that they show the intended environment and state.
- Keep checks scoped to the Plane ticket or explicit user request.
- Store one-off QA evidence under ignored `artifacts/qa/{ticketKey}/{runId}/` only when invoked through `quality-test-e2e`.

## Output

Report:

- target URL and viewport coverage,
- Browser or Playwright path used,
- flow exercised,
- assertions made,
- evidence captured,
- failures, blockers, or residual risk.

## Failure Rules

- If the target URL is unavailable, stop and report the validation blocker to the caller.
- If Browser is unavailable and no Playwright fallback is configured, report the missing tool path instead of inventing durable repo files.
- If screenshots, traces, console logs, or request data contain secrets, redact or discard them before handoff.
