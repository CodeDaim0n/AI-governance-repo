# 16. Kubernetes and Cilium

**Official product sources:** [Kubernetes](https://kubernetes.io/) · [Cilium](https://cilium.io/)

Workload and network-security platforms isolating the agent and restricting its permitted network routes.

## Role

Agent isolation with explicit egress.

## Implementation

- Native integration: `scripts/install_agent_sandbox.py`.
- Interface: `kind, Helm, Kubernetes and CiliumNetworkPolicy`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `16` in `scripts/accept_all_components.py`.

## Acceptance operation

Show a reachable target becomes blocked after policy while gateway remains reachable.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`Dedicated fabric-governance kind context and private bridge gateway`

The agent pod has no Kubernetes service-account token, host network or target credentials. Isolation receipts must match the commissioned deployment ID and source commit.

[View implementation](https://github.com/CodeDaim0n/AI-governance-repo/blob/main/scripts/install_agent_sandbox.py) · [All components](catalogue.md)
