# E2E Adapter: Playwright

Use this adapter only when `.codex/project-profile.json` lists Playwright as the configured E2E test framework.

## Sources Of Truth

- Test package versions live in E2E project lockfiles and workflow images.
- Browser execution commands live in test scripts and workflow jobs.
- QA evidence rules live in `.codex/skills/_shared/delivery-contract.md`.

## Operations

- `discover-targets`: read deployed QA URLs from configured evidence/target metadata.
- `run`: execute the configured E2E suite against deployed QA targets.
- `diagnose`: use browser traces, screenshots, console, network, and DOM state to classify failures.
- `publish-evidence`: package reports, traces, screenshots, and summaries through the artifact adapter.

## Failure Rules

- QA pass requires executable assertions mapped to acceptance criteria.
- Screenshots, traces, logs, and page loads support assertions but do not replace them.
- App code must not receive E2E-only hooks, bypasses, hidden helpers, timing shims, or test-only behavior.
