# 13. GLPI

**Official product sources:** [Official site](https://www.glpi-project.org/en/)

IT service-management and asset platform linking workflows to owned services and trackable remediation tickets.

## Role

Service inventory and remediation tickets.

## Implementation

- Native integration: `fabric/enterprise/clients.py`.
- Interface: `REST v1 initSession, Computer and Ticket`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `13` in `scripts/accept_all_components.py`.

## Acceptance operation

Read a dedicated synthetic service and create a remediation ticket.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`GLPI_URL, GLPI_APP_TOKEN, GLPI_USER_TOKEN, GLPI_SERVICE_ID, GLPI_ENTITY_ID`

The inventory read checks entity scope. Tickets contain minimized synthetic investigation references; production notification and API quotas must be qualified.

[View implementation](https://github.com/CodeDaim0n/governed-agent-fabric/blob/main/fabric/enterprise/clients.py) · [All components](catalogue.md)
