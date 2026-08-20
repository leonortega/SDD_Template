# nginx Missing /api Proxy Rule

## Summary

Production nginx serving a Vite/React SPA must include a `location /api/` proxy_pass to the backend API. Vite's dev server handles this automatically, but the built nginx config does not.

## Problem

When a React SPA uses `fetch("/api/auth/login", ...)`, Vite's dev server proxies `/api` to the Express/FastAPI backend. In production (nginx serving the built `dist/`), there is no proxy — nginx returns 405 Not Allowed for POST requests to `/api/*`.

## Context

- Vite config (`vite.config.ts`) has `server.proxy["/api"]` → backend
- `apps/<webAppId>/nginx.conf` only has `location / { try_files... }` and `location /health`
- The SPA's `fetch("/api/...")` calls hit nginx, which has no upstream for `/api/`

## Root Cause

The nginx.conf was generated without the `/api/` proxy rule, either:
- Before the scaffold template included it
- Manually created without the proxy block
- Copied from a minimal SPA template that assumed a separate API domain

## Solution

Add to `apps/<webAppId>/nginx.conf`:

```nginx
resolver kube-dns.kube-system.svc.cluster.local valid=10s;

location /api/ {
    set $api_upstream http://<api-appId>:5000;
    proxy_pass $api_upstream;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

Order of `location` blocks does not affect nginx prefix matching (longest prefix wins), but placing `/api/` before `/` makes the intent clearer.

## Alternatives

- Use a separate API domain (e.g., `api.example.com`) — adds DNS/CORS complexity
- Serve everything from the API server — loses SPA caching benefits

## Limitations

- The proxy target (`http://<api-appId>:5000`) is namespace-scoped in K8s. Works automatically when web and API are in the same namespace.
- The `resolver` directive is K8s-specific. For non-K8s deployments, use a static upstream or Docker Compose service names.

## Related Documents

- `.agents/skills/dev-ops-configure-k8s/SKILL.md` — AI-driven Dockerfile/nginx generation includes the proxy rule

## Tags

- Type: Pattern
- Status: Active
- Last verified: 2026-08-20
