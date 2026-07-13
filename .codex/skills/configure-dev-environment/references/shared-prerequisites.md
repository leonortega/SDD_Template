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
- `pytest` for running the lab repository's Python test suite.
  - Install:
    - `python -m pip install pytest`
  - Validate:
    - `python -m pytest tools/sdd_cli/tests`

## MCPs

- Codegraph for codebase context indexing.
  - Prerequisite: Node.js 18+ with npx.
    - Install:
      - Windows: download from https://nodejs.org/en/download or use Windows Package Manager `winget install OpenJS.NodeJS`
      - macOS: use Homebrew `brew install node`
      - Linux: install the distro package for Node.js 18+ or use NodeSource, for example `curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs`
    - Validate:
      - `node --version`
      - `npm --version`
      - `npx --version`
      - On Windows PowerShell, direct `npx` can be enabled with:
        - `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
      - As a fallback, `npx.cmd --version` also works if the PowerShell wrapper is blocked.
  - Install: configured in `.codex/config.toml` through `@colbymchenry/codegraph@1.1.1` via `npx`.
  - Validate: confirm the `.codex/config.toml` entry is present and `npx --yes @colbymchenry/codegraph@1.1.1 serve --mcp` starts successfully.
  - Note: telemetry is disabled via `CODEGRAPH_TELEMETRY=0` and `DO_NOT_TRACK=1`.

## Future Stack Tools

Add language runtimes, package managers, SDKs, and IDE extensions only when the new product stack requires them. Prefer tracked examples over local secret-bearing files.
