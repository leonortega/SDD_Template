param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('ArtifactPaths', 'CheckGitIgnored', 'NextRcVersion', 'ValidateReleaseManifest')]
  [string] $Mode,

  [string] $CommitSha,
  [string] $Path,
  [string] $TargetVersion,
  [string] $RepoRoot = (Get-Location).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Json($Value) {
  $Value | ConvertTo-Json -Depth 20
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

switch ($Mode) {
  'ArtifactPaths' { Write-Json (Get-ArtifactPaths $CommitSha) }
  'CheckGitIgnored' { Write-Json (Test-GitIgnored $Path) }
  'NextRcVersion' { Write-Json (Get-NextRcVersion $TargetVersion) }
  'ValidateReleaseManifest' { Write-Json (Test-ReleaseManifest $Path) }
}
