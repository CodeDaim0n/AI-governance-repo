# 09. OpenBao

**Official product sources:** [Official site](https://openbao.org/)

Secrets-management platform separating credential access for the gateway, workflow worker and evidence dispatcher.

## Role

Separated runtime secret access.

## Implementation

- Native integration: `fabric/enterprise/clients.py`.
- Interface: `KV v2 /v1/secret/data/fabric/{role}`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `9` in `scripts/accept_all_components.py`.

## Acceptance operation

Read gateway secrets and prove worker secret path inaccessible to the gateway token.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Secret separation

Gateway, workflow worker and dispatcher read different OpenBao paths using different tokens. The single-share lab unseal record is private commissioning material, not a production key-management design. Renewal, recovery and approved unseal arrangements must be configured for operation.

## Configuration and deployment notes

`BAO_URL and separate gateway, worker and dispatcher tokens`

Roles read distinct paths. The lab token duration is 24 hours and automatic renewal is not supplied. Keep lab root/unseal material offline and qualify production key custody.

[View implementation](https://github.com/CodeDaim0n/governed-agent-fabric/blob/main/fabric/enterprise/clients.py) · [All components](catalogue.md)
