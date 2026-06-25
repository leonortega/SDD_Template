param(
  [string]$Root = (Resolve-Path ".").Path,
  [switch]$AsJson,
  [switch]$FailOnFindings,
  [switch]$IncludeConfigure,
  [switch]$IncludeOpenSpec,
  [switch]$AllSkills
)

$ErrorActionPreference = "Stop"

$requiredSections = @(
  "Overview",
  "Shared Context",
  "Workflow",
  "Output",
  "Failure Rules"
)

$requiredTerms = @(
  ".codex/skills/_shared/delivery-contract.md",
  "docs/context-management.md",
  "ticket",
  "validation",
  "handoff"
)

$supportSkillNames = @(
  "caveman",
  "domain-modeling",
  "grill-me",
  "grill-with-docs",
  "grilling",
  "ponytail",
  "ponytail-audit",
  "ponytail-debt",
  "ponytail-help",
  "ponytail-review"
)

$providerNeutralSkillNames = @(
  "dev-flow-continue-implementation",
  "dev-flow-file-qa-bug",
  "dev-flow-implement-change",
  "dev-flow-implement-ticket",
  "dev-flow-parallel-ticket-coordinator",
  "dev-flow-pipeline-status",
  "dev-flow-pr-review-agent",
  "dev-flow-pr-review-feedback-loop",
  "dev-flow-retrospective-audit",
  "dev-flow-start-ticket",
  "dev-ops-deploy-prod",
  "dev-ops-deploy-qa",
  "dev-ops-hotfix-prod",
  "dev-ops-post-merge-deploy",
  "dev-ops-rollback-prod",
  "project-guidance-discover",
  "project-guidance-mapper",
  "quality-frontend-testing-debugging",
  "quality-test-e2e"
)

$providerSpecificTerms = @(
  "Plane",
  "plane",
  "OpenProject",
  "openProject",
  "OPENPROJECT",
  "work_packages",
  "Gitea",
  "gitea",
  "GITEA",
  "Azure",
  "azure",
  "AZURE",
  "rancher-desktop",
  "RANCHER",
  "Playwright",
  "playwright",
  ".NET",
  "dotnet"
)

function Get-RelativePathForAudit([string]$BasePath, [string]$FullPath) {
  $base = [System.IO.Path]::GetFullPath($BasePath).TrimEnd('\', '/')
  $full = [System.IO.Path]::GetFullPath($FullPath)
  $baseUri = [Uri]::new($base + [System.IO.Path]::DirectorySeparatorChar)
  $fullUri = [Uri]::new($full)
  return [Uri]::UnescapeDataString($baseUri.MakeRelativeUri($fullUri).ToString()).Replace("/", [System.IO.Path]::DirectorySeparatorChar)
}

$skillRoot = Join-Path $Root ".codex/skills"
if (-not (Test-Path $skillRoot)) {
  throw "Missing skill root: $skillRoot"
}

$results = @()
$providerSpecificFindings = @()

$profileFindings = @()
$profilePath = Join-Path $Root ".codex/project-profile.json"
$schemaPath = Join-Path $Root ".codex/project-profile.schema.json"
if (-not (Test-Path -LiteralPath $profilePath)) {
  $profileFindings += "Missing .codex/project-profile.json."
}
else {
  try {
    $profile = Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json
    if ($profile.schemaVersion -ne 1) {
      $profileFindings += "project-profile.json schemaVersion must be 1."
    }
    if ([string]::IsNullOrWhiteSpace([string]$profile.workflow.ticketKeyPattern)) {
      $profileFindings += "project-profile.json must define workflow.ticketKeyPattern."
    }
    if ($null -eq $profile.providers) {
      $profileFindings += "project-profile.json must define providers."
    }
    if ($null -eq $profile.adapters) {
      $profileFindings += "project-profile.json must define adapters."
    }
    else {
      foreach ($adapter in $profile.adapters.PSObject.Properties) {
        $adapterPath = [string]$adapter.Value
        if ([string]::IsNullOrWhiteSpace($adapterPath)) {
          $profileFindings += "Adapter '$($adapter.Name)' has an empty path."
          continue
        }
        if ([System.IO.Path]::IsPathRooted($adapterPath)) {
          $profileFindings += "Adapter '$($adapter.Name)' must use a repo-relative path."
          continue
        }
        $resolvedAdapterPath = [System.IO.Path]::GetFullPath((Join-Path $Root $adapterPath))
        $resolvedRoot = [System.IO.Path]::GetFullPath($Root)
        if (-not $resolvedAdapterPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
          $profileFindings += "Adapter '$($adapter.Name)' resolves outside the repository."
          continue
        }
        if (-not (Test-Path -LiteralPath $resolvedAdapterPath)) {
          $profileFindings += "Adapter '$($adapter.Name)' path does not exist: $adapterPath."
        }
      }
    }

    $profileText = Get-Content -LiteralPath $profilePath -Raw
    foreach ($secretNeedle in @("apiToken", "password", "clientSecret", "connectionString", "replace-with-")) {
      if ($profileText -match [regex]::Escape($secretNeedle)) {
        $profileFindings += "project-profile.json must not contain secret/local placeholder field '$secretNeedle'."
      }
    }
  }
  catch {
    $profileFindings += "Could not parse project-profile.json: $($_.Exception.Message)"
  }
}

if (-not (Test-Path -LiteralPath $schemaPath)) {
  $profileFindings += "Missing .codex/project-profile.schema.json."
}

Get-ChildItem -Path $skillRoot -Recurse -Filter "SKILL.md" |
  Where-Object {
    if ($AllSkills) { return $true }
    $skillName = Split-Path -Leaf (Split-Path -Parent $_.FullName)
    if ($supportSkillNames -contains $skillName) { return $false }
    if (-not $IncludeOpenSpec -and $_.FullName -match "\\openspec-") { return $false }
    if (-not $IncludeConfigure -and $_.FullName -match "\\configure-") { return $false }
    return $true
  } |
  Sort-Object FullName |
  ForEach-Object {
    $relativePath = (Get-RelativePathForAudit $Root $_.FullName).Replace("\", "/")
    $content = Get-Content -Path $_.FullName -Raw
    $missingSections = @()
    $missingTerms = @()

    foreach ($section in $requiredSections) {
      if ($content -notmatch "(?m)^##\s+$([regex]::Escape($section))\s*$") {
        $missingSections += $section
      }
    }

    foreach ($term in $requiredTerms) {
      if ($content -notmatch [regex]::Escape($term)) {
        $missingTerms += $term
      }
    }

    if ($providerNeutralSkillNames -contains $skillName) {
      foreach ($providerTerm in $providerSpecificTerms) {
        if ($content.Contains($providerTerm)) {
          $providerSpecificFindings += "$relativePath contains provider-specific term '$providerTerm'. Generic delivery skills must load provider details through .codex/project-profile.json and selected adapters."
        }
      }
    }

    $results += [ordered]@{
      path = $relativePath
      passed = ($missingSections.Count -eq 0 -and $missingTerms.Count -eq 0)
      missingSections = $missingSections
      missingTerms = $missingTerms
    }
  }

$summary = [ordered]@{
  checked = $results.Count
  passed = @($results | Where-Object { $_.passed }).Count
  failed = @($results | Where-Object { -not $_.passed }).Count
  profilePassed = ($profileFindings.Count -eq 0)
  profileFindings = $profileFindings
  providerSpecificPassed = ($providerSpecificFindings.Count -eq 0)
  providerSpecificFindings = $providerSpecificFindings
  results = $results
}

if ($AsJson) {
  $summary | ConvertTo-Json -Depth 10
  exit 0
}

"Checked: $($summary.checked)"
"Passed: $($summary.passed)"
"Failed: $($summary.failed)"
if ($summary.profilePassed) {
  "Project profile: PASS"
}
else {
  "Project profile: FAIL"
  foreach ($finding in $profileFindings) {
    "  $finding"
  }
}

if ($summary.providerSpecificPassed) {
  "Provider-neutral generic skills: PASS"
}
else {
  "Provider-neutral generic skills: FAIL"
  foreach ($finding in $providerSpecificFindings) {
    "  $finding"
  }
}

foreach ($result in $results | Where-Object { -not $_.passed }) {
  "FAIL $($result.path)"
  if ($result.missingSections.Count -gt 0) {
    "  missing sections: $($result.missingSections -join ', ')"
  }
  if ($result.missingTerms.Count -gt 0) {
    "  missing terms: $($result.missingTerms -join ', ')"
  }
}

# Compatibility contract: if ($FailOnFindings -and ($summary.failed -gt 0 -or $profileFindings.Count -gt 0))
if ($FailOnFindings -and ($summary.failed -gt 0 -or $profileFindings.Count -gt 0 -or $providerSpecificFindings.Count -gt 0)) {
  exit 1
}

