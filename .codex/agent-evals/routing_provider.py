"""
Promptfoo Custom Provider for SDD Agent Routing Evaluation.

This provider evaluates workflow routing decisions based on ticket,
branch, PR, and deployment state. It simulates the routing logic
that the Codex agent would follow according to the delivery contract.

Usage:
  Referenced from promptfooconfig.yaml via:
    providers:
      - id: 'file://.codex/agent-evals/routing_provider.py'
"""

import json
from typing import Any


def call_api(
    prompt: str,
    options: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a routing scenario and return the expected route.
    
    Args:
        prompt: The prompt template text (not used directly - we use vars).
        options: Provider options from config.
        context: Test context containing vars from the test case.
    
    Returns:
        dict with 'output' containing JSON of the routing decision.
    """
    ctx = context or {}
    vars_data = ctx.get("vars", {})

    # Extract test variables
    ticket_state = str(vars_data.get("ticketState", "")).strip().lower()
    branch_exists = str(vars_data.get("branchExists", "false")).strip().lower() == "true"
    pr_exists = str(vars_data.get("prExists", "false")).strip().lower() == "true"
    pr_merged = str(vars_data.get("prMerged", "false")).strip().lower() == "true"
    qa_evidence = str(vars_data.get("qaEvidence", "")).strip().lower()
    product_stack = str(vars_data.get("productStack", "")).strip().lower()
    incident = str(vars_data.get("incident", "false")).strip().lower() == "true"
    hotfix = str(vars_data.get("hotfix", "false")).strip().lower() == "true"

    # --- PARALLEL DELIVERY & DEPLOYMENT LANE VARS ---
    parallel_enabled = str(vars_data.get("parallelEnabled", "false")).strip().lower() == "true"
    max_active_reached = str(vars_data.get("maxActiveReached", "false")).strip().lower() == "true"
    lane_owner = str(vars_data.get("laneOwner", "")).strip().lower()
    prod_requested = str(vars_data.get("prodRequested", "false")).strip().lower() == "true"
    nexus_artifact_exists = str(vars_data.get("nexusArtifactExists", "true")).strip().lower() == "true"
    release_tag_conflict = str(vars_data.get("releaseTagConflict", "false")).strip().lower() == "true"
    worktree_exists = str(vars_data.get("worktreeExists", "false")).strip().lower() == "true"

    # Evaluate routing logic (mirrors dev-flow-continue-implementation + parallel + deploy lane logic)
    route = _evaluate_route(
        ticket_state=ticket_state,
        branch_exists=branch_exists,
        pr_exists=pr_exists,
        pr_merged=pr_merged,
        qa_evidence=qa_evidence,
        product_stack=product_stack,
        incident=incident,
        hotfix=hotfix,
        parallel_enabled=parallel_enabled,
        max_active_reached=max_active_reached,
        lane_owner=lane_owner,
        prod_requested=prod_requested,
        nexus_artifact_exists=nexus_artifact_exists,
        release_tag_conflict=release_tag_conflict,
        worktree_exists=worktree_exists,
    )

    # Build reasoning trace
    reasoning = _build_reasoning(
        ticket_state=ticket_state,
        branch_exists=branch_exists,
        pr_exists=pr_exists,
        pr_merged=pr_merged,
        qa_evidence=qa_evidence,
        product_stack=product_stack,
        incident=incident,
        hotfix=hotfix,
        parallel_enabled=parallel_enabled,
        max_active_reached=max_active_reached,
        lane_owner=lane_owner,
        prod_requested=prod_requested,
        nexus_artifact_exists=nexus_artifact_exists,
        release_tag_conflict=release_tag_conflict,
        worktree_exists=worktree_exists,
        route=route,
    )

    result = {
        "route": route,
        "reasoning": reasoning,
        "inputs": {
            "ticketState": ticket_state,
            "branchExists": branch_exists,
            "prExists": pr_exists,
            "prMerged": pr_merged,
            "qaEvidence": qa_evidence,
            "productStack": product_stack,
            "incident": incident,
            "hotfix": hotfix,
            "parallelEnabled": parallel_enabled,
            "maxActiveReached": max_active_reached,
            "laneOwner": lane_owner,
            "prodRequested": prod_requested,
            "nexusArtifactExists": nexus_artifact_exists,
            "releaseTagConflict": release_tag_conflict,
            "worktreeExists": worktree_exists,
        },
    }

    return {
        "output": json.dumps(result, indent=2),
        # Optional: report token usage to Promptfoo
        "tokenUsage": {"total": 0, "prompt": 0, "completion": 0},
    }


def _evaluate_route(
    ticket_state: str,
    branch_exists: bool,
    pr_exists: bool,
    pr_merged: bool,
    qa_evidence: str,
    product_stack: str,
    incident: bool,
    hotfix: bool,
    parallel_enabled: bool = False,
    max_active_reached: bool = False,
    lane_owner: str = "",
    prod_requested: bool = False,
    nexus_artifact_exists: bool = True,
    release_tag_conflict: bool = False,
    worktree_exists: bool = False,
) -> str:
    """Determine the correct workflow route based on the delivery contract.
    
    Routing order:
    1. Incident/hotfix -> dev-ops-rollback-prod or dev-ops-hotfix-prod
    2. No product stack -> dev-flow-pipeline-status
    3. Parallel delivery: max active reached -> blocked-max-active
    4. Parallel delivery: lane owned by other -> blocked-lane-conflict
    5. Todo + no branch -> dev-flow-start-ticket
    6. In Progress with worktree reuse -> dev-flow-implement-ticket
    7. In Progress + branch + no PR -> dev-flow-implement-ticket
    8. Open PR exists -> dev-flow-implement-ticket (review loop)
    9. PR merged -> dev-ops-post-merge-deploy (check lane, missing artifact)
    10. Release tag conflict -> blocked-tag-conflict
    11. Missing Nexus artifact -> blocked-missing-artifact
    12. QA evidence present -> configured QA gate (check lane)
    13. QA failed -> dev-flow-file-qa-bug
    14. PROD requested + QA passed -> dev-ops-deploy-prod (check lane)
    15. Done with QA passed, no PROD request -> blocked-no-prod
    16. Unknown/ambiguous -> dev-flow-pipeline-status
    """

    # Priority 1: Incident / hotfix overrides normal routing
    if incident:
        return "dev-ops-rollback-prod"
    if hotfix:
        return "dev-ops-hotfix-prod"

    # Priority 2: No product stack selected
    if product_stack == "none":
        return "dev-flow-pipeline-status"

    # Priority 3: Parallel delivery checks
    if parallel_enabled:
        if max_active_reached:
            return "blocked-max-active"

    # Helper: check deployment lane conflict
    def _lane_is_blocked() -> bool:
        return parallel_enabled and lane_owner not in ("", "current-ticket", "self")

    # Priority 4: Ticket state routing
    if ticket_state == "todo":
        if not branch_exists:
            return "dev-flow-start-ticket"
        if parallel_enabled and worktree_exists:
            return "dev-flow-implement-ticket"
        return "dev-flow-implement-ticket"

    if ticket_state == "in progress" or ticket_state == "in_progress":
        if pr_exists and pr_merged:
            # Merged PR with release tag conflict
            if release_tag_conflict:
                return "blocked-tag-conflict"
            # Merged PR with missing Nexus artifact
            if not nexus_artifact_exists:
                return "blocked-missing-artifact"
            # Merged PR: check deployment lane
            if _lane_is_blocked():
                return "blocked-lane-conflict"
            return "dev-ops-post-merge-deploy"
        if pr_exists:
            # Open PR: review/fix loop
            return "dev-flow-implement-ticket"
        if parallel_enabled and worktree_exists:
            # Reuse existing worktree
            return "dev-flow-implement-ticket"
        if branch_exists:
            return "dev-flow-implement-ticket"
        return "dev-flow-pipeline-status"

    if ticket_state == "qa":
        if qa_evidence == "failed":
            return "dev-flow-file-qa-bug"
        if qa_evidence == "passed":
            # QA passed - check if PROD was explicitly requested
            if prod_requested:
                if _lane_is_blocked():
                    return "blocked-lane-conflict"
                return "dev-ops-deploy-prod"
            return "blocked-no-prod"  # QA passed but needs explicit PROD promotion
        # QA evidence present (e.g. "deployed"): check lane
        if _lane_is_blocked():
            return "blocked-lane-conflict"
        if not nexus_artifact_exists:
            return "blocked-missing-artifact"
        return "configured QA gate"

    if ticket_state == "done":
        # Done with QA passed + PROD requested
        if prod_requested:
            if _lane_is_blocked():
                return "blocked-lane-conflict"
            return "dev-ops-deploy-prod"
        return "blocked-no-prod"  # Needs explicit PROD request

    # Priority 5: Unknown/ambiguous state
    return "dev-flow-pipeline-status"


def _build_reasoning(
    ticket_state: str,
    branch_exists: bool,
    pr_exists: bool,
    pr_merged: bool,
    qa_evidence: str,
    product_stack: str,
    incident: bool,
    hotfix: bool,
    parallel_enabled: bool = False,
    max_active_reached: bool = False,
    lane_owner: str = "",
    prod_requested: bool = False,
    nexus_artifact_exists: bool = True,
    release_tag_conflict: bool = False,
    worktree_exists: bool = False,
    route: str = "",
) -> list[str]:
    """Build human-readable reasoning steps for the routing decision."""
    steps = []

    if incident:
        steps.append("PROD incident detected: routing to rollback.")
    if hotfix:
        steps.append("PROD hotfix requested: routing to hotfix workflow.")

    if product_stack == "none":
        steps.append("No product stack selected: routing to pipeline status.")
    elif product_stack == "selected":
        steps.append("Product stack is configured.")

    if ticket_state:
        steps.append(f"Ticket state: {ticket_state}.")
    if branch_exists:
        steps.append("Branch exists.")
    else:
        steps.append("No branch yet.")
    if pr_exists and pr_merged:
        steps.append("PR merged. Ready for post-merge deployment.")
    elif pr_exists:
        steps.append("PR is open. Routing to review/fix loop.")

    # Parallel delivery reasoning
    if parallel_enabled:
        steps.append(f"Parallel delivery is enabled.")
        if max_active_reached:
            steps.append("Max active tickets reached: cannot start new ticket.")
        if lane_owner and lane_owner not in ("", "current-ticket", "self"):
            steps.append(f"Deployment lane owned by '{lane_owner}'. This ticket is blocked.")
        elif lane_owner in ("current-ticket", "self"):
            steps.append("This ticket owns the deployment lane.")
        if worktree_exists:
            steps.append("Worktree exists. Reusing for implementation.")
    else:
        steps.append("Standard (non-parallel) delivery.")

    # Deployment qa_evidence reasoning
    if prod_requested:
        steps.append("Explicit PROD promotion requested.")
    if not nexus_artifact_exists:
        steps.append("Nexus artifact missing: blocking.")
    if release_tag_conflict:
        steps.append("Release tag conflict: blocking.")

    if qa_evidence == "passed":
        if prod_requested:
            steps.append("QA passed + PROD requested. Routing to PROD deploy.")
        else:
            steps.append("QA passed. Blocked on explicit PROD promotion request.")
    elif qa_evidence == "failed":
        steps.append("QA failed. Routing to bug filing.")
    elif qa_evidence == "deployed":
        steps.append("QA evidence exists. Routing to QA gate.")

    steps.append(f"Selected route: {route}.")
    return steps
