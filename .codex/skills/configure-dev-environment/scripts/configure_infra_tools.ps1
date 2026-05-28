param(
  [ValidateSet("Audit", "InitLocalFiles", "SetClientTools", "SetPlaneEnv", "SetGiteaRunner", "SetPrometheusAzureTargets", "AuditQualityGates", "ValidateGiteaActionsRunner", "InitQualityGateTemplates", "SetQualityConfig")]
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

function Test-FileContains {
  param(
    [string]$RelativePath,
    [string]$Pattern
  )

  $path = Join-RootPath $RelativePath
  if (-not (Test-Path $path)) { return $false }
  $content = Get-Content -Path $path -Raw
  return $content -match $Pattern
}

function Get-WorkflowContent {
  param([string]$RelativePath)

  $path = Join-RootPath $RelativePath
  if (-not (Test-Path $path)) { return $null }
  return Get-Content -Path $path -Raw
}

function Get-WorkflowContainerImage {
  param([string]$Content)

  if ([string]::IsNullOrWhiteSpace($Content)) { return $null }
  if ($Content -match "(?m)^\s*image:\s*(\S+)\s*$") {
    return $Matches[1].Trim()
  }
  return $null
}

function Add-GiteaActionsRunnerCompatibilityFindings {
  param(
    $Result,
    [string]$WorkflowRelativePath
  )

  $workflow = Get-WorkflowContent $WorkflowRelativePath
  if ([string]::IsNullOrWhiteSpace($workflow)) { return }

  $containerImage = Get-WorkflowContainerImage $workflow
  $usesJobContainer = -not [string]::IsNullOrWhiteSpace($containerImage)
  $usesDotnetSdkContainer = $containerImage -match "^mcr\.microsoft\.com/dotnet/sdk:"

  if ($usesJobContainer -and $usesDotnetSdkContainer) {
    if ($workflow -match "(?m)^\s*uses:\s*actions/checkout@") {
      Add-Item $Result "findings" $WorkflowRelativePath "actions.checkout" "Workflow uses actions/checkout inside the .NET SDK job container. JavaScript actions require node in the job container; use shell checkout or a container image that includes node." "warning"
    }

    if ($workflow -match "(?m)^\s*uses:\s*aquasecurity/trivy-action@") {
      Add-Item $Result "findings" $WorkflowRelativePath "trivy-action" "Workflow uses a JavaScript Trivy action inside the .NET SDK job container. Install and run trivy from shell, or use a container image that includes node." "warning"
    }
  }

  if ($workflow -match "raw\.githubusercontent\.com/gitleaks/gitleaks/(master|main)/install\.sh") {
    Add-Item $Result "findings" $WorkflowRelativePath "gitleaks.install" "Workflow installs Gitleaks from a moving raw install script URL. Pin a Gitleaks release archive so CI does not break when install paths change." "warning"
  }

  if ($workflow -match "zip\s+-r" -and $workflow -notmatch "apt-get install .*zip") {
    Add-Item $Result "findings" $WorkflowRelativePath "zip.install" "Workflow creates ZIP artifacts inside a container but does not install zip. The .NET SDK container does not include zip by default." "warning"
  }

  if ($usesDotnetSdkContainer -and $containerImage -match ":10\.0\.100$") {
    Add-Item $Result "findings" $WorkflowRelativePath "dotnet.sdk.image" "Workflow uses mcr.microsoft.com/dotnet/sdk:10.0.100, which failed to pull on the local runner. Prefer a validated .NET 10 patch image such as 10.0.300 when compatible with global.json roll-forward." "warning"
  }

  if ($workflow -match "git fetch --depth 1 origin" -or $workflow -match "git remote add origin") {
    foreach ($hostname in @("localhost", "gitea")) {
      $rewriteLine = 'repo_url="${repo_url/__HOST__/host.docker.internal}"'.Replace("__HOST__", $hostname)
      if ($workflow -notmatch [regex]::Escape($rewriteLine)) {
        Add-Item $Result "findings" $WorkflowRelativePath "checkout.$hostname" "Containerized shell checkout does not rewrite '$hostname' to 'host.docker.internal'. Docker job containers may fail to reach local Gitea." "warning"
      }
    }
  }

}

function Add-GiteaBranchProtectionAuditFindings {
  param($Result)

  $clientLocal = ".codex/client-tools.local.json"
  $clientPath = Join-RootPath $clientLocal
  if (-not (Test-Path $clientPath)) { return }

  try {
    $client = Get-Content -Path $clientPath -Raw | ConvertFrom-Json
  } catch {
    Add-Item $Result "findings" $clientLocal "" "Could not parse local client tool config for branch protection validation." "warning"
    return
  }

  if (Test-Placeholder $client.gitea.apiToken -or $null -eq $client.gitea.baseUrl -or $null -eq $client.gitea.owner -or $null -eq $client.gitea.repo) {
    Add-Item $Result "findings" $clientLocal "gitea" "Cannot validate Gitea branch protection status contexts because Gitea API config is missing or placeholder." "info"
    return
  }

  $expectedContext = "PR validation / validate (pull_request)"
  $headers = @{ Authorization = "token $($client.gitea.apiToken)"; Accept = "application/json" }
  $baseUrl = ([string]$client.gitea.baseUrl).TrimEnd("/")
  $targetBranches = @("main", "dev")

  foreach ($branch in $targetBranches) {
    try {
      $protection = Invoke-RestMethod -Method Get -Uri "$baseUrl/api/v1/repos/$($client.gitea.owner)/$($client.gitea.repo)/branch_protections/$branch" -Headers $headers
    } catch {
      Add-Item $Result "findings" ".gitea/workflows/README.md" "branch-protection.$branch" "Could not read Gitea branch protection for '$branch'. Configure required status check context '$expectedContext' manually if branch protection is enabled." "info"
      continue
    }

    if ($protection.enable_status_check -and (@($protection.status_check_contexts) -notcontains $expectedContext)) {
      Add-Item $Result "findings" ".gitea/workflows/README.md" "branch-protection.$branch" "Gitea branch protection for '$branch' requires status contexts '$(@($protection.status_check_contexts) -join ', ')', but PR validation reports '$expectedContext'. Update branch protection to require the emitted context." "warning"
    }
  }
}

function Get-QualityCoverageMinimum {
  param([string]$RelativePath)

  $path = Join-RootPath $RelativePath
  if (-not (Test-Path $path)) { return $null }

  try {
    $quality = Get-Content -Path $path -Raw | ConvertFrom-Json
  } catch {
    return $null
  }

  if ($null -eq $quality.coverage.minimumPercent) { return $null }
  $minimum = 0
  if (-not [int]::TryParse([string]$quality.coverage.minimumPercent, [ref]$minimum)) {
    return $null
  }
  return $minimum
}

function Get-QualityCoverageMinimumFromObject {
  param($Quality)

  if ($null -eq $Quality.coverage.minimumPercent) { return $null }
  $minimum = 0
  if (-not [int]::TryParse([string]$Quality.coverage.minimumPercent, [ref]$minimum)) {
    return $null
  }
  return $minimum
}

function Add-QualityGateAuditFindings {
  param($Result)

  $qualityExample = ".codex/quality.example.json"
  $qualityLocal = ".codex/quality.local.json"
  $defaultCoverage = Get-QualityCoverageMinimum $qualityExample
  $localCoverage = Get-QualityCoverageMinimum $qualityLocal

  if ($null -eq $defaultCoverage) {
    Add-Item $Result "findings" $qualityExample "coverage.minimumPercent" "Missing or invalid default coverage threshold; expected integer 1-100 with default 80." "warning"
  } elseif ($defaultCoverage -lt 1 -or $defaultCoverage -gt 100) {
    Add-Item $Result "findings" $qualityExample "coverage.minimumPercent" "Default coverage threshold must be between 1 and 100." "warning"
  }

  if (-not (Test-Path (Join-RootPath $qualityLocal))) {
    Add-Item $Result "findings" $qualityLocal "coverage.minimumPercent" "Local quality config is missing; InitLocalFiles creates it from .codex/quality.example.json. Default coverage threshold is 80." "info"
  } elseif ($null -eq $localCoverage) {
    Add-Item $Result "findings" $qualityLocal "coverage.minimumPercent" "Local coverage threshold is missing or invalid; use SetQualityConfig with coverage.minimumPercent." "warning"
  } elseif ($localCoverage -lt 1 -or $localCoverage -gt 100) {
    Add-Item $Result "findings" $qualityLocal "coverage.minimumPercent" "Local coverage threshold must be between 1 and 100." "warning"
  }

  $prWorkflow = ".gitea/workflows/pr-validation.yml"
  if (-not (Test-Path (Join-RootPath $prWorkflow))) {
    Add-Item $Result "findings" $prWorkflow "" "Missing Gitea PR validation workflow." "warning"
  } else {
    foreach ($expected in @("dotnet restore", "dotnet format", "dotnet build", "dotnet test", "minimumPercent", "gitleaks", "trivy")) {
      if (-not (Test-FileContains $prWorkflow ([regex]::Escape($expected)))) {
        Add-Item $Result "findings" $prWorkflow $expected "PR validation workflow does not mention $expected." "warning"
      }
    }
    Add-GiteaActionsRunnerCompatibilityFindings $Result $prWorkflow
  }

  $releaseWorkflow = ".gitea/workflows/package-deploy.yml"
  if (-not (Test-Path (Join-RootPath $releaseWorkflow))) {
    Add-Item $Result "findings" $releaseWorkflow "" "Missing package/deploy workflow for Nexus artifact publication and Azure promotion." "warning"
  } else {
    foreach ($expected in @("NEXUS_URL", "NEXUS_USERNAME", "NEXUS_PASSWORD", "az webapp deploy", "classify-changes", "app_changed", "deploy_allowed", ".codex/delivery-policy.json", "ticketKeyPattern", "refs/heads/dev", "refs/heads/main", "deploy-qa", "deploy-prod", "artifact_commit_sha", "PROD_ARTIFACT_COMMIT_SHA", "release_version", "source_rc_version", "release.json", "schemaVersion", "planeTicketKey", "versionStatus", "AZURE_QA_RESOURCE_GROUP", "AZURE_QA_WEBAPP_NAME", "AZURE_QA_WEBAPP_URL", "AZURE_PROD_RESOURCE_GROUP", "AZURE_PROD_WEBAPP_NAME", "AZURE_PROD_WEBAPP_URL", "/health")) {
      if (-not (Test-FileContains $releaseWorkflow ([regex]::Escape($expected)))) {
        Add-Item $Result "findings" $releaseWorkflow $expected "Package/deploy workflow does not mention $expected." "warning"
      }
    }
    Add-GiteaActionsRunnerCompatibilityFindings $Result $releaseWorkflow
    if (-not (Test-FileContains $releaseWorkflow "branches:\s*\r?\n\s*-\s*dev")) {
      Add-Item $Result "findings" $releaseWorkflow "on.push.branches.dev" "Package/deploy workflow should trigger from dev for QA candidate artifacts." "warning"
    }
    if (-not (Test-FileContains $releaseWorkflow "branches:\s*\r?\n\s*-\s*dev\s*\r?\n\s*-\s*main")) {
      Add-Item $Result "findings" $releaseWorkflow "on.push.branches.main" "Package/deploy workflow should trigger from main for ticket-gated PROD promotion only." "warning"
    }
    if (-not (Test-FileContains $releaseWorkflow "needs\.classify-changes\.outputs\.deploy_allowed == 'true'")) {
      Add-Item $Result "findings" $releaseWorkflow "deploy_allowed" "Push-triggered deployments should be gated by ticket-named commits or merged PR titles." "warning"
    }
    if (-not (Test-FileContains $releaseWorkflow "app/\$\{GITHUB_SHA\}/release\.json")) {
      Add-Item $Result "findings" $releaseWorkflow "release.json" "Package/deploy workflow should upload a baseline Nexus release manifest next to the artifact." "warning"
    }
    $releaseContent = Get-Content -Path (Join-RootPath $releaseWorkflow) -Raw
    $publishCount = ([regex]::Matches($releaseContent, "dotnet publish")).Count
    if ($publishCount -gt 1) {
      Add-Item $Result "findings" $releaseWorkflow "dotnet publish" "Package/deploy workflow appears to publish more than once; DEV, QA, and PROD should promote the same Nexus artifact." "warning"
    }
  }

  $deliveryPolicy = ".codex/delivery-policy.json"
  if (-not (Test-Path (Join-RootPath $deliveryPolicy))) {
    Add-Item $Result "findings" $deliveryPolicy "ticketKeyPattern" "Missing delivery policy used by commit hooks and deployment gating." "warning"
  } elseif (-not (Test-FileContains $deliveryPolicy '"ticketKeyPattern"\s*:')) {
    Add-Item $Result "findings" $deliveryPolicy "ticketKeyPattern" "Delivery policy must define ticketKeyPattern for deployment gating." "warning"
  }

  $gitignore = ".gitignore"
  if (-not (Test-Path (Join-RootPath $gitignore))) {
    Add-Item $Result "findings" $gitignore ".codex/delivery-context.local.json" "Missing .gitignore; local ticket context lock must not be committed." "warning"
  } elseif (-not (Test-FileContains $gitignore "\.codex/delivery-context\.local\.json")) {
    Add-Item $Result "findings" $gitignore ".codex/delivery-context.local.json" "Local ticket context lock must be ignored so automatic delivery stays ticket-scoped without committing runtime state." "warning"
  }

  $globalJson = "global.json"
  $globalJsonPath = Join-RootPath $globalJson
  if (-not (Test-Path $globalJsonPath)) {
    Add-Item $Result "findings" $globalJson "sdk.version" "Missing global.json pinned to .NET 10 SDK." "warning"
  } else {
    $global = Get-Content -Path $globalJsonPath -Raw | ConvertFrom-Json
    if ($null -eq $global.sdk.version -or ([string]$global.sdk.version) -notmatch "^10\.") {
      Add-Item $Result "findings" $globalJson "sdk.version" "global.json is not pinned to a .NET 10 SDK version." "warning"
    }
  }

  foreach ($qualityFile in @(".editorconfig", "Directory.Build.props", "lefthook.yml")) {
    if (-not (Test-Path (Join-RootPath $qualityFile))) {
      Add-Item $Result "findings" $qualityFile "" "Missing quality gate template." "warning"
    }
  }

  $giteaCompose = "infra/gitea/compose.yml"
  if (Test-Path (Join-RootPath $giteaCompose)) {
    $compose = Get-Content -Path (Join-RootPath $giteaCompose) -Raw
    if ($compose -match "gitea/gitea:1\.21\.7") {
      Add-Item $Result "findings" $giteaCompose "gitea.image" "Gitea image is pinned to old 1.21.7; review and pin to a supported current release before relying on CI/CD." "warning" "pre-start"
    }
    if ($compose -match "gitea/act_runner:latest") {
      Add-Item $Result "findings" $giteaCompose "runner.image" "Gitea runner image uses floating latest tag; pin a known runner version." "warning" "pre-start"
    }
  }

  foreach ($composeFile in Get-ChildItem -Path (Join-RootPath "infra") -Filter "compose.yml" -Recurse -ErrorAction SilentlyContinue) {
    $relativeCompose = [System.IO.Path]::GetRelativePath($Root, $composeFile.FullName).Replace("\", "/")
    $lines = Get-Content -Path $composeFile.FullName
    for ($i = 0; $i -lt $lines.Count; $i++) {
      if ($lines[$i] -match "^\s*image:\s*(\S+):(\S+)\s*$") {
        $image = $Matches[1]
        $tag = $Matches[2]
        if ($tag -in @("latest", "main", "nightly") -or $tag -match "(^|[-.])rc($|[-.0-9])") {
          Add-Item $Result "findings" $relativeCompose "image" "Docker image '$image' uses floating or pre-release tag '$tag'; check current stable upstream version and pin a patch tag." "warning" "pre-start"
        }
      }
    }
  }

  $azureMain = "infra/azure/main.bicep"
  if (Test-FileContains $azureMain "DOTNETCORE\|8\.0") {
    Add-Item $Result "findings" $azureMain "webRuntimeStack/apiRuntimeStack" "Azure runtime defaults still target DOTNETCORE|8.0; align with .NET 10 app or use a self-contained deployment strategy." "warning"
  }
  foreach ($parametersFile in @("infra/azure/dev.parameters.json", "infra/azure/qa.parameters.json", "infra/azure/prod.parameters.json")) {
    if (Test-Path (Join-RootPath $parametersFile)) {
      $params = Get-Content -Path (Join-RootPath $parametersFile) -Raw | ConvertFrom-Json
      if ($null -eq $params.parameters.webRuntimeStack -or $null -eq $params.parameters.apiRuntimeStack) {
        Add-Item $Result "findings" $parametersFile "runtimeStack" "Runtime stack is not overridden; deployment will use the template default." "info"
      }
    }
  }

  $secretsDoc = ".gitea/workflows/README.md"
  if (-not (Test-Path (Join-RootPath $secretsDoc))) {
    Add-Item $Result "findings" $secretsDoc "" "Missing documentation for required Gitea Actions secrets and branch protection." "warning"
  } else {
    foreach ($secret in @("NEXUS_URL", "NEXUS_USERNAME", "NEXUS_PASSWORD", "NEXUS_REPOSITORY", "AZURE_CREDENTIALS", "AZURE_DEV_RESOURCE_GROUP", "AZURE_DEV_WEBAPP_NAME", "AZURE_DEV_WEBAPP_URL", "AZURE_QA_RESOURCE_GROUP", "AZURE_QA_WEBAPP_NAME", "AZURE_QA_WEBAPP_URL", "AZURE_PROD_RESOURCE_GROUP", "AZURE_PROD_WEBAPP_NAME", "AZURE_PROD_WEBAPP_URL")) {
      if (-not (Test-FileContains $secretsDoc $secret)) {
        Add-Item $Result "findings" $secretsDoc $secret "Required Gitea Actions secret is not documented." "warning"
      }
    }
  }

  Add-GiteaBranchProtectionAuditFindings $Result
  Add-GiteaActionsSecretAuditFindings $Result
  Add-NexusRepositoryAuditFindings $Result
}

function Get-ConfiguredGiteaActionsSecrets {
  $clientPath = Join-RootPath ".codex/client-tools.local.json"
  if (-not (Test-Path $clientPath)) {
    return $null
  }

  try {
    $client = Get-Content -Path $clientPath -Raw | ConvertFrom-Json
  } catch {
    return $null
  }

  if ($null -eq $client.gitea -or
      [string]::IsNullOrWhiteSpace([string]$client.gitea.baseUrl) -or
      [string]::IsNullOrWhiteSpace([string]$client.gitea.owner) -or
      [string]::IsNullOrWhiteSpace([string]$client.gitea.repo) -or
      (Test-Placeholder ([string]$client.gitea.apiToken))) {
    return $null
  }

  $headers = @{ Authorization = "token $($client.gitea.apiToken)" }
  $uri = "$($client.gitea.baseUrl.TrimEnd('/'))/api/v1/repos/$($client.gitea.owner)/$($client.gitea.repo)/actions/secrets?limit=100"
  $response = Invoke-RestMethod -Uri $uri -Headers $headers -TimeoutSec 15
  if ($response.PSObject.Properties.Name -contains "secrets") {
    return @($response.secrets | ForEach-Object { $_.name })
  }

  return @($response | ForEach-Object { $_.name })
}

function Add-GiteaActionsSecretAuditFindings {
  param($Result)

  $requiredSecrets = @(
    "NEXUS_URL",
    "NEXUS_USERNAME",
    "NEXUS_PASSWORD",
    "NEXUS_REPOSITORY",
    "AZURE_CREDENTIALS",
    "AZURE_DEV_RESOURCE_GROUP",
    "AZURE_DEV_WEBAPP_NAME",
    "AZURE_DEV_WEBAPP_URL",
    "AZURE_QA_RESOURCE_GROUP",
    "AZURE_QA_WEBAPP_NAME",
    "AZURE_QA_WEBAPP_URL",
    "AZURE_PROD_RESOURCE_GROUP",
    "AZURE_PROD_WEBAPP_NAME",
    "AZURE_PROD_WEBAPP_URL"
  )

  try {
    $configuredSecrets = Get-ConfiguredGiteaActionsSecrets
  } catch {
    Add-Item $Result "findings" ".codex/client-tools.local.json" "gitea.actions.secrets" "Could not validate Gitea Actions secrets by API; verify Gitea is running and the configured token can list repository Actions secrets." "warning" "post-start"
    return
  }

  if ($null -eq $configuredSecrets) {
    Add-Item $Result "findings" ".codex/client-tools.local.json" "gitea.actions.secrets" "Gitea Actions secrets were not validated because local Gitea API configuration is missing or placeholder." "warning" "post-start"
    return
  }

  foreach ($secret in $requiredSecrets) {
    if ($configuredSecrets -notcontains $secret) {
      Add-Item $Result "findings" ".gitea/workflows/package-deploy.yml" $secret "Missing required Gitea Actions secret for package/deploy workflow." "warning" "post-start"
    }
  }
}

function Get-NexusConfig {
  $clientPath = Join-RootPath ".codex/client-tools.local.json"
  if (-not (Test-Path $clientPath)) {
    return $null
  }

  try {
    $client = Get-Content -Path $clientPath -Raw | ConvertFrom-Json
  } catch {
    return $null
  }

  if ($null -eq $client.nexus) {
    return $null
  }

  return $client.nexus
}

function Test-NexusConfigComplete {
  param($Nexus)

  if ($null -eq $Nexus) { return $false }
  foreach ($key in @("baseUrl", "username", "password", "repository")) {
    if ($null -eq $Nexus.$key -or (Test-Placeholder ([string]$Nexus.$key))) {
      return $false
    }
  }

  return $true
}

function Get-NexusRepositories {
  param($Nexus)

  $baseUrl = ([string]$Nexus.baseUrl).TrimEnd("/")
  $pair = "$($Nexus.username):$($Nexus.password)"
  $encoded = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
  $headers = @{ Authorization = "Basic $encoded" }
  return Invoke-RestMethod -Uri "$baseUrl/service/rest/v1/repositories" -Headers $headers -TimeoutSec 15
}

function Add-NexusRepositoryAuditFindings {
  param($Result)

  $nexus = Get-NexusConfig
  if (-not (Test-NexusConfigComplete $nexus)) {
    Add-Item $Result "findings" ".codex/client-tools.local.json" "nexus" "Missing Nexus local check configuration; set nexus.baseUrl, nexus.username, nexus.password, and nexus.repository so repository checks can authenticate." "warning" "post-start"
    return
  }

  try {
    $repositories = @(Get-NexusRepositories $nexus)
  } catch {
    Add-Item $Result "findings" ".codex/client-tools.local.json" "nexus.repository" "Could not validate Nexus repository with configured credentials; verify Nexus is running and the configured user can list repositories." "warning" "post-start"
    return
  }

  $expectedRepository = [string]$nexus.repository
  $matchedRepository = @($repositories | Where-Object { $_.name -eq $expectedRepository -and $_.format -eq "raw" -and $_.type -eq "hosted" })
  if ($matchedRepository.Count -eq 0) {
    Add-Item $Result "findings" ".codex/client-tools.local.json" "nexus.repository" "Configured Nexus repository '$expectedRepository' was not found as a hosted raw repository." "warning" "post-start"
  }
}

function Test-ClientValueMissing {
  param(
    $Object,
    [string]$Name
  )

  if ($null -eq $Object) { return $true }
  if ($Object.PSObject.Properties.Name -notcontains $Name) { return $true }
  return Test-Placeholder ([string]$Object.$Name)
}

function Set-InferredClientValue {
  param(
    $Result,
    $Client,
    [string[]]$Path,
    $Value
  )

  $cursor = $Client
  for ($i = 0; $i -lt ($Path.Count - 1); $i++) {
    Ensure-ObjectProperty -Object $cursor -Name $Path[$i]
    $cursor = $cursor.$($Path[$i])
  }

  $leaf = $Path[$Path.Count - 1]
  if (-not (Test-ClientValueMissing $cursor $leaf)) {
    return
  }

  Set-ObjectValue -Object $Client -Path $Path -Value $Value
  Add-Item $Result "actions" ".codex/client-tools.local.json" ($Path -join ".") "Set inferred local client tool value."
}

function Get-GitRemoteOwnerRepo {
  $remoteUrl = ""
  try {
    $remoteUrl = (& git -C $Root remote get-url origin 2>$null)
  } catch {
    return $null
  }

  if ([string]::IsNullOrWhiteSpace($remoteUrl)) { return $null }
  $remoteUrl = $remoteUrl.Trim()

  if ($remoteUrl -match "[:/]([^/:]+)/([^/]+?)(?:\.git)?$") {
    return [pscustomobject]@{
      owner = $Matches[1]
      repo = $Matches[2]
    }
  }

  return $null
}

function Ensure-InferredClientToolsConfig {
  param($Result)

  $targetRelative = ".codex/client-tools.local.json"
  $target = Join-RootPath $targetRelative
  if (-not (Test-Path $target)) {
    $source = Join-RootPath ".codex/client-tools.example.json"
    if (-not (Test-Path $source)) {
      Add-Item $Result "warnings" ".codex/client-tools.example.json" "" "Template file is missing; cannot initialize local client tools config." "warning"
      return
    }

    Add-Item $Result "actions" $targetRelative "" "Create local client tools config from template."
    if (-not $DryRun) {
      Copy-Item -Path $source -Destination $target
    }
  }

  if (-not (Test-Path $target)) { return }
  try {
    $client = Get-Content -Path $target -Raw | ConvertFrom-Json -Depth 20
  } catch {
    Add-Item $Result "findings" $targetRelative "" "Local client tools config is not valid JSON." "error"
    return
  }

  $remote = Get-GitRemoteOwnerRepo

  Set-InferredClientValue $Result $client @("plane", "baseUrl") "http://localhost:8080"
  Set-InferredClientValue $Result $client @("plane", "todoState") "Todo"
  Set-InferredClientValue $Result $client @("plane", "inProgressState") "In Progress"
  Set-InferredClientValue $Result $client @("plane", "reviewState") "In Review"
  Set-InferredClientValue $Result $client @("plane", "qaState") "QA"
  Set-InferredClientValue $Result $client @("plane", "doneState") "Done"

  Set-InferredClientValue $Result $client @("git", "baseBranch") "dev"
  Set-InferredClientValue $Result $client @("git", "branchPrefix") "codex"
  Set-InferredClientValue $Result $client @("git", "branchPattern") "{prefix}/{ticketKeySlug}-{titleSlug}"
  Set-InferredClientValue $Result $client @("git", "maxBranchLength") 100

  Set-InferredClientValue $Result $client @("gitea", "baseUrl") "http://localhost:3000"
  if ($null -ne $remote) {
    Set-InferredClientValue $Result $client @("gitea", "owner") $remote.owner
    Set-InferredClientValue $Result $client @("gitea", "repo") $remote.repo
  }

  Set-InferredClientValue $Result $client @("nexus", "baseUrl") "http://localhost:8088"
  Set-InferredClientValue $Result $client @("nexus", "repository") "raw-hosted"

  Set-InferredClientValue $Result $client @("pr", "reviewers") "all"
  Set-InferredClientValue $Result $client @("pr", "labels", "enabled") $true
  Set-InferredClientValue $Result $client @("pr", "labels", "reviewed") "codex-reviewed"
  Set-InferredClientValue $Result $client @("pr", "labels", "needsTests") "needs-tests"
  Set-InferredClientValue $Result $client @("pr", "labels", "needsChanges") "needs-changes"

  if (-not $DryRun) {
    $client | ConvertTo-Json -Depth 20 | Set-Content -Path $target -Encoding UTF8
  }
}

function Invoke-Audit {
  $result = New-Result
  Ensure-InferredClientToolsConfig $result

  $clientLocal = ".codex/client-tools.local.json"
  $clientPath = Join-RootPath $clientLocal
  if (-not (Test-Path $clientPath)) {
    Add-Item $result "findings" $clientLocal "" "Local client tool config is missing." "error"
  } else {
    $client = Get-Content -Path $clientPath -Raw | ConvertFrom-Json
    foreach ($requiredPlaneValue in @("baseUrl", "todoState", "inProgressState", "reviewState", "qaState", "doneState")) {
      if (Test-ClientValueMissing $client.plane $requiredPlaneValue) {
        Add-Item $result "findings" $clientLocal "plane.$requiredPlaneValue" "Missing inferred Plane local value; rerun Audit to apply defaults or set manually." "warning"
      }
    }
    if (Test-Placeholder $client.plane.apiToken) {
      Add-Item $result "findings" $clientLocal "plane.apiToken" "Missing or placeholder Plane API token; ask the user for this value." "error"
    }
    foreach ($requiredPlaneUserValue in @("workspaceSlug", "projectIdentifier")) {
      if (Test-ClientValueMissing $client.plane $requiredPlaneUserValue) {
        Add-Item $result "findings" $clientLocal "plane.$requiredPlaneUserValue" "Missing Plane value and it is not inferable from local files; ask the user for this value." "warning"
      }
    }

    if ($null -eq $client.gitea) {
      Add-Item $result "findings" $clientLocal "gitea" "Missing Gitea PR automation config section." "warning"
    } else {
      if ($null -eq $client.gitea.baseUrl) {
        Add-Item $result "findings" $clientLocal "gitea.baseUrl" "Missing; default should be http://localhost:3000." "warning"
      }
      if (Test-Placeholder $client.gitea.apiToken) {
        Add-Item $result "findings" $clientLocal "gitea.apiToken" "Missing or placeholder Gitea API token for PR creation, review comments, labels, and reviewer lookup; ask the user for this value." "error"
      }
      foreach ($requiredGiteaValue in @("owner", "repo")) {
        if (Test-ClientValueMissing $client.gitea $requiredGiteaValue) {
          Add-Item $result "findings" $clientLocal "gitea.$requiredGiteaValue" "Missing Gitea value and it could not be inferred from the git origin remote; ask the user for this value." "warning"
        }
      }
    }

    if ($null -eq $client.nexus) {
      Add-Item $result "findings" $clientLocal "nexus" "Missing Nexus local check config; inferred baseUrl/repository should be completed, username and password/token must come from the user." "warning"
    } else {
      foreach ($requiredNexusUserValue in @("username", "password")) {
        if (Test-ClientValueMissing $client.nexus $requiredNexusUserValue) {
          Add-Item $result "findings" $clientLocal "nexus.$requiredNexusUserValue" "Missing Nexus credential and it is not inferable; ask the user for this value." "warning"
        }
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

  Add-QualityGateAuditFindings $result

  return $result
}

function Invoke-AuditQualityGates {
  $result = New-Result
  Ensure-InferredClientToolsConfig $result
  Add-QualityGateAuditFindings $result
  return $result
}

function Invoke-ValidateGiteaActionsRunner {
  $result = New-Result
  $workflowRelativePath = ".gitea/workflows/pr-validation.yml"
  $workflow = Get-WorkflowContent $workflowRelativePath

  Add-QualityGateAuditFindings $result

  if ([string]::IsNullOrWhiteSpace($workflow)) {
    Add-Item $result "findings" $workflowRelativePath "" "Cannot run Gitea Actions validation because the PR validation workflow is missing." "error"
    return $result
  }

  $containerImage = Get-WorkflowContainerImage $workflow
  if ([string]::IsNullOrWhiteSpace($containerImage)) {
    Add-Item $result "findings" $workflowRelativePath "container.image" "Cannot validate runner job container because no container image is configured." "warning"
    return $result
  }

  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if ($null -eq $docker) {
    Add-Item $result "findings" "docker" "" "Docker CLI is missing; install Docker Desktop or Docker Engine before validating Gitea Actions runner containers." "error"
    return $result
  }

  try {
    & docker version | Out-Null
    Add-Item $result "actions" "docker" "" "Docker CLI is available."
  } catch {
    Add-Item $result "findings" "docker" "" "Docker CLI is installed but not usable: $($_.Exception.Message)" "error"
    return $result
  }

  try {
    & docker pull $containerImage | Out-Null
    Add-Item $result "actions" $workflowRelativePath "container.image" "Pulled runner job image $containerImage successfully."
  } catch {
    Add-Item $result "findings" $workflowRelativePath "container.image" "Could not pull runner job image $containerImage. Pin a pullable stable patch image before enabling PR validation." "error"
    return $result
  }

  $toolCheck = "for tool in bash git curl tar dotnet; do command -v `$tool >/dev/null || { echo missing:`$tool; exit 1; }; done"
  try {
    & docker run --rm --entrypoint /bin/sh $containerImage -lc $toolCheck | Out-Null
    Add-Item $result "actions" $workflowRelativePath "container.tools" "Runner job image includes bash, git, curl, tar, and dotnet."
  } catch {
    Add-Item $result "findings" $workflowRelativePath "container.tools" "Runner job image is missing a tool required by shell-based PR validation. Required: bash, git, curl, tar, dotnet." "error"
  }

  $origin = $null
  try {
    $origin = (& git -C $Root remote get-url origin).Trim()
  } catch {
    Add-Item $result "findings" "git" "origin" "Cannot resolve git origin URL for container checkout validation." "warning"
  }

  if (-not [string]::IsNullOrWhiteSpace($origin)) {
    $repoUrl = $origin -replace "localhost", "host.docker.internal"
    $repoUrl = $repoUrl -replace "gitea", "host.docker.internal"
    try {
      & docker run --rm -e "REPO_URL=$repoUrl" --entrypoint /bin/sh $containerImage -lc 'git ls-remote "$REPO_URL" HEAD >/dev/null' | Out-Null
      Add-Item $result "actions" $workflowRelativePath "checkout.network" "Runner job image can reach the repository origin through host.docker.internal."
    } catch {
      Add-Item $result "findings" $workflowRelativePath "checkout.network" "Runner job image cannot reach the repository origin through host.docker.internal. Check Gitea URL rewriting, Docker host networking, and GITEA_INSTANCE_URL." "error"
    }
  }

  return $result
}

function Write-TemplateFile {
  param(
    $Result,
    [string]$RelativePath,
    [string]$Content
  )

  $target = Join-RootPath $RelativePath
  if (Test-Path $target) {
    Add-Item $Result "findings" $RelativePath "" "Template already exists."
    return
  }

  $parent = Split-Path -Path $target -Parent
  Add-Item $Result "actions" $RelativePath "" "Create quality gate template."
  if (-not $DryRun) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    Set-Content -Path $target -Value $Content -Encoding UTF8
  }
}

function Invoke-InitQualityGateTemplates {
  $result = New-Result

  Write-TemplateFile $result "global.json" @'
{
  "sdk": {
    "version": "10.0.100",
    "rollForward": "latestFeature"
  }
}
'@

  Write-TemplateFile $result ".editorconfig" @'
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.{cs,cshtml,razor}]
indent_style = space
indent_size = 4

[*.{yml,yaml,json,md}]
indent_style = space
indent_size = 2

[*.cs]
dotnet_analyzer_diagnostic.category-Style.severity = warning
dotnet_analyzer_diagnostic.category-Design.severity = warning
dotnet_analyzer_diagnostic.category-Security.severity = warning
dotnet_diagnostic.CA1822.severity = none
'@

  Write-TemplateFile $result "Directory.Build.props" @'
<Project>
  <PropertyGroup>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
    <AnalysisLevel>latest</AnalysisLevel>
    <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>
    <Deterministic>true</Deterministic>
    <ContinuousIntegrationBuild Condition="'$(CI)' == 'true'">true</ContinuousIntegrationBuild>
  </PropertyGroup>
</Project>
'@

  Write-TemplateFile $result ".gitignore" @'
# Build results
[Dd]ebug/
[Dd]ebugPublic/
[Rr]elease/
[Rr]eleases/
x64/
x86/
[Aa][Rr][Mm]/
[Aa][Rr][Mm]64/
bld/
[Bb]in/
[Oo]bj/
[Ll]og/
[Ll]ogs/
artifacts/
TestResults/
[Tt]est[Rr]esult*/
coverage/
coverage.*
*.coverage
*.coveragexml
*.trx
*.vsp
*.vspx
*.sap

# Visual Studio user and cache files
.vs/
*.user
*.rsuser
*.suo
*.userosscache
*.sln.docstates
*.sln.DotSettings.user
*.userprefs
*.pidb
*.svclog
*.pdb
*.ilk
*.symbols.nupkg

# Visual Studio profiling and diagnostics
*.psess
*.diagsession
BenchmarkDotNet.Artifacts/

# .NET Core / ASP.NET Core
project.lock.json
project.assets.json
*.nuget.props
*.nuget.targets
packages.lock.json
appsettings.*.local.json
appsettings.Local.json
appsettings.Development.local.json
appsettings.Production.local.json
Properties/launchSettings.local.json

# NuGet
packages/
*.nupkg
*.snupkg
*.nuspec.user

# Rider / JetBrains
.idea/
*.sln.iml

# VS Code
.vscode/
!.vscode/settings.json
!.vscode/tasks.json
!.vscode/launch.json
!.vscode/extensions.json
!.vscode/*.code-snippets

# Node/frontend artifacts that may appear in web projects
node_modules/
dist/
.vite/
.next/
.nuxt/
out/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# Local container runtime state
infra/plane/plane/
**/data/
**/logs/

# Local secrets and machine-specific environment files
*.env
!*.env.example
.plane.local.json
.codex/client-tools.local.json
.codex/quality.local.json
.codex/azure-login.local.json
.codex/delivery-context.local.json
infra/monitoring/prometheus.local.yml

# OS/editor noise
.DS_Store
Thumbs.db
ehthumbs.db
Desktop.ini
$RECYCLE.BIN/
'@

  Write-TemplateFile $result ".codex/quality.example.json" @'
{
  "coverage": {
    "minimumPercent": 80
  }
}
'@

  Write-TemplateFile $result ".codex/delivery-policy.json" @'
{
  "ticketKeyPattern": "E2EPROJECT-[0-9]+"
}
'@

  Write-TemplateFile $result "lefthook.yml" @'
pre-commit:
  commands:
    gitleaks-staged:
      run: gitleaks protect --staged --redact

commit-msg:
  commands:
    require-ticket:
      run: powershell -NoProfile -ExecutionPolicy Bypass -File .githooks/require-ticket.ps1 "{1}"
'@

  Write-TemplateFile $result ".githooks/require-ticket.ps1" @'
param(
  [Parameter(Mandatory = $true)]
  [string]$MessagePath
)

$ErrorActionPreference = "Stop"

$message = Get-Content -Path $MessagePath -Raw
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$policyPath = Join-Path $repoRoot ".codex/delivery-policy.json"
$ticketKeyPattern = "E2EPROJECT-[0-9]+"

if (Test-Path -LiteralPath $policyPath) {
  $policy = Get-Content -LiteralPath $policyPath -Raw | ConvertFrom-Json
  if ($policy.ticketKeyPattern) {
    $ticketKeyPattern = [string]$policy.ticketKeyPattern
  }
}

$pattern = "^(\[SDD\] .+|${ticketKeyPattern}: .+|openspec/[a-z0-9][a-z0-9-]*: .+)"

if ($message -notmatch $pattern) {
  Write-Error "Commit message must start with a ticket matching '$ticketKeyPattern', OpenSpec id, or [SDD] for direct SDD repo maintenance, for example: E2EPROJECT-1: scaffold blank Blazor site"
  exit 1
}
'@

  Write-TemplateFile $result ".gitea/workflows/pr-validation.yml" @'
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
      image: mcr.microsoft.com/dotnet/sdk:10.0.300
    steps:
      - name: Checkout
        shell: bash
        run: |
          set -euo pipefail

          repo_url="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}.git"
          repo_url="${repo_url/localhost/host.docker.internal}"
          repo_url="${repo_url/gitea/host.docker.internal}"

          git init .
          git remote add origin "$repo_url"
          git fetch --depth 1 origin "$GITHUB_SHA"
          git checkout --force FETCH_HEAD

      - name: Restore
        run: dotnet restore

      - name: Verify formatting
        run: dotnet format --verify-no-changes --no-restore

      - name: Build
        run: dotnet build -c Release --no-restore

      - name: Test
        run: dotnet test -c Release --no-build --logger trx --collect:"XPlat Code Coverage"

      - name: Enforce coverage threshold
        shell: bash
        run: |
          set -euo pipefail

          config=".codex/quality.local.json"
          if [ ! -f "$config" ]; then
            config=".codex/quality.example.json"
          fi

          minimum="$(sed -n 's/.*"minimumPercent"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$config" | head -n 1 || true)"
          if [ -z "$minimum" ]; then
            minimum="80"
          fi

          coverage_file="$(find . -path '*/coverage.cobertura.xml' -print -quit)"
          if [ -z "$coverage_file" ]; then
            echo "No Cobertura coverage report found."
            exit 1
          fi

          line_rate="$(sed -n 's/.*line-rate="\([0-9.]*\)".*/\1/p' "$coverage_file" | head -n 1 || true)"
          if [ -z "$line_rate" ]; then
            echo "Could not read line-rate from $coverage_file."
            exit 1
          fi

          actual="$(awk -v rate="$line_rate" 'BEGIN { printf "%.2f", rate * 100 }')"
          awk -v actual="$actual" -v minimum="$minimum" 'BEGIN { exit !(actual + 0 >= minimum + 0) }' || {
            echo "Coverage ${actual}% is below required ${minimum}%."
            exit 1
          }

          echo "Coverage ${actual}% meets required ${minimum}%."

      - name: Dependency vulnerability audit
        run: dotnet list package --vulnerable --include-transitive

      - name: Install Gitleaks
        run: |
          curl -sSfL https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz \
            | tar -xz -C /usr/local/bin gitleaks

      - name: Secret scan
        run: gitleaks detect --source . --redact --no-git

      - name: Install Trivy
        run: |
          curl -sSfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
            | sh -s -- -b /usr/local/bin v0.70.0

      - name: Trivy filesystem scan
        run: trivy fs --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed .

      # Optional: add Semgrep when rules and runtime budget are agreed.
'@

  Write-TemplateFile $result ".gitea/workflows/package-deploy.yml" @'
name: Package and deploy

on:
  push:
    branches:
      - dev
      - main
  workflow_dispatch:
    inputs:
      environment:
        description: Target environment for promotion
        required: true
        default: dev
      artifact_commit_sha:
        description: Existing Nexus artifact commit SHA for PROD promotion
        required: false
        default: ''
      release_version:
        description: Release version for PROD promotion
        required: false
        default: ''
      source_rc_version:
        description: QA-approved RC version promoted to PROD
        required: false
        default: ''

jobs:
  classify-changes:
    runs-on: ubuntu-latest
    outputs:
      app_changed: ${{ steps.classify.outputs.app_changed }}
      deploy_allowed: ${{ steps.classify.outputs.deploy_allowed }}
    steps:
      - name: Checkout
        shell: bash
        run: |
          set -euo pipefail

          repo_url="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}.git"
          repo_url="${repo_url/localhost/host.docker.internal}"
          repo_url="${repo_url/gitea/host.docker.internal}"

          git init .
          git remote add origin "$repo_url"
          git fetch origin "$GITHUB_SHA"
          git checkout --force FETCH_HEAD

          before="${{ github.event.before }}"
          if [ -n "$before" ] && [ "$before" != "0000000000000000000000000000000000000000" ]; then
            git fetch origin "$before" || true
          fi

      - name: Classify changed files
        id: classify
        shell: bash
        run: |
          set -euo pipefail

          if [ "$GITHUB_EVENT_NAME" != "push" ]; then
            echo "app_changed=true" >> "$GITHUB_OUTPUT"
            echo "deploy_allowed=true" >> "$GITHUB_OUTPUT"
            exit 0
          fi

          before="${{ github.event.before }}"
          if [ -n "$before" ] && [ "$before" != "0000000000000000000000000000000000000000" ] && git cat-file -e "$before^{commit}" 2>/dev/null; then
            changed_files="$(git diff --name-only "$before" "$GITHUB_SHA")"
          else
            changed_files="$(git diff-tree --no-commit-id --name-only -r "$GITHUB_SHA")"
          fi

          app_changed=false
          while IFS= read -r path; do
            case "$path" in
              src/*|tests/*|*.sln|*.csproj|Directory.Build.props|Directory.Build.targets|global.json)
                app_changed=true
                ;;
            esac
          done <<EOF
          $changed_files
          EOF

          ticket_key_pattern="$(sed -n 's/.*"ticketKeyPattern"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' .codex/delivery-policy.json | head -n 1 || true)"
          test -n "$ticket_key_pattern"

          commit_message="${{ github.event.head_commit.message }}"
          ticket_pattern="^${ticket_key_pattern}: "
          merge_pr_pattern="^Merge pull request '${ticket_key_pattern}:"
          deploy_allowed=false
          if [[ "$commit_message" =~ $ticket_pattern || "$commit_message" =~ $merge_pr_pattern ]]; then
            deploy_allowed=true
          fi

          echo "app_changed=$app_changed" >> "$GITHUB_OUTPUT"
          echo "deploy_allowed=$deploy_allowed" >> "$GITHUB_OUTPUT"

  package:
    needs: classify-changes
    if: (github.event_name == 'push' && github.ref == 'refs/heads/dev' && needs.classify-changes.outputs.app_changed == 'true' && needs.classify-changes.outputs.deploy_allowed == 'true') || github.event.inputs.environment == 'dev' || github.event.inputs.environment == 'qa'
    runs-on: ubuntu-latest
    container:
      image: mcr.microsoft.com/dotnet/sdk:10.0.300
    steps:
      - name: Checkout
        shell: bash
        run: |
          set -euo pipefail

          repo_url="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}.git"
          repo_url="${repo_url/localhost/host.docker.internal}"
          repo_url="${repo_url/gitea/host.docker.internal}"

          git init .
          git remote add origin "$repo_url"
          git fetch --depth 1 origin "$GITHUB_SHA"
          git checkout --force FETCH_HEAD

      - name: Publish
        run: dotnet publish src/SDDTemplate.Site/SDDTemplate.Site.csproj -c Release -o ./artifacts/app

      - name: Install packaging tools
        run: |
          apt-get update
          apt-get install -y --no-install-recommends zip

      - name: Create deployable ZIP
        run: |
          cd artifacts/app
          zip -r ../app.zip .
          cd ../..
          sha256sum artifacts/app.zip | sed 's#artifacts/app.zip#app.zip#' > artifacts/app.zip.sha256
          git rev-parse HEAD > artifacts/commit.sha

      - name: Upload artifact to Nexus
        run: |
          checksum="$(cut -d ' ' -f1 artifacts/app.zip.sha256)"
          commit_sha="$(cat artifacts/commit.sha)"
          ticket_key_pattern="$(sed -n 's/.*"ticketKeyPattern"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' .codex/delivery-policy.json | head -n 1 || true)"
          test -n "$ticket_key_pattern"

          commit_message="$(git log -1 --pretty=%B)"
          plane_ticket_key="$(printf '%s\n' "$commit_message" | sed -n "s/^\(${ticket_key_pattern}\): .*/\1/p" | head -n 1 || true)"
          if [ -z "$plane_ticket_key" ]; then
            plane_ticket_key="$(printf '%s\n' "$commit_message" | sed -n "s/^Merge pull request '\(${ticket_key_pattern}\):.*/\1/p" | head -n 1 || true)"
          fi
          if [ -z "$plane_ticket_key" ]; then
            plane_ticket_key="manual-dispatch"
          fi

          artifact_url="$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/app.zip"
          cat > artifacts/release.json <<EOF
          {
            "schemaVersion": 1,
            "commitSha": "$commit_sha",
            "checksum": "$checksum",
            "artifactUrl": "$artifact_url",
            "planeTicketKey": "$plane_ticket_key",
            "versionStatus": "unversioned"
          }
          EOF

          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" --upload-file artifacts/app.zip "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/app.zip"
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" --upload-file artifacts/app.zip.sha256 "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/app.zip.sha256"
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" --upload-file artifacts/commit.sha "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/commit.sha"
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" --upload-file artifacts/release.json "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/release.json"
        env:
          NEXUS_URL: ${{ secrets.NEXUS_URL }}
          NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
          NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
          NEXUS_REPOSITORY: ${{ secrets.NEXUS_REPOSITORY }}

  deploy-dev:
    needs:
      - classify-changes
      - package
    runs-on: ubuntu-latest
    if: (github.event_name == 'push' && github.ref == 'refs/heads/dev' && needs.classify-changes.outputs.app_changed == 'true' && needs.classify-changes.outputs.deploy_allowed == 'true') || github.event.inputs.environment == 'dev' || github.event.inputs.environment == 'qa'
    steps:
      - name: Download artifact from Nexus
        run: |
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o app.zip "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/app.zip"
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o app.zip.sha256 "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/app.zip.sha256"
          sha256sum -c app.zip.sha256
        env:
          NEXUS_URL: ${{ secrets.NEXUS_URL }}
          NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
          NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
          NEXUS_REPOSITORY: ${{ secrets.NEXUS_REPOSITORY }}

      - name: Install Azure CLI
        run: curl -sL https://aka.ms/InstallAzureCLIDeb | bash

      - name: Azure login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Deploy DEV package
        run: az webapp deploy --resource-group "$AZURE_DEV_RESOURCE_GROUP" --name "$AZURE_DEV_WEBAPP_NAME" --src-path app.zip --type zip --clean true
        env:
          AZURE_DEV_RESOURCE_GROUP: ${{ secrets.AZURE_DEV_RESOURCE_GROUP }}
          AZURE_DEV_WEBAPP_NAME: ${{ secrets.AZURE_DEV_WEBAPP_NAME }}

      - name: Smoke check DEV
        run: |
          curl --fail --silent --show-error --location "$AZURE_DEV_WEBAPP_URL" -o response.html
          grep -q "<title>SDD Template</title>" response.html
          ! grep -qi "Microsoft Azure" response.html
          curl --fail --silent --show-error --location "$AZURE_DEV_WEBAPP_URL/health" -o health.json
          grep -q '"status":"ok"' health.json
        env:
          AZURE_DEV_WEBAPP_URL: ${{ secrets.AZURE_DEV_WEBAPP_URL }}

  deploy-qa:
    needs:
      - classify-changes
      - deploy-dev
    runs-on: ubuntu-latest
    if: (github.event_name == 'push' && github.ref == 'refs/heads/dev' && needs.classify-changes.outputs.app_changed == 'true' && needs.classify-changes.outputs.deploy_allowed == 'true') || github.event.inputs.environment == 'qa'
    steps:
      - name: Download artifact from Nexus
        run: |
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o app.zip "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/app.zip"
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o app.zip.sha256 "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/app.zip.sha256"
          sha256sum -c app.zip.sha256
        env:
          NEXUS_URL: ${{ secrets.NEXUS_URL }}
          NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
          NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
          NEXUS_REPOSITORY: ${{ secrets.NEXUS_REPOSITORY }}

      - name: Install Azure CLI
        run: curl -sL https://aka.ms/InstallAzureCLIDeb | bash

      - name: Azure login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Deploy QA package
        run: az webapp deploy --resource-group "$AZURE_QA_RESOURCE_GROUP" --name "$AZURE_QA_WEBAPP_NAME" --src-path app.zip --type zip --clean true
        env:
          AZURE_QA_RESOURCE_GROUP: ${{ secrets.AZURE_QA_RESOURCE_GROUP }}
          AZURE_QA_WEBAPP_NAME: ${{ secrets.AZURE_QA_WEBAPP_NAME }}

      - name: Smoke check QA
        run: |
          curl --fail --silent --show-error --location "$AZURE_QA_WEBAPP_URL" -o response.html
          grep -q "<title>SDD Template</title>" response.html
          ! grep -qi "Microsoft Azure" response.html
          curl --fail --silent --show-error --location "$AZURE_QA_WEBAPP_URL/health" -o health.json
          grep -q '"status":"ok"' health.json
        env:
          AZURE_QA_WEBAPP_URL: ${{ secrets.AZURE_QA_WEBAPP_URL }}

  deploy-prod:
    needs: classify-changes
    runs-on: ubuntu-latest
    if: (github.event_name == 'push' && github.ref == 'refs/heads/main' && needs.classify-changes.outputs.app_changed == 'true' && needs.classify-changes.outputs.deploy_allowed == 'true') || (github.event_name == 'workflow_dispatch' && github.event.inputs.environment == 'prod')
    steps:
      - name: Resolve PROD promotion inputs
        shell: bash
        run: |
          set -euo pipefail

          if [ "$GITHUB_EVENT_NAME" = "push" ]; then
            artifact_commit_sha="$GITHUB_SHA"
          else
            artifact_commit_sha="$ARTIFACT_COMMIT_SHA"
            test -n "$RELEASE_VERSION"
            test -n "$SOURCE_RC_VERSION"
          fi

          test -n "$artifact_commit_sha"
          echo "PROD_ARTIFACT_COMMIT_SHA=$artifact_commit_sha" >> "$GITHUB_ENV"
        env:
          ARTIFACT_COMMIT_SHA: ${{ github.event.inputs.artifact_commit_sha }}
          RELEASE_VERSION: ${{ github.event.inputs.release_version }}
          SOURCE_RC_VERSION: ${{ github.event.inputs.source_rc_version }}

      - name: Download artifact from Nexus
        run: |
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o app.zip "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/$PROD_ARTIFACT_COMMIT_SHA/app.zip"
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o app.zip.sha256 "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/$PROD_ARTIFACT_COMMIT_SHA/app.zip.sha256"
          sha256sum -c app.zip.sha256
        env:
          NEXUS_URL: ${{ secrets.NEXUS_URL }}
          NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
          NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
          NEXUS_REPOSITORY: ${{ secrets.NEXUS_REPOSITORY }}

      - name: Install Azure CLI
        run: curl -sL https://aka.ms/InstallAzureCLIDeb | bash

      - name: Azure login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Deploy PROD package
        run: az webapp deploy --resource-group "$AZURE_PROD_RESOURCE_GROUP" --name "$AZURE_PROD_WEBAPP_NAME" --src-path app.zip --type zip --clean true
        env:
          AZURE_PROD_RESOURCE_GROUP: ${{ secrets.AZURE_PROD_RESOURCE_GROUP }}
          AZURE_PROD_WEBAPP_NAME: ${{ secrets.AZURE_PROD_WEBAPP_NAME }}

      - name: Smoke check PROD
        run: |
          curl --fail --silent --show-error --location "$AZURE_PROD_WEBAPP_URL" -o response.html
          grep -q "<title>SDD Template</title>" response.html
          ! grep -qi "Microsoft Azure" response.html
          curl --fail --silent --show-error --location "$AZURE_PROD_WEBAPP_URL/health" -o health.json
          grep -q '"status":"ok"' health.json
        env:
          AZURE_PROD_WEBAPP_URL: ${{ secrets.AZURE_PROD_WEBAPP_URL }}
'@

  Write-TemplateFile $result ".gitea/workflows/README.md" @'
# Gitea Actions Quality Gates

Gitea PR validation is the source of truth. Local hooks are only convenience checks for staged secrets and commit-message shape.

Coverage threshold defaults to `80%` from `.codex/quality.example.json`. Local development may override it with ignored `.codex/quality.local.json`; CI falls back to the tracked example when no local config is present.

The local runner executes PR validation inside a pinned .NET SDK container. Keep checkout and security tools shell-based unless the job container explicitly includes `node`; JavaScript `uses:` actions can fail inside plain SDK containers. Validate runner compatibility after workflow changes:

```powershell
.\.codex\skills\configure-dev-environment\scripts\configure_infra_tools.ps1 -Mode ValidateGiteaActionsRunner
```

That check pulls the configured job image, verifies required tools inside it, and confirms the container can reach local Gitea through `host.docker.internal`.

Required repository secrets:

- `NEXUS_URL` - use `http://host.docker.internal:8088` for local Docker Desktop runner jobs.
- `NEXUS_USERNAME`
- `NEXUS_PASSWORD`
- `NEXUS_REPOSITORY`
- `AZURE_CREDENTIALS`
- `AZURE_DEV_RESOURCE_GROUP`
- `AZURE_DEV_WEBAPP_NAME`
- `AZURE_DEV_WEBAPP_URL`
- `AZURE_QA_RESOURCE_GROUP`
- `AZURE_QA_WEBAPP_NAME`
- `AZURE_QA_WEBAPP_URL`
- `AZURE_PROD_RESOURCE_GROUP`
- `AZURE_PROD_WEBAPP_NAME`
- `AZURE_PROD_WEBAPP_URL`

Push-triggered deployments are ticket-gated by `.codex/delivery-policy.json`. Only commits or merged PR titles that start with the configured ticket key pattern may deploy. `[SDD]`, OpenSpec, chore, and ops-only maintenance changes do not deploy automatically.

DEV and QA deploy only from `dev` when application/test/package source changed. PROD deploys only from `main` when `main` points to the exact QA-approved packaged commit for the same ticket-gated application change. Manual workflow dispatch remains available for explicit DEV/QA/PROD promotion; PROD dispatch must pass an existing `artifact_commit_sha`, `release_version`, and `source_rc_version`. The PROD job downloads the existing Nexus artifact and does not rebuild.

Recommended branch protection:

- Block direct pushes to `dev` and `main`.
- Require pull requests into `dev`.
- Update `main` only after QA passes, preferably by fast-forwarding the tested commit.
- Require the PR validation workflow to pass.
- Require the exact emitted status check context: `PR validation / validate (pull_request)`.
- Require coverage to meet the configured threshold.
- Require review approval or the configured review label.
- Block merge while `needs-changes` is present.

Release flow:

```text
feature branch -> dev -> DEV -> QA -> main -> PROD
```

The package workflow builds and publishes from ticket-gated application changes on `dev`, including a baseline `app/{commitSha}/release.json`. DEV and QA must deploy the same Nexus ZIP artifact for the same commit SHA. PROD must deploy the QA-approved Nexus artifact from an exact-commit `main` promotion or explicit dispatch by commit SHA and must pass both the page smoke check and `/health` check.
'@

  return $result
}

function Invoke-SetQualityConfig {
  $result = New-Result
  $targetRelative = ".codex/quality.local.json"
  $target = Join-RootPath $targetRelative
  if (-not (Test-Path $target)) {
    Copy-LocalFile $result ".codex/quality.example.json" $targetRelative
  }

  $values = Convert-JsonToHashtable $ValuesJson
  if ($values.Count -eq 0) {
    throw "ValuesJson is required for SetQualityConfig when $targetRelative exists."
  }

  if (Test-Path $target) {
    $config = Get-Content -Path $target -Raw | ConvertFrom-Json -Depth 20
  } else {
    $source = Join-RootPath ".codex/quality.example.json"
    if (-not (Test-Path $source)) {
      throw "Missing .codex/quality.example.json. Run -Mode InitQualityGateTemplates first."
    }
    $config = Get-Content -Path $source -Raw | ConvertFrom-Json -Depth 20
  }

  foreach ($key in $values.Keys) {
    $path = @($key -split "\.")
    Set-ObjectValue -Object $config -Path $path -Value $values[$key]
    Add-Item $result "actions" $targetRelative $key "Set confirmed local quality config value."
  }

  $minimum = Get-QualityCoverageMinimumFromObject $config
  if ($null -eq $minimum) {
    throw "coverage.minimumPercent must be an integer between 1 and 100."
  }
  if ($minimum -lt 1 -or $minimum -gt 100) {
    throw "coverage.minimumPercent must be between 1 and 100."
  }

  if (-not $DryRun) {
    $config | ConvertTo-Json -Depth 20 | Set-Content -Path $target -Encoding UTF8
  }
  return $result
}

function Invoke-InitLocalFiles {
  $result = New-Result
  Copy-LocalFile $result ".codex/client-tools.example.json" ".codex/client-tools.local.json"
  Copy-LocalFile $result ".codex/quality.example.json" ".codex/quality.local.json"
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
  foreach ($section in @("plane", "git", "gitea", "nexus", "pr")) {
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
  "AuditQualityGates" { $result = Invoke-AuditQualityGates }
  "ValidateGiteaActionsRunner" { $result = Invoke-ValidateGiteaActionsRunner }
  "InitLocalFiles" { $result = Invoke-InitLocalFiles }
  "InitQualityGateTemplates" { $result = Invoke-InitQualityGateTemplates }
  "SetClientTools" { $result = Invoke-SetClientTools }
  "SetPlaneEnv" { $result = Invoke-SetEnvMode -TargetRelative "infra/plane/variables.env" }
  "SetGiteaRunner" { $result = Invoke-SetEnvMode -TargetRelative "infra/gitea/runner.env" }
  "SetPrometheusAzureTargets" { $result = Invoke-SetPrometheusAzureTargets }
  "SetQualityConfig" { $result = Invoke-SetQualityConfig }
}

$result | ConvertTo-Json -Depth 10
