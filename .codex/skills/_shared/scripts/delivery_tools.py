"""Shared delivery helper reference.

Canonical runtime: ``python -m tools.sdd_cli dev-flow <subcommand> ...``.
"""

DELIVERY_MODES = [
    "ArtifactPaths",
    "CheckGitIgnored",
    "NextRcVersion",
    "ReadProjectProfile",
    "ReadDeliveryPolicy",
    "ExtractTicketKey",
    "ReadCoverageThreshold",
    "ReadCoberturaLineRate",
    "ValidateReleaseManifest",
    "CreateArtifactPointer",
    "ValidateTicketLock",
    "ValidateDeploymentLane",
    "ValidateParallelDeliveryDryRun",
    "InitializeWorkflowTelemetry",
    "AppendWorkflowTelemetry",
    "ReadWorkflowTelemetry",
    "ReadOpenProjectTimeTelemetry",
    "ResolveOpenProjectTimeActivity",
    "RenderOpenProjectTimeTelemetryComment",
    "RenderTicketComment",
    "UpdateReleaseManifest",
]


def collapse_stages() -> None:
    """Collapse repeated stage rows into earliest start and latest finish."""


WORKFLOW_COMMENT_TYPE = "WorkflowTiming"
WORKFLOW_TABLE = "| Stage | Outcome | Duration | Started UTC | Finished UTC |"
