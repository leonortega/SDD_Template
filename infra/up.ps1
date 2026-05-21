$ErrorActionPreference = "Stop"

$infraDir = Split-Path -Parent $MyInvocation.MyCommand.Path

docker compose `
  --env-file (Join-Path $infraDir "plane\variables.env") `
  -f (Join-Path $infraDir "compose.yml") `
  --project-directory $infraDir `
  up -d
