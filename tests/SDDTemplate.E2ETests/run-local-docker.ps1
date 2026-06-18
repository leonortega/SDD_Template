param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $PlaywrightArgs
)

$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot '..\..')
$configPath = Join-Path $repoRoot '.codex\client-tools.local.json'
$image = 'agentic/e2e-ci:playwright-1.57.0-1'

$siteUrl = $env:E2E_SITE_URL
$apiUrl = $env:E2E_API_URL

if (([string]::IsNullOrWhiteSpace($siteUrl) -or [string]::IsNullOrWhiteSpace($apiUrl)) -and (Test-Path $configPath)) {
  $config = Get-Content -Raw $configPath | ConvertFrom-Json
  if ([string]::IsNullOrWhiteSpace($siteUrl)) {
    $siteUrl = $config.azure.qa.siteUrl
  }
  if ([string]::IsNullOrWhiteSpace($apiUrl)) {
    $apiUrl = $config.azure.qa.apiUrl
  }
}

if ([string]::IsNullOrWhiteSpace($siteUrl) -or [string]::IsNullOrWhiteSpace($apiUrl)) {
  throw 'E2E_SITE_URL and E2E_API_URL are required, or set azure.qa.siteUrl/apiUrl in .codex/client-tools.local.json.'
}

docker image inspect $image *> $null
if ($LASTEXITCODE -ne 0) {
  throw "Docker image '$image' is missing. Run config infra / BuildGiteaActionsImages before local Docker E2E."
}

$workspace = (Resolve-Path $repoRoot).Path -replace '\\', '/'
$testArgs = @()
if ($PlaywrightArgs) {
  $testArgs = $PlaywrightArgs | ForEach-Object { "'" + ($_ -replace "'", "'\''") + "'" }
}
$testCommand = 'npm ci && npx playwright test'
if ($testArgs.Count -gt 0) {
  $testCommand = "$testCommand $($testArgs -join ' ')"
}

docker run --rm --ipc=host `
  -e "E2E_SITE_URL=$siteUrl" `
  -e "E2E_API_URL=$apiUrl" `
  -v "${workspace}:/workspace" `
  -w /workspace/tests/SDDTemplate.E2ETests `
  $image `
  bash -lc $testCommand

exit $LASTEXITCODE
