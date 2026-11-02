# Gateway API

The native gateway is `fabric.enterprise.app:app`. It exposes FastAPI's generated `/docs` and `/openapi.json` on the dedicated lab endpoint. These are available only after native commissioning; the core loopback server has a smaller interface.

## Authentication

Pass `Authorization: Bearer <Keycloak access token>`. Tokens must have the configured issuer, gateway audience, supported signing algorithm, valid lifetime and an explicitly mapped lab principal. Never send a private signing key or client secret in an action body.

## Operations

| Route | Authorized role | Behavior |
| --- | --- | --- |
| `POST /propose` | Mapped actor | Ask the local model for a schema-conforming proposal; reject changes to the caller's bounded intent. |
| `POST /execute` | Authorized agent | AGT interception, business policy, native authorities and transactional write/evidence. |
| `POST /approve` | Same-tenant independent reviewer | Create a short-lived exact-action approval reference. |
| `POST /workflows/start` | `agent-a` in this lab | Start a durable Temporal workflow under that worker's bounded delegation. |
| `POST /workflows/{id}/approve` | Authorized reviewer | Approve the stored immutable request and signal its reference to Temporal. |
| `POST /models/{version}/approve` | Reviewer | Exercise the synthetic model-release gate; record approval and expiry. |
| `POST /stop?stopped=true` | Administrator | Stop new writes. Earlier receipts remain retrievable. |
| `POST /alerts` | Dedicated Alertmanager bearer credential | Record a minimized alert for incident processing. Does not automatically grant stop authority. |
| `POST /lab/refresh-case?case_id=case-a` | Administrator, lab mode only | Refresh explicit synthetic evidence and increment its version. Disabled outside lab mode. |
| `GET /metrics` | Private monitoring network | Expose bounded-label operational metrics. |
| `GET /health` | Private lab network | Process liveness only; does not assert readiness of the full stack. |

## Execute example

```json
{
  "action": {
    "case_id": "case-a",
    "tool": "credit.commit",
    "amount_pence": 50000,
    "idempotency_key": "example-request-001"
  },
  "approval_id": null
}
```

Unknown action fields, Boolean/fractional money and unauthorized tools are rejected. The model cannot set tenant, KYC status, validation state, approval authority or budget.

## Outcomes and retries

A successful commit returns `status: executed` and an action receipt. A business restriction returns `status: denied` with a policy reason. Authentication, authorization, malformed requests and dependency/storage failures also use HTTP errors. Callers must inspect both HTTP status and the business result.

Retry a request with the same actor, tenant, idempotency key and unchanged payload. A matching earlier receipt is returned without another side effect. A changed payload with the same key is rejected. Production remote adapters must enforce the same idempotency semantics at the target, with conditional updates and reconciliation.

## Input and evidence privacy

Bodies and bearer tokens are excluded from runtime trace attributes. Events use minimized references and digests. These remain potentially sensitive and require retention and access controls; neither hashing nor dropping two trace fields provides anonymization or comprehensive DLP.

## Autonomous task execution

The native gateway provides `POST /agent/tasks` with the same action/approval schema as `/execute`, then `POST /agent/tasks/{task_id}/run` using the same authenticated actor. Task state is server-owned, expires after ten minutes and cannot be read by a different actor. Tool routes `/inspect` and `/agent/execute` require the caller's bearer token and an `X-Fabric-Task` header supplied by the agent driver, never by generated tool arguments.

The inspection route checks tenant and native OpenFGA access. The commitment route checks the exact stored intent and read precondition, then invokes the existing AGT/policy/target boundary. A sole approval requirement starts a stable Temporal workflow; it returns `waiting_approval` and a workflow reference. The existing reviewer route grants an exact-action approval. A subsequent agent run can observe the completed workflow receipt. Other denials remain denials.

`/propose` remains a separate one-shot proposal interface; it does not demonstrate autonomous execution. See the [agent experiment and evidence boundaries](research/native-agent.md).

`GET /agent/tasks/{task_id}` and the `execution` field returned by `/run` derive status from the bound target ledger receipt. A model claiming success without an effect is returned as `not_executed`; generated narrative is never promoted into authoritative execution status.
