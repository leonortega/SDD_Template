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
            Assert.Contains("app/$PROD_ARTIFACT_COMMIT_SHA/deployable-apps.json", workflow);
            Assert.Contains("app/$PROD_ARTIFACT_COMMIT_SHA/$artifact_name", workflow);
            Assert.Contains("app/$PROD_ARTIFACT_COMMIT_SHA/$artifact_name.sha256", workflow);
        }

        [Fact]
        public void ProdDeploymentDoesNotRebuildArtifact()
        {
            string workflow = ReadWorkflow();
            string prodJob = GetSection(workflow, "  deploy-prod:");

            Assert.DoesNotContain("dotnet publish", prodJob);
            Assert.DoesNotContain("Upload artifact to Nexus", prodJob);
            Assert.DoesNotContain("app/${GITHUB_SHA}/site.zip", prodJob);
            Assert.DoesNotContain("app/${GITHUB_SHA}/api.zip", prodJob);
        }

        [Fact]
        public void ProdDeploymentChecksPageAndHealthEndpoint()
        {
            string workflow = ReadWorkflow();
            string prodJob = GetSection(workflow, "  deploy-prod:");

            Assert.Contains("Smoke check PROD", prodJob);
            Assert.Contains("<title>SDD Template</title>", prodJob);
            Assert.Contains("AZURE_PROD_${app_upper}_APP_URL", prodJob);
            Assert.Contains("${app_url}${health_path}", prodJob);
            Assert.Contains("'\"status\":\"ok\"'", prodJob);
        }

        [Fact]
        public void PushDeploymentsRequireTicketNamedCommitOrMergedPr()
        {
            string workflow = ReadWorkflow();

            Assert.Contains("ticketKeyPattern", workflow);
            Assert.Contains("BASH_REMATCH", workflow);
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
            Assert.Contains("--checksum \"$first_artifact_checksum\"", packageJob);
            Assert.Contains("--artifact-url \"$artifact_url\"", packageJob);
            Assert.Contains("--plane-ticket-key \"$plane_ticket_key\"", packageJob);
            Assert.Contains("--version-status unversioned", packageJob);
            Assert.Contains("ValidateReleaseManifest", packageJob);
            Assert.Contains("app/${GITHUB_SHA}/release.json", packageJob);
        }

        [Fact]
        public void TopologyManifestContainsSiteAndApiApps()
        {
            string root = FindRepositoryRoot().FullName;
            string manifest = File.ReadAllText(Path.Combine(root, "infra", "deployment", "apps.json"));
            using JsonDocument topology = JsonDocument.Parse(manifest);

            Assert.Contains("\"appId\": \"site\"", manifest);
            Assert.Contains("\"projectPath\": \"src/SDDTemplate.Site/SDDTemplate.Site.csproj\"", manifest);
            Assert.Contains("\"role\": \"web\"", manifest);
            Assert.Contains("\"artifactName\": \"site.zip\"", manifest);
            Assert.Contains("\"appId\": \"api\"", manifest);
            Assert.Contains("\"projectPath\": \"src/SDDTemplate.Api/SDDTemplate.Api.csproj\"", manifest);
            Assert.Contains("\"role\": \"api\"", manifest);
            Assert.Contains("\"artifactName\": \"api.zip\"", manifest);
            foreach (JsonElement app in topology.RootElement.GetProperty("apps").EnumerateArray())
            {
                string projectPath = app.GetProperty("projectPath").GetString() ?? string.Empty;
                Assert.StartsWith("src/", projectPath);
                Assert.DoesNotContain("tools/", projectPath);
                Assert.DoesNotContain(".codex/", projectPath);
                Assert.DoesNotContain("infra/", projectPath);
                Assert.DoesNotContain("openspec/", projectPath);
                Assert.DoesNotContain("tests/", projectPath);
            }
        }

        [Fact]
        public void AzureBicepUsesTopologyAndAppsettingsMappings()
        {
            string bicep = File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, "infra", "azure", "main.bicep"));

            Assert.Contains("param deployableApps array", bicep);
            Assert.Contains("resource apps 'Microsoft.Web/sites@2023-12-01' = [for app in deployableApps", bicep);
            Assert.Contains("resource appSettings 'Microsoft.Web/sites/config@2023-12-01'", bicep);
            Assert.Contains("Api__BaseUrl", bicep);
            Assert.Contains("Cors__AllowedOrigins__0", bicep);
            Assert.Contains("ConnectionStrings__ClientsDb", bicep);
            Assert.Contains("output apps array", bicep);
            Assert.Contains("output siteAppName", bicep);
            Assert.Contains("output apiAppName", bicep);
        }

        [Fact]
        public void PackageWorkflowPublishesUploadsAndDeploysPerAppArtifacts()
        {
            string workflow = ReadWorkflow();
            string normalizedWorkflow = NormalizeLineEndings(workflow);
            string packageJob = GetJobSection(workflow, "package");

            Assert.Contains("infra/deployment/apps.json", workflow);
            Assert.Contains("infra/deployment/configuration.json", workflow);
            Assert.Contains("BuildDeploymentConfig", workflow);
            Assert.Contains("jq -r '.apps[] | [.appId, .projectPath, .artifactName] | @tsv'", packageJob);
            Assert.Contains("projectPath must be under src/", packageJob);
            Assert.Contains("test -f \"$project_path\"", packageJob);
            Assert.Contains("dotnet publish \"$project_path\"", packageJob);
            Assert.Contains("artifacts/packages/$artifact_name", packageJob);
            Assert.Contains("deployable-apps.json", workflow);
            Assert.Contains("deployment-config.json", workflow);
            Assert.Contains("az webapp config appsettings set", workflow);
            Assert.Contains("az webapp config appsettings list", workflow);
            Assert.Contains("az webapp deploy", workflow);
            Assert.Contains("const apiBaseUrl", workflow);
            Assert.Contains("Access-Control-Allow-Origin", workflow);
            Assert.Contains("AZURE_DEV_${app_upper}_APP_NAME", workflow);
            Assert.Contains("AZURE_QA_${app_upper}_APP_NAME", workflow);
            Assert.Contains("AZURE_PROD_${app_upper}_APP_NAME", workflow);
            Assert.Contains("- name: Publish topology apps\n        shell: bash", normalizedWorkflow);
            Assert.Contains("- name: Upload topology artifacts to Nexus\n        shell: bash", normalizedWorkflow);
            Assert.Contains("- name: Apply and verify DEV deployment configuration\n        shell: bash", normalizedWorkflow);
            Assert.Contains("- name: Deploy DEV topology apps\n        shell: bash", normalizedWorkflow);
            Assert.Contains("- name: Smoke check DEV topology apps\n        shell: bash", normalizedWorkflow);
            Assert.Contains("- name: Apply and verify QA deployment configuration\n        shell: bash", normalizedWorkflow);
            Assert.Contains("- name: Deploy QA topology apps\n        shell: bash", normalizedWorkflow);
            Assert.Contains("- name: Smoke check QA topology apps\n        shell: bash", normalizedWorkflow);
            Assert.Contains("\n  e2e-qa:\n", normalizedWorkflow);
            Assert.DoesNotContain("\n  e2e-qa-branch:\n", normalizedWorkflow);
            Assert.Contains("- name: Apply and verify PROD deployment configuration\n        shell: bash", normalizedWorkflow);
            Assert.Contains("- name: Deploy PROD topology apps\n        shell: bash", normalizedWorkflow);
            Assert.Contains("- name: Smoke check PROD topology apps\n        shell: bash", normalizedWorkflow);
        }

        [Fact]
        public void PackageWorkflowUsesQaBranchE2eAsEvidenceGate()
        {
            string workflow = ReadWorkflow();
            string normalizedWorkflow = NormalizeLineEndings(workflow);
            string e2eJob = GetJobSection(workflow, "e2e-qa");

            Assert.DoesNotContain("\n  e2e-qa-branch:\n", normalizedWorkflow);
            Assert.Contains("startsWith(github.ref, 'refs/heads/qa/')", e2eJob);
            Assert.Contains("git merge-base HEAD origin/dev", e2eJob);
            Assert.Contains("tests/SDDTemplate.E2ETests", e2eJob);
            Assert.Contains("npm ci", e2eJob);
            Assert.DoesNotContain("npm run install:browsers", e2eJob);
            Assert.Contains("npm test || test_exit=$?", e2eJob);
            Assert.Contains("E2E_SITE_URL: ${{ secrets.AZURE_QA_SITE_APP_URL }}", e2eJob);
            Assert.Contains("E2E_API_URL: ${{ secrets.AZURE_QA_API_APP_URL }}", e2eJob);
            Assert.Contains("app/${E2E_ARTIFACT_COMMIT_SHA}/qa-e2e-evidence.zip", e2eJob);
            Assert.Contains("qa/${E2E_PLANE_TICKET_KEY}/${run_id}/qa-e2e-evidence.zip", e2eJob);
            Assert.Contains("exit \"$test_exit\"", e2eJob);
        }

        [Fact]
        public void PackageWorkflowRunsQaBranchE2eWithoutRedeploying()
        {
            string workflow = ReadWorkflow();
            string branchJob = GetJobSection(workflow, "e2e-qa");

            Assert.Contains("- qa/**", workflow);
            Assert.Contains("startsWith(github.ref, 'refs/heads/qa/')", branchJob);
            Assert.Contains("git fetch --depth 50 origin dev", branchJob);
            Assert.Contains("git merge-base HEAD origin/dev", branchJob);
            Assert.Contains("E2E_ARTIFACT_COMMIT_SHA", branchJob);
            Assert.Contains("E2E_PLANE_TICKET_KEY", branchJob);
            Assert.Contains("tests/SDDTemplate.E2ETests", branchJob);
            Assert.Contains("npm test || test_exit=$?", branchJob);
            Assert.Contains("app/${E2E_ARTIFACT_COMMIT_SHA}/qa-e2e-evidence.zip", branchJob);
            Assert.DoesNotContain("az webapp deploy", branchJob);
        }

        [Fact]
        public void PlaywrightQaE2eSuiteIsDeployedQaOnly()
        {
            string root = FindRepositoryRoot().FullName;
            string config = File.ReadAllText(Path.Combine(root, "tests", "SDDTemplate.E2ETests", "playwright.config.ts"));
            string package = File.ReadAllText(Path.Combine(root, "tests", "SDDTemplate.E2ETests", "package.json"));
            string spec = File.ReadAllText(Path.Combine(root, "tests", "SDDTemplate.E2ETests", "tests", "client-crud.spec.ts"));

            Assert.Contains("E2E_SITE_URL and E2E_API_URL are required", config);
            Assert.DoesNotContain("webServer", config);
            Assert.Contains("\"@playwright/test\"", package);
            Assert.Contains("Client CRUD deployed QA E2E", spec);
            Assert.Contains("/api/clients", spec);
            Assert.Contains("Born date cannot be in the future.", spec);
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
            Assert.Contains("Resolve PROD promotion inputs", prodJob);
            Assert.Contains("app/qa-approved/latest.json", prodJob);
            Assert.Contains("test \"$artifact_commit_sha\" = \"$GITHUB_SHA\"", prodJob);
            Assert.Contains("git fetch --depth 1 origin \"refs/tags/$source_rc_version:refs/tags/$source_rc_version\"", prodJob);
            Assert.Contains("PROD_ARTIFACT_COMMIT_SHA=$artifact_commit_sha", prodJob);
            Assert.DoesNotContain("parent_count", prodJob);
            Assert.DoesNotContain("candidates=()", prodJob);
            Assert.DoesNotContain("dotnet publish", prodJob);
            Assert.DoesNotContain("Upload artifact to Nexus", prodJob);
            Assert.DoesNotContain("deploy-dev", prodJob);
            Assert.DoesNotContain("deploy-qa", prodJob);
        }

        [Fact]
        public void ReleaseWorkflowUsesHumanReadableNexusPointerAliases()
        {
            string workflow = ReadWorkflow();
            string testE2eSkill = ReadSkill("test-e2e", "SKILL.md");
            string deployToProdSkill = ReadSkill("deploy-to-prod", "SKILL.md");
            string deploymentDoc = ReadDoc("deployment.md");

            Assert.Contains("app/qa-approved/latest.json", workflow);
            Assert.Contains("app/qa-approved/latest.json", testE2eSkill);
            Assert.Contains("app/rc/{sourceRcVersion}/artifact-pointer.json", testE2eSkill);
            Assert.Contains("app/releases/{finalReleaseVersion}/artifact-pointer.json", deployToProdSkill);
            Assert.Contains("metadata aliases", deploymentDoc);
            Assert.Contains("do not duplicate ZIP", deployToProdSkill);
        }

        [Fact]
        public void NonSrcAndNonTestsChangesDoNotDeployOnPush()
        {
            string workflow = ReadWorkflow();
            string classifyJob = GetJobSection(workflow, "classify-changes");

            Assert.Contains("app_changed=false", classifyJob);
            Assert.Contains("src/*|tests/*", classifyJob);
            Assert.DoesNotContain("infra/deployment/*", classifyJob);
            Assert.DoesNotContain("infra/azure/*", classifyJob);
            Assert.DoesNotContain(".codex/*", classifyJob);
            Assert.DoesNotContain(".gitea/*", classifyJob);
            Assert.DoesNotContain("*.sln", classifyJob);
            Assert.DoesNotContain("*.slnx", classifyJob);
            Assert.DoesNotContain("*.csproj", classifyJob);
            Assert.DoesNotContain("Directory.Build.props", classifyJob);
            Assert.DoesNotContain("Directory.Build.targets", classifyJob);
            Assert.DoesNotContain("global.json", classifyJob);
            Assert.Contains("deploy_allowed=false", classifyJob);
            Assert.Contains("ticketKeyPattern", classifyJob);
            Assert.Contains("BASH_REMATCH", classifyJob);
            Assert.DoesNotContain("dotnet run", classifyJob);
        }

        [Fact]
        public void PrValidationRunsOnlyForSrcAndTestsChanges()
        {
            string workflow = ReadPrValidationWorkflow();
            string configureTemplate = ReadConfigureScript();

            Assert.Contains("paths:", workflow);
            Assert.Contains("- src/**", workflow);
            Assert.Contains("- tests/**", workflow);
            Assert.Contains("paths:", configureTemplate);
            Assert.Contains("- src/**", configureTemplate);
            Assert.Contains("- tests/**", configureTemplate);
        }

        [Fact]
        public void PrValidationRunsApplicationTestsWithoutPowerShellInstall()
        {
            string workflow = ReadPrValidationWorkflow();
            string workflowReadme = File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, ".gitea", "workflows", "README.md"));
            string configureTemplate = ReadConfigureScript();

            Assert.DoesNotContain("Install PowerShell", workflow);
            Assert.DoesNotContain("apt-get install -y --no-install-recommends powershell", workflow);
            Assert.Contains("quality_projects=(", workflow);
            Assert.Contains("src/SDDTemplate.Site/SDDTemplate.Site.csproj", workflow);
            Assert.Contains("src/SDDTemplate.Api/SDDTemplate.Api.csproj", workflow);
            Assert.Contains("dotnet test tests/SDDTemplate.Site.Tests/SDDTemplate.Site.Tests.csproj", workflow);
            Assert.Contains("dotnet restore \"$project\"", workflow);
            Assert.Contains("dotnet format \"$project\" --verify-no-changes --no-restore", workflow);
            Assert.Contains("dotnet build \"$project\" -c Release --no-restore", workflow);
            Assert.Contains("dotnet list \"$project\" package --vulnerable --include-transitive", workflow);
            Assert.DoesNotContain("run: dotnet restore", workflow);
            Assert.DoesNotContain("run: dotnet format --verify-no-changes --no-restore", workflow);
            Assert.DoesNotContain("run: dotnet build -c Release --no-restore", workflow);
            Assert.DoesNotContain("dotnet test -c Release --no-build", workflow);
            Assert.DoesNotContain("dotnet test tools/", workflow);
            Assert.DoesNotContain("dotnet build \"tools/", workflow);
            Assert.DoesNotContain("dotnet restore \"tools/", workflow);

            Assert.DoesNotContain("Install PowerShell", configureTemplate);
            Assert.DoesNotContain("apt-get install -y --no-install-recommends powershell", configureTemplate);
            Assert.Contains("dotnet test tests/SDDTemplate.Site.Tests/SDDTemplate.Site.Tests.csproj", configureTemplate);
            Assert.Contains("dotnet restore \"$project\"", configureTemplate);
            Assert.Contains("dotnet format \"$project\" --verify-no-changes --no-restore", configureTemplate);
            Assert.Contains("dotnet build \"$project\" -c Release --no-restore", configureTemplate);
            Assert.Contains("dotnet list \"$project\" package --vulnerable --include-transitive", configureTemplate);
            Assert.Contains("PR validation must target product/application projects specifically", workflowReadme);
            Assert.Contains("OpenSpec, infrastructure, and meta-tests remain local/template-maintenance checks", workflowReadme);
            Assert.Contains("PR validation must target product/application projects specifically", configureTemplate);
            Assert.Contains("rejects deployable project paths outside `src/`", configureTemplate);
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
            Assert.Contains("AZURE_DEV_SITE_APP_NAME", readmeAudit);
            Assert.Contains("AZURE_DEV_SITE_APP_URL", readmeAudit);
            Assert.Contains("AZURE_DEV_API_APP_NAME", readmeAudit);
            Assert.Contains("AZURE_DEV_API_APP_URL", readmeAudit);
            Assert.Contains("AZURE_QA_RESOURCE_GROUP", readmeAudit);
            Assert.Contains("AZURE_QA_SITE_APP_NAME", readmeAudit);
            Assert.Contains("AZURE_QA_SITE_APP_URL", readmeAudit);
            Assert.Contains("AZURE_QA_API_APP_NAME", readmeAudit);
            Assert.Contains("AZURE_QA_API_APP_URL", readmeAudit);
            Assert.Contains("AZURE_PROD_RESOURCE_GROUP", readmeAudit);
            Assert.Contains("AZURE_PROD_SITE_APP_NAME", readmeAudit);
            Assert.Contains("AZURE_PROD_SITE_APP_URL", readmeAudit);
            Assert.Contains("AZURE_PROD_API_APP_NAME", readmeAudit);
            Assert.Contains("AZURE_PROD_API_APP_URL", readmeAudit);
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
            Assert.Contains("\"AZURE_PROD_SITE_APP_NAME\"", liveSecretAudit);
            Assert.Contains("\"AZURE_PROD_SITE_APP_URL\"", liveSecretAudit);
            Assert.Contains("\"AZURE_PROD_API_APP_NAME\"", liveSecretAudit);
            Assert.Contains("\"AZURE_PROD_API_APP_URL\"", liveSecretAudit);
        }

        [Fact]
        public void ConfigureTemplateUploadsBaselineReleaseManifest()
        {
            string script = ReadConfigureScript();

            Assert.Contains("CreateReleaseManifest", script);
            Assert.Contains("BuildDeploymentConfig", script);
            Assert.Contains("--plane-ticket-key \"$plane_ticket_key\"", script);
            Assert.Contains("--version-status unversioned", script);
            Assert.Contains("ValidateReleaseManifest", script);
            Assert.Contains("deployment-config.json", script);
            Assert.Contains("const apiBaseUrl", script);
            Assert.Contains("Access-Control-Allow-Origin", script);
            Assert.Contains("app/${GITHUB_SHA}/release.json", script);
            Assert.Contains("app/qa-approved/latest.json", script);
            Assert.Contains("test \"$artifact_commit_sha\" = \"$GITHUB_SHA\"", script);
            Assert.Contains("Package/deploy workflow should upload a baseline Nexus release manifest next to the artifact.", script);
        }

        [Fact]
        public void ConfigureTemplateAndDocsPreserveGiteaQaE2eEvidenceGate()
        {
            string script = ReadConfigureScript();
            string deploymentDoc = ReadDoc("deployment.md");
            string developmentDoc = ReadDoc("development.md");
            string workflowReadme = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".gitea",
                "workflows",
                "README.md"));
            string e2eSkill = ReadSkill("test-e2e", "SKILL.md");

            Assert.Contains("  e2e-qa:", script);
            Assert.DoesNotContain("\n  e2e-qa-branch:\n", NormalizeLineEndings(script));
            Assert.Contains("qa-e2e-evidence.zip", script);
            Assert.Contains("E2E_SITE_URL", script);
            Assert.Contains("E2E_API_URL", script);
            Assert.Contains("push a `qa/{ticketKey}` branch from current `dev`", deploymentDoc);
            Assert.Contains("rendered web API-base-url verification", deploymentDoc);
            Assert.Contains("API CORS preflight verification", deploymentDoc);
            Assert.Contains("tests/SDDTemplate.E2ETests", developmentDoc);
            Assert.Contains("deployed-QA regression suite", e2eSkill);
            Assert.Contains("qa/{ticketKey}", e2eSkill);
            Assert.Contains("app/{commitSha}/qa-e2e-evidence.zip", e2eSkill);
            Assert.Contains("acceptance-to-assertion QA proof", script);
            Assert.Contains("acceptance criteria proven by executable assertions", developmentDoc);
            Assert.Contains("Only full `PASS` can move Plane to Done", workflowReadme);
        }

        [Fact]
        public void E2EQaEvidenceContractIsGeneralAndBlocksWeakEvidence()
        {
            string contract = ReadSkill("_shared", "delivery-contract.md");
            string e2eSkill = ReadSkill("test-e2e", "SKILL.md");
            string deploymentDoc = ReadDoc("deployment.md");
            string qualityGates = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                "configure-dev-environment",
                "references",
                "quality-gates.md"));

            Assert.Contains("QA Evidence Contract", contract);
            Assert.Contains("QA Done = acceptance criteria proven by executable assertions against the deployed QA artifact", contract);
            Assert.Contains("Navigation/rendering", contract);
            Assert.Contains("API/backend effect", contract);
            Assert.Contains("State verification", contract);
            Assert.Contains("Validation and boundaries", contract);
            Assert.Contains("Environment correctness", contract);
            Assert.Contains("Evidence integrity", contract);
            Assert.Contains("Only `PASS` can move Plane to Done", contract);

            Assert.Contains("acceptance-to-assertion map", e2eSkill);
            Assert.Contains("scenario categories used", e2eSkill);
            Assert.Contains("executable assertions executed", e2eSkill);
            Assert.Contains("Screenshot-only, trace-only, log-only, page-load-only, or smoke-only evidence", e2eSkill);
            Assert.Contains("Data-changing ticket without independent state/API verification", e2eSkill);
            Assert.Contains("Validation-changing ticket without relevant invalid or boundary cases", e2eSkill);
            Assert.Contains("Wrong artifact, wrong QA URL, localhost, stale DEV endpoint", e2eSkill);
            Assert.Contains("Only `PASS` can move Plane to `plane.doneState`", e2eSkill);

            Assert.Contains("PASS WITH GAPS", deploymentDoc);
            Assert.Contains("PASS WITH GAPS", qualityGates);
        }

        [Fact]
        public void PlaywrightQaEvidenceHelpersEnforceDeployedTargetsAndBrowserEvidenceIntegrity()
        {
            string root = FindRepositoryRoot().FullName;
            string helper = File.ReadAllText(Path.Combine(root, "tests", "SDDTemplate.E2ETests", "support", "qa-evidence.ts"));
            string spec = File.ReadAllText(Path.Combine(root, "tests", "SDDTemplate.E2ETests", "tests", "client-crud.spec.ts"));

            Assert.Contains("qaScenarioCategories", helper);
            Assert.Contains("navigation-rendering", helper);
            Assert.Contains("api-backend-effect", helper);
            Assert.Contains("validation-boundaries", helper);
            Assert.Contains("environment-correctness", helper);
            Assert.Contains("evidence-integrity", helper);
            Assert.Contains("assertDeployedQaTarget", helper);
            Assert.Contains("assertSeparateServiceTargets", helper);
            Assert.Contains("createQaEvidenceRecorder", helper);
            Assert.Contains("localhost", helper);
            Assert.Contains("DEV", helper);
            Assert.Contains("unexpected browser console errors", helper);
            Assert.Contains("unexpected non-success browser API responses", helper);

            Assert.Contains("assertDeployedQaTarget", spec);
            Assert.Contains("assertSeparateServiceTargets", spec);
            Assert.Contains("createQaEvidenceRecorder", spec);
        }

        [Fact]
        public void ConfigureAzureSkillOwnsDeploymentTopologyReview()
        {
            string skill = ReadSkill("configure-azure-environments", "SKILL.md");
            string azureReference = ReadSkill("configure-dev-environment", Path.Combine("references", "azure.md"));
            string implementation = ReadSkill("implement-ticket", "SKILL.md");
            string feedbackLoop = ReadSkill("pr-review-feedback-loop", "SKILL.md");

            Assert.Contains("Deployment Topology Review", skill);
            Assert.Contains("infra/deployment/apps.json", skill);
            Assert.Contains("infra/deployment/configuration.json", skill);
            Assert.Contains("deployment-config.json", skill);
            Assert.Contains("Microsoft.NET.Sdk.Web", skill);
            Assert.Contains("Api:BaseUrl", skill);
            Assert.Contains("Api__BaseUrl", skill);
            Assert.Contains("Cors__AllowedOrigins__0", skill);
            Assert.Contains("ConnectionStrings__ClientsDb", skill);
            Assert.Contains("fail closed", skill);
            Assert.Contains("rendered clients page contains the expected API base URL", ReadSkill("_shared", "delivery-contract.md"));
            Assert.Contains("CORS preflight allows the matching web origin", ReadSkill("_shared", "delivery-contract.md"));
            Assert.Contains("deployment-config.json", azureReference);
            Assert.Contains("Deployment Topology Review", azureReference);
            Assert.Contains("explicit App Service appsettings resources", azureReference);
            Assert.Contains("Deployment topology: updated/verified/no deployable app changes", implementation);
            Assert.Contains("Deployment Topology Review", feedbackLoop);
        }

        [Fact]
        public void ConfigureAuditRequiresDeliveryContextLockGitignoreEntry()
        {
            string script = ReadConfigureScript();
            string attributes = File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, ".gitattributes"));

            Assert.Contains(".codex/delivery-context.local.json", script);
            Assert.Contains("Local ticket context lock must be ignored", script);
            Assert.Contains(".codex/parallel-delivery.local.json", script);
            Assert.Contains("Parallel delivery runtime state must be ignored", script);
            Assert.Contains(".gitattributes", script);
            Assert.Contains("text=auto eol=lf", script);
            Assert.Contains("Windows core.autocrlf checkouts can break dotnet format", script);
            Assert.Contains("* text=auto eol=lf", attributes);
            Assert.Contains("*.zip binary", attributes);
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
            Assert.Contains("post-prod-retrospective-learning-evidence", caseIds);
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
        public void WorkflowTimingCommentsAreContractedForDeliveryStagesAndE2EQa()
        {
            string contract = ReadSkill("_shared", "delivery-contract.md");
            string automatic = ReadSkill("automatic-implement-ticket", "SKILL.md");
            string starter = ReadSkill("plane-start-ticket", "SKILL.md");
            string implementation = ReadSkill("implement-ticket", "SKILL.md");
            string feedbackLoop = ReadSkill("pr-review-feedback-loop", "SKILL.md");
            string reviewAgent = ReadSkill("gitea-pr-review-agent", "SKILL.md");
            string postMergeDeploy = ReadSkill("post-merge-deploy", "SKILL.md");
            string deployToQa = ReadSkill("deploy-to-qa", "SKILL.md");
            string testE2E = ReadSkill("test-e2e", "SKILL.md");
            string contextDocs = ReadDoc("context-management.md");
            string deploymentDocs = ReadDoc("deployment.md");
            string script = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                "_shared",
                "scripts",
                "delivery_tools.ps1"));

            Assert.Contains("IA generated workflow timing: {ticketKey}", contract);
            Assert.Contains("RenderPlaneComment -Type WorkflowTiming", contract);
            Assert.Contains("comment_html", contract);
            Assert.Contains("comment_stripped", contract);
            Assert.Contains("InitializeWorkflowTelemetry", contract);
            Assert.Contains("AppendWorkflowTelemetry", contract);
            Assert.Contains("ReadWorkflowTelemetry", contract);
            Assert.Contains("Each non-OpenSpec delivery stage must capture UTC start and finish times and append one row", contract);
            Assert.Contains("test-e2e` must read rows for the active ticket with `ReadWorkflowTelemetry`", contract);
            Assert.Contains("Do not derive workflow timing from Plane generated marker timestamps", contract);
            Assert.Contains("update or reuse the existing workflow timing marker comment", contract);

            Assert.Contains("InitializeWorkflowTelemetry", starter);
            Assert.Contains("workflowStage=plane-start-ticket", starter);
            Assert.Contains("AppendWorkflowTelemetry", starter);
            Assert.Contains("Do not initialize telemetry when only listing Todo tickets", starter);
            Assert.Contains("workflowStage=implement-ticket", implementation);
            Assert.Contains("AppendWorkflowTelemetry", implementation);
            Assert.Contains("workflowStage=pr-review-feedback-loop", feedbackLoop);
            Assert.Contains("AppendWorkflowTelemetry", feedbackLoop);
            Assert.Contains("workflowStage=gitea-pr-review-agent", reviewAgent);
            Assert.Contains("AppendWorkflowTelemetry", reviewAgent);
            Assert.Contains("workflowStage=post-merge-deploy", postMergeDeploy);
            Assert.Contains("AppendWorkflowTelemetry", postMergeDeploy);
            Assert.Contains("workflowStage=deploy-to-qa", deployToQa);
            Assert.Contains("AppendWorkflowTelemetry", deployToQa);
            Assert.Contains("workflowStage=test-e2e", testE2E);
            Assert.Contains("AppendWorkflowTelemetry", testE2E);
            Assert.Contains("ReadWorkflowTelemetry", testE2E);
            Assert.Contains("RenderPlaneComment -Type WorkflowTiming", testE2E);
            Assert.Contains("patch that comment instead of creating a duplicate", testE2E);
            Assert.Contains("comment_html", testE2E);
            Assert.Contains("comment_stripped", testE2E);
            Assert.Contains(".codex/agent-telemetry.local.jsonl", automatic);
            Assert.Contains("Do not append telemetry for a delegated child stage", automatic);
            Assert.Contains("AppendWorkflowTelemetry", automatic);
            Assert.Contains("IA generated workflow timing: {ticketKey}", automatic);
            Assert.Contains("do not derive timing from Plane generated marker timestamps", automatic);
            Assert.Contains("workflow timing marker", automatic);

            Assert.Contains("Delivery stages maintain a concise generated Plane timing comment", contextDocs);
            Assert.Contains("E2E QA posts or patches the final timing comment", contextDocs);
            Assert.Contains("concise generated Plane timing comment", contextDocs);
            Assert.Contains("from that telemetry file", contextDocs);
            Assert.Contains("E2E QA posts or patches the workflow timing comment", deploymentDocs);
            Assert.Contains("PROD timing and PROD deployment comments remain part of the separate explicit PROD promotion step", deploymentDocs);
            Assert.DoesNotContain("retroactive marker-derived timing", contextDocs);
            Assert.Contains("'WorkflowTiming'", script);
            Assert.Contains("'InitializeWorkflowTelemetry'", script);
            Assert.Contains("'AppendWorkflowTelemetry'", script);
            Assert.Contains("'ReadWorkflowTelemetry'", script);
            Assert.Contains("| Stage | Outcome | Duration | Started UTC | Finished UTC |", script);
        }

        [Fact]
        public void PlaneStartTicketSetsEstimatePointOnlyWhenMissing()
        {
            string starter = ReadSkill("plane-start-ticket", "SKILL.md");
            string planeApi = ReadSkill("plane-start-ticket", Path.Combine("references", "plane-api.md"));

            Assert.Contains("If the fetched Plane ticket has empty or null `point`", starter);
            Assert.Contains("preserve it exactly and do not overwrite a human estimate", starter);
            Assert.Contains("## Estimate Points", starter);
            Assert.Contains("`0`: explicitly no-op, research-only, or investigation ticket", starter);
            Assert.Contains("`7`: large or high-risk work requiring broad coordination", starter);
            Assert.Contains("Patch the work item with only the resolved `point` value", starter);
            Assert.Contains("accepted mutable field for this workflow is `point`", starter);

            Assert.Contains("\"point\": 3", planeApi);
            Assert.Contains("Only send this patch when the fetched work item has null or empty `point` and `estimate_point`", planeApi);
            Assert.Contains("Preserve any non-empty `point` or `estimate_point` value", planeApi);
        }

        [Fact]
        public void DeployToProdRequiresPostProdRetrospectiveLearningEvidence()
        {
            string root = FindRepositoryRoot().FullName;
            string deployToProd = ReadSkill("deploy-to-prod", "SKILL.md");
            string retrospective = ReadSkill("delivery-retrospective-audit", "SKILL.md");
            string gitignore = File.ReadAllText(Path.Combine(root, ".gitignore"));
            string contract = ReadSkill("_shared", "delivery-contract.md");
            string developmentDocs = ReadDoc("development.md");
            string deploymentDocs = ReadDoc("deployment.md");
            string qualityGates = File.ReadAllText(Path.Combine(
                root,
                ".codex",
                "skills",
                "configure-dev-environment",
                "references",
                "quality-gates.md"));

            Assert.Contains("## Post-PROD Retrospective", deployToProd);
            Assert.Contains("post-prod-ticket-release", deployToProd);
            Assert.Contains("IA generated post-PROD retrospective: {finalVersion}", deployToProd);
            Assert.Contains(".codex/agent-evals/results.local.json", deployToProd);
            Assert.Contains("must not mutate Plane state", deployToProd);
            Assert.Contains("release handoff", deployToProd);

            Assert.Contains("post-prod-ticket-release", retrospective);
            Assert.Contains("### 6. Persist Post-PROD Learning Evidence", retrospective);
            Assert.Contains("appliedChanges: false", retrospective);
            Assert.Contains("IA generated post-PROD retrospective: {finalVersion}", retrospective);
            Assert.Contains("recommend a follow-up improvement ticket instead of creating it", retrospective);
            Assert.Contains(".codex/agent-evals/results.local.json", gitignore);
            Assert.Contains("Post-PROD retrospective: `IA generated post-PROD retrospective: {finalVersion}`", contract);
            Assert.Contains("post-prod-ticket-release", developmentDocs);
            Assert.Contains("post-PROD retrospective", deploymentDocs);
            Assert.Contains("post-PROD retrospective", qualityGates);
        }

        [Fact]
        public void ProdPromotionSupportsBatchReleaseAfterTicketsAreDone()
        {
            string contract = ReadSkill("_shared", "delivery-contract.md");
            string deploymentDocs = ReadDoc("deployment.md");
            string deployToProd = ReadSkill("deploy-to-prod", "SKILL.md");
            string retrospective = ReadSkill("delivery-retrospective-audit", "SKILL.md");
            string schema = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                "_shared",
                "release.schema.json"));
            string script = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                "_shared",
                "scripts",
                "delivery_tools.ps1"));

            Assert.Contains("QA accepted and eligible for a later explicit PROD release", contract);
            Assert.Contains("PROD promotion is explicit and release-centric", contract);
            Assert.Contains("A PROD release may include one or more Done tickets", contract);
            Assert.Contains("`includedTickets` is authoritative when present", contract);
            Assert.Contains("do not block only because the promoted commit includes multiple ticket keys", contract);
            Assert.Contains("record the same PROD release result on every included ticket", deployToProd);
            Assert.Contains("If `release.json.includedTickets` exists, treat it as the authoritative release membership list", deployToProd);
            Assert.Contains("Support single-ticket releases when includedTickets is absent", File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "agent-evals",
                "workflow-cases.json")));

            Assert.Contains("E2E QA `PASS` closes each ticket as Done", deploymentDocs);
            Assert.Contains("PROD is a later explicit release event that may include one or more Done tickets", deploymentDocs);
            Assert.Contains("comments the PROD result on every included ticket", deploymentDocs);
            Assert.Contains("just-promoted release", retrospective);
            Assert.Contains("\"includedTickets\"", schema);
            Assert.Contains("Included tickets", script);
        }

        [Fact]
        public void WorkflowEvalRequiresPostProdRetrospectiveLearningEvidence()
        {
            string root = FindRepositoryRoot().FullName;
            using JsonDocument cases = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, ".codex", "agent-evals", "workflow-cases.json")));
            JsonElement postProdCase = cases.RootElement.GetProperty("cases").EnumerateArray().Single(item =>
                string.Equals(item.GetProperty("id").GetString(), "post-prod-retrospective-learning-evidence", StringComparison.Ordinal));

            Assert.Equal("deploy-to-prod", postProdCase.GetProperty("stage").GetString());
            Assert.Equal("delivery-retrospective-audit", postProdCase.GetProperty("expectedRoute").GetString());

            string[] evidence = [.. postProdCase.GetProperty("requiredEvidence").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];
            string[] expectations = [.. postProdCase.GetProperty("toolExpectations").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];
            string[] stopConditions = [.. postProdCase.GetProperty("stopConditions").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];
            string[] unsafeMutations = [.. postProdCase.GetProperty("unsafeMutations").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];
            string[] handoffFields = [.. postProdCase.GetProperty("handoffFields").EnumerateArray().Select(item => item.GetString() ?? string.Empty)];

            Assert.Contains("successful PROD deployment marker", evidence);
            Assert.Contains("included ticket list", evidence);
            Assert.Contains(".codex/agent-evals/results.local.json ignored path", evidence);
            Assert.Contains("Invoke delivery-retrospective-audit in read-only post-prod-ticket-release mode", expectations);
            Assert.Contains("Add or reuse Plane marker IA generated post-PROD retrospective: {finalVersion}", expectations);
            Assert.Contains("PROD deployment has not succeeded", stopConditions);
            Assert.Contains("move Plane ticket state", unsafeMutations);
            Assert.Contains("apply docs, delivery contract, skill, eval, test, or memory changes automatically", unsafeMutations);
            Assert.Contains("includedTickets", handoffFields);
            Assert.Contains("localResultPath", handoffFields);
            Assert.Contains("planeRetrospectiveMarker", handoffFields);
            Assert.Contains("appliedChanges", handoffFields);
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
            Assert.Contains("SyncWorktreeLocalConfig", docs);
            Assert.Contains("EnsureDeliveryContext", docs);
            Assert.Contains(".codex/tool-recommendations.local.json", docs);
            Assert.Contains(".codex/azure-login.local.json", docs);
            Assert.Contains("after QA evidence is recorded and the Plane ticket is moved to Done", docs);
            Assert.Contains("git worktree remove <worktreePath>", docs);

            Assert.Contains("Before Git, Plane, or Gitea mutation", contract);
            Assert.Contains("ValidateParallelDeliveryDryRun", contract);
            Assert.Contains("one worktree", contract);
            Assert.Contains(".codex/tool-recommendations.local.json", contract);
            Assert.Contains(".codex/azure-login.local.json", contract);
            Assert.Contains("Never let two agents mutate the same Plane ticket", contract);
            Assert.Contains("Never parallelize DEV, QA, E2E QA, PROD, rollback, or hotfix promotion", contract);
            Assert.Contains("coordinator checkout owns ticket worktree teardown", contract);
            Assert.Contains("Child role agents must not delete their own assigned worktree", contract);

            Assert.Contains("Before any Git, Plane, or Gitea mutation", coordinator);
            Assert.Contains("Failed `ValidateParallelDeliveryDryRun`", coordinator);
            Assert.Contains("## Cleanup And Recovery", coordinator);
            Assert.Contains("required ignored local runtime files", coordinator);
            Assert.Contains("SyncWorktreeLocalConfig", coordinator);
            Assert.Contains("EnsureDeliveryContext", coordinator);
            Assert.Contains("git -C <worktreePath> status --porcelain", coordinator);
            Assert.Contains("git merge-base --is-ancestor <branch> <baseBranch>", coordinator);
            Assert.Contains("git worktree prune", coordinator);

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
            Assert.Contains("SyncWorktreeLocalConfig", configureRouter);
            Assert.Contains("EnsureDeliveryContext", configureRouter);
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
            Assert.Contains(".codex/tool-recommendations.local.json", File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, ".gitignore")));
            Assert.Contains("\"mode\": \"guided-manual\"", catalog);
            Assert.Contains("\"installMethod\": \"manual-copy\"", catalog);
            Assert.Contains("\"installMethod\": \"manual-config\"", catalog);
            Assert.Contains("\"installMethod\": \"manual-reference\"", catalog);
            Assert.Contains("\"sourceKind\": \"repo-local\"", catalog);
            Assert.Contains("\"sourceKind\": \"technology-owner\"", catalog);
            Assert.Contains("\"officialSources\"", catalog);
            Assert.Contains("\"searchQueries\"", catalog);
            Assert.DoesNotContain("installCommand", catalog);
        }

        [Fact]
        public void RecommendedToolsAuditDetectsCurrentStackAndAvoidsPlaneMcp()
        {
            string script = ReadConfigureScript();
            string discoveryScript = ReadSkill("project-guidance-discover", Path.Combine("scripts", "project_guidance_discovery.ps1"));
            string catalog = ReadToolRecommendationsCatalog();

            Assert.Contains("AuditRecommendedTools", script);
            Assert.Contains("DiscoverProjectGuidance", script);
            Assert.Contains("AcquireProjectGuidance", script);
            Assert.Contains("SetRecommendedTools", script);
            Assert.Contains("MapProjectGuidanceStep", script);
            Assert.Contains("tool-recommendations.local.json", script);
            Assert.Contains("usedInSteps", script);
            Assert.Contains("projectGuidanceDiscoveryScript", script);
            Assert.Contains("project-guidance-discover", script);
            Assert.Contains("project_guidance_discovery.ps1", script);
            Assert.Contains("function Invoke-DiscoverProjectGuidance", script);
            Assert.Contains("function Invoke-AcquireProjectGuidance", script);
            Assert.Contains("function Invoke-MapProjectGuidanceStep", script);
            Assert.Contains("function Get-DetectedStackTags", discoveryScript);
            Assert.Contains("function Get-ProjectGuidanceResearchTopics", discoveryScript);
            Assert.Contains("function Get-ProjectGuidanceDiscoveryReport", discoveryScript);
            Assert.Contains("project-guidance-search-plan", discoveryScript);
            Assert.Contains("guidance-search-plan", discoveryScript);
            Assert.Contains("research-then-manual-copy", discoveryScript);
            Assert.Contains("Get-ProjectGuidanceDiscoverySourcePriority", discoveryScript);
            Assert.Contains("\"repo-local\"", discoveryScript);
            Assert.Contains("\"skills-cli\"", discoveryScript);
            Assert.Contains("\"marketplace\"", discoveryScript);
            Assert.Contains("sourceKind", discoveryScript);
            Assert.Contains("\"dotnet\"", discoveryScript);
            Assert.Contains("\"dotnet-10\"", discoveryScript);
            Assert.Contains("\"aspnet-core\"", discoveryScript);
            Assert.Contains("\"blazor\"", discoveryScript);
            Assert.Contains("\"node\"", discoveryScript);
            Assert.Contains("\"typescript\"", discoveryScript);
            Assert.Contains("\"react\"", discoveryScript);
            Assert.Contains("\"python\"", discoveryScript);
            Assert.Contains("\"java\"", discoveryScript);
            Assert.Contains("\"docker\"", discoveryScript);
            Assert.Contains("\"terraform\"", discoveryScript);
            Assert.Contains("\"kubernetes\"", discoveryScript);
            Assert.Contains("\"xunit\"", discoveryScript);
            Assert.Contains("\"coverage\"", discoveryScript);
            Assert.Contains("\"plane\"", discoveryScript);
            Assert.Contains("\"gitea\"", discoveryScript);
            Assert.Contains("\"gitea-actions-runner\"", discoveryScript);
            Assert.Contains("\"nexus\"", discoveryScript);
            Assert.Contains("\"nexus-artifacts\"", discoveryScript);
            Assert.Contains("\"azure\"", discoveryScript);
            Assert.Contains("\"azure-app-service\"", discoveryScript);
            Assert.Contains("\"azure-monitor\"", discoveryScript);
            Assert.Contains("\"grafana\"", discoveryScript);
            Assert.Contains("\"e2e\"", discoveryScript);
            Assert.Contains("\"browser-e2e\"", discoveryScript);
            Assert.Contains("\"playwright-guidance\"", discoveryScript);
            Assert.Contains("\"clean-code\"", discoveryScript);
            Assert.Contains("\"architecture-guidance\"", discoveryScript);
            Assert.Contains("\"web-ui\"", discoveryScript);
            Assert.Contains("\"rest-api\"", discoveryScript);
            Assert.Contains("\"security\"", discoveryScript);
            Assert.Contains("Add-StackContextDriftFindings", discoveryScript);
            Assert.Contains("Add-DetectedSkillRecommendations", discoveryScript);
            Assert.Contains("openai-aspnet-core-skill", discoveryScript);
            Assert.Contains("dotnet-blazor-plan-ui-change-skill", discoveryScript);
            Assert.Contains("dotnet-webapi-skill", discoveryScript);
            Assert.Contains("openai-security-best-practices-skill", discoveryScript);
            Assert.Contains("openai-playwright-skill", discoveryScript);
            Assert.Contains("dotnet-assertion-quality-skill", discoveryScript);
            Assert.Contains("skill-gap", discoveryScript);
            Assert.Contains("official-first-internet-search", discoveryScript);
            Assert.Contains("requiresUserConfirmation", discoveryScript);
            Assert.Contains("github.com/openai/skills", discoveryScript);
            Assert.Contains("github.com/dotnet/skills", discoveryScript);
            Assert.Contains("skills.sh", discoveryScript);
            Assert.Contains("dotnet-10-platform-guidance", catalog);
            Assert.Contains("clean-code-practice-guidance", catalog);
            Assert.Contains("qa-automation-practice-guidance", catalog);
            Assert.Contains("security-review-standard-guidance", catalog);
            Assert.Contains("manual-copy", catalog);
            Assert.Contains("repo:.codex/skills/frontend-testing-debugging/SKILL.md", catalog);
            Assert.Contains("https://playwright.dev/docs/best-practices", catalog);
            Assert.Contains("Plane MCP is intentionally not recommended", catalog);
            Assert.Contains("repo-local skills must use the configured Plane API", catalog);
            Assert.DoesNotContain("openspec-delivery-skills", catalog);
            Assert.DoesNotContain("dotnet-quality-gates-skill", catalog);
            Assert.DoesNotContain("azure-environment-config-skill", catalog);
        }

        [Fact]
        public void ConfigureDocsDescribeManualSkillAcquisitionWorkflow()
        {
            string configureRouter = ReadSkill("configure-dev-environment", "SKILL.md");
            string readme = File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, "README.md"));

            Assert.Contains("AuditRecommendedTools", configureRouter);
            Assert.Contains("DiscoverProjectGuidance", configureRouter);
            Assert.Contains("AcquireProjectGuidance", configureRouter);
            Assert.Contains("SetRecommendedTools", configureRouter);
            Assert.Contains("project-guidance-discover", configureRouter);
            Assert.Contains("project-guidance-acquire", configureRouter);
            Assert.Contains("project-guidance-mapper", configureRouter);
            Assert.Contains("read the source `SKILL.md`", configureRouter);
            Assert.Contains("create `.codex/skills/{skill-name}/`", configureRouter);
            Assert.Contains("manual repo-based acquisition", configureRouter);
            Assert.Contains("Do not install skills by command", configureRouter);
            Assert.Contains("stack-context drift", configureRouter);
            Assert.Contains("scan-derived guidance findings", configureRouter);
            Assert.Contains("project-guidance-search-plan", configureRouter);
            Assert.Contains("detected project signals", configureRouter);
            Assert.Contains("additional desired skills or guidance", configureRouter);
            Assert.Contains("persistLocal=true", configureRouter);
            Assert.Contains("MapProjectGuidanceStep", configureRouter);
            Assert.Contains(".codex/tool-recommendations.local.json", configureRouter);
            Assert.Contains("asks whether the user wants to add additional desired items", File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, "docs", "development.md")));
            Assert.Contains("usedInSteps", File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, "docs", "development.md")));
            Assert.Contains("manual by default", readme);
            Assert.Contains("suggested missing skills", readme);
            Assert.Contains("stack, tooling, environments, test frameworks", readme);
            Assert.Contains("asks whether the operator wants to add additional desired skills or guidance", readme);
            Assert.Contains(".codex/tool-recommendations.local.json", readme);
            Assert.Contains("project-guidance-mapper` reads that local file", readme);
            Assert.Contains("read the source repository's `SKILL.md`", readme);
            Assert.Contains("Skills are not installed by command", readme);
            Assert.Contains(".codex/tool-recommendations.example.json", readme);
        }

        [Fact]
        public void ProjectGuidanceDiscoveryAcquisitionAndMapperSkillsAreDefined()
        {
            string discover = ReadSkill("project-guidance-discover", "SKILL.md");
            string acquire = ReadSkill("project-guidance-acquire", "SKILL.md");
            string mapper = ReadSkill("project-guidance-mapper", "SKILL.md");
            string discoveryScript = ReadSkill("project-guidance-discover", Path.Combine("scripts", "project_guidance_discovery.ps1"));

            Assert.Contains("name: project-guidance-discover", discover);
            Assert.Contains("suggested missing skills and guidance", discover);
            Assert.Contains("additional desired skills or guidance", discover);
            Assert.Contains("final confirmed list", discover);
            Assert.Contains("Do not copy anything from this skill", discover);
            Assert.Contains("function Get-ProjectGuidanceDiscoveryReport", discoveryScript);
            Assert.Contains("suggestedMissingSkills", discoveryScript);
            Assert.Contains("userAddedRequestedGuidance", discoveryScript);
            Assert.Contains("finalConfirmedGuidance", discoveryScript);
            Assert.Contains("persistLocal=true", discover);
            Assert.Contains(".codex/tool-recommendations.local.json", discover);
            Assert.Contains("usedInSteps", discover);

            Assert.Contains("name: project-guidance-acquire", acquire);
            Assert.Contains("final confirmed list from `project-guidance-discover`", acquire);
            Assert.Contains("Do not use command-based skill installers", acquire);
            Assert.Contains("Do not install into `$CODEX_HOME`", acquire);
            Assert.Contains("sourceKind", acquire);
            Assert.Contains("skills.sh", acquire);
            Assert.Contains("Test-Path", acquire);
            Assert.Contains("Do not copy secrets", acquire);
            Assert.Contains("Refresh `.codex/tool-recommendations.local.json`", acquire);

            Assert.Contains("name: project-guidance-mapper", mapper);
            Assert.Contains(".codex/tool-recommendations.local.json", mapper);
            Assert.Contains("MapProjectGuidanceStep", mapper);
            Assert.Contains("usedInSteps", mapper);
            Assert.Contains("Config infra", mapper);
            Assert.Contains("First ticket setup", mapper);
            Assert.Contains("Planning", mapper);
            Assert.Contains("Implementation", mapper);
            Assert.Contains("PR review", mapper);
            Assert.Contains("E2E QA", mapper);
            Assert.Contains("Rollback", mapper);
            Assert.Contains("Hotfix", mapper);
            Assert.Contains("missingUsefulGuidance", mapper);
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
            Assert.Contains("Azure Monitor", architecture);
            Assert.Contains("Grafana", architecture);
            Assert.Contains("Skills are not installed by command", architecture);
            Assert.Contains("project-guidance-discover", architecture);
            Assert.Contains("project-guidance-acquire", architecture);
            Assert.Contains("project-guidance-mapper", architecture);

            Assert.Contains("## Technology Stack And Tool Set", development);
            Assert.Contains(".NET 10", development);
            Assert.Contains("ASP.NET Core", development);
            Assert.Contains("Blazor", development);
            Assert.Contains("xUnit", development);
            Assert.Contains("coverlet", development);
            Assert.Contains("official-first research", development);
            Assert.Contains("Browser plugin and Playwright-style", development);
            Assert.Contains("project-guidance-discover", development);
            Assert.Contains("project-guidance-acquire", development);
            Assert.Contains("project-guidance-mapper", development);

            Assert.Contains("## Technology Stack And Tool Set", deployment);
            Assert.Contains("Azure App Service", deployment);
            Assert.Contains("Azure Monitor", deployment);
            Assert.Contains("Grafana", deployment);
            Assert.Contains("qa/{ticketKey}/{runId}/qa-evidence.zip", deployment);
            Assert.Contains("project-guidance-mapper", deployment);

            Assert.Contains("context: |", openSpecConfig);
            Assert.Contains("Delivery tool set:", openSpecConfig);
            Assert.Contains("Application stack: .NET 10, ASP.NET Core, Blazor", openSpecConfig);
            Assert.Contains("Recommended skills are copied manually", openSpecConfig);
            Assert.Contains("project-guidance-discover", openSpecConfig);
            Assert.Contains("project-guidance-acquire", openSpecConfig);
            Assert.Contains("project-guidance-mapper", openSpecConfig);
            Assert.Contains("usedInSteps", openSpecConfig);
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
            string apiHelpers = ReadSkill("_shared", "api-helpers.md");

            Assert.Contains("PR Review Feedback", contract);
            Assert.Contains("top-level PR comments and inline code review comments", contract);
            Assert.Contains("IA generated PR feedback detected: {headSha}:{feedbackBatchId}", contract);
            Assert.Contains("IA generated PR feedback fixes: {headSha}:{feedbackBatchId}", contract);
            Assert.Contains("as the first line by itself", contract);
            Assert.Contains("reviewer-facing Markdown summary", contract);
            Assert.Contains("**Reviewer feedback addressed:**", contract);
            Assert.Contains("**How IA resolved it:**", contract);
            Assert.Contains("**Reviewer readiness:**", contract);
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
            Assert.Contains("Keep the marker as the first line by itself", feedbackLoop);
            Assert.Contains("**Reviewer feedback addressed:**", feedbackLoop);
            Assert.Contains("**How IA resolved it:**", feedbackLoop);
            Assert.Contains("**Changed:**", feedbackLoop);
            Assert.Contains("**Validation:**", feedbackLoop);
            Assert.Contains("**Reviewer readiness:**", feedbackLoop);
            Assert.Contains("comment_html", feedbackLoop);
            Assert.Contains("comment_stripped", feedbackLoop);
            Assert.Contains("verify `comment_stripped` starts with the marker", feedbackLoop);
            Assert.Contains("Keep Plane in `In Review`", implementation);

            Assert.Contains("comment_html", contract);
            Assert.Contains("comment_stripped", contract);
            Assert.Contains("Do not send a Gitea-style `comment` or `body` field", apiHelpers);
            Assert.Contains("verify `comment_stripped` starts with the stable marker", apiHelpers);

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
            Assert.Contains("Feedback-fix Plane comments are reviewer-facing summaries", developmentDocs);
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
        public void RepositoryWorkRequiresDurableLearningCaptureGate()
        {
            string contract = ReadSkill("_shared", "delivery-contract.md");
            string skillStartup = ReadSkill("_shared", "skill-startup.md");
            string e2eSkill = ReadSkill("test-e2e", "SKILL.md");
            string agents = File.ReadAllText(Path.Combine(FindRepositoryRoot().FullName, "AGENTS.md"));
            string memoryPolicy = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "memory",
                "retrieval-policy.md"));

            Assert.Contains("## Durable Learning Capture Gate", contract);
            Assert.Contains("Before final handoff for any non-trivial repository work", contract);
            Assert.Contains("any prompt where an error, issue, blocker, or fix was diagnosed", contract);
            Assert.Contains("Memory updated: <files>", contract);
            Assert.Contains("Memory updated: none", contract);
            Assert.Contains("Do not treat Plane comments, PR comments, QA evidence, logs, or chat summaries as a substitute", contract);

            Assert.Contains("## Durable Learning Capture", skillStartup);
            Assert.Contains("This is not limited to QA or ticket delivery", skillStartup);
            Assert.Contains("Memory updated: <files>` or `Memory updated: none", skillStartup);

            Assert.Contains("Before final handoff for any non-trivial repo work", agents);
            Assert.Contains("any error, issue, blocker, fix, configuration repair, local tooling correction, or debugging result", agents);

            Assert.Contains("### 10. Durable Learning Capture Gate", e2eSkill);
            Assert.Contains(".codex/memory/retrieval-policy.md#update-process", e2eSkill);
            Assert.Contains("Plane comments, QA evidence, and final chat summaries do not satisfy this gate by themselves", e2eSkill);
            Assert.Contains("Memory updated: <files>` or `Memory updated: none", e2eSkill);

            Assert.Contains("## Update Process", memoryPolicy);
            Assert.Contains("Reusable but non-authoritative workflow knowledge belongs in `.codex/memory/`", memoryPolicy);
        }

        [Fact]
        public void MemorySearchHelperSupportsSymptomDrivenLookup()
        {
            string root = FindRepositoryRoot().FullName;
            string searchScriptPath = Path.Combine(root, ".codex", "memory", "search_memory.ps1");
            string searchScript = File.ReadAllText(searchScriptPath);
            string retrievalPolicy = File.ReadAllText(Path.Combine(root, ".codex", "memory", "retrieval-policy.md"));
            string memorySummary = File.ReadAllText(Path.Combine(root, ".codex", "memory", "memory_summary.md"));
            string skillStartup = ReadSkill("_shared", "skill-startup.md");
            string agents = File.ReadAllText(Path.Combine(root, "AGENTS.md"));
            string contextDocs = ReadDoc("context-management.md");

            Assert.Contains("param(", searchScript);
            Assert.Contains("-ListTopics", retrievalPolicy);
            Assert.Contains("search_memory.ps1 -Query <symptom>", memorySummary);
            Assert.Contains(".codex/memory/search_memory.ps1", skillStartup);
            Assert.Contains("search_memory.ps1 -Query <symptom>", agents);
            Assert.Contains("search_memory.ps1 -Query <symptom>", contextDocs);

            using System.Diagnostics.Process process = new()
            {
                StartInfo = new System.Diagnostics.ProcessStartInfo
                {
                    FileName = "pwsh",
                    ArgumentList =
                    {
                        "-NoProfile",
                        "-File",
                        searchScriptPath,
                        "-Query",
                        "Api__BaseUrl",
                        "-AsJson",
                        "-Root",
                        root
                    },
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false
                }
            };

            Assert.True(process.Start());
            string output = process.StandardOutput.ReadToEnd();
            string error = process.StandardError.ReadToEnd();
            bool exited = process.WaitForExit(30_000);

            Assert.True(exited, "Memory search helper did not exit within the timeout.");
            Assert.Equal(0, process.ExitCode);
            Assert.Contains("Api__BaseUrl", output);
            Assert.DoesNotContain("password", output, StringComparison.OrdinalIgnoreCase);
            Assert.DoesNotContain("token", output, StringComparison.OrdinalIgnoreCase);
            Assert.True(string.IsNullOrWhiteSpace(error), error);
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
                "WorkflowTiming",
                "UpdateReleaseManifest",
                "CreateArtifactPointer"
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
            Assert.Contains("function New-ArtifactPointer", script);
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
                    "CreateArtifactPointer",
                    "RenderPlaneComment -Type E2EQA"
                ],
                ["deploy-to-prod"] =
                [
                    "ValidateTicketLock",
                    "ValidateDeploymentLane",
                    "UpdateReleaseManifest",
                    "CreateArtifactPointer",
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
        public void TicketStartCanLazilyReplaceCompletedDeliveryContextLock()
        {
            string contract = ReadSkill("_shared", "delivery-contract.md");
            string startSkill = ReadSkill("plane-start-ticket", "SKILL.md");
            string configureRouter = ReadSkill("configure-dev-environment", "SKILL.md");
            string architecture = ReadDoc("architecture.md");
            string parallelDocs = ReadDoc("parallel-delivery.md");

            Assert.Contains("Do not delete the lock merely because E2E QA moved a ticket to `Done`", contract);
            Assert.Contains("fetch the locked ticket from Plane", contract);
            Assert.Contains("If the locked ticket is `Done`, replace the lock", contract);
            Assert.Contains("active, missing, ambiguous, or cannot be verified", contract);
            Assert.Contains("lazy cleanup on next ticket start", contract);

            Assert.Contains("fetch the locked ticket through the Plane API", startSkill);
            Assert.Contains("configured `plane.doneState` or default `Done`", startSkill);
            Assert.Contains("replaceExisting=true", startSkill);
            Assert.Contains("Do not delete the lock merely because the old ticket is QA Done or ready for PROD", startSkill);

            Assert.Contains("Use `replaceExisting=true` only after `plane-start-ticket` confirms", configureRouter);
            Assert.Contains("QA Done does not require immediate lock deletion", configureRouter);
            Assert.Contains("retained after QA Done", architecture);
            Assert.Contains("Do not copy `.codex/delivery-context.local.json`", parallelDocs);
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

        [Fact]
        public void TicketHandoffRequiresVerifiedHumanReviewers()
        {
            string contract = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                "_shared",
                "delivery-contract.md"));
            string implementSkill = ReadSkill("implement-ticket", "SKILL.md");
            string openspecSkill = ReadSkill("openspec-implement-change", "SKILL.md");
            string handoffReference = ReadSkill("openspec-implement-change", Path.Combine("references", "gitea-plane-handoff.md"));
            string configureReference = ReadSkill("configure-dev-environment", Path.Combine("references", "gitea-pr.md"));

            Assert.Contains("PR Reviewer Handoff", contract);
            Assert.Contains("requested-reviewers endpoint", contract);
            Assert.Contains("both a JSON array and a single collaborator object", contract);
            Assert.Contains("login` first, then `username", contract);
            Assert.Contains("not treat the Codex review-agent comment", contract);
            Assert.Contains("requested_reviewers", implementSkill);
            Assert.Contains("Gitea may return either an array or a single object", implementSkill);
            Assert.Contains("Do not move the Plane ticket to review until human reviewers are requested and verified", implementSkill);
            Assert.Contains("requested_reviewers", openspecSkill);
            Assert.Contains("normalize the response to a candidate list", openspecSkill);
            Assert.Contains("Re-fetch the PR and confirm the requested reviewers are present", openspecSkill);
            Assert.Contains("POST {gitea.baseUrl}/api/v1/repos/{owner}/{repo}/pulls/{prNumber}/requested_reviewers", handoffReference);
            Assert.Contains("single collaborator object", handoffReference);
            Assert.Contains("Ticket handoff remains responsible for proving reviewers were actually requested", configureReference);
            Assert.Contains("single collaborator object", configureReference);
        }

        [Fact]
        public void E2EQaDeletesTemporaryTriggerBranchAfterDurableEvidence()
        {
            string contract = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                "_shared",
                "delivery-contract.md"));
            string e2eSkill = ReadSkill("test-e2e", "SKILL.md");
            string deploymentDoc = ReadDoc("deployment.md");
            string developmentDoc = ReadDoc("development.md");
            string workflowReadme = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".gitea",
                "workflows",
                "README.md"));
            string configureScript = ReadConfigureScript();

            Assert.Contains("QA Evidence Trigger Branch Cleanup", contract);
            Assert.Contains("delete the remote `qa/{ticketKey}` branch from Gitea", contract);
            Assert.Contains("Durable QA evidence belongs in Nexus, Plane comments, release manifests, and tags", contract);
            Assert.Contains("git push origin --delete qa/E2EPROJECT-123", e2eSkill);
            Assert.Contains("Do not delete the branch before Nexus evidence exists", e2eSkill);
            Assert.Contains("delete the remote `qa/{ticketKey}` branch from Gitea", deploymentDoc);
            Assert.Contains("delete the remote `qa/{ticketKey}` branch", developmentDoc);
            Assert.Contains("deleting the remote `qa/{ticketKey}` branch after durable Nexus/Plane/release/tag evidence exists", workflowReadme);
            Assert.Contains("deleting the remote `qa/{ticketKey}` branch after durable Nexus/Plane/release/tag evidence exists", configureScript);
        }

        [Fact]
        public void E2EQaRequiresLinkedOpenSpecArchiveBeforeCompleteHandoff()
        {
            string contract = File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".codex",
                "skills",
                "_shared",
                "delivery-contract.md"));
            string e2eSkill = ReadSkill("test-e2e", "SKILL.md");
            string root = FindRepositoryRoot().FullName;
            string activeChange = Path.Combine(
                root,
                "openspec",
                "changes",
                "feat-e2eproject-2-add-a-crud-view-por-a-client");
            string archivedChange = Path.Combine(
                root,
                "openspec",
                "changes",
                "archive",
                "2026-06-05-feat-e2eproject-2-add-a-crud-view-por-a-client");

            Assert.Contains("OpenSpec Completion Archive Gate", contract);
            Assert.Contains("must be archived before the workflow is reported complete", contract);
            Assert.Contains("Do not report the QA workflow as fully complete while exactly one linked active OpenSpec change remains unarchived", e2eSkill);
            Assert.Contains("OpenSpec archived: <archive path>", e2eSkill);
            Assert.False(Directory.Exists(activeChange));
            Assert.True(Directory.Exists(archivedChange));
            Assert.True(File.Exists(Path.Combine(root, "openspec", "specs", "client-crud", "spec.md")));
        }

        private static string ReadWorkflow()
        {
            return File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".gitea",
                "workflows",
                "package-deploy.yml"));
        }

        private static string ReadPrValidationWorkflow()
        {
            return File.ReadAllText(Path.Combine(
                FindRepositoryRoot().FullName,
                ".gitea",
                "workflows",
                "pr-validation.yml"));
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

        private static string NormalizeLineEndings(string content)
        {
            return content.Replace("\r\n", "\n", StringComparison.Ordinal);
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
