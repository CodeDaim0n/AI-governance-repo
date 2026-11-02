# 06. CISO Assistant Community

## Role

Risk register and evidence records.

## Implementation

- Native integration: `fabric/enterprise/clients.py`.
- Interface: `/api/risk-scenarios/ and /api/evidences/`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `6` in `scripts/accept_all_components.py`.

## Acceptance operation

Create/read back 12 stable risk references; never auto-accept or overwrite owner ratings.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Risk ownership

The agent creates a proposed risk and attaches evidence. It cannot accept risk, change an owner-approved rating or close treatment solely because a technical test passed. The lab requires an explicitly provisioned folder and assessment; it does not silently select an unrelated organizational register.

## Configuration and deployment notes

`CISO_URL, CISO_TOKEN, CISO_FOLDER_ID, CISO_ASSESSMENT_ID`

Local scope checks prevent reusing a matching risk reference from a different assessment. Risk/control/evidence links are synchronized; accepted ratings are not overwritten.

[View implementation](https://github.com/CodeDaim0n/AI-governance-repo/blob/main/fabric/enterprise/clients.py) · [All components](catalogue.md)
