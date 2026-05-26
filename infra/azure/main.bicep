@description('Environment name.')
@allowed([
  'dev'
  'qa'
  'prod'
])
param environmentName string

@description('Azure region for the environment resources.')
param location string = resourceGroup().location

@description('Project tag and naming prefix used for cost tracking.')
param projectName string = 'agentic-e2e'

@description('App Service plan SKU name. B1 is the default because each environment hosts a web app and REST API.')
param appServicePlanSkuName string = 'B1'

@description('App Service plan SKU tier.')
param appServicePlanSkuTier string = 'Basic'

@description('Linux runtime stack for the web app.')
param webRuntimeStack string = 'DOTNETCORE|10.0'

@description('Linux runtime stack for the REST API app.')
param apiRuntimeStack string = 'DOTNETCORE|10.0'

@description('Relative SQLite database file name used by the REST API.')
param sqliteDatabaseFileName string = 'app.db'

var normalizedProjectName = take(toLower(replace(projectName, '-', '')), 20)
var uniqueSuffix = take(uniqueString(subscription().subscriptionId, resourceGroup().id, environmentName), 6)
var planName = 'plan-${normalizedProjectName}-${environmentName}-${uniqueSuffix}'
var webAppName = 'app-${normalizedProjectName}-${environmentName}-web-${uniqueSuffix}'
var apiAppName = 'app-${normalizedProjectName}-${environmentName}-api-${uniqueSuffix}'
var aspNetEnvironment = environmentName == 'prod' ? 'Production' : environmentName == 'qa' ? 'Staging' : 'Development'
var sqliteDbPath = '/home/data/${sqliteDatabaseFileName}'

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  kind: 'linux'
  sku: {
    name: appServicePlanSkuName
    tier: appServicePlanSkuTier
  }
  properties: {
    reserved: true
  }
  tags: {
    project: projectName
    env: environmentName
    managedBy: 'bicep'
  }
}

resource apiApp 'Microsoft.Web/sites@2023-12-01' = {
  name: apiAppName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: apiRuntimeStack
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        {
          name: 'ASPNETCORE_ENVIRONMENT'
          value: aspNetEnvironment
        }
        {
          name: 'DATABASE_PROVIDER'
          value: 'sqlite'
        }
        {
          name: 'SQLITE_DB_PATH'
          value: sqliteDbPath
        }
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'true'
        }
      ]
    }
  }
  tags: {
    project: projectName
    env: environmentName
    role: 'rest-api'
    managedBy: 'bicep'
  }
}

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: webRuntimeStack
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        {
          name: 'ASPNETCORE_ENVIRONMENT'
          value: aspNetEnvironment
        }
        {
          name: 'REST_API_BASE_URL'
          value: 'https://${apiApp.properties.defaultHostName}'
        }
        {
          name: 'VITE_API_BASE_URL'
          value: 'https://${apiApp.properties.defaultHostName}'
        }
        {
          name: 'NEXT_PUBLIC_API_BASE_URL'
          value: 'https://${apiApp.properties.defaultHostName}'
        }
      ]
    }
  }
  tags: {
    project: projectName
    env: environmentName
    role: 'web'
    managedBy: 'bicep'
  }
}

output environment string = environmentName
output appServicePlanName string = appServicePlan.name
output webAppName string = webApp.name
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output apiAppName string = apiApp.name
output apiAppUrl string = 'https://${apiApp.properties.defaultHostName}'
output sqliteDbPath string = sqliteDbPath
