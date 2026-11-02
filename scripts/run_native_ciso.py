"""Native CISO Assistant risk/control/evidence acceptance, dedicated synthetic SQLite.
Run with CISO's own Python environment and official backend source. Bootstrap uses
ORM only for isolated fixture/credentials; all integration operations use real HTTP.
Never touches an existing CISO instance or assigns real risk acceptance.
"""

import argparse, contextlib, hashlib, json, os, pathlib, secrets, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=pathlib.Path, required=True)
    parser.add_argument("--reuse-state", type=pathlib.Path)
    args = parser.parse_args()
    backend = args.backend.resolve()
    local = (
        args.reuse_state.resolve()
        if args.reuse_state
        else ROOT
        / ".local/native-ciso"
        / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    )
    if not args.reuse_state:
        local.mkdir(parents=True, exist_ok=False)
        local.chmod(0o700)
    report = {
        "status": "STARTED",
        "scope": "Actual CISO Assistant Community v4.2.1 HTTP risk/control/evidence operations; isolated SQLite; synthetic bootstrap administrator, not a production owner or least-privilege qualification",
        "real_human_acceptance": False,
        "bootstrap_uses": "official ORM fixture and private token; integration operations through actual REST API",
        "python": sys.version.split()[0],
    }
    out = ROOT / "results/native-ciso.json"
    out.write_text(json.dumps(report, indent=2))
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "ciso_assistant.settings",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
        "SQLITE_FILE": str(local / "ciso.sqlite3"),
        "LOCAL_STORAGE_DIRECTORY": str(local / "attachments"),
        "ALLOWED_HOSTS": "127.0.0.1,localhost",
        "CISO_ASSISTANT_URL": "http://127.0.0.1:8002",
        "DEBUG": "False",
        "ENABLE_CHAT": "False",
    }
    os.environ.update(env)
    sys.path.insert(0, str(backend))
    sys.path.insert(0, str(ROOT))
    os.chdir(backend)
    process = None
    log = open(local / "server.log", "a")
    try:
        import django

        django.setup()
        if args.reuse_state:
            private = json.loads((local / "credentials.json").read_text())
            os.environ.update(private)
            token = private["CISO_TOKEN"]
        else:
            from django.core.management import call_command

            with open(local / "migrations.log", "w") as migration_log:
                call_command(
                    "migrate",
                    interactive=False,
                    stdout=migration_log,
                    stderr=migration_log,
                )
            from iam.models import Folder, User
            from core.models import RiskMatrix, RiskAssessment
            from knox.models import AuthToken

            folder = Folder.objects.create(
                name="Governed Agent Fabric synthetic native experiment",
                parent_folder=Folder.get_root_folder(),
            )
            scale = [
                {
                    "name": x,
                    "description": "Synthetic uncalibrated demonstration category",
                    "abbreviation": x[0],
                }
                for x in ["Low", "Medium", "High"]
            ]
            matrix = RiskMatrix.objects.create(
                name="Synthetic demonstration matrix - not approved calibration",
                folder=folder,
                json_definition={
                    "probability": scale,
                    "impact": scale,
                    "risk": [
                        {"name": "Low", "hexcolor": "#4caf50"},
                        {"name": "Medium", "hexcolor": "#ffc107"},
                        {"name": "High", "hexcolor": "#f44336"},
                    ],
                    "grid": [[0, 0, 1], [0, 1, 2], [1, 2, 2]],
                },
            )
            assessment = RiskAssessment.objects.create(
                name="Synthetic agent-fabric engineering risks",
                folder=folder,
                risk_matrix=matrix,
            )
            user = User.objects.create_superuser(
                email="fabric-native-admin@example.invalid",
                password=secrets.token_urlsafe(32),
            )
            _, token = AuthToken.objects.create(user=user)
            private = {
                "CISO_TOKEN": token,
                "CISO_FOLDER_ID": str(folder.id),
                "CISO_ASSESSMENT_ID": str(assessment.id),
                "CISO_URL": "http://127.0.0.1:8002/api",
            }
            creds = local / "credentials.json"
            creds.write_text(json.dumps(private))
            creds.chmod(0o600)
            os.environ.update(private)
        process = subprocess.Popen(
            [
                sys.executable,
                str(backend / "manage.py"),
                "runserver",
                "127.0.0.1:8002",
                "--noreload",
            ],
            cwd=backend,
            env={**os.environ},
            stdout=log,
            stderr=log,
        )
        import httpx

        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("CISO backend exited before acceptance")
            try:
                r = httpx.get(
                    "http://127.0.0.1:8002/api/risk-scenarios/",
                    headers={"Authorization": "Token " + token},
                    timeout=2,
                    trust_env=False,
                )
                if r.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        else:
            raise RuntimeError("CISO native API readiness deadline")
        from fabric.enterprise.clients import CISOAssistant

        client = CISOAssistant()
        fixture = json.loads((ROOT / "docs/risk-register.json").read_text())
        controls = [client.control_for_risk(risk) for risk in fixture]
        first = client.risks()
        assert len(first) == len(fixture)
        protected = [
            "treatment",
            "current_proba",
            "current_impact",
            "current_level",
            "residual_proba",
            "residual_impact",
            "residual_level",
            "risk_acceptance",
            "existing_controls",
            "risk_owners",
        ]
        snapshot = {r["id"]: {k: r.get(k) for k in protected} for r in first}
        # Replay provisioning to test receiver read-back/idempotency without duplicates.
        for risk in fixture:
            client.control_for_risk(risk)
        prior_run = json.loads(
            (
                ROOT / "results/native-agent/20261102T023518Z/cross_tenant-17.json"
            ).read_text()
        )
        event = next(e for e in prior_run["audit"] if e.get("outcome") == "denied")
        evidence_id = "native-cross-tenant-20261102T023518Z-17"
        receipt = client.evidence(
            evidence_id,
            {
                "source_run": "20261102T023518Z",
                "source_artifact": "cross_tenant-17.json",
                "event": event,
                "risk_ids": [fixture[0]["risk_id"]],
            },
        )
        duplicate = client.evidence(
            evidence_id,
            {
                "source_run": "20261102T023518Z",
                "event": event,
                "risk_ids": [fixture[0]["risk_id"]],
            },
        )
        assert duplicate["id"] == receipt["id"]
        release = json.loads(
            (ROOT / "results/native-supply-chain/summary.json").read_text()
        )
        release_evidence = client.evidence(
            "native-dependency-gate-20261102",
            {
                "source_artifact": "results/native-supply-chain/summary.json",
                "vulnerability_gate": release["vulnerability_gate"],
                "findings_by_severity": release["findings_by_severity"],
                "sbom_sha256": release["dependencies.spdx.json_sha256"],
                "risk_ids": ["R12"],
            },
        )
        release_controls = [
            c
            for c in client.pages("/applied-controls/")
            if c.get("name") == client.control_name("R12")
        ]
        assert len(release_controls) == 1 and str(release_evidence["id"]) in client.ids(
            client.detail("applied-controls", release_controls[0]).get("evidences", [])
        )
        after = client.risks()
        assert len(after) == 12
        assert {r["id"]: {k: r.get(k) for k in protected} for r in after} == snapshot
        matching = client.pages("/applied-controls/")
        matching = [
            c
            for c in matching
            if c.get("name") == client.control_name(fixture[0]["risk_id"])
        ]
        assert len(matching) == 1
        detail = client.detail("applied-controls", matching[0])
        assert str(receipt["id"]) in client.ids(detail.get("evidences", []))
        payload = {
            "risk_records": after,
            "control_ids": [str(c["id"]) for c in controls],
            "evidence_id": str(receipt["id"]),
            "dependency_gate_evidence_id": str(release_evidence["id"]),
            "ratings_and_acceptance_before": snapshot,
            "ratings_and_acceptance_after": {
                r["id"]: {k: r.get(k) for k in protected} for r in after
            },
        }
        # API records are synthetic; credentials and bootstrap user are never serialized.
        path = ROOT / "results/native-ciso-records.json"
        path.write_text(json.dumps(payload, indent=2, default=str))
        report.update(
            status="PASS",
            risks_read_back=len(after),
            controls_created=len(controls),
            idempotent_risk_replay=True,
            observed_agent_denial_attached=True,
            failed_dependency_gate_attached_to_R12=True,
            evidence_duplicate_same_id=True,
            control_evidence_link_read_back=True,
            ratings_and_acceptance_unchanged=True,
            records_artifact=str(path.relative_to(ROOT)),
            source_provenance=json.loads(
                pathlib.Path(
                    "/tmp/fabric-native/downloads/provenance-ciso.json"
                ).read_text()
            ),
        )
        client.close()
    except Exception as e:
        report.update(status="FAIL", error_type=type(e).__name__, message=str(e)[:200])
        raise
    finally:
        out.write_text(json.dumps(report, indent=2, default=str) + "\n")
        attempts = ROOT / "results/native-ciso-attempts"
        attempts.mkdir(exist_ok=True)
        (
            attempts / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + ".json")
        ).write_text(json.dumps(report, indent=2, default=str) + "\n")
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        log.close()
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
