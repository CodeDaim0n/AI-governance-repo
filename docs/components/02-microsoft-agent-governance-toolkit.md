# 02. Microsoft Agent Governance Toolkit

**Official product sources:** [Official repository](https://github.com/microsoft/agent-governance-toolkit)

Runtime governance toolkit intercepting tool calls before they enter our centrally governed execution path.

## Role

Deterministic agent-side tool interception.

## Implementation

- Native integration: `fabric/microsoft_agt.py`.
- Interface: `govern wrapper`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `2` in `scripts/accept_all_components.py`.

## Acceptance operation

Allow one probe; deny an unlisted tool without invoking the function.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`AGT tool policy and authenticated actor binding`

AGT local allow never overrides a central denial. The gateway remains the sole route to target credentials.

[View implementation](https://github.com/CodeDaim0n/governed-agent-fabric/blob/main/fabric/microsoft_agt.py) · [All components](catalogue.md)
