import json
import os
import subprocess
import sys
import time
import venv
from pathlib import Path


def build_mcp_config(python_exe: str, script_path: str) -> dict:
    return {
        "mcpServers": {
            "monorepo-docs-search": {
                "command": python_exe,
                "args": [script_path],
            }
        }
    }


def _replace_path_values(obj, python_exe: str, script_path: str):
    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if isinstance(value, str):
                if value.startswith("/tmp/python.exe"):
                    obj[key] = python_exe
                elif value.startswith("/tmp/server.py"):
                    obj[key] = script_path
            else:
                _replace_path_values(value, python_exe, script_path)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            if isinstance(item, str):
                if item.startswith("/tmp/python.exe"):
                    obj[index] = python_exe
                elif item.startswith("/tmp/server.py"):
                    obj[index] = script_path
            else:
                _replace_path_values(item, python_exe, script_path)


def _safe_print(message: str) -> None:
    print(message, flush=True)


# ── Cline MCP settings helpers ──────────────────────────────────────────


def _get_cline_settings_path() -> Path | None:
    """Resolve Cline's global MCP settings path, or None if undetectable."""
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return (
                Path(appdata)
                / "Code"
                / "User"
                / "globalStorage"
                / "saoudrizwan.claude-dev"
                / "settings"
                / "cline_mcp_settings.json"
            )
    elif sys.platform == "darwin":
        mac_path = (
            Path.home()
            / "Library"
            / "Application Support"
            / "Code"
            / "User"
            / "globalStorage"
            / "saoudrizwan.claude-dev"
            / "settings"
            / "cline_mcp_settings.json"
        )
        return mac_path
    else:  # Linux
        linux_path = (
            Path.home()
            / ".config"
            / "Code"
            / "User"
            / "globalStorage"
            / "saoudrizwan.claude-dev"
            / "settings"
            / "cline_mcp_settings.json"
        )
        return linux_path
    return None


def _update_cline_mcp_settings(path: Path, mcp_name: str, server_config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text('{\n  "mcpServers": {\n  }\n}\n', encoding="utf-8")

    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {}

    servers = data.setdefault("mcpServers", {})
    if mcp_name in servers:
        _replace_path_values(
            servers, server_config["command"], server_config["args"][0]
        )
    else:
        servers[mcp_name] = server_config
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def register_mcp_server(
    repo_root: Path, server_name: str, server_config: dict
) -> set[Path]:
    """Register an MCP server in .vscode/mcp.json and optionally Cline's global settings.

    Args:
        repo_root: Repository root directory.
        server_name: Name for the MCP server (e.g. "monorepo-docs-search", "gitea").
        server_config: Server config dict with "command", "args", and optionally "env" keys.

    Returns:
        Set of file paths that were written.
    """
    repo_root = repo_root.resolve()
    vscode_dir = repo_root / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    written_paths: set[Path] = set()

    mcp_entry: dict[str, object] = {
        "command": server_config["command"],
        "args": server_config["args"],
    }
    env = server_config.get("env")
    if env:
        mcp_entry["env"] = env

    # .vscode/mcp.json
    copilot_path = vscode_dir / "mcp.json"
    if copilot_path.exists():
        try:
            copilot = json.loads(copilot_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            copilot = {}
    else:
        copilot = {}
    copilot.setdefault("mcpServers", {})[server_name] = mcp_entry
    copilot_path.write_text(
        json.dumps(copilot, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    written_paths.add(copilot_path)

    # Cline global MCP settings (user-specific, outside repo)
    cline_path = _get_cline_settings_path()
    if cline_path:
        cline_entry: dict[str, object] = {
            "command": server_config["command"],
            "args": server_config["args"],
        }
        if env:
            cline_entry["env"] = env
        _update_cline_mcp_settings(cline_path, server_name, cline_entry)
        written_paths.add(cline_path)

    return written_paths


# ── write_workspace_mcp_config ──────────────────────────────────────────


def write_workspace_mcp_config(repo_root: Path, config: dict) -> set[Path]:
    """Register the monorepo-docs-search MCP server in workspace config.

    Args:
        repo_root: Repository root directory.
        config: MCP config dict with "mcpServers" key containing at least
                a "monorepo-docs-search" entry.

    Returns:
        Set of file paths that were written.
    """
    server_config = config["mcpServers"]["monorepo-docs-search"]
    return register_mcp_server(repo_root, "monorepo-docs-search", server_config)


# ── OpenProject MCP ─────────────────────────────────────────────────────


def build_openproject_mcp_config(base_url: str, api_key: str) -> dict:
    """Build the server config dict for the openproject MCP server.

    Args:
        base_url: OpenProject instance URL (e.g. "http://localhost:8080").
        api_key: OpenProject API key for authentication.

    Returns:
        Server config dict with "command", "args", and "env" keys.
    """
    return {
        "command": "npx",
        "args": ["-y", "openproject-mcp"],
        "env": {
            "OPENPROJECT_URL": base_url,
            "OPENPROJECT_API_KEY": api_key,
        },
    }


def setup_openproject_mcp(
    repo_root: Path, base_url: str, api_key: str
) -> set[Path]:
    """Register the openproject MCP server in workspace config.

    Args:
        repo_root: Repository root directory.
        base_url: OpenProject instance URL.
        api_key: OpenProject API key.

    Returns:
        Set of file paths that were written.
    """
    server_config = build_openproject_mcp_config(base_url, api_key)
    return register_mcp_server(repo_root, "openproject", server_config)


# ── Gitea MCP (Docker) ──────────────────────────────────────────────────


def build_gitea_mcp_config(base_url: str, access_token: str) -> dict:
    """Build the server config dict for the Gitea MCP server (Docker-based).

    Args:
        base_url: Gitea instance URL (e.g. "http://localhost:3000").
        access_token: Gitea access token for authentication.

    Returns:
        Server config dict with "command", "args", and "env" keys.
    """
    return {
        "command": "docker",
        "args": [
            "run",
            "--rm",
            "-i",
            "docker.gitea.com/gitea-mcp-server",
            "--host",
            base_url,
        ],
        "env": {
            "GITEA_ACCESS_TOKEN": access_token,
        },
    }


def setup_gitea_mcp(
    repo_root: Path, base_url: str, access_token: str
) -> set[Path]:
    """Register the Gitea MCP server in workspace config.

    Requires a running Gitea instance and a valid API token.

    Args:
        repo_root: Repository root directory.
        base_url: Gitea instance URL (e.g. "http://localhost:3000").
        access_token: Gitea access token.

    Returns:
        Set of file paths that were written.
    """
    server_config = build_gitea_mcp_config(base_url, access_token)
    return register_mcp_server(repo_root, "gitea", server_config)


# ── Kubernetes MCP ──────────────────────────────────────────────────────


def build_k8s_mcp_config(kubeconfig_path: str | None = None) -> dict:
    """Build the server config dict for the Kubernetes MCP server.

    Args:
        kubeconfig_path: Optional path to kubeconfig file. If None,
                         uses the KUBECONFIG env var or default location.

    Returns:
        Server config dict with "command", "args", and "env" keys.
    """
    config: dict = {
        "command": "npx",
        "args": ["-y", "kubernetes-mcp-server@latest"],
    }
    if kubeconfig_path:
        config["env"] = {"KUBECONFIG": kubeconfig_path}
    return config


def setup_k8s_mcp(
    repo_root: Path, kubeconfig_path: str | None = None
) -> set[Path]:
    """Register the Kubernetes MCP server in workspace config.

    Requires kubectl configured with a valid cluster context.

    Args:
        repo_root: Repository root directory.
        kubeconfig_path: Optional path to kubeconfig file.

    Returns:
        Set of file paths that were written.
    """
    server_config = build_k8s_mcp_config(kubeconfig_path)
    return register_mcp_server(repo_root, "kubernetes", server_config)


# ── Auto-start MCP (monorepo-docs-search) ───────────────────────────────


def auto_start_mcp(repo_root: Path, config: dict) -> bool:
    """Auto-start the monorepo-docs-search MCP server as a background process."""
    python_exe = config["mcpServers"]["monorepo-docs-search"]["command"]
    script_path = config["mcpServers"]["monorepo-docs-search"]["args"][0]
    if not os.path.exists(python_exe):
        return False
    if not os.path.exists(script_path):
        return False

    pid_file = repo_root / ".vscode" / ".mcp_monorepo_docs_search.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            if pid > 0:
                probe = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if (
                    probe.returncode == 0
                    and "INFO: No tasks are running which match the specified criteria"
                    not in probe.stdout
                ):
                    return True
        except ValueError:
            pass

    process = subprocess.Popen(
        [python_exe, script_path],
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP
            if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP")
            else 0
        ),
    )
    time.sleep(1)
    pid_file.write_text(str(process.pid), encoding="utf-8")
    return True


# ── Legacy setup entrypoint ─────────────────────────────────────────────


def setup_mcp() -> int:
    user_profile = os.environ.get("USERPROFILE") or os.path.expandvars(
        "%USERPROFILE%"
    )
    if not user_profile:
        _safe_print(
            "❌ Error: No se pudo encontrar la variable de entorno USERPROFILE."
        )
        sys.exit(1)

    venv_dir = os.path.join(user_profile, ".mcp_shared_venv")
    python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
    pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe")

    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        current_dir = os.getcwd()

    script_path = os.path.join(current_dir, "mcp_doc_research.py")

    if not os.path.exists(venv_dir):
        _safe_print(f"Creando entorno virtual centralizado en: {venv_dir}")
        venv.create(venv_dir, with_pip=True)
    else:
        _safe_print(f"El entorno virtual ya existe en: {venv_dir}")

    _safe_print("Instalando dependencias (BM25S + FlashRank)...")
    try:
        subprocess.run(  # nosec
            [pip_exe, "install", "--upgrade", "pip", "--quiet"],
            check=True,
        )
        subprocess.run(  # nosec
            [pip_exe, "install", "mcp", "bm25s", "flashrank", "--quiet"],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        _safe_print(f"Error durante la instalacion de paquetes: {e}")
        sys.exit(1)

    config = build_mcp_config(python_exe, script_path)
    repo_root = Path(__file__).resolve().parents[2]
    write_workspace_mcp_config(repo_root, config)
    auto_start_mcp(repo_root, config)

    _safe_print("\nConfiguracion completada con exito desde Python!")
    _safe_print("El servidor MCP fue iniciado automaticamente.")
    return 0


if __name__ == "__main__":
    sys.exit(setup_mcp())
