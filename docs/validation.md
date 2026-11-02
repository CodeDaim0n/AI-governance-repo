# Validation and evidence

## Observed original experiment

| Group | Result | Evidence |
| --- | --- | --- |
| Python control and HTTP tests | 42 passed, zero failures/errors/skips | `results/summary.json`, `results/tests.log` |
| Rego policy checks | Six passed | `results/rego-tests.log` |
| Microsoft AGT wrapper assertions | Three passed | `results/agt.json` |

The original run used OPA 1.0.1, Python 3.12.14 and the dependency versions recorded in the result artifacts. These are historical observations. The expanded deployment selects newer declared product versions and must be validated separately.

## Additional observed checks

The expanded native adapter contract suite has 26 passing assertions using explicit simulated HTTP responses and signed test JWTs. It checks such behavior as rejecting malformed allow decisions, protecting accepted risk fields, requiring model approval/expiry/fairness evidence, restricting secret paths and preventing redirect-based endpoint changes. These are not remote integration results.

An isolated **real MLflow HTTP server plus Fairlearn** experiment computed fixture metrics, wrote the evaluation and candidate version, read the version back and confirmed the unapproved candidate could not validate. See `results/local-native-evaluation.json`. The server was temporary and this was not the full native stack.

## Expanded package

- **Adapter contract tests** exercise request construction, scope checks, failure handling and code wiring. They do not prove a remote product is running.
- **Live acceptance** performs native operations, checks product results and records a per-component status. It uses no mocked service responses.
- **Cilium acceptance** first proves a test target reachable, applies the policy, then proves it blocked while the gateway remains reachable.
- **Supply-chain acceptance** generates an image SBOM, applies a vulnerability gate and verifies a signature. Tool presence is insufficient.

Read the current machine-readable result in `results/all-18-live.json`. A missing commissioned host produces `BLOCKED` for all components and a nonzero exit.

## What a passing test cannot establish

A fixture is not a statistical safety estimate. The eight-row Fairlearn sample tests metric plumbing; it is not a fairness assessment of a credit model. The local model generates a proposal; no lending decision is delegated to it. A matching file hash does not establish supply-chain trust. A lab reviewer service account demonstrates an authorization mechanism, not meaningful human oversight.

## Required independent work

Representative business data, meaningful human review, protected-group and outcome evaluation, adversarial tool/context testing, target bypass testing, native-product fault injection, restore drills, evidence retention and applicable legal review remain necessary before production use.
