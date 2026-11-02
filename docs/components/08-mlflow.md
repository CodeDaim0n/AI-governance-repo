# 08. MLflow

## Role

Versioned evaluation, candidate and approved release.

## Implementation

- Native integration: `fabric/enterprise/clients.py`.
- Interface: `MlflowClient API`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `8` in `scripts/accept_all_components.py`.

## Acceptance operation

Publish candidate; authorize lab reviewer promotion; verify approved alias and expiry.

## Current evidence

The isolated Fairlearn-to-MLflow HTTP path was exercised successfully, including candidate write/read-back and rejection of an unapproved release. See `results/local-native-evaluation.json`. The full native stack has not run in this environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`MLFLOW_URL, MODEL_NAME, MODEL_TENANT, FAIRNESS_MAX_DIFFERENCE`

Evaluation creates a candidate. The scoped reviewer route promotes a synthetic release with expiry; an unapproved or expired candidate cannot satisfy runtime validation.

[View implementation](https://github.com/CodeDaim0n/AI-governance-repo/blob/main/fabric/enterprise/clients.py) · [All components](catalogue.md)
