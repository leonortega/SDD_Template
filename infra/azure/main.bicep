@description('Environment name.')
@allowed([
  'dev'
  'qa'
  'prod'
])
param environmentName string

@description('Azure region for the environment resources.')
param location string = resourceGroup().location

@description('Project tag used for cost tracking.')
param projectName string = 'agentic-e2e'

var appName = 'app-agentic-${environmentName}'
var planName = 'plan-agentic-${environmentName}'

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  sku: {
    name: 'F1'
    tier: 'Free'
  }
  properties: {
    reserved: false
  }
  tags: {
    project: projectName
    env: environmentName
    managedBy: 'bicep'
  }
}

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      appSettings: [
        {
          name: 'ASPNETCORE_ENVIRONMENT'
          value: environmentName == 'prod' ? 'Production' : environmentName == 'qa' ? 'Staging' : 'Development'
        }
      ]
    }
  }
  tags: {
    project: projectName
    env: environmentName
    managedBy: 'bicep'
  }
}

output appUrl string = 'https://${webApp.properties.defaultHostName}'
