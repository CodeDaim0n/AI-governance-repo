# Validation and evidence

## Configurable workflow regression — 2026-11-02

The reusable path was checked in local WSL with Python 3.14.4, OPA 1.0.1 and a real PostgreSQL 16.2 cluster. The recorded run passed all jobs:

| Group | Result | Evidence |
| --- | --- | --- |
| Core controls, configurable runtime, HTTP, agent and design tests | 100 passed; zero failures, errors or skips | `results/configurable-validation/summary.json`, `tests.log` |
| Original and configurable Rego policy checks | 12 passed | `results/configurable-validation/rego-tests.log` |
| Original Microsoft AGT wrapper assertions | Three passed | `results/configurable-validation/agt.json` |
| Native adapter contracts, configuration, generic bindings and toolkit integration | 77 passed | `results/configurable-validation/enterprise.log` |
| Real PostgreSQL storage and recovery | Passed for original controls and both configurable workflows | `results/configurable-validation/native-postgres.log` |
| Source compilation and strict documentation build | Passed | `results/configurable-validation/run-summary.json`, `docs.log` |

The configurable PostgreSQL checks exercised two independently approved workflow journeys, approval substitution denial, twelve concurrent retries producing one additional effect, and a shared budget across two actors allowing exactly ten of fifteen concurrent requests. They also checked configuration changes, audit/outbox consistency and receipt replay without additional effects after a PostgreSQL restart. The effect targets are synthetic local tables. Other native API contracts use simulated responses; these results do not establish complete eighteen-component acceptance or live-model performance.

The GitHub failure was caused by a locale-free PostgreSQL cluster initialized without an explicit encoding: SQL_ASCII text was returned as bytes, leading to a `text = bytea` comparison error. The runner now initializes UTF8 and verifies server/client encoding plus a Unicode fetch-and-rebind check. A subsequent configurable regression exposed PostgreSQL's decimal result for integer usage sums; the runtime now validates and normalizes those totals before policy serialization. The initial failure evidence is retained alongside the passing rerun.

Historical evidence below remains unchanged. Deployment commissioning and the independent work listed on this page still apply.

## Observed original experiment

| Group | Result | Evidence |
| --- | --- | --- |
| Python control and HTTP tests | 42 passed, zero failures/errors/skips | `results/summary.json`, `results/tests.log` |
| Rego policy checks | Six passed | `results/rego-tests.log` |
| Microsoft AGT wrapper assertions | Three passed | `results/agt.json` |

The original run used OPA 1.0.1, Python 3.12.14 and the dependency versions recorded in the result artifacts. These are historical observations. The expanded deployment selects newer declared product versions and must be validated separately.

## Additional observed checks

The expanded native adapter contract suite has 44 passing tests using explicit simulated HTTP responses and signed test JWTs. It checks such behavior as rejecting malformed allow decisions, protecting accepted risk fields, requiring model approval/expiry/fairness evidence, restricting secret paths and preventing redirect-based endpoint changes. Acceptance contracts also reject failed, incomplete or mismatched deployment receipts. These are not remote integration results.

An isolated **real MLflow HTTP server plus Fairlearn** experiment computed fixture metrics, wrote the evaluation and candidate version, read the version back and confirmed the unapproved candidate could not validate. See `results/local-native-evaluation.json`. The server was temporary and this was not the full native stack.

## Expanded package

- **Adapter contract tests** exercise request construction, scope checks, failure handling and code wiring. They do not prove a remote product is running.
- **Live acceptance** performs native operations, checks product results and records a per-component status. It uses no mocked service responses.
- **Cilium acceptance** first proves a test target reachable, applies the policy, then proves it blocked while the gateway remains reachable.
- **Supply-chain acceptance** generates an image SBOM, applies a vulnerability gate and verifies a signature. Tool presence is insufficient.

Read the current machine-readable result in `results/all-18-live.json`. A missing commissioned host produces `BLOCKED` for all components and a nonzero exit.

## What a passing test cannot establish

A fixture is not a statistical safety estimate. The eight-row Fairlearn sample tests metric plumbing; it is not a fairness assessment of a credit model. The autonomous model chooses tools for synthetic tasks; no real lending decision is delegated to it. A matching file hash does not establish supply-chain trust. A lab reviewer service account demonstrates an authorization mechanism, not meaningful human oversight.

## Required independent work

Representative business data, meaningful human review, protected-group and outcome evaluation, adversarial tool/context testing, target bypass testing, native-product fault injection, restore drills, evidence retention and applicable legal review remain necessary before production use.

## Native autonomous agent observations

Qwen runs now include unmodified model/tool transcripts, independent target-state checks and a connected approval journey through a real persisted Temporal server. Baseline and exploratory failures are retained. The [native study](research/native-agent.md) explains why target-state safety, task completion, injection exposure and product integration must be reported separately. The current per-product matrix is `results/native-component-status.json`; it does not replace complete-suite acceptance.

The deployment-pinned OpenTelemetry Collector 0.164.0 could not start in the restricted process filesystem. A separate, explicitly pinned 0.130.0 compatibility experiment passed actual OTLP delivery, matching-trace read-back and sensitive-attribute removal. This does not change or qualify the deployment image. Actual dependency scanning failed the High-severity gate; local signature verification does not override that failure. See the [resumed implementation record](research/resumed-implementation.md) for exact scope and reproduction.

Actual native CISO Assistant REST operations now provisioned and read back twelve risks/controls and linked observed runtime and release-gate evidence without changing risk ratings or acceptance. The [study](research/native-agent.md) distinguishes its synthetic administrator/SQLite scope from production GRC qualification.
