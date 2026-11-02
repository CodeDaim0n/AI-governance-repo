# 18. Ollama and Qwen2.5

## Role

Local proposal generation without execution credentials.

## Implementation

- Native integration: `fabric/enterprise/clients.py`.
- Interface: `/api/pull and /api/generate`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `18` in `scripts/accept_all_components.py`.

## Acceptance operation

Run the actual model and parse a generated JSON response.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`OLLAMA_URL and OLLAMA_MODEL`

Only a JSON proposal is returned. The gateway rejects changes to caller-bounded intent and never accepts model-generated identity, source status, authority or approval.

[View implementation](https://github.com/CodeDaim0n/AI-governance-repo/blob/main/fabric/enterprise/clients.py) · [All components](catalogue.md)
