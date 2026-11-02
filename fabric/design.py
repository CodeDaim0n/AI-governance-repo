"""Deterministic governance design from validated workflow contracts.

The output records configured controls and unresolved assurance needs. It does
not invent owners, legal applicability, risk ratings or production verification.
"""
from datetime import datetime, timezone


def assess(registry):
    workflows = []
    for definition in registry.workflows.values():
        spec = definition.to_dict()
        controls = []
        for name, operation in spec["operations"].items():
            controls.append({
                "operation": name, "adapter": operation["adapter"],
                "status": "configured", "allowed_roles": operation["allowed_roles"],
                "parameter_schema": operation["parameters"],
                "resource_checks": operation["resource_checks"],
                "approval": operation["approval"], "budgets": operation["budgets"],
                "required_evidence": ["authorized positive journey", "unauthorized negative journey",
                                      "approval substitution rejection", "effect and evidence atomicity"],
                "verification_status": "not_established_by_design_generation",
            })
        gaps = [
            "Named accountable owner and authorized release reviewer",
            "Operating context, affected people and applicable organizational requirements",
            "Authoritative production source and target integration",
            "Representative process-specific validation and human oversight evidence",
            "Retention, redress, incident response and recovery arrangements",
            "Native deployment commissioning and independent acceptance evidence",
        ]
        sections = {
            "4.1": {"completeness": "partial", "missing": gaps},
            "4.2": {"readiness": "design_review_required", "production_approval": False},
            "4.3": {"analysis": controls},
            "4.4": {"risk_register_status": "owner_assessment_required", "ratings": None,
                    "review_scenarios": ["unauthorized effect", "stale or incorrect source",
                                         "approval substitution", "duplicate effect", "evidence loss"]},
            "4.5": {"autonomy": "bounded_by_operation_contract", "delegation": "server_owned",
                    "operations": list(spec["operations"])},
            "4.6": {"control_configuration": controls, "enforcement": "ConfigurableFabric",
                    "remote_target_support": "requires_explicit_adapter_and_reconciliation_contract"},
            "4.7": {"traceability": {"workflow_id": definition.workflow_id,
                                     "workflow_version": definition.version,
                                     "config_digest": definition.digest},
                    "assurance_status": "configuration_is_not_operational_evidence"},
            "4.8": {"validation_status": "requires_separate_evidence", "required": gaps[3:4]},
            "4.9": {"configured": ["tenant-scoped stop", "transactional audit and outbox"],
                    "operating_arrangements": "unassigned"},
            "4.10": {"benefits": "not_measured", "costs": "not_measured"},
            "4.11": {"remediation": [{"action": gap, "owner": None, "status": "open"} for gap in gaps]},
            "4.12": {"schema_version": 1, "config_digest": definition.digest,
                     "evidence": [], "limitations": "Generated from configuration only; no deployment or approval performed"},
        }
        workflows.append({"workflow_id": definition.workflow_id, "description": spec["description"],
                          "config_digest": definition.digest, "sections": sections})
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
            "kind": "governance_design_and_assessment", "workflows": workflows}


def implementation_package(registry):
    """Export reviewable data; deployment approvals remain an external action."""
    definitions = [item.to_dict() for item in registry.workflows.values()]
    manifest = {item.workflow_id: {
        "enabled": False, "config_digest": item.digest,
        "allowed_operations": list(item.to_dict()["operations"]),
        "allowed_roles": sorted({role for op in item.to_dict()["operations"].values() for role in op["allowed_roles"]}),
        "allowed_tenants": [],
    } for item in registry.workflows.values()}
    return {"schema_version": 1, "workflow_definitions": definitions,
            "assessment": assess(registry), "opa_data": {"fabric_workflows": manifest},
            "deployment_status": "unapproved", "secrets_included": False,
            "required_adapter_ids": sorted({op["adapter"] for spec in definitions for op in spec["operations"].values()})}


def render_report(assessment):
    lines = ["# Governance design and assessment", "",
             "Generated from validated workflow configuration. Production readiness and control effectiveness require separate evidence.", ""]
    for item in assessment["workflows"]:
        lines += ["## " + item["workflow_id"], "", item["description"], "",
                  "Configuration digest: `" + item["config_digest"] + "`", "",
                  "| Operation | Adapter | Acting roles | Approval |", "| --- | --- | --- | --- |"]
        for control in item["sections"]["4.3"]["analysis"]:
            conditions = control["approval"]["when"]
            approval = "Any configured condition; separate reviewer" if conditions else "No additional approval predicate"
            lines.append("| " + " | ".join((control["operation"], control["adapter"], ", ".join(control["allowed_roles"]), approval)) + " |")
        lines += ["", "Unresolved governance inputs:", ""]
        lines += ["- " + gap for gap in item["sections"]["4.1"]["missing"]]
        lines += [""]
    return "\n".join(lines)
