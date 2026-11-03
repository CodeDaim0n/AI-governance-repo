# 01. Keycloak

**Official product sources:** [Official site](https://www.keycloak.org/)

Identity and access management providing signed identities and access tokens for agents and reviewers.

## Role

Verified service-account JWT identity.

## Implementation

- Native integration: `fabric/enterprise/clients.py`.
- Interface: `Keycloak.verify / token`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `1` in `scripts/accept_all_components.py`.

## Acceptance operation

Obtain three native tokens; verify signature, issuer, audience and mapped principal.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`KEYCLOAK_URL, KEYCLOAK_ISSUER, KEYCLOAK_REALM`

The lab uses client-credential service accounts with hard-coded, signed principal mappings. A production immutable-subject mapping, rotation, revocation and delegated-user model must be qualified.

[View implementation](https://github.com/CodeDaim0n/governed-agent-fabric/blob/main/fabric/enterprise/clients.py) · [All components](catalogue.md)
