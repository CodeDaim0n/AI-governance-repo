# 18. Ollama and Qwen

**Official product sources:** [Ollama](https://ollama.com/) · [Qwen model](https://huggingface.co/Qwen)

Local agent inference and bounded tool selection; observations drive the next step while the gateway independently authorizes effects.

## Role

Autonomous tool selection and observation processing without target or reviewer credentials.

## Implementation

- Autonomous agent loop: `fabric/agent.py`; native experiment gateway: `fabric/native_lab.py`.
- Single-proposal enterprise interface: `fabric/enterprise/clients.py`.
- Interface: `/api/pull`, `/api/chat` with native tools, and `/api/generate` for the separate proposal interface.
- Deployment: [full commissioning guide](../deployment/full-stack.md).
- Live acceptance: component `18` in `scripts/accept_all_components.py`.

## Acceptance operation

Run the actual model in a bounded tool loop, retain unmodified requests/responses, verify tool observations and check effects independently from model narration.

## Current evidence

See the [native agent experiment](../research/native-agent.md) and its per-trial transcripts. The complete eighteen-product acceptance remains separately recorded in `results/all-18-live.json`; a subset run does not establish that result.

## Authority and failure handling

Native service URLs and credentials are operator-controlled. Model output cannot nominate an endpoint, principal, source version or acceptance authority. An unavailable required authority must not become an allow. Side-effecting integrations use stable external references and delivery receipts; lost responses still require reconciliation.

## Release conditions

Qualify the chosen product release and license, test the exact deployed API, scope its identity and network permissions, exercise outages, and record the accountable owner. Demonstration settings do not establish production suitability.

## Configuration and deployment notes

`OLLAMA_URL and OLLAMA_MODEL`

The enterprise `/propose` endpoint returns one JSON proposal. The separate native agent experiment uses `/api/chat` tool calls and actual observations across model turns. The gateway rejects changes to caller-bounded intent and never accepts model-generated identity, source status, authority or approval.

[View implementation](https://github.com/CodeDaim0n/governed-agent-fabric/blob/main/fabric/enterprise/clients.py) · [All components](catalogue.md)
