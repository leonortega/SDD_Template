# Shared Prerequisites

The product stack is currently unselected. Keep prerequisites limited to the delivery shell until a new product defines concrete tools.

## Required Shell Tools

- Python 3.11 or newer for `tools.sdd_cli`.
  - Install:
    - Windows: download from https://www.python.org/downloads/windows/ or use Windows Package Manager `winget install Python.Python.3`
    - macOS: download from https://www.python.org/downloads/macos/ or use Homebrew `brew install python@3.11`
    - Linux: install the distro package for Python 3.11 or newer, for example `sudo apt install python3.11` on Debian/Ubuntu.
  - Validate:
    - `python --version` or `python3 --version`
    - `python -m tools.sdd_cli --help`
- Git for repository workflow.
- Docker-compatible runtime for local platform services.
- Gitleaks when running local secret scans.
- Trivy when filesystem/container scans are configured.

## MCPs

- Codegraph for codebase context indexing.
  - Install: already configured in `.codex/config.toml` through `@colbymchenry/codegraph@1.1.1` via `npx`.
  - Validate: confirm the `.codex/config.toml` entry is present and `npx --yes @colbymchenry/codegraph@1.1.1 serve --mcp` starts successfully.
  - Note: telemetry is disabled via `CODEGRAPH_TELEMETRY=0` and `DO_NOT_TRACK=1`.

## Future Stack Tools

Add language runtimes, package managers, SDKs, and IDE extensions only when the new product stack requires them. Prefer tracked examples over local secret-bearing files.
