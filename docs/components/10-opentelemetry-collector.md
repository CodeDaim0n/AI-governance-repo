# 10. OpenTelemetry Collector

## Role

Minimized exported execution spans.

## Implementation

- Native integration: `fabric/enterprise/telemetry.py`.
- Interface: `OTLP HTTP /v1/traces`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `10` in `scripts/accept_all_components.py`.

## Acceptance operation

Observe a real exported governed-action span and check bearer tokens are absent.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`OTEL_ENDPOINT and private collector evidence volume`

Only bounded outcome attributes are recorded. Exported spans are checked separately from liveness; product names, prompts, tokens or source records must not become arbitrary trace labels.

[View implementation](https://github.com/CodeDaim0n/AI-governance-repo/blob/main/fabric/enterprise/telemetry.py) · [All components](catalogue.md)
