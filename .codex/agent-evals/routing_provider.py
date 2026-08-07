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

# Explicit workflow-stage request types that map directly to a route,
# mirroring the Workflow Stage Routing matrix in AGENTS.md. An explicit
# user request for a stage wins over state-based ticket routing.
EXPLICIT_REQUEST_ROUTES = {
    "continue-implementation": "dev-flow-continue-implementation",
    "propose-change": "dev-flow-propose-change",
    "pr-review": "dev-flow-pr-review-agent",
    "pr-review-feedback": "dev-flow-pr-review-feedback-loop",
    "explore-change": "dev-flow-explore-change",
    "implement-multiple-tickets": "dev-flow-parallel-ticket-coordinator",
    "scaffold-project": "dev-flow-scaffold-project",
    "verify-change": "dev-flow-verify-change",
    "archive-change": "dev-flow-archive-change",
    "dashboard-update": "grafana-board-update",
    "retrospective-audit": "dev-flow-retrospective-audit",
    "docs-knowledge-maintenance": "docs-knowledge-maintenance",
    "deploy-qa": "dev-ops-deploy-qa",
}


# Frontend stack markers that activate frontend-design skills during
# implementation (mirrors the stack-mapping table in
# .codex/skills/dev-flow-implement-ticket/SKILL.md). Any web frontend gets
# playwright, playwright-interactive, and impeccable.
FRONTEND_STACK_MARKERS = (
    "react", "vue", "svelte", "angular", "next", "nuxt",
    "astro", "frontend", "typescript", "javascript", "web",
)


def _activated_skills_for_stack(route: str, product_stack: str) -> list[str]:
    """Return domain skills the implementation stage would activate for the stack.

    Mirrors the stack-mapping table in dev-flow-implement-ticket/SKILL.md:
    implementation-stage routes on a frontend stack activate the frontend
    design skill (impeccable) plus browser-testing skills. Non-frontend
    stacks and non-implementation routes activate nothing extra.
    """
    if route not in ("dev-flow-implement-ticket", "dev-flow-continue-implementation"):
        return []
    stack = product_stack.strip().lower()
    if not stack or stack == "none":
        return []
    is_frontend = any(marker in stack for marker in FRONTEND_STACK_MARKERS)
    if not is_frontend:
        return []
    return ["playwright", "playwright-interactive", "impeccable"]


def _review_outcome(
    pr_exists: bool,
    pr_merged: bool,
    pr_validation_status: str,
) -> dict[str, Any] | None:
    """Model the review gate for an open PR per dev-flow-pr-review-agent.

    Mirrors the CI-in-loop rule enforced in the skills: a red, pending, or
    unreadable PR Validation run on the current head is a BLOCKER finding
    (stable id CI-001) and keeps the `codex-reviewed` clean marker off, so
    the PR stays blocked on the CI gate until the run is green. Only an
    open    PR (exists, not merged) has a review gate; merged or absent PRs
    return None (gate not applicable). Unset status defaults to "unknown"
    (fail-closed), matching the skill rule that an undetermined status keeps
    `codex-reviewed` off; legacy tests that predate the gate assert only the
    route, so they are unaffected.
    """
    if not pr_exists or pr_merged:
        return None
    if pr_validation_status == "green":
        return {"codexReviewed": True, "findings": []}
    if pr_validation_status == "red":
        reason = "PR Validation run failed: at least one step is red"
    elif pr_validation_status == "pending":
        reason = "PR Validation run still running/pending"
    else:
        reason = "PR Validation run status could not be determined"
    return {
        "codexReviewed": False,
        "findings": [
            {
                "id": "CI-001",
                "severity": "BLOCKER",
                "source": "pr-validation",
                "summary": reason,
            }
        ],
    }


def _refinement_outcome(
    route: str,
    refinement_user_asked: bool,
) -> dict[str, Any] | None:
    """Model the ticket-refinement gate per dev-flow-start-ticket step 7.

    Refinement runs at least 1 grill-with-docs cycle (at most 4) and ALWAYS
    asks the user for extra info — even when the ticket seems complete —
    before the curated IA block is written. The gate applies only on the
    ``dev-flow-start-ticket`` route (a Todo ticket with no branch): until the
    user has been asked, the IA block must not be written (``blocked``).
    Other routes return None (gate not applicable), mirroring how the review
    gate returns None once a PR is merged.
    """
    if route != "dev-flow-start-ticket":
        return None
    if refinement_user_asked:
        return {
            "userAsked": True,
            "complete": True,
            "blocked": False,
            "blocker": None,
        }
    return {
        "userAsked": False,
        "complete": False,
        "blocked": True,
        "blocker": (
            "Refinement must ask the user for extra info before writing the "
            "IA block (at least 1 grill-with-docs cycle, at most 4)."
        ),
    }


def _capture_outcome(
    route: str,
    capture_mode: str,
) -> dict[str, Any] | None:
    """Model the Durable Learning Capture Gate for the completion stages.

    Mirrors the gate wired into dev-flow-archive-change, dev-ops-hotfix-prod, and
    dev-flow-retrospective-audit: after the stage completes, run the classifier
    (knowledge-search classify), update only the classifier-selected candidate
    docs/knowledge files via docs-knowledge-maintenance, and record the canonical
    markers. The gate applies only on those three routes; other routes return None
    (gate not applicable), mirroring the review/refinement gates.

    The retrospective is mode-aware: read-only/proposal audits and the automatic
    post-prod-ticket-release path must NOT mutate files (advisory only — the
    classifier candidates are reported as recommendations). Apply mode updates
    the candidate files and records the update markers.
    """
    if route not in (
        "dev-flow-archive-change",
        "dev-ops-hotfix-prod",
        "dev-flow-retrospective-audit",
    ):
        return None
    advisory = (
        route == "dev-flow-retrospective-audit"
        and capture_mode != "apply"
    )
    if advisory:
        return {
            "applicable": True,
            "classifierRun": True,
            "applied": False,
            "scope": "advisory-only",
            "markers": ["Docs updated: none", "Knowledge updated: none"],
        }
    return {
        "applicable": True,
        "classifierRun": True,
        "applied": True,
        "scope": "classifier-selected-candidates",
        "markers": ["Docs updated: <files>", "Knowledge updated: <files>"],
    }


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
    branch_exists = (
        str(vars_data.get("branchExists", "false")).strip().lower() == "true"
    )
    pr_exists = str(vars_data.get("prExists", "false")).strip().lower() == "true"
    pr_merged = str(vars_data.get("prMerged", "false")).strip().lower() == "true"
    qa_evidence = str(vars_data.get("qaEvidence", "")).strip().lower()
    product_stack = str(vars_data.get("productStack", "")).strip().lower()
    incident = str(vars_data.get("incident", "false")).strip().lower() == "true"
    hotfix = str(vars_data.get("hotfix", "false")).strip().lower() == "true"
    # PR Validation (Gitea Actions) run status for the current head.
    # green | red | pending | unknown — defaults to "unknown" (fail-closed):
    # an unspecified run keeps `codex-reviewed` off, mirroring the skill rule
    # that an undetermined status blocks the clean marker. Legacy tests that
    # predate the gate assert only `route`, so they are unaffected.
    pr_validation_status = str(
        vars_data.get("prValidationStatus", "unknown")
    ).strip().lower()

    # --- PARALLEL DELIVERY & DEPLOYMENT LANE VARS ---
    # `parallelEnabled` is an eval scenario input that models "the AI determined
    # the user asked to implement more than one ticket". There is no real
    # parallelDelivery.enabled config gate — the coordinator decides by ticket
    # count. The eval uses this var to exercise lane/capacity routing.
    parallel_enabled = (
        str(vars_data.get("parallelEnabled", "false")).strip().lower() == "true"
    )
    max_active_reached = (
        str(vars_data.get("maxActiveReached", "false")).strip().lower() == "true"
    )
    lane_owner = str(vars_data.get("laneOwner", "")).strip().lower()
    prod_requested = (
        str(vars_data.get("prodRequested", "false")).strip().lower() == "true"
    )
    nexus_artifact_exists = (
        str(vars_data.get("nexusArtifactExists", "true")).strip().lower() == "true"
    )
    release_tag_conflict = (
        str(vars_data.get("releaseTagConflict", "false")).strip().lower() == "true"
    )
    worktree_exists = (
        str(vars_data.get("worktreeExists", "false")).strip().lower() == "true"
    )
    # --- INFRASTRUCTURE VALIDATION VARS ---
    infra_validation_failed = (
        str(vars_data.get("infraValidationFailed", "false")).strip().lower() == "true"
    )
    # --- EXPLICIT WORKFLOW-STAGE REQUEST VARS ---
    request_type = str(vars_data.get("requestType", "")).strip().lower()
    # State-driven resume: user asks to automatically continue the ticket workflow
    # without knowing the current step (dev-flow-continue-implementation orchestrator).
    resume_requested = (
        str(vars_data.get("resumeRequested", "false")).strip().lower() == "true"
    )
    # User approval for the QA deployment (dev-ops-deploy-qa User Approval Gate).
    # False/unset = approval still pending: the agent verifies DEV and asks the
    # user before dispatching QA — never auto-approves. True = the user approved
    # and the QA deployment proceeds.
    qa_approved = (
        str(vars_data.get("qaApproved", "false")).strip().lower() == "true"
    )
    # Ticket refinement gate (dev-flow-start-ticket step 7): whether the
    # refinement has already asked the user for extra info. False/unset = the
    # grill-with-docs cycles have not asked the user yet, so the curated IA
    # block must NOT be written. True = the user answered the clarifying
    # questions and refinement may proceed.
    refinement_user_asked = (
        str(vars_data.get("refinementUserAsked", "false")).strip().lower() == "true"
    )
    # Durable Learning Capture Gate mode (archive / hotfix / retrospective):
    # "apply" (default) updates the classifier-selected candidate files; the
    # retrospective also supports read-only / proposal / post-prod-ticket-release
    # modes, which are advisory only (candidates are recommendations, nothing is
    # written). Mirrors the mode-awareness in
    # dev-flow-retrospective-audit/SKILL.md section 3.5.
    capture_mode = str(vars_data.get("captureMode", "apply")).strip().lower()

    # Review gate: models dev-flow-pr-review-agent's CI-in-loop rule. A red,
    # pending, or unreadable PR Validation run is a BLOCKER finding and keeps
    # `codex-reviewed` off, so the PR stays blocked on the CI gate until the
    # run is green. Route is unaffected — the review/fix loop still runs.
    review = _review_outcome(
        pr_exists=pr_exists,
        pr_merged=pr_merged,
        pr_validation_status=pr_validation_status,
    )

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
        infra_validation_failed=infra_validation_failed,
        request_type=request_type,
        resume_requested=resume_requested,
        qa_approved=qa_approved,
    )

    # Ticket refinement gate: applies on the dev-flow-start-ticket route only.
    # Mirrors dev-flow-start-ticket step 7 — refinement runs at least 1
    # grill-with-docs cycle (at most 4) and ALWAYS asks the user for extra
    # info (even when the ticket seems complete) before the curated IA block
    # is written. The route is unchanged; the always-ask invariant is exposed
    # through the `refinement` gate object so eval cases can assert it.
    refinement = _refinement_outcome(route, refinement_user_asked)

    # Durable Learning Capture Gate: applies on archive / hotfix / retrospective
    # routes only. Mirrors the gate in those skills — run the classifier, update
    # only the classifier-selected candidate files via docs-knowledge-maintenance,
    # and record the canonical markers. Exposed as a `capture` gate object so
    # eval cases can assert the capture step survives routing regressions.
    capture = _capture_outcome(route, capture_mode)

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
        "infraValidationFailed": infra_validation_failed,
        "requestType": request_type,
        "resumeRequested": resume_requested,
        "prValidationStatus": pr_validation_status,
        "qaApproved": qa_approved,
        "refinementUserAsked": refinement_user_asked,
        "captureMode": capture_mode,
    }

    reasoning = _build_reasoning(inputs, route)
    if review and not review["codexReviewed"]:
        reasoning.append(
            "PR Validation run not green: review is blocked, codex-reviewed stays off."
        )

    result = {
        "route": route,
        "activatedSkills": _activated_skills_for_stack(route, product_stack),
        "review": review,
        "refinement": refinement,
        "capture": capture,
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
    infra_validation_failed: bool = False,
    request_type: str = "",
    resume_requested: bool = False,
    qa_approved: bool = False,
) -> str:
    """Determine the correct workflow route based on the delivery contract.

    Priority order:
    1. Incident/hotfix — overrides everything
    2. No product stack — pipeline status
    3. Parallel max capacity — blocked
    4. Ticket state routing (todo → in progress → qa → done)
    """

    # Priority 1: Infrastructure validation failure (e.g. NodePort collision)
    if infra_validation_failed:
        return "blocked-infra-validation"

    # Priority 2: Incident / hotfix overrides normal routing
    if incident:
        return "dev-ops-rollback-prod"
    if hotfix:
        return "dev-ops-hotfix-prod"

    # Priority 2.5: Explicit workflow-stage request maps directly to its skill.
    # The latest explicit user request is the highest authority in the routing
    # hierarchy, so it wins over ambient ticket state and missing-stack fallback.
    if request_type:
        explicit_route = EXPLICIT_REQUEST_ROUTES.get(request_type)
        if explicit_route:
            return explicit_route

    # Priority 3: No product stack selected
    if product_stack == "none":
        return "dev-flow-pipeline-status"

    # Lane blocked helper
    lane_blocked = parallel_enabled and lane_owner not in (
        "",
        "current-ticket",
        "self",
        "none",
    )

    # Priority 3: Parallel delivery max capacity
    if parallel_enabled and max_active_reached:
        return "blocked-max-active"

    # Priority 4: Ticket state routing
    if ticket_state == "todo":
        return (
            "dev-flow-start-ticket"
            if not branch_exists
            else "dev-flow-implement-ticket"
        )

    if ticket_state in ("in progress", "in_progress"):
        if not branch_exists:
            return "dev-flow-pipeline-status"
        # State-driven resume: an in-progress ticket with an existing branch that
        # the user asks to automatically continue routes to the orchestrator.
        if resume_requested:
            return "dev-flow-continue-implementation"
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
        if qa_evidence == "deployed":
            # QA is deployed and awaiting E2E validation.
            return "configured QA gate"
        if not nexus_artifact_exists:
            return "blocked-missing-artifact"
        # User Approval Gate (dev-ops-deploy-qa): QA is not deployed yet. The
        # agent verifies DEV and asks the user for approval before dispatching
        # the QA deployment — never auto-approves. Only an explicit approval
        # proceeds to the actual QA deploy route.
        return (
            "dev-ops-deploy-qa"
            if qa_approved
            else "dev-ops-deploy-qa-approval-gate"
        )

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
    request_type = inputs.get("requestType", "")
    if request_type:
        steps.append(f"Explicit request: {request_type}.")
    if inputs.get("resumeRequested"):
        steps.append("Resume requested: continue-implementation orchestrator.")
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
    if route == "dev-ops-deploy-qa-approval-gate":
        steps.append("QA not deployed: verify DEV, ask the user for approval.")
    if route == "dev-ops-deploy-qa" and inputs.get("qaApproved"):
        steps.append("User approved QA: dispatch the QA deployment.")
    if route == "dev-flow-start-ticket" and not inputs.get("refinementUserAsked"):
        steps.append(
            "Refinement: ask the user for extra info before writing the IA block "
            "(at least 1 grill-with-docs cycle, at most 4)."
        )
    if route in (
        "dev-flow-archive-change",
        "dev-ops-hotfix-prod",
        "dev-flow-retrospective-audit",
    ):
        mode = inputs.get("captureMode", "apply")
        if route == "dev-flow-retrospective-audit" and mode != "apply":
            steps.append(
                "Capture: classifier run, candidates are advisory only (no file changes)."
            )
        else:
            steps.append(
                "Capture: run classifier, update only the selected candidate files."
            )

    steps.append(f"Route: {route}.")
    return steps
