param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('ArtifactPaths', 'CheckGitIgnored', 'NextRcVersion', 'ReadDeliveryPolicy', 'ExtractTicketKey', 'ReadCoverageThreshold', 'ReadCoberturaLineRate', 'ValidateReleaseManifest', 'ValidateTicketLock', 'ValidateDeploymentLane', 'ValidateParallelDeliveryDryRun', 'RenderPlaneComment', 'UpdateReleaseManifest')]
  [string] $Mode,

  [string] $CommitSha,
  [string] $Path,
  [string] $TargetVersion,
  [string] $TicketKey,
  [string] $Branch,
  [string] $PrNumber,
  [string] $ArtifactCommitSha,
  [string] $SourceRcVersion,
  [string] $FinalReleaseVersion,
  [string] $Stage,
  [string] $Type,
  [string] $Message,
  [int] $FallbackCoverageMinimum = 80,
  [string] $FallbackTicketKey,
  [string] $InputJson,
  [string] $RepoRoot = (Get-Location).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Json($Value) {
  $Value | ConvertTo-Json -Depth 20
}

function Get-ObjectProperty($Object, [string] $Name) {
  if ($null -eq $Object) {
    return $null
  }
  if ($Object.PSObject.Properties.Name -contains $Name) {
    return $Object.$Name
  }
  return $null
}

function Test-ExpectedValue([System.Collections.Generic.List[string]] $Errors, [string] $Name, $Actual, [string] $Expected) {
  if ([string]::IsNullOrWhiteSpace($Expected)) {
    return
  }
  if ([string]::IsNullOrWhiteSpace([string]$Actual)) {
    $Errors.Add("$Name is missing from the lock.")
    return
  }
  if ([string]$Actual -ne $Expected) {
    $Errors.Add("$Name mismatch: lock has '$Actual', expected '$Expected'.")
  }
}

function Get-ArtifactPaths([string] $Sha) {
  if ([string]::IsNullOrWhiteSpace($Sha)) {
    throw 'CommitSha is required for ArtifactPaths.'
  }

  [pscustomobject]@{
    appZip = "app/$Sha/app.zip"
    checksum = "app/$Sha/app.zip.sha256"
    commitMetadata = "app/$Sha/commit.sha"
    releaseManifest = "app/$Sha/release.json"
  }
}

function Test-GitIgnored([string] $CandidatePath) {
  if ([string]::IsNullOrWhiteSpace($CandidatePath)) {
    throw 'Path is required for CheckGitIgnored.'
  }

  Push-Location $RepoRoot
  try {
    $output = & git check-ignore -q -- "$CandidatePath" 2>$null
    $ignored = $LASTEXITCODE -eq 0
    [pscustomobject]@{
      path = $CandidatePath
      ignored = $ignored
    }
  }
  finally {
    Pop-Location
  }
}

function Get-NextRcVersion([string] $RequestedTargetVersion) {
  Push-Location $RepoRoot
  try {
    $tags = @(& git tag --list 'v[0-9]*.[0-9]*.[0-9]*' 2>$null)
    $finalVersions = @()
    $rcVersions = @()

    foreach ($tag in $tags) {
      if ($tag -match '^v(\d+)\.(\d+)\.(\d+)$') {
        $finalVersions += [pscustomobject]@{
          tag = $tag
          major = [int]$Matches[1]
          minor = [int]$Matches[2]
          patch = [int]$Matches[3]
        }
      }
      elseif ($tag -match '^v(\d+)\.(\d+)\.(\d+)-rc\.(\d+)$') {
        $rcVersions += [pscustomobject]@{
          tag = $tag
          major = [int]$Matches[1]
          minor = [int]$Matches[2]
          patch = [int]$Matches[3]
          rc = [int]$Matches[4]
        }
      }
    }

    if (-not [string]::IsNullOrWhiteSpace($RequestedTargetVersion)) {
      if ($RequestedTargetVersion -notmatch '^v(\d+)\.(\d+)\.(\d+)$') {
        throw 'TargetVersion must use vMAJOR.MINOR.PATCH.'
      }
      $major = [int]$Matches[1]
      $minor = [int]$Matches[2]
      $patch = [int]$Matches[3]
    }
    elseif ($finalVersions.Count -gt 0) {
      $latest = $finalVersions | Sort-Object major, minor, patch | Select-Object -Last 1
      $major = $latest.major
      $minor = $latest.minor
      $patch = $latest.patch + 1
    }
    else {
      $major = 0
      $minor = 1
      $patch = 0
    }

    $existing = @($rcVersions | Where-Object {
      $_.major -eq $major -and $_.minor -eq $minor -and $_.patch -eq $patch
    })
    $nextRc = 1
    if ($existing.Count -gt 0) {
      $nextRc = (($existing | Measure-Object -Property rc -Maximum).Maximum + 1)
    }

    [pscustomobject]@{
      targetVersion = "v$major.$minor.$patch"
      nextRcVersion = "v$major.$minor.$patch-rc.$nextRc"
    }
  }
  finally {
    Pop-Location
  }
}

function Test-ReleaseManifest([string] $ManifestPath) {
  if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    throw 'Path is required for ValidateReleaseManifest.'
  }
  if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "Release manifest not found: $ManifestPath"
  }

  $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
  $missing = @()
  foreach ($field in @('schemaVersion', 'commitSha', 'checksum', 'artifactUrl', 'planeTicketKey', 'versionStatus')) {
    if (-not ($manifest.PSObject.Properties.Name -contains $field) -or [string]::IsNullOrWhiteSpace([string]$manifest.$field)) {
      $missing += $field
    }
  }

  $errors = @()
  if ($missing.Count -gt 0) {
    $errors += "Missing required fields: $($missing -join ', ')"
  }
  if (($manifest.PSObject.Properties.Name -contains 'commitSha') -and $manifest.commitSha -notmatch '^[0-9a-fA-F]{7,40}$') {
    $errors += 'commitSha must be 7 to 40 hex characters.'
  }
  if (($manifest.PSObject.Properties.Name -contains 'sourceRcVersion') -and $manifest.sourceRcVersion -and $manifest.sourceRcVersion -notmatch '^v[0-9]+\.[0-9]+\.[0-9]+-rc\.[0-9]+$') {
    $errors += 'sourceRcVersion must use vMAJOR.MINOR.PATCH-rc.N.'
  }
  if (($manifest.PSObject.Properties.Name -contains 'finalReleaseVersion') -and $manifest.finalReleaseVersion -and $manifest.finalReleaseVersion -notmatch '^v[0-9]+\.[0-9]+\.[0-9]+$') {
    $errors += 'finalReleaseVersion must use vMAJOR.MINOR.PATCH.'
  }

  [pscustomobject]@{
    path = $ManifestPath
    valid = $errors.Count -eq 0
    errors = $errors
  }
}

function Get-DeliveryPolicy {
  $policyPath = Join-Path $RepoRoot '.codex/delivery-policy.json'
  if (-not (Test-Path -LiteralPath $policyPath)) {
    throw "Delivery policy not found: $policyPath"
  }

  $policy = Get-Content -LiteralPath $policyPath -Raw | ConvertFrom-Json
  $ticketKeyPattern = [string](Get-ObjectProperty $policy 'ticketKeyPattern')
  if ([string]::IsNullOrWhiteSpace($ticketKeyPattern)) {
    throw 'delivery-policy.json must define ticketKeyPattern.'
  }

  [pscustomobject]@{
    path = $policyPath
    ticketKeyPattern = $ticketKeyPattern
  }
}

function Get-ExtractedTicketKey {
  $policy = Get-DeliveryPolicy
  if ([string]::IsNullOrWhiteSpace($Message)) {
    throw 'Message is required for ExtractTicketKey.'
  }

  $firstLine = ($Message -replace "`r`n", "`n").Split("`n")[0]
  $ticketKey = $null
  if ($firstLine -match "^($($policy.ticketKeyPattern)): ") {
    $ticketKey = $Matches[1]
  }
  elseif ($firstLine -match "^Merge pull request '($($policy.ticketKeyPattern)):") {
    $ticketKey = $Matches[1]
  }
  elseif (-not [string]::IsNullOrWhiteSpace($FallbackTicketKey)) {
    $ticketKey = $FallbackTicketKey
  }

  [pscustomobject]@{
    ticketKey = $ticketKey
    matched = -not [string]::IsNullOrWhiteSpace($ticketKey)
    ticketKeyPattern = $policy.ticketKeyPattern
  }
}

function Get-CoverageThreshold {
  $qualityPath = if ([string]::IsNullOrWhiteSpace($Path)) {
    Join-Path $RepoRoot '.codex/quality.local.json'
  } else {
    if ([System.IO.Path]::IsPathRooted($Path)) { $Path } else { Join-Path $RepoRoot $Path }
  }

  if (-not (Test-Path -LiteralPath $qualityPath)) {
    $qualityPath = Join-Path $RepoRoot '.codex/quality.example.json'
  }

  $minimum = $FallbackCoverageMinimum
  if (Test-Path -LiteralPath $qualityPath) {
    $quality = Get-Content -LiteralPath $qualityPath -Raw | ConvertFrom-Json
    $coverage = Get-ObjectProperty $quality 'coverage'
    $configured = Get-ObjectProperty $coverage 'minimumPercent'
    if ($null -ne $configured -and [int]::TryParse([string]$configured, [ref]$minimum)) {
      $minimum = [int]$configured
    }
  }

  [pscustomobject]@{
    path = $qualityPath
    minimumPercent = $minimum
  }
}

function Get-CoberturaLineRate {
  if ([string]::IsNullOrWhiteSpace($Path)) {
    throw 'Path is required for ReadCoberturaLineRate.'
  }
  if (-not (Test-Path -LiteralPath $Path)) {
    throw "Cobertura coverage file not found: $Path"
  }

  [xml]$coverage = Get-Content -LiteralPath $Path -Raw
  $lineRate = [string]$coverage.coverage.'line-rate'
  if ([string]::IsNullOrWhiteSpace($lineRate)) {
    throw "Could not read line-rate from $Path."
  }

  $rate = [decimal]::Parse($lineRate, [System.Globalization.CultureInfo]::InvariantCulture)
  [pscustomobject]@{
    path = $Path
    lineRate = $rate
    percent = [Math]::Round($rate * 100, 2)
  }
}

function Test-TicketLock {
  $lockPath = Join-Path $RepoRoot '.codex/delivery-context.local.json'
  if (-not (Test-Path -LiteralPath $lockPath)) {
    return [pscustomobject]@{
      path = $lockPath
      exists = $false
      valid = $true
      errors = @()
    }
  }

  $lock = Get-Content -LiteralPath $lockPath -Raw | ConvertFrom-Json
  $errors = [System.Collections.Generic.List[string]]::new()

  Test-ExpectedValue $errors 'ticketKey' (Get-ObjectProperty $lock 'ticketKey') $TicketKey
  Test-ExpectedValue $errors 'branch' (Get-ObjectProperty $lock 'branch') $Branch
  Test-ExpectedValue $errors 'prNumber' (Get-ObjectProperty $lock 'prNumber') $PrNumber
  Test-ExpectedValue $errors 'artifactCommitSha' (Get-ObjectProperty $lock 'artifactCommitSha') $ArtifactCommitSha
  Test-ExpectedValue $errors 'sourceRcVersion' (Get-ObjectProperty $lock 'sourceRcVersion') $SourceRcVersion
  Test-ExpectedValue $errors 'finalReleaseVersion' (Get-ObjectProperty $lock 'finalReleaseVersion') $FinalReleaseVersion

  [pscustomobject]@{
    path = $lockPath
    exists = $true
    valid = $errors.Count -eq 0
    ticketKey = Get-ObjectProperty $lock 'ticketKey'
    branch = Get-ObjectProperty $lock 'branch'
    prNumber = Get-ObjectProperty $lock 'prNumber'
    artifactCommitSha = Get-ObjectProperty $lock 'artifactCommitSha'
    sourceRcVersion = Get-ObjectProperty $lock 'sourceRcVersion'
    finalReleaseVersion = Get-ObjectProperty $lock 'finalReleaseVersion'
    errors = @($errors)
  }
}

function Test-DeploymentLane {
  $lanePath = Join-Path $RepoRoot '.codex/parallel-delivery.local.json'
  if (-not (Test-Path -LiteralPath $lanePath)) {
    return [pscustomobject]@{
      path = $lanePath
      active = $false
      valid = $true
      errors = @()
    }
  }

  $state = Get-Content -LiteralPath $lanePath -Raw | ConvertFrom-Json
  $policy = [string](Get-ObjectProperty $state 'deploymentLanePolicy')
  $owner = Get-ObjectProperty $state 'deploymentLaneOwner'
  $ownerTicket = [string](Get-ObjectProperty $owner 'ticketKey')
  $ownerStage = [string](Get-ObjectProperty $owner 'stage')
  $errors = [System.Collections.Generic.List[string]]::new()

  if ($policy -eq 'serialized' -and -not [string]::IsNullOrWhiteSpace($ownerTicket)) {
    if (-not [string]::IsNullOrWhiteSpace($TicketKey) -and $ownerTicket -ne $TicketKey) {
      $errors.Add("Deployment lane is owned by '$ownerTicket' at stage '$ownerStage'.")
    }
  }

  [pscustomobject]@{
    path = $lanePath
    active = $true
    valid = $errors.Count -eq 0
    policy = $policy
    ownerTicketKey = $ownerTicket
    ownerStage = $ownerStage
    requestedTicketKey = $TicketKey
    requestedStage = $Stage
    errors = @($errors)
  }
}

function Test-ParallelDeliveryDryRun {
  $state = Get-InputObject
  $errors = [System.Collections.Generic.List[string]]::new()
  $tickets = @((Get-ObjectProperty $state 'tickets'))
  $maxActiveTickets = Get-ObjectProperty $state 'maxActiveTickets'
  if ($null -ne $maxActiveTickets -and $tickets.Count -gt [int]$maxActiveTickets) {
    $errors.Add("Active ticket count '$($tickets.Count)' exceeds maxActiveTickets '$maxActiveTickets'.")
  }

  $ticketKeys = @{}
  $worktreePaths = @{}
  $branches = @{}
  foreach ($ticket in $tickets) {
    $ticketKey = [string](Get-ObjectProperty $ticket 'ticketKey')
    $worktreePath = [string](Get-ObjectProperty $ticket 'worktreePath')
    $branch = [string](Get-ObjectProperty $ticket 'branch')

    if ([string]::IsNullOrWhiteSpace($ticketKey)) { $errors.Add('A ticket entry is missing ticketKey.') }
    if ([string]::IsNullOrWhiteSpace($worktreePath)) { $errors.Add("Ticket '$ticketKey' is missing worktreePath.") }
    if ([string]::IsNullOrWhiteSpace($branch)) { $errors.Add("Ticket '$ticketKey' is missing branch.") }

    foreach ($entry in @(
      @{ name = 'ticketKey'; value = $ticketKey; seen = $ticketKeys },
      @{ name = 'worktreePath'; value = $worktreePath; seen = $worktreePaths },
      @{ name = 'branch'; value = $branch; seen = $branches }
    )) {
      if ([string]::IsNullOrWhiteSpace([string]$entry.value)) { continue }
      if ($entry.seen.ContainsKey($entry.value)) {
        $errors.Add("Duplicate $($entry.name) '$($entry.value)' in parallel delivery state.")
      } else {
        $entry.seen[$entry.value] = $true
      }
    }
  }

  $policy = [string](Get-ObjectProperty $state 'deploymentLanePolicy')
  $owner = Get-ObjectProperty $state 'deploymentLaneOwner'
  $ownerTicket = [string](Get-ObjectProperty $owner 'ticketKey')
  if ($policy -eq 'serialized' -and -not [string]::IsNullOrWhiteSpace($ownerTicket) -and -not $ticketKeys.ContainsKey($ownerTicket)) {
    $errors.Add("Serialized deployment lane owner '$ownerTicket' is not an active ticket.")
  }

  [pscustomobject]@{
    valid = $errors.Count -eq 0
    activeTicketCount = $tickets.Count
    maxActiveTickets = $maxActiveTickets
    deploymentLanePolicy = $policy
    deploymentLaneOwnerTicketKey = $ownerTicket
    errors = @($errors)
  }
}

function Format-Link($Text, $Url) {
  if ([string]::IsNullOrWhiteSpace([string]$Url)) {
    return [string]$Text
  }
  return "[$Text]($Url)"
}

function Get-InputObject {
  if ([string]::IsNullOrWhiteSpace($InputJson)) {
    return [pscustomobject]@{}
  }
  return $InputJson | ConvertFrom-Json
}

function Render-PlaneComment {
  if ([string]::IsNullOrWhiteSpace($Type)) {
    throw 'Type is required for RenderPlaneComment.'
  }

  $data = Get-InputObject
  $shortCommit = [string](Get-ObjectProperty $data 'shortCommit')
  if ([string]::IsNullOrWhiteSpace($shortCommit)) {
    $fullCommit = [string](Get-ObjectProperty $data 'commitSha')
    if ($fullCommit.Length -ge 7) {
      $shortCommit = $fullCommit.Substring(0, 7)
    }
  }

  switch ($Type) {
    'QADeployment' {
      $commitSha = [string](Get-ObjectProperty $data 'commitSha')
      $lines = @(
        "IA generated QA deployment: $commitSha",
        '',
        "**Status:** $((Get-ObjectProperty $data 'status'))",
        '',
        '**Context**',
        "- PR: $(Format-Link 'PR' (Get-ObjectProperty $data 'prUrl'))",
        "- Commit: ``$shortCommit`` (``$commitSha``)",
        "- Version: $((Get-ObjectProperty $data 'versionStatus'))",
        "- Workflow: $(Format-Link 'workflow run' (Get-ObjectProperty $data 'workflowRunUrl'))",
        '',
        '**Artifacts**',
        "- App ZIP: $(Format-Link 'app.zip' (Get-ObjectProperty $data 'artifactUrl'))",
        "- Checksum: ``$((Get-ObjectProperty $data 'checksum'))``",
        "- Release manifest: $(Format-Link 'release.json' (Get-ObjectProperty $data 'releaseManifestUrl'))",
        '',
        '**Environment Validation**',
        '| Environment | Page | `/health` | URL |',
        '| --- | --- | --- | --- |',
        "| DEV | $((Get-ObjectProperty $data 'devStatus')) | $((Get-ObjectProperty $data 'devHealthStatus')) | $(Format-Link 'DEV' (Get-ObjectProperty $data 'devUrl')) |",
        "| QA | $((Get-ObjectProperty $data 'qaStatus')) | $((Get-ObjectProperty $data 'qaHealthStatus')) | $(Format-Link 'QA' (Get-ObjectProperty $data 'qaUrl')) |"
      )
      return ($lines -join [Environment]::NewLine)
    }
    'E2EQA' {
      $ticket = [string](Get-ObjectProperty $data 'ticketKey')
      $commitSha = [string](Get-ObjectProperty $data 'commitSha')
      $lines = @(
        "IA generated E2E QA: $ticket",
        '',
        "**Status:** $((Get-ObjectProperty $data 'status'))",
        '',
        '**Context**',
        "- Ticket: ``$ticket`` ($((Get-ObjectProperty $data 'ticketState')))",
        "- QA URL: $(Format-Link 'open QA' (Get-ObjectProperty $data 'qaUrl'))",
        "- Commit: ``$shortCommit`` (``$commitSha``)",
        "- PR: $(Format-Link 'PR' (Get-ObjectProperty $data 'prUrl'))",
        "- Artifact: $(Format-Link 'app.zip' (Get-ObjectProperty $data 'artifactUrl'))",
        "- Source RC: ``$((Get-ObjectProperty $data 'sourceRcVersion'))`` -> ``$commitSha``",
        "- Release lineage: ``$shortCommit`` -> ``$((Get-ObjectProperty $data 'sourceRcVersion'))`` -> pending ``$((Get-ObjectProperty $data 'finalReleaseVersion'))``",
        '',
        '**Scenarios**',
        "$((Get-ObjectProperty $data 'scenariosMarkdown'))",
        '',
        '**Evidence**',
        "- Evidence bundle: $(Format-Link 'qa-evidence.zip' (Get-ObjectProperty $data 'evidenceUrl'))",
        "- Release manifest: $(Format-Link 'release.json' (Get-ObjectProperty $data 'releaseManifestUrl'))",
        '',
        '**Notes**',
        "$((Get-ObjectProperty $data 'notesMarkdown'))"
      )
      return ($lines -join [Environment]::NewLine)
    }
    'ProdDeployment' {
      $finalVersion = [string](Get-ObjectProperty $data 'finalReleaseVersion')
      $commitSha = [string](Get-ObjectProperty $data 'commitSha')
      $lines = @(
        "IA generated PROD deployment: $finalVersion",
        '',
        "**Status:** $((Get-ObjectProperty $data 'status'))",
        '',
        '**Release**',
        "- Ticket: ``$((Get-ObjectProperty $data 'ticketKey'))`` ($((Get-ObjectProperty $data 'ticketState')))",
        "- Final version: ``$finalVersion``",
        "- Source RC: ``$((Get-ObjectProperty $data 'sourceRcVersion'))``",
        "- Lineage: ``$shortCommit`` -> ``$((Get-ObjectProperty $data 'sourceRcVersion'))`` -> ``$finalVersion``",
        "- Final tag: ``$finalVersion`` -> ``$commitSha``",
        "- Main update: $((Get-ObjectProperty $data 'mainUpdateResult'))",
        '',
        '**References**',
        "- Release PR: $(Format-Link 'release PR' (Get-ObjectProperty $data 'releasePrUrl'))",
        "- Workflow: $(Format-Link 'workflow run' (Get-ObjectProperty $data 'workflowRunUrl'))",
        "- Artifact: $(Format-Link 'app.zip' (Get-ObjectProperty $data 'artifactUrl'))",
        "- Checksum: ``$((Get-ObjectProperty $data 'checksum'))``",
        "- Release manifest: $(Format-Link 'release.json' (Get-ObjectProperty $data 'releaseManifestUrl'))",
        "- QA evidence: $(Format-Link 'qa-evidence.zip' (Get-ObjectProperty $data 'qaEvidenceUrl'))",
        '',
        '**Production Validation**',
        "$((Get-ObjectProperty $data 'validationMarkdown'))",
        '',
        "**PROD URL:** $(Format-Link 'open production' (Get-ObjectProperty $data 'prodUrl'))"
      )
      return ($lines -join [Environment]::NewLine)
    }
    default {
      throw "Unsupported RenderPlaneComment type: $Type"
    }
  }
}

function Update-ReleaseManifest {
  if ([string]::IsNullOrWhiteSpace($Path)) {
    throw 'Path is required for UpdateReleaseManifest.'
  }
  if ([string]::IsNullOrWhiteSpace($InputJson)) {
    throw 'InputJson is required for UpdateReleaseManifest.'
  }

  $manifest = [pscustomobject]@{}
  if (Test-Path -LiteralPath $Path) {
    $manifest = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
  }

  $updates = $InputJson | ConvertFrom-Json
  foreach ($property in $updates.PSObject.Properties) {
    $manifest | Add-Member -NotePropertyName $property.Name -NotePropertyValue $property.Value -Force
  }

  $parent = Split-Path -Parent $Path
  if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent | Out-Null
  }

  $manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $Path -Encoding UTF8
  Test-ReleaseManifest $Path
}

switch ($Mode) {
  'ArtifactPaths' { Write-Json (Get-ArtifactPaths $CommitSha) }
  'CheckGitIgnored' { Write-Json (Test-GitIgnored $Path) }
  'NextRcVersion' { Write-Json (Get-NextRcVersion $TargetVersion) }
  'ReadDeliveryPolicy' { Write-Json (Get-DeliveryPolicy) }
  'ExtractTicketKey' { Write-Json (Get-ExtractedTicketKey) }
  'ReadCoverageThreshold' { Write-Json (Get-CoverageThreshold) }
  'ReadCoberturaLineRate' { Write-Json (Get-CoberturaLineRate) }
  'ValidateReleaseManifest' { Write-Json (Test-ReleaseManifest $Path) }
  'ValidateTicketLock' { Write-Json (Test-TicketLock) }
  'ValidateDeploymentLane' { Write-Json (Test-DeploymentLane) }
  'ValidateParallelDeliveryDryRun' { Write-Json (Test-ParallelDeliveryDryRun) }
  'RenderPlaneComment' { Render-PlaneComment }
  'UpdateReleaseManifest' { Write-Json (Update-ReleaseManifest) }
}
