function Get-StackContextContent {
  $paths = @(
    "docs/architecture.md",
    "docs/development.md",
    "docs/deployment.md",
    "openspec/config.yaml"
  )

  $parts = foreach ($relativePath in $paths) {
    $path = Join-RootPath $relativePath
    if (Test-Path $path) {
      Get-Content -Path $path -Raw
    }
  }

  return ($parts -join [Environment]::NewLine)
}

function Get-ProjectGuidanceDiscoverySourcePriority {
  return @(
    "repo-local",
    "openai-official",
    "tool-official",
    "technology-owner",
    "skills-cli",
    "marketplace",
    "community"
  )
}

function Get-ProjectGuidanceDiscoverySourceNotes {
  return [ordered]@{
    "repo-local" = "Repository-local workflow skills, scripts, templates, and docs that are already tracked in this project."
    "openai-official" = "OpenAI skill catalogs or docs."
    "tool-official" = "Official repository or documentation for the target tool, framework, product, or plugin."
    "technology-owner" = "Technology-owner repositories or docs, such as Microsoft, .NET, Playwright, Azure, Azure Monitor, Gitea, Nexus, Grafana, Docker, Kubernetes, or OWASP."
    "skills-cli" = "skills.sh or skills command output that identifies a repository, ref, skill name, and likely SKILL.md path."
    "marketplace" = "Marketplace or directory pages that identify a repository, ref, skill name, and likely SKILL.md path."
    "community" = "Well-used public sources only when no stronger source exists; label clearly as community-maintained."
  }
}

function Add-StackContextDriftFindings {
  param(
    $Result,
    [string[]]$DetectedTags
  )

  $context = Get-StackContextContent
  $expectedMentions = @(
    [pscustomobject]@{ tag = "dotnet-10"; pattern = "\.NET 10|net10\.0"; label = ".NET 10" },
    [pscustomobject]@{ tag = "aspnet-core"; pattern = "ASP\.NET Core"; label = "ASP.NET Core" },
    [pscustomobject]@{ tag = "blazor"; pattern = "Blazor"; label = "Blazor" },
    [pscustomobject]@{ tag = "xunit"; pattern = "xUnit"; label = "xUnit" },
    [pscustomobject]@{ tag = "coverage"; pattern = "coverage|coverlet"; label = "coverage" },
    [pscustomobject]@{ tag = "plane"; pattern = "Plane"; label = "Plane" },
    [pscustomobject]@{ tag = "gitea"; pattern = "Gitea"; label = "Gitea" },
    [pscustomobject]@{ tag = "gitea-actions-runner"; pattern = "Gitea Actions"; label = "Gitea Actions" },
    [pscustomobject]@{ tag = "nexus-artifacts"; pattern = "Nexus"; label = "Nexus artifacts" },
    [pscustomobject]@{ tag = "azure-app-service"; pattern = "Azure App Service"; label = "Azure App Service" },
    [pscustomobject]@{ tag = "azure-monitor"; pattern = "Azure Monitor|Log Analytics"; label = "Azure Monitor and Log Analytics" },
    [pscustomobject]@{ tag = "grafana"; pattern = "Grafana"; label = "Grafana" },
    [pscustomobject]@{ tag = "browser-e2e"; pattern = "Browser|Playwright"; label = "Browser or Playwright QA" },
    [pscustomobject]@{ tag = "playwright-guidance"; pattern = "Playwright"; label = "Playwright guidance" },
    [pscustomobject]@{ tag = "clean-code"; pattern = "clean-code|clean code|Clean-code|Clean code"; label = "clean-code standards" },
    [pscustomobject]@{ tag = "architecture-guidance"; pattern = "architecture"; label = "architecture guidance" },
    [pscustomobject]@{ tag = "web-ui"; pattern = "Blazor|web UI|Browser|Playwright"; label = "web UI guidance" },
    [pscustomobject]@{ tag = "rest-api"; pattern = "REST|API|/health|/metrics"; label = "REST/API guidance" },
    [pscustomobject]@{ tag = "security"; pattern = "security|secret|Gitleaks|Trivy|OWASP"; label = "security guidance" },
    [pscustomobject]@{ tag = "openspec"; pattern = "OpenSpec"; label = "OpenSpec" }
  )

  foreach ($expected in $expectedMentions) {
    if ($DetectedTags -notcontains $expected.tag) { continue }
    if ($context -match $expected.pattern) { continue }

    Add-Item $Result "findings" "docs/, openspec/config.yaml" "stack-context.$($expected.tag)" "Detected stack tag '$($expected.tag)' but durable docs/OpenSpec context do not mention $($expected.label)." "warning"
  }
}

function Get-DetectedStackTags {
  $tags = [System.Collections.Generic.List[string]]::new()

  $hasSolution = (Get-ChildItem -Path $Root -Filter "*.slnx" -ErrorAction SilentlyContinue).Count -gt 0
  $hasProject = (Get-ChildItem -Path $Root -Filter "*.csproj" -Recurse -ErrorAction SilentlyContinue).Count -gt 0
  if ($hasSolution -or $hasProject) {
    $tags.Add("dotnet")
  }
  if ((Test-FileContains "global.json" '"version"\s*:\s*"10\.') -or
      (Test-AnyRepoFileContains @("src", "tests", "tools") @("*.csproj") "<TargetFramework>net10\.0</TargetFramework>")) {
    $tags.Add("dotnet-10")
  }
  if ((Test-Path (Join-RootPath "package.json")) -or
      (Test-Path (Join-RootPath "pnpm-lock.yaml")) -or
      (Test-Path (Join-RootPath "yarn.lock")) -or
      (Test-Path (Join-RootPath "package-lock.json"))) {
    $tags.Add("node")
  }
  if ((Test-Path (Join-RootPath "tsconfig.json")) -or
      (Test-AnyRepoFileContains @("src", "app", "pages", "components") @("*.ts", "*.tsx") "export|import")) {
    $tags.Add("typescript")
  }
  if ((Test-FileContains "package.json" '"react"|"next"|"vite"') -or
      (Test-AnyRepoFileContains @("src", "app", "pages", "components") @("*.tsx", "*.jsx", "*.js", "*.ts", "package.json") "react|next|vite")) {
    $tags.Add("react")
    $tags.Add("web-ui")
  }
  if ((Test-Path (Join-RootPath "pyproject.toml")) -or
      (Test-Path (Join-RootPath "requirements.txt")) -or
      (Test-AnyRepoFileContains @(".") @("*.py") "def |import ")) {
    $tags.Add("python")
  }
  if (Test-AnyRepoFileContains @(".") @("pyproject.toml", "requirements.txt", "*.py") "pytest") { $tags.Add("pytest") }
  if (Test-AnyRepoFileContains @(".") @("pyproject.toml", "requirements.txt", "*.py") "fastapi|django|flask") {
    $tags.Add("python-web-api")
    $tags.Add("rest-api")
  }
  if ((Test-Path (Join-RootPath "pom.xml")) -or
      (Test-Path (Join-RootPath "build.gradle")) -or
      (Test-Path (Join-RootPath "build.gradle.kts"))) {
    $tags.Add("java")
  }
  if (Test-AnyRepoFileContains @(".") @("pom.xml", "build.gradle", "build.gradle.kts", "*.java", "*.kt") "spring-boot|org\.springframework") {
    $tags.Add("spring")
    $tags.Add("rest-api")
  }
  if ((Test-Path (Join-RootPath "Dockerfile")) -or
      (Get-ChildItem -Path $Root -Filter "docker-compose*.yml" -Recurse -ErrorAction SilentlyContinue).Count -gt 0 -or
      (Get-ChildItem -Path $Root -Filter "compose.yml" -Recurse -ErrorAction SilentlyContinue).Count -gt 0) {
    $tags.Add("docker")
  }
  if (Test-AnyRepoFileContains @(".") @("*.bicep") "resource ") { $tags.Add("bicep") }
  if (Test-AnyRepoFileContains @(".") @("*.tf") "resource ") { $tags.Add("terraform") }
  if (Test-AnyRepoFileContains @(".") @("*.yaml", "*.yml") "apiVersion:|kind: Deployment|kind: Service") { $tags.Add("kubernetes") }
  if (Test-AnyRepoFileContains @("src", "tests") @("*.csproj") "Microsoft\.NET\.Sdk\.Web|Microsoft\.AspNetCore") {
    $tags.Add("aspnet-core")
  }
  if ((Test-AnyRepoFileContains @("src") @("*.csproj", "*.razor") "Blazor|@page|Microsoft\.NET\.Sdk\.Web") -or
      (Test-AnyRepoFileContains @("src") @("*.csproj") "BlazorDisableThrowNavigationException")) {
    $tags.Add("blazor")
    $tags.Add("web-ui")
  }
  if ($hasSolution -or $hasProject) {
    $tags.Add("clean-code")
    if (Test-Path (Join-RootPath "docs/architecture.md")) { $tags.Add("architecture-guidance") }
  }
  if ((Test-AnyRepoFileContains @("src") @("*.cs", "*.razor") "Map(Get|Post|Put|Delete|Patch)\(|ApiController|Http(Get|Post|Put|Delete|Patch)|AddControllers|ProblemDetails|OpenApi|Swagger") -or
      (Test-AnyRepoFileContains @("docs", "openspec") @("*.md", "*.yaml", "*.yml") "REST|API|/health|/metrics")) {
    $tags.Add("rest-api")
  }
  if (Test-AnyRepoFileContains @("tests") @("*.csproj") "xunit") { $tags.Add("xunit") }
  if ((Test-AnyRepoFileContains @("tests") @("*.csproj") "coverlet") -or
      (Test-FileContains ".codex/quality.example.json" '"coverage"')) {
    $tags.Add("coverage")
  }
  if ((Test-AnyRepoFileContains @(".gitea/workflows", ".codex", "docs") @("*.yml", "*.yaml", "*.json", "*.md", "*.ps1") "gitleaks|trivy|secret scan|dependency vulnerability|security") -or
      (Test-Path (Join-RootPath ".codex/quality.example.json"))) {
    $tags.Add("security")
  }
  if (Test-Path (Join-RootPath "infra/plane")) { $tags.Add("plane") }
  if (Test-Path (Join-RootPath "infra/gitea")) { $tags.Add("gitea") }
  if (Test-Path (Join-RootPath ".gitea/workflows")) {
    $tags.Add("gitea-actions")
    $tags.Add("gitea-actions-runner")
  }
  if ((Test-Path (Join-RootPath "infra/nexus")) -or (Test-AnyRepoFileContains @(".gitea/workflows") @("*.yml", "*.yaml") "NEXUS_|/repository/")) {
    $tags.Add("nexus")
    $tags.Add("nexus-artifacts")
  }
  if ((Test-Path (Join-RootPath "infra/azure")) -or (Test-AnyRepoFileContains @(".gitea/workflows") @("*.yml", "*.yaml") "az webapp deploy|Azure App Service")) {
    $tags.Add("azure")
    $tags.Add("azure-app-service")
  }
  if (Test-Path (Join-RootPath "infra/monitoring")) { $tags.Add("observability") }
  if ((Test-FileContains "infra/monitoring/grafana/provisioning/datasources/azure-monitor.yml" "grafana-azure-monitor-datasource") -or
      (Test-AnyRepoFileContains @("infra/azure", "docs", ".codex/skills") @("*.bicep", "*.md", "*.ps1") "Log Analytics|Azure Monitor")) {
    $tags.Add("azure-monitor")
  }
  if (Test-Path (Join-RootPath "infra/monitoring/grafana")) { $tags.Add("grafana") }
  if ((Test-Path (Join-RootPath "artifacts/qa")) -or (Test-Path (Join-RootPath ".codex/skills/test-e2e/SKILL.md"))) {
    $tags.Add("e2e")
    $tags.Add("browser-e2e")
  }
  if ((Test-Path (Join-RootPath ".codex/skills/frontend-testing-debugging/SKILL.md")) -or
      (Test-FileContains ".codex/skills/test-e2e/SKILL.md" "Playwright")) {
    $tags.Add("playwright-guidance")
  }
  if (Test-Path (Join-RootPath "openspec")) { $tags.Add("openspec") }

  return @($tags | Select-Object -Unique)
}

function Get-ProjectGuidanceResearchTopics {
  param([string[]]$DetectedTags)

  $topicDefinitions = @(
    [pscustomobject]@{
      id = "dotnet-aspnet"
      tags = @("dotnet", "dotnet-10", "aspnet-core")
      area = ".NET / ASP.NET Core"
      purpose = "Find skills for .NET SDK, ASP.NET Core architecture, dependency injection, middleware, hosting, and maintainable code."
      officialFirstSources = @("https://github.com/openai/skills", "https://github.com/dotnet/skills", "https://learn.microsoft.com/en-us/aspnet/core/")
      discoverySourcePriority = Get-ProjectGuidanceDiscoverySourcePriority
      searchQueries = @("site:github.com/openai/skills aspnet-core SKILL.md", "site:github.com/dotnet/skills ASP.NET Core skills", "site:learn.microsoft.com ASP.NET Core architecture dependency injection")
    },
    [pscustomobject]@{
      id = "web-ui"
      tags = @("blazor", "react", "web-ui")
      area = "Web UI"
      purpose = "Find skills for component architecture, accessibility, responsive behavior, browser-visible UI quality, and user workflow design."
      officialFirstSources = @("https://github.com/openai/skills", "https://github.com/dotnet/skills", "https://www.w3.org/WAI/standards-guidelines/wcag/")
      discoverySourcePriority = Get-ProjectGuidanceDiscoverySourcePriority
      searchQueries = @("site:github.com/openai/skills web UI skill", "site:github.com/dotnet/skills Blazor UI skill", "site:w3.org/WAI WCAG accessibility")
    },
    [pscustomobject]@{
      id = "rest-api"
      tags = @("rest-api", "aspnet-core", "python-web-api", "spring")
      area = "REST/API"
      purpose = "Find skills for route design, validation, ProblemDetails/error responses, authentication boundaries, OpenAPI, and API integration tests."
      officialFirstSources = @("https://github.com/openai/skills", "https://github.com/dotnet/skills", "https://learn.microsoft.com/en-us/aspnet/core/web-api/")
      discoverySourcePriority = Get-ProjectGuidanceDiscoverySourcePriority
      searchQueries = @("site:github.com/openai/skills API skill", "site:github.com/dotnet/skills webapi skill", "official REST API design skill SKILL.md")
    },
    [pscustomobject]@{
      id = "qa-testing"
      tags = @("xunit", "pytest", "coverage", "browser-e2e", "playwright-guidance")
      area = "QA / Testing"
      purpose = "Find skills for test strategy, assertion quality, coverage analysis, browser automation, test-gap analysis, and QA evidence."
      officialFirstSources = @("https://github.com/openai/skills", "https://github.com/dotnet/skills", "https://playwright.dev/docs/best-practices")
      discoverySourcePriority = Get-ProjectGuidanceDiscoverySourcePriority
      searchQueries = @("site:github.com/openai/skills playwright skill", "site:github.com/dotnet/skills assertion-quality coverage-analysis", "official test strategy skill SKILL.md")
    },
    [pscustomobject]@{
      id = "security"
      tags = @("security")
      area = "Security"
      purpose = "Find skills for application security review, threat modeling, secrets handling, dependency risk, authorization, logging, and OWASP review."
      officialFirstSources = @("https://github.com/openai/skills", "https://owasp.org/www-project-top-ten/", "https://owasp.org/www-project-application-security-verification-standard/")
      discoverySourcePriority = Get-ProjectGuidanceDiscoverySourcePriority
      searchQueries = @("site:github.com/openai/skills security-best-practices SKILL.md", "site:github.com/openai/skills security-threat-model SKILL.md", "OWASP application security skill SKILL.md")
    },
    [pscustomobject]@{
      id = "delivery-tools"
      tags = @("plane", "gitea", "gitea-actions-runner", "nexus-artifacts", "azure-app-service", "azure-monitor", "grafana")
      area = "Delivery tools and environments"
      purpose = "Find skills for ticket workflow, source control/review, CI runner behavior, artifact promotion, cloud deployment, and observability."
      officialFirstSources = @("https://github.com/openai/skills", "https://docs.gitea.com/", "https://learn.microsoft.com/en-us/azure/app-service/", "https://learn.microsoft.com/en-us/azure/azure-monitor/", "https://grafana.com/docs/")
      discoverySourcePriority = Get-ProjectGuidanceDiscoverySourcePriority
      searchQueries = @("official Gitea Actions skill SKILL.md", "official Azure App Service deploy skill SKILL.md", "official Azure Monitor Grafana skill SKILL.md")
    },
    [pscustomobject]@{
      id = "containers-iac"
      tags = @("docker", "bicep", "terraform", "kubernetes")
      area = "Containers / IaC"
      purpose = "Find skills for Docker, Compose, infrastructure as code, Kubernetes manifests, cloud resource templates, and environment drift checks."
      officialFirstSources = @("https://github.com/openai/skills", "https://docs.docker.com/", "https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/", "https://developer.hashicorp.com/terraform/docs", "https://kubernetes.io/docs/")
      discoverySourcePriority = Get-ProjectGuidanceDiscoverySourcePriority
      searchQueries = @("site:github.com/openai/skills Docker skill", "official Bicep skill SKILL.md", "official Terraform Kubernetes skill SKILL.md")
    },
    [pscustomobject]@{
      id = "code-standards"
      tags = @("clean-code", "architecture-guidance")
      area = "Code standards and architecture"
      purpose = "Find skills for clean code, maintainability, architecture reviews, code smells, refactoring boundaries, and project-specific engineering standards."
      officialFirstSources = @("https://github.com/openai/skills", "https://learn.microsoft.com/en-us/dotnet/architecture/")
      discoverySourcePriority = Get-ProjectGuidanceDiscoverySourcePriority
      searchQueries = @("site:github.com/openai/skills code architecture skill", "official clean code architecture skill SKILL.md", "site:learn.microsoft.com clean architecture web application")
    }
  )

  $topics = foreach ($definition in $topicDefinitions) {
    $matchedTags = @($definition.tags | Where-Object { $DetectedTags -contains $_ })
    if ($matchedTags.Count -eq 0) { continue }

    [ordered]@{
      id = $definition.id
      area = $definition.area
      matchedTags = @($matchedTags)
      purpose = $definition.purpose
      officialFirstSources = $definition.officialFirstSources
      discoverySourcePriority = $definition.discoverySourcePriority
      searchQueries = $definition.searchQueries
    }
  }

  return @($topics)
}

function Get-DetectedSkillDefinitions {
  return @(
    [pscustomobject]@{
      id = "openai-aspnet-core-skill"
      name = "OpenAI ASP.NET Core skill"
      requires = @("dotnet-10", "aspnet-core", "clean-code", "architecture-guidance")
      purpose = "Use OpenAI's curated ASP.NET Core skill for ASP.NET Core architecture, Blazor, Minimal APIs, Web APIs, middleware, DI, testing, deployment, and security guidance."
      sourceKind = "openai-official"
      source = "https://github.com/openai/skills/tree/main/skills/.curated/aspnet-core"
      target = ".codex/skills/aspnet-core/SKILL.md"
      candidateSkillSources = @("https://github.com/openai/skills/tree/main/skills/.curated/aspnet-core", "https://github.com/dotnet/skills/tree/main/plugins/dotnet-aspnet")
      researchTopics = @(".NET clean architecture", "ASP.NET Core architecture", "dependency injection", "testable boundaries", "Blazor", "Minimal APIs")
      officialSources = @("https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/common-web-application-architectures", "https://learn.microsoft.com/en-us/aspnet/core/fundamentals/")
      searchQueries = @("site:github.com/openai/skills aspnet-core SKILL.md", "site:github.com/dotnet/skills ASP.NET Core skills")
      notes = "Dynamic skill finding from detected .NET/ASP.NET stack and documented clean-code standards. OpenAI provides a curated aspnet-core skill; copy it manually after user confirmation."
    },
    [pscustomobject]@{
      id = "dotnet-blazor-plan-ui-change-skill"
      name = ".NET Blazor plan UI change skill"
      requires = @("blazor", "web-ui", "browser-e2e")
      purpose = "Use the .NET team's Blazor UI planning skill for Blazor page/component changes, user-visible behavior, accessibility, and responsive design decisions."
      sourceKind = "technology-owner"
      source = "https://github.com/dotnet/skills/tree/main/plugins/dotnet-blazor/skills/plan-ui-change"
      target = ".codex/skills/plan-ui-change/SKILL.md"
      candidateSkillSources = @("https://github.com/dotnet/skills/tree/main/plugins/dotnet-blazor/skills/plan-ui-change", "https://github.com/dotnet/skills/tree/main/plugins/dotnet-blazor/skills/author-component", "https://github.com/openai/skills/tree/main/skills/.curated/aspnet-core")
      researchTopics = @("Blazor components", "routing", "forms validation", "accessibility", "responsive layout", "Playwright assertions")
      officialSources = @("https://learn.microsoft.com/en-us/aspnet/core/blazor/", "https://playwright.dev/docs/best-practices", "https://www.w3.org/WAI/standards-guidelines/wcag/")
      searchQueries = @("site:github.com/dotnet/skills dotnet-blazor plan-ui-change", "site:github.com/openai/skills aspnet-core Blazor")
      notes = "Dynamic skill finding from Blazor/web UI signals. The .NET team publishes Blazor skills compatible with Codex; copy selected skills manually after user confirmation."
    },
    [pscustomobject]@{
      id = "dotnet-webapi-skill"
      name = ".NET Web API skill"
      requires = @("aspnet-core", "rest-api")
      purpose = "Use the .NET team's Web API skill for ASP.NET Core REST/minimal API design, route shape, validation, ProblemDetails, auth boundaries, OpenAPI, and integration tests."
      sourceKind = "technology-owner"
      source = "https://github.com/dotnet/skills/tree/main/plugins/dotnet-aspnet/skills/dotnet-webapi"
      target = ".codex/skills/dotnet-webapi/SKILL.md"
      candidateSkillSources = @("https://github.com/dotnet/skills/tree/main/plugins/dotnet-aspnet/skills/dotnet-webapi", "https://github.com/openai/skills/tree/main/skills/.curated/aspnet-core")
      researchTopics = @("ASP.NET Core minimal APIs", "REST API design", "ProblemDetails", "OpenAPI", "integration testing")
      officialSources = @("https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/", "https://learn.microsoft.com/en-us/aspnet/core/web-api/", "https://learn.microsoft.com/en-us/aspnet/core/fundamentals/error-handling-api")
      searchQueries = @("site:github.com/dotnet/skills dotnet-webapi", "site:github.com/openai/skills aspnet-core Minimal APIs Web APIs")
      notes = "Dynamic skill finding from API endpoint signals such as MapGet/health/metrics or REST/API docs. Copy the selected official skill manually after user confirmation."
    },
    [pscustomobject]@{
      id = "openai-security-best-practices-skill"
      name = "OpenAI security best practices skill"
      requires = @("security", "aspnet-core")
      purpose = "Use OpenAI's curated security best practices skill for security review, secrets, authentication, authorization, input validation, dependency risk, logging, headers, and OWASP risks."
      sourceKind = "openai-official"
      source = "https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices"
      target = ".codex/skills/security-best-practices/SKILL.md"
      candidateSkillSources = @("https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices", "https://github.com/openai/skills/tree/main/skills/.curated/security-threat-model", "https://github.com/openai/skills/tree/main/skills/.curated/aspnet-core")
      researchTopics = @("ASP.NET Core security", "OWASP Top 10", "secrets handling", "dependency scanning", "secure logging")
      officialSources = @("https://learn.microsoft.com/en-us/aspnet/core/security/", "https://owasp.org/www-project-top-ten/", "https://owasp.org/www-project-application-security-verification-standard/")
      searchQueries = @("site:github.com/openai/skills security-best-practices SKILL.md", "site:github.com/openai/skills security-threat-model SKILL.md")
      notes = "Dynamic skill finding from configured security gates and ASP.NET Core stack. OpenAI provides curated security skills; copy selected skills manually after user confirmation. It complements Gitleaks, Trivy, and dependency audit; it does not replace those gates."
    },
    [pscustomobject]@{
      id = "openai-playwright-skill"
      name = "OpenAI Playwright skill"
      requires = @("browser-e2e", "playwright-guidance")
      purpose = "Use OpenAI's curated Playwright skill for browser automation, user-visible assertions, traces, and repeatable UI QA support."
      sourceKind = "openai-official"
      source = "https://github.com/openai/skills/tree/main/skills/.curated/playwright"
      target = ".codex/skills/playwright/SKILL.md"
      candidateSkillSources = @("https://github.com/openai/skills/tree/main/skills/.curated/playwright", "https://github.com/openai/skills/tree/main/skills/.curated/playwright-interactive")
      researchTopics = @("Playwright locators", "web-first assertions", "browser automation", "trace evidence", "responsive UI checks")
      officialSources = @("https://playwright.dev/docs/best-practices", "https://playwright.dev/docs/test-agents")
      searchQueries = @("site:github.com/openai/skills playwright skill", "site:playwright.dev/docs Playwright best practices")
      notes = "Dynamic skill finding from browser/Playwright QA signals. This complements the repo-local frontend-testing-debugging skill with an official curated Playwright skill."
    },
    [pscustomobject]@{
      id = "dotnet-assertion-quality-skill"
      name = ".NET assertion quality skill"
      requires = @("dotnet-10", "xunit", "coverage")
      purpose = "Use the .NET team's assertion-quality skill for stronger test assertions, cleaner QA evidence, and better regression tests."
      sourceKind = "technology-owner"
      source = "https://github.com/dotnet/skills/tree/main/plugins/dotnet-test/skills/assertion-quality"
      target = ".codex/skills/assertion-quality/SKILL.md"
      candidateSkillSources = @("https://github.com/dotnet/skills/tree/main/plugins/dotnet-test/skills/assertion-quality", "https://github.com/dotnet/skills/tree/main/plugins/dotnet-test/skills/test-gap-analysis", "https://github.com/dotnet/skills/tree/main/plugins/dotnet-test/skills/coverage-analysis")
      researchTopics = @(".NET testing", "xUnit assertions", "coverage analysis", "test gap analysis", "test anti-patterns")
      officialSources = @("https://learn.microsoft.com/en-us/dotnet/core/testing/", "https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-test")
      searchQueries = @("site:github.com/dotnet/skills assertion-quality", "site:github.com/dotnet/skills coverage-analysis test-gap-analysis")
      notes = "Dynamic skill finding from xUnit and coverage signals. Copy selected .NET test skills manually after user confirmation."
    }
  )
}

function Test-SkillDefinitionMatchesStack {
  param(
    $Recommendation,
    [string[]]$DetectedTags
  )

  foreach ($tag in @($Recommendation.requires)) {
    if ($DetectedTags -notcontains $tag) { return $false }
  }

  return $true
}

function ConvertTo-SkillSuggestion {
  param(
    [string[]]$Accepted,
    $Recommendation
  )

  $targetExists = $false
  if (-not [string]::IsNullOrWhiteSpace($Recommendation.target)) {
    $targetExists = Test-Path (Join-RootPath $Recommendation.target)
  }

  return [ordered]@{
    id = $Recommendation.id
    name = $Recommendation.name
    type = "skill"
    purpose = $Recommendation.purpose
    installMethod = "manual-copy"
    sourceKind = $Recommendation.sourceKind
    source = $Recommendation.source
    target = $Recommendation.target
    validation = "Test-Path $($Recommendation.target)"
    accepted = ($Accepted -contains $Recommendation.id)
    detected = $true
    targetExists = $targetExists
    installStatus = $(if ($targetExists) { "present" } else { "proposed" })
    requiresUserConfirmation = (-not $targetExists)
    sourceDiscovery = "official-first-internet-search"
    discoverySourcePriority = Get-ProjectGuidanceDiscoverySourcePriority
    discoverySourceNotes = Get-ProjectGuidanceDiscoverySourceNotes
    officialSkillSources = @(
      "https://github.com/openai/skills",
      "https://help.openai.com/en/articles/20001066-skills-in-chatgpt",
      "https://openai.com/academy/skills/"
    )
    candidateSkillSources = @($Recommendation.candidateSkillSources)
    requires = @($Recommendation.requires)
    researchTopics = @($Recommendation.researchTopics)
    officialSources = @($Recommendation.officialSources)
    searchQueries = @($Recommendation.searchQueries)
    notes = $Recommendation.notes
  }
}

function Get-ScanDerivedSkillSuggestions {
  param(
    [string[]]$DetectedTags,
    [string[]]$Accepted,
    [string[]]$Dismissed
  )

  $suggestions = foreach ($skill in Get-DetectedSkillDefinitions) {
    if ($Dismissed -contains $skill.id) { continue }
    if (-not (Test-SkillDefinitionMatchesStack $skill $DetectedTags)) { continue }

    ConvertTo-SkillSuggestion $Accepted $skill
  }

  return @($suggestions)
}

function Add-ProjectGuidanceSearchPlanRecommendation {
  param(
    $Result,
    [string[]]$DetectedTags
  )

  $topics = Get-ProjectGuidanceResearchTopics $DetectedTags
  if ($topics.Count -eq 0) {
    Add-Item $Result "findings" "project guidance discovery" "guidance-search-plan.empty" "No specific project guidance search topics were detected. Ask the user for project technologies, tools, QA expectations, and code/security standards before recommending skills or guidance." "info"
    return
  }

  Add-Item $Result "actions" "project-guidance-discover" "guidanceSearchPlan" "Prepared $($topics.Count) project guidance search topics from detected project signals. Use project-guidance-discover to show suggested skills and guidance, ask for additional desired items, then pass confirmed skill items to project-guidance-acquire."

  Add-Recommendation $Result ([ordered]@{
    id = "project-guidance-search-plan"
    name = "Project guidance search plan"
    type = "guidance-search-plan"
    purpose = "Research skills, tools, references, practices, standards, MCPs, and plugins from detected project technologies, environments, tests, security gates, and code standards before proposing local guidance updates."
    installMethod = "research-then-manual-copy"
    accepted = $false
    detected = $true
    requiresUserConfirmation = $true
    sourceDiscovery = "official-first-internet-search"
    discoverySourcePriority = Get-ProjectGuidanceDiscoverySourcePriority
    discoverySourceNotes = Get-ProjectGuidanceDiscoverySourceNotes
    topics = [object[]]$topics
    nextStep = "Use project-guidance-discover: search OpenAI official catalogs/docs, official tool repositories/docs, technology-owner sources, skills.sh/skills or marketplace repository leads, and trusted public sources for each topic; check .codex/skills for existing SKILL.md files; show suggested missing skills and guidance; ask for additional desired items; then pass confirmed skill items to project-guidance-acquire."
  })
}

function Add-DetectedSkillRecommendation {
  param(
    $Result,
    [string[]]$DetectedTags,
    [string[]]$Accepted,
    [string[]]$Dismissed,
    $Recommendation
  )

  if ($Dismissed -contains $Recommendation.id) { return }
  if (-not (Test-SkillDefinitionMatchesStack $Recommendation $DetectedTags)) { return }

  $item = ConvertTo-SkillSuggestion $Accepted $Recommendation
  $message = if ($item.targetExists) {
    "Detected project signals for '$($Recommendation.name)' and the repo-local skill target already exists. Record acceptance with SetRecommendedTools if this skill should be part of the active project tool set."
  } else {
    "Detected project signals for '$($Recommendation.name)' but no repo-local skill exists at $($Recommendation.target). project-guidance-discover must show this suggestion, ask for additional desired skills or guidance, then project-guidance-acquire may manually copy the confirmed source SKILL.md."
  }
  $keyPrefix = if ($item.targetExists) { "skill-present" } else { "skill-gap" }
  $severity = if ($item.targetExists) { "info" } else { "warning" }
  Add-Item $Result "findings" $Recommendation.target "$keyPrefix.$($Recommendation.id)" $message $severity

  Add-Recommendation $Result $item
}

function Add-DetectedSkillRecommendations {
  param(
    $Result,
    [string[]]$DetectedTags,
    [string[]]$Accepted,
    [string[]]$Dismissed
  )

  foreach ($skill in Get-DetectedSkillDefinitions) {
    Add-DetectedSkillRecommendation $Result $DetectedTags $Accepted $Dismissed $skill
  }
}

function Get-ExistingRepoSkills {
  $skillsRoot = Join-RootPath ".codex/skills"
  if (-not (Test-Path $skillsRoot)) { return @() }

  $skills = foreach ($skillFile in Get-ChildItem -Path $skillsRoot -Filter "SKILL.md" -Recurse -File -ErrorAction SilentlyContinue) {
    $relative = Get-RepoRelativePath $skillFile.FullName
    $name = Split-Path -Leaf (Split-Path -Parent $skillFile.FullName)
    [ordered]@{
      name = $name
      target = $relative
    }
  }

  return @($skills | Sort-Object -Property name)
}

function ConvertTo-RequestedGuidance {
  param($Guidance)

  if ($Guidance -is [string]) {
    return [ordered]@{
      name = $Guidance
      type = "skill"
      installMethod = "manual-copy"
      sourceKind = $null
      source = $null
      target = ".codex/skills/$Guidance/SKILL.md"
      status = "needs-research"
    }
  }

  $name = if ($Guidance.PSObject.Properties.Name -contains "name") { [string]$Guidance.name } else { [string]$Guidance.id }
  $type = if ($Guidance.PSObject.Properties.Name -contains "type") { [string]$Guidance.type } else { "skill" }
  $installMethod = if ($Guidance.PSObject.Properties.Name -contains "installMethod") { [string]$Guidance.installMethod } elseif ($type -eq "skill") { "manual-copy" } else { "manual-reference" }
  $target = if ($Guidance.PSObject.Properties.Name -contains "target") { [string]$Guidance.target } elseif ($type -eq "skill") { ".codex/skills/$name/SKILL.md" } else { $null }
  $source = if ($Guidance.PSObject.Properties.Name -contains "source") { [string]$Guidance.source } else { $null }
  $sourceKind = if ($Guidance.PSObject.Properties.Name -contains "sourceKind") { [string]$Guidance.sourceKind } else { $null }

  return [ordered]@{
    name = $name
    type = $type
    installMethod = $installMethod
    sourceKind = $sourceKind
    source = $source
    target = $target
    status = $(if ([string]::IsNullOrWhiteSpace($source)) { "needs-research" } else { "source-provided" })
  }
}

function Get-AdditionalGuidanceRequestsFromJson {
  param([AllowNull()][string]$Json)

  if ([string]::IsNullOrWhiteSpace($Json)) { return @() }

  $data = $Json | ConvertFrom-Json
  $items = if ($data -is [array]) {
    @($data)
  } elseif ($data.PSObject.Properties.Name -contains "additionalGuidance") {
    @($data.additionalGuidance)
  } elseif ($data.PSObject.Properties.Name -contains "additionalSkills") {
    @($data.additionalSkills)
  } elseif ($data.PSObject.Properties.Name -contains "userAddedRequestedGuidance") {
    @($data.userAddedRequestedGuidance)
  } elseif ($data.PSObject.Properties.Name -contains "userAddedRequestedSkills") {
    @($data.userAddedRequestedSkills)
  } else {
    @()
  }

  return @($items | ForEach-Object { ConvertTo-RequestedGuidance $_ })
}

function Get-ScanDerivedCatalogGuidance {
  param(
    [string[]]$DetectedTags,
    [string[]]$Accepted,
    [string[]]$Dismissed
  )

  $catalog = Get-ToolRecommendationCatalog
  $guidance = foreach ($entry in @($catalog.recommendations)) {
    if ($Dismissed -contains $entry.id) { continue }
    if ($entry.type -eq "skill") { continue }
    if (-not (Test-RecommendationMatchesStack -Recommendation $entry -DetectedTags $DetectedTags)) { continue }

    $item = ConvertTo-CatalogRecommendation -Entry $entry -Accepted $Accepted
    if ($entry.PSObject.Properties.Name -contains "tags") {
      $item["tags"] = @($entry.tags)
    }
    $item
  }

  return @($guidance)
}

function Get-ProjectGuidanceDiscoveryReport {
  param(
    [string[]]$Accepted = @(),
    [string[]]$Dismissed = @(),
    [object[]]$UserAddedRequestedGuidance = @(),
    [switch]$Confirmed
  )

  $detectedTags = Get-DetectedStackTags
  $researchTopics = Get-ProjectGuidanceResearchTopics $detectedTags
  $suggestions = Get-ScanDerivedSkillSuggestions $detectedTags $Accepted $Dismissed
  $guidance = Get-ScanDerivedCatalogGuidance $detectedTags $Accepted $Dismissed
  $missing = @($suggestions | Where-Object { -not $_.targetExists })
  $present = @($suggestions | Where-Object { $_.targetExists })
  $userAdded = @($UserAddedRequestedGuidance)
  $confirmedGuidance = if ($Confirmed) {
    @($missing + $guidance + $userAdded)
  } else {
    @()
  }
  $confirmedSkills = @($confirmedGuidance | Where-Object { $_.type -eq "skill" })

  return [ordered]@{
    detectedTags = @($detectedTags)
    researchTopics = @($researchTopics)
    existingSkills = @(Get-ExistingRepoSkills)
    suggestedMissingSkills = @($missing)
    suggestedPresentSkills = @($present)
    suggestedGuidance = @($guidance)
    userAddedRequestedGuidance = @($userAdded)
    userAddedRequestedSkills = @($userAdded)
    finalConfirmedGuidance = @($confirmedGuidance)
    finalConfirmedSkills = @($confirmedSkills)
    discoverySourcePriority = Get-ProjectGuidanceDiscoverySourcePriority
    discoverySourceNotes = Get-ProjectGuidanceDiscoverySourceNotes
    nextUserQuestion = "Do you want to add any additional desired skills or guidance before project-guidance-acquire copies confirmed skill items and the local catalog records the rest?"
  }
}
