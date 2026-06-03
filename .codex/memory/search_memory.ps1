param(
  [string[]] $Query = @(),
  [switch] $ListTopics,
  [switch] $AsJson,
  [string] $Root = (Resolve-Path ".").Path
)

$ErrorActionPreference = "Stop"

$memoryRoot = Join-Path $Root ".codex/memory"
if (-not (Test-Path -LiteralPath $memoryRoot)) {
  throw "Memory root not found: $memoryRoot"
}

$files = Get-ChildItem -Path $memoryRoot -Filter "*.md" |
  Where-Object { $_.Name -notin @("MEMORY.md", "memory_summary.md", "retrieval-policy.md") } |
  Sort-Object Name

function ConvertTo-Entry([System.IO.FileInfo] $File, [string] $Heading, [string] $Body) {
  $type = ""
  $status = ""
  $source = ""
  $verified = ""

  if ($Body -match "(?m)^-\s+Type:\s*(.+)$") { $type = $Matches[1].Trim() }
  if ($Body -match "(?m)^-\s+Status:\s*(.+)$") { $status = $Matches[1].Trim() }
  if ($Body -match "(?m)^-\s+Source:\s*(.+)$") { $source = $Matches[1].Trim() }
  if ($Body -match "(?m)^-\s+Last verified:\s*(.+)$") { $verified = $Matches[1].Trim() }

  $plain = ($Body -replace "(?m)^-\s+(Type|Status|Source|Last verified):.+$", "" -replace "\s+", " ").Trim()
  if ($plain.Length -gt 240) {
    $plain = $plain.Substring(0, 240).Trim() + "..."
  }

  [pscustomobject]@{
    file = [System.IO.Path]::GetRelativePath($Root, $File.FullName).Replace("\", "/")
    title = $Heading.Trim()
    type = $type
    status = $status
    source = $source
    lastVerified = $verified
    excerpt = $plain
  }
}

$entries = foreach ($file in $files) {
  $content = Get-Content -LiteralPath $file.FullName -Raw
  $matches = [regex]::Matches($content, "(?ms)^##\s+(.+?)\r?\n(.*?)(?=^##\s+|\z)")
  foreach ($match in $matches) {
    ConvertTo-Entry $file $match.Groups[1].Value $match.Groups[2].Value
  }
}

if ($ListTopics) {
  $output = $entries | Select-Object file, title, type, status, lastVerified
} elseif ($Query.Count -gt 0) {
  $terms = @($Query | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { $_.Trim() })
  $output = $entries | Where-Object {
    $haystack = "$($_.file) $($_.title) $($_.type) $($_.source) $($_.excerpt)"
    foreach ($term in $terms) {
      if ($haystack.IndexOf($term, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        return $false
      }
    }
    return $true
  }
} else {
  $output = [pscustomobject]@{
    memoryRoot = [System.IO.Path]::GetRelativePath($Root, $memoryRoot).Replace("\", "/")
    usage = ".codex/memory/search_memory.ps1 -Query term1,term2 or -ListTopics"
    files = @($files | ForEach-Object { [System.IO.Path]::GetRelativePath($Root, $_.FullName).Replace("\", "/") })
  }
}

if ($AsJson) {
  $output | ConvertTo-Json -Depth 10
  exit 0
}

$output | Format-Table -AutoSize
