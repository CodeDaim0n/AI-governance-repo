# 12. DFIR-IRIS

**Official product sources:** [Official site](https://www.dfir-iris.org/)

Incident-response platform receiving customer-scoped alerts and supporting investigation, containment and recovery.

## Role

Native incident alert records.

## Implementation

- Native integration: `fabric/enterprise/clients.py`.
- Interface: `/alerts/filter and /alerts/add`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `12` in `scripts/accept_all_components.py`.

## Acceptance operation

Create an alert in the configured lab customer and inspect native success response.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`IRIS_URL, IRIS_TOKEN, IRIS_CUSTOMER_ID`

Use a dedicated authorized lab customer. The selected 2.4.29 release and customer-scope behavior require live qualification; do not reuse the older vulnerable release solely for convenience.

[View implementation](https://github.com/CodeDaim0n/AI-governance-repo/blob/main/fabric/enterprise/clients.py) · [All components](catalogue.md)
