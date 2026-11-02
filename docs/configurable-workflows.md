# Configurable governance workflows

The configurable path separates workflow contracts, shared enforcement and target adapters. It generates a reviewable governance design and assessment, then executes supported operations through the same engine. Loading a JSON definition does not approve a deployment, provision an identity, grant a resource permission or register executable code.

The shipped credit and access examples use local synthetic targets. Their approval, schema, concurrency, isolation and evidence checks are exercised locally. The new native bindings require commissioning and acceptance against real products; previous credit-lab evidence does not establish their deployment readiness.

## Run and inspect the examples

From a Python 3.11+ checkout, install the package into a virtual environment:

```bash
python -m pip install -e .
python -m fabric.workflow_cli validate --workflow workflows/synthetic-credit.json --workflow workflows/it-access.json
python -m fabric.workflow_cli demo --workflow workflows/synthetic-credit.json --workflow workflows/it-access.json
python -m fabric.workflow_cli package --workflow workflows/synthetic-credit.json --workflow workflows/it-access.json --output results/workflow-package.json --report results/workflow-assessment.md --opa-data results/opa-data.json
```

The demo explicitly provisions disposable fixtures in a temporary database. Each workflow first waits for independent approval, executes after reviewer approval, and returns the same receipt on retry. It checks the effect count and audit chain. It performs no real lending, directory change or model inference.

The package contains the original validated definitions, twelve assessment sections, required adapter identifiers and an OPA deployment manifest. OPA entries are **disabled**, with no allowed tenants, until reviewed and configured by the deployment owner. Generated assessments preserve unknown owners, risks, applicability and validation. They do not assign a universal governance score or manufacture compliance evidence. A [generated example report](examples/configurable-assessment.md) illustrates the output.

## Workflow contract

Definitions live in `workflows/`. The strict schema supports `schema_version: 1`, workflow ID, version, description, a resource schema, resource freshness and a map of operations. An operation declares:

| Field | Meaning |
| --- | --- |
| `adapter` | Identifier in an operator-created adapter registry; never an import path or URL. |
| `parameters` | Bounded object with string, integer and boolean properties. Unknown properties are rejected; booleans do not count as integers. |
| `allowed_roles` | Roles allowed to propose this operation; the authenticated principal supplies its role. |
| `resource_checks` | All predicates must pass against authoritative stored resource attributes. |
| `approval.when` | Any listed predicate requires separate approval. An empty list imposes no extra approval predicate. |
| `approval.reviewer_roles` | Permitted reviewer roles; the same actor cannot approve their own action. |
| `approval.ttl_seconds` | Expiration for the exact stored approval. |
| `budgets` | Positive integer usage limits, aggregated across actors within workflow, operation and tenant; optional resource scope. These are lifetime counters, not rolling windows. |

Predicates support `eq`, `ne`, `in`, `not_in`, `gt`, `gte`, `lt` and `lte`. Ordered comparisons require integers. Unsupported operators, fields, duplicate JSON keys, nonfinite numbers and unknown workflow versions fail validation. Nested object/array parameters, arbitrary expression evaluation, rolling budgets and general graph execution are outside this version's supported contract; add a tested capability before using them.

The canonical action envelope is:

```json
{
  "workflow_id": "it-access",
  "operation": "grant_access",
  "resource_id": "employee-a",
  "parameters": {"permission": "admin", "duration_hours": 4, "justification": "Approved exercise"},
  "idempotency_key": "access-request-001"
}
```

Identity, tenant, resource facts, approval authority, target endpoints and configuration are not action fields. A content digest identifies the entire definition. Changing schema, policy or adapter binding invalidates deployment approval and old action approvals, even if someone forgets to change the human-readable version.

## Shared runtime and adapters

`ConfigurableFabric` in `fabric/runtime.py` handles multiple workflows in one database. It enforces tenant boundaries, current roles, source freshness, approved configuration, stop state, resource conditions, budgets, approval and exact idempotency. Approval binds the complete action, actor state, resource state, configuration digest and deployment approval version. Reviewer revocation and changed source/configuration invalidate its use. External policies can add restrictions and cannot override a built-in denial.

Identities, source facts and deployment approval are provisioned through trusted Python administration methods: `provision_principal`, `provision_resource`, `approve_workflow` and `revoke_principal`. These are deliberately absent from the agent HTTP API. Deployment owners must connect these methods to their authenticated administrative/source ingestion process. Demo provisioning is an explicit fixture helper, never service startup behavior.

Adapters implement `validate(operation)` and `apply(connection, context)` and are registered in code by the deployment operator. The two included adapters record synthetic effects in the current transaction. Effect, usage, consumed approval, audit and outbox commit together. Audit/outbox records carry hashes rather than raw target receipts; scoped execution records retain receipts. Audit chaining detects modification but is not an independently immutable archive.

**The current adapter contract supports transactional local targets.** A remote business API needs target idempotency, conditional writes, durable delivery and reconciliation before it can safely serve as an execution adapter. Do not add an HTTP call inside `apply` and assume database rollback can undo it. A new supported local operation needs configuration and, where its effect is new, an adapter; it does not require modifying all eighteen products.

## Authenticated HTTP and agent execution

Start a preprovisioned local SQLite instance:

```bash
python -m fabric.configurable_server --workflow workflows/synthetic-credit.json --workflow workflows/it-access.json --db .local/configurable.db --public-key .local/public.pem --synthetic-adapters
```

The server binds loopback and requires signed RS256 tokens using the existing lab identity profile. It does not seed or approve workflows. `--synthetic-adapters` explicitly enables the local example effects. A custom deployment entry point registers other reviewed adapters. Remote service use requires an authenticated TLS ingress and operational hardening.

| Route | Contract |
| --- | --- |
| `POST /inspect` | `{workflow_id, resource_id}`; authenticated read with source freshness and access checks. |
| `POST /execute` | `{action, approval_id?}`; governed direct execution. |
| `POST /approve` | `{actor, action}`; authenticated separate reviewer. |
| `POST /stop` | `{workflow_id, stopped}`; administrator for their tenant. |
| `POST /agent/tasks` | `{action, approval_id?}`; creates expiring, immutable task intent. |
| `GET /agent/tasks/{id}` | Task's owner receives its intent, generated tool schemas and recorded execution. |
| `POST /agent/inspect` | Task-bound read; send `X-Fabric-Task` header. |
| `POST /agent/execute` | Exact task action; inspection required; send `X-Fabric-Task`. |
| `POST /agent/tasks/{id}/approve` | Empty object; independent reviewer approval for that stored task. |

`ConfigurableAgent` in `fabric/configurable_agent.py` loads task-specific schemas and proposes `inspect_resource` and `execute_operation`. The task's identity and approved intent stay server-owned. A fabricated model success claim never substitutes for an executed gateway receipt. Tests use simulated model responses; no new live-model performance claim is made.

## Native bindings across eighteen component groups

Use `--backend postgres` with `DATABASE_URL`, `--keycloak-identity` for native identity, and `--native-authorities` with `FABRIC_NATIVE_BINDINGS` pointing to an administrator-owned binding file. Each loaded workflow must have exactly one binding. OPA and relationship authority are required in native-authority mode; metadata, model and inventory gates are explicitly selected. Missing selected dependencies deny execution.

`deploy/configurable/native-bindings.example.json` illustrates the binding shape; its placeholder identifiers and illustrative metric bounds require owner review. OPA uses `policies/configurable.rego` and a separately reviewed deployment manifest. Its response must identify the same approved configuration digest. FGA resource IDs are the canonical tuple digest returned by `NativeAuthorities.resource_key(workflow_id, tenant, resource_id)`, preventing ambiguous names or relationships from another scope. Selected metadata, model and inventory gates require complete explicit bindings, with no fallback to unrelated lab resources. Native integration transport and policy contracts have simulation tests; this is not complete-stack acceptance.

The model gate verifies a configured MLflow release prerequisite. The agent's inference model is configured separately; this gate alone does not attest that the actual served model bytes match that registry release. A commissioned deployment must bind and verify that provenance before making model assurance claims.

| Component group | Reusable capability and workflow-specific binding |
| --- | --- |
| 01 Keycloak | Existing identity provider; configure signed principal mapping and provision runtime roles separately. |
| 02 Microsoft AGT | `--agt` generates the interceptor allowlist from loaded operation definitions; the gateway still independently checks authority and effects. Same-process interception does not replace workload isolation. |
| 03 OPA | Generic deployment-manifest policy and configuration digest; workflow policy rules remain explicit packages. |
| 04 OpenFGA | Configurable subject/resource types and relation; scoped tuples supplied during commissioning. |
| 05 Temporal | `GovernedOperation` uses gateway decisions to wait for approval without monetary assumptions. Start requests must come from a trusted scoped application; the worker verifies its delegation. |
| 06 CISO Assistant | Existing scoped risk/control/evidence API; configure risk links and accountable records. |
| 07 OpenMetadata | Configurable entity type, entity name, classification tag and owner checks. |
| 08 MLflow | Configurable model and required metric bounds; independent promotion remains separate. |
| 09 OpenBao | Existing credential custody; operator-configured paths and policies. Secrets never enter workflow definitions. |
| 10 OpenTelemetry | Existing export pipeline; generic deployment instrumentation must use minimized fields and be verified. |
| 11 Prometheus / Alertmanager | Existing monitoring infrastructure; select service metrics, thresholds and routing for deployment. |
| 12 DFIR-IRIS | Existing incident client; scoped customer configuration and correlation. |
| 13 GLPI | Configurable service resource type, ID and entity; existing remediation API. |
| 14 PostgreSQL | Same generic runtime schema with the existing serialized transaction bridge; `cfg_` tables preserve the original lab. |
| 15 Fairlearn | Supplied dataset evaluation and metric configuration; process-specific evaluation remains required. |
| 16 Kubernetes / Cilium | Reuse deployment/security patterns; adapt gateway command, service accounts and allowed routes, then test isolation. Existing manifests target the legacy lab. |
| 17 Syft / Grype / Cosign | Reuse supply-chain gates for each built release; a new configuration or adapter still needs release validation. |
| 18 Ollama / Qwen | Generic tool loop uses configured inference endpoint/model and task-generated schemas. |

The generic stack is an opt-in path; existing Compose/Kubernetes manifests and native acceptance scripts continue exercising the original lab unless explicitly adapted. This table describes reuse and integration boundaries, not a claim that all eighteen services have been commissioned for the generic path.

## Native configuration controls

| Setting | Purpose |
| --- | --- |
| `FABRIC_ALLOWED_PRINCIPALS_JSON` | Explicit allowlist for signed identity claims. |
| `FGA_USER_TYPE`, `FGA_OBJECT_TYPE`, `FGA_RELATION` | Relationship model vocabulary. |
| `METADATA_ENTITY_TYPE`, `METADATA_ENTITY_COLLECTION`, `METADATA_ENTITY_FQN` | Metadata resource mapping; legacy table variables remain supported. |
| `MODEL_METRIC_REQUIREMENTS_JSON` | Metric bounds, e.g. `{"accuracy":{"min":0.8}}`; missing, nonnumeric or nonfinite values fail. |
| `GLPI_SERVICE_TYPE` | Inventory resource type; service ID and entity scope remain mandatory. |
| `FABRIC_DISPATCH_RISK_MAP_JSON`, `FABRIC_EXECUTED_RISK_IDS_JSON` | Explicit evidence-to-risk mappings. |
| `FABRIC_DISPATCH_STORAGE` | `legacy` or `configurable` table families; never an arbitrary SQL prefix. |
| `FABRIC_WORKFLOW_RISK_BINDINGS_JSON` | Required in configurable dispatch: workflow IDs map to `{reason_to_risk, executed_risk_ids}`. Missing bindings retain events; no fallback to legacy credit risk IDs. |
| `FABRIC_WORKER_CLIENT_ID`, `FABRIC_TASK_QUEUE` | Generic Temporal worker delegation and queue. |

Native client defaults preserve the recorded credit lab for compatibility. Supply explicit bindings for new deployments; do not inherit example risk IDs, model metrics or identities without review. See `python -m fabric.enterprise.evaluate --help` for dataset and metric input.

## Compatibility and verification

`fabric/core.py`, the original agent/API and `GovernedCredit` remain compatibility fixtures for prior experiments. New work should use the configurable modules. Legacy stored records are not silently migrated into generic tables. A deployment migration requires deliberate source ingestion, identity mapping, reviewed configuration and fresh approvals.

Run new tests with `python -m unittest discover -s tests -p 'test_configurable*.py' -v`; the ordinary CI core discovery also includes them. Native contract tests run under `tests/enterprise`. The validation job additionally exercises original controls, OPA, the toolkit wrapper, real PostgreSQL and documentation. Historical evidence files describe their original revisions; new configuration does not upgrade those results into production evidence.
