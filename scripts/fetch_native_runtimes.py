"""Fetch exact native research releases. Verify pinned archive SHA before extracting.
No daemon installation or system configuration; Linux amd64, Python 3.12+.
Publisher/GitHub digest observations are recorded separately from trust attestation.
"""

import argparse, hashlib, json, pathlib, shutil, subprocess, tarfile, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--destination", type=pathlib.Path, required=True)
    p.add_argument("--products", nargs="*")
    p.add_argument("--lock", type=pathlib.Path, default=ROOT / "deploy/native/runtimes.lock.json")
    a = p.parse_args()
    dest = a.destination.resolve()
    (dest / "downloads").mkdir(parents=True, exist_ok=True)
    (dest / "bin").mkdir(exist_ok=True)
    for rec in json.loads(a.lock.read_text()):
        name = rec["product"]
        if a.products and name not in a.products:
            continue
        suffix = (
            ".tar.zst"
            if rec["source"].endswith(".tar.zst")
            else ".tar.gz"
            if rec["source"].endswith(".tar.gz")
            else ".bin"
        )
        archive = dest / "downloads" / (name + suffix)
        if not archive.exists():
            request = urllib.request.Request(
                rec["source"], headers={"User-Agent": "governed-agent-fabric-research"}
            )
            with (
                urllib.request.urlopen(request, timeout=180) as r,
                archive.open("wb") as f,
            ):
                shutil.copyfileobj(r, f)
        with archive.open("rb") as f:
            actual = hashlib.file_digest(f, "sha256").hexdigest()
        if actual != rec["sha256"]:
            raise SystemExit("Archive SHA mismatch: " + name)
        if name == "cosign":
            shutil.copyfile(archive, dest / "bin/cosign")
            (dest / "bin/cosign").chmod(0o755)
        elif name in ("keycloak", "jre"):
            target = dest / name
            target.mkdir(exist_ok=True)
            with tarfile.open(archive) as t:
                t.extractall(target, filter="data")
        elif name == "ollama":
            target = dest / "ollama"
            target.mkdir(exist_ok=True)
            with subprocess.Popen(
                ["zstd", "-dc", str(archive)], stdout=subprocess.PIPE
            ) as process:
                with tarfile.open(fileobj=process.stdout, mode="r|") as t:
                    for m in t:
                        if any(
                            x.startswith(("cuda", "rocm"))
                            for x in pathlib.PurePosixPath(m.name).parts
                        ):
                            continue
                        t.extract(m, target, filter="data")
                if process.wait() != 0:
                    raise SystemExit("zstd extraction failed")
        else:
            names = {
                "bao",
                "openfga",
                "temporal",
                "prometheus",
                "promtool",
                "alertmanager",
                "amtool",
                "otelcol-contrib",
                "syft",
                "grype",
            }
            with tarfile.open(archive) as t:
                for m in t:
                    if m.isfile() and pathlib.PurePosixPath(m.name).name in names:
                        target = dest / "bin" / pathlib.PurePosixPath(m.name).name
                        with t.extractfile(m) as source, target.open("wb") as f:
                            shutil.copyfileobj(source, f)
                        target.chmod(0o755)
        print(name + ": archive SHA matched; extracted", flush=True)


if __name__ == "__main__":
    main()
