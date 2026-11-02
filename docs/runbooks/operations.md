# Operations runbook

## Before a release

Name the business owner, risk owner, model validator, service operator and incident authority. Record intended scope, prohibited actions, product versions, dependency digests, applicable obligations, risk conditions and expiry. Require native acceptance plus independent validation; the lab's reviewer account is not a human sign-off.

## Policy or source unavailable

1. Preserve the deny result and dependency evidence. Never substitute a permissive local decision.
2. Check identity, OPA, OpenFGA, metadata, validation and inventory authorities in that order.
3. Use an approved manual business-service path if required by the impact tolerance.
4. Reconcile pending target outcomes before resuming. Retrying an uncertain business write is not a recovery procedure.

## Evidence or GRC delivery backlog

1. Inspect `fabric_outbox_pending` and per-sink receipts.
2. Restore the unavailable destination and retain undelivered events.
3. Search by stable external reference before repeating a request whose remote response was lost.
4. Reconcile duplicates or partial deliveries. The dispatcher is a single worker; concurrent dispatchers are not supported.
5. Apply the organization's defined restriction when backlog limits or evidence-export outage tolerance are exceeded.

## Suspected rogue agent or credential exposure

1. Use the authorized stop path to block new affected actions.
2. Revoke the specific workload credentials and relationships; stopping one process is insufficient.
3. Preserve approvals, source versions, target receipts and evidence anchors.
4. Open/correlate the incident and impacted risk records.
5. Identify completed, in-flight and uncertain target operations. Obtain authorized recovery decisions.

## OpenBao sealed or token expired

Do not bypass the secret store or copy privileged credentials into the agent. Use the approved unseal and renewal procedure. The lab issues 24-hour renewable role tokens; automated renewal is not implemented. Production recovery requires tested key custody, renewal, backup and restoration arrangements.

## Restore

Back up PostgreSQL, Temporal state, CISO Assistant, metadata/inventory systems, OpenBao and protected evidence stores according to agreed consistency and retention requirements. Test restoration in an isolated environment. Compare target state with action receipts and the outbox journal before allowing writes.

## Resume

Resume only after the incident authority and business/risk owners confirm remediation, reconciliation, validation validity and acceptable remaining exposure. Material policy, model, tool, source or permission changes require appropriate reassessment and approval invalidation.

## Lab stop

`python scripts/full_stack.py stop` preserves volumes. No automated destructive cleanup is supplied.

## Repeated acceptance runs

Each live acceptance run consumes the synthetic shared budget and creates auditable lab records. Do not erase the ledger to make a repeated test pass. Commission a new authorized lab window or instance while retaining the previous evidence.
