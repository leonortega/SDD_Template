using System.Diagnostics;
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
                "http://nexus/repository/raw-hosted/app/abcdef1/app.zip",
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
                "prometheus",
                "grafana",
                "browser-e2e",
                "playwright-guidance",
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
            Assert.Contains(audit.RootElement.GetProperty("recommendations").EnumerateArray(),
                item => item.GetProperty("id").GetString() == "nexus-artifact-api-guidance");
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

        private static string RunPowerShell(string script, params string[] args)
        {
            ProcessStartInfo startInfo = new()
            {
                FileName = "powershell",
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
            File.WriteAllText(Path.Combine(root, "infra", "monitoring", "prometheus.yml"), "prometheus:\nglobal:\n  scrape_interval: 15s\n");

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

            string context = ".NET 10 ASP.NET Core Blazor xUnit coverage Plane Gitea Gitea Actions Nexus Azure App Service Prometheus Grafana Browser Playwright OpenSpec";
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
