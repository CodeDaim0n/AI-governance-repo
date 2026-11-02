# 14. PostgreSQL

## Role

Transactional business state, evidence and delivery receipts.

## Implementation

- Native integration: `fabric/enterprise/postgres.py`.
- Interface: `psycopg transactions and row locks`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `14` in `scripts/accept_all_components.py`.

## Acceptance operation

Read committed target actions, verify audit chain and inspect per-sink receipts.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`DATABASE_URL and scoped product/database roles`

The single global guard serializes the small synthetic workload. Production needs measured latency/capacity, appropriately scoped locks/roles, high availability and restoration tests.

[View implementation](https://github.com/CodeDaim0n/AI-governance-repo/blob/main/fabric/enterprise/postgres.py) · [All components](catalogue.md)
