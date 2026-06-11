using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;

namespace SDDTemplate.DeliveryTools.Tests
{
    public sealed class DeliveryToolsTests
    {
        [Fact]
        public void ExtractTicketKeySupportsTicketCommitsAndGiteaMergeCommits()
        {
            const string pattern = "E2EPROJECT-[0-9]+";

            Assert.Equal(
                "E2EPROJECT-123",
                DeliveryWorkflowHelpers.ExtractTicketKey("E2EPROJECT-123: Add flow", pattern));
            Assert.Equal(
                "E2EPROJECT-456",
                DeliveryWorkflowHelpers.ExtractTicketKey("Merge pull request 'E2EPROJECT-456: Add flow' (#7)", pattern));
            Assert.Equal(
                "manual-dispatch",
                DeliveryWorkflowHelpers.ExtractTicketKey("[SDD] Update workflow", pattern, "manual-dispatch"));
        }

        [Fact]
        public void CoverageHelpersReadJsonThresholdAndCoberturaLineRate()
        {
            string root = CreateTempDirectory();
            string qualityPath = Path.Combine(root, "quality.json");
            string coveragePath = Path.Combine(root, "coverage.cobertura.xml");
            File.WriteAllText(qualityPath, JsonSerializer.Serialize(new { coverage = new { minimumPercent = 87 } }));
            File.WriteAllText(coveragePath, """<coverage line-rate="0.9123"></coverage>""");

            Assert.Equal(87, DeliveryWorkflowHelpers.ReadCoverageThreshold(qualityPath, 80));
            Assert.Equal(80, DeliveryWorkflowHelpers.ReadCoverageThreshold(Path.Combine(root, "missing.json"), 80));
            Assert.Equal(91.23m, DeliveryWorkflowHelpers.ReadCoberturaCoveragePercent(coveragePath));
        }

        [Fact]
        public void ReleaseManifestValidationReportsRequiredFieldsAndVersionFormats()
        {
            string root = CreateTempDirectory();
            string validPath = Path.Combine(root, "release.json");
            DeliveryWorkflowHelpers.CreateReleaseManifest(
                validPath,
                "abcdef1",
                "abc123",
                "http://nexus/repository/raw-hosted/app/abcdef1/site.zip",
                "E2EPROJECT-1",
                "unversioned");

            ReleaseManifestValidation valid = DeliveryWorkflowHelpers.ValidateReleaseManifest(validPath);
            Assert.True(valid.Valid);

            string invalidPath = Path.Combine(root, "invalid-release.json");
            File.WriteAllText(invalidPath, JsonSerializer.Serialize(new { schemaVersion = 1, commitSha = "not-a-sha" }));

            ReleaseManifestValidation invalid = DeliveryWorkflowHelpers.ValidateReleaseManifest(invalidPath);
            Assert.False(invalid.Valid);
            Assert.Contains(invalid.Errors, error => error.Contains("planeTicketKey", StringComparison.Ordinal));
            Assert.Contains(invalid.Errors, error => error.Contains("commitSha", StringComparison.Ordinal));
        }

        [Fact]
        public void TicketReadinessClassifiesReadyEnrichableAndBlockedTickets()
        {
            TicketReadinessResult ready = DeliveryWorkflowHelpers.ClassifyTicketReadiness(
                "Add client search",
                """
                Acceptance criteria:
                - Searching by client name filters the list.
                - Empty searches show all clients.
                Validation: add tests for matching and empty search.
                """);

            TicketReadinessResult enrichable = DeliveryWorkflowHelpers.ClassifyTicketReadiness(
                "Add client search",
                "Users should be able to search clients by name from the client list.");

            TicketReadinessResult blocked = DeliveryWorkflowHelpers.ClassifyTicketReadiness("Search", "Do thing");

            Assert.Equal("ready", ready.Status);
            Assert.Empty(ready.Missing);
            Assert.Equal("enrichable", enrichable.Status);
            Assert.Contains("validation expectation", enrichable.Missing);
            Assert.Equal("blocked", blocked.Status);
            Assert.Contains("user-visible goal", blocked.Missing);
        }

        [Fact]
        public void DeliveryRiskClassifiesLowStandardAndHighWork()
        {
            DeliveryRiskResult low = DeliveryWorkflowHelpers.ClassifyDeliveryRisk(["docs/development.md"], "clarify setup text", 12);
            DeliveryRiskResult standard = DeliveryWorkflowHelpers.ClassifyDeliveryRisk(["src/Feature.cs", "tests/FeatureTests.cs"], "normal feature", 120);
            DeliveryRiskResult high = DeliveryWorkflowHelpers.ClassifyDeliveryRisk([".gitea/workflows/package-deploy.yml"], "deployment health check", 40);

            Assert.Equal("low", low.Level);
            Assert.Equal("standard", standard.Level);
            Assert.Equal("high", high.Level);
            Assert.Contains(high.Reasons, reason => reason.Contains("deployment", StringComparison.Ordinal));
        }

        [Fact]
        public void WorkloadForecastParsesGuardLinesAndRequiresResolutionForOversizedWork()
        {
            const string markdown = """
                ## Review Workload Forecast

                Estimated changed lines: 650
                400-line budget risk: High
                Chained PRs recommended: Yes
                Decision needed before apply: Yes
                Delivery strategy: ask-on-risk
                """;

            WorkloadForecast forecast = DeliveryWorkflowHelpers.ParseWorkloadForecast(markdown);

            Assert.Equal("650", forecast.EstimatedChangedLines);
            Assert.Equal("High", forecast.BudgetRisk);
            Assert.True(forecast.ChainedPrsRecommended);
            Assert.True(forecast.DecisionNeededBeforeApply);
            Assert.True(forecast.RequiresResolutionBeforeApply);
        }

        [Fact]
        public void WorkloadForecastAllowsLowRiskSinglePrWork()
        {
            const string markdown = """
                ## Review Workload Forecast

                Estimated changed lines: 80-180
                400-line budget risk: Low
                Chained PRs recommended: No
                Decision needed before apply: No
                Delivery strategy: single-pr
                """;

            WorkloadForecast forecast = DeliveryWorkflowHelpers.ParseWorkloadForecast(markdown);

            Assert.Equal("80-180", forecast.EstimatedChangedLines);
            Assert.Equal("Low", forecast.BudgetRisk);
            Assert.False(forecast.ChainedPrsRecommended);
            Assert.False(forecast.DecisionNeededBeforeApply);
            Assert.False(forecast.RequiresResolutionBeforeApply);
        }

        [Fact]
        public void AdversarialReviewTriggerRequiresReviewForHighRiskOrExplicitRequests()
        {
            AdversarialReviewTrigger standard = DeliveryWorkflowHelpers.DetectAdversarialReviewTrigger(["docs/readme.md"], "docs only", 8, explicitRequest: false);
            AdversarialReviewTrigger highRisk = DeliveryWorkflowHelpers.DetectAdversarialReviewTrigger(["src/SDDTemplate.Site/Program.cs"], "health endpoint", 30, explicitRequest: false);
            AdversarialReviewTrigger explicitRequest = DeliveryWorkflowHelpers.DetectAdversarialReviewTrigger(["docs/readme.md"], "docs only", 8, explicitRequest: true);

            Assert.False(standard.Required);
            Assert.Equal("standard", standard.Mode);
            Assert.True(highRisk.Required);
            Assert.Equal("adversarial", highRisk.Mode);
            Assert.True(explicitRequest.Required);
            Assert.Contains("explicit user request", explicitRequest.Reasons);
        }

        [Fact]
        public void InstalledSkillIndexIsDerivedCachedAndExcludesSharedHelpers()
        {
            string root = CreateTempDirectory();
            string skill = Path.Combine(root, ".codex", "skills", "sample-skill");
            string shared = Path.Combine(root, ".codex", "skills", "_shared");
            _ = Directory.CreateDirectory(skill);
            _ = Directory.CreateDirectory(shared);
            File.WriteAllText(
                Path.Combine(skill, "SKILL.md"),
                """
                ---
                name: sample-skill
                description: "Trigger: sample work. Does a sample task."
                ---
                # Sample
                """);
            File.WriteAllText(Path.Combine(shared, "SKILL.md"), "# Shared");

            string indexPath = Path.Combine(root, ".codex", "installed-skill-index.local.json");
            string cachePath = Path.Combine(root, ".codex", "installed-skill-index.cache.local.json");
            SkillIndexWriteResult first = DeliveryWorkflowHelpers.WriteInstalledSkillIndex(root, indexPath, cachePath);
            SkillIndexWriteResult second = DeliveryWorkflowHelpers.WriteInstalledSkillIndex(root, indexPath, cachePath);

            Assert.False(first.CacheHit);
            Assert.True(second.CacheHit);
            Assert.Equal(1, first.SkillCount);
            string index = File.ReadAllText(indexPath);
            Assert.Contains("sample-skill", index);
            Assert.DoesNotContain("_shared", index);
        }

        [Fact]
        public void DeploymentConfigBuildsArtifactFromFlattenedAppsettingsAndMappings()
        {
            string root = CreateTempDirectory();
            string site = Path.Combine(root, "src", "Example.Site");
            string api = Path.Combine(root, "src", "Example.Api");
            string infra = Path.Combine(root, "infra", "deployment");
            _ = Directory.CreateDirectory(site);
            _ = Directory.CreateDirectory(api);
            _ = Directory.CreateDirectory(infra);

            File.WriteAllText(Path.Combine(site, "appsettings.json"), JsonSerializer.Serialize(new
            {
                Api = new { BaseUrl = "" },
                Feature = new { Enabled = true },
            }));
            File.WriteAllText(Path.Combine(api, "appsettings.json"), JsonSerializer.Serialize(new
            {
                Cors = new { AllowedOrigins = Array.Empty<string>() },
            }));
            File.WriteAllText(Path.Combine(infra, "apps.json"), JsonSerializer.Serialize(new
            {
                version = 1,
                apps = new object[]
                {
                    new { appId = "site", role = "web", projectPath = "src/Example.Site/Example.Site.csproj" },
                    new { appId = "api", role = "api", projectPath = "src/Example.Api/Example.Api.csproj" },
                },
            }));
            File.WriteAllText(Path.Combine(infra, "configuration.json"), JsonSerializer.Serialize(new
            {
                version = 1,
                settings = new object[]
                {
                    new { appId = "site", name = "Api__BaseUrl", source = "topologyReference", targetAppId = "api", targetProperty = "url", required = true, secret = false },
                    new { appId = "site", name = "Feature__Enabled", source = "literal", value = "true", required = false, secret = false },
                    new { appId = "api", name = "Cors__AllowedOrigins", source = "topologyReference", targetAppId = "site", targetProperty = "url", required = true, secret = false },
                    new { appId = "api", name = "ConnectionStrings__ClientsDb", source = "sqliteDataPath", value = "Data Source=/home/data/app.db", required = true, secret = false, additionalSetting = true },
                },
            }));

            string outputPath = Path.Combine(root, "artifacts", "deployment-config.json");
            DeploymentConfigBuildResult result = DeliveryWorkflowHelpers.BuildDeploymentConfig(
                root,
                Path.Combine(infra, "apps.json"),
                Path.Combine(infra, "configuration.json"),
                outputPath);

            Assert.True(result.Valid);
            using JsonDocument artifact = JsonDocument.Parse(File.ReadAllText(outputPath));
            JsonElement siteConfig = artifact.RootElement.GetProperty("apps").EnumerateArray().Single(item => item.GetProperty("appId").GetString() == "site");
            JsonElement apiConfig = artifact.RootElement.GetProperty("apps").EnumerateArray().Single(item => item.GetProperty("appId").GetString() == "api");
            Assert.Contains(siteConfig.GetProperty("settings").EnumerateArray(), item => item.GetProperty("name").GetString() == "Api__BaseUrl");
            Assert.Contains(apiConfig.GetProperty("settings").EnumerateArray(), item => item.GetProperty("name").GetString() == "ConnectionStrings__ClientsDb");
        }

        [Fact]
        public void DeploymentConfigFailsClosedForUnmappedRequiredSettings()
        {
            string root = CreateTempDirectory();
            string site = Path.Combine(root, "src", "Example.Site");
            string infra = Path.Combine(root, "infra", "deployment");
            _ = Directory.CreateDirectory(site);
            _ = Directory.CreateDirectory(infra);

            File.WriteAllText(Path.Combine(site, "appsettings.json"), JsonSerializer.Serialize(new { NewSetting = new { Value = "missing" } }));
            File.WriteAllText(Path.Combine(infra, "apps.json"), JsonSerializer.Serialize(new
            {
                version = 1,
                apps = new[] { new { appId = "site", role = "web", projectPath = "src/Example.Site/Example.Site.csproj" } },
            }));
            File.WriteAllText(Path.Combine(infra, "configuration.json"), JsonSerializer.Serialize(new { version = 1, settings = Array.Empty<object>() }));

            DeploymentConfigBuildResult result = DeliveryWorkflowHelpers.BuildDeploymentConfig(
                root,
                Path.Combine(infra, "apps.json"),
                Path.Combine(infra, "configuration.json"),
                Path.Combine(root, "deployment-config.json"));

            Assert.False(result.Valid);
            Assert.Contains(result.Errors, error => error.Contains("site:NewSetting__Value", StringComparison.Ordinal));
        }

        [Fact]
        public void AuditModesDoNotWriteLocalClientToolsConfigByDefault()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "client-tools.example.json"),
                Path.Combine(root, ".codex", "client-tools.local.json"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "client-tools.example.json"),
                Path.Combine(root, ".codex", "client-tools.example.json"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "quality.example.json"),
                Path.Combine(root, ".codex", "quality.example.json"));

            string before = File.ReadAllText(Path.Combine(root, ".codex", "client-tools.local.json"));
            string output = RunPowerShellScript("-Mode", "AuditQualityGates", "-Root", root);
            string after = File.ReadAllText(Path.Combine(root, ".codex", "client-tools.local.json"));

            Assert.Equal(before, after);
            using JsonDocument audit = JsonDocument.Parse(output);
            Assert.False(audit.RootElement.GetProperty("writeEnabled").GetBoolean());
            Assert.Contains("Would set inferred local client tool value", output);
        }

        [Fact]
        public void SyncWorktreeLocalConfigCopiesOnlyAllowlistedLocalRuntimeFiles()
        {
            string root = CreateTempDirectory();
            string worktree = Path.Combine(root, "ticket-worktrees", "e2eproject-1");
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            _ = Directory.CreateDirectory(worktree);
            File.WriteAllText(Path.Combine(root, ".codex", "client-tools.local.json"), JsonSerializer.Serialize(new { gitea = new { apiToken = "super-secret-token" } }));
            File.WriteAllText(Path.Combine(root, ".codex", "quality.local.json"), JsonSerializer.Serialize(new { coverage = new { minimumPercent = 80 } }));
            File.WriteAllText(Path.Combine(root, ".codex", "tool-recommendations.local.json"), JsonSerializer.Serialize(new { recommendations = Array.Empty<object>() }));
            File.WriteAllText(Path.Combine(root, ".codex", "parallel-delivery.local.json"), JsonSerializer.Serialize(new { tickets = Array.Empty<object>() }));
            File.WriteAllText(Path.Combine(root, ".codex", "delivery-context.local.json"), JsonSerializer.Serialize(new { ticketKey = "E2EPROJECT-ROOT" }));
            File.WriteAllText(Path.Combine(root, ".codex", "azure-login.local.json"), JsonSerializer.Serialize(new { clientSecret = "do-not-copy" }));

            string output = RunPowerShellScript(
                "-Mode",
                "SyncWorktreeLocalConfig",
                "-Root",
                root,
                "-ValuesJson",
                JsonSerializer.Serialize(new { worktreePaths = new[] { worktree } }));

            Assert.True(File.Exists(Path.Combine(worktree, ".codex", "client-tools.local.json")));
            Assert.True(File.Exists(Path.Combine(worktree, ".codex", "quality.local.json")));
            Assert.True(File.Exists(Path.Combine(worktree, ".codex", "tool-recommendations.local.json")));
            Assert.False(File.Exists(Path.Combine(worktree, ".codex", "parallel-delivery.local.json")));
            Assert.False(File.Exists(Path.Combine(worktree, ".codex", "delivery-context.local.json")));
            Assert.False(File.Exists(Path.Combine(worktree, ".codex", "azure-login.local.json")));
            Assert.DoesNotContain("super-secret-token", output);
            Assert.Contains(".codex/client-tools.local.json", output);
            Assert.Contains(".codex/quality.local.json", output);
        }

        [Fact]
        public void SyncWorktreeLocalConfigOverwritesDifferentAllowlistedFilesWithoutPrintingSecrets()
        {
            string root = CreateTempDirectory();
            string worktree = Path.Combine(root, "ticket-worktrees", "e2eproject-1");
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            _ = Directory.CreateDirectory(Path.Combine(worktree, ".codex"));
            File.WriteAllText(Path.Combine(root, ".codex", "client-tools.local.json"), JsonSerializer.Serialize(new { gitea = new { apiToken = "new-secret-token" } }));
            File.WriteAllText(Path.Combine(root, ".codex", "quality.local.json"), JsonSerializer.Serialize(new { coverage = new { minimumPercent = 85 } }));
            File.WriteAllText(Path.Combine(worktree, ".codex", "client-tools.local.json"), JsonSerializer.Serialize(new { gitea = new { apiToken = "old-secret-token" } }));
            File.WriteAllText(Path.Combine(worktree, ".codex", "quality.local.json"), JsonSerializer.Serialize(new { coverage = new { minimumPercent = 80 } }));

            string output = RunPowerShellScript(
                "-Mode",
                "SyncWorktreeLocalConfig",
                "-Root",
                root,
                "-ValuesJson",
                JsonSerializer.Serialize(new { worktreePaths = new[] { worktree } }));

            Assert.Contains("new-secret-token", File.ReadAllText(Path.Combine(worktree, ".codex", "client-tools.local.json")));
            Assert.Contains("85", File.ReadAllText(Path.Combine(worktree, ".codex", "quality.local.json")));
            Assert.DoesNotContain("new-secret-token", output);
            Assert.DoesNotContain("old-secret-token", output);
            Assert.Contains("Overwrite allowlisted local runtime file", output);
        }

        [Fact]
        public void SyncWorktreeLocalConfigReportsMissingRequiredSourceConfig()
        {
            string root = CreateTempDirectory();
            string worktree = Path.Combine(root, "ticket-worktrees", "e2eproject-1");
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            _ = Directory.CreateDirectory(worktree);
            File.WriteAllText(Path.Combine(root, ".codex", "quality.local.json"), JsonSerializer.Serialize(new { coverage = new { minimumPercent = 80 } }));

            string output = RunPowerShellScript(
                "-Mode",
                "SyncWorktreeLocalConfig",
                "-Root",
                root,
                "-ValuesJson",
                JsonSerializer.Serialize(new { worktreePaths = new[] { worktree } }));
            using JsonDocument result = JsonDocument.Parse(output);
            JsonElement finding = result.RootElement.GetProperty("findings").EnumerateArray().Single(
                item => item.GetProperty("path").GetString() == ".codex/client-tools.local.json");

            Assert.Equal("error", finding.GetProperty("severity").GetString());
            Assert.Contains("Coordinator checkout is missing required local runtime file", finding.GetProperty("message").GetString());
            Assert.False(File.Exists(Path.Combine(worktree, ".codex", "client-tools.local.json")));
        }

        [Fact]
        public void EnsureDeliveryContextCreatesTicketScopedLockFromExplicitValues()
        {
            string root = CreateTempDirectory();
            string output = RunPowerShellScript(
                "-Mode",
                "EnsureDeliveryContext",
                "-Root",
                root,
                "-ValuesJson",
                JsonSerializer.Serialize(new
                {
                    ticketKey = "E2EPROJECT-2",
                    branch = "feat/e2eproject-2-add-a-crud-view-por-a-client",
                    openspecChange = "feat-e2eproject-2-add-a-crud-view-por-a-client",
                    prNumber = 11,
                }));
            string lockPath = Path.Combine(root, ".codex", "delivery-context.local.json");

            Assert.True(File.Exists(lockPath));
            using JsonDocument context = JsonDocument.Parse(File.ReadAllText(lockPath));
            Assert.Equal("E2EPROJECT-2", context.RootElement.GetProperty("ticketKey").GetString());
            Assert.Equal("feat/e2eproject-2-add-a-crud-view-por-a-client", context.RootElement.GetProperty("branch").GetString());
            Assert.Equal("feat-e2eproject-2-add-a-crud-view-por-a-client", context.RootElement.GetProperty("openspecChange").GetString());
            Assert.Equal(11, context.RootElement.GetProperty("prNumber").GetInt32());
            Assert.Contains("Create or update ticket context lock", output);
        }

        [Fact]
        public void EnsureDeliveryContextRefusesDifferentExistingTicketLockByDefault()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.WriteAllText(
                Path.Combine(root, ".codex", "delivery-context.local.json"),
                JsonSerializer.Serialize(new { ticketKey = "E2EPROJECT-1", branch = "feat/e2eproject-1" }));

            string output = RunPowerShellScriptExpectFailure(
                "-Mode",
                "EnsureDeliveryContext",
                "-Root",
                root,
                "-ValuesJson",
                JsonSerializer.Serialize(new { ticketKey = "E2EPROJECT-2", branch = "feat/e2eproject-2" }));

            Assert.Contains("Existing .codex/delivery-context.local.json points to 'E2EPROJECT-1'", output);
        }

        [Fact]
        public void EnsureDeliveryContextCanReplaceExistingTicketLockWhenExplicitlyAllowed()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            string lockPath = Path.Combine(root, ".codex", "delivery-context.local.json");
            File.WriteAllText(
                lockPath,
                JsonSerializer.Serialize(new
                {
                    ticketKey = "E2EPROJECT-1",
                    branch = "feat/e2eproject-1",
                    artifactCommitSha = "abc123",
                    sourceRcVersion = "v1.2.3-rc.1",
                }));

            string output = RunPowerShellScript(
                "-Mode",
                "EnsureDeliveryContext",
                "-Root",
                root,
                "-ValuesJson",
                JsonSerializer.Serialize(new
                {
                    ticketKey = "E2EPROJECT-2",
                    branch = "feat/e2eproject-2",
                    replaceExisting = true,
                }));

            using JsonDocument context = JsonDocument.Parse(File.ReadAllText(lockPath));
            Assert.Equal("E2EPROJECT-2", context.RootElement.GetProperty("ticketKey").GetString());
            Assert.Equal("feat/e2eproject-2", context.RootElement.GetProperty("branch").GetString());
            Assert.False(context.RootElement.TryGetProperty("artifactCommitSha", out _));
            Assert.False(context.RootElement.TryGetProperty("sourceRcVersion", out _));
            Assert.Contains("Create or update ticket context lock", output);
            Assert.Contains("E2EPROJECT-2", output);
        }

        [Fact]
        public void AuditReportsRecordedTicketWorktreesMissingLocalRuntimeConfig()
        {
            string root = CreateTempDirectory();
            string worktree = Path.Combine(root, "ticket-worktrees", "e2eproject-1");
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            _ = Directory.CreateDirectory(worktree);
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "client-tools.example.json"),
                Path.Combine(root, ".codex", "client-tools.local.json"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "client-tools.example.json"),
                Path.Combine(root, ".codex", "client-tools.example.json"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "quality.example.json"),
                Path.Combine(root, ".codex", "quality.example.json"));
            File.WriteAllText(
                Path.Combine(root, ".codex", "parallel-delivery.local.json"),
                JsonSerializer.Serialize(new
                {
                    tickets = new[]
                    {
                        new { ticketKey = "E2EPROJECT-1", branch = "feat/e2eproject-1", worktreePath = worktree },
                    },
                }));

            string output = RunPowerShellScript("-Mode", "Audit", "-Root", root);
            using JsonDocument result = JsonDocument.Parse(output);
            string[] messages = [.. result.RootElement.GetProperty("findings")
                .EnumerateArray()
                .Select(item => item.GetProperty("message").GetString() ?? string.Empty)];

            Assert.Contains(messages, message => message.Contains("Ticket worktree is missing required local runtime file '.codex/client-tools.local.json'", StringComparison.Ordinal));
            Assert.Contains(messages, message => message.Contains("Ticket worktree is missing required local runtime file '.codex/quality.local.json'", StringComparison.Ordinal));
        }

        [Fact]
        public void AuditReportsMissingGrafanaAzureMonitorValues()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "plane"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "gitea"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "monitoring", "grafana", "dashboards"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "dashboards"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "datasources"));

            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "client-tools.example.json"),
                Path.Combine(root, ".codex", "client-tools.local.json"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "client-tools.example.json"),
                Path.Combine(root, ".codex", "client-tools.example.json"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "quality.example.json"),
                Path.Combine(root, ".codex", "quality.example.json"));
            File.WriteAllText(Path.Combine(root, "infra", "plane", "variables.env"), string.Empty);
            File.WriteAllText(Path.Combine(root, "infra", "gitea", "runner.env"), "GITEA_RUNNER_REGISTRATION_TOKEN=replace-with-token");
            File.WriteAllText(Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "dashboards", "dashboards.yml"), "apiVersion: 1");
            File.WriteAllText(Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "datasources", "azure-monitor.yml"), "uid: azure-monitor");

            string output = RunPowerShellScript("-Mode", "Audit", "-Root", root);
            using JsonDocument result = JsonDocument.Parse(output);
            string[] keys = [.. result.RootElement.GetProperty("findings")
                .EnumerateArray()
                .Select(item => item.GetProperty("key").GetString() ?? string.Empty)];

            Assert.Contains("GRAFANA_AZURE_TENANT_ID", keys);
            Assert.Contains("GRAFANA_AZURE_CLIENT_ID", keys);
            Assert.Contains("GRAFANA_AZURE_CLIENT_SECRET", keys);
            Assert.Contains("GRAFANA_AZURE_DEV_LOG_ANALYTICS_WORKSPACE_ID", keys);
        }

        [Fact]
        public void AzureBicepProvisionsLogAnalyticsAndDiagnosticSettingsForLogs()
        {
            string bicep = File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, "infra", "azure", "main.bicep"));

            Assert.Contains("Microsoft.OperationalInsights/workspaces", bicep);
            Assert.Contains("logAnalyticsWorkspaceName", bicep);
            Assert.Contains("Microsoft.Insights/diagnosticSettings@2021-05-01-preview", bicep);
            Assert.Contains("AppServiceConsoleLogs", bicep);
            Assert.Contains("workspaceId: logAnalyticsWorkspace.id", bicep);
            Assert.Contains("logAnalyticsDestinationType: 'Dedicated'", bicep);
        }

        [Fact]
        public void InitQualityGateTemplatesWritesCurrentDeliveryPolicyShape()
        {
            string root = CreateTempDirectory();

            string output = RunPowerShellScript("-Mode", "InitQualityGateTemplates", "-Root", root);
            string policyPath = Path.Combine(root, ".codex", "delivery-policy.json");

            Assert.True(File.Exists(policyPath));
            Assert.Contains(".codex/delivery-policy.json", output);
            using JsonDocument policy = JsonDocument.Parse(File.ReadAllText(policyPath));
            JsonElement optimization = policy.RootElement.GetProperty("agentOptimization");
            Assert.Equal(20, optimization.GetProperty("maxAutonomousIterations").GetInt32());
            Assert.Equal(2, optimization.GetProperty("maxToolRetries").GetInt32());
            Assert.True(optimization.GetProperty("promptCache").GetProperty("trackCachedTokens").GetBoolean());
            Assert.Equal(".codex/agent-telemetry.local.jsonl", optimization.GetProperty("telemetry").GetProperty("localPath").GetString());
            Assert.Equal(".codex/agent-evals/results.local.json", optimization.GetProperty("workflowEvals").GetProperty("resultsPath").GetString());
        }

        [Fact]
        public void AuditQualityGatesReportsLegacyDeliveryPolicyMissingAgentOptimization()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.WriteAllText(
                Path.Combine(root, ".codex", "delivery-policy.json"),
                JsonSerializer.Serialize(new { ticketKeyPattern = "E2EPROJECT-[0-9]+" }));

            string output = RunPowerShellScript("-Mode", "AuditQualityGates", "-Root", root);
            using JsonDocument audit = JsonDocument.Parse(output);
            JsonElement finding = audit.RootElement.GetProperty("findings").EnumerateArray().Single(
                item => item.GetProperty("path").GetString() == ".codex/delivery-policy.json"
                    && item.GetProperty("key").GetString() == "agentOptimization");

            Assert.Equal("warning", finding.GetProperty("severity").GetString());
        }

        [Fact]
        public void AuditRecommendedToolsRespectsAcceptedAndDismissedDecisions()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "tool-recommendations.example.json"),
                Path.Combine(root, ".codex", "tool-recommendations.example.json"));
            File.WriteAllText(
                Path.Combine(root, ".codex", "client-tools.local.json"),
                JsonSerializer.Serialize(new
                {
                    recommendedTools = new
                    {
                        enabled = true,
                        mode = "guided-manual",
                        accepted = new[] { "browser-e2e-qa-plugin" },
                        dismissed = new[] { "playwright-frontend-testing-skill" },
                    },
                }));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "plane"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "gitea"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "nexus"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "azure"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "monitoring"));
            _ = Directory.CreateDirectory(Path.Combine(root, ".gitea", "workflows"));
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex", "skills", "test-e2e"));
            File.WriteAllText(Path.Combine(root, "Example.slnx"), "<Solution />");
            File.WriteAllText(Path.Combine(root, ".codex", "skills", "test-e2e", "SKILL.md"), "# Test E2E");
            _ = Directory.CreateDirectory(Path.Combine(root, "openspec"));

            string output = RunPowerShellScript("-Mode", "AuditRecommendedTools", "-Root", root);
            using JsonDocument recommendations = JsonDocument.Parse(output);
            JsonElement recommendation = recommendations.RootElement.GetProperty("recommendations").EnumerateArray().Single(
                item => item.GetProperty("id").GetString() == "browser-e2e-qa-plugin");

            Assert.True(recommendation.GetProperty("accepted").GetBoolean());
            Assert.DoesNotContain("\"id\": \"playwright-frontend-testing-skill\"", output);
        }

        [Fact]
        public void AuditRecommendedToolsDetectsExpandedStackAndReturnsOfficialMetadata()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "tool-recommendations.example.json"),
                Path.Combine(root, ".codex", "tool-recommendations.example.json"));
            WriteExpandedStackFixture(root, includeContext: true);

            string output = RunPowerShellScript("-Mode", "AuditRecommendedTools", "-Root", root);
            using JsonDocument audit = JsonDocument.Parse(output);
            string stackMessage = audit.RootElement.GetProperty("actions").EnumerateArray().Single(
                item => item.GetProperty("key").GetString() == "detectedStack").GetProperty("message").GetString() ?? string.Empty;

            foreach (string tag in new[]
            {
                "dotnet-10",
                "aspnet-core",
                "blazor",
                "xunit",
                "coverage",
                "gitea-actions-runner",
                "nexus-artifacts",
                "azure-app-service",
                "azure-monitor",
                "grafana",
                "browser-e2e",
                "playwright-guidance",
                "clean-code",
                "architecture-guidance",
                "web-ui",
                "rest-api",
                "security",
                "openspec"
            })
            {
                Assert.Contains(tag, stackMessage);
            }

            JsonElement dotnetGuidance = audit.RootElement.GetProperty("recommendations").EnumerateArray().Single(
                item => item.GetProperty("id").GetString() == "dotnet-10-platform-guidance");
            string[] requires = [.. dotnetGuidance.GetProperty("requires").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];
            string[] officialSources = [.. dotnetGuidance.GetProperty("officialSources").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];
            string[] searchQueries = [.. dotnetGuidance.GetProperty("searchQueries").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];

            Assert.Contains("dotnet-10", requires);
            Assert.Contains(officialSources, source => source.Contains("learn.microsoft.com", StringComparison.Ordinal));
            Assert.Contains(searchQueries, query => query.Contains("site:learn.microsoft.com", StringComparison.Ordinal));
            Assert.Equal("manual-reference", dotnetGuidance.GetProperty("installMethod").GetString());
            Assert.Equal("technology-owner", dotnetGuidance.GetProperty("sourceKind").GetString());
            Assert.Contains(audit.RootElement.GetProperty("recommendations").EnumerateArray(),
                item => item.GetProperty("id").GetString() == "nexus-artifact-api-guidance");

            JsonElement searchPlan = audit.RootElement.GetProperty("recommendations").EnumerateArray().Single(
                item => item.GetProperty("id").GetString() == "project-guidance-search-plan");
            Assert.Equal("guidance-search-plan", searchPlan.GetProperty("type").GetString());
            Assert.Equal("research-then-manual-copy", searchPlan.GetProperty("installMethod").GetString());
            Assert.Equal("official-first-internet-search", searchPlan.GetProperty("sourceDiscovery").GetString());
            string[] sourcePriority = [.. searchPlan.GetProperty("discoverySourcePriority").EnumerateArray()
                .Select(item => item.GetString() ?? string.Empty)];
            Assert.Contains("repo-local", sourcePriority);
            Assert.Contains("openai-official", sourcePriority);
            Assert.Contains("skills-cli", sourcePriority);
            Assert.Contains("marketplace", sourcePriority);
            string[] topicIds = [.. searchPlan.GetProperty("topics").EnumerateArray()
                .Select(item => item.GetProperty("id").GetString() ?? string.Empty)];
            Assert.Contains("dotnet-aspnet", topicIds);
            Assert.Contains("web-ui", topicIds);
            Assert.Contains("rest-api", topicIds);
            Assert.Contains("qa-testing", topicIds);
            Assert.Contains("security", topicIds);
            Assert.Contains("delivery-tools", topicIds);
            Assert.Contains("code-standards", topicIds);

            string[] recommendationIds = [.. audit.RootElement.GetProperty("recommendations").EnumerateArray()
                .Select(item => item.GetProperty("id").GetString() ?? string.Empty)];
            Assert.Contains("openai-aspnet-core-skill", recommendationIds);
            Assert.Contains("dotnet-blazor-plan-ui-change-skill", recommendationIds);
            Assert.Contains("dotnet-webapi-skill", recommendationIds);
            Assert.Contains("openai-security-best-practices-skill", recommendationIds);
            Assert.Contains("openai-playwright-skill", recommendationIds);
            Assert.Contains("dotnet-assertion-quality-skill", recommendationIds);

            JsonElement securitySkill = audit.RootElement.GetProperty("recommendations").EnumerateArray().Single(
                item => item.GetProperty("id").GetString() == "openai-security-best-practices-skill");
            Assert.True(securitySkill.GetProperty("detected").GetBoolean());
            Assert.False(securitySkill.GetProperty("targetExists").GetBoolean());
            Assert.True(securitySkill.GetProperty("requiresUserConfirmation").GetBoolean());
            Assert.Equal("proposed", securitySkill.GetProperty("installStatus").GetString());
            Assert.Equal("official-first-internet-search", securitySkill.GetProperty("sourceDiscovery").GetString());
            Assert.Equal("openai-official", securitySkill.GetProperty("sourceKind").GetString());
            Assert.Contains(securitySkill.GetProperty("officialSources").EnumerateArray(),
                source => (source.GetString() ?? string.Empty).Contains("owasp.org", StringComparison.Ordinal));
            Assert.Contains(securitySkill.GetProperty("officialSkillSources").EnumerateArray(),
                source => (source.GetString() ?? string.Empty).Contains("github.com/openai/skills", StringComparison.Ordinal));
            Assert.Contains(securitySkill.GetProperty("candidateSkillSources").EnumerateArray(),
                source => (source.GetString() ?? string.Empty).Contains("security-best-practices", StringComparison.Ordinal));

            string[] findingKeys = [.. audit.RootElement.GetProperty("findings").EnumerateArray()
                .Select(item => item.GetProperty("key").GetString() ?? string.Empty)];
            Assert.Contains("skill-gap.openai-aspnet-core-skill", findingKeys);
            Assert.Contains("skill-gap.dotnet-blazor-plan-ui-change-skill", findingKeys);
            Assert.Contains("skill-gap.dotnet-webapi-skill", findingKeys);
            Assert.Contains("skill-gap.openai-security-best-practices-skill", findingKeys);
        }

        [Fact]
        public void AuditRecommendedToolsReportsStackContextDrift()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "tool-recommendations.example.json"),
                Path.Combine(root, ".codex", "tool-recommendations.example.json"));
            WriteExpandedStackFixture(root, includeContext: false);

            string output = RunPowerShellScript("-Mode", "AuditRecommendedTools", "-Root", root);
            using JsonDocument audit = JsonDocument.Parse(output);
            string[] findingKeys = [.. audit.RootElement.GetProperty("findings").EnumerateArray()
                .Select(item => item.GetProperty("key").GetString() ?? string.Empty)];

            Assert.Contains("stack-context.dotnet-10", findingKeys);
            Assert.Contains("stack-context.azure-app-service", findingKeys);
        }

        [Fact]
        public void AuditRecommendedToolsBuildsSearchPlanForNonDotnetStacks()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "tool-recommendations.example.json"),
                Path.Combine(root, ".codex", "tool-recommendations.example.json"));

            File.WriteAllText(
                Path.Combine(root, "package.json"),
                JsonSerializer.Serialize(new
                {
                    scripts = new { test = "playwright test" },
                    dependencies = new { react = "19.0.0" },
                    devDependencies = new Dictionary<string, string>
                    {
                        ["@playwright/test"] = "1.56.0",
                        ["typescript"] = "5.9.0",
                    },
                }));
            File.WriteAllText(Path.Combine(root, "tsconfig.json"), "{}");
            _ = Directory.CreateDirectory(Path.Combine(root, "src"));
            File.WriteAllText(Path.Combine(root, "src", "App.tsx"), "export function App() { return <main>Hello</main>; }");
            File.WriteAllText(Path.Combine(root, "Dockerfile"), "FROM node:22-alpine\n");

            string output = RunPowerShellScript("-Mode", "AuditRecommendedTools", "-Root", root);
            using JsonDocument audit = JsonDocument.Parse(output);
            string stackMessage = audit.RootElement.GetProperty("actions").EnumerateArray().Single(
                item => item.GetProperty("key").GetString() == "detectedStack").GetProperty("message").GetString() ?? string.Empty;
            JsonElement searchPlan = audit.RootElement.GetProperty("recommendations").EnumerateArray().Single(
                item => item.GetProperty("id").GetString() == "project-guidance-search-plan");
            string[] topicIds = [.. searchPlan.GetProperty("topics").EnumerateArray()
                .Select(item => item.GetProperty("id").GetString() ?? string.Empty)];

            Assert.Contains("node", stackMessage);
            Assert.Contains("typescript", stackMessage);
            Assert.Contains("react", stackMessage);
            Assert.Contains("docker", stackMessage);
            Assert.Contains("web-ui", topicIds);
            Assert.Contains("containers-iac", topicIds);
        }

        [Fact]
        public void DiscoverProjectGuidanceShowsSuggestionsAndAsksForAdditionalDesiredGuidance()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "tool-recommendations.example.json"),
                Path.Combine(root, ".codex", "tool-recommendations.example.json"));
            WriteExpandedStackFixture(root, includeContext: true);

            string output = RunPowerShellScript("-Mode", "DiscoverProjectGuidance", "-Root", root);
            using JsonDocument report = JsonDocument.Parse(output);

            string[] detectedTags = [.. report.RootElement.GetProperty("detectedTags").EnumerateArray()
                .Select(item => item.GetString() ?? string.Empty)];
            string[] topicIds = [.. report.RootElement.GetProperty("researchTopics").EnumerateArray()
                .Select(item => item.GetProperty("id").GetString() ?? string.Empty)];
            string[] missingSkillIds = [.. report.RootElement.GetProperty("suggestedMissingSkills").EnumerateArray()
                .Select(item => item.GetProperty("id").GetString() ?? string.Empty)];
            string[] sourcePriority = [.. report.RootElement.GetProperty("discoverySourcePriority").EnumerateArray()
                .Select(item => item.GetString() ?? string.Empty)];

            Assert.Equal("DiscoverProjectGuidance", report.RootElement.GetProperty("mode").GetString());
            Assert.False(report.RootElement.GetProperty("writeEnabled").GetBoolean());
            Assert.Contains("dotnet-10", detectedTags);
            Assert.Contains("qa-testing", topicIds);
            Assert.Contains("repo-local", sourcePriority);
            Assert.Contains("skills-cli", sourcePriority);
            Assert.Contains("openai-aspnet-core-skill", missingSkillIds);
            Assert.Contains("openai-playwright-skill", missingSkillIds);
            Assert.Contains("additional desired skills or guidance", report.RootElement.GetProperty("nextUserQuestion").GetString() ?? string.Empty);
            Assert.Empty(report.RootElement.GetProperty("finalConfirmedSkills").EnumerateArray());
        }

        [Fact]
        public void DiscoverProjectGuidanceIncludesUserAddedGuidanceWhenConfirmed()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "tool-recommendations.example.json"),
                Path.Combine(root, ".codex", "tool-recommendations.example.json"));
            WriteExpandedStackFixture(root, includeContext: true);

            string valuesJson = JsonSerializer.Serialize(new
            {
                confirmed = true,
                additionalSkills = new object[]
                {
                    "accessibility-review",
                    new
                    {
                        name = "api-security-review",
                        source = "https://example.invalid/skills/api-security-review",
                        target = ".codex/skills/api-security-review/SKILL.md",
                    },
                },
            });

            string output = RunPowerShellScript("-Mode", "DiscoverProjectGuidance", "-Root", root, "-ValuesJson", valuesJson);
            using JsonDocument report = JsonDocument.Parse(output);

            string[] userAdded = [.. report.RootElement.GetProperty("userAddedRequestedGuidance").EnumerateArray()
                .Select(item => item.GetProperty("name").GetString() ?? string.Empty)];
            string[] finalGuidanceNamesOrIds = [.. report.RootElement.GetProperty("finalConfirmedGuidance").EnumerateArray()
                .Select(item =>
                    item.TryGetProperty("id", out JsonElement id)
                        ? id.GetString() ?? string.Empty
                        : item.GetProperty("name").GetString() ?? string.Empty)];

            Assert.Contains("accessibility-review", userAdded);
            Assert.Contains("api-security-review", userAdded);
            Assert.Contains("openai-aspnet-core-skill", finalGuidanceNamesOrIds);
            Assert.Contains("clean-code-practice-guidance", finalGuidanceNamesOrIds);
            Assert.Contains("accessibility-review", finalGuidanceNamesOrIds);
            Assert.Contains("api-security-review", finalGuidanceNamesOrIds);
        }

        [Fact]
        public void DiscoverProjectGuidancePersistsCatalogShapedLocalRecommendationsWhenRequested()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "tool-recommendations.example.json"),
                Path.Combine(root, ".codex", "tool-recommendations.example.json"));
            WriteExpandedStackFixture(root, includeContext: true);

            string valuesJson = JsonSerializer.Serialize(new
            {
                confirmed = true,
                persistLocal = true,
            });

            string output = RunPowerShellScript("-Mode", "DiscoverProjectGuidance", "-Root", root, "-ValuesJson", valuesJson);
            using JsonDocument report = JsonDocument.Parse(output);
            string localPath = Path.Combine(root, ".codex", "tool-recommendations.local.json");

            Assert.True(report.RootElement.GetProperty("writeEnabled").GetBoolean());
            Assert.True(File.Exists(localPath));
            Assert.Contains(report.RootElement.GetProperty("actions").EnumerateArray(),
                item => item.GetProperty("path").GetString() == ".codex/tool-recommendations.local.json");

            using JsonDocument local = JsonDocument.Parse(File.ReadAllText(localPath));
            JsonElement rootElement = local.RootElement;
            Assert.Equal(1, rootElement.GetProperty("schemaVersion").GetInt32());
            Assert.Equal("guided-manual", rootElement.GetProperty("mode").GetString());
            Assert.Equal(".codex/tool-recommendations.example.json", rootElement.GetProperty("sourceCatalog").GetString());

            string[] detectedTags = [.. rootElement.GetProperty("detectedTags").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];
            Assert.Contains("dotnet-10", detectedTags);
            Assert.Contains("aspnet-core", detectedTags);

            JsonElement aspNetSkill = rootElement.GetProperty("recommendations").EnumerateArray().Single(
                item => item.GetProperty("id").GetString() == "openai-aspnet-core-skill");
            Assert.Equal("https://github.com/openai/skills/tree/main/skills/.curated/aspnet-core", aspNetSkill.GetProperty("source").GetString());
            Assert.Equal(".codex/skills/aspnet-core/SKILL.md", aspNetSkill.GetProperty("target").GetString());
            Assert.Equal("manual-copy", aspNetSkill.GetProperty("installMethod").GetString());
            Assert.Equal("openai-official", aspNetSkill.GetProperty("sourceKind").GetString());

            Assert.Contains(rootElement.GetProperty("notRecommended").EnumerateArray(),
                item => item.GetProperty("id").GetString() == "plane-mcp-for-ticket-delivery");

            JsonElement cleanCode = rootElement.GetProperty("recommendations").EnumerateArray().Single(
                item => item.GetProperty("id").GetString() == "clean-code-practice-guidance");
            Assert.Equal("practice", cleanCode.GetProperty("type").GetString());
            Assert.Empty(cleanCode.GetProperty("usedInSteps").EnumerateArray());
            Assert.False(rootElement.TryGetProperty("workflowStepMappings", out _));
        }

        [Fact]
        public void MapProjectGuidanceStepPersistsRecommendationUsedInSteps()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "tool-recommendations.example.json"),
                Path.Combine(root, ".codex", "tool-recommendations.example.json"));
            WriteExpandedStackFixture(root, includeContext: true);

            string firstMapping = JsonSerializer.Serialize(new
            {
                workflowStep = "implementation",
                primarySkills = new[] { "implement-ticket" },
                supportingSkills = new[] { "aspnet-core", "assertion-quality" },
                recommendationIds = new[] { "openai-aspnet-core-skill", "dotnet-assertion-quality-skill" },
                why = "Ticket implementation touched ASP.NET Core code and xUnit tests.",
                nextAction = "Use this mapping for similar implementation work.",
            });

            _ = RunPowerShellScript("-Mode", "MapProjectGuidanceStep", "-Root", root, "-ValuesJson", firstMapping);

            string secondMapping = JsonSerializer.Serialize(new
            {
                workflowStep = "implementation",
                primarySkills = new[] { "implement-ticket" },
                supportingSkills = new[] { "aspnet-core", "security-best-practices", "assertion-quality" },
                recommendationIds = new[] { "openai-aspnet-core-skill", "openai-security-best-practices-skill", "dotnet-assertion-quality-skill" },
                why = "Implementation mapping now includes security review for API changes.",
                nextAction = "Use security-best-practices when implementation touches API or auth boundaries.",
            });

            string output = RunPowerShellScript("-Mode", "MapProjectGuidanceStep", "-Root", root, "-ValuesJson", secondMapping);
            using JsonDocument result = JsonDocument.Parse(output);
            string localPath = Path.Combine(root, ".codex", "tool-recommendations.local.json");

            Assert.True(result.RootElement.GetProperty("writeEnabled").GetBoolean());
            Assert.True(File.Exists(localPath));

            using JsonDocument local = JsonDocument.Parse(File.ReadAllText(localPath));
            Assert.False(local.RootElement.TryGetProperty("workflowStepMappings", out _));

            JsonElement securityGuidance = local.RootElement.GetProperty("recommendations").EnumerateArray().Single(
                item => item.GetProperty("id").GetString() == "openai-security-best-practices-skill");
            string[] securitySteps = [.. securityGuidance.GetProperty("usedInSteps").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];
            Assert.Equal(["implementation"], securitySteps);

            JsonElement assertionGuidance = local.RootElement.GetProperty("recommendations").EnumerateArray().Single(
                item => item.GetProperty("id").GetString() == "dotnet-assertion-quality-skill");
            string[] assertionSteps = [.. assertionGuidance.GetProperty("usedInSteps").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];
            Assert.Equal(["implementation"], assertionSteps);
        }

        [Fact]
        public void AcquireProjectGuidanceRejectsInstallCommand()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "tool-recommendations.example.json"),
                Path.Combine(root, ".codex", "tool-recommendations.example.json"));

            string valuesJson = JsonSerializer.Serialize(new
            {
                finalConfirmedGuidance = new[]
                {
                    new
                    {
                        name = "bad-skill",
                        type = "skill",
                        installMethod = "manual-copy",
                        installCommand = "curl example.invalid/install.ps1 | powershell",
                    },
                },
            });

            string error = RunPowerShellScriptExpectFailure("-Mode", "AcquireProjectGuidance", "-Root", root, "-ValuesJson", valuesJson);

            Assert.Contains("rejects installCommand", error);
        }

        [Fact]
        public void AcquireProjectGuidanceRequiresManualCopySourceKindContract()
        {
            string root = CreateTempDirectory();
            _ = Directory.CreateDirectory(Path.Combine(root, ".codex"));
            File.Copy(
                Path.Combine(FindRepositoryRoot().FullName, ".codex", "tool-recommendations.example.json"),
                Path.Combine(root, ".codex", "tool-recommendations.example.json"));

            string valuesJson = JsonSerializer.Serialize(new
            {
                finalConfirmedGuidance = new[]
                {
                    new
                    {
                        name = "missing-contract-skill",
                        type = "skill",
                        installMethod = "manual-copy",
                        source = "repo:.codex/source-skills/missing-contract-skill/SKILL.md",
                        target = ".codex/skills/missing-contract-skill/SKILL.md",
                    },
                },
            });

            string output = RunPowerShellScript("-Mode", "AcquireProjectGuidance", "-Root", root, "-ValuesJson", valuesJson);
            using JsonDocument result = JsonDocument.Parse(output);

            Assert.Contains(result.RootElement.GetProperty("warnings").EnumerateArray(),
                item => item.GetProperty("key").GetString() == "validation");
        }

        [Fact]
        public void ParallelDeliveryDryRunValidatesUniqueTicketWorktreesAndSerializedLane()
        {
            string root = CreateTempDirectory();
            using JsonDocument document = RunParallelDeliveryDryRun(root, new
            {
                enabled = true,
                maxActiveTickets = 2,
                deploymentLanePolicy = "serialized",
                deploymentLaneOwner = new { ticketKey = "E2EPROJECT-1", stage = "deploy-to-qa" },
                tickets = new[]
                {
                    new { ticketKey = "E2EPROJECT-1", branch = "codex/e2eproject-1-a", worktreePath = "../ticket-worktrees/e2eproject-1" },
                    new { ticketKey = "E2EPROJECT-2", branch = "codex/e2eproject-2-b", worktreePath = "../ticket-worktrees/e2eproject-2" },
                },
            });

            Assert.True(document.RootElement.GetProperty("valid").GetBoolean());
            Assert.Equal(2, document.RootElement.GetProperty("activeTicketCount").GetInt32());
            Assert.Equal("serialized", document.RootElement.GetProperty("deploymentLanePolicy").GetString());
        }

        [Fact]
        public void ParallelDeliveryDryRunReportsUnsafeTicketWorktreePlans()
        {
            string root = CreateTempDirectory();
            using JsonDocument document = RunParallelDeliveryDryRun(root, new
            {
                enabled = false,
                maxActiveTickets = 2,
                deploymentLanePolicy = "serialized",
                deploymentLaneOwner = new { ticketKey = "E2EPROJECT-999", stage = "deploy-to-qa" },
                tickets = new[]
                {
                    new { ticketKey = "E2EPROJECT-1", branch = "codex/e2eproject-1-a", worktreePath = "../ticket-worktrees/e2eproject-1" },
                    new { ticketKey = "E2EPROJECT-1", branch = "codex/e2eproject-1-a", worktreePath = "../ticket-worktrees/e2eproject-1" },
                    new { ticketKey = "E2EPROJECT-3", branch = "codex/e2eproject-3-c", worktreePath = "" },
                },
            });
            string[] errors = GetJsonErrors(document);

            Assert.False(document.RootElement.GetProperty("valid").GetBoolean());
            Assert.Contains(errors, error => error.Contains("parallelDelivery.enabled must be true", StringComparison.Ordinal));
            Assert.Contains(errors, error => error.Contains("Active ticket count '3' exceeds maxActiveTickets '2'", StringComparison.Ordinal));
            Assert.Contains(errors, error => error.Contains("Duplicate ticketKey 'E2EPROJECT-1'", StringComparison.Ordinal));
            Assert.Contains(errors, error => error.Contains("Duplicate branch 'codex/e2eproject-1-a'", StringComparison.Ordinal));
            Assert.Contains(errors, error => error.Contains("Duplicate worktreePath '../ticket-worktrees/e2eproject-1'", StringComparison.Ordinal));
            Assert.Contains(errors, error => error.Contains("Ticket 'E2EPROJECT-3' is missing worktreePath", StringComparison.Ordinal));
            Assert.Contains(errors, error => error.Contains("Serialized deployment lane owner 'E2EPROJECT-999' is not an active ticket", StringComparison.Ordinal));
        }

        [Fact]
        public void ParallelDeliveryDryRunReportsUnsupportedLanePolicyAndMissingRuntimeFiles()
        {
            string root = CreateTempDirectory();
            using JsonDocument document = RunParallelDeliveryDryRun(root, new
            {
                enabled = true,
                maxActiveTickets = 2,
                deploymentLanePolicy = "parallel",
                requiredLocalConfigFiles = new[]
                {
                    ".codex/client-tools.local.json",
                    ".codex/quality.local.json",
                },
                tickets = new[]
                {
                    new { ticketKey = "E2EPROJECT-1", branch = "codex/e2eproject-1-a", worktreePath = "../ticket-worktrees/e2eproject-1" },
                },
            });
            string[] errors = GetJsonErrors(document);

            Assert.False(document.RootElement.GetProperty("valid").GetBoolean());
            Assert.Contains(errors, error => error.Contains("Unsupported deploymentLanePolicy 'parallel'", StringComparison.Ordinal));
            Assert.Contains(errors, error => error.Contains("Required local runtime file '.codex/client-tools.local.json' is missing.", StringComparison.Ordinal));
            Assert.Contains(errors, error => error.Contains("Required local runtime file '.codex/quality.local.json' is missing.", StringComparison.Ordinal));
        }

        private static JsonDocument RunParallelDeliveryDryRun(string root, object state)
        {
            string script = Path.Combine(FindRepositoryRoot().FullName, ".codex", "skills", "_shared", "scripts", "delivery_tools.ps1");
            string output = RunPowerShell(
                script,
                "-Mode",
                "ValidateParallelDeliveryDryRun",
                "-RepoRoot",
                root,
                "-InputJson",
                JsonSerializer.Serialize(state));

            return JsonDocument.Parse(output);
        }

        [Fact]
        public void RenderPlaneCommentRendersWorkflowTimingTable()
        {
            string script = Path.Combine(FindRepositoryRoot().FullName, ".codex", "skills", "_shared", "scripts", "delivery_tools.ps1");
            string inputJson = JsonSerializer.Serialize(new
            {
                ticketKey = "E2EPROJECT-123",
                status = "PASS - automatic route completed.",
                currentRoute = "implement-ticket",
                stages = new[]
                {
                    new
                    {
                        stage = "plane-start-ticket",
                        outcome = "PASS",
                        elapsedMilliseconds = 134000,
                        startedUtc = "2026-06-03T10:00:00Z",
                        finishedUtc = "2026-06-03T10:02:14Z",
                    },
                    new
                    {
                        stage = "implement-ticket",
                        outcome = "BLOCKED",
                        elapsedMilliseconds = 3605000,
                        startedUtc = "2026-06-03T10:02:14Z",
                        finishedUtc = "2026-06-03T11:02:19Z",
                    },
                },
            });

            string output = RunPowerShell(
                script,
                "-Mode",
                "RenderPlaneComment",
                "-Type",
                "WorkflowTiming",
                "-InputJson",
                inputJson);

            Assert.Contains("IA generated workflow timing: E2EPROJECT-123", output);
            Assert.Contains("**Status:** PASS - automatic route completed.", output);
            Assert.Contains("- Current route: `implement-ticket`", output);
            Assert.Contains("- Total elapsed: 1h 02m 19s", output);
            Assert.Contains("| Stage | Outcome | Duration | Started UTC | Finished UTC |", output);
            Assert.Contains("| `plane-start-ticket` | PASS | 2m 14s | 2026-06-03T10:00:00Z | 2026-06-03T10:02:14Z |", output);
            Assert.Contains("| `implement-ticket` | BLOCKED | 1h 00m 05s | 2026-06-03T10:02:14Z | 2026-06-03T11:02:19Z |", output);
            Assert.DoesNotContain("token", output, StringComparison.OrdinalIgnoreCase);
        }

        [Fact]
        public void WorkflowTelemetryInitializeCreatesAndClearsJsonlFile()
        {
            string root = CreateTempDirectory();
            string script = Path.Combine(FindRepositoryRoot().FullName, ".codex", "skills", "_shared", "scripts", "delivery_tools.ps1");
            string telemetryPath = Path.Combine(root, ".codex", "agent-telemetry.local.jsonl");
            _ = Directory.CreateDirectory(Path.GetDirectoryName(telemetryPath)!);
            File.WriteAllText(telemetryPath, JsonSerializer.Serialize(new { ticketKey = "OLD" }));

            string output = RunPowerShell(
                script,
                "-Mode",
                "InitializeWorkflowTelemetry",
                "-RepoRoot",
                root,
                "-TicketKey",
                "E2EPROJECT-123");

            using JsonDocument document = JsonDocument.Parse(output);
            Assert.True(document.RootElement.GetProperty("exists").GetBoolean());
            Assert.True(document.RootElement.GetProperty("cleared").GetBoolean());
            Assert.Equal("E2EPROJECT-123", document.RootElement.GetProperty("ticketKey").GetString());
            Assert.True(File.Exists(telemetryPath));
            Assert.Equal(string.Empty, File.ReadAllText(telemetryPath));
        }

        [Fact]
        public void WorkflowTelemetryAppendWritesValidJsonlWithRequiredFields()
        {
            string root = CreateTempDirectory();
            string script = Path.Combine(FindRepositoryRoot().FullName, ".codex", "skills", "_shared", "scripts", "delivery_tools.ps1");
            _ = RunPowerShell(script, "-Mode", "InitializeWorkflowTelemetry", "-RepoRoot", root, "-TicketKey", "E2EPROJECT-123");
            string inputJson = JsonSerializer.Serialize(new
            {
                workflowStage = "implement-ticket",
                agentRole = "implementation",
                startedUtc = "2026-06-09T10:00:00Z",
                finishedUtc = "2026-06-09T10:03:05Z",
                retryCount = 1,
                outcome = "PASS",
            });

            string output = RunPowerShell(
                script,
                "-Mode",
                "AppendWorkflowTelemetry",
                "-RepoRoot",
                root,
                "-TicketKey",
                "E2EPROJECT-123",
                "-InputJson",
                inputJson);

            using JsonDocument result = JsonDocument.Parse(output);
            Assert.True(result.RootElement.GetProperty("appended").GetBoolean());
            string telemetryPath = Path.Combine(root, ".codex", "agent-telemetry.local.jsonl");
            string line = Assert.Single(File.ReadAllLines(telemetryPath), static value => !string.IsNullOrWhiteSpace(value));
            using JsonDocument row = JsonDocument.Parse(line);
            Assert.Equal("E2EPROJECT-123", row.RootElement.GetProperty("ticketKey").GetString());
            Assert.Equal("implement-ticket", row.RootElement.GetProperty("workflowStage").GetString());
            Assert.Equal("implementation", row.RootElement.GetProperty("agentRole").GetString());
            Assert.Equal("2026-06-09T10:00:00Z", row.RootElement.GetProperty("startedUtc").GetString());
            Assert.Equal("2026-06-09T10:03:05Z", row.RootElement.GetProperty("finishedUtc").GetString());
            Assert.Equal(185000, row.RootElement.GetProperty("elapsedMilliseconds").GetInt64());
            Assert.Equal(1, row.RootElement.GetProperty("retryCount").GetInt64());
            Assert.Equal("PASS", row.RootElement.GetProperty("outcome").GetString());
        }

        [Fact]
        public void WorkflowTelemetryReadFiltersByTicketAndReturnsRenderableStages()
        {
            string root = CreateTempDirectory();
            string script = Path.Combine(FindRepositoryRoot().FullName, ".codex", "skills", "_shared", "scripts", "delivery_tools.ps1");
            _ = RunPowerShell(script, "-Mode", "InitializeWorkflowTelemetry", "-RepoRoot", root, "-TicketKey", "E2EPROJECT-123");
            foreach (var row in new[]
            {
                new { ticket = "E2EPROJECT-123", stage = "plane-start-ticket", agent = "ticketStarter", start = "2026-06-09T10:00:00Z", finish = "2026-06-09T10:01:00Z" },
                new { ticket = "E2EPROJECT-999", stage = "ignored-ticket", agent = "implementation", start = "2026-06-09T10:01:00Z", finish = "2026-06-09T10:02:00Z" },
                new { ticket = "E2EPROJECT-123", stage = "implement-ticket", agent = "implementation", start = "2026-06-09T10:01:00Z", finish = "2026-06-09T10:04:30Z" },
            })
            {
                string appendJson = JsonSerializer.Serialize(new
                {
                    workflowStage = row.stage,
                    agentRole = row.agent,
                    startedUtc = row.start,
                    finishedUtc = row.finish,
                    outcome = "PASS",
                });
                _ = RunPowerShell(script, "-Mode", "AppendWorkflowTelemetry", "-RepoRoot", root, "-TicketKey", row.ticket, "-InputJson", appendJson);
            }

            string readJson = RunPowerShell(
                script,
                "-Mode",
                "ReadWorkflowTelemetry",
                "-RepoRoot",
                root,
                "-TicketKey",
                "E2EPROJECT-123",
                "-InputJson",
                JsonSerializer.Serialize(new { status = "PASS - telemetry.", currentRoute = "implement-ticket" }));

            using JsonDocument document = JsonDocument.Parse(readJson);
            Assert.Equal("E2EPROJECT-123", document.RootElement.GetProperty("ticketKey").GetString());
            Assert.Equal(270000, document.RootElement.GetProperty("totalElapsedMilliseconds").GetInt64());
            JsonElement stages = document.RootElement.GetProperty("stages");
            Assert.Equal(2, stages.GetArrayLength());
            Assert.Equal("plane-start-ticket", stages[0].GetProperty("stage").GetString());
            Assert.Equal("implement-ticket", stages[1].GetProperty("stage").GetString());

            string comment = RunPowerShell(
                script,
                "-Mode",
                "RenderPlaneComment",
                "-Type",
                "WorkflowTiming",
                "-InputJson",
                readJson);
            Assert.Contains("IA generated workflow timing: E2EPROJECT-123", comment);
            Assert.Contains("- Total elapsed: 4m 30s", comment);
            Assert.Contains("| `implement-ticket` | PASS | 3m 30s | 2026-06-09T10:01:00Z | 2026-06-09T10:04:30Z |", comment);
        }

        private static string[] GetJsonErrors(JsonDocument document)
        {
            return [.. document.RootElement.GetProperty("errors").EnumerateArray().Select(error => error.GetString() ?? string.Empty)];
        }

        private static string RunPowerShellScript(params string[] args)
        {
            string script = Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                "configure-dev-environment",
                "scripts",
                "configure_infra_tools.ps1");

            return RunPowerShell(script, args);
        }

        private static string RunPowerShellScriptExpectFailure(params string[] args)
        {
            string script = Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                "configure-dev-environment",
                "scripts",
                "configure_infra_tools.ps1");

            ProcessStartInfo startInfo = new()
            {
                FileName = GetPowerShellFileName(),
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            startInfo.ArgumentList.Add("-NoProfile");
            startInfo.ArgumentList.Add("-File");
            startInfo.ArgumentList.Add(script);
            foreach (string arg in args)
            {
                startInfo.ArgumentList.Add(arg);
            }

            using Process process = Process.Start(startInfo) ?? throw new InvalidOperationException("Could not start PowerShell.");
            string stdout = process.StandardOutput.ReadToEnd();
            string stderr = process.StandardError.ReadToEnd();
            process.WaitForExit();

            Assert.NotEqual(0, process.ExitCode);
            return stdout + stderr;
        }

        private static string RunPowerShell(string script, params string[] args)
        {
            ProcessStartInfo startInfo = new()
            {
                FileName = GetPowerShellFileName(),
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            startInfo.ArgumentList.Add("-NoProfile");
            startInfo.ArgumentList.Add("-File");
            startInfo.ArgumentList.Add(script);
            foreach (string arg in args)
            {
                startInfo.ArgumentList.Add(arg);
            }

            using Process process = Process.Start(startInfo) ?? throw new InvalidOperationException("Could not start PowerShell.");
            string stdout = process.StandardOutput.ReadToEnd();
            string stderr = process.StandardError.ReadToEnd();
            process.WaitForExit();

            Assert.True(process.ExitCode == 0, stderr);
            return stdout;
        }

        private static string GetPowerShellFileName()
        {
            return RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "powershell" : "pwsh";
        }

        private static string CreateTempDirectory()
        {
            string path = Path.Combine(Path.GetTempPath(), "sdd-template-tests", Guid.NewGuid().ToString("N"));
            _ = Directory.CreateDirectory(path);
            return path;
        }

        private static void WriteExpandedStackFixture(string root, bool includeContext)
        {
            File.WriteAllText(
                Path.Combine(root, "global.json"),
                JsonSerializer.Serialize(new { sdk = new { version = "10.0.100", rollForward = "latestFeature" } }));

            string sourceDirectory = Path.Combine(root, "src", "Example.Site");
            string testDirectory = Path.Combine(root, "tests", "Example.Site.Tests");
            _ = Directory.CreateDirectory(sourceDirectory);
            _ = Directory.CreateDirectory(testDirectory);
            File.WriteAllText(
                Path.Combine(sourceDirectory, "Example.Site.csproj"),
                """
                <Project Sdk="Microsoft.NET.Sdk.Web">
                  <PropertyGroup>
                    <TargetFramework>net10.0</TargetFramework>
                    <BlazorDisableThrowNavigationException>true</BlazorDisableThrowNavigationException>
                  </PropertyGroup>
                </Project>
                """);
            File.WriteAllText(Path.Combine(sourceDirectory, "App.razor"), """<Router AppAssembly="@typeof(Program).Assembly" />""");
            File.WriteAllText(
                Path.Combine(sourceDirectory, "Program.cs"),
                """
                var builder = WebApplication.CreateBuilder(args);
                var app = builder.Build();
                app.MapGet("/health", () => Results.Ok(new { status = "ok" }));
                app.Run();
                """);
            File.WriteAllText(
                Path.Combine(testDirectory, "Example.Site.Tests.csproj"),
                """
                <Project Sdk="Microsoft.NET.Sdk">
                  <PropertyGroup>
                    <TargetFramework>net10.0</TargetFramework>
                  </PropertyGroup>
                  <ItemGroup>
                    <PackageReference Include="coverlet.collector" Version="6.0.4" />
                    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="10.0.8" />
                    <PackageReference Include="xunit" Version="2.9.3" />
                  </ItemGroup>
                </Project>
                """);

            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "plane"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "gitea"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "nexus"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "azure"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "monitoring", "grafana"));
            _ = Directory.CreateDirectory(Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "datasources"));
            File.WriteAllText(Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "datasources", "azure-monitor.yml"), "type: grafana-azure-monitor-datasource\n");

            string workflowDirectory = Path.Combine(root, ".gitea", "workflows");
            _ = Directory.CreateDirectory(workflowDirectory);
            File.WriteAllText(
                Path.Combine(workflowDirectory, "package-deploy.yml"),
                "steps:\n  - run: echo $NEXUS_URL && az webapp deploy\n");

            string e2eSkillDirectory = Path.Combine(root, ".codex", "skills", "test-e2e");
            string frontendSkillDirectory = Path.Combine(root, ".codex", "skills", "frontend-testing-debugging");
            _ = Directory.CreateDirectory(e2eSkillDirectory);
            _ = Directory.CreateDirectory(frontendSkillDirectory);
            File.WriteAllText(Path.Combine(e2eSkillDirectory, "SKILL.md"), "Use Playwright for rendered browser QA.");
            File.WriteAllText(Path.Combine(frontendSkillDirectory, "SKILL.md"), "# Frontend Testing Debugging");

            _ = Directory.CreateDirectory(Path.Combine(root, "openspec"));

            if (!includeContext) { return; }

            string context = ".NET 10 ASP.NET Core Blazor xUnit coverage Plane Gitea Gitea Actions Nexus Azure App Service Azure Monitor Log Analytics Grafana Browser Playwright OpenSpec clean code architecture web UI REST API security OWASP";
            _ = Directory.CreateDirectory(Path.Combine(root, "docs"));
            File.WriteAllText(Path.Combine(root, "docs", "architecture.md"), context);
            File.WriteAllText(Path.Combine(root, "docs", "development.md"), context);
            File.WriteAllText(Path.Combine(root, "docs", "deployment.md"), context);
            File.WriteAllText(Path.Combine(root, "openspec", "config.yaml"), $"schema: spec-driven\ncontext: |\n  {context}\n");
        }

        private static DirectoryInfo FindRepositoryRoot()
        {
            DirectoryInfo? current = new(AppContext.BaseDirectory);

            while (current is not null && !File.Exists(Path.Combine(current.FullName, "SDDTemplate.slnx")))
            {
                current = current.Parent;
            }

            return current ?? throw new DirectoryNotFoundException("Could not locate repository root.");
        }
    }
}
