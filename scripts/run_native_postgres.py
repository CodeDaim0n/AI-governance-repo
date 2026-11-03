"""Exercise the real PostgreSQL adapter and OPA without Docker.

Use a disposable cluster, Unix sockets only, and an unprivileged process. Supply
an existing PostgreSQL bin directory; no host database or system user is changed.
This is a storage/policy experiment, not complete-stack acceptance.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fabric.core import OPA, Rejected
from fabric.enterprise.postgres import PostgresFabric


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pg-bin", type=Path, required=True)
    p.add_argument("--opa", type=Path, required=True)
    args = p.parse_args()
    out = ROOT / "results/native-postgres" / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out.mkdir(parents=True, exist_ok=False)
    report = {"status": "FAIL", "scope": "isolated real PostgreSQL + OPA; not all-18 acceptance",
              "checks": {}, "adapter_sha256": hashlib.sha256((ROOT / "fabric/enterprise/postgres.py").read_bytes()).hexdigest()}
    # pgserver's packaged binaries can be used, but none of its process discovery,
    # user creation or permission-changing helpers are needed.
    pg_bin = args.pg_bin.resolve()
    report["postgres_version"] = subprocess.check_output([str(pg_bin / "postgres"), "--version"], text=True).strip()
    report["postgres_binary_sha256"] = hashlib.sha256((pg_bin / "postgres").read_bytes()).hexdigest()
    uid_map = Path("/proc/self/uid_map")
    if os.geteuid() == 0 and uid_map.exists() and uid_map.read_text().split() == ["0", "0", "1"]:
        report.update(status="BLOCKED", reason="Host maps only root; PostgreSQL requires an unprivileged process. No user or root-safety bypass attempted.")
        (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        raise SystemExit(2)
    user = pwd.getpwnam("nobody") if os.geteuid() == 0 else None
    identity = {"user": user.pw_uid, "group": user.pw_gid, "extra_groups": []} if user else {}
    with tempfile.TemporaryDirectory(prefix="fabric-postgres-") as temp:
        local = Path(temp)
        if user:
            os.chown(local, user.pw_uid, user.pw_gid)
        def pg(*command):
            return subprocess.run([str(pg_bin / command[0]), *map(str, command[1:])],
                                  cwd=local, capture_output=True, text=True, check=True, timeout=60, **identity)
        # --no-locale alone selects SQL_ASCII, making psycopg return text as bytes.
        pg("initdb", "-D", local / "data", "--auth-local=trust", "--auth-host=reject", "--no-locale", "--encoding=UTF8", "-U", "postgres")
        pg("pg_ctl", "-D", local / "data", "-l", local / "server.log", "-o", f"-h '' -k {local} -p 55439", "-w", "start")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
        log = open(local / "opa.log", "w")
        opa = subprocess.Popen([str(args.opa), "run", "--disable-telemetry", "--server", f"--addr=127.0.0.1:{port}", str(ROOT / "policies/credit.rego")], stdout=log, stderr=log)
        try:
            for _ in range(80):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=.2).close(); break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError("OPA did not start")
            db = PostgresFabric(f"host={local} port=55439 user=postgres dbname=postgres", OPA(f"http://127.0.0.1:{port}/v1/data/fabric/decision"))
            with db.connect() as c:
                server_encoding = c.execute("SHOW server_encoding").fetchone()[0]
                client_encoding = c.execute("SHOW client_encoding").fetchone()[0]
                assert server_encoding == "UTF8", f"Expected UTF8 server encoding, got {server_encoding!r}"
                assert client_encoding == "UTF8", f"Expected UTF8 client encoding, got {client_encoding!r}"
                sample = "crédit-東京"
                fetched = c.execute("SELECT ?::text", (sample,)).fetchone()[0]
                assert isinstance(fetched, str) and fetched == sample
                # Rebind fetched text, as tenant values are reused in authority queries.
                assert c.execute("SELECT ?::text = ?", (sample, fetched)).fetchone()[0] is True
            report["checks"]["utf8_text_round_trip"] = {"server_encoding": server_encoding, "client_encoding": client_encoding}
            db.seed()
            action = {"case_id": "case-a", "tool": "credit.commit", "amount_pence": 50000, "idempotency_key": "same-action"}
            assert db.execute("agent-a", action)["status"] == "denied"
            report["checks"]["unapproved_release_denied"] = True
            with db.tx() as c:
                c.execute("UPDATE registry SET approved=1,validated_until=?", (time.time() + 300,))
            with ThreadPoolExecutor(max_workers=8) as pool:
                receipts = list(pool.map(lambda _: db.execute("agent-a", action), range(12)))
            assert all(r == receipts[0] and r["status"] == "executed" for r in receipts)
            with db.connect() as c:
                assert c.execute("SELECT count(*) FROM actions").fetchone()[0] == 1
            report["checks"]["concurrent_retries_one_effect"] = {"requests": 12, "effects": 1}
            try:
                db.execute("agent-a", {**action, "amount_pence": 50001})
            except Rejected as exc:
                assert str(exc) == "idempotency_conflict"
            else:
                raise AssertionError("Changed intent accepted")
            report["checks"]["changed_intent_rejected"] = True
            assert db.execute("agent-a", {**action, "case_id": "case-b", "idempotency_key": "other-tenant"})["status"] == "denied"
            report["checks"]["cross_tenant_denied"] = True
            approved = {**action, "amount_pence": 200000, "idempotency_key": "reviewed"}
            assert db.execute("agent-a", approved)["status"] == "denied"
            approval = db.approve("reviewer-a", "agent-a", approved)
            receipt = db.execute("agent-a", approved, approval)
            assert receipt["status"] == "executed" and db.execute("agent-a", approved, approval) == receipt
            report["checks"]["reviewer_approval_exact_effect"] = True
            # Fill most of the budget with approved actions, then race low-risk
            # requests across independent connections. Commit-time locking must
            # allow only the two requests still covered by the shared budget.
            for n in range(5):
                a = {**approved, "idempotency_key": f"fill-{n}"}
                aid = db.approve("reviewer-a", "agent-a", a)
                assert db.execute("agent-a", a, aid)["status"] == "executed"
            actions = [{**action, "amount_pence": 100000, "idempotency_key": f"race-{n}"} for n in range(8)]
            with ThreadPoolExecutor(max_workers=8) as pool:
                raced = list(pool.map(lambda a: db.execute("agent-a", a), actions))
            assert sum(r["status"] == "executed" for r in raced) == 2
            report["checks"]["concurrent_budget_enforced"] = {"requests": 8, "executed": 2, "denied": 6}
            db.stop("admin-a")
            assert db.execute("agent-a", {**action, "idempotency_key": "stopped"})["status"] == "denied"
            report["checks"]["kill_switch_denied"] = True
            assert db.verify_chain()
            report["checks"]["audit_chain_verified"] = True
            from check_configurable_postgres import run as check_configurable, registry as configurable_registry, effect_count
            from fabric.enterprise.configurable import ConfigurablePostgresFabric
            from fabric.adapters import builtin_adapters
            configurable = check_configurable(db.path)
            report["checks"]["configurable_workflows"] = configurable
            with db.connect() as c:
                before = c.execute("SELECT count(*) FROM actions").fetchone()[0]
                pending = c.execute("SELECT count(*) FROM outbox WHERE delivered=0").fetchone()[0]
            assert pending > 0
            pg("pg_ctl", "-D", local / "data", "-l", local / "server.log", "-m", "fast", "-w", "restart")
            assert db.verify_chain()
            with db.connect() as c:
                assert c.execute("SELECT count(*) FROM actions").fetchone()[0] == before
                assert c.execute("SELECT count(*) FROM outbox WHERE delivered=0").fetchone()[0] == pending
            report["checks"]["restart_preserves_actions_audit_outbox"] = {"effects": before, "pending_outbox": pending}
            generic = ConfigurablePostgresFabric(db.path, configurable_registry(), adapters=builtin_adapters())
            for replay in configurable["restart_replays"]:
                assert generic.execute(replay["actor"], replay["action"]) == replay["response"]
            assert effect_count(generic, configurable["fixture"]["tenant"]) == configurable["expected_effect_count"]
            assert generic.verify_chain()
            report["checks"]["restart_preserves_configurable_receipts"] = True
            report["status"] = "PASS"
        finally:
            opa.terminate(); opa.wait(timeout=10); log.close()
            pg("pg_ctl", "-D", local / "data", "-m", "fast", "-w", "stop")
            (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
