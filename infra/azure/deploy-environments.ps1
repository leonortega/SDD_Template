param(
  [string]$Location = "westcentralus",
  [string]$DevResourceGroup = "rg-agentic-dev",
  [string]$QaResourceGroup = "rg-agentic-qa",
  [string]$ProdResourceGroup = "rg-agentic-prod",
  [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

$azureDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$template = Join-Path $azureDir "main.bicep"

function Invoke-AzChecked {
  param(
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments
  )

  & az @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Azure CLI command failed: az $($Arguments -join ' ')"
  }
}

$deployments = @(
  @{
    Environment = "dev"
    ResourceGroup = $DevResourceGroup
    Parameters = Join-Path $azureDir "dev.parameters.json"
  },
  @{
    Environment = "qa"
    ResourceGroup = $QaResourceGroup
    Parameters = Join-Path $azureDir "qa.parameters.json"
  },
  @{
    Environment = "prod"
    ResourceGroup = $ProdResourceGroup
    Parameters = Join-Path $azureDir "prod.parameters.json"
  }
)

Invoke-AzChecked @("account", "show", "--output", "none")

foreach ($deployment in $deployments) {
  if ($WhatIf) {
    & az group show --name $deployment.ResourceGroup --output none 2>$null
    if ($LASTEXITCODE -ne 0) {
      Write-Output "WhatIf: resource group '$($deployment.ResourceGroup)' would be created in '$Location'. Skipping deployment what-if for '$($deployment.Environment)' until the group exists."
      continue
    }

    $deploymentName = "agentic-$($deployment.Environment)-$(Get-Date -Format yyyyMMddHHmmss)"
    Invoke-AzChecked @(
      "deployment", "group", "what-if",
      "--resource-group", $deployment.ResourceGroup,
      "--name", $deploymentName,
      "--template-file", $template,
      "--parameters", $deployment.Parameters
    )
    continue
  }

  Invoke-AzChecked @(
    "group", "create",
    "--name", $deployment.ResourceGroup,
    "--location", $Location,
    "--tags", "project=agentic-e2e", "env=$($deployment.Environment)", "managedBy=bicep",
    "--output", "none"
  )

  $deploymentName = "agentic-$($deployment.Environment)-$(Get-Date -Format yyyyMMddHHmmss)"
  Invoke-AzChecked @(
    "deployment", "group", "create",
    "--resource-group", $deployment.ResourceGroup,
    "--name", $deploymentName,
    "--template-file", $template,
    "--parameters", $deployment.Parameters,
    "--output", "table"
  )
}
