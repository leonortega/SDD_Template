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
  "ponytail",
  "ponytail-audit",
  "ponytail-debt",
  "ponytail-help",
  "ponytail-review"
)

$skillRoot = Join-Path $Root ".codex/skills"
if (-not (Test-Path $skillRoot)) {
  throw "Missing skill root: $skillRoot"
}

$results = @()

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
    $relativePath = [System.IO.Path]::GetRelativePath($Root, $_.FullName).Replace("\", "/")
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
  results = $results
}

if ($AsJson) {
  $summary | ConvertTo-Json -Depth 10
  exit 0
}

"Checked: $($summary.checked)"
"Passed: $($summary.passed)"
"Failed: $($summary.failed)"

foreach ($result in $results | Where-Object { -not $_.passed }) {
  "FAIL $($result.path)"
  if ($result.missingSections.Count -gt 0) {
    "  missing sections: $($result.missingSections -join ', ')"
  }
  if ($result.missingTerms.Count -gt 0) {
    "  missing terms: $($result.missingTerms -join ', ')"
  }
}

if ($FailOnFindings -and $summary.failed -gt 0) {
  exit 1
}
