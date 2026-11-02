"""Scan actual installed dependencies; retain gate failures and offline signatures."""

import os, subprocess, pathlib, json, secrets, hashlib, gzip, collections, time, argparse

parser = argparse.ArgumentParser(
    description="Actual dependency-directory scan and offline signing; not a built-image acceptance"
)
parser.add_argument("--directory", type=pathlib.Path, required=True)
parser.add_argument("--runtime-dir", type=pathlib.Path, required=True)
args = parser.parse_args()
root = pathlib.Path(__file__).resolve().parents[1]
local = (
    root / ".local/native/supply-chain" / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
)
local.mkdir(parents=True, exist_ok=False)
local.chmod(0o700)
out = root / "results/native-supply-chain"
out.mkdir(exist_ok=True)
b = args.runtime_dir / "bin"
env = {
    **os.environ,
    "COSIGN_PASSWORD": secrets.token_urlsafe(32),
    "GRYPE_DB_CACHE_DIR": str(local / "grype-db"),
}
report = {
    "scope": "installed Python dependency directory, NOT built container image",
    "source": str(args.directory.resolve()),
    "gate_threshold": "high",
    "versions": {},
}


def run(args, **kw):
    return subprocess.run(
        [str(x) for x in args],
        env=env,
        text=True,
        capture_output=True,
        timeout=600,
        **kw,
    )


for name in ["syft", "grype", "cosign"]:
    r = run([b / name, "version"])
    report["versions"][name] = r.stdout[-1500:]
sbom = local / "dependencies.spdx.json"
vuln = local / "vulnerabilities.json"
r = run(
    [b / "syft", "dir:" + str(args.directory.resolve()), "-o", "spdx-json=" + str(sbom)]
)
report["syft_exit_code"] = r.returncode
if r.returncode:
    raise SystemExit("Syft failed; no successful scan asserted")
r = run(
    [
        b / "cosign",
        "signing-config",
        "create",
        "--no-default-fulcio",
        "--no-default-oidc",
        "--no-default-rekor",
        "--no-default-tsa",
        "--out",
        local / "offline.json",
    ]
)
if r.returncode:
    raise SystemExit("Offline signing configuration failed")
print("Starting real Grype vulnerability scan", flush=True)
r = run([b / "grype", "sbom:" + str(sbom), "-o", "json", "--fail-on", "high"])
vuln.write_text(r.stdout)
report["scan_exit_code"] = r.returncode
report["scan_stderr"] = r.stderr[-1500:]
try:
    data = json.loads(r.stdout)
    counts = collections.Counter(
        m["vulnerability"]["severity"] for m in data["matches"]
    )
    report["findings_by_severity"] = dict(counts)
    report["matches"] = len(data["matches"])
    report["database"] = data.get("descriptor", {}).get("db")
    report["vulnerability_gate"] = (
        "PASS" if r.returncode == 0 else "FAIL" if r.returncode == 2 else "ERROR"
    )
except Exception:
    report["vulnerability_gate"] = "ERROR"
print(
    "Grype result:",
    report["vulnerability_gate"],
    report.get("findings_by_severity"),
    flush=True,
)
key = local / "cosign"
r = run([b / "cosign", "generate-key-pair", "--output-key-prefix", key])
report["key_generation_exit"] = r.returncode
r = run(
    [
        b / "cosign",
        "sign-blob",
        "--yes",
        "--key",
        str(key) + ".key",
        "--bundle",
        local / "sbom.bundle",
        "--signing-config",
        local / "offline.json",
        sbom,
    ]
)
report["sign_exit"] = r.returncode
report["sign_stderr"] = r.stderr[-1000:]
if r.returncode == 0:
    r = run(
        [
            b / "cosign",
            "verify-blob",
            "--key",
            str(key) + ".pub",
            "--bundle",
            local / "sbom.bundle",
            "--insecure-ignore-tlog",
            sbom,
        ]
    )
    report["verification_exit"] = r.returncode
    report["verification_log"] = r.stderr[-1000:]
    tamper = local / "tampered.json"
    tamper.write_bytes(sbom.read_bytes() + b" ")
    r = run(
        [
            b / "cosign",
            "verify-blob",
            "--key",
            str(key) + ".pub",
            "--bundle",
            local / "sbom.bundle",
            "--insecure-ignore-tlog",
            tamper,
        ]
    )
    report["tampered_verification_exit"] = r.returncode
    report["tamper_rejected"] = r.returncode != 0
    for p in [
        pathlib.Path(str(key) + ".pub"),
        local / "sbom.bundle",
        local / "offline.json",
    ]:
        (out / p.name).write_bytes(p.read_bytes())
for p in [sbom, vuln]:
    if p.exists():
        raw = p.read_bytes()
        (out / (p.name + ".gz")).write_bytes(gzip.compress(raw, mtime=0))
        report[p.name + "_sha256"] = hashlib.sha256(raw).hexdigest()
report["release_qualified"] = False
report["limitations"] = (
    "Directory scan and local signature only. Built-image, deployment provenance and transparency-log qualification not performed. Findings are retained; no exceptions auto-approved."
)
(out / "summary.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report), flush=True)

raise SystemExit(
    0
    if report["vulnerability_gate"] == "PASS"
    and report.get("tamper_rejected")
    and report.get("verification_exit") == 0
    else 2
)
