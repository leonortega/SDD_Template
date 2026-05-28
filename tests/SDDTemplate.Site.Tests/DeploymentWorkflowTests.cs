namespace SDDTemplate.Site.Tests
{
    public sealed class DeploymentWorkflowTests
    {
        [Fact]
        public void ProdDeploymentDownloadsExistingArtifactByInputCommit()
        {
            string workflow = ReadWorkflow();

            Assert.Contains("artifact_commit_sha", workflow);
            Assert.Contains("PROD_ARTIFACT_COMMIT_SHA=$artifact_commit_sha", workflow);
            Assert.Contains("app/$PROD_ARTIFACT_COMMIT_SHA/app.zip", workflow);
            Assert.Contains("app/$PROD_ARTIFACT_COMMIT_SHA/app.zip.sha256", workflow);
        }

        [Fact]
        public void ProdDeploymentDoesNotRebuildArtifact()
        {
            string workflow = ReadWorkflow();
            string prodJob = GetSection(workflow, "  deploy-prod:");

            Assert.DoesNotContain("dotnet publish", prodJob);
            Assert.DoesNotContain("Upload artifact to Nexus", prodJob);
            Assert.DoesNotContain("app/${GITHUB_SHA}/app.zip", prodJob);
        }

        [Fact]
        public void ProdDeploymentChecksPageAndHealthEndpoint()
        {
            string workflow = ReadWorkflow();
            string prodJob = GetSection(workflow, "  deploy-prod:");

            Assert.Contains("Smoke check PROD", prodJob);
            Assert.Contains("<title>SDD Template</title>", prodJob);
            Assert.Contains("$AZURE_PROD_WEBAPP_URL/health", prodJob);
            Assert.Contains("'\"status\":\"ok\"'", prodJob);
        }

        [Fact]
        public void PushDeploymentsRequireTicketNamedCommitOrMergedPr()
        {
            string workflow = ReadWorkflow();

            Assert.Contains("ticketKeyPattern", workflow);
            Assert.Contains("ticket_pattern=\"^${ticket_key_pattern}: \"", workflow);
            Assert.Contains("merge_pr_pattern=\"^Merge pull request '${ticket_key_pattern}:\"", workflow);
            Assert.Contains("deploy_allowed=$deploy_allowed", workflow);
            Assert.Contains("needs.classify-changes.outputs.deploy_allowed == 'true'", workflow);
        }

        [Fact]
        public void PackageUploadsBaselineReleaseManifest()
        {
            string workflow = ReadWorkflow();
            string packageJob = GetJobSection(workflow, "package");

            Assert.Contains("cat > artifacts/release.json", packageJob);
            Assert.Contains("\"schemaVersion\": 1", packageJob);
            Assert.Contains("\"commitSha\": \"$commit_sha\"", packageJob);
            Assert.Contains("\"checksum\": \"$checksum\"", packageJob);
            Assert.Contains("\"artifactUrl\": \"$artifact_url\"", packageJob);
            Assert.Contains("\"planeTicketKey\": \"$plane_ticket_key\"", packageJob);
            Assert.Contains("\"versionStatus\": \"unversioned\"", packageJob);
            Assert.Contains("app/${GITHUB_SHA}/release.json", packageJob);
        }

        [Fact]
        public void DevPushDeploysDevAndQaOnlyWhenTicketGated()
        {
            string workflow = ReadWorkflow();

            Assert.Contains("github.ref == 'refs/heads/dev'", GetJobSection(workflow, "package"));
            Assert.Contains("github.ref == 'refs/heads/dev'", GetJobSection(workflow, "deploy-dev"));
            Assert.Contains("github.ref == 'refs/heads/dev'", GetJobSection(workflow, "deploy-qa"));
            Assert.DoesNotContain("refs/heads/main", GetJobSection(workflow, "package"));
            Assert.DoesNotContain("refs/heads/main", GetJobSection(workflow, "deploy-dev"));
            Assert.DoesNotContain("refs/heads/main", GetJobSection(workflow, "deploy-qa"));
        }

        [Fact]
        public void MainPushDeploysProdOnlyWithoutRebuild()
        {
            string workflow = ReadWorkflow();
            string prodJob = GetJobSection(workflow, "deploy-prod");

            Assert.Contains("github.ref == 'refs/heads/main'", prodJob);
            Assert.Contains("artifact_commit_sha=\"$GITHUB_SHA\"", prodJob);
            Assert.DoesNotContain("dotnet publish", prodJob);
            Assert.DoesNotContain("Upload artifact to Nexus", prodJob);
            Assert.DoesNotContain("deploy-dev", prodJob);
            Assert.DoesNotContain("deploy-qa", prodJob);
        }

        [Fact]
        public void ConfigOnlyAndSddChangesDoNotDeployOnPush()
        {
            string workflow = ReadWorkflow();
            string classifyJob = GetJobSection(workflow, "classify-changes");

            Assert.Contains("app_changed=false", classifyJob);
            Assert.DoesNotContain(".codex/*", classifyJob);
            Assert.DoesNotContain(".gitea/*", classifyJob);
            Assert.Contains("deploy_allowed=false", classifyJob);
            Assert.Contains("ticket_pattern=\"^${ticket_key_pattern}: \"", classifyJob);
            Assert.Contains("merge_pr_pattern=\"^Merge pull request '${ticket_key_pattern}:\"", classifyJob);
        }

        [Fact]
        public void ConfigureAuditRequiresAllWorkflowSecretsInReadme()
        {
            string script = ReadConfigureScript();
            string readmeAudit = GetBetween(
                script,
                "$secretsDoc = \".gitea/workflows/README.md\"",
                "Add-GiteaBranchProtectionAuditFindings $Result");

            Assert.Contains("NEXUS_REPOSITORY", readmeAudit);
            Assert.Contains("AZURE_DEV_RESOURCE_GROUP", readmeAudit);
            Assert.Contains("AZURE_DEV_WEBAPP_NAME", readmeAudit);
            Assert.Contains("AZURE_DEV_WEBAPP_URL", readmeAudit);
            Assert.Contains("AZURE_QA_RESOURCE_GROUP", readmeAudit);
            Assert.Contains("AZURE_QA_WEBAPP_NAME", readmeAudit);
            Assert.Contains("AZURE_QA_WEBAPP_URL", readmeAudit);
            Assert.Contains("AZURE_PROD_RESOURCE_GROUP", readmeAudit);
            Assert.Contains("AZURE_PROD_WEBAPP_NAME", readmeAudit);
            Assert.Contains("AZURE_PROD_WEBAPP_URL", readmeAudit);
            Assert.Contains("Required Gitea Actions secret is not documented.", readmeAudit);
        }

        [Fact]
        public void ConfigureLiveSecretAuditRequiresProdAzureSecrets()
        {
            string script = ReadConfigureScript();
            string liveSecretAudit = GetBetween(
                script,
                "function Add-GiteaActionsSecretAuditFindings",
                "function Get-NexusConfig");

            Assert.Contains("\"AZURE_PROD_RESOURCE_GROUP\"", liveSecretAudit);
            Assert.Contains("\"AZURE_PROD_WEBAPP_NAME\"", liveSecretAudit);
            Assert.Contains("\"AZURE_PROD_WEBAPP_URL\"", liveSecretAudit);
        }

        [Fact]
        public void ConfigureTemplateUploadsBaselineReleaseManifest()
        {
            string script = ReadConfigureScript();

            Assert.Contains("cat > artifacts/release.json", script);
            Assert.Contains("\"schemaVersion\": 1", script);
            Assert.Contains("\"planeTicketKey\": \"$plane_ticket_key\"", script);
            Assert.Contains("\"versionStatus\": \"unversioned\"", script);
            Assert.Contains("app/${GITHUB_SHA}/release.json", script);
            Assert.Contains("Package/deploy workflow should upload a baseline Nexus release manifest next to the artifact.", script);
        }

        private static string ReadWorkflow()
        {
            return File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".gitea",
                "workflows",
                "package-deploy.yml"));
        }

        private static string ReadConfigureScript()
        {
            return File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                "configure-dev-environment",
                "scripts",
                "configure_infra_tools.ps1"));
        }

        private static string GetSection(string content, string sectionHeader)
        {
            int start = content.IndexOf(sectionHeader, StringComparison.Ordinal);
            Assert.True(start >= 0, $"Expected workflow section '{sectionHeader}' to exist.");

            return content[start..];
        }

        private static string GetJobSection(string content, string jobName)
        {
            string sectionHeader = $"  {jobName}:";
            int start = content.IndexOf(sectionHeader, StringComparison.Ordinal);
            Assert.True(start >= 0, $"Expected workflow job '{jobName}' to exist.");

            int next = content.IndexOf("\n  ", start + sectionHeader.Length, StringComparison.Ordinal);
            while (next >= 0 && next + 3 < content.Length && content[next + 3] == ' ')
            {
                next = content.IndexOf("\n  ", next + 1, StringComparison.Ordinal);
            }

            return next < 0 ? content[start..] : content[start..next];
        }

        private static string GetBetween(string content, string startMarker, string endMarker)
        {
            int start = content.IndexOf(startMarker, StringComparison.Ordinal);
            Assert.True(start >= 0, $"Expected start marker '{startMarker}' to exist.");

            int end = content.IndexOf(endMarker, start + startMarker.Length, StringComparison.Ordinal);
            Assert.True(end >= 0, $"Expected end marker '{endMarker}' to exist after '{startMarker}'.");

            return content[start..end];
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
