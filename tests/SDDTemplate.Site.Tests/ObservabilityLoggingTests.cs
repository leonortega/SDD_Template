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
            Assert.DoesNotContain("Authorization", template, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("password", template, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("token", template, StringComparison.OrdinalIgnoreCase);
        }

        [Theory]
        [MemberData(nameof(ApplicationConfigPaths))]
        public void ProgramConfiguresCorrelationAwareRequestLoggingWithoutSensitivePayloads(string appPath)
        {
            string root = FindRepositoryRoot();
            string programPath = Path.Combine(root, appPath, "Program.cs");
            string program = File.ReadAllText(programPath);

            Assert.Contains("UseCorrelationAwareRequestLogging", program);
            Assert.DoesNotContain("diagnosticContext.Set(\"Authorization\"", program, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("diagnosticContext.Set(\"RequestBody\"", program, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("diagnosticContext.Set(\"password\"", program, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("diagnosticContext.Set(\"token\"", program, StringComparison.OrdinalIgnoreCase);
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
        public void AzureBicepDoesNotProvisionLogAnalyticsByDefault()
        {
            string root = FindRepositoryRoot();
            string bicep = File.ReadAllText(Path.Combine(root, "infra", "azure", "main.bicep"));

            Assert.DoesNotContain("Microsoft.OperationalInsights/workspaces", bicep);
            Assert.DoesNotContain("logAnalyticsWorkspaceName", bicep);
            Assert.DoesNotContain("workspaceId: logAnalyticsWorkspace.id", bicep);
            Assert.DoesNotContain("logAnalyticsDestinationType: 'Dedicated'", bicep);
            Assert.Contains("Microsoft.Web/sites@2023-12-01", bicep);
        }

        [Fact]
        public void AzureMonitorValidationScriptIsRemovedFromOperationalPath()
        {
            string root = FindRepositoryRoot();
            string path = Path.Combine(root, "infra", "monitoring", "validate-azure-monitor-logs.ps1");
            Assert.False(File.Exists(path));
        }

        [Fact]
        public void SeqComposeServiceIsLocalhostBoundAndPinned()
        {
            string root = FindRepositoryRoot();
            string compose = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "compose.yml"));

            Assert.Contains("seq-data:", compose);
            Assert.Contains("seq:", compose);
            Assert.Contains("image: datalust/seq:2025.2.16202", compose);
            Assert.Contains("container_name: agentic-seq", compose);
            Assert.Contains("ACCEPT_EULA: \"Y\"", compose);
            Assert.Contains("SEQ_FIRSTRUN_NOAUTHENTICATION: \"True\"", compose);
            Assert.Contains("\"127.0.0.1:5341:80\"", compose);
            Assert.Contains("SEQ_API_CANONICALURI: http://localhost:5341/", compose);
        }

        [Fact]
        public void CollectorComposeDefinesOptionalEventHubProfile()
        {
            string root = FindRepositoryRoot();
            string compose = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "compose.yml"));
            string collector = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "otelcol", "collector.yaml"));
            string envExample = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "variables.env.example"));

            Assert.Contains("image: otel/opentelemetry-collector-contrib:0.154.0", compose);
            Assert.Contains("profiles:", compose);
            Assert.Contains("eventhub", compose);
            Assert.Contains("agentic-otelcol", compose);
            Assert.Contains("agentic-prometheus", compose);
            Assert.Contains("agentic-blackbox", compose);
            Assert.Contains("--web.listen-address=0.0.0.0:9115", compose);
            Assert.Contains("azure_event_hub/dev", collector);
            Assert.Contains("azure_event_hub/qa", collector);
            Assert.Contains("azure_event_hub/prod", collector);
            Assert.Contains("otlphttp/seq", collector);
            Assert.Contains("OTELCOL_AZURE_EVENT_HUB_DEV_CONNECTION_STRING", envExample);
            Assert.Contains("OTELCOL_AZURE_EVENT_HUB_QA_CONNECTION_STRING", envExample);
            Assert.Contains("OTELCOL_AZURE_EVENT_HUB_PROD_CONNECTION_STRING", envExample);
        }

        [Fact]
        public void GrafanaHealthAlertProvisioningUsesConfigurablePendingDuration()
        {
            string root = FindRepositoryRoot();
            string compose = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "compose.yml"));
            string prometheus = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "prometheus", "prometheus.yml"));
            string blackbox = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "prometheus", "blackbox.yml"));
            string envExample = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "variables.env.example"));
            string alert = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "alerting", "health-alerts.yml"));

            Assert.Contains("./grafana/provisioning:/etc/grafana/provisioning:ro", compose);
            Assert.Contains("GRAFANA_HEALTH_ALERT_FOR: ${GRAFANA_HEALTH_ALERT_FOR:-10s}", compose);
            Assert.Contains("scrape_interval: 10s", prometheus);
            Assert.Contains("evaluation_interval: 10s", prometheus);
            Assert.Contains("scrape_timeout: 10s", prometheus);
            Assert.Contains("timeout: 9s", blackbox);
            Assert.Contains("GRAFANA_HEALTH_ALERT_FOR=10s", envExample);
            Assert.Contains("probe_success{job=\"blackbox_http_health\"} == 0", alert);
            Assert.Contains("for: ${GRAFANA_HEALTH_ALERT_FOR}", alert);
            Assert.Contains("noDataState: OK", alert);
            Assert.Contains("execErrState: OK", alert);
        }

        [Fact]
        public void SeqErrorAlertConfigurationUsesNativeSeqAlerting()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "scripts", "configure_infra_tools.ps1"));
            string envExample = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "variables.env.example"));

            Assert.Contains("Agentic E2E - Any Seq Error Logs", script);
            Assert.Contains("api/alerts/template", script);
            Assert.Contains("api/alerts", script);
            Assert.Contains("SEQ_ERROR_ALERT_WINDOW=1m", envExample);
            Assert.Contains("SEQ_ERROR_ALERT_THRESHOLD=0", envExample);
        }

        [Fact]
        public void GrafanaPrometheusDatasourceProvisioningExistsForHealthBoards()
        {
            string root = FindRepositoryRoot();
            string datasourcePath = Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "datasources", "prometheus.yml");
            string removedAzureMonitorPath = Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "datasources", "azure-monitor.yml");

            Assert.True(File.Exists(datasourcePath));
            Assert.False(File.Exists(removedAzureMonitorPath));
            Assert.Contains("uid: prometheus", File.ReadAllText(datasourcePath));
        }

        [Fact]
        public void GrafanaDashboardProvisioningLoadsGeneratedLocalHealthDashboards()
        {
            string root = FindRepositoryRoot();
            string dashboards = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "dashboards", "dashboards.yml"));
            string devDashboard = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "grafana", "dashboards.local", "dev-health-dashboard.json"));

            Assert.Contains("Agentic E2E Local", dashboards);
            Assert.Contains("/var/lib/grafana/dashboards.local", dashboards);
            Assert.Contains("\"uid\": \"prometheus\"", devDashboard);
            Assert.Contains("probe_success", devDashboard);
        }

        [Fact]
        public void ConfigureInfraUsesCollectorBasedSeqIngestionOnly()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "scripts", "configure_infra_tools.ps1"));

            Assert.Contains("SetSeqAzureEventHubLogs", script);
            Assert.DoesNotContain("SetSeqAzureLogs", script);
            Assert.DoesNotContain("\"SetGrafanaAzureMonitor\"", script);
        }

        [Fact]
        public void MonitoringComposeSharesTheAgenticE2eProjectCollection()
        {
            string root = FindRepositoryRoot();
            string compose = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "compose.yml"));

            Assert.Contains("name: agentic-e2e", compose);
            Assert.DoesNotContain("name: agentic-monitoring", compose);
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
