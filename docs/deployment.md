# Deployment

Deployment is currently a shell capability. No product app is configured for packaging, deployment, or runtime health checks.

## Current State

- `infra/deployment/apps.json` contains no app targets.
- `infra/deployment/configuration.json` contains no app settings.
- Provider adapters and platform infrastructure remain available.
- Gitea workflows are placeholders until the next product stack defines real artifacts and environments.

## Adding Deployment For A New Product

When a new product exists:

1. Add one app entry per deployable artifact to `infra/deployment/apps.json`.
2. Add required app settings to `infra/deployment/configuration.json`.
3. Add stack-specific package/build jobs.
4. Add environment smoke checks that prove the deployed artifact is healthy.
5. Publish immutable artifact metadata to Nexus.
6. Keep DEV, QA, and PROD promotion artifact-based.

## Release Rules

- Build once, promote the same artifact.
- Keep QA approval separate from production promotion.
- Record release lineage and evidence in the configured artifact and ticket providers.
- Do not rebuild during PROD promotion.
- Do not invent app health contracts before the new product defines them.

## QA Evidence

Playwright remains available for future browser QA, but no E2E suite exists in this shell. Add committed executable QA checks only after the new product has user-visible or API behavior to prove.
