## Context

The site already has Blazor pages for Home, Clients, and Products. `E2EPROJECT-8` changes the Home route into a richer landing page while keeping the existing application routes available through navigation.

The change is UI-focused. It should stay within the Blazor site project, use local/static assets, and avoid new backend, data, or deployment configuration changes.

## Goals / Non-Goals

**Goals:**
- Build a polished responsive landing page for a stock or inventory management company.
- Provide branded presentation with a logo or placeholder-ready logo, relevant visuals, a hero, services/features, benefits, and a contact/final CTA.
- Preserve navigation to Home, Clients, and Products while adding in-page section navigation.
- Include animation or transitions that improve polish without creating usability problems.
- Add focused tests that verify semantic content, navigation targets, and route compatibility.

**Non-Goals:**
- Do not change Clients or Products page behavior beyond shared navigation required by this ticket.
- Do not add API, database, authentication, deployment, or observability behavior.
- Do not depend on unlicensed external imagery or a runtime network request for landing page visuals.
- Do not add implementation-owned deployed Playwright E2E tests unless later ticket scope explicitly requires it.

## Decisions

- Keep the landing page in the existing Blazor site structure. This preserves current routing and avoids introducing a separate landing-page shell for a single home-page change.
- Use local or generated visual assets. This avoids license ambiguity and keeps the page deterministic in CI, DEV, QA, and PROD.
- Prefer CSS transitions/keyframes over JavaScript animation. This keeps the page simple, accessible, and compatible with Blazor rendering.
- Verify behavior through focused component/markup tests and existing route tests. Browser E2E or deployed QA proof remains owned by the configured `quality-test-e2e` stage.

## Risks / Trade-offs

- Visual polish can create brittle tests -> Test semantic content, links, and route reachability instead of exact layout pixels.
- Animations can harm usability -> Keep motion subtle and ensure content remains usable without relying on animation completion.
- Header changes can break existing route access -> Include tests or validation for `/clients` and `/products` links.
- Assets can increase repository size -> Use small optimized assets or CSS-generated/simple generated visuals where practical.

## Migration Plan

No data migration is required. Deploy through the normal branch, PR, artifact, DEV, QA, and E2E QA workflow. Rollback uses the existing artifact rollback process if the landing page causes production issues after explicit PROD promotion.

## Open Questions

- None for ticket start. Implementation may choose the exact company name, copy, and generated asset style as long as the ticket acceptance criteria remain satisfied.
