# 11. Prometheus and Alertmanager

## Role

Metrics, rule evaluation and authenticated alert delivery.

## Implementation

- Native integration: `fabric/enterprise/telemetry.py`.
- Interface: `Prometheus query and Alertmanager alerts APIs`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `11` in `scripts/accept_all_components.py`.

## Acceptance operation

Read scraped decisions and deliver a synthetic alert into the acknowledged audit path.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`Prometheus scrape/rule files and authenticated Alertmanager receiver`

Dependency failures and delivery backlog are monitored. Alerts are recorded for investigation; a metric label cannot independently grant administrator stop authority.

[View implementation](https://github.com/CodeDaim0n/AI-governance-repo/blob/main/fabric/enterprise/telemetry.py) · [All components](catalogue.md)
