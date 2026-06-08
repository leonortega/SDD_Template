## Why

Plane ticket `E2EPROJECT-4` reports that the Clients page freezes on the first `Save Client` click after navigating from the main page, while the same form works after a browser refresh. This blocks the normal client creation workflow in the deployed app and needs a regression-tested fix for routed navigation.

## What Changes

- Fix the Clients page so the first `Save Client` click after in-app navigation submits the completed form without requiring F5.
- Preserve the existing refresh-path save behavior and existing validation behavior for invalid or incomplete client forms.
- Add automated coverage for the navigation-to-Clients first-save path.
- Verify the change through the repo quality gates and ticket-scoped QA evidence.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `client-crud`: Client creation must work on the first save attempt after routed navigation to the Clients page.

## Impact

- Likely affected code: `src/SDDTemplate.Site` Clients page/component lifecycle, form state, routing, event binding, or validation flow.
- Likely affected tests: `tests/SDDTemplate.Site.Tests` coverage for routed navigation and client save behavior.
- No planned API contract, database schema, infrastructure, artifact, or deployment workflow changes.
