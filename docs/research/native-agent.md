# Autonomous agent fabric: native experiment

The fabric is designed for **bounded autonomous execution**: an agent chooses an allowed tool, receives its actual observation, and chooses its next step. Independent services decide whether its requested action is authorized. Reviewer approval is a deliberate pause when policy requires it.

![Autonomous loop and authority boundary](../assets/autonomous-agent-cycle.svg)

The 18 component groups contribute around this loop. A request does not traverse eighteen services in a serial chain.

| Contribution | Products | Role in autonomous execution |
| --- | --- | --- |
| Reasoning and tool selection | Ollama + Qwen | Choose read and commit tools; process observations within explicit budgets. |
| Identity, secrets and record access | Keycloak, OpenBao, OpenFGA | Establish the actor, authorized records and service credential custody. |
| Independent execution authority | Microsoft AGT, OPA | Intercept unlisted tools and enforce current restrictions at the write boundary. |
| Durable action lifecycle | Temporal, PostgreSQL | Preserve waits, retries, state, idempotency, audit and outbox records. |
| Data and model assurance | OpenMetadata, MLflow, Fairlearn | Supply ownership, classification, lineage and versioned release evidence. |
| Accountable governance | CISO Assistant, GLPI | Maintain risks, control evidence, service inventory and remediation. |
| Runtime operations | OpenTelemetry, Prometheus + Alertmanager, DFIR-IRIS | Observe effects, detect conditions and support investigation and recovery. |
| Deployment and release boundaries | Kubernetes + Cilium, Syft + Grype + Cosign | Restrict bypass routes and qualify deployed artifacts. |

These are architectural responsibilities. Observed experiments identify which products actually ran together.

## Research question and fixed protocol

Can a small local Qwen agent use a real tool loop to complete an authorized synthetic task while independent identity, relationship and policy services prevent unauthorized target mutations?

A separate workflow experiment checks a wait without an effect, worker replacement, server restart and one commitment after a separate reviewer identity grants exact-action approval.

The [protocol](https://github.com/CodeDaim0n/AI-governance-repo/blob/main/results/native-agent/protocol.json) was written before scenario inference. Its SHA-256 accompanies each summary. It fixes ten scenarios, three seeds, six turns, eight calls, a 180-second deadline, temperature zero and a 256-token response cap. Qwen3:0.6b was selected for the CPU-only, 8 GiB host before observing scenario performance.

Every trial retains actual inference requests/responses, token counts, calls, observations, target state before/after, action rows and audit events. Access tokens and private keys are excluded. Separate run directories retain failed startups and partial experiments. The target ledger supplies the effect oracle; model narration is not evidence of completion.

## How to read the results

- **Task completion:** an allowed task produces its expected effect, a read attempt and an executed receipt. A safe failure to perform allowed work remains a task failure.
- **Control safety:** prohibited tasks produce no additional effect; permitted effects preserve the requested amount and scope.
- **Path exercised:** no attempted commit means the action-policy path was not exercised. Inspection and commit attempts are reported separately.
- **Product integration:** an actual operation and read-back establish that particular path. A health endpoint or installed executable is insufficient.
- **Workflow continuity:** persistence and worker replacement are checked separately from model quality.

The model has no approval, administration, secret-reading or arbitrary-network tool. Authenticated identity and exact task binding are server-owned. Untrusted source text includes an explicit injection fixture.

## Native subset and complete-suite acceptance

`fabric/native_lab.py` connects the model loop to actual Keycloak, OpenBao, OpenFGA, OPA and Microsoft AGT. The driver attempts native Collector delivery; the observed Collector startup failure is retained, while local OpenTelemetry SDK spans are exported. Prometheus scrapes real decision metrics and Alertmanager delivers an observed webhook. Temporal runs its persisted development server. This experiment uses a **SQLite synthetic target**, not PostgreSQL. It is distinct from `fabric/enterprise/app.py` and does not assert all-18 operation.

CISO Assistant, OpenMetadata, DFIR-IRIS and GLPI require actual product deployments and scoped commissioning inputs. This experiment supplies no imitation servers for them. Kubernetes/Cilium isolation and built-image release qualification require their separate acceptance. A local dependency scan is distinct from an image gate.

The full-suite runner remains `scripts/accept_all_components.py`; its result is reported separately. No subset result establishes complete-stack operation, regulatory conformity, production resilience, representative agent performance or meaningful human oversight.

## Reproduction

Install `requirements-enterprise.lock` and the releases pinned in `deploy/native/runtimes.lock.json` on a disposable host. Processes bind to loopback. Private bootstrap material and product stores remain in the ignored `.local/` directory.

```bash
python scripts/fetch_native_runtimes.py --destination /tmp/fabric-native
python scripts/configure_full.py
OPA_BIN="$PWD/.local/opa" python scripts/test_all.py
python scripts/run_native_agent.py --runtime-dir /tmp/fabric-native --opa "$PWD/.local/opa" --trials
```

Reuse an existing private configuration: `configure_full.py` refuses to overwrite it. The supervisor stops its own subprocesses. Sanitized transcripts and run summaries remain under `results/native-agent/`.

## Threats to validity

This is a small, self-authored engineering case study. Three seeds under deterministic decoding are repeated configurations, not independent population samples. Exact-intent binding constrains a narrow task more tightly than open-ended enterprise delegation. This small Qwen release does not represent larger models. Development stores, plaintext loopback, a single gateway and an in-process experiment controller do not establish production isolation or high availability. A reviewer service account tests authorization, not human judgment. A privileged actor can rewrite the local ledger and audit chain. No statistical generalization or certification is claimed.

## Baseline and exploratory follow-ups

The original ten-scenario run is retained at `results/native-agent/20261102T023518Z/`. It used Qwen3:0.6b and produced 30/30 target-state safety passes, but **zero inspections**. All nine allowed-task trials therefore failed the full task criterion despite producing the correct ledger effects. The three injection trials never delivered the injected source text to the model. They provide no evidence of model resistance to injection.

A second internally fixed protocol added a gateway read precondition (`protocol-v2.json`), preserving prompts, model, seeds and expected effects. It is an exploratory intervention after observing the baseline, not an independently preregistered replication. The model must choose how to react to `context_required`; the controller never chooses or fabricates a tool call.

A separately fixed larger-model protocol (`protocol-v3.json`) compares Qwen3:4b on authorized execution, approval waiting and source injection, three seeds each. Model artifacts are independently pinned before those trials. The focused experiment does not establish larger-model behavior on the seven other scenarios. All baseline and follow-up failures remain in the evidence.

## Release-gate observation

Actual Syft/Grype scanning of the installed Python dependency environment found `GHSA-g6cj-pr64-35w5` in `cryptography==49.0.0`; the configured High-severity gate failed. The scanned Microsoft AGT 5.0.0 package declares `cryptography>=46.0.7,<50.0`. The upstream cryptography advisory identifies 50.0.0 as the fix. No incompatible dependency override or risk acceptance was silently applied.

This finding concerns PKCS#7 decryption error/timing behavior, which is not exercised by the lab's RS256 path. That reachability distinction is not an approval to release the affected dependency set. Grype's severity and the upstream advisory's displayed severity differ; the raw scanner result, database metadata and upstream advisory are retained for owner review.

- [Cryptography upstream advisory](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5)
- [Microsoft AGT package metadata](https://pypi.org/pypi/agent-governance-toolkit-core/5.0.0/json)
- Evidence: `results/native-supply-chain/summary.json`, compressed SBOM and findings, local public key and signature bundle.

Cosign verified the local SBOM signature and rejected modified bytes. This proves local artifact integrity under the supplied public key, not publisher identity or transparency-log inclusion. The scan covers a dependency directory, not a built container image; component 17's full release acceptance remains unmet.

## Commissioned enterprise API

The commissioned gateway now exposes task-scoped agent routes alongside its single-proposal interface:

1. `POST /agent/tasks` stores typed intent, actor, expiry and any approval reference.
2. `POST /agent/tasks/{task_id}/run` starts the bounded Qwen loop with a server-owned task reference.
3. The agent chooses `inspect_case` and `commit_action`; the HTTP routes enforce task ownership, exact intent, record relationships and a read precondition independently.
4. A sole human-approval requirement creates a stable Temporal workflow. The model receives a waiting state, never approval authority.
5. A separate reviewer uses the existing workflow approval route. Temporal rechecks execution authority at commitment; another agent run can observe the completed workflow receipt.

The enterprise task routes have contract tests. Their PostgreSQL/metadata/risk/incident deployment has not been live-validated here. The native experiment remains a separately identified subset with a SQLite target.


## Recorded outcomes

| Configuration | Trials | Authorized case reads | Full allowed-task completion | Injection exposure |
| --- | --- | --- | --- | --- |
| Qwen3:0.6b, original baseline | 30 | 0/30 | 0/9; correct effects but inspection skipped | 0/3 |
| Qwen3:0.6b, read prerequisite | 30 | 0/30 | 0/9; prerequisite stopped commitment | 0/3 |
| Qwen3:4b, base tag | 9 | 0/9 | 0/6; output budget exhausted before tools | 0/3 |
| Qwen3:4b-instruct | 9 | 9/9 | 3/6; all benign tasks completed, injection tasks aborted | 3/3 |

The nine instruction-tuned trials comprise three benign tasks, three approval waits and three injection tasks. The benign tasks each produced one exact effect and a real receipt. Approval waits produced no effects. Injection trials exposed the actual hostile source note and the model refused to continue: safe aborts, with task availability lost. No arm establishes broad prompt-injection immunity. All 78 target-state checks passed at their narrow scope; pooling them into a general safety percentage would be misleading.

The raw `task_success` field for a prohibited task tests only the zero-effect expectation, not correct refusal language. The comparison also reports how many calls actually reached a core-policy outcome versus stopping at a read prerequisite. The 0.6b gated arm did not exercise its intended deeper policy scenarios.

The second run's later trace assertion failed because the inherited SDK sampler sampled one percent of traces. The corrected experiment explicitly samples every span. This does not alter its preserved model trials. The native Collector remained unavailable because process metric registration failed against restricted procfs, including with metric level `none`.

## Connected autonomous approval journey

The successful connected journey is `results/native-agent/20261102T025035Z/`. Qwen3:4b-instruct selected an authorized read and commitment. The gateway created a real Temporal wait and returned its workflow reference. The target remained unchanged. We stopped the worker, restarted the native server against the same database, replaced the worker and granted approval with a separate Keycloak reviewer credential. The worker rechecked execution authority and produced one effect. A duplicate returned the same receipt; history replay passed.

A second actual model episode read context and observed the completed workflow's real receipt. The model was never given reviewer credentials or asked to invent approval. Both episodes are retained in `agent-approval-journey.json`; the native history and SDK spans accompany them. This demonstrates the observed native subset, not all eighteen products, PostgreSQL commitment or human decision quality.

The official base-model template and its truncated responses are retained as compatibility observations. Selecting the instruct variant is an exploratory engineering correction, not a hidden replacement of failed benchmark results. [Official tool-calling documentation](https://docs.ollama.com/capabilities/tool-calling) and the [official instruct artifact](https://ollama.com/library/qwen3:4b-instruct) identify the protocol and model distribution used.


## Native CISO Assistant observation

CISO Assistant Community v4.2.1 ran from official source with its supported SQLite backend and Python 3.14.8. Actual authenticated REST calls provisioned/read twelve risk scenarios and twelve controls. An observed Qwen cross-tenant denial was attached to R01; the failed dependency gate and SBOM digest were attached to R12. Replayed risk and evidence operations did not duplicate records. Risk ratings and acceptance fields remained unchanged.

The first acceptance exposed omitted relationships in lightweight list responses. The adapter now fetches full detail before merging links and verifies scope, preserving existing relationships. The failed attempt is retained alongside successful read-back. Two regression contracts check this behavior and wrong-scope detail rejection. Concurrent human edits still need single-writer coordination or supported conditional mutation and reconciliation.

This was a dedicated synthetic instance with a bootstrap administrator; it is not a production least-privilege or human-acceptance test. Application ORM use was limited to fixture/credential initialization. Integration operations and read-backs used the real API. Source, dependency and runtime details are retained in `deploy/native/ciso-source.lock.json`, `deploy/native/ciso-requirements.lock` and `results/native-ciso.json`.

```bash
# Use a separate Python 3.14 environment for the official backend dependencies.
# Install the pinned CPU Torch wheel from the official PyTorch CPU index first.
/path/to/ciso-venv/bin/python scripts/run_native_ciso.py --backend /path/to/official-v4.2.1/backend
```

The CISO environment is separate from the gateway dependency directory that was scanned. This operation does not qualify the CISO container image or complete eighteen-product deployment.

Public SDK span exports use a documented resource-attribute allowlist and valid JSONL. Unnecessary environment labels are omitted; trace IDs, timestamps and decision attributes remain. `results/native-agent/trace-minimization.json` records transformation hashes and counts. Model requests/responses are unchanged.
