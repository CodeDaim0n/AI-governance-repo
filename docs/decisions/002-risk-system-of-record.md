# ADR-002: CISO Assistant is the risk system of record

**Status:** accepted for the reference implementation.

## Context

Runtime detections are not risk acceptance decisions. Duplicate standalone registers lose ownership and traceability.

## Decision

Use stable risk references in CISO Assistant. Agents can propose risks and attach evidence; owner-approved ratings, residual exposure and acceptance remain protected human decisions. Existing enterprise GRC may replace this product through an equivalent contract.

## Consequences

Native credentials and an explicit dedicated assessment are required. API delivery needs deduplication, version protection and reconciliation. A passing technical check never silently closes a risk.
