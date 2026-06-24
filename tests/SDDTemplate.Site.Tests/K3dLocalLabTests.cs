using System.Text.Json;
using SDDTemplate.DeliveryTools;

namespace SDDTemplate.Site.Tests
{
    public sealed class K3dLocalLabTests
    {
        [Fact]
        public void ProjectProfileSelectsK3dAsDeploymentProvider()
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

            Assert.Equal("k3d", deployment.GetProperty("id").GetString());
            Assert.Equal(".codex/providers/deploy.k3d.md", deployment.GetProperty("adapter").GetString());
            Assert.Equal(".codex/providers/deploy.k3d.md", adapter);
            Assert.True(File.Exists(Path.Combine(root, ".codex", "providers", "deploy.k3d.md")));
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
        public void K3dWorkflowBuildsImagesAndPromotesDigestPinnedMetadata()
        {
            string root = FindRepositoryRoot();
            string workflow = File.ReadAllText(Path.Combine(root, ".gitea", "workflows", "k3d-local-deploy.yml"));
            string script = File.ReadAllText(Path.Combine(root, "infra", "k3d", "deploy-local-lab.sh"));

            Assert.Contains("NEXUS_DOCKER_REGISTRY", workflow);
            Assert.Contains("docker build -f src/SDDTemplate.Site/Dockerfile", workflow);
            Assert.Contains("docker build -f src/SDDTemplate.Api/Dockerfile", workflow);
            Assert.Contains("container-images.json", workflow);
            Assert.DoesNotContain("capture-observability.sh", workflow);
            Assert.Contains("wait_for_direct_health", workflow);
            Assert.Contains("healthCheckMode: \"direct-http\"", workflow);
            Assert.Contains("monitoring-summary.json", workflow);
            Assert.Contains("qa-observability.json", workflow);
            Assert.Contains("deploymentProvider = \"k3d\"", workflow);
            Assert.Contains("kubectl config current-context | grep -qx \"k3d-sdd-template\"", workflow);
            Assert.Contains("qa-local/**", workflow);
            Assert.Contains("source_rc_version", workflow);
            Assert.Contains("release_version", workflow);
            Assert.Contains("app/rc/${SOURCE_RC_VERSION}/artifact-pointer.json", workflow);
            Assert.Contains("qa/${E2E_TICKET_KEY}/${run_id}/qa-evidence.zip", workflow);
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
        public void SharedArtifactPathsDefaultToSelectedK3dProviderMetadata()
        {
            string root = FindRepositoryRoot();
            string script = Path.Combine(root, ".codex", "skills", "_shared", "scripts", "delivery_tools.ps1");

            string defaultJson = RunPowerShell(root, $"-NoProfile -ExecutionPolicy Bypass -File \"{script}\" -Mode ArtifactPaths -CommitSha abc123");
            string azureJson = RunPowerShell(root, $"-NoProfile -ExecutionPolicy Bypass -File \"{script}\" -Mode ArtifactPaths -CommitSha abc123 -DeploymentProvider azure-appservice");

            using JsonDocument defaultPaths = JsonDocument.Parse(defaultJson);
            using JsonDocument azure = JsonDocument.Parse(azureJson);

            Assert.Equal("k3d", defaultPaths.RootElement.GetProperty("deploymentProvider").GetString());
            Assert.Equal("app/abc123/container-images.json", defaultPaths.RootElement.GetProperty("containerImages").GetString());
            Assert.Equal("app/abc123/monitoring-summary-{environment}.json", defaultPaths.RootElement.GetProperty("monitoringSummaryPattern").GetString());
            Assert.Equal("app/abc123/qa-observability.json", defaultPaths.RootElement.GetProperty("qaObservability").GetString());

            Assert.Equal("azure-appservice", azure.RootElement.GetProperty("deploymentProvider").GetString());
            Assert.Equal("app/abc123/deployable-apps.json", azure.RootElement.GetProperty("topology").GetString());
            Assert.False(azure.RootElement.TryGetProperty("containerImages", out _));
        }

        [Fact]
        public void K3dObservabilityUsesDirectHealthAndDirectSeqAppLogs()
        {
            string root = FindRepositoryRoot();
            string workflow = File.ReadAllText(Path.Combine(root, ".gitea", "workflows", "k3d-local-deploy.yml"));

            Assert.False(File.Exists(Path.Combine(root, "infra", "k3d", "capture-observability.sh")));
            Assert.DoesNotContain("/ingest/clef", workflow);
            Assert.DoesNotContain("pod.sanitized.log", workflow);
            Assert.DoesNotContain("probe_success", workflow);
            Assert.Contains("wait_for_direct_health", workflow);
            Assert.Contains("curl --fail --silent --show-error --location \"$site_url\"", workflow);
            Assert.Contains("jq -e '.status == \"ok\"'", workflow);
            Assert.Contains("healthCheckMode: \"direct-http\"", workflow);
            Assert.Contains("sleep 10", workflow);
            Assert.Contains("for attempt in 1 2 3 4 5 6", workflow);
            Assert.Contains("K3D_APP_SEQ_URL", File.ReadAllText(Path.Combine(root, "infra", "monitoring", "variables.env.example")));
            Assert.Contains("Serilog__WriteTo__1__Name", File.ReadAllText(Path.Combine(root, "infra", "k3d", "deploy-local-lab.sh")));
            Assert.Contains("Serilog__WriteTo__1__Args__serverUrl", File.ReadAllText(Path.Combine(root, "infra", "k3d", "deploy-local-lab.sh")));
            Assert.Contains("http://host.docker.internal:5341", File.ReadAllText(Path.Combine(root, "infra", "k3d", "deploy-local-lab.sh")));

            Assert.Contains("app/${GITHUB_SHA}/monitoring-summary.json", workflow);
            Assert.Contains("app/${GITHUB_SHA}/qa-observability.json", workflow);
            Assert.Contains("qa-observability.json", workflow);
        }

        [Fact]
        public void GrafanaInfinityDatasourceIncludesK3dHealthUrls()
        {
            string root = FindRepositoryRoot();
            string datasource = File.ReadAllText(Path.Combine(root, "infra", "monitoring", "grafana", "provisioning", "datasources", "infinity-health.yml"));

            Assert.Contains("uid: infinity-health", datasource);
            Assert.Contains("type: yesoreyeram-infinity-datasource", datasource);
            Assert.Contains("http://host.docker.internal:18081", datasource);
            Assert.Contains("http://host.docker.internal:18082", datasource);
            Assert.Contains("http://host.docker.internal:18083", datasource);
            Assert.Contains("http://host.docker.internal:18084", datasource);
            Assert.Contains("http://host.docker.internal:18085", datasource);
            Assert.Contains("http://host.docker.internal:18086", datasource);
            Assert.DoesNotContain("azurewebsites.net", datasource);
        }

        [Fact]
        public void ConfigureInfraAuditsSelectedK3dLocalLabSurfaces()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "scripts", "configure_infra_tools.ps1"));
            string configureSkill = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "SKILL.md"));

            Assert.Contains("function Add-K3dLocalLabAuditFindings", script);
            Assert.Contains("Add-K3dLocalLabAuditFindings $result", script);
            Assert.Contains("\"docker\", \"kubectl\"", script);
            Assert.Contains(".codex/providers/deploy.k3d.md", script);
            Assert.Contains(".gitea/workflows/k3d-local-deploy.yml", script);
            Assert.Contains("infra/k3d/deploy-local-lab.sh", script);
            Assert.DoesNotContain("infra/k3d/capture-observability.sh", script);
            Assert.Contains("src/SDDTemplate.Site/Dockerfile", script);
            Assert.Contains("src/SDDTemplate.Api/Dockerfile", script);
            Assert.Contains("NEXUS_DOCKER_REGISTRY", script);
            Assert.Contains("K3D_KUBECONFIG_B64", script);
            Assert.Contains("SEQ_URL=http://localhost:5341", script);
            Assert.Contains("infinity-health", script);
            Assert.DoesNotContain("PROMETHEUS_URL=http://localhost:9091", script);
            Assert.DoesNotContain("K3D_OBSERVABILITY_ENABLED=true", script);
            Assert.Contains("k3d local lab", configureSkill);
            Assert.Contains("providers.deployment", script);
            Assert.Contains("Current k3d monitoring compose excludes local otelcol", script);
        }

        [Fact]
        public void ConfigureInfraCanEnsureK3dCluster()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "scripts", "configure_infra_tools.ps1"));
            string configureSkill = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "SKILL.md"));
            string aliasSkill = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-infra-tools", "SKILL.md"));
            string adapter = File.ReadAllText(Path.Combine(root, ".codex", "providers", "deploy.k3d.md"));
            string k3dReadme = File.ReadAllText(Path.Combine(root, "infra", "k3d", "README.md"));

            Assert.Contains("\"EnsureK3dCluster\"", script);
            Assert.Contains("function Invoke-EnsureK3dCluster", script);
            Assert.Contains("\"k3d\" @(\"cluster\", \"list\", $K3dClusterName, \"-o\", \"json\")", script);
            Assert.Contains("\"cluster\", \"create\", $K3dClusterName", script);
            Assert.Contains("\"--api-port\", \"127.0.0.1:$K3dApiPort\"", script);
            Assert.Contains("\"kubeconfig\", \"merge\", $K3dClusterName", script);
            Assert.Contains("\"--kubeconfig-merge-default\"", script);
            Assert.Contains("Get-Command $FileName", script);
            Assert.Contains("[System.IO.Path]::GetExtension($resolvedPath) -in @(\".cmd\", \".bat\")", script);
            Assert.Contains("\"get\", \"nodes\", \"-o\", \"json\", \"--request-timeout=5s\"", script);
            Assert.Contains("timed out after $TimeoutSeconds seconds", script);
            Assert.Contains("$startInfo.Arguments = $escapedArguments -join \" \"", script);
            Assert.Contains("nodes.ready", script);
            Assert.Contains("k3d cluster '$K3dClusterName' is missing", script);
            Assert.Contains("run `EnsureK3dCluster` before `EnsureK3dHeadlamp`, `EnsureK3dPortForwards`, `ShowEnvironmentUrls`, and `Audit`", configureSkill);
            Assert.Contains("`EnsureK3dCluster`, `EnsureK3dHeadlamp`, and `EnsureK3dPortForwards` when k3d is selected", aliasSkill);
            Assert.Contains("Plain `Audit` only reports missing or unhealthy k3d cluster state", adapter);
            Assert.Contains("explicit `config infra` runs `EnsureK3dCluster`", k3dReadme);
        }

        [Fact]
        public void ConfigureInfraCanEnsureK3dPortForwards()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "scripts", "configure_infra_tools.ps1"));
            string configureSkill = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "SKILL.md"));
            string aliasSkill = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-infra-tools", "SKILL.md"));
            string adapter = File.ReadAllText(Path.Combine(root, ".codex", "providers", "deploy.k3d.md"));
            string k3dReadme = File.ReadAllText(Path.Combine(root, "infra", "k3d", "README.md"));

            Assert.Contains("\"EnsureK3dPortForwards\"", script);
            Assert.Contains("function Invoke-EnsureK3dPortForwards", script);
            Assert.Contains("function Get-K3dPortForwardMappings", script);
            Assert.Contains("\"port-forward\"", script);
            Assert.Contains("\"--address\", \"127.0.0.1\"", script);
            Assert.Contains("Start-Process -FilePath \"kubectl\"", script);
            Assert.Contains("-WindowStyle Hidden", script);

            foreach (int port in new[] { 18081, 18082, 18083, 18084, 18085, 18086 })
            {
                Assert.Contains(port.ToString(), script);
                Assert.Contains($"127.0.0.1:{port}", adapter);
            }

            Assert.Contains("EnsureK3dCluster` before `EnsureK3dHeadlamp`, `EnsureK3dPortForwards`, `ShowEnvironmentUrls`, and `Audit`", configureSkill);
            Assert.Contains("starts localhost browser mappings", configureSkill);
            Assert.Contains("`EnsureK3dPortForwards` when k3d is selected", aliasSkill);
            Assert.Contains("Plain `Audit` only reports missing mappings", adapter);
            Assert.Contains("Windows cannot resolve the `*.sdd.localhost` ingress hosts", k3dReadme);
        }

        [Fact]
        public void ConfigureInfraCanEnsureK3dHeadlamp()
        {
            string root = FindRepositoryRoot();
            string script = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "scripts", "configure_infra_tools.ps1"));
            string configureSkill = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-dev-environment", "SKILL.md"));
            string aliasSkill = File.ReadAllText(Path.Combine(root, ".codex", "skills", "configure-infra-tools", "SKILL.md"));
            string adapter = File.ReadAllText(Path.Combine(root, ".codex", "providers", "deploy.k3d.md"));
            string k3dReadme = File.ReadAllText(Path.Combine(root, "infra", "k3d", "README.md"));

            Assert.Contains("\"EnsureK3dHeadlamp\"", script);
            Assert.Contains("function Invoke-EnsureK3dHeadlamp", script);
            Assert.Contains("helm\" @(\"repo\", \"add\", \"headlamp\", \"https://kubernetes-sigs.github.io/headlamp/\"", script);
            Assert.Contains("\"upgrade\", \"--install\", \"headlamp\", \"headlamp/headlamp\"", script);
            Assert.Contains("\"rollout\", \"status\", \"deploy/headlamp\"", script);
            Assert.Contains("\"svc/headlamp\"", script);
            Assert.Contains("\"4466:80\"", script);
            Assert.Contains("kubectl create token headlamp --namespace headlamp | Set-Clipboard", script);
            Assert.DoesNotContain("ConvertTo-SecureString", script);

            Assert.Contains("EnsureK3dHeadlamp", configureSkill);
            Assert.Contains("Tokens must not be printed", configureSkill);
            Assert.Contains("install Headlamp through `EnsureK3dHeadlamp`", aliasSkill);
            Assert.Contains("http://127.0.0.1:4466", adapter);
            Assert.Contains("kubectl create token headlamp --namespace headlamp | Set-Clipboard", k3dReadme);
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
              "ticketKey": "E2EPROJECT-1",
              "versionStatus": "local container candidate",
              "deploymentProvider": "k3d",
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
              "ticketKey": "E2EPROJECT-1",
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
