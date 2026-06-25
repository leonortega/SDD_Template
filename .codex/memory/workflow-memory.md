# Workflow Memory

The repository keeps the configured delivery workflow but has no product implementation.

Current workflow:

```text
Ticket -> OpenSpec -> implementation after stack selection -> review -> artifact/deployment/QA gates after app targets exist -> PROD promotion
```

Do not run product build, test, deploy, or QA commands until the new product stack defines them.
