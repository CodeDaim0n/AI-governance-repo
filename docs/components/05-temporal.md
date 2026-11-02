# 05. Temporal

**Official product sources:** [Official site](https://temporal.io/)

Durable workflow engine maintaining process progress, human approval waits and bounded retries.

## Role

Durable workflow, bounded retries and approval waits.

## Implementation

- Native integration: `fabric/enterprise/workflows.py`.
- Interface: `Workflow signals and activities`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `5` in `scripts/accept_all_components.py`.

## Acceptance operation

Execute a native workflow through the protected gateway and inspect its result.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`TEMPORAL_ADDRESS, GATEWAY_URL and worker OpenBao token`

The dedicated worker is delegated only to agent-a. Activities obtain tokens outside workflow history. The development server is persisted for the lab but is not an HA production topology.

[View implementation](https://github.com/CodeDaim0n/AI-governance-repo/blob/main/fabric/enterprise/workflows.py) · [All components](catalogue.md)
