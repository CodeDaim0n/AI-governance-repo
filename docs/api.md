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
