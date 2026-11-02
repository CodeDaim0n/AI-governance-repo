"""Design governance from prose, validate contracts, export packages, or run demos."""
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
    parser.add_argument("command", choices=("design", "validate", "assess", "package", "demo"))
    parser.add_argument("--workflow", action="append", help="Validated runtime definition; repeat for multiple workflows")
    description = parser.add_mutually_exclusive_group()
    description.add_argument("--description", help="Natural-language workflow description for design")
    description.add_argument("--description-file", type=Path, help="UTF-8 workflow description for design")
    parser.add_argument("--model", help="Installed Ollama model for design, for example qwen3:8b")
    parser.add_argument("--thinking", action="store_true", help="Request model reasoning for design; may need a longer time budget")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434", help="Operator-selected Ollama endpoint")
    parser.add_argument("--timeout", type=float, default=180, help="Design request time budget in seconds")
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("--report", help="Optional Markdown assessment report path")
    parser.add_argument("--opa-data", help="Optional disabled OPA deployment manifest for review")
    args = parser.parse_args()
    if args.command == "design":
        if args.workflow or args.opa_data:
            parser.error("design accepts prose and produces a review draft; --workflow and --opa-data belong to runtime packaging")
        if not args.model or (args.description is None and args.description_file is None):
            parser.error("design requires --model and either --description or --description-file")
        from .designer import DesignerError, WorkflowDesigner, render_design_report
        try:
            if args.description_file is not None:
                if args.description_file.stat().st_size > 200000:
                    parser.error("description file exceeds 200000 bytes")
                source = args.description_file.read_text(encoding="utf-8-sig")
            else:
                source = args.description
            result = WorkflowDesigner(args.ollama_url, args.model, timeout=args.timeout, thinking=args.thinking).design(source)
        except (OSError, UnicodeError, DesignerError, ValueError) as exc:
            parser.error(str(exc))
        report = render_design_report(result) if args.report else None
    else:
        if not args.workflow:
            parser.error("this command requires at least one --workflow")
        if args.description is not None or args.description_file is not None or args.model or args.thinking:
            parser.error("description and model arguments are available only for design")
        registry = WorkflowRegistry.from_paths(args.workflow)
        report = render_report(assess(registry)) if args.report else None
    if args.command == "validate":
        result = {"valid": True, "workflows": {key: item.digest for key, item in registry.workflows.items()}}
    elif args.command == "assess":
        result = assess(registry)
    elif args.command == "package":
        result = implementation_package(registry)
    elif args.command == "demo":
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
        target.write_text(report, encoding="utf-8")
    if args.opa_data:
        target = Path(args.opa_data)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(implementation_package(registry)["opa_data"], indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
