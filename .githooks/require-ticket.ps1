param(
  [Parameter(Mandatory = $true)]
  [string]$MessagePath
)

$ErrorActionPreference = "Stop"

$message = Get-Content -Path $MessagePath -Raw
$pattern = "^(\[SDD\] .+|E2EPROJECT-[0-9]+: .+|openspec/[a-z0-9][a-z0-9-]*: .+)"

if ($message -notmatch $pattern) {
  Write-Error "Commit message must start with a ticket, OpenSpec id, or [SDD] for direct SDD repo maintenance, for example: E2EPROJECT-1: scaffold blank Blazor site"
  exit 1
}
