---
name: configure-artifact-delivery
description: Configure Nexus artifact delivery and promotion for this repo, including Nexus service account guidance, artifact repository names, Gitea Actions secrets for Nexus, package/deploy workflow setup, build-once promote-same-artifact release flow, ticket-gated DEV/QA/PROD deployment, QA RC versioning, and PROD artifact promotion.
---

# Configure Artifact Delivery

Read `.codex/skills/configure-dev-environment/references/nexus.md` before asking for values or applying changes.

Use the shared script at `.codex/skills/configure-dev-environment/scripts/configure_infra_tools.ps1`.

Safety:

- Do not print or store Nexus credentials in tracked files.
- Do not read Nexus initial admin password from Docker containers, mounted volumes, databases, or logs.
- Do not change the architecture to container-image deployment unless explicitly requested.

Workflow:

1. Run `AuditQualityGates` to verify package/deploy workflow presence.
2. Ask for Nexus service account, password/token, local Nexus URL, and repository name only when configuring artifact publishing or repository validation.
3. When values are missing, explain how to create the Nexus raw hosted repository, create a Nexus service account, add Gitea Actions secrets, include official documentation links, and provide validation commands.
4. Guide the user to store Nexus credentials as Gitea Actions secrets for CI and in ignored `.codex/client-tools.local.json` for local repository checks.
5. Keep the release model: build once, upload artifact/checksum/commit metadata to Nexus, deploy/promote the same artifact through DEV, QA, and PROD.
6. Ensure workflow setup includes `/health` checks for DEV/QA/PROD, `.codex/delivery-policy.json` ticket gating, `dev` push deployment for DEV/QA, `main` push deployment for PROD only, and PROD dispatch inputs `artifact_commit_sha`, `release_version`, and `source_rc_version`.
7. Ensure Plane comments record version lineage so humans can trace `artifact commit -> source RC -> final release` without inspecting Git/Nexus manually.
8. Ensure Nexus release manifests at `app/{commitSha}/release.json` carry machine-readable release, QA, PROD, monitoring, and rollback metadata.
