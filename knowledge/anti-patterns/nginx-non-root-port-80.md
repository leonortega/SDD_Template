# Anti-pattern: nginx:alpine non-root on port 80

## Problem

nginx:alpine requires root to:
- Bind to port 80 (privileged port)
- Write to `/run/nginx.pid`

Setting `USER <non-root>` causes nginx to fail with `bind() to 0.0.0.0:80 failed (13: Permission denied)`.

## Checkov conflict

- **CKV_DOCKER_3**: Requires a `USER` instruction → add `USER root` ✓
- **CKV_DOCKER_8**: Requires last USER is not root → `USER root` fails ✗

These two rules contradict for nginx:alpine containers that bind port 80.

## Correct approach

Use `USER root` in the Dockerfile. nginx:alpine's master process needs root for port 80 and PID file. The nginx master drops privileges internally for worker processes via the `user` directive in `nginx.conf`.

```dockerfile
FROM nginx:alpine
USER root
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK ... CMD wget -qO- http://localhost/health || exit 1
```

## If CKV_DOCKER_8 must pass

Use port 8080 + K8s Service targetPort mapping:
- `listen 8080;` in nginx.conf
- `USER 1001` (non-root) in Dockerfile
- K8s Service: `port: 80, targetPort: 8080`

This is the standard production pattern but introduces port-change risk if migrating from port 80.

## Recommendation

For nginx:alpine in this repo: use `USER root` and skip CKV_DOCKER_8. The check is a false positive for containers that must bind privileged ports.
