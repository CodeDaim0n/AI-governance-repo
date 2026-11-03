# Resumed implementation and acceptance

The previous working tree contained the native Qwen task loop, task-scoped gateway routes, Temporal approval/restart experiment, CISO Assistant operations and their retained failed attempts. That work is preserved with the current implementation.

## Additional implementation

- External Cilium and supply-chain receipts must identify the current deployment and source commit, explicitly report success and contain successful operation checks. Matching provenance alone cannot turn a failed receipt into a pass.
- Built-image release acceptance now verifies that Cosign rejects a modified SBOM as well as verifying its original signature. The configured vulnerability gate remains mandatory.
- A real PostgreSQL/OPA runner exercises parallel retries, exact approval, changed-intent rejection, cross-tenant denial, shared-budget races, kill switch, audit integrity and database restart durability. CI runs it against its installed PostgreSQL binaries and retains logs as artifacts. For commit `43f4e51`, both the [push validation run](https://github.com/CodeDaim0n/governed-agent-fabric/actions/runs/41439547701) and the [pull-request validation run](https://github.com/CodeDaim0n/governed-agent-fabric/actions/runs/41439553948) succeeded. These are scoped repository checks, not complete-stack acceptance.
- A real Collector runner checks SDK-to-OTLP delivery, matches the exported trace ID, preserves a decision attribute and removes authorization and prompt/completion attributes. Its sampler is explicitly always-on so inherited sampling cannot silently omit the acceptance span.
- Lab OPA launchers disable optional anonymous outbound telemetry.

## Collector observation

In the restricted-host experiment on 2 November 2026, the stock 0.164.0 binary failed during process-metric registration. Reading its upstream source confirmed that the process registration occurs even with internal metrics disabled. The stock 0.130.0 source skips that registration when metrics are disabled. An isolated experiment used that older official release with a verified archive digest; it did not patch the binary or fabricate process statistics.

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

The runner creates its own disposable database, exposes only a private Unix socket, and uses an unprivileged process. It never targets an existing database or creates a system user. The initial restricted-host attempt on 2 November 2026 mapped only UID zero and reported PostgreSQL startup as `BLOCKED`; the runner did not bypass PostgreSQL's root restriction. That historical result remains in `results/native-postgres/20261102T071551Z/summary.json`.

Later WSL runs used a real PostgreSQL 16.2 server and OPA successfully. The recorded `PASS` in `results/native-postgres/20261102T114531Z/summary.json` includes both configurable workflows, synthetic credit and IT access, with exact approvals, concurrent retry and budget checks, audit/outbox consistency, and receipt replay after database restart. Their business effects are synthetic local tables. This later storage evidence and the successful CI checks do not commission the other products or establish complete-stack acceptance.

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

`results/all-18-live.json` remains the complete-deployment result; `results/native-component-status.json` records separate product observations, including historical host limitations. Neither contracts nor isolated success replace complete acceptance. The earlier restricted environment on 2 November 2026 had an 8 GiB memory limit, no container runtime or Kubernetes tools, and insufficient capacity for the documented complete deployment. The later PostgreSQL runs used a separate WSL environment; they do not remove those earlier limitations or demonstrate the full deployment. No production or cloud resources were provisioned.
