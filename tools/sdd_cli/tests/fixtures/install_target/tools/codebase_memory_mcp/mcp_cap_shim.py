# mcp_cap_shim.py - stdio proxy for codebase-memory-mcp
# Answers optional resource/prompt capability probes with empty lists so
# clients (e.g. Cline) do not log warnings for this tools-only server.
import json
import subprocess
import sys
import threading
from typing import Any

REAL_BINARY = r"C:\Users\marce\AppData\Local\Programs\codebase-memory-mcp\codebase-memory-mcp.exe"

HANDLED: dict[str, dict[str, Any]] = {
    "resources/list": {"resources": [], "nextCursor": None},
    "resources/templates/list": {"resourceTemplates": [], "nextCursor": None},
    "prompts/list": {"prompts": [], "nextCursor": None},
}


def write_json(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def pump_server_to_client(proc):
    for line in proc.stdout:
        sys.stdout.write(line if line.endswith("\n") else line + "\n")
        sys.stdout.flush()


def main():
    proc = subprocess.Popen(
        [REAL_BINARY] + sys.argv[1:],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        bufsize=1,
    )
    threading.Thread(target=pump_server_to_client, args=(proc,), daemon=True).start()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
            continue
        method = msg.get("method")
        msg_id = msg.get("id")
        if method in HANDLED and msg_id is not None:
            write_json({"jsonrpc": "2.0", "id": msg_id, "result": HANDLED[method]})
            continue
        proc.stdin.write(line + "\n")
        proc.stdin.flush()
    try:
        proc.stdin.close()
    except Exception:
        pass
    proc.wait()


if __name__ == "__main__":
    main()
