# Docker Desktop Deployment Adapter

This adapter handles deployment operations for Docker Desktop environments. It manages container lifecycle, image deployment, and environment configuration specific to Docker Desktop.

## Operations
- `deploy-artifact`: Push Docker images to Docker Desktop registry
- `apply-config`: Apply Docker Compose configurations
- `verify-config`: Check Docker Desktop environment health
- `health`: Run Docker Desktop health checks
- `record`: Log deployment events to local files

## Configuration
- Use Docker Desktop CLI commands for operations
- Store sensitive credentials in `.codex/client-tools.local.json`
- Reference Docker images via Docker Hub or local registry