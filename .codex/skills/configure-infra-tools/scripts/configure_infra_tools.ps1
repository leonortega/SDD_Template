param(
  [ValidateSet("Audit", "InitLocalFiles", "SetClientTools", "SetPlaneEnv", "SetGiteaRunner", "SetPrometheusAzureTargets")]
  [string]$Mode = "Audit",

  [string]$Root = (Resolve-Path ".").Path,

  [switch]$DryRun,

  [string]$ValuesJson
)

$ErrorActionPreference = "Stop"

function Join-RootPath {
  param([string]$RelativePath)
  return (Join-Path $Root $RelativePath)
}

function New-Result {
  return [ordered]@{
    mode = $Mode
    dryRun = [bool]$DryRun
    actions = @()
    findings = @()
    warnings = @()
  }
}

function Add-Item {
  param(
    $Result,
    [string]$Bucket,
    [string]$Path,
    [string]$Key,
    [string]$Message,
    [string]$Severity = "info",
    [string]$Phase = "post-start"
  )

  $Result[$Bucket] += [ordered]@{
    path = $Path
    key = $Key
    severity = $Severity
    phase = $Phase
    message = $Message
  }
}

function Test-Placeholder {
  param([AllowNull()][string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) { return $true }
  return $Value -match "replace-with|placeholder|changeme|change-me"
}

function Ensure-ObjectProperty {
  param(
    $Object,
    [string]$Name
  )

  if ($null -eq $Object.$Name) {
    $Object | Add-Member -MemberType NoteProperty -Name $Name -Value ([pscustomobject]@{})
  }
}

function Set-ObjectValue {
  param(
    $Object,
    [string[]]$Path,
    $Value
  )

  $cursor = $Object
  for ($i = 0; $i -lt ($Path.Count - 1); $i++) {
    Ensure-ObjectProperty -Object $cursor -Name $Path[$i]
    $cursor = $cursor.$($Path[$i])
  }

  $leaf = $Path[$Path.Count - 1]
  if ($cursor.PSObject.Properties.Name -contains $leaf) {
    $cursor.$leaf = $Value
  } else {
    $cursor | Add-Member -MemberType NoteProperty -Name $leaf -Value $Value
  }
}

function Read-EnvFile {
  param([string]$Path)
  $map = [ordered]@{}
  if (-not (Test-Path $Path)) { return $map }

  foreach ($line in Get-Content -Path $Path) {
    if ($line -match "^\s*$" -or $line -match "^\s*#") { continue }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { continue }
    $key = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1)
    $map[$key] = $value
  }

  return $map
}

function Set-EnvValues {
  param(
    [string]$Path,
    [hashtable]$Values
  )

  $lines = @()
  if (Test-Path $Path) {
    $lines = @(Get-Content -Path $Path)
  }

  $seen = @{}
  $newLines = foreach ($line in $lines) {
    if ($line -match "^\s*#" -or $line -notmatch "=") {
      $line
      continue
    }

    $idx = $line.IndexOf("=")
    $key = $line.Substring(0, $idx).Trim()
    if ($Values.ContainsKey($key)) {
      $seen[$key] = $true
      "$key=$($Values[$key])"
    } else {
      $line
    }
  }

  foreach ($key in $Values.Keys) {
    if (-not $seen.ContainsKey($key)) {
      $newLines += "$key=$($Values[$key])"
    }
  }

  if (-not $DryRun) {
    Set-Content -Path $Path -Value $newLines -Encoding UTF8
  }
}

function Convert-JsonToHashtable {
  param([string]$Json)
  if ([string]::IsNullOrWhiteSpace($Json)) { return @{} }
  $object = $Json | ConvertFrom-Json -Depth 20
  return Convert-ObjectToHashtable $object
}

function Convert-PrometheusTarget {
  param([string]$Value)

  $target = $Value.Trim()
  $target = $target -replace "^https?://", ""
  $target = $target.TrimEnd("/")
  if ([string]::IsNullOrWhiteSpace($target)) {
    throw "Prometheus target cannot be empty."
  }
  return $target
}

function Set-PrometheusAzureTargets {
  param(
    [string]$Path,
    [string[]]$Targets
  )

  $content = Get-Content -Path $Path -Raw
  $normalizedTargets = @($Targets | ForEach-Object { Convert-PrometheusTarget $_ })
  if ($normalizedTargets.Count -eq 0) {
    throw "At least one Azure Prometheus target is required."
  }

  $targetLines = ($normalizedTargets | ForEach-Object { "          - $_" }) -join [Environment]::NewLine
  $replacement = "`${prefix}$targetLines$([Environment]::NewLine)"
  $pattern = "(?ms)(?<prefix>  - job_name: azure-apps.*?      - targets:\r?\n)(?:          - .+?(?:\r?\n|$))+"
  $updated = [regex]::Replace($content, $pattern, $replacement, 1)
  if ($updated -eq $content) {
    throw "Could not find azure-apps targets block in $Path."
  }

  if (-not $DryRun) {
    Set-Content -Path $Path -Value $updated -Encoding UTF8
  }
}

function Convert-ObjectToHashtable {
  param($InputObject)

  if ($null -eq $InputObject) { return $null }
  if ($InputObject -is [System.Collections.IDictionary]) {
    $hash = [ordered]@{}
    foreach ($key in $InputObject.Keys) {
      $hash[$key] = Convert-ObjectToHashtable $InputObject[$key]
    }
    return $hash
  }
  if ($InputObject -is [System.Management.Automation.PSCustomObject]) {
    $hash = [ordered]@{}
    foreach ($prop in $InputObject.PSObject.Properties) {
      $hash[$prop.Name] = Convert-ObjectToHashtable $prop.Value
    }
    return $hash
  }
  if ($InputObject -is [System.Collections.IEnumerable] -and $InputObject -isnot [string]) {
    return @($InputObject | ForEach-Object { Convert-ObjectToHashtable $_ })
  }
  return $InputObject
}

function Copy-LocalFile {
  param(
    $Result,
    [string]$SourceRelative,
    [string]$TargetRelative
  )

  $source = Join-RootPath $SourceRelative
  $target = Join-RootPath $TargetRelative

  if (Test-Path $target) {
    Add-Item $Result "findings" $TargetRelative "" "Local file already exists."
    return
  }
  if (-not (Test-Path $source)) {
    Add-Item $Result "warnings" $SourceRelative "" "Template file is missing." "warning"
    return
  }

  Add-Item $Result "actions" $TargetRelative "" "Create local file from $SourceRelative."
  if (-not $DryRun) {
    Copy-Item -Path $source -Destination $target
  }
}

function Invoke-Audit {
  $result = New-Result

  $clientLocal = ".codex/client-tools.local.json"
  $clientPath = Join-RootPath $clientLocal
  if (-not (Test-Path $clientPath)) {
    Add-Item $result "findings" $clientLocal "" "Local client tool config is missing." "error"
  } else {
    $client = Get-Content -Path $clientPath -Raw | ConvertFrom-Json
    if ($null -eq $client.plane.inProgressState) {
      Add-Item $result "findings" $clientLocal "plane.inProgressState" "Missing; default should be In Progress unless the user chooses another state." "warning"
    }
    if ($null -eq $client.plane.reviewState) {
      Add-Item $result "findings" $clientLocal "plane.reviewState" "Missing; default should be In Review unless the user chooses another Plane review state." "warning"
    }
    if (Test-Placeholder $client.plane.apiToken) {
      Add-Item $result "findings" $clientLocal "plane.apiToken" "Missing or placeholder Plane API token." "error"
    }

    if ($null -eq $client.gitea) {
      Add-Item $result "findings" $clientLocal "gitea" "Missing Gitea PR automation config section." "warning"
    } else {
      if ($null -eq $client.gitea.baseUrl) {
        Add-Item $result "findings" $clientLocal "gitea.baseUrl" "Missing; default should be http://localhost:3000." "warning"
      }
      if (Test-Placeholder $client.gitea.apiToken) {
        Add-Item $result "findings" $clientLocal "gitea.apiToken" "Missing or placeholder Gitea API token for PR creation, review comments, labels, and reviewer lookup." "error"
      }
    }

    if ($null -eq $client.pr) {
      Add-Item $result "findings" $clientLocal "pr" "Missing PR workflow config section." "warning"
    } else {
      if ($null -eq $client.pr.reviewers) {
        Add-Item $result "findings" $clientLocal "pr.reviewers" "Missing; default should be all or an explicit developer username array." "warning"
      } elseif (($client.pr.reviewers -is [string]) -and [string]::IsNullOrWhiteSpace($client.pr.reviewers)) {
        Add-Item $result "findings" $clientLocal "pr.reviewers" "Empty reviewer config; use all or an explicit developer username array." "warning"
      }

      if ($null -eq $client.pr.labels) {
        Add-Item $result "findings" $clientLocal "pr.labels" "Missing PR label config; defaults should enable codex-reviewed, needs-tests, and needs-changes." "warning"
      } elseif ($client.pr.labels.enabled -ne $false) {
        foreach ($labelKey in @("reviewed", "needsTests", "needsChanges")) {
          if ($null -eq $client.pr.labels.$labelKey -or [string]::IsNullOrWhiteSpace([string]$client.pr.labels.$labelKey)) {
            Add-Item $result "findings" $clientLocal "pr.labels.$labelKey" "Missing PR label name." "warning"
          }
        }
      }
    }
  }

  $planeLocal = "infra/plane/variables.env"
  $plane = Read-EnvFile (Join-RootPath $planeLocal)
  if ($plane.Count -eq 0) {
    Add-Item $result "findings" $planeLocal "" "Plane local env file is missing or empty." "error" "pre-start"
  } else {
    $unsafePairs = @{
      POSTGRES_PASSWORD = @("plane")
      RABBITMQ_DEFAULT_PASS = @("plane")
      AWS_ACCESS_KEY_ID = @("access-key")
      AWS_SECRET_ACCESS_KEY = @("secret-key")
      MINIO_ROOT_USER = @("access-key")
      MINIO_ROOT_PASSWORD = @("secret-key")
    }

    foreach ($key in $unsafePairs.Keys) {
      if ($plane.Contains($key) -and ($unsafePairs[$key] -contains $plane[$key])) {
        Add-Item $result "findings" $planeLocal $key "Unsafe local default; replace with a generated local value." "warning" "pre-start"
      }
    }

    foreach ($key in @("MACHINE_SIGNATURE", "SECRET_KEY", "SILO_HMAC_SECRET_KEY", "AES_SECRET_KEY", "LIVE_SERVER_SECRET_KEY", "PI_INTERNAL_SECRET")) {
      if (-not $plane.Contains($key) -or (Test-Placeholder $plane[$key])) {
        Add-Item $result "findings" $planeLocal $key "Missing or placeholder generated secret." "warning" "pre-start"
      }
    }

    if ($plane.Contains("FOLLOWER_POSTGRES_URI") -and $plane["FOLLOWER_POSTGRES_URI"] -match "plane:plane@") {
      Add-Item $result "findings" $planeLocal "FOLLOWER_POSTGRES_URI" "Contains unsafe default Postgres password." "warning" "pre-start"
    }
    if ($plane.Contains("AMQP_URL") -and $plane["AMQP_URL"] -match "plane:plane@") {
      Add-Item $result "findings" $planeLocal "AMQP_URL" "Contains unsafe default RabbitMQ password." "warning" "pre-start"
    }
  }

  $runnerLocal = "infra/gitea/runner.env"
  $runner = Read-EnvFile (Join-RootPath $runnerLocal)
  if ($runner.Count -eq 0) {
    Add-Item $result "findings" $runnerLocal "" "Gitea runner env file is missing or empty." "error" "pre-start"
  } elseif (-not $runner.Contains("GITEA_RUNNER_REGISTRATION_TOKEN") -or (Test-Placeholder $runner["GITEA_RUNNER_REGISTRATION_TOKEN"])) {
    Add-Item $result "findings" $runnerLocal "GITEA_RUNNER_REGISTRATION_TOKEN" "Missing or placeholder Gitea runner registration token." "warning"
  }

  $promLocal = "infra/monitoring/prometheus.local.yml"
  $promPath = Join-RootPath $promLocal
  if (Test-Path $promPath) {
    $prom = Get-Content -Path $promPath -Raw
    foreach ($target in @("replace-dev-web.azurewebsites.net", "replace-dev-api.azurewebsites.net", "replace-qa-web.azurewebsites.net", "replace-qa-api.azurewebsites.net", "replace-prod-web.azurewebsites.net", "replace-prod-api.azurewebsites.net")) {
      if ($prom.Contains($target)) {
        Add-Item $result "findings" $promLocal "azure-apps" "Placeholder Azure target remains in local Prometheus config: $target." "info"
      }
    }
  } elseif ($plane.Contains("PROMETHEUS_CONFIG_FILE") -and $plane["PROMETHEUS_CONFIG_FILE"] -eq "./prometheus.local.yml") {
    Add-Item $result "findings" $promLocal "PROMETHEUS_CONFIG_FILE" "Plane env points Prometheus at a missing local config file." "warning" "pre-start"
  }

  $grafanaDashboards = @(
    "infra/monitoring/grafana/provisioning/dashboards/dashboards.yml",
    "infra/monitoring/grafana/dashboards/local-infra-health.json",
    "infra/monitoring/grafana/dashboards/azure-app-health.json"
  )
  foreach ($dashboardFile in $grafanaDashboards) {
    if (-not (Test-Path (Join-RootPath $dashboardFile))) {
      Add-Item $result "findings" $dashboardFile "grafana-dashboard-provisioning" "Missing Grafana dashboard provisioning artifact." "info" "post-start"
    }
  }

  return $result
}

function Invoke-InitLocalFiles {
  $result = New-Result
  Copy-LocalFile $result ".codex/client-tools.example.json" ".codex/client-tools.local.json"
  Copy-LocalFile $result "infra/plane/variables.env.example" "infra/plane/variables.env"
  Copy-LocalFile $result "infra/gitea/runner.env.example" "infra/gitea/runner.env"
  Copy-LocalFile $result "infra/monitoring/prometheus.yml" "infra/monitoring/prometheus.local.yml"
  return $result
}

function Invoke-SetClientTools {
  $result = New-Result
  $targetRelative = ".codex/client-tools.local.json"
  $target = Join-RootPath $targetRelative
  if (-not (Test-Path $target)) {
    throw "Missing $targetRelative. Run -Mode InitLocalFiles first."
  }

  $values = Convert-JsonToHashtable $ValuesJson
  $config = Get-Content -Path $target -Raw | ConvertFrom-Json -Depth 20
  foreach ($section in @("plane", "git", "gitea", "pr")) {
    if ($values.Contains($section)) {
      Ensure-ObjectProperty -Object $config -Name $section
      foreach ($key in $values[$section].Keys) {
        if (($values[$section][$key] -is [System.Collections.IDictionary]) -and ($null -ne $values[$section][$key])) {
          foreach ($nestedKey in $values[$section][$key].Keys) {
            Set-ObjectValue -Object $config -Path @($section, $key, $nestedKey) -Value $values[$section][$key][$nestedKey]
            Add-Item $result "actions" $targetRelative "$section.$key.$nestedKey" "Set confirmed value."
          }
        } else {
          Set-ObjectValue -Object $config -Path @($section, $key) -Value $values[$section][$key]
          Add-Item $result "actions" $targetRelative "$section.$key" "Set confirmed value."
        }
      }
    }
  }

  if (-not $DryRun) {
    $config | ConvertTo-Json -Depth 20 | Set-Content -Path $target -Encoding UTF8
  }
  return $result
}

function Invoke-SetEnvMode {
  param(
    [string]$TargetRelative
  )

  $result = New-Result
  $target = Join-RootPath $TargetRelative
  if (-not (Test-Path $target)) {
    throw "Missing $TargetRelative. Run -Mode InitLocalFiles first."
  }

  $values = Convert-JsonToHashtable $ValuesJson
  if ($values.Count -eq 0) {
    throw "ValuesJson is required for $Mode."
  }

  Set-EnvValues -Path $target -Values $values
  foreach ($key in $values.Keys) {
    Add-Item $result "actions" $TargetRelative $key "Set confirmed value."
  }
  return $result
}

function Invoke-SetPrometheusAzureTargets {
  $result = New-Result
  $targetRelative = "infra/monitoring/prometheus.local.yml"
  $target = Join-RootPath $targetRelative
  if (-not (Test-Path $target)) {
    throw "Missing $targetRelative. Run -Mode InitLocalFiles first."
  }

  $values = Convert-JsonToHashtable $ValuesJson
  if (-not $values.Contains("targets")) {
    throw "ValuesJson must include a targets array."
  }

  Set-PrometheusAzureTargets -Path $target -Targets @($values["targets"])
  foreach ($targetValue in @($values["targets"])) {
    Add-Item $result "actions" $targetRelative "azure-apps" "Set Azure Prometheus target $(Convert-PrometheusTarget $targetValue)."
  }
  return $result
}

switch ($Mode) {
  "Audit" { $result = Invoke-Audit }
  "InitLocalFiles" { $result = Invoke-InitLocalFiles }
  "SetClientTools" { $result = Invoke-SetClientTools }
  "SetPlaneEnv" { $result = Invoke-SetEnvMode -TargetRelative "infra/plane/variables.env" }
  "SetGiteaRunner" { $result = Invoke-SetEnvMode -TargetRelative "infra/gitea/runner.env" }
  "SetPrometheusAzureTargets" { $result = Invoke-SetPrometheusAzureTargets }
}

$result | ConvertTo-Json -Depth 10
