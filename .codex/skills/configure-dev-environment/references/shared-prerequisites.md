# Shared Prerequisites

The product stack is currently unselected. Keep prerequisites limited to the delivery shell until a new product defines concrete tools.

## Required Shell Tools

- Python 3.11 or newer for `tools.sdd_cli`.
- Git for repository workflow.
- Docker-compatible runtime for local platform services.
- Gitleaks when running local secret scans.
- Trivy when filesystem/container scans are configured.

## Future Stack Tools

Add language runtimes, package managers, SDKs, MCPs, and IDE extensions only when the new product stack requires them. Prefer tracked examples over local secret-bearing files.
