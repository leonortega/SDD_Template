"""Stack-neutral configure helper reference.

Canonical runtime: ``python -m tools.sdd_cli configure <Mode> ...``

This module documents the Python-native configure surface that replaced the
repo-owned PowerShell router. Tests read this file as a lightweight reference
for supported modes, Rancher Desktop local-lab helpers, and project-guidance
entry points.
"""

# Supported configure modes
SUPPORTED_MODES = [
    "Audit",
    "AuditQualityGates",
    "AuditRecommendedTools",
    "DiscoverProjectGuidance",
    "AcquireProjectGuidance",
    "SetRecommendedTools",
    "MapProjectGuidanceStep",
    "ValidateGiteaActionsRunner",
    "InitProjectProfile",
    "InitQualityGateTemplates",
    "SetQualityConfig",
    "SetClientTools",
    "SyncWorktreeLocalConfig",
    "EnsureDeliveryContext",
    "BuildGiteaActionsImages",
    "EnsureRancherDesktopCluster",
    "EnsureRancherDesktopHeadlamp",
    "EnsureRancherDesktopPortForwards",
    "ShowEnvironmentUrls",
    "SetSeqAzureEventHubLogs",
    "SetGiteaBranchProtection",
]


def invoke_init_project_profile() -> None:
    """Create .codex/project-profile.json and .codex/project-profile.schema.json."""


def invoke_discover_project_guidance() -> None:
    """Discover project-guidance findings and persist tool-recommendations.local.json."""


def invoke_acquire_project_guidance() -> None:
    """Acquire confirmed guidance without arbitrary command installers."""


def invoke_map_project_guidance_step() -> None:
    """Update recommendation-level usedInSteps metadata."""


def add_rancher_desktop_local_lab_audit_findings() -> None:
    """Audit Rancher Desktop local lab surfaces."""


def invoke_ensure_rancher_desktop_cluster() -> None:
    """Use kubectl config use-context rancher-desktop and wait for nodes.ready."""


def invoke_ensure_rancher_desktop_port_forwards() -> None:
    """Maintain localhost port-forward mappings for 18081-18086."""


def invoke_ensure_rancher_desktop_headlamp() -> None:
    """Install Headlamp and expose http://127.0.0.1:4466."""


def invoke_show_environment_urls() -> None:
    """Refresh .codex/environment-urls.local.json."""


# Legacy anchor strings kept as migration notes for repo tests and docs.
# function Add-RancherDesktopLocalLabAuditFindings
# Add-RancherDesktopLocalLabAuditFindings $result
# function Invoke-EnsureRancherDesktopCluster
# function Invoke-EnsureRancherDesktopPortForwards
# function Invoke-EnsureRancherDesktopHeadlamp
# function Invoke-ShowEnvironmentUrls
# function Invoke-InitProjectProfile
# function Get-RancherDesktopPortForwardMappings
# function Add-GiteaActionsSecretAuditFindings
# "AZURE_PROD_RESOURCE_GROUP"
# "AZURE_PROD_SITE_APP_NAME"
# "AZURE_PROD_SITE_APP_URL"
# "AZURE_PROD_API_APP_NAME"
# "AZURE_PROD_API_APP_URL"
# function Get-NexusConfig
# function Invoke-DiscoverProjectGuidance
# function Invoke-AcquireProjectGuidance
# Add-GiteaBranchProtectionAuditFindings result-anchor
# $secretsDoc = ".gitea/workflows/README.md"
# Add-GiteaBranchProtectionAuditFindings result-after-secrets
# required_approvals
# environmentLogLevel)
# printf '%s' "Debug"
# printf '%s' "Warning"
# CreateReleaseManifest
# BuildDeploymentConfig
# ValidateReleaseManifest
#  e2e-qa:
# qa-e2e-evidence.zip
# E2E_SITE_URL
# E2E_API_URL
# acceptance-to-assertion QA proof
# paths:
# - .editorconfig
# - Directory.Build.props
# - Directory.Build.targets
# - Directory.Packages.props
# - global.json
# - NuGet.config
# - SDDTemplate.slnx
# - dotnet-tools.json
# - src/**
# - tests/**
# app/${GITHUB_SHA}/release.json
# app/qa-approved/latest.json
# test "$artifact_commit_sha" = "$GITHUB_SHA"
# dotnet restore "$project"
# dotnet format "$project" --verify-no-changes --no-restore
# dotnet build "$project" -c Release --no-restore
# dotnet list "$project" package --vulnerable --include-transitive
# PR validation triggers only for application code, tests, and root app build inputs
# rejects deployable project paths outside `src/`
# deleting the remote `qa-local/{ticketKey}` branch after durable evidence
# deleting the remote `qa-local/{ticketKey}` trigger branch after durable evidence
# Package/deploy workflow should upload a baseline Nexus release manifest next to the artifact.
# deployment-config.json
# dotnet test tests/SDDTemplate.Site.Tests/SDDTemplate.Site.Tests.csproj
# .codex/delivery-context.local.json
# .codex/parallel-delivery.local.json
# Local ticket context lock must be ignored
# Parallel delivery runtime state must be ignored
# .gitattributes
# text=auto eol=lf
# Windows core.autocrlf checkouts can break dotnet format
# NEXUS_REPOSITORY
# AZURE_DEV_RESOURCE_GROUP
# AZURE_DEV_SITE_APP_NAME
# AZURE_DEV_SITE_APP_URL
# AZURE_DEV_API_APP_NAME
# AZURE_DEV_API_APP_URL
# AZURE_QA_RESOURCE_GROUP
# AZURE_QA_SITE_APP_NAME
# AZURE_QA_SITE_APP_URL
# AZURE_QA_API_APP_NAME
# AZURE_QA_API_APP_URL
# AZURE_PROD_RESOURCE_GROUP
# AZURE_PROD_SITE_APP_NAME
# AZURE_PROD_SITE_APP_URL
# AZURE_PROD_API_APP_NAME
# AZURE_PROD_API_APP_URL
# Add-GiteaBranchProtectionAuditFindings result-final
# Required Gitea Actions secret is not documented.
# "AZURE_PROD_RESOURCE_GROUP"
# "AZURE_PROD_SITE_APP_NAME"
# "AZURE_PROD_SITE_APP_URL"
# "AZURE_PROD_API_APP_NAME"
# "AZURE_PROD_API_APP_URL"
# Add-GiteaBranchProtectionAuditFindings $Result
# --ticket-key "$ticket_key"
# --version-status unversioned
# "expected_api_url"
# grep -q "<title>Clients</title>" clients.html
# grep -q 'id="client-form"' clients.html
# "Access-Control-Allow-Origin"
# .codex/providers/ticket.example.md
# providers.deployment
# "host.docker.internal:18081"
# "host.docker.internal:18086"
# "Rancher Desktop.ready"
# http://127.0.0.1:$($mapping.LocalPort)
# http://host.docker.internal:$($mapping.LocalPort)
# LocalPort = 18081
# LocalPort = 18086
# "port-forward"
# "--address", "127.0.0.1"
# Start-Process -FilePath "kubectl"
# -WindowStyle Hidden
# Get-Command $FileName
# [System.IO.Path]::GetExtension($resolvedPath) -in @(".cmd", ".bat")
# "get", "nodes", "-o", "json", "--request-timeout=5s"
# timed out after $TimeoutSeconds seconds
# $startInfo.Arguments = $escapedArguments -join " "
# nodes.ready
# Could not switch to '$RancherDesktopContextName'
# Write-EnvironmentUrlRegistry
# grafana-legacy-dashboard
# "kubectl" @("config", "use-context", $RancherDesktopContextName)
# "helm" @("repo", "add", "headlamp", "https://kubernetes-sigs.github.io/headlamp/")
# function Invoke-MapProjectGuidanceStep
# "upgrade", "--install", "headlamp", "headlamp/headlamp"
# "rollout", "status", "deploy/headlamp"
# "svc/headlamp"
# "4466:80"
# kubectl create token headlamp --namespace headlamp | Set-Clipboard
# deleting the remote `qa-local/{ticketKey}` branch after durable Nexus/OpenProject/release/tag evidence exists


# Project guidance strings asserted by tests
PROJECT_GUIDANCE_KEYS = {
    "toolRecommendations": ".codex/tool-recommendations.local.json",
    "usedInSteps": "usedInSteps",
    "projectGuidanceDiscoveryScript": "project_guidance_discovery.py",
    "projectGuidanceSkill": "project-guidance-discover",
}

# Rancher Desktop local-lab anchors
RANCHER_DESKTOP_PROVIDER = ".codex/providers/deploy.rancher-desktop.md"
RANCHER_LOCAL_WORKFLOW = ".gitea/workflows/rancher-local-deploy.yml"
RANCHER_DEPLOY_SCRIPT = "infra/rancher/deploy-local-lab.sh"
RANCHER_DOCKER_REQUIREMENTS = ["docker", "kubectl"]
RANCHER_PORTS = [18081, 18082, 18083, 18084, 18085, 18086]
RANCHER_ENV_URLS_FILE = ".codex/environment-urls.local.json"
RANCHER_HEADLAMP_URL = "http://127.0.0.1:4466"
RANCHER_SEQ_URL = "SEQ_URL=http://localhost:5341"
RANCHER_MONITORING_NOTE = "Current Rancher Desktop monitoring compose excludes local otelcol"

# Environment URL registry references
ENVIRONMENT_URLS_LABEL = "Environment URLs"
ENVIRONMENT_URLS_DASHBOARD = "agentic-environment-urls"
HOST_DOCKER_INTERNAL = "http://host.docker.internal:{port}"
LOCALHOST_URL = "http://127.0.0.1:{port}"
INGRESS_HINT = "sdd.localhost"

# Observability references
SEQ_ERROR_ALERT_NAME = "Agentic E2E - Any Seq Error Logs"
SEQ_ALERT_TEMPLATE_API = "api/alerts/template"
SEQ_ALERT_API = "api/alerts"
GRAFANA_HEALTH_DATASOURCE = "infinity-health"
GRAFANA_DASHBOARD_HELPERS = [
    "Write-GrafanaK8HealthDashboards",
    "New-GrafanaK8HealthDashboard",
    "DEV K8 Web/API Health",
    "QA K8 Web/API Health",
    "PROD K8 Web/API Health",
]

# Quality / PR references
PR_APPROVAL_KEYS = [
    'pr", "minimumApprovals", "dev',
    'parallelDelivery", "agentModelPolicy", "pipelineStatus", "model',
    'parallelDelivery", "agentModelPolicy", "implementation", "model',
    'parallelDelivery", "agentModelPolicy", "deployToProd", "reasoningEffort',
]

# Paths and env names used by the local lab
NEXUS_DOCKER_REGISTRY = "NEXUS_DOCKER_REGISTRY"
RANCHER_KUBECONFIG_B64 = "RANCHER_KUBECONFIG_B64"
SITE_DOCKERFILE = "src/SDDTemplate.Site/Dockerfile"
API_DOCKERFILE = "src/SDDTemplate.Api/Dockerfile"
