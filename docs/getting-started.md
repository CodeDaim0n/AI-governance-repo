# Getting started

## Select the deployment scope

| Scope | Purpose | Requirements |
| --- | --- | --- |
| Core laboratory | Reproduce the original enforcement experiment. | Python 3.11+, OPA; no containers. |
| Native 18-component stack | Exercise actual product APIs, workflow, evidence and isolation. | Dedicated privileged Linux host, Docker, Kubernetes tooling and native product commissioning. |

## Core laboratory

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/fetch_opa.py
OPA_BIN="$PWD/.local/opa" python scripts/test_all.py
python scripts/assess.py
```

The runner launches OPA, waits for readiness and runs the Python tests. Policy tests run against the real OPA binary. Results go to `results/`.

For the optional original AGT checks, use a separate environment:

```bash
python3 -m venv .venv-agt
source .venv-agt/bin/activate
python -m pip install -r requirements-agt.txt
OPA_BIN="$PWD/.local/opa" python scripts/test_agt.py
```

## Native implementation

Read the [full-stack guide](deployment/full-stack.md) before starting containers. The preflight command is safe to run without deployment:

```bash
python scripts/full_stack.py preflight
```

The environment used to build this repository cannot pass that preflight: it has no Docker daemon, Kubernetes tooling or eBPF/container privileges. This is reported as a concrete blocker, not replaced by mocked product results.

## Success criteria

- **Core success:** all requested control assertions pass with their logs retained.
- **Native success:** `scripts/accept_all_components.py` reports all 18 as `PASS`, with Cilium and supply-chain live evidence from the same commissioned installation.
- **Production approval:** a separate accountable release decision after independent validation, legal applicability review, security qualification and operational recovery testing.

Do not collapse those three criteria into one status.
