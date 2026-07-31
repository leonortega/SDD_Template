# Gitea Actions

The repository currently has no product app, so workflows are shell placeholders.

- `pr-validation.yml` validates JSON and runs a secret scan.
- `package-deploy.yml` is disabled until app targets exist.
  All CI workflows use pinned local job images built by `environment-lab build-gitea-images`. This command is mandatory before PR validation, deployment, or QA E2E runs. Local and CI validation must not rely on ad hoc host tool installs when a pinned Docker image is available.

When a new product stack is added, replace these placeholders with stack-specific build, test, package, deploy, and QA jobs.
