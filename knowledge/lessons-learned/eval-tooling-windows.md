<!-- TIER 2: SEMI-STABLE - Eval tooling lessons on Windows, loaded at startup -->

# Eval Tooling On Windows

Durable lessons about running the Promptfoo agent eval (`.codex/agent-evals/`)
on Windows hosts, captured during the post-PROD eval for release v0.1.0
(E2EPROJECT-37).

## Lesson: Promptfoo @libsql Blocker On Windows + Deterministic Fallback

### Symptom

`python -m tools.sdd_cli agent-eval run` fails on Windows with:

```text
Database migration failed: Error: \\?\C:\Users\<user>\AppData\Local\npm-cache\_npx\
<...>\node_modules\@libsql\win32-x64-msvc\index.node is not a valid Win32
application.
promptfoo exited with code 3221226505.
```

The `@libsql` native module cached by npx is not a valid Win32 binary, so
promptfoo cannot start its eval-store database. The CLI runner fails loudly
(correct behavior — it must not report a misleading "0 tests passed").

`npm install -g promptfoo` does **not** fix it on Windows: the esbuild
postinstall (`node install.js`) fails, leaving a broken global install
(`Cannot find module ...\dist\src\entrypoint.js`).

### Root Cause

- promptfoo uses `@libsql` (native) for its eval cache/store DB; the
  npx-cached `win32-x64-msvc/index.node` binary is incompatible/corrupt on
  this host.
- esbuild's platform binary also fails to build in a global install on
  Windows.

### Workarounds (documented in `.codex/agent-evals/README.md`)

1. `npm install -g promptfoo` — may fail on Windows (see root cause).
2. `npm cache clean --force` or delete `%LocalAppData%\npm-cache\_npx`.
3. Use WSL / a Unix machine.

### Deterministic Fallback (proven for release v0.1.0)

The eval is fully deterministic (no LLM) — the README documents verifying
every case without promptfoo by running the Python provider directly against
the YAML assertions. Recipe used for the v0.1.0 post-PROD eval (46/46 passed):

1. `import routing_provider` from `.codex/agent-evals/`.
2. Load `.codex/agent-evals/promptfooconfig.yaml` (pyyaml is available).
3. For each test case:
   `routing_provider.call_api("", {}, {"vars": test["vars"]})` →
   `{"output": "<json>"}`.
4. Evaluate the `is-json` + `javascript` assertions **exactly** with node:
   `new Function('output', 'return (' + assertion + ');')(output)`.
5. Persist to `.codex/agent-evals/results.local.json`
   (mode `post-prod-eval`, scope = release version).

Result for release v0.1.0 post-PROD: **46/46 passed, 0 failed** — no routing
regressions detected.

### Key Facts

- The eval is deterministic — results are identical with or without
  promptfoo.
- CI (Linux runners) can run promptfoo natively; only the local Windows host
  is blocked.
- Cleanup: uninstall a broken global promptfoo
  (`npm uninstall -g promptfoo`) so it does not shadow real runs.
- Console gotcha: on Windows cp1252 consoles, printing emoji from eval JSON
  crashes `print()` — use `PYTHONIOENCODING=utf-8`.
