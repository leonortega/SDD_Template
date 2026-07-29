"""Project guidance discovery reference.

Canonical runtime: ``python -m tools.sdd_cli guidance discover``.
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
        "node",
        "typescript",
        "react",
        "python",
        "java",
        "docker",
        "terraform",
        "kubernetes",
        "coverage",
        "openproject",
        "gitea",
        "gitea-actions-runner",
        "nexus",
        "nexus-artifacts",
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
        "suggestedMissingSkills": "",
        "userAddedRequestedGuidance": "accessibility-review",
        "finalConfirmedGuidance": "openai-playwright-skill",
    }


def add_stack_context_drift_findings() -> None:
    """stack-context drift checks."""


def add_detected_skill_recommendations() -> None:
    """skill-gap recommendations."""


RECOMMENDATION_IDS = [
    "openai-security-best-practices-skill",
    "openai-playwright-skill",
]
SOURCE_FAMILIES = ["repo-local", "skills-cli", "marketplace", "github.com/openai/skills", "skills.sh"]
SEARCH_PLAN = ["project-guidance-search-plan", "guidance-search-plan", "research-then-guarded-install", "official-first-internet-search"]
