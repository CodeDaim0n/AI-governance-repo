# 03. Open Policy Agent

**Official product sources:** [Official site](https://www.openpolicyagent.org/)

Policy engine evaluating deterministic allow/deny rules for actions, budgets, context and operational restrictions.

## Role

Business action/context policy.

## Implementation

- Native integration: `policies/credit.rego`.
- Interface: `POST /v1/data/fabric/decision`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `3` in `scripts/accept_all_components.py`.

## Acceptance operation

Check valid allow and kill-switch deny against the real policy service.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`OPA_DECISION_URL and policy bundle`

The logical policy version is checked; production also needs a verified signed bundle digest and controlled rollout.

[View implementation](https://github.com/CodeDaim0n/governed-agent-fabric/blob/main/policies/credit.rego) · [All components](catalogue.md)
