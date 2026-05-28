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
