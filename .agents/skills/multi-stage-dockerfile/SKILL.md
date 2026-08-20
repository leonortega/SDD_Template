---
name: multi-stage-dockerfile
description: 'Create optimized multi-stage Dockerfiles for any language or framework'
---

Your goal is to help me create efficient multi-stage Dockerfiles that follow best practices, resulting in smaller, more
secure container images.

## Multi-Stage Structure

- Use a builder stage for compilation, dependency installation, and other build-time operations
- Use a separate runtime stage that only includes what's needed to run the application
- Copy only the necessary artifacts from the builder stage to the runtime stage
- Use meaningful stage names with the `AS` keyword (e.g., `FROM node:18 AS builder`)
- Place stages in logical order: dependencies → build → test → runtime

## Base Images

- Start with official, minimal base images when possible
- Specify exact version tags to ensure reproducible builds (e.g., `python:3.11-slim` not just `python`)
- Consider distroless images for runtime stages where appropriate
- Use Alpine-based images for smaller footprints when compatible with your application
- Ensure the runtime image has the minimal necessary dependencies

## Layer Optimization

- Organize commands to maximize layer caching
- Place commands that change frequently (like code changes) after commands that change less frequently (like dependency
installation)
- Use `.dockerignore` to prevent unnecessary files from being included in the build context
- Combine related RUN commands with `&&` to reduce layer count
- Consider using COPY --chown to set permissions in one step

## Security Practices

- Avoid running containers as root - use `USER` instruction to specify a non-root user
- Remove build tools and unnecessary packages from the final image
- Scan the final image for vulnerabilities
- Set restrictive file permissions
- Use multi-stage builds to avoid including build secrets in the final image

## Performance Considerations

- Use build arguments for configuration that might change between environments
- Leverage build cache efficiently by ordering layers from least to most frequently changing
- Consider parallelization in build steps when possible
- Set appropriate environment variables like NODE_ENV=production to optimize runtime behavior
- Use appropriate healthchecks for the application type with the HEALTHCHECK instruction

## Workspace Monorepo & `file:` Dependencies (npm/Node)

When an app consumes `packages/<pkg>` via `file:` deps (repo layout
`apps/<appId>` + `packages/`, ADR-0002), the build context is the **repo root** and
these hardened rules apply — each one prevented a real CI failure:

- **Pin npm >= 11 in every stage** — `RUN npm install -g npm@11 --no-audit --no-fund`.
  npm 10.x (node:22-alpine) crashes on `file:` link deps (arborist
  `loadVirtual`/`extraneous`/`EUSAGE`).
- **Mirror the repo layout inside the image** — copy to
  `/app/apps/<appId>` + `/app/packages` (not a flat `/app`). npm resolves
  `file:` link targets via `relpath` against the lockfile; a flat layout yields
  `../packages/x` instead of the lockfile's `../../packages/x` and `npm ci`
  fails with `EMISSINGTARGET: Missing target in lock file`.
- **Use absolute COPY destinations** — `COPY apps/<appId>/package.json
  /app/apps/<appId>/`. A relative destination (`./apps/<appId>/`) resolves
  against the current `WORKDIR`; reordering `WORKDIR` (e.g. a hadolint
  DL3003 fix moving it above the COPY) silently drops the files into the wrong
  folder and `npm ci` fails with EUSAGE "no lockfile". Rebuild images after any
  Dockerfile lint fix.
- **Build shared packages to `dist/` first** — `WORKDIR /app/packages/<pkg>`
  then `npm ci && npm run build` before the app's tsc. Packages must ship compiled
  `dist/` (`exports`/`types` → `dist`, `files: ["dist"]`) so app tsc (NodeNext,
  `rootDir: src`) resolves them instead of pulling `.ts` into the app program.
- **Every consuming app Dockerfile must build the shared package — not just one app's.**
  When a shared package becomes a runtime `dependencies` entry of an app, that app's
  Dockerfile needs its own build step; an image that never builds the package fails at
  app `tsc` with `TS2307: Cannot find module '<pkg>'` (observed: web Dockerfile built
  `api-client`, dellop-api's did not — dev deploy failed until the step was added).
  Whenever a `file:` dependency is added or promoted to runtime use, audit **every**
  app Dockerfile that imports it; mirror the web app's working pattern, and verify with
  a local `docker build` + container boot/health check before pushing.
- **Classify shared deps by runtime need** — build-time-only packages (bundled by
  vite/webpack, e.g. a UI kit) go in `devDependencies` so the runtime stage stays
  lean; runtime-imported packages go in `dependencies`. The runtime stage runs
  `npm ci --omit=dev`.
- **Repo-root context ⇒ one root `.dockerignore`** — with the build context at
  the repo root, Docker only reads the root `.dockerignore`; per-app
  `.dockerignore` files are inert and must be removed.
