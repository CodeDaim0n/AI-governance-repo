# ADR-004: explicit transaction and reconciliation boundary

**Status:** accepted for the lab; remote target integration remains deployment work.

## Context

A shared local database can atomically commit an action and its evidence. Independent remote products generally cannot join that transaction.

## Decision

Use one PostgreSQL transaction for the synthetic target, budget, approval consumption and outbox. Track delivery receipts per destination. Real business adapters must use target idempotency, expected versions, receipts and reconciliation; no global exactly-once promise is made.

## Consequences

The single dispatcher can still encounter a lost response after a remote write. Integration owners must reconcile by stable external reference and handle duplicates or uncertain outcomes. Local hash chains also require an external protection/anchoring design against privileged rewriting.
