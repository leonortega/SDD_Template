---
name: configure-artifact-delivery
description: Configure Nexus artifact delivery and promotion for this repo, including Nexus service account guidance, artifact repository names, Gitea Actions secrets for Nexus, package/deploy workflow setup, and build-once promote-same-artifact release flow. Use when Codex needs to set up CI/CD artifact publishing or deployment promotion.
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
2. Ask for Nexus service account and repository names only when configuring artifact publishing.
3. When values are missing, explain how to create the Nexus raw hosted repository, create a Nexus service account, add Gitea Actions secrets, include official documentation links, and provide validation commands.
4. Guide the user to store Nexus credentials as Gitea Actions secrets.
5. Keep the release model: build once, upload artifact/checksum/commit metadata to Nexus, deploy/promote the same artifact.
