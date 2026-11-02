"""Keep native subset observations distinct from complete-stack acceptance."""

import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
manifest = json.loads((R / "docs/components/manifest.json").read_text())
runs = json.loads((R / "results/native-agent/comparison.json").read_text())["runs"]
rows = []
for product in manifest:
    n = product["id"]
    observed = [
        r
        for r in runs
        if r["component_results"].get(str(n), {}).get("status") == "PASS"
    ]
    row = {
        "id": n,
        "component": product["name"],
        "status": "NOT_COMMISSIONED",
        "native_observed": False,
        "complete_stack_verified": False,
        "evidence": [],
        "detail": "Source/deployment and contract implementation present; live product operation not observed here.",
    }
    if observed:
        row.update(
            status="OBSERVED_NATIVE_SUBSET",
            native_observed=True,
            evidence=[r["summary"] for r in observed],
            detail="Native operation/read-back in the explicitly scoped SQLite-target experiment; development stores. Not complete-stack qualification.",
        )
    if n in (8, 15):
        row.update(
            status="OBSERVED_ISOLATED_NATIVE",
            native_observed=True,
            evidence=["results/local-native-evaluation.json"],
            detail="Actual Fairlearn to MLflow HTTP write and read-back; eight-row fixture, unapproved candidate. Not Qwen fairness or predictive-model validation.",
        )
    if n == 10:
        row.update(
            status="PARTIAL",
            native_observed=True,
            evidence=[
                "results/native-agent/20261102T024826Z/summary.json",
                "results/native-agent/20261102T024826Z/traces.jsonl",
            ],
            detail="Actual OpenTelemetry SDK spans retained locally. Native Collector failed against restricted procfs; OTLP receipt not established.",
        )
    if n == 14:
        row["detail"] = (
            "Enterprise PostgreSQL adapter supplied. No PostgreSQL service observed; native experiment target is explicitly SQLite."
        )
        attempts = sorted((R / "results/native-postgres").glob("*/summary.json"))
        if attempts:
            latest = json.loads(attempts[-1].read_text())
            row.update(status=latest["status"], evidence=[str(attempts[-1].relative_to(R))], detail=latest.get("reason", latest["scope"]))
            if latest["status"] == "PASS":
                row.update(status="OBSERVED_ISOLATED_NATIVE", native_observed=True)
    if n == 16:
        row.update(
            status="HOST_BLOCKED",
            detail="No Kubernetes/container runtime, network-management or eBPF capabilities. Before/after Cilium enforcement acceptance not run.",
        )
    if n == 17:
        row.update(
            status="GATE_FAILED_PARTIAL",
            native_observed=True,
            evidence=["results/native-supply-chain/summary.json"],
            detail="Actual dependency-directory SBOM and vulnerability scan, local signature verification and tamper rejection. High gate failed. Built-image acceptance not run.",
        )
    if n == 6 and (R / "results/native-ciso.json").exists():
        ciso = json.loads((R / "results/native-ciso.json").read_text())
        if ciso.get("status") == "PASS":
            row.update(
                status="OBSERVED_ISOLATED_NATIVE",
                native_observed=True,
                evidence=["results/native-ciso.json"],
                detail=ciso["scope"],
            )
    rows.append(row)
    if n == 10:
        attempts = sorted((R / "results/native-telemetry").glob("*/summary.json"))
        successful = [p for p in attempts if json.loads(p.read_text()).get("status") == "PASS"]
        if successful:
            evidence = successful[-1]
            proof = json.loads(evidence.read_text())
            row.update(status="OBSERVED_ISOLATED_NATIVE", native_observed=True,
                       evidence=[str(evidence.relative_to(R)), proof["trace_file"]],
                       detail=proof["version"] + ": actual SDK OTLP delivery/read-back and sensitive-attribute removal. Isolated compatibility experiment; deployment-pinned 0.164.0 remains blocked on restricted procfs.")
result = {
    "scope": "per-component observed operations, not simultaneous all-18 success",
    "complete_stack_verified": False,
    "native_component_statuses_are_not_certification": True,
    "components": rows,
}
(R / "results/native-component-status.json").write_text(
    json.dumps(result, indent=2) + "\n"
)
print("Per-component observation matrix generated")
