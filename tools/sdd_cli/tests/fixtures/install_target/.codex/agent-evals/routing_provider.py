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

    # Evaluate routing logic
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

    inputs = {
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
    }

    reasoning = _build_reasoning(inputs, route)

    result = {
        "route": route,
        "reasoning": reasoning,
        "inputs": inputs,
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

    Priority order:
    1. Incident/hotfix — overrides everything
    2. No product stack — pipeline status
    3. Parallel max capacity — blocked
    4. Ticket state routing (todo → in progress → qa → done)
    """

    # Priority 1: Incident / hotfix overrides normal routing
    if incident:
        return "dev-ops-rollback-prod"
    if hotfix:
        return "dev-ops-hotfix-prod"

    # Priority 2: No product stack selected
    if product_stack == "none":
        return "dev-flow-pipeline-status"

    # Lane blocked helper
    lane_blocked = parallel_enabled and lane_owner not in ("", "current-ticket", "self", "none")

    # Priority 3: Parallel delivery max capacity
    if parallel_enabled and max_active_reached:
        return "blocked-max-active"

    # Priority 4: Ticket state routing
    if ticket_state == "todo":
        return "dev-flow-start-ticket" if not branch_exists else "dev-flow-implement-ticket"

    if ticket_state in ("in progress", "in_progress"):
        if not branch_exists:
            return "dev-flow-pipeline-status"
        if pr_merged:
            if release_tag_conflict:
                return "blocked-tag-conflict"
            if not nexus_artifact_exists:
                return "blocked-missing-artifact"
            if lane_blocked:
                return "blocked-lane-conflict"
            return "dev-ops-post-merge-deploy"
        if branch_exists:
            return "dev-flow-implement-ticket"
        return "dev-flow-pipeline-status"

    if ticket_state == "qa":
        if qa_evidence == "failed":
            return "dev-flow-file-qa-bug"
        if qa_evidence == "passed":
            if lane_blocked:
                return "blocked-lane-conflict"
            return "dev-ops-deploy-prod" if prod_requested else "blocked-no-prod"
        if lane_blocked:
            return "blocked-lane-conflict"
        if not nexus_artifact_exists:
            return "blocked-missing-artifact"
        return "configured QA gate"

    if ticket_state == "done":
        if lane_blocked:
            return "blocked-lane-conflict"
        return "dev-ops-deploy-prod" if prod_requested else "blocked-no-prod"

    # Priority 5: Unknown/ambiguous state
    return "dev-flow-pipeline-status"


def _build_reasoning(inputs: dict, route: str) -> list[str]:
    """Build compact reasoning steps for the routing decision."""
    steps = []
    if inputs.get("incident"):
        steps.append("PROD incident: rollback.")
    if inputs.get("hotfix"):
        steps.append("PROD hotfix: hotfix workflow.")
    if inputs.get("productStack") == "none":
        steps.append("No product stack: pipeline status.")

    state = inputs.get("ticketState", "")
    if state:
        steps.append(f"Ticket state: {state}.")
    if inputs.get("prMerged"):
        steps.append("PR merged.")
    if inputs.get("parallelEnabled"):
        lane = inputs.get("laneOwner", "")
        if lane and lane not in ("", "current-ticket", "self", "none"):
            steps.append(f"Lane blocked: owned by {lane}.")
    if inputs.get("qaEvidence"):
        steps.append(f"QA evidence: {inputs['qaEvidence']}.")

    steps.append(f"Route: {route}.")
    return steps
