using System.Text.Json;
using SDDTemplate.DeliveryTools;

namespace SDDTemplate.Site.Tests
{
    public sealed class RancherLocalLabTests
    {
        [Fact]
        public void ProjectProfileSelectsRancherDesktopAsDeploymentProvider()
        {
            string root = FindRepositoryRoot();
            using JsonDocument profile = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, ".codex", "project-profile.json")));

            JsonElement deployment = profile.RootElement
                .GetProperty("providers")
                .GetProperty("deployment");
            string adapter = profile.RootElement
                .GetProperty("adapters")
                .GetProperty("deployment")
                .GetString()!;

            Assert.Equal("rancher-desktop", deployment.GetProperty("id").GetString());
            Assert.Equal(".codex/providers/deploy.rancher-desktop.md", deployment.GetProperty("adapter").GetString());
            Assert.Equal(".codex/providers/deploy.rancher-desktop.md", adapter);
            Assert.True(File.Exists(Path.Combine(root, ".codex", "providers", "deploy.rancher-desktop.md")));
        }

        [Fact]
        public void AppDockerfilesPublishReleaseBuildsOnHttpPort8080()
        {
            string root = FindRepositoryRoot();
            string site = File.ReadAllText(Path.Combine(root, "src", "SDDTemplate.Site", "Dockerfile"));
            string api = File.ReadAllText(Path.Combine(root, "src", "SDDTemplate.Api", "Dockerfile"));

            foreach (string dockerfile in new[] { site, api })
            {
                Assert.Contains("mcr.microsoft.com/dotnet/sdk:10.0.300", dockerfile);
                Assert.Contains("mcr.microsoft.com/dotnet/aspnet:10.0.9", dockerfile);
                Assert.Contains("dotnet publish", dockerfile);
                Assert.Contains("ASPNETCORE_URLS=http://+:8080", dockerfile);
                Assert.Contains("EXPOSE 8080", dockerfile);
            }
        }

        [Fact]
        public void RancherWorkflowBuildsImagesAndPromotesDigestPinnedMetadata()
        {
            string root = FindRepositoryRoot();
            string workflow = File.ReadAllText(Path.Combine(root, ".gitea", "workflows", "rancher-local-deploy.yml"));
            string script = File.ReadAllText(Path.Combine(root, "infra", "rancher", "deploy-local-lab.sh"));

            Assert.Contains("NEXUS_DOCKER_REGISTRY", workflow);
            Assert.Contains("docker build -f src/SDDTemplate.Site/Dockerfile", workflow);
            Assert.Contains("docker build -f src/SDDTemplate.Api/Dockerfile", workflow);
            Assert.Contains("container-images.json", workflow);
            Assert.Contains("capture-observability.sh", workflow);
            Assert.Contains("monitoring-summary.json", workflow);
            Assert.Contains("qa-observability.json", workflow);
            Assert.Contains("deploymentProvider = \"rancher-desktop\"", workflow);
            Assert.Contains("kubectl config current-context | grep -qx \"rancher-desktop\"", workflow);
            Assert.Contains("qa-local/**", workflow);
            Assert.Contains("source_rc_version", workflow);
            Assert.Contains("release_version", workflow);
            Assert.Contains("app/rc/${SOURCE_RC_VERSION}/artifact-pointer.json", workflow);
            Assert.Contains("qa/${E2E_PLANE_TICKET_KEY}/${run_id}/qa-evidence.zip", workflow);
            Assert.Contains("monitoring-summary-prod.json", workflow);

            Assert.Contains("sdd-dev", workflow);
            Assert.Contains("sdd-qa", workflow);
            Assert.Contains("sdd-prod", workflow);
            Assert.Contains("@sha256:", script);
            Assert.Contains("imagePullSecrets:", script);
            Assert.Contains("readinessProbe:", script);
            Assert.Contains("PersistentVolumeClaim", script);
            Assert.Contains("sddtemplate.dev/commit-sha", script);
            Assert.Contains("SDDTEMPLATE_IMAGE_DIGEST", script);
        }

        [Fact]
        public void SharedArtifactPathsDefaultToSelectedRancherProviderMetadata()
        {
            string root = FindRepositoryRoot();
            string script = Path.Combine(root, ".codex", "skills", "_shared", "scripts", "delivery_tools.ps1");

            string defaultJson = RunPowerShell(root, $"-NoProfile -ExecutionPolicy Bypass -File \"{script}\" -Mode ArtifactPaths -CommitSha abc123");
            string azureJson = RunPowerShell(root, $"-NoProfile -ExecutionPolicy Bypass -File \"{script}\" -Mode ArtifactPaths -CommitSha abc123 -DeploymentProvider azure-appservice");

            using JsonDocument defaultPaths = JsonDocument.Parse(defaultJson);
            using JsonDocument azure = JsonDocument.Parse(azureJson);

            Assert.Equal("rancher-desktop", defaultPaths.RootElement.GetProperty("deploymentProvider").GetString());
            Assert.Equal("app/abc123/container-images.json", defaultPaths.RootElement.GetProperty("containerImages").GetString());
            Assert.Equal("app/abc123/monitoring-summary-{environment}.json", defaultPaths.RootElement.GetProperty("monitoringSummaryPattern").GetString());
            Assert.Equal("app/abc123/qa-observability.json", defaultPaths.RootElement.GetProperty("qaObservability").GetString());

            Assert.Equal("azure-appservice", azure.RootElement.GetProperty("deploymentProvider").GetString());
            Assert.Equal("app/abc123/deployable-apps.json", azure.RootElement.GetProperty("topology").GetString());
            Assert.False(azure.RootElement.TryGetProperty("containerImages", out _));
        }

        [Fact]
        public void RancherObservabilityCapturesSanitizedLogsAndSeqEvidence()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, "infra", "rancher", "capture-observability.sh"));
            string workflow = File.ReadAllText(Path.Combine(root, ".gitea", "workflows", "rancher-local-deploy.yml"));

            Assert.Contains("/ingest/clef", script);
            Assert.Contains("application/vnd.serilog.clef", script);
            Assert.Contains("sanitize_logs", script);
            Assert.Contains("monitoring-summary.json", script);
            Assert.Contains("seqRecentLogStatus", script);
            Assert.Contains("CommitSha", script);
            Assert.Contains("ImageDigest", script);

            Assert.Contains("app/${GITHUB_SHA}/monitoring-summary.json", workflow);
            Assert.Contains("app/${GITHUB_SHA}/qa-observability.json", workflow);
            Assert.Contains("qa-observability.json", workflow);
        }

        [Fact]
        public void PrometheusTargetsIncludeRancherDesktopHealthChecks()
        {
            string root = FindRepositoryRoot();
            string targets = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "prometheus", "targets.local.yml"));
            string prometheus = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "prometheus", "prometheus.yml"));

            Assert.Contains("http://site.dev.sdd.localhost/health", targets);
            Assert.Contains("http://api.dev.sdd.localhost/health", targets);
            Assert.Contains("http://site.qa.sdd.localhost/health", targets);
            Assert.Contains("http://api.qa.sdd.localhost/health", targets);
            Assert.Contains("http://site.prod.sdd.localhost/health", targets);
            Assert.Contains("http://api.prod.sdd.localhost/health", targets);
            Assert.Contains("provider: rancher-desktop", targets);
            Assert.DoesNotContain("azurewebsites.net", targets);
            Assert.DoesNotContain("provider: azure-appservice", targets);
            Assert.Contains("target_label: provider", prometheus);
        }

        [Fact]
        public void ConfigureInfraAuditsSelectedRancherLocalLabSurfaces()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "scripts", "configure_infra_tools.ps1"));
            string configureSkill = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "SKILL.md"));

            Assert.Contains("function Add-RancherLocalLabAuditFindings", script);
            Assert.Contains("Add-RancherLocalLabAuditFindings $result", script);
            Assert.Contains("\"docker\", \"kubectl\"", script);
            Assert.Contains(".codex/providers/deploy.rancher-desktop.md", script);
            Assert.Contains(".gitea/workflows/rancher-local-deploy.yml", script);
            Assert.Contains("infra/rancher/deploy-local-lab.sh", script);
            Assert.Contains("infra/rancher/capture-observability.sh", script);
            Assert.Contains("src/SDDTemplate.Site/Dockerfile", script);
            Assert.Contains("src/SDDTemplate.Api/Dockerfile", script);
            Assert.Contains("NEXUS_DOCKER_REGISTRY", script);
            Assert.Contains("RANCHER_KUBECONFIG_B64", script);
            Assert.Contains("SEQ_URL=http://localhost:5341", script);
            Assert.Contains("PROMETHEUS_URL=http://localhost:9091", script);
            Assert.Contains("RANCHER_OBSERVABILITY_ENABLED=true", script);
            Assert.Contains("target_label:\\s*provider", script);
            Assert.Contains("Rancher Desktop local lab", configureSkill);
            Assert.Contains("providers.deployment", script);
            Assert.Contains("Azure Event Hub collector checks skipped", script);
            Assert.Contains("if ($azureDeploymentSelected)", script);
        }

        [Fact]
        public void NexusComposeExposesDockerRegistryConnectorPort()
        {
            string root = FindRepositoryRoot();
            string compose = File.ReadAllText(Path.Combine(root, "infra", "nexus", "compose.yml"));

            Assert.Contains("\"8088:8081\"", compose);
            Assert.Contains("\"5001:5001\"", compose);
        }

        [Fact]
        public void ReleaseManifestValidationAcceptsDigestPinnedContainerImages()
        {
            string path = Path.Combine(Path.GetTempPath(), $"{Guid.NewGuid():N}.release.json");
            string digest = $"sha256:{new string('a', 64)}";
            File.WriteAllText(path, $$"""
            {
              "schemaVersion": 1,
              "commitSha": "abcdef1234567890",
              "checksum": "{{digest}}",
              "artifactUrl": "localhost:5001/sddtemplate/site@{{digest}}",
              "planeTicketKey": "E2EPROJECT-1",
              "versionStatus": "local container candidate",
              "deploymentProvider": "rancher-desktop",
              "containerImages": [
                {
                  "appId": "site",
                  "image": "localhost:5001/sddtemplate/site",
                  "tag": "abcdef1234567890",
                  "digest": "{{digest}}",
                  "reference": "localhost:5001/sddtemplate/site@{{digest}}"
                }
              ]
            }
            """);

            try
            {
                ReleaseManifestValidation result = DeliveryWorkflowHelpers.ValidateReleaseManifest(path);

                Assert.True(result.Valid, string.Join(Environment.NewLine, result.Errors));
            }
            finally
            {
                File.Delete(path);
            }
        }

        [Fact]
        public void ReleaseManifestValidationRejectsMutableContainerImageReferences()
        {
            string path = Path.Combine(Path.GetTempPath(), $"{Guid.NewGuid():N}.release.json");
            string digest = $"sha256:{new string('a', 64)}";
            File.WriteAllText(path, $$"""
            {
              "schemaVersion": 1,
              "commitSha": "abcdef1234567890",
              "checksum": "{{digest}}",
              "artifactUrl": "localhost:5001/sddtemplate/site:abcdef1234567890",
              "planeTicketKey": "E2EPROJECT-1",
              "versionStatus": "local container candidate",
              "containerImages": [
                {
                  "appId": "site",
                  "image": "localhost:5001/sddtemplate/site",
                  "tag": "abcdef1234567890",
                  "digest": "{{digest}}",
                  "reference": "localhost:5001/sddtemplate/site:abcdef1234567890"
                }
              ]
            }
            """);

            try
            {
                ReleaseManifestValidation result = DeliveryWorkflowHelpers.ValidateReleaseManifest(path);

                Assert.False(result.Valid);
                Assert.Contains(result.Errors, error => error.Contains("reference must be pinned", StringComparison.Ordinal));
            }
            finally
            {
                File.Delete(path);
            }
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

        private static string RunPowerShell(string workingDirectory, string arguments)
        {
            using System.Diagnostics.Process process = new()
            {
                StartInfo = new System.Diagnostics.ProcessStartInfo
                {
                    FileName = "powershell",
                    Arguments = arguments,
                    WorkingDirectory = workingDirectory,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false
                }
            };

            Assert.True(process.Start(), "PowerShell process did not start.");
            string output = process.StandardOutput.ReadToEnd();
            string error = process.StandardError.ReadToEnd();
            process.WaitForExit();

            Assert.True(process.ExitCode == 0, error);
            return output;
        }
    }
}
