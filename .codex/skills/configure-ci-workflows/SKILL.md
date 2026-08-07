---
name: configure-ci-workflows
license: MIT
description: >-
  >- Generate or update Gitea Actions CI/CD workflow files based on the project profile stack and app topology. Run
  after configure-dev-environment selects the project stack, or when apps.json, project-profile, or client-tools
  configuration changes.
---

<!-- TIER 3: STAGE-SPECIFIC - CI workflow configuration skill -->

# Configure CI Workflows

## Overview

Use this skill after `configure-dev-environment` has set the project stack and infrastructure is running. It reads the
project profile to determine which technologies are used (frontend, backend,
database), which apps exist in the deployment topology, and which providers are configured, then generates the
`.gitea/workflows/*.yml` files with appropriate build, package, upload, and deploy steps.

This skill replaces manually editing workflow files when the project stack changes. Run it whenever:

- A new project stack is selected (e.g., adding a backend after initial frontend-only setup)
- New apps are added to `infra/deployment/apps.json`
- The artifact or deployment provider changes (e.g., Nexus to docker-registry)

## Shared Context

Before generating workflows, read:

1. **Project profile** — use the merged profile (reads `project-profile.json` first, falls back to
`project-profile.example.json`, merges with `project-profile.local.json`). Get stack: frontend,
backend, database values and provider selections.
2. `infra/deployment/apps.json` — for app topology (appId, projectPath, role, artifactName, healthPath, deployOrder)
3. `.codex/client-tools.local.json` — for Gitea base URL, Nexus base URL and repository

Also follow `.codex/skills/_shared/skill-startup.md` for the standard startup sequence, then read
`.codex/skills/_shared/delivery-contract.md` and `docs/conventions/context-management.md` so the
generated workflows respect the shared delivery contract and stay scoped to the active ticket.

## Configuration

The skill derives configuration from these sources:

| Source                                                                         | What it provides                                                                                        |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| Merged project profile (`project-profile.json` + `project-profile.local.json`) | Stack: frontend/backend/database technologies. Providers: artifact (Nexus), deployment (docker-desktop) |
| `infra/deployment/apps.json`                                                   | App topology: what to build, package, and deploy                                                        |
| `client-tools.local.json → gitea`                                              | Gitea URL for checkout step                                                                             |
| `client-tools.local.json → nexus`                                              | Nexus URL, repository for upload step                                                                   |

## Workflow

Run this skill inside the active ticket's delivery context after the user confirms the stack and infrastructure is
running. Generate the workflow files, show a dry-run diff, and write only after
confirmation — see the Workflow Generation Rules below.

## Workflow Generation Rules

### 1. Ask User For Stack Technologies

**Do NOT auto-detect or infer the tech stack.** The stack must come from the user. Ask them explicitly:

- What frontend framework (e.g., React, Vue, Angular, none)?
- What backend framework (e.g., FastAPI, Django, Flask, ASP.NET Core, none)?
- What database (e.g., PostgreSQL, SQLite, none)?
- What languages and build tools are used?

Once the user confirms the stack, set it via:

```bash
python -m tools.sdd_cli environment-lab set-project-stack --values-json '{
  "frontend": "react",
  "backend": "fastapi",
  "database": "postgresql"
}'
```

Then read the confirmed values from `project-profile.local.json → stack` and determine build commands per domain using
the mapping table:

| Stack value               | Build command                     | Output directory            | Artifact pattern | Deploy command              |
| ------------------------- | --------------------------------- | --------------------------- | ---------------- | --------------------------- |
| `react`, `vue`, `angular` | `npm ci && npm run build`         | `dist/`                     | `{appId}-*.zip`  | `node server.mjs`           |
| `fastapi`                 | `pip install -r requirements.txt` | —                           | `backend-*.zip`  | `uvicorn main:app`          |
| `django`                  | `pip install -r requirements.txt` | —                           | `backend-*.zip`  | `gunicorn wsgi:application` |
| `flask`                   | `pip install -r requirements.txt` | —                           | `backend-*.zip`  | `flask run`                 |
| `dotnet`, `aspnetcore`    | `dotnet publish -c Release`       | `bin/Release/net*/publish/` | `backend-*.zip`  | `dotnet {assembly}.dll`     |

If a domain's `applies` is `false`, skip its build step.

### 2. Generate `package-deploy.yml`

Use this template structure, filling in sections based on detected stack and apps:

```yaml
name: Package and deploy

on:
  # Deploy ONLY when a pull request targeting `dev` is MERGED (closed event
  # with merged=true). Direct pushes to dev never deploy: every change that
  # reaches the dev branch must come through a PR merge.
  pull_request:
    types:
      - closed
    branches:
      - dev
  # Explicit operator override (e.g. QA/PROD promotion from a release branch).
  workflow_dispatch:
    inputs:
      environment:
        description: Target environment (dev, qa, or prod)
        required: true
        default: dev
      # PROD artifact-reuse: the QA-approved commit to deploy (build is skipped).
      artifact_commit_sha:
        description: QA-approved commit to deploy for prod (defaults to ref head)
        required: false
        default: ''
      release_version:
        description: Final release version recorded in release-prod.json
        required: false
        default: ''
      source_rc_version:
        description: Source RC tag recorded in release-prod.json
        required: false
        default: ''

jobs:
  build-and-deploy:
    # Dispatch always runs. For pull_request events (already restricted to
    # `closed` PRs targeting dev), only deploy when the PR was actually
    # merged — a closed-without-merge PR must not deploy.
    if: github.event_name == 'workflow_dispatch' || github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    container:
      image: sdd-e2e-ci:local
    steps:
      - name: Resolve deploy SHA
        id: sha
        shell: bash
        run: |
          if [ "${{ github.event_name }}" = "pull_request" ]; then
            # PR merge event: deploy the MERGE COMMIT on the base branch (dev),
            # not the PR head — GITHUB_SHA for pull_request events points at the
            # head, which is not the commit that landed on dev.
            MERGE_SHA="${{ github.event.pull_request.merge_commit_sha }}"
            if [ -n "${MERGE_SHA}" ]; then
              echo "SHA=${MERGE_SHA}" >> "$GITHUB_OUTPUT"
            else
              echo "SHA=${GITHUB_SHA}" >> "$GITHUB_OUTPUT"
            fi
          else
            echo "SHA=${GITHUB_SHA}" >> "$GITHUB_OUTPUT"
          fi

      - name: Checkout
        env:
          GITEA_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        shell: bash
        run: |
          set -eo pipefail
          export GIT_TERMINAL_PROMPT=0
          TOKEN="${GITEA_TOKEN:-}"
          repo_url="http://git:${TOKEN}@host.docker.internal:3000/${GITHUB_REPOSITORY}.git"
          git init .
          git remote add origin "$repo_url"
          git fetch --depth 2 origin "${{ steps.sha.outputs.SHA }}"
          git checkout --force FETCH_HEAD

      # ── Deployable-changes gate (src/test folders only) ──
      # Deploy in ANY environment only when the change set touches a src/,
      # test/, or tests/ folder at any depth. Docs/infra/workflow-only changes
      # must not deploy. Gate every deploy-pipeline step with:
      #   if: steps.changes.outputs.deployable == 'true'
      - name: Check for deployable changes (src/ or test/ folders)
        id: changes
        shell: bash
        run: |
          set -euo pipefail
          DEPLOY_SHA="${{ steps.sha.outputs.SHA }}"

          if [ "${{ github.event_name }}" = "pull_request" ]; then
            BASE_SHA="${{ github.event.pull_request.base.sha }}"
            git fetch --depth 1 origin "${BASE_SHA}" >/dev/null 2>&1 || BASE_SHA=""
          else
            BASE_SHA=$(git rev-parse --verify "${DEPLOY_SHA}^" 2>/dev/null || echo "")
          fi

          if [ -z "${BASE_SHA}" ]; then
            echo "DEPLOYABLE=true" >> "$GITHUB_OUTPUT"
            exit 0
          fi

          # git diff exits 0 (no differences), 1 (differences found), or >=128
          # (error). Errors fail OPEN so the advisory gate never blocks a real
          # deploy on its own hiccup.
          CHANGED=$(git diff --name-only "${BASE_SHA}" "${DEPLOY_SHA}" 2>/tmp/diff-err.log) || DIFF_STATUS=$?
          DIFF_STATUS="${DIFF_STATUS:-0}"
          if [ "${DIFF_STATUS}" -gt 1 ]; then
            echo "DEPLOYABLE=true" >> "$GITHUB_OUTPUT"
            exit 0
          fi
          if [ -z "${CHANGED}" ]; then
            echo "DEPLOYABLE=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi

          COUNT=$(echo "${CHANGED}" | grep -cE '(^|/)(src|test|tests)/' || true)
          if [ "${COUNT}" -gt 0 ]; then
            echo "DEPLOYABLE=true" >> "$GITHUB_OUTPUT"
          else
            echo "DEPLOYABLE=false" >> "$GITHUB_OUTPUT"
          fi

      # ── Build steps (one per app in apps.json) ──
      # For each app in apps.json where role == "web" and its projectPath has a buildable project:
      #   Generate a Build step with the appropriate command from the stack table above
      #   Example for React:
      #     - name: Build frontend
      #       shell: bash
      #       run: |
      #         set -euo pipefail
      #         cd frontend
      #         npm ci
      #         npm run build

      # ── Test steps (one per app) ──
      # If the app has a test script:
      #   Generate a Test step
      #   Example:
      #     - name: Test frontend
      #       shell: bash
      #       run: |
      #         set -euo pipefail
      #         cd frontend
      #         npm run test -- --run

      # ── Package artifacts step ──
      - name: Package artifacts
        shell: bash
        run: |
          set -euo pipefail
          COMMIT_SHA=$(git rev-parse HEAD)
          APPS_JSON="infra/deployment/apps.json"
          ARTIFACT_DIR="app/${COMMIT_SHA}"
          mkdir -p "${ARTIFACT_DIR}"

          if [ -f "${APPS_JSON}" ]; then
            python3 -c "
          import json, os
          with open('${APPS_JSON}') as f:
              config = json.load(f)
          for app in config.get('apps', []):
              aid = app['appId']
              artifact = app['artifactName']
              path = app.get('projectPath', aid)
              role = app.get('role', 'web')
              # Detect build output by role:
              # - web: dist/  (npm build output)
              # - api: check for compiled output or just package the source tree
              if role == 'web':
                  has_build = os.path.isdir(os.path.join(path, 'dist'))
              elif role == 'api':
                  # Check for .NET publish first, then assume source-based
                  has_build = (os.path.isdir(os.path.join(path, 'bin', 'Release', 'publish')) or
                               os.path.isfile(os.path.join(path, 'requirements.txt')) or
                               os.path.isfile(os.path.join(path, 'pyproject.toml')))
              else:
                  has_build = os.path.isdir(path)
              print(f'App: {aid}, Artifact: {artifact}, Has build: {has_build}')
            "
          fi

          # Package each app's output
          APPS=$(python3 -c "
          import json, os
          with open('${APPS_JSON}') as f:
              config = json.load(f)
          for app in config.get('apps', []):
              path = app.get('projectPath', app['appId'])
              role = app.get('role', 'web')
              if role == 'web' and os.path.isdir(os.path.join(path, 'dist')):
                  print(app['artifactName'])
              elif role == 'api' and os.path.isdir(os.path.join(path, 'bin', 'Release')):
                  print(app['artifactName'])
          " 2>/dev/null || echo "")

          if [ -z "${APPS}" ]; then
            echo "No build artifacts found — creating empty marker"
            echo '{"version":1,"apps":[],"note":"No apps produced artifacts for this commit"}' > "${ARTIFACT_DIR}/deployable-apps.json"
          else
            for artifact_name in ${APPS}; do
              app_id=$(python3 -c "
          import json
          with open('${APPS_JSON}') as f:
              config = json.load(f)
          for app in config.get('apps', []):
              if app['artifactName'] == '${artifact_name}':
                  print(app['projectPath'])
              " 2>/dev/null || echo "${artifact_name%.zip}")
              
              # Determine the source directory based on role
              ROLE=$(python3 -c "
          import json
          with open('${APPS_JSON}') as f:
              config = json.load(f)
          for app in config.get('apps', []):
              if app['artifactName'] == '${artifact_name}':
                  print(app.get('role', 'web'))
              " 2>/dev/null || echo "web")
              
              # Package source dir based on role and available output
              if [ "${ROLE}" = "web" ] && [ -d "${app_id}/dist" ]; then
                cd "${app_id}/dist"
                zip -r "../../${ARTIFACT_DIR}/${artifact_name}" .
                cd ../..
              elif [ "${ROLE}" = "api" ] && [ -d "${app_id}/bin/Release/publish" ]; then
                cd "${app_id}/bin/Release/publish"
                zip -r "../../../${ARTIFACT_DIR}/${artifact_name}" .
                cd ../../..
              elif [ "${ROLE}" = "api" ]; then
                # Source-based backend (Python, Node, etc.) — package entire project tree
                cd "${app_id}"
                zip -r "../${ARTIFACT_DIR}/${artifact_name}" . -x 'node_modules/*' '.venv/*' '__pycache__/*'
                cd ..
              fi
              sha256sum "${ARTIFACT_DIR}/${artifact_name}" > "${ARTIFACT_DIR}/${artifact_name}.sha256"
              echo "Packaged ${artifact_name}"
            done

            # Generate deployable-apps.json
            python3 -c "
          import json, os
          with open('${APPS_JSON}') as f:
              config = json.load(f)
          deployable = {'version': 1, 'apps': []}
          for app in config.get('apps', []):
              path = app.get('projectPath', app['appId'])
              role = app.get('role', 'web')
              has_build = False
              if role == 'web':
                  has_build = os.path.isdir(os.path.join(path, 'dist'))
              elif role == 'api':
                  has_build = (os.path.isdir(os.path.join(path, 'bin', 'Release', 'publish')) or
                               os.path.isfile(os.path.join(path, 'requirements.txt')) or
                               os.path.isfile(os.path.join(path, 'pyproject.toml')) or
                               os.path.isfile(os.path.join(path, 'package.json')))
              if has_build:
                  deployable['apps'].append({
                      'appId': app['appId'],
                      'artifactName': app['artifactName'],
                      'deployOrder': app.get('deployOrder', 0),
                      'healthPath': app.get('healthPath', '/health')
                  })
          with open('${ARTIFACT_DIR}/deployable-apps.json', 'w') as f:
              json.dump(deployable, f)
            "
          fi

          echo "${COMMIT_SHA}" > "${ARTIFACT_DIR}/commit.sha"
          echo "Packaged artifacts for commit ${COMMIT_SHA}"
          ls -la "${ARTIFACT_DIR}/"

      # ── Upload to artifact provider step ──
      # If artifact provider is Nexus (from project-profile.providers.artifact.id):
      #   Generate the Nexus upload step (see below)
      # If artifact provider is docker-registry or other:
      #   Generate appropriate upload step

      # ── Deploy step ──
      # If deployment provider is docker-desktop (from project-profile.providers.deployment.id):
      #   Generate the deploy step (see below)
      # If deployment provider is kubernetes or other:
      #   Generate appropriate deploy step
```

### 3. Nexus Upload Step (when `providers.artifact.id == "nexus"`)

```yaml
- name: Upload to Nexus
  env:
    NEXUS_URL: ${{ secrets.NEXUS_URL }}
    NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
    NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
    NEXUS_REPOSITORY: ${{ secrets.NEXUS_REPOSITORY }}
  shell: bash
  run: |
    set -euo pipefail
    COMMIT_SHA=$(git rev-parse HEAD)
    ARTIFACT_DIR="app/${COMMIT_SHA}"
    NEXUS_URL="${NEXUS_URL:-http://host.docker.internal:8088}"
    REPO="${NEXUS_REPOSITORY:-sdd-artifacts}"
    if [ -z "${NEXUS_USERNAME:-}" ] || [ -z "${NEXUS_PASSWORD:-}" ]; then
      echo "Nexus credentials not set — skipping upload"
      exit 0
    fi
    for file in $(find "${ARTIFACT_DIR}" -type f); do
      remote_path="${file}"
      echo "Uploading ${file} to ${NEXUS_URL}/repository/${REPO}/${remote_path}"
      curl -s -u "${NEXUS_USERNAME}:${NEXUS_PASSWORD}" \
        --upload-file "${file}" \
        "${NEXUS_URL}/repository/${REPO}/${remote_path}" \
        -w "HTTP:%{http_code}\n"
    done
    echo "Nexus upload complete"
```

### 4. Docker Desktop Deploy Step (when `providers.deployment.id == "docker-desktop"`)

```yaml
- name: Deploy to environment
  shell: bash
  run: |
    set -euo pipefail
    if [ "${{ github.event_name }}" = "pull_request" ]; then
      ENV="dev"
    else
      ENV="${{ github.event.inputs.environment }}"
    fi
    echo "Deploying to $ENV environment"

    # Deploy apps in deployOrder
    python3 -c "
    import json, os, subprocess, time
    with open('infra/deployment/apps.json') as f:
        config = json.load(f)
    sorted_apps = sorted(config.get('apps', []), key=lambda a: a.get('deployOrder', 0))
    for app in sorted_apps:
        aid = app['appId']
        health = app.get('healthPath', '/health')
        role = app.get('role', 'web')
        port_map = {'dev': 4173, 'qa': 4174}
        port = port_map.get(os.environ.get('ENV', 'dev'), 4173)
        
        if role == 'web' and os.path.isfile(os.path.join(app.get('projectPath', aid), 'server.mjs')):
            print(f'Starting {aid} on port {port}')
            os.chdir(app.get('projectPath', aid))
            proc = subprocess.Popen(['node', 'server.mjs'], env={**os.environ, 'PORT': str(port)})
            time.sleep(3)
            health_check = subprocess.run(
                ['curl', '-s', f'http://localhost:{port}{health}'],
                capture_output=True, text=True
            )
            if 'status\":\"ok\"' in health_check.stdout:
                print(f'{aid} health PASSED')
            else:
                print(f'{aid} health FAILED')
                exit(1)
            proc.terminate()
        else:
            print(f'{aid}: no deployable server — infra-only')
    "
```

### 4a. K8s/kind Deploy Step (when `providers.deployment.id == "kubernetes"` or the project uses kind)

When the deployment target is K8s (kind + NodePort services), the deploy step must follow these
hardened patterns — each one prevented a real CI failure:

1. **NodePort uniqueness gate** — before any apply, validate every `infra/k8s/overlays/*/service-patch.yaml` `nodePort:`
   against `infra/deployment/ports.json` (cluster-scoped: dev `30080/30500`, qa `31080/31500`, prod `32080/32500`).
   Drift or collision must fail the build. Use `tools/sdd_cli/k8s_ports.py` as the canonical generator.
2. **Delete Deployments before apply** — Deployment `spec.selector.matchLabels` is immutable; delete the existing
   Deployment per app in the target namespace before `kubectl apply`, or the apply fails with `field is immutable`.
   Do **not** delete Services — their selector IS mutable and they update in place.
3. **Heredoc/python column-0 rule** — any `python3 << PYEOF` / `python3 -c "..."` block inside a `run: |` block
   must start at **column 0** of the generated script (YAML keeps its indentation offset; bash heredoc terminators
   and Python `-c` bodies reject it). Validate with `bash -n` and `python -m py_compile` on extracted scripts.
4. **kind image pruning** — prune old commit tags from the local daemon and the kind node (`ctr -n k8s.io`),
   guarded so the current build's image is never pruned.
5. **CI kubeconfig** — never hardcode the API port `6443`; kind picks a random host port per cluster. Derive it
   from `kind get kubeconfig` and transform the file as YAML, not line surgery.
6. **PROD artifact-reuse guard** — when the dispatch input `environment=prod` is used: skip the build and prune
   steps (`if: steps.env.outputs.ENV != 'prod'`), deploy the pinned `artifact_commit_sha`, verify
   `app/{commitSha}/container-images.json` on Nexus (commitSha match + registry image existence) before deploy, and
   run a PROD `/health` smoke gate (host ports from `infra/deployment/ports.json`) after deploy. Never rebuild or
   republish during PROD promotion.
7. **src/test deploy gate** — deploy in ANY environment only when the change set touches a `src/`, `test/`, or
   `tests/` folder at any depth (`(^|/)(src|test|tests)/`). For PR merges diff the PR base against the merge commit;
   for `workflow_dispatch` use the commit's first-parent diff (checkout at depth 2). Docs, infra, and workflow-only
   changes must not deploy — gate every deploy step with `if: steps.changes.outputs.deployable == 'true'`.

### 5. Generate `pr-validation.yml`

This workflow is mostly static. Generate it with the standard checkout, JSON validation, secret scan,
SAST/SCA/IaC scans, and the dev-flow review gate steps. **Do NOT use `--skip-db-update` on a first-run
Trivy scan** (no pre-cached vuln DB in the CI image) — the runner container has outbound internet, so let
Trivy download its DB on the first run. It also includes the **repo tooling tests** step (see
`.codex/skills/_shared/test-requirements.md`):

**If SCA (Trivy fs) flags `react-router` in a consumer frontend:** the MEDIUM/HIGH advisories are only
fixed by a coordinated upgrade — `npm install react@^19.2.7 react-dom@^19.2.7 react-router@^8.3.0`
(v8 merged `react-router-dom` into `react-router` and requires React ≥ 19.2.7), remove
`react-router-dom` from `package.json`, and migrate imports `from "react-router-dom"` →
`from "react-router"` (same declarative API: `BrowserRouter`, `Routes`, `Route`, `Link`, `useNavigate`).

1. **Repo tooling tests** — always run the shell's own Python test suite (deterministic, stack-independent):

   ```bash
   python3 -m pytest tools/sdd_cli/tests/ -q
   ```

2. **Product tests (unit, integration, architecture) run via the lefthook `pre-push` hook** — NOT in the CI image. This
keeps `sdd-e2e-ci:local` lean: stack runtimes (.NET SDK, Go, ...) live on the
developer machine, and the tests run locally BEFORE push. The hook executes `python -m tools.sdd_cli stack-tests`, which
reads `project-profile.local.json → stack.testFrameworks` and runs the mapped
(install, test) pairs for the three test levels. When no stack is configured (template state), it reports and exits 0 —
never assume a tech stack.

   **⚠️ Enforcement note:** because product tests run via the local hook, CI does NOT gate product tests. The `pre-push`
   hook is the only enforcement point and can be bypassed with `git push
   --no-verify`. This matches the lean-image decision, but document it in PRs and never rely on CI to catch product test
   failures.

### 5a. Product Test Frameworks → Local Commands (`stack-tests`)

The `python -m tools.sdd_cli stack-tests` driver (`tools/sdd_cli/stack_tests.py`) maps each configured framework to an
(install, test) command pair covering the three levels:

| Framework | Install command (first) | Test command (unit + integration + architecture) |
|-----------|-------------------------|--------------------------------------------------|
| `pytest`  | `python3 -m pip install -r requirements.txt` | `python3 -m pytest test/unit test/integration test/architecture -q` |
| `vitest`  | `npm ci` | `npx vitest run test/unit test/integration test/architecture` |
| `jest`    | `npm ci` | `npx jest test/unit test/integration test/architecture` |
| `dotnet`, `xunit`, `nunit`, `mstest` | `dotnet restore` | `dotnet test` |

**⚠️ pytest is Python-only.** It CANNOT run .NET tests. All .NET test
frameworks (xUnit, NUnit, MSTest) run through `dotnet test`, which requires the
**.NET SDK installed on the developer machine** — never map a .NET framework to
pytest. Run the hook with:

```bash
python -m tools.sdd_cli stack-tests            # real run
python -m tools.sdd_cli stack-tests --dry-run true  # preview only
```

If a test framework has no runtime on the dev machine, the hook fails with
`dotnet`/`go` not found — that failure is a signal to install the runtime
locally, not to switch the framework to pytest.

### 6. Dry-Run Mode

Before writing any files, offer a dry-run preview:

```text
text
Would update .gitea/workflows/package-deploy.yml:
  + Build frontend (React): npm ci → dist/
  + Package artifacts: frontend-landing-page.zip, backend-api.zip
  + Upload to Nexus: http://host.docker.internal:8088/sdd-artifacts
  + Deploy to dev/qa: node server.mjs on port 4173/4174
Would keep .gitea/workflows/pr-validation.yml (unchanged)
```

Show the diff or full content of each generated file. Ask the user to confirm before writing.

### 7. Write Files

Write the generated YAML to:

- `.gitea/workflows/package-deploy.yml`
- `.gitea/workflows/pr-validation.yml`

Preserve the existing `set -eo pipefail` pattern (not `-u` to avoid unbound variable errors). Keep the checkout step's
`GIT_TERMINAL_PROMPT=0` and token-based URL pattern with
`host.docker.internal:3000`.

## Output

Report:

- Which workflow files were created or updated
- Which stack technologies were detected and the build commands generated for each
- Which apps from `apps.json` are included in the package/deploy steps
- Which artifact provider and deployment provider were configured
- Any apps with no build output detected (included in package step but skipped at runtime)
- Dry-run confirmation before writing
- handoff point: workflows ready for review on the active ticket

## Failure Rules

- If `project-profile.local.json` or `project-profile.example.json` does not exist, stop and ask the user to run
`configure-dev-environment` first to set the project stack.
- If `infra/deployment/apps.json` does not exist, generate minimal workflows with only checkout and a stub deploy step
that reports no apps configured.
- If no frontend, backend, or database stack is configured (all `applies: false`), generate minimal workflows without
build steps.
- Never overwrite a workflow file without first showing a dry-run diff and asking for confirmation.
- Never remove the checkout step — it is required for all workflows.
- Never hardcode secrets or tokens into workflow files — always use `${{ secrets.* }}` expressions.
- Preserve the checkout URL pattern with `host.docker.internal:3000` — do not change it to `localhost` or `gitea`.
