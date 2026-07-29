# Grafana Dashboard-As-Code And Observability

Create and manage Grafana dashboards, Prometheus/Loki queries, alert rules, and correlate with Seq structured logs.

## Scope

This skill covers dashboard provisioning via YAML, panel/query authoring, alert rule definitions, Seq query authoring, and incident triage workflows.

## Grafana Dashboard Provisioning

Dashboards are defined as YAML files under `infra/monitoring/grafana/dashboards/`:

```yaml
apiVersion: 1
providers:
  - name: 'default'
    orgId: 1
    folder: 'Applications'
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
```

## Dashboard JSON Model (key sections)

```json
{
  "title": "Application Overview",
  "panels": [
    {
      "title": "Request Rate",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(http_requests_total[5m])",
          "legendFormat": "{{ route }}"
        }
      ]
    }
  ]
}
```

## Common PromQL Queries

| Query | Purpose |
|---|---|
| `rate(http_requests_total[5m])` | Request rate per second |
| `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` | p95 latency |
| `sum(rate(http_requests_total{status=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m]))` | Error ratio |
| `up{job=\"api\"}` | Target up/down |

## Alert Rules

```yaml
groups:
  - name: api-alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "API error rate above 5%"
```

## Seq Structured Log Queries

Seq uses SQL-like signal syntax:

```sql
SELECT @Message, @Level, @Timestamp, Application, RequestPath
FROM Stream
WHERE @Level = 'Error'
  AND @Timestamp > NOW() - 1h
```

Common Seq queries:
- **Error correlation**: `@Level = 'Error' AND Application = 'MyApp'`
- **Request tracing**: `@Message LIKE '%{requestId}%'`
- **Performance**: `@Duration > 10000`
- **Dependency failures**: `@ExceptionType LIKE '%HttpRequestException%'`

## Dozzle Usage Patterns

Dozzle provides real-time, raw container log streaming. Use it for:
- **Quick debugging**: Check if a container is actually running and producing output
- **Raw stdout/stderr**: When you need unfiltered output (Seq only stores structured logs)
- **Startup diagnostics**: Check container init logs that may not reach Seq yet
- **Crash loops**: See repeated crash output without Seq query overhead

When to reach for Dozzle vs Seq:
| Scenario | Tool | Why |
|---|---|---|
| Container not starting | **Dozzle** | Seq may not receive logs from a crashing container |
| Error with stack trace | **Seq** | Structured search, filtering, correlation IDs |
| Performance issue (latency) | **Grafana** → **Seq** | Metrics first, then dive into structured logs |
| Missing log output | **Dozzle** | Quick check if the app is actually logging to stdout |
| Complex multi-service flow | **Seq** | Structured queries across services |

## Correlation Pattern

When triaging incidents: Grafana for metrics → Seq for structured logs → Dozzle for raw container output.

1. **Grafana** detects the anomaly (high latency, error rate)
2. **Seq** finds the structured error logs with stack traces and correlation IDs
3. **Dozzle** provides raw container stdout/stderr for debugging

## References

- Grafana MCP: `grafana` server in `.vscode/mcp.json`
- Grafana provisioning docs: https://grafana.com/docs/grafana/latest/administration/provisioning/
- Seq query docs: https://docs.datalust.co/docs/query-language
- Infra config: `infra/monitoring/compose.yml`
