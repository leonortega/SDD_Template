# OpenProject Compose Needs Container SECRET_KEY_BASE

## Summary

OpenProject Docker images require the container env `SECRET_KEY_BASE`; mapping only `OPENPROJECT_SECRET_KEY_BASE` leaves the app using or rejecting the default.

## Problem

OpenProject rejects or ignores the default secret when the container key is not provided, breaking the app in Compose.

## Context

Config infra run on 2026-06-25; verified against `infra/openproject/compose.yml`, `.codex/skills/configure-dev-environment/SKILL.md`, OpenProject GHSA-r85r-gjq2-f83r, and OpenProject 17.3.2 release notes.

## Root Cause

The compose service exposed the host-style variable name without mapping it to the container key the image actually reads.

## Solution

Keep the ignored local env/template key `OPENPROJECT_SECRET_KEY_BASE`, but map it to the container key `SECRET_KEY_BASE` in Compose. For the current Trivy CLI DB refresh, use `trivy image --download-db-only`, not the old root-level `trivy --download-db-only`.

## Alternatives

Not recorded.

## Limitations

Local `.env` files remain ignored; the mapping must exist in the Compose file itself.

## Examples

- Compose env mapping: `SECRET_KEY_BASE: ${OPENPROJECT_SECRET_KEY_BASE:...}`.

## Related Documents

- `infra/openproject/compose.yml`
- `.codex/skills/configure-dev-environment/SKILL.md`

## Tags

- Type: Pattern
- Status: Active
- Source: config infra run on 2026-06-25
- Last verified: 2026-06-25
- openproject, compose, secrets, trivy
