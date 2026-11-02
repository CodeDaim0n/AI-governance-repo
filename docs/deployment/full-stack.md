# Deploy the complete native stack

## Scope and prerequisites

This guide commissions **all 18 component groups** in a dedicated synthetic lab. It is not a production rollout procedure. The current build environment cannot execute it because it lacks a container daemon and Kubernetes/eBPF privileges.

Use a dedicated Linux host with a working Docker daemon and Compose plugin, Git, kind, kubectl, Helm, Syft, Grype and Cosign. A planning allowance of **32 GiB RAM and 80 GiB free disk** is recommended for the combined services and model; this is an estimate, not a measured capacity result. Cilium requires a compatible host kernel and eBPF privileges. Do not point these scripts at an enterprise production cluster.

## 1. Create the private configuration

```bash
python3 -m venv .venv-native
source .venv-native/bin/activate
python -m pip install -r requirements-enterprise.txt
python scripts/configure_full.py
python scripts/full_stack.py preflight
```

Configuration is generated under `.local/full/`, excluded from Git. It includes random credentials, a Keycloak lab realm and an authenticated Alertmanager receiver configuration. The script refuses to overwrite existing credentials. The private parent directory protects the files exposed read-only to containers.

Preflight must succeed before claiming a deployable host. It starts no services and reports concrete missing dependencies.

## 2. Resolve official vendor distributions

```bash
python scripts/full_stack.py vendors
```

CISO Assistant, DFIR-IRIS, OpenMetadata and GLPI have nontrivial upstream service topologies. The script checks out the specified official source ref, records its resolved commit, resolves the upstream Compose configuration and restricts published ports to loopback. CISO Assistant image tags are aligned to the chosen release. Other upstream dependencies remain visible in the resolved descriptors and must be qualified before production.

The resolved Compose files may contain credentials, so they remain private. This approach avoids presenting a guessed three-line container definition as a full product deployment.

## 3. Start the product infrastructure

```bash
python scripts/full_stack.py up-core
python scripts/full_stack.py up-vendors
python scripts/full_stack.py status
```

| Service group | Local administration endpoint |
| --- | --- |
| Keycloak | `http://localhost:8081` |
| OpenFGA | `http://localhost:8082` |
| OPA | `http://localhost:8181` |
| Temporal | gRPC `localhost:7233`, UI `http://localhost:8233` |
| MLflow | `http://localhost:5001` |
| OpenBao | `http://localhost:8200` |
| CISO Assistant API | `http://localhost:8002/api` |
| OpenMetadata | `http://localhost:8585` |
| DFIR-IRIS lab API | `http://localhost:8085` |
| GLPI | `http://localhost:8086` |
| Prometheus / Alertmanager | `http://localhost:9090` / `http://localhost:9093` |
| Ollama | `http://localhost:11434` |

These addresses expose development interfaces only on the lab host. Production requires approved TLS, identity, network and storage configuration. The development Temporal server and Keycloak `start-dev` mode are intentional lab choices, not recommended production deployments.

## 4. Provision product-native authorization

Copy `deploy/full/native-credentials.example.json` to `.local/full/native-credentials.json`, restrict it to the owner, and populate it through each product's supported administration procedure:

- **CISO Assistant:** create the lab administrator, scoped integration token, dedicated folder and risk assessment. Supply their actual identifiers; do not use an unrelated assessment.
- **OpenMetadata:** create a scoped integration JWT and supply the actual lab owner's user UUID. The bootstrap creates a synthetic custom-database service, tables and lineage; no business database password is ingested.
- **DFIR-IRIS:** supply the authorized API key and lab customer ID. The selected 2.4.29 release avoids the older alert/customer-assignment issue noted during research. Qualify all current advisories separately.
- **GLPI:** enable the supported REST v1 API and create scoped application/user tokens. Supply a service identifier or let bootstrap create the synthetic service record.

Native authorization is an explicit commissioning step, not a placeholder connector. The scripts fail when required tokens or owner identifiers are absent. Never paste these values into a public issue or commit them.

## 5. Commission integrations and a candidate model

```bash
PYTHONPATH=. python scripts/commission_native.py
python scripts/full_stack.py up-app
```

Commissioning performs real operations:

1. Initialize/unseal the dedicated OpenBao lab instance and create separate gateway, worker and dispatcher read policies.
2. Write role-specific secrets and issue separate tokens.
3. Create an OpenFGA store, relationship model and synthetic assignments.
4. Initialize PostgreSQL state with release approval disabled.
5. Create/read stable CISO Assistant risk records without changing accepted ratings.
6. Read/create the GLPI service and OpenMetadata entities and lineage.
7. Pull the selected Qwen model through Ollama.
8. Compute Fairlearn fixture metrics and publish an MLflow **candidate**, without automatically approving it.

The single-share lab unseal material and root token must remain private. A production deployment needs approved unseal/HSM arrangements, scoped service credentials, token renewal, backup and recovery controls.

## 6. Run agent isolation and release checks

```bash
python scripts/install_agent_sandbox.py
python scripts/supply_chain.py
```

The sandbox script uses the dedicated `fabric-governance` kind context. It installs Cilium, runs a non-root agent pod and verifies an actual before/after network restriction. Only gateway and identity ports are added on the private Docker bridge; vendor products and the database retain loopback-only bindings.

Set a private `COSIGN_PASSWORD` before the supply-chain command. It generates an SBOM for the built native image, rejects high/critical vulnerability findings and verifies an offline local signature. It does not claim transparency-log inclusion or independent builder provenance. If the gate fails, fix or qualify the dependency; do not label the component passed.

## 7. Run all 18 native acceptance operations

```bash
PYTHONPATH=. python scripts/accept_all_components.py
```

The suite obtains signed product identities, performs native read/write operations, exercises a workflow, checks monitoring delivery and consumes the actual isolation/signing receipts. It creates synthetic risks, tickets and alerts. It uses no mocked product responses. The synthetic reviewer account exercises the release gate; it does not stand in for an independent human validation decision in production.

The only complete success condition is `all_18_passed: true`. Missing configuration, failed calls, missing receipts or unavailable products must remain `BLOCKED` or `FAIL`.

## Stop and preserve state

```bash
python scripts/full_stack.py stop
```

This stops services without deleting volumes, risk records or evidence. No destructive `down -v` command is automated. Follow the [operations runbook](../runbooks/operations.md) for containment, reconciliation and recovery.
