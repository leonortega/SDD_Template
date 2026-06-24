# Shared Prerequisites

Load this reference whenever a required executable, SDK, CLI, scanner, or local dependency is missing or incompatible, or when a domain workflow asks for install guidance.

When reporting a missing prerequisite to the user, include:

- What is missing and why this repo needs it.
- The install command.
- The official URL.
- The command to run after installation to validate or configure it.

If the missing prerequisite is not listed here, use the official vendor documentation or package-manager page before giving install guidance, then add the same four pieces of information in the response.

## Git for Windows

Required for repo inspection, branch creation, pushing to Gitea, and owner/repo inference.

Check:

```powershell
git --version
```

Install:

```powershell
winget install --id Git.Git -e --source winget
```

Official URL: https://git-scm.com/install/windows

After install, reopen PowerShell and run `git --version`.

## Docker Desktop

Required for `.\infra\up.ps1`, `.\infra\down.ps1`, local Plane/Gitea/Nexus/Grafana/Seq, and non-secret live checks.

Check:

```powershell
docker --version
docker compose version
```

Install:

```powershell
winget install --id Docker.DockerDesktop -e --source winget
```

Official URL: https://docs.docker.com/desktop/setup/install/windows-install/

After install, run `wsl --update`, start Docker Desktop, reopen PowerShell, then run `docker run hello-world`.

## k3d

Required for the default local Kubernetes lane. k3d creates k3s cluster nodes as Docker containers while the `k3d` CLI runs on the host.

Check:

```powershell
k3d version
```

Install:

```powershell
choco install k3d -y
```

Alternative:

```powershell
winget install -e --id k3d.k3d
```

Local executable-folder fallback for this workstation:

```powershell
Invoke-WebRequest -Uri https://github.com/k3d-io/k3d/releases/download/v5.9.0/k3d-windows-amd64.exe -OutFile C:\Endava\EndevLocal\Executables\k3d.exe
$env:Path = "C:\Endava\EndevLocal\Executables;$env:Path"
```

Official URL: https://k3d.io/stable/

After install, reopen PowerShell and run:

```powershell
k3d version
k3d cluster create sdd-template --api-port 127.0.0.1:6550
kubectl config current-context
kubectl get nodes
```

## Azure CLI

Required for Azure DEV/QA/PROD validation, Bicep what-if, and deployment.

Check:

```powershell
az version
az account show
```

Install:

```powershell
winget install --exact --id Microsoft.AzureCLI
```

Official URL: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows

After install, reopen PowerShell and run `az login`.

## .NET 10 SDK

Required for .NET 10 Blazor scaffolding, local confidence checks, and Gitea PR validation containers.

Check:

```powershell
dotnet --info
```

Install:

```powershell
winget install --id Microsoft.DotNet.SDK.10 -e --source winget
```

Official URL: https://dotnet.microsoft.com/download/dotnet/10.0

## Lefthook

Required for lightweight local Git hooks.

Check:

```powershell
lefthook version
```

Install:

```powershell
winget install --id evilmartians.lefthook -e --source winget
```

Official URL: https://lefthook.dev/installation/

## Gitleaks

Required for staged local secret scanning and full CI secret scans.

Check:

```powershell
gitleaks version
```

Install:

```powershell
winget install --id Gitleaks.Gitleaks -e --source winget
```

Official URL: https://github.com/gitleaks/gitleaks

## Trivy

Required for CI filesystem/security scanning.

Check:

```powershell
trivy --version
```

Install:

```powershell
winget install --id AquaSecurity.Trivy -e --source winget
```

Official URL: https://aquasecurity.github.io/trivy/

When local scans report `Trivy DB stale`, refresh the local DB before running scans:

```powershell
trivy --download-db-only
```
