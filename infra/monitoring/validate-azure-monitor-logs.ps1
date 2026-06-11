param(
    [string] $GrafanaBaseUrl = "http://localhost:3001",
    [int] $TimeoutSeconds = 300,
    [int] $PollSeconds = 15
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$localEnvPath = Join-Path $repoRoot "infra\plane\variables.env"
if (Test-Path $localEnvPath) {
    foreach ($line in Get-Content -Path $localEnvPath) {
        if ($line -match '^\s*#' -or [string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $parts = $line -split '=', 2
        if ($parts.Count -eq 2 -and [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($parts[0]))) {
            [Environment]::SetEnvironmentVariable($parts[0], $parts[1], "Process")
        }
    }
}

$requiredEnvironmentVariables = @(
    "GRAFANA_AZURE_TENANT_ID",
    "GRAFANA_AZURE_CLIENT_ID",
    "GRAFANA_AZURE_CLIENT_SECRET",
    "GRAFANA_AZURE_SUBSCRIPTION_ID",
    "GRAFANA_AZURE_DEV_LOG_ANALYTICS_WORKSPACE_ID",
    "GRAFANA_AZURE_QA_LOG_ANALYTICS_WORKSPACE_ID",
    "GRAFANA_AZURE_PROD_LOG_ANALYTICS_WORKSPACE_ID"
)

$missing = @(
    foreach ($name in $requiredEnvironmentVariables) {
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
            $name
        }
    }
)

if ($missing.Count -gt 0) {
    throw "Missing required Grafana Azure Monitor environment variables: $($missing -join ', ')"
}

try {
    $health = Invoke-WebRequest -Uri "$GrafanaBaseUrl/api/health" -UseBasicParsing -TimeoutSec 10
    if ($health.StatusCode -lt 200 -or $health.StatusCode -ge 300) {
        throw "Grafana readiness returned HTTP $($health.StatusCode)."
    }
}
catch {
    throw "Grafana is not ready at $GrafanaBaseUrl. Start local monitoring before validating Azure Monitor. $($_.Exception.Message)"
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$environments = @("dev", "qa", "prod")
$observed = @{}
foreach ($environment in $environments) {
    $observed[$environment] = $false
}

while ((Get-Date) -lt $deadline) {
    foreach ($environment in $environments) {
        if ($observed[$environment]) {
            continue
        }

        $workspaceId = [Environment]::GetEnvironmentVariable("GRAFANA_AZURE_$($environment.ToUpperInvariant())_LOG_ANALYTICS_WORKSPACE_ID")
        $query = @"
union isfuzzy=true AppServiceConsoleLogs, AppServiceAppLogs, AppServiceHTTPLogs, AppServicePlatformLogs
| where TimeGenerated > ago(24h)
| take 1
"@

        try {
            $response = az monitor log-analytics query `
                --workspace $workspaceId `
                --analytics-query $query `
                --output json
            if ($LASTEXITCODE -ne 0) {
                throw "Azure CLI Log Analytics query failed."
            }

            $trimmedResponse = ($response -join [Environment]::NewLine).Trim()
            if (-not [string]::IsNullOrWhiteSpace($trimmedResponse) -and $trimmedResponse -ne "[]") {
                $observed[$environment] = $true
            }
        }
        catch {
            # Some environments may not have emitted logs yet. Keep polling until timeout.
        }
    }

    $remaining = @($environments | Where-Object { -not $observed[$_] })
    if ($remaining.Count -eq 0) {
        [pscustomobject]@{
            status = "passed"
            grafanaBaseUrl = $GrafanaBaseUrl
            observedEnvironments = $environments
        } | ConvertTo-Json
        exit 0
    }

    Start-Sleep -Seconds $PollSeconds
}

throw "Timed out waiting for Azure Monitor logs in Log Analytics for environments: $($remaining -join ', ')"
