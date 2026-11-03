"""Record real model-backed governance designs; no workflow execution or provisioning."""
import argparse
import hashlib
import json
import logging
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
from fabric.designer import DesignerError, WorkflowDesigner, render_design_report


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RecordingDesigner(WorkflowDesigner):
    """Optional observation recorder; transport and validation stay unchanged."""
    capture_directory = None
    case_name = None
    captures = None

    def _response(self, client, payload, deadline):
        raw = super()._response(client, payload, deadline)
        if self.capture_directory is not None:
            filename = self.case_name + "-response-" + str(len(self.captures) + 1) + ".json"
            (self.capture_directory / filename).write_bytes(raw)
            self.captures.append({"file": filename, "sha256": hashlib.sha256(raw).hexdigest()})
        return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--thinking", action="store_true", help="Request model reasoning within the same total time budget")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--description", action="append", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--capture-model-responses", action="store_true", help="Also preserve complete model responses for these supplied descriptions")
    args = parser.parse_args()
    if len({path.stem for path in args.description}) != len(args.description):
        parser.error("description basenames must be distinct")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error("use an empty output directory to preserve previous observations")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    designer = RecordingDesigner(args.ollama_url, args.model, timeout=args.timeout, thinking=args.thinking)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    designer.capture_directory = args.output_dir if args.capture_model_responses else None
    record = {
        "scope": "Real Ollama design generation from synthetic descriptions; no business effects or native deployment",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": args.model,
        "thinking_requested": args.thinking,
        "model_identity": {"status": "unavailable"},
        "raw_responses_recorded": args.capture_model_responses,
        "source_digest_basis": "Working-tree file bytes; checkout line-ending normalization can change these hashes",
        "source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in [ROOT / "fabric/designer.py", ROOT / "fabric/framework.py", ROOT / "fabric/workflow_cli.py"]},
        "cases": [],
    }
    try:
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=10) as client:
            response = client.get(args.ollama_url.rstrip("/") + "/api/tags")
            response.raise_for_status()
            matches = [model for model in response.json().get("models", []) if model.get("name") == args.model or model.get("model") == args.model]
            if matches:
                record["model_identity"] = {"status": "observed_in_server_catalogue", "name": matches[0].get("name"), "digest": matches[0].get("digest"), "details": matches[0].get("details")}
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        pass
    for path in args.description:
        designer.case_name, designer.captures = path.stem, []
        print("Designing " + path.stem, flush=True)
        start = time.monotonic()
        case = {"input": str(path), "name": path.stem, "status": "FAIL"}
        try:
            source = path.read_text(encoding="utf-8-sig")
            case["input_sha256"] = sha(path)
            design = designer.design(source)
            (args.output_dir / (path.stem + ".json")).write_text(json.dumps(design, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
            (args.output_dir / (path.stem + ".md")).write_text(render_design_report(design), encoding="utf-8")
            case.update(status="PASS", design_status=design["status"], step_count=len(design["graph"]["steps"]), risk_count=len(design["risks"]), control_count=len(design["controls"]), review="requires_substantive_human_review")
        except (DesignerError, OSError, UnicodeError, ValueError) as exc:
            case["error"] = str(exc)
            if isinstance(exc, DesignerError):
                case["attempts"] = getattr(exc, "attempts", [])
        case["seconds"] = round(time.monotonic() - start, 2)
        case["model_responses"] = list(designer.captures)
        record["cases"].append(case)
        print(json.dumps(case), flush=True)
        (args.output_dir / "run-summary.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return int(any(case["status"] != "PASS" for case in record["cases"]))


if __name__ == "__main__":
    raise SystemExit(main())
