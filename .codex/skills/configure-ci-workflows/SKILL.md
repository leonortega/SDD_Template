---
name: configure-ci-workflows
description: Generate or update Gitea Actions CI/CD workflow files based on the project profile stack and app topology. Run after configure-dev-environment selects the project stack, or when apps.json, project-profile, or client-tools configuration changes.
---

<!-- TIER 3: STAGE-SPECIFIC - CI workflow configuration skill -->

# Configure CI Workflows

## Overview

Use this skill after `configure-dev-environment` has set the project stack and infrastructure is running. It reads the project profile to determine which technologies are used (frontend, backend, database), which apps exist in the deployment topology, and which providers are configured, then generates the `.gitea/workflows/*.yml` files with appropriate build, package, upload, and deploy steps.

This skill replaces manually editing workflow files when the project stack changes. Run it whenever:

- A new project stack is selected (e.g., adding a backend after initial frontend-only setup)
- New apps are added to `infra/deployment/apps.json`
- The artifact or deployment provider changes (e.g., Nexus to docker-registry)

## Shared Context

Before generating workflows, read:

1. **Project profile** — use the merged profile (reads `project-profile.json` first, falls back to `project-profile.example.json`, merges with `project-profile.local.json`). Get stack: frontend, backend, database values and provider selections.
2. `infra/deployment/apps.json` — for app topology (appId, projectPath, role, artifactName, healthPath, deployOrder)
3. `.codex/client-tools.local.json` — for Gitea base URL, Nexus base URL and repository

Also follow `.codex/skills/_shared/skill-startup.md` for the standard startup sequence.

## Configuration

The skill derives configuration from these sources:

| Source                                                                         | What it provides                                                                                        |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| Merged project profile (`project-profile.json` + `project-profile.local.json`) | Stack: frontend/backend/database technologies. Providers: artifact (Nexus), deployment (docker-desktop) |
| `infra/deployment/apps.json`                                                   | App topology: what to build, package, and deploy                                                        |
| `client-tools.local.json → gitea`                                              | Gitea URL for checkout step                                                                             |
| `client-tools.local.json → nexus`                                              | Nexus URL, repository for upload step                                                                   |

## Workflow Generation Rules

### 1. Detect Stack Technologies

Read `project-profile.local.json → stack` and determine build commands per domain:

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
  push:
    branches:
      - dev
  workflow_dispatch:
    inputs:
      environment:
        description: Target environment (dev or qa)
        required: true
        default: dev

jobs:
  build-and-deploy:
    if: github.event_name == 'workflow_dispatch' || github.ref == 'refs/heads/dev'
    runs-on: ubuntu-latest
    container:
      image: sdd-e2e-ci:local
    steps:
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
          git fetch --depth 1 origin "$GITHUB_SHA"
          git checkout --force FETCH_HEAD

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
    if [ "${{ github.event_name }}" = "push" ]; then
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

### 5. Generate `pr-validation.yml`

This workflow is mostly static. Generate it with the standard checkout, JSON validation, and secret scan steps:

```yaml
name: PR validation

on:
  pull_request:
    branches:
      - main
      - dev

jobs:
  validate:
    runs-on: ubuntu-latest
    container:
      image: sdd-e2e-ci:local
    steps:
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
          git fetch --depth 1 origin "$GITHUB_SHA"
          git checkout --force FETCH_HEAD

      - name: Validate JSON files
        shell: bash
        run: |
          set -euo pipefail
          find . -path './.git' -prune -o -name '*.json' -print | while IFS= read -r file; do
            python3 -m json.tool "$file" >/dev/null
          done

      - name: Secret scan
        shell: bash
        run: gitleaks detect --source . --redact --no-git
```

### 6. Generate `agent-eval.yml`

This workflow is also mostly static:

```yaml
name: Agent evaluation

on:
  pull_request:
    branches:
      - dev
    paths:
      - ".codex/agent-evals/**"
      - ".codex/delivery-policy.json"
      - ".codex/skills/_shared/delivery-contract*.md"
      - "tools/sdd_cli/agent_eval.py"

jobs:
  eval:
    runs-on: ubuntu-latest
    container:
      image: sdd-e2e-ci:local
    steps:
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
          git fetch --depth 1 origin "$GITHUB_SHA"
          git checkout --force FETCH_HEAD

      - name: Install promptfoo
        shell: bash
        run: |
          set -euo pipefail
          npm install -g promptfoo
          promptfoo --version

      - name: Run agent routing evaluation
        shell: bash
        run: |
          set -euo pipefail
          python3 -m tools.sdd_cli agent-eval ci
```

### 7. Dry-Run Mode

Before writing any files, offer a dry-run preview:

```
text
Would update .gitea/workflows/package-deploy.yml:
  + Build frontend (React): npm ci → dist/
  + Package artifacts: frontend-landing-page.zip, openproject-17.5.1.zip
  + Upload to Nexus: http://host.docker.internal:8088/sdd-artifacts
  + Deploy to dev/qa: node server.mjs on port 4173/4174
Would keep .gitea/workflows/pr-validation.yml (unchanged)
Would keep .gitea/workflows/agent-eval.yml (unchanged)
```

Show the diff or full content of each generated file. Ask the user to confirm before writing.

### 8. Write Files

Write the generated YAML to:

- `.gitea/workflows/package-deploy.yml`
- `.gitea/workflows/pr-validation.yml`
- `.gitea/workflows/agent-eval.yml`

Preserve the existing `set -eo pipefail` pattern (not `-u` to avoid unbound variable errors). Keep the checkout step's `GIT_TERMINAL_PROMPT=0` and token-based URL pattern with `host.docker.internal:3000`.

## Output

Report:

- Which workflow files were created or updated
- Which stack technologies were detected and the build commands generated for each
- Which apps from `apps.json` are included in the package/deploy steps
- Which artifact provider and deployment provider were configured
- Any apps with no build output detected (included in package step but skipped at runtime)
- Dry-run confirmation before writing

## Failure Rules

- If `project-profile.local.json` or `project-profile.example.json` does not exist, stop and ask the user to run `configure-dev-environment` first to set the project stack.
- If `infra/deployment/apps.json` does not exist, generate minimal workflows with only checkout and a stub deploy step that reports no apps configured.
- If no frontend, backend, or database stack is configured (all `applies: false`), generate minimal workflows without build steps.
- Never overwrite a workflow file without first showing a dry-run diff and asking for confirmation.
- Never remove the checkout step — it is required for all workflows.
- Never hardcode secrets or tokens into workflow files — always use `${{ secrets.* }}` expressions.
- Preserve the checkout URL pattern with `host.docker.internal:3000` — do not change it to `localhost` or `gitea`.
