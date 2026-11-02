# 07. OpenMetadata

## Role

Data ownership, classification and lineage.

## Implementation

- Native integration: `fabric/enterprise/clients.py`.
- Interface: `/api/v1/tables and /api/v1/lineage`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `7` in `scripts/accept_all_components.py`.

## Acceptance operation

Read required owner/classification and verify a downstream lineage edge.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`METADATA_URL, METADATA_TOKEN, METADATA_TABLE_FQN, METADATA_REQUIRED_TAG`

The bootstrap uses a metadata-only custom database service. It does not ingest a source password or grant the agent data access. The runtime requires an owner and configured classification.

[View implementation](https://github.com/CodeDaim0n/AI-governance-repo/blob/main/fabric/enterprise/clients.py) · [All components](catalogue.md)
