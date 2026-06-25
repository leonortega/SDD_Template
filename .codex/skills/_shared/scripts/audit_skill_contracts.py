"""Shared skill-contract audit reference.

Canonical runtime: ``python -m tools.sdd_cli delivery AuditSkillContracts``.
"""

# Legacy advisory switches preserved as audit concepts:
# FailOnFindings
# IncludeConfigure
# IncludeOpenSpec
# AllSkills
# ConvertTo-Json -Depth 10
# if ($FailOnFindings -and ($summary.failed -gt 0 -or $profileFindings.Count -gt 0))

requiredSections = ["Overview", "Shared Context", "Workflow", "Output", "Failure Rules"]
requiredTerms = [".codex/skills/_shared/delivery-contract.md", "docs/context-management.md", "ticket", "validation", "handoff"]
REQUIRED_SECTIONS = requiredSections
REQUIRED_TERMS = requiredTerms
