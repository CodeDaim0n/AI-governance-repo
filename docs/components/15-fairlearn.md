# 15. Fairlearn

**Official product sources:** [Official site](https://fairlearn.org/)

Responsible-AI evaluation library calculating group-outcome differences and producing versioned validation evidence.

## Role

Actual fairness metric computation.

## Implementation

- Native integration: `fabric/enterprise/evaluate.py`.
- Interface: `MetricFrame with selection_rate`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `15` in `scripts/accept_all_components.py`.

## Acceptance operation

Compute group metrics from a synthetic fixture and publish evaluation to MLflow.

## Current evidence

The isolated Fairlearn-to-MLflow HTTP path was exercised successfully, including candidate write/read-back and rejection of an unapproved release. See `results/local-native-evaluation.json`. The full native stack has not run in this environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Interpretation

The eight synthetic records only prove the MetricFrame/evaluation pipeline runs. They provide no evidence of fair lending, representativeness, statistical power or customer-outcome quality.

## Configuration and deployment notes

`Authorized evaluation dataset and MLflow configuration`

Fixture metrics exercise real Fairlearn code but do not establish fair lending or independent model validation. A representative governed dataset is a separate requirement.

[View implementation](https://github.com/CodeDaim0n/governed-agent-fabric/blob/main/fabric/enterprise/evaluate.py) · [All components](catalogue.md)
