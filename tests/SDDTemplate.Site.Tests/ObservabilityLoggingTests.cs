using System.Text.Json;

namespace SDDTemplate.Site.Tests
{
    public sealed class ObservabilityLoggingTests
    {
        public static IEnumerable<object[]> ApplicationConfigPaths()
        {
            yield return ["src/SDDTemplate.Api"];
            yield return ["src/SDDTemplate.Site"];
        }

        [Theory]
        [MemberData(nameof(ApplicationConfigPaths))]
        public void ApplicationConfigUsesVerboseLoggingForDevAndQa(string appPath)
        {
            string root = FindRepositoryRoot();
            string development = Path.Combine(root, appPath, "appsettings.Development.json");
            string staging = Path.Combine(root, appPath, "appsettings.Staging.json");

            Assert.Equal("Verbose", ReadSerilogMinimumLevel(development));
            Assert.Equal("Verbose", ReadSerilogMinimumLevel(staging));
        }

        [Theory]
        [MemberData(nameof(ApplicationConfigPaths))]
        public void ApplicationConfigRestrictsProductionLogging(string appPath)
        {
            string root = FindRepositoryRoot();
            string production = Path.Combine(root, appPath, "appsettings.Production.json");
            string defaults = Path.Combine(root, appPath, "appsettings.json");

            Assert.Equal("Warning", ReadSerilogMinimumLevel(production));
            Assert.Equal("Warning", ReadSerilogMinimumLevel(defaults));
        }

        [Theory]
        [MemberData(nameof(ApplicationConfigPaths))]
        public void SerilogConsoleOutputIncludesStructuredFilterFields(string appPath)
        {
            string root = FindRepositoryRoot();
            string appsettings = Path.Combine(root, appPath, "appsettings.json");
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(appsettings));

            string template = document.RootElement
                .GetProperty("Serilog")
                .GetProperty("WriteTo")[0]
                .GetProperty("Args")
                .GetProperty("outputTemplate")
                .GetString()!;

            Assert.Contains("{Timestamp:O}", template);
            Assert.Contains("{Level:u3}", template);
            Assert.Contains("{SourceContext}", template);
            Assert.Contains("{Message:lj}", template);
            Assert.Contains("{Exception}", template);
        }

        [Fact]
        public void DeploymentConfigLeavesSerilogStaticConfigOutOfAppSettingsMutation()
        {
            string root = FindRepositoryRoot();
            string configurationPath = Path.Combine(root, "infra", "deployment", "configuration.json");
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(configurationPath));

            JsonElement ignoredPrefixes = document.RootElement.GetProperty("ignoredPrefixes");

            Assert.Contains(ignoredPrefixes.EnumerateArray(), prefix => prefix.GetString() == "Serilog");
        }

        [Fact]
        public void AzureBicepDefinesLogAnalyticsWorkspacesAndDiagnostics()
        {
            string root = FindRepositoryRoot();
            string bicep = File.ReadAllText(Path.Combine(root, "infra", "azure", "main.bicep"));

            Assert.Contains("Microsoft.OperationalInsights/workspaces", bicep);
            Assert.Contains("logAnalyticsWorkspaceName", bicep);
            Assert.Contains("workspaceId: logAnalyticsWorkspace.id", bicep);
            Assert.Contains("logAnalyticsDestinationType: 'Dedicated'", bicep);
            Assert.Contains("AppServiceConsoleLogs", bicep);
            Assert.Contains("AppServiceHTTPLogs", bicep);
        }

        [Fact]
        public void AzureMonitorValidationScriptRequiresEveryEnvironment()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "validate-azure-monitor-logs.ps1"));

            Assert.Contains("GRAFANA_AZURE_TENANT_ID", script);
            Assert.Contains("GRAFANA_AZURE_CLIENT_ID", script);
            Assert.Contains("GRAFANA_AZURE_CLIENT_SECRET", script);
            Assert.Contains("GRAFANA_AZURE_SUBSCRIPTION_ID", script);
            Assert.Contains("GRAFANA_AZURE_DEV_LOG_ANALYTICS_WORKSPACE_ID", script);
            Assert.Contains("GRAFANA_AZURE_QA_LOG_ANALYTICS_WORKSPACE_ID", script);
            Assert.Contains("GRAFANA_AZURE_PROD_LOG_ANALYTICS_WORKSPACE_ID", script);
            Assert.Contains("az monitor log-analytics query", script);
            Assert.Contains("dev", script);
            Assert.Contains("qa", script);
            Assert.Contains("prod", script);
        }

        [Fact]
        public void GrafanaDatasourceProvisioningDefinesStableUidsForDashboardReferences()
        {
            string root = FindRepositoryRoot();
            string datasourcePath = Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "datasources", "azure-monitor.yml");
            string datasources = File.ReadAllText(datasourcePath);

            Assert.Contains("name: Azure Monitor", datasources);
            Assert.Contains("uid: azure-monitor", datasources);
            Assert.Contains("type: grafana-azure-monitor-datasource", datasources);
            Assert.Contains("GRAFANA_AZURE_CLIENT_SECRET", datasources);
        }

        [Fact]
        public void GrafanaDashboardProvisioningLoadsGeneratedLocalAzureMonitorDashboards()
        {
            string root = FindRepositoryRoot();
            string dashboards = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "dashboards", "dashboards.yml"));

            Assert.Contains("Agentic E2E Local", dashboards);
            Assert.Contains("/var/lib/grafana/dashboards.local", dashboards);
        }

        private static string ReadSerilogMinimumLevel(string path)
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
            return document.RootElement
                .GetProperty("Serilog")
                .GetProperty("MinimumLevel")
                .GetProperty("Default")
                .GetString()!;
        }

        private static string FindRepositoryRoot()
        {
            DirectoryInfo? directory = new(AppContext.BaseDirectory);
            while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "SDDTemplate.slnx")))
            {
                directory = directory.Parent;
            }

            return directory?.FullName ?? throw new InvalidOperationException("Could not locate repository root.");
        }
    }
}
