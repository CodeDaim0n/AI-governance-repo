# 04. OpenFGA

**Official product sources:** [Official site](https://openfga.dev/)

Fine-grained authorization service deciding whether a particular agent may act on a particular record.

## Role

Record relationship authorization.

## Implementation

- Native integration: `fabric/enterprise/clients.py`.
- Interface: `POST /stores/{id}/check`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `4` in `scripts/accept_all_components.py`.

## Acceptance operation

Allow assigned case and deny a cross-case relationship.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`FGA_URL, FGA_TOKEN, FGA_STORE_ID, FGA_MODEL_ID`

The lab model exercises direct case assignment. A complete delegating-user/agent/task permission intersection is still required for production delegation.

[View implementation](https://github.com/CodeDaim0n/AI-governance-repo/blob/main/fabric/enterprise/clients.py) · [All components](catalogue.md)
