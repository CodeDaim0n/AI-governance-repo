# Resumed implementation and acceptance

The previous working tree contained the native Qwen task loop, task-scoped gateway routes, Temporal approval/restart experiment, CISO Assistant operations and their retained failed attempts. That work is preserved with the current implementation.

## Additional implementation

- External Cilium and supply-chain receipts must identify the current deployment and source commit, explicitly report success and contain successful operation checks. Matching provenance alone cannot turn a failed receipt into a pass.
- Built-image release acceptance now verifies that Cosign rejects a modified SBOM as well as verifying its original signature. The configured vulnerability gate remains mandatory.
- A real PostgreSQL/OPA runner exercises parallel retries, exact approval, changed-intent rejection, cross-tenant denial, shared-budget races, kill switch, audit integrity and database restart durability. The existing CI workflow is configured to run it against its installed PostgreSQL binaries and retain logs as artifacts. That added CI check has not run yet.
- A real Collector runner checks SDK-to-OTLP delivery, matches the exported trace ID, preserves a decision attribute and removes authorization and prompt/completion attributes. Its sampler is explicitly always-on so inherited sampling cannot silently omit the acceptance span.
- Lab OPA launchers disable optional anonymous outbound telemetry.

## Collector observation

The stock 0.164.0 binary still fails during process-metric registration on this host. Reading its upstream source confirmed that the process registration occurs even with internal metrics disabled. The stock 0.130.0 source skips that registration when metrics are disabled. An isolated experiment used that older official release with a verified archive digest; it did not patch the binary or fabricate process statistics.

The compatibility run passed: one SDK span was exported through actual OTLP/HTTP, the Collector file contained the matching trace, the decision outcome remained and three sensitive attributes were removed. Failed attempts remain alongside the successful attempt in `results/native-telemetry/`. The compatibility lock and experiment do not replace the deployment-pinned release or qualify an old release for production.

```bash
python scripts/fetch_native_runtimes.py \
  --lock deploy/native/telemetry-compat.lock.json \
  --destination /tmp/fabric-telemetry-compat
PYTHONPATH=. python scripts/run_native_telemetry.py \
  --collector /tmp/fabric-telemetry-compat/bin/otelcol-contrib
```

Install the repository's enterprise dependencies before running the experiment. To test the deployment-pinned binary, supply its path instead; failure is retained and returns a nonzero exit code.

## PostgreSQL execution

```bash
PYTHONPATH=. python scripts/run_native_postgres.py \
  --pg-bin "$(pg_config --bindir)" --opa /absolute/path/to/opa
```

The runner creates its own disposable database, exposes only a private Unix socket, and uses an unprivileged process. It never targets an existing database or creates a system user. This local host maps only UID zero, so PostgreSQL startup is reported `BLOCKED`; the runner does not bypass PostgreSQL's root restriction. Its isolated CI result must be read independently of complete-stack acceptance.

## Remaining complete-stack work

| Component group | Remaining live acceptance |
| --- | --- |
| OpenMetadata | Native classified entity, owner and lineage read-back in the commissioned deployment. |
| DFIR-IRIS | Native customer-scoped incident/alert creation and read-back. |
| GLPI | Native service ownership and remediation ticket operations. |
| PostgreSQL | Connected enterprise gateway effects, audit and downstream delivery receipts; isolated database acceptance alone is insufficient. |
| Kubernetes/Cilium | Before/after network enforcement and preserved gateway access on a capable kernel. |
| Syft/Grype/Cosign | Resolve the recorded dependency gate failure and qualify the actual built image. Directory signatures are insufficient. |
| All products together | Commission the dedicated host and run `scripts/accept_all_components.py`. |

`results/all-18-live.json` remains the complete-deployment result; `results/native-component-status.json` records separate product observations. Neither contracts nor isolated success replace complete acceptance. This host has an 8 GiB memory limit, no container runtime or Kubernetes tools, and insufficient capacity for the documented complete deployment. No production or cloud resources were provisioned.
