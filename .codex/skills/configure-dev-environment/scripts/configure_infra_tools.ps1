param(
  [ValidateSet("Audit", "InitLocalFiles", "SetClientTools", "SetPlaneEnv", "SetGiteaRunner", "SetGrafanaAzureMonitor", "AuditQualityGates", "AuditRecommendedTools", "DiscoverProjectGuidance", "AcquireProjectGuidance", "SetRecommendedTools", "MapProjectGuidanceStep", "BuildGiteaActionsImages", "ValidateGiteaActionsRunner", "InitQualityGateTemplates", "SetQualityConfig", "SyncWorktreeLocalConfig", "EnsureDeliveryContext")]
  [string]$Mode = "Audit",

  [string]$Root = (Resolve-Path ".").Path,

  [switch]$DryRun,

  [switch]$AllowAuditWrites,

  [string]$ValuesJson
)

$ErrorActionPreference = "Stop"

function Join-RootPath {
  param([string]$RelativePath)
  return (Join-Path $Root $RelativePath)
}

function Get-RepoRelativePath {
  param([string]$FullPath)

  $rootPath = (Resolve-Path $Root).Path.TrimEnd("\", "/") + [System.IO.Path]::DirectorySeparatorChar
  $targetPath = (Resolve-Path $FullPath).Path
  $rootUri = [System.Uri]::new($rootPath)
  $targetUri = [System.Uri]::new($targetPath)
  return [System.Uri]::UnescapeDataString($rootUri.MakeRelativeUri($targetUri).ToString()).Replace("\", "/")
}

function New-Result {
  return [ordered]@{
    mode = $Mode
    dryRun = [bool]$DryRun
    writeEnabled = (Test-ConfigWritesEnabled)
    actions = @()
    findings = @()
    recommendations = @()
    warnings = @()
  }
}

function Test-ValuesJsonFlag {
  param([string]$Name)

  if ([string]::IsNullOrWhiteSpace($ValuesJson)) { return $false }

  try {
    $data = $ValuesJson | ConvertFrom-Json
    if ($data.PSObject.Properties.Name -notcontains $Name) { return $false }
    return [bool]$data.$Name
  } catch {
    return $false
  }
}

function Test-ConfigWritesEnabled {
  if ($DryRun) { return $false }
  if ($Mode -eq "DiscoverProjectGuidance") { return (Test-ValuesJsonFlag "persistLocal") }
  if ($Mode -like "Audit*" -and -not $AllowAuditWrites) { return $false }
  return $true
}

function Get-GiteaActionsImages {
  return @(
    [ordered]@{
      id = "dotnet-ci"
      image = "agentic/dotnet-ci:10.0.300-tools-1"
      dockerfile = "infra/gitea/actions-images/dotnet-ci/Dockerfile"
      context = "infra/gitea/actions-images/dotnet-ci"
      requiredTools = @("bash", "git", "curl", "tar", "dotnet", "jq", "zip", "gitleaks", "trivy", "az", "node", "npm")
    },
    [ordered]@{
      id = "e2e-ci"
      image = "agentic/e2e-ci:playwright-1.57.0-1"
      dockerfile = "infra/gitea/actions-images/e2e-ci/Dockerfile"
      context = "infra/gitea/actions-images/e2e-ci"
      requiredTools = @("bash", "git", "curl", "node", "npm", "zip")
      extraCheck = "test -d /ms-playwright"
    }
  )
}

function Test-LocalImageTag {
  param([string]$Image)
  return $Image -match "^agentic/"
}

function Assert-NativeCommandSucceeded {
  param([string]$Action)
  if ($LASTEXITCODE -ne 0) {
    throw "$Action failed with exit code $LASTEXITCODE."
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
  $object = $Json | ConvertFrom-Json
  return Convert-ObjectToHashtable $object
}

function Invoke-AzJson {
  param([string[]]$Arguments)

  $output = & az @Arguments --output json 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "Azure CLI command failed: az $($Arguments -join ' ')`n$output"
  }

  $text = ($output | Out-String).Trim()
  if ([string]::IsNullOrWhiteSpace($text)) { return $null }
  $jsonStart = $text.IndexOf("{")
  $arrayStart = $text.IndexOf("[")
  $starts = @($jsonStart, $arrayStart) | Where-Object { $_ -ge 0 } | Sort-Object
  if ($starts.Count -gt 0 -and $starts[0] -gt 0) {
    $text = $text.Substring($starts[0])
  }
  return $text | ConvertFrom-Json
}

function Invoke-AzTsv {
  param([string[]]$Arguments)

  $output = & az @Arguments --output tsv 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "Azure CLI command failed: az $($Arguments -join ' ')`n$output"
  }

  return ($output | Out-String).Trim()
}

function ConvertTo-Array {
  param($Value)

  if ($null -eq $Value) { return @() }
  if ($Value -is [array]) { return @($Value) }
  return @($Value)
}

function Get-AgenticEnvironmentResourceGroups {
  return @(
    [ordered]@{ env = "dev"; resourceGroup = "rg-agentic-dev" },
    [ordered]@{ env = "qa"; resourceGroup = "rg-agentic-qa" },
    [ordered]@{ env = "prod"; resourceGroup = "rg-agentic-prod" }
  )
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

function Get-FileSha256 {
  param([string]$Path)

  $stream = [System.IO.File]::OpenRead($Path)
  try {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
      $hash = $sha.ComputeHash($stream)
      return ([System.BitConverter]::ToString($hash)).Replace("-", "")
    }
    finally {
      $sha.Dispose()
    }
  }
  finally {
    $stream.Dispose()
  }
}

function Get-WorktreeLocalConfigFiles {
  return @(
    [pscustomobject]@{ relativePath = ".codex/client-tools.local.json"; required = $true },
    [pscustomobject]@{ relativePath = ".codex/quality.local.json"; required = $true },
    [pscustomobject]@{ relativePath = ".codex/tool-recommendations.local.json"; required = $false }
  )
}

function Resolve-AnyPath {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $Root $Path))
}

function Add-UniquePath {
  param(
    [System.Collections.Generic.List[string]]$Paths,
    [string]$Path
  )

  $fullPath = Resolve-AnyPath $Path
  if ([string]::IsNullOrWhiteSpace($fullPath)) { return }

  foreach ($existing in $Paths) {
    if ([string]::Equals($existing, $fullPath, [System.StringComparison]::OrdinalIgnoreCase)) {
      return
    }
  }
  $Paths.Add($fullPath)
}

function Get-ValuesJsonWorktreePaths {
  $paths = [System.Collections.Generic.List[string]]::new()
  if ([string]::IsNullOrWhiteSpace($ValuesJson)) { return @($paths) }

  try {
    $values = $ValuesJson | ConvertFrom-Json
  } catch {
    return @($paths)
  }

  if ($values.PSObject.Properties.Name -contains "worktreePath") {
    Add-UniquePath $paths ([string]$values.worktreePath)
  }
  if ($values.PSObject.Properties.Name -contains "worktreePaths") {
    foreach ($path in @($values.worktreePaths)) {
      Add-UniquePath $paths ([string]$path)
    }
  }
  return @($paths)
}

function Get-RecordedParallelWorktreePaths {
  $paths = [System.Collections.Generic.List[string]]::new()
  $parallelPath = Join-RootPath ".codex/parallel-delivery.local.json"
  if (-not (Test-Path $parallelPath)) { return @($paths) }

  try {
    $state = Get-Content -Path $parallelPath -Raw | ConvertFrom-Json
  } catch {
    return @($paths)
  }

  foreach ($ticket in @($state.tickets)) {
    if ($null -eq $ticket) { continue }
    if ($ticket.PSObject.Properties.Name -notcontains "worktreePath") { continue }
    Add-UniquePath $paths ([string]$ticket.worktreePath)
  }
  return @($paths)
}

function Get-GitWorktreePaths {
  $paths = [System.Collections.Generic.List[string]]::new()
  try {
    $lines = @(& git -C $Root worktree list --porcelain 2>$null)
  } catch {
    return @($paths)
  }

  $rootPath = [System.IO.Path]::GetFullPath($Root)
  foreach ($line in $lines) {
    if ($line -notmatch "^worktree\s+(.+)$") { continue }
    $worktreePath = [System.IO.Path]::GetFullPath($Matches[1])
    if ([string]::Equals($worktreePath, $rootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
      continue
    }
    Add-UniquePath $paths $worktreePath
  }
  return @($paths)
}

function Get-KnownWorktreePaths {
  $paths = [System.Collections.Generic.List[string]]::new()
  foreach ($path in @(Get-GitWorktreePaths)) {
    Add-UniquePath $paths $path
  }
  foreach ($path in @(Get-RecordedParallelWorktreePaths)) {
    Add-UniquePath $paths $path
  }
  return @($paths)
}

function Get-SyncTargetWorktreePaths {
  $explicit = @(Get-ValuesJsonWorktreePaths)
  if ($explicit.Count -gt 0) { return $explicit }
  return @(Get-KnownWorktreePaths)
}

function Get-CurrentGitBranch {
  try {
    $branch = (& git -C $Root branch --show-current 2>$null)
    if ([string]::IsNullOrWhiteSpace($branch)) { return $null }
    return $branch.Trim()
  } catch {
    return $null
  }
}

function Get-InferredOpenSpecChange {
  param([string]$Branch)

  if ([string]::IsNullOrWhiteSpace($Branch)) { return $null }
  return $Branch.Replace("/", "-")
}

function Get-DisplayPath {
  param([string]$FullPath)

  try {
    return Get-RepoRelativePath $FullPath
  } catch {
    return $FullPath
  }
}

function Add-WorktreeLocalConfigAuditFindings {
  param($Result)

  foreach ($worktreePath in @(Get-KnownWorktreePaths)) {
    $displayPath = Get-DisplayPath $worktreePath
    if (-not (Test-Path -LiteralPath $worktreePath -PathType Container)) {
      Add-Item $Result "findings" $displayPath "worktreePath" "Recorded ticket worktree path does not exist; repair the parallel delivery index before routing this ticket." "warning"
      continue
    }

    foreach ($file in @(Get-WorktreeLocalConfigFiles)) {
      $relativePath = [string]$file.relativePath
      $sourcePath = Join-RootPath $relativePath
      $targetPath = Join-Path $worktreePath $relativePath
      if (-not (Test-Path $sourcePath) -and -not [bool]$file.required) { continue }

      if (-not (Test-Path -LiteralPath $targetPath)) {
        $severity = if ([bool]$file.required) { "error" } else { "info" }
        $message = if ([bool]$file.required) {
          "Ticket worktree is missing required local runtime file '$relativePath'. Run SyncWorktreeLocalConfig from the coordinator checkout before routing child skills."
        } else {
          "Ticket worktree is missing optional local runtime file '$relativePath'. SyncWorktreeLocalConfig will copy it when present in the coordinator checkout."
        }
        Add-Item $Result "findings" $displayPath $relativePath $message $severity
      }
    }
  }
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

  $usesRepoOwnedToolImage = $workflow -match "agentic/(dotnet-ci|e2e-ci):"
  if ($workflow -match "zip\s+-r" -and $workflow -notmatch "apt-get install .*zip" -and -not $usesRepoOwnedToolImage) {
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
    foreach ($expected in @("quality_projects", 'dotnet restore "$project"', 'dotnet format "$project"', 'dotnet build "$project"', "dotnet test tests/SDDTemplate.Site.Tests/SDDTemplate.Site.Tests.csproj", 'dotnet list "$project" package', "ReadCoverageThreshold", "ReadCoberturaLineRate", "gitleaks", "trivy")) {
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
    foreach ($expected in @("NEXUS_URL", "NEXUS_USERNAME", "NEXUS_PASSWORD", "az webapp deploy", "az webapp config appsettings set", "az webapp config appsettings list", "classify-changes", "app_changed", "deploy_allowed", ".codex/delivery-policy.json", "ticketKeyPattern", "BASH_REMATCH", "refs/heads/dev", "refs/heads/main", "qa/**", "deploy-qa", "e2e-qa-branch", "deploy-prod", "artifact_commit_sha", "PROD_ARTIFACT_COMMIT_SHA", "release_version", "source_rc_version", "release.json", "CreateReleaseManifest", "ValidateReleaseManifest", "BuildDeploymentConfig", "infra/deployment/apps.json", "infra/deployment/configuration.json", "deployable-apps.json", "deployment-config.json", "app/qa-approved/latest.json", "const apiBaseUrl", "Access-Control-Allow-Origin", "AZURE_QA_RESOURCE_GROUP", "AZURE_QA_SITE_APP_NAME", "AZURE_QA_SITE_APP_URL", "AZURE_QA_API_APP_NAME", "AZURE_QA_API_APP_URL", "E2E_SITE_URL", "E2E_API_URL", "E2E_ARTIFACT_COMMIT_SHA", "qa-e2e-evidence.zip", "AZURE_PROD_RESOURCE_GROUP", "AZURE_PROD_SITE_APP_NAME", "AZURE_PROD_SITE_APP_URL", "AZURE_PROD_API_APP_NAME", "AZURE_PROD_API_APP_URL", "healthPath", '${app_url}${health_path}')) {
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
    if (-not (Test-FileContains $releaseWorkflow "jq -r '\.apps\[\] \| \[\.appId, \.projectPath, \.artifactName\] \| @tsv'")) {
      Add-Item $Result "findings" $releaseWorkflow "topology.publish" "Package/deploy workflow should publish deployable apps from infra/deployment/apps.json." "warning"
    }
    if (-not (Test-FileContains $releaseWorkflow "projectPath must be under src/")) {
      Add-Item $Result "findings" $releaseWorkflow "topology.publish.source-root" "Package/deploy workflow should reject deployable project paths outside application source roots." "warning"
    }
  }

  $deliveryPolicy = ".codex/delivery-policy.json"
  if (-not (Test-Path (Join-RootPath $deliveryPolicy))) {
    Add-Item $Result "findings" $deliveryPolicy "ticketKeyPattern" "Missing delivery policy used by commit hooks and deployment gating." "warning"
  } elseif (-not (Test-FileContains $deliveryPolicy '"ticketKeyPattern"\s*:')) {
    Add-Item $Result "findings" $deliveryPolicy "ticketKeyPattern" "Delivery policy must define ticketKeyPattern for deployment gating." "warning"
  } else {
    foreach ($expectedPolicyKey in @(
      '"agentOptimization"\s*:',
      '"maxAutonomousIterations"\s*:',
      '"maxToolRetries"\s*:',
      '"promptCache"\s*:',
      '"telemetry"\s*:',
      '"workflowEvals"\s*:',
      '"cachedTokens"',
      '"requireEvalEvidenceBeforeNewAgentRole"\s*:'
    )) {
      if (-not (Test-FileContains $deliveryPolicy $expectedPolicyKey)) {
        Add-Item $Result "findings" $deliveryPolicy "agentOptimization" "Delivery policy should include agentOptimization defaults for retries, prompt cache, telemetry, and workflow eval paths." "warning"
        break
      }
    }
  }

  $gitignore = ".gitignore"
  if (-not (Test-Path (Join-RootPath $gitignore))) {
    Add-Item $Result "findings" $gitignore ".codex/delivery-context.local.json" "Missing .gitignore; local ticket context lock must not be committed." "warning"
  } elseif (-not (Test-FileContains $gitignore "\.codex/delivery-context\.local\.json")) {
    Add-Item $Result "findings" $gitignore ".codex/delivery-context.local.json" "Local ticket context lock must be ignored so automatic delivery stays ticket-scoped without committing runtime state." "warning"
  }
  if ((Test-Path (Join-RootPath $gitignore)) -and -not (Test-FileContains $gitignore "\.codex/parallel-delivery\.local\.json")) {
    Add-Item $Result "findings" $gitignore ".codex/parallel-delivery.local.json" "Parallel delivery runtime state must be ignored so active ticket worktree assignments and lane ownership are not committed." "warning"
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

  foreach ($qualityFile in @(".editorconfig", ".gitattributes", "Directory.Build.props", "lefthook.yml")) {
    if (-not (Test-Path (Join-RootPath $qualityFile))) {
      Add-Item $Result "findings" $qualityFile "" "Missing quality gate template." "warning"
    }
  }
  if ((Test-Path (Join-RootPath ".gitattributes")) -and -not (Test-FileContains ".gitattributes" "\*\s+text=auto\s+eol=lf")) {
    Add-Item $Result "findings" ".gitattributes" "text.eol" "Missing repository LF normalization rule; Windows core.autocrlf checkouts can break dotnet format end_of_line checks." "warning"
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

  foreach ($imageInfo in Get-GiteaActionsImages) {
    if (-not (Test-Path (Join-RootPath $imageInfo.dockerfile))) {
      Add-Item $Result "findings" $imageInfo.dockerfile "" "Missing repo-owned Gitea Actions image Dockerfile for $($imageInfo.id)." "warning" "pre-start"
    }
  }

  $prWorkflow = ".gitea/workflows/pr-validation.yml"
  if (Test-Path (Join-RootPath $prWorkflow)) {
    $prWorkflowContent = Get-Content -Path (Join-RootPath $prWorkflow) -Raw
    if ($prWorkflowContent -notmatch [regex]::Escape("agentic/dotnet-ci:10.0.300-tools-1")) {
      Add-Item $Result "findings" $prWorkflow "container.image" "PR validation should use the pinned repo-owned dotnet-ci image." "warning"
    }
    foreach ($installPattern in @("Install Gitleaks", "Install Trivy")) {
      if ($prWorkflowContent -match [regex]::Escape($installPattern)) {
        Add-Item $Result "findings" $prWorkflow $installPattern "PR validation still installs tools at run time; move required tools into dotnet-ci." "warning"
      }
    }
  }

  $deployWorkflow = ".gitea/workflows/package-deploy.yml"
  if (Test-Path (Join-RootPath $deployWorkflow)) {
    $deployWorkflowContent = Get-Content -Path (Join-RootPath $deployWorkflow) -Raw
    foreach ($image in @("agentic/dotnet-ci:10.0.300-tools-1", "agentic/e2e-ci:playwright-1.57.0-1")) {
      if ($deployWorkflowContent -notmatch [regex]::Escape($image)) {
        Add-Item $Result "findings" $deployWorkflow "container.image" "Package/deploy workflow should use pinned image $image where relevant." "warning"
      }
    }
    foreach ($installPattern in @("Install packaging tools", "Install deployment tools", "Install Azure CLI", "npm run install:browsers", "deb.nodesource.com/setup_22.x")) {
      if ($deployWorkflowContent -match [regex]::Escape($installPattern)) {
        Add-Item $Result "findings" $deployWorkflow $installPattern "Package/deploy workflow still installs tools at run time; move required tools into repo-owned CI images." "warning"
      }
    }
  }

  foreach ($composeFile in Get-ChildItem -Path (Join-RootPath "infra") -Filter "compose.yml" -Recurse -ErrorAction SilentlyContinue) {
    $relativeCompose = Get-RepoRelativePath $composeFile.FullName
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
  $topologyManifest = "infra/deployment/apps.json"
  $configurationManifest = "infra/deployment/configuration.json"
  if (-not (Test-Path (Join-RootPath $topologyManifest))) {
    Add-Item $Result "findings" $topologyManifest "" "Missing deployable app topology manifest used by Azure Bicep and package/deploy workflow." "warning"
  } else {
    foreach ($expectedTopology in @('"appId"\s*:\s*"site"', '"appId"\s*:\s*"api"', '"projectPath"\s*:', '"artifactName"\s*:', '"healthPath"\s*:')) {
      if (-not (Test-FileContains $topologyManifest $expectedTopology)) {
        Add-Item $Result "findings" $topologyManifest $expectedTopology "Deployable app topology manifest is missing an expected app or field." "warning"
      }
    }
    try {
      $topology = Get-Content -Path (Join-RootPath $topologyManifest) -Raw | ConvertFrom-Json
      foreach ($app in @($topology.apps)) {
        $projectPath = [string]$app.projectPath
        if ([string]::IsNullOrWhiteSpace($projectPath) -or -not $projectPath.StartsWith("src/")) {
          Add-Item $Result "findings" $topologyManifest "projectPath" "Deployable app '$($app.appId)' projectPath must be under src/ and must not target SDD, infrastructure, OpenSpec, agent, workflow, or tool projects." "warning"
        }
      }
    } catch {
      Add-Item $Result "findings" $topologyManifest "" "Deployable app topology manifest could not be parsed as JSON." "warning"
    }
  }
  if (-not (Test-Path (Join-RootPath $configurationManifest))) {
    Add-Item $Result "findings" $configurationManifest "" "Missing deployable configuration mapping manifest used to build deployment-config.json." "warning"
  } else {
    foreach ($expectedConfigurationMapping in @('"settings"\s*:', '"source"\s*:', '"required"\s*:', '"secret"\s*:')) {
      if (-not (Test-FileContains $configurationManifest $expectedConfigurationMapping)) {
        Add-Item $Result "findings" $configurationManifest $expectedConfigurationMapping "Deployable configuration manifest is missing expected mapping fields." "warning"
      }
    }
  }
  if (Test-FileContains $azureMain "DOTNETCORE\|8\.0") {
    Add-Item $Result "findings" $azureMain "webRuntimeStack/apiRuntimeStack" "Azure runtime defaults still target DOTNETCORE|8.0; align with .NET 10 app or use a self-contained deployment strategy." "warning"
  }
  foreach ($expectedAzureMapping in @("deployableApps", "Microsoft.Web/sites/config", "Api__BaseUrl", "Cors__AllowedOrigins__0", "ConnectionStrings__ClientsDb", "output apps array")) {
    if (-not (Test-FileContains $azureMain ([regex]::Escape($expectedAzureMapping)))) {
      Add-Item $Result "findings" $azureMain $expectedAzureMapping "Azure Bicep should map topology apps and appsettings-derived App Service settings." "warning"
    }
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
    foreach ($secret in @("NEXUS_URL", "NEXUS_USERNAME", "NEXUS_PASSWORD", "NEXUS_REPOSITORY", "AZURE_CREDENTIALS", "AZURE_DEV_RESOURCE_GROUP", "AZURE_DEV_SITE_APP_NAME", "AZURE_DEV_SITE_APP_URL", "AZURE_DEV_API_APP_NAME", "AZURE_DEV_API_APP_URL", "AZURE_QA_RESOURCE_GROUP", "AZURE_QA_SITE_APP_NAME", "AZURE_QA_SITE_APP_URL", "AZURE_QA_API_APP_NAME", "AZURE_QA_API_APP_URL", "AZURE_PROD_RESOURCE_GROUP", "AZURE_PROD_SITE_APP_NAME", "AZURE_PROD_SITE_APP_URL", "AZURE_PROD_API_APP_NAME", "AZURE_PROD_API_APP_URL")) {
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
    "AZURE_DEV_SITE_APP_NAME",
    "AZURE_DEV_SITE_APP_URL",
    "AZURE_DEV_API_APP_NAME",
    "AZURE_DEV_API_APP_URL",
    "AZURE_QA_RESOURCE_GROUP",
    "AZURE_QA_SITE_APP_NAME",
    "AZURE_QA_SITE_APP_URL",
    "AZURE_QA_API_APP_NAME",
    "AZURE_QA_API_APP_URL",
    "AZURE_PROD_RESOURCE_GROUP",
    "AZURE_PROD_SITE_APP_NAME",
    "AZURE_PROD_SITE_APP_URL",
    "AZURE_PROD_API_APP_NAME",
    "AZURE_PROD_API_APP_URL"
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
  $message = if (Test-ConfigWritesEnabled) {
    "Set inferred local client tool value."
  } else {
    "Would set inferred local client tool value; audit modes are read-only unless -AllowAuditWrites is supplied."
  }
  Add-Item $Result "actions" ".codex/client-tools.local.json" ($Path -join ".") $message
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

function Test-AnyRepoFileContains {
  param(
    [string[]]$RelativeRoots,
    [string[]]$Filters,
    [string]$Pattern
  )

  foreach ($relativeRoot in $RelativeRoots) {
    $path = Join-RootPath $relativeRoot
    if (-not (Test-Path $path)) { continue }

    foreach ($filter in $Filters) {
      foreach ($file in Get-ChildItem -Path $path -Recurse -File -Filter $filter -ErrorAction SilentlyContinue) {
        try {
          $content = Get-Content -Path $file.FullName -Raw -ErrorAction Stop
          if ($content -match $Pattern) { return $true }
        } catch {
          continue
        }
      }
    }
  }

  return $false
}

function Test-RecommendationMatchesStack {
  param(
    $Recommendation,
    [string[]]$DetectedTags
  )

  $requires = @($Recommendation.requires)
  if ($requires.Count -eq 0) { return $true }

  foreach ($tag in $requires) {
    if ($DetectedTags -notcontains $tag) { return $false }
  }
  return $true
}

function Get-ToolRecommendationCatalog {
  $catalogPath = Join-RootPath ".codex/tool-recommendations.example.json"
  if (-not (Test-Path $catalogPath)) {
    throw "Missing .codex/tool-recommendations.example.json."
  }

  return Get-Content -Path $catalogPath -Raw | ConvertFrom-Json
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
    if (Test-ConfigWritesEnabled) {
      Copy-Item -Path $source -Destination $target
    }
  }

  if (-not (Test-Path $target)) { return }
  try {
    $client = Get-Content -Path $target -Raw | ConvertFrom-Json
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

  Set-InferredClientValue $Result $client @("parallelDelivery", "enabled") $false
  Set-InferredClientValue $Result $client @("parallelDelivery", "maxActiveTickets") 2
  Set-InferredClientValue $Result $client @("parallelDelivery", "worktreeRoot") "../ticket-worktrees"
  Set-InferredClientValue $Result $client @("parallelDelivery", "deploymentLanePolicy") "serialized"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "coordinator", "model") "inherit"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "coordinator", "reasoningEffort") "medium"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "pipelineStatus", "model") "gpt-5.4-mini"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "pipelineStatus", "reasoningEffort") "low"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "ticketStarter", "model") "gpt-5.4-mini"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "ticketStarter", "reasoningEffort") "medium"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "implementation", "model") "gpt-5.3-codex"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "implementation", "reasoningEffort") "medium"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "prReview", "model") "gpt-5.4"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "prReview", "reasoningEffort") "high"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "postMergeDeploy", "model") "gpt-5.4-mini"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "postMergeDeploy", "reasoningEffort") "medium"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "deployToQa", "model") "gpt-5.4-mini"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "deployToQa", "reasoningEffort") "medium"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "e2eQa", "model") "gpt-5.4"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "e2eQa", "reasoningEffort") "medium"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "deployToProd", "model") "gpt-5.4"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "deployToProd", "reasoningEffort") "high"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "fileQaBug", "model") "gpt-5.4"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "fileQaBug", "reasoningEffort") "medium"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "rollbackProd", "model") "gpt-5.4"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "rollbackProd", "reasoningEffort") "high"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "hotfixProd", "model") "gpt-5.3-codex"
  Set-InferredClientValue $Result $client @("parallelDelivery", "agentModelPolicy", "hotfixProd", "reasoningEffort") "high"
  Set-InferredClientValue $Result $client @("recommendedTools", "enabled") $true
  Set-InferredClientValue $Result $client @("recommendedTools", "mode") "guided-manual"
  Set-InferredClientValue $Result $client @("recommendedTools", "accepted") @()
  Set-InferredClientValue $Result $client @("recommendedTools", "dismissed") @()

  if (Test-ConfigWritesEnabled) {
    $client | ConvertTo-Json -Depth 20 | Set-Content -Path $target -Encoding UTF8
  }
}

function Add-Recommendation {
  param(
    $Result,
    $Recommendation
  )

  $Result["recommendations"] += $Recommendation
}

$projectGuidanceDiscoveryScript = Join-Path $PSScriptRoot "..\..\project-guidance-discover\scripts\project_guidance_discovery.ps1"
. (Resolve-Path $projectGuidanceDiscoveryScript).Path

function Get-RecommendedToolsDecisionState {
  $state = [ordered]@{
    enabled = $true
    accepted = @()
    dismissed = @()
  }

  $clientPath = Join-RootPath ".codex/client-tools.local.json"
  if (-not (Test-Path $clientPath)) { return $state }

  try {
    $client = Get-Content -Path $clientPath -Raw | ConvertFrom-Json
    if ($null -eq $client.recommendedTools) { return $state }

    if ($client.recommendedTools.enabled -eq $false) { $state.enabled = $false }
    $state.accepted = @($client.recommendedTools.accepted)
    $state.dismissed = @($client.recommendedTools.dismissed)
  } catch {
    return $state
  }

  return $state
}

function ConvertTo-CatalogRecommendation {
  param(
    $Entry,
    [string[]]$Accepted
  )

  $recommendation = [ordered]@{
    id = $Entry.id
    name = $Entry.name
    type = $Entry.type
    purpose = $Entry.purpose
    installMethod = $Entry.installMethod
    source = $Entry.source
    target = $Entry.target
    validation = $Entry.validation
    accepted = ($Accepted -contains $Entry.id)
  }

  foreach ($optionalField in @("sourceKind", "requires", "researchTopics", "officialSources", "searchQueries", "notes")) {
    if ($Entry.PSObject.Properties.Name -contains $optionalField) {
      $recommendation[$optionalField] = $Entry.$optionalField
    }
  }

  return $recommendation
}

function Get-CanonicalWorkflowSteps {
  return @(
    "config-infra",
    "first-ticket-setup",
    "planning",
    "implementation",
    "pr-review",
    "review-feedback",
    "post-merge-deploy",
    "e2e-qa",
    "prod-promotion",
    "rollback",
    "hotfix",
    "retrospective"
  )
}

function Get-DefaultPrimarySkillsForWorkflowStep {
  param([string]$WorkflowStep)

  switch ($WorkflowStep) {
    "config-infra" { return @("configure-dev-environment") }
    "first-ticket-setup" { return @("plane-start-ticket") }
    "planning" { return @("openspec-propose", "openspec-explore") }
    "implementation" { return @("implement-ticket") }
    "pr-review" { return @("gitea-pr-review-agent") }
    "review-feedback" { return @("pr-review-feedback-loop") }
    "post-merge-deploy" { return @("post-merge-deploy", "deploy-to-qa") }
    "e2e-qa" { return @("test-e2e") }
    "prod-promotion" { return @("deploy-to-prod") }
    "rollback" { return @("rollback-prod") }
    "hotfix" { return @("hotfix-prod") }
    "retrospective" { return @("delivery-retrospective-audit") }
    default { return @() }
  }
}

function Get-DefaultSupportingSkillsForWorkflowStep {
  param([string]$WorkflowStep)

  switch ($WorkflowStep) {
    "config-infra" { return @("project-guidance-discover", "project-guidance-mapper") }
    "first-ticket-setup" { return @("configure-dev-environment", "project-guidance-discover", "project-guidance-mapper") }
    "planning" { return @("aspnet-core", "plan-ui-change", "dotnet-webapi", "security-best-practices") }
    "implementation" { return @("aspnet-core", "plan-ui-change", "dotnet-webapi", "security-best-practices", "assertion-quality") }
    "pr-review" { return @("aspnet-core", "dotnet-webapi", "security-best-practices", "assertion-quality", "playwright") }
    "review-feedback" { return @("aspnet-core", "plan-ui-change", "dotnet-webapi", "security-best-practices", "assertion-quality") }
    "post-merge-deploy" { return @("configure-artifact-delivery", "configure-azure-environments", "configure-observability") }
    "e2e-qa" { return @("frontend-testing-debugging", "playwright", "assertion-quality") }
    "prod-promotion" { return @("configure-artifact-delivery", "configure-azure-environments", "configure-observability") }
    "rollback" { return @("configure-artifact-delivery", "configure-azure-environments", "security-best-practices") }
    "hotfix" { return @("security-best-practices", "assertion-quality", "aspnet-core") }
    "retrospective" { return @("project-guidance-discover", "project-guidance-mapper", "configure-dev-environment") }
    default { return @() }
  }
}

function Get-DefaultRecommendationIdsForWorkflowStep {
  param([string]$WorkflowStep)

  switch ($WorkflowStep) {
    "config-infra" { return @("project-guidance-search-plan") }
    "first-ticket-setup" { return @("project-guidance-search-plan") }
    "planning" { return @("openai-aspnet-core-skill", "dotnet-blazor-plan-ui-change-skill", "dotnet-webapi-skill", "openai-security-best-practices-skill", "clean-code-practice-guidance", "modern-dotnet-architecture-guidance") }
    "implementation" { return @("openai-aspnet-core-skill", "dotnet-blazor-plan-ui-change-skill", "dotnet-webapi-skill", "openai-security-best-practices-skill", "dotnet-assertion-quality-skill", "clean-code-practice-guidance", "modern-dotnet-architecture-guidance", "rest-api-design-practice-guidance") }
    "pr-review" { return @("gitea-pr-review-agent-skill", "openai-aspnet-core-skill", "dotnet-webapi-skill", "openai-security-best-practices-skill", "dotnet-assertion-quality-skill", "pr-review-practice-guidance") }
    "review-feedback" { return @("openai-aspnet-core-skill", "dotnet-blazor-plan-ui-change-skill", "dotnet-webapi-skill", "openai-security-best-practices-skill", "dotnet-assertion-quality-skill", "clean-code-practice-guidance") }
    "post-merge-deploy" { return @("nexus-artifact-api-guidance", "azure-app-service-zip-deploy-guidance", "azure-monitor-log-analytics-guidance", "grafana-provisioning-guidance", "release-practice-guidance") }
    "e2e-qa" { return @("browser-e2e-qa-plugin", "playwright-frontend-testing-skill", "openai-playwright-skill", "dotnet-assertion-quality-skill", "qa-automation-practice-guidance") }
    "prod-promotion" { return @("nexus-artifact-api-guidance", "azure-app-service-zip-deploy-guidance", "azure-monitor-log-analytics-guidance", "grafana-provisioning-guidance", "release-practice-guidance") }
    "rollback" { return @("nexus-artifact-api-guidance", "azure-app-service-zip-deploy-guidance", "azure-monitor-log-analytics-guidance", "grafana-provisioning-guidance", "rollback-practice-guidance") }
    "hotfix" { return @("openai-security-best-practices-skill", "dotnet-assertion-quality-skill", "release-practice-guidance", "rollback-practice-guidance") }
    "retrospective" { return @("project-guidance-search-plan", "clean-code-practice-guidance", "qa-automation-practice-guidance", "pr-review-practice-guidance") }
    default { return @() }
  }
}

function Get-ExistingRecommendationStepUsage {
  param($Existing)

  $usage = @{}
  if ($null -eq $Existing) { return $usage }

  foreach ($recommendation in @($Existing.recommendations)) {
    if ($null -eq $recommendation.id) { continue }
    if ($recommendation.PSObject.Properties.Name -notcontains "usedInSteps") { continue }
    $usage[[string]$recommendation.id] = @($recommendation.usedInSteps)
  }

  if ($Existing.PSObject.Properties.Name -contains "workflowStepMappings") {
    foreach ($mapping in @($Existing.workflowStepMappings)) {
      if ($null -eq $mapping.workflowStep) { continue }
      foreach ($id in @($mapping.recommendationIds)) {
        if ([string]::IsNullOrWhiteSpace([string]$id)) { continue }
        $current = if ($usage.ContainsKey([string]$id)) { @($usage[[string]$id]) } else { @() }
        $usage[[string]$id] = @(@($current) + @([string]$mapping.workflowStep) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
      }
    }
  }

  return $usage
}

function Add-UsedInStepsToRecommendation {
  param(
    [hashtable]$Recommendation,
    [hashtable]$Usage
  )

  $id = [string]$Recommendation["id"]
  $steps = if ($Usage.ContainsKey($id)) { @($Usage[$id]) } else { @() }
  $Recommendation["usedInSteps"] = @($steps | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
  return $Recommendation
}

function Get-RecommendationSearchText {
  param($Recommendation)

  $parts = @(
    $Recommendation.id,
    $Recommendation.name,
    $Recommendation.type,
    $Recommendation.purpose,
    $Recommendation.notes,
    @($Recommendation.requires) -join " ",
    @($Recommendation.researchTopics) -join " ",
    @($Recommendation.tags) -join " "
  )

  return (($parts | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }) -join " ").ToLowerInvariant()
}

function Test-RecommendationFitsWorkflowStep {
  param(
    $Recommendation,
    [string]$WorkflowStep
  )

  $text = Get-RecommendationSearchText $Recommendation
  switch ($WorkflowStep) {
    "config-infra" { return $text -match "guidance-search|tool|mcp|plugin|delivery|environment|configure" }
    "first-ticket-setup" { return $text -match "guidance-search|ticket|stack|architecture|tool|context" }
    "planning" { return $text -match "architecture|clean|api|rest|ui|blazor|security|standard|practice" }
    "implementation" { return $text -match "aspnet|blazor|api|rest|security|clean|architecture|assertion|test|code" }
    "pr-review" { return $text -match "review|security|assertion|api|rest|clean|architecture|gitea" }
    "review-feedback" { return $text -match "feedback|review|security|assertion|api|rest|clean|architecture" }
    "post-merge-deploy" { return $text -match "nexus|azure|deploy|release|monitor|log analytics|grafana|observability" }
    "e2e-qa" { return $text -match "qa|e2e|browser|playwright|test|assertion" }
    "prod-promotion" { return $text -match "prod|release|nexus|azure|deploy|monitor|log analytics|grafana|observability" }
    "rollback" { return $text -match "rollback|nexus|azure|prod|release|artifact|monitoring" }
    "hotfix" { return $text -match "hotfix|security|test|assertion|release|rollback|api" }
    "retrospective" { return $text -match "practice|standard|quality|review|guidance-search|clean|qa" }
    default { return $false }
  }
}

function Get-ExistingProjectGuidanceLocalState {
  $path = Join-RootPath ".codex/tool-recommendations.local.json"
  if (-not (Test-Path $path)) { return $null }

  try {
    return Get-Content -Path $path -Raw | ConvertFrom-Json
  } catch {
    return $null
  }
}

function New-ProjectGuidanceLocalState {
  param(
    [string[]]$Accepted,
    [string[]]$Dismissed,
    [object[]]$UserAddedRequestedGuidance = @(),
    [switch]$Confirmed
  )

  $detectedTags = Get-DetectedStackTags
  $report = Get-ProjectGuidanceDiscoveryReport -Accepted $Accepted -Dismissed $Dismissed -UserAddedRequestedGuidance $UserAddedRequestedGuidance -Confirmed:($Confirmed)
  $catalog = Get-ToolRecommendationCatalog
  $recommendations = @()
  $existing = Get-ExistingProjectGuidanceLocalState
  $stepUsage = Get-ExistingRecommendationStepUsage $existing

  if ($report.researchTopics.Count -gt 0) {
    $recommendations += [ordered]@{
      id = "project-guidance-search-plan"
      name = "Project guidance search plan"
      type = "guidance-search-plan"
      purpose = "Research skills, tools, references, practices, standards, MCPs, and plugins from detected project technologies, environments, tests, security gates, and code standards before proposing local guidance updates."
      installMethod = "research-then-manual-copy"
      accepted = $false
      detected = $true
      requiresUserConfirmation = $true
      sourceDiscovery = "official-first-internet-search"
      discoverySourcePriority = Get-ProjectGuidanceDiscoverySourcePriority
      discoverySourceNotes = Get-ProjectGuidanceDiscoverySourceNotes
      topics = @($report.researchTopics)
      nextStep = "Use project-guidance-discover to search OpenAI official catalogs/docs, official tool repositories/docs, technology-owner sources, skills.sh/skills or marketplace repository leads, and trusted public sources; show suggested missing skills and guidance; ask for additional desired items; then pass confirmed skill items to project-guidance-acquire."
    }
  }

  $recommendations += @($report.suggestedMissingSkills)
  $recommendations += @($report.suggestedPresentSkills)
  $recommendations += @($report.suggestedGuidance)
  $recommendations += @($report.userAddedRequestedGuidance)

  foreach ($entry in @($catalog.recommendations)) {
    if (-not (Test-RecommendationMatchesStack -Recommendation $entry -DetectedTags $detectedTags)) { continue }
    if ($Dismissed -contains $entry.id) { continue }
    $recommendations += ConvertTo-CatalogRecommendation -Entry $entry -Accepted $Accepted
  }

  $recommendationsById = [ordered]@{}
  foreach ($recommendation in @($recommendations)) {
    if ($null -eq $recommendation) { continue }
    $hash = Convert-ObjectToHashtable $recommendation
    if (-not $hash.Contains("id") -or [string]::IsNullOrWhiteSpace([string]$hash["id"])) {
      if (-not $hash.Contains("name") -or [string]::IsNullOrWhiteSpace([string]$hash["name"])) { continue }
      $hash["id"] = ([string]$hash["name"]).ToLowerInvariant().Replace(" ", "-")
    }
    $recommendationsById[[string]$hash["id"]] = Add-UsedInStepsToRecommendation -Recommendation $hash -Usage $stepUsage
  }

  $notRecommended = foreach ($entry in @($catalog.notRecommended)) {
    if (-not (Test-RecommendationMatchesStack -Recommendation $entry -DetectedTags $detectedTags)) { continue }

    [ordered]@{
      id = $entry.id
      name = $entry.name
      type = $entry.type
      requires = @($entry.requires)
      reason = $entry.reason
      dismissed = ($Dismissed -contains $entry.id)
    }
  }

  return [ordered]@{
    schemaVersion = 1
    mode = "guided-manual"
    sourceCatalog = ".codex/tool-recommendations.example.json"
    localStatePath = ".codex/tool-recommendations.local.json"
    generatedBy = "project-guidance-discover"
    generatedAtUtc = [DateTime]::UtcNow.ToString("o")
    detectedTags = @($report.detectedTags)
    researchTopics = @($report.researchTopics)
    existingSkills = @($report.existingSkills)
    suggestedMissingSkills = @($report.suggestedMissingSkills)
    suggestedPresentSkills = @($report.suggestedPresentSkills)
    suggestedGuidance = @($report.suggestedGuidance)
    userAddedRequestedGuidance = @($report.userAddedRequestedGuidance)
    userAddedRequestedSkills = @($report.userAddedRequestedSkills)
    finalConfirmedGuidance = @($report.finalConfirmedGuidance)
    finalConfirmedSkills = @($report.finalConfirmedSkills)
    acceptedRecommendations = @($Accepted)
    dismissedRecommendations = @($Dismissed)
    recommendations = @($recommendationsById.Values)
    notRecommended = @($notRecommended)
  }
}

function Write-ProjectGuidanceLocalState {
  param(
    $Result,
    $State,
    [string]$Message
  )

  $targetRelative = ".codex/tool-recommendations.local.json"
  $target = Join-RootPath $targetRelative
  Add-Item $Result "actions" $targetRelative "projectGuidance" $Message

  if (Test-ConfigWritesEnabled) {
    $targetDirectory = Split-Path -Parent $target
    if (-not (Test-Path $targetDirectory)) {
      New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
    }

    $State | ConvertTo-Json -Depth 30 | Set-Content -Path $target -Encoding UTF8
  }
}

function Get-HashtableArrayValue {
  param(
    [hashtable]$Map,
    [string]$Key
  )

  if (-not $Map.Contains($Key) -or $null -eq $Map[$Key]) { return @() }
  return @($Map[$Key])
}

function Get-ConfirmedGuidanceItemsFromJson {
  param([AllowNull()][string]$Json)

  if ([string]::IsNullOrWhiteSpace($Json)) {
    throw "ValuesJson is required for AcquireProjectGuidance."
  }
  if ($Json -match '"installCommand"\s*:') {
    throw "AcquireProjectGuidance rejects installCommand; project skills must use manual-copy only."
  }

  $data = $Json | ConvertFrom-Json
  if ($data -is [array]) { return @($data) }
  foreach ($propertyName in @("finalConfirmedGuidance", "confirmedGuidance", "finalConfirmedSkills", "skills", "guidance")) {
    if ($data.PSObject.Properties.Name -contains $propertyName) {
      return @($data.$propertyName)
    }
  }

  throw "ValuesJson must include finalConfirmedGuidance, confirmedGuidance, finalConfirmedSkills, skills, or guidance."
}

function Test-RepoRelativeTarget {
  param([string]$TargetRelative)

  if ([string]::IsNullOrWhiteSpace($TargetRelative)) { return $false }
  $normalized = $TargetRelative.Replace("\", "/")
  if (-not $normalized.StartsWith(".codex/skills/")) { return $false }
  if (-not $normalized.EndsWith("/SKILL.md")) { return $false }
  if ($normalized -match "(^|/)\.\.($|/)") { return $false }
  return $true
}

function Get-RequiredSkillAcquisitionFields {
  return @("name", "type", "installMethod", "source", "target", "validation", "sourceKind")
}

function Test-ValidProjectGuidanceSourceKind {
  param([string]$SourceKind)

  if ([string]::IsNullOrWhiteSpace($SourceKind)) { return $false }
  return @(Get-ProjectGuidanceDiscoverySourcePriority) -contains $SourceKind
}

function Test-ConfirmedSkillAcquisitionContract {
  param(
    $Result,
    $Item,
    [string]$DisplayName
  )

  foreach ($field in Get-RequiredSkillAcquisitionFields) {
    if ($Item.PSObject.Properties.Name -notcontains $field -or [string]::IsNullOrWhiteSpace([string]$Item.$field)) {
      Add-Item $Result "warnings" $DisplayName $field "Skipping skill because confirmed manual-copy skill items must include '$field'." "warning"
      return $false
    }
  }

  if ([string]$Item.type -ne "skill") {
    Add-Item $Result "warnings" $DisplayName "type" "Skipping skill because type must be 'skill'." "warning"
    return $false
  }
  if ([string]$Item.installMethod -ne "manual-copy") {
    Add-Item $Result "warnings" $DisplayName "installMethod" "Skipping skill because installMethod is '$($Item.installMethod)', not manual-copy." "warning"
    return $false
  }
  if (-not (Test-ValidProjectGuidanceSourceKind ([string]$Item.sourceKind))) {
    Add-Item $Result "warnings" $DisplayName "sourceKind" "Skipping skill because sourceKind must be one of: $((Get-ProjectGuidanceDiscoverySourcePriority) -join ', ')." "warning"
    return $false
  }

  return $true
}

function Invoke-AcquireProjectGuidance {
  $result = New-Result
  $items = Get-ConfirmedGuidanceItemsFromJson $ValuesJson

  foreach ($item in @($items)) {
    $type = if ($item.PSObject.Properties.Name -contains "type") { [string]$item.type } else { "skill" }
    $name = if ($item.PSObject.Properties.Name -contains "name") { [string]$item.name } elseif ($item.PSObject.Properties.Name -contains "id") { [string]$item.id } else { "unnamed-guidance" }

    if ($type -ne "skill") {
      Add-Item $result "findings" $name "non-skill-guidance" "Non-skill guidance remains in .codex/tool-recommendations.local.json; no file copy is required." "info"
      continue
    }

    if (-not (Test-ConfirmedSkillAcquisitionContract $result $item $name)) {
      continue
    }

    $source = [string]$item.source
    $targetRelative = [string]$item.target
    if (-not (Test-RepoRelativeTarget $targetRelative)) {
      Add-Item $result "warnings" $targetRelative "target" "Skipping skill because target must be under .codex/skills/{skill-name}/SKILL.md." "warning"
      continue
    }

    if (-not $source.StartsWith("repo:")) {
      Add-Item $result "warnings" $name "source" "Source '$source' is not a repo: path. Use skills.sh/skills, marketplace, or remote URLs only to identify and verify a source repository/ref/path; then provide a repo: source for this deterministic copy step or copy through the project-guidance-acquire skill." "warning"
      continue
    }

    $sourceRelative = $source.Substring("repo:".Length)
    $sourcePath = Join-RootPath $sourceRelative
    $targetPath = Join-RootPath $targetRelative
    if (-not (Test-Path $sourcePath)) {
      Add-Item $result "warnings" $sourceRelative "source" "Source SKILL.md does not exist." "warning"
      continue
    }
    if (Test-Path $targetPath) {
      Add-Item $result "findings" $targetRelative "already-present" "Repo-local skill already exists; not overwriting without explicit replacement." "info"
      continue
    }

    Add-Item $result "actions" $targetRelative "manual-copy" "Copy confirmed SKILL.md from $source with sourceKind '$($item.sourceKind)'."
    if (Test-ConfigWritesEnabled) {
      $targetDirectory = Split-Path -Parent $targetPath
      if (-not (Test-Path $targetDirectory)) {
        New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
      }
      Copy-Item -Path $sourcePath -Destination $targetPath
    }

    Add-Item $result "findings" $targetRelative "validation" "Validate with: $($item.validation)" "info"
  }

  return $result
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

  $grafanaDashboards = @(
    "infra/monitoring/grafana/provisioning/dashboards/dashboards.yml",
    "infra/monitoring/grafana/provisioning/datasources/azure-monitor.yml"
  )
  foreach ($dashboardFile in $grafanaDashboards) {
    if (-not (Test-Path (Join-RootPath $dashboardFile))) {
      Add-Item $result "findings" $dashboardFile "grafana-dashboard-provisioning" "Missing Grafana dashboard provisioning artifact." "info" "post-start"
    }
  }

  $requiredAzureMonitorEnv = @(
    "GRAFANA_AZURE_TENANT_ID",
    "GRAFANA_AZURE_CLIENT_ID",
    "GRAFANA_AZURE_CLIENT_SECRET",
    "GRAFANA_AZURE_SUBSCRIPTION_ID",
    "GRAFANA_AZURE_DEV_LOG_ANALYTICS_WORKSPACE_ID",
    "GRAFANA_AZURE_QA_LOG_ANALYTICS_WORKSPACE_ID",
    "GRAFANA_AZURE_PROD_LOG_ANALYTICS_WORKSPACE_ID"
  )
  foreach ($name in $requiredAzureMonitorEnv) {
    if (-not $plane.Contains($name) -or [string]::IsNullOrWhiteSpace($plane[$name])) {
      Add-Item $result "findings" $planeLocal $name "Missing Grafana Azure Monitor value. Run SetGrafanaAzureMonitor after Azure environments are deployed." "warning" "pre-start"
    }
  }

  $localDashboardDirectory = "infra/monitoring/grafana/dashboards.local"
  if (-not (Test-Path (Join-RootPath $localDashboardDirectory))) {
    Add-Item $result "findings" $localDashboardDirectory "azure-monitor-dashboards" "Generated local Azure Monitor dashboards are missing. Run SetGrafanaAzureMonitor after Azure environments are deployed." "info" "pre-start"
  } else {
    foreach ($envName in @("dev", "qa", "prod")) {
      $dashboardFile = "$localDashboardDirectory/$envName-azure-monitor.json"
      $dashboardPath = Join-RootPath $dashboardFile
      if (-not (Test-Path $dashboardPath)) {
        Add-Item $result "findings" $dashboardFile "azure-monitor-dashboard" "Generated $envName Azure Monitor dashboard is missing. Run SetGrafanaAzureMonitor after Azure environments are deployed." "info" "pre-start"
        continue
      }

      $dashboardContent = Get-Content -Raw -Path $dashboardPath
      if ($dashboardContent -notmatch "/health" -or $dashboardContent -notmatch "App Service Health") {
        Add-Item $result "findings" $dashboardFile "azure-monitor-health-dashboard" "Generated Azure Monitor dashboard is stale and does not include App Service /health panels. Run SetGrafanaAzureMonitor to regenerate dashboards." "warning" "pre-start"
      }

      $healthDashboardFile = "$localDashboardDirectory/$envName-health-dashboard.json"
      $healthDashboardPath = Join-RootPath $healthDashboardFile
      if (-not (Test-Path $healthDashboardPath)) {
        Add-Item $result "findings" $healthDashboardFile "health-dashboard" "Generated $envName health dashboard is missing. Run SetGrafanaAzureMonitor to regenerate dashboards." "warning" "pre-start"
        continue
      }

      $healthDashboardContent = Get-Content -Raw -Path $healthDashboardPath
      if ($healthDashboardContent -notmatch "/health" -or $healthDashboardContent -notmatch "Health Dashboard") {
        Add-Item $result "findings" $healthDashboardFile "health-dashboard" "Generated health dashboard is stale. Run SetGrafanaAzureMonitor to regenerate dashboards." "warning" "pre-start"
      }
    }
  }

  try {
    $containers = @(& docker ps --format "{{.Names}}" 2>$null)
    if ($LASTEXITCODE -eq 0) {
      if ($containers -contains "agentic-grafana") {
        Add-Item $result "actions" "docker" "agentic-grafana" "Grafana container is running."
        try {
          $ready = Invoke-WebRequest -Uri "http://localhost:3001/api/health" -UseBasicParsing -TimeoutSec 5
          if ($ready.StatusCode -eq 200) {
            Add-Item $result "actions" "grafana" "ready" "Grafana readiness endpoint is healthy."
          }
        } catch {
          Add-Item $result "findings" "grafana" "ready" "Grafana container is running but readiness endpoint failed: $($_.Exception.Message)" "warning" "post-start"
        }
      } else {
        Add-Item $result "findings" "docker" "agentic-grafana" "Grafana container is not running; Azure Monitor dashboards are unavailable." "warning" "post-start"
      }
    }
  } catch {
    Add-Item $result "findings" "docker" "monitoring" "Could not inspect Grafana container state: $($_.Exception.Message)" "info" "post-start"
  }

  Add-QualityGateAuditFindings $result
  Add-WorktreeLocalConfigAuditFindings $result

  return $result
}

function Invoke-AuditQualityGates {
  $result = New-Result
  Ensure-InferredClientToolsConfig $result
  Add-QualityGateAuditFindings $result
  return $result
}

function Invoke-AuditRecommendedTools {
  $result = New-Result
  $detectedTags = Get-DetectedStackTags
  $catalog = Get-ToolRecommendationCatalog
  $accepted = @()
  $dismissed = @()
  $recommendationsEnabled = $true
  $clientLocal = ".codex/client-tools.local.json"
  $clientPath = Join-RootPath $clientLocal

  if (Test-Path $clientPath) {
    try {
      $client = Get-Content -Path $clientPath -Raw | ConvertFrom-Json
      if ($null -ne $client.recommendedTools) {
        if ($client.recommendedTools.enabled -eq $false) { $recommendationsEnabled = $false }
        $accepted = @($client.recommendedTools.accepted)
        $dismissed = @($client.recommendedTools.dismissed)
      } else {
        Add-Item $result "findings" $clientLocal "recommendedTools" "Recommended tools config is missing; use SetRecommendedTools after the user accepts or dismisses recommendations." "info"
      }
    } catch {
      Add-Item $result "findings" $clientLocal "recommendedTools" "Could not parse local client config; recommended tools audit will use defaults." "warning"
    }
  } else {
    Add-Item $result "findings" $clientLocal "recommendedTools" "Local client config is missing; recommended tools audit will use defaults." "info"
  }

  Add-Item $result "actions" ".codex/tool-recommendations.example.json" "detectedStack" "Detected stack tags: $($detectedTags -join ', ')."
  Add-StackContextDriftFindings $result $detectedTags

  if (-not $recommendationsEnabled) {
    Add-Item $result "findings" $clientLocal "recommendedTools.enabled" "Recommended tools audit is disabled in local config." "info"
    return $result
  }

  Add-ProjectGuidanceSearchPlanRecommendation $result $detectedTags
  Add-DetectedSkillRecommendations $result $detectedTags $accepted $dismissed

  foreach ($entry in @($catalog.recommendations)) {
    if (-not (Test-RecommendationMatchesStack -Recommendation $entry -DetectedTags $detectedTags)) { continue }
    if ($dismissed -contains $entry.id) { continue }

    $recommendation = [ordered]@{
      id = $entry.id
      name = $entry.name
      type = $entry.type
      purpose = $entry.purpose
      installMethod = $entry.installMethod
      source = $entry.source
      target = $entry.target
      validation = $entry.validation
      accepted = ($accepted -contains $entry.id)
    }

    foreach ($optionalField in @("sourceKind", "requires", "researchTopics", "officialSources", "searchQueries", "notes")) {
      if ($entry.PSObject.Properties.Name -contains $optionalField) {
        $recommendation[$optionalField] = $entry.$optionalField
      }
    }

    Add-Recommendation $result $recommendation
  }

  foreach ($entry in @($catalog.notRecommended)) {
    if (-not (Test-RecommendationMatchesStack -Recommendation $entry -DetectedTags $detectedTags)) { continue }
    Add-Item $result "findings" $entry.name $entry.id $entry.reason "info"
  }

  return $result
}

function Invoke-DiscoverProjectGuidance {
  $accepted = @()
  $dismissed = @()
  $additionalGuidance = @()
  $confirmed = $false
  $persistLocal = $false
  $clientPath = Join-RootPath ".codex/client-tools.local.json"

  if (Test-Path $clientPath) {
    try {
      $client = Get-Content -Path $clientPath -Raw | ConvertFrom-Json
      if ($null -ne $client.recommendedTools) {
        $accepted = @($client.recommendedTools.accepted)
        $dismissed = @($client.recommendedTools.dismissed)
      }
    } catch {
      # Discovery remains useful even when local preference state is unreadable.
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($ValuesJson)) {
    $data = $ValuesJson | ConvertFrom-Json
    $additionalGuidance = Get-AdditionalGuidanceRequestsFromJson $ValuesJson
    if ($data.PSObject.Properties.Name -contains "confirmed") {
      $confirmed = [bool]$data.confirmed
    } elseif ($data.PSObject.Properties.Name -contains "confirmSuggested") {
      $confirmed = [bool]$data.confirmSuggested
    }

    if ($data.PSObject.Properties.Name -contains "persistLocal") {
      $persistLocal = [bool]$data.persistLocal
    } elseif ($data.PSObject.Properties.Name -contains "writeLocalRecommendations") {
      $persistLocal = [bool]$data.writeLocalRecommendations
    }
  }

  $report = Get-ProjectGuidanceDiscoveryReport -Accepted $accepted -Dismissed $dismissed -UserAddedRequestedGuidance $additionalGuidance -Confirmed:($confirmed)
  $result = [ordered]@{
    mode = $Mode
    dryRun = [bool]$DryRun
    writeEnabled = (Test-ConfigWritesEnabled)
    actions = @()
    findings = @()
    recommendations = @()
    warnings = @()
    detectedTags = $report.detectedTags
    researchTopics = $report.researchTopics
    existingSkills = $report.existingSkills
    suggestedMissingSkills = $report.suggestedMissingSkills
    suggestedPresentSkills = $report.suggestedPresentSkills
    suggestedGuidance = $report.suggestedGuidance
    userAddedRequestedGuidance = $report.userAddedRequestedGuidance
    userAddedRequestedSkills = $report.userAddedRequestedSkills
    finalConfirmedGuidance = $report.finalConfirmedGuidance
    finalConfirmedSkills = $report.finalConfirmedSkills
    discoverySourcePriority = $report.discoverySourcePriority
    discoverySourceNotes = $report.discoverySourceNotes
    localRecommendationsPath = ".codex/tool-recommendations.local.json"
    nextUserQuestion = $report.nextUserQuestion
  }

  if ($persistLocal) {
    $state = New-ProjectGuidanceLocalState -Accepted $accepted -Dismissed $dismissed -UserAddedRequestedGuidance $additionalGuidance -Confirmed:($confirmed)
    Write-ProjectGuidanceLocalState $result $state "Persist catalog-shaped project guidance state for project-guidance-mapper and future workflow steps."
  }

  return $result
}

function Invoke-SetRecommendedTools {
  $result = New-Result
  $targetRelative = ".codex/client-tools.local.json"
  $target = Join-RootPath $targetRelative
  if (-not (Test-Path $target)) {
    throw "Missing $targetRelative. Run -Mode InitLocalFiles first."
  }

  $values = Convert-JsonToHashtable $ValuesJson
  if (-not $values.Contains("accepted") -and -not $values.Contains("dismissed")) {
    throw "ValuesJson must include accepted or dismissed recommendation id arrays."
  }

  $config = Get-Content -Path $target -Raw | ConvertFrom-Json
  Ensure-ObjectProperty -Object $config -Name "recommendedTools"
  Set-ObjectValue -Object $config -Path @("recommendedTools", "enabled") -Value $true
  Set-ObjectValue -Object $config -Path @("recommendedTools", "mode") -Value "guided-manual"

  foreach ($key in @("accepted", "dismissed")) {
    if ($values.Contains($key)) {
      Set-ObjectValue -Object $config -Path @("recommendedTools", $key) -Value @($values[$key])
      Add-Item $result "actions" $targetRelative "recommendedTools.$key" "Record confirmed recommendation ids; no skills, plugins, MCPs, or secrets were installed."
    }
  }

  if (-not $DryRun) {
    $config | ConvertTo-Json -Depth 20 | Set-Content -Path $target -Encoding UTF8
  }
  return $result
}

function Invoke-MapProjectGuidanceStep {
  $result = New-Result
  $values = Convert-JsonToHashtable $ValuesJson

  if (-not $values.Contains("workflowStep") -or [string]::IsNullOrWhiteSpace([string]$values.workflowStep)) {
    throw "ValuesJson must include workflowStep."
  }

  $workflowStep = [string]$values.workflowStep
  $canonicalSteps = Get-CanonicalWorkflowSteps
  if ($canonicalSteps -notcontains $workflowStep) {
    throw "workflowStep must be one of: $($canonicalSteps -join ', ')."
  }

  $decisions = Get-RecommendedToolsDecisionState
  $state = New-ProjectGuidanceLocalState -Accepted $decisions.accepted -Dismissed $decisions.dismissed

  $explicitRecommendationIds = @(Get-HashtableArrayValue $values "recommendationIds")
  if ($explicitRecommendationIds.Count -eq 0) {
    $explicitRecommendationIds = @(Get-HashtableArrayValue $values "guidanceIds")
  }

  $existingMappedIds = @($state.recommendations | Where-Object {
    $_.usedInSteps -contains $workflowStep
  } | ForEach-Object { [string]$_.id })
  $defaultIds = @(Get-DefaultRecommendationIdsForWorkflowStep $workflowStep)
  $heuristicIds = @($state.recommendations | Where-Object {
    ($null -eq $_.usedInSteps -or @($_.usedInSteps).Count -eq 0) -and (Test-RecommendationFitsWorkflowStep $_ $workflowStep)
  } | ForEach-Object { [string]$_.id })

  $selectedIds = if ($explicitRecommendationIds.Count -gt 0) {
    @($explicitRecommendationIds)
  } else {
    @($existingMappedIds + $defaultIds + $heuristicIds)
  }
  $selectedIds = @($selectedIds | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Sort-Object -Unique)

  $foundIds = [System.Collections.Generic.List[string]]::new()
  foreach ($recommendation in @($state.recommendations)) {
    if ($selectedIds -notcontains [string]$recommendation.id) { continue }
    $currentSteps = if ($null -ne $recommendation.usedInSteps) { @($recommendation.usedInSteps) } else { @() }
    $recommendation["usedInSteps"] = @(@($currentSteps) + @($workflowStep) | Sort-Object -Unique)
    $foundIds.Add([string]$recommendation.id)
  }

  $missingIds = @($selectedIds | Where-Object { $foundIds -notcontains [string]$_ })
  foreach ($missingId in $missingIds) {
    Add-Item $result "warnings" ".codex/tool-recommendations.local.json" $missingId "Recommendation id was requested or inferred for '$workflowStep' but is not present in the local catalog." "warning"
  }

  $state.generatedBy = "project-guidance-mapper"
  $state.generatedAtUtc = [DateTime]::UtcNow.ToString("o")

  Write-ProjectGuidanceLocalState $result $state "Persist project-guidance-mapper usedInSteps mapping for '$workflowStep'."
  $primarySkills = @(Get-HashtableArrayValue $values "primarySkills")
  if ($primarySkills.Count -eq 0) { $primarySkills = @(Get-DefaultPrimarySkillsForWorkflowStep $workflowStep) }
  $supportingSkills = @(Get-HashtableArrayValue $values "supportingSkills")
  if ($supportingSkills.Count -eq 0) { $supportingSkills = @(Get-DefaultSupportingSkillsForWorkflowStep $workflowStep) }
  $guidanceRecommendations = @($state.recommendations | Where-Object { $foundIds -contains [string]$_.id } | ForEach-Object {
    [ordered]@{
      id = $_.id
      name = $_.name
      type = $_.type
      usedInSteps = @($_.usedInSteps)
    }
  })

  $result["workflowStep"] = $workflowStep
  $result["primarySkills"] = @($primarySkills)
  $result["supportingSkills"] = @($supportingSkills)
  $result["guidanceRecommendations"] = @($guidanceRecommendations)
  $result["missingUsefulGuidance"] = @($missingIds)
  $result["why"] = $(if ($values.Contains("why")) { [string]$values.why } elseif ($values.Contains("reason")) { [string]$values.reason } else { "Mapped project guidance for workflow step '$workflowStep'." })
  $result["nextAction"] = $(if ($values.Contains("nextAction")) { [string]$values.nextAction } else { "Use mapped guidance after verifying current ticket, files, and installed skills." })
  $result["localMappingUpdated"] = (Test-ConfigWritesEnabled)
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
    Assert-NativeCommandSucceeded "docker version"
    Add-Item $result "actions" "docker" "" "Docker CLI is available."
  } catch {
    Add-Item $result "findings" "docker" "" "Docker CLI is installed but not usable: $($_.Exception.Message)" "error"
    return $result
  }

  foreach ($imageInfo in Get-GiteaActionsImages) {
    $image = [string]$imageInfo.image
    try {
      & docker image inspect $image | Out-Null
      Assert-NativeCommandSucceeded "docker image inspect $image"
      Add-Item $result "actions" $imageInfo.dockerfile "image" "Found local Gitea Actions image $image."
    } catch {
      Add-Item $result "findings" $imageInfo.dockerfile "image" "Missing local Gitea Actions image $image. Run -Mode BuildGiteaActionsImages before relying on workflows." "error"
      continue
    }

    $tools = @($imageInfo.requiredTools)
    $toolCheck = "for tool in $($tools -join ' '); do command -v `$tool >/dev/null || { echo missing:`$tool; exit 1; }; done"
    if (-not [string]::IsNullOrWhiteSpace([string]$imageInfo.extraCheck)) {
      $toolCheck = "$toolCheck; $($imageInfo.extraCheck)"
    }
    try {
      & docker run --rm --entrypoint /bin/sh $image -lc $toolCheck | Out-Null
      Assert-NativeCommandSucceeded "docker run tool check for $image"
      Add-Item $result "actions" $imageInfo.dockerfile "container.tools" "Image $image includes required tools: $($tools -join ', ')."
    } catch {
      Add-Item $result "findings" $imageInfo.dockerfile "container.tools" "Image $image is missing one or more required tools: $($tools -join ', ')." "error"
    }
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
      Assert-NativeCommandSucceeded "docker run checkout network check"
      Add-Item $result "actions" $workflowRelativePath "checkout.network" "Runner job image can reach the repository origin through host.docker.internal."
    } catch {
      Add-Item $result "findings" $workflowRelativePath "checkout.network" "Runner job image cannot reach the repository origin through host.docker.internal. Check Gitea URL rewriting, Docker host networking, and GITEA_INSTANCE_URL." "error"
    }
  }

  return $result
}

function Invoke-BuildGiteaActionsImages {
  $result = New-Result
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if ($null -eq $docker) {
    Add-Item $result "findings" "docker" "" "Docker CLI is missing; install Docker Desktop or Docker Engine before building Gitea Actions images." "error"
    return $result
  }

  try {
    & docker version | Out-Null
    Assert-NativeCommandSucceeded "docker version"
    Add-Item $result "actions" "docker" "" "Docker CLI is available."
  } catch {
    Add-Item $result "findings" "docker" "" "Docker CLI is installed but not usable: $($_.Exception.Message)" "error"
    return $result
  }

  foreach ($imageInfo in Get-GiteaActionsImages) {
    $dockerfile = Join-RootPath $imageInfo.dockerfile
    $context = Join-RootPath $imageInfo.context
    $image = [string]$imageInfo.image

    if (-not (Test-Path $dockerfile)) {
      Add-Item $result "findings" $imageInfo.dockerfile "" "Missing Dockerfile for $image." "error"
      continue
    }

    if ($DryRun) {
      Add-Item $result "actions" $imageInfo.dockerfile "docker build" "Would build $image from $($imageInfo.context)."
      continue
    }

    try {
      & docker build --pull -t $image -f $dockerfile $context | Out-Null
      Assert-NativeCommandSucceeded "docker build $image"
      Add-Item $result "actions" $imageInfo.dockerfile "docker build" "Built $image."
    } catch {
      Add-Item $result "findings" $imageInfo.dockerfile "docker build" "Failed to build $image`: $($_.Exception.Message)" "error"
      continue
    }

    $tools = @($imageInfo.requiredTools)
    $toolCheck = "for tool in $($tools -join ' '); do command -v `$tool >/dev/null || { echo missing:`$tool; exit 1; }; done"
    if (-not [string]::IsNullOrWhiteSpace([string]$imageInfo.extraCheck)) {
      $toolCheck = "$toolCheck; $($imageInfo.extraCheck)"
    }

    try {
      & docker run --rm --entrypoint /bin/sh $image -lc $toolCheck | Out-Null
      Assert-NativeCommandSucceeded "docker run tool check for $image"
      Add-Item $result "actions" $imageInfo.dockerfile "container.tools" "Validated $image required tools: $($tools -join ', ')."
    } catch {
      Add-Item $result "findings" $imageInfo.dockerfile "container.tools" "Built $image but required tool validation failed: $($tools -join ', ')." "error"
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

  Write-TemplateFile $result ".gitattributes" @'
* text=auto eol=lf

*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.ico binary
*.pdf binary
*.zip binary
*.gz binary
*.tar binary
*.7z binary
*.dll binary
*.exe binary
*.pdb binary
*.db binary
*.sqlite binary
*.woff binary
*.woff2 binary
*.ttf binary
*.eot binary
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
.codex/delivery-context.local.json
.codex/parallel-delivery.local.json
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
.vscode/*
!.vscode/settings.json
!.vscode/tasks.json
!.vscode/launch.json
!.vscode/extensions.json
!.vscode/*.code-snippets
!.vscode/copilot-instructions.md

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
infra/monitoring/grafana/dashboards.local/

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
  "ticketKeyPattern": "E2EPROJECT-[0-9]+",
  "agentOptimization": {
    "maxAutonomousIterations": 20,
    "maxToolRetries": 2,
    "promptCache": {
      "enabled": true,
      "staticContextFirst": true,
      "dynamicRuntimeContextLast": true,
      "trackCachedTokens": true
    },
    "telemetry": {
      "enabled": true,
      "localPath": ".codex/agent-telemetry.local.jsonl",
      "requiredFields": [
        "timestampUtc",
        "workflowStage",
        "agentRole",
        "model",
        "reasoningEffort",
        "inputTokens",
        "outputTokens",
        "cachedTokens",
        "toolCallCount",
        "retryCount",
        "elapsedMilliseconds",
        "outcome"
      ]
    },
    "workflowEvals": {
      "casesPath": ".codex/agent-evals/workflow-cases.json",
      "resultsPath": ".codex/agent-evals/results.local.json",
      "requireEvalEvidenceBeforeNewAgentRole": true
    }
  }
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
    paths:
      - src/**
      - tests/**

jobs:
  validate:
    runs-on: ubuntu-latest
    container:
      image: agentic/dotnet-ci:10.0.300-tools-1
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

      - name: Restore application projects
        shell: bash
        run: |
          set -euo pipefail

          quality_projects=(
            "src/SDDTemplate.Site/SDDTemplate.Site.csproj"
            "src/SDDTemplate.Api/SDDTemplate.Api.csproj"
            "tests/SDDTemplate.Site.Tests/SDDTemplate.Site.Tests.csproj"
          )
          for project in "${quality_projects[@]}"; do
            dotnet restore "$project"
          done

      - name: Verify application formatting
        shell: bash
        run: |
          set -euo pipefail

          quality_projects=(
            "src/SDDTemplate.Site/SDDTemplate.Site.csproj"
            "src/SDDTemplate.Api/SDDTemplate.Api.csproj"
            "tests/SDDTemplate.Site.Tests/SDDTemplate.Site.Tests.csproj"
          )
          for project in "${quality_projects[@]}"; do
            dotnet format "$project" --verify-no-changes --no-restore
          done

      - name: Build application projects
        shell: bash
        run: |
          set -euo pipefail

          quality_projects=(
            "src/SDDTemplate.Site/SDDTemplate.Site.csproj"
            "src/SDDTemplate.Api/SDDTemplate.Api.csproj"
            "tests/SDDTemplate.Site.Tests/SDDTemplate.Site.Tests.csproj"
          )
          for project in "${quality_projects[@]}"; do
            dotnet build "$project" -c Release --no-restore
          done

      - name: Test
        run: dotnet test tests/SDDTemplate.Site.Tests/SDDTemplate.Site.Tests.csproj -c Release --no-build --logger trx --collect:"XPlat Code Coverage"

      - name: Enforce coverage threshold
        shell: bash
        run: |
          set -euo pipefail

          config=".codex/quality.local.json"
          if [ ! -f "$config" ]; then
            config=".codex/quality.example.json"
          fi

          minimum="$(dotnet run --project tools/SDDTemplate.DeliveryTools/SDDTemplate.DeliveryTools.csproj -- ReadCoverageThreshold --path "$config" --fallback 80)"

          coverage_file="$(find . -path '*/coverage.cobertura.xml' -print -quit)"
          if [ -z "$coverage_file" ]; then
            echo "No Cobertura coverage report found."
            exit 1
          fi

          actual="$(dotnet run --project tools/SDDTemplate.DeliveryTools/SDDTemplate.DeliveryTools.csproj -- ReadCoberturaLineRate --path "$coverage_file")"
          awk -v actual="$actual" -v minimum="$minimum" 'BEGIN { exit !(actual + 0 >= minimum + 0) }' || {
            echo "Coverage ${actual}% is below required ${minimum}%."
            exit 1
          }

          echo "Coverage ${actual}% meets required ${minimum}%."

      - name: Dependency vulnerability audit
        shell: bash
        run: |
          set -euo pipefail

          quality_projects=(
            "src/SDDTemplate.Site/SDDTemplate.Site.csproj"
            "src/SDDTemplate.Api/SDDTemplate.Api.csproj"
            "tests/SDDTemplate.Site.Tests/SDDTemplate.Site.Tests.csproj"
          )
          for project in "${quality_projects[@]}"; do
            dotnet list "$project" package --vulnerable --include-transitive
          done

      - name: Secret scan
        run: gitleaks detect --source . --redact --no-git

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
      - qa/**
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
              src/*|tests/*)
                app_changed=true
                ;;
            esac
          done <<EOF
          $changed_files
          EOF

          ticket_key_pattern="$(sed -nE 's/.*"ticketKeyPattern"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' .codex/delivery-policy.json | head -n 1)"
          if [ -z "$ticket_key_pattern" ]; then
            echo "Could not read ticketKeyPattern from .codex/delivery-policy.json."
            exit 1
          fi

          commit_message="${{ github.event.head_commit.message }}"
          plane_ticket_key=""
          if [[ "$commit_message" =~ ^($ticket_key_pattern) ]]; then
            plane_ticket_key="${BASH_REMATCH[1]}"
          elif [[ "$commit_message" =~ Merge\ pull\ request.*\'($ticket_key_pattern): ]]; then
            plane_ticket_key="${BASH_REMATCH[1]}"
          fi
          deploy_allowed=false
          if [ -n "$plane_ticket_key" ]; then
            deploy_allowed=true
          fi

          echo "app_changed=$app_changed" >> "$GITHUB_OUTPUT"
          echo "deploy_allowed=$deploy_allowed" >> "$GITHUB_OUTPUT"

  package:
    needs: classify-changes
    if: (github.event_name == 'push' && github.ref == 'refs/heads/dev' && needs.classify-changes.outputs.app_changed == 'true' && needs.classify-changes.outputs.deploy_allowed == 'true') || github.event.inputs.environment == 'dev' || github.event.inputs.environment == 'qa'
    runs-on: ubuntu-latest
    container:
      image: agentic/dotnet-ci:10.0.300-tools-1
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

      - name: Publish topology apps
        shell: bash
        run: |
          set -euo pipefail

          mkdir -p artifacts/packages
          jq -c '.apps | sort_by(.deployOrder)' infra/deployment/apps.json > artifacts/deployable-apps.json
          jq -r '.apps[] | [.appId, .projectPath, .artifactName] | @tsv' infra/deployment/apps.json |
          while IFS=$'\t' read -r app_id project_path artifact_name; do
            case "$project_path" in
              src/*) ;;
              *) echo "Deployable app '$app_id' projectPath must be under src/: $project_path" && exit 1 ;;
            esac
            test -f "$project_path"
            echo "Publishing $app_id from $project_path"
            dotnet publish "$project_path" -c Release -o "artifacts/$app_id"
            (cd "artifacts/$app_id" && zip -r "../packages/$artifact_name" .)
            sha256sum "artifacts/packages/$artifact_name" | sed "s#artifacts/packages/##" > "artifacts/packages/$artifact_name.sha256"
          done

          git rev-parse HEAD > artifacts/commit.sha
          dotnet run --project tools/SDDTemplate.DeliveryTools/SDDTemplate.DeliveryTools.csproj -- BuildDeploymentConfig --root . --topology infra/deployment/apps.json --mapping infra/deployment/configuration.json --output artifacts/deployment-config.json

      - name: Upload topology artifacts to Nexus
        shell: bash
        run: |
          set -euo pipefail

          commit_sha="$(cat artifacts/commit.sha)"
          first_artifact_name="$(jq -r '.apps | sort_by(.deployOrder) | .[0].artifactName' infra/deployment/apps.json)"
          first_artifact_checksum="$(cut -d ' ' -f1 "artifacts/packages/$first_artifact_name.sha256")"
          ticket_key_pattern="$(dotnet run --project tools/SDDTemplate.DeliveryTools/SDDTemplate.DeliveryTools.csproj -- ReadDeliveryPolicy --path .codex/delivery-policy.json)"

          commit_message="$(git log -1 --pretty=%B)"
          plane_ticket_key="$(dotnet run --project tools/SDDTemplate.DeliveryTools/SDDTemplate.DeliveryTools.csproj -- ExtractTicketKey --pattern "$ticket_key_pattern" --message "$commit_message" --fallback manual-dispatch)"

          artifact_url="$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/$first_artifact_name"
          dotnet run --project tools/SDDTemplate.DeliveryTools/SDDTemplate.DeliveryTools.csproj -- CreateReleaseManifest --output artifacts/release.json --commit-sha "$commit_sha" --checksum "$first_artifact_checksum" --artifact-url "$artifact_url" --plane-ticket-key "$plane_ticket_key" --version-status unversioned
          dotnet run --project tools/SDDTemplate.DeliveryTools/SDDTemplate.DeliveryTools.csproj -- ValidateReleaseManifest --path artifacts/release.json

          jq -r '.apps[] | .artifactName' infra/deployment/apps.json |
          while IFS= read -r artifact_name; do
            curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" --upload-file "artifacts/packages/$artifact_name" "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/$artifact_name"
            curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" --upload-file "artifacts/packages/$artifact_name.sha256" "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/$artifact_name.sha256"
          done

          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" --upload-file artifacts/deployable-apps.json "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/deployable-apps.json"
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" --upload-file artifacts/deployment-config.json "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/deployment-config.json"
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
    container:
      image: agentic/dotnet-ci:10.0.300-tools-1
    if: (github.event_name == 'push' && github.ref == 'refs/heads/dev' && needs.classify-changes.outputs.app_changed == 'true' && needs.classify-changes.outputs.deploy_allowed == 'true') || github.event.inputs.environment == 'dev' || github.event.inputs.environment == 'qa'
    steps:
      - name: Download topology artifacts from Nexus
        shell: bash
        run: |
          set -euo pipefail

          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o deployable-apps.json "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/deployable-apps.json"
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o deployment-config.json "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/deployment-config.json"
          jq -r '.[].artifactName' deployable-apps.json |
          while IFS= read -r artifact_name; do
            curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o "$artifact_name" "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/$artifact_name"
            curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o "$artifact_name.sha256" "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/$artifact_name.sha256"
            sha256sum -c "$artifact_name.sha256"
          done
        env:
          NEXUS_URL: ${{ secrets.NEXUS_URL }}
          NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
          NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
          NEXUS_REPOSITORY: ${{ secrets.NEXUS_REPOSITORY }}

      - name: Azure login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Apply and verify DEV deployment configuration
        shell: bash
        run: |
          set -euo pipefail

          resolve_setting() {
            local source="$1"
            local target_app_id="$2"
            local target_property="$3"
            local literal_value="$4"
            local secret_name="$5"
            case "$source" in
              literal|sqliteDataPath)
                printf '%s' "$literal_value"
                ;;
              environmentName)
                printf '%s' "Development"
                ;;
              topologyReference)
                target_upper="$(echo "$target_app_id" | tr '[:lower:]-' '[:upper:]_')"
                case "$target_property" in
                  url) var_name="AZURE_DEV_${target_upper}_APP_URL" ;;
                  name) var_name="AZURE_DEV_${target_upper}_APP_NAME" ;;
                  *) echo "Unsupported topology target property: $target_property" >&2; return 1 ;;
                esac
                test -n "${!var_name:-}"
                printf '%s' "${!var_name}"
                ;;
              environmentSecret)
                test -n "$secret_name"
                test -n "${!secret_name:-}"
                printf '%s' "${!secret_name}"
                ;;
              manualRequired)
                echo "Manual required setting is not mapped for CI deployment." >&2
                return 1
                ;;
              *)
                echo "Unsupported deployment configuration source: $source" >&2
                return 1
                ;;
            esac
          }

          jq -c '.apps[]' deployment-config.json |
          while IFS= read -r app_config; do
            app_id="$(jq -r '.appId' <<< "$app_config")"
            app_upper="$(echo "$app_id" | tr '[:lower:]-' '[:upper:]_')"
            app_name_var="AZURE_DEV_${app_upper}_APP_NAME"
            app_name="${!app_name_var:-}"
            test -n "$app_name"

            settings_args=()
            while IFS= read -r setting; do
              name="$(jq -r '.name' <<< "$setting")"
              source="$(jq -r '.source' <<< "$setting")"
              target_app_id="$(jq -r '.targetAppId // ""' <<< "$setting")"
              target_property="$(jq -r '.targetProperty // ""' <<< "$setting")"
              literal_value="$(jq -r '.value // ""' <<< "$setting")"
              secret_name="$(jq -r '.secretName // ""' <<< "$setting")"
              value="$(resolve_setting "$source" "$target_app_id" "$target_property" "$literal_value" "$secret_name")"
              settings_args+=("$name=$value")
            done < <(jq -c '.settings[]' <<< "$app_config")

            if [ "${#settings_args[@]}" -gt 0 ]; then
              az webapp config appsettings set --resource-group "$AZURE_DEV_RESOURCE_GROUP" --name "$app_name" --settings "${settings_args[@]}" --output none
            fi

            while IFS= read -r setting; do
              name="$(jq -r '.name' <<< "$setting")"
              required="$(jq -r '.required' <<< "$setting")"
              secret="$(jq -r '.secret' <<< "$setting")"
              source="$(jq -r '.source' <<< "$setting")"
              target_app_id="$(jq -r '.targetAppId // ""' <<< "$setting")"
              target_property="$(jq -r '.targetProperty // ""' <<< "$setting")"
              literal_value="$(jq -r '.value // ""' <<< "$setting")"
              secret_name="$(jq -r '.secretName // ""' <<< "$setting")"
              expected="$(resolve_setting "$source" "$target_app_id" "$target_property" "$literal_value" "$secret_name")"
              actual="$(az webapp config appsettings list --resource-group "$AZURE_DEV_RESOURCE_GROUP" --name "$app_name" --query "[?name=='$name'].value | [0]" -o tsv)"
              if [ "$required" = "true" ] && [ -z "$actual" ]; then
                echo "Required deployment setting '$name' is missing for DEV app '$app_id'." >&2
                exit 1
              fi
              if [ "$secret" != "true" ] && [ "$actual" != "$expected" ]; then
                echo "Deployment setting '$name' does not match expected DEV value for app '$app_id'." >&2
                exit 1
              fi
            done < <(jq -c '.settings[]' <<< "$app_config")
          done
        env:
          AZURE_DEV_RESOURCE_GROUP: ${{ secrets.AZURE_DEV_RESOURCE_GROUP }}
          AZURE_DEV_SITE_APP_NAME: ${{ secrets.AZURE_DEV_SITE_APP_NAME }}
          AZURE_DEV_SITE_APP_URL: ${{ secrets.AZURE_DEV_SITE_APP_URL }}
          AZURE_DEV_API_APP_NAME: ${{ secrets.AZURE_DEV_API_APP_NAME }}
          AZURE_DEV_API_APP_URL: ${{ secrets.AZURE_DEV_API_APP_URL }}

      - name: Deploy DEV topology apps
        shell: bash
        run: |
          set -euo pipefail

          jq -c 'sort_by(.deployOrder)' deployable-apps.json |
          jq -r '.[] | [.appId, .artifactName] | @tsv' |
          while IFS=$'\t' read -r app_id artifact_name; do
            app_upper="$(echo "$app_id" | tr '[:lower:]-' '[:upper:]_')"
            name_var="AZURE_DEV_${app_upper}_APP_NAME"
            app_name="${!name_var:-}"
            test -n "$app_name"
            az webapp deploy --resource-group "$AZURE_DEV_RESOURCE_GROUP" --name "$app_name" --src-path "$artifact_name" --type zip --clean true
          done
        env:
          AZURE_DEV_RESOURCE_GROUP: ${{ secrets.AZURE_DEV_RESOURCE_GROUP }}
          AZURE_DEV_SITE_APP_NAME: ${{ secrets.AZURE_DEV_SITE_APP_NAME }}
          AZURE_DEV_API_APP_NAME: ${{ secrets.AZURE_DEV_API_APP_NAME }}

      - name: Smoke check DEV topology apps
        shell: bash
        run: |
          set -euo pipefail

          jq -r '.[] | [.appId, .role, .healthPath] | @tsv' deployable-apps.json |
          while IFS=$'\t' read -r app_id role health_path; do
            app_upper="$(echo "$app_id" | tr '[:lower:]-' '[:upper:]_')"
            url_var="AZURE_DEV_${app_upper}_APP_URL"
            app_url="${!url_var:-}"
            test -n "$app_url"
            if [ "$role" = "web" ]; then
              curl --fail --silent --show-error --location "$app_url" -o response.html
              grep -q "<title>SDD Template</title>" response.html
              ! grep -qi "Microsoft Azure" response.html
              expected_api_url="${AZURE_DEV_API_APP_URL:-}"
              test -n "$expected_api_url"
              curl --fail --silent --show-error --location "${app_url}/clients" -o clients.html
              grep -q "const apiBaseUrl = \"${expected_api_url}\";" clients.html
            fi
            if [ "$role" = "api" ]; then
              site_origin="${AZURE_DEV_SITE_APP_URL:-}"
              test -n "$site_origin"
              curl --fail --silent --show-error --request OPTIONS \
                --header "Origin: $site_origin" \
                --header "Access-Control-Request-Method: POST" \
                --header "Access-Control-Request-Headers: content-type" \
                --dump-header cors.headers \
                --output /dev/null \
                "${app_url}/api/clients"
              grep -iq "^Access-Control-Allow-Origin: ${site_origin}" cors.headers
            fi
            curl --fail --silent --show-error --location "${app_url}${health_path}" -o health.json
            grep -q '"status":"ok"' health.json
          done
        env:
          AZURE_DEV_SITE_APP_URL: ${{ secrets.AZURE_DEV_SITE_APP_URL }}
          AZURE_DEV_API_APP_URL: ${{ secrets.AZURE_DEV_API_APP_URL }}

  deploy-qa:
    needs:
      - classify-changes
      - deploy-dev
    runs-on: ubuntu-latest
    container:
      image: agentic/dotnet-ci:10.0.300-tools-1
    if: (github.event_name == 'push' && github.ref == 'refs/heads/dev' && needs.classify-changes.outputs.app_changed == 'true' && needs.classify-changes.outputs.deploy_allowed == 'true') || github.event.inputs.environment == 'qa'
    steps:
      - name: Download topology artifacts from Nexus
        shell: bash
        run: |
          set -euo pipefail

          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o deployable-apps.json "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/deployable-apps.json"
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o deployment-config.json "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/deployment-config.json"
          jq -r '.[].artifactName' deployable-apps.json |
          while IFS= read -r artifact_name; do
            curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o "$artifact_name" "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/$artifact_name"
            curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o "$artifact_name.sha256" "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${GITHUB_SHA}/$artifact_name.sha256"
            sha256sum -c "$artifact_name.sha256"
          done
        env:
          NEXUS_URL: ${{ secrets.NEXUS_URL }}
          NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
          NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
          NEXUS_REPOSITORY: ${{ secrets.NEXUS_REPOSITORY }}

      - name: Azure login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Apply and verify QA deployment configuration
        shell: bash
        run: |
          set -euo pipefail

          resolve_setting() {
            local source="$1"
            local target_app_id="$2"
            local target_property="$3"
            local literal_value="$4"
            local secret_name="$5"
            case "$source" in
              literal|sqliteDataPath)
                printf '%s' "$literal_value"
                ;;
              environmentName)
                printf '%s' "Staging"
                ;;
              topologyReference)
                target_upper="$(echo "$target_app_id" | tr '[:lower:]-' '[:upper:]_')"
                case "$target_property" in
                  url) var_name="AZURE_QA_${target_upper}_APP_URL" ;;
                  name) var_name="AZURE_QA_${target_upper}_APP_NAME" ;;
                  *) echo "Unsupported topology target property: $target_property" >&2; return 1 ;;
                esac
                test -n "${!var_name:-}"
                printf '%s' "${!var_name}"
                ;;
              environmentSecret)
                test -n "$secret_name"
                test -n "${!secret_name:-}"
                printf '%s' "${!secret_name}"
                ;;
              manualRequired)
                echo "Manual required setting is not mapped for CI deployment." >&2
                return 1
                ;;
              *)
                echo "Unsupported deployment configuration source: $source" >&2
                return 1
                ;;
            esac
          }

          jq -c '.apps[]' deployment-config.json |
          while IFS= read -r app_config; do
            app_id="$(jq -r '.appId' <<< "$app_config")"
            app_upper="$(echo "$app_id" | tr '[:lower:]-' '[:upper:]_')"
            app_name_var="AZURE_QA_${app_upper}_APP_NAME"
            app_name="${!app_name_var:-}"
            test -n "$app_name"

            settings_args=()
            while IFS= read -r setting; do
              name="$(jq -r '.name' <<< "$setting")"
              source="$(jq -r '.source' <<< "$setting")"
              target_app_id="$(jq -r '.targetAppId // ""' <<< "$setting")"
              target_property="$(jq -r '.targetProperty // ""' <<< "$setting")"
              literal_value="$(jq -r '.value // ""' <<< "$setting")"
              secret_name="$(jq -r '.secretName // ""' <<< "$setting")"
              value="$(resolve_setting "$source" "$target_app_id" "$target_property" "$literal_value" "$secret_name")"
              settings_args+=("$name=$value")
            done < <(jq -c '.settings[]' <<< "$app_config")

            if [ "${#settings_args[@]}" -gt 0 ]; then
              az webapp config appsettings set --resource-group "$AZURE_QA_RESOURCE_GROUP" --name "$app_name" --settings "${settings_args[@]}" --output none
            fi

            while IFS= read -r setting; do
              name="$(jq -r '.name' <<< "$setting")"
              required="$(jq -r '.required' <<< "$setting")"
              secret="$(jq -r '.secret' <<< "$setting")"
              source="$(jq -r '.source' <<< "$setting")"
              target_app_id="$(jq -r '.targetAppId // ""' <<< "$setting")"
              target_property="$(jq -r '.targetProperty // ""' <<< "$setting")"
              literal_value="$(jq -r '.value // ""' <<< "$setting")"
              secret_name="$(jq -r '.secretName // ""' <<< "$setting")"
              expected="$(resolve_setting "$source" "$target_app_id" "$target_property" "$literal_value" "$secret_name")"
              actual="$(az webapp config appsettings list --resource-group "$AZURE_QA_RESOURCE_GROUP" --name "$app_name" --query "[?name=='$name'].value | [0]" -o tsv)"
              if [ "$required" = "true" ] && [ -z "$actual" ]; then
                echo "Required deployment setting '$name' is missing for QA app '$app_id'." >&2
                exit 1
              fi
              if [ "$secret" != "true" ] && [ "$actual" != "$expected" ]; then
                echo "Deployment setting '$name' does not match expected QA value for app '$app_id'." >&2
                exit 1
              fi
            done < <(jq -c '.settings[]' <<< "$app_config")
          done
        env:
          AZURE_QA_RESOURCE_GROUP: ${{ secrets.AZURE_QA_RESOURCE_GROUP }}
          AZURE_QA_SITE_APP_NAME: ${{ secrets.AZURE_QA_SITE_APP_NAME }}
          AZURE_QA_SITE_APP_URL: ${{ secrets.AZURE_QA_SITE_APP_URL }}
          AZURE_QA_API_APP_NAME: ${{ secrets.AZURE_QA_API_APP_NAME }}
          AZURE_QA_API_APP_URL: ${{ secrets.AZURE_QA_API_APP_URL }}

      - name: Deploy QA topology apps
        shell: bash
        run: |
          set -euo pipefail

          jq -c 'sort_by(.deployOrder)' deployable-apps.json |
          jq -r '.[] | [.appId, .artifactName] | @tsv' |
          while IFS=$'\t' read -r app_id artifact_name; do
            app_upper="$(echo "$app_id" | tr '[:lower:]-' '[:upper:]_')"
            name_var="AZURE_QA_${app_upper}_APP_NAME"
            app_name="${!name_var:-}"
            test -n "$app_name"
            az webapp deploy --resource-group "$AZURE_QA_RESOURCE_GROUP" --name "$app_name" --src-path "$artifact_name" --type zip --clean true
          done
        env:
          AZURE_QA_RESOURCE_GROUP: ${{ secrets.AZURE_QA_RESOURCE_GROUP }}
          AZURE_QA_SITE_APP_NAME: ${{ secrets.AZURE_QA_SITE_APP_NAME }}
          AZURE_QA_API_APP_NAME: ${{ secrets.AZURE_QA_API_APP_NAME }}

      - name: Smoke check QA topology apps
        shell: bash
        run: |
          set -euo pipefail

          jq -r '.[] | [.appId, .role, .healthPath] | @tsv' deployable-apps.json |
          while IFS=$'\t' read -r app_id role health_path; do
            app_upper="$(echo "$app_id" | tr '[:lower:]-' '[:upper:]_')"
            url_var="AZURE_QA_${app_upper}_APP_URL"
            app_url="${!url_var:-}"
            test -n "$app_url"
            if [ "$role" = "web" ]; then
              curl --fail --silent --show-error --location "$app_url" -o response.html
              grep -q "<title>SDD Template</title>" response.html
              ! grep -qi "Microsoft Azure" response.html
              expected_api_url="${AZURE_QA_API_APP_URL:-}"
              test -n "$expected_api_url"
              curl --fail --silent --show-error --location "${app_url}/clients" -o clients.html
              grep -q "const apiBaseUrl = \"${expected_api_url}\";" clients.html
            fi
            if [ "$role" = "api" ]; then
              site_origin="${AZURE_QA_SITE_APP_URL:-}"
              test -n "$site_origin"
              curl --fail --silent --show-error --request OPTIONS \
                --header "Origin: $site_origin" \
                --header "Access-Control-Request-Method: POST" \
                --header "Access-Control-Request-Headers: content-type" \
                --dump-header cors.headers \
                --output /dev/null \
                "${app_url}/api/clients"
              grep -iq "^Access-Control-Allow-Origin: ${site_origin}" cors.headers
            fi
            curl --fail --silent --show-error --location "${app_url}${health_path}" -o health.json
            grep -q '"status":"ok"' health.json
          done
        env:
          AZURE_QA_SITE_APP_URL: ${{ secrets.AZURE_QA_SITE_APP_URL }}
          AZURE_QA_API_APP_URL: ${{ secrets.AZURE_QA_API_APP_URL }}

  e2e-qa-branch:
    runs-on: ubuntu-latest
    container:
      image: agentic/e2e-ci:playwright-1.57.0-1
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/heads/qa/')
    steps:
      - name: Checkout QA E2E branch
        shell: bash
        run: |
          set -euo pipefail

          repo_url="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}.git"
          repo_url="${repo_url/localhost/host.docker.internal}"
          repo_url="${repo_url/gitea/host.docker.internal}"

          git init .
          git remote add origin "$repo_url"
          git fetch --depth 50 origin "$GITHUB_SHA"
          git checkout --force FETCH_HEAD
          git fetch --depth 50 origin dev

      - name: Resolve QA artifact commit
        shell: bash
        run: |
          set -euo pipefail

          artifact_commit_sha="$(git merge-base HEAD origin/dev)"
          test -n "$artifact_commit_sha"
          echo "E2E_ARTIFACT_COMMIT_SHA=$artifact_commit_sha" >> "$GITHUB_ENV"

          ticket_key_pattern="$(sed -nE 's/.*"ticketKeyPattern"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' .codex/delivery-policy.json | head -n 1)"
          branch_name="${GITHUB_REF#refs/heads/}"
          plane_ticket_key="$(printf '%s\n' "$branch_name" | sed -nE "s#^qa/($ticket_key_pattern)(/.*)?\$#\1#p" | head -n 1)"
          test -n "$plane_ticket_key"
          echo "E2E_PLANE_TICKET_KEY=$plane_ticket_key" >> "$GITHUB_ENV"

      - name: Install E2E dependencies
        shell: bash
        run: |
          set -euo pipefail

          cd tests/SDDTemplate.E2ETests
          npm ci

      - name: Run QA branch E2E suite and upload evidence
        shell: bash
        run: |
          set -euo pipefail

          cd tests/SDDTemplate.E2ETests
          mkdir -p evidence

          test_exit=0
          npm test || test_exit=$?

          run_id="$(date -u +%Y%m%d-%H%M%S)-${GITHUB_SHA:0:7}"
          {
            echo "ticketKey=$E2E_PLANE_TICKET_KEY"
            echo "artifactCommitSha=$E2E_ARTIFACT_COMMIT_SHA"
            echo "testCommitSha=$GITHUB_SHA"
            echo "runId=$run_id"
            echo "siteUrl=$E2E_SITE_URL"
            echo "apiUrl=$E2E_API_URL"
            echo "result=$([ "$test_exit" -eq 0 ] && echo PASS || echo FAIL)"
          } > evidence/qa-e2e-summary.txt

          [ -d playwright-report ] && cp -r playwright-report evidence/
          [ -d test-results ] && cp -r test-results evidence/
          zip -r qa-e2e-evidence.zip evidence

          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" --upload-file qa-e2e-evidence.zip "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/${E2E_ARTIFACT_COMMIT_SHA}/qa-e2e-evidence.zip"
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" --upload-file qa-e2e-evidence.zip "$NEXUS_URL/repository/$NEXUS_REPOSITORY/qa/${E2E_PLANE_TICKET_KEY}/${run_id}/qa-e2e-evidence.zip"

          exit "$test_exit"
        env:
          E2E_SITE_URL: ${{ secrets.AZURE_QA_SITE_APP_URL }}
          E2E_API_URL: ${{ secrets.AZURE_QA_API_APP_URL }}
          NEXUS_URL: ${{ secrets.NEXUS_URL }}
          NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
          NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
          NEXUS_REPOSITORY: ${{ secrets.NEXUS_REPOSITORY }}

  deploy-prod:
    needs: classify-changes
    runs-on: ubuntu-latest
    container:
      image: agentic/dotnet-ci:10.0.300-tools-1
    if: (github.event_name == 'push' && github.ref == 'refs/heads/main' && needs.classify-changes.outputs.app_changed == 'true' && needs.classify-changes.outputs.deploy_allowed == 'true') || (github.event_name == 'workflow_dispatch' && github.event.inputs.environment == 'prod')
    steps:
      - name: Resolve PROD promotion inputs
        shell: bash
        run: |
          set -euo pipefail

          if [ "$GITHUB_EVENT_NAME" = "push" ]; then
            curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o qa-approved-latest.json "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/qa-approved/latest.json"
            artifact_commit_sha="$(jq -r '.artifactCommitSha // empty' qa-approved-latest.json)"
            source_rc_version="$(jq -r '.version // empty' qa-approved-latest.json)"
            release_manifest_path="$(jq -r '.releaseManifestPath // empty' qa-approved-latest.json)"

            test -n "$artifact_commit_sha"
            test -n "$source_rc_version"
            test "$release_manifest_path" = "app/$artifact_commit_sha/release.json"
            [[ "$source_rc_version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-rc\.[0-9]+$ ]]
            test "$artifact_commit_sha" = "$GITHUB_SHA"

            curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o commit.sha "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/$artifact_commit_sha/commit.sha"
            test "$(tr -d '[:space:]' < commit.sha)" = "$artifact_commit_sha"
            curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o release.json "$NEXUS_URL/repository/$NEXUS_REPOSITORY/$release_manifest_path"
            test "$(jq -r '.commitSha // empty' release.json)" = "$artifact_commit_sha"
            test "$(jq -r '.sourceRcVersion // empty' release.json)" = "$source_rc_version"
            test "$(jq -r '.qaResult // empty' release.json)" = "PASS"
            test -n "$(jq -r '.qaEvidenceUrl // empty' release.json)"
            test "$(jq -c '(.includedTickets // [.planeTicketKey]) | sort' qa-approved-latest.json)" = "$(jq -c '(.includedTickets // [.planeTicketKey]) | sort' release.json)"

            git fetch --depth 1 origin "refs/tags/$source_rc_version:refs/tags/$source_rc_version"
            test "$(git rev-list -n 1 "$source_rc_version")" = "$artifact_commit_sha"
          else
            artifact_commit_sha="$ARTIFACT_COMMIT_SHA"
            test -n "$RELEASE_VERSION"
            test -n "$SOURCE_RC_VERSION"
          fi

          test -n "$artifact_commit_sha"
          echo "PROD_ARTIFACT_COMMIT_SHA=$artifact_commit_sha" >> "$GITHUB_ENV"
        env:
          NEXUS_URL: ${{ secrets.NEXUS_URL }}
          NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
          NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
          NEXUS_REPOSITORY: ${{ secrets.NEXUS_REPOSITORY }}
          ARTIFACT_COMMIT_SHA: ${{ github.event.inputs.artifact_commit_sha }}
          RELEASE_VERSION: ${{ github.event.inputs.release_version }}
          SOURCE_RC_VERSION: ${{ github.event.inputs.source_rc_version }}

      - name: Download topology artifacts from Nexus
        shell: bash
        run: |
          set -euo pipefail

          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o deployable-apps.json "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/$PROD_ARTIFACT_COMMIT_SHA/deployable-apps.json"
          curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o deployment-config.json "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/$PROD_ARTIFACT_COMMIT_SHA/deployment-config.json"
          jq -r '.[].artifactName' deployable-apps.json |
          while IFS= read -r artifact_name; do
            curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o "$artifact_name" "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/$PROD_ARTIFACT_COMMIT_SHA/$artifact_name"
            curl --fail --user "$NEXUS_USERNAME:$NEXUS_PASSWORD" -o "$artifact_name.sha256" "$NEXUS_URL/repository/$NEXUS_REPOSITORY/app/$PROD_ARTIFACT_COMMIT_SHA/$artifact_name.sha256"
            sha256sum -c "$artifact_name.sha256"
          done
        env:
          NEXUS_URL: ${{ secrets.NEXUS_URL }}
          NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
          NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
          NEXUS_REPOSITORY: ${{ secrets.NEXUS_REPOSITORY }}

      - name: Azure login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Apply and verify PROD deployment configuration
        shell: bash
        run: |
          set -euo pipefail

          resolve_setting() {
            local source="$1"
            local target_app_id="$2"
            local target_property="$3"
            local literal_value="$4"
            local secret_name="$5"
            case "$source" in
              literal|sqliteDataPath)
                printf '%s' "$literal_value"
                ;;
              environmentName)
                printf '%s' "Production"
                ;;
              topologyReference)
                target_upper="$(echo "$target_app_id" | tr '[:lower:]-' '[:upper:]_')"
                case "$target_property" in
                  url) var_name="AZURE_PROD_${target_upper}_APP_URL" ;;
                  name) var_name="AZURE_PROD_${target_upper}_APP_NAME" ;;
                  *) echo "Unsupported topology target property: $target_property" >&2; return 1 ;;
                esac
                test -n "${!var_name:-}"
                printf '%s' "${!var_name}"
                ;;
              environmentSecret)
                test -n "$secret_name"
                test -n "${!secret_name:-}"
                printf '%s' "${!secret_name}"
                ;;
              manualRequired)
                echo "Manual required setting is not mapped for CI deployment." >&2
                return 1
                ;;
              *)
                echo "Unsupported deployment configuration source: $source" >&2
                return 1
                ;;
            esac
          }

          jq -c '.apps[]' deployment-config.json |
          while IFS= read -r app_config; do
            app_id="$(jq -r '.appId' <<< "$app_config")"
            app_upper="$(echo "$app_id" | tr '[:lower:]-' '[:upper:]_')"
            app_name_var="AZURE_PROD_${app_upper}_APP_NAME"
            app_name="${!app_name_var:-}"
            test -n "$app_name"

            settings_args=()
            while IFS= read -r setting; do
              name="$(jq -r '.name' <<< "$setting")"
              source="$(jq -r '.source' <<< "$setting")"
              target_app_id="$(jq -r '.targetAppId // ""' <<< "$setting")"
              target_property="$(jq -r '.targetProperty // ""' <<< "$setting")"
              literal_value="$(jq -r '.value // ""' <<< "$setting")"
              secret_name="$(jq -r '.secretName // ""' <<< "$setting")"
              value="$(resolve_setting "$source" "$target_app_id" "$target_property" "$literal_value" "$secret_name")"
              settings_args+=("$name=$value")
            done < <(jq -c '.settings[]' <<< "$app_config")

            if [ "${#settings_args[@]}" -gt 0 ]; then
              az webapp config appsettings set --resource-group "$AZURE_PROD_RESOURCE_GROUP" --name "$app_name" --settings "${settings_args[@]}" --output none
            fi

            while IFS= read -r setting; do
              name="$(jq -r '.name' <<< "$setting")"
              required="$(jq -r '.required' <<< "$setting")"
              secret="$(jq -r '.secret' <<< "$setting")"
              source="$(jq -r '.source' <<< "$setting")"
              target_app_id="$(jq -r '.targetAppId // ""' <<< "$setting")"
              target_property="$(jq -r '.targetProperty // ""' <<< "$setting")"
              literal_value="$(jq -r '.value // ""' <<< "$setting")"
              secret_name="$(jq -r '.secretName // ""' <<< "$setting")"
              expected="$(resolve_setting "$source" "$target_app_id" "$target_property" "$literal_value" "$secret_name")"
              actual="$(az webapp config appsettings list --resource-group "$AZURE_PROD_RESOURCE_GROUP" --name "$app_name" --query "[?name=='$name'].value | [0]" -o tsv)"
              if [ "$required" = "true" ] && [ -z "$actual" ]; then
                echo "Required deployment setting '$name' is missing for PROD app '$app_id'." >&2
                exit 1
              fi
              if [ "$secret" != "true" ] && [ "$actual" != "$expected" ]; then
                echo "Deployment setting '$name' does not match expected PROD value for app '$app_id'." >&2
                exit 1
              fi
            done < <(jq -c '.settings[]' <<< "$app_config")
          done
        env:
          AZURE_PROD_RESOURCE_GROUP: ${{ secrets.AZURE_PROD_RESOURCE_GROUP }}
          AZURE_PROD_SITE_APP_NAME: ${{ secrets.AZURE_PROD_SITE_APP_NAME }}
          AZURE_PROD_SITE_APP_URL: ${{ secrets.AZURE_PROD_SITE_APP_URL }}
          AZURE_PROD_API_APP_NAME: ${{ secrets.AZURE_PROD_API_APP_NAME }}
          AZURE_PROD_API_APP_URL: ${{ secrets.AZURE_PROD_API_APP_URL }}

      - name: Deploy PROD topology apps
        shell: bash
        run: |
          set -euo pipefail

          jq -c 'sort_by(.deployOrder)' deployable-apps.json |
          jq -r '.[] | [.appId, .artifactName] | @tsv' |
          while IFS=$'\t' read -r app_id artifact_name; do
            app_upper="$(echo "$app_id" | tr '[:lower:]-' '[:upper:]_')"
            name_var="AZURE_PROD_${app_upper}_APP_NAME"
            app_name="${!name_var:-}"
            test -n "$app_name"
            az webapp deploy --resource-group "$AZURE_PROD_RESOURCE_GROUP" --name "$app_name" --src-path "$artifact_name" --type zip --clean true
          done
        env:
          AZURE_PROD_RESOURCE_GROUP: ${{ secrets.AZURE_PROD_RESOURCE_GROUP }}
          AZURE_PROD_SITE_APP_NAME: ${{ secrets.AZURE_PROD_SITE_APP_NAME }}
          AZURE_PROD_API_APP_NAME: ${{ secrets.AZURE_PROD_API_APP_NAME }}

      - name: Smoke check PROD topology apps
        shell: bash
        run: |
          set -euo pipefail

          jq -r '.[] | [.appId, .role, .healthPath] | @tsv' deployable-apps.json |
          while IFS=$'\t' read -r app_id role health_path; do
            app_upper="$(echo "$app_id" | tr '[:lower:]-' '[:upper:]_')"
            url_var="AZURE_PROD_${app_upper}_APP_URL"
            app_url="${!url_var:-}"
            test -n "$app_url"
            if [ "$role" = "web" ]; then
              curl --fail --silent --show-error --location "$app_url" -o response.html
              grep -q "<title>SDD Template</title>" response.html
              ! grep -qi "Microsoft Azure" response.html
              expected_api_url="${AZURE_PROD_API_APP_URL:-}"
              test -n "$expected_api_url"
              curl --fail --silent --show-error --location "${app_url}/clients" -o clients.html
              grep -q "const apiBaseUrl = \"${expected_api_url}\";" clients.html
            fi
            if [ "$role" = "api" ]; then
              site_origin="${AZURE_PROD_SITE_APP_URL:-}"
              test -n "$site_origin"
              curl --fail --silent --show-error --request OPTIONS \
                --header "Origin: $site_origin" \
                --header "Access-Control-Request-Method: POST" \
                --header "Access-Control-Request-Headers: content-type" \
                --dump-header cors.headers \
                --output /dev/null \
                "${app_url}/api/clients"
              grep -iq "^Access-Control-Allow-Origin: ${site_origin}" cors.headers
            fi
            curl --fail --silent --show-error --location "${app_url}${health_path}" -o health.json
            grep -q '"status":"ok"' health.json
          done
        env:
          AZURE_PROD_SITE_APP_URL: ${{ secrets.AZURE_PROD_SITE_APP_URL }}
          AZURE_PROD_API_APP_URL: ${{ secrets.AZURE_PROD_API_APP_URL }}
'@

  Write-TemplateFile $result ".gitea/workflows/README.md" @'
# Gitea Actions Quality Gates

Gitea PR validation is the source of truth. Local hooks are only convenience checks for staged secrets and commit-message shape.

Coverage threshold defaults to `80%` from `.codex/quality.example.json`. Local development may override it with ignored `.codex/quality.local.json`; CI falls back to the tracked example when no local config is present.

The local runner executes PR validation inside a pinned .NET SDK container. PR validation must target product/application projects specifically for restore, format, build, tests, coverage, and dependency audit. For this template, CI uses explicit `src/SDDTemplate.Site`, `src/SDDTemplate.Api`, and `tests/SDDTemplate.Site.Tests` project paths; SDD delivery-tool, workflow, agent, OpenSpec, infrastructure, and meta-tests remain local/template-maintenance checks and are not part of normal PR CI. Keep checkout and security tools shell-based unless the job container explicitly includes `node`; JavaScript `uses:` actions can fail inside plain SDK containers. Validate runner compatibility after workflow changes:

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
- `AZURE_DEV_SITE_APP_NAME`
- `AZURE_DEV_SITE_APP_URL`
- `AZURE_DEV_API_APP_NAME`
- `AZURE_DEV_API_APP_URL`
- `AZURE_QA_RESOURCE_GROUP`
- `AZURE_QA_SITE_APP_NAME`
- `AZURE_QA_SITE_APP_URL`
- `AZURE_QA_API_APP_NAME`
- `AZURE_QA_API_APP_URL`
- `AZURE_PROD_RESOURCE_GROUP`
- `AZURE_PROD_SITE_APP_NAME`
- `AZURE_PROD_SITE_APP_URL`
- `AZURE_PROD_API_APP_NAME`
- `AZURE_PROD_API_APP_URL`

Push-triggered deployments are ticket-gated by `.codex/delivery-policy.json`. Only commits or merged PR titles that start with the configured ticket key pattern may deploy, and automatic CI/deployment work is skipped when the change does not touch `src/**` or `tests/**`.

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
feature branch -> dev -> DEV -> QA -> Gitea E2E evidence -> Plane E2E QA -> main -> PROD
```

The package workflow reads `infra/deployment/apps.json`, rejects deployable project paths outside `src/`, builds one ZIP per deployable app, builds `deployment-config.json` from `infra/deployment/configuration.json` plus each app's `appsettings*.json`, and publishes from ticket-gated application changes on `dev`, including `app/{commitSha}/deployable-apps.json`, `app/{commitSha}/deployment-config.json`, per-app ZIP/checksum files, and a baseline `app/{commitSha}/release.json`. DEV, QA, and PROD must apply and verify deployment configuration before deployment success is claimed. Smoke checks also verify that the clients page renders the expected API base URL and that API CORS preflight allows the matching web origin. DEV and QA must deploy the same Nexus app artifacts for the same commit SHA. After QA deploy and smoke checks, push a `qa/{ticketKey}` branch from current `dev`; the `e2e-qa-branch` job runs the committed Playwright suite against the deployed QA Site/API URLs without redeploying, resolves the artifact commit from the branch point with `dev`, and uploads `app/{commitSha}/qa-e2e-evidence.zip` plus a ticket/run evidence copy under `qa/{ticketKey}/{runId}/qa-e2e-evidence.zip`. This Gitea job is evidence-only; the `test-e2e` skill remains responsible for acceptance-to-assertion QA proof, Plane Done state, RC tagging, release manifest QA lineage, and deleting the remote `qa/{ticketKey}` branch after durable Nexus/Plane/release/tag evidence exists. Only full `PASS` can move Plane to Done; `PASS WITH GAPS` or `FAIL` remain in QA. PROD is an explicit release event that may include one or more Done tickets through `release.json.includedTickets`; it must deploy the QA-approved Nexus app artifacts from an exact-commit `main` promotion or explicit dispatch by commit SHA, pass deployment configuration verification, rendered API base URL validation, CORS preflight validation, the web page smoke check, and every app `/health` check, then record the PROD result on every included ticket.
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
    $config = Get-Content -Path $target -Raw | ConvertFrom-Json
  } else {
    $source = Join-RootPath ".codex/quality.example.json"
    if (-not (Test-Path $source)) {
      throw "Missing .codex/quality.example.json. Run -Mode InitQualityGateTemplates first."
    }
    $config = Get-Content -Path $source -Raw | ConvertFrom-Json
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
  return $result
}

function Invoke-SyncWorktreeLocalConfig {
  $result = New-Result
  $worktreePaths = @(Get-SyncTargetWorktreePaths)
  if ($worktreePaths.Count -eq 0) {
    Add-Item $result "findings" "git worktree" "" "No ticket worktrees were found. Provide ValuesJson with worktreePaths or create/reuse ticket worktrees first." "warning"
    return $result
  }

  foreach ($file in @(Get-WorktreeLocalConfigFiles)) {
    $relativePath = [string]$file.relativePath
    $sourcePath = Join-RootPath $relativePath
    if (-not (Test-Path -LiteralPath $sourcePath)) {
      if ([bool]$file.required) {
        Add-Item $result "findings" $relativePath "" "Coordinator checkout is missing required local runtime file '$relativePath'. Run InitLocalFiles and SetClientTools before syncing ticket worktrees." "error"
      } else {
        Add-Item $result "findings" $relativePath "" "Optional local runtime file '$relativePath' is not present in the coordinator checkout; skipping it." "info"
      }
    }
  }

  foreach ($worktreePath in $worktreePaths) {
    $displayPath = Get-DisplayPath $worktreePath
    if (-not (Test-Path -LiteralPath $worktreePath -PathType Container)) {
      Add-Item $result "findings" $displayPath "worktreePath" "Ticket worktree path does not exist; create or repair the worktree before syncing local config." "error"
      continue
    }

    foreach ($file in @(Get-WorktreeLocalConfigFiles)) {
      $relativePath = [string]$file.relativePath
      $sourcePath = Join-RootPath $relativePath
      if (-not (Test-Path -LiteralPath $sourcePath)) { continue }

      $targetPath = Join-Path $worktreePath $relativePath
      $targetDirectory = Split-Path -Parent $targetPath
      if (Test-Path -LiteralPath $targetPath) {
        $sourceHash = Get-FileSha256 $sourcePath
        $targetHash = Get-FileSha256 $targetPath
        if ($sourceHash -eq $targetHash) {
          Add-Item $result "findings" $displayPath $relativePath "Allowlisted local runtime file is already synced." "info"
          continue
        }

        Add-Item $result "actions" $displayPath $relativePath "Overwrite allowlisted local runtime file from coordinator checkout."
      } else {
        Add-Item $result "actions" $displayPath $relativePath "Copy allowlisted local runtime file from coordinator checkout."
      }

      if (Test-ConfigWritesEnabled) {
        if (-not (Test-Path -LiteralPath $targetDirectory)) {
          New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
        }
        Copy-Item -Path $sourcePath -Destination $targetPath -Force
      }
    }
  }

  return $result
}

function Invoke-EnsureDeliveryContext {
  $result = New-Result
  $targetRelative = ".codex/delivery-context.local.json"
  $target = Join-RootPath $targetRelative
  $values = Convert-JsonToHashtable $ValuesJson

  if (-not $values.Contains("ticketKey") -or [string]::IsNullOrWhiteSpace([string]$values.ticketKey)) {
    throw "ValuesJson must include ticketKey for EnsureDeliveryContext."
  }

  $ticketKey = [string]$values.ticketKey
  $branch = if ($values.Contains("branch")) { [string]$values.branch } else { Get-CurrentGitBranch }
  if ([string]::IsNullOrWhiteSpace($branch)) {
    throw "ValuesJson must include branch when the current Git branch cannot be inferred."
  }

  $openspecChange = if ($values.Contains("openspecChange")) { [string]$values.openspecChange } else { Get-InferredOpenSpecChange $branch }
  $replaceExisting = $values.Contains("replaceExisting") -and [bool]$values.replaceExisting

  if (Test-Path -LiteralPath $target) {
    try {
      $existing = Get-Content -Path $target -Raw | ConvertFrom-Json
      $existingTicket = [string]$existing.ticketKey
      if (-not [string]::IsNullOrWhiteSpace($existingTicket) -and $existingTicket -ne $ticketKey -and -not $replaceExisting) {
        throw "Existing $targetRelative points to '$existingTicket'. Pass replaceExisting=true only after plane-start-ticket confirms '$existingTicket' is in the configured Done state, or after explicit operator confirmation for a known-safe repair to '$ticketKey'."
      }
    } catch {
      if (-not $replaceExisting) {
        throw
      }
    }
  }

  $context = [ordered]@{
    ticketKey = $ticketKey
    branch = $branch
  }
  if (-not [string]::IsNullOrWhiteSpace($openspecChange)) {
    $context["openspecChange"] = $openspecChange
  }
  foreach ($optionalKey in @("prNumber", "artifactCommitSha", "sourceRcVersion", "finalReleaseVersion")) {
    if ($values.Contains($optionalKey) -and -not [string]::IsNullOrWhiteSpace([string]$values[$optionalKey])) {
      $context[$optionalKey] = $values[$optionalKey]
    }
  }

  Add-Item $result "actions" $targetRelative "" "Create or update ticket context lock for '$ticketKey' without copying another worktree's lock."
  if (Test-ConfigWritesEnabled) {
    $targetDirectory = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $targetDirectory)) {
      New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
    }
    ([pscustomobject]$context) | ConvertTo-Json -Depth 10 | Set-Content -Path $target -Encoding UTF8
  }
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
  $config = Get-Content -Path $target -Raw | ConvertFrom-Json
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

function New-AzureMonitorLogDashboard {
  param(
    [string]$EnvironmentName,
    [string]$WorkspaceResourceId
  )

  $upper = $EnvironmentName.ToUpperInvariant()
  $kql = @"
union isfuzzy=true AppServiceConsoleLogs, AppServiceAppLogs, AppServiceHTTPLogs, AppServicePlatformLogs, AppServiceAuditLogs, AppServiceIPSecAuditLogs, AppServiceAuthenticationLogs
| where TimeGenerated >= ago(6h)
| extend Category = tostring(column_ifexists("Category", ""))
| extend Message = coalesce(tostring(column_ifexists("Message", "")), tostring(column_ifexists("Details", "")), tostring(column_ifexists("ResultDescription", "")), tostring(column_ifexists("CsUriStem", "")))
| project TimeGenerated, Category, ResourceId = tostring(column_ifexists("_ResourceId", "")), Message
| order by TimeGenerated desc
| take 200
"@

  $activityKql = @"
union isfuzzy=true AppServiceConsoleLogs, AppServiceAppLogs, AppServiceHTTPLogs, AppServicePlatformLogs, AppServiceAuditLogs, AppServiceIPSecAuditLogs, AppServiceAuthenticationLogs
| where TimeGenerated >= ago(6h)
| summarize Count = count() by bin(TimeGenerated, 5m), ResourceId = tostring(column_ifexists("_ResourceId", ""))
| order by TimeGenerated asc
"@

  $healthKql = @"
AppServiceHTTPLogs
| where TimeGenerated >= ago(6h)
| extend Path = tostring(column_ifexists("CsUriStem", ""))
| where Path == "/health" or Path endswith "/health"
| extend StatusCode = toint(column_ifexists("ScStatus", int(null)))
| summarize Checks = count(), Failures = countif(StatusCode < 200 or StatusCode >= 300) by bin(TimeGenerated, 5m), ResourceId = tostring(column_ifexists("_ResourceId", ""))
| extend Healthy = Checks - Failures
| order by TimeGenerated asc
"@

  $recentHealthKql = @"
AppServiceHTTPLogs
| where TimeGenerated >= ago(6h)
| extend Path = tostring(column_ifexists("CsUriStem", ""))
| where Path == "/health" or Path endswith "/health"
| extend StatusCode = toint(column_ifexists("ScStatus", int(null)))
| project TimeGenerated, ResourceId = tostring(column_ifexists("_ResourceId", "")), Path, StatusCode, Method = tostring(column_ifexists("CsMethod", "")), UserAgent = tostring(column_ifexists("UserAgent", ""))
| order by TimeGenerated desc
| take 100
"@

  $dashboard = [ordered]@{
    annotations = [ordered]@{
      list = @(
        [ordered]@{
          builtIn = 1
          datasource = [ordered]@{ type = "grafana"; uid = "-- Grafana --" }
          enable = $true
          hide = $true
          iconColor = "rgba(0, 211, 255, 1)"
          name = "Annotations & Alerts"
          type = "dashboard"
        }
      )
    }
    editable = $true
    fiscalYearStartMonth = 0
    graphTooltip = 0
    id = $null
    links = @()
    liveNow = $false
    panels = @(
      [ordered]@{
        datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
        fieldConfig = [ordered]@{ defaults = [ordered]@{}; overrides = @() }
        gridPos = [ordered]@{ h = 8; w = 24; x = 0; y = 0 }
        id = 1
        options = [ordered]@{
          legend = [ordered]@{ displayMode = "list"; placement = "bottom"; showLegend = $true }
          tooltip = [ordered]@{ mode = "single"; sort = "none" }
        }
        targets = @(
          [ordered]@{
            azureLogAnalytics = [ordered]@{
              query = $activityKql
              resources = @($WorkspaceResourceId)
              resultFormat = "time_series"
            }
            datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
            queryType = "Azure Log Analytics"
            refId = "A"
          }
        )
        title = "$upper Azure Log Activity"
        type = "timeseries"
      },
      [ordered]@{
        datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
        fieldConfig = [ordered]@{ defaults = [ordered]@{}; overrides = @() }
        gridPos = [ordered]@{ h = 8; w = 24; x = 0; y = 8 }
        id = 2
        options = [ordered]@{
          legend = [ordered]@{ displayMode = "list"; placement = "bottom"; showLegend = $true }
          tooltip = [ordered]@{ mode = "single"; sort = "none" }
        }
        targets = @(
          [ordered]@{
            azureLogAnalytics = [ordered]@{
              query = $healthKql
              resources = @($WorkspaceResourceId)
              resultFormat = "time_series"
            }
            datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
            queryType = "Azure Log Analytics"
            refId = "A"
          }
        )
        title = "$upper App Service Health"
        type = "timeseries"
      },
      [ordered]@{
        datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
        fieldConfig = [ordered]@{ defaults = [ordered]@{}; overrides = @() }
        gridPos = [ordered]@{ h = 8; w = 24; x = 0; y = 16 }
        id = 3
        options = [ordered]@{
          cellHeight = "sm"
          footer = [ordered]@{ countRows = $false; fields = ""; reducer = @("sum"); show = $false }
          showHeader = $true
        }
        targets = @(
          [ordered]@{
            azureLogAnalytics = [ordered]@{
              query = $recentHealthKql
              resources = @($WorkspaceResourceId)
              resultFormat = "table"
            }
            datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
            queryType = "Azure Log Analytics"
            refId = "A"
          }
        )
        title = "$upper Recent Health Checks"
        type = "table"
      },
      [ordered]@{
        datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
        fieldConfig = [ordered]@{ defaults = [ordered]@{}; overrides = @() }
        gridPos = [ordered]@{ h = 10; w = 24; x = 0; y = 24 }
        id = 4
        options = [ordered]@{
          cellHeight = "sm"
          footer = [ordered]@{ countRows = $false; fields = ""; reducer = @("sum"); show = $false }
          showHeader = $true
        }
        targets = @(
          [ordered]@{
            azureLogAnalytics = [ordered]@{
              query = $kql
              resources = @($WorkspaceResourceId)
              resultFormat = "table"
            }
            datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
            queryType = "Azure Log Analytics"
            refId = "A"
          }
        )
        title = "$upper Azure Logs"
        type = "table"
      }
    )
    refresh = "30s"
    schemaVersion = 41
    tags = @("agentic-e2e", "azure", "logs", $EnvironmentName)
    templating = [ordered]@{ list = @() }
    time = [ordered]@{ from = "now-6h"; to = "now" }
    timepicker = [ordered]@{}
    timezone = "browser"
    title = "$upper Azure Monitor"
    uid = "agentic-$EnvironmentName-azure-monitor"
    version = 1
    weekStart = ""
  }

  return ($dashboard | ConvertTo-Json -Depth 30)
}

function New-AzureMonitorHealthDashboard {
  param(
    [string]$EnvironmentName,
    [string]$WorkspaceResourceId
  )

  $upper = $EnvironmentName.ToUpperInvariant()
  $healthKql = @"
AppServiceHTTPLogs
| where TimeGenerated >= ago(7d)
| extend Path = tostring(CsUriStem)
| where Path == '/health' or Path endswith '/health'
| extend StatusCode = toint(column_ifexists("ScStatus", int(null)))
| summarize Checks = count(), Failures = countif(StatusCode < 200 or StatusCode >= 300) by bin(TimeGenerated, 5m), ResourceId = tostring(column_ifexists("_ResourceId", ""))
| extend Healthy = Checks - Failures
| order by TimeGenerated asc
"@

  $recentHealthKql = @"
AppServiceHTTPLogs
| where TimeGenerated >= ago(7d)
| extend Path = tostring(CsUriStem)
| where Path == '/health' or Path endswith '/health'
| extend StatusCode = toint(column_ifexists("ScStatus", int(null)))
| extend Result = iff(StatusCode >= 200 and StatusCode < 300, "ok", "failed")
| project TimeGenerated, Result, StatusCode, ResourceId = tostring(column_ifexists("_ResourceId", "")), Path, Method = tostring(column_ifexists("CsMethod", "")), UserAgent = tostring(column_ifexists("UserAgent", ""))
| order by TimeGenerated desc
| take 200
"@

  $webStatusKql = @"
AppServiceHTTPLogs
| where TimeGenerated >= ago(7d)
| where CsUriStem == '/health' or CsUriStem endswith '/health'
| where CsHost contains 'web'
| extend StatusCode = toint(ScStatus)
| top 1 by TimeGenerated desc
| extend Value = iff(StatusCode >= 200 and StatusCode < 300 and TimeGenerated >= ago(24h), 1, 0)
| project TimeGenerated = now(), Value
"@

  $apiStatusKql = @"
AppServiceHTTPLogs
| where TimeGenerated >= ago(7d)
| where CsUriStem == '/health' or CsUriStem endswith '/health'
| where CsHost contains 'api'
| extend StatusCode = toint(ScStatus)
| top 1 by TimeGenerated desc
| extend Value = iff(StatusCode >= 200 and StatusCode < 300 and TimeGenerated >= ago(24h), 1, 0)
| project TimeGenerated = now(), Value
"@

  $dashboard = [ordered]@{
    annotations = [ordered]@{
      list = @(
        [ordered]@{
          builtIn = 1
          datasource = [ordered]@{ type = "grafana"; uid = "-- Grafana --" }
          enable = $true
          hide = $true
          iconColor = "rgba(0, 211, 255, 1)"
          name = "Annotations & Alerts"
          type = "dashboard"
        }
      )
    }
    editable = $true
    fiscalYearStartMonth = 0
    graphTooltip = 0
    id = $null
    links = @()
    liveNow = $false
    panels = @(
      [ordered]@{
        datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
        fieldConfig = [ordered]@{
          defaults = [ordered]@{
            color = [ordered]@{ mode = "thresholds" }
            mappings = @(
              [ordered]@{ options = [ordered]@{ "0" = [ordered]@{ color = "red"; text = "FAIL/STALE" }; "1" = [ordered]@{ color = "green"; text = "OK" } }; type = "value" }
            )
            thresholds = [ordered]@{ mode = "absolute"; steps = @([ordered]@{ color = "red"; value = $null }, [ordered]@{ color = "green"; value = 1 }) }
          }
          overrides = @()
        }
        gridPos = [ordered]@{ h = 8; w = 12; x = 0; y = 0 }
        id = 1
        options = [ordered]@{
          colorMode = "background"
          graphMode = "none"
          justifyMode = "center"
          orientation = "auto"
          reduceOptions = [ordered]@{ calcs = @("lastNotNull"); fields = ""; values = $false }
          textMode = "value_and_name"
          wideLayout = $true
        }
        targets = @(
          [ordered]@{
            azureLogAnalytics = [ordered]@{
              query = $webStatusKql
              resources = @($WorkspaceResourceId)
              resultFormat = "time_series"
            }
            datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
            queryType = "Azure Log Analytics"
            refId = "A"
          }
        )
        title = "$upper Web /health"
        type = "stat"
      },
      [ordered]@{
        datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
        fieldConfig = [ordered]@{
          defaults = [ordered]@{
            color = [ordered]@{ mode = "thresholds" }
            mappings = @(
              [ordered]@{ options = [ordered]@{ "0" = [ordered]@{ color = "red"; text = "FAIL/STALE" }; "1" = [ordered]@{ color = "green"; text = "OK" } }; type = "value" }
            )
            thresholds = [ordered]@{ mode = "absolute"; steps = @([ordered]@{ color = "red"; value = $null }, [ordered]@{ color = "green"; value = 1 }) }
          }
          overrides = @()
        }
        gridPos = [ordered]@{ h = 8; w = 12; x = 12; y = 0 }
        id = 2
        options = [ordered]@{
          colorMode = "background"
          graphMode = "none"
          justifyMode = "center"
          orientation = "auto"
          reduceOptions = [ordered]@{ calcs = @("lastNotNull"); fields = ""; values = $false }
          textMode = "value_and_name"
          wideLayout = $true
        }
        targets = @(
          [ordered]@{
            azureLogAnalytics = [ordered]@{
              query = $apiStatusKql
              resources = @($WorkspaceResourceId)
              resultFormat = "time_series"
            }
            datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
            queryType = "Azure Log Analytics"
            refId = "A"
          }
        )
        title = "$upper API /health"
        type = "stat"
      },
      [ordered]@{
        datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
        fieldConfig = [ordered]@{ defaults = [ordered]@{}; overrides = @() }
        gridPos = [ordered]@{ h = 12; w = 24; x = 0; y = 8 }
        id = 3
        options = [ordered]@{
          cellHeight = "sm"
          footer = [ordered]@{ countRows = $false; fields = ""; reducer = @("sum"); show = $false }
          showHeader = $true
        }
        targets = @(
          [ordered]@{
            azureLogAnalytics = [ordered]@{
              query = $recentHealthKql
              resources = @($WorkspaceResourceId)
              resultFormat = "table"
            }
            datasource = [ordered]@{ type = "grafana-azure-monitor-datasource"; uid = "azure-monitor" }
            queryType = "Azure Log Analytics"
            refId = "A"
          }
        )
        title = "$upper Recent /health Requests"
        type = "table"
      }
    )
    refresh = "30s"
    schemaVersion = 41
    tags = @("agentic-e2e", "azure", "health", $EnvironmentName)
    templating = [ordered]@{ list = @() }
    time = [ordered]@{ from = "now-7d"; to = "now" }
    timepicker = [ordered]@{}
    timezone = "browser"
    title = "$upper Health Dashboard"
    uid = "agentic-$EnvironmentName-health"
    version = 1
    weekStart = ""
  }

  return ($dashboard | ConvertTo-Json -Depth 30)
}

function Invoke-SetGrafanaAzureMonitor {
  $result = New-Result
  $targetRelative = "infra/plane/variables.env"
  $target = Join-RootPath $targetRelative
  if (-not (Test-Path $target)) {
    throw "Missing $targetRelative. Run -Mode InitLocalFiles first."
  }

  $values = Convert-JsonToHashtable $ValuesJson
  $servicePrincipalName = "sp-agentic-e2e-grafana-monitor"
  if ($values.Contains("servicePrincipalName") -and -not [string]::IsNullOrWhiteSpace($values["servicePrincipalName"])) {
    $servicePrincipalName = [string]$values["servicePrincipalName"]
  }

  $account = Invoke-AzJson @("account", "show")
  Add-Item $result "actions" "az" "account" "Resolved Azure subscription '$($account.name)' and tenant '$($account.tenantId)'."

  $envValues = @{}
  $workspaceIds = @()
  foreach ($environment in Get-AgenticEnvironmentResourceGroups) {
    $envName = $environment.env
    $resourceGroup = $environment.resourceGroup
    $prefix = "law-agentice2e-$envName-"
    $workspaces = ConvertTo-Array (Invoke-AzJson @("monitor", "log-analytics", "workspace", "list", "--resource-group", $resourceGroup))
    $workspace = @($workspaces | Where-Object { $_.name -like "$prefix*" } | Sort-Object name | Select-Object -First 1)
    if ($workspace.Count -eq 0) {
      throw "No Log Analytics workspace matching '$prefix*' found in '$resourceGroup'. Run infra/azure/deploy-environments.ps1 first."
    }

    $workspaceName = $workspace[0].name
    $workspaceResourceId = [string]$workspace[0].id
    $workspaceCustomerId = Invoke-AzTsv @("monitor", "log-analytics", "workspace", "show", "--resource-group", $resourceGroup, "--workspace-name", $workspaceName, "--query", "customerId")
    $upper = $envName.ToUpperInvariant()
    $envValues["GRAFANA_AZURE_${upper}_LOG_ANALYTICS_WORKSPACE_ID"] = $workspaceCustomerId
    $envValues["GRAFANA_AZURE_${upper}_LOG_ANALYTICS_WORKSPACE_RESOURCE_ID"] = $workspaceResourceId
    $workspaceIds += $workspaceResourceId
    Add-Item $result "actions" "azure-log-analytics" $workspaceName "Resolved $envName Log Analytics workspace."

    $webApps = ConvertTo-Array (Invoke-AzJson @("webapp", "list", "--resource-group", $resourceGroup))
    foreach ($app in @($webApps | Where-Object { $_.name -like "app-agentice2e-$envName-*" })) {
      $settings = ConvertTo-Array (Invoke-AzJson @("monitor", "diagnostic-settings", "list", "--resource", $app.id))
      $matchingSettings = @($settings | Where-Object { $_.name -eq "send-appservice-logs-to-log-analytics" -and $_.workspaceId -eq $workspaceResourceId })
      if ($matchingSettings.Count -gt 0) {
        Add-Item $result "actions" "azure-diagnostic-settings" $app.name "Diagnostic setting for Azure Monitor Logs exists."
      } else {
        Add-Item $result "findings" "azure-diagnostic-settings" $app.name "Missing App Service diagnostic setting for Azure Monitor Logs." "warning" "post-start"
      }
    }

    $dashboardDirectory = Join-RootPath "infra/monitoring/grafana/dashboards.local"
    if (-not $DryRun -and -not (Test-Path $dashboardDirectory)) {
      New-Item -ItemType Directory -Path $dashboardDirectory -Force | Out-Null
    }
    $dashboardPath = Join-Path $dashboardDirectory "$envName-azure-monitor.json"
    Add-Item $result "actions" "infra/monitoring/grafana/dashboards.local/$envName-azure-monitor.json" "" "Generate local Grafana Azure Monitor dashboard."
    if (-not $DryRun) {
      New-AzureMonitorLogDashboard -EnvironmentName $envName -WorkspaceResourceId $workspaceResourceId | Set-Content -Path $dashboardPath -Encoding UTF8
    }

    $healthDashboardPath = Join-Path $dashboardDirectory "$envName-health-dashboard.json"
    Add-Item $result "actions" "infra/monitoring/grafana/dashboards.local/$envName-health-dashboard.json" "" "Generate local Grafana health dashboard."
    if (-not $DryRun) {
      New-AzureMonitorHealthDashboard -EnvironmentName $envName -WorkspaceResourceId $workspaceResourceId | Set-Content -Path $healthDashboardPath -Encoding UTF8
    }
  }

  $servicePrincipals = ConvertTo-Array (Invoke-AzJson @("ad", "sp", "list", "--display-name", $servicePrincipalName))
  if ($servicePrincipals.Count -gt 0) {
    $appId = $servicePrincipals[0].appId
    $credential = Invoke-AzJson @("ad", "sp", "credential", "reset", "--id", $appId, "--append", "--display-name", "grafana-azure-monitor-local", "--years", "1")
    Add-Item $result "actions" "azure-ad" $servicePrincipalName "Reused service principal and created a local-only Grafana Azure Monitor client secret."
  } else {
    $credential = Invoke-AzJson @("ad", "sp", "create-for-rbac", "--name", $servicePrincipalName, "--skip-assignment")
    $appId = $credential.appId
    Add-Item $result "actions" "azure-ad" $servicePrincipalName "Created service principal for Grafana Azure Monitor."
  }

  foreach ($scope in @($workspaceIds)) {
    foreach ($role in @("Reader", "Log Analytics Reader")) {
      $assignments = ConvertTo-Array (Invoke-AzJson @("role", "assignment", "list", "--assignee", $appId, "--scope", $scope, "--role", $role))
      if ($assignments.Count -eq 0) {
        $null = Invoke-AzJson @("role", "assignment", "create", "--assignee", $appId, "--scope", $scope, "--role", $role)
        Add-Item $result "actions" "azure-rbac" $role "Assigned Grafana service principal to Log Analytics workspace scope."
      } else {
        Add-Item $result "actions" "azure-rbac" $role "Grafana service principal already has role on Log Analytics workspace scope."
      }
    }
  }

  $envValues["GRAFANA_AZURE_CLIENT_ID"] = $appId
  $envValues["GRAFANA_AZURE_TENANT_ID"] = $account.tenantId
  $envValues["GRAFANA_AZURE_CLIENT_SECRET"] = $credential.password
  $envValues["GRAFANA_AZURE_SUBSCRIPTION_ID"] = $account.id

  Set-EnvValues -Path $target -Values $envValues
  foreach ($key in $envValues.Keys) {
    Add-Item $result "actions" $targetRelative $key "Set Grafana Azure Monitor value."
  }

  return $result
}

switch ($Mode) {
  "Audit" { $result = Invoke-Audit }
  "AuditQualityGates" { $result = Invoke-AuditQualityGates }
  "AuditRecommendedTools" { $result = Invoke-AuditRecommendedTools }
  "DiscoverProjectGuidance" { $result = Invoke-DiscoverProjectGuidance }
  "AcquireProjectGuidance" { $result = Invoke-AcquireProjectGuidance }
  "ValidateGiteaActionsRunner" { $result = Invoke-ValidateGiteaActionsRunner }
  "InitLocalFiles" { $result = Invoke-InitLocalFiles }
  "InitQualityGateTemplates" { $result = Invoke-InitQualityGateTemplates }
  "SetClientTools" { $result = Invoke-SetClientTools }
  "SetRecommendedTools" { $result = Invoke-SetRecommendedTools }
  "MapProjectGuidanceStep" { $result = Invoke-MapProjectGuidanceStep }
  "BuildGiteaActionsImages" { $result = Invoke-BuildGiteaActionsImages }
  "SyncWorktreeLocalConfig" { $result = Invoke-SyncWorktreeLocalConfig }
  "EnsureDeliveryContext" { $result = Invoke-EnsureDeliveryContext }
  "SetPlaneEnv" { $result = Invoke-SetEnvMode -TargetRelative "infra/plane/variables.env" }
  "SetGiteaRunner" { $result = Invoke-SetEnvMode -TargetRelative "infra/gitea/runner.env" }
  "SetGrafanaAzureMonitor" { $result = Invoke-SetGrafanaAzureMonitor }
  "SetQualityConfig" { $result = Invoke-SetQualityConfig }
}

$result | ConvertTo-Json -Depth 10
