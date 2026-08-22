# Health Response Contract

## Standard

All services must return the same health response format:

```json
{"status": "ok"}
```

## Why

The CI health gate in `package-deploy.yml` checks for `status == "ok"`. If any service returns a different value (e.g., `"healthy"`), the health gate fails and blocks deployment.

## Implementation

### Flask (tkp-api)

```python
@app.route("/health")
def health():
    return jsonify({"status": "ok"})
```

### Nginx (tkp-web)

```nginx
location /health {
    return 200 '{"status":"ok"}';
    add_header Content-Type application/json;
}
```

### Tests

Update test assertions to match:

```python
def test_health_returns_200(client):
    response = client.get("/health")
    data = response.get_json()
    assert data["status"] == "ok"  # NOT "healthy"
```

## Validation

The health probe at `http://localhost:8090/health` aggregates all service health endpoints. All must return `status=ok`.

## Related

- PR #16 — health response mismatch fix
- `infra/monitoring/health_probe.py` — health probe service
- `.gitea/workflows/package-deploy.yml` — CI health gate
