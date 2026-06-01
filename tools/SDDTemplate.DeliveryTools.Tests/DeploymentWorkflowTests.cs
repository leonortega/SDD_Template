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
            Assert.Contains("late-human-pr-feedback-manual-resume", caseIds);
            Assert.Contains("qa-promotion-artifact-lineage", caseIds);
            Assert.Contains("prod-explicit-artifact-promotion", caseIds);
            Assert.Contains("rollback-no-main-rewrite", caseIds);

            Assert.Contains(".codex/agent-telemetry.local.jsonl", gitignore);
            Assert.Contains(".codex/agent-evals/results.local.json", gitignore);
            Assert.Contains("## Prompt Cache Hygiene", contextDocs);
            Assert.Contains("## Agent Telemetry", contextDocs);
            Assert.Contains("## Agent Workflow Evals", developmentDocs);
            Assert.Contains("audit_skill_contracts.ps1", developmentDocs);
            Assert.Contains("Normal process validation must use the default scope and exclude `openspec-*` skills", developmentDocs);
            Assert.Contains("model-optimization", retrospective);
            Assert.Contains("eval-coverage", retrospective);
            Assert.Contains(".codex/delivery-policy.json", skillStartup);
            Assert.Contains("agentOptimization", skillStartup);
        }

        [Fact]
        public void WorkflowEvalRequiresLateHumanFeedbackBatchResume()
        {
            string root = FindRepositoryRoot().FullName;
            using JsonDocument cases = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, ".codex", "agent-evals", "workflow-cases.json")));
            JsonElement lateFeedbackCase = cases.RootElement.GetProperty("cases").EnumerateArray().Single(item =>
                string.Equals(item.GetProperty("id").GetString(), "late-human-pr-feedback-manual-resume", StringComparison.Ordinal));

            Assert.Equal("automatic-implement-ticket", lateFeedbackCase.GetProperty("stage").GetString());
            Assert.Equal("implement-ticket", lateFeedbackCase.GetProperty("expectedRoute").GetString());

            string[] evidence = [.. lateFeedbackCase.GetProperty("requiredEvidence").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];
            string[] expectations = [.. lateFeedbackCase.GetProperty("toolExpectations").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];
            string[] stopConditions = [.. lateFeedbackCase.GetProperty("stopConditions").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];

            Assert.Contains("new human top-level or inline PR comment ids", evidence);
            Assert.Contains("Manual resume scans PR comments instead of relying on webhook or polling", expectations);
            Assert.Contains("Delegate feedback processing to pr-review-feedback-loop", expectations);
            Assert.Contains("Derive a new feedbackBatchId from sorted late human comment source ids", expectations);
            Assert.Contains("Keep Plane In Review while applying late human feedback fixes", expectations);
            Assert.Contains("late human comment source ids are already covered by a completed feedback batch", stopConditions);
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
            Assert.Contains("\"installMethod\": \"manual-reference\"", catalog);
            Assert.Contains("\"officialSources\"", catalog);
            Assert.Contains("\"searchQueries\"", catalog);
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
            Assert.Contains("\"dotnet-10\"", script);
            Assert.Contains("\"aspnet-core\"", script);
            Assert.Contains("\"blazor\"", script);
            Assert.Contains("\"xunit\"", script);
            Assert.Contains("\"coverage\"", script);
            Assert.Contains("\"plane\"", script);
            Assert.Contains("\"gitea\"", script);
            Assert.Contains("\"gitea-actions-runner\"", script);
            Assert.Contains("\"nexus\"", script);
            Assert.Contains("\"nexus-artifacts\"", script);
            Assert.Contains("\"azure\"", script);
            Assert.Contains("\"azure-app-service\"", script);
            Assert.Contains("\"prometheus\"", script);
            Assert.Contains("\"grafana\"", script);
            Assert.Contains("\"e2e\"", script);
            Assert.Contains("\"browser-e2e\"", script);
            Assert.Contains("\"playwright-guidance\"", script);
            Assert.Contains("Add-StackContextDriftFindings", script);
            Assert.Contains("dotnet-10-platform-guidance", catalog);
            Assert.Contains("manual-copy", catalog);
            Assert.Contains("repo:.codex/skills/frontend-testing-debugging/SKILL.md", catalog);
            Assert.Contains("https://playwright.dev/docs/best-practices", catalog);
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
            Assert.Contains("Do not install skills by command", configureRouter);
            Assert.Contains("stack-context drift", configureRouter);
            Assert.Contains("manual by default", readme);
            Assert.Contains("read the source repository's `SKILL.md`", readme);
            Assert.Contains("Skills are not installed by command", readme);
            Assert.Contains(".codex/tool-recommendations.example.json", readme);
        }

        [Fact]
        public void StackToolsetDocsAndOpenSpecContextAreDefined()
        {
            string architecture = ReadDoc("architecture.md");
            string development = ReadDoc("development.md");
            string deployment = ReadDoc("deployment.md");
            string openSpecConfig = File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, "openspec", "config.yaml"));

            Assert.Contains("## Technology Stack And Tool Set", architecture);
            Assert.Contains("Plane", architecture);
            Assert.Contains("Gitea Actions", architecture);
            Assert.Contains("Nexus", architecture);
            Assert.Contains("Azure App Service", architecture);
            Assert.Contains("Prometheus", architecture);
            Assert.Contains("Grafana", architecture);
            Assert.Contains("Skills are not installed by command", architecture);

            Assert.Contains("## Technology Stack And Tool Set", development);
            Assert.Contains(".NET 10", development);
            Assert.Contains("ASP.NET Core", development);
            Assert.Contains("Blazor", development);
            Assert.Contains("xUnit", development);
            Assert.Contains("coverlet", development);
            Assert.Contains("official-first research", development);
            Assert.Contains("Browser plugin and Playwright-style", development);

            Assert.Contains("## Technology Stack And Tool Set", deployment);
            Assert.Contains("Azure App Service", deployment);
            Assert.Contains("Prometheus", deployment);
            Assert.Contains("Grafana", deployment);
            Assert.Contains("qa/{ticketKey}/{runId}/qa-evidence.zip", deployment);

            Assert.Contains("context: |", openSpecConfig);
            Assert.Contains("Delivery tool set:", openSpecConfig);
            Assert.Contains("Application stack: .NET 10, ASP.NET Core, Blazor", openSpecConfig);
            Assert.Contains("Recommended skills are copied manually", openSpecConfig);
            Assert.Contains("Plane MCP is not used for ticket delivery", openSpecConfig);
            Assert.Contains("official-first research", openSpecConfig);
            Assert.Contains("rules:", openSpecConfig);
            Assert.Contains("proposal:", openSpecConfig);
            Assert.Contains("design:", openSpecConfig);
            Assert.Contains("tasks:", openSpecConfig);
            Assert.Contains("spec:", openSpecConfig);
        }

        [Fact]
        public void FirstTicketStartRequiresStackContextPreflight()
        {
            string readme = File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, "README.md"));
            string development = ReadDoc("development.md");
            string contract = ReadSkill("_shared", "delivery-contract.md");
            string starter = ReadSkill("plane-start-ticket", "SKILL.md");
            string automatic = ReadSkill("automatic-implement-ticket", "SKILL.md");
            string configure = ReadSkill("configure-dev-environment", "SKILL.md");

            Assert.Contains("Before the first ticket starts", readme);
            Assert.Contains("routes to `configure-dev-environment`", readme);
            Assert.Contains("Before the first ticket starts", development);
            Assert.Contains("stop before creating branches, Plane generated blocks, ticket locks, or OpenSpec proposals", development);

            Assert.Contains("Before starting the first ticket", contract);
            Assert.Contains("AuditRecommendedTools", contract);
            Assert.Contains("stack-context.*", contract);
            Assert.Contains("Route the operator to `configure-dev-environment`", contract);

            Assert.Contains("## Stack Context Preflight", starter);
            Assert.Contains("docs/architecture.md`, `docs/development.md`, and `docs/deployment.md` contain `Technology Stack And Tool Set`", starter);
            Assert.Contains("openspec/config.yaml` contains `context:` and `rules:`", starter);
            Assert.Contains(".codex/tool-recommendations.example.json", starter);
            Assert.Contains("AuditRecommendedTools", starter);
            Assert.Contains("stop before branch creation, Plane description updates, comments, state changes, ticket-lock writes, or OpenSpec proposal creation", starter);
            Assert.Contains("Run the Stack Context Preflight", starter);

            Assert.Contains("Stack Context Preflight", automatic);
            Assert.Contains("first ticket must not create a branch", automatic);
            Assert.Contains("stack-context.*", automatic);

            Assert.Contains("blocks the first ticket because stack context is missing", configure);
            Assert.Contains("openspec/config.yaml", configure);
            Assert.Contains(".codex/tool-recommendations.example.json", configure);
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
        public void ImplementationReviewLoopRequiresReconnectablePrFeedbackBatches()
        {
            string contract = ReadSkill("_shared", "delivery-contract.md");
            string implementation = ReadSkill("implement-ticket", "SKILL.md");
            string feedbackLoop = ReadSkill("pr-review-feedback-loop", "SKILL.md");
            string reviewAgent = ReadSkill("gitea-pr-review-agent", "SKILL.md");
            string autoRouter = ReadSkill("automatic-implement-ticket", "SKILL.md");
            string developmentDocs = ReadDoc("development.md");
            string giteaApiReference = ReadSkill("gitea-pr-review-agent", Path.Combine("references", "gitea-review-api.md"));

            Assert.Contains("PR Review Feedback", contract);
            Assert.Contains("top-level PR comments and inline code review comments", contract);
            Assert.Contains("IA generated PR feedback detected: {headSha}:{feedbackBatchId}", contract);
            Assert.Contains("IA generated PR feedback fixes: {headSha}:{feedbackBatchId}", contract);
            Assert.Contains("deterministic short id from the sorted source ids", contract);
            Assert.Contains("late human comments on the same `headSha`", contract);
            Assert.Contains("Commit and push", contract, StringComparison.OrdinalIgnoreCase);

            Assert.Contains("pr-review-feedback-loop", implementation);
            Assert.Contains("Do not put this local delivery behavior in external `openspec-*` skills", implementation);

            Assert.Contains("OpenSpec `## PR Review Feedback` tasks", feedbackLoop);
            Assert.Contains("including AI `BLOCKER`, `WARNING`, and `SUGGESTION` severities", feedbackLoop);
            Assert.Contains("Apply the requested code, test, documentation, or workflow change", feedbackLoop);
            Assert.Contains("Commit with the ticket key", feedbackLoop);
            Assert.Contains("IA generated PR feedback detected: {headSha}:{feedbackBatchId}", feedbackLoop);
            Assert.Contains("IA generated PR feedback fixes: {headSha}:{feedbackBatchId}", feedbackLoop);
            Assert.Contains("Keep Plane in `In Review`", implementation);

            Assert.Contains("Plane PR feedback detection/fix batch markers", autoRouter);
            Assert.Contains("later human comment on the same PR head SHA", autoRouter);
            Assert.Contains("route to `implement-ticket`", autoRouter);
            Assert.Contains("pr-review-feedback-loop", autoRouter);

            Assert.Contains("Human-authored comments are implementation inputs", reviewAgent);
            Assert.Contains("stable finding id", reviewAgent);
            Assert.Contains("pulls/{index}/reviews", giteaApiReference);
            Assert.Contains("pulls/{index}/reviews/{reviewId}/comments", giteaApiReference);
            Assert.Contains("Every AI finding in the review body must include a stable finding id", giteaApiReference);
            Assert.Contains("PR review feedback has two timed loops", developmentDocs);
            Assert.Contains("repo-local `pr-review-feedback-loop` skill", developmentDocs);
            Assert.Contains("Plane remains `In Review` while late human feedback fixes are applied", developmentDocs);
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
                "pr-review-feedback-loop",
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
                "pr-review-feedback-loop",
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
                "pr-review-feedback-loop",
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
