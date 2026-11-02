"""Validate workflows, export governance packages, or run explicit synthetic demos."""
import argparse
import json
from pathlib import Path
import tempfile

from .configuration import WorkflowRegistry
from .design import assess, implementation_package, render_report


def demo(registry):
    from .adapters import builtin_adapters
    from .runtime import ConfigurableFabric
    samples = {
        "synthetic-credit": {"operation": "commit_credit", "resource_id": "case-a",
                             "parameters": {"amount_pence": 20000, "reason": "Explicit synthetic demonstration"}},
        "it-access": {"operation": "grant_access", "resource_id": "employee-a",
                      "parameters": {"permission": "admin", "duration_hours": 4, "justification": "Explicit synthetic demonstration"}},
    }
    with tempfile.TemporaryDirectory(prefix="fabric-demo-") as folder:
        fabric = ConfigurableFabric(Path(folder) / "demo.db", registry, adapters=builtin_adapters())
        fabric.provision_demo()
        journeys = []
        for workflow_id in registry.workflows:
            action = {"workflow_id": workflow_id, "idempotency_key": "demo", **samples[workflow_id]}
            before = fabric.execute("agent-a", action)
            if before != {"status": "denied", "reason": "approval_required"}:
                raise RuntimeError("Demo expected independent approval before the effect")
            approval = fabric.approve("reviewer-a", "agent-a", action)
            executed = fabric.execute("agent-a", action, approval)
            repeated = fabric.execute("agent-a", action, approval)
            if executed["status"] != "executed" or repeated != executed:
                raise RuntimeError("Demo execution or idempotent retry failed")
            journeys.append({"workflow_id": workflow_id, "before_approval": before,
                             "after_approval": executed, "retry_returns_same_receipt": True})
        with fabric.connect() as connection:
            effects = connection.execute("SELECT COUNT(*) FROM cfg_effects").fetchone()[0]
        if effects != len(journeys) or not fabric.verify_chain():
            raise RuntimeError("Demo evidence or effect count failed")
        return {"scope": "local synthetic adapters, no external systems or model inference",
                "workflows": journeys, "effects": effects, "audit_chain_valid": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "assess", "package", "demo"))
    parser.add_argument("--workflow", action="append", required=True)
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("--report", help="Optional Markdown assessment report path")
    parser.add_argument("--opa-data", help="Optional disabled OPA deployment manifest for review")
    args = parser.parse_args()
    registry = WorkflowRegistry.from_paths(args.workflow)
    if args.command == "validate":
        result = {"valid": True, "workflows": {key: item.digest for key, item in registry.workflows.items()}}
    elif args.command == "assess":
        result = assess(registry)
    elif args.command == "package":
        result = implementation_package(registry)
    else:
        result = demo(registry)
    output = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
        print(target)
    else:
        print(output)
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_report(assess(registry)), encoding="utf-8")
    if args.opa_data:
        target = Path(args.opa_data)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(implementation_package(registry)["opa_data"], indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
