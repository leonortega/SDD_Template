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

- **monorepo-docs-search** for documentation search across `.md`/`.mdx` files using BM25 + FlashRank.
  - Install: `python tools/bm25s_flashrank/setup_mcp.py`
  - Validate: check `.vscode/mcp.json` for `servers.monorepo-docs-search` entry.
- **codebase-memory-mcp** for codebase context indexing.
  - Install: system/binary installer.
  - Validate: confirm the installed `codebase-memory-mcp` binary and agent config are present.

## Future Stack Tools

Add language runtimes, package managers, SDKs, and IDE extensions only when the new product stack requires them. Prefer tracked examples over local secret-bearing files.
