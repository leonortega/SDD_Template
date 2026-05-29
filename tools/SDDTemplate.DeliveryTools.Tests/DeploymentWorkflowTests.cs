using System.Text.Json;

namespace SDDTemplate.DeliveryTools.Tests
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

            Assert.Contains("ReadDeliveryPolicy", workflow);
            Assert.Contains("ExtractTicketKey", workflow);
            Assert.Contains("deploy_allowed=$deploy_allowed", workflow);
            Assert.Contains("needs.classify-changes.outputs.deploy_allowed == 'true'", workflow);
        }

        [Fact]
        public void PackageUploadsBaselineReleaseManifest()
        {
            string workflow = ReadWorkflow();
            string packageJob = GetJobSection(workflow, "package");

            Assert.Contains("CreateReleaseManifest", packageJob);
            Assert.Contains("--commit-sha \"$commit_sha\"", packageJob);
            Assert.Contains("--checksum \"$checksum\"", packageJob);
            Assert.Contains("--artifact-url \"$artifact_url\"", packageJob);
            Assert.Contains("--plane-ticket-key \"$plane_ticket_key\"", packageJob);
            Assert.Contains("--version-status unversioned", packageJob);
            Assert.Contains("ValidateReleaseManifest", packageJob);
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
            Assert.Contains("ReadDeliveryPolicy", classifyJob);
            Assert.Contains("ExtractTicketKey", classifyJob);
        }

        [Fact]
        public void SolutionFileChangesIncludeSlnxAsAppAffecting()
        {
            string workflow = ReadWorkflow();
            string classifyJob = GetJobSection(workflow, "classify-changes");

            Assert.Contains("*.slnx", classifyJob);
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

            Assert.Contains("CreateReleaseManifest", script);
            Assert.Contains("--plane-ticket-key \"$plane_ticket_key\"", script);
            Assert.Contains("--version-status unversioned", script);
            Assert.Contains("ValidateReleaseManifest", script);
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
        public void AgentOptimizationPolicyDocsAndEvalFixturesAreDefined()
        {
            string root = FindRepositoryRoot().FullName;
            string deliveryPolicy = File.ReadAllText(Path.Combine(root, ".codex", "delivery-policy.json"));
            string gitignore = File.ReadAllText(Path.Combine(root, ".gitignore"));
            string contextDocs = ReadDoc("context-management.md");
            string developmentDocs = ReadDoc("development.md");
            string retrospective = ReadSkill("delivery-retrospective-audit", "SKILL.md");
            string skillStartup = ReadSkill("_shared", "skill-startup.md");

            using JsonDocument policy = JsonDocument.Parse(deliveryPolicy);
            JsonElement optimization = policy.RootElement.GetProperty("agentOptimization");
            Assert.True(optimization.GetProperty("promptCache").GetProperty("enabled").GetBoolean());
            Assert.True(optimization.GetProperty("promptCache").GetProperty("staticContextFirst").GetBoolean());
            Assert.True(optimization.GetProperty("workflowEvals").GetProperty("requireEvalEvidenceBeforeNewAgentRole").GetBoolean());
            Assert.Contains("cachedTokens", optimization.GetProperty("telemetry").GetProperty("requiredFields").EnumerateArray().Select(field => field.GetString()));

            using JsonDocument cases = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, ".codex", "agent-evals", "workflow-cases.json")));
            string[] caseIds = [.. cases.RootElement.GetProperty("cases").EnumerateArray().Select(item => item.GetProperty("id").GetString() ?? string.Empty)];
            Assert.Contains("ticket-start-lock-created", caseIds);
            Assert.Contains("implementation-quality-gated", caseIds);
            Assert.Contains("qa-promotion-artifact-lineage", caseIds);
            Assert.Contains("prod-explicit-artifact-promotion", caseIds);
            Assert.Contains("rollback-no-main-rewrite", caseIds);

            Assert.Contains(".codex/agent-telemetry.local.jsonl", gitignore);
            Assert.Contains(".codex/agent-evals/results.local.json", gitignore);
            Assert.Contains("## Prompt Cache Hygiene", contextDocs);
            Assert.Contains("## Agent Telemetry", contextDocs);
            Assert.Contains("## Agent Workflow Evals", developmentDocs);
            Assert.Contains("audit_skill_contracts.ps1", developmentDocs);
            Assert.Contains("model-optimization", retrospective);
            Assert.Contains("eval-coverage", retrospective);
            Assert.Contains(".codex/delivery-policy.json", skillStartup);
            Assert.Contains("agentOptimization", skillStartup);
        }

        [Fact]
        public void SkillContractAuditScriptRunsInAdvisoryModeByDefault()
        {
            string script = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                "_shared",
                "scripts",
                "audit_skill_contracts.ps1"));

            Assert.Contains("FailOnFindings", script);
            Assert.Contains("IncludeConfigure", script);
            Assert.Contains("IncludeOpenSpec", script);
            Assert.Contains("AllSkills", script);
            Assert.Contains("requiredSections", script);
            Assert.Contains("requiredTerms", script);
            Assert.Contains("ConvertTo-Json -Depth 10", script);
            Assert.Contains("if ($FailOnFindings -and $summary.failed -gt 0)", script);
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
        public void ParallelDeliveryDocsContractsAndCoordinatorDefinePreflightRolesAndRecovery()
        {
            string readme = File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, "README.md"));
            string docs = ReadDoc("parallel-delivery.md");
            string contract = ReadSkill("_shared", "delivery-contract.md");
            string coordinator = ReadSkill("parallel-ticket-coordinator", "SKILL.md");
            string configureRouter = ReadSkill("configure-dev-environment", "SKILL.md");

            Assert.Contains("docs/parallel-delivery.md", readme);
            Assert.Contains("## Cleanup And Recovery", docs);
            Assert.Contains("Can I safely start these 2 tickets in parallel?", docs);
            Assert.Contains("parallelDelivery.maxActiveTickets=2", docs);
            Assert.Contains("parallelDelivery.enabled=false", docs);
            Assert.Contains("local runtime files required by child worktrees", docs);

            Assert.Contains("Before Git, Plane, or Gitea mutation", contract);
            Assert.Contains("ValidateParallelDeliveryDryRun", contract);
            Assert.Contains("one worktree", contract);
            Assert.Contains("Never let two agents mutate the same Plane ticket", contract);
            Assert.Contains("Never parallelize DEV, QA, E2E QA, PROD, rollback, or hotfix promotion", contract);

            Assert.Contains("Before any Git, Plane, or Gitea mutation", coordinator);
            Assert.Contains("Failed `ValidateParallelDeliveryDryRun`", coordinator);
            Assert.Contains("## Cleanup And Recovery", coordinator);
            Assert.Contains("required ignored local runtime files", coordinator);

            foreach (string role in new[]
            {
                "coordinator",
                "ticketStarter",
                "implementation",
                "prReview",
                "deployment",
                "qa",
                "prodHotfix"
            })
            {
                Assert.Contains($"`{role}`", docs);
                Assert.Contains($"`{role}`", contract);
                Assert.Contains($"`{role}`", coordinator);
            }

            Assert.Contains("parallelDelivery.enabled=false", configureRouter);
            Assert.Contains("docs/parallel-delivery.md", configureRouter);
            Assert.Contains("required ignored local runtime files", configureRouter);
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
        public void CanonicalContextDocsExistAndReadmeLinksThem()
        {
            string readme = File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, "README.md"));

            foreach (string docPath in new[]
            {
                "context-management.md",
                "architecture.md",
                "development.md",
                "deployment.md"
            })
            {
                string doc = ReadDoc(docPath);
                Assert.False(string.IsNullOrWhiteSpace(doc));
                Assert.Contains($"docs/{docPath}", readme);
            }

            Assert.Contains("## Canonical Context", readme);
            Assert.Contains("Docs: no durable context changes", readme);
        }

        [Fact]
        public void DeliveryContractReferencesContextManagementDocs()
        {
            string contract = ReadSkill("_shared", "delivery-contract.md");

            Assert.Contains("docs/context-management.md", contract);
            Assert.Contains("docs/architecture.md", contract);
            Assert.Contains("docs/development.md", contract);
            Assert.Contains("docs/deployment.md", contract);
            Assert.Contains("delivery contract wins for automation behavior", contract);
        }

        [Fact]
        public void ImplementationSkillsRequireContextFindingsReview()
        {
            string skill = ReadSkill("implement-ticket", "SKILL.md");

            Assert.Contains("Context Findings Review", skill);
            Assert.Contains("docs/context-management.md", skill);
            Assert.Contains("Docs: no durable context changes", skill);
            Assert.Contains("Context findings: added/updated/none", skill);
            Assert.Contains("Assumptions recorded: <short list or none>", skill);
        }

        [Fact]
        public void ContextFindingClassificationRoutesToCanonicalDocs()
        {
            string contract = ReadSkill("_shared", "delivery-contract.md");
            string contextDocs = ReadDoc("context-management.md");
            string retrospective = ReadSkill("delivery-retrospective-audit", "SKILL.md");
            string implementation = ReadSkill("implement-ticket", "SKILL.md");
            string contextFindings = GetSection(contextDocs, "## Context Findings");

            Assert.Contains("docs/architecture.md", contextFindings);
            Assert.Contains("docs/development.md", contextFindings);
            Assert.Contains("docs/deployment.md", contextFindings);
            Assert.Contains("docs/context-management.md", contextFindings);
            Assert.Contains(".codex/skills/_shared/delivery-contract.md", contextFindings);

            Assert.DoesNotContain("Equivalent plain-language routing", contextDocs);
            Assert.Contains("Implementation PR bodies and Plane handoff comments", contract);
            Assert.Contains("Context Findings classification from `docs/context-management.md`", contract);
            Assert.Contains("Context Findings classification from `docs/context-management.md`", implementation);
            Assert.Contains("Context Findings classification from `docs/context-management.md`", retrospective);
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
                "ReadDeliveryPolicy",
                "ExtractTicketKey",
                "ReadCoverageThreshold",
                "ReadCoberturaLineRate",
                "ValidateTicketLock",
                "ValidateDeploymentLane",
                "ValidateParallelDeliveryDryRun",
                "RenderPlaneComment",
                "UpdateReleaseManifest"
            })
            {
                Assert.Contains(mode, contract);
                Assert.Contains(mode, script);
            }

            Assert.Contains("function Test-TicketLock", script);
            Assert.Contains("function Test-DeploymentLane", script);
            Assert.Contains("function Get-DeliveryPolicy", script);
            Assert.Contains("function Get-ExtractedTicketKey", script);
            Assert.Contains("function Get-CoverageThreshold", script);
            Assert.Contains("function Get-CoberturaLineRate", script);
            Assert.Contains("function Test-ParallelDeliveryDryRun", script);
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
        public void DeliverySkillsReferenceSharedContextDocsByRole()
        {
            string[] deliverySkills =
            [
                "automatic-implement-ticket",
                "delivery-retrospective-audit",
                "deploy-to-prod",
                "deploy-to-qa",
                "file-qa-bug",
                "gitea-pr-review-agent",
                "hotfix-prod",
                "implement-ticket",
                "parallel-ticket-coordinator",
                "pipeline-status",
                "plane-start-ticket",
                "post-merge-deploy",
                "rollback-prod",
                "test-e2e"
            ];

            foreach (string skillName in deliverySkills)
            {
                string skill = ReadSkill(skillName, "SKILL.md");
                Assert.Contains(".codex/skills/_shared/delivery-contract.md", skill);
                Assert.Contains("docs/context-management.md", skill);
            }

            foreach (string skillName in new[]
            {
                "post-merge-deploy",
                "deploy-to-qa",
                "test-e2e",
                "deploy-to-prod",
                "rollback-prod",
                "hotfix-prod",
                "file-qa-bug"
            })
            {
                Assert.Contains("docs/deployment.md", ReadSkill(skillName, "SKILL.md"));
            }

            foreach (string skillName in new[]
            {
                "implement-ticket",
                "gitea-pr-review-agent",
                "hotfix-prod",
                "file-qa-bug",
                "delivery-retrospective-audit"
            })
            {
                Assert.Contains("docs/development.md", ReadSkill(skillName, "SKILL.md"));
            }

            foreach (string skillName in new[]
            {
                "automatic-implement-ticket",
                "parallel-ticket-coordinator",
                "pipeline-status",
                "plane-start-ticket",
                "delivery-retrospective-audit"
            })
            {
                Assert.Contains("docs/architecture.md", ReadSkill(skillName, "SKILL.md"));
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

        [Fact]
        public void FrontendTestingDebuggingSkillIsInstalledAndPreferredForWebsiteQa()
        {
            string frontendSkill = ReadSkill("frontend-testing-debugging", "SKILL.md");
            string e2eSkill = ReadSkill("test-e2e", "SKILL.md");

            Assert.Contains("name: frontend-testing-debugging", frontendSkill);
            Assert.Contains("Prefer the Browser plugin", frontendSkill);
            Assert.Contains("$frontend-testing-debugging", e2eSkill);
            Assert.Contains("Blazor", e2eSkill);
            Assert.Contains("browser-visible validation", e2eSkill);
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

        private static string ReadDoc(string fileName)
        {
            return File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                "docs",
                fileName));
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
