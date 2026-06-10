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
var siteAppName = hasSiteApp ? 'app-${normalizedProjectName}-${environmentName}-web-${uniqueSuffix}' : ''
var apiAppUrl = hasApiApp ? 'https://${apiAppName}.azurewebsites.net' : ''
var siteAppUrl = hasSiteApp ? 'https://${siteAppName}.azurewebsites.net' : ''
var aspNetEnvironment = environmentName == 'prod' ? 'Production' : environmentName == 'qa' ? 'Staging' : 'Development'
var sqliteDbPath = '/home/data/${sqliteDatabaseFileName}'
var eventHubNamespaceName = 'evhns-${normalizedProjectName}-${environmentName}-${uniqueSuffix}'
var appServiceLogsEventHubName = 'appservice-logs'
var alloyConsumerGroupName = 'grafana-alloy-${environmentName}'
var diagnosticLogCategories = [
  'AppServiceHTTPLogs'
  'AppServiceConsoleLogs'
  'AppServiceAppLogs'
  'AppServiceAuditLogs'
  'AppServiceIPSecAuditLogs'
  'AppServicePlatformLogs'
  'AppServiceAuthenticationLogs'
]

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
  name: 'app-${normalizedProjectName}-${environmentName}-${app.role == 'web' ? 'web' : app.appId}-${uniqueSuffix}'
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

resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: eventHubNamespaceName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: 1
  }
  properties: {
    minimumTlsVersion: '1.2'
    kafkaEnabled: true
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
  tags: {
    project: projectName
    env: environmentName
    managedBy: 'bicep'
    purpose: 'app-service-log-ingestion'
  }
}

resource appServiceLogsEventHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  name: appServiceLogsEventHubName
  parent: eventHubNamespace
  properties: {
    messageRetentionInDays: 1
    partitionCount: 4
  }
}

resource alloyConsumerGroup 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = {
  name: alloyConsumerGroupName
  parent: appServiceLogsEventHub
}

resource diagnosticSendRule 'Microsoft.EventHub/namespaces/authorizationRules@2024-01-01' = {
  name: 'diagnostic-send'
  parent: eventHubNamespace
  properties: {
    rights: [
      'Send'
    ]
  }
}

resource alloyListenRule 'Microsoft.EventHub/namespaces/eventhubs/authorizationRules@2024-01-01' = {
  name: 'alloy-listen'
  parent: appServiceLogsEventHub
  properties: {
    rights: [
      'Listen'
    ]
  }
}

resource appLogDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = [for (app, i) in deployableApps: {
  name: 'send-appservice-logs-to-eventhub'
  scope: apps[i]
  properties: {
    eventHubAuthorizationRuleId: diagnosticSendRule.id
    eventHubName: appServiceLogsEventHub.name
    logs: [for category in diagnosticLogCategories: {
      category: category
      enabled: true
      retentionPolicy: {
        enabled: false
        days: 0
      }
    }]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: false
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}]

output environment string = environmentName
output appServicePlanName string = appServicePlan.name
output apps array = [for app in deployableApps: {
  appId: app.appId
  name: 'app-${normalizedProjectName}-${environmentName}-${app.role == 'web' ? 'web' : app.appId}-${uniqueSuffix}'
  url: 'https://app-${normalizedProjectName}-${environmentName}-${app.role == 'web' ? 'web' : app.appId}-${uniqueSuffix}.azurewebsites.net'
  role: app.role
  artifactName: app.artifactName
  healthPath: app.healthPath
}]
output siteAppName string = siteAppName
output siteAppUrl string = siteAppUrl
output apiAppName string = apiAppName
output apiAppUrl string = apiAppUrl
output sqliteDbPath string = sqliteDbPath
output eventHubNamespace string = eventHubNamespace.name
output eventHubName string = appServiceLogsEventHub.name
output eventHubConsumerGroup string = alloyConsumerGroup.name
output alloyListenAuthorizationRule string = alloyListenRule.name
output diagnosticSettings array = [for (app, i) in deployableApps: {
  appId: app.appId
  appName: apps[i].name
  name: appLogDiagnosticSettings[i].name
}]
