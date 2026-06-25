# Gitea Runner

The Gitea runner currently executes shell-level placeholder workflows. Product-specific runner images and tools should be added with the new product stack.

Required shell workflow tools:

- `bash`
- `git`
- `curl`
- `python`
- `gitleaks`

Keep runner secrets in ignored local or provider-managed secret stores.
