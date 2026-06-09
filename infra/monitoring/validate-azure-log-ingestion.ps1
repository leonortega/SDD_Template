param(
    [string] $LokiBaseUrl = "http://localhost:3100",
    [int] $TimeoutSeconds = 300,
    [int] $PollSeconds = 10
)

$ErrorActionPreference = "Stop"

$requiredEnvironmentVariables = @(
    "AZURE_DEV_EVENTHUB_NAMESPACE",
    "AZURE_DEV_EVENTHUB_NAME",
    "AZURE_QA_EVENTHUB_NAMESPACE",
    "AZURE_QA_EVENTHUB_NAME",
    "AZURE_PROD_EVENTHUB_NAMESPACE",
    "AZURE_PROD_EVENTHUB_NAME",
    "AZURE_CLIENT_ID",
    "AZURE_TENANT_ID"
)

$missing = @(
    foreach ($name in $requiredEnvironmentVariables) {
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) {
            $name
        }
    }
)

if ($missing.Count -gt 0) {
    throw "Missing required Azure log ingestion environment variables: $($missing -join ', ')"
}

$healthUri = "$LokiBaseUrl/ready"
try {
    $health = Invoke-WebRequest -Uri $healthUri -UseBasicParsing -TimeoutSec 10
    if ($health.StatusCode -lt 200 -or $health.StatusCode -ge 300) {
        throw "Loki readiness returned HTTP $($health.StatusCode)."
    }
}
catch {
    throw "Loki is not ready at $healthUri. Start infra/monitoring compose before validating ingestion. $($_.Exception.Message)"
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

        $query = [uri]::EscapeDataString("{environment=`"$environment`"}")
        $uri = "$LokiBaseUrl/loki/api/v1/query_range?query=$query&limit=1"
        $response = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 20
        $streams = @($response.data.result)
        if ($streams.Count -gt 0) {
            $observed[$environment] = $true
        }
    }

    $remaining = @($environments | Where-Object { -not $observed[$_] })
    if ($remaining.Count -eq 0) {
        [pscustomobject]@{
            status = "passed"
            lokiBaseUrl = $LokiBaseUrl
            observedEnvironments = $environments
        } | ConvertTo-Json
        exit 0
    }

    Start-Sleep -Seconds $PollSeconds
}

throw "Timed out waiting for Azure logs in Loki for environments: $($remaining -join ', ')"
