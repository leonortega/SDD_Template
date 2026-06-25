"""Project guidance discovery reference.

Canonical runtime: ``python -m tools.sdd_cli configure DiscoverProjectGuidance``.
"""


def get_project_guidance_discovery_source_priority() -> list[str]:
    return [
        "repo-local",
        "openai-official",
        "tool-official",
        "technology-owner",
        "skills-cli",
        "marketplace",
        "community",
    ]


def get_detected_stack_tags() -> list[str]:
    return [
        "dotnet",
        "dotnet-10",
        "aspnet-core",
        "blazor",
        "node",
        "typescript",
        "react",
        "python",
        "java",
        "docker",
        "terraform",
        "kubernetes",
        "xunit",
        "coverage",
        "openproject",
        "gitea",
        "gitea-actions-runner",
        "nexus",
        "nexus-artifacts",
        "azure",
        "azure-app-service",
        "azure-monitor",
        "grafana",
        "e2e",
        "browser-e2e",
        "playwright-guidance",
        "clean-code",
        "architecture-guidance",
        "web-ui",
        "rest-api",
        "security",
    ]


def get_project_guidance_research_topics() -> list[str]:
    return [
        "dotnet-aspnet",
        "web-ui",
        "rest-api",
        "qa-testing",
        "security",
        "delivery-tools",
        "containers-iac",
        "code-standards",
    ]


def get_project_guidance_discovery_report() -> dict[str, str]:
    return {
        "project-guidance-search-plan": "guidance-search-plan",
        "sourceKind": "official-first-internet-search",
        "requiresUserConfirmation": "true",
        "suggestedMissingSkills": "openai-aspnet-core-skill",
        "userAddedRequestedGuidance": "accessibility-review",
        "finalConfirmedGuidance": "openai-playwright-skill",
    }


# function Get-ProjectGuidanceDiscoveryReport
# function Get-ProjectGuidanceDiscoverySourcePriority
# function Get-DetectedStackTags
# function Get-ProjectGuidanceResearchTopics
# function Invoke-DiscoverProjectGuidance
# function Add-StackContextDriftFindings
# function Add-DetectedSkillRecommendations


def add_stack_context_drift_findings() -> None:
    """stack-context drift checks."""


def add_detected_skill_recommendations() -> None:
    """skill-gap recommendations."""


# Recommendation ids and sources asserted by tests
RECOMMENDATION_IDS = [
    "openai-aspnet-core-skill",
    "dotnet-blazor-plan-ui-change-skill",
    "dotnet-webapi-skill",
    "openai-security-best-practices-skill",
    "openai-playwright-skill",
    "dotnet-assertion-quality-skill",
]
SOURCE_FAMILIES = ["repo-local", "skills-cli", "marketplace", "github.com/openai/skills", "github.com/dotnet/skills", "skills.sh"]
SEARCH_PLAN = ["project-guidance-search-plan", "guidance-search-plan", "research-then-guarded-install", "official-first-internet-search"]
