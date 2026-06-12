param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('ArtifactPaths', 'CheckGitIgnored', 'NextRcVersion', 'ReadDeliveryPolicy', 'ExtractTicketKey', 'ReadCoverageThreshold', 'ReadCoberturaLineRate', 'ValidateReleaseManifest', 'CreateArtifactPointer', 'ValidateTicketLock', 'ValidateDeploymentLane', 'ValidateParallelDeliveryDryRun', 'InitializeWorkflowTelemetry', 'AppendWorkflowTelemetry', 'ReadWorkflowTelemetry', 'RenderPlaneComment', 'UpdateReleaseManifest')]
  [string] $Mode,

  [string] $CommitSha,
  [string] $Path,
  [string] $TargetVersion,
  [string] $Version,
  [string] $TicketKey,
  [string] $IncludedTickets,
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

function Invoke-DeliveryCli([string[]] $Arguments, [switch] $AllowFailure) {
  $project = Join-Path $RepoRoot 'tools/SDDTemplate.DeliveryTools/SDDTemplate.DeliveryTools.csproj'
  if (-not (Test-Path -LiteralPath $project)) {
    throw "Delivery tools project not found: $project"
  }

  $output = & dotnet run --project $project -- $Arguments
  if ($LASTEXITCODE -ne 0 -and -not $AllowFailure) {
    throw "Delivery tools command failed: $($Arguments -join ' ')"
  }
  return ($output -join [Environment]::NewLine).Trim()
}

function Get-ObjectProperty($Object, [string] $Name) {
  if ($null -eq $Object) {
    return $null
  }
  if (@($Object.PSObject.Properties | Select-Object -ExpandProperty Name) -contains $Name) {
    return $Object.$Name
  }
  return $null
}

function Resolve-RepoPath([string] $CandidatePath, [string] $DefaultRelativePath) {
  $resolved = if ([string]::IsNullOrWhiteSpace($CandidatePath)) {
    Join-Path $RepoRoot $DefaultRelativePath
  } elseif ([System.IO.Path]::IsPathRooted($CandidatePath)) {
    $CandidatePath
  } else {
    Join-Path $RepoRoot $CandidatePath
  }
  return [System.IO.Path]::GetFullPath($resolved)
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
    topology = "app/$Sha/deployable-apps.json"
    appArtifactPattern = "app/$Sha/{artifactName}"
    checksumPattern = "app/$Sha/{artifactName}.sha256"
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

  $validation = Invoke-DeliveryCli @('ValidateReleaseManifest', '--path', $ManifestPath) -AllowFailure | ConvertFrom-Json

  [pscustomobject]@{
    path = $ManifestPath
    valid = [bool]$validation.Valid
    errors = @($validation.Errors)
  }
}

function New-ArtifactPointer([string] $OutputPath) {
  if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    throw 'Path is required for CreateArtifactPointer.'
  }
  if ([string]::IsNullOrWhiteSpace($Version)) {
    throw 'Version is required for CreateArtifactPointer.'
  }
  if ([string]::IsNullOrWhiteSpace($ArtifactCommitSha)) {
    throw 'ArtifactCommitSha is required for CreateArtifactPointer.'
  }
  if ([string]::IsNullOrWhiteSpace($TicketKey)) {
    throw 'TicketKey is required for CreateArtifactPointer.'
  }

  $arguments = @(
    'CreateArtifactPointer',
    '--output', $OutputPath,
    '--version', $Version,
    '--artifact-commit-sha', $ArtifactCommitSha,
    '--plane-ticket-key', $TicketKey
  )
  if (-not [string]::IsNullOrWhiteSpace($IncludedTickets)) {
    $arguments += @('--included-tickets', $IncludedTickets)
  }

  Invoke-DeliveryCli $arguments | Out-Null
  [pscustomobject]@{
    path = $OutputPath
    version = $Version
    artifactCommitSha = $ArtifactCommitSha
  }
}

function Get-DeliveryPolicy {
  $policyPath = Join-Path $RepoRoot '.codex/delivery-policy.json'
  $ticketKeyPattern = Invoke-DeliveryCli @('ReadDeliveryPolicy', '--path', $policyPath)

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

  $args = @('ExtractTicketKey', '--pattern', $policy.ticketKeyPattern, '--message', $Message)
  if (-not [string]::IsNullOrWhiteSpace($FallbackTicketKey)) {
    $args += @('--fallback', $FallbackTicketKey)
  }
  $ticketKey = Invoke-DeliveryCli $args

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

  $minimum = [int](Invoke-DeliveryCli @('ReadCoverageThreshold', '--path', $qualityPath, '--fallback', ([string]$FallbackCoverageMinimum)))

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

  $percent = [decimal]::Parse((Invoke-DeliveryCli @('ReadCoberturaLineRate', '--path', $Path)), [System.Globalization.CultureInfo]::InvariantCulture)
  $rate = $percent / 100
  [pscustomobject]@{
    path = $Path
    lineRate = $rate
    percent = $percent
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
  $enabled = Get-ObjectProperty $state 'enabled'
  if ($null -ne $enabled -and -not [bool]$enabled) {
    $errors.Add('parallelDelivery.enabled must be true before starting or routing parallel ticket work.')
  }

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
  if (-not [string]::IsNullOrWhiteSpace($policy) -and $policy -ne 'serialized') {
    $errors.Add("Unsupported deploymentLanePolicy '$policy'. Only 'serialized' is supported.")
  }

  $owner = Get-ObjectProperty $state 'deploymentLaneOwner'
  $ownerTicket = [string](Get-ObjectProperty $owner 'ticketKey')
  if ($policy -eq 'serialized' -and -not [string]::IsNullOrWhiteSpace($ownerTicket) -and -not $ticketKeys.ContainsKey($ownerTicket)) {
    $errors.Add("Serialized deployment lane owner '$ownerTicket' is not an active ticket.")
  }

  $requiredLocalConfigFilesValue = Get-ObjectProperty $state 'requiredLocalConfigFiles'
  [object[]]$requiredLocalConfigFiles = @()
  if ($null -ne $requiredLocalConfigFilesValue) {
    $requiredLocalConfigFiles = @($requiredLocalConfigFilesValue)
  }
  foreach ($requiredFile in $requiredLocalConfigFiles) {
    $relativePath = [string]$requiredFile
    if ([string]::IsNullOrWhiteSpace($relativePath)) {
      continue
    }

    $localPath = if ([System.IO.Path]::IsPathRooted($relativePath)) {
      $relativePath
    } else {
      Join-Path $RepoRoot $relativePath
    }

    if (-not (Test-Path -LiteralPath $localPath)) {
      $errors.Add("Required local runtime file '$relativePath' is missing.")
      continue
    }

    if (-not [System.IO.Path]::IsPathRooted($relativePath)) {
      Push-Location $RepoRoot
      try {
        & git check-ignore -q -- "$relativePath" 2>$null
        if ($LASTEXITCODE -ne 0) {
          $errors.Add("Required local runtime file '$relativePath' must be ignored.")
        }
      }
      finally {
        Pop-Location
      }
    }
  }

  [pscustomobject]@{
    valid = $errors.Count -eq 0
    enabled = $enabled
    activeTicketCount = $tickets.Count
    maxActiveTickets = $maxActiveTickets
    deploymentLanePolicy = $policy
    deploymentLaneOwnerTicketKey = $ownerTicket
    requiredLocalConfigFiles = $requiredLocalConfigFiles
    errors = @($errors)
  }
}

function Format-Link($Text, $Url) {
  if ([string]::IsNullOrWhiteSpace([string]$Url)) {
    return [string]$Text
  }
  return "[$Text]($Url)"
}

function Format-Duration([Nullable[long]] $Milliseconds) {
  if ($null -eq $Milliseconds -or $Milliseconds -lt 0) {
    return 'n/a'
  }

  $duration = [TimeSpan]::FromMilliseconds([double]$Milliseconds)
  if ($duration.TotalHours -ge 1) {
    return ('{0}h {1:D2}m {2:D2}s' -f [math]::Floor($duration.TotalHours), $duration.Minutes, $duration.Seconds)
  }
  if ($duration.TotalMinutes -ge 1) {
    return ('{0}m {1:D2}s' -f [math]::Floor($duration.TotalMinutes), $duration.Seconds)
  }
  return ('{0}s' -f [math]::Max(0, [math]::Round($duration.TotalSeconds)))
}

function Format-UtcTimestamp($Value) {
  if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
    return 'n/a'
  }
  if ($Value -is [datetime]) {
    return $Value.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ', [System.Globalization.CultureInfo]::InvariantCulture)
  }
  return [string]$Value
}

function Get-LongProperty($Object, [string] $Name) {
  $value = Get-ObjectProperty $Object $Name
  if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) {
    return $null
  }
  return [long]$value
}

function Get-WorkflowTimingStageRows($StageRows) {
  $standardStages = @(
    'plane-start-ticket',
    'implement-ticket',
    'pr-review-feedback-loop',
    'gitea-pr-review-agent',
    'post-merge-deploy',
    'deploy-to-qa',
    'test-e2e'
  )

  $inputRows = @($StageRows | Where-Object { $null -ne $_ })
  $expandedRows = [System.Collections.Generic.List[object]]::new()
  $includedIndexes = [System.Collections.Generic.HashSet[int]]::new()

  foreach ($standardStage in $standardStages) {
    $matched = $false
    for ($index = 0; $index -lt $inputRows.Count; $index++) {
      $stageName = [string](Get-ObjectProperty $inputRows[$index] 'stage')
      if ($stageName -eq $standardStage) {
        $expandedRows.Add($inputRows[$index])
        [void]$includedIndexes.Add($index)
        $matched = $true
      }
    }

    if (-not $matched) {
      $expandedRows.Add([pscustomobject]@{
        stage = $standardStage
        outcome = 'NOT RUN / N/A'
        elapsedMilliseconds = $null
        startedUtc = '-'
        finishedUtc = '-'
      })
    }
  }

  for ($index = 0; $index -lt $inputRows.Count; $index++) {
    if (-not $includedIndexes.Contains($index)) {
      $expandedRows.Add($inputRows[$index])
    }
  }

  return @($expandedRows)
}

function Get-WorkflowTelemetryPath {
  Resolve-RepoPath $Path '.codex/agent-telemetry.local.jsonl'
}

function Get-RequiredTelemetryTicketKey {
  if ([string]::IsNullOrWhiteSpace($TicketKey)) {
    throw 'TicketKey is required for workflow telemetry.'
  }
  return $TicketKey
}

function ConvertTo-UtcDateTime($Value, [string] $Name) {
  if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
    throw "$Name is required for workflow telemetry."
  }
  if ($Value -is [datetime]) {
    return $Value.ToUniversalTime()
  }
  return [DateTimeOffset]::Parse($Value).UtcDateTime
}

function Initialize-WorkflowTelemetry {
  $ticket = Get-RequiredTelemetryTicketKey
  $telemetryPath = Get-WorkflowTelemetryPath
  $parent = Split-Path -Parent $telemetryPath
  if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent | Out-Null
  }

  Set-Content -LiteralPath $telemetryPath -Value '' -NoNewline -Encoding UTF8
  [pscustomobject]@{
    path = $telemetryPath
    ticketKey = $ticket
    exists = Test-Path -LiteralPath $telemetryPath
    cleared = $true
  }
}

function Append-WorkflowTelemetry {
  $ticket = Get-RequiredTelemetryTicketKey
  $input = Get-InputObject
  $telemetryPath = Get-WorkflowTelemetryPath
  $parent = Split-Path -Parent $telemetryPath
  if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent | Out-Null
  }
  if (-not (Test-Path -LiteralPath $telemetryPath)) {
    New-Item -ItemType File -Path $telemetryPath | Out-Null
  }

  $workflowStage = [string](Get-ObjectProperty $input 'workflowStage')
  if ([string]::IsNullOrWhiteSpace($workflowStage)) {
    $workflowStage = [string](Get-ObjectProperty $input 'stage')
  }
  if ([string]::IsNullOrWhiteSpace($workflowStage)) {
    throw 'workflowStage is required for workflow telemetry.'
  }

  $agentRole = [string](Get-ObjectProperty $input 'agentRole')
  if ([string]::IsNullOrWhiteSpace($agentRole)) {
    throw 'agentRole is required for workflow telemetry.'
  }

  $outcome = [string](Get-ObjectProperty $input 'outcome')
  if ([string]::IsNullOrWhiteSpace($outcome)) {
    throw 'outcome is required for workflow telemetry.'
  }

  $started = ConvertTo-UtcDateTime (Get-ObjectProperty $input 'startedUtc') 'startedUtc'
  $finished = ConvertTo-UtcDateTime (Get-ObjectProperty $input 'finishedUtc') 'finishedUtc'
  if ($finished -lt $started) {
    throw 'finishedUtc must be greater than or equal to startedUtc.'
  }

  $elapsed = Get-LongProperty $input 'elapsedMilliseconds'
  if ($null -eq $elapsed) {
    $elapsed = [long]($finished - $started).TotalMilliseconds
  }

  $retryCount = Get-LongProperty $input 'retryCount'
  if ($null -eq $retryCount) {
    $retryCount = 0
  }

  $row = [ordered]@{
    ticketKey = $ticket
    timestampUtc = $finished.ToString('yyyy-MM-ddTHH:mm:ssZ', [System.Globalization.CultureInfo]::InvariantCulture)
    workflowStage = $workflowStage
    agentRole = $agentRole
    model = Get-ObjectProperty $input 'model'
    reasoningEffort = Get-ObjectProperty $input 'reasoningEffort'
    inputTokens = Get-ObjectProperty $input 'inputTokens'
    outputTokens = Get-ObjectProperty $input 'outputTokens'
    reasoningTokens = Get-ObjectProperty $input 'reasoningTokens'
    cachedTokens = Get-ObjectProperty $input 'cachedTokens'
    toolCallCount = Get-ObjectProperty $input 'toolCallCount'
    retryCount = [long]$retryCount
    startedUtc = $started.ToString('yyyy-MM-ddTHH:mm:ssZ', [System.Globalization.CultureInfo]::InvariantCulture)
    finishedUtc = $finished.ToString('yyyy-MM-ddTHH:mm:ssZ', [System.Globalization.CultureInfo]::InvariantCulture)
    elapsedMilliseconds = [long]$elapsed
    outcome = $outcome
    blockerCategory = Get-ObjectProperty $input 'blockerCategory'
  }

  $line = $row | ConvertTo-Json -Depth 20 -Compress
  Add-Content -LiteralPath $telemetryPath -Value $line -Encoding UTF8

  [pscustomobject]@{
    path = $telemetryPath
    ticketKey = $ticket
    appended = $true
    workflowStage = $workflowStage
    elapsedMilliseconds = [long]$elapsed
  }
}

function Read-WorkflowTelemetry {
  $ticket = Get-RequiredTelemetryTicketKey
  $input = Get-InputObject
  $telemetryPath = Get-WorkflowTelemetryPath
  if (-not (Test-Path -LiteralPath $telemetryPath)) {
    throw "Workflow telemetry file not found: $telemetryPath"
  }

  $rows = [System.Collections.Generic.List[object]]::new()
  foreach ($line in (Get-Content -LiteralPath $telemetryPath)) {
    if ([string]::IsNullOrWhiteSpace($line)) {
      continue
    }
    $row = $line | ConvertFrom-Json
    if ([string](Get-ObjectProperty $row 'ticketKey') -eq $ticket) {
      $rows.Add($row)
    }
  }

  if ($rows.Count -eq 0) {
    throw "Workflow telemetry has no rows for ticket '$ticket'."
  }

  $stageRows = @($rows | ForEach-Object {
    [pscustomobject]@{
      stage = Get-ObjectProperty $_ 'workflowStage'
      outcome = Get-ObjectProperty $_ 'outcome'
      elapsedMilliseconds = Get-LongProperty $_ 'elapsedMilliseconds'
      startedUtc = Format-UtcTimestamp (Get-ObjectProperty $_ 'startedUtc')
      finishedUtc = Format-UtcTimestamp (Get-ObjectProperty $_ 'finishedUtc')
    }
  })

  $totalElapsedMilliseconds = 0L
  foreach ($stageRow in $stageRows) {
    $elapsed = Get-LongProperty $stageRow 'elapsedMilliseconds'
    if ($null -ne $elapsed -and $elapsed -gt 0) {
      $totalElapsedMilliseconds += $elapsed
    }
  }

  $status = [string](Get-ObjectProperty $input 'status')
  if ([string]::IsNullOrWhiteSpace($status)) {
    $status = 'PASS - timing generated from workflow telemetry.'
  }
  $currentRoute = [string](Get-ObjectProperty $input 'currentRoute')
  if ([string]::IsNullOrWhiteSpace($currentRoute)) {
    $currentRoute = [string](Get-ObjectProperty $stageRows[-1] 'stage')
  }

  [pscustomobject]@{
    ticketKey = $ticket
    status = $status
    currentRoute = $currentRoute
    totalElapsedMilliseconds = $totalElapsedMilliseconds
    stages = $stageRows
  }
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
        "- Topology artifact: $(Format-Link 'deployable-apps.json' (Get-ObjectProperty $data 'topologyUrl'))",
        "- Representative app artifact: $(Format-Link 'app artifact' (Get-ObjectProperty $data 'artifactUrl'))",
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
        "- Artifact: $(Format-Link 'app artifact' (Get-ObjectProperty $data 'artifactUrl'))",
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
      $includedTickets = @((Get-ObjectProperty $data 'includedTickets') | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
      $includedTicketText = if ($includedTickets.Count -gt 0) {
        ($includedTickets | ForEach-Object { "``$($_)``" }) -join ', '
      } else {
        "``$((Get-ObjectProperty $data 'ticketKey'))``"
      }
      $lines = @(
        "IA generated PROD deployment: $finalVersion",
        '',
        "**Status:** $((Get-ObjectProperty $data 'status'))",
        '',
        '**Release**',
        "- Primary ticket: ``$((Get-ObjectProperty $data 'ticketKey'))`` ($((Get-ObjectProperty $data 'ticketState')))",
        "- Included tickets: $includedTicketText",
        "- Final version: ``$finalVersion``",
        "- Source RC: ``$((Get-ObjectProperty $data 'sourceRcVersion'))``",
        "- Lineage: ``$shortCommit`` -> ``$((Get-ObjectProperty $data 'sourceRcVersion'))`` -> ``$finalVersion``",
        "- Final tag: ``$finalVersion`` -> ``$commitSha``",
        "- Main update: $((Get-ObjectProperty $data 'mainUpdateResult'))",
        '',
        '**References**',
        "- Release PR: $(Format-Link 'release PR' (Get-ObjectProperty $data 'releasePrUrl'))",
        "- Workflow: $(Format-Link 'workflow run' (Get-ObjectProperty $data 'workflowRunUrl'))",
        "- Artifact: $(Format-Link 'app artifact' (Get-ObjectProperty $data 'artifactUrl'))",
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
    'WorkflowTiming' {
      $ticket = [string](Get-ObjectProperty $data 'ticketKey')
      if ([string]::IsNullOrWhiteSpace($ticket)) {
        throw 'ticketKey is required for WorkflowTiming comments.'
      }

      $stageRows = Get-WorkflowTimingStageRows @((Get-ObjectProperty $data 'stages'))
      $totalElapsedMilliseconds = Get-LongProperty $data 'totalElapsedMilliseconds'
      if ($null -eq $totalElapsedMilliseconds) {
        $totalElapsedMilliseconds = 0
        foreach ($stageRow in $stageRows) {
          $stageElapsed = Get-LongProperty $stageRow 'elapsedMilliseconds'
          if ($null -ne $stageElapsed -and $stageElapsed -gt 0) {
            $totalElapsedMilliseconds += $stageElapsed
          }
        }
      }

      $lines = @(
        "IA generated workflow timing: $ticket",
        '',
        "**Status:** $((Get-ObjectProperty $data 'status'))",
        "- Current route: ``$((Get-ObjectProperty $data 'currentRoute'))``",
        "- Total elapsed: $(Format-Duration $totalElapsedMilliseconds)",
        '',
        '| Stage | Outcome | Duration | Started UTC | Finished UTC |',
        '| --- | --- | ---: | --- | --- |'
      )

      foreach ($stageRow in $stageRows) {
        $stageName = [string](Get-ObjectProperty $stageRow 'stage')
        $outcome = [string](Get-ObjectProperty $stageRow 'outcome')
        $startedUtc = Format-UtcTimestamp (Get-ObjectProperty $stageRow 'startedUtc')
        $finishedUtc = Format-UtcTimestamp (Get-ObjectProperty $stageRow 'finishedUtc')
        $elapsed = Get-LongProperty $stageRow 'elapsedMilliseconds'

        if ([string]::IsNullOrWhiteSpace($stageName)) { $stageName = 'unknown' }
        if ([string]::IsNullOrWhiteSpace($outcome)) { $outcome = 'unknown' }

        $duration = if ($outcome -eq 'NOT RUN / N/A') { 'no time' } else { Format-Duration $elapsed }
        $lines += "| ``$stageName`` | $outcome | $duration | $startedUtc | $finishedUtc |"
      }

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
  'CreateArtifactPointer' { Write-Json (New-ArtifactPointer $Path) }
  'ValidateTicketLock' { Write-Json (Test-TicketLock) }
  'ValidateDeploymentLane' { Write-Json (Test-DeploymentLane) }
  'ValidateParallelDeliveryDryRun' { Write-Json (Test-ParallelDeliveryDryRun) }
  'InitializeWorkflowTelemetry' { Write-Json (Initialize-WorkflowTelemetry) }
  'AppendWorkflowTelemetry' { Write-Json (Append-WorkflowTelemetry) }
  'ReadWorkflowTelemetry' { Write-Json (Read-WorkflowTelemetry) }
  'RenderPlaneComment' { Render-PlaneComment }
  'UpdateReleaseManifest' { Write-Json (Update-ReleaseManifest) }
}
