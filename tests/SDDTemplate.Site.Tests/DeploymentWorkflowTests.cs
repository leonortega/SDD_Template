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

        [Fact]
        public void ConfigureAuditRequiresDeliveryContextLockGitignoreEntry()
        {
            string script = ReadConfigureScript();

            Assert.Contains(".codex/delivery-context.local.json", script);
            Assert.Contains("Local ticket context lock must be ignored", script);
            Assert.Contains(".codex/parallel-delivery.local.json", script);
            Assert.Contains("Parallel delivery runtime state must be ignored", script);
        }

        [Fact]
        public void DeliveryContextLockIsIgnoredAndSharedContractDefinesIt()
        {
            string gitignore = File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, ".gitignore"));
            string contract = ReadSkill("_shared", "delivery-contract.md");

            Assert.Contains(".codex/delivery-context.local.json", gitignore);
            Assert.Contains(".codex/parallel-delivery.local.json", gitignore);
            Assert.Contains("## Ticket Context Lock", contract);
            Assert.Contains("Normal automatic delivery must stay locked to one Plane ticket.", contract);
            Assert.Contains("scopes it to the ticket worktree", contract);
            Assert.Contains("one Git worktree per active ticket", contract);
            Assert.Contains("deploymentLanePolicy", contract);
            Assert.Contains("serialized", contract);
            Assert.Contains("\"ticketKey\": \"E2EPROJECT-123\"", contract);
            Assert.Contains("release.json.planeTicketKey", contract);
            Assert.Contains("rollback-prod", contract);
        }

        [Fact]
        public void ParallelTicketCoordinatorSkillAndAgentAreDefined()
        {
            string skill = ReadSkill("parallel-ticket-coordinator", "SKILL.md");
            string agent = ReadSkill("parallel-ticket-coordinator", Path.Combine("agents", "openai.yaml"));

            Assert.Contains("name: parallel-ticket-coordinator", skill);
            Assert.Contains("one Git worktree per active ticket", skill);
            Assert.Contains(".codex/parallel-delivery.local.json", skill);
            Assert.Contains("serialized deployment lane", skill);
            Assert.Contains("Parallel Ticket Coordinator", agent);
            Assert.Contains("$parallel-ticket-coordinator", agent);
        }

        [Fact]
        public void ClientToolsExampleDefinesParallelDeliveryDefaults()
        {
            string config = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "client-tools.example.json"));

            Assert.Contains("\"parallelDelivery\"", config);
            Assert.Contains("\"enabled\": false", config);
            Assert.Contains("\"maxActiveTickets\": 2", config);
            Assert.Contains("\"worktreeRoot\": \"../ticket-worktrees\"", config);
            Assert.Contains("\"deploymentLanePolicy\": \"serialized\"", config);
            Assert.Contains("\"agentModelPolicy\"", config);
            Assert.Contains("\"coordinator\"", config);
            Assert.Contains("\"model\": \"inherit\"", config);
            Assert.Contains("\"pipelineStatus\"", config);
            Assert.Contains("\"model\": \"gpt-5.4-mini\"", config);
            Assert.Contains("\"ticketStarter\"", config);
            Assert.Contains("\"implementation\"", config);
            Assert.Contains("\"model\": \"gpt-5.3-codex\"", config);
            Assert.Contains("\"prReview\"", config);
            Assert.Contains("\"deployToProd\"", config);
            Assert.Contains("\"reasoningEffort\": \"high\"", config);

            string script = ReadConfigureScript();
            Assert.Contains("parallelDelivery\", \"agentModelPolicy\", \"pipelineStatus\", \"model", script);
            Assert.Contains("parallelDelivery\", \"agentModelPolicy\", \"implementation\", \"model", script);
            Assert.Contains("parallelDelivery\", \"agentModelPolicy\", \"deployToProd\", \"reasoningEffort", script);
        }

        [Fact]
        public void RecommendedToolsConfigAndCatalogUseGuidedManualDefaults()
        {
            string config = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "client-tools.example.json"));
            string catalog = ReadToolRecommendationsCatalog();

            Assert.Contains("\"recommendedTools\"", config);
            Assert.Contains("\"mode\": \"guided-manual\"", config);
            Assert.Contains("\"accepted\": []", config);
            Assert.Contains("\"dismissed\": []", config);
            Assert.Contains("\"mode\": \"guided-manual\"", catalog);
            Assert.Contains("\"installMethod\": \"manual-copy\"", catalog);
            Assert.Contains("\"installMethod\": \"manual-config\"", catalog);
            Assert.DoesNotContain("installCommand", catalog);
        }

        [Fact]
        public void RecommendedToolsAuditDetectsCurrentStackAndAvoidsPlaneMcp()
        {
            string script = ReadConfigureScript();
            string catalog = ReadToolRecommendationsCatalog();

            Assert.Contains("AuditRecommendedTools", script);
            Assert.Contains("SetRecommendedTools", script);
            Assert.Contains("function Get-DetectedStackTags", script);
            Assert.Contains("\"dotnet\"", script);
            Assert.Contains("\"plane\"", script);
            Assert.Contains("\"gitea\"", script);
            Assert.Contains("\"nexus\"", script);
            Assert.Contains("\"azure\"", script);
            Assert.Contains("\"e2e\"", script);
            Assert.Contains("Plane MCP is intentionally not recommended", catalog);
            Assert.Contains("repo-local skills must use the configured Plane API", catalog);
        }

        [Fact]
        public void ConfigureDocsDescribeManualSkillAcquisitionWorkflow()
        {
            string configureRouter = ReadSkill("configure-dev-environment", "SKILL.md");
            string readme = File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, "README.md"));

            Assert.Contains("AuditRecommendedTools", configureRouter);
            Assert.Contains("SetRecommendedTools", configureRouter);
            Assert.Contains("read the source `SKILL.md`", configureRouter);
            Assert.Contains("create `.codex/skills/{skill-name}/`", configureRouter);
            Assert.Contains("manual repo-based acquisition", configureRouter);
            Assert.Contains("manual by default", readme);
            Assert.Contains("read the source repository's `SKILL.md`", readme);
            Assert.Contains(".codex/tool-recommendations.example.json", readme);
        }

        [Fact]
        public void SkillSynchronizationRuleRequiresConfigureCheckAfterDeliverySkillChanges()
        {
            string contract = ReadSkill("_shared", "delivery-contract.md");
            string configureRouter = ReadSkill("configure-dev-environment", "SKILL.md");

            Assert.Contains("Before finishing any change to a non-OpenSpec delivery skill", contract);
            Assert.Contains("update the matching `configure-*` skill docs, references, templates, scripts, and tests in the same change", contract);
            Assert.Contains("state in the final response that the configure skills were checked and no configure sync was required", contract);
            Assert.Contains("Before changing configure behavior or finishing any non-OpenSpec delivery skill change", configureRouter);
            Assert.Contains("If no configure update is needed, say that explicitly in the final response", configureRouter);
        }

        [Fact]
        public void SharedDeliveryToolsExposeReusableWorkflowModes()
        {
            string contract = ReadSkill("_shared", "delivery-contract.md");
            string script = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                "_shared",
                "scripts",
                "delivery_tools.ps1"));

            foreach (string mode in new[]
            {
                "ValidateTicketLock",
                "ValidateDeploymentLane",
                "RenderPlaneComment",
                "UpdateReleaseManifest"
            })
            {
                Assert.Contains(mode, contract);
                Assert.Contains(mode, script);
            }

            Assert.Contains("function Test-TicketLock", script);
            Assert.Contains("function Test-DeploymentLane", script);
            Assert.Contains("function Render-PlaneComment", script);
            Assert.Contains("function Update-ReleaseManifest", script);
        }

        [Fact]
        public void DeliverySkillsUseSharedToolsForRepeatedMechanics()
        {
            Dictionary<string, string[]> expectations = new()
            {
                ["deploy-to-qa"] =
                [
                    "ValidateTicketLock",
                    "ValidateDeploymentLane",
                    "UpdateReleaseManifest",
                    "RenderPlaneComment -Type QADeployment"
                ],
                ["test-e2e"] =
                [
                    "ValidateTicketLock",
                    "ValidateDeploymentLane",
                    "UpdateReleaseManifest",
                    "RenderPlaneComment -Type E2EQA"
                ],
                ["deploy-to-prod"] =
                [
                    "ValidateTicketLock",
                    "ValidateDeploymentLane",
                    "UpdateReleaseManifest",
                    "RenderPlaneComment -Type ProdDeployment"
                ],
                ["post-merge-deploy"] =
                [
                    "ValidateTicketLock",
                    "ValidateDeploymentLane",
                    "ArtifactPaths"
                ],
                ["rollback-prod"] =
                [
                    "ValidateTicketLock",
                    "UpdateReleaseManifest",
                    "ValidateReleaseManifest"
                ]
            };

            foreach ((string skillName, string[] expectedModes) in expectations)
            {
                string skill = ReadSkill(skillName, "SKILL.md");

                Assert.Contains(".codex/skills/_shared/scripts/delivery_tools.ps1", skill);
                foreach (string expectedMode in expectedModes)
                {
                    Assert.Contains(expectedMode, skill);
                }
            }
        }

        [Fact]
        public void DeliveryFlowSkillsEnforceTicketContextLock()
        {
            string[] skillNames =
            [
                "automatic-implement-ticket",
                "parallel-ticket-coordinator",
                "plane-start-ticket",
                "implement-ticket",
                "gitea-pr-review-agent",
                "post-merge-deploy",
                "deploy-to-qa",
                "test-e2e",
                "deploy-to-prod",
                "file-qa-bug",
                "pipeline-status",
                "hotfix-prod",
                "rollback-prod"
            ];

            foreach (string skillName in skillNames)
            {
                string skill = ReadSkill(skillName, "SKILL.md");
                Assert.Contains("delivery-context.local.json", skill);
            }
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

        private static string ReadToolRecommendationsCatalog()
        {
            return File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "tool-recommendations.example.json"));
        }

        private static string ReadSkill(string skillName, string fileName)
        {
            return File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                skillName,
                fileName));
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
