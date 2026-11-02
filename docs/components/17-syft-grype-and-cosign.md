# 17. Syft, Grype and Cosign

**Official product sources:** [Syft](https://github.com/anchore/syft) · [Grype](https://github.com/anchore/grype) · [Cosign](https://github.com/sigstore/cosign)

Software-supply-chain tools inventorying built images, checking vulnerabilities and signing/verifying release artifacts.

## Role

Image inventory, vulnerability gate and offline signing.

## Implementation

- Native integration: `scripts/supply_chain.py`.
- Interface: `Native CLIs`.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `17` in `scripts/accept_all_components.py`.

## Acceptance operation

Generate an image SBOM, reject high/critical findings and verify its local signature.

## Current evidence

The expanded native path has not run successfully in the available environment. A native health response, import success or adapter contract test does not satisfy the acceptance operation. Consult `results/all-18-live.json` for the current recorded result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Signature scope

The lab verifies an offline local signature. It deliberately does not claim public transparency-log inclusion, independent builder provenance or production attestation.

## Configuration and deployment notes

`FABRIC_IMAGE, native CLIs and a private COSIGN_PASSWORD`

The image vulnerability gate must succeed before signing. Offline local signatures do not establish transparency-log inclusion or trusted-builder provenance. Receipts are bound to deployment and source.

[View implementation](https://github.com/CodeDaim0n/governed-agent-fabric/blob/main/scripts/supply_chain.py) · [All components](catalogue.md)
