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

@description('App Service plan SKU name. B1 is the default because each environment can host multiple apps.')
param appServicePlanSkuName string = 'B1'

@description('App Service plan SKU tier.')
param appServicePlanSkuTier string = 'Basic'

@description('Linux runtime stack for deployable .NET apps.')
param runtimeStack string = 'DOTNETCORE|10.0'

@description('Relative SQLite database file name used by API apps.')
param sqliteDatabaseFileName string = 'app.db'

@description('Deployable application topology. Keep this aligned with infra/deployment/apps.json.')
param deployableApps array = [
  {
    appId: 'api'
    role: 'api'
    artifactName: 'api.zip'
    healthPath: '/health'
    deployOrder: 10
  }
  {
    appId: 'site'
    role: 'web'
    artifactName: 'site.zip'
    healthPath: '/health'
    deployOrder: 20
  }
]

var normalizedProjectName = take(toLower(replace(projectName, '-', '')), 20)
var uniqueSuffix = take(uniqueString(subscription().subscriptionId, resourceGroup().id, environmentName), 6)
var planName = 'plan-${normalizedProjectName}-${environmentName}-${uniqueSuffix}'
var appIds = [for app in deployableApps: app.appId]
var hasApiApp = contains(appIds, 'api')
var hasSiteApp = contains(appIds, 'site')
var apiAppName = hasApiApp ? 'app-${normalizedProjectName}-${environmentName}-api-${uniqueSuffix}' : ''
var siteAppName = hasSiteApp ? 'app-${normalizedProjectName}-${environmentName}-site-${uniqueSuffix}' : ''
var apiAppUrl = hasApiApp ? 'https://${apiAppName}.azurewebsites.net' : ''
var siteAppUrl = hasSiteApp ? 'https://${siteAppName}.azurewebsites.net' : ''
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

resource apps 'Microsoft.Web/sites@2023-12-01' = [for app in deployableApps: {
  name: 'app-${normalizedProjectName}-${environmentName}-${app.appId}-${uniqueSuffix}'
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: runtimeStack
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
    }
  }
  tags: {
    project: projectName
    env: environmentName
    role: app.role
    appId: app.appId
    managedBy: 'bicep'
  }
}]

resource appSettings 'Microsoft.Web/sites/config@2023-12-01' = [for (app, i) in deployableApps: {
  name: 'appsettings'
  parent: apps[i]
  properties: union(
    {
      ASPNETCORE_ENVIRONMENT: aspNetEnvironment
    },
    app.role == 'web' && hasApiApp ? {
      Api__BaseUrl: apiAppUrl
    } : {},
    app.role == 'api' && hasSiteApp ? {
      Cors__AllowedOrigins__0: siteAppUrl
    } : {},
    app.role == 'api' ? {
      ConnectionStrings__ClientsDb: 'Data Source=${sqliteDbPath}'
      WEBSITES_ENABLE_APP_SERVICE_STORAGE: 'true'
    } : {}
  )
}]

output environment string = environmentName
output appServicePlanName string = appServicePlan.name
output apps array = [for app in deployableApps: {
  appId: app.appId
  name: 'app-${normalizedProjectName}-${environmentName}-${app.appId}-${uniqueSuffix}'
  url: 'https://app-${normalizedProjectName}-${environmentName}-${app.appId}-${uniqueSuffix}.azurewebsites.net'
  role: app.role
  artifactName: app.artifactName
  healthPath: app.healthPath
}]
output siteAppName string = siteAppName
output siteAppUrl string = siteAppUrl
output apiAppName string = apiAppName
output apiAppUrl string = apiAppUrl
output sqliteDbPath string = sqliteDbPath
