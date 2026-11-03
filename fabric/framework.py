"""Trusted, JSON-serializable framework and implementation catalog.

Source section identifiers are retained; labels and descriptions are paraphrases.
Product selection, control families and engineering status belong to this project,
not to the source author. Status is scoped evidence, never deployment permission.
No imports, executable adapters, network access or user-controlled code live here.
"""

FRAMEWORK_SOURCE = {
    "title": "Implementing Governance for Agentic Workflows",
    "url": "https://www.linkedin.com/pulse/implementing-governance-agentic-workflows-erdos-effect-vipie",
    "original_shared_url": "https://lnkd.in/p/ei3YEcEx",
    "author": "Erdos Effect",
    "publication_date": "2026-11-01",
    "accessed_date": "2026-11-02",
    "verification_method": "Complete public article body and publication metadata read directly; independently checked in browser.",
    "label_style": "Paraphrased labels; original numeric section references retained.",
    "interpretation_boundary": "The source already includes implementable controls, enforcement, evaluation and operational evidence. This catalog adds our engineering mappings and scoped implementation status.",
}

INPUTS = [
    {"id": "3.1.1", "title": "Purpose and context", "description": "Objective, boundaries, operating setting and success measures."},
    {"id": "3.1.2", "title": "Process structure", "description": "Activities, actors, dependencies, handoffs and exceptions."},
    {"id": "3.1.3", "title": "AI authority", "description": "Intended duties, actual permissions and delegation limits."},
    {"id": "3.1.4", "title": "Information context", "description": "Provenance, sensitivity, reliability, movement and retention."},
    {"id": "3.1.5", "title": "Accountability and impact", "description": "Owners, affected people, consequences and redress."},
    {"id": "3.1.6", "title": "Assessment criteria", "description": "Versioned obligations, applicability, limits and approval rules."},
    {"id": "3.1.7", "title": "Safeguards and evidence", "description": "Controls, tests, run records, incidents and changes."},
]

OUTPUTS = [
    {"id": "4.1", "title": "Understanding and gaps", "description": "Interpretation, missing facts, assumptions and conflicting evidence."},
    {"id": "4.2", "title": "Decision advice", "description": "Readiness recommendation and conditions for accountable approval."},
    {"id": "4.3", "title": "Analysis by step", "description": "Locate exposure, safeguards and findings within activities."},
    {"id": "4.4", "title": "Risk records", "description": "Failure scenarios, uncertainty, ownership and treatment."},
    {"id": "4.5", "title": "Autonomy boundaries", "description": "Compare needed authority with permissions actually available."},
    {"id": "4.6", "title": "Control designs", "description": "Define enforcement, responsibility, verification and evidence."},
    {"id": "4.7", "title": "Requirements traceability", "description": "Link criteria, controls and supporting evidence."},
    {"id": "4.8", "title": "Validation design", "description": "Specify scenarios, measures, acceptance criteria and evaluators."},
    {"id": "4.9", "title": "Operational response", "description": "Plan observation, intervention, recovery and review."},
    {"id": "4.10", "title": "Value and restraint", "description": "Weigh benefits against control costs and exposure."},
    {"id": "4.11", "title": "Remediation priorities", "description": "Assign changes, dependencies, deadlines and completion proof."},
    {"id": "4.12", "title": "Assessment history", "description": "Preserve versions, decisions, expiry and reassessment triggers."},
]

COMPONENTS = [
    {
        "id": "01", "name": "Keycloak",
        "role": "Authenticate people and service accounts before the runtime resolves their stored role and tenant.",
        "workflow_specific": "Realm, audience, permitted principal claims and trusted role/tenant provisioning.",
        "implementation_status": "Configurable identity allowlist and native client shipped; historical native subset recorded; new deployment commissioning required.",
        "evidence_paths": ["fabric/enterprise/clients.py", "results/native-component-status.json"],
    },
    {
        "id": "02", "name": "Microsoft Agent Governance Toolkit",
        "role": "Intercept proposed tool calls using an operation allowlist before independent gateway enforcement.",
        "workflow_specific": "Loaded operation identifiers, workload identity and optional interceptor activation.",
        "implementation_status": "Configurable wrapper and real installed-toolkit tests shipped; same-process interception is not workload isolation.",
        "evidence_paths": ["fabric/microsoft_agt.py", "results/configurable-validation/agt.json"],
    },
    {
        "id": "03", "name": "Open Policy Agent",
        "role": "Evaluate administrator-owned action policy and approved configuration identity.",
        "workflow_specific": "Policy package, deployed digest, enabled operations, permitted roles and tenants.",
        "implementation_status": "Generic Rego policy and local OPA tests shipped; generated deployment manifests begin disabled.",
        "evidence_paths": ["policies/configurable.rego", "results/configurable-validation/rego-tests.log"],
    },
    {
        "id": "04", "name": "OpenFGA",
        "role": "Check an actor's relationship to a resource scoped by workflow and tenant.",
        "workflow_specific": "Authorization model, subject/object types, relation and commissioned resource tuples.",
        "implementation_status": "Validated per-workflow bindings and simulated native contracts shipped; historical native subset does not commission new tuples.",
        "evidence_paths": ["fabric/enterprise/configurable.py", "tests/enterprise/test_configurable_native.py", "results/native-component-status.json"],
    },
    {
        "id": "05", "name": "Temporal",
        "role": "Keep workflow progress and approval waits durable while submitting actions to the gateway.",
        "workflow_specific": "Task queue, worker delegation, intended operation and approval timeout.",
        "implementation_status": "Generic activity/workflow code and simulated contracts shipped; prior lab journey recorded; generic native acceptance remains separate.",
        "evidence_paths": ["fabric/enterprise/configurable_workflows.py", "results/native-component-status.json"],
    },
    {
        "id": "06", "name": "CISO Assistant Community",
        "role": "Maintain accountable risk/control records and attach execution evidence without automatically accepting risk.",
        "workflow_specific": "Assessment and folder scope, risk identifiers, owners and treatment/acceptance authority.",
        "implementation_status": "Native client and workflow-specific dispatch risk links shipped; isolated historical HTTP operations recorded; production ownership remains unassigned.",
        "evidence_paths": ["fabric/enterprise/dispatch.py", "fabric/enterprise/clients.py", "results/native-ciso.json"],
    },
    {
        "id": "07", "name": "OpenMetadata",
        "role": "Supply required ownership and classification checks for a selected information asset.",
        "workflow_specific": "Entity type, collection, qualified name, required tag and source governance arrangements.",
        "implementation_status": "Configurable client and simulated contracts shipped; live product commissioning remains unverified.",
        "evidence_paths": ["fabric/enterprise/clients.py", "tests/enterprise/test_configuration.py", "results/native-component-status.json"],
    },
    {
        "id": "08", "name": "MLflow",
        "role": "Record evaluations and enforce a configured approved-release prerequisite with finite metric gates.",
        "workflow_specific": "Registered model, tenant scope, metric bounds, independent reviewer and validation expiry.",
        "implementation_status": "Shared validation/promotion gates shipped; historical synthetic candidate write/read-back recorded; served-model provenance requires commissioning.",
        "evidence_paths": ["fabric/enterprise/clients.py", "fabric/enterprise/evaluate.py", "results/local-native-evaluation.json"],
    },
    {
        "id": "09", "name": "OpenBao",
        "role": "Keep service credentials in an operator-managed secret store, outside workflow and model inputs.",
        "workflow_specific": "Secret paths, workload policies, credential lifetime and separate service identities.",
        "implementation_status": "Native secret client and historical subset operations recorded; new deployment policies and rotation need verification.",
        "evidence_paths": ["fabric/enterprise/clients.py", "results/native-component-status.json"],
    },
    {
        "id": "10", "name": "OpenTelemetry Collector",
        "role": "Export minimized operational traces to help correlate decisions and service failures.",
        "workflow_specific": "Instrumentation, permitted attributes, exporters, retention and access controls.",
        "implementation_status": "Existing telemetry code and isolated compatibility-version experiment recorded; generic instrumentation and deployment-pinned collector are not commissioned.",
        "evidence_paths": ["fabric/enterprise/telemetry.py", "results/native-telemetry/20261102T071551Z/summary.json"],
    },
    {
        "id": "11", "name": "Prometheus and Alertmanager",
        "role": "Observe service metrics and route threshold breaches to authenticated operational handlers.",
        "workflow_specific": "Metrics, alert thresholds, escalation routes, service objectives and response owners.",
        "implementation_status": "Existing monitoring integration and historical native subset recorded; generic deployment instrumentation and alert acceptance remain required.",
        "evidence_paths": ["fabric/enterprise/telemetry.py", "results/native-component-status.json"],
    },
    {
        "id": "12", "name": "DFIR-IRIS",
        "role": "Receive correlated incident alerts for investigation and response.",
        "workflow_specific": "Customer scope, workflow correlation, severity policy and incident ownership.",
        "implementation_status": "Native alert client and generic dispatch contracts shipped; live product commissioning remains unverified.",
        "evidence_paths": ["fabric/enterprise/dispatch.py", "fabric/enterprise/clients.py", "results/native-component-status.json"],
    },
    {
        "id": "13", "name": "GLPI",
        "role": "Check service inventory scope and create trackable remediation tickets.",
        "workflow_specific": "Service resource type/identifier, organizational entity, support owner and ticket routing.",
        "implementation_status": "Configurable inventory client and ticket dispatch contracts shipped; live product commissioning remains unverified.",
        "evidence_paths": ["fabric/enterprise/clients.py", "fabric/enterprise/dispatch.py", "results/native-component-status.json"],
    },
    {
        "id": "14", "name": "PostgreSQL",
        "role": "Serialize governed local effects with approvals, usage, idempotent receipts, audit and outbox records.",
        "workflow_specific": "Provisioned identities/resources, reviewed deployment records, database roles and operational recovery.",
        "implementation_status": "Both generic workflows passed isolated real PostgreSQL concurrency/approval/restart checks with synthetic targets; complete-stack acceptance remains unverified.",
        "evidence_paths": ["fabric/runtime.py", "fabric/enterprise/configurable.py", "results/native-postgres/20261102T093819Z/summary.json"],
    },
    {
        "id": "15", "name": "Fairlearn",
        "role": "Compute supported group metrics over an explicitly supplied binary-classification dataset.",
        "workflow_specific": "Representative population, labels, group definitions, valid metrics, acceptance limits and independent evaluation.",
        "implementation_status": "Supplied-data evaluator shipped; historical eight-record metric/MLflow experiment recorded; no business fairness or Qwen validation follows from that fixture.",
        "evidence_paths": ["fabric/enterprise/evaluate.py", "results/local-native-evaluation.json"],
    },
    {
        "id": "16", "name": "Kubernetes and Cilium",
        "role": "Provide deployment and network-isolation patterns intended to keep execution on the governed path.",
        "workflow_specific": "Service accounts, topology, gateway/target routes, privileges and before/after isolation tests.",
        "implementation_status": "Legacy deployment patterns supplied; generic adaptation and live isolation acceptance remain unverified.",
        "evidence_paths": ["deploy/kubernetes", "results/native-component-status.json"],
    },
    {
        "id": "17", "name": "Syft, Grype and Cosign",
        "role": "Inventory dependencies, evaluate vulnerabilities and verify signed release artifacts.",
        "workflow_specific": "Built artifact, SBOM, vulnerability policy, signing trust and release acceptance.",
        "implementation_status": "Historical directory scan/signature checks recorded, with a failed vulnerability gate; built-image and generic release acceptance remain incomplete.",
        "evidence_paths": ["results/native-supply-chain/summary.json", "results/native-component-status.json"],
    },
    {
        "id": "18", "name": "Ollama and Qwen",
        "role": "Generate bounded tool proposals and process observations while the gateway independently controls effects.",
        "workflow_specific": "Inference endpoint/model, task-generated schemas, call/time limits and model-release provenance.",
        "implementation_status": "Generic tool loop and simulated response tests shipped; historical real Qwen subset runs recorded; no new generic live-model performance claim.",
        "evidence_paths": ["fabric/configurable_agent.py", "results/native-component-status.json"],
    },
]

# These families are this project's engineering choices, not source section names.
CONTROL_FAMILIES = [
    {"id": "identity_access", "title": "Identity and access", "component_ids": ["01", "04", "09"]},
    {"id": "action_boundaries", "title": "Action boundaries", "component_ids": ["02", "03", "16"]},
    {"id": "human_approval", "title": "Independent human approval", "component_ids": ["01", "03", "05", "06"]},
    {"id": "data_quality", "title": "Trusted information", "component_ids": ["07", "09"]},
    {"id": "model_evaluation", "title": "Model and outcome evaluation", "component_ids": ["08", "15", "18"]},
    {"id": "execution_reliability", "title": "Reliable execution", "component_ids": ["05", "14"]},
    {"id": "evidence_audit", "title": "Evidence and audit", "component_ids": ["06", "07", "10", "14"]},
    {"id": "monitoring_response", "title": "Monitoring and response", "component_ids": ["10", "11", "12", "13"]},
    {"id": "release_security", "title": "Release and isolation assurance", "component_ids": ["09", "16", "17"]},
    {"id": "accountability_remediation", "title": "Accountability and remediation", "component_ids": ["06", "13"]},
]
