$ErrorActionPreference = "Stop"

$infraDir = Split-Path -Parent $MyInvocation.MyCommand.Path

docker compose `
  --env-file (Join-Path $infraDir "openproject\variables.env") `
  --env-file (Join-Path $infraDir "monitoring\variables.env") `
  -f (Join-Path $infraDir "compose.yml") `
  --project-directory $infraDir `
  up -d --remove-orphans
