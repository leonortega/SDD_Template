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
        public void AlloyConfigDefinesSeparateAzureConsumersForEachEnvironment()
        {
            string root = FindRepositoryRoot();
            string alloy = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "alloy", "config.alloy"));

            Assert.Contains("loki.source.azure_event_hubs \"dev\"", alloy);
            Assert.Contains("loki.source.azure_event_hubs \"qa\"", alloy);
            Assert.Contains("loki.source.azure_event_hubs \"prod\"", alloy);
            Assert.Contains("AZURE_DEV_EVENTHUB_NAMESPACE", alloy);
            Assert.Contains("AZURE_QA_EVENTHUB_NAMESPACE", alloy);
            Assert.Contains("AZURE_PROD_EVENTHUB_NAMESPACE", alloy);
            Assert.Contains("environment = \"dev\"", alloy);
            Assert.Contains("environment = \"qa\"", alloy);
            Assert.Contains("environment = \"prod\"", alloy);
            Assert.Contains("group_id                  = \"grafana-alloy-dev\"", alloy);
            Assert.Contains("group_id                  = \"grafana-alloy-qa\"", alloy);
            Assert.Contains("group_id                  = \"grafana-alloy-prod\"", alloy);
            Assert.Contains("loki.write \"local\"", alloy);
        }

        [Fact]
        public void AzureLogIngestionValidationScriptRequiresEveryEnvironment()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "validate-azure-log-ingestion.ps1"));

            Assert.Contains("AZURE_DEV_EVENTHUB_NAMESPACE", script);
            Assert.Contains("AZURE_DEV_EVENTHUB_NAME", script);
            Assert.Contains("AZURE_QA_EVENTHUB_NAMESPACE", script);
            Assert.Contains("AZURE_QA_EVENTHUB_NAME", script);
            Assert.Contains("AZURE_PROD_EVENTHUB_NAMESPACE", script);
            Assert.Contains("AZURE_PROD_EVENTHUB_NAME", script);
            Assert.Contains("AZURE_CLIENT_ID", script);
            Assert.Contains("AZURE_TENANT_ID", script);
            Assert.Contains("AZURE_CLIENT_SECRET", script);
            Assert.Contains("/loki/api/v1/query_range", script);
            Assert.Contains("dev", script);
            Assert.Contains("qa", script);
            Assert.Contains("prod", script);
        }

        [Fact]
        public void GrafanaDatasourceProvisioningDefinesStableUidsForDashboardReferences()
        {
            string root = FindRepositoryRoot();
            string datasourcePath = Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "datasources", "prometheus.yml");
            string datasources = File.ReadAllText(datasourcePath);

            Assert.Contains("name: Prometheus", datasources);
            Assert.Contains("uid: Prometheus", datasources);
            Assert.Contains("name: Loki", datasources);
            Assert.Contains("uid: Loki", datasources);
        }

        [Theory]
        [InlineData("dev", "DEV")]
        [InlineData("qa", "QA")]
        [InlineData("prod", "PROD")]
        public void GrafanaLogBoardsFilterByEnvironmentTextTimeAndCategory(string environment, string titlePrefix)
        {
            string root = FindRepositoryRoot();
            string dashboardPath = Path.Combine(root, "infra", "monitoring", "grafana", "dashboards", $"{environment}-azure-logs.json");
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(dashboardPath));
            JsonElement rootElement = document.RootElement;

            Assert.Equal($"{titlePrefix} Azure Logs", rootElement.GetProperty("title").GetString());
            Assert.True(rootElement.TryGetProperty("time", out JsonElement time));
            Assert.Equal("now-6h", time.GetProperty("from").GetString());
            Assert.Equal("now", time.GetProperty("to").GetString());

            JsonElement variables = rootElement.GetProperty("templating").GetProperty("list");
            Assert.Contains(variables.EnumerateArray(), variable => variable.GetProperty("name").GetString() == "text");
            Assert.Contains(variables.EnumerateArray(), variable => variable.GetProperty("name").GetString() == "category");

            string expression = rootElement.GetProperty("panels")[0]
                .GetProperty("targets")[0]
                .GetProperty("expr")
                .GetString()!;

            Assert.Contains($"environment=\"{environment}\"", expression);
            Assert.Contains("category=~\"$category\"", expression);
            Assert.Contains("|~ \"$text\"", expression);
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
