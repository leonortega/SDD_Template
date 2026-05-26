param(
  [ValidateSet("Audit", "InitLocalFiles", "SetClientTools", "SetPlaneEnv", "SetGiteaRunner", "SetPrometheusAzureTargets", "AuditQualityGates", "InitQualityGateTemplates", "SetQualityConfig")]
  [string]$Mode = "Audit",

  [string]$Root = (Resolve-Path ".").Path,

  [switch]$DryRun,

  [string]$ValuesJson
)

$ErrorActionPreference = "Stop"

$scriptPath = Resolve-Path (Join-Path $PSScriptRoot "../../configure-dev-environment/scripts/configure_infra_tools.ps1")
$arguments = @{
  Mode = $Mode
  Root = $Root
}

if ($DryRun) {
  $arguments["DryRun"] = $true
}

if (-not [string]::IsNullOrWhiteSpace($ValuesJson)) {
  $arguments["ValuesJson"] = $ValuesJson
}

& $scriptPath @arguments
