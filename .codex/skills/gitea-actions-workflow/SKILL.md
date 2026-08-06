# Gitea Actions Workflow Authoring

Author and maintain Gitea Actions CI/CD workflows for .NET Core, Node.js, Python, and other stacks.

## Scope

This skill covers writing, testing, and debugging `.gitea/workflows/*.yml` files for Gitea Actions runners.

## Workflow Patterns

### Build and Test (.NET Core)

```yaml
name: build-test
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup .NET
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: '8.0.x'
      - name: Restore
        run: dotnet restore
      - name: Build
        run: dotnet build --no-restore
      - name: Test
        run: dotnet test --no-build --verbosity normal
```

### Matrix Build

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest]
    dotnet: ['8.0.x', '9.0.x']
```

### Docker Build and Push

```yaml
- name: Build and push Docker image
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: ${{ secrets.REGISTRY_URL }}/app:${{ github.sha }}
```

### NuGet Package Caching

```yaml
- name: Cache NuGet packages
  uses: actions/cache@v4
  with:
    path: ~/.nuget/packages
    key: ${{ runner.os }}-nuget-${{ hashFiles('**/*.csproj') }}
    restore-keys: |
      ${{ runner.os }}-nuget-
```

## Runner Configuration (Self-Hosted)

### Registration

- Navigate to Gitea: `Site Admin → Runners → Create Runner`
- Registration token is found at `/{owner}/{repo}/settings/actions/runners`
- Use the token when starting the runner: `./act_runner register --token {token}`

### Docker-in-Docker Runner Setup

- Use Docker image for the runner itself (acts as a Docker-out-of-Docker or DinD setup):

  ```yaml
  version: '3'
  services:
    runner:
      image: gitea/act_runner:latest
      environment:
        - GITEA_INSTANCE_URL=http://gitea:3000
        - GITEA_RUNNER_REGISTRATION_TOKEN={token}
        - GITEA_RUNNER_LABELS=ubuntu-latest:docker://node:20-bullseye
      volumes:
        - /var/run/docker.sock:/var/run/docker.sock
        - ./data:/data
  ```

- Mounting `/var/run/docker.sock` gives the runner access to the host Docker daemon (Docker-out-of-Docker)
- For full DinD isolation, use a Docker-in-Docker sidecar instead of socket mounting

### Runner Scaling

- Add multiple runner instances with the **same registration token** for horizontal scaling
- Use Docker Compose `replicas` or separate services for different label sets
- Labels control which runner picks which job (e.g., `ubuntu-latest`, `windows-latest`)
- Monitor runner health via Gitea admin UI or runner logs

## Branch Protection

- Configure via Gitea UI: `Settings → Branches → Branch Protection`
- Required checks: status checks from Actions workflows
- PR templates at `.gitea/PULL_REQUEST_TEMPLATE.md`
- Webhook setup for external CI: `Settings → Webhooks`

## References

- Gitea Actions docs: <https://docs.gitea.com/usage/actions>
- Gitea MCP: `gitea` server in `.vscode/mcp.json`
