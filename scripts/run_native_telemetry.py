"""Real SDK -> OTLP/HTTP -> Collector -> minimized file export acceptance.

Accepts an explicit Collector binary and records its digest/version. An older
compatibility binary is never substituted for the configured deployment image.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request

import yaml
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--collector", type=Path, required=True)
    args = parser.parse_args()
    binary = args.collector.resolve()
    out = ROOT / "results/native-telemetry" / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out.mkdir(parents=True, exist_ok=False)
    report = {"status": "FAIL", "scope": "isolated native OTLP delivery and attribute minimization; not all-18 acceptance",
              "version": subprocess.check_output([str(binary), "--version"], text=True).strip(),
              "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    forbidden = ["authorization", "gen_ai.prompt", "gen_ai.completion"]
    config = {
        "receivers": {"otlp": {"protocols": {"http": {"endpoint": f"127.0.0.1:{port}"}}}},
        "processors": {"attributes/minimize": {"actions": [{"key": key, "action": "delete"} for key in forbidden]}},
        "exporters": {"file": {"path": str(out / "traces.jsonl")}},
        "service": {"telemetry": {"metrics": {"level": "none"}},
                    "pipelines": {"traces": {"receivers": ["otlp"], "processors": ["attributes/minimize"], "exporters": ["file"]}}}}
    (out / "collector.yaml").write_text(yaml.safe_dump(config))
    provider = None
    with (out / "collector.log").open("w") as log:
        process = subprocess.Popen([str(binary), "--config=" + str(out / "collector.yaml")], stdout=log, stderr=log)
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError("Collector exited during startup")
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/traces", timeout=.2).close(); break
                except urllib.error.HTTPError:
                    break  # A real HTTP response establishes receiver readiness only.
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError("Collector readiness timeout")
            provider = TracerProvider(resource=Resource({"service.name": "fabric-telemetry-acceptance"}), sampler=ALWAYS_ON)
            provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=f"http://127.0.0.1:{port}/v1/traces", timeout=5)))
            with provider.get_tracer("fabric.acceptance").start_as_current_span("governed-action") as span:
                span.set_attribute("fabric.outcome", "denied")
                for key in forbidden:
                    span.set_attribute(key, "synthetic-must-be-removed")
                trace_id = format(span.get_span_context().trace_id, "032x")
            provider.force_flush()
            process.terminate(); process.wait(timeout=15)
            data = [json.loads(line) for line in (out / "traces.jsonl").read_text().splitlines() if line.strip()]
            spans = [span for batch in data for resource in batch["resourceSpans"] for scope in resource["scopeSpans"] for span in scope["spans"]]
            matched = [span for span in spans if span["traceId"] == trace_id and span["name"] == "governed-action"]
            assert len(matched) == 1
            attributes = {x["key"]: x["value"] for x in matched[0]["attributes"]}
            assert attributes["fabric.outcome"] == {"stringValue": "denied"}
            assert not set(forbidden) & attributes.keys()
            assert "synthetic-must-be-removed" not in (out / "traces.jsonl").read_text()
            report.update(status="PASS", checks={"actual_otlp_trace_read_back": True, "trace_id_matches": True,
                "allowed_outcome_preserved": True, "sensitive_attributes_removed": forbidden},
                trace_file=str((out / "traces.jsonl").relative_to(ROOT)))
        except Exception as exc:
            report["error_type"] = type(exc).__name__
            report["reason"] = str(exc)
        finally:
            if provider:
                provider.shutdown()
            if process.poll() is None:
                process.terminate(); process.wait(timeout=15)
    (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
