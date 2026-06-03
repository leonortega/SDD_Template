# Agent Workflow Evals

This directory defines lightweight evaluation cases for SDLC agent behavior. These evals measure whether agents choose the correct workflow path, tool boundary, mutation gate, and handoff evidence before the code or deployment outcome is inspected.

The default cases live in `workflow-cases.json`. Local run output belongs in ignored `results.local.json` and must not contain secrets, tokens, cookies, credential-bearing URLs, or raw tool payloads with sensitive values.

## Evaluation Focus

- `route`: the agent chooses the correct skill or workflow stage.
- `tool-selection`: the agent calls the right deterministic helper or external system.
- `argument-precision`: ticket keys, PR numbers, commit SHAs, artifact paths, release versions, and evidence paths match the active context.
- `mutation-gate`: the agent stops before unsafe Plane, Git, Gitea, Nexus, Azure, tag, or deployment mutation.
- `handoff`: the final status preserves the required workflow context, validation, blockers, assumptions, docs, and memory outcome.
- `risk-depth`: the agent chooses compact or full workflow depth correctly, including ticket readiness, workload forecast, adversarial review, and installed-skill index behavior.

## Usage

Use these cases as fixtures for manual audits, retrospective prompts, or future automated eval runners. A passing delivery run should satisfy the relevant case expectations without relying on chat history or unstated assumptions.
