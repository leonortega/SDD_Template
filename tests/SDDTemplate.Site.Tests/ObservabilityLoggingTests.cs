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
        public void ApplicationConfigUsesDebugLoggingForDevAndQa(string appPath)
        {
            string root = FindRepositoryRoot();
            string development = Path.Combine(root, appPath, "appsettings.Development.json");
            string staging = Path.Combine(root, appPath, "appsettings.Staging.json");

            Assert.Equal("Debug", ReadSerilogMinimumLevel(development));
            Assert.Equal("Debug", ReadSerilogMinimumLevel(staging));
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
        public void ApplicationConfigLoadsSeqSinkForLiveLogSearch(string appPath)
        {
            string root = FindRepositoryRoot();
            string appsettings = Path.Combine(root, appPath, "appsettings.json");
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(appsettings));

            JsonElement usingEntries = document.RootElement
                .GetProperty("Serilog")
                .GetProperty("Using");

            Assert.Contains(usingEntries.EnumerateArray(), entry => entry.GetString() == "Serilog.Sinks.Console");
            Assert.Contains(usingEntries.EnumerateArray(), entry => entry.GetString() == "Serilog.Sinks.Seq");
        }

        [Fact]
        public void SharedLoggingPackageIncludesSeqSink()
        {
            string root = FindRepositoryRoot();
            string project = File.ReadAllText(Path.Combine(root, "src", "SDDTemplate.Common", "SDDTemplate.Common.csproj"));

            Assert.Contains("Serilog.Sinks.Seq", project);
            Assert.Contains("Version=\"9.1.0\"", project);
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
        public void DeploymentConfigIgnoresSerilogStaticSubtree()
        {
            string root = FindRepositoryRoot();
            string configurationPath = Path.Combine(root, "infra", "deployment", "configuration.json");
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(configurationPath));

            JsonElement ignoredPrefixes = document.RootElement.GetProperty("ignoredPrefixes");

            Assert.Contains(ignoredPrefixes.EnumerateArray(), prefix => prefix.GetString() == "Serilog");
        }

        [Fact]
        public void DeploymentConfigAppliesEnvironmentSpecificLogLevels()
        {
            string root = FindRepositoryRoot();
            string configurationPath = Path.Combine(root, "infra", "deployment", "configuration.json");
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(configurationPath));

            JsonElement settings = document.RootElement.GetProperty("settings");

            foreach (string appId in new[] { "api", "site" })
            {
                Assert.Contains(settings.EnumerateArray(), setting =>
                    setting.GetProperty("appId").GetString() == appId
                    && setting.GetProperty("name").GetString() == "Serilog__MinimumLevel__Default"
                    && setting.GetProperty("source").GetString() == "environmentLogLevel");

                Assert.Contains(settings.EnumerateArray(), setting =>
                    setting.GetProperty("appId").GetString() == appId
                    && setting.GetProperty("name").GetString() == "Logging__LogLevel__Default"
                    && setting.GetProperty("source").GetString() == "environmentLogLevel");
            }
        }

        [Fact]
        public void DeploymentWorkflowResolvesEnvironmentSpecificLogLevels()
        {
            string root = FindRepositoryRoot();
            string workflow = File.ReadAllText(Path.Combine(root, ".gitea", "workflows", "package-deploy.yml"));
            string configureScript = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "scripts", "configure_infra_tools.py"));

            foreach (string source in new[] { workflow, configureScript })
            {
                Assert.Contains("environmentLogLevel)", source);
                Assert.Contains("printf '%s' \"Debug\"", source);
                Assert.Contains("printf '%s' \"Warning\"", source);
            }
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
        public void MonitoringComposeDoesNotRunLocalOtelCollector()
        {
            string root = FindRepositoryRoot();
            string compose = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "compose.yml"));
            string envExample = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "variables.env.example"));

            Assert.DoesNotContain("otel/opentelemetry-collector-contrib", compose);
            Assert.DoesNotContain("agentic-otelcol", compose);
            Assert.DoesNotContain("otelcol-data", compose);
            Assert.DoesNotContain("agentic-prometheus", compose);
            Assert.DoesNotContain("agentic-blackbox", compose);
            Assert.Contains("GF_PLUGINS_PREINSTALL_SYNC: yesoreyeram-infinity-datasource@3.8.0", compose);
            Assert.DoesNotContain("OTELCOL_", envExample);
        }

        [Fact]
        public void GrafanaHealthAlertProvisioningUsesConfigurablePendingDuration()
        {
            string root = FindRepositoryRoot();
            string compose = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "compose.yml"));
            string envExample = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "variables.env.example"));
            string alert = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "alerting", "health-alerts.yml"));

            Assert.Contains("./grafana/provisioning:/etc/grafana/provisioning:ro", compose);
            Assert.Contains("GRAFANA_HEALTH_ALERT_FOR: ${GRAFANA_HEALTH_ALERT_FOR:-2m}", compose);
            Assert.Contains("GRAFANA_HEALTH_ALERT_FOR=2m", envExample);
            Assert.Contains("datasourceUid: infinity-health", alert);
            Assert.Contains("computed_columns:", alert);
            Assert.Contains("selector: \"status == 'ok' ? 1 : 0\"", alert);
            Assert.Contains("root_is_not_array: true", alert);
            Assert.Contains("root_selector: \"\"", alert);
            Assert.Contains("type: lt", alert);
            Assert.Contains("url: http://host.docker.internal:18081/health", alert);
            Assert.DoesNotContain("probe_success", alert);
            Assert.Contains("for: ${GRAFANA_HEALTH_ALERT_FOR}", alert);
            Assert.Contains("noDataState: OK", alert);
            Assert.Contains("execErrState: OK", alert);
        }

        [Fact]
        public void SeqErrorAlertConfigurationUsesNativeSeqAlerting()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "scripts", "configure_infra_tools.py"));
            string envExample = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "variables.env.example"));

            Assert.Contains("Agentic E2E - Any Seq Error Logs", script);
            Assert.Contains("api/alerts/template", script);
            Assert.Contains("api/alerts", script);
            Assert.Contains("SEQ_ERROR_ALERT_WINDOW=1m", envExample);
            Assert.Contains("SEQ_ERROR_ALERT_THRESHOLD=0", envExample);
        }

        [Fact]
        public void GrafanaInfinityDatasourceProvisioningExistsForHealthBoards()
        {
            string root = FindRepositoryRoot();
            string datasourcePath = Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "datasources", "infinity-health.yml");
            string removedPrometheusPath = Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "datasources", "prometheus.yml");
            string removedAzureMonitorPath = Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "datasources", "azure-monitor.yml");

            Assert.True(File.Exists(datasourcePath));
            Assert.False(File.Exists(removedPrometheusPath));
            Assert.False(File.Exists(removedAzureMonitorPath));
            string datasource = File.ReadAllText(datasourcePath);
            Assert.Contains("deleteDatasources:", datasource);
            Assert.Contains("name: Prometheus", datasource);
            Assert.Contains("uid: infinity-health", datasource);
            Assert.Contains("type: yesoreyeram-infinity-datasource", datasource);
            Assert.Contains("http://host.docker.internal:18081", datasource);
            Assert.Contains("http://host.docker.internal:18086", datasource);
        }

        [Fact]
        public void GrafanaDashboardProvisioningLoadsGeneratedLocalHealthDashboards()
        {
            string root = FindRepositoryRoot();
            string dashboards = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "dashboards", "dashboards.yml"));
            string devDashboardPath = Path.Combine(root, "infra", "monitoring", "grafana", "dashboards.local", "dev-health-dashboard.json");

            Assert.Contains("Agentic E2E Local", dashboards);
            Assert.Contains("/var/lib/grafana/dashboards.local", dashboards);
            Assert.Contains("infra/monitoring/grafana/dashboards.local/", File.ReadAllText(Path.Combine(root, ".gitignore")));

            if (!File.Exists(devDashboardPath))
            {
                return;
            }

            string devDashboard = File.ReadAllText(devDashboardPath);
            Assert.Contains("\"uid\": \"infinity-health\"", devDashboard);
            Assert.Contains("yesoreyeram-infinity-datasource", devDashboard);
            Assert.Contains("\"parser\": \"backend\"", devDashboard);
            Assert.Contains("\"root_is_not_array\": true", devDashboard);
            Assert.Contains("\"selector\": \"status\"", devDashboard);
            Assert.Contains("\"computed_columns\"", devDashboard);
            Assert.Contains("\"selector\": \"status == 'ok' ? 1 : 0\"", devDashboard);
            Assert.Contains("\"text\": \"up\"", devDashboard);
            Assert.Contains("\"1\"", devDashboard);
            Assert.Contains("\"text\": \"UP\"", devDashboard);
            Assert.Contains("DEV K8 Web/API Health", devDashboard);
            Assert.Contains("\"url\": \"http://host.docker.internal:18081/health\"", devDashboard);
            Assert.Contains("\"url\": \"http://host.docker.internal:18082/health\"", devDashboard);
            Assert.DoesNotContain("probe_success", devDashboard);
            Assert.DoesNotContain("prometheus", devDashboard, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("app=\\\"web\\\"", devDashboard);
            Assert.DoesNotContain("Azure", devDashboard);
        }

        [Fact]
        public void ConfigureInfraGeneratesK8GrafanaHealthDashboards()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "scripts", "configure_infra_tools.py"));

            Assert.Contains("Write-GrafanaK8HealthDashboards", script);
            Assert.Contains("New-GrafanaK8HealthDashboard", script);
            Assert.Contains("DEV K8 Web/API Health", script);
            Assert.Contains("QA K8 Web/API Health", script);
            Assert.Contains("PROD K8 Web/API Health", script);
            Assert.Contains("host.docker.internal:18081", script);
            Assert.Contains("host.docker.internal:18086", script);
            Assert.Contains("infinity-health", script);
            Assert.Contains("grafana-legacy-dashboard", script);
        }

        [Fact]
        public void ConfigureInfraShowsEnvironmentUrls()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "scripts", "configure_infra_tools.py"));
            string gitignore = File.ReadAllText(Path.Combine(root, ".gitignore"));

            Assert.Contains("\"ShowEnvironmentUrls\"", script);
            Assert.Contains("Invoke-ShowEnvironmentUrls", script);
            Assert.Contains("Write-EnvironmentUrlRegistry", script);
            Assert.Contains(".codex/environment-urls.local.json", script);
            Assert.Contains("Environment URLs", script);
            Assert.Contains("agentic-environment-urls", script);
            Assert.Contains("LocalPort = 18081", script);
            Assert.Contains("LocalPort = 18086", script);
            Assert.Contains("http://127.0.0.1:$($mapping.LocalPort)", script);
            Assert.Contains("http://host.docker.internal:$($mapping.LocalPort)", script);
            Assert.Contains("sdd.localhost", script);
            Assert.Contains(".codex/environment-urls.local.json", gitignore);
        }

        [Fact]
        public void ConfigureInfraUsesCollectorBasedSeqIngestionOnly()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "scripts", "configure_infra_tools.py"));
            string observabilitySkill = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-observability", "SKILL.md"));

            Assert.Contains("SetSeqAzureEventHubLogs", script);
            Assert.DoesNotContain("RANCHER_OBSERVABILITY_ENABLED", script);
            Assert.Contains("Rancher Desktop.ready", script);
            Assert.DoesNotContain("Azure collector-based Seq ingestion path", script);
            Assert.Contains("Grafana Infinity health checks", observabilitySkill);
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
