# Gitea Actions

The repository currently has no product app, so workflows are shell placeholders.

- `pr-validation.yml` validates JSON and runs a secret scan.
- `package-deploy.yml` is disabled until app targets exist.
- `rancher-local-deploy.yml` is disabled until product images exist.

When a new product stack is added, replace these placeholders with stack-specific build, test, package, deploy, and QA jobs.
