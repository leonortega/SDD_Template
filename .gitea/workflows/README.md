# Gitea Actions Quality Gates

Gitea PR validation is the source of truth. Local hooks are only convenience checks for staged secrets and commit-message shape.

Required repository secrets:

- `NEXUS_URL`
- `NEXUS_USERNAME`
- `NEXUS_PASSWORD`
- `NEXUS_REPOSITORY`
- `AZURE_CREDENTIALS`
- `AZURE_DEV_RESOURCE_GROUP`
- `AZURE_DEV_WEBAPP_NAME`
- `AZURE_DEV_WEBAPP_URL`

Add equivalent QA and PROD secrets before enabling promotion jobs.

Recommended branch protection:

- Block direct pushes to `main`.
- Require pull requests.
- Require the PR validation workflow to pass.
- Require review approval or the configured review label.
- Block merge while `needs-changes` is present.
