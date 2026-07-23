import json
import os
import shlex
import subprocess
import sys
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


def write_workspace_mcp_config(repo_root: Path, config: dict) -> None:
    target = repo_root / ".vscode" / "mcp.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if target.exists():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data.setdefault("mcpServers", {}).update(config.get("mcpServers", {}))
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def auto_start_mcp(repo_root: Path, config: dict) -> bool:
    return False


def setup_mcp() -> int:
    user_profile = os.environ.get("USERPROFILE") or os.path.expandvars("%USERPROFILE%")
    if not user_profile:
        _safe_print("Error: No se pudo encontrar la variable de entorno USERPROFILE.")
        return 1

    venv_dir = os.path.join(user_profile, ".mcp_shared_venv")
    python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
    pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe")

    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        current_dir = os.getcwd()

    script_path = os.path.join(current_dir, "mcp_doc_research.py")

    if not os.path.exists(venv_dir):
        _safe_print(f"📦 Creando entorno virtual centralizado en: {venv_dir}")
        venv.create(venv_dir, with_pip=True)
    else:
        _safe_print(f"ℹ️ El entorno virtual ya existe en: {venv_dir}")

    _safe_print("📥 Instalando dependencias (BM25S + FlashRank)...")
    try:
        subprocess.run(  # nosec
            [shlex.quote(pip_exe), "install", "--upgrade", "pip", "--quiet"], check=True
        )
        subprocess.run(  # nosec
            [shlex.quote(pip_exe), "install", "mcp", "bm25s", "flashrank", "--quiet"],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        _safe_print(f"❌ Error durante la instalación de paquetes: {e}")
        return 1

    config = build_mcp_config(python_exe, script_path)
    repo_root = Path(__file__).resolve().parents[2]
    write_workspace_mcp_config(repo_root, config)
    auto_started = auto_start_mcp(repo_root, config)

    _safe_print("\n✅ ¡Configuración completada con éxito desde Python!")
    if auto_started:
        _safe_print("🚀 MCP server auto-startado.")
    return 0


if __name__ == "__main__":
    sys.exit(setup_mcp())
